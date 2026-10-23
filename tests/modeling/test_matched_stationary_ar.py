"""Analytic, stationary-law and reset tests for the new memory-only control."""
import json
import unittest

import numpy as np

from lane_residuals.modeling.matched_gaussian import MatchedGaussian
from lane_residuals.modeling.matched_stationary_ar import StationaryAR, fit_stationary_ar, objective


def base(rows=40):
    return MatchedGaussian('conditional_gaussian',np.linspace(-.2,.2,21),np.linspace(.5,1.5,21),
        np.zeros(6),np.ones(6),np.zeros(21),np.full((6,21),.03),
        .3*np.ones((21,21))+.7*np.eye(21),rows,7)


class StationaryARTests(unittest.TestCase):
    def model(self,phi=.7,rows=40):
        return StationaryAR(base(max(40,rows)),phi,20,(420.,420.,294.,420))

    def test_zero_phi_is_bitwise_original_sampler_and_density(self):
        model=self.model(0);x=np.arange(240).reshape(40,6)/100;y=np.ones((40,21))
        np.testing.assert_array_equal(model.sample(x,[0,10,40],sample_count=8,seed=4),model.base.sample(x,sample_count=8,seed=4))
        np.testing.assert_array_equal(model.logpdf_observed_history(x,y,[0,10,40]),model.base.logpdf(x,y))

    def test_stationary_covariance_and_lag_follow_the_declared_law(self):
        model=self.model(.7,6);x=np.zeros((6,6));draws=model.sample(x,[0,6],sample_count=30000,seed=5)
        centered=(draws-model.base.residual_mean)/model.base.residual_scale
        for t in [0,1,5]:
            np.testing.assert_allclose(np.cov(centered[:,t].T),model.base.covariance,atol=.04)
        correlation=np.corrcoef(centered[:,0,0],centered[:,1,0])[0,1]
        self.assertAlmostEqual(correlation,.7,delta=.015)

    def test_reset_and_future_features_do_not_change_other_sequences_or_past(self):
        model=self.model();x=np.zeros((40,6));a=model.sample(x,[0,20,40],sample_count=8,seed=1)
        x[:20]+=5
        b=model.sample(x,[0,20,40],sample_count=8,seed=1)
        np.testing.assert_array_equal(a[:,20:],b[:,20:])
        x=np.zeros((40,6));x[10:]+=4
        c=model.sample(x,[0,20,40],sample_count=8,seed=1)
        np.testing.assert_array_equal(a[:,:10],c[:,:10])

    def test_chain_density_matches_explicit_physical_multivariate_normal(self):
        model=self.model(.6,3);x=np.zeros((3,6));y=np.linspace(-.3,.3,63).reshape(3,21)
        scale=model.base.residual_scale
        spatial=model.base.covariance*np.outer(scale,scale)
        temporal=model.phi**np.abs(np.arange(3)[:,None]-np.arange(3)[None,:])
        covariance=np.kron(temporal,spatial)
        e=(y-model.base.predict_mean(x)).reshape(-1)
        sign,ld=np.linalg.slogdet(covariance)
        expected=-.5*(63*np.log(2*np.pi)+ld+e@np.linalg.solve(covariance,e))
        self.assertEqual(sign,1)
        self.assertAlmostEqual(model.logpdf_observed_history(x,y,[0,3]).sum(),expected,places=10)

    def test_training_MLE_recovers_phi_and_beats_dense_grid_objective(self):
        prior=base(2400);true=StationaryAR(prior,.73,2000,(42000.,42000.,30000.,42000))
        x=np.zeros((2400,6));offsets=np.arange(0,2401,12)
        y=true.sample(x,offsets,sample_count=4,seed=17)[0]
        fitted=fit_stationary_ar(prior,[(y,x,offsets)])
        self.assertAlmostEqual(fitted.phi,.73,delta=.025)
        grid=np.linspace(-.99,.99,10001)
        self.assertLessEqual(objective(fitted.phi,fitted.sufficient_statistics),min(objective(p,fitted.sufficient_statistics) for p in grid)+1e-8)
        h=1e-6
        derivative=(objective(fitted.phi+h,fitted.sufficient_statistics)-objective(fitted.phi-h,fitted.sufficient_statistics))/(2*h)
        self.assertAlmostEqual(derivative,0,delta=.001)

    def test_training_blocks_never_create_boundary_transitions(self):
        prior=base(40);x=np.zeros((40,6));y=np.random.default_rng(2).normal(size=(40,21))
        result=fit_stationary_ar(prior,[(y[:20],x[:20],[0,10,20]),(y[20:],x[20:],[0,10,20])])
        self.assertEqual(result.training_transitions,36)

    def test_singletons_reset_to_exact_original_marginal(self):
        model=self.model(.9);x=np.zeros((40,6))
        np.testing.assert_array_equal(model.sample(x,np.arange(41),sample_count=8,seed=9),model.base.sample(x,sample_count=8,seed=9))

    def test_roundtrip_sampling_density_and_closed_schema(self):
        model=self.model();payload=json.loads(json.dumps(model.to_dict()))
        restored=StationaryAR.from_dict(payload);x=np.ones((40,6))
        np.testing.assert_array_equal(model.sample(x,[0,40],sample_count=8,seed=8),restored.sample(x,[0,40],sample_count=8,seed=8))
        payload['extra']=True
        with self.assertRaises(ValueError):StationaryAR.from_dict(payload)

    def test_bad_cap_nonfinite_boolean_and_bad_offsets_are_rejected(self):
        for phi in [True,float('nan'),1.,-.991]:
            with self.subTest(phi=phi),self.assertRaises(ValueError):self.model(phi)
        for offsets in [[0,0,40],[0,41],[1,40],[0.,40.],np.array([0,30,10,40],dtype=np.uint64)]:
            with self.subTest(offsets=offsets),self.assertRaises(ValueError):self.model().sample(np.zeros((40,6)),offsets,sample_count=8,seed=1)

    def test_no_pairs_or_wrong_training_population_refused(self):
        x=np.zeros((40,6));y=np.random.default_rng(5).normal(size=(40,21))
        for blocks in [[(y,x,np.arange(41))],[(y[:20],x[:20],[0,20])]]:
            with self.assertRaises(ValueError):fit_stationary_ar(base(),blocks)
