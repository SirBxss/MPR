"""Frozen-cohort drive-held-out conditional Gaussian workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
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
)
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.conditional_gaussian import (
    ConditionalGaussianResidualModel,
    fit_linear_conditional_gaussian,
)
from ..modeling.gaussian import fit_gaussian_residual_model
from ..visualization.conditional_gaussian import plot_conditional_gaussian_comparison
from .gaussian_diagnostics import (
    GaussianBaselineArtifacts,
    load_gaussian_baseline_artifacts,
)

VERSION = "0.8.0"
ACCEPTED_FEATURE_VERSION = "0.7.2"
ACCEPTED_FEATURE_PURPOSE = "exact_manifest_prediction_time_conditional_feature_audit"
EXPECTED_SPEED_SOURCE = "odometry_50ms_displacement"
EXPECTED_SPEED_INTERVAL_MS = 50.0
EXPECTED_MAXIMUM_ODOMETRY_GAP_MS = 50.0
MARGINAL_95_QUANTILE = 1.959963984540054

CONDITIONAL_FEATURE_NAMES = BMW_CONDITION_FEATURE_NAMES

COHORT_FIELDS = (*RESIDUAL_VECTOR_FIELDS, *CONDITIONAL_FEATURE_NAMES)
EXCLUSION_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "estimate_message_index",
    "estimate_source_time_ns_private",
    "feature_state",
    "failure_codes",
)
EVALUATION_FIELDS = (
    "model_type",
    "scope",
    "held_out_drive_id",
    "training_drive_ids",
    "training_vector_count",
    "test_vector_count",
    "dimension",
    "feature_count",
    "mean_model_parameter_count_per_station",
    "covariance_regularization_m2",
    "mean_joint_negative_log_likelihood",
    "mean_squared_mahalanobis",
    "mean_squared_mahalanobis_per_dimension",
    "pooled_mean_prediction_rmse_m",
    "mean_station_mean_prediction_rmse_m",
    "marginal_95_coverage",
    "training_covariance_condition_number",
    "training_mean_design_condition_number",
)
STATION_EVALUATION_FIELDS = (
    "model_type",
    "scope",
    "held_out_drive_id",
    "station_m",
    "test_vector_count",
    "mean_prediction_rmse_m",
    "mean_prediction_bias_m",
    "marginal_95_coverage",
)
VECTOR_EVALUATION_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "conditional_joint_negative_log_likelihood",
    "unconditional_joint_negative_log_likelihood",
    "conditional_minus_unconditional_joint_negative_log_likelihood",
    "conditional_squared_mahalanobis_per_dimension",
    "unconditional_squared_mahalanobis_per_dimension",
    "conditional_mean_prediction_rmse_m",
    "unconditional_mean_prediction_rmse_m",
)


def _read_strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def _read_csv(path: Path, *, required_fields: Sequence[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = tuple(reader.fieldnames or ())
        missing = [field for field in required_fields if field not in actual]
        if missing:
            raise ResidualDatasetContractError(
                f"{path.name} is missing required columns: {missing}"
            )
        return [dict(row) for row in reader]


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
        raise ValueError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _required_integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResidualDatasetContractError(f"{key} must be a nonnegative integer")
    return value


def _finite_row_float(row: Mapping[str, Any], key: str) -> float:
    raw = str(row.get(key, "")).strip()
    try:
        value = float(raw)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be numeric") from error
    if not math.isfinite(value):
        raise ResidualDatasetContractError(f"{key} must be finite")
    return value


def _row_integer(row: Mapping[str, Any], key: str) -> int:
    raw = str(row.get(key, "")).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be an integer") from error
    if value < 0:
        raise ResidualDatasetContractError(f"{key} must be nonnegative")
    return value


@dataclass(frozen=True)
class ConditionalCohort:
    observations: tuple[ResidualObservation, ...]
    features: np.ndarray = field(repr=False)
    exclusions: tuple[dict[str, Any], ...] = field(repr=False)

    def __post_init__(self) -> None:
        features = np.asarray(self.features, dtype=np.float64)
        if len(self.observations) < 2:
            raise ValueError("conditional cohort needs at least two observations")
        if features.shape != (len(self.observations), len(CONDITIONAL_FEATURE_NAMES)):
            raise ValueError("conditional feature matrix has the wrong shape")
        if not np.all(np.isfinite(features)):
            raise ValueError("conditional features must be finite")
        keys = [observation.key for observation in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("conditional cohort keys must be unique")
        features.setflags(write=False)
        object.__setattr__(self, "features", features)

    @property
    def residuals_m(self) -> np.ndarray:
        return np.vstack([observation.residuals_m for observation in self.observations])

    @property
    def drive_ids(self) -> tuple[str, ...]:
        return tuple(observation.drive_id for observation in self.observations)


def _validate_feature_summary(
    feature_directory: Path,
    baseline_directory: Path,
) -> Mapping[str, Any]:
    summary_path = feature_directory / "conditional_feature_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"conditional feature summary not found: {summary_path}")
    summary = _read_strict_json(summary_path)
    if not isinstance(summary, Mapping):
        raise ResidualDatasetContractError("conditional feature summary must be an object")
    if summary.get("version") != ACCEPTED_FEATURE_VERSION:
        raise ResidualDatasetContractError("conditional feature version must be 0.7.2")
    if summary.get("purpose") != ACCEPTED_FEATURE_PURPOSE:
        raise ResidualDatasetContractError("conditional feature purpose is not accepted")
    if summary.get("status") not in ("complete", "incomplete"):
        raise ResidualDatasetContractError("conditional feature status is not accepted")
    if summary.get("source_baseline_version") != "0.6.0":
        raise ResidualDatasetContractError("conditional features require baseline v0.6.0")
    if summary.get("drive_grouping_source") != "accepted_exact_alignment_manifest":
        raise ResidualDatasetContractError("feature drive grouping must be exact")
    if summary.get("canonical_condition_station_grid_m") != list(
        CANONICAL_MODEL_STATIONS_M
    ):
        raise ResidualDatasetContractError("conditional feature grid must be H100")
    if summary.get("model_feature_fields") != list(CONDITIONAL_FEATURE_NAMES):
        raise ResidualDatasetContractError("conditional model feature fields changed")
    if summary.get("speed_source") != EXPECTED_SPEED_SOURCE:
        raise ResidualDatasetContractError("accepted feature speed source is odometry")
    if summary.get("speed_is_signed") is not False:
        raise ResidualDatasetContractError("odometry speed must remain explicitly unsigned")
    if not math.isclose(
        float(summary.get("speed_displacement_interval_ms", float("nan"))),
        EXPECTED_SPEED_INTERVAL_MS,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise ResidualDatasetContractError("odometry speed interval must be 50 ms")
    if not math.isclose(
        float(summary.get("maximum_odometry_interpolation_gap_ms", float("nan"))),
        EXPECTED_MAXIMUM_ODOMETRY_GAP_MS,
        rel_tol=0.0,
        abs_tol=0.0,
    ):
        raise ResidualDatasetContractError("odometry interpolation limit must be 50 ms")
    if _required_integer(summary, "odometry_conflicting_timestamp_group_count") != 0:
        raise ResidualDatasetContractError("conflicting odometry timestamp groups are forbidden")
    if _required_integer(summary, "odometry_discarded_conflicting_message_count") != 0:
        raise ResidualDatasetContractError("discarded conflicting odometry is forbidden")
    if summary.get("conditional_model_trained") is not False:
        raise ResidualDatasetContractError("feature audit must not already train a model")
    if summary.get("cohort_selection_performed") is not False:
        raise ResidualDatasetContractError("feature audit must precede cohort selection")
    source_hashes = summary.get("source_baseline_files_sha256")
    if not isinstance(source_hashes, Mapping):
        raise ResidualDatasetContractError("feature summary lacks baseline hashes")
    for filename in (
        "residual_vectors.csv",
        "residual_dataset_summary.json",
        "gaussian_model.json",
        "gaussian_summary.json",
    ):
        path = baseline_directory / filename
        if not path.is_file() or source_hashes.get(filename) != _sha256(path):
            raise ResidualDatasetContractError(
                f"feature audit does not match baseline file: {filename}"
            )
    return summary


def load_conditional_cohort(
    feature_directory: Path,
    baseline_directory: Path,
    artifacts: GaussianBaselineArtifacts,
) -> tuple[ConditionalCohort, Mapping[str, Any]]:
    """Join exact feature and residual keys, selecting only complete features."""

    summary = _validate_feature_summary(feature_directory, baseline_directory)
    feature_path = feature_directory / "conditional_features.csv"
    if not feature_path.is_file():
        raise FileNotFoundError(f"conditional feature CSV not found: {feature_path}")
    required = (
        "recording_id",
        "drive_id",
        "pair_index",
        "estimate_message_index",
        "estimate_source_time_ns_private",
        "feature_state",
        "failure_codes",
        "speed_source",
        "speed_is_signed",
        "speed_evaluation_method",
        "speed_displacement_m",
        "speed_displacement_interval_ms",
        "speed_previous_target_timestamp_ns_private",
        "speed_current_target_timestamp_ns_private",
        "speed_previous_lower_timestamp_ns_private",
        "speed_previous_upper_timestamp_ns_private",
        "speed_current_lower_timestamp_ns_private",
        "speed_current_upper_timestamp_ns_private",
        "speed_previous_interpolation_span_ms",
        "speed_current_interpolation_span_ms",
        *CONDITIONAL_FEATURE_NAMES,
    )
    rows = _read_csv(feature_path, required_fields=required)
    row_by_key: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        key = str(row["recording_id"]).strip(), _row_integer(row, "pair_index")
        if not key[0] or key in row_by_key:
            raise ResidualDatasetContractError("feature keys must be nonempty and unique")
        row_by_key[key] = row

    baseline_by_key = {
        observation.key: observation for observation in artifacts.dataset.observations
    }
    if set(row_by_key) != set(baseline_by_key):
        raise ResidualDatasetContractError(
            "feature rows must match every canonical residual key exactly"
        )
    if _required_integer(summary, "residual_vector_count") != len(rows):
        raise ResidualDatasetContractError("feature row count does not reconcile")

    observations: list[ResidualObservation] = []
    features: list[list[float]] = []
    exclusions: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()
    for observation in artifacts.dataset.observations:
        row = row_by_key[observation.key]
        if str(row["drive_id"]).strip() != observation.drive_id:
            raise ResidualDatasetContractError("feature drive ID disagrees with residual")
        if _row_integer(row, "estimate_message_index") != observation.estimate_message_index:
            raise ResidualDatasetContractError("feature estimate index disagrees with residual")
        if _row_integer(
            row,
            "estimate_source_time_ns_private",
        ) != observation.estimate_source_time_ns_private:
            raise ResidualDatasetContractError("feature source time disagrees with residual")
        state = str(row["feature_state"]).strip()
        failures = str(row["failure_codes"]).strip()
        if row["speed_source"] != EXPECTED_SPEED_SOURCE:
            raise ResidualDatasetContractError("row speed source is not accepted")
        if str(row["speed_is_signed"]).strip().lower() != "false":
            raise ResidualDatasetContractError("row odometry speed must be unsigned")
        if state == "ready":
            if failures:
                raise ResidualDatasetContractError("ready feature row has failures")
            if row["speed_evaluation_method"] != EXPECTED_SPEED_SOURCE:
                raise ResidualDatasetContractError("row speed method is not accepted")
            interval_ms = _finite_row_float(row, "speed_displacement_interval_ms")
            if not math.isclose(
                interval_ms,
                EXPECTED_SPEED_INTERVAL_MS,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ResidualDatasetContractError("row speed interval must be 50 ms")
            current_target = _row_integer(
                row,
                "speed_current_target_timestamp_ns_private",
            )
            previous_target = _row_integer(
                row,
                "speed_previous_target_timestamp_ns_private",
            )
            if current_target != observation.estimate_source_time_ns_private:
                raise ResidualDatasetContractError("speed target must equal estimate time")
            if current_target - previous_target != 50_000_000:
                raise ResidualDatasetContractError("speed endpoints must be 50 ms apart")
            for prefix, target in (
                ("previous", previous_target),
                ("current", current_target),
            ):
                lower = _row_integer(
                    row,
                    f"speed_{prefix}_lower_timestamp_ns_private",
                )
                upper = _row_integer(
                    row,
                    f"speed_{prefix}_upper_timestamp_ns_private",
                )
                span = _finite_row_float(
                    row,
                    f"speed_{prefix}_interpolation_span_ms",
                )
                if not lower <= target <= upper:
                    raise ResidualDatasetContractError("speed target lies outside bracket")
                if not math.isclose(span, (upper - lower) / 1e6, abs_tol=1e-12):
                    raise ResidualDatasetContractError("speed bracket span is inconsistent")
                if span > EXPECTED_MAXIMUM_ODOMETRY_GAP_MS:
                    raise ResidualDatasetContractError("speed bracket exceeds 50 ms")
            feature_values = [
                _finite_row_float(row, name) for name in CONDITIONAL_FEATURE_NAMES
            ]
            displacement = _finite_row_float(row, "speed_displacement_m")
            if not math.isclose(
                displacement,
                feature_values[0] * 0.05,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ResidualDatasetContractError("speed and displacement disagree")
            observations.append(observation)
            features.append(feature_values)
        elif state == "not_ready":
            if failures != "speed__odometry_reference_time_outside_coverage":
                raise ResidualDatasetContractError(
                    "only recording-boundary odometry coverage exclusions are accepted"
                )
            if observation.pair_index != 0:
                raise ResidualDatasetContractError("coverage exclusion must be pair zero")
            unavailable_speed_fields = (
                "speed_mps",
                "speed_evaluation_method",
                "speed_displacement_m",
                "speed_displacement_interval_ms",
                "speed_previous_target_timestamp_ns_private",
                "speed_current_target_timestamp_ns_private",
                "speed_previous_lower_timestamp_ns_private",
                "speed_previous_upper_timestamp_ns_private",
                "speed_current_lower_timestamp_ns_private",
                "speed_current_upper_timestamp_ns_private",
                "speed_previous_interpolation_span_ms",
                "speed_current_interpolation_span_ms",
            )
            if any(str(row.get(name, "")).strip() for name in unavailable_speed_fields):
                raise ResidualDatasetContractError(
                    "excluded boundary row must not contain partial speed evidence"
                )
            for name in CONDITIONAL_FEATURE_NAMES[1:]:
                _finite_row_float(row, name)
            failure_counts[failures] += 1
            exclusions.append(
                {
                    field_name: row[field_name] for field_name in EXCLUSION_FIELDS
                }
            )
        else:
            raise ResidualDatasetContractError(f"unknown feature state: {state}")

    if _required_integer(summary, "feature_ready_count") != len(observations):
        raise ResidualDatasetContractError("ready feature count does not reconcile")
    if _required_integer(summary, "feature_not_ready_count") != len(exclusions):
        raise ResidualDatasetContractError("excluded feature count does not reconcile")
    if summary.get("feature_failure_counts") != dict(sorted(failure_counts.items())):
        raise ResidualDatasetContractError("feature failure counts do not reconcile")
    ready_by_drive = dict(
        sorted(Counter(observation.drive_id for observation in observations).items())
    )
    all_by_drive = dict(
        sorted(
            Counter(
                observation.drive_id
                for observation in artifacts.dataset.observations
            ).items()
        )
    )
    if summary.get("feature_ready_count_by_drive") != ready_by_drive:
        raise ResidualDatasetContractError("ready feature drive counts do not reconcile")
    if summary.get("residual_vector_count_by_drive") != all_by_drive:
        raise ResidualDatasetContractError("source feature drive counts do not reconcile")
    expected_status = "complete" if not exclusions else "incomplete"
    if summary.get("status") != expected_status:
        raise ResidualDatasetContractError("feature audit status does not reconcile")
    cohort = ConditionalCohort(
        observations=tuple(observations),
        features=np.asarray(features, dtype=np.float64),
        exclusions=tuple(exclusions),
    )
    if len(set(cohort.drive_ids)) < 2:
        raise ResidualDatasetContractError("conditional cohort needs two drives")
    return cohort, summary


def _model_arrays(
    *,
    model_type: str,
    training_features: np.ndarray,
    training_residuals: np.ndarray,
    test_features: np.ndarray,
    test_residuals: np.ndarray,
    covariance_regularization_m2: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float | None]:
    if model_type == "conditional_linear_gaussian":
        model = fit_linear_conditional_gaussian(
            training_features,
            training_residuals,
            feature_names=CONDITIONAL_FEATURE_NAMES,
            covariance_regularization_m2=covariance_regularization_m2,
        )
        prediction = model.predict_mean(test_features)
        errors = test_residuals - prediction
        squared = model.squared_mahalanobis(test_features, test_residuals)
        nll = -model.logpdf(test_features, test_residuals)
        covariance = model.covariance_m2
        standardized = model.standardized_features(training_features)
        design_condition = float(
            np.linalg.cond(np.column_stack((np.ones(len(standardized)), standardized)))
        )
    elif model_type == "unconditional_gaussian_same_cohort":
        model = fit_gaussian_residual_model(
            training_residuals,
            regularization=covariance_regularization_m2,
        )
        prediction = np.broadcast_to(model.mean, test_residuals.shape)
        errors = test_residuals - prediction
        squared = model.squared_mahalanobis(test_residuals)
        nll = -model.logpdf(test_residuals)
        covariance = model.covariance
        design_condition = None
    else:
        raise ValueError(f"unknown model type: {model_type}")
    standard_deviation = np.sqrt(np.diag(covariance))
    coverage = np.abs(errors) <= MARGINAL_95_QUANTILE * standard_deviation
    return (
        errors,
        coverage,
        squared,
        nll,
        float(np.linalg.cond(covariance)),
        design_condition,
    )


def _evaluation_row(
    *,
    model_type: str,
    scope: str,
    held_out_drive_id: str | None,
    training_drive_ids: Sequence[str],
    training_vector_count: int | None,
    errors: np.ndarray,
    coverage: np.ndarray,
    squared: np.ndarray,
    nll: np.ndarray,
    covariance_regularization_m2: float,
    covariance_condition: float | None,
    design_condition: float | None,
) -> dict[str, Any]:
    station_rmse = np.sqrt(np.mean(np.square(errors), axis=0))
    conditional = model_type == "conditional_linear_gaussian"
    return {
        "model_type": model_type,
        "scope": scope,
        "held_out_drive_id": held_out_drive_id,
        "training_drive_ids": ";".join(training_drive_ids),
        "training_vector_count": training_vector_count,
        "test_vector_count": len(errors),
        "dimension": errors.shape[1],
        "feature_count": len(CONDITIONAL_FEATURE_NAMES) if conditional else 0,
        "mean_model_parameter_count_per_station": (
            len(CONDITIONAL_FEATURE_NAMES) + 1 if conditional else 1
        ),
        "covariance_regularization_m2": covariance_regularization_m2,
        "mean_joint_negative_log_likelihood": float(np.mean(nll)),
        "mean_squared_mahalanobis": float(np.mean(squared)),
        "mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared) / errors.shape[1]
        ),
        "pooled_mean_prediction_rmse_m": float(
            np.sqrt(np.mean(np.square(errors)))
        ),
        "mean_station_mean_prediction_rmse_m": float(np.mean(station_rmse)),
        "marginal_95_coverage": float(np.mean(coverage)),
        "training_covariance_condition_number": covariance_condition,
        "training_mean_design_condition_number": design_condition,
    }


def _station_rows(
    *,
    model_type: str,
    scope: str,
    held_out_drive_id: str | None,
    errors: np.ndarray,
    coverage: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, station in enumerate(CANONICAL_MODEL_STATIONS_M):
        values = errors[:, index]
        rows.append(
            {
                "model_type": model_type,
                "scope": scope,
                "held_out_drive_id": held_out_drive_id,
                "station_m": station,
                "test_vector_count": len(values),
                "mean_prediction_rmse_m": float(
                    np.sqrt(np.mean(np.square(values)))
                ),
                "mean_prediction_bias_m": float(np.mean(values)),
                "marginal_95_coverage": float(np.mean(coverage[:, index])),
            }
        )
    return rows


def evaluate_same_cohort_models(
    cohort: ConditionalCohort,
    *,
    covariance_regularization_m2: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate both models on identical leave-one-drive-out folds."""

    features = cohort.features
    residuals = cohort.residuals_m
    drives = np.asarray(cohort.drive_ids)
    model_types = (
        "unconditional_gaussian_same_cohort",
        "conditional_linear_gaussian",
    )
    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    stored: dict[str, dict[str, np.ndarray]] = {
        model_type: {
            "errors": np.empty_like(residuals),
            "coverage": np.empty_like(residuals, dtype=bool),
            "squared": np.empty(len(residuals)),
            "nll": np.empty(len(residuals)),
        }
        for model_type in model_types
    }
    unique_drives = sorted(set(cohort.drive_ids))
    for held_out_drive in unique_drives:
        test_mask = drives == held_out_drive
        train_mask = ~test_mask
        training_drives = sorted(set(drives[train_mask].tolist()))
        for model_type in model_types:
            errors, coverage, squared, nll, covariance_condition, design_condition = (
                _model_arrays(
                    model_type=model_type,
                    training_features=features[train_mask],
                    training_residuals=residuals[train_mask],
                    test_features=features[test_mask],
                    test_residuals=residuals[test_mask],
                    covariance_regularization_m2=covariance_regularization_m2,
                )
            )
            stored[model_type]["errors"][test_mask] = errors
            stored[model_type]["coverage"][test_mask] = coverage
            stored[model_type]["squared"][test_mask] = squared
            stored[model_type]["nll"][test_mask] = nll
            evaluation_rows.append(
                _evaluation_row(
                    model_type=model_type,
                    scope="held_out_drive",
                    held_out_drive_id=held_out_drive,
                    training_drive_ids=training_drives,
                    training_vector_count=int(np.sum(train_mask)),
                    errors=errors,
                    coverage=coverage,
                    squared=squared,
                    nll=nll,
                    covariance_regularization_m2=covariance_regularization_m2,
                    covariance_condition=covariance_condition,
                    design_condition=design_condition,
                )
            )
            station_rows.extend(
                _station_rows(
                    model_type=model_type,
                    scope="held_out_drive",
                    held_out_drive_id=held_out_drive,
                    errors=errors,
                    coverage=coverage,
                )
            )

    for model_type in model_types:
        arrays = stored[model_type]
        evaluation_rows.append(
            _evaluation_row(
                model_type=model_type,
                scope="overall_cross_validated",
                held_out_drive_id=None,
                training_drive_ids=(),
                training_vector_count=None,
                errors=arrays["errors"],
                coverage=arrays["coverage"],
                squared=arrays["squared"],
                nll=arrays["nll"],
                covariance_regularization_m2=covariance_regularization_m2,
                covariance_condition=None,
                design_condition=None,
            )
        )
        station_rows.extend(
            _station_rows(
                model_type=model_type,
                scope="overall_cross_validated",
                held_out_drive_id=None,
                errors=arrays["errors"],
                coverage=arrays["coverage"],
            )
        )

    vector_rows: list[dict[str, Any]] = []
    conditional = stored["conditional_linear_gaussian"]
    unconditional = stored["unconditional_gaussian_same_cohort"]
    for index, observation in enumerate(cohort.observations):
        conditional_rmse = float(
            np.sqrt(np.mean(np.square(conditional["errors"][index])))
        )
        unconditional_rmse = float(
            np.sqrt(np.mean(np.square(unconditional["errors"][index])))
        )
        vector_rows.append(
            {
                "recording_id": observation.recording_id,
                "drive_id": observation.drive_id,
                "pair_index": observation.pair_index,
                "conditional_joint_negative_log_likelihood": float(
                    conditional["nll"][index]
                ),
                "unconditional_joint_negative_log_likelihood": float(
                    unconditional["nll"][index]
                ),
                "conditional_minus_unconditional_joint_negative_log_likelihood": (
                    float(conditional["nll"][index] - unconditional["nll"][index])
                ),
                "conditional_squared_mahalanobis_per_dimension": float(
                    conditional["squared"][index] / residuals.shape[1]
                ),
                "unconditional_squared_mahalanobis_per_dimension": float(
                    unconditional["squared"][index] / residuals.shape[1]
                ),
                "conditional_mean_prediction_rmse_m": conditional_rmse,
                "unconditional_mean_prediction_rmse_m": unconditional_rmse,
            }
        )
    return evaluation_rows, station_rows, vector_rows


def _model_payload(
    model: ConditionalGaussianResidualModel,
    cohort: ConditionalCohort,
) -> dict[str, Any]:
    standardized = model.standardized_features(cohort.features)
    design = np.column_stack((np.ones(len(standardized)), standardized))
    return {
        "version": VERSION,
        "status": "complete",
        "model_type": "linear_mean_conditional_multivariate_gaussian",
        "mean_fit_method": "ordinary_least_squares_on_standardized_features",
        "mean_prediction_equation": (
            "intercept_m + ((features - feature_mean) / feature_scale) "
            "@ standardized_feature_coefficients_m"
        ),
        "covariance_fit_method": "maximum_likelihood_training_error_covariance",
        "feature_names": list(model.feature_names),
        "feature_count": model.feature_count,
        "feature_mean": model.feature_mean.tolist(),
        "feature_scale": model.feature_scale.tolist(),
        "stations_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": model.dimension,
        "n_training_vectors": model.n_training_samples,
        "training_drive_ids": sorted(set(cohort.drive_ids)),
        "intercept_m": model.intercept_m.tolist(),
        "standardized_feature_coefficients_m": (
            model.standardized_coefficients_m.tolist()
        ),
        "covariance_regularization_m2": model.covariance_regularization_m2,
        "covariance_m2": model.covariance_m2.tolist(),
        "marginal_standard_deviation_m": np.sqrt(
            np.diag(model.covariance_m2)
        ).tolist(),
        "training_mean_design_condition_number": float(np.linalg.cond(design)),
        "training_covariance_condition_number": float(
            np.linalg.cond(model.covariance_m2)
        ),
        "speed_is_signed": False,
        "reference_signal_role": "best_available_pseudo_ground_truth",
    }


def run_conditional_gaussian(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Freeze the complete-feature cohort and compare Gaussian baselines."""

    regularization = arguments.covariance_regularization_m2
    if not math.isfinite(regularization) or regularization <= 0.0:
        raise ValueError("covariance-regularization-m2 must be finite and positive")
    artifacts = load_gaussian_baseline_artifacts(
        arguments.gaussian_baseline_directory
    )
    cohort, feature_summary = load_conditional_cohort(
        arguments.conditional_feature_directory,
        arguments.gaussian_baseline_directory,
        artifacts,
    )
    _ensure_empty_output(arguments.output_directory)

    cohort_rows: list[dict[str, Any]] = []
    for observation, feature_values in zip(cohort.observations, cohort.features):
        row = observation.as_csv_row()
        row.update(
            {
                name: float(feature_values[index])
                for index, name in enumerate(CONDITIONAL_FEATURE_NAMES)
            }
        )
        cohort_rows.append(row)
    write_csv_rows(
        arguments.output_directory / "conditional_cohort.csv",
        COHORT_FIELDS,
        cohort_rows,
    )
    write_csv_rows(
        arguments.output_directory / "conditional_cohort_exclusions.csv",
        EXCLUSION_FIELDS,
        cohort.exclusions,
    )

    drive_counts = Counter(cohort.drive_ids)
    recording_counts = Counter(
        observation.recording_id for observation in cohort.observations
    )
    exclusion_counts = Counter(
        exclusion["failure_codes"] for exclusion in cohort.exclusions
    )
    baseline_files = (
        "residual_vectors.csv",
        "residual_dataset_summary.json",
        "gaussian_model.json",
        "gaussian_summary.json",
    )
    feature_files = (
        "conditional_features.csv",
        "conditional_feature_recording_summary.csv",
        "conditional_feature_summary.json",
    )
    cohort_summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "frozen_complete_feature_conditional_h100_cohort",
        "source_residual_vector_count": len(artifacts.dataset.observations),
        "selected_vector_count": len(cohort.observations),
        "excluded_vector_count": len(cohort.exclusions),
        "selection_rule": "feature_state_equals_ready",
        "selection_uses_residual_values": False,
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "cross_mcap_feature_extraction": False,
        "speed_extrapolation": False,
        "speed_source": EXPECTED_SPEED_SOURCE,
        "speed_is_signed": False,
        "speed_displacement_interval_ms": EXPECTED_SPEED_INTERVAL_MS,
        "maximum_odometry_interpolation_gap_ms": (
            EXPECTED_MAXIMUM_ODOMETRY_GAP_MS
        ),
        "feature_names": list(CONDITIONAL_FEATURE_NAMES),
        "feature_count": len(CONDITIONAL_FEATURE_NAMES),
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "constant_pair_count_at_every_station": True,
        "selected_vector_count_by_drive": dict(sorted(drive_counts.items())),
        "selected_vector_count_by_recording": dict(
            sorted(recording_counts.items())
        ),
        "source_baseline_files_sha256": {
            filename: _sha256(arguments.gaussian_baseline_directory / filename)
            for filename in baseline_files
        },
        "source_feature_files_sha256": {
            filename: _sha256(arguments.conditional_feature_directory / filename)
            for filename in feature_files
        },
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "pair_count_is_independent_sample_size": False,
        "confidentiality": "Cohort rows derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "conditional_cohort_summary.json",
        cohort_summary,
    )

    evaluation_rows, station_rows, vector_rows = evaluate_same_cohort_models(
        cohort,
        covariance_regularization_m2=regularization,
    )
    write_csv_rows(
        arguments.output_directory / "conditional_gaussian_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "conditional_gaussian_station_evaluation.csv",
        STATION_EVALUATION_FIELDS,
        station_rows,
    )
    write_csv_rows(
        arguments.output_directory / "conditional_gaussian_vector_evaluation.csv",
        VECTOR_EVALUATION_FIELDS,
        vector_rows,
    )

    final_model = fit_linear_conditional_gaussian(
        cohort.features,
        cohort.residuals_m,
        feature_names=CONDITIONAL_FEATURE_NAMES,
        covariance_regularization_m2=regularization,
    )
    write_strict_json(
        arguments.output_directory / "conditional_gaussian_model.json",
        _model_payload(final_model, cohort),
    )
    plot_conditional_gaussian_comparison(
        arguments.output_directory / "conditional_gaussian_comparison.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        evaluation_rows=evaluation_rows,
        station_rows=station_rows,
        feature_names=CONDITIONAL_FEATURE_NAMES,
        standardized_coefficients_m=final_model.standardized_coefficients_m,
    )

    overall = {
        row["model_type"]: row
        for row in evaluation_rows
        if row["scope"] == "overall_cross_validated"
    }
    conditional = overall["conditional_linear_gaussian"]
    unconditional = overall["unconditional_gaussian_same_cohort"]
    nll_delta = (
        conditional["mean_joint_negative_log_likelihood"]
        - unconditional["mean_joint_negative_log_likelihood"]
    )
    rmse_delta = (
        conditional["pooled_mean_prediction_rmse_m"]
        - unconditional["pooled_mean_prediction_rmse_m"]
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "drive_held_out_conditional_gaussian_same_cohort_comparison",
        "model_type": "linear_mean_conditional_multivariate_gaussian",
        "comparator_model_type": "unconditional_gaussian_refit_on_same_cohort",
        "evaluation_scheme": "leave_one_physical_drive_out",
        "evaluation_fold_count": len(set(cohort.drive_ids)),
        "same_training_and_test_rows_for_both_models": True,
        "fold_local_feature_standardization": True,
        "hyperparameter_selection_on_held_out_drives": False,
        "conditional_feature_count": len(CONDITIONAL_FEATURE_NAMES),
        "conditional_feature_names": list(CONDITIONAL_FEATURE_NAMES),
        "selected_vector_count": len(cohort.observations),
        "excluded_boundary_vector_count": len(cohort.exclusions),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "covariance_regularization_m2": regularization,
        "conditional_cross_validated_mean_joint_negative_log_likelihood": (
            conditional["mean_joint_negative_log_likelihood"]
        ),
        "unconditional_cross_validated_mean_joint_negative_log_likelihood": (
            unconditional["mean_joint_negative_log_likelihood"]
        ),
        "conditional_minus_unconditional_mean_joint_negative_log_likelihood": (
            nll_delta
        ),
        "conditional_cross_validated_pooled_mean_prediction_rmse_m": (
            conditional["pooled_mean_prediction_rmse_m"]
        ),
        "unconditional_cross_validated_pooled_mean_prediction_rmse_m": (
            unconditional["pooled_mean_prediction_rmse_m"]
        ),
        "conditional_minus_unconditional_pooled_mean_prediction_rmse_m": (
            rmse_delta
        ),
        "conditional_cross_validated_marginal_95_coverage": conditional[
            "marginal_95_coverage"
        ],
        "unconditional_cross_validated_marginal_95_coverage": unconditional[
            "marginal_95_coverage"
        ],
        "conditional_cross_validated_mean_squared_mahalanobis_per_dimension": (
            conditional["mean_squared_mahalanobis_per_dimension"]
        ),
        "unconditional_cross_validated_mean_squared_mahalanobis_per_dimension": (
            unconditional["mean_squared_mahalanobis_per_dimension"]
        ),
        "conditional_improves_joint_negative_log_likelihood": nll_delta < 0.0,
        "conditional_improves_mean_prediction_rmse": rmse_delta < 0.0,
        "model_acceptance_threshold_predeclared": False,
        "final_conditional_model_fit_after_evaluation": True,
        "final_conditional_model_training_vector_count": len(cohort.observations),
        "source_feature_audit_version": feature_summary["version"],
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "pair_count_is_independent_sample_size": False,
        "scientific_limitations": [
            "RLMB is a pseudo-reference, not independent physical ground truth.",
            "Only two physical drives are available for held-out evaluation.",
            "Sequential residual vectors are correlated.",
            "Odometry displacement speed is unsigned.",
            "Seven MCAP-boundary vectors are excluded without using residual values.",
            "The conditional mean is linear and covariance is condition-invariant.",
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "conditional_gaussian_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "ACCEPTED_FEATURE_VERSION",
    "COHORT_FIELDS",
    "CONDITIONAL_FEATURE_NAMES",
    "ConditionalCohort",
    "EVALUATION_FIELDS",
    "EXCLUSION_FIELDS",
    "STATION_EVALUATION_FIELDS",
    "VECTOR_EVALUATION_FIELDS",
    "VERSION",
    "evaluate_same_cohort_models",
    "load_conditional_cohort",
    "run_conditional_gaussian",
]
