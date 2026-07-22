import unittest

import numpy as np

from lane_residuals import GaussianResidualModel, fit_gaussian_residual_model


class GaussianResidualModelTests(unittest.TestCase):
    def test_fit_uses_mle_mean_covariance_and_regularization(self) -> None:
        residuals = np.array(
            [
                [0.0, 1.0],
                [2.0, 3.0],
                [4.0, 5.0],
            ]
        )

        model = fit_gaussian_residual_model(residuals, regularization=0.25)

        np.testing.assert_allclose(model.mean, [2.0, 3.0])
        np.testing.assert_allclose(
            model.covariance,
            [[8.0 / 3.0 + 0.25, 8.0 / 3.0], [8.0 / 3.0, 8.0 / 3.0 + 0.25]],
        )
        self.assertEqual(model.n_training_samples, 3)
        self.assertEqual(model.dimension, 2)

    def test_logpdf_matches_standard_normal_formula(self) -> None:
        model = GaussianResidualModel(
            mean=[0.0],
            covariance=[[1.0]],
            n_training_samples=10,
            regularization=0.0,
        )

        actual = model.logpdf([[0.0], [1.0]])
        expected = -0.5 * (np.log(2.0 * np.pi) + np.array([0.0, 1.0]))

        np.testing.assert_allclose(actual, expected)
        self.assertAlmostEqual(model.negative_log_likelihood([[0.0]]), -expected[0])

    def test_sampling_is_reproducible_and_has_expected_shape(self) -> None:
        model = GaussianResidualModel(
            mean=[0.5, -0.5],
            covariance=[[1.0, 0.3], [0.3, 2.0]],
            n_training_samples=10,
            regularization=0.0,
        )

        first = model.sample(4, rng=np.random.default_rng(12))
        second = model.sample(4, rng=np.random.default_rng(12))

        self.assertEqual(first.shape, (4, 2))
        np.testing.assert_allclose(first, second)

    def test_regularization_makes_rank_deficient_fit_usable(self) -> None:
        residuals = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0],
            ]
        )

        model = fit_gaussian_residual_model(residuals, regularization=1e-6)

        self.assertTrue(np.all(np.isfinite(model.logpdf(residuals))))

    def test_invalid_training_data_is_rejected(self) -> None:
        invalid_cases = [
            (np.array([1.0, 2.0]), "two-dimensional"),
            (np.empty((0, 2)), "must not be empty"),
            (np.array([[1.0, np.nan], [2.0, 3.0]]), "finite"),
            (np.array([[1.0, 2.0]]), "at least two"),
        ]

        for residuals, message in invalid_cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    fit_gaussian_residual_model(residuals)

    def test_likelihood_rejects_wrong_residual_dimension(self) -> None:
        model = GaussianResidualModel(
            mean=[0.0, 0.0],
            covariance=np.eye(2),
            n_training_samples=10,
            regularization=0.0,
        )

        with self.assertRaisesRegex(ValueError, "2 columns"):
            model.logpdf([[0.0, 0.0, 0.0]])


if __name__ == "__main__":
    unittest.main()
