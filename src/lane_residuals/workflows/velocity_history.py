"""Repeatable cached analysis; no raw-operation claim or training authorization."""
from pathlib import Path

from ..domain.velocity_history import REVISION, summarize
from ..domain.velocity_timing import TOPICS
from ..io.velocity_history import load_return
from .velocity_timing_pilot import write_json, write_csv


def run(archive, archive_sha256, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FileExistsError("history_new_output_directory_required")
    cached = load_return(archive, archive_sha256)
    analysis, screens = summarize(cached["records"], cached["targets"])
    baseline = {(r["topic"], r["candidate_index"]): r for r in cached["original_frames"]}
    for row in screens:
        previous = baseline[(row["topic"], row["candidate_index"])]
        row["approved_latest_log_screen_met"] = previous["recorded_clock_screen_met"]
        row["approved_latest_log_hypothetical_complete"] = previous["local_hypothetical_complete"]
        row["approved_latest_log_source_age_ns"] = previous["source_age_ns"]
    report = {"revision": REVISION, "status": "started_cached_analysis", "analysis": analysis,
        "input_archive_sha256": cached["input_archive_sha256"], "input_member_sha256": cached["input_member_sha256"],
        "input_provenance": cached["provenance"], "original_analysis_replayed": True,
        "window_start_log_ns": cached["request"]["window_start_log_ns"], "window_end_log_ns": cached["request"]["window_end_log_ns"],
        "original_complete": cached["original_analysis"]["local_original_complete"],
        "geometry_only": cached["original_analysis"]["local_geometry_only"],
        "approved_latest_log": {t: cached["original_analysis"]["topics"][t]["local_hypothetical_complete_under_screen"] for t in TOPICS},
        "raw_recording_opened": False, "new_raw_payload_decoded": False, "new_training_arrays_exported": False,
        "training_dataset_modified": False, "model_fitted": False, "speed_feature_adopted": False,
        "semantic_evidence_still_needed": ["longitudinal units/sign/reference point", "producer timestamp and clock domain",
            "measurement age versus interface creation", "actual EDP consumer input availability", "independent development-window validation"],
        "interpretation": "Post-hoc hypothesis on the same fixed cached development window. No cohort recovery, physical availability, feature adoption or model claim follows."}
    output.mkdir()
    try:
        write_json(output/"report.private.json", report)
        write_csv(output/"history_frames.private.csv", screens)
        support = [{"selection": "original_complete", "topic": "both", **report["original_complete"]}]
        for topic in TOPICS:
            support.extend([{"selection": "approved_latest_log", "topic": topic, **report["approved_latest_log"][topic]},
                {"selection": "post_hoc_strict_prior_log", "topic": topic, **analysis["topics"][topic]["local_hypothetical_complete_under_screen"]}])
        write_csv(output/"support_comparison.private.csv", support)
        from ..reporting.velocity_history import plot
        plot(output, screens, report)
        report["status"] = "complete_cached_history_diagnostic"
    except BaseException as error:
        report.update(status="incomplete_cached_analysis", failure_class=type(error).__name__)
        raise
    finally:
        write_json(output/"report.private.json", report)
    return report
