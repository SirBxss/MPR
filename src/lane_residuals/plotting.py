"""Visual checks for the minimal residual-extraction pipeline."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from numpy.typing import ArrayLike
from typing import TYPE_CHECKING

from .gaussian import GaussianResidualModel
from .residuals import Path2D, residual_vector

if TYPE_CHECKING:
    from .preprocessing import ResidualDataset


def plot_path_pair_and_residual(
    ground_truth: Path2D,
    estimate: Path2D,
    stations: ArrayLike,
    *,
    reference_label: str = "Ground truth",
    estimate_label: str = "Estimate",
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot path geometry and its signed residual vector side by side."""

    stations_array = np.asarray(stations, dtype=np.float64)
    residual = residual_vector(ground_truth, estimate, stations_array)
    ground_truth_points = ground_truth.sample(stations_array)
    estimate_points = estimate.sample(stations_array)

    figure, (path_axis, residual_axis) = plt.subplots(1, 2, figsize=(11, 4.5))

    path_axis.plot(
        ground_truth.x,
        ground_truth.y,
        label=reference_label,
        linewidth=2,
    )
    path_axis.plot(
        estimate.x,
        estimate.y,
        label=estimate_label,
        linewidth=2,
    )
    for gt_point, estimate_point in zip(ground_truth_points, estimate_points):
        path_axis.plot(
            [gt_point[0], estimate_point[0]],
            [gt_point[1], estimate_point[1]],
            color="0.65",
            linewidth=0.8,
        )
    path_axis.set_title("Aligned path pair")
    path_axis.set_xlabel("x [m]")
    path_axis.set_ylabel("y [m]")
    path_axis.axis("equal")
    path_axis.grid(alpha=0.25)
    path_axis.legend()

    residual_axis.axhline(0.0, color="black", linewidth=0.8)
    residual_axis.plot(stations_array, residual, marker="o")
    residual_axis.set_title("Signed lateral residual")
    residual_axis.set_xlabel("Reference station s [m]")
    residual_axis.set_ylabel("Residual e(s) [m]")
    residual_axis.grid(alpha=0.25)

    figure.tight_layout()
    return figure, (path_axis, residual_axis)


def plot_gaussian_residual_model(
    model: GaussianResidualModel,
    stations: ArrayLike,
    *,
    observed_residuals: ArrayLike | None = None,
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot the Gaussian marginal band and its spatial correlation matrix."""

    stations_array = np.asarray(stations, dtype=np.float64)
    if stations_array.ndim != 1 or len(stations_array) != model.dimension:
        raise ValueError("stations must be one-dimensional with length H")
    if not np.all(np.isfinite(stations_array)):
        raise ValueError("stations must contain only finite values")

    figure, (mean_axis, correlation_axis) = plt.subplots(
        1,
        2,
        figsize=(11, 4.5),
    )

    if observed_residuals is not None:
        observations = np.asarray(observed_residuals, dtype=np.float64)
        if observations.ndim != 2 or observations.shape[1] != model.dimension:
            raise ValueError("observed_residuals must have shape (N, H)")
        if not np.all(np.isfinite(observations)):
            raise ValueError("observed_residuals must contain only finite values")
        mean_axis.plot(
            stations_array,
            observations[:20].T,
            color="0.65",
            alpha=0.25,
            linewidth=0.8,
        )

    marginal_standard_deviation = np.sqrt(np.diag(model.covariance))
    lower = model.mean - 1.96 * marginal_standard_deviation
    upper = model.mean + 1.96 * marginal_standard_deviation
    mean_axis.fill_between(
        stations_array,
        lower,
        upper,
        color="tab:blue",
        alpha=0.2,
        label="Marginal 95% Gaussian interval",
    )
    mean_axis.plot(
        stations_array,
        model.mean,
        color="tab:blue",
        linewidth=2,
        label="Learned mean",
    )
    mean_axis.axhline(0.0, color="black", linewidth=0.8)
    mean_axis.set_title("Unconditional residual distribution")
    mean_axis.set_xlabel("Reference station s [m]")
    mean_axis.set_ylabel("Residual e(s) [m]")
    mean_axis.grid(alpha=0.25)
    mean_axis.legend()

    correlation = model.covariance / np.outer(
        marginal_standard_deviation,
        marginal_standard_deviation,
    )
    correlation = np.clip(correlation, -1.0, 1.0)
    image = correlation_axis.imshow(
        correlation,
        vmin=-1.0,
        vmax=1.0,
        cmap="coolwarm",
        origin="lower",
        extent=(
            stations_array[0],
            stations_array[-1],
            stations_array[0],
            stations_array[-1],
        ),
        aspect="auto",
    )
    correlation_axis.set_title("Learned spatial correlation")
    correlation_axis.set_xlabel("Station s [m]")
    correlation_axis.set_ylabel("Station s [m]")
    figure.colorbar(image, ax=correlation_axis, label="Correlation")

    figure.tight_layout()
    return figure, (mean_axis, correlation_axis)


def plot_mcap_dataset_diagnostics(
    dataset: "ResidualDataset",
) -> tuple[Figure, np.ndarray]:
    """Plot cropped geometry, residual, timing, rejection, and horizon audits."""

    figure, axes = plt.subplots(2, 3, figsize=(15, 9))
    (
        path_axis,
        residual_axis,
        synchronization_axis,
        rejection_axis,
        horizon_axis,
        selection_axis,
    ) = axes.ravel()

    if dataset.examples:
        example = dataset.examples[0]
        dense_stations = np.linspace(
            float(dataset.stations[0]),
            float(dataset.stations[-1]),
            250,
        )
        reference_curve = example.reference.sample(dense_stations)
        estimate_curve = example.estimate.sample(dense_stations)
        path_axis.plot(
            reference_curve[:, 0],
            reference_curve[:, 1],
            linewidth=2,
            label="Map-based surrogate reference",
        )
        path_axis.plot(
            estimate_curve[:, 0],
            estimate_curve[:, 1],
            linewidth=2,
            label="Sensor-based estimate",
        )
        reference_points = example.reference.sample(dataset.stations)
        estimate_points = example.estimate.sample(dataset.stations)
        for reference_point, estimate_point in zip(
            reference_points,
            estimate_points,
        ):
            path_axis.plot(
                [reference_point[0], estimate_point[0]],
                [reference_point[1], estimate_point[1]],
                color="0.65",
                linewidth=0.7,
            )
        all_y = np.concatenate((reference_curve[:, 1], estimate_curve[:, 1]))
        y_range = float(np.max(all_y) - np.min(all_y))
        y_margin = max(0.5, 0.15 * y_range)
        path_axis.set_ylim(
            float(np.min(all_y)) - y_margin,
            float(np.max(all_y)) + y_margin,
        )
        path_axis.legend()
    else:
        path_axis.text(
            0.5,
            0.5,
            "No accepted path pair",
            ha="center",
            va="center",
            transform=path_axis.transAxes,
        )
    path_axis.set_title(
        f"Accepted path example ({dataset.stations[0]:g}–"
        f"{dataset.stations[-1]:g} m only)"
    )
    path_axis.set_xlabel("Local x [m]")
    path_axis.set_ylabel("Local y [m]")
    path_axis.grid(alpha=0.25)

    if len(dataset.residuals):
        residual_axis.plot(
            dataset.stations,
            dataset.residuals[:30].T,
            color="0.65",
            alpha=0.28,
            linewidth=0.8,
        )
        residual_axis.plot(
            dataset.stations,
            np.mean(dataset.residuals, axis=0),
            color="tab:blue",
            linewidth=2,
            label="Sample mean",
        )
        residual_axis.legend()
    else:
        residual_axis.text(
            0.5,
            0.5,
            "No accepted residual paths",
            ha="center",
            va="center",
            transform=residual_axis.transAxes,
        )
    residual_axis.axhline(0.0, color="black", linewidth=0.8)
    residual_axis.set_title(f"Accepted residual paths (N={len(dataset.residuals)})")
    residual_axis.set_xlabel("Reference station s [m]")
    residual_axis.set_ylabel("Discrepancy e(s) [m]")
    residual_axis.grid(alpha=0.25)

    log_deltas = np.asarray(
        [record.log_time_delta_ms for record in dataset.pair_audit_records],
        dtype=np.float64,
    )
    source_deltas = np.asarray(
        [
            record.source_time_delta_ms
            for record in dataset.pair_audit_records
            if record.source_time_delta_ms is not None
        ],
        dtype=np.float64,
    )
    if len(log_deltas):
        synchronization_axis.hist(
            log_deltas,
            bins=min(20, max(1, len(log_deltas))),
            alpha=0.55,
            label="MCAP log time",
        )
    if len(source_deltas):
        synchronization_axis.hist(
            source_deltas,
            bins=min(20, max(1, len(source_deltas))),
            alpha=0.55,
            label="Embedded source time",
        )
    synchronization_axis.axvline(0.0, color="black", linewidth=0.8)
    synchronization_axis.set_title(
        f"Pair timing (basis: {dataset.report.time_basis})"
    )
    synchronization_axis.set_xlabel("Estimate time − reference time [ms]")
    synchronization_axis.set_ylabel("Count")
    synchronization_axis.grid(alpha=0.25)
    if len(log_deltas) or len(source_deltas):
        synchronization_axis.legend()

    rejection_counts = dataset.report.rejection_dict
    if rejection_counts:
        labels = list(rejection_counts)
        counts = [rejection_counts[label] for label in labels]
        positions = np.arange(len(labels))
        rejection_axis.barh(positions, counts)
        rejection_axis.set_yticks(positions, labels=labels)
        rejection_axis.set_xlabel("Rejected pairs")
    else:
        rejection_axis.text(
            0.5,
            0.5,
            "No preprocessing rejections",
            ha="center",
            va="center",
            transform=rejection_axis.transAxes,
        )
        rejection_axis.set_xticks([])
        rejection_axis.set_yticks([])
    rejection_axis.set_title("Rejection audit")
    rejection_axis.grid(axis="x", alpha=0.25)

    horizon_counts = dataset.horizon_coverage_counts()
    horizon_labels = [f"{horizon:g}" for horizon in horizon_counts]
    horizon_values = list(horizon_counts.values())
    horizon_axis.bar(horizon_labels, horizon_values)
    horizon_axis.set_title("Geometric coverage by horizon")
    horizon_axis.set_xlabel("Forward horizon [m]")
    horizon_axis.set_ylabel("Synchronized pairs")
    horizon_axis.grid(axis="y", alpha=0.25)

    selection_counts: dict[str, int] = {}
    for role in ("reference", "estimate"):
        methods = [
            getattr(record, f"{role}_selection")
            for record in dataset.pair_audit_records
            if getattr(record, f"{role}_selection")
        ]
        for method in sorted(set(methods)):
            selection_counts[f"{role}: {method}"] = methods.count(method)
    if selection_counts:
        labels = list(selection_counts)
        values = [selection_counts[label] for label in labels]
        positions = np.arange(len(labels))
        selection_axis.barh(positions, values)
        selection_axis.set_yticks(positions, labels=labels)
        selection_axis.set_xlabel("Selected pairs")
    else:
        selection_axis.text(
            0.5,
            0.5,
            "No segment selections",
            ha="center",
            va="center",
            transform=selection_axis.transAxes,
        )
        selection_axis.set_xticks([])
        selection_axis.set_yticks([])
    selection_axis.set_title("Selection-method audit")
    selection_axis.grid(axis="x", alpha=0.25)

    figure.suptitle(
        "MCAP v0.3.2 audit — map-based data is not confirmed ground truth",
        fontsize=13,
    )
    figure.tight_layout()
    return figure, axes


def plot_lane_association_audit(
    dataset: "ResidualDataset",
) -> tuple[Figure, np.ndarray]:
    """Plot every candidate segment for retained synchronized-pair examples."""

    examples = dataset.association_examples
    if not examples:
        raise ValueError("dataset must retain at least one association example")

    n_columns = 2
    n_rows = int(np.ceil(len(examples) / n_columns))
    figure, axes = plt.subplots(
        n_rows,
        n_columns,
        figsize=(14, 4.5 * n_rows),
        squeeze=False,
    )
    flat_axes = axes.ravel()
    x_min = -5.0
    x_max = float(max(dataset.stations[-1], max(dataset.audit_horizons_m))) + 5.0

    for axis, example in zip(flat_axes, examples):
        plotted_y: list[float] = []
        for segments, color, prefix, selected_id, label_offset in (
            (
                example.reference_segments,
                "tab:blue",
                "M",
                example.selected_reference_segment_id,
                9,
            ),
            (
                example.estimate_segments,
                "tab:orange",
                "S",
                example.selected_estimate_segment_id,
                -11,
            ),
        ):
            for segment_index, segment in enumerate(segments):
                in_window = (segment.x >= x_min) & (segment.x <= x_max)
                if np.count_nonzero(in_window) < 2:
                    continue
                selected = segment.segment_id == selected_id
                x = segment.x[in_window]
                y = segment.y[in_window]
                plotted_y.extend(y.tolist())
                axis.plot(
                    x,
                    y,
                    color=color,
                    linewidth=3.0 if selected else 1.0,
                    alpha=1.0 if selected else 0.45,
                )
                label_index = min(
                    len(x) - 1,
                    int((0.32 + 0.18 * (segment_index % 3)) * len(x)),
                )
                axis.annotate(
                    f"{prefix}:{segment.segment_id}"
                    + (" *" if selected else ""),
                    xy=(x[label_index], y[label_index]),
                    xytext=(0, label_offset),
                    textcoords="offset points",
                    color=color,
                    fontsize=7,
                    ha="center",
                    bbox={
                        "facecolor": "white",
                        "edgecolor": "none",
                        "alpha": 0.65,
                        "pad": 1.0,
                    },
                )
        axis.scatter([0.0], [0.0], color="black", marker="x", label="Ego origin")
        status = "accepted" if example.accepted else example.rejection_reason
        source_delta = (
            "missing"
            if example.source_time_delta_ms is None
            else f"{example.source_time_delta_ms:+.2f} ms"
        )
        axis.set_title(
            f"Pair {example.pair_index}: {status}; source Δt={source_delta}"
        )
        axis.set_xlim(x_min, x_max)
        if plotted_y:
            y_min = min(plotted_y)
            y_max = max(plotted_y)
            margin = max(0.75, 0.1 * (y_max - y_min))
            axis.set_ylim(y_min - margin, y_max + margin)
        axis.set_xlabel("Local x [m]")
        axis.set_ylabel("Local y [m]")
        axis.grid(alpha=0.25)
        axis.legend(loc="upper right")

    for axis in flat_axes[len(examples) :]:
        axis.set_visible(False)

    figure.suptitle(
        "Lane-association audit: all candidates labelled; * marks selection",
        fontsize=13,
    )
    figure.tight_layout()
    return figure, axes
