"""Linear conditional multivariate Gaussian for canonical residual vectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _finite_matrix(values: ArrayLike, *, name: str) -> FloatArray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{name} must be a nonempty two-dimensional matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


@dataclass(frozen=True)
class ConditionalGaussianResidualModel:
    """Gaussian with a linear feature-conditioned mean and fixed covariance."""

    feature_names: tuple[str, ...]
    feature_mean: ArrayLike
    feature_scale: ArrayLike
    intercept_m: ArrayLike
    standardized_coefficients_m: ArrayLike
    covariance_m2: ArrayLike
    n_training_samples: int
    covariance_regularization_m2: float

    def __post_init__(self) -> None:
        names = tuple(str(name) for name in self.feature_names)
        feature_mean = np.asarray(self.feature_mean, dtype=np.float64)
        feature_scale = np.asarray(self.feature_scale, dtype=np.float64)
        intercept = np.asarray(self.intercept_m, dtype=np.float64)
        coefficients = np.asarray(
            self.standardized_coefficients_m,
            dtype=np.float64,
        )
        covariance = np.asarray(self.covariance_m2, dtype=np.float64)
        if not names or any(not name for name in names) or len(set(names)) != len(names):
            raise ValueError("feature names must be nonempty and unique")
        if feature_mean.shape != (len(names),) or feature_scale.shape != (
            len(names),
        ):
            raise ValueError("feature mean and scale must match feature names")
        if not np.all(np.isfinite(feature_mean)):
            raise ValueError("feature mean must be finite")
        if not np.all(np.isfinite(feature_scale)) or np.any(feature_scale <= 0.0):
            raise ValueError("feature scale must be finite and positive")
        if intercept.ndim != 1 or len(intercept) == 0:
            raise ValueError("intercept must be a nonempty vector")
        if coefficients.shape != (len(names), len(intercept)):
            raise ValueError("coefficient matrix must have shape (features, stations)")
        if covariance.shape != (len(intercept), len(intercept)):
            raise ValueError("covariance must have shape (stations, stations)")
        if not all(
            np.all(np.isfinite(values))
            for values in (intercept, coefficients, covariance)
        ):
            raise ValueError("conditional Gaussian parameters must be finite")
        if not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-12):
            raise ValueError("covariance must be symmetric")
        if self.n_training_samples <= len(names) + 1:
            raise ValueError("training samples must exceed linear mean parameters")
        if (
            not np.isfinite(self.covariance_regularization_m2)
            or self.covariance_regularization_m2 < 0.0
        ):
            raise ValueError("covariance regularization must be finite and nonnegative")
        covariance = 0.5 * (covariance + covariance.T)
        try:
            np.linalg.cholesky(covariance)
        except np.linalg.LinAlgError as error:
            raise ValueError("covariance must be positive definite") from error
        for array in (
            feature_mean,
            feature_scale,
            intercept,
            coefficients,
            covariance,
        ):
            array.setflags(write=False)
        object.__setattr__(self, "feature_names", names)
        object.__setattr__(self, "feature_mean", feature_mean)
        object.__setattr__(self, "feature_scale", feature_scale)
        object.__setattr__(self, "intercept_m", intercept)
        object.__setattr__(self, "standardized_coefficients_m", coefficients)
        object.__setattr__(self, "covariance_m2", covariance)

    @property
    def feature_count(self) -> int:
        return len(self.feature_names)

    @property
    def dimension(self) -> int:
        return len(self.intercept_m)

    def standardized_features(self, features: ArrayLike) -> FloatArray:
        matrix = np.asarray(features, dtype=np.float64)
        if matrix.ndim == 1:
            matrix = matrix[None, :]
        matrix = _finite_matrix(matrix, name="features")
        if matrix.shape[1] != self.feature_count:
            raise ValueError(
                f"features must have {self.feature_count} columns, "
                f"received {matrix.shape[1]}"
            )
        return (matrix - self.feature_mean) / self.feature_scale

    def predict_mean(self, features: ArrayLike) -> FloatArray:
        standardized = self.standardized_features(features)
        return self.intercept_m + standardized @ self.standardized_coefficients_m

    def errors(self, features: ArrayLike, residuals: ArrayLike) -> FloatArray:
        values = np.asarray(residuals, dtype=np.float64)
        if values.ndim == 1:
            values = values[None, :]
        values = _finite_matrix(values, name="residuals")
        prediction = self.predict_mean(features)
        if values.shape != prediction.shape:
            raise ValueError("residuals must align with conditional predictions")
        return values - prediction

    def squared_mahalanobis(
        self,
        features: ArrayLike,
        residuals: ArrayLike,
    ) -> FloatArray:
        errors = self.errors(features, residuals)
        cholesky = np.linalg.cholesky(self.covariance_m2)
        whitened = np.linalg.solve(cholesky, errors.T).T
        return np.sum(np.square(whitened), axis=1)

    def logpdf(self, features: ArrayLike, residuals: ArrayLike) -> FloatArray:
        squared = self.squared_mahalanobis(features, residuals)
        cholesky = np.linalg.cholesky(self.covariance_m2)
        log_determinant = 2.0 * np.sum(np.log(np.diag(cholesky)))
        normalizer = self.dimension * np.log(2.0 * np.pi) + log_determinant
        return -0.5 * (normalizer + squared)


def fit_linear_conditional_gaussian(
    features: ArrayLike,
    residuals: ArrayLike,
    *,
    feature_names: Sequence[str],
    covariance_regularization_m2: float = 1e-6,
) -> ConditionalGaussianResidualModel:
    """Fit an OLS conditional mean and MLE covariance of training errors."""

    feature_matrix = _finite_matrix(features, name="features")
    residual_matrix = _finite_matrix(residuals, name="residuals")
    names = tuple(str(name) for name in feature_names)
    if feature_matrix.shape[0] != residual_matrix.shape[0]:
        raise ValueError("features and residuals must have the same row count")
    if feature_matrix.shape[1] != len(names):
        raise ValueError("feature names must match feature columns")
    if feature_matrix.shape[0] <= feature_matrix.shape[1] + 1:
        raise ValueError("training rows must exceed linear mean parameters")
    if (
        not np.isfinite(covariance_regularization_m2)
        or covariance_regularization_m2 < 0.0
    ):
        raise ValueError("covariance regularization must be finite and nonnegative")

    feature_mean = np.mean(feature_matrix, axis=0)
    feature_scale = np.std(feature_matrix, axis=0, ddof=0)
    if np.any(feature_scale <= 0.0):
        raise ValueError("every training feature must have positive variation")
    standardized = (feature_matrix - feature_mean) / feature_scale
    design = np.column_stack((np.ones(len(standardized)), standardized))
    parameters, _residuals, rank, _singular_values = np.linalg.lstsq(
        design,
        residual_matrix,
        rcond=None,
    )
    if rank != design.shape[1]:
        raise ValueError("conditional mean design matrix is rank deficient")
    fitted_mean = design @ parameters
    errors = residual_matrix - fitted_mean
    covariance = errors.T @ errors / len(errors)
    covariance += covariance_regularization_m2 * np.eye(residual_matrix.shape[1])
    return ConditionalGaussianResidualModel(
        feature_names=names,
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        intercept_m=parameters[0],
        standardized_coefficients_m=parameters[1:],
        covariance_m2=covariance,
        n_training_samples=len(feature_matrix),
        covariance_regularization_m2=float(covariance_regularization_m2),
    )


__all__ = [
    "ConditionalGaussianResidualModel",
    "fit_linear_conditional_gaussian",
]
