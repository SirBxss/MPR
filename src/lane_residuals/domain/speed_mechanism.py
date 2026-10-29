"""Fixed row-local timestamp questions, never a replacement speed feature."""
from collections import Counter
import re
from .artifact_registry import require

REVISION = "v0.19.23-cached-speed-mechanism-a1"
TICK_NS = 2**20
BRACKETS = ("current_lower_timestamp_ns_decimal_private", "current_upper_timestamp_ns_decimal_private",
    "previous_lower_timestamp_ns_decimal_private", "previous_upper_timestamp_ns_decimal_private")
CELLS = ("complete_equal", "complete_unequal", "incomplete_equal", "incomplete_unequal")


def stamp(value):
    if value is None:
        return None
    if type(value) is not str or re.fullmatch(r"0|-?[1-9][0-9]*", value) is None:
        raise ValueError("mechanism_integer_decimal_stamp_required")
    return int(value)


def clock_summary(pairs):
    pairs = [(recording, stamp(value)) for recording, value in pairs]
    positive = [(recording, value) for recording, value in pairs if value is not None and value > 0]
    unique = set(positive)
    on_grid = lambda value: (value % 1_000_000_000) % TICK_NS == 0
    return {"entries": len(pairs), "missing_entries": sum(v is None for _, v in pairs),
        "nonpositive_entries": sum(v is not None and v <= 0 for _, v in pairs),
        "positive_entries": len(positive), "positive_entries_on_grid": sum(on_grid(v) for _, v in positive),
        "unique_positive_recording_stamp_pairs": len(unique), "unique_pairs_on_grid": sum(on_grid(v) for _, v in unique),
        "clock_identity_or_physical_resolution_proven": False}


def endpoint(source, lower, upper):
    if source is None or lower is None or upper is None:
        return None, "missing_current_bracket_or_edp_stamp"
    if min(source, lower, upper) <= 0:
        return None, "nonpositive_current_bracket_or_edp_stamp"
    if lower > upper:
        return None, "inverted_current_bracket"
    if not lower <= source <= upper:
        return None, "edp_outside_current_bracket"
    return source in (lower, upper), None


def summarize(outing_id, rows, original_support, previously_examined):
    if not rows or type(previously_examined) is not bool:
        raise ValueError("mechanism_rows_and_prior_label_required")
    all_table, eligible_table = dict.fromkeys(CELLS, 0), dict.fromkeys(CELLS, 0)
    failures, unknown, eligible_unknown = Counter(), Counter(), Counter()
    frames, seen = [], set()
    for row in rows:
        if type(row["recording_id"]) is not str or not row["recording_id"]:
            raise ValueError("mechanism_recording_identity_required")
        for key in ("candidate_index", "estimate_message_index", "pair_index"):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError("mechanism_original_row_index_required")
        identity = (row["recording_id"], row["candidate_index"])
        if identity in seen:
            raise ValueError("mechanism_duplicate_candidate_row")
        seen.add(identity)
        if any(type(row[k]) is not bool for k in ("residual_available", "conditions_available")):
            raise ValueError("mechanism_original_boolean_required")
        codes = row["condition_failure_codes"]
        if type(codes) is not list or any(type(c) is not str for c in codes):
            raise ValueError("mechanism_failure_code_list_required")
        evidence = row.get("speed_bracket_evidence")
        if evidence is None:
            evidence = {}
        if type(evidence) is not dict:
            raise ValueError("mechanism_bracket_object_required")
        times = {key: stamp(evidence.get(key)) for key in BRACKETS}
        source = stamp(row.get("estimate_source_time_ns_decimal_private"))
        equal, reason = endpoint(source, times[BRACKETS[0]], times[BRACKETS[1]])
        complete = row["residual_available"] and row["conditions_available"]
        no_estimate_failure = not any(c.startswith("estimate_features_") for c in codes)
        eligible = row["residual_available"] and no_estimate_failure
        cell = ("complete_" if complete else "incomplete_")+("equal" if equal else "unequal") if equal is not None else None
        if cell is None:
            unknown[reason] += 1
            if eligible:
                eligible_unknown[reason] += 1
        else:
            all_table[cell] += 1
            if eligible:
                eligible_table[cell] += 1
        failures.update(codes)
        frames.append({"outing_id": outing_id, "previously_examined_case": previously_examined,
            "recording_id": row["recording_id"], "candidate_index": row["candidate_index"],
            "estimate_message_index": row["estimate_message_index"], "pair_index": row["pair_index"],
            "edp_source_ns": None if source is None else str(source),
            **{key: None if value is None else str(value) for key, value in times.items()},
            "residual_available": row["residual_available"], "conditions_available": row["conditions_available"],
            "original_matched_complete": complete, "no_declared_estimate_feature_failure": no_estimate_failure,
            "geometry_without_declared_estimate_failure": eligible,
            "current_endpoint_equal": equal, "endpoint_not_assessable_reason": reason, "complete_endpoint_cell": cell,
            "future_source_speed_failure": "speed_uses_future_source_sample" in codes,
            "geometry_with_only_future_source_speed_failure": bool(row["residual_available"] and codes == ["speed_uses_future_source_sample"]),
            "condition_failure_codes": list(codes)})
    clocks = {
        "edp_source": clock_summary((r["recording_id"], r.get("estimate_source_time_ns_decimal_private")) for r in rows),
        "reference_source": clock_summary((r["recording_id"], r.get("reference_source_time_ns_decimal_private")) for r in rows),
        "odometry_brackets": clock_summary((r["recording_id"], (r.get("speed_bracket_evidence") or {}).get(k))
            for r in rows for k in BRACKETS)}
    summary = {"outing_id": outing_id, "previously_examined_case": previously_examined,
        "retained_candidate_rows": len(rows), "geometry_available_rows": sum(r["residual_available"] for r in frames),
        "original_matched_complete_rows": sum(r["original_matched_complete"] for r in frames),
        "geometry_with_only_future_source_speed_failure": sum(r["geometry_with_only_future_source_speed_failure"] for r in frames),
        "other_rows": sum(not r["original_matched_complete"] and not r["geometry_with_only_future_source_speed_failure"] for r in frames),
        "all_assessable_complete_endpoint_table": all_table, "endpoint_not_assessable_counts": dict(unknown),
        "geometry_without_declared_estimate_failure_rows": sum(r["geometry_without_declared_estimate_failure"] for r in frames),
        "stratum_assessable_complete_endpoint_table": eligible_table, "stratum_not_assessable_counts": dict(eligible_unknown),
        "condition_failure_counts": dict(failures), "clock_observations": clocks, "original_matched_support": original_support}
    require(sum(all_table.values())+sum(unknown.values()) == len(rows), "mechanism_accounting_mismatch")
    require(sum(eligible_table.values())+sum(eligible_unknown.values()) == summary["geometry_without_declared_estimate_failure_rows"], "mechanism_accounting_mismatch")
    require(summary["original_matched_complete_rows"]+summary["geometry_with_only_future_source_speed_failure"]+summary["other_rows"] == len(rows), "mechanism_accounting_mismatch")
    return summary, frames
