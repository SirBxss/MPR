"""Training only paired solver screening and descriptive Monte Carlo checks."""
from __future__ import annotations

import numpy as np

from .matched_flow import MatchedFlow, sample_matched_flow

CALIBRATION = {"solver": "heun", "steps": [32, 64, 128], "sample_count": 32, "seed": 20261105,
               "maximum_sequences": 18, "paired_standardized_rmse_limit": .025,
               "paired_standardized_maximum_limit": .15,
               "maximum_standardized_mean_change_limit": .025,
               "maximum_standardized_sd_change_limit": .025,
               "maximum_standardized_quantile_change_limit": .05,
               "pointwise_tail_probability_change_threshold": .0625,
               "tail_probability_exceedance_fraction_limit": .02,
               "pooled_tail_probability_change_limit": .01}


def calibration_conditions(blocks: list) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Choose shortest, middle and longest sequence per training outing by length.

    Ties use original sequence index. Only conditions and reset indices are read;
    residual values and validation blocks cannot influence this selection.
    """
    chunks, offsets, identities = [], [0], []
    for b in blocks:
        lengths = np.diff(b.offsets)
        ordered = sorted(range(len(lengths)), key=lambda i: (int(lengths[i]), i))
        for i in sorted({ordered[0], ordered[len(ordered)//2], ordered[-1]}):
            lo, hi = b.offsets[i:i+2]
            chunks.append(b.x[lo:hi])
            offsets.append(offsets[-1]+int(hi-lo))
            identities.append({"outing_id": b.outing_id, "sequence_index": i, "length": int(hi-lo)})
    if not chunks or len(chunks) > CALIBRATION["maximum_sequences"]:
        raise ValueError("flow_calibration_subset_bound")
    return np.concatenate(chunks), np.asarray(offsets, dtype=np.int64), identities


def refinement_diagnostics(coarse: np.ndarray, fine: np.ndarray, scale: np.ndarray) -> dict:
    """Changes in paired paths, moments, quantiles and physical profile tails."""
    delta = (fine-coarse)/scale
    q = (.05, .5, .95)
    thresholds = (.5, 1., 2.)
    tail_changes = np.asarray([np.abs((np.abs(fine).max(2)>t).mean(0)-
                                      (np.abs(coarse).max(2)>t).mean(0)) for t in thresholds])
    exceeded = tail_changes > CALIBRATION["pointwise_tail_probability_change_threshold"]
    return {"paired_standardized_rmse": float(np.sqrt(np.square(delta).mean())),
            "paired_standardized_maximum": float(np.abs(delta).max()),
            "maximum_standardized_mean_change": float(np.max(np.abs(fine.mean(0)-coarse.mean(0))/scale)),
            "maximum_standardized_sd_change": float(np.max(np.abs(fine.std(0)-coarse.std(0))/scale)),
            "maximum_standardized_quantile_change": float(np.max(np.abs(np.quantile(fine, q, axis=0)-np.quantile(coarse, q, axis=0))/scale)),
            "maximum_tail_probability_change": float(tail_changes.max()),
            "tail_probability_exceedance_fraction": float(exceeded.mean()),
            "tail_probability_exceedance_count": int(exceeded.sum()),
            "tail_comparison_pair_count": int(exceeded.size),
            "tail_probability_exceedance_counts_by_threshold": {
                str(t): int(exceeded[i].sum()) for i, t in enumerate(thresholds)},
            "pooled_tail_probability_change": max(abs(float((np.abs(fine).max(2)>threshold).mean())-
                                                      float((np.abs(coarse).max(2)>threshold).mean()))
                                                  for threshold in (.5, 1., 2.))}


def calibrate_solver(model: MatchedFlow, training_blocks: list) -> dict:
    """Always use 128 steps if the last paired refinement passes; else stop.

    This bounded numerical screen does not prove global ODE convergence, tail
    accuracy or generalization. Its thresholds require scientific review before
    real fitting, and cannot be relaxed after an observed failure.
    """
    x, offsets, identities = calibration_conditions(training_blocks)
    prior, refinements = None, []
    for steps in CALIBRATION["steps"]:
        draws = sample_matched_flow(model, x, offsets, sample_count=CALIBRATION["sample_count"],
                                    seed=CALIBRATION["seed"], steps=steps, solver=CALIBRATION["solver"])
        if prior is not None:
            metrics = refinement_diagnostics(prior, draws, model.residual_scale)
            criteria = {name.removesuffix("_limit"): metrics[name.removesuffix("_limit")] <= limit
                        for name, limit in CALIBRATION.items() if name.endswith("_limit")}
            passed = all(criteria.values())
            refinements.append({"coarse_steps": steps//2, "fine_steps": steps, "metrics": metrics,
                                "criteria_passed": criteria, "passed": passed})
        prior = draws
    accepted = refinements[-1]["passed"]
    return {"configuration": dict(CALIBRATION), "subset": identities, "refinements": refinements,
            "passed": accepted, "solver": CALIBRATION["solver"],
            "selected_steps": CALIBRATION["steps"][-1] if accepted else None,
            "scope": "training_subset_numerical_screen_no_global_convergence_claim"}


def monte_carlo_diagnostics(y: np.ndarray, offsets: np.ndarray, draws: np.ndarray) -> dict:
    """Descriptive differences between two independent halves, never selection."""
    from .matched_evaluation import evaluate_matched_samples
    half = len(draws)//2
    scores = [evaluate_matched_samples(y, offsets, d) for d in (draws[:half], draws[half:])]
    keys = ("mean_normalized_sequence_energy_score_m", "mean_energy_score_m", "mean_marginal_crps_m",
            "sample_mean_rmse_m", "median_absolute_lag_one_correlation_error")
    return {"draws_per_half": half, "scores": scores,
            "second_minus_first": {k: None if any(s[k] is None for s in scores) else scores[1][k]-scores[0][k] for k in keys},
            "scope": "single_run_Monte_Carlo_sensitivity_not_independent_validation_or_error_bar"}
