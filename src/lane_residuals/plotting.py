"""Visual checks for the minimal residual-extraction pipeline."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from numpy.typing import ArrayLike
from typing import TYPE_CHECKING

from .gaussian import GaussianResidualModel
from .residuals import Path2D, residual_vector

if TYPE_CHECKING:
    from .preprocessing import ResidualDataset


def plot_path_pair_and_residual(
    ground_truth: Path2D,
    estimate: Path2D,
    stations: ArrayLike,
    *,
    reference_label: str = "Ground truth",
    estimate_label: str = "Estimate",
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot path geometry and its signed residual vector side by side."""

    stations_array = np.asarray(stations, dtype=np.float64)
    residual = residual_vector(ground_truth, estimate, stations_array)
    ground_truth_points = ground_truth.sample(stations_array)
    estimate_points = estimate.sample(stations_array)

    figure, (path_axis, residual_axis) = plt.subplots(1, 2, figsize=(11, 4.5))

    path_axis.plot(
        ground_truth.x,
        ground_truth.y,
        label=reference_label,
        linewidth=2,
    )
    path_axis.plot(
        estimate.x,
        estimate.y,
        label=estimate_label,
        linewidth=2,
    )
    for gt_point, estimate_point in zip(ground_truth_points, estimate_points):
        path_axis.plot(
            [gt_point[0], estimate_point[0]],
            [gt_point[1], estimate_point[1]],
            color="0.65",
            linewidth=0.8,
        )
    path_axis.set_title("Aligned path pair")
    path_axis.set_xlabel("x [m]")
    path_axis.set_ylabel("y [m]")
    path_axis.axis("equal")
    path_axis.grid(alpha=0.25)
    path_axis.legend()

    residual_axis.axhline(0.0, color="black", linewidth=0.8)
    residual_axis.plot(stations_array, residual, marker="o")
    residual_axis.set_title("Signed lateral residual")
    residual_axis.set_xlabel("Reference station s [m]")
    residual_axis.set_ylabel("Residual e(s) [m]")
    residual_axis.grid(alpha=0.25)

    figure.tight_layout()
    return figure, (path_axis, residual_axis)


def plot_gaussian_residual_model(
    model: GaussianResidualModel,
    stations: ArrayLike,
    *,
    observed_residuals: ArrayLike | None = None,
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot the Gaussian marginal band and its spatial correlation matrix."""

    stations_array = np.asarray(stations, dtype=np.float64)
    if stations_array.ndim != 1 or len(stations_array) != model.dimension:
        raise ValueError("stations must be one-dimensional with length H")
    if not np.all(np.isfinite(stations_array)):
        raise ValueError("stations must contain only finite values")

    figure, (mean_axis, correlation_axis) = plt.subplots(
        1,
        2,
        figsize=(11, 4.5),
    )

    if observed_residuals is not None:
        observations = np.asarray(observed_residuals, dtype=np.float64)
        if observations.ndim != 2 or observations.shape[1] != model.dimension:
            raise ValueError("observed_residuals must have shape (N, H)")
        if not np.all(np.isfinite(observations)):
            raise ValueError("observed_residuals must contain only finite values")
        mean_axis.plot(
            stations_array,
            observations[:20].T,
            color="0.65",
            alpha=0.25,
            linewidth=0.8,
        )

    marginal_standard_deviation = np.sqrt(np.diag(model.covariance))
    lower = model.mean - 1.96 * marginal_standard_deviation
    upper = model.mean + 1.96 * marginal_standard_deviation
    mean_axis.fill_between(
        stations_array,
        lower,
        upper,
        color="tab:blue",
        alpha=0.2,
        label="Marginal 95% Gaussian interval",
    )
    mean_axis.plot(
        stations_array,
        model.mean,
        color="tab:blue",
        linewidth=2,
        label="Learned mean",
    )
    mean_axis.axhline(0.0, color="black", linewidth=0.8)
    mean_axis.set_title("Unconditional residual distribution")
    mean_axis.set_xlabel("Reference station s [m]")
    mean_axis.set_ylabel("Residual e(s) [m]")
    mean_axis.grid(alpha=0.25)
    mean_axis.legend()

    correlation = model.covariance / np.outer(
        marginal_standard_deviation,
        marginal_standard_deviation,
    )
    correlation = np.clip(correlation, -1.0, 1.0)
    image = correlation_axis.imshow(
        correlation,
        vmin=-1.0,
        vmax=1.0,
        cmap="coolwarm",
        origin="lower",
        extent=(
            stations_array[0],
            stations_array[-1],
            stations_array[0],
            stations_array[-1],
        ),
        aspect="auto",
    )
    correlation_axis.set_title("Learned spatial correlation")
    correlation_axis.set_xlabel("Station s [m]")
    correlation_axis.set_ylabel("Station s [m]")
    figure.colorbar(image, ax=correlation_axis, label="Correlation")

    figure.tight_layout()
    return figure, (mean_axis, correlation_axis)


def plot_mcap_dataset_diagnostics(
    dataset: "ResidualDataset",
) -> tuple[Figure, np.ndarray]:
    """Plot geometry, residuals, synchronization, and rejection diagnostics."""

    if not dataset.examples:
        raise ValueError("dataset must retain at least one path-pair example")

    figure, axes = plt.subplots(2, 2, figsize=(12, 9))
    path_axis, residual_axis, synchronization_axis, rejection_axis = axes.ravel()

    example = dataset.examples[0]
    path_axis.plot(
        example.reference.x,
        example.reference.y,
        linewidth=2,
        label="Map-based surrogate reference",
    )
    path_axis.plot(
        example.estimate.x,
        example.estimate.y,
        linewidth=2,
        label="Sensor-based estimate",
    )
    reference_points = example.reference.sample(dataset.stations)
    estimate_points = example.estimate.sample(dataset.stations)
    for reference_point, estimate_point in zip(reference_points, estimate_points):
        path_axis.plot(
            [reference_point[0], estimate_point[0]],
            [reference_point[1], estimate_point[1]],
            color="0.65",
            linewidth=0.7,
        )
    path_axis.set_title("Accepted path-pair example")
    path_axis.set_xlabel("Local x [m]")
    path_axis.set_ylabel("Local y [m]")
    path_axis.axis("equal")
    path_axis.grid(alpha=0.25)
    path_axis.legend()

    residual_axis.plot(
        dataset.stations,
        dataset.residuals[:30].T,
        color="0.65",
        alpha=0.28,
        linewidth=0.8,
    )
    residual_axis.plot(
        dataset.stations,
        np.mean(dataset.residuals, axis=0),
        color="tab:blue",
        linewidth=2,
        label="Sample mean",
    )
    residual_axis.axhline(0.0, color="black", linewidth=0.8)
    residual_axis.set_title(f"Accepted residual paths (N={len(dataset.residuals)})")
    residual_axis.set_xlabel("Reference station s [m]")
    residual_axis.set_ylabel("Discrepancy e(s) [m]")
    residual_axis.grid(alpha=0.25)
    residual_axis.legend()

    deltas = np.asarray(
        [record.synchronization_delta_ms for record in dataset.records],
        dtype=np.float64,
    )
    synchronization_axis.hist(deltas, bins=min(20, max(1, len(deltas))))
    synchronization_axis.axvline(0.0, color="black", linewidth=0.8)
    synchronization_axis.set_title("Accepted timestamp differences")
    synchronization_axis.set_xlabel("Estimate time − reference time [ms]")
    synchronization_axis.set_ylabel("Count")
    synchronization_axis.grid(alpha=0.25)

    rejection_counts = dataset.report.rejection_dict
    if rejection_counts:
        labels = list(rejection_counts)
        counts = [rejection_counts[label] for label in labels]
        positions = np.arange(len(labels))
        rejection_axis.barh(positions, counts)
        rejection_axis.set_yticks(positions, labels=labels)
        rejection_axis.set_xlabel("Rejected pairs")
    else:
        rejection_axis.text(
            0.5,
            0.5,
            "No preprocessing rejections",
            ha="center",
            va="center",
            transform=rejection_axis.transAxes,
        )
        rejection_axis.set_xticks([])
        rejection_axis.set_yticks([])
    rejection_axis.set_title("Rejection audit")
    rejection_axis.grid(axis="x", alpha=0.25)

    figure.suptitle(
        "MCAP v0.3.1 diagnostics — map-based data is not confirmed ground truth",
        fontsize=13,
    )
    figure.tight_layout()
    return figure, axes
