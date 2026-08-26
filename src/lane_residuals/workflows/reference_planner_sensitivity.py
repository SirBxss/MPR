"""Paired v0.16 temporal-order reference-planner sensitivity workflow."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.reference_planner import (
    ReferencePlannerConfig,
    perturb_path_left_normal,
    plan_reference_step,
    signed_curvature_at_origin,
)
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.reports import write_strict_json
from .development_residual_sampling import SAMPLES_FILENAME, SUMMARY_FILENAME
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.16.0"
ARM_NAMES = ("zero", "time_shuffled_ar", "frozen_ar")
SCENARIO_KEYS = frozenset(
    {
        "conditions",
        "feature_names",
        "lengths",
        "nominal_paths_xy_m",
        "sequence_ids",
        "stations_m",
        "timestamps_ns",
    }
)
SAMPLE_KEYS = frozenset(
    {"feature_names", "lengths", "residual_samples_m", "sequence_ids", "stations_m"}
)
FRAME_FILENAME = "reference_planner_frame_metrics.npz"
SEQUENCE_FILENAME = "reference_planner_sequence_metrics.csv"
SUMMARY_OUTPUT_FILENAME = "reference_planner_sensitivity_summary.json"
METRIC_NAMES = (
    "lateral_error_m",
    "heading_error_rad",
    "curvature_per_m",
    "curvature_rate_per_m_s",
    "lateral_acceleration_mps2",
    "lateral_jerk_mps3",
    "objective",
    "constraint_violation",
)


def _string_array(value: NDArray[Any], label: str) -> NDArray[np.str_]:
    raw = np.asarray(value)
    if raw.dtype.kind not in {"U", "S"}:
        raise TypeError(f"{label} must use a string dtype")
    return np.asarray(raw, dtype=np.str_)


def _integer_array(value: NDArray[Any], label: str) -> NDArray[np.int64]:
    raw = np.asarray(value)
    if raw.dtype == np.bool_ or not np.issubdtype(raw.dtype, np.integer):
        raise TypeError(f"{label} must use an integer dtype")
    return np.asarray(raw, dtype=np.int64)


def _load_npz(path: Path, expected_keys: frozenset[str]) -> dict[str, NDArray[Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != expected_keys:
                raise ValueError(
                    f"{path.name} keys must be exactly {sorted(expected_keys)}"
                )
            return {key: np.asarray(archive[key]) for key in archive.files}
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"invalid NPZ archive {path}: {error}") from error


def _validate_source_summary(directory: Path, sample_path: Path) -> dict[str, Any]:
    summary_path = directory / SUMMARY_FILENAME
    if not summary_path.is_file():
        raise FileNotFoundError(summary_path)
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid residual sampling summary: {error}") from error
    if summary.get("version") != "0.15.4" or summary.get("status") != "complete":
        raise ValueError("residual sampling summary is not a complete v0.15.4 result")
    if summary.get("sample_file") != SAMPLES_FILENAME:
        raise ValueError("residual sampling summary names an unexpected sample file")
    if summary.get("sample_file_sha256") != sha256_file(sample_path):
        raise ValueError("residual sample hash differs from its v0.15.4 summary")
    if summary.get("sampling_is_free_running") is not True:
        raise ValueError("v0.16 requires free-running residual samples")
    return summary


def _validate_inputs(
    scenario: dict[str, NDArray[Any]], samples: dict[str, NDArray[Any]]
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
    NDArray[np.str_],
    NDArray[np.float64],
    NDArray[np.int64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    conditions = np.asarray(scenario["conditions"], dtype=np.float64)
    lengths = _integer_array(scenario["lengths"], "scenario lengths")
    sequence_ids = _string_array(scenario["sequence_ids"], "scenario sequence IDs")
    paths = np.asarray(scenario["nominal_paths_xy_m"], dtype=np.float64)
    timestamps = _integer_array(scenario["timestamps_ns"], "scenario timestamps")
    stations = np.asarray(scenario["stations_m"], dtype=np.float64)
    feature_names = tuple(
        _string_array(scenario["feature_names"], "scenario feature names").tolist()
    )
    residuals = np.asarray(samples["residual_samples_m"], dtype=np.float64)
    sample_lengths = _integer_array(samples["lengths"], "sample lengths")
    sample_ids = _string_array(samples["sequence_ids"], "sample sequence IDs")
    sample_stations = np.asarray(samples["stations_m"], dtype=np.float64)
    sample_features = tuple(
        _string_array(samples["feature_names"], "sample feature names").tolist()
    )
    if feature_names != BMW_CONDITION_FEATURE_NAMES or sample_features != feature_names:
        raise ValueError("feature order differs from BMW condition schema v1")
    if conditions.ndim != 3 or conditions.shape[2] != 6:
        raise ValueError("conditions must have shape [B,T,6]")
    batch, maximum_time, _ = conditions.shape
    if paths.shape != (batch, maximum_time, 21, 2):
        raise ValueError("nominal_paths_xy_m must have shape [B,T,21,2]")
    if timestamps.shape != (batch, maximum_time):
        raise ValueError("timestamps_ns must have shape [B,T]")
    if lengths.shape != (batch,) or sequence_ids.shape != (batch,):
        raise ValueError("scenario lengths and sequence_ids must have shape [B]")
    if residuals.ndim != 4 or residuals.shape[1:] != (batch, maximum_time, 21):
        raise ValueError("residual_samples_m must have shape [S,B,T,21]")
    if residuals.shape[0] < 20:
        raise ValueError("predeclared evaluation requires at least 20 residual draws")
    if not np.array_equal(sample_lengths, lengths) or not np.array_equal(
        sample_ids, sequence_ids
    ):
        raise ValueError("scenario and residual sequence identity differs")
    if stations.shape != (21,) or not np.array_equal(stations, sample_stations):
        raise ValueError("scenario and residual H100 stations differ")
    if not np.array_equal(stations, np.arange(0.0, 101.0, 5.0)):
        raise ValueError("v0.16 requires the exact 0:5:100 m station grid")
    if any(not value for value in sequence_ids.tolist()) or len(set(sequence_ids)) != batch:
        raise ValueError("sequence IDs must be nonempty and unique")
    if np.any(lengths < 2) or np.any(lengths > maximum_time):
        raise ValueError("every planning sequence must contain 2..T active frames")
    if not np.all(np.isfinite(conditions)) or not np.all(np.isfinite(paths)):
        raise ValueError("scenario arrays must be finite")
    if not np.all(np.isfinite(residuals)):
        raise ValueError("residual samples must be finite")
    for sequence_index, length in enumerate(lengths):
        active = int(length)
        if np.any(np.diff(timestamps[sequence_index, :active]) <= 0):
            raise ValueError("active timestamps must strictly increase per sequence")
        if np.any(timestamps[sequence_index, active:] != 0):
            raise ValueError("padded timestamps must be zero")
        if np.any(conditions[sequence_index, active:] != 0.0):
            raise ValueError("padded conditions must be zero")
        if np.any(paths[sequence_index, active:] != 0.0):
            raise ValueError("padded paths must be zero")
        if np.any(residuals[:, sequence_index, active:] != 0.0):
            raise ValueError("padded residuals must be zero")
    return conditions, lengths, sequence_ids, paths, timestamps, stations, residuals


def _time_shuffle(
    residuals: NDArray[np.float64], lengths: NDArray[np.int64], seed: int
) -> tuple[NDArray[np.float64], int]:
    shuffled = np.zeros_like(residuals)
    changed = 0
    generator = np.random.default_rng(seed)
    for sample_index in range(residuals.shape[0]):
        for sequence_index, length in enumerate(lengths):
            active = int(length)
            permutation = generator.permutation(active)
            changed += int(np.count_nonzero(permutation != np.arange(active)))
            shuffled[sample_index, sequence_index, :active] = residuals[
                sample_index, sequence_index, permutation
            ]
    return shuffled, changed


def _frame_intervals_s(timestamps: NDArray[np.int64]) -> NDArray[np.float64]:
    differences = np.diff(timestamps).astype(np.float64) / 1e9
    return np.concatenate(([differences[0]], differences))


def _run_arm_sequence(
    *,
    residuals: NDArray[np.float64],
    paths: NDArray[np.float64],
    timestamps: NDArray[np.int64],
    speeds: NDArray[np.float64],
    stations: NDArray[np.float64],
    config: ReferencePlannerConfig,
) -> tuple[NDArray[np.float64], dict[str, float]]:
    length = residuals.shape[0]
    metrics = np.zeros((length, len(METRIC_NAMES)), dtype=np.float64)
    intervals = _frame_intervals_s(timestamps)
    lateral = heading = previous_correction = 0.0
    previous_total_curvature = previous_acceleration = 0.0
    for frame in range(length):
        dt_s = float(intervals[frame])
        speed = float(speeds[frame])
        nominal_curvature = signed_curvature_at_origin(paths[frame])
        perturb_path_left_normal(paths[frame], residuals[frame])
        step = plan_reference_step(
            lateral_error_m=lateral,
            heading_error_rad=heading,
            previous_curvature_correction_per_m=previous_correction,
            residual_profile_m=residuals[frame],
            stations_m=stations,
            speed_mps=speed,
            dt_s=dt_s,
            config=config,
        )
        lateral = step.lateral_error_m
        heading = step.heading_error_rad
        correction = step.curvature_correction_per_m
        total_curvature = nominal_curvature + correction
        curvature_rate = (
            0.0 if frame == 0 else (total_curvature - previous_total_curvature) / dt_s
        )
        acceleration = speed**2 * total_curvature
        jerk = 0.0 if frame == 0 else (acceleration - previous_acceleration) / dt_s
        violation = any(
            (
                abs(total_curvature) > config.maximum_abs_curvature_per_m,
                abs(curvature_rate) > config.maximum_abs_curvature_rate_per_m_s,
                abs(acceleration) > config.maximum_abs_lateral_acceleration_mps2,
                abs(jerk) > config.maximum_abs_lateral_jerk_mps3,
                abs(lateral) > config.maximum_abs_lateral_deviation_m,
            )
        )
        metrics[frame] = (
            lateral,
            heading,
            total_curvature,
            curvature_rate,
            acceleration,
            jerk,
            step.objective,
            float(violation),
        )
        previous_correction = correction
        previous_total_curvature = total_curvature
        previous_acceleration = acceleration
    summary = {
        "integrated_abs_lateral_error_m_s": float(np.sum(np.abs(metrics[:, 0]) * intervals)),
        "maximum_abs_lateral_error_m": float(np.max(np.abs(metrics[:, 0]))),
        "fraction_beyond_lateral_threshold": float(
            np.mean(np.abs(metrics[:, 0]) > config.lateral_excursion_threshold_m)
        ),
        "constraint_violation_fraction": float(np.mean(metrics[:, 7])),
        "final_abs_lateral_error_m": float(abs(metrics[-1, 0])),
    }
    return metrics, summary


def run_reference_planner_sensitivity(
    *,
    residual_sample_directory: Path,
    scenario_archive: Path,
    output_directory: Path,
    shuffle_seed: int = 20260827,
    config: ReferencePlannerConfig | None = None,
) -> tuple[dict[str, Any], int]:
    """Run the predeclared A0/A1/A2 paired temporal-order experiment."""

    if isinstance(shuffle_seed, bool) or not isinstance(shuffle_seed, (int, np.integer)):
        raise TypeError("shuffle_seed must be an integer")
    if shuffle_seed < 0:
        raise ValueError("shuffle_seed must be nonnegative")
    planner_config = config or ReferencePlannerConfig()
    sample_path = residual_sample_directory / SAMPLES_FILENAME
    source_summary = _validate_source_summary(residual_sample_directory, sample_path)
    scenario = _load_npz(scenario_archive, SCENARIO_KEYS)
    samples = _load_npz(sample_path, SAMPLE_KEYS)
    conditions, lengths, sequence_ids, paths, timestamps, stations, frozen = (
        _validate_inputs(scenario, samples)
    )
    shuffled, changed_positions = _time_shuffle(frozen, lengths, shuffle_seed)
    zero = np.zeros_like(frozen)
    arm_residuals = (zero, shuffled, frozen)
    sample_count, batch, maximum_time, _ = frozen.shape
    frame_metrics = np.zeros(
        (len(ARM_NAMES), sample_count, batch, maximum_time, len(METRIC_NAMES)),
        dtype=np.float64,
    )
    sequence_rows: list[dict[str, Any]] = []
    for arm_index, arm_name in enumerate(ARM_NAMES):
        for sample_index in range(sample_count):
            for sequence_index, length in enumerate(lengths):
                active = int(length)
                metrics, summary = _run_arm_sequence(
                    residuals=arm_residuals[arm_index][sample_index, sequence_index, :active],
                    paths=paths[sequence_index, :active],
                    timestamps=timestamps[sequence_index, :active],
                    speeds=conditions[sequence_index, :active, 0],
                    stations=stations,
                    config=planner_config,
                )
                frame_metrics[arm_index, sample_index, sequence_index, :active] = metrics
                sequence_rows.append(
                    {
                        "arm": arm_name,
                        "sample_index": sample_index,
                        "sequence_id": str(sequence_ids[sequence_index]),
                        "active_frame_count": active,
                        **summary,
                    }
                )

    ensure_empty_output_directory(output_directory)
    frame_path = output_directory / FRAME_FILENAME
    np.savez_compressed(
        frame_path,
        frame_metrics=frame_metrics,
        metric_names=np.asarray(METRIC_NAMES, dtype=np.str_),
        arm_names=np.asarray(ARM_NAMES, dtype=np.str_),
        lengths=lengths,
        sequence_ids=sequence_ids,
    )
    sequence_path = output_directory / SEQUENCE_FILENAME
    fieldnames = list(sequence_rows[0])
    with sequence_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sequence_rows)

    headline_metrics = (
        "integrated_abs_lateral_error_m_s",
        "maximum_abs_lateral_error_m",
        "fraction_beyond_lateral_threshold",
        "constraint_violation_fraction",
        "final_abs_lateral_error_m",
    )
    seed_macro: dict[str, NDArray[np.float64]] = {
        name: np.zeros((len(ARM_NAMES), sample_count), dtype=np.float64)
        for name in headline_metrics
    }
    for arm_index, arm_name in enumerate(ARM_NAMES):
        for sample_index in range(sample_count):
            selected = [
                row
                for row in sequence_rows
                if row["arm"] == arm_name and row["sample_index"] == sample_index
            ]
            for metric in headline_metrics:
                seed_macro[metric][arm_index, sample_index] = np.mean(
                    [float(row[metric]) for row in selected]
                )
    paired_comparisons: dict[str, Any] = {}
    for comparison, left, right in (
        ("a2_frozen_ar_minus_a1_time_shuffled_ar", 2, 1),
        ("a2_frozen_ar_minus_a0_zero", 2, 0),
    ):
        effects: dict[str, Any] = {}
        for metric in headline_metrics:
            difference = seed_macro[metric][left] - seed_macro[metric][right]
            effects[metric] = {
                "mean_difference": float(np.mean(difference)),
                "paired_monte_carlo_draw_interval_2_5_97_5_percent": [
                    float(value) for value in np.quantile(difference, [0.025, 0.975])
                ],
                "individual_differences": [float(value) for value in difference],
            }
        paired_comparisons[comparison] = effects
    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "reference_planner_temporal_order_sensitivity",
        "arms_in_required_order": list(ARM_NAMES),
        "primary_comparison": "frozen_ar_minus_time_shuffled_ar",
        "sample_count": sample_count,
        "sequence_count": batch,
        "active_frame_count": int(np.sum(lengths)),
        "shuffle_seed": int(shuffle_seed),
        "shuffled_frame_positions_changed": changed_positions,
        "planner_config": asdict(planner_config),
        "scenario_archive_sha256": sha256_file(scenario_archive),
        "source_sample_file_sha256": sha256_file(sample_path),
        "source_sampling_random_seed": source_summary["random_seed"],
        "frame_metrics_file": FRAME_FILENAME,
        "frame_metrics_file_sha256": sha256_file(frame_path),
        "sequence_metrics_file": SEQUENCE_FILENAME,
        "sequence_metrics_file_sha256": sha256_file(sequence_path),
        "paired_comparisons": paired_comparisons,
        "temporal_propagation_used": True,
        "global_pose_replay_used": False,
        "simulation_interpretation": (
            "linearized lateral and heading error propagation around recorded motion"
        ),
        "time_shuffle_preserves_frame_profiles_exactly_within_sequence": True,
        "time_shuffle_crosses_sequence_boundaries": False,
        "interval_label": (
            "paired Monte Carlo-draw interval under one reproducibility seed; "
            "not a dataset confidence interval"
        ),
        "planner_benefit_claimed": False,
        "bmw_planner_behavior_claimed": False,
        "journey_level_generalization_estimated": False,
    }
    write_strict_json(output_directory / SUMMARY_OUTPUT_FILENAME, summary)
    return summary, 0


__all__ = [
    "ARM_NAMES",
    "FRAME_FILENAME",
    "METRIC_NAMES",
    "SCENARIO_KEYS",
    "SEQUENCE_FILENAME",
    "SUMMARY_OUTPUT_FILENAME",
    "VERSION",
    "run_reference_planner_sensitivity",
]
