"""Seal and replay matched development experiments without changing cohort roles."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from ..domain.artifact_registry import digest, require
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from . import artifact_registry as registry, locked_development as locked
from .numeric_export_inputs import read_bytes, read_json

REVISION = "v0.19.16-matched-development-experiment-2026-10-22-a1"
AUTHORIZATION_REVISION = "v0.19.16-development-gaussian-fit-2026-10-22-a1"
REQUEST_FIELDS = {"contract_revision", "cohort_directory", "expected_cohort_sha256", "original_registry_directory",
    "expected_original_registry_sha256", "descendants", "archive_sha256", "export_receipt", "expected_export_receipt_sha256",
    "experiment_directory", "training_directory", "authorization", "result_zip"}
ATTESTATIONS = {"explicit_development_gaussian_fit", "independent_protocol_review_and_ci_accepted",
                "final_outings_remain_unexposed", "fixed_protocol_and_preserve_failed_attempts"}
MODEL_NAMES = ("unconditional_gaussian", "conditional_gaussian")
PROTOCOL = {
    "population":"all_complete_feature_rows_of_all_locked_new_development_outings",
    "legacy_data":"retained_separately_not_automatically_pooled",
    "target":"signed_left_normal_SENSOR_EDP_minus_RLMB_H100_pseudo_residual_m",
    "stations_m":list(range(0,101,5)), "feature_names":list(BMW_CONDITION_FEATURE_NAMES),
    "models":list(MODEL_NAMES), "fit_weighting":"equal_frame_training",
    "conditional_mean":"training_standardized_minimum_norm_OLS_intercept_and_six_features",
    "covariance":"full_spatial_MLE_plus_1e-6_identity_in_training_standardized_units",
    "constant_columns":"exact_equality_training_only_mean_exact_value_scale_one",
    "folds":"leave_one_locked_development_outing_out",
    "primary_aggregation":"equal_outing_macro", "secondary_aggregation":"frame_weighted_diagnostic",
    "selection":"fixed_settings_no_hyperparameter_or_early_stopping_search",
    "sample_count":128, "sampling_seed":20261022,
    "scores":["physical_joint_nll","frame_energy","normalized_sequence_energy","marginal_crps",
              "sample_mean_rmse","station_bias_rmse","marginal_intervals_50_80_95",
              "profile_max_absolute_tail_brier_0.5_1_2m","retained_transition_lag_one"],
    "sequence_policy":"exact_original_conditioned_offsets_no_bridging_no_downsampling",
    "temporal_claim":"Gaussian_temporal_null_short_retained_sequences_only",
    "final_evaluation_authorized":False, "advanced_real_fit_authorized":False,
    "planner_evaluation_authorized":False, "raw_processing_authorized":False,
    "physical_ground_truth_claim":False,
}


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""):
            h.update(block)
    return h.hexdigest()


def metadata_path(path):
    p = Path(path).expanduser().absolute()
    require(".." not in p.parts and not str(p).lower().endswith((".mcap",".mcap.zst")),
            "experiment_raw_or_traversal_path_forbidden")
    require(p.parent.resolve() == p.parent and not p.is_symlink(), "experiment_metadata_symlink_forbidden")
    return p


def pinned_json(path, expected):
    p = metadata_path(path)
    value, pin, _ = read_json(p)
    require(pin == digest(expected), "experiment_input_digest_mismatch")
    raw,_ = read_bytes(p,64*1024**2)
    require(hashlib.sha256(raw).hexdigest() == pin,"experiment_input_changed")
    return value,raw


def resolve(project, value):
    require(type(value) is str and bool(value), "experiment_path_required")
    return metadata_path(Path(project)/Path(value).expanduser())


def validate_request(request):
    require(type(request) is dict and set(request) == REQUEST_FIELDS and request["contract_revision"] == REVISION,
            "experiment_closed_request_schema")
    for field in ("expected_cohort_sha256","expected_original_registry_sha256","expected_export_receipt_sha256"):
        digest(request[field])
    require(type(request["archive_sha256"]) is list and request["archive_sha256"] == sorted(set(request["archive_sha256"])))
    require(bool(request["archive_sha256"]) and type(request["descendants"]) is list, "experiment_explicit_selection_required")
    for pin in request["archive_sha256"]:
        digest(pin)
    for child in request["descendants"]:
        require(type(child) is dict and set(child) == {"directory","sha256"})
        digest(child["sha256"])


@dataclass(frozen=True)
class MatchedBlock:
    outing_id: str
    archive: object

    @property
    def y(self):
        return self.archive.matched_residuals_m

    @property
    def x(self):
        return self.archive.conditions

    @property
    def offsets(self):
        return self.archive.arrays["conditioned_sequence_offsets"]


@dataclass(frozen=True)
class ExperimentInputs:
    request: dict
    context: object
    blocks: tuple
    watched: dict
    file_sets: dict

    def unchanged(self):
        require(all(sha(p) == h for p,h in self.watched.items()), "experiment_input_changed")
        require(all(frozenset(root.rglob(pattern)) == paths
                    for (root,pattern),paths in self.file_sets.items()), "experiment_input_file_set_changed")


def load_inputs(project, request_path, expected_request_sha256):
    """Strict raw-free replay, complete development coverage, fixed receipt chain."""
    request, _ = pinned_json(request_path,expected_request_sha256)
    validate_request(request)
    path = lambda value:resolve(project,value)
    receipt, _ = pinned_json(path(request["export_receipt"]),request["expected_export_receipt_sha256"])
    require(receipt["status"] == "complete_locked_development_exports" and receipt["exit_code"] == 0
            and receipt["input_integrity_verified"] is True and not receipt["failures"]
            and receipt["stages"] and all(type(v) is int and v == 0 for v in receipt["stages"].values()),
            "experiment_successful_export_receipt_required")
    require(receipt["cohort_sha256"] == request["expected_cohort_sha256"] and
            receipt["original_registry_sha256"] == request["expected_original_registry_sha256"] and
            receipt["matched_archives_sha256"] == request["archive_sha256"], "experiment_receipt_selection_mismatch")
    chain = [locked.RegistryCheckpoint(path(c["directory"]),c["sha256"]) for c in request["descendants"]]
    require([c.sha256 for c in chain] == [c["sha256"] for c in receipt["descendants"]],
            "experiment_receipt_complete_chain_required")
    # Receipt paths are producer locators. Digest-bound local copies may live
    # elsewhere, enabling audited offline replay without touching owner paths.
    context = locked.load_context(cohort_directory=path(request["cohort_directory"]),
        expected_cohort_sha256=request["expected_cohort_sha256"], original_registry_directory=path(request["original_registry_directory"]),
        descendants=chain)
    require(context.original_metadata and context.cohort["registry_sha256"] == request["expected_original_registry_sha256"]
            and context.registry_sha256 == receipt["latest_registry_sha256"], "experiment_original_latest_registry_binding")
    locked.require_project_history(context,project)
    by_raw = {raw:o for o in context.cohort["outings"] for raw in o["raw_sha256"]}
    development = {raw for raw,o in by_raw.items() if o["cohort_role"] == "development"}
    blocks,seen,components = [],set(),set()
    for pin in request["archive_sha256"]:
        require(pin in context.datasets,"experiment_archive_missing")
        archive = context.datasets[pin]
        raws = list(archive.raw_sha256_by_recording.values())
        require(len(raws) == len(set(raws)) and not seen.intersection(raws)
                and set(raws) <= development,"experiment_duplicate_alias_or_non_development_archive")
        ids = {by_raw[r]["outing_id"] for r in raws}
        require(len(ids) == 1,"experiment_single_outing_archive_required")
        for raw in raws:
            component = context.graph[raw]["possible_component_sha256"]
            require(component not in components,"experiment_duplicate_possible_component")
            components.add(component)
        seen.update(raws)
        blocks.append(MatchedBlock(next(iter(ids)),archive))
    require(seen == development and len(blocks) >= 3 and len({b.outing_id for b in blocks}) == len(blocks),
            "experiment_all_locked_development_outings_required")
    # This initial adapter deliberately requires one archive per whole outing.
    # It never treats technical pieces of a session as separate inference units.
    watch = {metadata_path(request_path):expected_request_sha256,path(request["export_receipt"]):request["expected_export_receipt_sha256"]}
    file_sets = {}
    for folder in [path(request["cohort_directory"]),path(request["original_registry_directory"]),*[c.directory for c in chain]]:
        file_sets[(folder,"*")] = frozenset(folder.rglob("*"))
        for p in folder.rglob("*"):
            if p.is_file():
                watch[p] = sha(p)
    private = Path(project)/"data/catalog/private"
    file_sets[(private,"registry.json")] = frozenset(private.rglob("registry.json"))
    config = Path(project)/"config/private"
    file_sets[(config,"*.json")] = frozenset(config.rglob("*.json"))
    known = {e["sha256"] for e in context.metadata["events"] if e["kind"] == "authorization"}
    store = registry.ObjectStore()
    for record in context.metadata["records"]:
        store.raw_paths.update(record["canonical_paths_private"])
    for event in context.metadata["events"]:
        if event["kind"] in {"registration","archive"}:
            key = "source_specification.json" if event["kind"] == "registration" else "registration/source_specification.json"
            store.raw_paths.update(r["local_path_private"] for r in registry.decode(context.objects[event["files"][key]])["recordings"])
    for p in file_sets[(config,"*.json")]:
        h = store.add(p)
        value = registry.decode(store.objects[h])
        if isinstance(value,dict) and (value.get("purpose") == registry.numeric.AUTHORIZATION_PURPOSE
                or value.get("contract_revision") == registry.numeric.AUTHORIZATION_REVISION
                or p.name.startswith("numeric_export_authorization_")):
            if registry.authorization(value):
                require(h in known,"experiment_unregistered_new_numeric_consent")
        watch[p] = h
    result = ExperimentInputs(request,context,tuple(sorted(blocks,key=lambda b:b.outing_id)),watch,file_sets)
    result.unchanged()
    return result


def payloads(inputs, request_sha256):
    rows,archives = [],[]
    for block in inputs.blocks:
        a = block.archive.arrays
        indices = a["conditioned_profile_indices"]
        rows.append({"outing_id":block.outing_id,"archive_sha256":block.archive.summary_sha256,
            "conditioned_profile_indices":indices.tolist(), "conditioned_sequence_offsets":block.offsets.tolist(),
            **{name:a[name][indices].tolist() for name in ("recording_id","candidate_index","pair_index","estimate_message_index",
                "reference_message_index","estimate_source_time_ns_decimal","reference_source_time_ns_decimal")}})
        times = [int(s) for s in a["estimate_source_time_ns_decimal"][indices]]
        durations = [times[b-1]-times[a] for a,b in zip(block.offsets[:-1],block.offsets[1:])]
        archives.append({"outing_id":block.outing_id,"archive_sha256":block.archive.summary_sha256,
            "geometry_vectors":len(block.archive.geometry_residuals_m),"complete_feature_rows":len(block.x),
            "sequences":len(block.offsets)-1,"valid_transitions":len(block.x)-len(block.offsets)+1,
            "maximum_complete_sequence_duration_ns":max(durations),"maximum_complete_sequence_frames":int(np.diff(block.offsets).max())})
    ids = [b.outing_id for b in inputs.blocks]
    folds = [{"fold_id":"hold_out_"+held,"validation_outing":held,"training_outings":[i for i in ids if i != held]}
             for held in ids]
    manifest = {"contract_revision":REVISION,"status":"complete_matched_development_experiment",
        "request_sha256":request_sha256,"original_cohort_sha256":inputs.context.cohort_sha256,
        "original_registry_sha256":inputs.request["expected_original_registry_sha256"],
        "latest_registry_sha256":inputs.context.registry_sha256,"protocol":PROTOCOL,
        "archives":archives,"folds":folds,"row_manifest_sha256":hashlib.sha256(encoded(rows)).hexdigest(),
        "model_admission_authorized":False,"final_evaluation_authorized":False,
        "identity_evidence_quality":"owner_declared_not_independently_verified",
        "final_evidence_scope":"retained_supplied_registry_history_only"}
    return manifest,rows


def load_experiment(project, directory, expected_experiment_sha256):
    folder = metadata_path(directory)
    require(folder.is_dir() and {p.name for p in folder.iterdir()} == {"experiment.json","row_manifest.json","request.json"},
            "experiment_exact_file_set")
    stored,_ = pinned_json(folder/"experiment.json",expected_experiment_sha256)
    inputs = load_inputs(project,folder/"request.json",stored["request_sha256"])
    expected,rows = payloads(inputs,stored["request_sha256"])
    require(stored == expected and (folder/"row_manifest.json").read_bytes() == encoded(rows),
            "experiment_cached_rows_folds_or_protocol_mismatch")
    inputs.watched[folder/"experiment.json"] = expected_experiment_sha256
    inputs.watched[folder/"row_manifest.json"] = expected["row_manifest_sha256"]
    return inputs,stored


def authorization_draft(experiment_sha256):
    digest(experiment_sha256)
    return {"contract_revision":AUTHORIZATION_REVISION,"purpose":"fixed_gaussian_pair_development_cross_validation_only",
        "experiment_sha256":experiment_sha256,"attestations":dict.fromkeys(sorted(ATTESTATIONS),False)}


def require_authorization(value, experiment_sha256):
    expected = authorization_draft(experiment_sha256)
    expected["attestations"] = dict.fromkeys(sorted(ATTESTATIONS),True)
    require(type(value) is dict and value == expected and all(type(v) is bool and v for v in value["attestations"].values()),
            "experiment_explicit_owner_gaussian_authorization_required")
