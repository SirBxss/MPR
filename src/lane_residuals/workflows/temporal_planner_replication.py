"""Replicate the accepted temporal pilot on all frozen development outings."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

import numpy as np

from ..domain import temporal_planner_pilot as scoring, temporal_planner_replication as policy
from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as original
from ..io.temporal_planner_pilot import TemporalModels, accepted_spatial
from ..io.temporal_planner_replication import load_all_models, load_pilot
from ..modeling.matched_one_state_ar import MAX_SAMPLED_PADDED_FRAMES
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write
from .temporal_planner_pilot import assemble_arms, draw_arms

SCOPE = dict(raw_payload_opened=False, model_refitted=False, new_recordings_admitted=False,
             final_evaluation_authorized=False, planner_tuning_performed=False)


@dataclass(frozen=True)
class PreparedFold:
    evidence: dict
    held: object
    arrays: dict
    records: list[dict]
    training: np.ndarray
    models: TemporalModels


def prepare_folds(inputs, marker: dict, plan: dict, models: dict) -> list[PreparedFold]:
    """Check every cohort, clock, state, training pool and sampling bound first."""
    blocks = {b.outing_id: b for b in inputs.blocks}
    outings = sorted(blocks)
    folds = [entry["fold"] for entry in plan["folds"]]
    require(len(outings) == len(inputs.blocks) == policy.OUTING_COUNT
            and [f["validation_outing"] for f in folds] == outings and folds == marker["folds"]
            and plan["pilot_outing"] == outings[0], "temporal_replication_frozen_fold_set")
    prepared = []
    for expected in plan["folds"]:
        fold = expected["fold"]
        held = blocks[fold["validation_outing"]]
        require(fold["training_outings"] == [i for i in outings if i != held.outing_id]
                and 0 < len(held.y) <= 20_000 and len(held.archive.raw_sha256_by_recording) == 1,
                "temporal_replication_fold_partition_or_recording_support")
        rows, arrays, records, support = scoring.prepare(held, fold)
        require(support["eligible_sequences"] > 0, "temporal_replication_empty_primary_fold")
        padded = scoring.PROTOCOL["draws"] * len(held.offsets[:-1]) * int(np.diff(held.offsets).max())
        require(padded <= MAX_SAMPLED_PADDED_FRAMES, "temporal_replication_native_sampling_budget")
        model = models[fold["fold_id"]]
        training = np.concatenate([blocks[i].y for i in fold["training_outings"]])
        evidence = dict(fold=fold, expected_support=support, training_rows=len(training),
                        validation_archive_sha256=held.archive.summary_sha256,
                        saved_model_sha256=model.hashes,
                        scenario_rows_sha256=hashlib.sha256(original.encoded(rows)).hexdigest())
        require(evidence == expected and len(training) == model.gaussian.training_rows,
                "temporal_replication_reviewed_fold_evidence_mismatch")
        prepared.append(PreparedFold(evidence, held, arrays, records, training, model))
    return prepared


def run(*, project: Path, manifest_path: Path, manifest_pin: str, one_state_zip: Path,
        spatial_zip: Path, pilot_zip: Path, expected_tree: str, expected_runtime: str,
        output: Path, preflight_only: bool = False) -> tuple[dict, Path | None]:
    """Verify all inputs, reproduce the pilot, then score six new temporal folds."""
    project, manifest_path, one_state_zip, spatial_zip, pilot_zip, output = map(
        original.metadata_path, (project, manifest_path, one_state_zip, spatial_zip, pilot_zip, output))
    result = output.with_name(output.name + "_results.zip")
    partial = result.with_suffix(".zip.partial")
    source = source_guard(project, expected_tree, expected_runtime)
    plan, _ = original.pinned_json(manifest_path, manifest_pin)
    require(set(plan) == {"revision", "protocol", "original_experiment_directory", "original_experiment_sha256",
            "one_state_experiment_directory", "one_state_experiment_sha256", "one_state_result_sha256",
            "accepted_spatial_result_sha256", "accepted_spatial_tree", "accepted_pilot_result_sha256",
            "accepted_pilot_manifest_sha256", "pilot_source", "pilot_outing", "folds"}
            and plan["revision"] == policy.REVISION and plan["protocol"] == policy.PROTOCOL
            and len(plan["folds"]) == policy.OUTING_COUNT
            and set(plan["pilot_source"]) == {"consumer_git_commit", "consumer_git_tree",
                                              "consumer_runtime_source_sha256"},
            "temporal_replication_sealed_manifest_contract")
    folder = original.resolve(project, plan["original_experiment_directory"])
    one_folder = original.resolve(project, plan["one_state_experiment_directory"])
    inputs, marker = original.load_experiment(project, folder, plan["original_experiment_sha256"])
    # Validate exact fold identities before the model loader uses the selection.
    require([f["fold"] for f in plan["folds"]] == marker["folds"], "temporal_replication_frozen_fold_set")
    native, models = load_all_models(project, one_folder, plan, marker, one_state_zip)
    prepared = prepare_folds(inputs, marker, plan, models)
    accepted_spatial(spatial_zip, plan["accepted_spatial_result_sha256"], plan, marker, plan["folds"][0]["fold"])
    pilot = load_pilot(pilot_zip, plan["accepted_pilot_result_sha256"], plan)
    require(pilot.records == prepared[0].records, "temporal_replication_pilot_sequence_census")
    inputs.watched.update({manifest_path: manifest_pin, one_state_zip: plan["one_state_result_sha256"],
                           spatial_zip: plan["accepted_spatial_result_sha256"],
                           pilot_zip: plan["accepted_pilot_result_sha256"]})

    def unchanged():
        inputs.unchanged()
        native.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source, "temporal_replication_source_changed")

    protected = protected_inputs(project, inputs.request) + [folder, one_folder, *inputs.watched]
    protected += list(native.watched) + list(native.temporal_inputs.watched)
    for destination in (output, result, partial):
        require(not os.path.lexists(destination), "temporal_replication_new_output_required")
        registry.separate_output(destination, protected)
        require(not destination.is_relative_to(project) or destination.is_relative_to(project / "outputs/diagnostics/private"),
                "temporal_replication_output_requires_private_diagnostics")
        require(not any(os.path.lexists(parent / name) for parent in destination.parents for name in
                        ("experiment.json", "run_receipt.json", "replication_manifest.private.json",
                         "temporal_manifest.private.json", "pilot_report.private.json")),
                "temporal_replication_output_inside_prior_evidence")
    unchanged()
    receipt = dict(revision=policy.REVISION, source=source, manifest_sha256=manifest_pin,
                   fold_support=[f.evidence for f in prepared], **SCOPE)
    if preflight_only:
        return dict(receipt, status="verified_temporal_replication_inputs_no_scores"), None

    output.mkdir(parents=True, exist_ok=False)
    stage = "preserve_manifest"
    try:
        write(output / "replication_manifest.private.json", plan)
        for fold in prepared:
            write(output / (fold.held.outing_id + "_sequences.private.json"), fold.records)
        results = {}
        for index, fold in enumerate(prepared):
            outing = fold.held.outing_id
            stage = "sample_" + outing
            print("Sampling frozen temporal fold:", outing, flush=True)
            arms = draw_arms(fold.training, fold.held.x, fold.held.offsets, fold.models)
            stage = "score_" + outing
            scores = scoring.score(fold.arrays, fold.records, arms)
            write(output / (outing + "_scores.private.json"), dict(**fold.evidence, scores=scores))
            stage = "score_prefix_" + outing
            prefix = scoring.PROTOCOL["prefix_draws"]
            prefix_arms = assemble_arms(arms["nominal"], arms["empirical"][:prefix],
                                       arms["conditional_gaussian"][:prefix], arms["stationary_ar"][:prefix],
                                       arms["one_state_ar"][:prefix], fold.held.offsets)
            prefix_scores = scoring.score(fold.arrays, fold.records, prefix_arms)
            scored = dict(scores=scores, prefix_scores=prefix_scores)
            write(output / (outing + "_prefix_scores.private.json"), dict(prefix_draws=prefix, scores=prefix_scores))
            if index == 0:
                stage = "verify_pilot_parity"
                require(policy.scores_match(scores, pilot.scores)
                        and policy.scores_match(policy.aggregates(prefix_scores), pilot.report["prefix_scores"]),
                        "temporal_replication_pilot_parity_mismatch")
                print("Accepted pilot main and prefix score parity verified.", flush=True)
            stage = "diagnose_" + outing
            diagnostics = policy.diagnose(scores, prefix_scores, fold.records)
            write(output / (outing + "_diagnostics.private.json"), diagnostics)
            results[outing] = scored
            # Bound memory to the current fold's original rows and draw ensembles.
            del arms, prefix_arms
            unchanged()
        stage = "verify_and_aggregate"
        unchanged()
        report = dict(receipt, status="complete_development_temporal_replication", protocol=policy.PROTOCOL,
                      pilot_score_parity_verified=True, summary=policy.summarize_outings(results, plan["pilot_outing"]))
        stage = "publish_result"
        write(output / "replication_report.private.json", report)
        package(partial, [(output, "temporal_replication")])
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, result)
        registry._fsync_directory(result.parent)
    except BaseException as exc:
        write(output / "failure.private.json", dict(status="incomplete_preserve_temporal_replication_evidence",
              stage=stage, exception_type=type(exc).__name__, message=str(exc)))
        raise
    try:
        partial.unlink()
    except OSError:
        print("Published result; temporary duplicate link retained.", flush=True)
    return report, result
