from copy import deepcopy
import unittest

import numpy as np

from lane_residuals.modeling.matched_gaussian import MatchedGaussian, fit_matched_gaussian, scale
from lane_residuals.modeling.matched_evaluation import evaluate_matched_samples


class MatchedGaussianTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(9)
        self.x = rng.normal(size=(100,6))
        self.y = self.x[:,:1] @ np.linspace(.1,1,21)[None,:] + rng.normal(0,.1,(100,21))

    def test_full_rank_conditional_mean_matches_independent_physical_ols(self):
        model = fit_matched_gaussian(self.y,self.x,mode="conditional_gaussian")
        design = np.column_stack((np.ones(100),self.x))
        parameters = np.linalg.lstsq(design,self.y,rcond=None)[0]
        np.testing.assert_allclose(model.predict_mean(self.x),design@parameters,atol=1e-13)
        self.assertEqual(model.design_rank,7)

    def test_unconditional_fit_and_samples_ignore_conditions(self):
        one = fit_matched_gaussian(self.y,self.x,mode="unconditional_gaussian")
        two = fit_matched_gaussian(self.y,self.x*1000+100,mode="unconditional_gaussian")
        self.assertEqual(one.to_dict(),two.to_dict())
        np.testing.assert_array_equal(one.sample(self.x,sample_count=8,seed=9),
                                      two.sample(self.x*2,sample_count=8,seed=9))

    def test_constant_decimal_and_collinear_features_have_valid_minimum_norm_fit(self):
        x = self.x.copy()
        x[:,0],x[:,1],x[:,2] = .1,self.x[:,3],self.x[:,3]
        model = fit_matched_gaussian(self.y,x,mode="conditional_gaussian")
        self.assertEqual(model.condition_mean[0],.1)
        self.assertEqual(model.condition_scale[0],1)
        self.assertLess(model.design_rank,7)
        self.assertTrue(np.isfinite(model.logpdf(x,self.y)).all())

    def test_varying_small_scale_is_retained_and_one_ulp_is_not_constant(self):
        values = np.tile([.1,1e-10],(192,1))
        values[-1,0] = np.nextafter(.1,1.)
        values[:,1] += np.arange(192)*1e-15
        _,s = scale(values)
        self.assertTrue(np.all(s<1e-8))

    def test_transforms_depend_only_on_training_rows(self):
        one = fit_matched_gaussian(self.y[:80],self.x[:80],mode="conditional_gaussian")
        heldout = self.x[80:]+1e8
        one.predict_mean(heldout)
        two = fit_matched_gaussian(self.y[:80],self.x[:80],mode="conditional_gaussian")
        self.assertEqual(one.to_dict(),two.to_dict())
        np.testing.assert_array_equal(one.condition_mean,self.x[:80].mean(axis=0))

    def test_log_density_has_physical_jacobian_and_matches_direct_covariance(self):
        model = fit_matched_gaussian(self.y,self.x,mode="conditional_gaussian")
        covariance = model.covariance*model.residual_scale[:,None]*model.residual_scale[None,:]
        error = self.y-model.predict_mean(self.x)
        _,logdet = np.linalg.slogdet(covariance)
        expected = -.5*(21*np.log(2*np.pi)+logdet+np.einsum('ni,ij,nj->n',error,np.linalg.inv(covariance),error))
        np.testing.assert_allclose(model.logpdf(self.x,self.y),expected,rtol=1e-11,atol=1e-10)

    def test_model_round_trip_sampling_and_source_array_detachment(self):
        model = fit_matched_gaussian(self.y,self.x,mode="conditional_gaussian")
        payload = model.to_dict()
        clone = MatchedGaussian.from_dict(payload)
        payload['coefficients'][0][0] += 100
        np.testing.assert_array_equal(model.sample(self.x,sample_count=8,seed=6),clone.sample(self.x,sample_count=8,seed=6))
        self.assertFalse(clone.coefficients.flags.writeable)

    def test_invalid_shapes_values_state_and_sampling_fail(self):
        for y,x,mode in [(self.y[:1],self.x[:1],"conditional_gaussian"),
                (self.y[:,:20],self.x,"conditional_gaussian"),(self.y,self.x,"flow")]:
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                fit_matched_gaussian(y,x,mode=mode)
        model = fit_matched_gaussian(self.y,self.x,mode="conditional_gaussian")
        payload = model.to_dict(); payload['covariance'][0][0] = -1
        with self.assertRaises((ValueError,np.linalg.LinAlgError)):
            MatchedGaussian.from_dict(payload)
        with self.assertRaises(ValueError):
            model.sample(self.x,sample_count=True,seed=1)


class MatchedEvaluationTests(unittest.TestCase):
    def test_exact_constant_predictive_distribution_has_zero_proper_scores(self):
        y = np.full((5,21),.1)
        scores = evaluate_matched_samples(y,np.array([0,2,3,5]),np.repeat(y[None],8,axis=0))
        self.assertEqual(scores['mean_energy_score_m'],0)
        self.assertEqual(scores['mean_marginal_crps_m'],0)
        self.assertEqual(scores['mean_normalized_sequence_energy_score_m'],0)
        self.assertEqual(scores['valid_transitions'],2)
        self.assertIsNone(scores['median_absolute_lag_one_correlation_error'])
        self.assertEqual(scores['lag_valid_station_count'],0)

    def test_singletons_are_retained_without_inventing_transitions(self):
        y = np.arange(5*21,dtype=float).reshape(5,21)
        scores = evaluate_matched_samples(y,np.arange(6),np.repeat(y[None],8,axis=0))
        self.assertEqual(scores['frame_count'],5)
        self.assertEqual(scores['sequence_count'],5)
        self.assertEqual(scores['valid_transitions'],0)
        self.assertIsNone(scores['median_absolute_lag_one_correlation_error'])

    def test_lag_uses_only_within_sequence_pairs(self):
        rng = np.random.default_rng(4)
        y = rng.normal(size=(20,21))
        offsets = np.array([0,5,10,20])
        scores = evaluate_matched_samples(y,offsets,np.repeat(y[None],8,axis=0))
        self.assertEqual(scores['valid_transitions'],17)
        self.assertEqual(scores['median_absolute_lag_one_correlation_error'],0)

    def test_mc_energy_matches_independent_direct_formula(self):
        rng = np.random.default_rng(5)
        y,draws = rng.normal(size=(6,21)),rng.normal(size=(8,6,21))
        result = evaluate_matched_samples(y,np.array([0,6]),draws)
        expected = np.mean([np.linalg.norm(d-y,axis=1).mean() for d in draws])
        expected -= .5*np.mean([np.linalg.norm(a-b,axis=1).mean() for a,b in zip(draws[:4],draws[4:])])
        self.assertAlmostEqual(result['mean_energy_score_m'],expected)

    def test_nonfinite_values_odd_draws_bad_offsets_fail(self):
        y = np.zeros((6,21)); draws = np.zeros((8,6,21))
        for offsets,samples in [(np.array([0,0,6]),draws),(np.array([0,5]),draws),(np.array([0,6]),draws[:7])]:
            with self.assertRaises(ValueError):
                evaluate_matched_samples(y,offsets,samples)
