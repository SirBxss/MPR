"""One separately adopted fixed one-state AR fit on immutable matched folds."""
from dataclasses import asdict
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess

import numpy as np

from ..domain.artifact_registry import require
from ..io import artifact_registry as registry,development_experiment as previous,development_temporal as temporal,development_one_state as contract
from ..modeling.matched_evaluation import evaluate_matched_samples
from ..modeling.matched_one_state_ar import MODEL_NAME,OneStateAR,fit_one_state_ar
from .development_experiment import source_guard,project_lock
from .development_temporal import destination,protected as temporal_protected,_receipt
from .locked_development_export import write,package


def durable_parents(path):
    """Create and fsync every new ancestor, rather than just the final directory."""
    path=previous.metadata_path(path);missing=[];cursor=path
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    require(cursor.is_dir() and cursor.resolve()==cursor,'one_state_regular_parent_required')
    for folder in reversed(missing):
        folder.mkdir(exist_ok=False);registry._fsync_directory(folder);registry._fsync_directory(folder.parent)


def protected(project,request,request_path):
    folder=previous.resolve(project,request['original_temporal_experiment_directory'])
    marker,_=previous.pinned_json(folder/'experiment.json',request['expected_original_temporal_experiment_sha256'])
    old,_=previous.pinned_json(folder/'request.json',marker['request_sha256'])
    value=request['stationary_ar_result_zip']
    require(type(value) is str and bool(value),'one_state_predecessor_path_required')
    predecessor=(Path(project)/Path(value).expanduser()).absolute()
    require('..' not in predecessor.parts,'one_state_predecessor_traversal_forbidden')
    # Separation is lexical. The reader rejects registered raw aliases before
    # the first metadata-path lstat/open of this newly supplied predecessor.
    return [folder,predecessor,previous.metadata_path(request_path),
            *temporal_protected(project,old,folder/'request.json')]


def ledger_path(project,manifest):
    root=previous.resolve(project,'outputs/fit_ledgers/private/matched_one_state_v01918')
    path=root/manifest['original_gaussian_experiment_sha256']/(contract.design_sha256(manifest)+'.started.json')
    previous.metadata_path(path);registry.separate_output(root,[previous.resolve(project,'data/catalog/private')])
    require(not os.path.lexists(path),'one_state_design_already_attempted_preserve_ledger')
    return path


def prepare(*,project,request_path,expected_request_sha256,expected_tree,expected_runtime):
    project=Path(project).absolute();source_guard(project,expected_tree,expected_runtime)
    request,raw=previous.pinned_json(request_path,expected_request_sha256);contract.validate_request(request)
    guards=protected(project,request,request_path)
    output=destination(project,request['experiment_directory'],guards,'experiment')
    training=destination(project,request['training_directory'],guards+[output],'training')
    destination(project,request['result_zip'],guards+[output,training],'zip')
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs=contract.load_inputs(project,request_path,expected_request_sha256)
        manifest=contract.marker(inputs,expected_request_sha256);ledger_path(project,manifest);inputs.unchanged()
        durable_parents(output.parent);output.mkdir(exist_ok=False);registry._fsync_directory(output.parent)
        write(output/'request.json',raw);inputs.unchanged();source_guard(project,expected_tree,expected_runtime)
        write(output/'experiment.json',manifest)
    return manifest,previous.sha(output/'experiment.json')


def failure_event(claim,stage,exc,code,**details):
    """Separate immutable failure evidence; never repair a prior published ZIP."""
    path=claim.with_name(claim.name+'.'+stage+'_failure.json')
    write(path,{'contract_revision':contract.REVISION,'status':'failed_preserve_attempt','stage':stage,
        'exit_code':code,'failure_code':getattr(exc,'code',type(exc).__name__),
        'claim_sha256':previous.sha(claim),'recorded_at_utc':datetime.now(timezone.utc).isoformat(),**details})
    print('Failure event:',path,flush=True)


def history_comparison(rows):
    output={}
    for name in sorted({r['model'] for r in rows}):
        selected=[r for r in rows if r['model']==name]
        values=[r['mean_observed_history_joint_nll_per_frame'] if 'mean_observed_history_joint_nll_per_frame' in r
                else r['metrics']['mean_physical_joint_nll'] for r in selected]
        output[name]={'equal_outing_macro_chain_NLL_per_frame':float(np.mean(values)),'outings':len(values),
            'scope':'offline_joint_sequence_factorization_not_online_observed_error_input'}
    return output


def train(*,project,experiment_directory,expected_experiment_sha256,authorization_path,
          expected_authorization_sha256,expected_tree,expected_runtime):
    project=Path(project).absolute();source=source_guard(project,expected_tree,expected_runtime)
    folder=previous.metadata_path(experiment_directory)
    manifest,_=previous.pinned_json(folder/'experiment.json',expected_experiment_sha256)
    auth,authraw=previous.pinned_json(authorization_path,expected_authorization_sha256)
    contract.require_authorization(auth,expected_experiment_sha256)
    request,_=previous.pinned_json(folder/'request.json',manifest['request_sha256']);contract.validate_request(request)
    require(previous.resolve(project,request['experiment_directory'])==folder and previous.resolve(project,request['authorization'])==previous.metadata_path(authorization_path),
            'one_state_issued_locations_mismatch')
    guards=protected(project,request,folder/'request.json')+[folder,previous.metadata_path(authorization_path)]
    output=destination(project,request['training_directory'],guards,'training')
    result=destination(project,request['result_zip'],guards+[output],'zip')
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs,manifest=contract.load_experiment(project,folder,expected_experiment_sha256)
        require(previous.sha(authorization_path)==expected_authorization_sha256,'one_state_authorization_changed')
        inputs.watched[previous.metadata_path(authorization_path)]=expected_authorization_sha256
        # Repeat destination checks while holding the cooperative writer lock.
        destination(project,request['training_directory'],guards,'training');destination(project,request['result_zip'],guards+[output],'zip')
        claim=ledger_path(project,manifest);durable_parents(claim.parent)
        require(subprocess.run(['git','-C',str(project),'check-ignore','--no-index','--quiet',str(claim)],capture_output=True).returncode==0,
                'one_state_private_ledger_must_be_ignored')
        inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'one_state_runtime_changed')
        write(claim,{'contract_revision':contract.REVISION,'status':'claimed_do_not_retry','design_sha256':contract.design_sha256(manifest),
            'experiment_sha256':expected_experiment_sha256,'original_gaussian_experiment_sha256':manifest['original_gaussian_experiment_sha256'],
            'stationary_ar_result_sha256':manifest['stationary_ar_result_sha256'],'source':source,
            'authorization_sha256':expected_authorization_sha256,'training_directory':str(output),'result_zip':str(result),
            'claimed_at_utc':datetime.now(timezone.utc).isoformat()})
        inputs.watched[claim]=previous.sha(claim)
        try:
            durable_parents(output.parent);output.mkdir(exist_ok=False);registry._fsync_directory(output.parent)
        except (Exception,KeyboardInterrupt) as exc:
            code=130 if isinstance(exc,KeyboardInterrupt) else 2
            failure_event(claim,'output_creation',exc,code);return code
        receipt={'contract_revision':contract.REVISION,'status':'failed_preserve_attempt','exit_code':2,'source':source,
            'experiment_sha256':expected_experiment_sha256,'stationary_ar_result_sha256':manifest['stationary_ar_result_sha256'],
            'authorization_sha256':expected_authorization_sha256,'attempt_claim_sha256':previous.sha(claim),
            'attempt_claim_path_private':str(claim),'fit_attempted':False,'development_one_state_ar_fit_authorized':True,
            'multi_state_or_flow_fit_authorized':False,'advanced_real_fit_authorized':False,'final_evaluation_authorized':False,
            'raw_payload_opened':False,'baseline_refitted':False,'transform_refitted':False,'input_integrity_verified':False,
            'completed':[],'failures':[],'started_at_utc':datetime.now(timezone.utc).isoformat()}
        stage='preserve_inputs';blocks={b.outing_id:b for b in inputs.temporal_inputs.previous_inputs.blocks}
        try:
            write(output/'authorization.json',authraw);write(output/'attempt_claim.json',claim.read_bytes())
            write(output/'accepted_stationary_ar_result.zip',inputs.stationary_raw)
            for index,fold in enumerate(manifest['folds']):
                stage=fold['fold_id'];inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'one_state_runtime_changed')
                base,basepin=inputs.temporal_inputs.states[stage]['conditional_gaussian']
                training=[blocks[i] for i in fold['training_outings']]
                print('Fitting fixed one-state AR held-out',fold['validation_outing'],flush=True);receipt['fit_attempted']=True
                state,fit_report=fit_one_state_ar(base,training)
                model_file=output/(stage+'_model.json')
                write(model_file,{'contract_revision':contract.REVISION,'experiment_sha256':expected_experiment_sha256,'fold':fold,
                    'base_conditional_transform_source_sha256':basepin,'state':state.to_dict(),'fit_report':asdict(fit_report)})
                restored=OneStateAR.from_dict(previous.pinned_json(model_file,previous.sha(model_file))[0]['state'])
                held=blocks[fold['validation_outing']];seed=contract.PROTOCOL['sampling_seed']+index
                draws=restored.sample(held.x,held.offsets,sample_count=contract.PROTOCOL['sample_count'],seed=seed)
                metrics=evaluate_matched_samples(held.y,held.offsets,draws)
                metrics['mean_physical_joint_nll']=float(-restored.marginal_logpdf(held.x,held.y,held.offsets).mean())
                history_nll=float(-restored.logpdf_observed_history([held]).mean())
                require(np.isfinite(history_nll) and np.isfinite(metrics['mean_physical_joint_nll']),'one_state_finite_density_required')
                legacy=restored.model.to_dict();coeff=np.asarray(legacy['autoregressive_coefficients'])[0]
                row={'model':MODEL_NAME,'fold':fold,'sampling_seed':seed,'metrics':metrics,
                    'mean_observed_history_joint_nll_per_frame':history_nll,
                    'single_frame_density_scope':'analytic_generated_history_marginal_not_teacher_forcing',
                    'marginal_analytic_mean_rmse_m':float(np.sqrt(np.square(restored.predict_mean(held.x,held.offsets)-held.y).mean())),
                    'base_conditional_transform_source_sha256':basepin,'model_sha256':previous.sha(model_file),
                    'training_rows':base.training_rows,'training_sequences':legacy['training_sequence_count'],
                    'training_transitions':sum(len(b.y)-len(b.offsets)+1 for b in training),
                    'validation_archive_sha256':held.archive.summary_sha256,
                    'fit_converged':legacy['converged'],'fit_warnings':list(fit_report.warnings),
                    'fit_quality_status':'converged' if legacy['converged'] else 'training_fit_warning_requires_scientific_review',
                    'best_iteration_index':legacy['best_iteration_index'],'iterations_logged':len(legacy['log_likelihood_history']),
                    'autoregressive_coefficients':coeff.tolist(),'cap_station_count':int(np.sum(np.abs(coeff)>=.99-1e-10))}
                write(output/(stage+'_scores.json'),row);receipt['completed'].append(row)
                print('Fit quality:',row['fit_quality_status'],'cap stations:',row['cap_station_count'],'warnings:',len(row['fit_warnings']),flush=True)
            allrows=inputs.previous_results+receipt['completed']
            receipt.update(status='complete_matched_one_state_ar_cross_validation',exit_code=0,
                all_folds_converged=all(r['fit_converged'] for r in receipt['completed']),
                comparison=temporal.aggregate(allrows),paired_comparisons=contract.paired_comparisons(inputs.previous_results,receipt['completed']),
                observed_history_density_comparison=history_comparison(allrows),
                scientific_interpretation='valid_finite_outputs_not_automatic_model_fit_acceptance_or_winner')
        except (Exception,KeyboardInterrupt) as exc:
            receipt['exit_code']=130 if isinstance(exc,KeyboardInterrupt) else 2
            receipt['failures'].append({'stage':stage,'failure_code':getattr(exc,'code',type(exc).__name__)})
        try:
            inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'one_state_runtime_changed')
            receipt['input_integrity_verified']=True
        except (Exception,KeyboardInterrupt) as exc:
            receipt.update(status='failed_preserve_attempt',exit_code=130 if isinstance(exc,KeyboardInterrupt) else 2)
            receipt['failures'].append({'stage':'postflight','failure_code':getattr(exc,'code',type(exc).__name__)})
        receipt['finished_at_utc']=datetime.now(timezone.utc).isoformat();partial=result.with_suffix('.zip.partial')
        try:
            receipt['output_files_sha256']={p.name:previous.sha(p) for p in sorted(output.iterdir()) if p.is_file()}
            _receipt(output,receipt)
        except (Exception,KeyboardInterrupt) as exc:
            code=130 if isinstance(exc,KeyboardInterrupt) else 2
            failure_event(claim,'receipt',exc,code);return code
        try:
            package(partial,[(output,'training'),(folder,'experiment')])
            with partial.open('rb') as stream:os.fsync(stream.fileno())
            os.link(partial,result);registry._fsync_directory(result.parent)
        except (Exception,KeyboardInterrupt) as exc:
            code=130 if isinstance(exc,KeyboardInterrupt) else 2
            receipt.update(status='failed_packaging_preserve_attempt',exit_code=code)
            receipt['failures'].append({'stage':'packaging','failure_code':getattr(exc,'code',type(exc).__name__)})
            if not os.path.lexists(result):_receipt(output,receipt,replace_unpublished=True)
            failure_event(claim,'packaging',exc,code,final_zip_present=os.path.lexists(result))
            print('Preserve every claim, event, receipt, partial ZIP and terminal output. Do not retry.',flush=True)
            return code
        try:partial.unlink()
        except OSError:print('Published result; temporary duplicate link retained:',partial,flush=True)
        print('Result ZIP:',result,'SHA-256:',previous.sha(result),flush=True)
        return receipt['exit_code']
