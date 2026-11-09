"""Read pinned scenario and saved model evidence without extracting ZIP members."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import stat
import zipfile

import numpy as np

from ..domain import cached_planner_scenarios as scenario
from ..domain.artifact_registry import require
from ..modeling.matched_flow import MatchedFlow
from ..modeling.matched_gaussian import MatchedGaussian
from . import artifact_registry as registry, development_experiment as original
from .development_temporal import gaussian_evidence_bytes


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pinned_bytes(path: Path, pin: str) -> bytes:
    raw, _ = original.read_bytes(original.metadata_path(path), 64 * 1024**2)
    require(_sha(raw) == registry.digest(pin), "pilot_input_zip_digest_mismatch")
    return raw


@contextmanager
def _verified_zip(raw: bytes):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = archive.namelist()
        require(len(names) == len(set(names)) <= 256
                and sum(i.file_size for i in infos) <= 64 * 1024**2
                and all(not n.startswith("/") and ".." not in Path(n).parts
                        and not i.is_dir() and not stat.S_ISLNK(i.external_attr >> 16)
                        for n, i in zip(names, infos)), "pilot_zip_members_out_of_contract")
        entries = [line.split("  ", 1) for line in archive.read("SHA256SUMS").decode().splitlines()]
        sums = {name: registry.digest(digest) for digest, name in entries}
        require(len(entries) == len(sums) and set(names) == set(sums) | {"SHA256SUMS"}
                and "SHA256SUMS" not in sums, "pilot_zip_checksum_manifest")
        require(all(_sha(archive.read(name)) == pin for name, pin in sums.items()),
                "pilot_zip_member_digest_mismatch")
        yield archive, sums


def load_scenarios(path: Path, pin: str, marker: dict, fold: dict, held) -> tuple[list[dict], dict]:
    """Match every cached row and array against the native sealed experiment."""
    rows, arrays, summary = scenario.prepare_scenario_rows(held, fold)
    with _verified_zip(_pinned_bytes(path, pin)) as (archive, sums):
        prefix = "scenarios/"
        filenames = ("scenario_manifest.private.json", "scenario_rows.private.json", "scenario_arrays.npz")
        require(set(sums) == {prefix + name for name in filenames}, "pilot_scenario_member_set")
        report = registry.decode(archive.read(prefix + filenames[0]))
        require(report["contract_revision"] == scenario.REVISION
                and report["status"] == "complete_cached_spatial_scenario_preparation"
                and report["protocol"] == scenario.PROTOCOL and report["summary"] == summary
                and report["original_experiment_sha256"] == _sha(original.encoded(marker))
                and report["fold"] == fold and report["pilot_scenarios_ready"] is True
                and report["output_files_sha256"] == {n: sums[prefix + n] for n in filenames[1:]}
                and all(report[k] is False for k in ("raw_payload_opened", "model_sampling_executed",
                         "planner_scoring_executed", "final_evaluation_authorized", "new_recordings_admitted"))
                and all(report["original_" + k] == marker["original_" + k]
                        for k in ("cohort_sha256", "registry_sha256"))
                and report["latest_registry_sha256"] == marker["latest_registry_sha256"]
                and report["original_row_manifest_sha256"] == marker["row_manifest_sha256"]
                and sums[prefix + filenames[1]] == summary["rows_sha256"], "pilot_scenario_lineage")
        with np.load(io.BytesIO(archive.read(prefix + filenames[2])), allow_pickle=False) as saved:
            require(set(saved.files) == set(arrays) and len(saved.files) == len(arrays)
                    and all(saved[k].dtype == v.dtype and np.array_equal(saved[k], v)
                            for k, v in arrays.items()), "pilot_scenario_array_replay_mismatch")
    return rows, arrays


@dataclass(frozen=True)
class SavedSpatialModels:
    gaussian: MatchedGaussian
    flow: MatchedFlow
    hashes: dict[str, str]


def load_saved_models(path: Path, pin: str, marker: dict, fold: dict, held_sha: str) -> SavedSpatialModels:
    """Restore one exact fold from completed model evidence and its ancestry."""
    with _verified_zip(_pinned_bytes(path, pin)) as (archive, sums):
        def read(name: str) -> dict:
            return registry.decode(archive.read(name))

        receipt = read("training/run_receipt.json")
        experiment = read("experiment/experiment.json")
        exp_pin = sums["experiment/experiment.json"]
        require(receipt["status"] == "complete_matched_flow_cross_validation"
                and receipt["exit_code"] == 0 and receipt["failures"] == []
                and receipt["input_integrity_verified"] is True
                and all(receipt[k] is False for k in ("raw_payload_opened", "baseline_refitted",
                         "transform_refitted", "final_evaluation_authorized"))
                and receipt["experiment_sha256"] == exp_pin
                and experiment["original_gaussian_experiment_sha256"] == _sha(original.encoded(marker))
                and experiment["folds"] == marker["folds"], "pilot_completed_flow_lineage_required")
        stem = "training/" + fold["fold_id"] + "_unconditional"
        model_name, score_name, calibration_name = (stem + suffix for suffix in
                                                    ("_model.json", "_scores.json", "_calibration.json"))
        saved, score, calibration = read(model_name), read(score_name), read(calibration_name)
        require(score in receipt["completed"] and saved["fold"] == score["fold"] == fold
                and saved["experiment_sha256"] == exp_pin
                and score["model"] == "matched_unconditional_flow"
                and score["validation_archive_sha256"] == held_sha
                and score["model_sha256"] == sums[model_name]
                and score["solver_calibration_sha256"] == sums[calibration_name]
                and all(receipt["output_files_sha256"][n.removeprefix("training/")] == sums[n]
                        for n in (model_name, score_name, calibration_name))
                and calibration["passed"] is True and calibration["solver"] == score["solver"] == "heun"
                and calibration["selected_steps"] == score["solver_steps"] == 128,
                "pilot_flow_state_calibration_or_fold_mismatch")
        flow = MatchedFlow.from_dict(saved["state"])
        require(flow.mode == "unconditional" and flow.training_rows == score["training_rows"],
                "pilot_flow_state_identity")
        one_raw = archive.read("training/accepted_one_state_ar_result.zip")
        require(_sha(one_raw) == experiment["one_state_ar_result_sha256"], "pilot_one_state_ancestry")
        with _verified_zip(one_raw) as (one, _):
            one_marker = registry.decode(one.read("experiment/experiment.json"))
            ar_raw = one.read("training/accepted_stationary_ar_result.zip")
        require(_sha(ar_raw) == one_marker["stationary_ar_result_sha256"], "pilot_stationary_ar_ancestry")
        with _verified_zip(ar_raw) as (ar, _):
            ar_marker = registry.decode(ar.read("experiment/experiment.json"))
            gauss_raw = ar.read("training/accepted_gaussian_result.zip")
        _, states, _, _ = gaussian_evidence_bytes(gauss_raw, ar_marker["gaussian_result_sha256"], marker)
        gaussian, gaussian_pin = states[fold["fold_id"]]["unconditional_gaussian"]
        conditional, conditional_pin = states[fold["fold_id"]]["conditional_gaussian"]
        require(saved["base_conditional_transform_source_sha256"] == conditional_pin
                == score["base_conditional_transform_source_sha256"]
                and all(np.array_equal(getattr(flow, key), getattr(conditional, key))
                        for key in ("residual_mean", "residual_scale", "condition_mean", "condition_scale")),
                "pilot_flow_transform_provenance")
    return SavedSpatialModels(gaussian, flow, {"gaussian": gaussian_pin, "flow": sums[model_name],
                                               "flow_solver_calibration": sums[calibration_name]})
