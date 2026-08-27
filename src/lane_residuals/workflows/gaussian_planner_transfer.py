"""A3-only v0.16.1 transfer through the accepted v0.16 reference planner."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.reference_planner import ReferencePlannerConfig
from ..io.expanded_sequence_dataset import read_json_object
from ..io.reports import write_strict_json
from .gaussian_planner_transfer_contract import (
    ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT,
    GAUSSIAN_SAMPLE_FILENAME,
    GAUSSIAN_SAMPLE_SUMMARY_FILENAME,
    TRANSFER_FRAME_FILENAME,
    TRANSFER_SEQUENCE_FILENAME,
    TRANSFER_SUMMARY_FILENAME,
    GaussianPlannerTransferContract,
    VERSION,
)
from .reference_planner_sensitivity import (
    ARM_NAMES,
    FRAME_FILENAME,
    METRIC_NAMES,
    SCENARIO_KEYS,
    SEQUENCE_FILENAME,
    SUMMARY_OUTPUT_FILENAME,
    _frame_intervals_s,
    _run_arm_sequence,
)
from .sequence_contract import ensure_empty_output_directory, sha256_file
from .unconditional_gaussian_residual_sampling import (
    _integer_array,
    _load_npz,
    _string_array,
    _validate_scenario,
)

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]
StringArray = NDArray[np.str_]

GAUSSIAN_SAMPLE_KEYS = frozenset(
    {"feature_names", "lengths", "residual_samples_m", "sequence_ids", "stations_m"}
)
V016_FRAME_KEYS = frozenset(
    {"arm_names", "frame_metrics", "lengths", "metric_names", "sequence_ids"}
)
TRANSFER_FRAME_KEYS = frozenset(
    {"arm_name", "frame_metrics", "lengths", "metric_names", "sequence_ids"}
)
PRIMARY_METRICS = (
    "p95_abs_curvature_rate_per_m_s",
    "p95_abs_lateral_jerk_mps3",
    "mean_abs_lateral_error_m",
    "integrated_abs_lateral_error_m_s",
)
PRIMARY_DIRECTIONS = {
    "p95_abs_curvature_rate_per_m_s": "higher",
    "p95_abs_lateral_jerk_mps3": "higher",
    "mean_abs_lateral_error_m": "lower",
    "integrated_abs_lateral_error_m_s": "lower",
}
SEQUENCE_FIELDS = (
    "arm",
    "sample_index",
    "sequence_id",
    "active_frame_count",
    *PRIMARY_METRICS,
    "maximum_abs_lateral_error_m",
    "final_abs_lateral_error_m",
    "fraction_beyond_lateral_threshold",
    "constraint_violation_fraction",
    "mean_objective",
    "curvature_violation_fraction",
    "curvature_rate_violation_fraction",
    "lateral_acceleration_violation_fraction",
    "lateral_jerk_violation_fraction",
    "lateral_deviation_violation_fraction",
)


def _validate_gaussian_samples(
    directory: Path,
    *,
    scenario_archive: Path,
    lengths: IntegerArray,
    sequence_ids: StringArray,
    stations: FloatArray,
    maximum_time: int,
    contract: GaussianPlannerTransferContract,
) -> tuple[FloatArray, Mapping[str, Any], Path, Path]:
    expected = {GAUSSIAN_SAMPLE_FILENAME, GAUSSIAN_SAMPLE_SUMMARY_FILENAME}
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("A3 sample directory filename set differs")
    sample_path = directory / GAUSSIAN_SAMPLE_FILENAME
    summary_path = directory / GAUSSIAN_SAMPLE_SUMMARY_FILENAME
    summary = read_json_object(summary_path)
    if (
        summary.get("version") != VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose") != "unconditional_gaussian_planner_transfer_sampling"
        or summary.get("arm") != "unconditional_gaussian"
        or summary.get("sample_file") != GAUSSIAN_SAMPLE_FILENAME
        or summary.get("sample_file_sha256") != sha256_file(sample_path)
        or summary.get("sample_count") != contract.sample_count
        or summary.get("random_seed") != contract.gaussian_sampling_seed
        or summary.get("sequence_count") != contract.sequence_count
        or summary.get("active_frame_count") != contract.active_frame_count
        or summary.get("scenario_archive_sha256") != sha256_file(scenario_archive)
        or summary.get("accepted_a2_sample_file_sha256") != contract.a2_sample_sha256
        or summary.get("development_model_sha256")
        != contract.development_model_sha256
        or summary.get("temporal_dependency_order") != 0
        or summary.get("active_frames_are_independent_draws") is not True
        or summary.get("common_random_numbers_with_a1_a2_used") is not False
        or summary.get("paired_residual_profiles_with_a1_a2_used") is not False
        or summary.get("planner_executed") is not False
    ):
        raise ValueError("A3 sampling summary differs from v0.16.1 contract")
    standardizer_audit = summary.get("standardizer_equality_audit")
    diagnostics = summary.get("marginal_diagnostics_by_station")
    diagnostic_keys = {
        "station_m",
        "a3_mean_m",
        "a2_mean_m",
        "a3_minus_a2_mean_m",
        "a3_population_sd_m",
        "a2_population_sd_m",
        "a3_over_a2_population_sd_ratio",
    }
    diagnostic_schema_valid = isinstance(diagnostics, list) and len(diagnostics) == 21
    if diagnostic_schema_valid:
        for index, row in enumerate(diagnostics):
            if not isinstance(row, Mapping) or set(row) != diagnostic_keys:
                diagnostic_schema_valid = False
                break
            values = np.asarray(list(row.values()), dtype=np.float64)
            if (
                not np.all(np.isfinite(values))
                or float(row["station_m"]) != float(stations[index])
                or float(row["a2_population_sd_m"]) <= 0.0
                or float(row["a3_population_sd_m"]) <= 0.0
                or float(row["a3_over_a2_population_sd_ratio"]) <= 0.0
            ):
                diagnostic_schema_valid = False
                break
    if (
        not isinstance(standardizer_audit, Mapping)
        or standardizer_audit.get("elementwise_exact_equal") is not True
        or standardizer_audit.get("tolerance_based_acceptance_used") is not False
        or not diagnostic_schema_valid
    ):
        raise ValueError("A3 standardizer or marginal diagnostic record is incomplete")
    payload = _load_npz(sample_path, GAUSSIAN_SAMPLE_KEYS)
    residuals = np.asarray(payload["residual_samples_m"], dtype=np.float64)
    sample_lengths = _integer_array(payload["lengths"], "A3 lengths")
    sample_ids = _string_array(payload["sequence_ids"], "A3 sequence IDs")
    sample_stations = np.asarray(payload["stations_m"], dtype=np.float64)
    feature_names = tuple(
        _string_array(payload["feature_names"], "A3 feature names").tolist()
    )
    if residuals.shape != (
        contract.sample_count,
        contract.sequence_count,
        maximum_time,
        21,
    ):
        raise ValueError("A3 residual sample shape differs")
    if feature_names != (
        "speed_mps",
        "estimated_mean_abs_curvature_per_m",
        "estimated_curvature_delta_per_m",
        "confidence_near_mean",
        "confidence_middle_mean",
        "confidence_far_mean",
    ):
        raise ValueError("A3 feature order differs from BMW schema v1")
    if not np.array_equal(sample_lengths, lengths) or not np.array_equal(
        sample_ids, sequence_ids
    ):
        raise ValueError("A3 and scenario sequence identities differ")
    if not np.array_equal(sample_stations, stations):
        raise ValueError("A3 and scenario stations differ")
    time_mask = np.arange(maximum_time)[None, :] < lengths[:, None]
    if not np.all(np.isfinite(residuals)) or np.any(residuals[:, ~time_mask] != 0.0):
        raise ValueError("A3 samples are non-finite or have nonzero padding")
    return residuals, summary, sample_path, summary_path


def _read_v016_sequence_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = (
            "arm",
            "sample_index",
            "sequence_id",
            "active_frame_count",
            "integrated_abs_lateral_error_m_s",
            "maximum_abs_lateral_error_m",
            "fraction_beyond_lateral_threshold",
            "constraint_violation_fraction",
            "final_abs_lateral_error_m",
        )
        if tuple(reader.fieldnames or ()) != expected:
            raise ValueError("v0.16 sequence metric columns differ")
        return tuple(dict(row) for row in reader)


def _validate_v016_inputs(
    directory: Path,
    *,
    lengths: IntegerArray,
    sequence_ids: StringArray,
    maximum_time: int,
    contract: GaussianPlannerTransferContract,
) -> tuple[FloatArray, ReferencePlannerConfig, Mapping[str, Any], Path, Path, Path]:
    expected = {FRAME_FILENAME, SEQUENCE_FILENAME, SUMMARY_OUTPUT_FILENAME}
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("accepted v0.16 sensitivity directory filename set differs")
    frame_path = directory / FRAME_FILENAME
    sequence_path = directory / SEQUENCE_FILENAME
    summary_path = directory / SUMMARY_OUTPUT_FILENAME
    actual_hashes = (
        sha256_file(frame_path),
        sha256_file(sequence_path),
        sha256_file(summary_path),
    )
    expected_hashes = (
        contract.v016_frame_sha256,
        contract.v016_sequence_sha256,
        contract.v016_summary_sha256,
    )
    if actual_hashes != expected_hashes:
        raise ValueError("v0.16 sensitivity lineage differs from accepted hashes")
    summary = read_json_object(summary_path)
    if (
        summary.get("version") != "0.16.0"
        or summary.get("status") != "complete"
        or summary.get("purpose") != "reference_planner_temporal_order_sensitivity"
        or summary.get("arms_in_required_order") != list(ARM_NAMES)
        or summary.get("primary_comparison") != "frozen_ar_minus_time_shuffled_ar"
        or summary.get("sample_count") != contract.sample_count
        or summary.get("sequence_count") != contract.sequence_count
        or summary.get("active_frame_count") != contract.active_frame_count
        or summary.get("shuffle_seed") != contract.shuffle_seed
        or summary.get("shuffled_frame_positions_changed")
        != contract.shuffled_frame_positions_changed
        or summary.get("scenario_archive_sha256") != contract.scenario_sha256
        or summary.get("source_sample_file_sha256") != contract.a2_sample_sha256
        or summary.get("source_sampling_random_seed") != contract.a2_sampling_seed
        or summary.get("frame_metrics_file_sha256") != contract.v016_frame_sha256
        or summary.get("sequence_metrics_file_sha256") != contract.v016_sequence_sha256
        or summary.get("time_shuffle_preserves_frame_profiles_exactly_within_sequence")
        is not True
        or summary.get("time_shuffle_crosses_sequence_boundaries") is not False
        or summary.get("planner_benefit_claimed") is not False
        or summary.get("bmw_planner_behavior_claimed") is not False
        or summary.get("journey_level_generalization_estimated") is not False
    ):
        raise ValueError("accepted v0.16 sensitivity summary differs")
    config_payload = summary.get("planner_config")
    config_names = {field.name for field in fields(ReferencePlannerConfig)}
    if not isinstance(config_payload, Mapping) or set(config_payload) != config_names:
        raise ValueError("accepted v0.16 planner configuration fields differ")
    config = ReferencePlannerConfig(**dict(config_payload))
    if asdict(config) != dict(config_payload):
        raise ValueError("accepted v0.16 planner configuration values differ")
    payload = _load_npz(frame_path, V016_FRAME_KEYS)
    frame_metrics = np.asarray(payload["frame_metrics"], dtype=np.float64)
    metric_names = tuple(
        _string_array(payload["metric_names"], "v0.16 metric names").tolist()
    )
    arm_names = tuple(_string_array(payload["arm_names"], "v0.16 arm names").tolist())
    frame_lengths = _integer_array(payload["lengths"], "v0.16 lengths")
    frame_ids = _string_array(payload["sequence_ids"], "v0.16 sequence IDs")
    if metric_names != METRIC_NAMES or arm_names != ARM_NAMES:
        raise ValueError("v0.16 frame metric axes differ")
    if frame_metrics.shape != (
        len(ARM_NAMES),
        contract.sample_count,
        contract.sequence_count,
        maximum_time,
        len(METRIC_NAMES),
    ):
        raise ValueError("v0.16 frame metric shape differs")
    if not np.array_equal(frame_lengths, lengths) or not np.array_equal(
        frame_ids, sequence_ids
    ):
        raise ValueError("v0.16 and scenario sequence identities differ")
    time_mask = np.arange(maximum_time)[None, :] < lengths[:, None]
    if not np.all(np.isfinite(frame_metrics)) or np.any(frame_metrics[:, :, ~time_mask] != 0.0):
        raise ValueError("v0.16 frame metrics are non-finite or have nonzero padding")
    rows = _read_v016_sequence_rows(sequence_path)
    if len(rows) != len(ARM_NAMES) * contract.sample_count * contract.sequence_count:
        raise ValueError("v0.16 sequence metric row count differs")
    observed_keys = {
        (row["arm"], int(row["sample_index"]), row["sequence_id"])
        for row in rows
    }
    expected_keys = {
        (arm, sample, str(sequence_id))
        for arm in ARM_NAMES
        for sample in range(contract.sample_count)
        for sequence_id in sequence_ids
    }
    if observed_keys != expected_keys:
        raise ValueError("v0.16 sequence metric identities differ")
    a0_sequence_violation = np.zeros(
        (contract.sample_count, contract.sequence_count), dtype=np.float64
    )
    for sample in range(contract.sample_count):
        for sequence, length in enumerate(lengths):
            a0_sequence_violation[sample, sequence] = np.mean(
                frame_metrics[0, sample, sequence, : int(length), 7]
            )
    a0_macro = float(np.mean(a0_sequence_violation))
    if round(a0_macro, 6) != contract.a0_macro_constraint_violation_fraction_rounded_6:
        raise ValueError("v0.16 A0 content invariant differs")
    return frame_metrics, config, summary, frame_path, sequence_path, summary_path


def _sequence_metrics(
    frame_metrics: FloatArray,
    *,
    lengths: IntegerArray,
    timestamps: IntegerArray,
    config: ReferencePlannerConfig,
) -> dict[str, FloatArray]:
    if frame_metrics.ndim != 4 or frame_metrics.shape[-1] != len(METRIC_NAMES):
        raise ValueError("arm frame metrics must have shape [S,B,T,8]")
    sample_count, sequence_count, _, _ = frame_metrics.shape
    result = {
        name: np.zeros((sample_count, sequence_count), dtype=np.float64)
        for name in SEQUENCE_FIELDS[4:]
    }
    for sequence_index, raw_length in enumerate(lengths):
        length = int(raw_length)
        intervals = _frame_intervals_s(timestamps[sequence_index, :length])
        values = frame_metrics[:, sequence_index, :length]
        absolute_lateral = np.abs(values[:, :, 0])
        result["p95_abs_curvature_rate_per_m_s"][:, sequence_index] = np.quantile(
            np.abs(values[:, :, 3]), 0.95, axis=1, method="linear"
        )
        result["p95_abs_lateral_jerk_mps3"][:, sequence_index] = np.quantile(
            np.abs(values[:, :, 5]), 0.95, axis=1, method="linear"
        )
        result["mean_abs_lateral_error_m"][:, sequence_index] = np.mean(
            absolute_lateral, axis=1
        )
        result["integrated_abs_lateral_error_m_s"][:, sequence_index] = np.sum(
            absolute_lateral * intervals[None, :], axis=1
        )
        result["maximum_abs_lateral_error_m"][:, sequence_index] = np.max(
            absolute_lateral, axis=1
        )
        result["final_abs_lateral_error_m"][:, sequence_index] = absolute_lateral[:, -1]
        result["fraction_beyond_lateral_threshold"][:, sequence_index] = np.mean(
            absolute_lateral > config.lateral_excursion_threshold_m, axis=1
        )
        result["constraint_violation_fraction"][:, sequence_index] = np.mean(
            values[:, :, 7], axis=1
        )
        result["mean_objective"][:, sequence_index] = np.mean(values[:, :, 6], axis=1)
        for name, index, threshold in (
            ("curvature_violation_fraction", 2, config.maximum_abs_curvature_per_m),
            (
                "curvature_rate_violation_fraction",
                3,
                config.maximum_abs_curvature_rate_per_m_s,
            ),
            (
                "lateral_acceleration_violation_fraction",
                4,
                config.maximum_abs_lateral_acceleration_mps2,
            ),
            (
                "lateral_jerk_violation_fraction",
                5,
                config.maximum_abs_lateral_jerk_mps3,
            ),
            (
                "lateral_deviation_violation_fraction",
                0,
                config.maximum_abs_lateral_deviation_m,
            ),
        ):
            result[name][:, sequence_index] = np.mean(
                np.abs(values[:, :, index]) > threshold, axis=1
            )
    return result


def _macro_values(
    metrics: Mapping[str, FloatArray],
    *,
    lengths: IntegerArray,
    minimum_p95_frames: int,
) -> tuple[dict[str, FloatArray], dict[str, FloatArray]]:
    p95_eligible = lengths >= minimum_p95_frames
    if not np.any(p95_eligible):
        raise ValueError("no sequence is eligible for the primary p95 macro")
    primary: dict[str, FloatArray] = {}
    robustness: dict[str, FloatArray] = {}
    for name in PRIMARY_METRICS:
        values = metrics[name]
        if name.startswith("p95_"):
            primary[name] = np.mean(values[:, p95_eligible], axis=1)
            robustness[name] = np.mean(values, axis=1)
        else:
            primary[name] = np.mean(values, axis=1)
    return primary, robustness


def _pooled_frame_summary(
    frame_metrics: FloatArray,
    *,
    lengths: IntegerArray,
) -> dict[str, float]:
    time_mask = np.arange(frame_metrics.shape[2])[None, :] < lengths[:, None]
    active = frame_metrics[:, time_mask]
    return {
        "active_values_per_metric": int(active.shape[0] * active.shape[1]),
        "p95_abs_curvature_rate_per_m_s": float(
            np.quantile(np.abs(active[:, :, 3]), 0.95, method="linear")
        ),
        "p95_abs_lateral_jerk_mps3": float(
            np.quantile(np.abs(active[:, :, 5]), 0.95, method="linear")
        ),
        "mean_abs_lateral_error_m": float(np.mean(np.abs(active[:, :, 0]))),
        "constraint_violation_fraction": float(np.mean(active[:, :, 7])),
        "mean_objective": float(np.mean(active[:, :, 6])),
    }


def _comparison_summary(
    *,
    a3_macro: Mapping[str, FloatArray],
    a2_macro: Mapping[str, FloatArray],
    a3_sequence: Mapping[str, FloatArray],
    a2_sequence: Mapping[str, FloatArray],
    lengths: IntegerArray,
    sequence_ids: StringArray,
    contract: GaussianPlannerTransferContract,
) -> tuple[dict[str, Any], dict[str, bool], str]:
    bootstrap: dict[str, NDArray[np.float64]] = {
        name: np.zeros(contract.bootstrap_replicates, dtype=np.float64)
        for name in PRIMARY_METRICS
    }
    generator = np.random.default_rng(contract.bootstrap_seed)
    for replicate in range(contract.bootstrap_replicates):
        a3_indices = generator.integers(0, contract.sample_count, contract.sample_count)
        a2_indices = generator.integers(0, contract.sample_count, contract.sample_count)
        for name in PRIMARY_METRICS:
            bootstrap[name][replicate] = float(
                np.mean(a3_macro[name][a3_indices])
                - np.mean(a2_macro[name][a2_indices])
            )
    comparisons: dict[str, Any] = {}
    metric_pass: dict[str, bool] = {}
    for name in PRIMARY_METRICS:
        interval = np.quantile(
            bootstrap[name], [0.025, 0.975], method="linear"
        )
        direction = PRIMARY_DIRECTIONS[name]
        passed = bool(interval[0] > 0.0) if direction == "higher" else bool(interval[1] < 0.0)
        metric_pass[name] = passed
        eligible = (
            lengths >= contract.p95_minimum_active_frames
            if name.startswith("p95_")
            else np.ones(len(lengths), dtype=np.bool_)
        )
        per_sequence_difference = np.mean(a3_sequence[name], axis=0) - np.mean(
            a2_sequence[name], axis=0
        )
        agreement = per_sequence_difference > 0.0
        if direction == "lower":
            agreement = per_sequence_difference < 0.0
        eligible_ids = np.asarray(sequence_ids)[eligible]
        comparisons[name] = {
            "direction": direction,
            "a3_macro_mean": float(np.mean(a3_macro[name])),
            "a2_macro_mean": float(np.mean(a2_macro[name])),
            "a3_minus_a2_mean_difference": float(
                np.mean(a3_macro[name]) - np.mean(a2_macro[name])
            ),
            "independent_two_sample_bootstrap_interval_2_5_97_5_percent": [
                float(value) for value in interval
            ],
            "interval_outcome": (
                "hypothesised_direction"
                if passed
                else (
                    "indeterminate"
                    if interval[0] <= 0.0 <= interval[1]
                    else "opposite_direction"
                )
            ),
            "eligible_sequence_count": int(np.count_nonzero(eligible)),
            "hypothesised_sign_sequence_agreement": {
                "k": int(np.count_nonzero(agreement[eligible])),
                "N": int(np.count_nonzero(eligible)),
                "sequence_ids": [
                    str(value)
                    for value in eligible_ids[agreement[eligible]].tolist()
                ],
                "is_hypothesis_test": False,
                "changes_pass_fail_rule": False,
            },
        }
    family_pass = {
        "smoothness": all(metric_pass[name] for name in PRIMARY_METRICS[:2]),
        "deviation": all(metric_pass[name] for name in PRIMARY_METRICS[2:]),
    }
    if all(family_pass.values()):
        decision = "full support"
    elif family_pass["smoothness"]:
        decision = "partial support: smoothness family only"
    elif family_pass["deviation"]:
        decision = "partial support: deviation family only"
    else:
        decision = "unsupported"
    return comparisons, family_pass, decision


def _descriptive_arm_comparison(
    left: Mapping[str, FloatArray], right: Mapping[str, FloatArray]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in PRIMARY_METRICS:
        left_mean = float(np.mean(left[name]))
        right_mean = float(np.mean(right[name]))
        result[name] = {
            "left_mean": left_mean,
            "right_mean": right_mean,
            "left_minus_right": left_mean - right_mean,
            "left_over_right_ratio": left_mean / right_mean if right_mean != 0.0 else None,
        }
    return result


def run_gaussian_planner_transfer(
    *,
    gaussian_sample_directory: Path,
    scenario_archive: Path,
    accepted_v016_sensitivity_directory: Path,
    output_directory: Path,
    contract: GaussianPlannerTransferContract = (
        ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT
    ),
) -> tuple[dict[str, Any], int]:
    """Execute only A3 and compare it with immutable accepted A1/A2 metrics."""

    _, lengths, sequence_ids, stations = _validate_scenario(
        scenario_archive, contract=contract
    )
    scenario = _load_npz(scenario_archive, SCENARIO_KEYS)
    conditions = np.asarray(scenario["conditions"], dtype=np.float64)
    paths = np.asarray(scenario["nominal_paths_xy_m"], dtype=np.float64)
    timestamps = _integer_array(scenario["timestamps_ns"], "scenario timestamps")
    maximum_time = conditions.shape[1]
    a3_residuals, a3_summary, a3_sample_path, a3_summary_path = (
        _validate_gaussian_samples(
            gaussian_sample_directory,
            scenario_archive=scenario_archive,
            lengths=lengths,
            sequence_ids=sequence_ids,
            stations=stations,
            maximum_time=maximum_time,
            contract=contract,
        )
    )
    v016_frames, config, v016_summary, v016_frame_path, v016_sequence_path, v016_summary_path = (
        _validate_v016_inputs(
            accepted_v016_sensitivity_directory,
            lengths=lengths,
            sequence_ids=sequence_ids,
            maximum_time=maximum_time,
            contract=contract,
        )
    )
    a3_frames = np.zeros(
        (
            contract.sample_count,
            contract.sequence_count,
            maximum_time,
            len(METRIC_NAMES),
        ),
        dtype=np.float64,
    )
    for sample_index in range(contract.sample_count):
        for sequence_index, raw_length in enumerate(lengths):
            active = int(raw_length)
            metrics, _ = _run_arm_sequence(
                residuals=a3_residuals[sample_index, sequence_index, :active],
                paths=paths[sequence_index, :active],
                timestamps=timestamps[sequence_index, :active],
                speeds=conditions[sequence_index, :active, 0],
                stations=stations,
                config=config,
            )
            a3_frames[sample_index, sequence_index, :active] = metrics
    time_mask = np.arange(maximum_time)[None, :] < lengths[:, None]
    if not np.all(np.isfinite(a3_frames)) or np.any(a3_frames[:, ~time_mask] != 0.0):
        raise ValueError("A3 planner metrics are non-finite or have nonzero padding")

    frames_by_arm = {
        "time_shuffled_ar": v016_frames[1],
        "frozen_ar": v016_frames[2],
        "unconditional_gaussian": a3_frames,
    }
    sequence_metrics = {
        arm: _sequence_metrics(
            frames,
            lengths=lengths,
            timestamps=timestamps,
            config=config,
        )
        for arm, frames in frames_by_arm.items()
    }
    macro: dict[str, dict[str, FloatArray]] = {}
    p95_robustness: dict[str, dict[str, FloatArray]] = {}
    for arm, metrics in sequence_metrics.items():
        macro[arm], p95_robustness[arm] = _macro_values(
            metrics,
            lengths=lengths,
            minimum_p95_frames=contract.p95_minimum_active_frames,
        )
    comparisons, family_pass, decision = _comparison_summary(
        a3_macro=macro["unconditional_gaussian"],
        a2_macro=macro["frozen_ar"],
        a3_sequence=sequence_metrics["unconditional_gaussian"],
        a2_sequence=sequence_metrics["frozen_ar"],
        lengths=lengths,
        sequence_ids=sequence_ids,
        contract=contract,
    )
    sequence_rows: list[dict[str, Any]] = []
    for sample_index in range(contract.sample_count):
        for sequence_index, sequence_id in enumerate(sequence_ids):
            sequence_rows.append(
                {
                    "arm": "unconditional_gaussian",
                    "sample_index": sample_index,
                    "sequence_id": str(sequence_id),
                    "active_frame_count": int(lengths[sequence_index]),
                    **{
                        name: float(
                            sequence_metrics["unconditional_gaussian"][name][
                                sample_index, sequence_index
                            ]
                        )
                        for name in SEQUENCE_FIELDS[4:]
                    },
                }
            )
    short_sequences = [
        {"sequence_id": str(sequence_ids[index]), "active_frame_count": int(length)}
        for index, length in enumerate(lengths)
        if int(length) < contract.p95_minimum_active_frames
    ]
    per_sequence_primary_means = {
        arm: [
            {
                "sequence_id": str(sequence_ids[index]),
                "active_frame_count": int(lengths[index]),
                **{
                    name: float(np.mean(sequence_metrics[arm][name][:, index]))
                    for name in PRIMARY_METRICS
                },
            }
            for index in range(contract.sequence_count)
        ]
        for arm in frames_by_arm
    }
    pooled = {
        arm: _pooled_frame_summary(frames, lengths=lengths)
        for arm, frames in frames_by_arm.items()
    }

    ensure_empty_output_directory(output_directory)
    frame_path = output_directory / TRANSFER_FRAME_FILENAME
    np.savez_compressed(
        frame_path,
        frame_metrics=a3_frames,
        metric_names=np.asarray(METRIC_NAMES, dtype=np.str_),
        arm_name=np.asarray("unconditional_gaussian", dtype=np.str_),
        lengths=lengths,
        sequence_ids=sequence_ids,
    )
    sequence_path = output_directory / TRANSFER_SEQUENCE_FILENAME
    with sequence_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SEQUENCE_FIELDS)
        writer.writeheader()
        writer.writerows(sequence_rows)
    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "unconditional_gaussian_reference_planner_transfer",
        "newly_executed_arm": "unconditional_gaussian",
        "immutable_accepted_arms": ["time_shuffled_ar", "frozen_ar"],
        "a0_rerun": False,
        "a1_a2_rerun": False,
        "primary_comparison": "unconditional_gaussian_minus_frozen_ar",
        "sample_count_per_arm": contract.sample_count,
        "sequence_count": contract.sequence_count,
        "active_frame_count": contract.active_frame_count,
        "gaussian_sampling_seed": contract.gaussian_sampling_seed,
        "bootstrap_seed": contract.bootstrap_seed,
        "bootstrap_replicates": contract.bootstrap_replicates,
        "bootstrap_resampling_unit": "Monte Carlo draw",
        "bootstrap_is_independent_two_sample": True,
        "bootstrap_quantile_method": "linear",
        "interval_label": (
            "independent two-sample Monte Carlo interval with fixed cohort; "
            "not dataset, journey, or model-fitting uncertainty"
        ),
        "planner_config": asdict(config),
        "scenario_archive_sha256": sha256_file(scenario_archive),
        "gaussian_sample_file_sha256": sha256_file(a3_sample_path),
        "gaussian_sample_summary_sha256": sha256_file(a3_summary_path),
        "accepted_v016_frame_metrics_sha256": sha256_file(v016_frame_path),
        "accepted_v016_sequence_metrics_sha256": sha256_file(v016_sequence_path),
        "accepted_v016_summary_sha256": sha256_file(v016_summary_path),
        "accepted_a2_sample_file_sha256": a3_summary[
            "accepted_a2_sample_file_sha256"
        ],
        "accepted_v016_shuffle_seed": v016_summary["shuffle_seed"],
        "accepted_v016_shuffled_frame_positions_changed": v016_summary[
            "shuffled_frame_positions_changed"
        ],
        "input_content_invariants": {
            "scenario_shape": list(paths.shape),
            "scenario_dtype": str(paths.dtype),
            "a3_sample_shape": list(a3_residuals.shape),
            "a3_sample_dtype": str(a3_residuals.dtype),
            "accepted_v016_frame_shape": list(v016_frames.shape),
            "accepted_v016_frame_dtype": str(v016_frames.dtype),
            "active_frame_count": int(np.sum(lengths)),
            "shuffled_frame_positions_changed": v016_summary[
                "shuffled_frame_positions_changed"
            ],
            "a0_macro_constraint_violation_fraction": (
                contract.a0_macro_constraint_violation_fraction_rounded_6
            ),
        },
        "primary_metric_order": list(PRIMARY_METRICS),
        "primary_metric_directions": dict(PRIMARY_DIRECTIONS),
        "posthoc_selection_disclosure": (
            "The four primary metrics, p95 level, and directions came from "
            "accepted v0.16 A1/A2 descriptions before A3 existed."
        ),
        "pre_run_minimum_detectable_difference_context": {
            "source": "accepted A1/A2 ensembles with A1 as an A3 variance proxy",
            "is_gate": False,
            "p95_abs_curvature_rate_per_m_s": {
                "absolute": 0.0130,
                "percent_of_a2_level": 6.2,
            },
            "p95_abs_lateral_jerk_mps3": {
                "absolute": 5.431,
                "percent_of_a2_level": 7.1,
            },
            "mean_abs_lateral_error_m": {
                "absolute": 0.00212,
                "percent_of_a2_level": 3.0,
            },
            "integrated_abs_lateral_error_m_s": {
                "absolute": 0.03405,
                "percent_of_a2_level": 2.3,
            },
        },
        "p95_quantile": 0.95,
        "p95_quantile_method": "linear",
        "p95_minimum_active_frames_primary": contract.p95_minimum_active_frames,
        "p95_short_sequences_excluded_from_primary": short_sequences,
        "p95_all_sequence_robustness_macro_means": {
            arm: {
                name: float(np.mean(values))
                for name, values in p95_robustness[arm].items()
            }
            for arm in p95_robustness
        },
        "primary_a3_minus_a2_comparisons": comparisons,
        "hypothesis_family_pass": family_pass,
        "smoothness_family_role": "manipulation_check",
        "deviation_family_role": "informative_transfer_test",
        "overall_decision": decision,
        "full_planner_observable_trade_supported": decision == "full support",
        "temporal_model_difference_planner_observable_with_real_model": (
            decision == "full support"
        ),
        "distributional_ranking_alone_does_not_determine_planner_behavior_supported": (
            decision == "full support"
        ),
        "per_sequence_primary_metric_means": per_sequence_primary_means,
        "pooled_frame_summaries": pooled,
        "secondary_a3_minus_a1_description": _descriptive_arm_comparison(
            macro["unconditional_gaussian"], macro["time_shuffled_ar"]
        ),
        "a3_differs_from_a2_in_marginals_cross_station_covariance_and_temporal_structure": True,
        "a3_minus_a2_causal_temporal_effect_claimed": False,
        "causal_temporal_order_claim_remains_anchored_to_v016_a2_minus_a1": True,
        "both_model_fits_are_in_sample_all_clean_descriptive": True,
        "distributional_model_ranking_determines_planner_behavior_claimed": False,
        "planner_benefit_claimed": False,
        "comfort_claimed": False,
        "safety_claimed": False,
        "bmw_planner_behavior_claimed": False,
        "production_readiness_claimed": False,
        "physical_ground_truth_claimed": False,
        "global_replay_claimed": False,
        "final_model_selection_authorized": False,
        "journey_level_generalization_estimated": False,
        "frame_metrics_file": TRANSFER_FRAME_FILENAME,
        "frame_metrics_file_sha256": sha256_file(frame_path),
        "sequence_metrics_file": TRANSFER_SEQUENCE_FILENAME,
        "sequence_metrics_file_sha256": sha256_file(sequence_path),
    }
    write_strict_json(output_directory / TRANSFER_SUMMARY_FILENAME, summary)
    return summary, 0


__all__ = [
    "GAUSSIAN_SAMPLE_KEYS",
    "PRIMARY_DIRECTIONS",
    "PRIMARY_METRICS",
    "SEQUENCE_FIELDS",
    "TRANSFER_FRAME_KEYS",
    "V016_FRAME_KEYS",
    "run_gaussian_planner_transfer",
]
