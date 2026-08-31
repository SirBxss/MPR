"""Lineage-locked v0.16.2 A2/A3 cross-station structure audit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.spatial_structure import (
    SpatialMoments,
    mean_adjacent_correlation,
    mean_off_diagonal_correlation,
    population_spatial_moments,
)
from ..io.reports import write_csv_rows, write_strict_json
from .sequence_contract import (
    ensure_empty_output_directory,
    read_strict_json,
    sha256_file,
)
from .spatial_structure_audit_contract import (
    A2_SAMPLE_FILENAME,
    A2_SUMMARY_FILENAME,
    A3_SAMPLE_FILENAME,
    A3_SUMMARY_FILENAME,
    ACCEPTED_SPATIAL_STRUCTURE_AUDIT_CONTRACT,
    MATRICES_FILENAME,
    OUTPUT_FILENAMES,
    PAIR_FILENAME,
    SEPARATION_FILENAME,
    SEQUENCE_FILENAME,
    SUMMARY_FILENAME,
    SpatialStructureAuditContract,
    VERSION,
)

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]
StringArray = NDArray[np.str_]

ARM_NAMES = ("frozen_ar", "unconditional_gaussian")
STATIONS_M = np.arange(0.0, 105.0, 5.0, dtype=np.float64)
FEATURE_NAMES = (
    "speed_mps",
    "estimated_mean_abs_curvature_per_m",
    "estimated_curvature_delta_per_m",
    "confidence_near_mean",
    "confidence_middle_mean",
    "confidence_far_mean",
)
SAMPLE_KEYS = frozenset(
    {"feature_names", "lengths", "residual_samples_m", "sequence_ids", "stations_m"}
)
MATRIX_KEYS = frozenset(
    {
        "arm_names",
        "stations_m",
        "sequence_ids",
        "lengths",
        "pooled_means_m",
        "pooled_covariances_m2",
        "pooled_correlations",
        "pooled_covariance_difference_m2",
        "pooled_correlation_difference",
        "per_sequence_covariances_m2",
        "per_sequence_correlations",
        "per_sequence_covariance_differences_m2",
        "per_sequence_correlation_differences",
    }
)
PAIR_FIELDS = (
    "station_i_m",
    "station_j_m",
    "separation_m",
    "frozen_ar_covariance_m2",
    "unconditional_gaussian_covariance_m2",
    "unconditional_gaussian_minus_frozen_ar_covariance_m2",
    "frozen_ar_correlation",
    "unconditional_gaussian_correlation",
    "unconditional_gaussian_minus_frozen_ar_correlation",
)
SEPARATION_FIELDS = (
    "separation_m",
    "station_pair_count",
    "frozen_ar_mean_covariance_m2",
    "unconditional_gaussian_mean_covariance_m2",
    "unconditional_gaussian_minus_frozen_ar_mean_covariance_m2",
    "frozen_ar_mean_correlation",
    "unconditional_gaussian_mean_correlation",
    "unconditional_gaussian_minus_frozen_ar_mean_correlation",
)
SEQUENCE_FIELDS = (
    "sequence_id",
    "active_frame_count",
    "frozen_ar_mean_off_diagonal_correlation",
    "unconditional_gaussian_mean_off_diagonal_correlation",
    "unconditional_gaussian_minus_frozen_ar_mean_off_diagonal_correlation",
    "frozen_ar_mean_adjacent_station_correlation",
    "unconditional_gaussian_mean_adjacent_station_correlation",
    "unconditional_gaussian_minus_frozen_ar_mean_adjacent_station_correlation",
)


@dataclass(frozen=True)
class _SampleArm:
    residuals: FloatArray
    lengths: IntegerArray
    stations: FloatArray
    sequence_ids: StringArray
    feature_names: StringArray
    sample_path: Path
    summary_path: Path


@dataclass(frozen=True)
class _ArmMoments:
    pooled: SpatialMoments
    per_sequence_covariances: FloatArray
    per_sequence_correlations: FloatArray
    per_sequence_off_diagonal: FloatArray
    per_sequence_adjacent: FloatArray


def _json_object(path: Path) -> Mapping[str, Any]:
    payload = read_strict_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _validated_paths(
    directory: Path,
    *,
    sample_filename: str,
    summary_filename: str,
    sample_sha256: str,
    summary_sha256: str,
    arm_label: str,
) -> tuple[Path, Path]:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    expected = {sample_filename, summary_filename}
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError(f"{arm_label} sample directory filename set differs")
    sample_path = directory / sample_filename
    summary_path = directory / summary_filename
    if sha256_file(sample_path) != sample_sha256:
        raise ValueError(f"{arm_label} sample SHA-256 differs from the accepted input")
    if sha256_file(summary_path) != summary_sha256:
        raise ValueError(f"{arm_label} summary SHA-256 differs from the accepted input")
    return sample_path, summary_path


def _validate_a2_summary(
    summary: Mapping[str, Any],
    *,
    contract: SpatialStructureAuditContract,
) -> None:
    if (
        summary.get("version") != "0.15.4"
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "planner_facing_development_residual_sequence_sampling"
        or summary.get("sample_file") != A2_SAMPLE_FILENAME
        or summary.get("sample_file_sha256") != contract.a2_sample_sha256
        or summary.get("sample_count") != contract.sample_count
        or summary.get("sequence_count") != contract.sequence_count
        or summary.get("maximum_sequence_length")
        != contract.maximum_sequence_length
        or summary.get("active_frame_count") != contract.active_frame_count
        or summary.get("random_seed") != contract.a2_sampling_seed
        or summary.get("residual_unit") != "m"
        or summary.get("generated_previous_residual_used") is not True
        or summary.get("sampling_is_free_running") is not True
        or summary.get("sequence_reset_applied_once_per_input_sequence") is not True
        or summary.get("independent_frame_sampling_used") is not False
        or summary.get("planner_executed") is not False
        or summary.get("path_geometry_modified") is not False
        or summary.get("planner_benefit_claimed") is not False
        or summary.get("final_model_selection_authorized") is not False
        or summary.get("positive_direction")
        != "left of the pseudo-reference with respect to increasing station"
        or summary.get("residual_definition")
        != (
            "EDP estimate minus spatially aligned RLMB pseudo-reference, "
            "projected onto the pseudo-reference left unit normal"
        )
        or summary.get("stations_m") != STATIONS_M.tolist()
        or summary.get("feature_names_in_required_order") != list(FEATURE_NAMES)
    ):
        raise ValueError("A2 sampling summary differs from the accepted identity")


def _validate_a3_summary(
    summary: Mapping[str, Any],
    *,
    contract: SpatialStructureAuditContract,
) -> None:
    standardizer = summary.get("standardizer_equality_audit")
    discrepancy = (
        standardizer.get("maximum_absolute_discrepancy")
        if isinstance(standardizer, Mapping)
        else None
    )
    if (
        summary.get("version") != "0.16.1"
        or summary.get("status") != "complete"
        or summary.get("purpose")
        != "unconditional_gaussian_planner_transfer_sampling"
        or summary.get("arm") != "unconditional_gaussian"
        or summary.get("sample_file") != A3_SAMPLE_FILENAME
        or summary.get("sample_file_sha256") != contract.a3_sample_sha256
        or summary.get("sample_count") != contract.sample_count
        or summary.get("sequence_count") != contract.sequence_count
        or summary.get("maximum_sequence_length")
        != contract.maximum_sequence_length
        or summary.get("active_frame_count") != contract.active_frame_count
        or summary.get("random_seed") != contract.a3_sampling_seed
        or summary.get("accepted_a2_sampling_seed") != contract.a2_sampling_seed
        or summary.get("accepted_a2_sample_file_sha256")
        != contract.a2_sample_sha256
        or summary.get("accepted_a2_sample_summary_sha256")
        != contract.a2_summary_sha256
        or summary.get("residual_unit") != "m"
        or summary.get("temporal_dependency_order") != 0
        or summary.get("sequence_state_used") is not False
        or summary.get("active_frames_are_independent_draws") is not True
        or summary.get("spatial_cross_station_covariance_preserved") is not True
        or summary.get("common_random_numbers_with_a1_a2_used") is not False
        or summary.get("paired_residual_profiles_with_a1_a2_used") is not False
        or summary.get("planner_executed") is not False
        or summary.get("planner_benefit_claimed") is not False
        or summary.get("bmw_planner_behavior_claimed") is not False
        or summary.get("journey_level_generalization_estimated") is not False
        or summary.get("final_model_selection_authorized") is not False
        or summary.get("stations_m") != STATIONS_M.tolist()
        or summary.get("feature_names_in_required_order") != list(FEATURE_NAMES)
        or not isinstance(standardizer, Mapping)
        or standardizer.get("comparison_dtype") != "float64"
        or standardizer.get("elementwise_exact_equal") is not True
        or standardizer.get("tolerance_based_acceptance_used") is not False
        or discrepancy
        != {"residual_mean_m": 0.0, "residual_scale_m": 0.0, "stations_m": 0.0}
    ):
        raise ValueError("A3 sampling summary differs from the accepted identity")


def _load_npz(path: Path) -> dict[str, np.ndarray[Any, Any]]:
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != SAMPLE_KEYS:
            raise ValueError(f"sample NPZ key set differs: {path}")
        return {name: np.array(archive[name], copy=True) for name in archive.files}


def _string_array(value: np.ndarray[Any, Any], label: str) -> StringArray:
    array = np.asarray(value)
    if array.ndim != 1 or array.dtype.kind not in {"U", "S"}:
        raise TypeError(f"{label} must be a one-dimensional NumPy string array")
    return np.asarray(array, dtype=np.str_)


def _integer_array(value: np.ndarray[Any, Any], label: str) -> IntegerArray:
    array = np.asarray(value)
    if array.ndim != 1 or array.dtype.kind not in {"i", "u"}:
        raise TypeError(f"{label} must be a one-dimensional integer array")
    if array.dtype.kind == "u" and np.any(array > np.iinfo(np.int64).max):
        raise ValueError(f"{label} exceeds int64")
    return np.asarray(array, dtype=np.int64)


def _load_sample_arm(
    directory: Path,
    *,
    sample_filename: str,
    summary_filename: str,
    sample_sha256: str,
    summary_sha256: str,
    arm_label: str,
    contract: SpatialStructureAuditContract,
) -> _SampleArm:
    sample_path, summary_path = _validated_paths(
        directory,
        sample_filename=sample_filename,
        summary_filename=summary_filename,
        sample_sha256=sample_sha256,
        summary_sha256=summary_sha256,
        arm_label=arm_label,
    )
    summary = _json_object(summary_path)
    if arm_label == "A2":
        _validate_a2_summary(summary, contract=contract)
    else:
        _validate_a3_summary(summary, contract=contract)

    payload = _load_npz(sample_path)
    residuals = np.asarray(payload["residual_samples_m"])
    lengths = _integer_array(payload["lengths"], f"{arm_label} lengths")
    stations = np.asarray(payload["stations_m"])
    sequence_ids = _string_array(payload["sequence_ids"], f"{arm_label} sequence IDs")
    feature_names = _string_array(payload["feature_names"], f"{arm_label} features")
    expected_shape = (
        contract.sample_count,
        contract.sequence_count,
        contract.maximum_sequence_length,
        len(STATIONS_M),
    )
    if residuals.dtype != np.dtype(np.float64) or residuals.shape != expected_shape:
        raise TypeError(f"{arm_label} residuals must be float64 with the fixed shape")
    if lengths.shape != (contract.sequence_count,):
        raise ValueError(f"{arm_label} length shape differs")
    if np.any(lengths < 1) or np.any(lengths > contract.maximum_sequence_length):
        raise ValueError(f"{arm_label} lengths lie outside the padded range")
    if int(np.sum(lengths, dtype=np.int64)) != contract.active_frame_count:
        raise ValueError(f"{arm_label} active-frame count differs")
    if stations.dtype != np.dtype(np.float64) or not np.array_equal(
        stations, STATIONS_M
    ):
        raise ValueError(f"{arm_label} station grid differs from H100")
    if sequence_ids.shape != (contract.sequence_count,) or len(set(sequence_ids)) != len(
        sequence_ids
    ):
        raise ValueError(f"{arm_label} sequence identities are invalid")
    if tuple(feature_names.tolist()) != FEATURE_NAMES:
        raise ValueError(f"{arm_label} feature order differs from BMW schema v1")

    time_mask = np.arange(contract.maximum_sequence_length)[None, :] < lengths[:, None]
    if not np.all(np.isfinite(residuals[:, time_mask, :])):
        raise ValueError(f"{arm_label} active residuals are non-finite")
    if np.any(residuals[:, ~time_mask, :] != 0.0):
        raise ValueError(f"{arm_label} residual padding is not exactly zero")
    return _SampleArm(
        residuals=np.asarray(residuals, dtype=np.float64),
        lengths=lengths,
        stations=np.asarray(stations, dtype=np.float64),
        sequence_ids=sequence_ids,
        feature_names=feature_names,
        sample_path=sample_path,
        summary_path=summary_path,
    )


def _calculate_arm(
    arm: _SampleArm,
    *,
    correlation_tolerance: float,
) -> _ArmMoments:
    maximum_time = arm.residuals.shape[2]
    time_mask = np.arange(maximum_time)[None, :] < arm.lengths[:, None]
    pooled_profiles = np.asarray(
        arm.residuals[:, time_mask, :].reshape(-1, len(STATIONS_M)),
        dtype=np.float64,
    )
    pooled = population_spatial_moments(
        pooled_profiles, correlation_tolerance=correlation_tolerance
    )

    sequence_count = len(arm.lengths)
    covariances = np.empty(
        (sequence_count, len(STATIONS_M), len(STATIONS_M)), dtype=np.float64
    )
    correlations = np.empty_like(covariances)
    off_diagonal = np.empty(sequence_count, dtype=np.float64)
    adjacent = np.empty(sequence_count, dtype=np.float64)
    for sequence_index, length in enumerate(arm.lengths):
        profiles = np.asarray(
            arm.residuals[:, sequence_index, : int(length), :].reshape(
                -1, len(STATIONS_M)
            ),
            dtype=np.float64,
        )
        moments = population_spatial_moments(
            profiles, correlation_tolerance=correlation_tolerance
        )
        covariances[sequence_index] = moments.covariance
        correlations[sequence_index] = moments.correlation
        off_diagonal[sequence_index] = mean_off_diagonal_correlation(
            moments.correlation
        )
        adjacent[sequence_index] = mean_adjacent_correlation(moments.correlation)
    return _ArmMoments(
        pooled=pooled,
        per_sequence_covariances=covariances,
        per_sequence_correlations=correlations,
        per_sequence_off_diagonal=off_diagonal,
        per_sequence_adjacent=adjacent,
    )


def _pair_and_separation_rows(
    a2: _ArmMoments,
    a3: _ArmMoments,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pair_rows: list[dict[str, Any]] = []
    for station_i in range(len(STATIONS_M) - 1):
        for station_j in range(station_i + 1, len(STATIONS_M)):
            a2_covariance = float(a2.pooled.covariance[station_i, station_j])
            a3_covariance = float(a3.pooled.covariance[station_i, station_j])
            a2_correlation = float(a2.pooled.correlation[station_i, station_j])
            a3_correlation = float(a3.pooled.correlation[station_i, station_j])
            pair_rows.append(
                {
                    "station_i_m": float(STATIONS_M[station_i]),
                    "station_j_m": float(STATIONS_M[station_j]),
                    "separation_m": float(STATIONS_M[station_j] - STATIONS_M[station_i]),
                    "frozen_ar_covariance_m2": a2_covariance,
                    "unconditional_gaussian_covariance_m2": a3_covariance,
                    "unconditional_gaussian_minus_frozen_ar_covariance_m2": (
                        a3_covariance - a2_covariance
                    ),
                    "frozen_ar_correlation": a2_correlation,
                    "unconditional_gaussian_correlation": a3_correlation,
                    "unconditional_gaussian_minus_frozen_ar_correlation": (
                        a3_correlation - a2_correlation
                    ),
                }
            )
    if len(pair_rows) != 210:
        raise ValueError("H100 station-pair count differs from 210")

    separation_rows: list[dict[str, Any]] = []
    for separation in STATIONS_M[1:]:
        matching = [row for row in pair_rows if row["separation_m"] == float(separation)]
        if len(matching) != len(STATIONS_M) - int(separation / 5.0):
            raise ValueError("station-separation pair count differs")

        def mean_field(name: str) -> float:
            return float(
                np.mean(
                    np.asarray([row[name] for row in matching], dtype=np.float64),
                    dtype=np.float64,
                )
            )

        a2_covariance = mean_field("frozen_ar_covariance_m2")
        a3_covariance = mean_field("unconditional_gaussian_covariance_m2")
        a2_correlation = mean_field("frozen_ar_correlation")
        a3_correlation = mean_field("unconditional_gaussian_correlation")
        separation_rows.append(
            {
                "separation_m": float(separation),
                "station_pair_count": len(matching),
                "frozen_ar_mean_covariance_m2": a2_covariance,
                "unconditional_gaussian_mean_covariance_m2": a3_covariance,
                "unconditional_gaussian_minus_frozen_ar_mean_covariance_m2": (
                    a3_covariance - a2_covariance
                ),
                "frozen_ar_mean_correlation": a2_correlation,
                "unconditional_gaussian_mean_correlation": a3_correlation,
                "unconditional_gaussian_minus_frozen_ar_mean_correlation": (
                    a3_correlation - a2_correlation
                ),
            }
        )
    return pair_rows, separation_rows


def _sequence_rows(
    a2: _ArmMoments,
    a3: _ArmMoments,
    *,
    sequence_ids: StringArray,
    lengths: IntegerArray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, sequence_id in enumerate(sequence_ids):
        a2_off = float(a2.per_sequence_off_diagonal[index])
        a3_off = float(a3.per_sequence_off_diagonal[index])
        a2_adjacent = float(a2.per_sequence_adjacent[index])
        a3_adjacent = float(a3.per_sequence_adjacent[index])
        rows.append(
            {
                "sequence_id": str(sequence_id),
                "active_frame_count": int(lengths[index]),
                "frozen_ar_mean_off_diagonal_correlation": a2_off,
                "unconditional_gaussian_mean_off_diagonal_correlation": a3_off,
                "unconditional_gaussian_minus_frozen_ar_mean_off_diagonal_correlation": (
                    a3_off - a2_off
                ),
                "frozen_ar_mean_adjacent_station_correlation": a2_adjacent,
                "unconditional_gaussian_mean_adjacent_station_correlation": a3_adjacent,
                "unconditional_gaussian_minus_frozen_ar_mean_adjacent_station_correlation": (
                    a3_adjacent - a2_adjacent
                ),
            }
        )
    return rows


def _arm_difference(a3_value: float, a2_value: float) -> dict[str, float]:
    return {
        "frozen_ar": float(a2_value),
        "unconditional_gaussian": float(a3_value),
        "unconditional_gaussian_minus_frozen_ar": float(a3_value - a2_value),
    }


def run_spatial_structure_audit(
    a2_sample_directory: Path,
    a3_sample_directory: Path,
    output_directory: Path,
    *,
    contract: SpatialStructureAuditContract = (
        ACCEPTED_SPATIAL_STRUCTURE_AUDIT_CONTRACT
    ),
) -> tuple[Mapping[str, Any], int]:
    """Execute the closed descriptive audit against immutable A2/A3 samples."""

    a2 = _load_sample_arm(
        a2_sample_directory,
        sample_filename=A2_SAMPLE_FILENAME,
        summary_filename=A2_SUMMARY_FILENAME,
        sample_sha256=contract.a2_sample_sha256,
        summary_sha256=contract.a2_summary_sha256,
        arm_label="A2",
        contract=contract,
    )
    a2_moments = _calculate_arm(
        a2, correlation_tolerance=contract.correlation_tolerance
    )
    a3 = _load_sample_arm(
        a3_sample_directory,
        sample_filename=A3_SAMPLE_FILENAME,
        summary_filename=A3_SUMMARY_FILENAME,
        sample_sha256=contract.a3_sample_sha256,
        summary_sha256=contract.a3_summary_sha256,
        arm_label="A3",
        contract=contract,
    )
    if (
        not np.array_equal(a2.lengths, a3.lengths)
        or not np.array_equal(a2.stations, a3.stations)
        or not np.array_equal(a2.sequence_ids, a3.sequence_ids)
        or not np.array_equal(a2.feature_names, a3.feature_names)
    ):
        raise ValueError("A2 and A3 metadata axes differ")
    a3_moments = _calculate_arm(
        a3, correlation_tolerance=contract.correlation_tolerance
    )

    pair_rows, separation_rows = _pair_and_separation_rows(a2_moments, a3_moments)
    sequence_rows = _sequence_rows(
        a2_moments,
        a3_moments,
        sequence_ids=a2.sequence_ids,
        lengths=a2.lengths,
    )
    pair_differences = np.asarray(
        [
            row["unconditional_gaussian_minus_frozen_ar_correlation"]
            for row in pair_rows
        ],
        dtype=np.float64,
    )
    sequence_off_differences = (
        a3_moments.per_sequence_off_diagonal
        - a2_moments.per_sequence_off_diagonal
    )
    sequence_adjacent_differences = (
        a3_moments.per_sequence_adjacent - a2_moments.per_sequence_adjacent
    )
    pair_positive_count = int(np.count_nonzero(pair_differences > 0.0))
    sequence_off_positive_count = int(
        np.count_nonzero(sequence_off_differences > 0.0)
    )
    sequence_adjacent_positive_count = int(
        np.count_nonzero(sequence_adjacent_differences > 0.0)
    )

    pooled_off_a2 = mean_off_diagonal_correlation(a2_moments.pooled.correlation)
    pooled_off_a3 = mean_off_diagonal_correlation(a3_moments.pooled.correlation)
    pooled_adjacent_a2 = mean_adjacent_correlation(a2_moments.pooled.correlation)
    pooled_adjacent_a3 = mean_adjacent_correlation(a3_moments.pooled.correlation)
    macro_off_a2 = float(
        np.mean(a2_moments.per_sequence_off_diagonal, dtype=np.float64)
    )
    macro_off_a3 = float(
        np.mean(a3_moments.per_sequence_off_diagonal, dtype=np.float64)
    )
    macro_adjacent_a2 = float(
        np.mean(a2_moments.per_sequence_adjacent, dtype=np.float64)
    )
    macro_adjacent_a3 = float(
        np.mean(a3_moments.per_sequence_adjacent, dtype=np.float64)
    )

    matrices = {
        "arm_names": np.asarray(ARM_NAMES, dtype=np.str_),
        "stations_m": np.asarray(a2.stations, dtype=np.float64),
        "sequence_ids": np.asarray(a2.sequence_ids, dtype=np.str_),
        "lengths": np.asarray(a2.lengths, dtype=np.int64),
        "pooled_means_m": np.stack(
            (a2_moments.pooled.mean, a3_moments.pooled.mean)
        ).astype(np.float64),
        "pooled_covariances_m2": np.stack(
            (a2_moments.pooled.covariance, a3_moments.pooled.covariance)
        ).astype(np.float64),
        "pooled_correlations": np.stack(
            (a2_moments.pooled.correlation, a3_moments.pooled.correlation)
        ).astype(np.float64),
        "pooled_covariance_difference_m2": np.asarray(
            a3_moments.pooled.covariance - a2_moments.pooled.covariance,
            dtype=np.float64,
        ),
        "pooled_correlation_difference": np.asarray(
            a3_moments.pooled.correlation - a2_moments.pooled.correlation,
            dtype=np.float64,
        ),
        "per_sequence_covariances_m2": np.stack(
            (
                a2_moments.per_sequence_covariances,
                a3_moments.per_sequence_covariances,
            )
        ).astype(np.float64),
        "per_sequence_correlations": np.stack(
            (
                a2_moments.per_sequence_correlations,
                a3_moments.per_sequence_correlations,
            )
        ).astype(np.float64),
        "per_sequence_covariance_differences_m2": np.asarray(
            a3_moments.per_sequence_covariances
            - a2_moments.per_sequence_covariances,
            dtype=np.float64,
        ),
        "per_sequence_correlation_differences": np.asarray(
            a3_moments.per_sequence_correlations
            - a2_moments.per_sequence_correlations,
            dtype=np.float64,
        ),
    }
    if set(matrices) != MATRIX_KEYS:
        raise ValueError("internal matrix schema differs from the fixed contract")
    if any(
        value.dtype == np.dtype(object)
        for value in matrices.values()
    ):
        raise TypeError("object arrays are forbidden in the matrix artifact")

    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "post_hoc_a2_a3_cross_station_structure_audit",
        "arm_names_in_required_order": list(ARM_NAMES),
        "post_hoc_descriptive_audit": True,
        "accepted_artifact_run_role": "lineage_controlled_reproducibility_execution",
        "reviewer_preimplementation_calculation_disclosed": True,
        "reviewer_calculation_timing": (
            "complete fixed audit calculated after the statistic list was fixed "
            "and before workflow implementation"
        ),
        "statistic_added_or_removed_after_reviewer_calculation": False,
        "input_files_sha256": {
            A2_SAMPLE_FILENAME: contract.a2_sample_sha256,
            A2_SUMMARY_FILENAME: contract.a2_summary_sha256,
            A3_SAMPLE_FILENAME: contract.a3_sample_sha256,
            A3_SUMMARY_FILENAME: contract.a3_summary_sha256,
        },
        "source_sampling_seeds": {
            "frozen_ar": contract.a2_sampling_seed,
            "unconditional_gaussian": contract.a3_sampling_seed,
        },
        "sample_count_per_arm": contract.sample_count,
        "sequence_count": contract.sequence_count,
        "active_frame_count_per_draw": contract.active_frame_count,
        "generated_profile_count_per_arm": (
            contract.sample_count * contract.active_frame_count
        ),
        "station_count": len(STATIONS_M),
        "station_pair_count": len(pair_rows),
        "station_separation_count": len(separation_rows),
        "stations_m": STATIONS_M.tolist(),
        "feature_names_in_required_order": list(FEATURE_NAMES),
        "residual_unit": "m",
        "residual_sign": (
            "positive left of the pseudo-reference with respect to increasing station"
        ),
        "population_moment_formula": {
            "mean": "mean_n X[n,j]",
            "covariance": (
                "mean_n ((X[n,j] - mean[j]) * (X[n,k] - mean[k]))"
            ),
            "correlation": "covariance[j,k] / sqrt(covariance[j,j] * covariance[k,k])",
            "covariance_denominator": "N",
            "arithmetic_dtype": "float64",
            "correlation_roundoff_tolerance": contract.correlation_tolerance,
        },
        "weighting": {
            "pooled_active_frame": "all generated active frame profiles weighted equally",
            "equal_sequence_macro": "15 per-sequence statistics weighted equally",
            "padding_excluded": True,
            "sequence_dropped": False,
        },
        "pooled_correlation_summary": {
            "mean_off_diagonal": _arm_difference(pooled_off_a3, pooled_off_a2),
            "mean_adjacent_station": _arm_difference(
                pooled_adjacent_a3, pooled_adjacent_a2
            ),
            "pairs_with_higher_unconditional_gaussian_correlation": {
                "count": pair_positive_count,
                "denominator": len(pair_rows),
                "fraction": float(pair_positive_count / len(pair_rows)),
                "interpretation": (
                    "dependent descriptive tally; not independent pair comparisons"
                ),
            },
            "separation_profile": separation_rows,
        },
        "equal_sequence_macro_correlation_summary": {
            "mean_off_diagonal": _arm_difference(macro_off_a3, macro_off_a2),
            "mean_adjacent_station": _arm_difference(
                macro_adjacent_a3, macro_adjacent_a2
            ),
        },
        "sequence_directional_counts": {
            "off_diagonal_positive_unconditional_gaussian_minus_frozen_ar": {
                "count": sequence_off_positive_count,
                "denominator": contract.sequence_count,
            },
            "adjacent_positive_unconditional_gaussian_minus_frozen_ar": {
                "count": sequence_adjacent_positive_count,
                "denominator": contract.sequence_count,
            },
            "interpretation": (
                "direction only; not uniform magnitude and not absence of a "
                "relationship with sequence length"
            ),
        },
        "temporal_dependence": {
            "frozen_ar": (
                "serially dependent finite-horizon sequences with one reset per sequence"
            ),
            "unconditional_gaussian": "independent active frames with order zero",
            "equal_nominal_profile_count_implies_equal_estimation_precision": False,
            "scalar_effective_sample_size_reported": False,
        },
        "interpretation_limits": [
            "The audit describes only these exact accepted generated ensembles.",
            "It does not estimate either input difference's contribution to the planner result.",
            "Marginal scale and cross-station coherence are not causally separated.",
            "Per-sequence A2 moments mix reset, transient, conditional, and later free-running profiles.",
            "No journey-level, planner-level, vehicle-level, or BMW generalization is estimated.",
            "No planner benefit, comfort, safety, production, or physical-ground-truth claim is authorized.",
            "The v0.16 and v0.16.1 conclusions and length qualifier remain unchanged.",
        ],
        "strict_monotonicity_claimed": False,
        "p_value_or_interval_reported": False,
        "planner_executed": False,
        "planner_benefit_claimed": False,
        "bmw_planner_behavior_claimed": False,
        "journey_level_generalization_estimated": False,
        "causal_contribution_estimated": False,
        "marginal_scale_and_spatial_coherence_causally_separated": False,
        "comfort_safety_or_production_readiness_evaluated": False,
        "physical_ground_truth_evaluated": False,
        "model_refit": False,
        "residual_resampling": False,
        "final_model_selection_authorized": False,
        "new_a4_arm_authorized": False,
        "generated_outputs_remain_outside_version_control": True,
        "files_in_output_directory": list(OUTPUT_FILENAMES),
        "matrix_array_schemas": {
            name: {"dtype": str(value.dtype), "shape": list(value.shape)}
            for name, value in matrices.items()
        },
        "csv_columns": {
            PAIR_FILENAME: list(PAIR_FIELDS),
            SEPARATION_FILENAME: list(SEPARATION_FIELDS),
            SEQUENCE_FILENAME: list(SEQUENCE_FIELDS),
        },
    }

    ensure_empty_output_directory(output_directory)
    matrix_path = output_directory / MATRICES_FILENAME
    pair_path = output_directory / PAIR_FILENAME
    separation_path = output_directory / SEPARATION_FILENAME
    sequence_path = output_directory / SEQUENCE_FILENAME
    summary_path = output_directory / SUMMARY_FILENAME
    np.savez_compressed(matrix_path, **matrices)
    write_csv_rows(pair_path, PAIR_FIELDS, pair_rows)
    write_csv_rows(separation_path, SEPARATION_FIELDS, separation_rows)
    write_csv_rows(sequence_path, SEQUENCE_FIELDS, sequence_rows)
    summary["output_files_sha256"] = {
        MATRICES_FILENAME: sha256_file(matrix_path),
        PAIR_FILENAME: sha256_file(pair_path),
        SEPARATION_FILENAME: sha256_file(separation_path),
        SEQUENCE_FILENAME: sha256_file(sequence_path),
    }
    summary["summary_self_hash_excluded_to_avoid_recursive_hash"] = True
    write_strict_json(summary_path, summary)
    return summary, 0


__all__ = [
    "ARM_NAMES",
    "FEATURE_NAMES",
    "MATRIX_KEYS",
    "PAIR_FIELDS",
    "SEPARATION_FIELDS",
    "SEQUENCE_FIELDS",
    "STATIONS_M",
    "run_spatial_structure_audit",
]
