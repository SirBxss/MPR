"""Pinned reuse of accepted Gaussian evidence for a matched AR control."""

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import stat
import zipfile

import numpy as np

from ..domain.artifact_registry import require
from ..modeling.matched_gaussian import MatchedGaussian
from ..modeling.matched_stationary_ar import MODEL_NAME, MAXIMUM_ABSOLUTE_PHI
from . import development_experiment as previous, artifact_registry as registry

REVISION = "v0.19.17-matched-stationary-ar-2026-10-23-a1"
AUTHORIZATION_REVISION = "v0.19.17-stationary-ar-fit-2026-10-23-a1"
GAUSSIAN_SOURCE = ("071235289618447e52770829d2d30d4420b2b8ec",
    "a87bfb331bb1ce7d30490c79f8d494ccacfdb845",
    "b88b8aa3f8dfc139741901e9bd291b3409bee07e32a4a2d9db18f64c31cdfe9f")
FIELDS = {"contract_revision","original_experiment_directory","expected_original_experiment_sha256",
          "gaussian_result_zip","expected_gaussian_result_sha256","experiment_directory",
          "training_directory","authorization","result_zip"}
ATTESTATIONS = {"explicit_development_stationary_ar_fit","independent_protocol_review_and_ci_accepted",
                "final_outings_remain_unexposed","fixed_protocol_and_preserve_failed_attempts"}
PROTOCOL = {"model":MODEL_NAME,"base":"accepted_conditional_Gaussian_state_no_refit",
    "mean_and_spatial_covariance":"frozen_from_each_original_training_fold",
    "phi":"one_shared_scalar_bounded_training_transition_MLE",
    "maximum_absolute_phi":MAXIMUM_ABSOLUTE_PHI,"coefficient_units":"per_retained_frame_not_per_second",
    "innovation_covariance":"(1-phi**2)*frozen_spatial_covariance",
    "reset":"frozen_conditional_Gaussian_marginal_independent_at_every_original_reset",
    "sequences":"original_offsets_no_bridging_no_frame_removal",
    "sample_count":128,"sampling_seed":20261022,"primary_aggregation":"equal_outing_macro",
    "primary_question":"does_memory_improve_short_sequence_generation_with_frame_marginals_fixed",
    "primary_metrics":["mean_normalized_sequence_energy_score_m","median_absolute_lag_one_correlation_error"],
    "marginal_scores":"unchanged_in_distribution_finite_MC_differences_not_marginal_improvement_evidence",
    "density":"observed_history_chain_density_separate_from_unchanged_single_frame_density",
    "history_scope":"generated_previous_deviation_for_simulation_observed_past_for_offline_density_only",
    "selection":"fixed_cap_no_search_no_early_stopping_no_held_out_tuning",
    "claim":"short_window_development_pseudo_residual_control_not_legacy_AR_reproduction",
    "final_evaluation_authorized":False,"advanced_real_fit_authorized":False,
    "planner_evaluation_authorized":False,"raw_processing_authorized":False,
    "physical_ground_truth_claim":False}


def validate_request(value):
    require(type(value) is dict and set(value) == FIELDS and value["contract_revision"] == REVISION,
            "temporal_closed_request_schema")
    for k in ("expected_original_experiment_sha256","expected_gaussian_result_sha256"):
        registry.digest(value[k])


def aggregate(results):
    """Equal-outing primary; frames/sequence counts weight the pooled diagnostic."""
    scores = ("mean_physical_joint_nll","sample_mean_rmse_m","mean_energy_score_m",
              "mean_normalized_sequence_energy_score_m","mean_marginal_crps_m")
    output = {}
    for model in sorted({r["model"] for r in results}):
        rows = [r for r in results if r["model"] == model]
        weights = [r["metrics"]["frame_count"] for r in rows]
        pooled = {k:float(np.average([r["metrics"][k] for r in rows],weights=(
            [r["metrics"]["sequence_count"] for r in rows] if k == "mean_normalized_sequence_energy_score_m" else weights))) for k in scores}
        pooled["sample_mean_rmse_m"] = float(np.sqrt(np.average([r["metrics"]["sample_mean_rmse_m"]**2 for r in rows],weights=weights)))
        output[model] = {"outings":len(rows),"frames":sum(weights),
            "equal_outing_macro":{k:float(np.mean([r["metrics"][k] for r in rows])) for k in scores},
            "pooled_diagnostic":pooled,
            "equal_outing_macro_interval_coverage":{level:float(np.mean([r["metrics"]["intervals"][level]["coverage"] for r in rows])) for level in ("0.5","0.8","0.95")},
            "equal_outing_macro_tail_brier":{level:float(np.mean([r["metrics"]["profile_max_absolute_tail"][level]["brier_score"] for r in rows])) for level in ("0.5","1.0","2.0")}}
    return output


def paired_temporal_comparison(baseline_results, temporal_results):
    """Paired outing diagnostics; unavailable lag is missing, never zero-filled."""
    base = {r["fold"]["fold_id"]:r for r in baseline_results if r["model"] == "conditional_gaussian"}
    require(len(temporal_results) == len(base) and len({r["fold"]["fold_id"] for r in temporal_results}) == len(base),
            "temporal_exact_paired_folds_required")
    output = {"baseline":"conditional_gaussian","direction":"AR_minus_baseline_lower_is_better",
              "scope":"descriptive_equal_outing_no_significance_or_long_horizon_claim","metrics":{}}
    for metric in PROTOCOL["primary_metrics"]:
        rows = []
        for result in temporal_results:
            baseline = base[result["fold"]["fold_id"]]
            require(result["fold"] == baseline["fold"],"temporal_paired_fold_mismatch")
            a,b = baseline["metrics"][metric],result["metrics"][metric]
            rows.append({"validation_outing":result["fold"]["validation_outing"],"baseline":a,"AR":b,
                         "difference":None if a is None or b is None else float(b-a)})
        differences = [r["difference"] for r in rows if r["difference"] is not None]
        output["metrics"][metric] = {"paired_outings":rows,"assessed_outings":len(differences),
            "unassessed_outings":len(rows)-len(differences),
            "equal_outing_mean_difference":float(np.mean(differences)) if differences else None,
            "improved_outings":sum(d < 0 for d in differences),"worsened_outings":sum(d > 0 for d in differences),
            "tied_outings":sum(d == 0 for d in differences)}
    return output


def gaussian_evidence(path, expected_pin, manifest):
    """Read bounded JSON only; exact external ZIP pin and reviewed producer tuple."""
    p = previous.metadata_path(path)
    raw,_ = previous.read_bytes(p,64*1024**2)
    require(hashlib.sha256(raw).hexdigest() == registry.digest(expected_pin),"temporal_gaussian_result_digest_mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and len(names) <= 128
                and sum(i.file_size for i in z.infolist()) <= 64*1024**2
                and all(not n.startswith("/") and ".." not in Path(n).parts
                        and not n.endswith("/") and not stat.S_ISLNK(i.external_attr>>16)
                        for n,i in zip(names,z.infolist())),"temporal_gaussian_zip_members")
        require(z.testzip() is None,"temporal_gaussian_zip_crc")
        sums = {}
        for line in z.read("SHA256SUMS").decode().splitlines():
            h,name = line.split("  ",1)
            require(name not in sums,"temporal_gaussian_duplicate_sha_entry")
            sums[name] = registry.digest(h)
        require(set(names) == set(sums)|{"SHA256SUMS"},"temporal_gaussian_zip_file_set")
        for name,h in sums.items():
            require(hashlib.sha256(z.read(name)).hexdigest() == h,"temporal_gaussian_member_digest")
        read = lambda name:registry.decode(z.read(name))
        receipt = read("training/run_receipt.json")
        source = receipt["source"]
        require(tuple(source[k] for k in ("consumer_git_commit","consumer_git_tree","consumer_runtime_source_sha256")) == GAUSSIAN_SOURCE,
                "temporal_gaussian_unreviewed_producer")
        require(receipt["status"] == "complete_development_gaussian_cross_validation" and receipt["exit_code"] == 0
                and receipt["input_integrity_verified"] is True and receipt["failures"] == []
                and receipt["development_gaussian_fit_authorized"] is True
                and receipt["advanced_real_fit_authorized"] is False
                and receipt["final_evaluation_authorized"] is False and receipt["raw_payload_opened"] is False,
                "temporal_successful_gaussian_receipt_required")
        marker_raw = z.read("experiment/experiment.json")
        require(read("experiment/experiment.json") == manifest and
                hashlib.sha256(marker_raw).hexdigest() == receipt["experiment_sha256"],"temporal_original_experiment_mismatch")
        previous.require_authorization(read("training/authorization.json"),receipt["experiment_sha256"])
        require(sums["training/authorization.json"] == receipt["authorization_sha256"],"temporal_gaussian_authorization_pin")
        required = {"SHA256SUMS","experiment/experiment.json","experiment/request.json","experiment/row_manifest.json",
                    "training/authorization.json","training/run_receipt.json"}
        states,results = {},[]
        for index,fold in enumerate(manifest["folds"]):
            states[fold["fold_id"]] = {}
            for mode in previous.MODEL_NAMES:
                stem = "training/"+fold["fold_id"]+"_"+mode
                model_name,score_name = stem+"_model.json",stem+"_scores.json"
                required.update((model_name,score_name))
                saved,result = read(model_name),read(score_name)
                require(saved["fold"] == fold and result["fold"] == fold and saved["experiment_sha256"] == receipt["experiment_sha256"]
                        and result["model"] == mode and result["sampling_seed"] == PROTOCOL["sampling_seed"]+index
                        and result["model_sha256"] == sums[model_name],"temporal_gaussian_fold_or_seed_mismatch")
                state = MatchedGaussian.from_dict(saved["state"])
                require(state.mode == mode and state.training_rows == result["training_rows"]
                        and result["training_outing_count"] == len(fold["training_outings"]),"temporal_gaussian_state_identity")
                states[fold["fold_id"]][mode] = (state,sums[model_name])
                results.append(result)
        require(set(names) == required and receipt["completed"] == results and receipt["aggregate"] == aggregate(results),
                "temporal_gaussian_completed_or_aggregate_mismatch")
        expected_files = {n.removeprefix("training/"):sums[n] for n in required if n.startswith("training/") and n != "training/run_receipt.json"}
        require(receipt["output_files_sha256"] == expected_files,"temporal_gaussian_receipt_output_manifest")
        return raw,states,results,{n:z.read(n) for n in required if n.startswith("experiment/")}


@dataclass
class TemporalInputs:
    request: dict
    previous_inputs: object
    previous_manifest: dict
    gaussian_raw: bytes
    states: dict
    baseline_results: list
    watched: dict

    def unchanged(self):
        self.previous_inputs.unchanged()
        require(all(previous.sha(p) == h for p,h in self.watched.items()),"temporal_input_changed")


def load_inputs(project, request_path, expected_request_sha256):
    request,_ = previous.pinned_json(request_path,expected_request_sha256)
    validate_request(request)
    folder = previous.resolve(project,request["original_experiment_directory"])
    inputs,manifest = previous.load_experiment(project,folder,request["expected_original_experiment_sha256"])
    path = previous.resolve(project,request["gaussian_result_zip"])
    raw,states,results,files = gaussian_evidence(path,request["expected_gaussian_result_sha256"],manifest)
    require(all((folder/n.removeprefix("experiment/")).read_bytes() == data for n,data in files.items()),
            "temporal_original_experiment_bytes_mismatch")
    by_id = {b.outing_id:b for b in inputs.blocks}
    for fold in manifest["folds"]:
        expected_rows = sum(len(by_id[i].x) for i in fold["training_outings"])
        for mode in previous.MODEL_NAMES:
            require(states[fold["fold_id"]][mode][0].training_rows == expected_rows,"temporal_training_row_count")
        for result in [r for r in results if r["fold"] == fold]:
            block = by_id[fold["validation_outing"]]
            require(result["validation_archive_sha256"] == block.archive.summary_sha256
                    and result["metrics"]["frame_count"] == len(block.x)
                    and result["metrics"]["sequence_count"] == len(block.offsets)-1
                    and result["metrics"]["valid_transitions"] == len(block.x)-len(block.offsets)+1,
                    "temporal_validation_support_mismatch")
    result = TemporalInputs(request,inputs,manifest,raw,states,results,
        {previous.metadata_path(request_path):expected_request_sha256,path:request["expected_gaussian_result_sha256"]})
    result.unchanged()
    return result


def marker(inputs, request_sha256):
    return {"contract_revision":REVISION,"status":"complete_matched_stationary_ar_experiment",
        "request_sha256":request_sha256,"original_experiment_sha256":inputs.request["expected_original_experiment_sha256"],
        "gaussian_result_sha256":inputs.request["expected_gaussian_result_sha256"],
        "row_manifest_sha256":inputs.previous_manifest["row_manifest_sha256"],"folds":inputs.previous_manifest["folds"],
        "archives":inputs.previous_manifest["archives"],"protocol":PROTOCOL,
        "model_admission_authorized":False,"final_evaluation_authorized":False}


def load_experiment(project, folder, pin):
    folder = previous.metadata_path(folder)
    require(folder.is_dir() and {p.name for p in folder.iterdir()} == {"request.json","experiment.json"},"temporal_exact_experiment_file_set")
    saved,_ = previous.pinned_json(folder/"experiment.json",pin)
    inputs = load_inputs(project,folder/"request.json",saved["request_sha256"])
    require(saved == marker(inputs,saved["request_sha256"]),"temporal_cached_protocol_or_folds_changed")
    inputs.watched[folder/"experiment.json"] = pin
    return inputs,saved


def authorization_draft(pin):
    registry.digest(pin)
    return {"contract_revision":AUTHORIZATION_REVISION,"purpose":"fixed_stationary_ar_control_development_only",
            "experiment_sha256":pin,"attestations":dict.fromkeys(sorted(ATTESTATIONS),False)}


def require_authorization(value,pin):
    expected = authorization_draft(pin)
    expected["attestations"] = dict.fromkeys(sorted(ATTESTATIONS),True)
    require(type(value) is dict and value == expected and all(type(v) is bool and v for v in value["attestations"].values()),
            "temporal_explicit_owner_ar_authorization_required")


def design_sha256(manifest):
    # Output locations/request aliases do not grant another invisible attempt.
    return hashlib.sha256(previous.encoded({k:manifest[k] for k in
        ("original_experiment_sha256","gaussian_result_sha256","protocol")})).hexdigest()
