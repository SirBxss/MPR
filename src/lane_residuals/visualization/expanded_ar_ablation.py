"""Focused diagnostics for the v0.15.1 one-state AR ablation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def _held_out_sequence_energy(
    rows: Sequence[Mapping[str, Any]], *, gaussian: bool = False
) -> dict[str, float]:
    result: dict[str, float] = {}
    expected_scope = "primary_held_out_drive" if gaussian else "held_out_drive"
    for row in rows:
        if row.get("scope") != expected_scope:
            continue
        if gaussian and row.get("model_name") != "conditional_gaussian":
            continue
        group = str(row.get("held_out_drive_id", ""))
        if not group or group in result:
            raise ValueError("held-out sequence-energy rows are ambiguous")
        result[group] = float(row["mean_normalized_sequence_energy_score_m"])
    return result


def plot_expanded_ar_ablation_diagnostics(
    path: Path,
    *,
    stations_m: Sequence[float],
    evaluation_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
    gaussian_evaluation_rows: Sequence[Mapping[str, Any]],
    aiohmm_evaluation_rows: Sequence[Mapping[str, Any]],
    gaussian_macro: Mapping[str, Any],
    one_state_macro: Mapping[str, Any],
    aiohmm_macro: Mapping[str, Any],
    final_autoregressive_coefficients: np.ndarray,
    maximum_absolute_autoregression: float,
) -> None:
    """Plot diagnostics that remain meaningful when no latent states exist."""

    stations = np.asarray(stations_m, dtype=np.float64)
    overall = [
        row for row in station_rows if row["scope"] == "overall_cross_validated"
    ]
    overall.sort(key=lambda row: float(row["station_m"]))
    if len(overall) != len(stations) or not np.allclose(
        [float(row["station_m"]) for row in overall], stations
    ):
        raise ValueError("one-state AR station diagnostics do not cover H100")
    coefficients = np.asarray(final_autoregressive_coefficients, dtype=np.float64)
    if coefficients.shape != (1, len(stations)):
        raise ValueError("one-state AR coefficient grid has the wrong shape")

    candidate_by_group = _held_out_sequence_energy(evaluation_rows)
    gaussian_by_group = _held_out_sequence_energy(
        gaussian_evaluation_rows, gaussian=True
    )
    aiohmm_by_group = _held_out_sequence_energy(aiohmm_evaluation_rows)
    if not candidate_by_group or not (
        set(candidate_by_group) == set(gaussian_by_group) == set(aiohmm_by_group)
    ):
        raise ValueError("model comparison groups differ")
    groups = sorted(candidate_by_group)

    figure, axes = plt.subplots(2, 3, figsize=(18, 10), constrained_layout=True)
    rmse_axis, coverage_axis, lag_axis = axes[0]
    macro_axis, sequence_axis, ar_axis = axes[1]

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
        label="Generated one-state AR",
    )
    lag_axis.set_ylim(-1.0, 1.0)
    lag_axis.set_title("Observed versus generated lag-one dependence")
    lag_axis.set_xlabel("Station (m)")
    lag_axis.set_ylabel("Pearson correlation")
    lag_axis.grid(alpha=0.25)
    lag_axis.legend(fontsize=8)

    metric_fields = (
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
    )
    metric_labels = ("RMSE", "Frame energy", "Sequence energy")
    model_payloads = (gaussian_macro, one_state_macro, aiohmm_macro)
    model_labels = ("Conditional Gaussian", "One-state AR", "Two-state AIOHMM")
    positions = np.arange(len(metric_fields), dtype=np.float64)
    width = 0.24
    for index, (label, payload) in enumerate(zip(model_labels, model_payloads)):
        macro_axis.bar(
            positions + (index - 1) * width,
            [float(payload[field]) for field in metric_fields],
            width=width,
            label=label,
        )
    macro_axis.set_xticks(positions)
    macro_axis.set_xticklabels(metric_labels)
    macro_axis.set_title("Primary macro-group sample metrics (lower is better)")
    macro_axis.set_ylabel("Metres")
    macro_axis.grid(axis="y", alpha=0.25)
    macro_axis.legend(fontsize=8)

    group_positions = np.arange(len(groups), dtype=np.float64)
    group_values = (gaussian_by_group, candidate_by_group, aiohmm_by_group)
    for index, (label, values) in enumerate(zip(model_labels, group_values)):
        sequence_axis.bar(
            group_positions + (index - 1) * width,
            [values[group] for group in groups],
            width=width,
            label=label,
        )
    sequence_axis.set_xticks(group_positions)
    sequence_axis.set_xticklabels(groups, rotation=20, ha="right")
    sequence_axis.set_title("Paired held-out-group sequence energy")
    sequence_axis.set_ylabel("Normalized energy score (m)")
    sequence_axis.grid(axis="y", alpha=0.25)
    sequence_axis.legend(fontsize=8)

    ar_axis.plot(
        stations,
        coefficients[0],
        marker="o",
        markersize=4,
        label="Fitted AR(1) coefficient",
    )
    ar_axis.axhline(
        maximum_absolute_autoregression,
        color="tab:red",
        linestyle="--",
        label="configured stability bounds",
    )
    ar_axis.axhline(
        -maximum_absolute_autoregression,
        color="tab:red",
        linestyle="--",
    )
    ar_axis.axhline(0.0, color="black", linewidth=0.8)
    ar_axis.set_ylim(-1.02, 1.02)
    ar_axis.set_title("All-clean descriptive AR coefficient profile")
    ar_axis.set_xlabel("Station (m)")
    ar_axis.set_ylabel("Coefficient")
    ar_axis.grid(alpha=0.25)
    ar_axis.legend(fontsize=8)

    figure.suptitle(
        "MPR v0.15.1 one-state conditional-AR ablation\n"
        "Same folds, transforms, hyperparameters, sampling, and metrics as v0.15",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


__all__ = ["plot_expanded_ar_ablation_diagnostics"]
