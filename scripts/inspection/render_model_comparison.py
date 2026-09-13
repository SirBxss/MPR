#!/usr/bin/env python3
"""Render the reviewed MPR development-model comparison for reports.

The constants below reproduce the accepted same-cohort macro evidence recorded
by the v0.14--v0.15.4 workflow artifacts.  This script does not read private
data, refit a model, recompute a scientific statistic, or select a final model.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


@dataclass(frozen=True)
class ModelResult:
    """One reviewed macro model-comparison row."""

    label: str
    short_label: str
    color: str
    rmse_m: float
    frame_energy_m: float
    coverage_95: float
    sequence_energy_m: float
    lag_one_error: float
    lag_one_approximate: bool = False


RESULTS = (
    ModelResult(
        label="Unconditional Gaussian",
        short_label="Unconditional\nGaussian",
        color="#0072B2",
        rmse_m=0.359350,
        frame_energy_m=0.984050,
        coverage_95=0.937690,
        sequence_energy_m=0.297740,
        lag_one_error=0.958,
        lag_one_approximate=True,
    ),
    ModelResult(
        label="Six-feature conditional Gaussian",
        short_label="Conditional\nGaussian",
        color="#56B4E9",
        rmse_m=0.362535,
        frame_energy_m=0.994829,
        coverage_95=0.928183,
        sequence_energy_m=0.286028,
        lag_one_error=0.888345,
    ),
    ModelResult(
        label="One-state conditional AR (0.98)",
        short_label="One-state AR\ncap 0.98",
        color="#009E73",
        rmse_m=0.364830,
        frame_energy_m=1.007659,
        coverage_95=0.907818,
        sequence_energy_m=0.276110,
        lag_one_error=0.008472,
    ),
    ModelResult(
        label="Two-state AIOHMM (v0.15.0)",
        short_label="Two-state\nAIOHMM",
        color="#D55E00",
        rmse_m=0.374542,
        frame_energy_m=1.018113,
        coverage_95=0.868940,
        sequence_energy_m=0.286286,
        lag_one_error=0.018276,
    ),
    ModelResult(
        label="Frozen one-state AR (0.99)",
        short_label="Frozen AR\ncap 0.99",
        color="#E69F00",
        rmse_m=0.365110,
        frame_energy_m=1.009150,
        coverage_95=0.917083,
        sequence_energy_m=0.276216,
        lag_one_error=0.007590,
    ),
)


METRICS = (
    ("rmse_m", "Sample-mean RMSE", "m", False, 6),
    ("frame_energy_m", "Frame energy score", "m", False, 6),
    ("coverage_error", "Absolute 95% coverage error", "percentage points", False, 3),
    ("sequence_energy_m", "Normalized sequence energy", "m", False, 6),
    ("lag_one_error", "Lag-one correlation error", "dimensionless · log scale", True, 6),
)


def _metric_values(metric: str) -> list[float]:
    if metric == "coverage_error":
        return [abs(result.coverage_95 - 0.95) * 100.0 for result in RESULTS]
    return [float(getattr(result, metric)) for result in RESULTS]


def _format_value(metric: str, value: float, precision: int) -> str:
    if metric == "coverage_error":
        return f"{value:.3f} pp"
    if metric == "lag_one_error" and value == RESULTS[0].lag_one_error:
        return f"≈{value:.3f}"
    return f"{value:.{precision}f}"


def _draw_metric_panel(
    axis: plt.Axes,
    metric: str,
    title: str,
    unit: str,
    log_scale: bool,
    precision: int,
) -> None:
    values = _metric_values(metric)
    positions = list(range(len(RESULTS)))
    colors = [result.color for result in RESULTS]
    best_index = min(range(len(values)), key=values.__getitem__)

    if log_scale:
        axis.set_xscale("log")
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))

    axis.scatter(values, positions, s=82, color=colors, edgecolor="white", linewidth=0.8, zorder=3)
    axis.grid(axis="x", color="#D9E1E8", linewidth=0.8, zorder=0)
    axis.set_title(title, loc="left", fontsize=11, fontweight="bold", pad=12)
    axis.text(0.0, 1.005, unit, transform=axis.transAxes, fontsize=8.5, color="#5B6573")
    axis.set_yticks(positions)
    axis.set_yticklabels([])
    axis.invert_yaxis()
    axis.tick_params(axis="both", labelsize=8.5, colors="#334155")

    minimum = min(values)
    maximum = max(values)
    if not log_scale:
        span = maximum - minimum
        padding = span * 0.24 if span else max(abs(minimum) * 0.1, 0.1)
        axis.set_xlim(max(0.0, minimum - padding), maximum + padding * 1.7)

    for index, value in enumerate(values):
        label = _format_value(metric, value, precision)
        suffix = "  BEST" if index == best_index else ""
        axis.annotate(
            label + suffix,
            (value, index),
            xytext=(7, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color="#111827",
            fontweight="bold" if index == best_index else "normal",
        )

    for spine in axis.spines.values():
        spine.set_visible(False)


def render(output: Path) -> None:
    """Render the fixed comparison figure to ``output``."""

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "mpr-v0171-model-comparison",
        }
    )
    figure = plt.figure(figsize=(16, 9), facecolor="#F8FAFC")
    grid = figure.add_gridspec(
        2,
        3,
        left=0.055,
        right=0.975,
        top=0.80,
        bottom=0.15,
        wspace=0.20,
        hspace=0.38,
    )

    axes = [figure.add_subplot(grid[row, column]) for row in range(2) for column in range(3)]
    for axis, metric in zip(axes[:5], METRICS):
        _draw_metric_panel(axis, *metric)

    decision_axis = axes[5]
    decision_axis.set_facecolor("#EEF4F8")
    decision_axis.set_xticks([])
    decision_axis.set_yticks([])
    for spine in decision_axis.spines.values():
        spine.set_visible(False)
    decision_axis.text(
        0.06,
        0.89,
        "Scientific reading",
        transform=decision_axis.transAxes,
        fontsize=12,
        fontweight="bold",
        color="#0F172A",
    )
    decision_lines = (
        ("Marginal fidelity", "Unconditional Gaussian"),
        ("Temporal fidelity", "One-state AR"),
        ("Latent switching", "No added value shown"),
        ("Development sampler", "Frozen AR, cap 0.99"),
        ("Final model", "Not authorized"),
    )
    y_position = 0.72
    for heading, conclusion in decision_lines:
        decision_axis.text(
            0.06,
            y_position,
            heading,
            transform=decision_axis.transAxes,
            fontsize=8.5,
            color="#64748B",
            fontweight="bold",
        )
        decision_axis.text(
            0.06,
            y_position - 0.08,
            conclusion,
            transform=decision_axis.transAxes,
            fontsize=10.5,
            color="#0F172A",
        )
        y_position -= 0.16

    figure.suptitle(
        "MPR development-model comparison — no universal winner",
        x=0.055,
        y=0.955,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color="#0F172A",
    )
    figure.text(
        0.055,
        0.905,
        "4,084 primary frames · 16 sequences · four technical groups from one physical outing · lower is better",
        fontsize=11.5,
        color="#475569",
    )

    legend_x = 0.055
    for result in RESULTS:
        figure.text(legend_x, 0.855, "●", color=result.color, fontsize=15, va="center")
        figure.text(legend_x + 0.014, 0.855, result.short_label.replace("\n", " "), fontsize=8.7, va="center", color="#1E293B")
        legend_x += 0.185

    figure.text(
        0.055,
        0.075,
        "Axes use metric-specific ranges to expose close values. The lag-one axis is logarithmic. "
        "The unconditional lag-one value is available only to three decimals.",
        fontsize=9,
        color="#475569",
    )
    figure.text(
        0.055,
        0.045,
        "Within-outing development evidence only · RLMB is a pseudo-reference · no independent-journey generalization or final selection",
        fontsize=9.5,
        color="#9A3412",
        fontweight="bold",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        format=output.suffix.lstrip(".") or "svg",
        facecolor=figure.get_facecolor(),
        metadata={"Date": None, "Creator": "MPR render_model_comparison.py"},
    )
    plt.close(figure)
    if output.suffix.lower() == ".svg":
        # Matplotlib terminates SVG path-command lines with spaces. Removing
        # them keeps the committed generated artifact clean under
        # ``git diff --check`` without changing its rendered content.
        svg = output.read_text(encoding="utf-8")
        output.write_text(
            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/figures/model_comparison_overview.svg"),
        help="output .svg or .png path",
    )
    args = parser.parse_args()
    if args.output.suffix.lower() not in {".svg", ".png"}:
        parser.error("--output must end in .svg or .png")
    render(args.output)
    print(f"Model comparison figure written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
