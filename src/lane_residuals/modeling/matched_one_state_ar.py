"""Matched adapter for the unchanged one-state AIOHMM Gaussian AR law.

Only the new one-state model parameters are fitted. Training-fold transforms
are immutable accepted Gaussian parameters. Marginal density is calculated by
Gaussian mean/covariance recursion; observed-history density remains separate.
"""
from dataclasses import dataclass
import numpy as np

from ..domain.sequence_dataset import PaddedSequenceDataset, BMW_CONDITION_FEATURE_NAMES
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from .aiohmm import AIOHMMConfig, AutoregressiveInputOutputHMM
from .matched_gaussian import MatchedGaussian, matrix
from .matched_stationary_ar import offsets_for

MODEL_NAME = 'matched_one_state_aiohmm_ar'
REVISION = 'v0.19.18-matched-one-state-adapter-2026-10-24-a1'
MAX_PADDED_FRAMES = 100000
MAX_SAMPLED_PADDED_FRAMES = 2000000
# Existing regularization/stopping defaults are explicit and fixed; only the
# historical one-state architecture, ineffective transitions and 0.99 ceiling
# differ from the generic class defaults. No current held-out tuning occurs.
CONFIGURATION = dict(state_count=1, maximum_em_iterations=30, minimum_em_iterations=5,
    convergence_tolerance=1e-4, convergence_criterion='relative_total_log_probability',
    regression_ridge_penalty=1e-3, emission_parameter_pooling_penalty=10.,
    state_covariance_pooling=.5, covariance_diagonal_shrinkage=.15,
    covariance_minimum_eigenvalue=1e-5, minimum_effective_state_observations=10.,
    maximum_absolute_autoregression=.99, transition_l2_penalty=1e-3,
    transition_learning_rate=.03, transition_adam_steps=30,
    initial_probability_smoothing=1e-2, minimum_state_occupancy_fraction=.01,
    initialization_seed=20260820, input_dependent_transitions=False)


def condition_tensor(features, offsets, base):
    x=matrix(features,6);offsets=offsets_for(offsets,len(x));lengths=np.diff(offsets)
    if len(lengths)*int(lengths.max())>MAX_PADDED_FRAMES:raise ValueError('one_state_padded_resource_bound')
    tensor=np.zeros((len(lengths),int(lengths.max()),6))
    for i,(lo,hi) in enumerate(zip(offsets[:-1],offsets[1:])):
        tensor[i,:hi-lo]=(x[lo:hi]-base.condition_mean)/base.condition_scale
    return tensor,lengths


def unpad(values,lengths):
    values=np.asarray(values)
    return np.concatenate([values[:,i,:n] for i,n in enumerate(lengths)],axis=1)


def padded_blocks(blocks, base):
    """Preserve every row, original reset and exact source-clock provenance."""
    if not blocks or base.mode!='conditional_gaussian':
        raise ValueError('one_state_training_blocks_and_conditional_transform_required')
    sequences=[]
    for block in blocks:
        y,x=matrix(block.y,21),matrix(block.x,6)
        if len(y)!=len(x):raise ValueError('one_state_block_row_alignment')
        offsets=offsets_for(block.offsets,len(y));arrays=block.archive.arrays
        selected=arrays['conditioned_profile_indices']
        if len(selected)!=len(y):raise ValueError('one_state_exact_conditioned_mapping_required')
        for i,(lo,hi) in enumerate(zip(offsets[:-1],offsets[1:])):
            rows=selected[lo:hi];recordings=arrays['recording_id'][rows]
            if len(set(recordings.tolist()))!=1:raise ValueError('one_state_reset_crosses_recording')
            times=[int(t) for t in arrays['estimate_source_time_ns_decimal'][rows]]
            if any(t<0 or t>np.iinfo(np.int64).max for t in times) or any(b<=a for a,b in zip(times,times[1:])):
                raise ValueError('one_state_exact_increasing_source_clock_required')
            sequences.append((block.outing_id+'/'+str(i),str(recordings[0]),block.outing_id,
                (x[lo:hi]-base.condition_mean)/base.condition_scale,
                (y[lo:hi]-base.residual_mean)/base.residual_scale,
                arrays['pair_index'][rows],arrays['estimate_message_index'][rows],times))
    maximum=max(len(v[3]) for v in sequences);count=len(sequences)
    if count*maximum>MAX_PADDED_FRAMES:raise ValueError('one_state_padded_resource_bound')
    x=np.zeros((count,maximum,6));y=np.zeros((count,maximum,21));valid=np.zeros_like(y,dtype=bool)
    pair=np.full((count,maximum),-1,dtype=np.int64);message=pair.copy();time=pair.copy()
    lengths=[]
    for i,(_,_,_,xx,yy,pp,mm,tt) in enumerate(sequences):
        n=len(xx);lengths.append(n);x[i,:n]=xx;y[i,:n]=yy;valid[i,:n]=True
        pair[i,:n]=pp;message[i,:n]=mm;time[i,:n]=tt
    return PaddedSequenceDataset(sequence_ids=[s[0] for s in sequences],recording_ids=[s[1] for s in sequences],
        drive_ids=[s[2] for s in sequences],conditions=x,residuals_m=y,valid_mask=valid,lengths=lengths,
        pair_indices=pair,estimate_message_indices=message,estimate_source_times_ns_private=time,
        feature_names=BMW_CONDITION_FEATURE_NAMES,stations_m=CANONICAL_MODEL_STATIONS_M,standardized=True)


@dataclass(frozen=True)
class OneStateAR:
    transform_source: MatchedGaussian
    model: AutoregressiveInputOutputHMM

    def __post_init__(self):
        if not isinstance(self.transform_source,MatchedGaussian) or self.transform_source.mode!='conditional_gaussian':
            raise ValueError('one_state_frozen_conditional_transform_required')
        if not isinstance(self.model,AutoregressiveInputOutputHMM) or not self.model.is_fitted:
            raise ValueError('one_state_fitted_model_required')
        if self.model.config.to_dict()!=CONFIGURATION or self.model.has_latent_state_switching:
            raise ValueError('one_state_fixed_configuration_required')
        payload=self.model.to_dict()
        if payload['training_frame_count']!=self.transform_source.training_rows or not 1<=payload['training_sequence_count']<=payload['training_frame_count']:
            raise ValueError('one_state_training_population_mismatch')

    def sample(self,features,offsets,*,sample_count,seed):
        # Deliberately pass only features and lengths, never observed targets.
        x,lengths=condition_tensor(features,offsets,self.transform_source)
        if type(sample_count) is not int or sample_count<1 or sample_count*len(lengths)*int(lengths.max())>MAX_SAMPLED_PADDED_FRAMES:
            raise ValueError('one_state_sampled_resource_bound')
        standardized=self.model.sample(x,lengths,sample_count=sample_count,seed=seed).values
        flat=unpad(standardized,lengths)
        physical=flat*self.transform_source.residual_scale+self.transform_source.residual_mean
        if not np.isfinite(physical).all():raise ValueError('one_state_nonfinite_physical_draws')
        return physical

    def marginal_parameters(self,features,offsets):
        """Exact generated-history Gaussian marginals, conditional on features."""
        x=matrix(features,6);offsets=offsets_for(offsets,len(x));base=self.transform_source
        z=(x-base.condition_mean)/base.condition_scale;design=np.column_stack((np.ones(len(z)),z))
        p=self.model.to_dict();initial=np.asarray(p['initial_emission_coefficients'])
        B=np.asarray(p['emission_coefficients'])[0];a=np.asarray(p['autoregressive_coefficients'])[0]
        C0=np.asarray(p['initial_emission_covariance_standardized2']);Q=np.asarray(p['covariances_standardized2'])[0]
        means=np.empty((len(x),21));covariances=np.empty((len(x),21,21))
        for lo,hi in zip(offsets[:-1],offsets[1:]):
            means[lo]=design[lo]@initial;covariances[lo]=C0
            for t in range(lo+1,hi):
                means[t]=design[t]@B+a*means[t-1]
                covariances[t]=a[:,None]*covariances[t-1]*a[None,:]+Q
        return means,covariances

    def predict_mean(self,features,offsets):
        means,_=self.marginal_parameters(features,offsets)
        return means*self.transform_source.residual_scale+self.transform_source.residual_mean

    def marginal_logpdf(self,features,residuals,offsets):
        y=matrix(residuals,21);means,covariances=self.marginal_parameters(features,offsets);base=self.transform_source
        if len(y)!=len(means):raise ValueError('one_state_density_row_alignment')
        error=(y-base.residual_mean)/base.residual_scale-means
        L=np.linalg.cholesky(covariances);white=np.linalg.solve(L,error[...,None])[...,0]
        return -.5*(21*np.log(2*np.pi)+2*np.log(np.diagonal(L,axis1=1,axis2=2)).sum(axis=1)+np.square(white).sum(axis=1))-np.log(base.residual_scale).sum()

    def logpdf_observed_history(self,blocks):
        dataset=padded_blocks(blocks,self.transform_source)
        increments=self.model.log_probability(dataset)
        active=increments[dataset.time_mask]
        return active-np.log(self.transform_source.residual_scale).sum()

    def to_dict(self):
        return {'contract_revision':REVISION,'model':MODEL_NAME,'transform_source':self.transform_source.to_dict(),
                'legacy_model':self.model.to_dict()}

    @classmethod
    def from_dict(cls,value):
        from ..io.development_experiment import encoded
        if type(value) is not dict or set(value)!={'contract_revision','model','transform_source','legacy_model'} or value['contract_revision']!=REVISION or value['model']!=MODEL_NAME:
            raise ValueError('one_state_closed_adapter_schema')
        result=cls(MatchedGaussian.from_dict(value['transform_source']),AutoregressiveInputOutputHMM.from_dict(value['legacy_model']))
        if encoded(result.to_dict())!=encoded(value):raise ValueError('one_state_exact_canonical_state_required')
        return result


def fit_one_state_ar(base,training_blocks):
    """Exactly one legacy fit on training rows; no transform or validation fit."""
    dataset=padded_blocks(training_blocks,base)
    if dataset.frame_count!=base.training_rows:raise ValueError('one_state_exact_training_frame_count')
    if sum(dataset.lengths-1)<1:raise ValueError('one_state_training_transitions_required')
    model=AutoregressiveInputOutputHMM(AIOHMMConfig(**CONFIGURATION))
    report=model.fit(dataset)  # validation_data deliberately absent
    return OneStateAR(base,model),report
