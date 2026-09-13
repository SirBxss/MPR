#!/usr/bin/env python3
"""Plot the reviewed model comparison directly from v0.15.3 outputs.

The v0.15.3 comparison is the lineage-validated consolidation of the v0.14
Gaussian baselines, corrected v0.15.2 two-state AIOHMM, v0.15.1 one-state AR,
and v0.15.3 AR-boundary candidates. This script reads its macro and fold CSVs;
it contains model identities and presentation metadata, but no metric values.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter


MACRO_FILENAME = "ar_boundary_model_comparison.csv"
FOLD_FILENAME = "ar_boundary_fold_comparison.csv"

MACRO_FIELDS = (
    "model_id",
    "model_family",
    "artifact_version",
    "state_count",
    "maximum_absolute_autoregression",
    "is_frozen_reference",
    "mean_joint_negative_log_likelihood_physical",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_absolute_lag_one_correlation_error",
)

FOLD_FIELDS = (
    "model_id",
    "maximum_absolute_autoregression",
    "held_out_drive_id",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_absolute_lag_one_correlation_error",
)


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    label: str
    artifact_version: str
    color: str


@dataclass(frozen=True)
class MetricSpec:
    key: str
    title: str
    detail: str
    precision: int
    fold_values_available: bool
    logarithmic: bool = False


# Model identities and labels are fixed by the reviewed v0.15.3 contract.
# Metric values are deliberately absent and must come from the input CSVs.
MODELS = (
    ModelSpec(
        "unconditional_gaussian",
        "Unconditional Gaussian",
        "0.14.0",
        "#0072B2",
    ),
    ModelSpec(
        "conditional_gaussian",
        "Conditional Gaussian",
        "0.14.0",
        "#56B4E9",
    ),
    ModelSpec(
        "one_state_ar_cap_0_980",
        "One-state AR, cap 0.98",
        "0.15.1",
        "#009E73",
    ),
    ModelSpec(
        "corrected_two_state_aiohmm",
        "Corrected two-state AIOHMM",
        "0.15.2",
        "#D55E00",
    ),
    ModelSpec(
        "one_state_ar_cap_0_990",
        "Frozen AR, cap 0.99",
        "0.15.3",
        "#E69F00",
    ),
)

ALL_MODEL_IDS = frozenset(
    {
        *(model.model_id for model in MODELS),
        "one_state_ar_cap_0_995",
        "one_state_ar_cap_0_999",
    }
)

METRICS = (
    MetricSpec(
        "mean_joint_negative_log_likelihood_physical",
        "Mean observed-history NLL",
        "physical density · macro only",
        3,
        False,
    ),
    MetricSpec(
        "sample_mean_prediction_rmse_m",
        "Sample-mean RMSE",
        "metres",
        6,
        True,
    ),
    MetricSpec(
        "mean_normalized_sequence_energy_score_m",
        "Normalized sequence energy score",
        "metres · free-running",
        6,
        True,
    ),
    MetricSpec(
        "median_absolute_lag_one_correlation_error",
        "Median absolute lag-one error",
        "dimensionless · free-running · log scale",
        6,
        True,
        logarithmic=True,
    ),
)

FOLD_METRIC_KEYS = tuple(
    field
    for field in FOLD_FIELDS
    if field
    not in {
        "model_id",
        "maximum_absolute_autoregression",
        "held_out_drive_id",
    }
)


class ComparisonInputError(ValueError):
    """Raised when the v0.15.3 reporting inputs violate their contract."""


def _read_exact_csv(path: Path, expected_fields: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ComparisonInputError(f"required comparison file is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(expected_fields):
            raise ComparisonInputError(
                f"unexpected CSV schema for {path.name}: {reader.fieldnames}"
            )
        rows = list(reader)
    if not rows:
        raise ComparisonInputError(f"comparison CSV is empty: {path}")
    if any(None in row for row in rows):
        raise ComparisonInputError(f"malformed CSV row in {path}")
    return rows


def _finite_float(row: Mapping[str, str], field: str, context: str) -> float:
    raw = row.get(field, "")
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ComparisonInputError(
            f"{context} has invalid {field}: {raw!r}"
        ) from error
    if not math.isfinite(value):
        raise ComparisonInputError(f"{context} has non-finite {field}")
    return value


def load_comparison(
    directory: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    """Load and reconcile the exact v0.15.3 macro/fold comparison pair."""

    if not directory.is_dir():
        raise ComparisonInputError(f"v0.15.3 output directory is missing: {directory}")
    macro_rows = _read_exact_csv(directory / MACRO_FILENAME, MACRO_FIELDS)
    fold_rows = _read_exact_csv(directory / FOLD_FILENAME, FOLD_FIELDS)

    macro_by_model: dict[str, dict[str, str]] = {}
    for row in macro_rows:
        model_id = row["model_id"]
        if not model_id or model_id in macro_by_model:
            raise ComparisonInputError("macro model identities are empty or duplicated")
        macro_by_model[model_id] = row
        for field in MACRO_FIELDS[6:]:
            _finite_float(row, field, f"macro model {model_id}")
    if set(macro_by_model) != ALL_MODEL_IDS:
        raise ComparisonInputError(
            "macro model set differs from the reviewed seven-model comparison"
        )

    for model in MODELS:
        if macro_by_model[model.model_id]["artifact_version"] != model.artifact_version:
            raise ComparisonInputError(
                f"unexpected artifact version for {model.model_id}"
            )

    fold_by_model: dict[str, dict[str, dict[str, str]]] = {
        model_id: {} for model_id in ALL_MODEL_IDS
    }
    for row in fold_rows:
        model_id = row["model_id"]
        drive_id = row["held_out_drive_id"]
        if model_id not in fold_by_model:
            raise ComparisonInputError(f"unexpected fold model: {model_id}")
        if not drive_id or drive_id in fold_by_model[model_id]:
            raise ComparisonInputError(
                f"fold identity is empty or duplicated for {model_id}"
            )
        for field in FOLD_METRIC_KEYS:
            value = _finite_float(row, field, f"fold {model_id}/{drive_id}")
            if field == "median_absolute_lag_one_correlation_error" and value <= 0.0:
                raise ComparisonInputError(
                    "lag-one errors must be positive for logarithmic plotting"
                )
        fold_by_model[model_id][drive_id] = row

    drive_sets = {frozenset(rows) for rows in fold_by_model.values()}
    if len(drive_sets) != 1:
        raise ComparisonInputError("models do not share identical held-out groups")
    drive_ids = next(iter(drive_sets))
    if len(drive_ids) != 4:
        raise ComparisonInputError("the reviewed comparison requires four held-out groups")
    if len(fold_rows) != len(ALL_MODEL_IDS) * len(drive_ids):
        raise ComparisonInputError("fold comparison row count is inconsistent")

    for model_id, rows in fold_by_model.items():
        for field in FOLD_METRIC_KEYS:
            fold_mean = fmean(
                _finite_float(row, field, f"fold {model_id}/{drive_id}")
                for drive_id, row in sorted(rows.items())
            )
            macro_value = _finite_float(
                macro_by_model[model_id], field, f"macro model {model_id}"
            )
            if not math.isclose(fold_mean, macro_value, rel_tol=0.0, abs_tol=1e-12):
                raise ComparisonInputError(
                    f"macro/fold reconciliation failed for {model_id}/{field}"
                )

    return macro_by_model, fold_by_model


def _format_value(metric: MetricSpec, value: float) -> str:
    return f"{value:.{metric.precision}f}"


def _set_metric_limits(axis: plt.Axes, values: Sequence[float], logarithmic: bool) -> None:
    minimum = min(values)
    maximum = max(values)
    if logarithmic:
        axis.set_xscale("log")
        axis.set_xlim(minimum / 1.7, maximum * 2.2)
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        return
    span = maximum - minimum
    padding = span * 0.18 if span else max(abs(minimum) * 0.05, 0.1)
    axis.set_xlim(minimum - padding, maximum + padding * 1.7)


def _draw_panel(
    axis: plt.Axes,
    metric: MetricSpec,
    macro_by_model: Mapping[str, Mapping[str, str]],
    fold_by_model: Mapping[str, Mapping[str, Mapping[str, str]]],
    *,
    show_model_labels: bool,
) -> None:
    positions = np.arange(len(MODELS), dtype=np.float64)
    plotted_values: list[float] = []
    if metric.fold_values_available:
        drive_ids = sorted(next(iter(fold_by_model.values())))
        offsets = np.linspace(-0.14, 0.14, len(drive_ids))
        for position, model in zip(positions, MODELS):
            for offset, drive_id in zip(offsets, drive_ids):
                value = _finite_float(
                    fold_by_model[model.model_id][drive_id],
                    metric.key,
                    f"plot fold {model.model_id}/{drive_id}",
                )
                plotted_values.append(value)
                axis.scatter(
                    value,
                    position + offset,
                    s=27,
                    color=model.color,
                    alpha=0.48,
                    edgecolor="none",
                    zorder=2,
                )

    macro_values = [
        _finite_float(macro_by_model[model.model_id], metric.key, model.model_id)
        for model in MODELS
    ]
    plotted_values.extend(macro_values)
    for position, model, value in zip(positions, MODELS, macro_values):
        axis.scatter(
            value,
            position,
            marker="D",
            s=66,
            color=model.color,
            edgecolor="#111827",
            linewidth=0.7,
            zorder=4,
        )
        axis.annotate(
            _format_value(metric, value),
            (value, position),
            xytext=(7, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color="#111827",
        )

    _set_metric_limits(axis, plotted_values, metric.logarithmic)
    axis.set_title(metric.title, loc="left", fontsize=11.5, fontweight="bold", pad=13)
    axis.text(
        0.0,
        1.01,
        metric.detail,
        transform=axis.transAxes,
        fontsize=8.5,
        color="#64748B",
    )
    axis.set_yticks(positions)
    axis.set_yticklabels(
        [model.label for model in MODELS] if show_model_labels else []
    )
    axis.invert_yaxis()
    axis.grid(axis="x", color="#D9E1E8", linewidth=0.8, zorder=0)
    axis.tick_params(axis="both", labelsize=8.5, colors="#334155")
    for spine in axis.spines.values():
        spine.set_visible(False)


def render_comparison(
    source_directory: Path,
    output: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    """Validate the accepted outputs and render the compact comparison."""

    macro_by_model, fold_by_model = load_comparison(source_directory)
    if output.exists():
        raise ComparisonInputError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "mpr-output-driven-model-comparison",
        }
    )
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(16, 9),
        facecolor="#F8FAFC",
        constrained_layout=False,
    )
    figure.subplots_adjust(
        left=0.18,
        right=0.97,
        top=0.79,
        bottom=0.14,
        wspace=0.22,
        hspace=0.38,
    )
    for index, (axis, metric) in enumerate(zip(axes.flat, METRICS)):
        _draw_panel(
            axis,
            metric,
            macro_by_model,
            fold_by_model,
            show_model_labels=index % 2 == 0,
        )

    figure.suptitle(
        "Model comparison: observed-history fit and free-running quality disagree",
        x=0.055,
        y=0.955,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color="#0F172A",
    )
    figure.text(
        0.055,
        0.905,
        "Diamonds: macro mean over four technical groups · circles: held-out-group values · lower is better",
        fontsize=11,
        color="#475569",
    )
    legend = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="none",
            markersize=8,
            markerfacecolor=model.color,
            markeredgecolor="none",
            label=model.label,
        )
        for model in MODELS
    ]
    figure.legend(
        handles=legend,
        loc="upper center",
        bbox_to_anchor=(0.52, 0.865),
        ncol=5,
        frameon=False,
        fontsize=8.8,
    )
    figure.text(
        0.055,
        0.075,
        "NLL uses observed residual history (teacher forcing); RMSE, sequence energy, and lag-one error come from free-running samples.",
        fontsize=9.2,
        color="#475569",
    )
    figure.text(
        0.055,
        0.045,
        "Within one outing only · group spread is descriptive, not journey-level uncertainty · no final model selection",
        fontsize=9.5,
        color="#9A3412",
        fontweight="bold",
    )
    figure.savefig(
        output,
        dpi=180,
        facecolor=figure.get_facecolor(),
        metadata={"Date": None, "Creator": "MPR render_model_comparison.py"},
    )
    plt.close(figure)
    if output.suffix.lower() == ".svg":
        svg = output.read_text(encoding="utf-8")
        output.write_text(
            "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
            encoding="utf-8",
        )
    return macro_by_model, fold_by_model


def _print_macro_reading(macro_by_model: Mapping[str, Mapping[str, str]]) -> None:
    print("Descriptive macro minima (not final model selections):")
    for metric in METRICS:
        model = min(
            MODELS,
            key=lambda candidate: _finite_float(
                macro_by_model[candidate.model_id], metric.key, candidate.model_id
            ),
        )
        value = _finite_float(macro_by_model[model.model_id], metric.key, model.model_id)
        print(f"  {metric.title}: {model.label} ({_format_value(metric, value)})")
    print("Final model selection authorized: false")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ar_boundary_directory",
        type=Path,
        help="complete accepted v0.15.3 AR-boundary output directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new .png or .svg figure path",
    )
    arguments = parser.parse_args(argv)
    if arguments.output.suffix.lower() not in {".png", ".svg"}:
        parser.error("--output must end in .png or .svg")
    try:
        macro_by_model, _ = render_comparison(
            arguments.ar_boundary_directory,
            arguments.output,
        )
    except (ComparisonInputError, OSError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(f"Model comparison figure written to: {arguments.output}")
    _print_macro_reading(macro_by_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
