"""Independent Gaussian-law, causal sampling and exact provenance adapter checks."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

from lane_residuals.modeling import matched_gaussian as gaussian
from lane_residuals.modeling.matched_gaussian import MatchedGaussian
from lane_residuals.modeling.matched_one_state_ar import OneStateAR,CONFIGURATION,fit_one_state_ar,padded_blocks
from lane_residuals.modeling.aiohmm import AutoregressiveInputOutputHMM
from lane_residuals.domain.sequence_dataset import SequenceStandardizer


def base(rows=40):
    return MatchedGaussian('conditional_gaussian',np.linspace(-.2,.3,21),np.linspace(.7,1.6,21),
        np.arange(6)/10,np.linspace(.5,1.,6),np.zeros(21),np.zeros((6,21)),np.eye(21),rows,7)


def block(name='train',rows=40):
    rng=np.random.default_rng(39);indices=np.arange(rows)*2
    arrays={'conditioned_profile_indices':indices,'recording_id':np.full(rows*2,'synthetic-recording'),
        'pair_index':np.arange(rows*2)+100,'estimate_message_index':np.arange(rows*2)+200,
        'estimate_source_time_ns_decimal':np.array([str(1_000_000_000+i*50_000_000) for i in range(rows*2)])}
    return SimpleNamespace(outing_id=name,y=rng.normal(size=(rows,21)),x=rng.normal(size=(rows,6)),
        offsets=np.arange(0,rows+1,8),archive=SimpleNamespace(arrays=arrays))


class MatchedOneStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fitted,_=fit_one_state_ar(base(),[block()])
        payload=fitted.model.to_dict()
        initial=np.zeros((7,21));initial[0]=np.linspace(-.1,.1,21);initial[1]=.08
        emission=np.zeros((1,7,21));emission[0,0]=.04;emission[0,2]=-.05
        payload.update(initial_emission_coefficients=initial.tolist(),emission_coefficients=emission.tolist(),
            autoregressive_coefficients=[np.linspace(.2,.8,21).tolist()],
            initial_emission_covariance_standardized2=(.4*np.eye(21)+.1*np.ones((21,21))).tolist(),
            covariances_standardized2=[(.12*np.eye(21)+.02*np.ones((21,21))).tolist()])
        cls.state=OneStateAR(base(),AutoregressiveInputOutputHMM.from_dict(payload))

    def test_exact_padding_provenance_transforms_and_order(self):
        b=block();d=padded_blocks([b],base());active=d.time_mask
        np.testing.assert_array_equal(d.conditions[active],(b.x-base().condition_mean)/base().condition_scale)
        np.testing.assert_array_equal(d.residuals_m[active],(b.y-base().residual_mean)/base().residual_scale)
        np.testing.assert_array_equal(d.pair_indices[active],b.archive.arrays['pair_index'][b.archive.arrays['conditioned_profile_indices']])
        np.testing.assert_array_equal(d.estimate_source_times_ns_private[active],[int(v) for v in b.archive.arrays['estimate_source_time_ns_decimal'][::2]])
        self.assertEqual(d.frame_count,40);self.assertEqual(d.sequence_count,5)
        self.assertEqual(set(d.drive_ids),{'train'})

    def test_variable_lengths_singletons_and_zero_padding_remain(self):
        b=block();b.offsets=np.array([0,1,4,12,40]);d=padded_blocks([b],base())
        np.testing.assert_array_equal(d.lengths,[1,3,8,28])
        self.assertTrue(np.all(d.conditions[~d.time_mask]==0));self.assertTrue(np.all(d.residuals_m[~d.time_mask]==0))
        self.assertTrue(np.all(d.pair_indices[~d.time_mask]==-1));self.assertEqual(d.frame_count,40)

    def test_resource_limits_reject_before_legacy_fit_or_sample(self):
        from lane_residuals.modeling import matched_one_state_ar as adapter
        with patch.object(adapter,'MAX_PADDED_FRAMES',39),patch.object(AutoregressiveInputOutputHMM,'fit') as fit:
            with self.assertRaisesRegex(ValueError,'padded_resource_bound'):fit_one_state_ar(base(),[block()])
            fit.assert_not_called()
        with patch.object(adapter,'MAX_SAMPLED_PADDED_FRAMES',7),patch.object(self.state.model,'sample') as sampler:
            with self.assertRaisesRegex(ValueError,'sampled_resource_bound'):self.state.sample(np.zeros((8,6)),[0,8],sample_count=1,seed=2)
            sampler.assert_not_called()

    def test_source_clock_recording_and_row_alignment_fail_before_fit(self):
        for kind in ['clock','recording','rows']:
            b=block()
            if kind=='clock':b.archive.arrays['estimate_source_time_ns_decimal'][2]='1'
            if kind=='recording':b.archive.arrays['recording_id'][2]='different-recording'
            if kind=='rows':b.y=b.y[:-1]
            with self.subTest(kind=kind),patch.object(AutoregressiveInputOutputHMM,'fit') as fitter,self.assertRaises(ValueError):
                fit_one_state_ar(base(),[b])
            fitter.assert_not_called()

    def test_fit_calls_legacy_once_training_only_without_transform_fit(self):
        b=block();original=AutoregressiveInputOutputHMM.fit;calls=[]
        def spy(model,training_data,validation_data=None):
            calls.append((training_data,validation_data));return original(model,training_data,validation_data)
        with patch.object(AutoregressiveInputOutputHMM,'fit',new=spy), \
                patch.object(SequenceStandardizer,'fit',side_effect=AssertionError('new transform fit')), \
                patch.object(gaussian,'scale',side_effect=AssertionError('new transform fit')):
            fitted,report=fit_one_state_ar(base(),[b])
        self.assertEqual(len(calls),1);self.assertIsNone(calls[0][1]);self.assertEqual(set(calls[0][0].drive_ids),{'train'})
        self.assertEqual(fitted.model.config.to_dict(),CONFIGURATION);self.assertFalse(fitted.model.has_latent_state_switching)
        self.assertEqual(report.validation_sequence_count,0)
        np.testing.assert_array_equal(fitted.transform_source.residual_scale,base().residual_scale)

    def test_sampling_and_marginal_mean_are_causal_and_reset_isolated(self):
        x=np.zeros((12,6));a=self.state.sample(x,[0,6,12],sample_count=8,seed=73)
        changed=x.copy();changed[4:6]=7;changed[10:]=9
        b=self.state.sample(changed,[0,6,12],sample_count=8,seed=73)
        np.testing.assert_array_equal(a[:,:4],b[:,:4]);np.testing.assert_array_equal(a[:,6:10],b[:,6:10])
        np.testing.assert_array_equal(self.state.predict_mean(x,[0,6,12])[:4],self.state.predict_mean(changed,[0,6,12])[:4])
        other=x.copy();other[:6]=5
        np.testing.assert_array_equal(a[:,6:],self.state.sample(other,[0,6,12],sample_count=8,seed=73)[:,6:])

    def test_marginal_means_covariances_match_legacy_free_running_samples(self):
        x=np.zeros((3,6));draw=self.state.sample(x,[0,3],sample_count=12000,seed=4)
        mean,cov=self.state.marginal_parameters(x,[0,3]);s=self.state.transform_source.residual_scale
        physical_mean=mean*s+self.state.transform_source.residual_mean
        np.testing.assert_allclose(draw.mean(axis=0),physical_mean,atol=.025)
        for i in range(3):np.testing.assert_allclose(np.cov(draw[:,i].T),cov[i]*np.outer(s,s),atol=.045)

    def test_marginal_density_matches_explicit_physical_Gaussian(self):
        x=np.zeros((3,6));y=np.linspace(-.2,.4,63).reshape(3,21)
        means,cov=self.state.marginal_parameters(x,[0,3]);s=self.state.transform_source.residual_scale
        expected=[]
        for t in range(3):
            C=cov[t]*np.outer(s,s);e=y[t]-(means[t]*s+self.state.transform_source.residual_mean)
            expected.append(-.5*(21*np.log(2*np.pi)+np.linalg.slogdet(C)[1]+e@np.linalg.solve(C,e)))
        np.testing.assert_allclose(self.state.marginal_logpdf(x,y,[0,3]),expected,atol=1e-11,rtol=0)

    def test_observed_history_density_matches_joint_physical_Kronecker_blocks(self):
        b=block(rows=40);b.x=b.x[:3];b.y=b.y[:3];b.offsets=np.array([0,3])
        b.archive.arrays['conditioned_profile_indices']=np.array([0,2,4])
        mean,cov=self.state.marginal_parameters(b.x,[0,3]);payload=self.state.model.to_dict()
        A=np.diag(payload['autoregressive_coefficients'][0]);s=self.state.transform_source.residual_scale
        C=np.empty((3,3,21,21))
        for i in range(3):
            for j in range(3):C[i,j]=cov[i]@np.linalg.matrix_power(A.T,j-i) if j>=i else np.linalg.matrix_power(A,i-j)@cov[j]
        joint=C.transpose(0,2,1,3).reshape(63,63)*np.outer(np.tile(s,3),np.tile(s,3))
        error=(b.y-(mean*s+self.state.transform_source.residual_mean)).reshape(-1)
        expected=-.5*(63*np.log(2*np.pi)+np.linalg.slogdet(joint)[1]+error@np.linalg.solve(joint,error))
        self.assertAlmostEqual(self.state.logpdf_observed_history([b]).sum(),expected,places=10)

    def test_history_density_is_separate_from_marginal_and_resets_match(self):
        b=block();a=self.state.logpdf_observed_history([b]);m=self.state.marginal_logpdf(b.x,b.y,b.offsets)
        np.testing.assert_allclose(a[b.offsets[:-1]],m[b.offsets[:-1]],rtol=0,atol=1e-11)
        self.assertGreater(np.max(np.abs(a-m)),.1)

    def test_round_trip_closed_schema_config_and_canonical_state(self):
        payload=self.state.to_dict();restored=OneStateAR.from_dict(payload)
        x=np.zeros((5,6));np.testing.assert_array_equal(self.state.sample(x,[0,5],sample_count=8,seed=2),restored.sample(x,[0,5],sample_count=8,seed=2))
        changes=[lambda p:p.update(extra=1),lambda p:p['legacy_model'].update(extra=1),
            lambda p:p['legacy_model']['configuration'].update(state_count=2),lambda p:p['legacy_model'].update(training_frame_count=True)]
        for mutate in changes:
            p=deepcopy(payload);mutate(p)
            with self.assertRaises(ValueError):OneStateAR.from_dict(p)

    def test_bad_offsets_nonfinite_and_wrong_training_count_rejected(self):
        for offsets in [[0,3,2,5],np.array([0,3,2,5],dtype=np.uint64),[0.,5.],[1,5]]:
            with self.assertRaises(ValueError):self.state.sample(np.zeros((5,6)),offsets,sample_count=8,seed=1)
        with self.assertRaises(ValueError):self.state.sample(np.full((5,6),np.nan),[0,5],sample_count=8,seed=1)
        with self.assertRaises(ValueError):fit_one_state_ar(base(48),[block()])

    def test_prospective_regularization_of_reset_and_innovation_matches_raw_spectrum(self):
        # Coherent rank-deficient errors make shrinkage and floor changes visible.
        b=block();b.y=np.tile(b.y[:,:1],(1,21));transform=base()
        fitted,_=fit_one_state_ar(transform,[b]);p=fitted.model.to_dict()
        self.assertEqual(p['configuration']['covariance_diagonal_shrinkage'],0.)
        self.assertEqual(p['configuration']['covariance_minimum_eigenvalue'],1e-6)
        z=(b.y-transform.residual_mean)/transform.residual_scale
        x=(b.x-transform.condition_mean)/transform.condition_scale
        design=np.column_stack((np.ones(len(x)),x))
        initial=np.asarray(p['initial_emission_coefficients'])
        reset_error=z-design@initial
        rows=np.setdiff1d(np.arange(len(z)),b.offsets[:-1])
        B=np.asarray(p['emission_coefficients'])[0];a=np.asarray(p['autoregressive_coefficients'])[0]
        innovation=z[rows]-design[rows]@B-z[rows-1]*a
        for errors,actual in [(reset_error,p['initial_emission_covariance_standardized2']),
                (innovation,p['covariances_standardized2'][0])]:
            raw=errors.T@errors/len(errors)
            eigenvalues,vectors=np.linalg.eigh((raw+raw.T)/2)
            expected=(vectors*np.maximum(eigenvalues,1e-6))@vectors.T
            np.testing.assert_allclose(actual,expected,atol=2e-14,rtol=1e-11)
            self.assertLess(eigenvalues[0],1e-6)
            # The accepted Gaussian uses addition; do not conflate conventions.
            self.assertGreater(np.max(np.abs(np.asarray(actual)-(raw+1e-6*np.eye(21)))),1e-8)

    def test_superseded_adapter_revision_and_shrinkage_states_are_rejected(self):
        p=deepcopy(self.state.to_dict());p['contract_revision']='v0.19.18-matched-one-state-adapter-2026-10-24-a1'
        with self.assertRaisesRegex(ValueError,'closed_adapter_schema'):OneStateAR.from_dict(p)
        p=deepcopy(self.state.to_dict());p['legacy_model']['configuration']['covariance_diagonal_shrinkage']=.15
        with self.assertRaisesRegex(ValueError,'fixed_configuration'):OneStateAR.from_dict(p)
