"""Native accepted temporal model lineage and the accepted spatial checkpoint."""

from dataclasses import dataclass
from pathlib import Path

from ..domain.artifact_registry import require
from ..modeling.matched_one_state_ar import OneStateAR
from ..modeling.matched_stationary_ar import StationaryAR
from ..modeling.matched_gaussian import MatchedGaussian
from . import artifact_registry as registry, development_experiment as original
from .development_one_state import load_experiment
from .development_flow import one_state_evidence
from .spatial_planner_pilot import _pinned_bytes, _verified_zip


@dataclass(frozen=True)
class TemporalModels:
    gaussian: MatchedGaussian
    stationary: StationaryAR
    one_state: OneStateAR
    hashes: dict[str, str]


def restore_models(one_raw: bytes, stationary_raw: bytes, fold: dict,
                   gaussian: MatchedGaussian, gaussian_pin: str) -> TemporalModels:
    """Restore the selected fold only after the native lineage validator passes."""
    name = "training/" + fold["fold_id"] + "_model.json"
    with _verified_zip(one_raw) as (archive, sums):
        saved = registry.decode(archive.read(name))
        one_state = OneStateAR.from_dict(saved["state"])
        one_pin = sums[name]
    with _verified_zip(stationary_raw) as (archive, sums):
        stationary_saved = registry.decode(archive.read(name))
        stationary = StationaryAR.from_dict(stationary_saved["state"])
        stationary_pin = sums[name]
    require(saved["fold"] == stationary_saved["fold"] == fold
            and saved["base_conditional_transform_source_sha256"] ==
            stationary_saved["base_conditional_model_sha256"] == gaussian_pin
            and one_state.transform_source.to_dict() == stationary.base.to_dict() == gaussian.to_dict(),
            "temporal_pilot_saved_fold_or_transform_mismatch")
    return TemporalModels(gaussian, stationary, one_state, {
        "conditional_gaussian": gaussian_pin, "stationary_ar": stationary_pin, "one_state_ar": one_pin,
    })


def load_models(project: Path, directory: Path, experiment_pin: str,
                result_zip: Path, result_pin: str, original_marker: dict, fold: dict):
    """Reuse the existing complete one state and predecessor evidence replay."""
    inputs, marker = load_experiment(project, directory, experiment_pin)
    original = inputs.temporal_inputs.previous_manifest
    require(original == original_marker and marker["folds"] == original_marker["folds"],
            "temporal_pilot_original_lineage_changed")
    raw, _, _ = one_state_evidence(result_zip, result_pin, inputs, marker)
    gaussian, pin = inputs.temporal_inputs.states[fold["fold_id"]]["conditional_gaussian"]
    models = restore_models(raw, inputs.stationary_raw, fold, gaussian, pin)
    return inputs, models


def accepted_spatial(path: Path, pin: str, plan: dict, original_marker: dict, fold: dict) -> dict:
    """Check the pinned completed spatial replication before the temporal stage."""
    with _verified_zip(_pinned_bytes(path, pin)) as (archive, _):
        report = registry.decode(archive.read("replication/replication_report.private.json"))
        manifest = registry.decode(archive.read("replication/replication_manifest.private.json"))
    require(report["status"] == "complete_development_spatial_replication"
            and report["pilot_score_parity_verified"] is True
            and report["source"]["consumer_git_tree"] == plan["accepted_spatial_tree"]
            and manifest["original_experiment_sha256"] == plan["original_experiment_sha256"]
            and [v["fold"] for v in manifest["folds"]] == original_marker["folds"]
            and manifest["pilot_outing"] == fold["validation_outing"]
            and all(report[key] is False for key in
                    ("raw_payload_opened", "model_refitted", "new_recordings_admitted", "final_evaluation_authorized")),
            "temporal_pilot_accepted_spatial_checkpoint_required")
    return report
