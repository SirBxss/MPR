"""Prospectively fixed diagnostics; no feature adoption or training policy."""
from collections import Counter
import math

from .artifact_registry import require
from .speed_mechanism import endpoint, stamp
from .velocity_source_ties import summarize as paired_summary
from .velocity_timing import TOPICS, sequence_stats

REVISION = "v0.19.24-bounded-direct-speed-study-a1"
MAX_FILE_BYTES = 4*1024**3
MAX_TOTAL_BYTES = 6*1024**3
AGREEMENT_LIMITS = {"absolute_bias_mps": .5, "rms_difference_mps": 1., "maximum_absolute_difference_mps": 3.}


def sequences(rows, mask):
    require(len(rows) == len(mask), "study_mask_length_mismatch")
    result, current, previous = [], [], None
    def close():
        if current:
            a, b = current[0], current[-1]
            result.append({"recording_id": a["recording_id"], "frames": len(current),
                "first_candidate_index": a["candidate_index"], "last_candidate_index": b["candidate_index"],
                "span_ns_decimal": str(int(b["estimate_source_time_ns_decimal_private"])-int(a["estimate_source_time_ns_decimal_private"]))})
    for row, include in zip(rows, mask):
        adjacent = previous is not None and row["recording_id"] == previous["recording_id"] and \
            row["estimate_message_index"] == previous["estimate_message_index"]+1 and row["pair_index"] == previous["pair_index"]+1 and \
            0 < int(row["estimate_source_time_ns_decimal_private"])-int(previous["estimate_source_time_ns_decimal_private"]) <= 200_000_000
        if not include or not adjacent:
            close(); current = []
        if include:
            current.append(row)
        previous = row if include else None
    close()
    support = sequence_stats(rows, mask)
    require(sum(r["frames"] for r in result) == support["frames"] and len(result) == support["sequences"] and
        max((int(r["span_ns_decimal"]) for r in result), default=0)/1e9 == support["maximum_span_s"], "study_sequence_accounting_mismatch")
    return {**support, "runs": result}


def agreement(pairs):
    if not pairs:
        return {"pairs": 0, "assessable": False, "within_provisional_tolerances": None,
            "bias_mps": None, "rms_difference_mps": None, "maximum_absolute_difference_mps": None,
            "old_range_mps": None, "direct_range_mps": None, "maximum_difference_over_combined_range": None}
    old, direct = zip(*pairs)
    differences = [b-a for a,b in pairs]
    bias = math.fsum(d/len(pairs) for d in differences)
    rms = math.hypot(*(d/math.sqrt(len(pairs)) for d in differences))
    maximum = max(abs(d) for d in differences)
    require(all(math.isfinite(v) for v in (bias,rms,maximum)), "study_nonfinite_comparison")
    spread = max(*old,*direct)-min(*old,*direct)
    return {"pairs": len(pairs), "assessable": True, "bias_mps": bias, "rms_difference_mps": rms,
        "maximum_absolute_difference_mps": maximum, "old_range_mps": [min(old),max(old)],
        "direct_range_mps": [min(direct),max(direct)],
        "maximum_difference_over_combined_range": maximum/spread if spread > 0 else None,
        "within_provisional_tolerances": abs(bias) <= AGREEMENT_LIMITS["absolute_bias_mps"] and
            rms <= AGREEMENT_LIMITS["rms_difference_mps"] and maximum <= AGREEMENT_LIMITS["maximum_absolute_difference_mps"]}


def analyze(records, targets, old_speed):
    paired, frames = paired_summary(records, targets)
    # The functions retain their original revision IDs; these are new-window
    # applications of their unchanged computations, not the old post-hoc run.
    paired["policy_origin"] = "predeclared_rules_on_new_bounded_development_windows"
    paired["primary_analysis_unchanged"]["policy_origin"] = paired["policy_origin"]
    original_mask = [r["residual_available"] and r["conditions_available"] for r in targets]
    denominator = sum(r["residual_available"] and not any(c.startswith("estimate_features_") for c in r["condition_failure_codes"]) for r in targets)
    original = sequences(targets, original_mask)
    topics = {}
    for topic in TOPICS:
        local = [r for r in frames if r["topic"] == topic]
        require(len(local) == len(targets), "study_frame_accounting_mismatch")
        rules = {}
        for name, key, reasons in (("primary", "local_hypothetical_complete", "reasons"),
                ("strict_source_secondary", "strict_source_local_hypothetical_complete", "strict_source_reasons")):
            mask = [r[key] for r in local]
            pairs = []
            for r, included in zip(local, mask):
                r["old_speed_mps"] = old_speed.get(r["candidate_index"])
                if included and r["original_local_complete"]:
                    require(r["candidate_index"] in old_speed, "study_original_complete_speed_missing")
                    pairs.append((old_speed[r["candidate_index"]], r["candidate_value_native_units"]))
            support = sequences(targets, mask)
            coverage = support["frames"]/denominator if denominator else None
            rules[name] = {"support": support, "stratum_coverage": coverage,
                "failure_reason_counts": dict(Counter(c for r in local for c in r[reasons])),
                "gained_original_incomplete_frames": sum(a and not b for a,b in zip(mask,original_mask)),
                "lost_original_complete_frames": sum(b and not a for a,b in zip(mask,original_mask)),
                "agreement_on_original_complete_rows": agreement(pairs)}
        values = [r["value"] for r in records if r["topic"] == topic and r["value"] is not None]
        topics[topic] = {"rules": rules, "negative_retained_value_count": sum(v < 0 for v in values),
            "primary_temporal_target_met": bool(denominator and rules["primary"]["stratum_coverage"] >= .95 and
                rules["primary"]["support"]["maximum_span_s"] >= 5),
            "all_retained_candidates": len(targets), "geometry_without_estimate_failure_rows": denominator}
    return {"paired_selector_diagnostics": paired, "original_support": original, "topics": topics,
        "provisional_agreement_limits": AGREEMENT_LIMITS, "comparison_units_premise": "source-reported m/s; physical quantity equivalence unproven",
        "feature_adopted": False, "cohort_recovery_established": False}, frames


def population(blocks, audits):
    """Per-outing, per-station descriptive comparison on accepted geometry."""
    import numpy as np
    summaries, stations = [], []
    for block in blocks:
        rows = audits[block.outing_id]
        arrays = block.archive.arrays
        index = {(str(r),int(c)):i for i,(r,c) in enumerate(zip(arrays["recording_id"], arrays["candidate_index"]))}
        expected = {(r["recording_id"],r["candidate_index"]) for r in rows if r["residual_available"]}
        require(len(index) == len(arrays["candidate_index"]) and set(index) == expected, "study_population_geometry_identity")
        complete = [bool(r["residual_available"] and r["conditions_available"]) for r in rows]
        future = [bool(r["residual_available"] and r["condition_failure_codes"] == ["speed_uses_future_source_sample"]) for r in rows]
        groups = {}
        for name, mask in (("original_complete",complete),("future_only",future)):
            selected = [index[r["recording_id"],r["candidate_index"]] for r,keep in zip(rows,mask) if keep]
            values = arrays["residuals_m"][selected]
            groups[name] = {"count": len(selected), "mean": values.mean(axis=0).tolist() if selected else None,
                "std": values.std(axis=0,ddof=0).tolist() if selected else None,
                "rms": np.sqrt(np.mean(values*values,axis=0)).tolist() if selected else None}
        for j,station in enumerate(arrays["stations_m"]):
            item = {"outing_id": block.outing_id, "station_m": float(station)}
            for name,g in groups.items():
                item[name+"_count"] = g["count"]
                for statistic in ("mean","std","rms"):
                    item[name+"_"+statistic+"_m"] = g[statistic][j] if g["count"] else None
            item["future_only_minus_complete_mean_m"] = groups["future_only"]["mean"][j]-groups["original_complete"]["mean"][j] if all(g["count"] for g in groups.values()) else None
            stations.append(item)
        equality, unknown = [], 0
        for row in rows:
            e = row.get("speed_bracket_evidence") or {}
            equal,_ = endpoint(stamp(row.get("estimate_source_time_ns_decimal_private")),
                stamp(e.get("current_lower_timestamp_ns_decimal_private")),stamp(e.get("current_upper_timestamp_ns_decimal_private")))
            equality.append(equal is True); unknown += equal is None
        spacing, previous = Counter(), {}
        for row,keep in zip(rows,equality):
            if keep:
                recording = row["recording_id"]
                if recording in previous:
                    delta = row["estimate_message_index"]-previous[recording]
                    require(delta > 0, "study_population_message_order")
                    spacing[str(delta)] += 1
                previous[recording] = row["estimate_message_index"]
        summaries.append({"outing_id": block.outing_id, "retained_candidates": len(rows),
            "original_complete_rows": sum(complete), "future_only_rows": sum(future),
            "other_rows": len(rows)-sum(complete)-sum(future), "endpoint_unassessable_rows": unknown,
            "original_complete_sequences": sequences(rows,complete), "endpoint_equal_sequences": sequences(rows,equality),
            "endpoint_equal_message_index_spacing_counts_within_recording": dict(spacing),
            "archive_sha256": block.archive.summary_sha256})
    return {"outings": summaries, "station_summary_count": len(stations), "frame_independence_assumed": False,
        "population_bias_or_representativeness_established": False,
        "non_speed_conditions_on_incomplete_rows": "not_exported_in_original_archive",
        "interpretation": "Descriptive within-outing residual differences and retained-candidate timing patterns only; no model impact or deterministic physical beat follows."}, stations
