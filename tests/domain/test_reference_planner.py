import unittest

import numpy as np

from lane_residuals.domain.reference_planner import (
    ReferencePlannerConfig,
    perturb_path_left_normal,
    plan_reference_step,
    signed_curvature_at_origin,
)


class ReferencePlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stations = np.arange(0.0, 101.0, 5.0)
        self.path = np.column_stack((self.stations, np.zeros(21)))
        self.config = ReferencePlannerConfig()

    def test_positive_residual_moves_straight_path_to_left(self) -> None:
        perturbed = perturb_path_left_normal(self.path, np.full(21, 0.2))
        np.testing.assert_allclose(perturbed[:, 0], self.stations)
        np.testing.assert_allclose(perturbed[:, 1], 0.2)
        self.assertEqual(signed_curvature_at_origin(self.path), 0.0)

    def test_signed_curvature_follows_left_turn(self) -> None:
        angle = self.stations / 50.0
        path = np.column_stack((50.0 * np.sin(angle), 50.0 * (1.0 - np.cos(angle))))
        self.assertAlmostEqual(signed_curvature_at_origin(path), 0.02, places=5)

    def test_zero_reference_preserves_zero_error_state(self) -> None:
        step = plan_reference_step(
            lateral_error_m=0.0,
            heading_error_rad=0.0,
            previous_curvature_correction_per_m=0.0,
            residual_profile_m=np.zeros(21),
            stations_m=self.stations,
            speed_mps=10.0,
            dt_s=0.08,
            config=self.config,
        )
        self.assertEqual(step.lateral_error_m, 0.0)
        self.assertEqual(step.heading_error_rad, 0.0)
        self.assertEqual(step.curvature_correction_per_m, 0.0)
        self.assertEqual(step.objective, 0.0)

    def test_positive_reference_generates_left_curvature(self) -> None:
        step = plan_reference_step(
            lateral_error_m=0.0,
            heading_error_rad=0.0,
            previous_curvature_correction_per_m=0.0,
            residual_profile_m=np.full(21, 0.2),
            stations_m=self.stations,
            speed_mps=10.0,
            dt_s=0.08,
            config=self.config,
        )
        self.assertGreater(step.curvature_correction_per_m, 0.0)
        self.assertGreater(step.heading_error_rad, 0.0)

    def test_nonconstant_reference_matches_direct_horizon_optimum(self) -> None:
        config = ReferencePlannerConfig(horizon_steps=6)
        residual = 0.002 * self.stations + 0.00002 * self.stations**2
        speed = 12.0
        dt_s = 0.08
        distance = speed * dt_s
        initial = np.asarray([0.03, -0.01, 0.004], dtype=np.float64)
        references = np.interp(
            distance * (np.arange(config.horizon_steps) + 1),
            self.stations,
            residual,
        )

        def objective(controls: np.ndarray) -> float:
            lateral, heading, previous = initial
            total = 0.0
            for index, control in enumerate(controls):
                lateral = lateral + distance * heading
                heading = heading + distance * control
                multiplier = (
                    config.terminal_multiplier
                    if index == config.horizon_steps - 1
                    else 1.0
                )
                total += multiplier * (
                    config.weight_lateral
                    * (lateral - references[index]) ** 2
                    + config.weight_heading * heading**2
                )
                total += config.weight_curvature * control**2
                total += config.weight_curvature_rate * (control - previous) ** 2
                previous = control
            return float(total)

        count = config.horizon_steps
        epsilon = 1e-4
        zero = np.zeros(count, dtype=np.float64)
        zero_objective = objective(zero)
        gradient = np.empty(count, dtype=np.float64)
        hessian = np.empty((count, count), dtype=np.float64)
        for first in range(count):
            first_step = np.zeros(count, dtype=np.float64)
            first_step[first] = epsilon
            gradient[first] = (
                objective(first_step) - objective(-first_step)
            ) / (2.0 * epsilon)
            hessian[first, first] = (
                objective(first_step)
                + objective(-first_step)
                - 2.0 * zero_objective
            ) / epsilon**2
            for second in range(first):
                second_step = np.zeros(count, dtype=np.float64)
                second_step[second] = epsilon
                hessian[first, second] = hessian[second, first] = (
                    objective(first_step + second_step)
                    - objective(first_step - second_step)
                    - objective(-first_step + second_step)
                    + objective(-first_step - second_step)
                ) / (4.0 * epsilon**2)
        direct_controls = np.linalg.solve(hessian, -gradient)
        step = plan_reference_step(
            lateral_error_m=float(initial[0]),
            heading_error_rad=float(initial[1]),
            previous_curvature_correction_per_m=float(initial[2]),
            residual_profile_m=residual,
            stations_m=self.stations,
            speed_mps=speed,
            dt_s=dt_s,
            config=config,
        )
        self.assertAlmostEqual(
            step.curvature_correction_per_m,
            float(direct_controls[0]),
            places=9,
        )
        self.assertAlmostEqual(step.objective, objective(direct_controls), places=9)

    def test_invalid_timestep_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "frame interval"):
            plan_reference_step(
                lateral_error_m=0.0,
                heading_error_rad=0.0,
                previous_curvature_correction_per_m=0.0,
                residual_profile_m=np.zeros(21),
                stations_m=self.stations,
                speed_mps=10.0,
                dt_s=1.0,
                config=self.config,
            )


if __name__ == "__main__":
    unittest.main()
