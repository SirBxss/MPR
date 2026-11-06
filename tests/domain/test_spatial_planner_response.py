import unittest

import numpy as np

from lane_residuals.domain.reference_planner import (
    ReferencePlannerConfig,
    plan_reference_horizon,
    plan_reference_step,
)
from lane_residuals.domain.spatial_planner_response import (
    STATIONS_M,
    SpatialPlannerScenario,
    build_spatial_response,
)
from lane_residuals.workflows.spatial_planner_benchmark import benchmark_spatial_profiles


class SpatialPlannerResponseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ReferencePlannerConfig()
        self.scenario = SpatialPlannerScenario(17.0, 0.1, 0.12, 0.016, 0.001)
        self.stations = np.asarray(STATIONS_M)
        self.inputs = dict(
            stations_m=self.stations,
            config=self.config,
            speed_mps=self.scenario.speed_mps,
            dt_s=self.scenario.dt_s,
            lateral_error_m=self.scenario.lateral_error_m,
            heading_error_rad=self.scenario.heading_error_rad,
            previous_curvature_correction_per_m=self.scenario.previous_curvature_correction_per_m,
        )

    def test_affine_response_matches_direct_nonzero_state_rollout(self) -> None:
        residual = 0.12 + 0.15 * np.sin(self.stations / 25)
        nominal = plan_reference_horizon(residual_profile_m=np.zeros(21), **self.inputs)
        perturbed = plan_reference_horizon(residual_profile_m=residual, **self.inputs)
        step = plan_reference_step(residual_profile_m=residual, **self.inputs)
        self.assertEqual(perturbed.first_step, step)
        self.assertEqual(perturbed.curvature_correction_per_m[0], step.curvature_correction_per_m)
        self.assertEqual(perturbed.lateral_error_m[0], step.lateral_error_m)
        self.assertEqual(len(perturbed.distances_m), self.config.horizon_steps)

        response = build_spatial_response(self.scenario, self.config)
        metrics = response.evaluate(residual)
        lateral_delta = perturbed.lateral_error_m - nominal.lateral_error_m
        curvature_delta = perturbed.curvature_correction_per_m - nominal.curvature_correction_per_m
        np.testing.assert_allclose(residual @ response.lateral_response, lateral_delta, atol=2e-15)
        np.testing.assert_allclose(residual @ response.curvature_response, curvature_delta, atol=2e-15)
        self.assertAlmostEqual(metrics["peak_planned_lateral_change_m"], np.max(np.abs(lateral_delta)))
        self.assertAlmostEqual(metrics["first_curvature_change_per_m"], curvature_delta[0])

    def test_far_station_outside_lookahead_has_no_effect(self) -> None:
        response = build_spatial_response(self.scenario, self.config)
        only_far = np.zeros(21)
        only_far[-1] = 1.0
        self.assertEqual(response.evaluate(only_far)["peak_planned_lateral_change_m"], 0.0)
        self.assertEqual(response.evaluate(only_far)["first_curvature_change_per_m"], 0.0)
        with self.assertRaisesRegex(ValueError, "100 m"):
            build_spatial_response(SpatialPlannerScenario(60.0, 0.1), self.config)

    def test_replay_identical_point_forecast_has_zero_crps(self) -> None:
        response = build_spatial_response(self.scenario, self.config)
        profiles = np.full((4, 21), 0.2)
        result = benchmark_spatial_profiles(response, profiles, {"identical": profiles})
        self.assertEqual(result["draws_per_sampled_arm"], 4)
        for metric in result["arms"]["replay"]:
            self.assertEqual(result["arms"]["identical"][metric]["crps_vs_replay"], 0.0)
            self.assertGreater(result["arms"]["nominal"][metric]["crps_vs_replay"], 0.0)
        with self.assertRaisesRegex(ValueError, "common draw count"):
            benchmark_spatial_profiles(response, profiles, {"a": profiles, "b": np.tile(profiles, (2, 1))})
