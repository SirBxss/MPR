"""Paired source-equality sensitivity on the same selected recorded update.

This diagnostic does not establish producer semantics or change feature policy.
"""
from __future__ import annotations

from collections import Counter

from .velocity_history import summarize as history_summary
from .velocity_timing import TOPICS, sequence_stats

REVISION = "v0.19.22-paired-source-tie-audit-a1"


def clock_observations(values):
    """Integer observations only; neither epoch nor clock domain is inferred."""
    values = [int(v) for v in values]
    return {
        "count": len(values),
        "minimum_ns_decimal": str(min(values)) if values else None,
        "maximum_ns_decimal": str(max(values)) if values else None,
        "zero_count": sum(v == 0 for v in values),
        "negative_count": sum(v < 0 for v in values),
        "seconds_component_range": [min(values)//1_000_000_000, max(values)//1_000_000_000] if values else None,
        "positive_timestamp_below_five_seconds_count": sum(0 < v < 5_000_000_000 for v in values),
        "adjacent_equal_count": sum(a == b for a, b in zip(values, values[1:])),
        "adjacent_decreasing_count": sum(b < a for a, b in zip(values, values[1:])),
        "epoch_or_producer_identified": False,
    }


def summarize(records, targets):
    """Run the unchanged primary once, then exclude equality on that sample.

    A secondary failure cannot cause another update to be selected. Source-age,
    publish, quality, geometry, other-feature and reset rules remain unchanged.
    Both conventions are post hoc when applied to the original cached window.
    """
    primary, original_screens = history_summary(records, targets)
    screens, topics = [], {}
    for topic in TOPICS:
        local = []
        for original in original_screens:
            if original["topic"] != topic:
                continue
            row = dict(original)
            row["reasons"] = list(original["reasons"])
            age = row["source_age_ns"]
            age = int(age) if age is not None else None
            equal = age == 0
            secondary_reasons = list(row["reasons"])
            if equal:
                secondary_reasons.append("selected_source_time_equal_to_edp")
            row.update(
                selected_source_time_equal_to_edp=equal,
                strict_source_recorded_clock_screen_met=bool(row["recorded_clock_screen_met"] and age is not None and age > 0),
                strict_source_local_hypothetical_complete=bool(row["local_hypothetical_complete"] and age is not None and age > 0),
                strict_source_reasons=secondary_reasons,
            )
            local.append(row)
        primary_mask = [r["local_hypothetical_complete"] for r in local]
        secondary_mask = [r["strict_source_local_hypothetical_complete"] for r in local]
        old_mask = [r["original_local_complete"] for r in local]
        topic_records = sorted((r for r in records if r["topic"] == topic), key=lambda r: int(r["log_ns"]))
        topics[topic] = {
            "primary_source_at_or_before": primary["topics"][topic],
            "secondary_source_strictly_before": {
                "local_hypothetical_complete_under_screen": sequence_stats(targets, secondary_mask),
                "gained_original_incomplete_frames": sum(s and not o for s, o in zip(secondary_mask, old_mask)),
                "lost_original_complete_frames": sum(o and not s for s, o in zip(secondary_mask, old_mask)),
                "failure_reason_counts": dict(Counter(c for r in local for c in r["strict_source_reasons"])),
            },
            "selected_source_equal_frames": sum(r["selected_source_time_equal_to_edp"] for r in local),
            "primary_complete_source_equal_frames": sum(p and r["selected_source_time_equal_to_edp"] for p, r in zip(primary_mask, local)),
            "primary_only_frames": sum(p and not s for p, s in zip(primary_mask, secondary_mask)),
            "secondary_only_frames": sum(s and not p for p, s in zip(primary_mask, secondary_mask)),
            "retained_update_clocks_in_log_order": {
                field: clock_observations(r[field] for r in topic_records)
                for field in ("source_ns", "log_ns", "publish_ns")
            },
        }
        screens.extend(local)
    return {
        "revision": REVISION,
        "primary_analysis_unchanged": primary,
        "topics": topics,
        "edp_cached_target_clocks_in_candidate_order": {
            key: clock_observations(r[field] for r in targets) for key, field in (
                ("source_ns", "estimate_source_time_ns_decimal_private"),
                ("log_ns", "estimate_log_time_ns_decimal_private"),
                ("publish_ns", "estimate_publish_time_ns_decimal_private"))
        },
        "secondary_uses_same_selected_update": True,
        "secondary_update_reselection_used": False,
        "policy_origin": "post_hoc_on_original_cached_window_not_independent_validation",
        "clock_interpretation": "Header log/publish fields and source stamps are observed numeric clocks; producer publication, measurement epoch and consumer receipt are not established.",
        "per_message_edp_topology_and_event_qualifier_retained": False,
        "producer_value_semantics_established": False,
        "source_publish_clock_comparability_established": False,
        "deployed_producer_identified": False,
        "physical_causal_availability_proven": False,
        "speed_feature_adopted": False,
        "cohort_wide_temporal_recovery_established": False,
        "independent_generalization_validation": False,
    }, screens
