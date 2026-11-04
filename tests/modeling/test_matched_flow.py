"""Synthetic numerical, history, persistence and calibration regression tests."""
from dataclasses import replace
import json
from types import SimpleNamespace as Block
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.modeling import matched_flow as flow, matched_flow_calibration as calibration
from lane_residuals.modeling.matched_gaussian import fit_matched_gaussian
from lane_residuals.modeling.flow_matching import SyntheticFlowModel


class MatchedFlowTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(17)
        self.x = rng.normal(size=(24, 6))
        self.y = rng.normal(size=(24, 21))*.2
        self.block = Block(outing_id="synthetic", x=self.x, y=self.y, offsets=np.arange(0, 25, 3))
        self.base = fit_matched_gaussian(self.y, self.x, mode="conditional_gaussian")

    def fit(self, mode="conditional", checkpoint=None):
        return flow.fit_matched_flow(self.base, [self.block], mode=mode, seed=31, checkpoint=checkpoint)

    def test_separate_learner_exact_external_transforms_and_fixed_configuration(self):
        before = self.base.to_dict()
        with patch("lane_residuals.modeling.flow_matching.fit_synthetic_flow", side_effect=AssertionError("synthetic trainer")):
            state, report = self.fit()
        self.assertIsInstance(state, flow.MatchedFlow)
        self.assertNotIsInstance(state, SyntheticFlowModel)
        self.assertEqual(self.base.to_dict(), before)
        for name in ("residual_mean", "residual_scale", "condition_mean", "condition_scale"):
            np.testing.assert_array_equal(getattr(state, name), getattr(self.base, name))
            self.assertFalse(getattr(state, name).flags.writeable)
        self.assertEqual(len(state.training_losses), 100)
        self.assertFalse(report["transform_refitted"])
        self.assertFalse(report["convergence_claim"])
        self.assertEqual(report["epochs_completed"], 100)

    def test_exact_roundtrip_deterministic_seed_and_batching(self):
        a, _ = self.fit()
        b, _ = self.fit()
        self.assertEqual(a.to_dict(), b.to_dict())
        b = flow.MatchedFlow.from_dict(json.loads(json.dumps(a.to_dict(), allow_nan=False)))
        draws = flow.sample_matched_flow(a, self.x, self.block.offsets, sample_count=8, seed=40, steps=8)
        other = flow.sample_matched_flow(b, self.x, self.block.offsets, sample_count=8, seed=40, steps=8, batch_size=7)
        np.testing.assert_allclose(draws, other, atol=2e-15, rtol=2e-15)

    def test_reset_flag_ignores_previous_value(self):
        state, _ = self.fit()
        z, t, s = np.zeros((2, 21)), np.ones(2)*.3, np.array([True, False])
        a = state.velocity(z, t, self.x[:2], np.zeros_like(z), s)
        b = state.velocity(z, t, self.x[:2], np.ones_like(z)*5, s)
        np.testing.assert_array_equal(a[0], b[0])
        self.assertFalse(np.allclose(a[1], b[1]))

    def test_unconditional_ignores_conditions_and_history(self):
        state, _ = self.fit("unconditional")
        kw = dict(sample_count=8, seed=4, steps=8)
        a = flow.sample_matched_flow(state, self.x, self.block.offsets, **kw)
        b = flow.sample_matched_flow(state, self.x+100, np.arange(25), **kw)
        np.testing.assert_allclose(a, b, atol=2e-15, rtol=2e-15)

    def test_free_running_history_and_each_reset(self):
        state, _ = self.fit()
        seen = []
        def field(model, z, t, x, previous, starts):
            seen.append((previous.copy(), starts.copy()))
            return np.broadcast_to(np.where(starts[:, None], 1., previous+1), z.shape)
        state = replace(state, residual_mean=np.zeros(21), residual_scale=np.ones(21))
        offsets = np.array([0, 2, 3])
        with patch.object(flow.MatchedFlow, "velocity", new=field):
            result = flow.sample_matched_flow(state, self.x[:3], offsets, sample_count=4, seed=5, steps=1)
        self.assertTrue(seen[0][1].all())
        self.assertFalse(seen[1][1].any())
        np.testing.assert_array_equal(seen[1][0], result[:, 0])
        self.assertEqual(seen[0][0].shape, (8, 21))

    def test_training_bridge_never_crosses_reset_and_is_mode_paired(self):
        captured = {}
        original = flow._training_inputs
        def observe(y, x, o, noise, t, mode):
            if mode not in captured:
                a, target = original(y, x, o, noise, t, mode)
                captured[mode] = (noise.copy(), t.copy(), a.copy(), target.copy(), y.copy())
            return original(y, x, o, noise, t, mode)
        with patch.object(flow, "_training_inputs", side_effect=observe):
            self.fit(); self.fit("unconditional")
        noise, times, a, target, y = captured["conditional"]
        np.testing.assert_array_equal(noise, captured["unconditional"][0])
        np.testing.assert_array_equal(times, captured["unconditional"][1])
        np.testing.assert_array_equal(target, captured["unconditional"][3])
        starts = self.block.offsets[:-1]
        np.testing.assert_array_equal(a[starts, 28:49], np.zeros((len(starts), 21)))
        np.testing.assert_array_equal(a[starts, 49], np.ones(len(starts)))
        np.testing.assert_array_equal(a[1, 28:49], y[0])

    def test_checkpoints_finite_partial_states_and_timeout_no_restart(self):
        states = []
        self.fit(checkpoint=states.append)
        self.assertEqual([len(s.training_losses) for s in states], [1]+list(range(10, 101, 10)))
        with patch.object(flow, "monotonic", side_effect=[0., 601.]), self.assertRaises(TimeoutError):
            self.fit()

    def test_exact_block_boundaries_and_counts(self):
        b = Block(outing_id="other", x=self.x, y=self.y, offsets=np.array([0, 4, 24]))
        y, x, o = flow.joined_blocks([self.block, b])
        np.testing.assert_array_equal(o, [0, 3, 6, 9, 12, 15, 18, 21, 24, 28, 48])
        self.assertEqual(y.shape, (48, 21))
        with self.assertRaises(ValueError): flow.joined_blocks([b, b])
        with self.assertRaisesRegex(ValueError, "training_support"):
            flow.fit_matched_flow(self.base, [self.block, b], mode="conditional", seed=0)

    def test_closed_state_and_invalid_sizes(self):
        state, _ = self.fit()
        value = state.to_dict(); value["extra"] = 0
        with self.assertRaises(ValueError): flow.MatchedFlow.from_dict(value)
        with self.assertRaises(ValueError): replace(state, residual_scale=np.zeros(21))
        with self.assertRaises(ValueError): replace(state, seed=True)
        for count, steps in ((3, 8), (5, 8), (8, 129), (True, 8)):
            with self.assertRaises(ValueError):
                flow.sample_matched_flow(state, self.x, self.block.offsets, sample_count=count, seed=0, steps=steps)
        with patch.object(flow, "monotonic", side_effect=[0., 181.]), self.assertRaises(TimeoutError):
            flow.sample_matched_flow(state, self.x, self.block.offsets, sample_count=8, seed=0, steps=8)

    def test_calibration_selection_uses_only_training_lengths_and_conditions(self):
        x, o, identities = calibration.calibration_conditions([self.block])
        b = Block(outing_id=self.block.outing_id, x=self.x, offsets=self.block.offsets)
        xx, oo, ids = calibration.calibration_conditions([b])
        np.testing.assert_array_equal(x, xx); np.testing.assert_array_equal(o, oo)
        self.assertEqual(identities, ids)
        self.assertEqual([i["sequence_index"] for i in ids], [0, 4, 7])

    def test_calibration_analytic_field_refinement_and_failed_screen(self):
        state, _ = self.fit()
        state = replace(state, residual_mean=np.zeros(21), residual_scale=np.ones(21))
        def linear(model, z, t, x, p, s): return z*.1
        with patch.object(flow.MatchedFlow, "velocity", new=linear):
            report = calibration.calibrate_solver(state, [self.block])
        self.assertTrue(report["passed"])
        self.assertEqual(report["selected_steps"], 64)
        self.assertLess(report["refinements"][1]["metrics"]["paired_standardized_rmse"],
                        report["refinements"][0]["metrics"]["paired_standardized_rmse"])
        def stiff(model, z, t, x, p, s): return z*4
        with patch.object(flow.MatchedFlow, "velocity", new=stiff):
            report = calibration.calibrate_solver(state, [self.block])
        self.assertFalse(report["passed"])
        self.assertIsNone(report["selected_steps"])


if __name__ == "__main__":
    unittest.main()
