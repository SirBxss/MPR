"""Prospectively fixed comparisons for the recorded spatial engineering pilot."""

from functools import lru_cache

import numpy as np

from .cached_planner_scenarios import DT_S
from .reference_planner import ReferencePlannerConfig
from .spatial_planner_response import SpatialPlannerScenario, build_spatial_response

REVISION = "v0.19.30-recorded-spatial-pilot-2026-11-09-a1"
FULL = "full_gaussian"
PEAK = "peak_planned_lateral_change_m"
FIRST = "first_curvature_change_per_m"
ARMS = ("nominal", "empirical", "diagonal_gaussian", FULL, "unconditional_flow_reset")
PROTOCOL = {
    "draws": 512,
    "draw_sensitivity_prefix": 128,
    "sampling_seed": 193001,
    "speed_offsets_mps": [-4.0, 0.0, 4.0],
    "increment_threshold_m": 0.3,
    "block_duration_s": 30,
    "bootstrap_replicates": 1000,
    "bootstrap_seed": 193002,
    "primary": {"metric": PEAK, "score": "crps", "comparator": FULL},
    "flow_context": "unconditional_single_profile_with_reset",
    "weighting": "equal_rows_within_one_held_out_outing",
    "sensitivity_support": "rows_admissible_at_all_three_speed_offsets",
    "scope": "unconstrained_affine_snapshot_increment_one_recording",
}


def _row_statistics(draws: np.ndarray, observed: float) -> dict[str, float]:
    ordered = np.sort(draws)
    count = len(ordered)
    weights = 2 * np.arange(count) + 1 - count
    half_pair_distance = (ordered @ weights) / count**2
    lower, upper = np.quantile(ordered, [0.05, 0.95])
    return {
        "crps": float(np.abs(ordered - observed).mean() - half_pair_distance),
        "draw_mean": float(ordered.mean()),
        "draw_p95_absolute": float(np.quantile(np.abs(ordered), 0.95)),
        "central_90_coverage": float(lower <= observed <= upper),
        "central_90_width": float(upper - lower),
    }


def _mean_fields(rows: list[dict[str, float]]) -> dict[str, float]:
    return {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}


def _bootstrap(contrasts: np.ndarray, block_ids: np.ndarray) -> dict:
    """Conditional block sensitivity for one recording, with row weighting."""
    _, inverse = np.unique(block_ids, return_inverse=True)
    counts = np.bincount(inverse)
    result = {"mean_crps_difference_vs_full": float(contrasts.mean()), "blocks": len(counts)}
    if len(counts) < 5:
        return {**result, "central_95_block_bootstrap_interval": None}
    totals = np.bincount(inverse, weights=contrasts)
    rng = np.random.default_rng(PROTOCOL["bootstrap_seed"])
    draws = rng.integers(len(counts), size=(PROTOCOL["bootstrap_replicates"], len(counts)))
    means = totals[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {**result, "central_95_block_bootstrap_interval": np.quantile(means, [0.025, 0.975]).tolist()}


def spatial_speed_support(arrays: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return the frozen speed grid and the mask eligible at every offset."""
    config = ReferencePlannerConfig()
    speeds = arrays["speed_mps"]
    eligible = arrays["eligible"]
    shifted = speeds[:, None] + PROTOCOL["speed_offsets_mps"]
    in_support = (shifted >= config.minimum_speed_mps) & (
        shifted * DT_S * config.horizon_steps <= arrays["stations_m"][-1]
    )
    if not np.array_equal(in_support[:, 1], eligible) or not eligible.any():
        raise ValueError("pilot original eligibility differs or is empty")
    common = eligible & np.all(in_support, axis=1)
    return shifted, common


def score_spatial_pilot(arrays: dict, rows: list[dict], arms: dict[str, np.ndarray]) -> dict:
    """Compare recorded and simulated changes at exact per-row cached speed."""
    if tuple(arms) != ARMS or any(
        len(draws) != (1 if name == "nominal" else PROTOCOL["draws"])
        for name, draws in arms.items()
    ):
        raise ValueError("pilot requires the fixed arms and draw counts")
    shifted, common = spatial_speed_support(arrays)
    eligible = arrays["eligible"]
    config = ReferencePlannerConfig()
    offsets = arrays["conditioned_sequence_offsets"]
    epochs = [int(rows[i]["estimate_source_time_ns_decimal"]) for i in offsets[:-1]]
    first_epoch = min(epochs)
    duration_ns = PROTOCOL["block_duration_s"] * 10**9
    blocks = np.repeat([(epoch - first_epoch) // duration_ns for epoch in epochs], np.diff(offsets))
    threshold = PROTOCOL["increment_threshold_m"]
    prefix = PROTOCOL["draw_sensitivity_prefix"]
    arm_profiles = np.concatenate(list(arms.values()))
    stops = np.cumsum([len(draws) for draws in arms.values()])[:-1]

    @lru_cache(maxsize=128)
    def response(speed: float):
        return build_spatial_response(SpatialPlannerScenario(speed, DT_S), config)

    def score(mask: np.ndarray, speed_index: int, include_prefix: bool = False) -> dict:
        indices = np.flatnonzero(mask)
        if not len(indices):
            return {"rows": 0}
        metrics = (PEAK, FIRST)
        samples = {name: {metric: [] for metric in metrics} for name in ARMS}
        replay = {metric: [] for metric in metrics}
        prefixes = {name: [] for name in ARMS}
        for i in indices:
            mapping = response(float(shifted[i, speed_index]))
            outcomes = mapping.evaluate(np.vstack((arrays["residuals_m"][i], arm_profiles)))
            for metric, values in outcomes.items():
                observed = float(values[0])
                replay[metric].append(observed)
                for name, draws in zip(ARMS, np.split(values[1:], stops)):
                    stats = _row_statistics(draws, observed)
                    if metric == PEAK:
                        probability = float(np.mean(draws > threshold))
                        stats.update(exceedance_probability=probability,
                                     brier=(probability - (observed > threshold))**2)
                        if include_prefix:
                            prefixes[name].append(_row_statistics(draws[:prefix], observed)["crps"])
                    samples[name][metric].append(stats)
        results = {name: {metric: _mean_fields(values) for metric, values in scores.items()}
                   for name, scores in samples.items()}
        observed = {metric: {"mean": float(np.mean(values)),
                             "p95_absolute": float(np.quantile(np.abs(values), 0.95))}
                    for metric, values in replay.items()}
        observed[PEAK]["exceedance_fraction"] = float(np.mean(np.asarray(replay[PEAK]) > threshold))
        result = {"rows": len(indices), "replay": observed, "arms": results}
        if include_prefix:
            full = np.asarray([row["crps"] for row in samples[FULL][PEAK]])
            result["primary_crps_contrasts"] = {
                name: _bootstrap(np.asarray([row["crps"] for row in samples[name][PEAK]]) - full,
                                 blocks[indices])
                for name in ARMS if name != FULL
            }
            result["prefix_primary_crps"] = {name: float(np.mean(v)) for name, v in prefixes.items()}
        return result

    primary = score(eligible, 1, include_prefix=True)
    # Reuse the primary score when the sensitivity arms have identical support.
    center = primary if np.array_equal(eligible, common) else score(common, 1)
    return {
        "primary": primary,
        "speed_sensitivity": {"minus_4_mps": score(common, 0), "original": center,
                              "plus_4_mps": score(common, 2)},
        "excluded_from_speed_sensitivity": int(np.count_nonzero(eligible & ~common)),
    }
