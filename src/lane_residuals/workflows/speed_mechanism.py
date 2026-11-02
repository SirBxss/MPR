"""Repeatable cache-only mechanism tables; no changed data eligibility."""
from pathlib import Path

from ..domain.speed_mechanism import REVISION, TICK_NS, summarize
from ..io.speed_mechanism import load
from ..io.artifact_registry import separate_output
from ..io.private_reports import write_csv, write_json


def run(project, request, request_sha256, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FileExistsError("mechanism_fresh_output_directory_required")
    separate_output(output)
    loaded = load(project, request, request_sha256)
    separate_output(output, loaded["protected_output_roots"])
    outings, frames = [], []
    for item in loaded["outings"]:
        summary, rows = summarize(item["outing_id"], item["rows"], item["original_support"], item["previously_examined"])
        summary["audit_sha256"] = item["audit_sha256"]
        outings.append(summary); frames.extend(rows)
    report = {"revision": REVISION, "status": "started_cached_speed_mechanism_audit", "tick_ns": TICK_NS,
        **{k: loaded[k] for k in ("request_sha256", "experiment_sha256", "cohort_sha256", "registry_sha256", "provenance")},
        "outings": outings, "outing_count": len(outings), "retained_candidate_rows": len(frames),
        "original_matched_complete_rows": sum(o["original_matched_complete_rows"] for o in outings),
        "hypothesis_origin": "fixed_from_previously_examined_case_then_checked_on_already_exposed_development_audits",
        "independent_final_or_model_validation": False, "raw_recording_opened": False,
        "direct_velocity_rule_evaluated": False, "new_training_arrays_exported": False,
        "training_dataset_modified": False, "speed_feature_adopted": False, "model_fitted": False,
        "physical_causal_availability_proven": False, "cohort_wide_temporal_recovery_established": False,
        "interpretation": "Observed old endpoint/failure and clock structure only. Missing brackets stay unknown. No direct-speed recovery, new eligibility, clock identity or physical availability follows."}
    output.mkdir()
    try:
        write_json(output/"report.private.json", report)
        write_csv(output/"candidate_mechanism.private.csv", frames)
        columns = ("outing_id", "previously_examined_case", "retained_candidate_rows", "geometry_available_rows",
            "original_matched_complete_rows", "geometry_with_only_future_source_speed_failure", "other_rows")
        write_csv(output/"outing_summary.private.csv", [{**{k:o[k] for k in columns},
            **o["stratum_assessable_complete_endpoint_table"],
            "stratum_not_assessable": sum(o["stratum_not_assessable_counts"].values()),
            "original_maximum_complete_span_s": o["original_matched_support"]["maximum_complete_sequence_duration_ns"]/1e9} for o in outings])
        write_csv(output/"clock_structure.private.csv", [{"outing_id": o["outing_id"], "clock": key, **value}
            for o in outings for key, value in o["clock_observations"].items()])
        from ..reporting.speed_mechanism import plot
        plot(output, report)
        loaded["unchanged"]()
        report["status"] = "complete_cached_speed_mechanism_audit"
    except BaseException as error:
        report.update(status="incomplete_cached_speed_mechanism_audit", failure_class=type(error).__name__)
        raise
    finally:
        write_json(output/"report.private.json", report)
    return report
