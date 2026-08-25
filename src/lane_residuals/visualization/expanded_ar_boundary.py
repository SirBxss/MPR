"""Focused diagnostics for the v0.15.3 AR-ceiling sensitivity audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def plot_expanded_ar_boundary_sensitivity(
    path: str | Path,
    *,
    model_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
    baseline_ceiling: float,
) -> Path:
    """Plot cap sensitivity, station calibration, and boundary contact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ar_models = [
        row
        for row in model_rows
        if row["model_family"] == "one_state_conditional_ar_gaussian"
    ]
    ar_models.sort(key=lambda row: float(row["maximum_absolute_autoregression"]))
    if not ar_models:
        raise ValueError("AR-boundary model comparison rows are missing")
    ceilings = np.asarray(
        [float(row["maximum_absolute_autoregression"]) for row in ar_models],
        dtype=np.float64,
    )
    if baseline_ceiling not in ceilings:
        raise ValueError("AR-boundary baseline row is missing")
    baseline = next(
        row
        for row in ar_models
        if float(row["maximum_absolute_autoregression"]) == baseline_ceiling
    )

    by_model: dict[str, list[Mapping[str, Any]]] = {}
    for row in station_rows:
        by_model.setdefault(str(row["model_id"]), []).append(row)
    for rows in by_model.values():
        rows.sort(key=lambda row: float(row["station_m"]))

    figure, axes = plt.subplots(2, 2, figsize=(14.5, 10), constrained_layout=True)
    macro_axis, coverage_axis, station_axis, boundary_axis = axes.flat

    metric_keys = (
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "absolute_marginal_95_coverage_error",
        "median_absolute_lag_one_correlation_error",
    )
    metric_labels = ("RMSE", "Frame ES", "Sequence ES", "Coverage error", "Lag-1")
    positions = np.arange(len(metric_keys), dtype=np.float64)
    width = 0.18
    for index, row in enumerate(ar_models):
        values = [float(row[key]) - float(baseline[key]) for key in metric_keys]
        macro_axis.bar(
            positions + (index - (len(ar_models) - 1) / 2) * width,
            values,
            width=width,
            label=f"cap {float(row['maximum_absolute_autoregression']):.3f}",
        )
    macro_axis.axhline(0.0, color="black", linewidth=0.8)
    macro_axis.set_xticks(positions, metric_labels, rotation=25, ha="right")
    macro_axis.set_ylabel("Delta from cap 0.980 (negative is better)")
    macro_axis.set_title("Held-out macro sensitivity")
    macro_axis.grid(axis="y", alpha=0.25)
    macro_axis.legend(fontsize=8)

    coverage_axis.plot(
        ceilings,
        [float(row["marginal_95_coverage"]) for row in ar_models],
        marker="o",
        label="Macro-group coverage",
    )
    coverage_axis.axhline(0.95, color="black", linestyle="--", label="Nominal 95%")
    coverage_axis.set_xlabel("Maximum absolute AR coefficient")
    coverage_axis.set_ylabel("Marginal coverage")
    coverage_axis.set_ylim(0.0, 1.02)
    coverage_axis.set_title("Calibration response")
    coverage_axis.grid(alpha=0.25)
    coverage_axis.legend(fontsize=8)

    colors = ("#4c78a8", "#f58518", "#54a24b", "#e45756")
    for color, row in zip(colors, ar_models):
        model_id = str(row["model_id"])
        rows = by_model.get(model_id, [])
        if not rows:
            raise ValueError(f"station rows are missing for {model_id}")
        station_axis.plot(
            [float(item["station_m"]) for item in rows],
            [float(item["marginal_95_coverage"]) for item in rows],
            marker="o",
            markersize=3,
            color=color,
            label=f"cap {float(row['maximum_absolute_autoregression']):.3f}",
        )
    baseline_rows = by_model[
        str(
            next(
                row["model_id"]
                for row in ar_models
                if float(row["maximum_absolute_autoregression"])
                == baseline_ceiling
            )
        )
    ]
    binding_stations = [
        float(row["station_m"])
        for row in baseline_rows
        if bool(row["reference_cap_binding_station"])
    ]
    for station in binding_stations:
        station_axis.axvspan(station - 1.0, station + 1.0, color="grey", alpha=0.08)
    station_axis.axhline(0.95, color="black", linestyle="--", linewidth=0.9)
    station_axis.set_xlabel("H100 station (m)")
    station_axis.set_ylabel("Marginal coverage")
    station_axis.set_ylim(0.0, 1.02)
    station_axis.set_title("Station calibration; shaded = cap-0.98 binding")
    station_axis.grid(alpha=0.2)
    station_axis.legend(fontsize=8)

    boundary_counts = []
    maximum_coefficients = []
    for row in ar_models:
        rows = by_model[str(row["model_id"])]
        boundary_counts.append(
            sum(bool(item["candidate_cap_binding_station"]) for item in rows)
        )
        maximum_coefficients.append(
            max(abs(float(item["median_model_autoregressive_coefficient"])) for item in rows)
        )
    positions = np.arange(len(ar_models), dtype=np.float64)
    boundary_axis.bar(positions, boundary_counts, color="#805ad5")
    boundary_axis.set_xticks(
        positions,
        [f"{ceiling:.3f}" for ceiling in ceilings],
    )
    boundary_axis.set_xlabel("Maximum absolute AR coefficient")
    boundary_axis.set_ylabel("Binding pooled station count")
    boundary_axis.set_title("Constraint contact after relaxing the ceiling")
    boundary_axis.grid(axis="y", alpha=0.25)
    coefficient_axis = boundary_axis.twinx()
    coefficient_axis.plot(
        positions,
        maximum_coefficients,
        color="#2f855a",
        marker="o",
        label="Maximum fitted |AR|",
    )
    coefficient_axis.set_ylabel("Maximum pooled |AR|")
    coefficient_axis.set_ylim(0.0, 1.01)

    figure.suptitle(
        "MPR v0.15.3 — one-state AR-boundary sensitivity\n"
        "Only the stationarity ceiling changes; all evidence is within one outing",
        fontsize=14,
    )
    figure.savefig(target, dpi=180)
    plt.close(figure)
    return target


__all__ = ["plot_expanded_ar_boundary_sensitivity"]
