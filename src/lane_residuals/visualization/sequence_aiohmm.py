"""Diagnostics for the MPR v0.11.0 AIOHMM sequence model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np


def plot_sequence_aiohmm_diagnostics(
    path: Path,
    *,
    stations_m: Sequence[float],
    evaluation_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
    state_rows: Sequence[Mapping[str, Any]],
    final_transition_matrix: np.ndarray,
    final_autoregressive_coefficients: np.ndarray,
) -> None:
    """Plot spatial accuracy, calibration, temporal fit, and state diagnostics."""

    stations = np.asarray(stations_m, dtype=np.float64)
    overall = [
        row for row in station_rows if row["scope"] == "overall_cross_validated"
    ]
    if len(overall) != len(stations):
        raise ValueError("overall AIOHMM station diagnostics do not cover H100")
    overall.sort(key=lambda row: float(row["station_m"]))
    if not np.allclose(
        [float(row["station_m"]) for row in overall], stations
    ):
        raise ValueError("AIOHMM station diagnostic grid differs from H100")
    held_out = [
        row for row in evaluation_rows if row["scope"] == "held_out_drive"
    ]
    if len(held_out) < 2:
        raise ValueError("at least two held-out drive rows are required")
    held_out.sort(key=lambda row: str(row["held_out_drive_id"]))
    held_out_states = [
        row
        for row in state_rows
        if row["scope"] == "held_out_drive_test_posterior"
    ]
    state_count = final_autoregressive_coefficients.shape[0]
    if final_transition_matrix.shape != (state_count, state_count):
        raise ValueError("final transition matrix has the wrong shape")
    if final_autoregressive_coefficients.shape != (state_count, len(stations)):
        raise ValueError("final AR coefficient grid has the wrong shape")

    figure, axes = plt.subplots(2, 3, figsize=(18, 10), constrained_layout=True)
    rmse_axis, coverage_axis, lag_axis = axes[0]
    fold_axis, occupancy_axis, transition_axis = axes[1]

    rmse_axis.plot(
        stations,
        [float(row["sample_mean_prediction_rmse_m"]) for row in overall],
        marker="o",
        markersize=4,
    )
    rmse_axis.set_title("Cross-validated sample-mean error")
    rmse_axis.set_xlabel("Station (m)")
    rmse_axis.set_ylabel("RMSE (m)")
    rmse_axis.grid(alpha=0.25)

    coverage_axis.plot(
        stations,
        [float(row["marginal_95_coverage"]) for row in overall],
        marker="o",
        markersize=4,
    )
    coverage_axis.axhline(0.95, color="black", linestyle="--", label="nominal 95%")
    coverage_axis.set_ylim(0.0, 1.02)
    coverage_axis.set_title("Sample-based marginal calibration")
    coverage_axis.set_xlabel("Station (m)")
    coverage_axis.set_ylabel("Coverage")
    coverage_axis.grid(alpha=0.25)
    coverage_axis.legend(fontsize=8)

    lag_axis.plot(
        stations,
        [float(row["observed_lag_one_correlation"]) for row in overall],
        marker="o",
        markersize=4,
        label="Observed",
    )
    lag_axis.plot(
        stations,
        [float(row["generated_median_lag_one_correlation"]) for row in overall],
        marker="o",
        markersize=4,
        label="Generated AIOHMM",
    )
    lag_axis.set_ylim(-1.0, 1.0)
    lag_axis.set_title("Observed versus generated lag-one dependence")
    lag_axis.set_xlabel("Station (m)")
    lag_axis.set_ylabel("Pearson correlation")
    lag_axis.grid(alpha=0.25)
    lag_axis.legend(fontsize=8)

    positions = np.arange(len(held_out), dtype=np.float64)
    width = 0.35
    fold_axis.bar(
        positions - width / 2.0,
        [float(row["sample_mean_prediction_rmse_m"]) for row in held_out],
        width=width,
        label="Sample-mean RMSE",
    )
    fold_axis.bar(
        positions + width / 2.0,
        [float(row["mean_energy_score_m"]) for row in held_out],
        width=width,
        label="Energy score",
    )
    fold_axis.set_xticks(positions)
    fold_axis.set_xticklabels(
        [str(row["held_out_drive_id"]) for row in held_out],
        rotation=20,
        ha="right",
    )
    fold_axis.set_title("Physical-drive-held-out sample metrics")
    fold_axis.set_ylabel("Metres")
    fold_axis.grid(axis="y", alpha=0.25)
    fold_axis.legend(fontsize=8)

    drive_ids = sorted({str(row["held_out_drive_id"]) for row in held_out_states})
    occupancy_width = 0.8 / state_count
    for state_index in range(state_count):
        state_values = []
        for drive_id in drive_ids:
            matches = [
                row
                for row in held_out_states
                if str(row["held_out_drive_id"]) == drive_id
                and int(row["state_index"]) == state_index
            ]
            if len(matches) != 1:
                raise ValueError("state occupancy rows are incomplete")
            state_values.append(float(matches[0]["posterior_state_occupancy"]))
        occupancy_axis.bar(
            np.arange(len(drive_ids))
            - 0.4
            + occupancy_width / 2.0
            + state_index * occupancy_width,
            state_values,
            width=occupancy_width,
            label=f"State {state_index}",
        )
    occupancy_axis.set_xticks(np.arange(len(drive_ids)))
    occupancy_axis.set_xticklabels(drive_ids, rotation=20, ha="right")
    occupancy_axis.set_ylim(0.0, 1.0)
    occupancy_axis.set_title("Held-out posterior state occupancy")
    occupancy_axis.set_ylabel("Fraction of frames")
    occupancy_axis.grid(axis="y", alpha=0.25)
    occupancy_axis.legend(fontsize=8)

    image = transition_axis.imshow(
        final_transition_matrix,
        vmin=0.0,
        vmax=1.0,
        cmap="viridis",
        aspect="equal",
    )
    for source_state in range(state_count):
        for destination_state in range(state_count):
            value = final_transition_matrix[source_state, destination_state]
            color = "white" if value < 0.45 else "black"
            transition_axis.text(
                destination_state,
                source_state,
                f"{value:.2f}",
                ha="center",
                va="center",
                color=color,
                fontsize=9,
            )
    transition_axis.set_xticks(np.arange(state_count))
    transition_axis.set_yticks(np.arange(state_count))
    transition_axis.set_xlabel("Destination state")
    transition_axis.set_ylabel("Source state")
    transition_axis.set_title("All-data descriptive mean transition matrix")
    figure.colorbar(image, ax=transition_axis, fraction=0.046, pad=0.04)

    figure.suptitle(
        "MPR v0.11.0 autoregressive input-output HMM\n"
        "Three-state development model; state labels are not physical classes",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


__all__ = ["plot_sequence_aiohmm_diagnostics"]
