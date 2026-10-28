"""A fixed strict-prior-log hypothesis, isolated from training feature policy."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
import math

from .velocity_timing import AGE_NS, TOPICS, sequence_stats

REVISION = "v0.19.21-cached-velocity-history-a1"
POLICY = "latest_strictly_prior_log_then_unchanged_100ms_screen"


def summarize(records, targets):
    """Exclude all co-logged updates, select once, then validate without fallback.

    No interpolation, fitted offset, source-time sorting or outer-enum policy.
    Source/publish inversions in recorded order are counted, not repaired.
    Inputs are from one already exposed development recording and fixed window.
    """
    if not targets or len({r["recording_id"] for r in targets}) != 1:
        raise ValueError("history_one_recording_required")
    result, screens = {}, []
    for topic in TOPICS:
        events = sorted((r for r in records if r["topic"] == topic), key=lambda r: int(r["log_ns"]))
        logs = [int(r["log_ns"]) for r in events]
        mask, local = [], []
        for row in targets:
            log = int(row["estimate_log_time_ns_decimal_private"])
            source = int(row["estimate_source_time_ns_decimal_private"])
            publish = int(row["estimate_publish_time_ns_decimal_private"])
            position = bisect_left(logs, log)-1
            chosen = events[position] if position >= 0 else None
            reasons, age = [], None
            if chosen is None:
                reasons.append("no_strictly_prior_update_in_bounded_history")
            else:
                age = source-int(chosen["source_ns"])
                if position > 0 and logs[position-1] == logs[position]:
                    reasons.append("latest_prior_log_time_ambiguous")
                if not chosen["nested_present"]:
                    reasons.append("nested_message_absent")
                if int(chosen["source_ns"]) <= 0:
                    reasons.append("nonpositive_source_timestamp")
                elif age < 0:
                    reasons.append("future_source_timestamp")
                elif age > AGE_NS:
                    reasons.append("source_age_above_exploratory_100ms")
                if not 0 < int(chosen["publish_ns"]) <= publish:
                    reasons.append("publish_clock_screen_failed")
                if chosen["qualifier"] != 1:
                    reasons.append("inner_qualifier_not_declared_valid")
                if chosen["value"] is None or not math.isfinite(chosen["value"]):
                    reasons.append("nonfinite_value")
            other = not any(c.startswith("estimate_features_") for c in row["condition_failure_codes"])
            included = bool(row["residual_available"] and other and not reasons)
            mask.append(included)
            screen = {"topic": topic, "recording_id": row["recording_id"], "candidate_index": row["candidate_index"],
                "edp_source_ns": str(source), "edp_log_ns": str(log), "edp_publish_ns": str(publish),
                "chosen_update_log_ns": chosen["log_ns"] if chosen else None,
                "chosen_update_source_ns": chosen["source_ns"] if chosen else None,
                "chosen_update_publish_ns": chosen["publish_ns"] if chosen else None,
                "source_age_ns": str(age) if age is not None else None,
                "logged_history_age_ns": str(log-int(chosen["log_ns"])) if chosen else None,
                "co_logged_updates_excluded": bisect_right(logs, log)-bisect_left(logs, log),
                "recorded_clock_screen_met": not reasons, "local_hypothetical_complete": included,
                "old_complete": row["conditions_available"], "residual_available": row["residual_available"],
                "original_local_complete": bool(row["residual_available"] and row["conditions_available"]),
                "non_speed_features_available": other, "condition_failure_codes": list(row["condition_failure_codes"]),
                "candidate_value_native_units": chosen["value"] if chosen and chosen["value"] is not None and math.isfinite(chosen["value"]) else None,
                "chosen_inner_qualifier": chosen["qualifier"] if chosen else None,
                "chosen_outer_qualifier_observed_only": chosen.get("outer_qualifier") if chosen else None,
                "chosen_standstill_status_observed_only": chosen.get("standstill_status") if chosen else None,
                "reasons": reasons}
            local.append(screen)
        screens.extend(local)
        valid_ages = [int(r["source_age_ns"]) for r in local if r["source_age_ns"] is not None]
        result[topic] = {"retained_update_count": len(events),
            "co_logged_updates_excluded": sum(r["co_logged_updates_excluded"] for r in local),
            "source_time_inversions_in_log_order": sum(int(b["source_ns"]) < int(a["source_ns"]) for a, b in zip(events, events[1:])),
            "publish_time_inversions_in_log_order": sum(int(b["publish_ns"]) < int(a["publish_ns"]) for a, b in zip(events, events[1:])),
            "failure_reason_counts": dict(Counter(c for r in local for c in r["reasons"])),
            "source_age_ns_range": [str(min(valid_ages)), str(max(valid_ages))] if valid_ages else None,
            "local_hypothetical_complete_under_screen": sequence_stats(targets, mask),
            "gained_original_incomplete_frames": sum(r["local_hypothetical_complete"] and not r["original_local_complete"] for r in local),
            "lost_original_complete_frames": sum(r["original_local_complete"] and not r["local_hypothetical_complete"] for r in local),
            "outer_qualifier_policy_adopted": False, "standstill_policy_adopted": False}
    return {"revision": REVISION, "policy": POLICY, "exploratory_age_ns": AGE_NS, "topics": result,
        "policy_origin": "post_hoc_hypothesis_replayed_on_the_same_fixed_window",
        "independent_generalization_validation": False, "invalid_update_fallback_used": False,
        "source_publish_clock_comparability_established": False, "physical_causal_availability_proven": False,
        "producer_value_semantics_established": False, "speed_feature_adopted": False,
        "cohort_wide_temporal_recovery_established": False}, screens
