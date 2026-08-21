"""Deterministic overview plot for the expanded-corpus inventory."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..domain.corpus_inventory import ContinuityEdge, McapInventoryRecord


def plot_corpus_inventory(
    records: Sequence[McapInventoryRecord],
    edges: Sequence[ContinuityEdge],
    output: Path,
) -> None:
    """Plot file sizes, internal durations, and assessed boundary gaps."""

    ordered = list(records)
    positions = list(range(1, len(ordered) + 1))
    sizes_mb = [record.file_size_bytes / 1_000_000.0 for record in ordered]
    durations_s = [
        (record.internal_duration_ns or 0) / 1_000_000_000.0 for record in ordered
    ]
    colors = ["#2b8cbe" if record.usable else "#d95f0e" for record in ordered]

    figure, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
    axes[0].bar(positions, sizes_mb, color=colors, width=0.85)
    axes[0].set_ylabel("File size (MB)")
    axes[0].set_title("Expanded MCAP corpus (blue usable; orange excluded)")
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].bar(positions, durations_s, color=colors, width=0.85)
    axes[1].set_ylabel("Internal duration (s)")
    axes[1].grid(axis="y", alpha=0.25)

    edge_positions = list(range(1, len(edges) + 1))
    edge_gaps = [
        (edge.relevant_source_gap_ns or 0) / 1_000_000.0 for edge in edges
    ]
    edge_colors = ["#238b45" if edge.stitchable else "#cb181d" for edge in edges]
    axes[2].scatter(edge_positions, edge_gaps, c=edge_colors, s=24)
    axes[2].axhline(200.0, color="black", linestyle="--", linewidth=1.0)
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_xlabel("Chronological boundary index within mapped drives")
    axes[2].set_ylabel("Relevant source gap (ms)")
    axes[2].set_title("Boundary audit (green stitchable; red rejected)")
    axes[2].grid(alpha=0.25)

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        dpi=150,
        metadata={"Software": "lane_residuals corpus inventory"},
    )
    plt.close(figure)


__all__ = ["plot_corpus_inventory"]
