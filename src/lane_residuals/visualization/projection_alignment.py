"""Plots for native projection-based reference alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def _finite_rows(
    rows: Sequence[Mapping[str, Any]],
    key: str,
) -> list[Mapping[str, Any]]:
    finite: list[Mapping[str, Any]] = []
    for row in rows:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            if np.isfinite(float(value)):
                finite.append(row)
        except (TypeError, ValueError):
            continue
    return finite


def plot_alignment_comparison(
    path: Path,
    *,
    pair_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Compare native and spatially aligned disagreement without hiding counts."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not station_rows:
        figure, axis = plt.subplots(1, 1, figsize=(9.0, 4.5))
        axis.text(
            0.5,
            0.5,
            "No spatially aligned pairs with complete H60 coverage",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        axis.set_axis_off()
        figure.suptitle(
            "CONFIDENTIAL — spatial reference alignment validation",
            fontsize=12,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=170)
        plt.close(figure)
        return

    grouped: dict[float, list[Mapping[str, Any]]] = {}
    for row in station_rows:
        grouped.setdefault(float(row["station_m"]), []).append(row)
    stations = np.asarray(sorted(grouped), dtype=np.float64)
    native_median: list[float] = []
    aligned_median: list[float] = []
    native_rms: list[float] = []
    aligned_rms: list[float] = []
    comparison_counts: list[int] = []
    aligned_counts: list[int] = []
    for station in stations:
        rows = grouped[float(station)]
        aligned = np.asarray(
            [float(row["aligned_lateral_m"]) for row in rows],
            dtype=np.float64,
        )
        native = np.asarray(
            [
                float(row["native_lateral_m"])
                for row in rows
                if row.get("native_lateral_m") not in {None, ""}
            ],
            dtype=np.float64,
        )
        aligned_median.append(float(np.median(aligned)))
        aligned_rms.append(float(np.sqrt(np.mean(np.square(aligned)))))
        aligned_counts.append(len(aligned))
        native_median.append(float(np.median(native)) if len(native) else np.nan)
        native_rms.append(
            float(np.sqrt(np.mean(np.square(native)))) if len(native) else np.nan
        )
        comparison_counts.append(len(native))

    figure, axes = plt.subplots(3, 1, figsize=(10.0, 10.0))
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].plot(stations, native_median, marker="o", label="native stationing")
    axes[0].plot(
        stations,
        aligned_median,
        marker="o",
        label="projected-reference alignment",
    )
    axes[0].set_ylabel("median lateral [m]")
    axes[0].set_title("Station-wise median disagreement")
    axes[0].legend()

    axes[1].plot(stations, native_rms, marker="o", label="native stationing")
    axes[1].plot(
        stations,
        aligned_rms,
        marker="o",
        label="projected-reference alignment",
    )
    axes[1].set_ylabel("RMS [m]")
    axes[1].set_title("Station-wise lateral RMS")
    axes[1].legend()

    h100_pairs = _finite_rows(
        pair_rows,
        "aligned_minus_native_h100_lateral_rms_m",
    )
    if h100_pairs:
        axes[2].scatter(
            [float(row["source_delta_ms"]) for row in h100_pairs],
            [
                float(row["aligned_minus_native_h100_lateral_rms_m"])
                for row in h100_pairs
            ],
            s=14,
            alpha=0.7,
        )
        axes[2].axhline(0.0, color="black", linewidth=0.8)
        axes[2].set_xlabel("signed EDP minus RLMB source time [ms]")
        axes[2].set_ylabel("aligned − native H100 pair RMS [m]")
        axes[2].set_title("Alignment effect versus timestamp offset")
    else:
        axes[2].step(stations, aligned_counts, where="mid", label="aligned")
        axes[2].step(
            stations,
            comparison_counts,
            where="mid",
            label="native comparison available",
        )
        axes[2].set_xlabel("station [m]")
        axes[2].set_ylabel("pair count")
        axes[2].set_title("Available comparison pairs")
        axes[2].legend()

    for axis in axes[:2]:
        axis.axvline(60.0, color="tab:red", linestyle="--", linewidth=1.0)
        axis.set_xlabel("aligned forward station [m]")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    figure.suptitle(
        "CONFIDENTIAL — spatial reference alignment; not explicit motion compensation",
        fontsize=12,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)
