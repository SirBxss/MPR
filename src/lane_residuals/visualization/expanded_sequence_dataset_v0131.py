"""Concise v0.13.1 boundary-context sequence diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np


def plot_expanded_sequence_diagnostics_v0131(
    path: Path,
    *,
    drive_rows: Sequence[Mapping[str, Any]],
    sequence_rows: Sequence[Mapping[str, Any]],
    profile_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Show retained profiles, stitched sequence lengths, and heading evidence."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    drives = [str(row["drive_id"]) for row in drive_rows]
    retained = np.asarray([int(row["eligible_profile_count"]) for row in drive_rows])
    excluded = np.asarray([int(row["excluded_profile_count"]) for row in drive_rows])
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.2))
    axes[0].bar(drives, retained, label="eligible sensor H100")
    axes[0].bar(drives, excluded, bottom=retained, label="excluded")
    axes[0].set_title("Profiles by physical drive")
    axes[0].set_ylabel("message/profile count")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].legend(fontsize=8)

    lengths = [int(row["frame_count"]) for row in sequence_rows]
    axes[1].hist(lengths, bins=min(40, max(1, len(set(lengths)))))
    axes[1].set_title("Boundary-aware sequence lengths")
    axes[1].set_xlabel("frames")
    axes[1].set_ylabel("sequence count")

    headings = [
        abs(float(row["anchor_heading_delta_rad"]))
        for row in profile_rows
        if row.get("profile_eligible") in {True, "True"}
        and row.get("anchor_heading_delta_rad") not in {None, ""}
    ]
    axes[2].hist(headings, bins=50)
    axes[2].set_title("Eligible absolute anchor heading")
    axes[2].set_xlabel("|heading delta| [rad]")
    axes[2].set_ylabel("profile count")
    for axis in axes:
        axis.grid(True, alpha=0.2)
    figure.suptitle("CONFIDENTIAL — v0.13.1 accepted-boundary odometry context")
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


__all__ = ["plot_expanded_sequence_diagnostics_v0131"]
