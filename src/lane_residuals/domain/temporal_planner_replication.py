"""Prospective aggregation of the frozen short temporal planner experiment."""

from statistics import mean

import numpy as np

from .artifact_registry import require
from . import temporal_planner_pilot as pilot
from .spatial_planner_replication import scores_match

REVISION = "v0.19.33-temporal-planner-replication-a1"
OUTING_COUNT = 7
ENERGY = "normalized_command_sequence_energy_mps2"
LATERAL = "peak_incremental_state_lateral_crps_m"
MARGINAL = "mean_command_marginal_crps_mps2"
METRICS = (ENERGY, LATERAL, MARGINAL)
TEMPORAL_ARMS = ("one_state_ar", "stationary_ar")
PROTOCOL = {
    "scoring": pilot.PROTOCOL,
    "fold_count": OUTING_COUNT,
    "aggregation": "equal_eligible_sequence_within_outing_then_equal_outing_macro",
    "replication_population": "six_previously_unscored_outings_separate_from_pilot",
    "replication_rule": "six_new_outing_primary_macro_negative_and_at_least_four_of_six_negative",
    "empty_primary_support": "block_complete_run",
    "empty_lateral_support": "unavailable_for_affected_macro_group_report_missing_outings",
    "pilot_parity": {"rtol": 1e-9, "atol": 1e-12, "main": "all_sequence_scores",
                     "prefix": "all_stored_aggregate_scores", "sequence_census": "exact"},
    "block_interval": {"width_ns": 30_000_000_000, "replicates": 1000, "seed": 193002,
                       "minimum_blocks": 5, "quantiles": [0.025, 0.975],
                       "origin": "earliest_start_of_all_original_sequences_including_excluded",
                       "weighting": "resample_nonempty_bins_carry_intact_sequences_pool_equal_sequence_mean",
                       "interpretation": "descriptive_within_outing_conditional_on_frozen_models_and_draws"},
    "length_groups": [[2, 2], [3, 5], [6, 9], [10, None]],
    "claims": "development_exogenous_affine_simulator_not_tuning_or_physical_vehicle_validation",
}


def aggregates(scores: dict) -> dict:
    """Remove the sequence table for comparison with the accepted pilot prefix."""
    return {k: v for k, v in scores.items() if k != "sequence_scores"}


def validate_scores(scores: dict, records: list[dict]) -> None:
    """Verify the score census, finite values and recomputed sequence averages."""
    eligible = [r for r in records if r["status"] == "eligible"]
    table = scores["sequence_scores"]
    require(bool(eligible) and len(table) == len(eligible) == scores["eligible_sequences"]
            and [s["sequence_index"] for s in table] == [r["sequence_index"] for r in eligible],
            "temporal_replication_score_census")
    for row, record in zip(table, eligible):
        require(row["frame_count"] == record["frame_count"] and set(row["arms"]) == set(pilot.ARMS),
                "temporal_replication_score_identity")
        for values in row["arms"].values():
            require(set(values) == set(METRICS)
                    and (values[LATERAL] is None) == (record["frame_count"] < 3)
                    and all((v is None and k == LATERAL) or
                            (type(v) is float and np.isfinite(v)) for k, v in values.items()),
                    "temporal_replication_finite_scores")
    expected = {arm: {metric: _mean_available([s["arms"][arm][metric] for s in table])
                      for metric in METRICS} for arm in pilot.ARMS}
    contrasts = {arm: float(np.mean([s["arms"][arm][ENERGY] - s["arms"][arm+"_permuted"][ENERGY]
                                    for s in table])) for arm in TEMPORAL_ARMS}
    require(scores_match(scores["arms"], expected)
            and scores_match(scores["temporal_minus_permuted_energy_mps2"], contrasts),
            "temporal_replication_score_arithmetic")


def _mean_available(values: list) -> float | None:
    kept = [v for v in values if v is not None]
    return float(np.mean(kept)) if kept else None


def diagnose(scores: dict, prefix: dict, records: list[dict]) -> dict:
    """Apply the already declared block and length diagnostics to one outing."""
    validate_scores(scores, records)
    validate_scores(prefix, records)
    eligible = [r for r in records if r["status"] == "eligible"]
    origin = min(int(r["source_start_ns_decimal"]) for r in records)
    settings = PROTOCOL["block_interval"]
    bins = [(int(r["source_start_ns_decimal"]) - origin) // settings["width_ns"] for r in eligible]
    unique, inverse = np.unique(bins, return_inverse=True)
    counts = np.bincount(inverse)
    selections = np.random.default_rng(settings["seed"]).integers(
        len(unique), size=(settings["replicates"], len(unique)))
    lengths = np.array([r["frame_count"] for r in eligible])
    result = {}
    for arm in TEMPORAL_ARMS:
        delta = np.array([s["arms"][arm][ENERGY] - s["arms"][arm+"_permuted"][ENERGY]
                          for s in scores["sequence_scores"]])
        totals = np.bincount(inverse, weights=delta)
        bootstrap = totals[selections].sum(axis=1) / counts[selections].sum(axis=1)
        bounds = np.quantile(bootstrap, settings["quantiles"]).tolist() if len(unique) >= settings["minimum_blocks"] else None
        groups = []
        for low, high in PROTOCOL["length_groups"]:
            mask = lengths >= low
            if high is not None:
                mask &= lengths <= high
            groups.append(dict(minimum_frames=low, maximum_frames=high, sequences=int(mask.sum()),
                               mean_difference_mps2=float(delta[mask].mean()) if mask.any() else None,
                               negative_fraction=float(np.mean(delta[mask] < 0)) if mask.any() else None))
        result[arm] = dict(mean_difference_mps2=float(delta.mean()),
                           prefix_difference_mps2=prefix["temporal_minus_permuted_energy_mps2"][arm],
                           negative_sequences=int(np.sum(delta < 0)), positive_sequences=int(np.sum(delta > 0)),
                           tied_sequences=int(np.sum(delta == 0)), eligible_sequences=len(delta),
                           nonempty_source_bins=[int(v) for v in unique],
                           source_origin_ns_decimal=str(origin),
                           descriptive_95_block_interval_mps2=bounds, length_groups=groups)
    return result


def summarize_outings(folds: dict[str, dict], pilot_outing: str) -> dict:
    """Keep each outing equally weighted and the six new outcomes explicit."""
    require(len(folds) == OUTING_COUNT and pilot_outing in folds
            and all(f["scores"]["eligible_sequences"] > 0 for f in folds.values()),
            "temporal_replication_complete_primary_folds_required")

    def group(ids: list[str]) -> dict:
        missing = [i for i in ids if folds[i]["scores"]["arms"]["nominal"][LATERAL] is None]
        def macro(key: str) -> dict:
            return {arm: {metric: None if metric == LATERAL and missing else
                          mean(folds[i][key]["arms"][arm][metric] for i in ids)
                          for metric in METRICS} for arm in pilot.ARMS}
        contrasts = {}
        for arm in TEMPORAL_ARMS:
            values = [folds[i]["scores"]["temporal_minus_permuted_energy_mps2"][arm] for i in ids]
            contrasts[arm] = dict(mean_difference_mps2=mean(values), minimum_difference_mps2=min(values),
                                 maximum_difference_mps2=max(values), negative_outings=sum(v < 0 for v in values),
                                 positive_outings=sum(v > 0 for v in values), tied_outings=sum(v == 0 for v in values),
                                 prefix_mean_difference_mps2=mean(folds[i]["prefix_scores"][
                                     "temporal_minus_permuted_energy_mps2"][arm] for i in ids))
        return dict(outing_ids=ids, outing_count=len(ids), arms=macro("scores"), prefix_arms=macro("prefix_scores"),
                    temporal_contrasts=contrasts,
                    lateral_status="unavailable_empty_support" if missing else "complete",
                    outings_without_lateral_support=missing)

    ids = list(folds)
    all_seven, six = group(ids), group([i for i in ids if i != pilot_outing])
    primary = six["temporal_contrasts"]["one_state_ar"]
    return dict(all_seven=all_seven, six_beyond_pilot=six,
                descriptive_primary_replication_passes=primary["mean_difference_mps2"] < 0
                and primary["negative_outings"] >= 4)
