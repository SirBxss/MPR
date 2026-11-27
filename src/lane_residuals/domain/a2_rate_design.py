"""Nominal feasibility and synthetic loss sensitivity on the accepted a2 task."""

from dataclasses import replace
from itertools import combinations

import numpy as np

from . import a2_budget_pilot as budget, planner_parameter_design as moments, planner_parameter_selection as a2
from .artifact_registry import require
from .reference_planner import ReferencePlannerConfig

REVISION = "a2-steering-rate-design-v1"
RATE_SCALES = (.25, .5, 1., 2., 4.)
CONFIGS = tuple(replace(a2.BASE, weight_curvature_rate=a2.BASE.weight_curvature_rate * scale)
                for scale in RATE_SCALES)
DEFAULT = RATE_SCALES.index(1.)
UPPER_CONFIGS = tuple(replace(CONFIGS[-1], weight_curvature_rate=CONFIGS[-1].weight_curvature_rate * 2 ** step)
                      for step in range(1, 7))
PROTOCOL = {
    "a2_revision": a2.REVISION,
    "context_panel": budget.REVISION,
    "curvature_weight": a2.BASE.weight_curvature,
    "curvature_rate_weights": [cfg.weight_curvature_rate for cfg in CONFIGS],
    "reference_index": DEFAULT,
    "tracking_reference": "original_nine_curvature_grid_best_per_calibration_outing",
    "tracking_allowance": a2.PROTOCOL["nominal_gate"],
    "passive_probe_tracking_fraction": a2.PROTOCOL["probe_passive_tracking_fraction"],
    "nominal_peak_limits": list(budget.NOMINAL_PEAK_LIMIT),
    "nominal_peak_scope": "each_context_and_passive_comparison_probe",
    "relative_margin": budget.PROTOCOL["descriptive_margin"],
    "synthetic_sigmas_m": a2.PROTOCOL["design_diagnostic"]["synthetic_sigmas_m"],
    "synthetic_rhos": a2.PROTOCOL["design_diagnostic"]["synthetic_rhos"],
    "spatial_length_m": a2.PROTOCOL["design_diagnostic"]["spatial_length_m"],
    "maximum_frames": a2.PROTOCOL["design_diagnostic"]["maximum_frames"],
    "weighting": "equal_tasks_and_sequences_within_each_outing_then_equal_outings",
}
EXTENSION_PROTOCOL = {
    **PROTOCOL,
    "curvature_rate_weights": [cfg.weight_curvature_rate for cfg in CONFIGS + UPPER_CONFIGS],
    "upper_search_stop": "first_new_nominal_gate_failure_or_last_declared_weight",
    "synthetic_scoring": "after_nominal_search_on_tested_feasible_candidates",
}


def nominal_summary(speeds: np.ndarray, intervals: np.ndarray,
                    config: ReferencePlannerConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    costs = a2.rollout_costs_for_config(np.zeros((1, len(speeds), 21)), speeds, intervals, config, a2.TASKS)
    return (np.array([costs[metric].mean() for metric in a2.COMPONENTS]),
            costs["tracking"][0],
            np.array([costs["peak_acceleration"].max(), costs["peak_jerk"].max()]))


def _candidate_reasons(tracking: np.ndarray, tracking_limit: np.ndarray, probe_ratio: np.ndarray,
                       peaks: np.ndarray) -> list[str]:
    reasons = []
    if np.any(tracking > tracking_limit + 1e-12):
        reasons.append("outing_tracking_over_original_grid_allowance")
    if np.any(probe_ratio > PROTOCOL["passive_probe_tracking_fraction"] + 1e-12):
        reasons.append("passive_probe_recovery_failed")
    if np.any(peaks > budget.NOMINAL_PEAK_LIMIT):
        reasons.append("nominal_peak_envelope_failed")
    return reasons


def describe_tradeoffs(feasible: list[int], macro: np.ndarray) -> list[dict]:
    """Find opposed tracking and jerk improvements of at least the declared margin."""
    rows = []
    for first, second in combinations(feasible, 2):
        tracking, jerk = macro[[first, second]][:, [0, 2]].T
        if tracking[0] > tracking[1]:
            first, second = second, first
            tracking, jerk = tracking[::-1], jerk[::-1]
        tracking_reduction = float(1 - tracking[0] / tracking[1]) if tracking[1] else 0.
        jerk_reduction = float(1 - jerk[1] / jerk[0]) if jerk[0] else 0.
        if min(tracking_reduction, jerk_reduction) >= PROTOCOL["relative_margin"]:
            rows.append({"better_tracking": first, "lower_jerk": second,
                         "tracking_relative_reduction": tracking_reduction,
                         "jerk_relative_reduction": jerk_reduction})
    return rows


def _loss_summary(losses: np.ndarray, feasible: list[int]) -> dict:
    minimum = min(float(losses[i]) for i in feasible)
    tolerance = a2.PROTOCOL["numerical_tie_tolerance"]
    priority = [DEFAULT, *[i for i in feasible if i != DEFAULT]]
    best = next(i for i in priority if i in feasible and losses[i] <= minimum + tolerance)
    band = minimum * (1 + PROTOCOL["relative_margin"]) + tolerance
    gaps = sorted(float(losses[i]) - minimum for i in feasible)
    return {"choice": best, "near_optimal_candidates": [i for i in feasible if losses[i] <= band],
            "runner_up_gap": gaps[1] if len(gaps) > 1 else None,
            "losses_by_candidate": {str(i): float(losses[i]) for i in feasible}}


def _synthetic_losses(contexts: list[tuple], weights: np.ndarray, feasible: list[int], macro: np.ndarray,
                      configs: tuple[ReferencePlannerConfig, ...]) -> list[dict]:
    results = []
    for rho in PROTOCOL["synthetic_rhos"]:
        slopes = np.zeros(len(macro))
        for weight, (speeds, intervals) in zip(weights, contexts):
            covariance = moments.unit_covariance(len(speeds), rho)
            for i in feasible:
                matrix = moments.quadratic_map_for_config(speeds, intervals, configs[i])
                slopes[i] += weight * float(np.sum(matrix * covariance))
        for sigma in PROTOCOL["synthetic_sigmas_m"]:
            losses = macro[:, -1] + sigma ** 2 * slopes
            results.append({"rho": rho, "sigma_m": sigma, **_loss_summary(losses, feasible)})
    return results


def diagnose(panel: budget.Panel, covariates: dict[str, np.ndarray], original_nominal: dict, *,
             extend_upper: bool = False) -> dict:
    """Compare rate settings with zero disturbances first, then fixed covariance probes."""
    groups = original_nominal["training_outing_ids"]
    group_index = np.array([groups.index(sequence.outing) for sequence in panel.contexts])
    require(len(groups) == budget.BUDGETS[-1] and set(group_index) == set(range(len(groups))),
            "rate_design_context_groups")
    contexts = [(tuple(covariates[s.outing][s.start:s.stop, 0]), tuple(s.intervals())) for s in panel.contexts]
    require(all(3 <= len(speeds) <= PROTOCOL["maximum_frames"] for speeds, _ in contexts),
            "rate_design_context_frame_bound")

    original_best = np.asarray(original_nominal["grid_best_tracking_by_outing"])
    tracking_limit = (1 + PROTOCOL["tracking_allowance"]) * original_best
    probes = a2.PROTOCOL["nominal_probes"]
    passive = a2.passive_probes()
    require(np.all(passive > 0), "rate_design_passive_tracking_scale")
    reports, feasible = [], []
    configs = CONFIGS + UPPER_CONFIGS if extend_upper else CONFIGS
    for i, config in enumerate(configs):
        summaries = [nominal_summary(np.asarray(v), np.asarray(dt), config) for v, dt in contexts]
        by_context, _, context_peaks = map(np.array, zip(*summaries))
        by_outing = np.stack([by_context[group_index == j].mean(axis=0) for j in range(len(groups))])
        probe_summaries = [
            nominal_summary(np.full(probes["frames"], speed), np.full(probes["frames"] - 1, probes["dt_s"]), config)
            for speed in probes["speeds_mps"]
        ]
        probe_ratio = np.array([summary[1] for summary in probe_summaries]) / passive
        probe_peaks = np.array([summary[2] for summary in probe_summaries])
        reasons = _candidate_reasons(by_outing[:, 0], tracking_limit, probe_ratio,
                                     np.concatenate((context_peaks, probe_peaks)))
        if not reasons:
            feasible.append(i)
        reports.append({
            "candidate": i, "curvature_rate_weight": config.weight_curvature_rate, "nominal_gate_failures": reasons,
            "macro_components": by_outing.mean(axis=0).tolist(),
            "components_by_outing": by_outing.tolist(),
            "over_allowance_outings": [oid for oid, value, limit in zip(groups, by_outing[:, 0], tracking_limit)
                                       if value > limit + 1e-12],
            "probe_tracking_fraction_of_passive": probe_ratio.tolist(),
            "worst_context_peaks": context_peaks.max(axis=0).tolist(),
            "probe_peaks": probe_peaks.tolist(),
        })
        if i >= len(CONFIGS) and reasons:
            break
    macro = np.asarray([report["macro_components"] for report in reports])
    weights = np.array([1 / (len(groups) * np.count_nonzero(group_index == j)) for j in group_index])
    tradeoffs = describe_tradeoffs(feasible, macro)
    synthetic = _synthetic_losses(contexts, weights, feasible, macro, configs) if len(feasible) >= 2 else []
    nominal = _loss_summary(macro[:, -1], feasible) if feasible else None
    if len(feasible) < 2:
        finding = "fewer_than_two_nominally_feasible_rates"
    elif not tradeoffs:
        finding = "no_material_nominal_tracking_jerk_tradeoff"
    else:
        finding = "material_nominal_tracking_jerk_tradeoff"
    design = {
        "finding": finding, "context_count": len(contexts), "outings": groups,
        "original_grid_best_tracking": original_best.tolist(), "tracking_limit": tracking_limit.tolist(),
        "component_order": list(a2.COMPONENTS), "candidates": reports, "feasible_candidates": feasible,
        "nominal_choice_diagnostic": nominal, "nominal_tradeoffs": tradeoffs, "synthetic_covariance_probes": synthetic,
    }
    if extend_upper:
        describe_upper_stop(design)
    return design


def describe_upper_stop(design: dict) -> None:
    """Record the observed boundary on each side of a reported choice."""
    tested = design["candidates"]
    design["upper_stop"] = ("first_upper_nominal_gate_failure" if tested[-1]["nominal_gate_failures"]
                            else "feasible_upper_cap")
    choices = [design["nominal_choice_diagnostic"], *design["synthetic_covariance_probes"]]
    for summary in choices:
        if summary is None:
            continue
        for side, index in (("lower", summary["choice"] - 1), ("upper", summary["choice"] + 1)):
            if not 0 <= index < len(tested):
                status = "tested_range_edge"
            elif tested[index]["nominal_gate_failures"]:
                status = "adjacent_weight_failed_nominal_gate"
            else:
                status = "adjacent_weight_feasible"
            summary[side + "_boundary"] = status
