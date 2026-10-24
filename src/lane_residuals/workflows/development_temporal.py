"""A separately adopted matched memory control with durable attempt claims."""

from datetime import datetime, timezone
import os
from pathlib import Path

import numpy as np

from ..domain.artifact_registry import require
from ..io import artifact_registry as registry, development_experiment as previous, development_temporal as contract
from ..modeling.matched_evaluation import evaluate_matched_samples
from ..modeling.matched_stationary_ar import MODEL_NAME, StationaryAR, fit_stationary_ar
from .development_experiment import source_guard, project_lock, protected_inputs
from .locked_development_export import package, write

MARKERS = ("experiment.json","run_receipt.json","cohort_manifest.json","session_declaration.json",
           "objects","authorization.json","request.json","row_manifest.json","attempt_claim.json")


def destination(project, value, protected, kind):
    p = previous.resolve(project,value)
    registry.separate_output(p,protected)
    require(not os.path.lexists(p),"temporal_new_output_required_preserve_existing")
    for ancestor in (p,*p.parents):
        require(not any(os.path.lexists(ancestor/n) for n in MARKERS),"temporal_output_inside_partial_or_immutable_evidence")
    if kind == "zip":
        require(p.suffix == ".zip" and p.parent.is_dir() and p.parent.resolve() == p.parent,
                "temporal_existing_regular_zip_parent_required")
        require(not os.path.lexists(p.with_suffix(".zip.partial")),"temporal_partial_zip_exists_preserve_attempt")
    else:
        prefix = Path(project)/("outputs/experiments/private" if kind == "experiment" else "outputs/models/private")
        require(p.is_relative_to(prefix) and p != prefix,"temporal_private_output_location")
    if p.is_relative_to(Path(project)):
        import subprocess
        require(subprocess.run(["git","-C",str(project),"check-ignore","--no-index","--quiet",str(p)],
            capture_output=True).returncode == 0,"temporal_output_must_be_gitignored")
    return p


def protected(project, request, request_path):
    folder = previous.resolve(project,request["original_experiment_directory"])
    marker,_ = previous.pinned_json(folder/"experiment.json",request["expected_original_experiment_sha256"])
    old_request,_ = previous.pinned_json(folder/"request.json",marker["request_sha256"])
    return [folder,previous.resolve(project,request["gaussian_result_zip"]),
            previous.metadata_path(request_path),*protected_inputs(project,old_request)]


def ledger_path(project, manifest):
    root = previous.resolve(project,"outputs/fit_ledgers/private/matched_temporal_v01917")
    path = root/manifest["original_experiment_sha256"]/(contract.design_sha256(manifest)+".started.json")
    previous.metadata_path(path)
    registry.separate_output(root,[previous.resolve(project,"data/catalog/private")])
    require(not os.path.lexists(path),"temporal_design_already_attempted_preserve_ledger")
    return path


def prepare(*,project,request_path,expected_request_sha256,expected_tree,expected_runtime):
    project = Path(project).absolute()
    source_guard(project,expected_tree,expected_runtime)
    request,raw = previous.pinned_json(request_path,expected_request_sha256)
    contract.validate_request(request)
    guards = protected(project,request,request_path)
    output = destination(project,request["experiment_directory"],guards,"experiment")
    training = destination(project,request["training_directory"],guards+[output],"training")
    destination(project,request["result_zip"],guards+[output,training],"zip")
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs = contract.load_inputs(project,request_path,expected_request_sha256)
        manifest = contract.marker(inputs,expected_request_sha256)
        ledger_path(project,manifest)
        inputs.unchanged()
        output.mkdir(parents=True,exist_ok=False)
        write(output/"request.json",raw)
        inputs.unchanged()
        source_guard(project,expected_tree,expected_runtime)
        write(output/"experiment.json",manifest)
    return manifest,previous.sha(output/"experiment.json")


def _receipt(output, receipt, *, replace_unpublished=False):
    """Only the current attempt's unpublished receipt may be finalized on failure."""
    path = output/"run_receipt.json"
    if not replace_unpublished or not path.exists():
        write(path,receipt)
        return
    require(path.is_file() and not path.is_symlink(),"temporal_regular_owned_receipt_required")
    replacement = output/"run_receipt.packaging_failure.json"
    write(replacement,receipt)
    os.replace(replacement,path)
    registry._fsync_directory(output)


def train(*,project,experiment_directory,expected_experiment_sha256,authorization_path,
          expected_authorization_sha256,expected_tree,expected_runtime):
    project = Path(project).absolute()
    source = source_guard(project,expected_tree,expected_runtime)
    folder = previous.metadata_path(experiment_directory)
    manifest,_ = previous.pinned_json(folder/"experiment.json",expected_experiment_sha256)
    auth,auth_raw = previous.pinned_json(authorization_path,expected_authorization_sha256)
    contract.require_authorization(auth,expected_experiment_sha256)
    request,_ = previous.pinned_json(folder/"request.json",manifest["request_sha256"])
    contract.validate_request(request)
    require(previous.resolve(project,request["experiment_directory"]) == folder and
            previous.resolve(project,request["authorization"]) == previous.metadata_path(authorization_path),
            "temporal_issued_locations_mismatch")
    guards = protected(project,request,folder/"request.json")+[folder,previous.metadata_path(authorization_path)]
    output = destination(project,request["training_directory"],guards,"training")
    result = destination(project,request["result_zip"],guards+[output],"zip")
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs,manifest = contract.load_experiment(project,folder,expected_experiment_sha256)
        require(previous.sha(authorization_path) == expected_authorization_sha256,"temporal_authorization_changed")
        inputs.watched[previous.metadata_path(authorization_path)] = expected_authorization_sha256
        claim = ledger_path(project,manifest)
        claim.parent.mkdir(parents=True,exist_ok=True)
        import subprocess
        require(subprocess.run(["git","-C",str(project),"check-ignore","--no-index","--quiet",str(claim)],
            capture_output=True).returncode == 0,"temporal_private_ledger_must_be_ignored")
        inputs.unchanged()
        write(claim,{"contract_revision":contract.REVISION,"status":"claimed_do_not_retry",
            "design_sha256":contract.design_sha256(manifest),"experiment_sha256":expected_experiment_sha256,
            "original_experiment_sha256":manifest["original_experiment_sha256"],
            "gaussian_result_sha256":manifest["gaussian_result_sha256"],"source":source,
            "training_directory":str(output),"result_zip":str(result),
            "claimed_at_utc":datetime.now(timezone.utc).isoformat()})
        inputs.watched[claim] = previous.sha(claim)
        # A hard kill from this point has an immutable trace even without a receipt.
        output.mkdir(parents=True,exist_ok=False)
        receipt = {"contract_revision":contract.REVISION,"status":"failed_preserve_attempt","exit_code":2,
            "source":source,"experiment_sha256":expected_experiment_sha256,
            "gaussian_result_sha256":manifest["gaussian_result_sha256"],
            "authorization_sha256":expected_authorization_sha256,"attempt_claim_sha256":previous.sha(claim),
            "attempt_claim_path_private":str(claim),"fit_attempted":False,
            "development_stationary_ar_fit_authorized":True,"advanced_real_fit_authorized":False,
            "final_evaluation_authorized":False,"raw_payload_opened":False,
            "baseline_refitted":False,"input_integrity_verified":False,"completed":[],"failures":[],
            "started_at_utc":datetime.now(timezone.utc).isoformat()}
        stage = "preserve_authorization"
        by_id = {b.outing_id:b for b in inputs.previous_inputs.blocks}
        try:
            write(output/"authorization.json",auth_raw)
            write(output/"attempt_claim.json",claim.read_bytes())
            write(output/"accepted_gaussian_result.zip",inputs.gaussian_raw)
            for index,fold in enumerate(manifest["folds"]):
                stage = fold["fold_id"]
                inputs.unchanged()
                require(source_guard(project,expected_tree,expected_runtime) == source,"temporal_runtime_changed")
                base,base_pin = inputs.states[fold["fold_id"]]["conditional_gaussian"]
                training = [(by_id[i].y,by_id[i].x,by_id[i].offsets) for i in fold["training_outings"]]
                print("Fitting stationary AR control held-out",fold["validation_outing"],flush=True)
                receipt["fit_attempted"] = True
                state = fit_stationary_ar(base,training)
                model_file = output/(stage+"_model.json")
                write(model_file,{"contract_revision":contract.REVISION,"experiment_sha256":expected_experiment_sha256,
                    "fold":fold,"base_conditional_model_sha256":base_pin,"state":state.to_dict()})
                saved,_ = previous.pinned_json(model_file,previous.sha(model_file))
                restored = StationaryAR.from_dict(saved["state"])
                held = by_id[fold["validation_outing"]]
                seed = contract.PROTOCOL["sampling_seed"]+index
                draws = restored.sample(held.x,held.offsets,sample_count=contract.PROTOCOL["sample_count"],seed=seed)
                metrics = evaluate_matched_samples(held.y,held.offsets,draws)
                metrics["mean_physical_joint_nll"] = float(-base.logpdf(held.x,held.y).mean())
                history_nll = float(-restored.logpdf_observed_history(held.x,held.y,held.offsets).mean())
                require(np.isfinite(history_nll),"temporal_nonfinite_history_density")
                result_row = {"model":MODEL_NAME,"fold":fold,"sampling_seed":seed,"metrics":metrics,
                    "mean_observed_history_joint_nll_per_frame":history_nll,
                    "single_frame_marginal_nll_unchanged":True,
                    "marginal_analytic_mean_rmse_m":float(np.sqrt(np.square(base.predict_mean(held.x)-held.y).mean())),
                    "base_conditional_model_sha256":base_pin,"model_sha256":previous.sha(model_file),
                    "training_rows":base.training_rows,"training_transitions":state.training_transitions,
                    "phi":state.phi,"phi_at_fixed_cap":bool(abs(state.phi) == .99),
                    "validation_archive_sha256":held.archive.summary_sha256}
                write(output/(stage+"_scores.json"),result_row)
                receipt["completed"].append(result_row)
            receipt.update(status="complete_matched_stationary_ar_cross_validation",exit_code=0,
                comparison=contract.aggregate(inputs.baseline_results+receipt["completed"]),
                paired_temporal_comparison=contract.paired_temporal_comparison(inputs.baseline_results,receipt["completed"]),
                marginal_comparison_rule="same_frame_distributions_finite_sample_metric_differences_not_predictive_improvement")
        except (Exception,KeyboardInterrupt) as exc:
            receipt["exit_code"] = 130 if isinstance(exc,KeyboardInterrupt) else 2
            receipt["failures"].append({"stage":stage,"failure_code":getattr(exc,"code",type(exc).__name__)})
        try:
            inputs.unchanged()
            require(source_guard(project,expected_tree,expected_runtime) == source,"temporal_runtime_changed")
            receipt["input_integrity_verified"] = True
        except (Exception,KeyboardInterrupt) as exc:
            receipt.update(status="failed_preserve_attempt",exit_code=2)
            receipt["failures"].append({"stage":"postflight","failure_code":getattr(exc,"code",type(exc).__name__)})
        receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["output_files_sha256"] = {p.name:previous.sha(p) for p in sorted(output.iterdir()) if p.is_file()}
        _receipt(output,receipt)
        partial = result.with_suffix(".zip.partial")
        try:
            package(partial,[(output,"training"),(folder,"experiment")])
            with partial.open("rb") as stream:
                os.fsync(stream.fileno())
            os.link(partial,result)  # exclusive atomic publication, never replace an existing result
            registry._fsync_directory(result.parent)
        except (Exception,KeyboardInterrupt) as exc:
            receipt.update(status="failed_packaging_preserve_attempt",exit_code=130 if isinstance(exc,KeyboardInterrupt) else 2)
            receipt["failures"].append({"stage":"packaging","failure_code":getattr(exc,"code",type(exc).__name__)})
            if not os.path.lexists(result):
                _receipt(output,receipt,replace_unpublished=True)
            print("Packaging/finalization failed; preserve claim, local receipt, partial ZIP and terminal evidence.",flush=True)
            return receipt["exit_code"]
        try:
            partial.unlink()  # only this run's fully published temporary link
        except OSError:
            print("Published result; temporary duplicate link retained:",partial,flush=True)
        print("Result ZIP:",result,"SHA-256:",previous.sha(result),flush=True)
        return receipt["exit_code"]
