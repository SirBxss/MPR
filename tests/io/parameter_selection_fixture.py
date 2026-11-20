"""Entirely synthetic frozen six-model result and metadata for consumer tests."""

from dataclasses import replace
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

import numpy as np

from lane_residuals.domain import planner_parameter_selection as policy, temporal_planner_pilot as temporal
from lane_residuals.io import development_experiment as original, development_flow as flow_io
from lane_residuals.io.planner_parameter_selection import FrozenFamily
from lane_residuals.io.temporal_planner_pilot import TemporalModels
from lane_residuals.modeling.aiohmm import AutoregressiveInputOutputHMM
from lane_residuals.modeling.matched_flow import MatchedFlow, CONFIGURATION
from lane_residuals.modeling.matched_flow_evaluation import comparison, paired_comparisons
from lane_residuals.modeling.matched_gaussian import MatchedGaussian
from lane_residuals.modeling.matched_one_state_ar import OneStateAR
from lane_residuals.modeling.matched_stationary_ar import StationaryAR
from tests.modeling import test_matched_one_state_ar as fixture


def pack(files: dict) -> bytes:
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in files.items():
            z.writestr(name,value if isinstance(value,bytes) else original.encoded(value))
        z.writestr("SHA256SUMS","".join(hashlib.sha256(z.read(n)).hexdigest()+"  "+n+"\n" for n in files))
    return stream.getvalue()


def frozen_family() -> FrozenFamily:
    fixture.MatchedOneStateTests.setUpClass()
    base=replace(fixture.MatchedOneStateTests.state.transform_source,training_rows=216)
    payload=fixture.MatchedOneStateTests.state.model.to_dict()
    payload["training_frame_count"]=216
    payload["training_sequence_count"]=72
    one=OneStateAR(base,AutoregressiveInputOutputHMM.from_dict(payload))
    stationary=StationaryAR(base,.8,144,(100.,100.,80.,144*21))
    uncond=MatchedGaussian("unconditional_gaussian",base.residual_mean,base.residual_scale,np.zeros(6),np.ones(6),
        np.zeros(21),np.zeros((6,21)),np.eye(21),216,1)
    flows={mode:MatchedFlow(mode,base.residual_mean,base.residual_scale,base.condition_mean,base.condition_scale,
        np.zeros((22 if mode=="unconditional" else 50,64)),np.zeros(64),np.zeros((64,21)),np.zeros(21),
        tuple([0.]*100),216,72,1) for mode in ("unconditional","conditional")}
    temporal_models=TemporalModels(base,stationary,one,dict(conditional_gaussian="a"*64,stationary_ar="b"*64,one_state_ar="c"*64))
    return FrozenFamily(uncond,temporal_models,flows,dict(unconditional_gaussian="d"*64,**temporal_models.hashes,
        unconditional_flow="e"*64,unconditional_flow_solver="f"*64,conditional_flow="0"*64,conditional_flow_solver="1"*64))


def data(root: Path, family: FrozenFamily):
    ids=["synthetic_"+str(i) for i in range(7)]
    folds=[dict(fold_id="hold_"+oid,validation_outing=oid,training_outings=[i for i in ids if i!=oid]) for oid in ids]
    blocks=[]
    for j,oid in enumerate(ids):
        n=36
        indices=np.arange(n,dtype=np.int64)
        arrays=dict(conditioned_profile_indices=indices,stations_m=np.arange(0,101,5),
            recording_id=np.full(n,"recording_"+str(j)),
            estimate_source_time_ns_decimal=np.array([str(10**17+(i//3)*1_000_000_000+(i%3)*100_000_000) for i in indices]),
            reference_source_time_ns_decimal=np.array([str(10**17+(i//3)*1_000_000_000+(i%3)*100_000_000) for i in indices]),
            **{key:indices+indices//3 for key in ("candidate_index","pair_index","estimate_message_index","reference_message_index")})
        x=np.zeros((n,6));x[:,0]=20.
        blocks.append(SimpleNamespace(outing_id=oid,y=np.random.default_rng(j).normal(0,.01,(n,21)),x=x,
            offsets=np.arange(0,n+1,3),archive=SimpleNamespace(arrays=arrays,summary_sha256=str(j)*64,
                            raw_sha256_by_recording={"recording_"+str(j):"2"*64})))
    inputs=SimpleNamespace(blocks=blocks,watched={},unchanged=Mock(),request=dict(
        cohort_directory=str(root/"cohort"),original_registry_directory=str(root/"registry"),export_receipt=str(root/"export"),descendants=[]))
    marker=dict(folds=folds,contract_revision="synthetic_original")
    families={f["fold_id"]:family for f in folds}
    old_folds=[]; all_records={}; supports={}
    for block,fold in zip(blocks,folds):
        rows,_,records,support=temporal.prepare(block,fold)
        all_records[block.outing_id]=records;supports[block.outing_id]=support
        old_folds.append(dict(fold=fold,expected_support=support,
            scenario_rows_sha256=hashlib.sha256(original.encoded(rows)).hexdigest(),saved_model_sha256=family.temporal.hashes))
    plan=dict(revision=policy.REVISION,protocol=policy.PROTOCOL,flow_experiment_directory="flow_experiment",
        flow_experiment_sha256="2"*64,flow_result_sha256="3"*64,accepted_temporal_result_sha256="4"*64,
        accepted_temporal_manifest_sha256="5"*64,accepted_temporal_source=dict(consumer_git_commit="synthetic",
            consumer_git_tree="synthetic",consumer_runtime_source_sha256="synthetic"),folds=[])
    for fold,block in zip(folds,blocks):
        descriptors=policy.context_descriptors(all_records,fold["training_outings"])
        kept=[r for r in all_records[block.outing_id] if r["status"]=="eligible" and r["frame_count"]>=3]
        plan["folds"].append(dict(fold=fold,saved_model_sha256=family.hashes,
            validation_archive_sha256=block.archive.summary_sha256,original_support=supports[block.outing_id],
            training_contexts=descriptors,selection_frame_count=sum(r["frame_count"] for r in descriptors),training_pool_rows=216,
            held_sequence_indices=[r["sequence_index"] for r in kept],held_frame_count=sum(r["frame_count"] for r in kept),
            held_transition_count=sum(r["frame_count"]-1 for r in kept)))
    native=SimpleNamespace(watched={},unchanged=Mock(),one_state_inputs=SimpleNamespace(watched={},temporal_inputs=SimpleNamespace(
        watched={},previous_inputs=inputs,previous_manifest=marker)))
    return SimpleNamespace(ids=ids,blocks=blocks,folds=folds,inputs=inputs,marker=marker,families=families,
                           checkpoint=dict(folds=old_folds),plan=plan,native=native)


def flow_return(bundle, family: FrozenFamily):
    """Construct a complete synthetic return for the result reader, not a fit."""
    original_marker=bundle.marker
    marker=dict(folds=bundle.folds,original_gaussian_experiment_sha256=hashlib.sha256(original.encoded(original_marker)).hexdigest(),
        one_state_ar_result_sha256="6"*64,protocol=flow_io.PROTOCOL)
    one_files={};stationary_files={}
    for fold in bundle.folds:
        name="training/"+fold["fold_id"]+"_model.json"
        one_files[name]=dict(fold=fold,base_conditional_transform_source_sha256="a"*64,state=family.temporal.one_state.to_dict())
        stationary_files[name]=dict(fold=fold,base_conditional_model_sha256="a"*64,state=family.temporal.stationary.to_dict())
    one_raw,stationary_raw=pack(one_files),pack(stationary_files)
    marker["one_state_ar_result_sha256"]=hashlib.sha256(one_raw).hexdigest()
    pin=hashlib.sha256(original.encoded(marker)).hexdigest()
    auth=flow_io.authorization_draft(pin)
    auth["attestations"]={k:True for k in auth["attestations"]}
    files={"experiment/experiment.json":marker,"experiment/request.json":{"synthetic":True},
           "training/authorization.json":auth,"training/accepted_one_state_ar_result.zip":one_raw}
    auth_pin=hashlib.sha256(original.encoded(auth)).hexdigest()
    source=dict(consumer_git_commit="synthetic",consumer_git_tree="synthetic",consumer_runtime_source_sha256="synthetic")
    files["training/attempt_claim.json"]=dict(status="claimed_do_not_retry",source=source,experiment_sha256=pin,
        authorization_sha256=auth_pin,design_sha256=flow_io.design_sha256(marker),
        one_state_ar_result_sha256=marker["one_state_ar_result_sha256"],original_gaussian_experiment_sha256=marker["original_gaussian_experiment_sha256"])
    completed=[]
    for i,fold in enumerate(bundle.folds):
        for mode in ("unconditional","conditional"):
            stem="training/"+fold["fold_id"]+"_"+mode
            fit=dict(configuration=CONFIGURATION,epochs_completed=100,transform_refitted=False)
            saved=dict(fold=fold,contract_revision=flow_io.REVISION,experiment_sha256=pin,
                base_conditional_transform_source_sha256="a"*64,state=family.flows[mode].to_dict(),fit_report=fit)
            calibration=dict(configuration=flow_io.CALIBRATION,passed=True,solver="heun",selected_steps=128)
            files[stem+"_model.json"],files[stem+"_calibration.json"]=saved,calibration
            metrics=dict(frame_count=36,sequence_count=12,mean_normalized_sequence_energy_score_m=1.,
                median_absolute_lag_one_correlation_error=.1,intervals={s:dict(coverage=.5,mean_width_m=1.) for s in ("0.5","0.8","0.95")},
                profile_max_absolute_tail={s:dict(brier_score=.2) for s in ("0.5","1.0","2.0")})
            score=dict(fold=fold,model="matched_"+mode+"_flow",base_conditional_transform_source_sha256="a"*64,
                training_rows=216,training_sequences=72,sampling_seed=flow_io.PROTOCOL["sampling_seed"]+i,
                model_sha256=hashlib.sha256(original.encoded(saved)).hexdigest(),solver_calibration_sha256=hashlib.sha256(original.encoded(calibration)).hexdigest(),
                solver="heun",solver_steps=128,validation_archive_sha256=str(i)*64,metrics=metrics,fit_report=fit)
            files[stem+"_scores.json"]=score;completed.append(score)
    previous=[]
    summary=comparison(previous+completed)
    files["training/comparison.json"]=dict(models=summary,paired_comparisons=paired_comparisons(previous,completed))
    receipt=dict(contract_revision=flow_io.REVISION,status="complete_matched_flow_cross_validation",exit_code=0,failures=[],
        input_integrity_verified=True,development_matched_flow_fit_authorized=True,fit_attempted=True,experiment_sha256=pin,
        authorization_sha256=auth_pin,attempt_claim_sha256=hashlib.sha256(original.encoded(files["training/attempt_claim.json"])).hexdigest(),
        source=source,completed=completed,comparison=summary,**{k:False for k in ("raw_payload_opened","baseline_refitted",
            "transform_refitted","final_evaluation_authorized","other_advanced_real_fit_authorized")},
        output_files_sha256={n.removeprefix("training/"):hashlib.sha256(v if isinstance(v,bytes) else original.encoded(v)).hexdigest()
                            for n,v in files.items() if n.startswith("training/")})
    files["training/run_receipt.json"]=receipt
    states={f["fold_id"]:dict(conditional_gaussian=(family.temporal.gaussian,"a"*64),unconditional_gaussian=(family.unconditional,"d"*64)) for f in bundle.folds}
    native=SimpleNamespace(one_state_raw=one_raw,previous_results=previous,one_state_inputs=SimpleNamespace(stationary_raw=stationary_raw,
        temporal_inputs=SimpleNamespace(states=states,previous_inputs=bundle.inputs,previous_manifest=original_marker)))
    return files,native,marker,pin
