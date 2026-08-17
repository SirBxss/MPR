"""Diagnostic visualization for the canonical unconditional Gaussian baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike

from ..modeling.gaussian import GaussianResidualModel


def plot_gaussian_baseline_diagnostics(
    path: Path,
    *,
    stations_m: ArrayLike,
    residual_matrix_m: ArrayLike,
    model: GaussianResidualModel,
    held_out_station_rmse_m: Mapping[str, Sequence[float]],
) -> None:
    """Plot empirical/model marginals, covariance correlation, and fold RMSE."""

    stations = np.asarray(stations_m, dtype=np.float64)
    residuals = np.asarray(residual_matrix_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or len(stations) == 0
        or residuals.ndim != 2
        or residuals.shape[0] == 0
        or residuals.shape[1] != len(stations)
    ):
        raise ValueError("residual matrix and stations have incompatible shapes")

    empirical_mean = np.mean(residuals, axis=0)
    empirical_p05, empirical_p95 = np.quantile(residuals, (0.05, 0.95), axis=0)
    model_standard_deviation = np.sqrt(np.diag(model.covariance))
    model_lower = model.mean - 1.959963984540054 * model_standard_deviation
    model_upper = model.mean + 1.959963984540054 * model_standard_deviation
    correlation = model.covariance / np.outer(
        model_standard_deviation,
        model_standard_deviation,
    )

    figure, axes = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)

    marginal_axis = axes[0]
    marginal_axis.fill_between(
        stations,
        model_lower,
        model_upper,
        color="tab:blue",
        alpha=0.18,
        label="Gaussian marginal 95%",
    )
    marginal_axis.fill_between(
        stations,
        empirical_p05,
        empirical_p95,
        color="tab:orange",
        alpha=0.20,
        label="Empirical 5–95%",
    )
    marginal_axis.plot(stations, model.mean, color="tab:blue", label="Model mean")
    marginal_axis.plot(
        stations,
        empirical_mean,
        color="tab:orange",
        linestyle="--",
        label="Empirical mean",
    )
    marginal_axis.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
    marginal_axis.set_title("Final all-data fit")
    marginal_axis.set_xlabel("Station (m)")
    marginal_axis.set_ylabel("Signed lateral residual (m)")
    marginal_axis.grid(alpha=0.25)
    marginal_axis.legend(fontsize=8)

    correlation_axis = axes[1]
    image = correlation_axis.imshow(
        correlation,
        origin="lower",
        vmin=-1.0,
        vmax=1.0,
        cmap="coolwarm",
        extent=(stations[0] - 2.5, stations[-1] + 2.5) * 2,
        aspect="auto",
    )
    correlation_axis.set_title("Spatial correlation")
    correlation_axis.set_xlabel("Station (m)")
    correlation_axis.set_ylabel("Station (m)")
    figure.colorbar(image, ax=correlation_axis, label="Correlation")

    rmse_axis = axes[2]
    for drive_id, values in sorted(held_out_station_rmse_m.items()):
        rmse = np.asarray(values, dtype=np.float64)
        if rmse.shape != stations.shape:
            raise ValueError("held-out station RMSE has the wrong dimension")
        rmse_axis.plot(stations, rmse, marker="o", markersize=3, label=drive_id)
    rmse_axis.set_title("Leave-one-drive-out error")
    rmse_axis.set_xlabel("Station (m)")
    rmse_axis.set_ylabel("Held-out mean-prediction RMSE (m)")
    rmse_axis.grid(alpha=0.25)
    rmse_axis.legend(title="Held-out drive", fontsize=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


__all__ = ["plot_gaussian_baseline_diagnostics"]
