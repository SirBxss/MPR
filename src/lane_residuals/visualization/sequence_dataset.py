"""Diagnostics for the common v0.9.0 sequential dataset."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike

from ..domain.sequence_dataset import SequentialResidualDataset


def plot_sequence_dataset_diagnostics(
    path: Path,
    *,
    dataset: SequentialResidualDataset,
    raw_lag_one_correlations: ArrayLike,
) -> None:
    """Plot sequence support and raw temporal dependence without fitting a model."""

    correlations = np.asarray(raw_lag_one_correlations, dtype=np.float64)
    stations = np.asarray(dataset.to_padded().stations_m, dtype=np.float64)
    if correlations.shape != stations.shape or not np.all(np.isfinite(correlations)):
        raise ValueError("lag-one correlations must align with the station grid")

    drive_ids = dataset.drive_ids
    color_map = {
        drive_id: plt.get_cmap("tab10")(index % 10)
        for index, drive_id in enumerate(drive_ids)
    }
    sequence_labels = [sequence.sequence_id for sequence in dataset.sequences]
    sequence_positions = np.arange(len(sequence_labels), dtype=np.float64)
    frame_counts = np.asarray(
        [sequence.length for sequence in dataset.sequences],
        dtype=np.int64,
    )
    durations = np.asarray(
        [sequence.duration_s for sequence in dataset.sequences],
        dtype=np.float64,
    )
    intervals = np.concatenate(
        [
            sequence.interval_ms
            for sequence in dataset.sequences
            if sequence.length > 1
        ]
    )
    if len(intervals) == 0:
        raise ValueError("sequence diagnostics require at least one transition")

    figure, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    count_axis, duration_axis = axes[0]
    interval_axis, correlation_axis = axes[1]

    for drive_id in drive_ids:
        mask = np.asarray(
            [sequence.drive_id == drive_id for sequence in dataset.sequences]
        )
        count_axis.bar(
            sequence_positions[mask],
            frame_counts[mask],
            color=color_map[drive_id],
            label=drive_id,
        )
        duration_axis.bar(
            sequence_positions[mask],
            durations[mask],
            color=color_map[drive_id],
            label=drive_id,
        )

    for axis, title, ylabel in (
        (count_axis, "Frames per contiguous sequence", "Frames"),
        (duration_axis, "Duration per contiguous sequence", "Duration (s)"),
    ):
        axis.set_title(title)
        axis.set_xlabel("Sequence")
        axis.set_ylabel(ylabel)
        axis.set_xticks(sequence_positions)
        axis.set_xticklabels(sequence_labels, rotation=55, ha="right", fontsize=7)
        axis.grid(axis="y", alpha=0.25)
        axis.legend(fontsize=8)

    interval_axis.hist(intervals, bins=min(30, max(5, int(np.sqrt(len(intervals))))))
    interval_axis.axvline(
        dataset.maximum_contiguous_gap_ms,
        color="tab:red",
        linestyle="--",
        label=f"split threshold ({dataset.maximum_contiguous_gap_ms:g} ms)",
    )
    interval_axis.set_title("Intervals retained inside sequences")
    interval_axis.set_xlabel("Interval (ms)")
    interval_axis.set_ylabel("Transition count")
    interval_axis.grid(alpha=0.25)
    interval_axis.legend(fontsize=8)

    correlation_axis.plot(stations, correlations, marker="o", markersize=4)
    correlation_axis.axhline(0.0, color="black", linewidth=0.8)
    correlation_axis.set_ylim(-1.0, 1.0)
    correlation_axis.set_title("Raw residual lag-one correlation")
    correlation_axis.set_xlabel("Station (m)")
    correlation_axis.set_ylabel("Pearson correlation")
    correlation_axis.grid(alpha=0.25)

    figure.suptitle(
        "MPR v0.9.0 sequential dataset diagnostics\n"
        "Recording-local gaps only; no model fitted",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


__all__ = ["plot_sequence_dataset_diagnostics"]
