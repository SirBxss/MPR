"""Independent native solve, cost arithmetic and training-only choice checks."""

from copy import deepcopy
import unittest

import numpy as np

from lane_residuals.domain import planner_parameter_selection as policy
from lane_residuals.domain.reference_planner import plan_reference_step
from lane_residuals.domain.spatial_planner_response import STATIONS_M


class PlannerParameterSelectionTests(unittest.TestCase):
    def test_all_candidate_maps_match_independent_native_solves(self):
        rng = np.random.default_rng(34)
        for candidate in range(9):
            for speed in (.1, 12., 20.3, 40.):
                k, g = policy.control_map(candidate, speed)
                for _ in range(3):
                    state = rng.normal(size=3)*np.array([.3, .02, .001])
                    profile = rng.normal(0, .1, 21)
                    native = plan_reference_step(lateral_error_m=state[0], heading_error_rad=state[1],
                        previous_curvature_correction_per_m=state[2], residual_profile_m=profile,
                        stations_m=np.array(STATIONS_M), speed_mps=speed, dt_s=.1, config=policy.config(candidate))
                    self.assertAlmostEqual(float(state@k+profile@g), native.curvature_correction_per_m, places=12)
        self.assertEqual(policy.config(policy.DEFAULT), policy.BASE)
        self.assertRaises(ValueError, policy.control_map, 0, 40.01)

    def test_owner_engineering_screen_rejects_zero_control_nominal_probe(self):
        report=policy.engineering_screen()
        self.assertEqual(report["cases"],108)
        self.assertLess(report["maximum_command_difference_per_m"],1e-10)
        self.assertTrue(report["unresponsive_nominal_control_rejected"])

    def test_response_costs_match_direct_native_rollout_and_physical_normalization(self):
        rng = np.random.default_rng(19)
        profiles = rng.normal(0, .02, (2, 4, 21))
        speed = np.array([12., 14., 15., 13.])
        dt = np.array([.09, .1, .11])
        for candidate in (0, policy.DEFAULT, 8):
            actual = policy.rollout_costs(profiles, speed, dt, candidate, policy.TASKS)
            expected = {m: np.zeros((2, 4)) for m in policy.METRICS}
            for draw in range(2):
                for task, initial in enumerate(policy.TASKS):
                    state, states, commands = initial.copy(), [], []
                    for t, velocity in enumerate(speed):
                        states.append(state.copy())
                        step = plan_reference_step(lateral_error_m=state[0], heading_error_rad=state[1],
                            previous_curvature_correction_per_m=state[2], residual_profile_m=profiles[draw, t],
                            stations_m=np.array(STATIONS_M), speed_mps=velocity, dt_s=.1, config=policy.config(candidate))
                        u = step.curvature_correction_per_m
                        commands.append(u*velocity**2)
                        if t < len(dt):
                            state = np.array([state[0]+velocity*dt[t]*state[1], state[1]+velocity*dt[t]*u, u])
                    states, commands = np.array(states), np.array(commands)
                    jerk = np.diff(commands)/dt
                    tracking = np.mean((states[1:,0]/.03)**2 + (states[1:,1]/.003)**2)
                    acceleration, smoothness = np.mean((commands/3.)**2), np.mean((jerk/5.)**2)
                    values = (tracking, acceleration, smoothness, tracking+acceleration+smoothness,
                              float(np.max(np.abs(states[1:,0])) > 1.), float(np.max(np.abs(commands)) > 3.),
                              float(np.max(np.abs(jerk)) > 5.))
                    for metric, value in zip(policy.METRICS, values):
                        expected[metric][draw,task] = value
            for metric in policy.METRICS:
                np.testing.assert_allclose(actual[metric], expected[metric], rtol=1e-11, atol=1e-12)

    def test_metadata_context_spread_preserves_whole_sequences_and_exact_clocks(self):
        rows = []
        for index in range(22):
            rows.append(dict(sequence_index=index, status="eligible", frame_count=2 if index==0 else 4,
                start_row=index*4, stop_row=index*4+4, source_start_ns_decimal=str(10**19+index*1_000_000_000),
                interval_ns=[100_000_001]*3, unused_residual_value=float(index)))
        first = policy.context_descriptors({"train":rows}, ["train"])
        self.assertEqual(len(first), 12)
        self.assertEqual(first[0]["original_sequence_index"], 1)
        self.assertEqual(first[-1]["original_sequence_index"], 21)
        self.assertEqual(first[-1]["stop_row"], 48)
        self.assertEqual(first[0]["interval_ns"], [100_000_001]*3)
        for row in rows:
            row["unused_residual_value"] = -1e99
        self.assertEqual(first, policy.context_descriptors({"train":rows}, ["train"]))
        self.assertRaises(ValueError, policy.select_context_indices, rows[:11])

    def grid(self):
        ids = [str(i) for i in range(6) for _ in range(12)]
        costs = np.full((9, 8, 2, 72, len(policy.METRICS)), 10.)
        costs[policy.DEFAULT, :, :, :, policy.METRICS.index("loss")] = 5.
        return ids, dict(costs=costs, nominal_tracking=np.ones((9,72,4)), nominal_probe_tracking=policy.nominal_probes().copy(), decomposition=np.zeros((9,8,2,72,3,4)),total_tails=np.zeros((9,8,2,72,3)))

    def test_nominal_probes_block_attractive_unresponsive_choice_and_prefix_is_separate(self):
        ids, grid = self.grid()
        ix = policy.METRICS.index("loss")
        grid["costs"][0,:,:,:,ix] = 0.
        grid["nominal_probe_tracking"][0] = 2.
        grid["costs"][8,:,:,:,ix] = 2.
        grid["costs"][1,:,1,:,ix] = 1.
        result = policy.select_parameters(grid, ids)
        for name, setting in result["settings"].items():
            self.assertNotIn(0, setting["feasible_candidates"])
            self.assertEqual(setting["selected_candidates"]["one_state_ar"], 1 if setting["draws"]==32 else 8)
        self.assertRaises(ValueError, policy.select_parameters, grid, ["held"]*72)

    def test_gate_sensitivity_and_default_first_ties_are_predeclared(self):
        ids, grid = self.grid()
        ix = policy.METRICS.index("loss")
        grid["costs"][:,:,:,:,ix] = 5.
        result = policy.select_parameters(grid, ids)
        self.assertEqual(result["settings"]["draws_64_gate_0.20"]["selected_candidates"]["empirical"], policy.DEFAULT)
        grid["costs"][8,:,:,:,ix] = 1.
        grid["nominal_tracking"][8] = 1.3
        result = policy.select_parameters(grid, ids)
        self.assertEqual(result["settings"]["draws_64_gate_0.20"]["selected_candidates"]["one_state_ar"], policy.DEFAULT)
        self.assertEqual(result["settings"]["draws_64_gate_0.40"]["selected_candidates"]["one_state_ar"], 8)
        probes = policy.nominal_probes()
        self.assertEqual(probes.shape, (9,3,4))
        self.assertTrue(np.isfinite(probes).all())
        self.assertTrue((probes[policy.DEFAULT] > 0).all())
        self.assertFalse(probes.flags.writeable)

    def test_grid_prefix_reuses_native_draws_and_no_unobserved_terminal_state(self):
        rng = np.random.default_rng(2)
        arms = {a:rng.normal(0,.01,(64,3,21)) for a in policy.ARMS}
        arms["zero_disturbance"] = np.zeros((1,3,21))
        record = dict(start_row=0,stop_row=3,interval_ns=[90_000_000,110_000_000])
        speeds = np.full(3,20.)
        grid = policy.grid_costs(arms,speeds,[record])
        values = policy.response_costs(arms["conditional_flow"][:32],speeds,np.array([.09,.11]),0)
        np.testing.assert_allclose(grid["costs"][0,-1,1,0],[values[m].mean() for m in policy.METRICS])
        self.assertRaises(ValueError, policy.response_costs, arms["conditional_flow"][:,:2], speeds[:2], np.array([.1]), 0)

    def test_oracle_is_retrospective_and_held_nominal_failures_remain_visible(self):
        ids, grid = self.grid()
        selection = policy.select_parameters(grid, ids)
        selected = deepcopy(selection)
        held = dict(candidate_mean_metrics=[{m:float(9-i) for m in policy.METRICS} for i in range(9)],
                    nominal_tracking_by_sequence_candidate_task=np.ones((2,9,4)).tolist(),nominal_peaks_by_sequence_candidate=np.zeros((2,9,2)).tolist())
        result = policy.compare_choices(selection,held)
        main=result["draws_64_gate_0.20"]
        self.assertEqual(main["methods"]["one_state_ar"]["candidate"],policy.DEFAULT)
        self.assertEqual(main["retrospective_grid_oracle_loss"],1.)
        self.assertEqual(main["methods"]["one_state_ar"]["regret_vs_training_feasible_grid_oracle"],4.)
        self.assertEqual(selection,selected)
        summary=policy.summarize({str(i):result for i in range(7)})
        self.assertFalse(summary["descriptive_primary_risk_improves"])
        self.assertTrue(summary["primary_held_nominal_requirement_passes"])
        main["methods"]["one_state_ar"]["nominal_violating_outings"]=1
        summary=policy.summarize({str(i):result for i in range(7)})
        self.assertFalse(summary["primary_held_nominal_requirement_passes"])
        self.assertFalse(summary["development_recommendation_supported"])


if __name__ == "__main__":
    unittest.main()
