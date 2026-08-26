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
