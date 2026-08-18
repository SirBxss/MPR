"""Comparison plots for conditional and same-cohort Gaussian baselines."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike


_CONDITIONAL = "conditional_linear_gaussian"
_UNCONDITIONAL = "unconditional_gaussian_same_cohort"
_MODEL_LABELS = {
    _CONDITIONAL: "Conditional linear mean",
    _UNCONDITIONAL: "Unconditional (same cohort)",
}


def _finite_vector(values: ArrayLike, *, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or len(vector) == 0 or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be a nonempty finite vector")
    return vector


def _overall_station_values(
    station_rows: Sequence[Mapping[str, Any]],
    *,
    model_type: str,
    metric: str,
    stations: np.ndarray,
) -> np.ndarray:
    matches = {
        float(row["station_m"]): float(row[metric])
        for row in station_rows
        if row["model_type"] == model_type
        and row["scope"] == "overall_cross_validated"
    }
    if set(matches) != set(stations.tolist()):
        raise ValueError(f"incomplete overall station rows for {model_type}")
    values = np.asarray([matches[float(station)] for station in stations])
    if not np.all(np.isfinite(values)):
        raise ValueError(f"non-finite {metric} values")
    return values


def _held_out_metric(
    evaluation_rows: Sequence[Mapping[str, Any]],
    *,
    model_type: str,
    drive_id: str,
    metric: str,
) -> float:
    matches = [
        float(row[metric])
        for row in evaluation_rows
        if row["model_type"] == model_type
        and row["scope"] == "held_out_drive"
        and row["held_out_drive_id"] == drive_id
    ]
    if len(matches) != 1 or not math.isfinite(matches[0]):
        raise ValueError(f"missing held-out metric for {model_type}/{drive_id}")
    return matches[0]


def plot_conditional_gaussian_comparison(
    path: Path,
    *,
    stations_m: ArrayLike,
    evaluation_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    standardized_coefficients_m: ArrayLike,
) -> None:
    """Plot held-out errors and final standardized conditional coefficients."""

    stations = _finite_vector(stations_m, name="stations_m")
    features = tuple(str(name) for name in feature_names)
    if not features or any(not name for name in features):
        raise ValueError("feature_names must be nonempty")
    coefficients = np.asarray(standardized_coefficients_m, dtype=np.float64)
    if coefficients.shape != (len(features), len(stations)):
        raise ValueError("standardized coefficients have the wrong shape")
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("standardized coefficients must be finite")

    drive_ids = sorted(
        {
            str(row["held_out_drive_id"])
            for row in evaluation_rows
            if row["scope"] == "held_out_drive"
        }
    )
    if len(drive_ids) < 2:
        raise ValueError("at least two held-out drives are required")

    figure, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    rmse_axis, coverage_axis = axes[0]
    nll_axis, coefficient_axis = axes[1]

    for model_type, color in (
        (_UNCONDITIONAL, "tab:gray"),
        (_CONDITIONAL, "tab:blue"),
    ):
        rmse_axis.plot(
            stations,
            _overall_station_values(
                station_rows,
                model_type=model_type,
                metric="mean_prediction_rmse_m",
                stations=stations,
            ),
            marker="o",
            markersize=3,
            color=color,
            label=_MODEL_LABELS[model_type],
        )
        coverage_axis.plot(
            stations,
            _overall_station_values(
                station_rows,
                model_type=model_type,
                metric="marginal_95_coverage",
                stations=stations,
            ),
            marker="o",
            markersize=3,
            color=color,
            label=_MODEL_LABELS[model_type],
        )
    rmse_axis.set_title("Cross-validated conditional-mean error")
    rmse_axis.set_xlabel("Station (m)")
    rmse_axis.set_ylabel("RMSE (m)")
    rmse_axis.grid(alpha=0.25)
    rmse_axis.legend(fontsize=8)
    coverage_axis.axhline(0.95, color="black", linestyle="--", label="nominal 95%")
    coverage_axis.set_ylim(0.0, 1.02)
    coverage_axis.set_title("Cross-validated marginal coverage")
    coverage_axis.set_xlabel("Station (m)")
    coverage_axis.set_ylabel("Coverage")
    coverage_axis.grid(alpha=0.25)
    coverage_axis.legend(fontsize=8)

    positions = np.arange(len(drive_ids), dtype=np.float64)
    width = 0.36
    for offset, model_type, color in (
        (-width / 2.0, _UNCONDITIONAL, "tab:gray"),
        (width / 2.0, _CONDITIONAL, "tab:blue"),
    ):
        nll_axis.bar(
            positions + offset,
            [
                _held_out_metric(
                    evaluation_rows,
                    model_type=model_type,
                    drive_id=drive_id,
                    metric="mean_joint_negative_log_likelihood",
                )
                for drive_id in drive_ids
            ],
            width=width,
            color=color,
            label=_MODEL_LABELS[model_type],
        )
    nll_axis.set_xticks(positions, drive_ids)
    nll_axis.set_title("Mean joint NLL by held-out drive")
    nll_axis.set_ylabel("Negative log-likelihood")
    nll_axis.grid(axis="y", alpha=0.25)
    nll_axis.legend(fontsize=8)

    limit = float(np.max(np.abs(coefficients)))
    if limit == 0.0:
        limit = 1.0
    image = coefficient_axis.imshow(
        coefficients,
        aspect="auto",
        cmap="coolwarm",
        vmin=-limit,
        vmax=limit,
        extent=(stations[0] - 2.5, stations[-1] + 2.5, len(features) - 0.5, -0.5),
    )
    coefficient_axis.set_yticks(np.arange(len(features)), features)
    coefficient_axis.set_xticks(stations[::2])
    coefficient_axis.set_title("Final-model effect per +1 training SD")
    coefficient_axis.set_xlabel("Station (m)")
    figure.colorbar(image, ax=coefficient_axis, label="Mean residual change (m)")

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


__all__ = ["plot_conditional_gaussian_comparison"]
