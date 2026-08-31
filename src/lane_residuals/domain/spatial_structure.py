"""Population cross-station moments for fixed generated residual ensembles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class SpatialMoments:
    """Float64 population moments across station profiles."""

    mean: FloatArray
    covariance: FloatArray
    correlation: FloatArray


def population_spatial_moments(
    profiles: FloatArray,
    *,
    correlation_tolerance: float = 1e-12,
) -> SpatialMoments:
    """Calculate population moments for rows of contemporaneous station values."""

    values = np.asarray(profiles)
    if values.dtype != np.dtype(np.float64):
        raise TypeError("spatial profiles must use float64")
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
        raise ValueError("spatial profiles must have shape [profiles>=2, stations>=2]")
    if (
        not np.isfinite(correlation_tolerance)
        or correlation_tolerance < 0.0
    ):
        raise ValueError("correlation tolerance must be finite and nonnegative")
    if not np.all(np.isfinite(values)):
        raise ValueError("spatial profiles must be finite")

    mean = np.mean(values, axis=0, dtype=np.float64)
    centered = values - mean
    covariance = (centered.T @ centered) / np.float64(values.shape[0])
    variances = np.diag(covariance)
    if not np.all(np.isfinite(variances)) or np.any(variances <= 0.0):
        raise ValueError("every station must have finite positive population variance")

    scales = np.sqrt(variances)
    correlation = covariance / np.multiply.outer(scales, scales)
    if not np.all(np.isfinite(correlation)):
        raise ValueError("spatial correlations must be finite")
    diagonal = np.diag(correlation)
    if not np.allclose(
        diagonal,
        np.ones_like(diagonal),
        rtol=0.0,
        atol=correlation_tolerance,
    ):
        raise ValueError("spatial correlation diagonal differs from one")
    if (
        np.min(correlation) < -1.0 - correlation_tolerance
        or np.max(correlation) > 1.0 + correlation_tolerance
    ):
        raise ValueError("spatial correlation lies outside the round-off tolerance")

    return SpatialMoments(
        mean=np.asarray(mean, dtype=np.float64),
        covariance=np.asarray(covariance, dtype=np.float64),
        correlation=np.asarray(np.clip(correlation, -1.0, 1.0), dtype=np.float64),
    )


def mean_off_diagonal_correlation(correlation: FloatArray) -> float:
    """Return the unweighted mean over unordered off-diagonal station pairs."""

    values = _validated_correlation_matrix(correlation)
    indices = np.triu_indices(values.shape[0], k=1)
    return float(np.mean(values[indices], dtype=np.float64))


def mean_adjacent_correlation(correlation: FloatArray) -> float:
    """Return the unweighted mean over adjacent-station correlations."""

    values = _validated_correlation_matrix(correlation)
    return float(np.mean(np.diag(values, k=1), dtype=np.float64))


def _validated_correlation_matrix(correlation: FloatArray) -> FloatArray:
    values = np.asarray(correlation)
    if values.dtype != np.dtype(np.float64):
        raise TypeError("correlation matrix must use float64")
    if values.ndim != 2 or values.shape[0] != values.shape[1] or values.shape[0] < 2:
        raise ValueError("correlation matrix must be square with at least two stations")
    if not np.all(np.isfinite(values)):
        raise ValueError("correlation matrix must be finite")
    return values


__all__ = [
    "SpatialMoments",
    "mean_adjacent_correlation",
    "mean_off_diagonal_correlation",
    "population_spatial_moments",
]
