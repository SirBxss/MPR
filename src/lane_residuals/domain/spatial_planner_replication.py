"""Fixed aggregation and parity rules for the spatial planner replication."""

import math
from statistics import mean

from .artifact_registry import require
from .spatial_planner_pilot import ARMS, FULL, PROTOCOL as PILOT_PROTOCOL

REVISION = "v0.19.31-spatial-planner-replication-a1"
OUTING_COUNT = 7
PARITY_RELATIVE_TOLERANCE = 1e-9
PARITY_ABSOLUTE_TOLERANCE = 1e-12
SPEED_CASES = ("minus_4_mps", "original", "plus_4_mps")
PROTOCOL = {
    "scoring": PILOT_PROTOCOL,
    "fold_count": OUTING_COUNT,
    "aggregation": "equal_outing_weight_on_within_outing_row_means",
    "replication": "six_previously_unscored_outings_separate_from_pilot",
    "empty_primary_support": "block_complete_run",
    "empty_common_speed_support": "unavailable_for_affected_macro_group",
    "parity": {"rtol": PARITY_RELATIVE_TOLERANCE, "atol": PARITY_ABSOLUTE_TOLERANCE},
}


def scores_match(actual, accepted) -> bool:
    """Require exact structure and counts, allowing roundoff in score values."""
    if type(actual) is not type(accepted):
        return False
    if isinstance(actual, dict):
        return actual.keys() == accepted.keys() and all(scores_match(actual[k], accepted[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(accepted) and all(scores_match(a, b) for a, b in zip(actual, accepted))
    if isinstance(actual, float):
        return math.isclose(actual, accepted, rel_tol=PARITY_RELATIVE_TOLERANCE,
                            abs_tol=PARITY_ABSOLUTE_TOLERANCE)
    return actual == accepted


def _macro_metrics(scores: list[dict]) -> dict:
    """Average each reported scalar over outings, including within outing quantiles."""
    def fields(groups: list[dict]) -> dict:
        return {field: mean(g[field] for g in groups) for field in groups[0]}

    return {
        "arms": {arm: {metric: fields([s["arms"][arm][metric] for s in scores])
                       for metric in scores[0]["arms"][arm]} for arm in ARMS},
        "replay": {metric: fields([s["replay"][metric] for s in scores])
                   for metric in scores[0]["replay"]},
    }


def summarize_outings(outing_scores: dict[str, dict], pilot_outing: str) -> dict:
    """Publish macro results only when all frozen primary folds are present."""
    require(len(outing_scores) == OUTING_COUNT and pilot_outing in outing_scores
            and all(s["primary"]["rows"] > 0 for s in outing_scores.values()),
            "spatial_replication_complete_primary_folds_required")

    def group(ids: list[str]) -> dict:
        scores = [outing_scores[i] for i in ids]
        primary = [s["primary"] for s in scores]
        speed = [s["speed_sensitivity"] for s in scores]
        missing = [i for i, s in zip(ids, speed) if s["original"]["rows"] == 0]
        return {
            "outing_ids": ids,
            "outing_count": len(ids),
            "primary": {
                **_macro_metrics(primary),
                "mean_crps_difference_vs_full": {
                    a: mean(p["primary_crps_contrasts"][a]["mean_crps_difference_vs_full"] for p in primary)
                    for a in ARMS if a != FULL
                },
                "prefix_primary_crps": {a: mean(p["prefix_primary_crps"][a] for p in primary) for a in ARMS},
            },
            "speed_sensitivity": {
                "status": "unavailable_empty_common_support" if missing else "complete",
                "outings_without_common_support": missing,
                "macro": None if missing else {case: _macro_metrics([s[case] for s in speed])
                                               for case in SPEED_CASES},
            },
        }

    ids = list(outing_scores)
    return {"all_seven": group(ids), "six_beyond_pilot": group([i for i in ids if i != pilot_outing])}
