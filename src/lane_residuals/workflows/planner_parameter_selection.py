"""Select planner settings on training forecasts before held residual replay."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Callable

import numpy as np

from ..domain import planner_parameter_selection as policy, temporal_planner_pilot as temporal
from ..domain.planner_parameter_design import design_diagnostics
from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as original
from ..io.planner_parameter_selection import FrozenFamily, accepted_temporal, load_families
from ..modeling.matched_flow import CONFIGURATION as FLOW_LIMITS, sample_matched_flow
from ..modeling.matched_one_state_ar import MAX_SAMPLED_PADDED_FRAMES
from .development_experiment import protected_inputs, source_guard
from .locked_development_export import package, write

SCOPE = dict(raw_payload_opened=False, model_refitted=False, new_recordings_admitted=False,
             final_evaluation_authorized=False, planner_parameters_adopted=False)


@dataclass(frozen=True)
class PreparedFold:
    evidence: dict
    family: FrozenFamily
    conditions: np.ndarray
    speeds: np.ndarray
    offsets: np.ndarray
    context_records: list[dict]
    training_pool: np.ndarray
    held_arrays: dict
    held_records: list[dict]


def sample_arms(training_pool: np.ndarray, conditions: np.ndarray, offsets: np.ndarray,
                family: FrozenFamily, checkpoint: Callable | None = None) -> dict[str, np.ndarray]:
    """Generate each law once; held residuals are absent from this interface."""
    count, seed = policy.PROTOCOL["draws"], policy.PROTOCOL["seed"]
    result = {}
    def add(name: str, values: np.ndarray):
        require(values.shape == (1 if name == "zero_disturbance" else count, len(conditions), 21)
                and np.isfinite(values).all(), "parameter_selection_finite_draws")
        result[name] = values
        if checkpoint is not None:
            checkpoint(name, values)
    add("zero_disturbance", np.zeros((1, len(conditions), 21)))
    add("empirical", training_pool[np.random.default_rng(seed).integers(len(training_pool), size=(count, len(conditions)))])
    add("unconditional_gaussian", family.unconditional.sample(conditions, sample_count=count, seed=seed))
    add("conditional_gaussian", family.temporal.gaussian.sample(conditions, sample_count=count, seed=seed))
    add("stationary_ar", family.temporal.stationary.sample(conditions, offsets, sample_count=count, seed=seed))
    add("one_state_ar", family.temporal.one_state.sample(conditions, offsets, sample_count=count, seed=seed))
    for mode in ("unconditional", "conditional"):
        add(mode+"_flow", sample_matched_flow(family.flows[mode], conditions, offsets,
            sample_count=count, seed=seed, steps=policy.PROTOCOL["flow_steps"], solver=policy.PROTOCOL["flow_solver"]))
    require(tuple(result) == policy.ARMS, "parameter_selection_fixed_sampler_order")
    return result


def prepare_folds(inputs, marker: dict, plan: dict, checkpoint: dict, families: dict) -> list[PreparedFold]:
    """Seal every training context and held sequence from original metadata only."""
    blocks = {b.outing_id: b for b in inputs.blocks}
    ids = sorted(blocks)
    require(len(ids) == len(inputs.blocks) == 7
            and [f["fold"] for f in plan["folds"]] == marker["folds"]
            and [f["validation_outing"] for f in marker["folds"]] == ids,
            "parameter_selection_complete_original_fold_set")
    old_by_id = {f["fold"]["validation_outing"]: f for f in checkpoint["folds"]}
    arrays, records, supports = {}, {}, {}
    for fold in marker["folds"]:
        oid = fold["validation_outing"]
        block = blocks[oid]
        require(len(block.archive.raw_sha256_by_recording) == 1 and 0 < len(block.y) <= 20_000
                and fold["training_outings"] == [i for i in ids if i != oid], "parameter_selection_original_partition")
        rows, arrays[oid], records[oid], supports[oid] = temporal.prepare(block, fold)
        old = old_by_id[oid]
        require(supports[oid] == old["expected_support"]
                and hashlib.sha256(original.encoded(rows)).hexdigest() == old["scenario_rows_sha256"]
                and block.archive.summary_sha256 == plan["folds"][ids.index(oid)]["validation_archive_sha256"],
                "parameter_selection_original_rows_or_clocks_changed")
    prepared = []
    for expected in plan["folds"]:
        fold = expected["fold"]
        oid = fold["validation_outing"]
        descriptors = policy.context_descriptors(records, fold["training_outings"])
        x = np.concatenate([blocks[d["outing_id"]].x[d["original_start_row"]:d["original_stop_row"]] for d in descriptors])
        offsets = np.array([0]+[d["stop_row"] for d in descriptors], dtype=np.int64)
        require(len(x) == offsets[-1] and policy.PROTOCOL["draws"]*len(descriptors)*int(np.diff(offsets).max())
                <= MAX_SAMPLED_PADDED_FRAMES and policy.PROTOCOL["draws"]*len(x)*21 <= FLOW_LIMITS["maximum_sample_values"]
                and len(x) <= FLOW_LIMITS["maximum_rows"] and len(descriptors) <= FLOW_LIMITS["maximum_sequences"]
                and int(np.diff(offsets).max()) <= FLOW_LIMITS["maximum_sequence_length"],
                "parameter_selection_native_sampling_budget")
        kept = [r for r in records[oid] if r["status"] == "eligible" and r["frame_count"] >= 3]
        require(bool(kept), "parameter_selection_empty_held_support")
        family = families[fold["fold_id"]]
        pool = np.concatenate([blocks[i].y for i in fold["training_outings"]])
        evidence = dict(fold=fold, saved_model_sha256=family.hashes,
            validation_archive_sha256=blocks[oid].archive.summary_sha256, original_support=supports[oid],
            training_contexts=descriptors, selection_frame_count=len(x), training_pool_rows=len(pool),
            held_sequence_indices=[r["sequence_index"] for r in kept],
            held_frame_count=sum(r["frame_count"] for r in kept),
            held_transition_count=sum(r["frame_count"]-1 for r in kept))
        require(evidence == expected and len(pool) == family.temporal.gaussian.training_rows,
                "parameter_selection_sealed_fold_evidence")
        prepared.append(PreparedFold(evidence, family, x, x[:, 0].copy(), offsets, descriptors,
                                     pool, arrays[oid], kept))
    return prepared


def run(*, project: Path, manifest_path: Path, manifest_pin: str, flow_zip: Path, temporal_zip: Path,
        expected_tree: str, expected_runtime: str, output: Path, preflight_only: bool = False, design_only: bool = False) -> tuple[dict, Path | None]:
    """Preflight all folds, write all choices, then evaluate the fixed held grid."""
    require(not (preflight_only and design_only), "parameter_selection_modes_exclusive")
    project, manifest_path, flow_zip, temporal_zip, output = map(
        original.metadata_path, (project, manifest_path, flow_zip, temporal_zip, output))
    result, partial = (output.with_name(output.name+suffix) for suffix in ("_results.zip", "_results.zip.partial"))
    source = source_guard(project, expected_tree, expected_runtime)
    plan, _ = original.pinned_json(manifest_path, manifest_pin)
    require(set(plan) == {"revision", "protocol", "flow_experiment_directory", "flow_experiment_sha256",
                         "flow_result_sha256", "accepted_temporal_result_sha256", "accepted_temporal_manifest_sha256",
                         "accepted_temporal_source", "folds"}
            and plan["revision"] == policy.REVISION and plan["protocol"] == policy.PROTOCOL
            and len(plan["folds"]) == 7
            and set(plan["accepted_temporal_source"]) == {"consumer_git_commit", "consumer_git_tree", "consumer_runtime_source_sha256"},
            "parameter_selection_sealed_manifest_contract")
    folder = original.resolve(project, plan["flow_experiment_directory"])
    native, flow_marker, marker, families = load_families(project, folder, plan["flow_experiment_sha256"],
                                                        flow_zip, plan["flow_result_sha256"])
    checkpoint = accepted_temporal(temporal_zip, plan["accepted_temporal_result_sha256"], plan, flow_marker, marker, families)
    inputs = native.one_state_inputs.temporal_inputs.previous_inputs
    prepared = prepare_folds(inputs, marker, plan, checkpoint, families)
    native.watched.update({manifest_path: manifest_pin, flow_zip: plan["flow_result_sha256"],
                           temporal_zip: plan["accepted_temporal_result_sha256"]})

    def unchanged():
        native.unchanged()
        require(source_guard(project, expected_tree, expected_runtime) == source, "parameter_selection_source_changed")

    layers = (native, native.one_state_inputs, native.one_state_inputs.temporal_inputs, inputs)
    watched = [p for layer in layers for p in layer.watched]
    protected = protected_inputs(project, inputs.request) + [folder, *watched]
    protected += [p.parent for p in watched if p.name in ("experiment.json", "request.json", "numeric_export.json")]
    for path in (output, result, partial):
        require(not os.path.lexists(path), "parameter_selection_new_output_required")
        registry.separate_output(path, protected)
        require(not path.is_relative_to(project) or path.is_relative_to(project/"outputs/diagnostics/private"),
                "parameter_selection_output_requires_private_diagnostics")
        require(not any(os.path.lexists(parent/name) for parent in path.parents for name in
            ("experiment.json", "run_receipt.json", "replication_manifest.private.json", "temporal_manifest.private.json",
             "selection_manifest.private.json", "scenario_manifest.private.json", "registry.json", "cohort_manifest.json")),
            "parameter_selection_output_inside_prior_evidence")
    unchanged()
    receipt = dict(revision=policy.REVISION, manifest_sha256=manifest_pin, source=source,
                   fold_evidence=[f.evidence for f in prepared], **SCOPE)
    if preflight_only:
        return dict(receipt, status="verified_parameter_selection_inputs_no_sampling_or_scores"), None
    def publish():
        """Publish either a bounded design result or the completed held study."""
        package(partial, [(output, "parameter_selection")])
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, result)
        registry._fsync_directory(result.parent)
        try:
            partial.unlink()
        except OSError:
            print("Published result; temporary duplicate link retained.", flush=True)

    output.mkdir(parents=True, exist_ok=False)
    stage = "preserve_manifest"
    try:
        write(output/"selection_manifest.private.json", plan)
        stage = "synthetic_native_engineering_screen"
        write(output/"engineering_check.private.json", policy.engineering_screen())
        designs = {}
        # The complete metadata design barrier precedes every learned-model draw.
        for fold in prepared:
            oid = fold.evidence["fold"]["validation_outing"]
            stage = "training_metadata_design_"+oid
            print("Checking training-only decision design for held outing:", oid, flush=True)
            designs[oid] = design_diagnostics(fold.speeds,fold.context_records)
            write(output/(oid+"_design.private.json"),designs[oid])
            unchanged()
        ready = all(d["informative"] for d in designs.values())
        design_report = dict(receipt,status="complete_parameter_selection_design_ready" if ready else
            "complete_parameter_selection_design_not_informative",design_ready=ready,
            all_designs_completed_before_model_sampling=True,model_sampling_performed=False,held_scoring_performed=False,
            design_by_outing={oid:dict(informative=d["informative"],reasons=d["reasons"],
                primary=d["settings"]["gate_0.20"]) for oid,d in designs.items()})
        write(output/"design_report.private.json",design_report)
        if design_only or not ready:
            unchanged()
            stage = "publish_design_result"
            publish()
            return design_report,result
        selections = {}
        # No held response is scored anywhere in this first loop.
        for fold in prepared:
            oid = fold.evidence["fold"]["validation_outing"]
            stage = "sample_training_contexts_"+oid
            print("Selecting on training contexts for held outing:", oid, flush=True)
            def save_draw(name: str, values: np.ndarray):
                write(output/(oid+"_sampling_"+name+".private.json"), dict(
                    arm=name, seed=policy.PROTOCOL["seed"], shape=list(values.shape),
                    draw_array_sha256=hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()))
            arms = sample_arms(fold.training_pool, fold.conditions, fold.offsets, fold.family, save_draw)
            stage = "forecast_grid_"+oid
            grid = policy.grid_costs(arms, fold.speeds, fold.context_records)
            stage = "freeze_choices_"+oid
            selection = policy.select_parameters(grid, [d["outing_id"] for d in fold.context_records])
            write(output/(oid+"_selection.private.json"), selection)
            selections[oid] = selection
            del arms, grid
            unchanged()
        write(output/"choices_frozen.private.json", dict(held_scoring_started=False,
            selection_file_sha256={oid: original.sha(output/(oid+"_selection.private.json")) for oid in selections}))
        comparisons = {}
        for fold in prepared:
            oid = fold.evidence["fold"]["validation_outing"]
            stage = "held_residual_replay_"+oid
            print("Evaluating fixed choices on held residual replay:", oid, flush=True)
            held = policy.evaluate_held(fold.held_arrays["residuals_m"], fold.held_arrays["speed_mps"], fold.held_records)
            write(output/(oid+"_held_scores.private.json"), held)
            comparisons[oid] = policy.compare_choices(selections[oid], held)
            write(output/(oid+"_comparison.private.json"), comparisons[oid])
            unchanged()
        stage = "verify_choices_and_aggregate"
        frozen = registry.decode((output/"choices_frozen.private.json").read_bytes())
        require(all(original.sha(output/(oid+"_selection.private.json")) == pin
                    for oid, pin in frozen["selection_file_sha256"].items()), "parameter_selection_choices_changed")
        unchanged()
        report = dict(receipt, status="complete_development_parameter_selection", protocol=policy.PROTOCOL,
                      all_choices_frozen_before_held_scoring=True,model_sampling_performed=True,held_scoring_performed=True,
                      design_ready=True,summary=policy.summarize(comparisons))
        write(output/"selection_report.private.json", report)
        stage = "publish_result"
        publish()
    except BaseException as exc:
        write(output/"failure.private.json", dict(stage=stage, exception_type=type(exc).__name__, message=str(exc)))
        raise
    return report, result
