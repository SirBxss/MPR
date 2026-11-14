"""Independent affine cancellation, clock and finite marginal control checks."""

import unittest

import numpy as np

from lane_residuals.domain import temporal_planner_pilot as pilot
from lane_residuals.domain.reference_planner import plan_reference_step
from lane_residuals.domain.spatial_planner_response import STATIONS_M
from tests.domain import test_cached_planner_scenarios as scenario_fixture


class TemporalPlannerTests(unittest.TestCase):
    def test_varying_motion_increment_cancels_two_nominal_initial_states(self):
        rng = np.random.default_rng(92)
        profiles = rng.normal(0, 0.1, (5, 21))
        nominal_profiles = rng.normal(0, 0.05, (5, 21))
        speeds = np.array([15., 17., 16., 19., 18.])
        intervals = np.array([0.09, 0.11, 0.10, 0.12])
        acceleration, lateral = pilot.rollout(profiles[None], speeds, intervals)

        def command(state, residual, speed):
            return plan_reference_step(
                lateral_error_m=state[0], heading_error_rad=state[1],
                previous_curvature_correction_per_m=state[2], residual_profile_m=residual,
                stations_m=np.asarray(STATIONS_M), speed_mps=speed,
                dt_s=pilot.DT_S, config=pilot.CONFIG).curvature_correction_per_m

        for initial in (np.array([0.4, 0.01, -0.002]), np.array([-0.7, -0.02, 0.003])):
            nominal, perturbed = initial.copy(), initial.copy()
            for t, speed in enumerate(speeds):
                a = command(nominal, nominal_profiles[t], speed)
                b = command(perturbed, nominal_profiles[t] + profiles[t], speed)
                self.assertAlmostEqual((b-a) * speed**2, acceleration[0, t], places=11)
                self.assertAlmostEqual(perturbed[0]-nominal[0], lateral[0, t], places=12)
                if t < len(intervals):
                    distance = speed * intervals[t]
                    # Independent explicit update, plus a common affine forcing.
                    forcing = np.array([0.02, -0.001, 0.0])
                    nominal = np.array([nominal[0]+distance*nominal[1], nominal[1]+distance*a, a])+forcing
                    perturbed = np.array([perturbed[0]+distance*perturbed[1], perturbed[1]+distance*b, b])+forcing

    def test_draw_permutation_preserves_each_whole_profile_and_initial_frame(self):
        rng = np.random.default_rng(11)
        profiles = rng.normal(size=(128, 7, 21))
        permuted = pilot.permute_draws(profiles, np.array([0, 3, 7]), 71)
        np.testing.assert_array_equal(permuted[:, [0, 3]], profiles[:, [0, 3]])
        for t in range(7):
            original_order = np.argsort(profiles[:, t, 0])
            new_order = np.argsort(permuted[:, t, 0])
            np.testing.assert_array_equal(profiles[original_order, t], permuted[new_order, t])
        self.assertFalse(np.array_equal(profiles[:, 1], permuted[:, 1]))
        np.testing.assert_array_equal(permuted, pilot.permute_draws(profiles, np.array([0, 3, 7]), 71))

    def test_source_intervals_keep_decimal_precision_and_reject_whole_sequence(self):
        block = scenario_fixture.CachedScenarioPolicyTests().block()
        block.x[:, 0] = 20
        block.archive.arrays["estimate_source_time_ns_decimal"] = np.array(
            [str(10**19 + i*50_000_000) for i in range(7)])
        fold = {"validation_outing": block.outing_id, "training_outings": ["other"]}
        _, arrays, records, support = pilot.prepare(block, fold)
        self.assertEqual(support["eligible_sequences"], 2)
        self.assertEqual(records[0]["interval_ns"], [100_000_000])
        self.assertEqual(support["lateral_state_assessed_sequences"], 0)
        block.archive.arrays["estimate_source_time_ns_decimal"][2] = str(10**19 + 400_000_000)
        _, _, records, support = pilot.prepare(block, fold)
        self.assertEqual(support["eligible_sequences"], 1)
        self.assertEqual(records[0]["status"], "source_interval_outside_planner_range")
        self.assertEqual(len(arrays["residuals_m"]), 4)

    def test_sequence_score_matches_pairwise_definition_and_resets(self):
        rng = np.random.default_rng(7)
        arrays = dict(residuals_m=rng.normal(size=(5, 21)), speed_mps=np.full(5, 20.))
        records = [dict(start_row=0, stop_row=2, sequence_index=0, interval_ns=[100_000_000], status="eligible"),
                   dict(start_row=2, stop_row=5, sequence_index=1, interval_ns=[100_000_000]*2, status="eligible")]
        native = rng.normal(size=(128, 5, 21))
        arms = {name: native.copy() for name in pilot.ARMS}
        arms["nominal"] = np.zeros((1, 5, 21))
        scored = pilot.score(arrays, records, arms)
        observed, _ = pilot.rollout(arrays["residuals_m"][None, 2:], arrays["speed_mps"][2:], np.array([.1, .1]))
        draws, _ = pilot.rollout(native[:, 2:], arrays["speed_mps"][2:], np.array([.1, .1]))
        first = sum(np.sqrt(np.square(row-observed[0]).sum()) for row in draws) / 128
        second = sum(np.sqrt(np.square(a-b).sum()) for a in draws for b in draws) / 128**2
        expected = (first-second/2)/np.sqrt(3)
        actual = scored["sequence_scores"][1]["arms"]["one_state_ar"]["normalized_command_sequence_energy_mps2"]
        self.assertAlmostEqual(actual, expected, places=12)
        self.assertIsNone(scored["sequence_scores"][0]["arms"]["one_state_ar"]["peak_incremental_state_lateral_crps_m"])
        self.assertEqual(scored["temporal_minus_permuted_energy_mps2"]["one_state_ar"], 0)

    def test_no_terminal_update_and_unsupported_lookahead(self):
        profiles = np.zeros((1, 2, 21))
        profiles[:, 0] = .1
        _, lateral = pilot.rollout(profiles, np.full(2, 20.), np.array([.1]))
        np.testing.assert_array_equal(lateral, 0)
        with self.assertRaisesRegex(ValueError, "unsupported_speed"):
            pilot.rollout(profiles, np.array([20., 41.]), np.array([.1]))


if __name__ == "__main__":
    unittest.main()
