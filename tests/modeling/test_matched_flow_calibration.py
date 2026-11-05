"""Prospective tail tolerance boundaries and realistic scale synthetic checks."""
import json
from time import monotonic
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.modeling import matched_flow_calibration as calibration
from lane_residuals.modeling.matched_flow import fit_matched_flow, joined_blocks, MODES, CONFIGURATION, MatchedFlow, sample_matched_flow
from lane_residuals.modeling.matched_gaussian import fit_matched_gaussian
from tests.modeling.matched_flow_fixtures import large_training_blocks


class TailScreenTests(unittest.TestCase):
    def setUp(self):
        self.block = SimpleNamespace(outing_id="artificial", x=np.zeros((100, 6)), offsets=np.array([0, 1, 3, 100]))
        self.model = SimpleNamespace(residual_scale=np.ones(21))
        self.coarse = np.zeros((32, 100, 21)); self.coarse[:, :, 0] = .49

    def screen(self, changed_rows, changed_draws=3):
        fine = self.coarse.copy(); fine[:changed_draws, :changed_rows, 0] = .51
        with patch.object(calibration, "sample_matched_flow", side_effect=[self.coarse, self.coarse, fine]):
            return calibration.calibrate_solver(self.model, [self.block])

    def test_two_of_32_changes_are_not_exceedances(self):
        report = self.screen(1, changed_draws=2)
        last = report["refinements"][-1]
        self.assertEqual(last["metrics"]["maximum_tail_probability_change"], 2/32)
        self.assertEqual(last["metrics"]["tail_probability_exceedance_count"], 0)
        self.assertEqual(last["metrics"]["tail_comparison_pair_count"], 300)
        self.assertTrue(report["passed"])

    def test_fraction_boundary_accepts_six_of_300_and_refuses_seven(self):
        accepted, refused = self.screen(6), self.screen(7)
        a, b = accepted["refinements"][-1], refused["refinements"][-1]
        self.assertEqual(a["metrics"]["tail_probability_exceedance_fraction"], .02)
        self.assertEqual(a["metrics"]["tail_probability_exceedance_count"], 6)
        self.assertTrue(a["criteria_passed"]["tail_probability_exceedance_fraction"])
        self.assertTrue(accepted["passed"])
        self.assertEqual(accepted["selected_steps"], 128)
        self.assertFalse(b["criteria_passed"]["tail_probability_exceedance_fraction"])
        self.assertEqual(b["metrics"]["tail_probability_exceedance_counts_by_threshold"], {"0.5": 7, "1.0": 0, "2.0": 0})
        self.assertFalse(refused["passed"])
        self.assertIsNone(refused["selected_steps"])

    def test_pooled_limit_still_refuses_many_small_pointwise_changes(self):
        report = self.screen(100, changed_draws=1)
        last = report["refinements"][-1]
        self.assertEqual(last["metrics"]["tail_probability_exceedance_count"], 0)
        self.assertTrue(last["criteria_passed"]["tail_probability_exceedance_fraction"])
        self.assertFalse(last["criteria_passed"]["pooled_tail_probability_change"])
        self.assertFalse(report["passed"])

    def test_only_final_refinement_selects_fixed_128_steps(self):
        with patch.object(calibration, "sample_matched_flow", side_effect=[self.coarse*10, self.coarse, self.coarse]) as sampler:
            report = calibration.calibrate_solver(self.model, [self.block])
        self.assertEqual([c.kwargs["steps"] for c in sampler.call_args_list], [32, 64, 128])
        self.assertFalse(report["refinements"][0]["passed"])
        self.assertTrue(report["refinements"][1]["passed"])
        self.assertEqual(report["selected_steps"], 128)


class HeunSamplerTests(unittest.TestCase):
    def setUp(self):
        self.model = MatchedFlow("conditional", np.zeros(21), np.ones(21), np.zeros(6), np.ones(6),
            np.zeros((50, 64)), np.zeros(64), np.zeros((64, 21)), np.zeros(21), (1.,), 8, 2, 1)
        self.x = np.zeros((3, 6)); self.offsets = np.array([0, 2, 3])

    def sample(self, *, solver="heun", steps=8, batch_size=4096):
        return sample_matched_flow(self.model, self.x, self.offsets, sample_count=4, seed=9,
                                   steps=steps, batch_size=batch_size, solver=solver)

    def test_time_dependent_integral_and_two_velocity_evaluations_per_step(self):
        calls = []
        def field(model, z, t, x, p, starts):
            calls.append(t.copy()); return np.broadcast_to(2*t[:, None], z.shape)
        with patch.object(MatchedFlow, "velocity", new=field): result = self.sample(steps=1)
        expected = np.random.default_rng(9).standard_normal((4, 3, 21))+1
        np.testing.assert_array_equal(result, expected)
        self.assertEqual(len(calls), 4)
        np.testing.assert_array_equal(calls[0], np.zeros(8))
        np.testing.assert_array_equal(calls[1], np.ones(8))

    def test_second_order_refinement_on_known_exponential_field(self):
        def field(model, z, t, x, p, starts): return z
        exact = np.random.default_rng(9).standard_normal((4, 3, 21))*np.e
        with patch.object(MatchedFlow, "velocity", new=field):
            a, b, euler = self.sample(steps=8), self.sample(steps=16), self.sample(solver="euler", steps=16)
        error_a, error_b = np.linalg.norm(a-exact), np.linalg.norm(b-exact)
        self.assertGreater(error_a/error_b, 3.4)
        self.assertLess(error_a/error_b, 4.1)
        self.assertLess(error_b, np.linalg.norm(euler-exact)/10)

    def test_both_stages_use_same_generated_past_and_reset_flag(self):
        seen = []
        def field(model, z, t, x, previous, starts):
            seen.append((previous.copy(), starts.copy()))
            return np.where(starts[:, None], np.ones_like(z), previous+1)
        with patch.object(MatchedFlow, "velocity", new=field): result = self.sample(steps=1)
        for i in (0, 1):
            self.assertTrue(seen[i][1].all()); np.testing.assert_array_equal(seen[i][0], np.zeros((8, 21)))
        for i in (2, 3):
            self.assertFalse(seen[i][1].any()); np.testing.assert_array_equal(seen[i][0], result[:, 0])

    def test_indexed_noise_and_batching_preserved_for_heun(self):
        def field(model, z, t, x, previous, starts): return np.tanh(z+t[:, None])
        with patch.object(MatchedFlow, "velocity", new=field):
            a, b = self.sample(batch_size=4096), self.sample(batch_size=1)
        np.testing.assert_allclose(a, b, atol=2e-15, rtol=2e-15)
        with patch.object(MatchedFlow, "velocity", return_value=np.zeros((8, 21))) as field_mock:
            with self.assertRaisesRegex(ValueError, "supported_solver"): self.sample(solver="unknown")
        field_mock.assert_not_called()


class LargeSyntheticScreenTests(unittest.TestCase):
    def check_distribution(self, innovation):
        blocks = large_training_blocks(seed=20261106, innovation=innovation)
        y, x, offsets = joined_blocks(blocks)
        self.assertEqual(len(y), 8802)
        self.assertGreater(len(offsets)-1, 2000)
        self.assertLess(len(offsets)-1, 2200)
        self.assertEqual(max(np.diff(offsets)), 14)
        self.assertLessEqual(np.median(np.diff(offsets)), 3)
        base = fit_matched_gaussian(y, x, mode="conditional_gaussian")
        for mode in MODES:
            with self.subTest(innovation=innovation, mode=mode):
                model, fit = fit_matched_flow(base, blocks, mode=mode, seed=20261104)
                started = monotonic()
                report = calibration.calibrate_solver(model, blocks)
                elapsed = monotonic()-started
                final = report["refinements"][-1]
                print(json.dumps({"synthetic_scale_screen": {"innovation": innovation, "mode": mode,
                    "rows": len(y), "sequences": len(offsets)-1, "calibration_rows": sum(r["length"] for r in report["subset"]),
                    "fit_seconds": fit["elapsed_seconds"], "calibration_seconds": elapsed,
                    "passed": report["passed"], "final_metrics": final["metrics"]}}, sort_keys=True), flush=True)
                self.assertEqual(len(model.training_losses), CONFIGURATION["epochs"])
                self.assertTrue(report["passed"], final)
                self.assertEqual(report["selected_steps"], 128)

    def test_gaussian_innovation_both_modes(self):
        self.check_distribution("gaussian")

    def test_student_t_innovation_both_modes(self):
        self.check_distribution("student_t5")
