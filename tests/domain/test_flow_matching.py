from __future__ import annotations

import unittest

import numpy as np

from lane_residuals.domain.flow_matching import linear_flow_batch, integrate_euler, sample_free_running


class FlowMatchingMathTests(unittest.TestCase):
    def test_linear_path_velocity_and_observed_previous_reset(self):
        y = np.arange(4.0)[:, None] * np.ones((1, 21))
        noise = -np.ones((4, 21))
        x = np.zeros((4, 6))
        tau = np.array([0., .25, .5, 1.])
        batch = linear_flow_batch(y, x, np.array([0, 2, 4]), noise, tau)
        np.testing.assert_allclose(batch.bridge, (1 - tau[:, None]) * noise + tau[:, None] * y)
        np.testing.assert_allclose(batch.target_velocity, y - noise)
        np.testing.assert_allclose(batch.observed_previous[:, 0], [0., 0., 0., 2.])

    def test_euler_constant_velocity_and_free_running_feedback_with_sequence_reset(self):
        def field(z, tau, conditions, previous):
            self.assertTrue(np.all((tau >= 0) & (tau < 1)))
            return previous + conditions[:, 0, None] + np.zeros_like(z)

        x = np.zeros((2, 3, 6))
        x[:, :, 0] = [[1., 2., 999.], [3., 4., 5.]]
        noise = np.zeros((2, 2, 3, 21))
        result = sample_free_running(field, x, np.array([2, 3]), noise, 4)
        self.assertEqual(result.shape, (2, 2, 3, 21))
        np.testing.assert_allclose(result[:, 0, :, 0], [[1., 3., 0.], [1., 3., 0.]])
        np.testing.assert_allclose(result[:, 1, :, 0], [[3., 7., 12.], [3., 7., 12.]])
        np.testing.assert_allclose(integrate_euler(field, np.zeros((1, 21)),
                                   x[0, 0:1], np.zeros((1, 21)), 2), 1.)

    def test_invalid_shapes_steps_nonfinite_velocity_and_offset_gaps_rejected(self):
        x = np.zeros((2, 6))
        y = np.zeros((2, 21))
        for offsets in ([0, 1, 1, 2], [0, 3], [1, 2]):
            with self.assertRaises(ValueError):
                linear_flow_batch(y, x, np.asarray(offsets), y, np.zeros(2))
        with self.assertRaises(ValueError):
            linear_flow_batch(y, x, np.array([0, 2]), y, np.array([.5, 1.1]))
        with self.assertRaises(ValueError):
            integrate_euler(lambda *args: y, y, x, y, 0)
        with self.assertRaises(ValueError):
            integrate_euler(lambda *args: np.full((2, 21), np.nan), y, x, y, 2)
        with self.assertRaises(ValueError):
            sample_free_running(lambda *args: y, np.zeros((1, 2, 6)),
                                np.array([3]), np.zeros((1, 1, 2, 21)), 2)


if __name__ == "__main__":
    unittest.main()
