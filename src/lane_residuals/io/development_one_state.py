"""Closed matched one-state experiment and immutable predecessor evidence."""
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import stat
import zipfile
import numpy as np

from ..domain.artifact_registry import require
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..modeling.matched_one_state_ar import MODEL_NAME, CONFIGURATION,padded_blocks,MAX_PADDED_FRAMES,MAX_SAMPLED_PADDED_FRAMES
from ..modeling.matched_stationary_ar import StationaryAR
from . import development_experiment as previous, development_temporal as temporal, artifact_registry as registry

REVISION='v0.19.18-matched-one-state-experiment-2026-10-25-a2'
AUTHORIZATION_REVISION='v0.19.18-one-state-ar-fit-2026-10-25-a2'
STATIONARY_SOURCE=('188a3a896172ad139d26006f31f430141f72c8f6','10ef92f593b86c05b979b085559d6a614c006a2e',
                   '33479095e835df9e911c0bf40a30e91bcbc7f065f5e3e19f444dc7969e461166')
FIELDS={'contract_revision','original_temporal_experiment_directory','expected_original_temporal_experiment_sha256',
    'stationary_ar_result_zip','expected_stationary_ar_result_sha256','experiment_directory','training_directory','authorization','result_zip'}
ATTESTATIONS={'explicit_development_one_state_ar_fit','independent_protocol_review_and_ci_accepted',
              'final_outings_remain_unexposed','fixed_protocol_and_preserve_failed_attempts'}
PROTOCOL={'model':MODEL_NAME,'configuration':CONFIGURATION,'feature_names':list(BMW_CONDITION_FEATURE_NAMES),
 'covariance_regularization':'prospective_D1B_zero_diagonal_shrinkage_eigenvalue_clip_1e-6_not_Gaussian_additive_1e-6_I',
 'maximum_padded_frames':MAX_PADDED_FRAMES,'maximum_sampled_padded_frames':MAX_SAMPLED_PADDED_FRAMES,
 'population':'exact_original_complete_feature_rows_all_locked_development_outings',
 'transform':'reuse_each_accepted_conditional_Gaussian_training_fold_means_scales_exactly_no_refit',
 'fit':'one_unchanged_AIOHMM_fit_training_only_no_validation_argument',
 'architecture':'one_state_station_wise_AR_full_innovation_covariance_no_latent_switching',
 'reset':'unchanged_state_independent_training_marginal_conditional_Gaussian_fitted_on_all_training_frames',
 'sequences':'exact_original_rows_offsets_recordings_source_clocks_no_bridging_or_removal',
 'selection':'fixed_configuration_training_likelihood_stopping_single_initialization_no_restarts_no_outer_tuning',
 'fit_warning_policy':'retain_all_valid_states_and_warnings_flag_unconverged_for_scientific_review_never_retry',
 'sampling':'unchanged_legacy_free_running_sampler_current_conditions_generated_previous_residual',
 'sample_count':128,'sampling_seed':20261022,
 'random_numbers':'fixed_seeds_not_common_indexed_noise_with_legacy_sampler',
 'primary_aggregation':'equal_outing_macro',
 'primary_metrics':['mean_normalized_sequence_energy_score_m','median_absolute_lag_one_correlation_error'],
 'frame_density':'exact_Gaussian_generated_history_marginal_recursion_not_teacher_forcing',
 'chain_density':'separate_offline_observed_history_joint_NLL_per_frame',
 'comparison':'reuse_original_Gaussian_and_scalar_AR_scores_no_refit_no_historical_score_pooling',
 'interpretation':'broader_model_comparison_not_a_pure_memory_ablation_no_marginal_invariance_claim',
 'claim':'short_window_development_RLMB_pseudo_residuals_not_independent_physical_ground_truth',
 'multi_state_or_flow_fit_authorized':False,'advanced_real_fit_authorized':False,
 'final_evaluation_authorized':False,'planner_evaluation_authorized':False,'raw_processing_authorized':False}


def validate_request(value):
    require(type(value) is dict and set(value)==FIELDS and value['contract_revision']==REVISION,'one_state_closed_request_schema')
    for k in ('expected_original_temporal_experiment_sha256','expected_stationary_ar_result_sha256'):registry.digest(value[k])


def stationary_evidence(path,pin,inputs,manifest):
    path=previous.metadata_path(path)
    require(path.suffix=='.zip','one_state_predecessor_ZIP_required')
    raw,_=previous.read_bytes(path,64*1024**2)
    require(hashlib.sha256(raw).hexdigest()==registry.digest(pin),'one_state_predecessor_digest_mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();infos=z.infolist()
        require(len(names)==len(set(names)) and len(names)<=128 and sum(v.file_size for v in infos)<=64*1024**2
            and all(not n.startswith('/') and '..' not in Path(n).parts and not n.endswith('/')
                    and not stat.S_ISLNK(v.external_attr>>16) for n,v in zip(names,infos)),'one_state_predecessor_bounded_members')
        require(z.testzip() is None,'one_state_predecessor_CRC')
        sums={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            h,n=line.split('  ',1);require(n not in sums,'one_state_duplicate_SHA_entry');sums[n]=registry.digest(h)
        require(set(names)==set(sums)|{'SHA256SUMS'},'one_state_predecessor_file_set')
        require(all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in sums.items()),'one_state_predecessor_member_digest')
        read=lambda n:registry.decode(z.read(n))
        receipt=read('training/run_receipt.json');source=receipt['source']
        require(tuple(source[k] for k in ('consumer_git_commit','consumer_git_tree','consumer_runtime_source_sha256'))==STATIONARY_SOURCE,
                'one_state_predecessor_unreviewed_producer')
        require(receipt['status']=='complete_matched_stationary_ar_cross_validation' and type(receipt['exit_code']) is int
            and receipt['exit_code']==0 and receipt['input_integrity_verified'] is True and receipt['failures']==[]
            and receipt['development_stationary_ar_fit_authorized'] is True and receipt['fit_attempted'] is True
            and receipt['baseline_refitted'] is False and receipt['advanced_real_fit_authorized'] is False
            and receipt['final_evaluation_authorized'] is False and receipt['raw_payload_opened'] is False,'one_state_successful_predecessor_required')
        require(read('experiment/experiment.json')==manifest and hashlib.sha256(z.read('experiment/experiment.json')).hexdigest()==receipt['experiment_sha256'],
                'one_state_predecessor_experiment')
        temporal.require_authorization(read('training/authorization.json'),receipt['experiment_sha256'])
        require(sums['training/authorization.json']==receipt['authorization_sha256'],'one_state_predecessor_authorization_pin')
        claim=read('training/attempt_claim.json')
        require(claim['status']=='claimed_do_not_retry' and claim['source']==source and claim['design_sha256']==temporal.design_sha256(manifest)
                and sums['training/attempt_claim.json']==receipt['attempt_claim_sha256'],'one_state_predecessor_claim')
        for key in ('experiment_sha256','original_experiment_sha256','gaussian_result_sha256'):
            expected=receipt[key] if key in receipt else manifest[key]
            require(claim[key]==expected,'one_state_predecessor_claim_binding')
        require(Path(receipt['attempt_claim_path_private']).name==claim['design_sha256']+'.started.json','one_state_predecessor_claim_locator')
        require(z.read('training/accepted_gaussian_result.zip')==inputs.gaussian_raw,'one_state_predecessor_Gaussian_changed')
        required={'SHA256SUMS','experiment/experiment.json','experiment/request.json','training/run_receipt.json',
            'training/authorization.json','training/attempt_claim.json','training/accepted_gaussian_result.zip'}
        results=[];blocks={b.outing_id:b for b in inputs.previous_inputs.blocks}
        for index,fold in enumerate(manifest['folds']):
            stem='training/'+fold['fold_id'];m,s=stem+'_model.json',stem+'_scores.json';required|={m,s}
            model,result=read(m),read(s);state=StationaryAR.from_dict(model['state']);base,basepin=inputs.states[fold['fold_id']]['conditional_gaussian']
            require(model['contract_revision']==temporal.REVISION and model['experiment_sha256']==receipt['experiment_sha256']
                and model['fold']==result['fold']==fold and model['base_conditional_model_sha256']==result['base_conditional_model_sha256']==basepin
                and state.base.to_dict()==base.to_dict(),'one_state_predecessor_model_binding')
            require(result['model']==temporal.MODEL_NAME and result['model_sha256']==sums[m]
                and result['sampling_seed']==PROTOCOL['sampling_seed']+index and result['phi']==state.phi
                and result['phi_at_fixed_cap'] is bool(abs(state.phi)==.99) and result['single_frame_marginal_nll_unchanged'] is True,
                'one_state_predecessor_score_identity')
            train=[blocks[i] for i in fold['training_outings']];held=blocks[fold['validation_outing']]
            require(result['training_rows']==state.base.training_rows==sum(len(b.y) for b in train)
                and result['training_transitions']==state.training_transitions==sum(len(b.y)-len(b.offsets)+1 for b in train)
                and result['validation_archive_sha256']==held.archive.summary_sha256
                and result['metrics']['frame_count']==len(held.y) and result['metrics']['sequence_count']==len(held.offsets)-1
                and result['metrics']['valid_transitions']==len(held.y)-len(held.offsets)+1,'one_state_predecessor_exact_support')
            results.append(result)
        require(set(names)==required and receipt['completed']==results,'one_state_predecessor_exact_completed_set')
        require(receipt['comparison']==temporal.aggregate(inputs.baseline_results+results)
                and receipt['paired_temporal_comparison']==temporal.paired_temporal_comparison(inputs.baseline_results,results),
                'one_state_predecessor_aggregate_or_pairs')
        require(receipt['output_files_sha256']=={n.removeprefix('training/'):sums[n] for n in required if n.startswith('training/') and n!='training/run_receipt.json'},
                'one_state_predecessor_receipt_manifest')
        return raw,results,{n:z.read(n) for n in required if n.startswith('experiment/')}


@dataclass
class OneStateInputs:
    request:dict
    temporal_inputs:object
    temporal_manifest:dict
    stationary_raw:bytes
    stationary_results:list
    watched:dict

    @property
    def previous_results(self):return self.temporal_inputs.baseline_results+self.stationary_results

    def unchanged(self):
        self.temporal_inputs.unchanged()
        require(all(previous.sha(p)==h for p,h in self.watched.items()),'one_state_input_changed')


def load_inputs(project,request_path,expected_request_sha256):
    request,_=previous.pinned_json(request_path,expected_request_sha256);validate_request(request)
    folder=previous.resolve(project,request['original_temporal_experiment_directory'])
    inputs,manifest=temporal.load_experiment(project,folder,request['expected_original_temporal_experiment_sha256'])
    # Guard known raw aliases lexically before any metadata-path lstat/open.
    value=request['stationary_ar_result_zip'];require(type(value) is str and bool(value),'one_state_predecessor_path_required')
    candidate=(Path(project)/Path(value).expanduser()).absolute()
    raw_paths={s for row in inputs.previous_inputs.context.metadata['records'] for s in row['canonical_paths_private']}
    require(str(candidate) not in raw_paths,'one_state_known_raw_input_forbidden')
    path=previous.metadata_path(candidate)
    raw,results,files=stationary_evidence(path,request['expected_stationary_ar_result_sha256'],inputs,manifest)
    require(all((folder/n.removeprefix('experiment/')).read_bytes()==b for n,b in files.items()),'one_state_original_experiment_bytes_changed')
    result=OneStateInputs(request,inputs,manifest,raw,results,{previous.metadata_path(request_path):expected_request_sha256,path:request['expected_stationary_ar_result_sha256']})
    result.unchanged();return result


def layout(dataset):
    """Pin the exact legacy adapter interface without fitting or saving targets."""
    h=hashlib.sha256()
    h.update(previous.encoded({'sequence_ids':list(dataset.sequence_ids),'recording_ids':list(dataset.recording_ids),
        'drive_ids':list(dataset.drive_ids),'lengths':dataset.lengths.tolist()}))
    for name,dtype in [('conditions','<f8'),('residuals_m','<f8'),('valid_mask','u1'),('pair_indices','<i8'),
                       ('estimate_message_indices','<i8'),('estimate_source_times_ns_private','<i8')]:
        array=np.asarray(getattr(dataset,name),dtype=dtype)
        h.update(previous.encoded({'name':name,'shape':list(array.shape),'dtype':dtype}));h.update(array.tobytes(order='C'))
    return {'interface_sha256':h.hexdigest(),'frames':dataset.frame_count,'sequences':dataset.sequence_count,
        'valid_transitions':int(sum(dataset.lengths-1)),'maximum_length':int(max(dataset.lengths)),
        'padded_frames':int(len(dataset.lengths)*max(dataset.lengths))}


def marker(inputs,request_sha256):
    old=inputs.temporal_manifest
    blocks={b.outing_id:b for b in inputs.temporal_inputs.previous_inputs.blocks};layouts=[]
    for fold in old['folds']:
        base,_=inputs.temporal_inputs.states[fold['fold_id']]['conditional_gaussian']
        training=padded_blocks([blocks[i] for i in fold['training_outings']],base)
        held=padded_blocks([blocks[fold['validation_outing']]],base)
        require(len(held.lengths)*int(max(held.lengths))*PROTOCOL['sample_count']<=MAX_SAMPLED_PADDED_FRAMES,
            'one_state_sampled_resource_bound')
        layouts.append({'fold_id':fold['fold_id'],'training':layout(training),'validation':layout(held)})
    return {'contract_revision':REVISION,'status':'complete_matched_one_state_ar_experiment','request_sha256':request_sha256,
        'original_temporal_experiment_sha256':inputs.request['expected_original_temporal_experiment_sha256'],
        'original_gaussian_experiment_sha256':old['original_experiment_sha256'],
        'stationary_ar_result_sha256':inputs.request['expected_stationary_ar_result_sha256'],'gaussian_result_sha256':old['gaussian_result_sha256'],
        'row_manifest_sha256':old['row_manifest_sha256'],'folds':old['folds'],'archives':old['archives'],'protocol':PROTOCOL,'adapter_layouts':layouts,
        'model_admission_authorized':False,'final_evaluation_authorized':False}


def load_experiment(project,folder,pin):
    folder=previous.metadata_path(folder)
    require(folder.is_dir() and {p.name for p in folder.iterdir()}=={'request.json','experiment.json'},'one_state_exact_experiment_file_set')
    saved,_=previous.pinned_json(folder/'experiment.json',pin)
    inputs=load_inputs(project,folder/'request.json',saved['request_sha256'])
    require(saved==marker(inputs,saved['request_sha256']),'one_state_cached_protocol_or_folds_changed')
    inputs.watched[folder/'experiment.json']=pin;return inputs,saved


def authorization_draft(pin):
    registry.digest(pin)
    return {'contract_revision':AUTHORIZATION_REVISION,'purpose':'fixed_one_state_ar_development_only',
        'experiment_sha256':pin,'attestations':dict.fromkeys(sorted(ATTESTATIONS),False)}


def require_authorization(value,pin):
    expected=authorization_draft(pin);expected['attestations']=dict.fromkeys(sorted(ATTESTATIONS),True)
    require(type(value) is dict and value==expected and all(type(v) is bool and v for v in value['attestations'].values()),
            'one_state_explicit_owner_authorization_required')


def design_sha256(manifest):
    return hashlib.sha256(previous.encoded({k:manifest[k] for k in ('original_gaussian_experiment_sha256','stationary_ar_result_sha256','protocol')})).hexdigest()


def paired_comparisons(previous_results,results):
    output={}
    for baseline in sorted({r['model'] for r in previous_results}):
        rows=[r for r in previous_results if r['model']==baseline]
        require(len(rows)==len(results) and len({r['fold']['fold_id'] for r in results})==len(rows),'one_state_exact_paired_folds')
        comparisons={}
        for metric in PROTOCOL['primary_metrics']:
            pairs=[]
            for row in results:
                base=next(r for r in rows if r['fold']==row['fold']);a,b=base['metrics'][metric],row['metrics'][metric]
                pairs.append({'validation_outing':row['fold']['validation_outing'],'baseline':a,'candidate':b,'difference':None if a is None or b is None else b-a})
            d=[p['difference'] for p in pairs if p['difference'] is not None]
            comparisons[metric]={'paired_outings':pairs,'assessed_outings':len(d),'unassessed_outings':len(pairs)-len(d),
                'equal_outing_mean_difference':sum(d)/len(d) if d else None,'improved_outings':sum(v<0 for v in d),
                'worsened_outings':sum(v>0 for v in d),'tied_outings':sum(v==0 for v in d)}
        output[baseline]=comparisons
    return {'candidate':MODEL_NAME,'direction':'candidate_minus_baseline_lower_is_better','baselines':output,
            'scope':'descriptive_development_no_automatic_winner_or_significance_claim'}
