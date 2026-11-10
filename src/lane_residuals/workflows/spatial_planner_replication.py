"""Replicate the accepted spatial pilot on the frozen development folds."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

import numpy as np

from ..domain import cached_planner_scenarios as scenarios
from ..domain.artifact_registry import require
from ..domain.spatial_planner_pilot import REVISION as PILOT_REVISION, score_spatial_pilot, spatial_speed_support
from ..domain.spatial_planner_replication import OUTING_COUNT, PROTOCOL, REVISION, scores_match, summarize_outings
from ..io import artifact_registry as registry, development_experiment as original
from ..io.spatial_planner_pilot import SavedSpatialModels, load_pilot_report, load_saved_models, load_scenarios
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write
from .spatial_planner_pilot import draw_arms

SCOPE = dict(raw_payload_opened=False, model_refitted=False, speed_feature_replaced=False,
             final_evaluation_authorized=False, new_recordings_admitted=False)


@dataclass(frozen=True)
class PreparedFold:
    evidence: dict
    support: dict
    rows: list[dict]
    arrays: dict
    training: np.ndarray
    models: SavedSpatialModels


def _prepare_folds(inputs, marker: dict, plan: dict, scenario_zip: Path, flow_zip: Path) -> list[PreparedFold]:
    blocks = {block.outing_id: block for block in inputs.blocks}
    folds = [entry["fold"] for entry in plan["folds"]]
    outings = sorted(blocks)
    require(len(outings) == len(inputs.blocks) == OUTING_COUNT
            and [fold["validation_outing"] for fold in folds] == outings and folds == marker["folds"]
            and plan["pilot_outing"] == outings[0], "spatial_replication_frozen_fold_set")
    prepared = []
    for expected in plan["folds"]:
        fold = expected["fold"]
        outing = fold["validation_outing"]
        held = blocks[outing]
        require(fold["training_outings"] == [i for i in outings if i != outing]
                and 0 < len(held.y) <= 20_000 and len(held.archive.raw_sha256_by_recording) == 1,
                "spatial_replication_fold_partition_or_recording_support")
        if outing == plan["pilot_outing"]:
            rows, arrays = load_scenarios(scenario_zip, plan["scenario_zip_sha256"], marker, fold, held)
        else:
            rows, arrays, _ = scenarios.prepare_scenario_rows(held, fold)
        _, common = spatial_speed_support(arrays)
        archive_pin = held.archive.summary_sha256
        models = load_saved_models(flow_zip, plan["flow_result_zip_sha256"], marker, fold, archive_pin)
        training = np.concatenate([blocks[i].y for i in fold["training_outings"]])
        evidence = {
            "fold": fold,
            "validation_archive_sha256": archive_pin,
            "saved_model_and_solver_sha256": models.hashes,
            "training_rows": len(training),
            "held_geometry_rows": len(held.archive.arrays["residuals_m"]),
            "held_complete_feature_rows": len(rows),
            "held_sequences": len(held.offsets) - 1,
        }
        require(evidence == expected and len(training) == models.gaussian.training_rows == models.flow.training_rows,
                "spatial_replication_reviewed_fold_evidence_mismatch")
        support = {
            "scenario_rows_sha256": hashlib.sha256(original.encoded(rows)).hexdigest(),
            "primary_rows": int(arrays["eligible"].sum()),
            "common_speed_rows": int(common.sum()),
        }
        prepared.append(PreparedFold(evidence, support, rows, arrays, training, models))
    return prepared


def _check_pilot(pilot: dict, plan: dict, prepared: PreparedFold) -> None:
    require(pilot["status"] == "complete_recorded_spatial_planner_pilot"
            and pilot["revision"] == PILOT_REVISION and pilot["protocol"] == PROTOCOL["scoring"]
            and all(pilot[key] is False for key in SCOPE)
            and all(pilot[key] == plan[key] for key in
                    ("original_experiment_sha256", "scenario_zip_sha256", "flow_result_zip_sha256"))
            and {key: pilot["source"][key] for key in plan["pilot_source"]} == plan["pilot_source"]
            and all(pilot[key] == value for key, value in prepared.evidence.items()
                    if key != "validation_archive_sha256"),
            "spatial_replication_accepted_pilot_lineage")


def run(*, project: Path, experiment_directory: Path, manifest_path: Path, manifest_sha256: str,
        scenario_zip: Path, flow_zip: Path, pilot_zip: Path, expected_tree: str, expected_runtime: str,
        output: Path, preflight_only: bool = False) -> tuple[dict, Path | None]:
    """Verify every frozen fold before scoring or publishing aggregate evidence."""
    project = original.metadata_path(project)
    folder = original.resolve(project, str(experiment_directory))
    manifest_path, scenario_zip, flow_zip, pilot_zip, output = map(
        original.metadata_path, (manifest_path, scenario_zip, flow_zip, pilot_zip, output)
    )
    result = output.with_name(output.name + "_results.zip")
    partial = result.with_suffix(".zip.partial")
    source = source_guard(project, expected_tree, expected_runtime)
    plan, _ = original.pinned_json(manifest_path, manifest_sha256)
    require(set(plan) == {"revision", "protocol", "planner_protocol", "folds", "pilot_outing", "pilot_source",
                          "original_experiment_sha256", "scenario_zip_sha256", "flow_result_zip_sha256",
                          "accepted_pilot_zip_sha256"}
            and plan["revision"] == REVISION and plan["protocol"] == PROTOCOL
            and plan["planner_protocol"] == scenarios.PROTOCOL
            and len(plan["folds"]) == OUTING_COUNT
            and set(plan["pilot_source"]) == {"consumer_git_commit", "consumer_git_tree",
                                             "consumer_runtime_source_sha256"},
            "spatial_replication_manifest_contract")
    inputs, marker = original.load_experiment(project, folder, plan["original_experiment_sha256"])
    watched = {
        manifest_path: manifest_sha256,
        scenario_zip: plan["scenario_zip_sha256"],
        flow_zip: plan["flow_result_zip_sha256"],
        pilot_zip: plan["accepted_pilot_zip_sha256"],
    }
    protected = protected_inputs(project, inputs.request) + [folder, *inputs.watched, *watched]
    for destination in (output, result, partial):
        require(not os.path.lexists(destination), "spatial_replication_new_output_required")
        registry.separate_output(destination, protected)
        require(not destination.is_relative_to(project)
                or destination.is_relative_to(project / "outputs/diagnostics/private"),
                "spatial_replication_output_inside_project_requires_private_diagnostics")
        require(not any(os.path.lexists(parent / name) for parent in destination.parents
                        for name in ("experiment.json", "run_receipt.json", "scenario_manifest.private.json",
                                     "pilot_report.private.json", "replication_manifest.private.json")),
                "spatial_replication_output_inside_prior_evidence")
    prepared = _prepare_folds(inputs, marker, plan, scenario_zip, flow_zip)
    pilot = load_pilot_report(pilot_zip, plan["accepted_pilot_zip_sha256"])
    _check_pilot(pilot, plan, prepared[0])
    inputs.watched.update(watched)
    inputs.unchanged()
    require(source_guard(project, expected_tree, expected_runtime) == source, "spatial_replication_source_changed")
    receipt = {
        "revision": REVISION, "manifest_sha256": manifest_sha256, "source": source, **SCOPE,
        "fold_support": [{**fold.evidence, **fold.support} for fold in prepared],
    }
    if preflight_only:
        return {**receipt, "status": "verified_replication_inputs_no_scores"}, None

    output.mkdir(parents=True, exist_ok=False)
    stage = "write_reviewed_plan"
    try:
        write(output / "replication_manifest.private.json", plan)
        scores = {}
        for fold in prepared:
            outing = fold.evidence["fold"]["validation_outing"]
            stage = "score_" + outing
            print("Scoring frozen development fold:", outing, flush=True)
            scored = score_spatial_pilot(fold.arrays, fold.rows, draw_arms(fold.training, fold.models))
            require(scored["primary"]["rows"] == fold.support["primary_rows"]
                    and all(v["rows"] == fold.support["common_speed_rows"]
                            for v in scored["speed_sensitivity"].values()),
                    "spatial_replication_scored_support_mismatch")
            write(output / (outing + "_scores.private.json"), {**fold.evidence, **fold.support, "scores": scored})
            if outing == plan["pilot_outing"]:
                require(scores_match(scored, pilot["scores"]), "spatial_replication_pilot_parity_mismatch")
            scores[outing] = scored
        stage = "verify_inputs_and_aggregate"
        inputs.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source, "spatial_replication_source_changed")
        report = {
            **receipt,
            "status": "complete_development_spatial_replication",
            "pilot_score_parity_verified": True,
            "summary": summarize_outings(scores, plan["pilot_outing"]),
        }
        stage = "publish_result"
        write(output / "replication_report.private.json", report)
        package(partial, [(output, "replication")])
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, result)
        registry._fsync_directory(result.parent)
    except BaseException as exc:
        write(output / "failure.private.json", {
            "status": "incomplete_preserve_replication_evidence", "stage": stage,
            "exception_type": type(exc).__name__, "message": str(exc),
        })
        raise
    try:
        partial.unlink()
    except OSError:
        print("Published result; temporary duplicate link retained.", flush=True)
    return report, result
