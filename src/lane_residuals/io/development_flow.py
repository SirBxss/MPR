"""Closed real flow protocol with immutable original four model lineage."""
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import stat
import zipfile

from ..domain.artifact_registry import require
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..modeling.matched_flow import CONFIGURATION, MODES, MODEL_NAMES, joined_blocks
from ..modeling.matched_flow_calibration import CALIBRATION, calibration_conditions
from ..modeling.matched_one_state_ar import OneStateAR, MODEL_NAME as ONE_STATE_NAME
from . import artifact_registry as registry, development_experiment as previous, development_one_state as one, development_temporal as temporal

REVISION = "v0.19.27-matched-flow-2026-11-04"
AUTHORIZATION_REVISION = "v0.19.27-matched-flow-owner-2026-11-04"
ONE_STATE_SOURCE = ("77b533947414ed41676d3b8fff461935c2bed61a", "80add0f7ab822bfb6a50372404c47a6d5e83ec5b",
                    "c3bb400238f602a30e2326258126e261c9ecf84f25bdfbd9aec77b678d6e3fd4")
FIELDS = {"contract_revision", "original_one_state_experiment_directory", "expected_original_one_state_experiment_sha256",
          "one_state_ar_result_zip", "expected_one_state_ar_result_sha256", "experiment_directory", "training_directory", "authorization", "result_zip"}
ATTESTATIONS = {"explicit_two_flow_development_fit", "independent_source_protocol_helper_review_and_ci_accepted",
                "restricted_original_short_support_scope_accepted", "supervisor_visible_model_substitution_decision_accepted",
                "final_outings_remain_unexposed", "fixed_protocol_and_preserve_failed_attempts"}
PROTOCOL = {"models": list(MODEL_NAMES), "modes": list(MODES), "configuration": CONFIGURATION,
            "calibration": CALIBRATION, "feature_names": list(BMW_CONDITION_FEATURE_NAMES),
            "population": "exact_original_complete_feature_rows_no_speed_replacement_no_new_recordings",
            "transform": "accepted_conditional_Gaussian_fold_means_scales_exact_no_refit_both_modes",
            "architecture": "one_tanh_hidden_layer_linear_output_straight_independent_noise_bridge",
            "training": "fixed_epochs_Adam_training_rows_only_observed_previous_only_within_sequence",
            "selection": "none_fixed_architecture_epochs_seed_no_restarts_no_outer_tuning",
            "training_seed": 20261104, "sample_count": 128, "sampling_seed": 20261022,
            "solver": "Euler_fixed_64_after_training_only_32_to_64_screen_no_validation_selection",
            "random_numbers": "mode_paired_bridge_streams_and_indexed_row_sampling_noise_not_paired_with_legacy_AR",
            "calibration_subset": "shortest_middle_longest_sequence_per_training_outing_length_and_index_only",
            "timing": "first_authorized_fit_is_timing_check_fixed_600_seconds_each_stop_preserve_on_timeout",
            "reset": "exact_original_offsets_generated_previous_physical_residual_zero_standardized_at_reset_with_flag",
            "likelihood": "unavailable_no_verified_divergence_integral_training_MSE_is_not_NLL",
            "primary_metrics": list(one.PROTOCOL["primary_metrics"]), "primary_aggregation": "equal_outing_macro",
            "comparison": "reuse_four_original_matched_baselines_no_refit_no_historical_score_pooling",
            "interpretation": "conditional_combines_features_and_history_not_pure_memory_or_speed_ablation",
            "claim": "original_short_window_RLMB_fusion_pseudo_residuals_not_physical_ground_truth",
            "failure": "stop_later_fits_preserve_claim_checkpoints_states_scores_and_partial_return_no_automatic_retry",
            "long_temporal_support_gate_passed": False, "speed_feature_adopted": False,
            "raw_processing_authorized": False, "final_evaluation_authorized": False, "planner_evaluation_authorized": False}


def validate_request(value):
    require(type(value) is dict and set(value) == FIELDS and value["contract_revision"] == REVISION, "flow_closed_request_schema")
    for key in ("expected_original_one_state_experiment_sha256", "expected_one_state_ar_result_sha256"):
        registry.digest(value[key])
    for key in FIELDS - {"contract_revision", "expected_original_one_state_experiment_sha256", "expected_one_state_ar_result_sha256"}:
        require(type(value[key]) is str and bool(value[key]), "flow_path_string_required")


def one_state_evidence(path, pin, inputs, manifest):
    """Read bounded accepted evidence, without rerunning any fit or sampler."""
    path = previous.metadata_path(path)
    require(path.suffix == ".zip", "flow_predecessor_ZIP_required")
    raw, _ = previous.read_bytes(path, 64*1024**2)
    require(hashlib.sha256(raw).hexdigest() == registry.digest(pin), "flow_predecessor_digest_mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos, names = z.infolist(), z.namelist()
        require(len(names) == len(set(names)) and len(names) <= 128 and sum(i.file_size for i in infos) <= 64*1024**2
                and all(not n.startswith("/") and ".." not in Path(n).parts and not n.endswith("/")
                        and not stat.S_ISLNK(i.external_attr >> 16) for n, i in zip(names, infos)), "flow_predecessor_bounded_members")
        require(z.testzip() is None, "flow_predecessor_CRC")
        sums = {}
        for line in z.read("SHA256SUMS").decode().splitlines():
            h, n = line.split("  ", 1)
            require(n not in sums, "flow_duplicate_SHA_entry")
            sums[n] = registry.digest(h)
        require(set(names) == set(sums) | {"SHA256SUMS"}
                and all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in sums.items()), "flow_predecessor_file_set_or_digest")
        read = lambda n: registry.decode(z.read(n))
        receipt = read("training/run_receipt.json")
        source = receipt["source"]
        require(tuple(source[k] for k in ("consumer_git_commit", "consumer_git_tree", "consumer_runtime_source_sha256")) == ONE_STATE_SOURCE,
                "flow_predecessor_unreviewed_producer")
        require(receipt["status"] == "complete_matched_one_state_ar_cross_validation" and type(receipt["exit_code"]) is int
                and receipt["exit_code"] == 0 and receipt["failures"] == [] and receipt["input_integrity_verified"] is True
                and receipt["fit_attempted"] is True and receipt["development_one_state_ar_fit_authorized"] is True
                and all(receipt[k] is False for k in ("raw_payload_opened", "baseline_refitted", "transform_refitted", "final_evaluation_authorized", "advanced_real_fit_authorized")),
                "flow_successful_predecessor_required")
        require(read("experiment/experiment.json") == manifest and receipt["experiment_sha256"] == sums["experiment/experiment.json"], "flow_predecessor_experiment")
        one.require_authorization(read("training/authorization.json"), receipt["experiment_sha256"])
        require(receipt["authorization_sha256"] == sums["training/authorization.json"], "flow_predecessor_authorization_pin")
        claim = read("training/attempt_claim.json")
        require(claim["status"] == "claimed_do_not_retry" and claim["source"] == source
                and claim["design_sha256"] == one.design_sha256(manifest) and receipt["attempt_claim_sha256"] == sums["training/attempt_claim.json"]
                and claim["experiment_sha256"] == receipt["experiment_sha256"]
                and claim["authorization_sha256"] == receipt["authorization_sha256"]
                and claim["original_gaussian_experiment_sha256"] == manifest["original_gaussian_experiment_sha256"]
                and claim["stationary_ar_result_sha256"] == manifest["stationary_ar_result_sha256"], "flow_predecessor_claim")
        require(z.read("training/accepted_stationary_ar_result.zip") == inputs.stationary_raw, "flow_predecessor_original_baselines_changed")
        required = {"SHA256SUMS", "experiment/experiment.json", "experiment/request.json", "training/run_receipt.json",
                    "training/authorization.json", "training/attempt_claim.json", "training/accepted_stationary_ar_result.zip"}
        results = []
        blocks = {b.outing_id: b for b in inputs.temporal_inputs.previous_inputs.blocks}
        for index, fold in enumerate(manifest["folds"]):
            stem = "training/"+fold["fold_id"]
            m, s = stem+"_model.json", stem+"_scores.json"
            required |= {m, s}
            saved, row = read(m), read(s)
            model = OneStateAR.from_dict(saved["state"])
            base, basepin = inputs.temporal_inputs.states[fold["fold_id"]]["conditional_gaussian"]
            train, held = [blocks[i] for i in fold["training_outings"]], blocks[fold["validation_outing"]]
            require(saved["contract_revision"] == one.REVISION and saved["experiment_sha256"] == receipt["experiment_sha256"]
                    and saved["fold"] == row["fold"] == fold and row["model"] == ONE_STATE_NAME
                    and saved["base_conditional_transform_source_sha256"] == row["base_conditional_transform_source_sha256"] == basepin
                    and model.transform_source.to_dict() == base.to_dict() and row["model_sha256"] == sums[m]
                    and row["sampling_seed"] == PROTOCOL["sampling_seed"]+index
                    and row["training_rows"] == sum(len(b.y) for b in train) == base.training_rows
                    and row["training_sequences"] == sum(len(b.offsets)-1 for b in train)
                    and row["training_transitions"] == sum(len(b.y)-len(b.offsets)+1 for b in train)
                    and row["validation_archive_sha256"] == held.archive.summary_sha256
                    and row["metrics"]["frame_count"] == len(held.y)
                    and row["metrics"]["sequence_count"] == len(held.offsets)-1
                    and row["metrics"]["valid_transitions"] == len(held.y)-len(held.offsets)+1, "flow_predecessor_state_score_support")
            results.append(row)
        require(set(names) == required and receipt["completed"] == results
                and receipt["comparison"] == temporal.aggregate(inputs.previous_results+results)
                and receipt["paired_comparisons"] == one.paired_comparisons(inputs.previous_results, results), "flow_predecessor_completed_comparison")
        require(receipt["output_files_sha256"] == {n.removeprefix("training/"): sums[n] for n in required
                if n.startswith("training/") and n != "training/run_receipt.json"}, "flow_predecessor_receipt_manifest")
        return raw, results, {n: z.read(n) for n in required if n.startswith("experiment/")}


@dataclass
class FlowInputs:
    request: dict
    one_state_inputs: object
    one_state_manifest: dict
    one_state_raw: bytes
    one_state_results: list
    watched: dict

    @property
    def previous_results(self):
        return self.one_state_inputs.previous_results+self.one_state_results

    def unchanged(self):
        self.one_state_inputs.unchanged()
        require(all(previous.sha(p) == h for p, h in self.watched.items()), "flow_input_changed")


def load_inputs(project, request_path, pin):
    request, _ = previous.pinned_json(request_path, pin)
    validate_request(request)
    folder = previous.resolve(project, request["original_one_state_experiment_directory"])
    old, manifest = one.load_experiment(project, folder, request["expected_original_one_state_experiment_sha256"])
    candidate = (Path(project)/Path(request["one_state_ar_result_zip"]).expanduser()).absolute()
    raw_paths = {s for row in old.temporal_inputs.previous_inputs.context.metadata["records"] for s in row["canonical_paths_private"]}
    require(str(candidate) not in raw_paths, "flow_known_raw_input_forbidden")
    path = previous.metadata_path(candidate)
    raw, rows, files = one_state_evidence(path, request["expected_one_state_ar_result_sha256"], old, manifest)
    require(all((folder/n.removeprefix("experiment/")).read_bytes() == b for n, b in files.items()), "flow_original_experiment_bytes_changed")
    inputs = FlowInputs(request, old, manifest, raw, rows,
                        {previous.metadata_path(request_path): pin, path: request["expected_one_state_ar_result_sha256"]})
    inputs.unchanged()
    return inputs


def marker(inputs, pin):
    old = inputs.one_state_manifest
    blocks = {b.outing_id: b for b in inputs.one_state_inputs.temporal_inputs.previous_inputs.blocks}
    layouts = []
    for fold in old["folds"]:
        training = [blocks[i] for i in fold["training_outings"]]
        y, x, o = joined_blocks(training)
        held = blocks[fold["validation_outing"]]
        require(PROTOCOL["sample_count"]*len(held.x)*21 <= CONFIGURATION["maximum_sample_values"], "flow_sampled_resource_bound")
        _, _, subset = calibration_conditions(training)
        layouts.append({"fold_id": fold["fold_id"], "training_rows": len(y), "training_sequences": len(o)-1,
                        "training_transitions": len(y)-len(o)+1, "validation_rows": len(held.x), "calibration_subset": subset})
    return {"contract_revision": REVISION, "status": "complete_matched_flow_experiment", "request_sha256": pin,
            "original_gaussian_experiment_sha256": old["original_gaussian_experiment_sha256"],
            "original_one_state_experiment_sha256": inputs.request["expected_original_one_state_experiment_sha256"],
            "one_state_ar_result_sha256": inputs.request["expected_one_state_ar_result_sha256"],
            "row_manifest_sha256": old["row_manifest_sha256"], "folds": old["folds"], "archives": old["archives"],
            "protocol": PROTOCOL, "adapter_layouts": layouts, "model_admission_authorized": False, "final_evaluation_authorized": False}


def load_experiment(project, folder, pin):
    folder = previous.metadata_path(folder)
    require(folder.is_dir() and {p.name for p in folder.iterdir()} == {"request.json", "experiment.json"}, "flow_exact_experiment_file_set")
    saved, _ = previous.pinned_json(folder/"experiment.json", pin)
    inputs = load_inputs(project, folder/"request.json", saved["request_sha256"])
    require(saved == marker(inputs, saved["request_sha256"]), "flow_cached_protocol_or_folds_changed")
    inputs.watched[folder/"experiment.json"] = pin
    return inputs, saved


def authorization_draft(pin):
    registry.digest(pin)
    return {"contract_revision": AUTHORIZATION_REVISION, "purpose": "fixed_two_flows_original_short_support_development_only",
            "experiment_sha256": pin, "attestations": dict.fromkeys(sorted(ATTESTATIONS), False)}


def require_authorization(value, pin):
    expected = authorization_draft(pin)
    expected["attestations"] = dict.fromkeys(sorted(ATTESTATIONS), True)
    require(type(value) is dict and value == expected and all(type(v) is bool and v for v in value["attestations"].values()),
            "flow_explicit_owner_authorization_required")


def design_sha256(manifest):
    return hashlib.sha256(previous.encoded({k: manifest[k] for k in
        ("original_gaussian_experiment_sha256", "one_state_ar_result_sha256", "protocol")})).hexdigest()
