"""Plots for the exact-manifest conditional-feature availability audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np


def _finite_values(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    *,
    drive_id: str | None = None,
) -> np.ndarray:
    values: list[float] = []
    for row in rows:
        if drive_id is not None and row.get("drive_id") != drive_id:
            continue
        value = row.get(field)
        if value is None or value == "":
            continue
        number = float(value)
        if np.isfinite(number):
            values.append(number)
    return np.asarray(values, dtype=np.float64)


def _histogram_by_drive(
    axis: Any,
    rows: Sequence[Mapping[str, Any]],
    field: str,
    *,
    title: str,
    xlabel: str,
) -> None:
    drives = sorted({str(row["drive_id"]) for row in rows})
    plotted = False
    for drive_id in drives:
        values = _finite_values(rows, field, drive_id=drive_id)
        if len(values) == 0:
            continue
        axis.hist(values, bins=30, alpha=0.55, density=True, label=drive_id)
        plotted = True
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Density")
    axis.grid(alpha=0.2)
    if plotted:
        axis.legend(fontsize=8)
    else:
        axis.text(0.5, 0.5, "No available values", ha="center", va="center")


def plot_conditional_feature_audit(
    path: Path,
    *,
    feature_rows: Sequence[Mapping[str, Any]],
    recording_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Plot coverage and distributions without silently selecting model rows."""

    if not feature_rows or not recording_rows:
        raise ValueError("feature and recording audit rows must be nonempty")
    figure, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)

    labels = [str(row["recording_id"]) for row in recording_rows]
    fractions = [float(row["feature_ready_fraction"]) for row in recording_rows]
    axes[0, 0].bar(np.arange(len(labels)), fractions, color="tab:blue")
    axes[0, 0].axhline(1.0, color="black", linestyle="--", linewidth=0.9)
    axes[0, 0].set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
    axes[0, 0].set_ylim(0.0, 1.05)
    axes[0, 0].set_title("Feature-ready fraction by recording")
    axes[0, 0].set_ylabel("Fraction of canonical residual vectors")
    axes[0, 0].grid(axis="y", alpha=0.2)

    _histogram_by_drive(
        axes[0, 1],
        feature_rows,
        "speed_mps",
        title=(
            "Prediction-time signed longitudinal speed"
            if all(bool(row.get("speed_is_signed")) for row in feature_rows)
            else "Prediction-time unsigned odometry speed"
        ),
        xlabel="Speed (m/s; magnitude when unsigned)",
    )
    _histogram_by_drive(
        axes[0, 2],
        feature_rows,
        "estimated_mean_abs_curvature_per_m",
        title="EDP mean absolute curvature over H100",
        xlabel="Mean |curvature| (1/m)",
    )
    _histogram_by_drive(
        axes[1, 0],
        feature_rows,
        "estimated_curvature_delta_per_m",
        title="EDP curvature change over H100",
        xlabel="Curvature(100 m) - curvature(0 m) (1/m)",
    )

    drives = sorted({str(row["drive_id"]) for row in feature_rows})
    confidence_fields = (
        "confidence_near_mean",
        "confidence_middle_mean",
        "confidence_far_mean",
    )
    positions = np.arange(3, dtype=np.float64)
    for drive_index, drive_id in enumerate(drives):
        means: list[float] = []
        lower: list[float] = []
        upper: list[float] = []
        for field in confidence_fields:
            values = _finite_values(feature_rows, field, drive_id=drive_id)
            if len(values):
                means.append(float(np.median(values)))
                lower.append(float(np.quantile(values, 0.10)))
                upper.append(float(np.quantile(values, 0.90)))
            else:
                means.append(float("nan"))
                lower.append(float("nan"))
                upper.append(float("nan"))
        mean_array = np.asarray(means)
        axes[1, 1].plot(positions, mean_array, marker="o", label=drive_id)
        axes[1, 1].fill_between(
            positions,
            np.asarray(lower),
            np.asarray(upper),
            alpha=0.15,
        )
    axes[1, 1].set_xticks(positions, ("near", "middle", "far"))
    axes[1, 1].set_ylim(0.0, 1.02)
    axes[1, 1].set_title("KEEP_LANE confidence: median and 10–90%")
    axes[1, 1].set_ylabel("Confidence")
    axes[1, 1].grid(alpha=0.2)
    if drives:
        axes[1, 1].legend(fontsize=8)

    feature_names = (
        "speed",
        "curvature",
        "confidence near",
        "confidence middle",
        "confidence far",
    )
    availability_fields = (
        "speed_mps",
        "estimated_mean_abs_curvature_per_m",
        "confidence_near_mean",
        "confidence_middle_mean",
        "confidence_far_mean",
    )
    availability = [
        len(_finite_values(feature_rows, field)) / len(feature_rows)
        for field in availability_fields
    ]
    axes[1, 2].bar(np.arange(len(feature_names)), availability, color="tab:green")
    axes[1, 2].set_xticks(
        np.arange(len(feature_names)),
        feature_names,
        rotation=35,
        ha="right",
    )
    axes[1, 2].set_ylim(0.0, 1.05)
    axes[1, 2].set_title("Individual feature availability")
    axes[1, 2].set_ylabel("Fraction of canonical residual vectors")
    axes[1, 2].grid(axis="y", alpha=0.2)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


__all__ = ["plot_conditional_feature_audit"]
