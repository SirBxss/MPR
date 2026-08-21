"""Concise diagnostic plot for topology semantics and anchor quality."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np


def plot_topology_quality_diagnostic(
    path: Path,
    *,
    message_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Plot session topology proportions and eligible anchor distances."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sessions = sorted({str(row["drive_id"]) for row in message_rows})
    sources = sorted({str(row["topology_source_name"]) for row in message_rows})
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    bottoms = np.zeros(len(sessions), dtype=np.float64)
    for source in sources:
        proportions = []
        for session in sessions:
            counts = Counter(
                str(row["topology_source_name"])
                for row in message_rows
                if str(row["drive_id"]) == session
            )
            total = sum(counts.values())
            proportions.append(counts[source] / total if total else 0.0)
        values = np.asarray(proportions, dtype=np.float64)
        axes[0].bar(sessions, values, bottom=bottoms, label=source.replace("ROAD_TOPOLOGY_SOURCE_", ""))
        bottoms += values
    axes[0].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("message fraction")
    axes[0].set_title("EDP topology source by physical session")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].legend(fontsize=8)

    distances = [
        float(row["anchor_distance_m"])
        for row in message_rows
        if row.get("h60_aligned_eligible") is True
        and row.get("anchor_distance_m") not in {None, ""}
    ]
    if distances:
        axes[1].hist(distances, bins=50, color="tab:blue", alpha=0.8)
        axes[1].axvline(1.0, color="tab:red", linestyle="--", label="audit listing > 1.0 m")
        axes[1].set_xlabel("anchor distance [m]")
        axes[1].set_ylabel("eligible pair count")
        axes[1].set_title("Current H60-eligible anchor distance")
        axes[1].legend(fontsize=8)
    else:
        axes[1].text(.5, .5, "No H60-eligible pairs", ha="center", va="center")
        axes[1].set_axis_off()
    for axis in axes:
        axis.grid(True, alpha=.2)
    figure.suptitle("CONFIDENTIAL — read-only topology and alignment-quality audit")
    figure.tight_layout(rect=(0, 0, 1, .94))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


__all__ = ["plot_topology_quality_diagnostic"]
