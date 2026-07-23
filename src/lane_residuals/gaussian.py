"""Unconditional multivariate-Gaussian model for residual vectors.

Each observation is one complete residual vector over the selected reference
stations.  The model intentionally has no condition variables and no temporal
state; it estimates only one global mean vector and one global covariance
matrix from an ``N x H`` residual matrix.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .residuals import FloatArray


def _finite_residual_matrix(values: ArrayLike, *, name: str) -> FloatArray:
    """Return a finite two-dimensional residual matrix."""

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError(f"{name} must be two-dimensional")
    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


@dataclass(frozen=True)
class GaussianResidualModel:
    """One unconditional Gaussian distribution over residual vectors.

    ``mean`` has shape ``(H,)`` and ``covariance`` has shape ``(H, H)``.
    ``n_training_samples`` records how many independent residual vectors were
    used for fitting. ``regularization`` is the diagonal variance added during
    fitting, expressed in squared residual units (normally square metres).
    """

    mean: ArrayLike
    covariance: ArrayLike
    n_training_samples: int
    regularization: float

    def __post_init__(self) -> None:
        mean = np.asarray(self.mean, dtype=np.float64)
        covariance = np.asarray(self.covariance, dtype=np.float64)

        if mean.ndim != 1 or len(mean) == 0:
            raise ValueError("mean must be a nonempty one-dimensional array")
        if not np.all(np.isfinite(mean)):
            raise ValueError("mean must contain only finite values")
        if covariance.shape != (len(mean), len(mean)):
            raise ValueError("covariance must have shape (H, H)")
        if not np.all(np.isfinite(covariance)):
            raise ValueError("covariance must contain only finite values")
        if not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-12):
            raise ValueError("covariance must be symmetric")
        if self.n_training_samples < 2:
            raise ValueError("n_training_samples must be at least two")
        if not np.isfinite(self.regularization) or self.regularization < 0.0:
            raise ValueError("regularization must be finite and nonnegative")

        covariance = 0.5 * (covariance + covariance.T)
        try:
            np.linalg.cholesky(covariance)
        except np.linalg.LinAlgError as error:
            raise ValueError(
                "covariance must be positive definite; increase regularization"
            ) from error

        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "covariance", covariance)

    @property
    def dimension(self) -> int:
        """Number of reference stations represented by one residual vector."""

        return len(self.mean)

    def logpdf(self, residuals: ArrayLike) -> FloatArray:
        """Return the joint log-density of each supplied residual vector."""

        values = np.asarray(residuals, dtype=np.float64)
        if values.ndim == 1:
            values = values[None, :]
        values = _finite_residual_matrix(values, name="residuals")
        if values.shape[1] != self.dimension:
            raise ValueError(
                f"residuals must have {self.dimension} columns, "
                f"received {values.shape[1]}"
            )

        """log p(e) =-1/2*[Hlog(2π)+log∣Σ∣+(e−μ)⊤Σ−1(e−μ)]"""

        cholesky = np.linalg.cholesky(self.covariance)
        centered = values - self.mean
        whitened = np.linalg.solve(cholesky, centered.T).T
        squared_mahalanobis = np.sum(whitened**2, axis=1)
        log_determinant = 2.0 * np.sum(np.log(np.diag(cholesky)))
        normalizer = self.dimension * np.log(2.0 * np.pi) + log_determinant
        return -0.5 * (normalizer + squared_mahalanobis)

    def negative_log_likelihood(self, residuals: ArrayLike) -> float:
        """Return mean negative joint log-likelihood for a residual dataset."""

        return float(-np.mean(self.logpdf(residuals)))

    def sample(
        self,
        n_samples: int,
        *,
        rng: np.random.Generator | None = None,
    ) -> FloatArray:
        """Draw complete, spatially correlated residual vectors."""

        if isinstance(n_samples, bool) or not isinstance(n_samples, (int, np.integer)):
            raise TypeError("n_samples must be an integer")
        if n_samples < 1:
            raise ValueError("n_samples must be at least one")

        generator = np.random.default_rng() if rng is None else rng
        cholesky = np.linalg.cholesky(self.covariance)
        standard_normal = generator.standard_normal((n_samples, self.dimension))
        return self.mean + standard_normal @ cholesky.T


def fit_gaussian_residual_model(
    residuals: ArrayLike,
    *,
    regularization: float = 1e-8,
) -> GaussianResidualModel:
    """Fit an unconditional Gaussian by maximum likelihood.

    The empirical covariance uses the maximum-likelihood divisor ``N`` rather
    than the unbiased-estimation divisor ``N - 1``. A fixed diagonal
    ``regularization`` is then added to make likelihood evaluation and sampling
    numerically stable. The value must be reported with experimental results.
    """

    matrix = _finite_residual_matrix(residuals, name="residuals")
    n_samples, dimension = matrix.shape
    if n_samples < 2:
        raise ValueError("at least two residual vectors are required")
    if not np.isfinite(regularization) or regularization < 0.0:
        raise ValueError("regularization must be finite and nonnegative")

    mean = np.mean(matrix, axis=0)
    centered = matrix - mean
    covariance = centered.T @ centered / n_samples
    covariance += regularization * np.eye(dimension)

    return GaussianResidualModel(
        mean=mean,
        covariance=covariance,
        n_training_samples=n_samples,
        regularization=float(regularization),
    )
