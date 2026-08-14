"""Plots for single-recording pairing diagnostics."""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ..domain.pairing import (
    EgoRelativePath,
    compare_ego_relative_paths,
    sample_ego_relative_path,
)


@dataclass(frozen=True)
class PairPlot:
    title: str
    estimate: EgoRelativePath = field(repr=False)
    reference: EgoRelativePath = field(repr=False)
    stations_m: tuple[float, ...]


def plot_pairs(path: Path, plots: Sequence[PairPlot]) -> None:
    if not plots:
        path.unlink(missing_ok=True)
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = min(4, len(plots))
    rows = int(math.ceil(len(plots) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(4.7 * columns, 3.9 * rows), squeeze=False)
    for axis, item in zip(axes.flat, plots):
        for geometry, label, color in (
            (item.reference, "RLMB pseudo-reference candidate", "tab:blue"),
            (item.estimate, "Estimated KEEP_LANE", "tab:orange"),
        ):
            visible = (geometry.stations_m >= -10.0) & (geometry.stations_m <= max(item.stations_m) + 5.0)
            axis.plot(geometry.x_m[visible], geometry.y_m[visible], color=color, linewidth=1.5, label=label)
            sampled = sample_ego_relative_path(geometry, item.stations_m)
            axis.scatter(sampled.x_m, sampled.y_m, color=color, s=8)
            axis.scatter(geometry.origin_footpoint_m[0], geometry.origin_footpoint_m[1], color=color, marker="x", s=35)
        axis.scatter(0.0, 0.0, color="black", marker="+", s=45, label="(0,0)")
        axis.set_title(item.title, fontsize=9)
        axis.set_xlabel("x [m]")
        axis.set_ylabel("y [m]")
        axis.grid(True, alpha=0.25)
        axis.set_aspect("equal", adjustable="datalim")
    for axis in axes.flat[len(plots):]:
        axis.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, fontsize=9)
    figure.suptitle("EDP–RLMB raw-frame pairing audit (diagnostic only; no motion compensation)", fontsize=12, y=0.997)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.975))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_lateral_zoom(path: Path, plots: Sequence[PairPlot]) -> None:
    if not plots:
        path.unlink(missing_ok=True)
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = min(4, len(plots))
    rows = int(math.ceil(len(plots) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(4.7 * columns, 3.4 * rows), squeeze=False, sharey=True)
    disagreements = [compare_ego_relative_paths(item.estimate, item.reference, stations_m=item.stations_m) for item in plots]
    shared_limit = max(0.5, max(float(np.max(np.abs(item.lateral_m))) for item in disagreements) * 1.15)
    for axis, item, disagreement in zip(axes.flat, plots, disagreements):
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.plot(disagreement.stations_m, disagreement.lateral_m, color="tab:purple", marker="o", markersize=2.8, linewidth=1.2)
        axis.axvspan(0.0, min(60.0, max(item.stations_m)), color="tab:green", alpha=0.06)
        axis.set_ylim(-shared_limit, shared_limit)
        axis.set_title(item.title, fontsize=9)
        axis.set_xlabel("ego-relative station [m]")
        axis.set_ylabel("signed lateral disagreement [m]")
        axis.grid(True, alpha=0.25)
    for axis in axes.flat[len(plots):]:
        axis.set_visible(False)
    figure.suptitle("EDP–RLMB lateral zoom (diagnostic only; green = primary 0–60 m)", fontsize=12, y=0.997)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.975))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_station_profiles(path: Path, station_rows: Sequence[dict[str, Any]]) -> None:
    if not station_rows:
        path.unlink(missing_ok=True)
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grouped: dict[float, list[float]] = {}
    for row in station_rows:
        grouped.setdefault(float(row["station_m"]), []).append(float(row["diagnostic_lateral_m"]))
    stations = np.asarray(sorted(grouped), dtype=np.float64)
    values = [np.asarray(grouped[station], dtype=np.float64) for station in stations]
    medians = np.asarray([np.median(item) for item in values], dtype=np.float64)
    lower = np.asarray([np.quantile(item, 0.05) for item in values], dtype=np.float64)
    upper = np.asarray([np.quantile(item, 0.95) for item in values], dtype=np.float64)
    rms = np.asarray([np.sqrt(np.mean(np.square(item))) for item in values], dtype=np.float64)
    counts = np.asarray([len(item) for item in values], dtype=np.int64)
    figure, axes = plt.subplots(3, 1, figsize=(9.5, 9.0), sharex=True)
    axes[0].fill_between(stations, lower, upper, color="tab:blue", alpha=0.2, label="5–95%")
    axes[0].plot(stations, medians, color="tab:blue", marker="o", label="median")
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_ylabel("lateral [m]")
    axes[0].set_title("Signed EDP–RLMB diagnostic disagreement")
    axes[0].legend()
    axes[1].plot(stations, rms, color="tab:orange", marker="o")
    axes[1].set_ylabel("RMS [m]")
    axes[1].set_title("Station-wise RMS")
    axes[2].step(stations, counts, where="mid", color="tab:green")
    axes[2].set_ylabel("pair count")
    axes[2].set_xlabel("ego-relative station [m]")
    axes[2].set_title("Available diagnostic pairs")
    for axis in axes:
        axis.axvline(60.0, color="tab:red", linestyle="--", linewidth=1.0)
        axis.grid(True, alpha=0.25)
    figure.suptitle("CONFIDENTIAL — pseudo-reference diagnostics; no motion compensation", fontsize=12)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)
