from __future__ import annotations

import unittest

import numpy as np

from lane_residuals.domain.spatial_structure import (
    mean_adjacent_correlation,
    mean_off_diagonal_correlation,
    population_spatial_moments,
)


class SpatialStructureTest(unittest.TestCase):
    def test_population_moments_use_population_denominator(self) -> None:
        profiles = np.asarray(
            [[0.0, 1.0, 2.0], [1.0, 2.0, 4.0], [2.0, 4.0, 5.0]],
            dtype=np.float64,
        )

        moments = population_spatial_moments(profiles)

        np.testing.assert_allclose(
            moments.mean, np.asarray([1.0, 7.0 / 3.0, 11.0 / 3.0])
        )
        expected_covariance = np.asarray(
            [
                [2.0 / 3.0, 1.0, 1.0],
                [1.0, 14.0 / 9.0, 13.0 / 9.0],
                [1.0, 13.0 / 9.0, 14.0 / 9.0],
            ],
            dtype=np.float64,
        )
        np.testing.assert_allclose(moments.covariance, expected_covariance)
        np.testing.assert_array_equal(np.diag(moments.correlation), np.ones(3))
        self.assertAlmostEqual(
            mean_adjacent_correlation(moments.correlation),
            float(np.mean([moments.correlation[0, 1], moments.correlation[1, 2]])),
        )
        self.assertAlmostEqual(
            mean_off_diagonal_correlation(moments.correlation),
            float(
                np.mean(
                    [
                        moments.correlation[0, 1],
                        moments.correlation[0, 2],
                        moments.correlation[1, 2],
                    ]
                )
            ),
        )

    def test_rejects_non_float64_nonfinite_and_zero_variance(self) -> None:
        with self.assertRaisesRegex(TypeError, "float64"):
            population_spatial_moments(np.ones((3, 2), dtype=np.float32))
        with self.assertRaisesRegex(ValueError, "finite"):
            population_spatial_moments(
                np.asarray([[0.0, 1.0], [1.0, np.nan]], dtype=np.float64)
            )
        with self.assertRaisesRegex(ValueError, "positive population variance"):
            population_spatial_moments(
                np.asarray([[0.0, 1.0], [0.0, 2.0]], dtype=np.float64)
            )

    def test_rejects_invalid_shape_and_tolerance(self) -> None:
        with self.assertRaisesRegex(ValueError, "shape"):
            population_spatial_moments(np.ones((1, 2), dtype=np.float64))
        with self.assertRaisesRegex(ValueError, "tolerance"):
            population_spatial_moments(
                np.asarray([[0.0, 0.0], [1.0, 2.0]], dtype=np.float64),
                correlation_tolerance=-1.0,
            )


if __name__ == "__main__":
    unittest.main()
