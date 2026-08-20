"""Diagnostics for the v0.10.0 sequence-contract Gaussian baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np


def plot_sequence_gaussian_diagnostics(
    path: Path,
    *,
    stations_m: Sequence[float],
    evaluation_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Plot held-out spatial, calibration, and temporal-null diagnostics."""

    stations = np.asarray(stations_m, dtype=np.float64)
    overall = [row for row in station_rows if row["scope"] == "overall_cross_validated"]
    if len(overall) != len(stations):
        raise ValueError("overall station diagnostics do not cover H100")
    overall.sort(key=lambda row: float(row["station_m"]))
    if not np.allclose(
        [float(row["station_m"]) for row in overall],
        stations,
    ):
        raise ValueError("overall station diagnostic grid differs from H100")
    held_out = [row for row in evaluation_rows if row["scope"] == "held_out_drive"]
    if len(held_out) < 2:
        raise ValueError("at least two held-out drive rows are required")
    held_out.sort(key=lambda row: str(row["held_out_drive_id"]))

    figure, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    rmse_axis, coverage_axis = axes[0]
    lag_axis, fold_axis = axes[1]

    rmse_axis.plot(
        stations,
        [float(row["sample_mean_prediction_rmse_m"]) for row in overall],
        marker="o",
        markersize=4,
    )
    rmse_axis.set_title("Cross-validated sample-mean error")
    rmse_axis.set_xlabel("Station (m)")
    rmse_axis.set_ylabel("RMSE (m)")
    rmse_axis.grid(alpha=0.25)

    coverage_axis.plot(
        stations,
        [float(row["marginal_95_coverage"]) for row in overall],
        marker="o",
        markersize=4,
    )
    coverage_axis.axhline(0.95, color="black", linestyle="--", label="nominal 95%")
    coverage_axis.set_ylim(0.0, 1.02)
    coverage_axis.set_title("Sample-based marginal calibration")
    coverage_axis.set_xlabel("Station (m)")
    coverage_axis.set_ylabel("Coverage")
    coverage_axis.grid(alpha=0.25)
    coverage_axis.legend(fontsize=8)

    lag_axis.plot(
        stations,
        [float(row["observed_lag_one_correlation"]) for row in overall],
        marker="o",
        markersize=4,
        label="Observed",
    )
    lag_axis.plot(
        stations,
        [float(row["generated_median_lag_one_correlation"]) for row in overall],
        marker="o",
        markersize=4,
        label="Generated temporal null",
    )
    lag_axis.set_ylim(-1.0, 1.0)
    lag_axis.set_title("Observed versus generated lag-one dependence")
    lag_axis.set_xlabel("Station (m)")
    lag_axis.set_ylabel("Pearson correlation")
    lag_axis.grid(alpha=0.25)
    lag_axis.legend(fontsize=8)

    positions = np.arange(len(held_out), dtype=np.float64)
    width = 0.35
    fold_axis.bar(
        positions - width / 2.0,
        [float(row["sample_mean_prediction_rmse_m"]) for row in held_out],
        width=width,
        label="Sample-mean RMSE",
    )
    fold_axis.bar(
        positions + width / 2.0,
        [float(row["mean_energy_score_m"]) for row in held_out],
        width=width,
        label="Energy score",
    )
    fold_axis.set_xticks(positions)
    fold_axis.set_xticklabels(
        [str(row["held_out_drive_id"]) for row in held_out],
        rotation=20,
        ha="right",
    )
    fold_axis.set_title("Physical-drive-held-out sample metrics")
    fold_axis.set_ylabel("Metres")
    fold_axis.grid(axis="y", alpha=0.25)
    fold_axis.legend(fontsize=8)

    figure.suptitle(
        "MPR v0.10.0 sequence-contract conditional Gaussian\n"
        "Independent emissions are the declared temporal null",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


__all__ = ["plot_sequence_gaussian_diagnostics"]
