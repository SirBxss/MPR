"""Pinned preparation and explicitly adopted Gaussian development experiments."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import subprocess

import numpy as np

from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as contract
from ..modeling.matched_gaussian import MatchedGaussian, fit_matched_gaussian
from ..modeling.matched_evaluation import evaluate_matched_samples
from .locked_development_export import package, write
from .recording_ingestion import _runtime


def source_guard(project, expected_tree, expected_runtime):
    project = Path(project).absolute()
    def git(*args):
        return subprocess.check_output(["git","-C",str(project),*args],text=True).strip()
    require(Path(__file__).resolve().is_relative_to(project/"src/lane_residuals"),
            "experiment_import_must_resolve_inside_selected_project")
    runtime = _runtime(include_compression=True)
    require(git("rev-parse","HEAD^{tree}") == expected_tree and not git("status","--porcelain")
            and runtime["runtime_source_sha256"] == expected_runtime,"experiment_reviewed_clean_source_required")
    return {"consumer_git_commit":git("rev-parse","HEAD"),"consumer_git_tree":expected_tree,
            "consumer_runtime_source_sha256":expected_runtime,"consumer_runtime_versions":runtime["runtime_versions"]}


def destination(project, output, protected, *, kind):
    p = contract.resolve(project,output)
    registry.separate_output(p,protected)
    require(not os.path.lexists(p),"experiment_new_output_required_preserve_existing")
    for ancestor in (p,*p.parents):
        require(not any(os.path.lexists(ancestor/name) for name in
            ("experiment.json","run_receipt.json","cohort_manifest.json","session_declaration.json","objects")),
            "experiment_output_inside_immutable_or_partial_evidence")
    if kind != "zip":
        prefix = "outputs/experiments/private" if kind == "experiment" else "outputs/models/private"
        require(p.is_relative_to(Path(project)/prefix) and p != Path(project)/prefix,"experiment_private_output_location")
        require(subprocess.run(["git","-C",str(project),"check-ignore","--no-index","--quiet",str(p)],
            capture_output=True).returncode == 0,"experiment_output_must_be_gitignored")
    else:
        require(p.suffix == ".zip","experiment_zip_output_required")
        if p.is_relative_to(Path(project)):
            require(subprocess.run(["git","-C",str(project),"check-ignore","--no-index","--quiet",str(p)],
                capture_output=True).returncode == 0,"experiment_result_inside_project_must_be_gitignored")
    return p


def protected_inputs(project, request):
    return [contract.resolve(project,request[k]) for k in ("cohort_directory","original_registry_directory","export_receipt")]+[
        contract.resolve(project,c["directory"]) for c in request["descendants"]]


@contextmanager
def project_lock(project):
    private = Path(project)/"data/catalog/private"
    require(private.is_dir() and private.resolve() == private,"experiment_private_registry_root_required")
    fd = os.open(private/".registry-write.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode),"experiment_regular_lock_required")
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            require(False,"experiment_another_registry_operation_running")
        yield
    finally:
        os.close(fd)


def prepare(*, project, request_path, expected_request_sha256, expected_tree, expected_runtime):
    """Freeze row identities and folds. No transformation or model is fitted."""
    project = Path(project).absolute()
    source_guard(project,expected_tree,expected_runtime)
    request,request_raw = contract.pinned_json(request_path,expected_request_sha256)
    contract.validate_request(request)
    protected = protected_inputs(project,request)+[Path(request_path).absolute()]
    output = destination(project,request["experiment_directory"],protected,kind="experiment")
    # Future fit destinations are part of this sealed request, never CLI overrides.
    training = destination(project,request["training_directory"],protected+[output],kind="training")
    destination(project,request["result_zip"],protected+[output,training],kind="zip")
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs = contract.load_inputs(project,request_path,expected_request_sha256)
        manifest,rows = contract.payloads(inputs,expected_request_sha256)
        inputs.unchanged()
        output.mkdir(parents=True,exist_ok=False)
        write(output/"request.json",request_raw)
        write(output/"row_manifest.json",rows)
        # Completion marker comes last, after input and source rechecks.
        inputs.unchanged()
        source_guard(project,expected_tree,expected_runtime)
        write(output/"experiment.json",manifest)
    return manifest,contract.sha(output/"experiment.json")


def _aggregate(results):
    scores = ("mean_physical_joint_nll","sample_mean_rmse_m","mean_energy_score_m",
              "mean_normalized_sequence_energy_score_m","mean_marginal_crps_m")
    output = {}
    for model in contract.MODEL_NAMES:
        selected = [r for r in results if r["model"] == model]
        weights = [r["metrics"]["frame_count"] for r in selected]
        pooled = {k:float(np.average([r["metrics"][k] for r in selected],weights=(
            [r["metrics"]["sequence_count"] for r in selected] if k == "mean_normalized_sequence_energy_score_m" else weights))) for k in scores}
        pooled["sample_mean_rmse_m"] = float(np.sqrt(np.average(
            [r["metrics"]["sample_mean_rmse_m"]**2 for r in selected],weights=weights)))
        output[model] = {"outings":len(selected),"frames":sum(weights),
            "equal_outing_macro":{k:float(np.mean([r["metrics"][k] for r in selected])) for k in scores},
            "pooled_diagnostic":pooled,
            "equal_outing_macro_interval_coverage":{level:float(np.mean([r["metrics"]["intervals"][level]["coverage"] for r in selected]))
                for level in ("0.5","0.8","0.95")},
            "equal_outing_macro_tail_brier":{level:float(np.mean([r["metrics"]["profile_max_absolute_tail"][level]["brier_score"] for r in selected]))
                for level in ("0.5","1.0","2.0")}}
    return output


def train(*, project, experiment_directory, expected_experiment_sha256, authorization_path,
          expected_authorization_sha256, expected_tree, expected_runtime):
    """Run the fixed Gaussian pair once; preserve every started/failed attempt."""
    project = Path(project).absolute()
    source = source_guard(project,expected_tree,expected_runtime)
    folder = contract.metadata_path(experiment_directory)
    manifest,_ = contract.pinned_json(folder/"experiment.json",expected_experiment_sha256)
    auth,auth_raw = contract.pinned_json(authorization_path,expected_authorization_sha256)
    contract.require_authorization(auth,expected_experiment_sha256)
    request,_ = contract.pinned_json(folder/"request.json",manifest["request_sha256"])
    contract.validate_request(request)
    require(contract.resolve(project,request["experiment_directory"]) == folder and
            contract.resolve(project,request["authorization"]) == contract.metadata_path(authorization_path),
            "experiment_issued_locations_mismatch")
    protected = protected_inputs(project,request)+[folder,contract.metadata_path(authorization_path)]
    output = destination(project,request["training_directory"],protected,kind="training")
    result_zip = destination(project,request["result_zip"],protected+[output],kind="zip")
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs,manifest = contract.load_experiment(project,folder,expected_experiment_sha256)
        require(contract.sha(authorization_path) == expected_authorization_sha256,"experiment_authorization_changed")
        inputs.watched[contract.metadata_path(authorization_path)] = expected_authorization_sha256
        inputs.unchanged()
        output.mkdir(parents=True,exist_ok=False)
        receipt = {"contract_revision":contract.REVISION,"status":"failed_preserve_attempt","exit_code":2,
            "started_at_utc":datetime.now(timezone.utc).isoformat(),"experiment_sha256":expected_experiment_sha256,
            "authorization_sha256":expected_authorization_sha256,"source":source,"fit_attempted":False,
            "development_gaussian_fit_authorized":True,"advanced_real_fit_authorized":False,
            "final_evaluation_authorized":False,"raw_payload_opened":False,"input_integrity_verified":False,
            "failures":[],"completed":[]}
        stage = "preserve_authorization"
        by_id = {b.outing_id:b for b in inputs.blocks}
        try:
            write(output/"authorization.json",auth_raw)
            for fold_index,fold in enumerate(manifest["folds"]):
                stage = fold["fold_id"]+"_preflight"
                inputs.unchanged()
                require(source_guard(project,expected_tree,expected_runtime) == source,"experiment_runtime_changed")
                training = [by_id[i] for i in fold["training_outings"]]
                validation = by_id[fold["validation_outing"]]
                y = np.concatenate([b.y for b in training])
                x = np.concatenate([b.x for b in training])
                for mode in contract.MODEL_NAMES:
                    stage = fold["fold_id"]+"_"+mode
                    inputs.unchanged()
                    require(source_guard(project,expected_tree,expected_runtime) == source,"experiment_runtime_changed")
                    print("Fitting",mode,"held-out",fold["validation_outing"],flush=True)
                    receipt["fit_attempted"] = True
                    model = fit_matched_gaussian(y,x,mode=mode)
                    model_file = output/(stage+"_model.json")
                    write(model_file,{"contract_revision":contract.REVISION,"experiment_sha256":expected_experiment_sha256,
                        "fold":fold,"state":model.to_dict()})
                    # Replay the actual persisted state before scoring; no pickle.
                    saved,_ = contract.pinned_json(model_file,contract.sha(model_file))
                    restored = MatchedGaussian.from_dict(saved["state"])
                    seed = contract.PROTOCOL["sampling_seed"]+fold_index
                    draws = restored.sample(validation.x,sample_count=contract.PROTOCOL["sample_count"],seed=seed)
                    metrics = evaluate_matched_samples(validation.y,validation.offsets,draws)
                    metrics["mean_physical_joint_nll"] = float(-restored.logpdf(validation.x,validation.y).mean())
                    require(np.isfinite(metrics["mean_physical_joint_nll"]),"experiment_nonfinite_density")
                    result = {"model":mode,"fold":fold,"sampling_seed":seed,"metrics":metrics,
                        "training_rows":len(y),"model_sha256":contract.sha(model_file),
                        "training_outing_count":len(training),"validation_archive_sha256":validation.archive.summary_sha256}
                    write(output/(stage+"_scores.json"),result)
                    receipt["completed"].append(result)
            receipt.update(status="complete_development_gaussian_cross_validation",exit_code=0,
                           aggregate=_aggregate(receipt["completed"]))
        except (Exception,KeyboardInterrupt) as exc:
            receipt["exit_code"] = 130 if isinstance(exc,KeyboardInterrupt) else 2
            receipt["failures"].append({"stage":stage,"failure_code":getattr(exc,"code",type(exc).__name__)})
        try:
            inputs.unchanged()
            require(source_guard(project,expected_tree,expected_runtime) == source,"experiment_runtime_changed")
            receipt["input_integrity_verified"] = True
        except (Exception,KeyboardInterrupt) as exc:
            receipt.update(status="failed_preserve_attempt",exit_code=2)
            receipt["failures"].append({"stage":"postflight","failure_code":getattr(exc,"code",type(exc).__name__)})
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["output_files_sha256"] = {p.name:contract.sha(p) for p in sorted(output.iterdir()) if p.is_file()}
        write(output/"run_receipt.json",receipt)
        package(result_zip,[(output,"training"),(folder,"experiment")])
        print("Result ZIP:",result_zip,"SHA-256:",contract.sha(result_zip),flush=True)
        return receipt["exit_code"]
