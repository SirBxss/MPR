"""Restore six frozen laws after complete native ancestry and result checks."""

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np

from ..domain.artifact_registry import require
from ..modeling.matched_flow import MatchedFlow, MODES, CONFIGURATION
from ..modeling.matched_flow_evaluation import comparison, paired_comparisons
from ..modeling.matched_gaussian import MatchedGaussian
from . import artifact_registry as registry, development_flow as flow_io, development_experiment as original
from .spatial_planner_pilot import _verified_zip, _pinned_bytes
from .temporal_planner_pilot import TemporalModels, restore_models


@dataclass(frozen=True)
class FrozenFamily:
    unconditional: MatchedGaussian
    temporal: TemporalModels
    flows: dict[str, MatchedFlow]
    hashes: dict[str, str]


def restore_families(raw: bytes, native, marker: dict, original_marker: dict) -> dict[str, FrozenFamily]:
    """Validate the accepted complete flow return and restore both modes per fold."""
    with _verified_zip(raw) as (archive, sums):
        read = lambda n: registry.decode(archive.read(n))
        receipt = read("training/run_receipt.json")
        pin = sums["experiment/experiment.json"]
        require(read("experiment/experiment.json") == marker
                and receipt["contract_revision"] == flow_io.REVISION
                and receipt["status"] == "complete_matched_flow_cross_validation"
                and type(receipt["exit_code"]) is int and receipt["exit_code"] == 0
                and receipt["failures"] == [] and receipt["input_integrity_verified"] is True
                and receipt["development_matched_flow_fit_authorized"] is True and receipt["fit_attempted"] is True
                and receipt["experiment_sha256"] == pin and marker["folds"] == original_marker["folds"]
                and marker["original_gaussian_experiment_sha256"] == hashlib.sha256(original.encoded(original_marker)).hexdigest()
                and all(receipt[k] is False for k in ("raw_payload_opened", "baseline_refitted", "transform_refitted",
                    "final_evaluation_authorized", "other_advanced_real_fit_authorized")),
                "parameter_selection_completed_flow_lineage")
        outputs = {"training/"+n: h for n, h in receipt["output_files_sha256"].items()}
        require(set(sums) == set(outputs) | {"experiment/experiment.json", "experiment/request.json", "training/run_receipt.json"}
                and all(sums[n] == h for n, h in outputs.items())
                and sums["training/authorization.json"] == receipt["authorization_sha256"],
                "parameter_selection_flow_result_census")
        flow_io.require_authorization(read("training/authorization.json"), pin)
        claim = read("training/attempt_claim.json")
        require(sums["training/attempt_claim.json"] == receipt["attempt_claim_sha256"]
                and claim["status"] == "claimed_do_not_retry" and claim["source"] == receipt["source"]
                and claim["experiment_sha256"] == pin and claim["authorization_sha256"] == receipt["authorization_sha256"]
                and claim["design_sha256"] == flow_io.design_sha256(marker)
                and claim["one_state_ar_result_sha256"] == marker["one_state_ar_result_sha256"]
                and claim["original_gaussian_experiment_sha256"] == marker["original_gaussian_experiment_sha256"]
                and archive.read("training/accepted_one_state_ar_result.zip") == native.one_state_raw,
                "parameter_selection_flow_fit_claim_and_parent")
        families, completed = {}, []
        blocks = {b.outing_id: b for b in native.one_state_inputs.temporal_inputs.previous_inputs.blocks}
        for index, fold in enumerate(marker["folds"]):
            states = native.one_state_inputs.temporal_inputs.states[fold["fold_id"]]
            gaussian, gp = states["conditional_gaussian"]
            unconditional, up = states["unconditional_gaussian"]
            temporal = restore_models(native.one_state_raw, native.one_state_inputs.stationary_raw, fold, gaussian, gp)
            hashes = dict(unconditional_gaussian=up, **temporal.hashes)
            flows = {}
            for mode in MODES:
                stem = "training/"+fold["fold_id"]+"_"+mode
                mn, sn, cn = (stem+suffix for suffix in ("_model.json", "_scores.json", "_calibration.json"))
                saved, score, calibration = read(mn), read(sn), read(cn)
                model = MatchedFlow.from_dict(saved["state"])
                held = blocks[fold["validation_outing"]]
                require(saved["fold"] == score["fold"] == fold and saved["contract_revision"] == flow_io.REVISION
                        and saved["experiment_sha256"] == pin and score["model"] == "matched_"+mode+"_flow"
                        and saved["base_conditional_transform_source_sha256"] == score["base_conditional_transform_source_sha256"] == gp
                        and model.mode == mode and model.training_rows == score["training_rows"] == gaussian.training_rows
                        == sum(len(blocks[i].y) for i in fold["training_outings"])
                        and model.training_sequences == score["training_sequences"] == sum(len(blocks[i].offsets)-1 for i in fold["training_outings"])
                        and score["sampling_seed"] == flow_io.PROTOCOL["sampling_seed"]+index
                        and score["model_sha256"] == sums[mn] and score["solver_calibration_sha256"] == sums[cn]
                        and calibration["passed"] is True and calibration["solver"] == score["solver"] == "heun"
                        and calibration["selected_steps"] == score["solver_steps"] == 128
                        and calibration["configuration"] == flow_io.CALIBRATION
                        and len(model.training_losses) == CONFIGURATION["epochs"]
                        and saved["fit_report"]["configuration"] == CONFIGURATION
                        and saved["fit_report"]["epochs_completed"] == CONFIGURATION["epochs"]
                        and saved["fit_report"]["transform_refitted"] is False
                        and score["validation_archive_sha256"] == held.archive.summary_sha256
                        and score["metrics"]["frame_count"] == len(held.y)
                        and score["metrics"]["sequence_count"] == len(held.offsets)-1
                        and saved["fit_report"] == score["fit_report"]
                        and all(np.array_equal(getattr(model, k), getattr(gaussian, k)) for k in
                                ("residual_mean", "residual_scale", "condition_mean", "condition_scale")),
                        "parameter_selection_frozen_flow_state_or_solver")
                flows[mode] = model
                hashes[mode+"_flow"], hashes[mode+"_flow_solver"] = sums[mn], sums[cn]
                completed.append(score)
            families[fold["fold_id"]] = FrozenFamily(unconditional, temporal, flows, hashes)
        require(receipt["completed"] == completed and receipt["comparison"] == comparison(native.previous_results+completed),
                "parameter_selection_completed_flow_comparison")
        compare_file = read("training/comparison.json")
        require(compare_file["models"] == receipt["comparison"]
                and compare_file["paired_comparisons"] == paired_comparisons(native.previous_results, completed),
                "parameter_selection_flow_comparison_binding")
    return families


def load_families(project: Path, directory: Path, experiment_pin: str, result: Path, result_pin: str):
    """Replay native inputs once; a failed native check has no archive fallback."""
    native, marker = flow_io.load_experiment(project, directory, experiment_pin)
    raw = _pinned_bytes(result, result_pin)
    with _verified_zip(raw) as (archive, sums):
        require(sums["experiment/experiment.json"] == experiment_pin
                and archive.read("experiment/request.json") == (directory/"request.json").read_bytes(),
                "parameter_selection_original_flow_experiment_bytes")
    original_marker = native.one_state_inputs.temporal_inputs.previous_manifest
    families = restore_families(raw, native, marker, original_marker)
    return native, marker, original_marker, families


def accepted_temporal(path: Path, pin: str, plan: dict, flow_marker: dict, original_marker: dict,
                     families: dict) -> dict:
    """Pin the accepted temporal checkpoint and its complete original fold set."""
    with _verified_zip(_pinned_bytes(path, pin)) as (archive, sums):
        report = registry.decode(archive.read("temporal_replication/replication_report.private.json"))
        manifest = registry.decode(archive.read("temporal_replication/replication_manifest.private.json"))
        require(sums["temporal_replication/replication_manifest.private.json"] == plan["accepted_temporal_manifest_sha256"]
                and report["manifest_sha256"] == plan["accepted_temporal_manifest_sha256"]
                and report["status"] == "complete_development_temporal_replication"
                and report["pilot_score_parity_verified"] is True
                and {k: report["source"][k] for k in plan["accepted_temporal_source"]} == plan["accepted_temporal_source"]
                and [f["fold"] for f in manifest["folds"]] == original_marker["folds"] == flow_marker["folds"]
                and manifest["original_experiment_sha256"] == flow_marker["original_gaussian_experiment_sha256"]
                and manifest["one_state_result_sha256"] == flow_marker["one_state_ar_result_sha256"]
                and report["fold_support"] == manifest["folds"]
                and all(report[k] is False for k in ("raw_payload_opened", "model_refitted", "new_recordings_admitted",
                                                     "final_evaluation_authorized", "planner_tuning_performed")),
                "parameter_selection_accepted_temporal_checkpoint")
        for entry in manifest["folds"]:
            require(entry["saved_model_sha256"] == families[entry["fold"]["fold_id"]].temporal.hashes,
                    "parameter_selection_temporal_state_ancestry")
    return manifest
