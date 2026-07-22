"""Visual checks for the minimal residual-extraction pipeline."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from numpy.typing import ArrayLike

from .residuals import Path2D, residual_vector


def plot_path_pair_and_residual(
    ground_truth: Path2D,
    estimate: Path2D,
    stations: ArrayLike,
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot path geometry and its signed residual vector side by side."""

    stations_array = np.asarray(stations, dtype=np.float64)
    residual = residual_vector(ground_truth, estimate, stations_array)
    ground_truth_points = ground_truth.sample(stations_array)
    estimate_points = estimate.sample(stations_array)

    figure, (path_axis, residual_axis) = plt.subplots(1, 2, figsize=(11, 4.5))

    path_axis.plot(ground_truth.x, ground_truth.y, label="Ground truth", linewidth=2)
    path_axis.plot(estimate.x, estimate.y, label="Estimate", linewidth=2)
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
