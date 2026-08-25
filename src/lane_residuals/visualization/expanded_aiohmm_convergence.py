"""Focused visualization for the v0.15.2 convergence audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def plot_expanded_aiohmm_convergence_audit(
    path: str | Path,
    *,
    convergence_rows: Sequence[Mapping[str, Any]],
    corrected_minus_reference: Mapping[str, float],
    corrected_minus_one_state: Mapping[str, float],
    corrected_vs_one_state_folds: Mapping[str, Any],
) -> Path:
    """Plot iteration changes and corrected sample-metric comparisons."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(row["fold_id"]).replace("hold_out_", "") for row in convergence_rows]
    reference_iterations = np.asarray(
        [float(row["reference_iteration_count"]) for row in convergence_rows]
    )
    corrected_iterations = np.asarray(
        [float(row["corrected_iteration_count"]) for row in convergence_rows]
    )

    metric_labels = ("RMSE", "Frame energy", "Sequence energy", "Coverage", "Lag-1")
    metric_keys = (
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "absolute_marginal_95_coverage_error",
        "median_absolute_lag_one_correlation_error",
    )
    reference_deltas = np.asarray(
        [float(corrected_minus_reference[key]) for key in metric_keys]
    )
    one_state_deltas = np.asarray(
        [float(corrected_minus_one_state[key]) for key in metric_keys]
    )
    sequence_diagnostics = corrected_vs_one_state_folds["metrics"][
        "mean_normalized_sequence_energy_score_m"
    ]
    sequence_delta_key = (
        "corrected_two_state_aiohmm_minus_one_state_ar_by_group"
    )
    sequence_deltas = sequence_diagnostics[sequence_delta_key]
    drive_labels = list(sequence_deltas)
    drive_values = np.asarray([float(sequence_deltas[key]) for key in drive_labels])

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    positions = np.arange(len(labels))
    width = 0.38
    axes[0].bar(
        positions - width / 2,
        reference_iterations,
        width,
        label="v0.15 relative-total",
        color="#8c8c8c",
    )
    axes[0].bar(
        positions + width / 2,
        corrected_iterations,
        width,
        label="v0.15.2 per-frame",
        color="#2b6cb0",
    )
    axes[0].set_xticks(positions, labels, rotation=30, ha="right")
    axes[0].set_ylabel("Selected EM iterations")
    axes[0].set_title("Stopping behavior")
    axes[0].legend(fontsize=8)

    metric_positions = np.arange(len(metric_labels))
    axes[1].bar(
        metric_positions - width / 2,
        reference_deltas,
        width,
        label="corrected − v0.15",
        color="#805ad5",
    )
    axes[1].bar(
        metric_positions + width / 2,
        one_state_deltas,
        width,
        label="corrected − one-state",
        color="#dd6b20",
    )
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_xticks(metric_positions, metric_labels, rotation=35, ha="right")
    axes[1].set_ylabel("Macro delta (negative is better)")
    axes[1].set_title("Effect on held-out sample metrics")
    axes[1].legend(fontsize=8)

    colors = np.where(drive_values < 0.0, "#2f855a", "#c53030")
    axes[2].bar(np.arange(len(drive_labels)), drive_values, color=colors)
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_xticks(
        np.arange(len(drive_labels)), drive_labels, rotation=30, ha="right"
    )
    axes[2].set_ylabel("Sequence-energy delta (m)")
    axes[2].set_title("Corrected two-state − one-state")

    figure.suptitle(
        "MPR v0.15.2 — size-invariant two-state EM convergence audit",
        fontsize=13,
    )
    figure.tight_layout()
    figure.savefig(target, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return target


__all__ = ["plot_expanded_aiohmm_convergence_audit"]
