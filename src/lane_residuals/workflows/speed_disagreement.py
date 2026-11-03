"""Cached diagnostic only; no raw workflow, model, feature or population export."""
from pathlib import Path

from ..domain.speed_disagreement import REVISION, summarize
from ..io.artifact_registry import separate_output
from ..io.private_reports import write_csv, write_json
from ..io.speed_disagreement import load_return


def run(archive, archive_sha256, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FileExistsError("disagreement_fresh_output_required")
    separate_output(output,(Path(archive).absolute(),))
    cached = load_return(archive,archive_sha256)
    cases,rows,groups = [],[],[]
    for case in cached["cases"]:
        analysis,frames = summarize(case["targets"],case["frames"])
        cases.append({"outing_id":case["outing_id"],"analysis":analysis,
            "original_support_and_rules":case["original_analysis"]})
        rows.extend({"outing_id":case["outing_id"],**r} for r in frames)
        groups.extend({"outing_id":case["outing_id"],**g} for g in analysis["groups"])
    report = {"revision":REVISION,"status":"started_cached_speed_disagreement","cases":cases,
        "input_archive_sha256":cached["input_sha256"],"input_member_sha256":cached["input_member_sha256"],
        "archived_source":cached["source"],"input_provenance":cached["input_provenance"],
        "original_selector_and_saved_frames_replayed":True,"post_hoc_on_exposed_windows":True,
        "raw_recording_opened":False,"new_training_arrays_exported":False,"model_fitted":False,
        "feature_or_population_adopted":False,"cause_identified":False,"physical_availability_proven":False}
    output.mkdir()
    try:
        write_json(output/"report.private.json",report)
        write_csv(output/"bracket_comparison.private.csv",rows)
        write_csv(output/"group_comparison.private.csv",groups)
        from ..reporting.speed_disagreement import plot
        plot(output,rows)
        report["status"] = "complete_cached_speed_disagreement"
    except BaseException as error:
        report.update(status="incomplete_cached_speed_disagreement",failure_class=type(error).__name__)
        raise
    finally:
        write_json(output/"report.private.json",report)
    return report
