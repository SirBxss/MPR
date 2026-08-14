"""Plots for fixed-cohort batch pairing diagnostics."""

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def plot_fixed_cohorts(path: Path, station_rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    overall = [row for row in station_rows if row["scope_type"] == "overall"]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), squeeze=False)
    for row_index, horizon in enumerate((60, 100)):
        rows = sorted(
            (row for row in overall if int(row["horizon_m"]) == horizon),
            key=lambda row: float(row["station_m"]),
        )
        stations = np.asarray([row["station_m"] for row in rows], dtype=np.float64)
        counts = [int(row["cohort_pair_count"]) for row in rows]
        if rows and counts and counts[0] > 0:
            median = np.asarray([row["lateral_median_m"] for row in rows], dtype=np.float64)
            p05 = np.asarray([row["lateral_p05_m"] for row in rows], dtype=np.float64)
            p95 = np.asarray([row["lateral_p95_m"] for row in rows], dtype=np.float64)
            rms = np.asarray([row["lateral_rms_m"] for row in rows], dtype=np.float64)
            axes[row_index, 0].plot(stations, median, color="tab:blue", label="median")
            axes[row_index, 0].fill_between(stations, p05, p95, color="tab:blue", alpha=0.2, label="5--95%")
            axes[row_index, 1].plot(stations, rms, color="tab:orange", marker="o", markersize=3)
            axes[row_index, 0].legend(loc="best")
        else:
            for axis in axes[row_index]:
                axis.text(0.5, 0.5, "No complete cohort", ha="center", va="center", transform=axis.transAxes)
        axes[row_index, 0].set_title(f"Fixed H{horizon} cohort: signed distribution")
        axes[row_index, 1].set_title(f"Fixed H{horizon} cohort: RMS")
        for axis in axes[row_index]:
            axis.set_xlabel("ego-relative station [m]")
            axis.set_ylabel("diagnostic lateral disagreement [m]")
            axis.grid(True, alpha=0.25)
            if counts:
                axis.text(0.02, 0.96, f"n={counts[0]} pairs at every station", transform=axis.transAxes, va="top")
    figure.suptitle("CONFIDENTIAL — fixed-cohort EDP–RLMB pseudo-residual diagnostics")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_recording_summary(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    successful = [row for row in rows if row["status"] == "succeeded"]
    figure, axis = plt.subplots(figsize=(max(9.0, 0.8 * len(successful) + 3.0), 5.5))
    if successful:
        x = np.arange(len(successful), dtype=np.float64)
        h60 = [row["h60_median_pair_lateral_rms_m"] for row in successful]
        h100 = [row["h100_median_pair_lateral_rms_m"] for row in successful]
        axis.bar(x - 0.2, [0.0 if value is None else value for value in h60], width=0.4, label="H60")
        axis.bar(x + 0.2, [0.0 if value is None else value for value in h100], width=0.4, label="H100")
        axis.set_xticks(x, [row["recording_id"] for row in successful], rotation=45, ha="right")
        axis.legend()
    else:
        axis.text(0.5, 0.5, "No successful recordings", ha="center", va="center", transform=axis.transAxes)
    axis.set_ylabel("median per-pair lateral RMS [m]")
    axis.set_title("Recording-level fixed-cohort diagnostic summary")
    axis.grid(True, axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_temporal(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    drive_ids = sorted({str(row["drive_id"]) for row in rows})
    figure, axes = plt.subplots(max(1, len(drive_ids)), 1, figsize=(12, max(4.0, 3.4 * len(drive_ids))), squeeze=False)
    if not drive_ids:
        axes[0, 0].text(0.5, 0.5, "No temporal pairs", ha="center", va="center", transform=axes[0, 0].transAxes)
    for index, drive_id in enumerate(drive_ids):
        axis = axes[index, 0]
        drive_rows = [row for row in rows if row["drive_id"] == drive_id and row["drive_relative_source_time_s"] is not None]
        for key, label, color in (
            ("h60_pair_lateral_rms_m", "H60", "tab:blue"),
            ("h100_pair_lateral_rms_m", "H100", "tab:orange"),
        ):
            selected = [row for row in drive_rows if row[key] is not None]
            axis.plot([row["drive_relative_source_time_s"] for row in selected], [row[key] for row in selected], marker=".", linewidth=0.8, markersize=3, color=color, label=label)
        primary_threshold = next((row["h60_tail_threshold_m"] for row in drive_rows if row["h60_tail_threshold_m"] is not None), None)
        full_threshold = next((row["h100_tail_threshold_m"] for row in drive_rows if row["h100_tail_threshold_m"] is not None), None)
        if primary_threshold is not None:
            axis.axhline(primary_threshold, color="tab:blue", linestyle="--", alpha=0.6)
        if full_threshold is not None:
            axis.axhline(full_threshold, color="tab:orange", linestyle="--", alpha=0.6)
        axis.set_title(drive_id)
        axis.set_xlabel("drive-relative source time [s]")
        axis.set_ylabel("per-pair lateral RMS [m]")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best")
    figure.suptitle("CONFIDENTIAL — temporal pseudo-residual diagnostics")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    figure.savefig(path, dpi=170)
    plt.close(figure)
