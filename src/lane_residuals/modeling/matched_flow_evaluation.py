"""Common sample score summaries with explicit unavailable flow likelihood."""
import numpy as np

from ..domain.artifact_registry import require

METRICS = ("mean_normalized_sequence_energy_score_m", "mean_marginal_crps_m", "mean_energy_score_m",
           "sample_mean_rmse_m", "median_absolute_lag_one_correlation_error", "mean_physical_joint_nll")


def comparison(rows: list[dict]) -> dict:
    """Equal outing means and support counts; missing density stays unavailable."""
    output = {}
    for model in sorted({r["model"] for r in rows}):
        selected = [r for r in rows if r["model"] == model]
        require(len({r["fold"]["fold_id"] for r in selected}) == len(selected), "flow_unique_comparison_folds")
        def summary(values):
            available = [v for v in values if v is not None]
            require(all(np.isfinite(v) for v in available), "flow_comparison_finite")
            return {"equal_outing_mean": float(np.mean(available)) if available else None,
                    "assessed_outings": len(available), "unassessed_outings": len(values)-len(available)}
        output[model] = {"outings": len(selected), "metrics": {k: summary([r["metrics"].get(k) for r in selected]) for k in METRICS},
                         "intervals": {level: {k: summary([r["metrics"]["intervals"][level][k] for r in selected])
                                      for k in ("coverage", "mean_width_m")} for level in ("0.5", "0.8", "0.95")},
                         "tail_brier": {level: summary([r["metrics"]["profile_max_absolute_tail"][level]["brier_score"] for r in selected])
                                        for level in ("0.5", "1.0", "2.0")}}
    return output


def paired_comparisons(baselines: list[dict], results: list[dict]) -> dict:
    primary = ("mean_normalized_sequence_energy_score_m", "median_absolute_lag_one_correlation_error")
    output = {}
    for candidate in sorted({r["model"] for r in results}):
        rr = {r["fold"]["fold_id"]: r for r in results if r["model"] == candidate}
        output[candidate] = {}
        for baseline in sorted({r["model"] for r in baselines}):
            bb = {r["fold"]["fold_id"]: r for r in baselines if r["model"] == baseline}
            require(set(bb) == set(rr), "flow_exact_paired_folds")
            metrics = {}
            for metric in primary:
                pairs = []
                for fold_id, r in rr.items():
                    require(bb[fold_id]["fold"] == r["fold"], "flow_exact_paired_fold_identity")
                    a, b = bb[fold_id]["metrics"][metric], r["metrics"][metric]
                    pairs.append({"validation_outing": r["fold"]["validation_outing"], "baseline": a, "candidate": b,
                                  "difference": None if a is None or b is None else b-a})
                d = [p["difference"] for p in pairs if p["difference"] is not None]
                metrics[metric] = {"paired_outings": pairs, "assessed_outings": len(d), "unassessed_outings": len(pairs)-len(d),
                                   "equal_outing_mean_difference": float(np.mean(d)) if d else None,
                                   "improved_outings": sum(v < 0 for v in d), "worsened_outings": sum(v > 0 for v in d)}
            output[candidate][baseline] = metrics
    return {"direction": "candidate_minus_baseline_lower_is_better", "models": output,
            "scope": "descriptive_development_no_significance_automatic_winner_or_planner_claim"}
