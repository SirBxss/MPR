"""Fail-closed v0.6.1 adequacy diagnostics for a v0.6.0 Gaussian baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    CanonicalResidualDataset,
    ResidualDatasetContractError,
    ResidualObservation,
    residual_column_name,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.gaussian import GaussianResidualModel, fit_gaussian_residual_model
from ..modeling.gaussian_diagnostics import (
    chi_square_cdf,
    chi_square_quantile,
    leave_one_group_out_gaussian_predictions,
    marginal_calibration_statistics,
    multivariate_calibration_statistics,
    standard_normal_two_sided_quantile,
)
from ..visualization.gaussian_diagnostics import (
    plot_gaussian_marginal_adequacy,
    plot_gaussian_multivariate_adequacy,
)

VERSION = "0.6.1"
ACCEPTED_BASELINE_VERSION = "0.6.0"
ACCEPTED_BASELINE_PURPOSE = "drive_held_out_unconditional_gaussian_baseline"
ACCEPTED_DATASET_PURPOSE = "canonical_h100_residual_vector_export"


def _read_strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def _required_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResidualDatasetContractError(f"{name} must be a JSON object")
    return value


def _required_integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResidualDatasetContractError(f"{key} must be a nonnegative integer")
    return value


def _required_finite_float(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool):
        raise ResidualDatasetContractError(f"{key} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ResidualDatasetContractError(f"{key} must be numeric") from error
    if not math.isfinite(result):
        raise ResidualDatasetContractError(f"{key} must be finite")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(
            f"output directory is not empty: {path}; use a new diagnostic directory"
        )
    path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class GaussianBaselineArtifacts:
    """Validated v0.6.0 vectors, final model, and source summaries."""

    dataset: CanonicalResidualDataset
    final_model: GaussianResidualModel
    dataset_summary: Mapping[str, Any] = field(repr=False)
    gaussian_summary: Mapping[str, Any] = field(repr=False)


def _load_residual_vectors(path: Path) -> CanonicalResidualDataset:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(RESIDUAL_VECTOR_FIELDS):
            raise ResidualDatasetContractError(
                "residual_vectors.csv header does not match the canonical v0.6.0 contract"
            )
        rows = list(reader)
    observations: list[ResidualObservation] = []
    residual_fields = [
        residual_column_name(station) for station in CANONICAL_MODEL_STATIONS_M
    ]
    for row_number, row in enumerate(rows, start=2):
        try:
            observation = ResidualObservation(
                recording_id=str(row["recording_id"]).strip(),
                drive_id=str(row["drive_id"]).strip(),
                pair_index=int(row["pair_index"]),
                estimate_message_index=int(row["estimate_message_index"]),
                map_message_index=int(row["map_message_index"]),
                estimate_source_time_ns_private=int(
                    row["estimate_source_time_ns_private"]
                ),
                map_source_time_ns_private=int(row["map_source_time_ns_private"]),
                source_delta_ms=float(row["source_delta_ms"]),
                residuals_m=np.asarray(
                    [float(row[field]) for field in residual_fields],
                    dtype=np.float64,
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ResidualDatasetContractError(
                f"invalid canonical residual vector at CSV row {row_number}: {error}"
            ) from error
        observations.append(observation)
    try:
        return CanonicalResidualDataset(tuple(observations))
    except ValueError as error:
        raise ResidualDatasetContractError(str(error)) from error


def load_gaussian_baseline_artifacts(
    input_directory: Path,
) -> GaussianBaselineArtifacts:
    """Validate and load only the exact current v0.6.0 baseline contract."""

    required_files = (
        "residual_vectors.csv",
        "residual_dataset_summary.json",
        "gaussian_model.json",
        "gaussian_summary.json",
    )
    for filename in required_files:
        path = input_directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"required Gaussian baseline output not found: {path}")

    dataset_summary = _required_mapping(
        _read_strict_json(input_directory / "residual_dataset_summary.json"),
        name="residual_dataset_summary.json",
    )
    gaussian_summary = _required_mapping(
        _read_strict_json(input_directory / "gaussian_summary.json"),
        name="gaussian_summary.json",
    )
    model_payload = _required_mapping(
        _read_strict_json(input_directory / "gaussian_model.json"),
        name="gaussian_model.json",
    )

    if dataset_summary.get("version") != ACCEPTED_BASELINE_VERSION:
        raise ResidualDatasetContractError("dataset summary version must be 0.6.0")
    if dataset_summary.get("status") != "complete":
        raise ResidualDatasetContractError("dataset summary status must be complete")
    if dataset_summary.get("purpose") != ACCEPTED_DATASET_PURPOSE:
        raise ResidualDatasetContractError("dataset summary purpose is not canonical H100")
    if dataset_summary.get("canonical_station_grid_m") != list(
        CANONICAL_MODEL_STATIONS_M
    ):
        raise ResidualDatasetContractError("dataset station grid is not canonical H100")
    if dataset_summary.get("constant_pair_count_at_every_station") is not True:
        raise ResidualDatasetContractError("dataset must have constant station denominators")
    if dataset_summary.get("available_case_rows_used") is not False:
        raise ResidualDatasetContractError("available-case model inputs are forbidden")
    if dataset_summary.get("drive_grouping_source") != "exact_private_basename_map":
        raise ResidualDatasetContractError("drive grouping must come from exact manifest")

    if gaussian_summary.get("version") != ACCEPTED_BASELINE_VERSION:
        raise ResidualDatasetContractError("Gaussian summary version must be 0.6.0")
    if gaussian_summary.get("status") != "complete":
        raise ResidualDatasetContractError("Gaussian summary status must be complete")
    if gaussian_summary.get("purpose") != ACCEPTED_BASELINE_PURPOSE:
        raise ResidualDatasetContractError("Gaussian summary purpose is not accepted")
    if gaussian_summary.get("evaluation_scheme") != "leave_one_physical_drive_out":
        raise ResidualDatasetContractError("baseline evaluation must be drive-held-out")
    if model_payload.get("version") != ACCEPTED_BASELINE_VERSION:
        raise ResidualDatasetContractError("Gaussian model version must be 0.6.0")
    if model_payload.get("status") != "complete":
        raise ResidualDatasetContractError("Gaussian model status must be complete")
    if model_payload.get("model_type") != "unconditional_multivariate_gaussian":
        raise ResidualDatasetContractError("unexpected Gaussian model type")
    if model_payload.get("stations_m") != list(CANONICAL_MODEL_STATIONS_M):
        raise ResidualDatasetContractError("Gaussian model station grid is not H100")

    dataset = _load_residual_vectors(input_directory / "residual_vectors.csv")
    vector_count = len(dataset.observations)
    if _required_integer(dataset_summary, "vector_count") != vector_count:
        raise ResidualDatasetContractError("dataset vector count does not reconcile")
    if _required_integer(model_payload, "n_training_vectors") != vector_count:
        raise ResidualDatasetContractError("model training count does not reconcile")
    if _required_integer(gaussian_summary, "final_model_training_vector_count") != vector_count:
        raise ResidualDatasetContractError("Gaussian summary training count does not reconcile")
    if _required_integer(model_payload, "dimension") != len(CANONICAL_MODEL_STATIONS_M):
        raise ResidualDatasetContractError("Gaussian model dimension must be 21")
    if _required_integer(gaussian_summary, "dimension") != len(
        CANONICAL_MODEL_STATIONS_M
    ):
        raise ResidualDatasetContractError("Gaussian summary dimension must be 21")

    regularization = _required_finite_float(model_payload, "regularization_m2")
    if regularization <= 0.0:
        raise ResidualDatasetContractError("model regularization must be positive")
    if not math.isclose(
        _required_finite_float(gaussian_summary, "regularization_m2"),
        regularization,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise ResidualDatasetContractError("summary/model regularization mismatch")
    try:
        final_model = GaussianResidualModel(
            mean=model_payload.get("mean_m"),
            covariance=model_payload.get("covariance_m2"),
            n_training_samples=vector_count,
            regularization=regularization,
        )
    except (TypeError, ValueError) as error:
        raise ResidualDatasetContractError(f"invalid Gaussian model: {error}") from error
    refit = fit_gaussian_residual_model(
        dataset.matrix_m,
        regularization=regularization,
    )
    if not np.allclose(refit.mean, final_model.mean, rtol=1e-12, atol=1e-12):
        raise ResidualDatasetContractError("stored Gaussian mean does not match vectors")
    if not np.allclose(
        refit.covariance,
        final_model.covariance,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise ResidualDatasetContractError("stored Gaussian covariance does not match vectors")

    actual_drive_counts = {
        drive_id: dataset.drive_ids.count(drive_id)
        for drive_id in sorted(set(dataset.drive_ids))
    }
    if dataset_summary.get("vector_count_by_drive") != actual_drive_counts:
        raise ResidualDatasetContractError("drive vector counts do not reconcile")
    actual_recording_counts = {
        recording_id: dataset.recording_ids.count(recording_id)
        for recording_id in sorted(set(dataset.recording_ids))
    }
    if dataset_summary.get("vector_count_by_recording") != actual_recording_counts:
        raise ResidualDatasetContractError("recording vector counts do not reconcile")
    if _required_integer(dataset_summary, "drive_count") != len(actual_drive_counts):
        raise ResidualDatasetContractError("dataset drive count does not reconcile")
    if _required_integer(dataset_summary, "recording_count") != len(
        actual_recording_counts
    ):
        raise ResidualDatasetContractError("dataset recording count does not reconcile")
    station_counts = dataset_summary.get("station_pair_counts")
    expected_station_counts = {
        f"{int(station):03d}m": vector_count
        for station in CANONICAL_MODEL_STATIONS_M
    }
    if station_counts != expected_station_counts:
        raise ResidualDatasetContractError("station pair counts are not constant")
    return GaussianBaselineArtifacts(
        dataset=dataset,
        final_model=final_model,
        dataset_summary=dataset_summary,
        gaussian_summary=gaussian_summary,
    )


VECTOR_DIAGNOSTIC_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "squared_mahalanobis",
    "squared_mahalanobis_per_dimension",
    "chi_square_cdf",
    "chi_square_upper_tail_probability",
    "joint_negative_log_likelihood",
    "above_chi_square_p95",
    "above_chi_square_p99",
)

MARGINAL_DIAGNOSTIC_FIELDS = (
    "scope_type",
    "scope_id",
    "station_m",
    "vector_count",
    "standardized_mean",
    "standardized_std",
    "skewness",
    "excess_kurtosis",
    "normal_qq_correlation",
    "empirical_p01",
    "empirical_p05",
    "empirical_p50",
    "empirical_p95",
    "empirical_p99",
    "coverage_50",
    "coverage_80",
    "coverage_90",
    "coverage_95",
    "coverage_99",
    "lower_tail_exceedance_95",
    "upper_tail_exceedance_95",
)

MULTIVARIATE_DIAGNOSTIC_FIELDS = (
    "scope_type",
    "scope_id",
    "vector_count",
    "dimension",
    "mean_joint_negative_log_likelihood",
    "mean_squared_mahalanobis",
    "mean_squared_mahalanobis_per_dimension",
    "chi_square_pit_mean",
    "chi_square_pit_ks_distance",
    "chi_square_qq_correlation",
    "chi_square_expected_p50",
    "empirical_mahalanobis_p50",
    "chi_square_expected_p90",
    "empirical_mahalanobis_p90",
    "above_chi_square_p90_rate",
    "chi_square_expected_p95",
    "empirical_mahalanobis_p95",
    "above_chi_square_p95_rate",
    "chi_square_expected_p99",
    "empirical_mahalanobis_p99",
    "above_chi_square_p99_rate",
)


def _scope_masks(drive_ids: Sequence[str]) -> list[tuple[str, str, np.ndarray]]:
    drives = np.asarray(drive_ids)
    scopes = [
        ("drive", drive_id, drives == drive_id)
        for drive_id in sorted(set(drive_ids))
    ]
    scopes.append(("overall", "all_drives", np.ones(len(drives), dtype=bool)))
    return scopes


def _validate_against_baseline_summary(
    artifacts: GaussianBaselineArtifacts,
    *,
    standardized_errors: np.ndarray,
    squared_mahalanobis: np.ndarray,
    joint_negative_log_likelihood: np.ndarray,
) -> None:
    summary = artifacts.gaussian_summary
    dimension = standardized_errors.shape[1]
    coverage_95 = float(
        np.mean(
            np.abs(standardized_errors)
            <= standard_normal_two_sided_quantile(0.95)
        )
    )
    expected = {
        "cross_validated_marginal_95_coverage": coverage_95,
        "cross_validated_mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared_mahalanobis) / dimension
        ),
        "cross_validated_mean_joint_negative_log_likelihood": float(
            np.mean(joint_negative_log_likelihood)
        ),
    }
    for key, value in expected.items():
        reported = _required_finite_float(summary, key)
        if not math.isclose(reported, value, rel_tol=1e-12, abs_tol=1e-12):
            raise ResidualDatasetContractError(
                f"recomputed out-of-drive metric disagrees with {key}"
            )


def run_gaussian_diagnostics(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Recompute held-out predictions and export Gaussian adequacy evidence."""

    artifacts = load_gaussian_baseline_artifacts(arguments.gaussian_baseline_directory)
    dataset = artifacts.dataset
    matrix = dataset.matrix_m
    predictions = leave_one_group_out_gaussian_predictions(
        matrix,
        dataset.drive_ids,
        regularization=artifacts.final_model.regularization,
    )
    _validate_against_baseline_summary(
        artifacts,
        standardized_errors=predictions.standardized_marginal_errors,
        squared_mahalanobis=predictions.squared_mahalanobis,
        joint_negative_log_likelihood=predictions.joint_negative_log_likelihood,
    )
    _ensure_empty_output(arguments.output_directory)

    dimension = matrix.shape[1]
    chi_square_p95 = chi_square_quantile(0.95, degrees_of_freedom=dimension)
    chi_square_p99 = chi_square_quantile(0.99, degrees_of_freedom=dimension)
    vector_rows: list[dict[str, Any]] = []
    for index, observation in enumerate(dataset.observations):
        squared = float(predictions.squared_mahalanobis[index])
        cdf = chi_square_cdf(squared, degrees_of_freedom=dimension)
        vector_rows.append(
            {
                "recording_id": observation.recording_id,
                "drive_id": observation.drive_id,
                "pair_index": observation.pair_index,
                "squared_mahalanobis": squared,
                "squared_mahalanobis_per_dimension": squared / dimension,
                "chi_square_cdf": cdf,
                "chi_square_upper_tail_probability": 1.0 - cdf,
                "joint_negative_log_likelihood": float(
                    predictions.joint_negative_log_likelihood[index]
                ),
                "above_chi_square_p95": squared > chi_square_p95,
                "above_chi_square_p99": squared > chi_square_p99,
            }
        )
    write_csv_rows(
        arguments.output_directory / "gaussian_vector_diagnostics.csv",
        VECTOR_DIAGNOSTIC_FIELDS,
        vector_rows,
    )

    marginal_rows: list[dict[str, Any]] = []
    multivariate_rows: list[dict[str, Any]] = []
    scopes = _scope_masks(dataset.drive_ids)
    for scope_type, scope_id, mask in scopes:
        for station_index, station in enumerate(CANONICAL_MODEL_STATIONS_M):
            row = {
                "scope_type": scope_type,
                "scope_id": scope_id,
                "station_m": station,
            }
            row.update(
                marginal_calibration_statistics(
                    predictions.standardized_marginal_errors[mask, station_index]
                )
            )
            marginal_rows.append(row)
        multivariate_row = {
            "scope_type": scope_type,
            "scope_id": scope_id,
        }
        multivariate_row.update(
            multivariate_calibration_statistics(
                predictions.squared_mahalanobis[mask],
                predictions.joint_negative_log_likelihood[mask],
                dimension=dimension,
            )
        )
        multivariate_rows.append(multivariate_row)
    write_csv_rows(
        arguments.output_directory / "gaussian_marginal_diagnostics.csv",
        MARGINAL_DIAGNOSTIC_FIELDS,
        marginal_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_multivariate_diagnostics.csv",
        MULTIVARIATE_DIAGNOSTIC_FIELDS,
        multivariate_rows,
    )

    plot_gaussian_marginal_adequacy(
        arguments.output_directory / "gaussian_marginal_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        standardized_errors=predictions.standardized_marginal_errors,
        drive_ids=dataset.drive_ids,
    )
    plot_gaussian_multivariate_adequacy(
        arguments.output_directory / "gaussian_multivariate_diagnostics.png",
        squared_mahalanobis=predictions.squared_mahalanobis,
        drive_ids=dataset.drive_ids,
        dimension=dimension,
    )

    overall_marginal = [
        row for row in marginal_rows if row["scope_type"] == "overall"
    ]
    overall_multivariate = next(
        row for row in multivariate_rows if row["scope_type"] == "overall"
    )
    drive_masks = [scope for scope in scopes if scope[0] == "drive"]
    drive_coverage_95 = {
        scope_id: float(
            np.mean(
                np.abs(predictions.standardized_marginal_errors[mask])
                <= standard_normal_two_sided_quantile(0.95)
            )
        )
        for _, scope_id, mask in drive_masks
    }
    largest_skewness = max(overall_marginal, key=lambda row: abs(row["skewness"]))
    largest_kurtosis = max(
        overall_marginal,
        key=lambda row: abs(row["excess_kurtosis"]),
    )
    source_names = (
        "residual_vectors.csv",
        "residual_dataset_summary.json",
        "gaussian_model.json",
        "gaussian_summary.json",
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "drive_held_out_gaussian_adequacy_diagnostics",
        "source_baseline_version": ACCEPTED_BASELINE_VERSION,
        "source_files_sha256": {
            filename: _sha256(arguments.gaussian_baseline_directory / filename)
            for filename in source_names
        },
        "evaluation_scheme": "leave_one_physical_drive_out",
        "vector_count": len(dataset.observations),
        "drive_count": len(set(dataset.drive_ids)),
        "dimension": dimension,
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "regularization_m2": artifacts.final_model.regularization,
        "overall_pooled_marginal_95_coverage": float(
            np.mean(
                np.abs(predictions.standardized_marginal_errors)
                <= standard_normal_two_sided_quantile(0.95)
            )
        ),
        "pooled_marginal_95_coverage_by_drive": drive_coverage_95,
        "maximum_drive_coverage_95_gap": (
            max(drive_coverage_95.values()) - min(drive_coverage_95.values())
        ),
        "minimum_station_marginal_95_coverage": float(
            min(row["coverage_95"] for row in overall_marginal)
        ),
        "minimum_coverage_station_m": float(
            min(overall_marginal, key=lambda row: row["coverage_95"])["station_m"]
        ),
        "largest_absolute_skewness": float(abs(largest_skewness["skewness"])),
        "largest_absolute_skewness_station_m": float(
            largest_skewness["station_m"]
        ),
        "largest_absolute_excess_kurtosis": float(
            abs(largest_kurtosis["excess_kurtosis"])
        ),
        "largest_absolute_excess_kurtosis_station_m": float(
            largest_kurtosis["station_m"]
        ),
        "overall_mean_squared_mahalanobis_per_dimension": float(
            overall_multivariate["mean_squared_mahalanobis_per_dimension"]
        ),
        "overall_chi_square_pit_ks_distance": float(
            overall_multivariate["chi_square_pit_ks_distance"]
        ),
        "overall_above_chi_square_p95_rate": float(
            overall_multivariate["above_chi_square_p95_rate"]
        ),
        "overall_above_chi_square_p99_rate": float(
            overall_multivariate["above_chi_square_p99_rate"]
        ),
        "expected_above_chi_square_p95_rate": 0.05,
        "expected_above_chi_square_p99_rate": 0.01,
        "formal_iid_normality_test_performed": False,
        "formal_test_reason": (
            "Sequential pairs are correlated, so conventional iid normality "
            "p-values would be misleading."
        ),
        "adequacy_thresholds_predeclared": False,
        "adequacy_decision": "diagnostic_complete_no_acceptance_gate",
        "next_decision": (
            "Review tail shape and between-drive calibration before choosing a "
            "conditional Gaussian, mixture model, or sequential model."
        ),
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "pair_count_is_independent_sample_size": False,
        "confidentiality": (
            "Diagnostics contain or derive from private BMW residual measurements."
        ),
    }
    write_strict_json(
        arguments.output_directory / "gaussian_adequacy_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "ACCEPTED_BASELINE_VERSION",
    "GaussianBaselineArtifacts",
    "MARGINAL_DIAGNOSTIC_FIELDS",
    "MULTIVARIATE_DIAGNOSTIC_FIELDS",
    "VECTOR_DIAGNOSTIC_FIELDS",
    "VERSION",
    "load_gaussian_baseline_artifacts",
    "run_gaussian_diagnostics",
]
