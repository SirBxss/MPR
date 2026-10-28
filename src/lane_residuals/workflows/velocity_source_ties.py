"""Bounded cached paired audit; no raw path, feature export or fit operation."""
from pathlib import Path

from ..domain.velocity_source_ties import REVISION, summarize
from ..domain.velocity_timing import TOPICS
from ..io.velocity_history import load_return
from .velocity_timing_pilot import write_csv, write_json


def run(archive, archive_sha256, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FileExistsError("source_ties_new_output_directory_required")
    cached = load_return(archive, archive_sha256)
    analysis, screens = summarize(cached["records"], cached["targets"])
    baseline = {(r["topic"], r["candidate_index"]): r for r in cached["original_frames"]}
    for row in screens:
        previous = baseline[(row["topic"], row["candidate_index"])]
        row["approved_latest_log_hypothetical_complete"] = previous["local_hypothetical_complete"]
    support = [{"selection": "original_complete", "topic": "both", **cached["original_analysis"]["local_original_complete"]}]
    for topic in TOPICS:
        support.append({"selection": "approved_latest_log", "topic": topic,
            **cached["original_analysis"]["topics"][topic]["local_hypothetical_complete_under_screen"]})
        for key in ("primary_source_at_or_before", "secondary_source_strictly_before"):
            support.append({"selection": key, "topic": topic,
                **analysis["topics"][topic][key]["local_hypothetical_complete_under_screen"]})
    report = {
        "revision": REVISION, "status": "started_cached_source_tie_audit", "analysis": analysis,
        "input_archive_sha256": cached["input_archive_sha256"], "input_member_sha256": cached["input_member_sha256"],
        "input_provenance": cached["provenance"], "original_analysis_replayed": True,
        "window_start_log_ns": cached["request"]["window_start_log_ns"],
        "window_end_log_ns": cached["request"]["window_end_log_ns"],
        "support_comparison": support,
        "raw_recording_opened": False, "new_raw_payload_decoded": False,
        "new_training_arrays_exported": False, "training_dataset_modified": False,
        "model_fitted": False, "speed_feature_adopted": False,
        "interpretation": "Paired post-hoc sensitivity on one exposed cached development window. No producer, physical availability, independent validation or training admission follows.",
    }
    output.mkdir()
    try:
        write_json(output/"report.private.json", report)
        write_csv(output/"paired_frames.private.csv", screens)
        write_csv(output/"support_comparison.private.csv", support)
        from ..reporting.velocity_source_ties import plot
        plot(output, screens, report)
        report["status"] = "complete_cached_source_tie_audit"
    except BaseException as error:
        report.update(status="incomplete_cached_source_tie_audit", failure_class=type(error).__name__)
        raise
    finally:
        write_json(output/"report.private.json", report)
    return report
