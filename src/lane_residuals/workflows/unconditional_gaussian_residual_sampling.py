"""Strict v0.16.1 sampling from the stored v0.14 unconditional Gaussian."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.model_evaluation import build_leave_one_drive_out_folds
from ..domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    SequenceStandardizer,
)
from ..io.expanded_modeling_dataset import load_expanded_modeling_dataset
from ..io.expanded_sequence_dataset import read_json_object
from ..io.model_evaluation import load_expanded_gaussian_baseline
from ..io.reports import write_strict_json
from ..modeling.development_residual import DevelopmentResidualModel
from ..modeling.sequence_unconditional_gaussian import SequenceUnconditionalGaussian
from .development_residual_sampling import SAMPLES_FILENAME, SUMMARY_FILENAME
from .gaussian_planner_transfer_contract import (
    ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT,
    GAUSSIAN_SAMPLE_FILENAME,
    GAUSSIAN_SAMPLE_SUMMARY_FILENAME,
    GaussianPlannerTransferContract,
    VERSION,
)
from .reference_planner_sensitivity import SAMPLE_KEYS, SCENARIO_KEYS
from .sequence_contract import ensure_empty_output_directory, sha256_file

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]
StringArray = NDArray[np.str_]


def _load_npz(path: Path, expected_keys: frozenset[str]) -> dict[str, NDArray[Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != expected_keys:
                raise ValueError(
                    f"{path.name} keys must be exactly {sorted(expected_keys)}"
                )
            return {name: np.asarray(archive[name]) for name in archive.files}
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"invalid NPZ archive {path}: {error}") from error


def _string_array(value: NDArray[Any], label: str) -> StringArray:
    raw = np.asarray(value)
    if raw.dtype.kind not in {"U", "S"}:
        raise TypeError(f"{label} must use a string dtype")
    return np.asarray(raw, dtype=np.str_)


def _integer_array(value: NDArray[Any], label: str) -> IntegerArray:
    raw = np.asarray(value)
    if raw.dtype == np.bool_ or not np.issubdtype(raw.dtype, np.integer):
        raise TypeError(f"{label} must use an integer dtype")
    return np.asarray(raw, dtype=np.int64)


def _validate_scenario(
    path: Path,
    *,
    contract: GaussianPlannerTransferContract,
) -> tuple[FloatArray, IntegerArray, StringArray, FloatArray]:
    if sha256_file(path) != contract.scenario_sha256:
        raise ValueError("scenario archive differs from accepted v0.16 lineage")
    payload = _load_npz(path, SCENARIO_KEYS)
    conditions = np.asarray(payload["conditions"], dtype=np.float64)
    lengths = _integer_array(payload["lengths"], "scenario lengths")
    sequence_ids = _string_array(payload["sequence_ids"], "scenario sequence IDs")
    stations = np.asarray(payload["stations_m"], dtype=np.float64)
    paths = np.asarray(payload["nominal_paths_xy_m"], dtype=np.float64)
    timestamps = _integer_array(payload["timestamps_ns"], "scenario timestamps")
    features = tuple(
        _string_array(payload["feature_names"], "scenario feature names").tolist()
    )
    if features != BMW_CONDITION_FEATURE_NAMES:
        raise ValueError("scenario feature order differs from BMW schema v1")
    if conditions.ndim != 3 or conditions.shape[2] != len(features):
        raise ValueError("scenario conditions must have shape [B,T,6]")
    batch, maximum_time, _ = conditions.shape
    if lengths.shape != (batch,) or sequence_ids.shape != (batch,):
        raise ValueError("scenario identity arrays must have shape [B]")
    if paths.shape != (batch, maximum_time, 21, 2):
        raise ValueError("scenario paths must have shape [B,T,21,2]")
    if timestamps.shape != (batch, maximum_time):
        raise ValueError("scenario timestamps must have shape [B,T]")
    if stations.shape != (21,) or not np.array_equal(
        stations, np.arange(0.0, 101.0, 5.0)
    ):
        raise ValueError("scenario station grid differs from H100")
    if batch != contract.sequence_count or int(np.sum(lengths)) != contract.active_frame_count:
        raise ValueError("scenario counts differ from the v0.16.1 contract")
    if any(not item for item in sequence_ids.tolist()) or len(set(sequence_ids)) != batch:
        raise ValueError("scenario sequence IDs must be nonempty and unique")
    if np.any(lengths < 2) or np.any(lengths > maximum_time):
        raise ValueError("scenario sequence lengths are invalid")
    if not np.all(np.isfinite(conditions)) or not np.all(np.isfinite(paths)):
        raise ValueError("active scenario inputs must be finite")
    time_mask = np.arange(maximum_time)[None, :] < lengths[:, None]
    if np.any(conditions[~time_mask] != 0.0) or np.any(paths[~time_mask] != 0.0):
        raise ValueError("scenario float padding must be zero")
    for sequence_index, length in enumerate(lengths):
        active = int(length)
        if np.any(np.diff(timestamps[sequence_index, :active]) <= 0):
            raise ValueError("active timestamps must strictly increase per sequence")
        if np.any(timestamps[sequence_index, active:] != 0):
            raise ValueError("scenario timestamp padding must be zero")
    return conditions, lengths, sequence_ids, stations


def _validate_a2_samples(
    directory: Path,
    *,
    lengths: IntegerArray,
    sequence_ids: StringArray,
    stations: FloatArray,
    maximum_time: int,
    contract: GaussianPlannerTransferContract,
) -> tuple[FloatArray, Mapping[str, Any], Path, Path]:
    expected_files = {SAMPLES_FILENAME, SUMMARY_FILENAME}
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    if {path.name for path in directory.iterdir()} != expected_files:
        raise ValueError("accepted A2 sample directory filename set differs")
    sample_path = directory / SAMPLES_FILENAME
    summary_path = directory / SUMMARY_FILENAME
    if sha256_file(sample_path) != contract.a2_sample_sha256:
        raise ValueError("A2 residual samples differ from accepted v0.16 lineage")
    summary = read_json_object(summary_path)
    if (
        summary.get("version") != "0.15.4"
        or summary.get("status") != "complete"
        or summary.get("sample_file") != SAMPLES_FILENAME
        or summary.get("sample_file_sha256") != contract.a2_sample_sha256
        or summary.get("sample_count") != contract.sample_count
        or summary.get("random_seed") != contract.a2_sampling_seed
        or summary.get("sequence_count") != contract.sequence_count
        or summary.get("active_frame_count") != contract.active_frame_count
        or summary.get("sampling_is_free_running") is not True
        or summary.get("independent_frame_sampling_used") is not False
        or summary.get("development_model_file_sha256")
        != contract.development_model_sha256
        or summary.get("path_geometry_modified") is not False
        or summary.get("planner_executed") is not False
        or summary.get("final_model_selection_authorized") is not False
    ):
        raise ValueError("A2 residual sampling summary differs from v0.16.1 contract")
    payload = _load_npz(sample_path, SAMPLE_KEYS)
    residuals = np.asarray(payload["residual_samples_m"], dtype=np.float64)
    sample_lengths = _integer_array(payload["lengths"], "A2 sample lengths")
    sample_ids = _string_array(payload["sequence_ids"], "A2 sequence IDs")
    sample_stations = np.asarray(payload["stations_m"], dtype=np.float64)
    features = tuple(
        _string_array(payload["feature_names"], "A2 feature names").tolist()
    )
    expected_shape = (contract.sample_count, len(lengths), maximum_time, 21)
    if residuals.shape != expected_shape:
        raise ValueError("A2 residual sample shape differs from v0.16.1 contract")
    if features != BMW_CONDITION_FEATURE_NAMES:
        raise ValueError("A2 feature order differs from BMW schema v1")
    if not np.array_equal(sample_lengths, lengths) or not np.array_equal(
        sample_ids, sequence_ids
    ):
        raise ValueError("A2 and scenario sequence identities differ")
    if not np.array_equal(sample_stations, stations):
        raise ValueError("A2 and scenario stations differ")
    if not np.all(np.isfinite(residuals)):
        raise ValueError("A2 residual samples must be finite")
    time_mask = np.arange(residuals.shape[2])[None, :] < lengths[:, None]
    if np.any(residuals[:, ~time_mask] != 0.0):
        raise ValueError("A2 residual sample padding must be zero")
    return residuals, summary, sample_path, summary_path


def _load_gaussian_and_standardizer(
    *,
    dataset_directory: Path,
    gaussian_directory: Path,
) -> tuple[
    SequenceUnconditionalGaussian,
    SequenceStandardizer,
    Mapping[str, str],
    Mapping[str, str],
]:
    source = load_expanded_modeling_dataset(dataset_directory)
    folds = build_leave_one_drive_out_folds(
        source.sequences, primary_drive_ids=source.clean_drive_ids
    )
    _, _, gaussian_hashes = load_expanded_gaussian_baseline(
        gaussian_directory,
        source_files_sha256=source.source_files_sha256,
        folds=folds,
    )
    payload = read_json_object(gaussian_directory / "gaussian_grouped_models.json")
    if (
        payload.get("version") != "0.14.0"
        or payload.get("status") != "complete"
        or payload.get("purpose") != "drive_grouped_gaussian_fold_and_descriptive_models"
    ):
        raise ValueError("v0.14 Gaussian model bundle identity differs")
    models = payload.get("models")
    if not isinstance(models, Mapping) or set(models) != {
        "unconditional_gaussian",
        "conditional_gaussian",
    }:
        raise ValueError("v0.14 Gaussian model members differ")
    unconditional = models.get("unconditional_gaussian")
    if not isinstance(unconditional, Mapping):
        raise ValueError("v0.14 unconditional Gaussian member is missing")
    descriptive = unconditional.get("descriptive_all_clean_fit")
    if not isinstance(descriptive, Mapping) or set(descriptive) != {
        "role",
        "not_an_untouched_final_model",
        "standardizer",
        "fit_report",
        "model",
    }:
        raise ValueError("v0.14 descriptive all-clean payload differs")
    if (
        descriptive.get("role")
        != "fit_on_all_clean_development_drives_after_cross_validation"
        or descriptive.get("not_an_untouched_final_model") is not True
    ):
        raise ValueError("v0.14 descriptive fit authorization differs")
    standardizer_payload = descriptive.get("standardizer")
    model_payload = descriptive.get("model")
    if not isinstance(standardizer_payload, Mapping) or not isinstance(
        model_payload, Mapping
    ):
        raise ValueError("v0.14 descriptive model or standardizer is missing")
    standardizer = SequenceStandardizer.from_dict(standardizer_payload)
    model = SequenceUnconditionalGaussian.from_dict(dict(model_payload))
    if (
        standardizer.train_drive_ids != source.clean_drive_ids
        or standardizer.training_frame_count != source.primary.frame_count
        or model.fitted_model.n_training_samples != source.primary.frame_count
    ):
        raise ValueError("v0.14 descriptive all-clean training cohort differs")
    if model.temporal_dependency_order != 0:
        raise ValueError("v0.14 unconditional Gaussian must have temporal order zero")
    return model, standardizer, source.source_files_sha256, gaussian_hashes


def _standardizer_audit(
    gaussian: SequenceStandardizer,
    frozen: SequenceStandardizer,
) -> dict[str, Any]:
    arrays = {
        "stations_m": (
            np.asarray(gaussian.stations_m, dtype=np.float64),
            np.asarray(frozen.stations_m, dtype=np.float64),
        ),
        "residual_mean_m": (gaussian.residual_mean_m, frozen.residual_mean_m),
        "residual_scale_m": (gaussian.residual_scale_m, frozen.residual_scale_m),
    }
    discrepancies: dict[str, float] = {}
    for name, (left, right) in arrays.items():
        if left.shape != right.shape:
            raise ValueError(f"Gaussian and frozen {name} shapes differ")
        maximum = float(np.max(np.abs(left - right)))
        discrepancies[name] = maximum
        if not np.array_equal(left, right):
            raise ValueError(f"Gaussian and frozen {name} values differ")
    return {
        "comparison_dtype": "float64",
        "elementwise_exact_equal": True,
        "tolerance_based_acceptance_used": False,
        "maximum_absolute_discrepancy": discrepancies,
    }


def _marginal_diagnostics(
    a3: FloatArray,
    a2: FloatArray,
    lengths: IntegerArray,
    stations: FloatArray,
) -> list[dict[str, float]]:
    time_mask = np.arange(a3.shape[2])[None, :] < lengths[:, None]
    active_a3 = a3[:, time_mask]
    active_a2 = a2[:, time_mask]
    rows: list[dict[str, float]] = []
    for station_index, station in enumerate(stations):
        a3_values = active_a3[:, :, station_index].reshape(-1)
        a2_values = active_a2[:, :, station_index].reshape(-1)
        a3_mean = float(np.mean(a3_values))
        a2_mean = float(np.mean(a2_values))
        a3_sd = float(np.std(a3_values, ddof=0))
        a2_sd = float(np.std(a2_values, ddof=0))
        if a2_sd <= 0.0:
            raise ValueError("A2 station standard deviation must be positive")
        rows.append(
            {
                "station_m": float(station),
                "a3_mean_m": a3_mean,
                "a2_mean_m": a2_mean,
                "a3_minus_a2_mean_m": a3_mean - a2_mean,
                "a3_population_sd_m": a3_sd,
                "a2_population_sd_m": a2_sd,
                "a3_over_a2_population_sd_ratio": a3_sd / a2_sd,
            }
        )
    return rows


def run_unconditional_gaussian_residual_sampling(
    *,
    dataset_directory: Path,
    gaussian_directory: Path,
    development_model_path: Path,
    accepted_a2_sample_directory: Path,
    scenario_archive: Path,
    output_directory: Path,
    contract: GaussianPlannerTransferContract = (
        ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT
    ),
) -> tuple[dict[str, Any], int]:
    """Generate the fixed A3 ensemble without executing the planner."""

    conditions, lengths, sequence_ids, stations = _validate_scenario(
        scenario_archive, contract=contract
    )
    a2, a2_summary, a2_path, a2_summary_path = _validate_a2_samples(
        accepted_a2_sample_directory,
        lengths=lengths,
        sequence_ids=sequence_ids,
        stations=stations,
        maximum_time=conditions.shape[1],
        contract=contract,
    )
    model, gaussian_standardizer, dataset_hashes, gaussian_hashes = (
        _load_gaussian_and_standardizer(
            dataset_directory=dataset_directory,
            gaussian_directory=gaussian_directory,
        )
    )
    if sha256_file(development_model_path) != contract.development_model_sha256:
        raise ValueError("development model differs from accepted v0.15.4 lineage")
    development_model = DevelopmentResidualModel.load(development_model_path)
    frozen_standardizer = SequenceStandardizer.from_dict(
        development_model.metadata["standardizer"]
    )
    standardizer_audit = _standardizer_audit(
        gaussian_standardizer, frozen_standardizer
    )
    generated = model.sample(
        conditions,
        lengths,
        sample_count=contract.sample_count,
        seed=contract.gaussian_sampling_seed,
    )
    values_m = np.zeros_like(generated.values)
    time_mask = np.arange(conditions.shape[1])[None, :] < lengths[:, None]
    values_m[:, time_mask] = (
        generated.values[:, time_mask]
        * gaussian_standardizer.residual_scale_m[None, None, :]
        + gaussian_standardizer.residual_mean_m[None, None, :]
    )
    if not np.all(np.isfinite(values_m)) or np.any(values_m[:, ~time_mask] != 0.0):
        raise ValueError("generated A3 samples are non-finite or have nonzero padding")
    marginal_diagnostics = _marginal_diagnostics(values_m, a2, lengths, stations)

    ensure_empty_output_directory(output_directory)
    sample_path = output_directory / GAUSSIAN_SAMPLE_FILENAME
    np.savez_compressed(
        sample_path,
        residual_samples_m=values_m,
        lengths=lengths,
        stations_m=stations,
        sequence_ids=sequence_ids,
        feature_names=np.asarray(BMW_CONDITION_FEATURE_NAMES, dtype=np.str_),
    )
    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "unconditional_gaussian_planner_transfer_sampling",
        "arm": "unconditional_gaussian",
        "source_model_member": "unconditional_gaussian.descriptive_all_clean_fit",
        "source_fit_role": "fit_on_all_clean_development_drives_after_cross_validation",
        "source_fit_is_in_sample_all_clean_descriptive": True,
        "not_an_untouched_final_model": True,
        "dataset_files_sha256": dict(sorted(dataset_hashes.items())),
        "gaussian_files_sha256": dict(sorted(gaussian_hashes.items())),
        "development_model_sha256": sha256_file(development_model_path),
        "scenario_archive_sha256": sha256_file(scenario_archive),
        "accepted_a2_sample_file_sha256": sha256_file(a2_path),
        "accepted_a2_sample_summary_sha256": sha256_file(a2_summary_path),
        "accepted_a2_sampling_seed": a2_summary["random_seed"],
        "sample_file": GAUSSIAN_SAMPLE_FILENAME,
        "sample_file_sha256": sha256_file(sample_path),
        "sample_count": contract.sample_count,
        "random_seed": contract.gaussian_sampling_seed,
        "sequence_count": contract.sequence_count,
        "maximum_sequence_length": int(conditions.shape[1]),
        "active_frame_count": contract.active_frame_count,
        "feature_names_in_required_order": list(BMW_CONDITION_FEATURE_NAMES),
        "stations_m": [float(value) for value in stations],
        "residual_unit": "m",
        "temporal_dependency_order": 0,
        "active_frames_are_independent_draws": True,
        "spatial_cross_station_covariance_preserved": True,
        "sequence_state_used": False,
        "padding_is_exactly_zero": True,
        "common_random_numbers_with_a1_a2_used": False,
        "paired_residual_profiles_with_a1_a2_used": False,
        "standardizer_equality_audit": standardizer_audit,
        "marginal_diagnostics_by_station": marginal_diagnostics,
        "marginal_diagnostics_gate_execution": False,
        "marginal_similarity_threshold_predeclared": False,
        "planner_executed": False,
        "planner_benefit_claimed": False,
        "bmw_planner_behavior_claimed": False,
        "final_model_selection_authorized": False,
        "journey_level_generalization_estimated": False,
    }
    write_strict_json(output_directory / GAUSSIAN_SAMPLE_SUMMARY_FILENAME, summary)
    return summary, 0


__all__ = [
    "run_unconditional_gaussian_residual_sampling",
]
