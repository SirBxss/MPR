import math
import unittest

import numpy as np

from lane_residuals.modeling.gaussian_diagnostics import (
    chi_square_cdf,
    chi_square_quantile,
    leave_one_group_out_gaussian_predictions,
    marginal_calibration_statistics,
    multivariate_calibration_statistics,
    probability_integral_transform_ks,
    standard_normal_two_sided_quantile,
)


class GaussianAdequacyMathTests(unittest.TestCase):
    def test_chi_square_df_two_matches_closed_form(self) -> None:
        for value in (0.0, 0.1, 1.0, 2.0, 5.0, 10.0):
            self.assertAlmostEqual(
                chi_square_cdf(value, degrees_of_freedom=2),
                1.0 - math.exp(-value / 2.0),
                places=12,
            )
        for probability in (0.5, 0.9, 0.95, 0.99):
            self.assertAlmostEqual(
                chi_square_quantile(probability, degrees_of_freedom=2),
                -2.0 * math.log(1.0 - probability),
                places=10,
            )

    def test_leave_one_group_out_predictions_align_with_source_rows(self) -> None:
        residuals = np.asarray(
            [
                [-0.3, -0.1],
                [-0.1, 0.0],
                [0.2, 0.1],
                [0.4, 0.3],
                [0.0, -0.2],
                [0.1, 0.0],
                [0.3, 0.2],
                [0.5, 0.4],
            ]
        )
        groups = ("a", "a", "a", "a", "b", "b", "b", "b")

        result = leave_one_group_out_gaussian_predictions(
            residuals,
            groups,
            regularization=1e-4,
        )

        self.assertEqual(result.standardized_marginal_errors.shape, (8, 2))
        self.assertEqual(result.squared_mahalanobis.shape, (8,))
        self.assertTrue(np.all(result.squared_mahalanobis >= 0.0))
        self.assertTrue(np.all(np.isfinite(result.joint_negative_log_likelihood)))

    def test_marginal_statistics_report_shape_and_multiple_coverages(self) -> None:
        values = np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0])

        result = marginal_calibration_statistics(values)

        self.assertAlmostEqual(result["standardized_mean"], 0.0)
        self.assertAlmostEqual(result["skewness"], 0.0)
        self.assertIn("coverage_50", result)
        self.assertIn("coverage_95", result)
        self.assertIn("coverage_99", result)
        self.assertGreater(result["normal_qq_correlation"], 0.99)

    def test_multivariate_statistics_use_chi_square_reference(self) -> None:
        probabilities = np.linspace(0.05, 0.95, 19)
        squared = np.asarray(
            [chi_square_quantile(float(p), degrees_of_freedom=2) for p in probabilities]
        )
        nll = 0.5 * squared

        result = multivariate_calibration_statistics(
            squared,
            nll,
            dimension=2,
        )

        self.assertEqual(result["vector_count"], 19)
        self.assertGreater(result["chi_square_qq_correlation"], 0.99)
        self.assertLess(result["chi_square_pit_ks_distance"], 0.06)
        self.assertIn("above_chi_square_p95_rate", result)

    def test_pit_ks_and_normal_quantile_validation(self) -> None:
        self.assertAlmostEqual(
            probability_integral_transform_ks([0.1, 0.3, 0.5, 0.7, 0.9]),
            0.1,
        )
        self.assertAlmostEqual(
            standard_normal_two_sided_quantile(0.95),
            1.959963984540054,
        )
        with self.assertRaisesRegex(ValueError, "strictly within"):
            standard_normal_two_sided_quantile(1.0)


if __name__ == "__main__":
    unittest.main()
