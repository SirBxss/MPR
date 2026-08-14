"""Diagnostic overlays for geometry-validation workflows."""

import logging
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

LOGGER = logging.getLogger(__name__)


def plot_overlays(result: Any, output_directory: Path, *, maximum: int) -> int:
    if maximum <= 0 or result.decoded is None or not result.metrics:
        return 0
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        LOGGER.warning("matplotlib unavailable; overlays skipped")
        return 0
    completed_pairs = sorted({
        (estimate, comparator)
        for estimate, comparator, metric in result.metrics
        if metric.status == "comparison_completed"
    })
    if not completed_pairs:
        return 0
    estimate_by_index = {frame.message_index: frame for frame in result.decoded.estimated_frames}
    preferred_positions: list[int] = [0, len(completed_pairs) - 1]
    represented_intervals: set[int] = set()
    for position, (estimate_index, _) in enumerate(completed_pairs):
        interval_count = estimate_by_index[estimate_index].interval_count
        if interval_count is not None and interval_count not in represented_intervals:
            preferred_positions.append(position)
            represented_intervals.add(interval_count)
    ready_indices = [
        frame.message_index for frame in result.decoded.estimated_frames
        if frame.candidate_ready
    ]
    if ready_indices:
        run_edges = {ready_indices[0], ready_indices[-1]}
        for left, right in pairwise(ready_indices):
            if right != left + 1:
                run_edges.update((left, right))
        pair_position_by_estimate = {
            estimate_index: position
            for position, (estimate_index, _) in enumerate(completed_pairs)
        }
        preferred_positions.extend(
            pair_position_by_estimate[index]
            for index in sorted(run_edges)
            if index in pair_position_by_estimate
        )
    evenly_spaced = np.linspace(0, len(completed_pairs) - 1, min(maximum, len(completed_pairs))).astype(int)
    preferred_positions.extend(map(int, evenly_spaced))
    selected_positions: list[int] = []
    for position in preferred_positions:
        if position not in selected_positions:
            selected_positions.append(position)
        if len(selected_positions) >= maximum:
            break
    positions = np.asarray(sorted(selected_positions), dtype=int)
    comparator_by_index = {frame.message_index: frame for frame in result.decoded.comparator_frames}
    overlay_directory = output_directory / "validation_overlays" / result.recording_id
    overlay_directory.mkdir(parents=True, exist_ok=True)
    written = 0
    for output_index, position in enumerate(positions):
        estimate_index, comparator_index = completed_pairs[int(position)]
        comparator = comparator_by_index[comparator_index]
        if comparator.geometry is None:
            continue
        fig, axis = plt.subplots(figsize=(8, 5))
        axis.plot(
            comparator.geometry.x, comparator.geometry.y, color="black", linewidth=2.2,
            label="ego-lane comparator (not ground truth)",
        )
        for hypothesis, color in (
            ("curvature_rate__anchor_zero", "tab:blue"),
            ("curvature_delta__anchor_zero", "tab:orange"),
        ):
            curve = result.generated_curves.get((estimate_index, hypothesis))
            if curve is not None:
                axis.plot(curve.x, curve.y, color=color, label=hypothesis)
        axis.set_aspect("equal", adjustable="datalim")
        axis.set_xlabel("x [unverified shared frame]")
        axis.set_ylabel("y [unverified shared frame]")
        axis.set_title(
            f"{result.recording_id}, diagnostic pair {output_index:03d}\n"
            "No fitted alignment, scaling, reflection, or station shift"
        )
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(overlay_directory / f"pair_{output_index:03d}.png", dpi=160)
        plt.close(fig)
        written += 1
    return written
