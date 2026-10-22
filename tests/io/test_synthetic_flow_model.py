import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from lane_residuals.io.synthetic_flow_model import load_synthetic_flow,save_synthetic_flow
from lane_residuals.modeling.flow_matching import fit_synthetic_flow


class SyntheticFlowPersistenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'flow.json'
        rng = np.random.default_rng(7)
        self.y,self.x = rng.normal(size=(12,21)),rng.normal(size=(12,6))

    def test_both_learned_modes_round_trip_and_keep_step_halving_samples_exact(self):
        for mode in ('unconditional','conditional'):
            with self.subTest(mode=mode):
                path = self.path.with_name(mode+'.json')
                model = fit_synthetic_flow(self.y,self.x,np.array([0,4,12]),mode=mode,epochs=3,hidden_width=8,seed=5)
                pin = save_synthetic_flow(model,path)
                restored = load_synthetic_flow(path,pin)
                conditions = self.x[:8].reshape(2,4,6)
                for steps in (4,8,16):
                    np.testing.assert_array_equal(model.sample(conditions,np.array([3,4]),sample_count=2,seed=1,steps=steps),
                        restored.sample(conditions,np.array([3,4]),sample_count=2,seed=1,steps=steps))
                self.assertFalse(restored.weights_in.flags.writeable)

    def test_no_overwrite_and_wrong_digest(self):
        model = fit_synthetic_flow(self.y,self.x,np.array([0,12]),mode='unconditional',epochs=1)
        pin = save_synthetic_flow(model,self.path)
        with self.assertRaises(FileExistsError):
            save_synthetic_flow(model,self.path)
        with self.assertRaises(ValueError):
            load_synthetic_flow(self.path,'f'*64)

    def test_repinned_scope_or_malformed_weights_remain_invalid(self):
        model = fit_synthetic_flow(self.y,self.x,np.array([0,12]),mode='conditional',epochs=1)
        save_synthetic_flow(model,self.path)
        original = json.loads(self.path.read_text())
        for field,value in [('scope','real'),('real_fit_authorized',True),('model',{'mode':'conditional'})]:
            payload = dict(original); payload[field] = value
            self.path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_synthetic_flow(self.path,hashlib.sha256(self.path.read_bytes()).hexdigest())
