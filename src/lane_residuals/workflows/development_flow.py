"""Separately adopted two flow fits on immutable matched development folds."""
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess

from ..domain.artifact_registry import require
from ..io import artifact_registry as registry,development_experiment as previous,development_flow as contract
from ..modeling.matched_evaluation import evaluate_matched_samples
from ..modeling.matched_flow import MODES, MODEL_NAMES, MatchedFlow, fit_matched_flow, sample_matched_flow
from ..modeling.matched_flow_calibration import calibrate_solver, monte_carlo_diagnostics
from ..modeling.matched_flow_evaluation import comparison, paired_comparisons
from ..visualization.matched_flow import plot_comparison
from .development_experiment import source_guard,project_lock
from .development_temporal import destination,_receipt
from .locked_development_export import write,package


def durable_parents(path):
    """Create and fsync every new ancestor, rather than just the final directory."""
    path=previous.metadata_path(path);missing=[];cursor=path
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    require(cursor.is_dir() and cursor.resolve()==cursor,'flow_regular_parent_required')
    for folder in reversed(missing):
        folder.mkdir(exist_ok=False);registry._fsync_directory(folder);registry._fsync_directory(folder.parent)


def protected(project,request,request_path):
    folder=previous.resolve(project,request['original_one_state_experiment_directory'])
    marker,_=previous.pinned_json(folder/'experiment.json',request['expected_original_one_state_experiment_sha256'])
    old,_=previous.pinned_json(folder/'request.json',marker['request_sha256'])
    candidate=(Path(project)/Path(request['one_state_ar_result_zip']).expanduser()).absolute()
    require('..' not in candidate.parts,'flow_predecessor_traversal_forbidden')
    from .development_one_state import protected as old_protected
    return [folder,candidate,previous.metadata_path(request_path),*old_protected(project,old,folder/'request.json')]


def ledger_path(project,manifest):
    root=previous.resolve(project,'outputs/fit_ledgers/private/matched_flow_v01927')
    path=root/manifest['original_gaussian_experiment_sha256']/(contract.design_sha256(manifest)+'.started.json')
    previous.metadata_path(path);registry.separate_output(root,[previous.resolve(project,'data/catalog/private')])
    require(not os.path.lexists(path),'flow_design_already_attempted_preserve_ledger')
    return path


def prepare(*,project,request_path,expected_request_sha256,expected_tree,expected_runtime):
    project=Path(project).absolute();source_guard(project,expected_tree,expected_runtime)
    request,raw=previous.pinned_json(request_path,expected_request_sha256);contract.validate_request(request)
    guards=protected(project,request,request_path)
    auth=previous.resolve(project,request['authorization'])
    require(auth.is_relative_to(project/'config/private') and auth!=project/'config/private','flow_private_authorization_location')
    registry.separate_output(auth,guards)
    guards.append(auth)
    output=destination(project,request['experiment_directory'],guards,'experiment')
    training=destination(project,request['training_directory'],guards+[output],'training')
    destination(project,request['result_zip'],guards+[output,training],'zip')
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs=contract.load_inputs(project,request_path,expected_request_sha256)
        manifest=contract.marker(inputs,expected_request_sha256);ledger_path(project,manifest);inputs.unchanged()
        destination(project,request['experiment_directory'],guards,'experiment')
        destination(project,request['training_directory'],guards+[output],'training')
        destination(project,request['result_zip'],guards+[output,training],'zip')
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



def train(*,project,experiment_directory,expected_experiment_sha256,authorization_path,
          expected_authorization_sha256,expected_tree,expected_runtime):
    project=Path(project).absolute();source=source_guard(project,expected_tree,expected_runtime)
    folder=previous.metadata_path(experiment_directory)
    manifest,_=previous.pinned_json(folder/'experiment.json',expected_experiment_sha256)
    auth,authraw=previous.pinned_json(authorization_path,expected_authorization_sha256)
    contract.require_authorization(auth,expected_experiment_sha256)
    request,_=previous.pinned_json(folder/'request.json',manifest['request_sha256']);contract.validate_request(request)
    require(previous.resolve(project,request['experiment_directory'])==folder and previous.resolve(project,request['authorization'])==previous.metadata_path(authorization_path),
            'flow_issued_locations_mismatch')
    guards=protected(project,request,folder/'request.json')+[folder,previous.metadata_path(authorization_path)]
    output=destination(project,request['training_directory'],guards,'training')
    result=destination(project,request['result_zip'],guards+[output],'zip')
    with project_lock(project):
        source_guard(project,expected_tree,expected_runtime)
        inputs,manifest=contract.load_experiment(project,folder,expected_experiment_sha256)
        require(previous.sha(authorization_path)==expected_authorization_sha256,'flow_authorization_changed')
        inputs.watched[previous.metadata_path(authorization_path)]=expected_authorization_sha256
        # Repeat destination checks while holding the cooperative writer lock.
        destination(project,request['training_directory'],guards,'training');destination(project,request['result_zip'],guards+[output],'zip')
        claim=ledger_path(project,manifest);durable_parents(claim.parent)
        require(subprocess.run(['git','-C',str(project),'check-ignore','--no-index','--quiet',str(claim)],capture_output=True).returncode==0,
                'flow_private_ledger_must_be_ignored')
        inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'flow_runtime_changed')
        write(claim,{'contract_revision':contract.REVISION,'status':'claimed_do_not_retry','design_sha256':contract.design_sha256(manifest),
            'experiment_sha256':expected_experiment_sha256,'original_gaussian_experiment_sha256':manifest['original_gaussian_experiment_sha256'],
            'one_state_ar_result_sha256':manifest['one_state_ar_result_sha256'],'source':source,
            'authorization_sha256':expected_authorization_sha256,'training_directory':str(output),'result_zip':str(result),
            'claimed_at_utc':datetime.now(timezone.utc).isoformat()})
        inputs.watched[claim]=previous.sha(claim)
        try:
            durable_parents(output.parent);output.mkdir(exist_ok=False);registry._fsync_directory(output.parent)
        except (Exception,KeyboardInterrupt) as exc:
            code=130 if isinstance(exc,KeyboardInterrupt) else 2
            failure_event(claim,'output_creation',exc,code);return code
        receipt={'contract_revision':contract.REVISION,'status':'failed_preserve_attempt','exit_code':2,'source':source,
            'experiment_sha256':expected_experiment_sha256,'one_state_ar_result_sha256':manifest['one_state_ar_result_sha256'],
            'authorization_sha256':expected_authorization_sha256,'attempt_claim_sha256':previous.sha(claim),
            'attempt_claim_path_private':str(claim),'fit_attempted':False,'development_matched_flow_fit_authorized':True,
            'other_advanced_real_fit_authorized':False,'final_evaluation_authorized':False,
            'raw_payload_opened':False,'baseline_refitted':False,'transform_refitted':False,'input_integrity_verified':False,
            'completed':[],'failures':[],'started_at_utc':datetime.now(timezone.utc).isoformat()}
        stage='preserve_inputs';blocks={b.outing_id:b for b in inputs.one_state_inputs.temporal_inputs.previous_inputs.blocks}
        try:
            write(output/'authorization.json',authraw);write(output/'attempt_claim.json',claim.read_bytes())
            write(output/'accepted_one_state_ar_result.zip',inputs.one_state_raw)
            for index,fold in enumerate(manifest['folds']):
                base,basepin=inputs.one_state_inputs.temporal_inputs.states[fold['fold_id']]['conditional_gaussian']
                training=[blocks[i] for i in fold['training_outings']]
                held=blocks[fold['validation_outing']]
                for mode,name in zip(MODES,MODEL_NAMES):
                    stage=fold['fold_id']+'_'+mode
                    inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'flow_runtime_changed')
                    def checkpoint(state):
                        write(output/(stage+'_epoch'+str(len(state.training_losses))+'.json'),
                              {'diagnostic_only_not_resumable':True,'experiment_sha256':expected_experiment_sha256,
                               'fold':fold,'base_conditional_transform_source_sha256':basepin,'state':state.to_dict()})
                    print('Fitting fixed',name,'held out',fold['validation_outing'],flush=True)
                    receipt['fit_attempted']=True
                    state,fit_report=fit_matched_flow(base,training,mode=mode,seed=contract.PROTOCOL['training_seed']+index,checkpoint=checkpoint)
                    model_file=output/(stage+'_model.json')
                    write(model_file,{'contract_revision':contract.REVISION,'experiment_sha256':expected_experiment_sha256,
                        'fold':fold,'base_conditional_transform_source_sha256':basepin,'state':state.to_dict(),'fit_report':fit_report})
                    restored=MatchedFlow.from_dict(previous.pinned_json(model_file,previous.sha(model_file))[0]['state'])
                    inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'flow_runtime_changed')
                    stage=fold['fold_id']+'_'+mode+'_calibration'
                    calibration=calibrate_solver(restored,training)
                    calibration_file=output/(stage+'.json');write(calibration_file,calibration)
                    require(calibration['passed'] is True,'flow_solver_screen_failed_preserve_state_no_later_fit')
                    stage=fold['fold_id']+'_'+mode+'_scoring'
                    seed=contract.PROTOCOL['sampling_seed']+index
                    draws=sample_matched_flow(restored,held.x,held.offsets,sample_count=contract.PROTOCOL['sample_count'],
                                              seed=seed,steps=calibration['selected_steps'])
                    metrics=evaluate_matched_samples(held.y,held.offsets,draws)
                    metrics['mean_physical_joint_nll']=None
                    row={'model':name,'fold':fold,'sampling_seed':seed,'metrics':metrics,
                         'density_status':'unavailable_no_verified_divergence_integral',
                         'base_conditional_transform_source_sha256':basepin,'model_sha256':previous.sha(model_file),
                         'solver_calibration_sha256':previous.sha(calibration_file),'solver_steps':calibration['selected_steps'],
                         'training_rows':state.training_rows,'training_sequences':state.training_sequences,
                         'training_transitions':state.training_rows-state.training_sequences,
                         'validation_archive_sha256':held.archive.summary_sha256,
                         'fit_quality_status':'fixed_epochs_finite_state_not_a_convergence_claim',
                         'fit_report':fit_report,'monte_carlo_diagnostics':monte_carlo_diagnostics(held.y,held.offsets,draws)}
                    write(output/(fold['fold_id']+'_'+mode+'_scores.json'),row);receipt['completed'].append(row)
                    del draws
                    print('Saved state and scores:',name,fold['validation_outing'],flush=True)
            allrows=inputs.previous_results+receipt['completed']
            stage='comparison'
            summary=comparison(allrows)
            write(output/'comparison.json',{'models':summary,'paired_comparisons':paired_comparisons(inputs.previous_results,receipt['completed']),
                'scope':'matched_short_support_development_no_automatic_winner'})
            plot_comparison(allrows,output/'comparison.png')
            receipt.update(status='complete_matched_flow_cross_validation',exit_code=0,comparison=summary,
                           scientific_interpretation='finite_fixed_epoch_states_and_numeric_screen_not_model_acceptance_or_planner_benefit')
        except (Exception,KeyboardInterrupt) as exc:
            receipt['exit_code']=130 if isinstance(exc,KeyboardInterrupt) else 2
            receipt['failures'].append({'stage':stage,'failure_code':getattr(exc,'code',type(exc).__name__)})
        try:
            inputs.unchanged();require(source_guard(project,expected_tree,expected_runtime)==source,'flow_runtime_changed')
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
