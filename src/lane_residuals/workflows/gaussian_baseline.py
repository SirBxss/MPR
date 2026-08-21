"""Canonical residual export and drive-held-out Gaussian baseline workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    CanonicalResidualDataset,
    ResidualDatasetContractError,
    build_canonical_residual_dataset,
)
from ..domain.alignment_contract import (
    CURRENT_ALIGNMENT_VERSION,
    HISTORICAL_ALIGNMENT_PURPOSE,
    HISTORICAL_ALIGNMENT_VERSION,
    validate_native_projection_contract,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.gaussian import GaussianResidualModel, fit_gaussian_residual_model
from ..visualization.gaussian import plot_gaussian_baseline_diagnostics

VERSION = "0.6.0"
ACCEPTED_ALIGNMENT_VERSION = HISTORICAL_ALIGNMENT_VERSION
ACCEPTED_ALIGNMENT_PURPOSE = HISTORICAL_ALIGNMENT_PURPOSE
MARGINAL_95_QUANTILE = 1.959963984540054


def _read_strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def _read_csv(path: Path, *, required_fields: Sequence[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_fields = tuple(reader.fieldnames or ())
        missing = [field for field in required_fields if field not in actual_fields]
        if missing:
            raise ResidualDatasetContractError(
                f"{path.name} is missing required columns: {missing}"
            )
        return [dict(row) for row in reader]


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(
            f"output directory is not empty: {path}; use a new model directory"
        )
    path.mkdir(parents=True, exist_ok=True)


def _required_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResidualDatasetContractError(f"{name} must be a JSON object")
    return value


def _required_integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResidualDatasetContractError(f"{key} must be an integer")
    if value < 0:
        raise ResidualDatasetContractError(f"{key} must be nonnegative")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_alignment_metadata(
    input_directory: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    required_files = (
        "alignment_batch_summary.json",
        "batch_manifest.json",
        "alignment_pair_audit.csv",
        "alignment_station_comparison.csv",
    )
    for filename in required_files:
        path = input_directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"required alignment output not found: {path}")

    summary = _required_mapping(
        _read_strict_json(input_directory / "alignment_batch_summary.json"),
        name="alignment_batch_summary.json",
    )
    manifest = _required_mapping(
        _read_strict_json(input_directory / "batch_manifest.json"),
        name="batch_manifest.json",
    )
    contracts = []
    for name, payload in (("summary", summary), ("manifest", manifest)):
        contracts.append(
            validate_native_projection_contract(
                payload,
                name=name,
                error_type=ResidualDatasetContractError,
            )
        )
        if payload.get("status") != "complete":
            raise ResidualDatasetContractError(f"{name} status must be complete")
        if payload.get("blockers") != []:
            raise ResidualDatasetContractError(f"{name} blockers must be empty")
    if contracts[0] != contracts[1]:
        raise ResidualDatasetContractError(
            "alignment summary and manifest contracts do not match"
        )

    if contracts[0][0] == CURRENT_ALIGNMENT_VERSION:
        provenance_path = input_directory / "batch_output_provenance.json"
        if not provenance_path.is_file():
            raise FileNotFoundError(
                f"required v0.5.2 provenance output not found: {provenance_path}"
            )
        provenance = _required_mapping(
            _read_strict_json(provenance_path),
            name="batch_output_provenance.json",
        )
        validate_native_projection_contract(
            provenance,
            name="batch_output_provenance.json",
            error_type=ResidualDatasetContractError,
        )
        source_hashes = provenance.get("source_files_sha256")
        generated_hashes = provenance.get("generated_batch_outputs_sha256")
        required_source_hashes = {
            "drive_map_private_json",
            "corpus_inventory_summary.json",
            "recording_continuity.csv",
            "proposed_session_groups.json",
        }
        if not isinstance(source_hashes, Mapping) or set(source_hashes) != required_source_hashes:
            raise ResidualDatasetContractError(
                "v0.5.2 provenance source hashes are incomplete"
            )
        if summary.get("source_files_sha256") != source_hashes or manifest.get(
            "source_files_sha256"
        ) != source_hashes:
            raise ResidualDatasetContractError(
                "v0.5.2 source provenance does not reconcile"
            )
        expected_generated = {
            "recording_alignment_summary.csv",
            "alignment_pair_audit.csv",
            "alignment_station_comparison.csv",
            "alignment_batch_comparison.png",
            "alignment_batch_summary.json",
            "batch_manifest.json",
        }
        if not isinstance(generated_hashes, Mapping) or set(generated_hashes) != expected_generated:
            raise ResidualDatasetContractError(
                "v0.5.2 generated-output hashes are incomplete"
            )
        for filename, expected_hash in generated_hashes.items():
            if not isinstance(expected_hash, str) or _sha256(
                input_directory / filename
            ) != expected_hash:
                raise ResidualDatasetContractError(
                    f"v0.5.2 generated output hash mismatch: {filename}"
                )

    expected_grid = list(CANONICAL_MODEL_STATIONS_M)
    if summary.get("canonical_station_grid_m") != expected_grid:
        raise ResidualDatasetContractError(
            "alignment summary does not contain the immutable H100 station grid"
        )
    if manifest.get("canonical_station_grid_m") != expected_grid:
        raise ResidualDatasetContractError(
            "alignment manifest does not contain the immutable H100 station grid"
        )
    if summary.get("canonical_horizons_m") != [60, 100]:
        raise ResidualDatasetContractError("canonical horizons must be [60, 100]")
    if summary.get("h100_is_subset_of_h60") is not True:
        raise ResidualDatasetContractError("alignment summary must prove H100 ⊆ H60")
    if summary.get("spatial_reference_alignment_applied") is not True:
        raise ResidualDatasetContractError(
            "accepted alignment summary must record spatial projection/resampling"
        )
    if summary.get("explicit_ego_pose_motion_compensation_applied") is not False:
        raise ResidualDatasetContractError(
            "motion-compensated alignment is not accepted as v0.6.0 model input"
        )
    if summary.get("source_delta_used_numerically_for_alignment") is not False:
        raise ResidualDatasetContractError(
            "accepted projection alignment must not numerically warp by source delta"
        )
    if summary.get("drive_grouping_source") != "exact_private_basename_map":
        raise ResidualDatasetContractError(
            "drive grouping must come from the exact private basename map"
        )
    if manifest.get("drive_grouping_source") != "exact_private_basename_map":
        raise ResidualDatasetContractError(
            "manifest drive grouping must come from the exact private basename map"
        )

    raw_recordings = manifest.get("recordings")
    if not isinstance(raw_recordings, list) or not raw_recordings:
        raise ResidualDatasetContractError("manifest recordings must be nonempty")
    recording_drive_ids: dict[str, str] = {}
    basenames: set[str] = set()
    for raw_recording in raw_recordings:
        recording = _required_mapping(raw_recording, name="manifest recording")
        recording_id = str(recording.get("recording_id", "")).strip()
        drive_id = str(recording.get("drive_id", "")).strip()
        basename = str(recording.get("mcap_filename_private", "")).strip()
        if not recording_id or not drive_id or not basename:
            raise ResidualDatasetContractError(
                "each manifest recording needs recording_id, drive_id, and basename"
            )
        if recording.get("status") != "succeeded":
            raise ResidualDatasetContractError(
                f"manifest recording must have succeeded: {recording_id}"
            )
        if recording_id in recording_drive_ids:
            raise ResidualDatasetContractError(
                f"duplicate recording_id in manifest: {recording_id}"
            )
        if basename in basenames:
            raise ResidualDatasetContractError(
                f"MCAP basename appears more than once in manifest: {basename}"
            )
        recording_drive_ids[recording_id] = drive_id
        basenames.add(basename)

    if _required_integer(manifest, "expected_file_count") != len(raw_recordings):
        raise ResidualDatasetContractError(
            "manifest expected_file_count does not reconcile with recordings"
        )
    if _required_integer(manifest, "resolved_file_count") != len(raw_recordings):
        raise ResidualDatasetContractError(
            "manifest resolved_file_count does not reconcile with recordings"
        )
    if _required_integer(manifest, "successful_recording_count") != len(raw_recordings):
        raise ResidualDatasetContractError(
            "manifest successful_recording_count does not reconcile with recordings"
        )
    if _required_integer(summary, "resolved_file_count") != len(raw_recordings):
        raise ResidualDatasetContractError(
            "alignment resolved_file_count does not reconcile with manifest"
        )
    if _required_integer(summary, "successful_recording_count") != len(raw_recordings):
        raise ResidualDatasetContractError(
            "alignment successful_recording_count does not reconcile with manifest"
        )
    if _required_integer(summary, "failed_recording_count") != 0:
        raise ResidualDatasetContractError("accepted alignment must have zero failures")
    if _required_integer(summary, "drive_count") != len(set(recording_drive_ids.values())):
        raise ResidualDatasetContractError(
            "alignment drive_count does not reconcile with exact manifest"
        )
    return summary, manifest, recording_drive_ids


PAIR_REQUIRED_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "estimate_message_index",
    "map_message_index",
    "estimate_source_time_ns_private",
    "map_source_time_ns_private",
    "source_delta_ms",
    "pair_state",
    "failure_code",
    "h60_aligned_eligible",
    "h100_aligned_eligible",
)

STATION_REQUIRED_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "station_m",
    "aligned_lateral_m",
    "h100_aligned_eligible",
)


def load_accepted_residual_dataset(
    input_directory: Path,
) -> tuple[CanonicalResidualDataset, Mapping[str, Any], Mapping[str, Any]]:
    """Load and validate the accepted v0.5.0 batch without filename inference."""

    summary, manifest, recording_drive_ids = _validate_alignment_metadata(
        input_directory
    )
    pair_rows = _read_csv(
        input_directory / "alignment_pair_audit.csv",
        required_fields=PAIR_REQUIRED_FIELDS,
    )
    station_rows = _read_csv(
        input_directory / "alignment_station_comparison.csv",
        required_fields=STATION_REQUIRED_FIELDS,
    )
    dataset = build_canonical_residual_dataset(
        pair_rows,
        station_rows,
        recording_drive_ids=recording_drive_ids,
    )
    expected_h100 = _required_integer(summary, "h100_aligned_complete_pair_count")
    if len(dataset.observations) != expected_h100:
        raise ResidualDatasetContractError(
            "canonical vector count does not reconcile with H100 summary count"
        )
    return dataset, summary, manifest


EVALUATION_FIELDS = (
    "scope",
    "held_out_drive_id",
    "training_drive_ids",
    "training_vector_count",
    "test_vector_count",
    "dimension",
    "regularization_m2",
    "mean_joint_negative_log_likelihood",
    "mean_squared_mahalanobis",
    "mean_squared_mahalanobis_per_dimension",
    "pooled_mean_prediction_rmse_m",
    "mean_station_mean_prediction_rmse_m",
    "marginal_95_coverage",
    "training_covariance_condition_number",
)

STATION_EVALUATION_FIELDS = (
    "scope",
    "held_out_drive_id",
    "station_m",
    "test_vector_count",
    "mean_prediction_rmse_m",
    "mean_prediction_bias_m",
    "marginal_95_coverage",
)


def _evaluation_row(
    *,
    scope: str,
    held_out_drive_id: str | None,
    training_drive_ids: Sequence[str],
    training_vector_count: int | None,
    test_vector_count: int,
    regularization_m2: float,
    nll: np.ndarray,
    squared_mahalanobis: np.ndarray,
    differences_m: np.ndarray,
    coverage: np.ndarray,
    covariance_condition_number: float | None,
) -> dict[str, Any]:
    station_rmse = np.sqrt(np.mean(np.square(differences_m), axis=0))
    return {
        "scope": scope,
        "held_out_drive_id": held_out_drive_id,
        "training_drive_ids": ";".join(training_drive_ids),
        "training_vector_count": training_vector_count,
        "test_vector_count": test_vector_count,
        "dimension": differences_m.shape[1],
        "regularization_m2": regularization_m2,
        "mean_joint_negative_log_likelihood": float(np.mean(nll)),
        "mean_squared_mahalanobis": float(np.mean(squared_mahalanobis)),
        "mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared_mahalanobis) / differences_m.shape[1]
        ),
        "pooled_mean_prediction_rmse_m": float(
            np.sqrt(np.mean(np.square(differences_m)))
        ),
        "mean_station_mean_prediction_rmse_m": float(np.mean(station_rmse)),
        "marginal_95_coverage": float(np.mean(coverage)),
        "training_covariance_condition_number": covariance_condition_number,
    }


def _station_evaluation_rows(
    *,
    scope: str,
    held_out_drive_id: str | None,
    differences_m: np.ndarray,
    coverage: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, station in enumerate(CANONICAL_MODEL_STATIONS_M):
        differences = differences_m[:, index]
        rows.append(
            {
                "scope": scope,
                "held_out_drive_id": held_out_drive_id,
                "station_m": station,
                "test_vector_count": len(differences),
                "mean_prediction_rmse_m": float(
                    np.sqrt(np.mean(np.square(differences)))
                ),
                "mean_prediction_bias_m": float(np.mean(differences)),
                "marginal_95_coverage": float(np.mean(coverage[:, index])),
            }
        )
    return rows


def evaluate_leave_one_drive_out(
    dataset: CanonicalResidualDataset,
    *,
    regularization_m2: float,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[float]],
]:
    """Evaluate model generalization with each physical drive held out once."""

    matrix = dataset.matrix_m
    drives = np.asarray(dataset.drive_ids)
    unique_drives = sorted(set(dataset.drive_ids))
    if len(unique_drives) < 2:
        raise ResidualDatasetContractError(
            "drive-held-out evaluation requires at least two physical drives"
        )

    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    station_rmse_by_drive: dict[str, list[float]] = {}
    all_nll: list[np.ndarray] = []
    all_mahalanobis: list[np.ndarray] = []
    all_differences: list[np.ndarray] = []
    all_coverage: list[np.ndarray] = []
    for held_out_drive in unique_drives:
        test_mask = drives == held_out_drive
        train = matrix[~test_mask]
        test = matrix[test_mask]
        if len(train) < 2 or len(test) == 0:
            raise ResidualDatasetContractError(
                f"drive fold {held_out_drive} lacks train or test vectors"
            )
        model = fit_gaussian_residual_model(
            train,
            regularization=regularization_m2,
        )
        differences = test - model.mean
        standard_deviation = np.sqrt(np.diag(model.covariance))
        coverage = (
            np.abs(differences)
            <= MARGINAL_95_QUANTILE * standard_deviation[None, :]
        )
        nll = -model.logpdf(test)
        squared_mahalanobis = model.squared_mahalanobis(test)
        training_drives = sorted(set(drives[~test_mask].tolist()))
        evaluation_rows.append(
            _evaluation_row(
                scope="held_out_drive",
                held_out_drive_id=held_out_drive,
                training_drive_ids=training_drives,
                training_vector_count=len(train),
                test_vector_count=len(test),
                regularization_m2=regularization_m2,
                nll=nll,
                squared_mahalanobis=squared_mahalanobis,
                differences_m=differences,
                coverage=coverage,
                covariance_condition_number=float(np.linalg.cond(model.covariance)),
            )
        )
        fold_station_rows = _station_evaluation_rows(
            scope="held_out_drive",
            held_out_drive_id=held_out_drive,
            differences_m=differences,
            coverage=coverage,
        )
        station_rows.extend(fold_station_rows)
        station_rmse_by_drive[held_out_drive] = [
            float(row["mean_prediction_rmse_m"]) for row in fold_station_rows
        ]
        all_nll.append(nll)
        all_mahalanobis.append(squared_mahalanobis)
        all_differences.append(differences)
        all_coverage.append(coverage)

    combined_nll = np.concatenate(all_nll)
    combined_mahalanobis = np.concatenate(all_mahalanobis)
    combined_differences = np.vstack(all_differences)
    combined_coverage = np.vstack(all_coverage)
    evaluation_rows.append(
        _evaluation_row(
            scope="overall_cross_validated",
            held_out_drive_id=None,
            training_drive_ids=(),
            training_vector_count=None,
            test_vector_count=len(combined_differences),
            regularization_m2=regularization_m2,
            nll=combined_nll,
            squared_mahalanobis=combined_mahalanobis,
            differences_m=combined_differences,
            coverage=combined_coverage,
            covariance_condition_number=None,
        )
    )
    station_rows.extend(
        _station_evaluation_rows(
            scope="overall_cross_validated",
            held_out_drive_id=None,
            differences_m=combined_differences,
            coverage=combined_coverage,
        )
    )
    return evaluation_rows, station_rows, station_rmse_by_drive


def _dataset_summary(
    dataset: CanonicalResidualDataset,
    alignment_summary: Mapping[str, Any],
    input_directory: Path,
) -> dict[str, Any]:
    drive_counts = Counter(dataset.drive_ids)
    recording_counts = Counter(dataset.recording_ids)
    absolute_source_deltas = np.abs(
        np.asarray(
            [observation.source_delta_ms for observation in dataset.observations],
            dtype=np.float64,
        )
    )
    count = len(dataset.observations)
    alignment_source_files = [
        "alignment_batch_summary.json",
        "batch_manifest.json",
        "alignment_pair_audit.csv",
        "alignment_station_comparison.csv",
    ]
    if alignment_summary.get("version") == CURRENT_ALIGNMENT_VERSION:
        alignment_source_files.append("batch_output_provenance.json")
    return {
        "version": VERSION,
        "status": "complete",
        "purpose": "canonical_h100_residual_vector_export",
        "source_alignment_version": alignment_summary["version"],
        "source_alignment_purpose": alignment_summary["purpose"],
        "source_alignment_status": alignment_summary["status"],
        "source_files_sha256": {
            filename: _sha256(input_directory / filename)
            for filename in alignment_source_files
        },
        "residual_definition": (
            "EDP estimate minus aligned RLMB pseudo-reference, projected onto "
            "the pseudo-reference left normal"
        ),
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "canonical_horizon_m": 100,
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "vector_count": count,
        "station_observation_count": count * len(CANONICAL_MODEL_STATIONS_M),
        "station_pair_counts": {
            f"{int(station):03d}m": count
            for station in CANONICAL_MODEL_STATIONS_M
        },
        "constant_pair_count_at_every_station": True,
        "available_case_rows_used": False,
        "h100_is_subset_of_h60": True,
        "drive_grouping_source": "exact_private_basename_map",
        "drive_count": len(drive_counts),
        "vector_count_by_drive": dict(sorted(drive_counts.items())),
        "recording_count": len(recording_counts),
        "vector_count_by_recording": dict(sorted(recording_counts.items())),
        "timestamp_pairing_crosses_recording_boundaries": False,
        "median_absolute_source_delta_ms": float(np.median(absolute_source_deltas)),
        "timestamp_motion_compensation_applied": False,
        "timestamp_delta_decision": (
            "accepted as a documented modelling limitation; v0.5.1 odometry "
            "compensation is not a dataset prerequisite"
        ),
        "pair_count_is_independent_sample_size": False,
        "confidentiality": (
            "Residual vectors contain BMW-derived timestamps and measurements "
            "and must remain private."
        ),
    }


def _model_payload(
    model: GaussianResidualModel,
    dataset: CanonicalResidualDataset,
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "complete",
        "model_type": "unconditional_multivariate_gaussian",
        "fit_method": "maximum_likelihood_with_fixed_diagonal_regularization",
        "residual_units": "m",
        "covariance_units": "m^2",
        "residual_definition": (
            "EDP estimate minus aligned RLMB pseudo-reference, projected onto "
            "the pseudo-reference left normal"
        ),
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "stations_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": model.dimension,
        "n_training_vectors": model.n_training_samples,
        "training_drive_ids": sorted(set(dataset.drive_ids)),
        "regularization_m2": model.regularization,
        "mean_m": model.mean.tolist(),
        "covariance_m2": model.covariance.tolist(),
        "marginal_standard_deviation_m": np.sqrt(
            np.diag(model.covariance)
        ).tolist(),
        "training_covariance_condition_number": float(
            np.linalg.cond(model.covariance)
        ),
        "intended_use": (
            "descriptive unconditional baseline and spatially correlated "
            "residual sampler for the accepted corpus"
        ),
        "not_for": (
            "claiming independent physical ground truth, temporal independence, "
            "or generalization beyond the audited operating situation"
        ),
    }


def run_gaussian_baseline(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Validate accepted alignment evidence, export vectors, and fit/evaluate."""

    if (
        not math.isfinite(arguments.regularization_m2)
        or arguments.regularization_m2 <= 0.0
    ):
        raise ValueError("regularization-m2 must be finite and positive")
    dataset, alignment_summary, _manifest = load_accepted_residual_dataset(
        arguments.alignment_batch_directory
    )
    _ensure_empty_output(arguments.output_directory)

    write_csv_rows(
        arguments.output_directory / "residual_vectors.csv",
        RESIDUAL_VECTOR_FIELDS,
        (observation.as_csv_row() for observation in dataset.observations),
    )
    dataset_summary = _dataset_summary(
        dataset,
        alignment_summary,
        arguments.alignment_batch_directory,
    )
    write_strict_json(
        arguments.output_directory / "residual_dataset_summary.json",
        dataset_summary,
    )

    evaluation_rows, station_evaluation_rows, station_rmse_by_drive = (
        evaluate_leave_one_drive_out(
            dataset,
            regularization_m2=arguments.regularization_m2,
        )
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_station_evaluation.csv",
        STATION_EVALUATION_FIELDS,
        station_evaluation_rows,
    )

    final_model = fit_gaussian_residual_model(
        dataset.matrix_m,
        regularization=arguments.regularization_m2,
    )
    write_strict_json(
        arguments.output_directory / "gaussian_model.json",
        _model_payload(final_model, dataset),
    )
    plot_gaussian_baseline_diagnostics(
        arguments.output_directory / "gaussian_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        residual_matrix_m=dataset.matrix_m,
        model=final_model,
        held_out_station_rmse_m=station_rmse_by_drive,
    )

    overall_evaluation = next(
        row for row in evaluation_rows if row["scope"] == "overall_cross_validated"
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "drive_held_out_unconditional_gaussian_baseline",
        "model_type": "unconditional_multivariate_gaussian",
        "evaluation_scheme": "leave_one_physical_drive_out",
        "evaluation_fold_count": len(set(dataset.drive_ids)),
        "final_model_fit_after_evaluation": True,
        "final_model_training_vector_count": len(dataset.observations),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "regularization_m2": arguments.regularization_m2,
        "cross_validated_test_vector_count": overall_evaluation["test_vector_count"],
        "cross_validated_mean_joint_negative_log_likelihood": overall_evaluation[
            "mean_joint_negative_log_likelihood"
        ],
        "cross_validated_mean_squared_mahalanobis_per_dimension": (
            overall_evaluation["mean_squared_mahalanobis_per_dimension"]
        ),
        "cross_validated_pooled_mean_prediction_rmse_m": overall_evaluation[
            "pooled_mean_prediction_rmse_m"
        ],
        "cross_validated_mean_station_mean_prediction_rmse_m": overall_evaluation[
            "mean_station_mean_prediction_rmse_m"
        ],
        "cross_validated_marginal_95_coverage": overall_evaluation[
            "marginal_95_coverage"
        ],
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "timestamp_motion_compensation_required": False,
        "pair_count_is_independent_sample_size": False,
        "scientific_limitations": [
            "RLMB is a pseudo-reference, not independent physical ground truth.",
            "The median source-time mismatch is retained as small label noise.",
            "Sequential path pairs are correlated; vector count is not an independent sample size.",
            "Only two physical drives are available for held-out evaluation.",
            "The unconditional Gaussian cannot represent situation-dependent or multimodal errors.",
        ],
        "confidentiality": (
            "Model and evaluation outputs are derived from private BMW measurements."
        ),
    }
    write_strict_json(
        arguments.output_directory / "gaussian_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "ACCEPTED_ALIGNMENT_VERSION",
    "EVALUATION_FIELDS",
    "STATION_EVALUATION_FIELDS",
    "VERSION",
    "evaluate_leave_one_drive_out",
    "load_accepted_residual_dataset",
    "run_gaussian_baseline",
]
