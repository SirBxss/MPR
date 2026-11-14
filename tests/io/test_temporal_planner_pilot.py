"""Saved temporal states retain the accepted Gaussian and selected fold."""

import hashlib
import io
import json
import unittest
from zipfile import ZipFile

from lane_residuals.io.temporal_planner_pilot import restore_models
from lane_residuals.modeling.matched_stationary_ar import StationaryAR
from tests.modeling import test_matched_one_state_ar as fixture


def archive(files):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as z:
        for name, value in files.items():
            raw = json.dumps(value).encode()
            z.writestr(name, raw)
        z.writestr("SHA256SUMS", "".join(hashlib.sha256(z.read(n)).hexdigest()+"  "+n+"\n" for n in files))
    return buffer.getvalue()


class TemporalModelReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.MatchedOneStateTests.setUpClass()
        cls.one_state = fixture.MatchedOneStateTests.state
        cls.base = cls.one_state.transform_source
        cls.stationary = StationaryAR(cls.base, .8, 35, (30., 30., 20., 735))

    def test_restores_both_native_states_and_rejects_fold_or_transform_drift(self):
        fold = {"fold_id": "held", "validation_outing": "synthetic_held", "training_outings": ["synthetic_train"]}
        name = "training/held_model.json"
        one = archive({name: dict(fold=fold, base_conditional_transform_source_sha256="a"*64,
                                 state=self.one_state.to_dict())})
        stationary = archive({name: dict(fold=fold, base_conditional_model_sha256="a"*64,
                                        state=self.stationary.to_dict())})
        state = restore_models(one, stationary, fold, self.base, "a"*64)
        self.assertEqual(state.one_state.to_dict(), self.one_state.to_dict())
        self.assertEqual(state.stationary.to_dict(), self.stationary.to_dict())
        for wrong_fold, wrong_pin in (({**fold, "training_outings": ["other"]}, "a"*64), (fold, "b"*64)):
            with self.assertRaisesRegex(ValueError, "fold_or_transform_mismatch"):
                restore_models(one, stationary, wrong_fold, self.base, wrong_pin)


if __name__ == "__main__":
    unittest.main()
