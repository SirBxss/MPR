"""Plots for EstimatedDrivePaths transition diagnostics."""

from pathlib import Path
from typing import Sequence

from ..domain.edp_transitions import (
    EDP_SPLINE_HYPOTHESES,
    CandidateSnapshot,
    SelectedTransition,
)


def plot_transition_windows(
    path: Path, *, candidates: Sequence[CandidateSnapshot], centers: Sequence[int], radius: int
) -> None:
    if not centers:
        path.unlink(missing_ok=True)
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(len(centers), len(EDP_SPLINE_HYPOTHESES), figsize=(13.0, 4.5 * len(centers)), squeeze=False)
    color_map = plt.get_cmap("tab10")
    for row_index, center in enumerate(centers):
        for column_index, hypothesis in enumerate(EDP_SPLINE_HYPOTHESES):
            axis = axes[row_index, column_index]
            window_candidates = [item for item in candidates if abs(item.message_index - center) <= radius and item.geometry(hypothesis) is not None]
            for item in window_candidates:
                geometry = item.geometry(hypothesis)
                assert geometry is not None
                relative = abs(item.message_index - center)
                alpha = 1.0 - 0.65 * relative / max(radius + 1, 1)
                label = None
                if item.message_index == center:
                    label = f"E{item.message_index} p{item.path_index} {item.role_symbol}"
                axis.plot(
                    geometry.x_m, geometry.y_m,
                    color=color_map(item.path_index % 10),
                    linewidth=(2.0 if item.selected_for_pairing_audit else 0.9),
                    linestyle=("-" if item.selected_unique_keep_lane else "--"),
                    alpha=alpha, label=label,
                )
                axis.scatter(geometry.x_m[0], geometry.y_m[0], color=color_map(item.path_index % 10), s=8, alpha=alpha)
            axis.scatter(0.0, 0.0, marker="+", color="black", s=35)
            axis.set_title(f"center E{center}, messages ±{radius}; {hypothesis}", fontsize=10)
            axis.set_xlabel("provisional spline x [m]")
            axis.set_ylabel("provisional spline y [m]")
            axis.grid(True, alpha=0.25)
            axis.set_aspect("equal", adjustable="datalim")
            handles, labels = axis.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                axis.legend(by_label.values(), by_label.keys(), fontsize=7, loc="best")
    figure.suptitle("EDP candidate transition windows: all candidates; solid = unique KEEP_LANE", fontsize=12)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.985))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


def plot_transition_metrics(
    path: Path, *, transitions: Sequence[SelectedTransition], centers: Sequence[int]
) -> None:
    if not transitions:
        path.unlink(missing_ok=True)
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = (
        ("sampled_position_rms_m", "same-station raw RMS [m]"),
        ("shift_aware_shape_rms_m", "rollover shift-aware shape RMS [m]"),
        ("station_shift_m", "detected native-station shift [m]"),
    )
    figure, axes = plt.subplots(3, 1, figsize=(12.0, 9.0), sharex=True)
    for axis, (attribute, label) in zip(axes, metrics):
        for hypothesis, color in (("curvature_rate", "tab:blue"), ("curvature_delta", "tab:orange")):
            items = [item for item in transitions if item.hypothesis == hypothesis]
            axis.plot(
                [item.current_message_index for item in items],
                [getattr(item, attribute) for item in items],
                label=hypothesis, color=color, linewidth=1.0, marker="o", markersize=2.5,
            )
        for center in centers:
            axis.axvline(center, color="black", linestyle=":", alpha=0.4)
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.25)
    axes[-1].set_xlabel("current EDP message index")
    axes[0].legend(loc="upper right")
    figure.suptitle("Selected KEEP_LANE continuity (rollover-aware; diagnostic only)", fontsize=12)
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.98))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)
