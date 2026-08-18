import unittest

import numpy as np

from lane_residuals.modeling.conditional_gaussian import (
    ConditionalGaussianResidualModel,
    fit_linear_conditional_gaussian,
)


class ConditionalGaussianModelTests(unittest.TestCase):
    def test_fit_recovers_linear_conditional_mean(self) -> None:
        rng = np.random.default_rng(42)
        features = rng.normal(size=(400, 2))
        coefficients = np.asarray(((0.3, -0.2, 0.1), (-0.1, 0.4, 0.2)))
        intercept = np.asarray((0.05, -0.03, 0.02))
        residuals = intercept + features @ coefficients
        residuals += rng.normal(scale=0.01, size=residuals.shape)

        model = fit_linear_conditional_gaussian(
            features,
            residuals,
            feature_names=("speed", "curvature"),
            covariance_regularization_m2=1e-6,
        )

        predictions = model.predict_mean(features)
        self.assertEqual(predictions.shape, residuals.shape)
        self.assertLess(float(np.sqrt(np.mean((residuals - predictions) ** 2))), 0.012)
        self.assertEqual(model.feature_count, 2)
        self.assertEqual(model.dimension, 3)
        self.assertTrue(np.all(np.isfinite(model.logpdf(features, residuals))))
        self.assertTrue(
            np.all(model.squared_mahalanobis(features, residuals) >= 0.0)
        )

    def test_standardization_is_training_local_and_predictions_are_linear(self) -> None:
        features = np.asarray(
            [
                [10.0, 0.1],
                [12.0, 0.2],
                [14.0, 0.3],
                [16.0, 0.5],
                [18.0, 0.8],
                [20.0, 1.3],
            ]
        )
        residuals = np.column_stack(
            (
                0.5 + 0.02 * features[:, 0] - features[:, 1],
                -0.1 + 0.03 * features[:, 0] + 0.5 * features[:, 1],
            )
        )

        model = fit_linear_conditional_gaussian(
            features,
            residuals,
            feature_names=("a", "b"),
            covariance_regularization_m2=1e-6,
        )

        np.testing.assert_allclose(model.feature_mean, np.mean(features, axis=0))
        np.testing.assert_allclose(model.feature_scale, np.std(features, axis=0))
        np.testing.assert_allclose(model.predict_mean(features), residuals, atol=1e-12)

    def test_constant_or_rank_deficient_features_fail_closed(self) -> None:
        residuals = np.arange(24, dtype=np.float64).reshape(8, 3)
        with self.assertRaisesRegex(ValueError, "positive variation"):
            fit_linear_conditional_gaussian(
                np.ones((8, 2)),
                residuals,
                feature_names=("a", "b"),
            )
        features = np.column_stack((np.arange(8), 2.0 * np.arange(8)))
        with self.assertRaisesRegex(ValueError, "rank deficient"):
            fit_linear_conditional_gaussian(
                features,
                residuals,
                feature_names=("a", "b"),
            )

    def test_model_rejects_nonpositive_covariance(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive definite"):
            ConditionalGaussianResidualModel(
                feature_names=("a",),
                feature_mean=[0.0],
                feature_scale=[1.0],
                intercept_m=[0.0, 0.0],
                standardized_coefficients_m=[[0.0, 0.0]],
                covariance_m2=[[1.0, 1.0], [1.0, 1.0]],
                n_training_samples=10,
                covariance_regularization_m2=0.0,
            )


if __name__ == "__main__":
    unittest.main()
