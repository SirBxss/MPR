import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.modeling.flow_matching import SyntheticFlowModel,fit_synthetic_flow
from lane_residuals.modeling.synthetic_flow_sampling import sample_synthetic_flow_batched


class BatchedSyntheticFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(19)
        cls.x = rng.normal(size=(20,6))
        y = rng.normal(size=(20,21))
        cls.models = [fit_synthetic_flow(y,cls.x,np.array([0,4,12,20]),mode=mode,
            seed=2,hidden_width=8,epochs=3) for mode in ('unconditional','conditional')]

    def test_reference_agreement_padding_and_resets_for_both_modes(self):
        x = self.x[:12].reshape(3,4,6)
        lengths = np.array([1,3,4])
        for model in self.models:
            reference = model.sample(x,lengths,sample_count=3,seed=7,steps=8)
            for size in (1,2,100):
                with self.subTest(mode=model.mode,batch=size):
                    batched = sample_synthetic_flow_batched(model,x,lengths,sample_count=3,seed=7,steps=8,batch_rows=size)
                    np.testing.assert_allclose(batched,reference,rtol=1e-12,atol=1e-12)
                    if size == 1:
                        np.testing.assert_array_equal(batched,reference)
                    self.assertTrue(np.all(batched[:,0,1:]==0))

    def test_batching_reduces_velocity_calls_without_changing_solver_steps(self):
        x = self.x[:12].reshape(3,4,6)
        model = self.models[1]
        original = SyntheticFlowModel.velocity
        calls = []
        def observed(self,*args,**kwargs):
            calls.append(1)
            return original(self,*args,**kwargs)
        with patch.object(SyntheticFlowModel,'velocity',observed):
            sample_synthetic_flow_batched(model,x,np.array([1,3,4]),sample_count=8,seed=3,steps=8,batch_rows=100)
        self.assertEqual(len(calls),4*8)
        self.assertLess(len(calls),8*(1+3+4)*8)

    def test_invalid_dimensions_lengths_nonfinite_and_boolean_parameters_fail(self):
        x = self.x[:12].reshape(3,4,6)
        for lengths,count in [(np.array([0,3,4]),2),(np.array([1.,3.,4.]),2),(np.array([1,3,4]),True)]:
            with self.assertRaises(ValueError):
                sample_synthetic_flow_batched(self.models[0],x,lengths,sample_count=count,seed=1)
