"""Bounded readers for the accepted temporal pilot and frozen fold states."""

from dataclasses import dataclass
from pathlib import Path

from ..domain.artifact_registry import require
from ..domain import temporal_planner_pilot as pilot
from ..domain.temporal_planner_replication import aggregates, scores_match, validate_scores
from . import artifact_registry as registry
from .spatial_planner_pilot import _pinned_bytes, _verified_zip
from .temporal_planner_pilot import load_models, restore_models


@dataclass(frozen=True)
class AcceptedPilot:
    report: dict
    scores: dict
    records: list[dict]
    manifest: dict


def load_pilot(path: Path, pin: str, plan: dict) -> AcceptedPilot:
    """Bind the complete accepted return to the sealed producer and input pins."""
    expected = {"temporal/" + name for name in ("temporal_report.private.json", "scores.private.json",
                                               "sequences.private.json", "temporal_manifest.private.json")}
    with _verified_zip(_pinned_bytes(path, pin)) as (archive, sums):
        require(set(sums) == expected and sums["temporal/temporal_manifest.private.json"] ==
                plan["accepted_pilot_manifest_sha256"], "temporal_replication_pilot_member_set_or_manifest")
        read = lambda name: registry.decode(archive.read("temporal/" + name))
        report, manifest = read("temporal_report.private.json"), read("temporal_manifest.private.json")
        scores, records = read("scores.private.json"), read("sequences.private.json")
    first = plan["folds"][0]
    require(report["status"] == "complete_short_temporal_planner_pilot"
            and report["revision"] == manifest["revision"] == pilot.REVISION
            and report["protocol"] == manifest["protocol"] == pilot.PROTOCOL
            and {k: report["source"][k] for k in plan["pilot_source"]} == plan["pilot_source"]
            and report["manifest_sha256"] == plan["accepted_pilot_manifest_sha256"]
            and report["fold"] == manifest["fold"] == first["fold"]
            and report["support"] == manifest["expected_support"] == first["expected_support"]
            and report["saved_model_sha256"] == manifest["saved_model_sha256"] == first["saved_model_sha256"]
            and report["scenario_rows_sha256"] == manifest["scenario_rows_sha256"] == first["scenario_rows_sha256"]
            and report["training_rows"] == first["training_rows"]
            and all(report[k] is False for k in ("raw_payload_opened", "model_refitted",
                                                "new_recordings_admitted", "final_evaluation_authorized"))
            and all(manifest[k] == plan[k] for k in ("original_experiment_directory", "original_experiment_sha256",
                "one_state_experiment_directory", "one_state_experiment_sha256", "one_state_result_sha256",
                "accepted_spatial_result_sha256", "accepted_spatial_tree")),
            "temporal_replication_accepted_pilot_lineage")
    validate_scores(scores, records)
    require(scores_match(aggregates(scores), report["scores"]), "temporal_replication_pilot_score_binding")
    return AcceptedPilot(report, scores, records, manifest)


def load_all_models(project: Path, directory: Path, plan: dict, marker: dict, result_zip: Path):
    """Replay native predecessor evidence once, then restore every verified fold."""
    folds = [f["fold"] for f in plan["folds"]]
    inputs, first = load_models(project, directory, plan["one_state_experiment_sha256"],
                               result_zip, plan["one_state_result_sha256"], marker, folds[0])
    raw = _pinned_bytes(result_zip, plan["one_state_result_sha256"])
    models = {folds[0]["fold_id"]: first}
    for fold in folds[1:]:
        gaussian, pin = inputs.temporal_inputs.states[fold["fold_id"]]["conditional_gaussian"]
        models[fold["fold_id"]] = restore_models(raw, inputs.stationary_raw, fold, gaussian, pin)
    return inputs, models
