"""Exploratory recorded-clock screens; no physical-availability certification."""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import math

LONGITUDINAL = "/adp/velocity_vehicle_longitudinal"
VEHICLE = "/adp/vehicle_velocity"
TOPICS = (LONGITUDINAL, VEHICLE)
AGE_NS = 100_000_000  # Fixed exploratory screen, not an adopted feature bound.


def sequence_stats(rows, mask):
    lengths, spans, count, first, previous = [], [], 0, None, None
    def close():
        if count:
            lengths.append(count)
            spans.append(int(previous["estimate_source_time_ns_decimal_private"])-first)
    for row, include in zip(rows, mask):
        t = int(row["estimate_source_time_ns_decimal_private"])
        adjacent = previous is not None and row["recording_id"] == previous["recording_id"] and \
            row["estimate_message_index"] == previous["estimate_message_index"]+1 and \
            row["pair_index"] == previous["pair_index"]+1 and \
            0 < t-int(previous["estimate_source_time_ns_decimal_private"]) <= 200_000_000
        if not include or not adjacent:
            close()
            count, first = 0, None
        if include:
            if not count:
                first = t
            count += 1
        previous = row if include else None
    close()
    return {"frames": sum(lengths), "sequences": len(lengths), "transitions": sum(v-1 for v in lengths),
        "maximum_frames": max(lengths, default=0), "maximum_span_s": max(spans, default=0)/1e9}


def summarize(records, targets, old_speed):
    """Use last logged update; never bypass an invalid/future/zero latest update.

    Log time controls which update is observed. Source/publish checks are separate
    integer comparisons. Equal log timestamps are ambiguous; no storage ordering
    is promoted to an availability order. Clock comparability is unproven.
    """
    result, screens = {}, []
    for topic in TOPICS:
        events = sorted((r for r in records if r["topic"] == topic), key=lambda r: int(r["log_ns"]))
        logs = [int(r["log_ns"]) for r in events]
        counts, qualifiers, outer = Counter(), Counter(), Counter()
        for event in events:
            qualifiers[str(event["qualifier"])] += 1
            if event["outer_qualifier"] is not None:
                outer[str(event["outer_qualifier"])] += 1
            counts["decoded_updates"] += 1
            counts["zero_timestamp"] += event["source_ns"] == "0"
            counts["negative_timestamp"] += int(event["source_ns"]) < 0
            counts["missing_nested_message"] += not event["nested_present"]
            counts["nonfinite_value"] += event["value"] is None
        mask, pairs = [], []
        for row in targets:
            deadline = int(row["estimate_log_time_ns_decimal_private"])
            t = int(row["estimate_source_time_ns_decimal_private"])
            pub = int(row["estimate_publish_time_ns_decimal_private"])
            i = bisect_right(logs, deadline)-1
            chosen = events[i] if i >= 0 else None
            reasons, age = [], None
            if chosen is None:
                reasons.append("no_update_in_bounded_log_history")
            else:
                source = int(chosen["source_ns"])
                age = t-source
                if i > 0 and logs[i-1] == logs[i]:
                    reasons.append("latest_log_time_ambiguous")
                if not chosen["nested_present"]:
                    reasons.append("nested_message_absent")
                if source <= 0:
                    reasons.append("nonpositive_source_timestamp")
                elif age < 0:
                    reasons.append("future_source_timestamp")
                elif age > AGE_NS:
                    reasons.append("source_age_above_exploratory_100ms")
                if int(chosen["publish_ns"]) <= 0 or int(chosen["publish_ns"]) > pub:
                    reasons.append("publish_clock_screen_failed")
                if chosen["qualifier"] != 1:
                    reasons.append("inner_qualifier_not_declared_valid")
                if chosen["value"] is None:
                    reasons.append("nonfinite_value")
            clock_screen = not reasons
            # Frozen producer: estimate-derived failures have this prefix;
            # remaining codes (including odometry_* and exception classes) are speed-path failures.
            other_ok = not any(c.startswith("estimate_features_") for c in row["condition_failure_codes"])
            include = row["residual_available"] and other_ok and clock_screen
            mask.append(include)
            old = old_speed.get(row["candidate_index"])
            if include and old is not None:
                pairs.append((old, chosen["value"]))
            screens.append({"topic": topic, "candidate_index": row["candidate_index"],
                "edp_source_ns": str(t), "edp_log_ns": str(deadline),
                "source_age_ns": None if age is None else str(age), "recorded_clock_screen_met": clock_screen,
                "log_time_tied_to_edp": chosen is not None and int(chosen["log_ns"]) == deadline,
                "local_hypothetical_complete": bool(include), "old_complete": row["conditions_available"],
                "residual_available": row["residual_available"], "non_speed_features_available": other_ok,
                "condition_failure_codes": list(row["condition_failure_codes"]),
                "old_speed_mps": old, "candidate_value_native_units": chosen["value"] if chosen else None,
                "reasons": reasons})
        differences = [new-old for old, new in pairs]
        source_deltas = [int(b["source_ns"])-int(a["source_ns"]) for a, b in zip(events, events[1:])
            if int(a["source_ns"]) > 0 and int(b["source_ns"]) > 0]
        result[topic] = {"update_counts": dict(counts), "inner_qualifier_counts": dict(qualifiers),
            "outer_qualifier_counts": dict(outer), "duplicate_log_times": len(logs)-len(set(logs)),
            "edp_log_tie_frames": sum(r["log_time_tied_to_edp"] for r in screens if r["topic"] == topic),
            "source_time_inversions_in_log_order": sum(d < 0 for d in source_deltas),
            "source_delta_ns_range_in_log_order": [str(min(source_deltas)), str(max(source_deltas))] if source_deltas else None,
            "local_hypothetical_complete_under_screen": sequence_stats(targets, mask),
            "native_numeric_comparison_only": {"pairs": len(pairs),
                "mean_native_minus_old_value": math.fsum(d/len(differences) for d in differences) if pairs else None,
                "rmse_native_against_old_value": math.hypot(*(d/math.sqrt(len(differences)) for d in differences)) if pairs else None,
                "units_equivalence_established": False},
            "outer_qualifier_acceptance_adopted": False}
    return {"topics": result,
        "local_original_complete": sequence_stats(targets, [r["residual_available"] and r["conditions_available"] for r in targets]),
        "local_geometry_only": sequence_stats(targets, [r["residual_available"] for r in targets]),
        "physical_causal_availability_proven": False, "speed_feature_adopted": False,
        "interpretation": "Exploratory 100 ms latest-logged-update screen with no invalid-update fallback. Source/publish/log clock semantics and physical availability are unproven. Vehicle outer qualifiers and topic-specific units/reference points are not adopted. Local hypothetical support is not a new dataset or cohort-wide temporal recovery."}, screens
