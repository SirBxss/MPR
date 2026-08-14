import unittest

import numpy as np

from lane_residuals import Path2D, residual_matrix, residual_vector


class ResidualTests(unittest.TestCase):
    def test_straight_path_has_left_positive_residual(self) -> None:
        ground_truth = Path2D(
            s=[0.0, 5.0, 10.0],
            x=[0.0, 5.0, 10.0],
            y=[0.0, 0.0, 0.0],
        )
        estimate = Path2D(
            s=[0.0, 10.0],
            x=[0.0, 10.0],
            y=[0.75, 0.75],
        )

        actual = residual_vector(ground_truth, estimate, stations=[0.0, 2.5, 10.0])

        np.testing.assert_allclose(actual, [0.75, 0.75, 0.75])

    def test_straight_path_has_right_negative_residual(self) -> None:
        ground_truth = Path2D([0.0, 10.0], [0.0, 10.0], [0.0, 0.0])
        estimate = Path2D([0.0, 10.0], [0.0, 10.0], [-0.25, -0.25])

        actual = residual_vector(ground_truth, estimate, stations=[0.0, 10.0])

        np.testing.assert_allclose(actual, [-0.25, -0.25])

    def test_normal_offset_is_recovered_for_curved_path(self) -> None:
        stations = np.linspace(0.0, 20.0, 41)
        ground_truth = Path2D(stations, stations, 0.01 * stations**2)
        normals = ground_truth.unit_left_normals(stations)
        ground_truth_points = ground_truth.sample(stations)
        expected = 0.1 + 0.01 * stations
        estimate_points = ground_truth_points + expected[:, None] * normals
        estimate = Path2D(stations, estimate_points[:, 0], estimate_points[:, 1])

        actual = residual_vector(ground_truth, estimate, stations)

        np.testing.assert_allclose(actual, expected, atol=1e-12)

    def test_path_pairs_are_stacked_as_rows(self) -> None:
        ground_truth = Path2D([0.0, 10.0], [0.0, 10.0], [0.0, 0.0])
        estimate_left = Path2D([0.0, 10.0], [0.0, 10.0], [1.0, 1.0])
        estimate_right = Path2D([0.0, 10.0], [0.0, 10.0], [-2.0, -2.0])

        actual = residual_matrix(
            [(ground_truth, estimate_left), (ground_truth, estimate_right)],
            stations=[0.0, 5.0, 10.0],
        )

        np.testing.assert_allclose(
            actual,
            [[1.0, 1.0, 1.0], [-2.0, -2.0, -2.0]],
        )
        self.assertEqual(actual.shape, (2, 3))

    def test_requested_stations_must_be_covered_by_both_paths(self) -> None:
        ground_truth = Path2D([0.0, 10.0], [0.0, 10.0], [0.0, 0.0])
        short_estimate = Path2D([0.0, 8.0], [0.0, 8.0], [0.0, 0.0])

        with self.assertRaisesRegex(ValueError, "estimate does not cover"):
            residual_vector(ground_truth, short_estimate, stations=[0.0, 10.0])

    def test_invalid_paths_are_rejected(self) -> None:
        cases = [
            ([0.0], [0.0], [0.0], "at least two"),
            ([0.0, 1.0], [0.0], [0.0, 1.0], "same length"),
            ([0.0, 0.0], [0.0, 1.0], [0.0, 1.0], "strictly increasing"),
            ([0.0, 1.0], [0.0, np.nan], [0.0, 1.0], "finite"),
        ]
        for s, x, y, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    Path2D(s=s, x=x, y=y)


if __name__ == "__main__":
    unittest.main()
