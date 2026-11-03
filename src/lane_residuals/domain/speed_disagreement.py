"""Fixed descriptive bracket questions; never a speed correction or selector."""
from collections import Counter
import math

from .artifact_registry import require
from .direct_speed_study import AGREEMENT_LIMITS, agreement
from .speed_mechanism import stamp
from .velocity_timing import TOPICS

REVISION = "v0.19.26-cached-speed-disagreement-a1"
INTERVAL_NS = 50_000_000
GROUPS = ("all_shared", "source_equal", "source_earlier", "previous_exact",
    "previous_interpolated", "previous_unknown", "previous_crosses_second", "previous_same_second")


def bracket(target, lower, upper):
    target, lower, upper = stamp(target), stamp(lower), stamp(upper)
    if None in (target, lower, upper):
        return {"state":"missing", "span_ns":None, "fraction":None, "crosses_second":None}
    if min(target, lower, upper) <= 0 or lower > upper or not lower <= target <= upper:
        return {"state":"invalid", "span_ns":None, "fraction":None, "crosses_second":None}
    exact = lower == upper
    return {"state":"exact" if exact else "interpolated", "span_ns":str(upper-lower),
        "fraction":0.0 if exact else (target-lower)/(upper-lower),
        "crosses_second":lower//1_000_000_000 != upper//1_000_000_000}


def summarize(targets, frames):
    targets_by_id = {(r["recording_id"], r["candidate_index"]):r for r in targets}
    require(len(targets_by_id) == len(targets), "disagreement_duplicate_target")
    expected = {(t,*identity) for t in TOPICS for identity in targets_by_id}
    seen, result = set(), []
    for frame in frames:
        identity = (frame["topic"], frame["recording_id"], frame["candidate_index"])
        require(identity in expected and identity not in seen, "disagreement_frame_identity")
        seen.add(identity)
        target = targets_by_id[identity[1:]]
        source = stamp(target["estimate_source_time_ns_decimal_private"])
        require(source is not None and source >= INTERVAL_NS, "disagreement_source_epoch")
        evidence = target.get("speed_bracket_evidence") or {}
        previous = bracket(str(source-INTERVAL_NS), evidence.get("previous_lower_timestamp_ns_decimal_private"),
            evidence.get("previous_upper_timestamp_ns_decimal_private"))
        current = bracket(str(source), evidence.get("current_lower_timestamp_ns_decimal_private"),
            evidence.get("current_upper_timestamp_ns_decimal_private"))
        old, direct = frame["old_speed_mps"], frame["candidate_value_native_units"]
        for value in (old, direct):
            require(value is None or type(value) in (int,float) and math.isfinite(value), "disagreement_finite_value")
        shared = bool(frame["original_local_complete"] and frame["local_hypothetical_complete"])
        require(not shared or old is not None and direct is not None, "disagreement_shared_value_missing")
        difference = direct-old if shared else None
        result.append({"topic":frame["topic"], "recording_id":frame["recording_id"], "candidate_index":frame["candidate_index"],
            "edp_source_ns":str(source), "source_age_ns":frame["source_age_ns"],
            "source_equal":frame["selected_source_time_equal_to_edp"],
            "original_complete":frame["original_local_complete"], "primary_complete":frame["local_hypothetical_complete"],
            "strict_source_complete":frame["strict_source_local_hypothetical_complete"],
            "shared_original_complete":shared, "old_speed_mps":old, "candidate_speed_mps":direct,
            "candidate_minus_old_mps":difference,
            "exceeds_frozen_maximum_difference":abs(difference)>AGREEMENT_LIMITS["maximum_absolute_difference_mps"] if shared else None,
            "previous_bracket_state":previous["state"], "previous_bracket_span_ns":previous["span_ns"],
            "previous_interpolation_fraction":previous["fraction"], "previous_bracket_crosses_second":previous["crosses_second"],
            "current_bracket_state":current["state"], "current_bracket_span_ns":current["span_ns"],
            "current_interpolation_fraction":current["fraction"], "condition_failure_codes":target["condition_failure_codes"]})
    require(seen == expected, "disagreement_missing_frame")
    groups = []
    for topic in TOPICS:
        local = [r for r in result if r["topic"] == topic]
        shared = [r for r in local if r["shared_original_complete"]]
        predicates = {
            "all_shared":lambda r:True,
            "source_equal":lambda r:r["source_equal"],
            "source_earlier":lambda r:stamp(r["source_age_ns"]) is not None and stamp(r["source_age_ns"]) > 0,
            "previous_exact":lambda r:r["previous_bracket_state"] == "exact",
            "previous_interpolated":lambda r:r["previous_bracket_state"] == "interpolated",
            "previous_unknown":lambda r:r["previous_bracket_state"] in ("missing","invalid"),
            "previous_crosses_second":lambda r:r["previous_bracket_crosses_second"] is True,
            "previous_same_second":lambda r:r["previous_bracket_crosses_second"] is False,
        }
        for name in GROUPS:
            selected = [r for r in shared if predicates[name](r)]
            groups.append({"topic":topic, "group":name, "rows":len(selected),
                "above_frozen_maximum_difference":sum(r["exceeds_frozen_maximum_difference"] for r in selected),
                **agreement([(r["old_speed_mps"],r["candidate_speed_mps"]) for r in selected])})
        require(sum(g["rows"] for g in groups if g["topic"] == topic and g["group"] in
            ("previous_exact","previous_interpolated","previous_unknown")) == len(shared), "disagreement_group_accounting")
    return {"revision":REVISION, "target_count":len(targets), "frame_rows":len(result), "groups":groups,
        "bracket_states_all_frames":dict(Counter(r["previous_bracket_state"] for r in result)),
        "limits_unchanged":dict(AGREEMENT_LIMITS), "odometry_positions_in_cache":False,
        "cause_identified":False, "speed_feature_adopted":False, "model_impact_established":False,
        "interpretation":"Post hoc descriptive associations on fixed exposed windows; no correction, truth reference or causal mechanism is inferred."}, result
