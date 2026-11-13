"""Incremental temporal responses in the existing affine lateral simulator."""

from dataclasses import asdict
from functools import lru_cache

import numpy as np

from .cached_planner_scenarios import DT_S, prepare_scenario_rows
from .reference_planner import ReferencePlannerConfig, plan_reference_step
from .spatial_planner_response import STATIONS_M

REVISION = "v0.19.32-temporal-planner-pilot-a1"
CONFIG = ReferencePlannerConfig()
ARMS = ("nominal", "empirical", "conditional_gaussian", "stationary_ar",
        "stationary_ar_permuted", "one_state_ar", "one_state_ar_permuted")
PROTOCOL = {
    "pilot_selection": "lexicographically_first_original_development_outing",
    "prediction_dt_s": DT_S,
    "planner": asdict(CONFIG),
    "draws": 128,
    "prefix_draws": 64,
    "sampling_seed": 193201,
    "permutation_seed": 193202,
    "primary": "mean_normalized_command_sequence_energy_mps2",
    "primary_contrast": "one_state_ar_minus_one_state_ar_permuted",
    "secondary": ["peak_incremental_state_lateral_crps_m", "mean_command_marginal_crps_mps2"],
    "weighting": "equal_eligible_original_sequence_within_one_outing",
    "clock": "recorded_EDP_source_epoch_difference_integer_subtraction_before_seconds",
    "eligibility": "whole_original_sequence_length_at_least_two_all_frames_supported_all_intervals_valid",
    "terminal": "last_recorded_command_without_unobserved_terminal_propagation",
    "reset": "zero_incremental_lateral_heading_and_previous_command_at_every_original_reset",
    "ablation": "independent_draw_permutation_at_each_noninitial_frame_whole_profile_preserved",
    "prefix": "first_64_native_draws_permuted_again_within_the_prefix",
    "claim": "short_recorded_support_in_exogenous_affine_incremental_simulator",
}


def prepare(block, fold: dict) -> tuple[list[dict], dict, list[dict], dict]:
    """Preserve all original model rows and classify entire temporal sequences."""
    rows, arrays, _ = prepare_scenario_rows(block, fold)
    records = []
    for index, (lo, hi) in enumerate(zip(block.offsets[:-1], block.offsets[1:])):
        times = [int(row["estimate_source_time_ns_decimal"]) for row in rows[lo:hi]]
        intervals = [b - a for a, b in zip(times[:-1], times[1:])]
        if hi - lo < 2:
            status = "singleton"
        elif not np.all(arrays["eligible"][lo:hi]):
            status = "unsupported_spatial_lookahead_or_speed"
        elif any(not CONFIG.minimum_dt_s * 1e9 <= dt <= CONFIG.maximum_dt_s * 1e9 for dt in intervals):
            status = "source_interval_outside_planner_range"
        else:
            status = "eligible"
        records.append(dict(sequence_index=index, start_row=int(lo), stop_row=int(hi),
                            frame_count=int(hi-lo), source_start_ns_decimal=str(times[0]),
                            interval_ns=intervals, status=status))
    counts = {status: sum(r["status"] == status for r in records) for status in
              ("eligible", "singleton", "unsupported_spatial_lookahead_or_speed",
               "source_interval_outside_planner_range")}
    eligible = [r for r in records if r["status"] == "eligible"]
    intervals = [dt for r in eligible for dt in r["interval_ns"]]
    summary = dict(
        original_rows=len(rows), original_sequences=len(records), sequence_status_counts=counts,
        eligible_sequences=len(eligible), eligible_rows=sum(r["frame_count"] for r in eligible),
        eligible_transitions=len(intervals),
        eligible_sequences_by_frame_count={str(n): sum(r["frame_count"] == n for r in eligible)
                                           for n in sorted({r["frame_count"] for r in eligible})},
        lateral_state_assessed_sequences=sum(r["frame_count"] >= 3 for r in eligible),
        maximum_eligible_duration_s=max((sum(r["interval_ns"]) / 1e9 for r in eligible), default=None),
        interval_s_minimum=min(intervals) / 1e9 if intervals else None,
        interval_s_maximum=max(intervals) / 1e9 if intervals else None,
    )
    return rows, arrays, records, summary


def permute_draws(profiles: np.ndarray, offsets: np.ndarray, seed: int) -> np.ndarray:
    """Permute whole profiles across draws while keeping framewise empirical laws."""
    result = profiles.copy()
    rng = np.random.default_rng(seed)
    for lo, hi in zip(offsets[:-1], offsets[1:]):
        for row in range(lo + 1, hi):
            result[:, row] = profiles[rng.permutation(len(profiles)), row]
    return result


@lru_cache(maxsize=128)
def control_map(speed_mps: float) -> tuple[np.ndarray, np.ndarray]:
    """Obtain the native first control's linear state and profile coefficients."""
    if not np.isfinite(speed_mps) or speed_mps < CONFIG.minimum_speed_mps or speed_mps * DT_S * CONFIG.horizon_steps > 100:
        raise ValueError("temporal_planner_unsupported_speed")
    def control(state: np.ndarray, profile: np.ndarray) -> float:
        return plan_reference_step(
            lateral_error_m=float(state[0]), heading_error_rad=float(state[1]),
            previous_curvature_correction_per_m=float(state[2]),
            residual_profile_m=profile, stations_m=np.asarray(STATIONS_M),
            speed_mps=speed_mps, dt_s=DT_S, config=CONFIG,
        ).curvature_correction_per_m
    state_map = np.array([control(s, np.zeros(21)) for s in np.eye(3)])
    profile_map = np.array([control(np.zeros(3), p) for p in np.eye(21)])
    state_map.setflags(write=False)
    profile_map.setflags(write=False)
    return state_map, profile_map


def propagate(state: np.ndarray, command: np.ndarray, speed: float, dt: float) -> np.ndarray:
    """Apply the native Euler error dynamics over the next observed interval."""
    distance = speed * dt
    return np.stack((state[..., 0] + distance * state[..., 1],
                     state[..., 1] + distance * command, command), axis=-1)


def rollout(profiles: np.ndarray, speeds: np.ndarray, intervals_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return commanded acceleration increments and states at recorded frame times."""
    profiles = np.asarray(profiles, dtype=float)
    speeds, intervals_s = np.asarray(speeds, dtype=float), np.asarray(intervals_s, dtype=float)
    if profiles.ndim != 3 or not len(profiles) or profiles.shape[1:] != (len(speeds), 21) or len(speeds) < 2:
        raise ValueError("temporal_planner_sequence_shape")
    if intervals_s.shape != (len(speeds)-1,) or not np.isfinite(profiles).all() or not np.isfinite(intervals_s).all():
        raise ValueError("temporal_planner_sequence_values")
    if np.any(intervals_s < CONFIG.minimum_dt_s) or np.any(intervals_s > CONFIG.maximum_dt_s):
        raise ValueError("temporal_planner_sequence_intervals")
    state = np.zeros((len(profiles), 3))
    lateral, acceleration = np.empty(profiles.shape[:2]), np.empty(profiles.shape[:2])
    for row, speed in enumerate(speeds):
        state_map, profile_map = control_map(float(speed))
        command = state @ state_map + profiles[:, row] @ profile_map
        lateral[:, row] = state[:, 0]
        acceleration[:, row] = command * speed**2
        if row < len(intervals_s):
            state = propagate(state, command, speed, float(intervals_s[row]))
    if not np.isfinite(lateral).all() or not np.isfinite(acceleration).all():
        raise ValueError("temporal_planner_nonfinite_response")
    return acceleration, lateral


def _energy(draws: np.ndarray, observed: np.ndarray) -> float:
    first = np.linalg.norm(draws - observed, axis=1).mean()
    pairs = np.linalg.norm(draws[:, None] - draws[None, :], axis=2).mean()
    return float((first - 0.5 * pairs) / np.sqrt(len(observed)))


def score(arrays: dict, records: list[dict], arms: dict[str, np.ndarray]) -> dict:
    """Score identical retained sequences with one vector of commands per draw."""
    if tuple(arms) != ARMS or any(
        profiles.ndim != 3 or profiles.shape[1:] != arrays["residuals_m"].shape
        or not np.isfinite(profiles).all() for profiles in arms.values()
    ):
        raise ValueError("temporal_planner_fixed_arms_and_shapes")
    sizes = {len(v) for k, v in arms.items() if k != "nominal"}
    if len(sizes) != 1 or next(iter(sizes)) not in (PROTOCOL["draws"], PROTOCOL["prefix_draws"]) or len(arms["nominal"]) != 1:
        raise ValueError("temporal_planner_fixed_draw_counts")
    counts = [len(v) for v in arms.values()]
    stops = np.cumsum([1, *counts])[:-1]
    sequence_scores = []
    for record in records:
        if record["status"] != "eligible":
            continue
        lo, hi = record["start_row"], record["stop_row"]
        joined = np.concatenate((arrays["residuals_m"][None, lo:hi], *[v[:, lo:hi] for v in arms.values()]))
        acceleration, lateral = rollout(joined, arrays["speed_mps"][lo:hi], np.array(record["interval_ns"]) / 1e9)
        observed, *draws = np.split(acceleration, stops)
        observed_lateral, *lateral_draws = np.split(lateral, stops)
        results = {}
        for name, values, states in zip(ARMS, draws, lateral_draws):
            results[name] = {
                "normalized_command_sequence_energy_mps2": _energy(values, observed[0]),
                "peak_incremental_state_lateral_crps_m": _energy(
                    np.max(np.abs(states), axis=1)[:, None], np.array([np.max(np.abs(observed_lateral))])) if hi-lo >= 3 else None,
                "mean_command_marginal_crps_mps2": float(np.abs(values - observed[0]).mean()
                    - 0.5 * np.abs(values[:, None] - values[None, :]).mean()),
            }
        sequence_scores.append(dict(sequence_index=record["sequence_index"], frame_count=hi-lo, arms=results))
    if not sequence_scores:
        raise ValueError("temporal_planner_no_eligible_sequences")
    means = {}
    for arm in ARMS:
        means[arm] = {}
        for metric in sequence_scores[0]["arms"][arm]:
            values = [row["arms"][arm][metric] for row in sequence_scores if row["arms"][arm][metric] is not None]
            means[arm][metric] = float(np.mean(values)) if values else None
    key = "normalized_command_sequence_energy_mps2"
    contrasts = {
        name: float(np.mean([row["arms"][name][key] - row["arms"][name + "_permuted"][key]
                            for row in sequence_scores]))
        for name in ("stationary_ar", "one_state_ar")
    }
    return dict(eligible_sequences=len(sequence_scores), arms=means,
                temporal_minus_permuted_energy_mps2=contrasts, sequence_scores=sequence_scores)
