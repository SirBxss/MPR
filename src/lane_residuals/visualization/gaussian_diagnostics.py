"""Plots for held-out Gaussian marginal and multivariate adequacy."""

from __future__ import annotations

from pathlib import Path
from statistics import NormalDist
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike

from ..modeling.gaussian_diagnostics import (
    chi_square_cdf,
    chi_square_quantile,
    marginal_calibration_statistics,
    standard_normal_two_sided_quantile,
)

_NORMAL = NormalDist()


def _validated_inputs(
    *,
    values: ArrayLike,
    drive_ids: Sequence[str],
    expected_columns: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    array = np.asarray(values, dtype=np.float64)
    drives = np.asarray([str(value) for value in drive_ids])
    if array.ndim not in (1, 2) or array.shape[0] == 0:
        raise ValueError("diagnostic values must be a nonempty vector or matrix")
    if expected_columns is not None and (
        array.ndim != 2 or array.shape[1] != expected_columns
    ):
        raise ValueError("diagnostic matrix has the wrong station dimension")
    if len(drives) != array.shape[0] or np.any(drives == ""):
        raise ValueError("drive_ids must align with diagnostic values")
    if not np.all(np.isfinite(array)):
        raise ValueError("diagnostic values must be finite")
    return array, drives


def _scope_masks(drives: np.ndarray) -> list[tuple[str, np.ndarray]]:
    scopes = [
        (drive_id, drives == drive_id) for drive_id in sorted(set(drives.tolist()))
    ]
    return scopes + [("all drives", np.ones(len(drives), dtype=bool))]


def plot_gaussian_marginal_adequacy(
    path: Path,
    *,
    stations_m: ArrayLike,
    standardized_errors: ArrayLike,
    drive_ids: Sequence[str],
) -> None:
    """Plot held-out coverage, moments, scale, and selected marginal Q–Q views."""

    stations = np.asarray(stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or len(stations) == 0
        or not np.all(np.isfinite(stations))
    ):
        raise ValueError("stations must be a nonempty finite vector")
    standardized, drives = _validated_inputs(
        values=standardized_errors,
        drive_ids=drive_ids,
        expected_columns=len(stations),
    )
    scopes = _scope_masks(drives)
    marginal_95 = standard_normal_two_sided_quantile(0.95)

    figure, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    coverage_axis, shape_axis, scale_axis = axes[0]
    for scope_id, mask in scopes:
        coverage = np.mean(np.abs(standardized[mask]) <= marginal_95, axis=0)
        coverage_axis.plot(
            stations,
            coverage,
            marker="o",
            markersize=3,
            label=scope_id,
        )
    coverage_axis.axhline(0.95, color="black", linestyle="--", label="nominal 95%")
    coverage_axis.set_ylim(0.0, 1.02)
    coverage_axis.set_title("Out-of-drive marginal coverage")
    coverage_axis.set_xlabel("Station (m)")
    coverage_axis.set_ylabel("Coverage")
    coverage_axis.grid(alpha=0.25)
    coverage_axis.legend(fontsize=8)

    overall_statistics = [
        marginal_calibration_statistics(standardized[:, index])
        for index in range(len(stations))
    ]
    shape_axis.plot(
        stations,
        [row["skewness"] for row in overall_statistics],
        marker="o",
        markersize=3,
        label="skewness",
    )
    shape_axis.plot(
        stations,
        [row["excess_kurtosis"] for row in overall_statistics],
        marker="o",
        markersize=3,
        label="excess kurtosis",
    )
    shape_axis.axhline(0.0, color="black", linewidth=0.8)
    shape_axis.set_title("Held-out marginal shape")
    shape_axis.set_xlabel("Station (m)")
    shape_axis.set_ylabel("Standardized moment")
    shape_axis.grid(alpha=0.25)
    shape_axis.legend(fontsize=8)

    for scope_id, mask in scopes:
        scale_axis.plot(
            stations,
            np.std(standardized[mask], axis=0),
            marker="o",
            markersize=3,
            label=scope_id,
        )
    scale_axis.axhline(1.0, color="black", linestyle="--", label="ideal")
    scale_axis.set_title("Out-of-drive standardized scale")
    scale_axis.set_xlabel("Station (m)")
    scale_axis.set_ylabel("Standard deviation of z")
    scale_axis.grid(alpha=0.25)
    scale_axis.legend(fontsize=8)

    selected_stations = (0.0, 50.0, 100.0)
    for axis, selected_station in zip(axes[1], selected_stations):
        station_index = int(np.argmin(np.abs(stations - selected_station)))
        ordered = np.sort(standardized[:, station_index])
        probabilities = (np.arange(len(ordered), dtype=np.float64) + 0.5) / len(
            ordered
        )
        theoretical = np.asarray(
            [_NORMAL.inv_cdf(float(probability)) for probability in probabilities]
        )
        limit = max(float(np.max(np.abs(theoretical))), float(np.max(np.abs(ordered))))
        axis.plot(theoretical, ordered, color="tab:blue", linewidth=1.2)
        axis.plot((-limit, limit), (-limit, limit), "k--", linewidth=0.9)
        axis.set_title(f"Normal Q–Q at {stations[station_index]:.0f} m")
        axis.set_xlabel("Theoretical normal quantile")
        axis.set_ylabel("Held-out standardized residual")
        axis.grid(alpha=0.25)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def plot_gaussian_multivariate_adequacy(
    path: Path,
    *,
    squared_mahalanobis: ArrayLike,
    drive_ids: Sequence[str],
    dimension: int,
) -> None:
    """Plot chi-square Q–Q, tail exceedance, and PIT calibration by drive."""

    squared, drives = _validated_inputs(
        values=squared_mahalanobis,
        drive_ids=drive_ids,
    )
    if squared.ndim != 1 or np.any(squared < 0.0):
        raise ValueError("squared Mahalanobis values must be a nonnegative vector")
    if isinstance(dimension, bool) or not isinstance(dimension, (int, np.integer)):
        raise TypeError("dimension must be an integer")
    if dimension < 1:
        raise ValueError("dimension must be positive")
    scopes = _scope_masks(drives)

    figure, axes = plt.subplots(1, 3, figsize=(16, 4.9), constrained_layout=True)
    qq_axis, exceedance_axis, pit_axis = axes
    maximum_quantile = 0.0
    for scope_id, mask in scopes:
        observed = np.sort(squared[mask])
        probabilities = (np.arange(len(observed), dtype=np.float64) + 0.5) / len(
            observed
        )
        theoretical = np.asarray(
            [
                chi_square_quantile(
                    float(probability),
                    degrees_of_freedom=dimension,
                )
                for probability in probabilities
            ]
        )
        qq_axis.plot(theoretical, observed, linewidth=1.2, label=scope_id)
        maximum_quantile = max(
            maximum_quantile,
            float(np.max(theoretical)),
            float(np.max(observed)),
        )
    qq_axis.plot(
        (0.0, maximum_quantile),
        (0.0, maximum_quantile),
        "k--",
        linewidth=0.9,
        label="chi-square reference",
    )
    qq_axis.set_title(f"Mahalanobis Q–Q (df={dimension})")
    qq_axis.set_xlabel("Theoretical chi-square quantile")
    qq_axis.set_ylabel("Observed squared Mahalanobis")
    qq_axis.grid(alpha=0.25)
    qq_axis.legend(fontsize=8)

    probability_levels = (0.90, 0.95, 0.99)
    x_positions = np.arange(len(probability_levels), dtype=np.float64)
    width = 0.8 / len(scopes)
    for scope_index, (scope_id, mask) in enumerate(scopes):
        rates = []
        for probability in probability_levels:
            threshold = chi_square_quantile(
                probability,
                degrees_of_freedom=dimension,
            )
            rates.append(float(np.mean(squared[mask] > threshold)))
        positions = x_positions - 0.4 + width / 2.0 + scope_index * width
        exceedance_axis.bar(positions, rates, width=width, label=scope_id)
    exceedance_axis.plot(
        x_positions,
        [1.0 - probability for probability in probability_levels],
        "ko--",
        linewidth=1.0,
        label="expected",
    )
    exceedance_axis.set_xticks(
        x_positions,
        [f"> p{int(probability * 100)}" for probability in probability_levels],
    )
    exceedance_axis.set_title("Upper-tail exceedance")
    exceedance_axis.set_ylabel("Observed rate")
    exceedance_axis.grid(axis="y", alpha=0.25)
    exceedance_axis.legend(fontsize=8)

    for scope_id, mask in scopes:
        pit = np.sort(
            np.asarray(
                [
                    chi_square_cdf(float(value), degrees_of_freedom=dimension)
                    for value in squared[mask]
                ]
            )
        )
        empirical = np.arange(1, len(pit) + 1, dtype=np.float64) / len(pit)
        pit_axis.plot(pit, empirical, linewidth=1.2, label=scope_id)
    pit_axis.plot((0.0, 1.0), (0.0, 1.0), "k--", linewidth=0.9, label="uniform")
    pit_axis.set_title("Chi-square probability calibration")
    pit_axis.set_xlabel("Reference CDF at observed distance")
    pit_axis.set_ylabel("Empirical CDF")
    pit_axis.grid(alpha=0.25)
    pit_axis.legend(fontsize=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


__all__ = [
    "plot_gaussian_marginal_adequacy",
    "plot_gaussian_multivariate_adequacy",
]
