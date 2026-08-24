"""Compact diagnostics for the v0.14 drive-grouped Gaussian re-baseline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def plot_expanded_gaussian_diagnostics(
    path: Path,
    *,
    stations_m: Sequence[float],
    evaluation_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Compare unconditional and conditional temporal-null baselines."""

    stations = np.asarray(stations_m, dtype=np.float64)
    model_names = ("unconditional_gaussian", "conditional_gaussian")
    labels = {
        "unconditional_gaussian": "Unconditional",
        "conditional_gaussian": "Conditional (6 features)",
    }
    colors = {
        "unconditional_gaussian": "#6c757d",
        "conditional_gaussian": "#2a6fbb",
    }
    overall_by_model: dict[str, list[Mapping[str, Any]]] = {}
    for model_name in model_names:
        rows = [
            row
            for row in station_rows
            if row["scope"] == "primary_cross_validated"
            and row["model_name"] == model_name
        ]
        rows.sort(key=lambda row: float(row["station_m"]))
        if len(rows) != len(stations) or not np.allclose(
            [float(row["station_m"]) for row in rows], stations
        ):
            raise ValueError(f"primary station diagnostics differ for {model_name}")
        overall_by_model[model_name] = rows
    folds = [
        row for row in evaluation_rows if row["scope"] == "primary_held_out_drive"
    ]
    held_out = sorted({str(row["held_out_drive_id"]) for row in folds})
    if len(held_out) < 3:
        raise ValueError("at least three primary held-out drives are required")

    figure, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    rmse_axis, coverage_axis = axes[0]
    lag_axis, fold_axis = axes[1]
    for model_name in model_names:
        rows = overall_by_model[model_name]
        rmse_axis.plot(
            stations,
            [float(row["sample_mean_prediction_rmse_m"]) for row in rows],
            marker="o",
            markersize=3,
            color=colors[model_name],
            label=labels[model_name],
        )
        coverage_axis.plot(
            stations,
            [float(row["marginal_95_coverage"]) for row in rows],
            marker="o",
            markersize=3,
            color=colors[model_name],
            label=labels[model_name],
        )
        lag_axis.plot(
            stations,
            [float(row["generated_median_lag_one_correlation"]) for row in rows],
            marker="o",
            markersize=3,
            color=colors[model_name],
            label=f"Generated {labels[model_name]}",
        )
    observed = overall_by_model[model_names[0]]
    lag_axis.plot(
        stations,
        [float(row["observed_lag_one_correlation"]) for row in observed],
        color="black",
        linewidth=2,
        label="Observed",
    )
    rmse_axis.set(title="Primary held-out sample-mean error", xlabel="Station (m)", ylabel="RMSE (m)")
    coverage_axis.set(title="Primary marginal calibration", xlabel="Station (m)", ylabel="Coverage", ylim=(0.0, 1.02))
    coverage_axis.axhline(0.95, color="black", linestyle="--", linewidth=1)
    lag_axis.set(title="Temporal-null diagnostic", xlabel="Station (m)", ylabel="Lag-one correlation", ylim=(-1.0, 1.0))
    for axis in (rmse_axis, coverage_axis, lag_axis):
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)

    positions = np.arange(len(held_out), dtype=np.float64)
    width = 0.36
    for model_index, model_name in enumerate(model_names):
        by_drive = {
            str(row["held_out_drive_id"]): float(row["mean_energy_score_m"])
            for row in folds
            if row["model_name"] == model_name
        }
        if set(by_drive) != set(held_out):
            raise ValueError(f"fold energy rows differ for {model_name}")
        offset = (model_index - 0.5) * width
        fold_axis.bar(
            positions + offset,
            [by_drive[drive] for drive in held_out],
            width=width,
            color=colors[model_name],
            label=labels[model_name],
        )
    fold_axis.set_xticks(positions)
    fold_axis.set_xticklabels(held_out, rotation=20, ha="right")
    fold_axis.set(title="Energy score by held-out physical drive", ylabel="Metres")
    fold_axis.grid(axis="y", alpha=0.25)
    fold_axis.legend(fontsize=8)

    figure.suptitle(
        "MPR v0.14 leakage-safe Gaussian re-baseline\n"
        "Clean drives only; mixed-source fragments are supplementary",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


__all__ = ["plot_expanded_gaussian_diagnostics"]
