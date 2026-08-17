"""Out-of-group calibration diagnostics for multivariate Gaussian residuals.

The diagnostics operate on predictions made for a group that was not used to
fit the corresponding Gaussian.  For MPR the groups are physical drives.  The
module has no file or plotting dependencies and keeps every numerical rule
independently testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .gaussian import fit_gaussian_residual_model

FloatArray = NDArray[np.float64]

_GAMMA_EPSILON = 1e-14
_GAMMA_MAX_ITERATIONS = 10_000
_GAMMA_FLOOR = 1e-300
_NORMAL = NormalDist()

MARGINAL_COVERAGE_LEVELS = (0.50, 0.80, 0.90, 0.95, 0.99)
MULTIVARIATE_QUANTILE_LEVELS = (0.50, 0.90, 0.95, 0.99)


def _finite_matrix(values: ArrayLike, *, name: str) -> FloatArray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{name} must be a nonempty two-dimensional matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix


def regularized_gamma_p(shape: float, value: float) -> float:
    """Return the regularized lower incomplete gamma ``P(shape, value)``.

    A convergent series is used below ``shape + 1`` and a continued fraction
    for the complementary function otherwise.  This avoids adding SciPy only
    for chi-square calibration references.
    """

    if not math.isfinite(shape) or shape <= 0.0:
        raise ValueError("gamma shape must be finite and positive")
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("gamma value must be finite and nonnegative")
    if value == 0.0:
        return 0.0

    log_scale = -value + shape * math.log(value) - math.lgamma(shape)
    if value < shape + 1.0:
        term = 1.0 / shape
        total = term
        denominator = shape
        for _ in range(_GAMMA_MAX_ITERATIONS):
            denominator += 1.0
            term *= value / denominator
            total += term
            if abs(term) <= abs(total) * _GAMMA_EPSILON:
                return float(min(1.0, max(0.0, total * math.exp(log_scale))))
        raise RuntimeError("regularized gamma series did not converge")

    denominator = value + 1.0 - shape
    if abs(denominator) < _GAMMA_FLOOR:
        denominator = _GAMMA_FLOOR
    reciprocal = 1.0 / denominator
    fraction = reciprocal
    numerator_guard = 1.0 / _GAMMA_FLOOR
    for iteration in range(1, _GAMMA_MAX_ITERATIONS + 1):
        coefficient = -iteration * (iteration - shape)
        denominator += 2.0
        reciprocal = coefficient * reciprocal + denominator
        if abs(reciprocal) < _GAMMA_FLOOR:
            reciprocal = _GAMMA_FLOOR
        numerator_guard = denominator + coefficient / numerator_guard
        if abs(numerator_guard) < _GAMMA_FLOOR:
            numerator_guard = _GAMMA_FLOOR
        reciprocal = 1.0 / reciprocal
        update = reciprocal * numerator_guard
        fraction *= update
        if abs(update - 1.0) <= _GAMMA_EPSILON:
            complement = math.exp(log_scale) * fraction
            return float(min(1.0, max(0.0, 1.0 - complement)))
    raise RuntimeError("regularized gamma continued fraction did not converge")


def chi_square_cdf(value: float, *, degrees_of_freedom: int) -> float:
    """Return the chi-square cumulative probability without SciPy."""

    if isinstance(degrees_of_freedom, bool) or not isinstance(
        degrees_of_freedom, (int, np.integer)
    ):
        raise TypeError("degrees_of_freedom must be an integer")
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("chi-square value must be finite and nonnegative")
    return regularized_gamma_p(degrees_of_freedom / 2.0, value / 2.0)


def chi_square_quantile(
    probability: float,
    *,
    degrees_of_freedom: int,
) -> float:
    """Invert the chi-square CDF by deterministic bracketing and bisection."""

    if not math.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError("probability must be finite and strictly within (0, 1)")
    if isinstance(degrees_of_freedom, bool) or not isinstance(
        degrees_of_freedom, (int, np.integer)
    ):
        raise TypeError("degrees_of_freedom must be an integer")
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")

    lower = 0.0
    upper = float(max(1, degrees_of_freedom))
    while chi_square_cdf(upper, degrees_of_freedom=degrees_of_freedom) < probability:
        upper *= 2.0
    for _ in range(200):
        midpoint = 0.5 * (lower + upper)
        if chi_square_cdf(
            midpoint,
            degrees_of_freedom=degrees_of_freedom,
        ) < probability:
            lower = midpoint
        else:
            upper = midpoint
        if upper - lower <= 1e-12 * max(1.0, upper):
            break
    return 0.5 * (lower + upper)


def standard_normal_two_sided_quantile(coverage: float) -> float:
    """Return ``z`` such that ``P(-z <= Z <= z) == coverage``."""

    if not math.isfinite(coverage) or not 0.0 < coverage < 1.0:
        raise ValueError("coverage must be finite and strictly within (0, 1)")
    return float(_NORMAL.inv_cdf(0.5 + 0.5 * coverage))


@dataclass(frozen=True)
class OutOfGroupGaussianPredictions:
    """Prediction diagnostics aligned one-to-one with the source observations."""

    standardized_marginal_errors: FloatArray = field(repr=False)
    squared_mahalanobis: FloatArray = field(repr=False)
    joint_negative_log_likelihood: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        standardized = np.asarray(
            self.standardized_marginal_errors,
            dtype=np.float64,
        )
        squared = np.asarray(self.squared_mahalanobis, dtype=np.float64)
        nll = np.asarray(self.joint_negative_log_likelihood, dtype=np.float64)
        if standardized.ndim != 2 or standardized.shape[0] == 0:
            raise ValueError("standardized errors must be a nonempty matrix")
        if squared.shape != (standardized.shape[0],) or nll.shape != squared.shape:
            raise ValueError("vector diagnostics must align with standardized errors")
        if not all(np.all(np.isfinite(array)) for array in (standardized, squared, nll)):
            raise ValueError("out-of-group diagnostics must be finite")
        if np.any(squared < 0.0):
            raise ValueError("squared Mahalanobis values must be nonnegative")
        for name, array in (
            ("standardized_marginal_errors", standardized),
            ("squared_mahalanobis", squared),
            ("joint_negative_log_likelihood", nll),
        ):
            array.setflags(write=False)
            object.__setattr__(self, name, array)


def leave_one_group_out_gaussian_predictions(
    residuals: ArrayLike,
    groups: Sequence[str],
    *,
    regularization: float,
) -> OutOfGroupGaussianPredictions:
    """Fit on all other groups and predict every observation exactly once."""

    matrix = _finite_matrix(residuals, name="residuals")
    if len(groups) != len(matrix):
        raise ValueError("groups must have one label per residual vector")
    normalized_groups = np.asarray([str(group).strip() for group in groups])
    if np.any(normalized_groups == ""):
        raise ValueError("group labels must be nonempty")
    unique_groups = sorted(set(normalized_groups.tolist()))
    if len(unique_groups) < 2:
        raise ValueError("out-of-group prediction requires at least two groups")
    if not math.isfinite(regularization) or regularization <= 0.0:
        raise ValueError("regularization must be finite and positive")

    standardized = np.empty_like(matrix)
    squared_mahalanobis = np.empty(len(matrix), dtype=np.float64)
    negative_log_likelihood = np.empty(len(matrix), dtype=np.float64)
    assigned = np.zeros(len(matrix), dtype=bool)
    for held_out_group in unique_groups:
        test_mask = normalized_groups == held_out_group
        training = matrix[~test_mask]
        test = matrix[test_mask]
        if len(training) < 2 or len(test) == 0:
            raise ValueError(f"group fold {held_out_group} lacks train or test vectors")
        model = fit_gaussian_residual_model(
            training,
            regularization=regularization,
        )
        differences = test - model.mean
        standard_deviation = np.sqrt(np.diag(model.covariance))
        standardized[test_mask] = differences / standard_deviation[None, :]
        squared_mahalanobis[test_mask] = model.squared_mahalanobis(test)
        negative_log_likelihood[test_mask] = -model.logpdf(test)
        assigned[test_mask] = True
    if not np.all(assigned):
        raise RuntimeError("not every residual vector received an out-of-group prediction")
    return OutOfGroupGaussianPredictions(
        standardized_marginal_errors=standardized,
        squared_mahalanobis=squared_mahalanobis,
        joint_negative_log_likelihood=negative_log_likelihood,
    )


def normal_qq_correlation(values: ArrayLike) -> float:
    """Correlation of ordered values with standard-normal plotting quantiles."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) < 3 or not np.all(np.isfinite(array)):
        raise ValueError("QQ values must be a finite vector with at least three items")
    probabilities = (np.arange(len(array), dtype=np.float64) + 0.5) / len(array)
    theoretical = np.asarray([_NORMAL.inv_cdf(float(p)) for p in probabilities])
    correlation = np.corrcoef(theoretical, np.sort(array))[0, 1]
    return float(correlation)


def marginal_calibration_statistics(values: ArrayLike) -> dict[str, float | int]:
    """Return shape, quantile, and symmetric-coverage metrics for z-scores."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) < 3 or not np.all(np.isfinite(array)):
        raise ValueError(
            "standardized marginal values must be finite with at least three items"
        )
    mean = float(np.mean(array))
    centered = array - mean
    standard_deviation = float(np.sqrt(np.mean(np.square(centered))))
    if standard_deviation <= np.finfo(np.float64).eps:
        raise ValueError("standardized marginal values must have nonzero variance")
    scaled = centered / standard_deviation
    statistics: dict[str, float | int] = {
        "vector_count": len(array),
        "standardized_mean": mean,
        "standardized_std": standard_deviation,
        "skewness": float(np.mean(scaled**3)),
        "excess_kurtosis": float(np.mean(scaled**4) - 3.0),
        "normal_qq_correlation": normal_qq_correlation(array),
    }
    for percentile in (0.01, 0.05, 0.50, 0.95, 0.99):
        statistics[f"empirical_p{int(percentile * 100):02d}"] = float(
            np.quantile(array, percentile)
        )
    for coverage in MARGINAL_COVERAGE_LEVELS:
        quantile = standard_normal_two_sided_quantile(coverage)
        statistics[f"coverage_{int(coverage * 100):02d}"] = float(
            np.mean(np.abs(array) <= quantile)
        )
    marginal_95 = standard_normal_two_sided_quantile(0.95)
    statistics["lower_tail_exceedance_95"] = float(np.mean(array < -marginal_95))
    statistics["upper_tail_exceedance_95"] = float(np.mean(array > marginal_95))
    return statistics


def probability_integral_transform_ks(values: ArrayLike) -> float:
    """One-sample Kolmogorov-Smirnov distance from Uniform(0, 1)."""

    array = np.asarray(values, dtype=np.float64)
    if (
        array.ndim != 1
        or len(array) == 0
        or not np.all(np.isfinite(array))
        or np.any(array < 0.0)
        or np.any(array > 1.0)
    ):
        raise ValueError("PIT values must be a finite vector within [0, 1]")
    ordered = np.sort(array)
    n_values = len(ordered)
    upper = np.arange(1, n_values + 1, dtype=np.float64) / n_values
    lower = np.arange(0, n_values, dtype=np.float64) / n_values
    return float(max(np.max(upper - ordered), np.max(ordered - lower)))


def multivariate_calibration_statistics(
    squared_mahalanobis: ArrayLike,
    joint_negative_log_likelihood: ArrayLike,
    *,
    dimension: int,
) -> dict[str, float | int]:
    """Compare held-out Mahalanobis distances with their chi-square reference."""

    squared = np.asarray(squared_mahalanobis, dtype=np.float64)
    nll = np.asarray(joint_negative_log_likelihood, dtype=np.float64)
    if (
        squared.ndim != 1
        or len(squared) < 3
        or nll.shape != squared.shape
        or not np.all(np.isfinite(squared))
        or not np.all(np.isfinite(nll))
        or np.any(squared < 0.0)
    ):
        raise ValueError("multivariate diagnostics require aligned finite vectors")
    if isinstance(dimension, bool) or not isinstance(dimension, (int, np.integer)):
        raise TypeError("dimension must be an integer")
    if dimension < 1:
        raise ValueError("dimension must be positive")

    pit = np.asarray(
        [chi_square_cdf(float(value), degrees_of_freedom=dimension) for value in squared]
    )
    probabilities = (np.arange(len(squared), dtype=np.float64) + 0.5) / len(squared)
    theoretical_ordered = np.asarray(
        [
            chi_square_quantile(float(probability), degrees_of_freedom=dimension)
            for probability in probabilities
        ]
    )
    result: dict[str, float | int] = {
        "vector_count": len(squared),
        "dimension": dimension,
        "mean_joint_negative_log_likelihood": float(np.mean(nll)),
        "mean_squared_mahalanobis": float(np.mean(squared)),
        "mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared) / dimension
        ),
        "chi_square_pit_mean": float(np.mean(pit)),
        "chi_square_pit_ks_distance": probability_integral_transform_ks(pit),
        "chi_square_qq_correlation": float(
            np.corrcoef(theoretical_ordered, np.sort(squared))[0, 1]
        ),
    }
    for probability in MULTIVARIATE_QUANTILE_LEVELS:
        suffix = int(probability * 100)
        threshold = chi_square_quantile(
            probability,
            degrees_of_freedom=dimension,
        )
        result[f"chi_square_expected_p{suffix:02d}"] = threshold
        result[f"empirical_mahalanobis_p{suffix:02d}"] = float(
            np.quantile(squared, probability)
        )
        if probability >= 0.90:
            result[f"above_chi_square_p{suffix:02d}_rate"] = float(
                np.mean(squared > threshold)
            )
    return result


__all__ = [
    "MARGINAL_COVERAGE_LEVELS",
    "MULTIVARIATE_QUANTILE_LEVELS",
    "OutOfGroupGaussianPredictions",
    "chi_square_cdf",
    "chi_square_quantile",
    "leave_one_group_out_gaussian_predictions",
    "marginal_calibration_statistics",
    "multivariate_calibration_statistics",
    "normal_qq_correlation",
    "probability_integral_transform_ks",
    "regularized_gamma_p",
    "standard_normal_two_sided_quantile",
]
