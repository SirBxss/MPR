"""v0.15.3 one-state AR-ceiling sensitivity on the frozen model protocol."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.model_evaluation import build_leave_one_drive_out_folds
from ..io.expanded_modeling_dataset import load_expanded_modeling_dataset
from ..io.expanded_sequence_dataset import read_csv_rows
from ..io.model_evaluation import (
    load_expanded_aiohmm_baseline,
    load_expanded_gaussian_baseline,
    load_expanded_one_state_ar_baseline,
    load_expanded_two_state_convergence_baseline,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.aiohmm import (
    ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE,
    RELATIVE_TOTAL_LOG_PROBABILITY_CONVERGENCE,
    AIOHMMConfig,
)
from ..visualization.expanded_ar_boundary import (
    plot_expanded_ar_boundary_sensitivity,
)
from .expanded_aiohmm import (
    ExpandedAutoregressiveExperiment,
    _run_expanded_autoregressive,
    _same_schema_metric_deltas,
)
from .expanded_aiohmm_convergence import _paired_sample_metric_diagnostics
from .sequence_aiohmm import _configuration
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.15.3"
REFERENCE_AR_CEILING = 0.98
AR_CEILINGS = (0.98, 0.99, 0.995, 0.999)
FITTED_AR_CEILINGS = AR_CEILINGS[1:]
AR_BOUNDARY_TOLERANCE = 1e-10
RECORDED_POOLED_COVERAGE_HYPOTHESIS = 0.918

EXPERIMENT = ExpandedAutoregressiveExperiment(
    version=VERSION,
    output_prefix="one_state_ar",
    expected_state_count=1,
    purpose="one_state_ar_boundary_sensitivity_candidate",
    fold_models_purpose="v0153_clean_group_fold_one_state_ar_candidate_models",
    state_count_rationale="unchanged_reviewed_v0151_one_state_architecture",
    plot_subtitle="One-state AR candidate in the fixed v0.15.3 boundary audit",
    candidate_label="one_state_ar_boundary_candidate",
    comparison_key=(
        "one_state_ar_candidate_minus_conditional_gaussian_primary_macro_deltas"
    ),
    next_phase="consolidate_fixed_ar_ceiling_candidates_before_planner_evaluation",
    scientific_limitations=(
        (
            "The four clean technical groups are separated portions of one "
            "longer same-day outing, not four independent journeys."
        ),
        "Leave-one-group-out results do not estimate journey-level generalization.",
        (
            "The audit varies only a stationarity ceiling in the reviewed "
            "one-state architecture; it is not a new model family."
        ),
        (
            "A development-supported ceiling still requires confirmation on "
            "untouched independent outings."
        ),
        "Sample metrics retain finite Monte Carlo error under the recorded seed.",
    ),
)

MODEL_COMPARISON_FIELDS = (
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

FOLD_COMPARISON_FIELDS = (
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

STATION_COMPARISON_FIELDS = (
    "model_id",
    "maximum_absolute_autoregression",
    "station_m",
    "reference_cap_binding_station",
    "candidate_cap_binding_station",
    "sample_mean_prediction_rmse_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "observed_lag_one_correlation",
    "generated_median_lag_one_correlation",
    "absolute_lag_one_correlation_error",
    "median_model_autoregressive_coefficient",
)


def _ceiling_label(value: float) -> str:
    return f"{value:.3f}".replace(".", "_")


def _model_id(value: float) -> str:
    return f"one_state_ar_cap_{_ceiling_label(value)}"


def _normalized_configuration(payload: Mapping[str, Any]) -> dict[str, Any]:
    return AIOHMMConfig.from_dict(payload).to_dict()


def _validate_baseline_configuration(
    arguments: argparse.Namespace,
    one_state_summary: Mapping[str, Any],
) -> dict[str, Any]:
    payload = one_state_summary.get("configuration")
    if not isinstance(payload, Mapping):
        raise ValueError("v0.15.1 one-state configuration is missing")
    reference = _normalized_configuration(payload)
    requested = _configuration(arguments).to_dict()
    if reference.get("state_count") != 1 or requested.get("state_count") != 1:
        raise ValueError("v0.15.3 fixes the architecture at one state")
    if (
        float(reference.get("maximum_absolute_autoregression", -1.0))
        != REFERENCE_AR_CEILING
        or float(requested["maximum_absolute_autoregression"])
        != REFERENCE_AR_CEILING
    ):
        raise ValueError("v0.15.3 baseline AR ceiling must remain 0.98")
    differences = {
        name: {"v0151": reference.get(name), "requested": value}
        for name, value in requested.items()
        if reference.get(name) != value
    }
    if differences:
        raise ValueError(
            "v0.15.3 baseline configuration differs from v0.15.1: "
            f"{differences}"
        )
    if one_state_summary.get("restart_count_per_fit") != arguments.restart_count:
        raise ValueError("v0.15.3 restart count differs from v0.15.1")
    return reference


def _validate_reference_configuration_lineage(
    *,
    aiohmm_summary: Mapping[str, Any],
    one_state_summary: Mapping[str, Any],
    corrected_summary: Mapping[str, Any],
) -> None:
    payloads = {
        "v0150": aiohmm_summary.get("configuration"),
        "v0151": one_state_summary.get("configuration"),
        "v0152": corrected_summary.get("configuration"),
    }
    if not all(isinstance(payload, Mapping) for payload in payloads.values()):
        raise ValueError("autoregressive reference configuration is missing")
    reference = _normalized_configuration(payloads["v0150"])
    one_state = _normalized_configuration(payloads["v0151"])
    corrected = _normalized_configuration(payloads["v0152"])
    if (
        reference["state_count"] != 2
        or reference["input_dependent_transitions"] is not True
        or reference["convergence_criterion"]
        != RELATIVE_TOTAL_LOG_PROBABILITY_CONVERGENCE
        or float(reference["convergence_tolerance"]) != 1e-4
    ):
        raise ValueError("v0.15.0 reference configuration is not the reviewed one")
    one_state_permitted = {"state_count", "input_dependent_transitions"}
    one_state_drift = {
        name: {"v0150": value, "v0151": one_state.get(name)}
        for name, value in reference.items()
        if name not in one_state_permitted and one_state.get(name) != value
    }
    if (
        one_state_drift
        or one_state["state_count"] != 1
        or one_state["input_dependent_transitions"] is not False
    ):
        raise ValueError(
            "v0.15.1 configuration is not the reviewed one-state ablation: "
            f"{one_state_drift}"
        )
    corrected_permitted = {"convergence_criterion", "convergence_tolerance"}
    corrected_drift = {
        name: {"v0150": value, "v0152": corrected.get(name)}
        for name, value in reference.items()
        if name not in corrected_permitted and corrected.get(name) != value
    }
    if (
        corrected_drift
        or corrected["convergence_criterion"]
        != ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE
        or float(corrected["convergence_tolerance"]) != 1e-3
    ):
        raise ValueError(
            "v0.15.2 configuration is not the reviewed convergence correction: "
            f"{corrected_drift}"
        )


def _validated_references(
    arguments: argparse.Namespace,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, str],
    Mapping[str, Any],
    Mapping[str, str],
    Mapping[str, Any],
    Mapping[str, str],
    Mapping[str, Any],
    Mapping[str, str],
    dict[str, Any],
]:
    source = load_expanded_modeling_dataset(arguments.expanded_sequence_directory)
    folds = build_leave_one_drive_out_folds(
        source.sequences, primary_drive_ids=source.clean_drive_ids
    )
    gaussian_summary, gaussian_protocol, gaussian_hashes = (
        load_expanded_gaussian_baseline(
            arguments.gaussian_directory,
            source_files_sha256=source.source_files_sha256,
            folds=folds,
        )
    )
    monte_carlo = gaussian_protocol.get("monte_carlo")
    if not isinstance(monte_carlo, Mapping):
        raise ValueError("v0.14 Monte Carlo contract is missing")
    aiohmm_summary, aiohmm_hashes = load_expanded_aiohmm_baseline(
        arguments.aiohmm_directory,
        source_files_sha256=source.source_files_sha256,
        gaussian_files_sha256=gaussian_hashes,
        folds=folds,
        sample_count=arguments.sample_count,
        base_seed=arguments.seed,
    )
    one_state_summary, one_state_hashes = load_expanded_one_state_ar_baseline(
        arguments.one_state_ar_directory,
        source_files_sha256=source.source_files_sha256,
        gaussian_files_sha256=gaussian_hashes,
        aiohmm_files_sha256=aiohmm_hashes,
        folds=folds,
        sample_count=arguments.sample_count,
        base_seed=arguments.seed,
    )
    corrected_summary, corrected_hashes = (
        load_expanded_two_state_convergence_baseline(
            arguments.two_state_convergence_directory,
            source_files_sha256=source.source_files_sha256,
            gaussian_files_sha256=gaussian_hashes,
            aiohmm_files_sha256=aiohmm_hashes,
            one_state_ar_files_sha256=one_state_hashes,
            folds=folds,
            sample_count=arguments.sample_count,
            base_seed=arguments.seed,
        )
    )
    _validate_reference_configuration_lineage(
        aiohmm_summary=aiohmm_summary,
        one_state_summary=one_state_summary,
        corrected_summary=corrected_summary,
    )
    configuration = _validate_baseline_configuration(
        arguments, one_state_summary
    )
    return (
        gaussian_summary,
        gaussian_hashes,
        aiohmm_summary,
        aiohmm_hashes,
        one_state_summary,
        one_state_hashes,
        corrected_summary,
        corrected_hashes,
        configuration,
    )


def _candidate_arguments(
    arguments: argparse.Namespace,
    *,
    ceiling: float,
    output_directory: Path,
) -> argparse.Namespace:
    values = dict(vars(arguments))
    values["maximum_absolute_autoregression"] = ceiling
    values["output_directory"] = output_directory
    return argparse.Namespace(**values)


def _gaussian_macro(
    gaussian_summary: Mapping[str, Any], model_name: str
) -> dict[str, float]:
    models = gaussian_summary.get("models")
    if not isinstance(models, Mapping) or not isinstance(
        models.get(model_name), Mapping
    ):
        raise ValueError(f"v0.14 Gaussian model is missing: {model_name}")
    raw = models[model_name].get("primary_macro_drive_metrics")
    if not isinstance(raw, Mapping):
        raise ValueError(f"v0.14 Gaussian macro metrics are missing: {model_name}")
    return {
        "mean_joint_negative_log_likelihood_physical": float(
            raw["mean_frame_negative_log_likelihood_physical"]
        ),
        "sample_mean_prediction_rmse_m": float(
            raw["sample_mean_prediction_rmse_m"]
        ),
        "mean_energy_score_m": float(raw["mean_energy_score_m"]),
        "mean_normalized_sequence_energy_score_m": float(
            raw["mean_normalized_sequence_energy_score_m"]
        ),
        "marginal_95_coverage": float(raw["marginal_95_coverage"]),
        "absolute_marginal_95_coverage_error": float(
            raw["absolute_marginal_95_coverage_error"]
        ),
        "median_absolute_lag_one_correlation_error": float(
            raw["median_absolute_lag_one_correlation_error"]
        ),
    }


def _autoregressive_macro(summary: Mapping[str, Any]) -> dict[str, float]:
    raw = summary.get("primary_macro_drive_metrics")
    if not isinstance(raw, Mapping):
        raise ValueError("autoregressive primary macro metrics are missing")
    return {
        name: float(raw[name])
        for name in (
            "mean_joint_negative_log_likelihood_physical",
            "sample_mean_prediction_rmse_m",
            "mean_energy_score_m",
            "mean_normalized_sequence_energy_score_m",
            "marginal_95_coverage",
            "absolute_marginal_95_coverage_error",
            "median_absolute_lag_one_correlation_error",
        )
    }


def _comparison_row(
    *,
    model_id: str,
    model_family: str,
    version: str,
    state_count: int | None,
    ceiling: float | None,
    frozen: bool,
    macro: Mapping[str, float],
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "model_family": model_family,
        "artifact_version": version,
        "state_count": state_count,
        "maximum_absolute_autoregression": ceiling,
        "is_frozen_reference": frozen,
        **macro,
    }


def _gaussian_fold_rows(
    rows: Sequence[Mapping[str, Any]], *, model_name: str
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        if (
            row.get("scope") != "primary_held_out_drive"
            or row.get("model_name") != model_name
        ):
            continue
        drive_id = str(row.get("held_out_drive_id", ""))
        if not drive_id or drive_id in result:
            raise ValueError("v0.14 held-out Gaussian rows are ambiguous")
        result[drive_id] = {
            name: float(row[name])
            for name in (
                "sample_mean_prediction_rmse_m",
                "mean_energy_score_m",
                "mean_normalized_sequence_energy_score_m",
                "marginal_95_coverage",
                "absolute_marginal_95_coverage_error",
                "median_absolute_lag_one_correlation_error",
            )
        }
    if not result:
        raise ValueError("v0.14 held-out Gaussian rows are missing")
    return result


def _autoregressive_fold_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        if row.get("scope") != "held_out_drive":
            continue
        drive_id = str(row.get("held_out_drive_id", ""))
        if not drive_id or drive_id in result:
            raise ValueError("held-out autoregressive rows are ambiguous")
        result[drive_id] = {
            name: float(row[name])
            for name in (
                "sample_mean_prediction_rmse_m",
                "mean_energy_score_m",
                "mean_normalized_sequence_energy_score_m",
                "marginal_95_coverage",
                "absolute_marginal_95_coverage_error",
                "median_absolute_lag_one_correlation_error",
            )
        }
    if not result:
        raise ValueError("held-out autoregressive rows are missing")
    return result


def _append_fold_comparison_rows(
    target: list[dict[str, Any]],
    *,
    model_id: str,
    ceiling: float | None,
    rows: Mapping[str, Mapping[str, float]],
) -> None:
    for drive_id in sorted(rows):
        target.append(
            {
                "model_id": model_id,
                "maximum_absolute_autoregression": ceiling,
                "held_out_drive_id": drive_id,
                **rows[drive_id],
            }
        )


def _overall_station_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[float, Mapping[str, Any]]:
    result: dict[float, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("scope") != "overall_cross_validated":
            continue
        station = float(row["station_m"])
        if station in result:
            raise ValueError("overall station rows are ambiguous")
        result[station] = row
    if not result:
        raise ValueError("overall station rows are missing")
    return result


def _boundary_station_fold_count(
    rows: Sequence[Mapping[str, Any]], *, ceiling: float
) -> int:
    return sum(
        row.get("scope") == "held_out_drive"
        and abs(float(row["median_model_autoregressive_coefficient"]))
        >= ceiling - AR_BOUNDARY_TOLERANCE
        for row in rows
    )


def _station_comparison_rows(
    *,
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows_by_ceiling: Mapping[float, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    baseline = _overall_station_rows(baseline_rows)
    result: list[dict[str, Any]] = []
    all_rows = {REFERENCE_AR_CEILING: baseline_rows, **candidate_rows_by_ceiling}
    for ceiling in AR_CEILINGS:
        current = _overall_station_rows(all_rows[ceiling])
        if set(current) != set(baseline):
            raise ValueError("AR-boundary station grids differ")
        for station in sorted(current):
            row = current[station]
            reference_coefficient = float(
                baseline[station]["median_model_autoregressive_coefficient"]
            )
            coefficient = float(row["median_model_autoregressive_coefficient"])
            coverage = float(row["marginal_95_coverage"])
            result.append(
                {
                    "model_id": _model_id(ceiling),
                    "maximum_absolute_autoregression": ceiling,
                    "station_m": station,
                    "reference_cap_binding_station": (
                        abs(reference_coefficient)
                        >= REFERENCE_AR_CEILING - AR_BOUNDARY_TOLERANCE
                    ),
                    "candidate_cap_binding_station": (
                        abs(coefficient) >= ceiling - AR_BOUNDARY_TOLERANCE
                    ),
                    "sample_mean_prediction_rmse_m": float(
                        row["sample_mean_prediction_rmse_m"]
                    ),
                    "marginal_95_coverage": coverage,
                    "absolute_marginal_95_coverage_error": abs(coverage - 0.95),
                    "observed_lag_one_correlation": float(
                        row["observed_lag_one_correlation"]
                    ),
                    "generated_median_lag_one_correlation": float(
                        row["generated_median_lag_one_correlation"]
                    ),
                    "absolute_lag_one_correlation_error": float(
                        row["absolute_lag_one_correlation_error"]
                    ),
                    "median_model_autoregressive_coefficient": coefficient,
                }
            )
    return result


def _candidate_decision(
    *,
    ceiling: float,
    summary: Mapping[str, Any],
    baseline_macro: Mapping[str, float],
    candidate_macro: Mapping[str, float],
    paired: Mapping[str, Any],
    baseline_boundary_count: int,
    candidate_boundary_count: int,
) -> dict[str, Any]:
    metrics = paired["metrics"]

    def at_least_three_not_worse(metric: str) -> bool:
        payload = metrics[metric]
        return (
            int(payload["one_state_ar_cap_candidate_better_fold_count"])
            + int(payload["tied_fold_count"])
            >= 3
        )

    checks = {
        "no_failed_restart": int(summary["failed_restart_count"]) == 0,
        "all_selected_fits_converged": int(
            summary["selected_fit_nonconvergence_count"]
        )
        == 0,
        "station_fold_boundary_contact_reduced": (
            candidate_boundary_count < baseline_boundary_count
        ),
        "macro_coverage_error_improved": (
            candidate_macro["absolute_marginal_95_coverage_error"]
            < baseline_macro["absolute_marginal_95_coverage_error"]
        ),
        "coverage_not_worse_in_at_least_three_groups": at_least_three_not_worse(
            "absolute_marginal_95_coverage_error"
        ),
        "sequence_energy_not_worse_macro": (
            candidate_macro["mean_normalized_sequence_energy_score_m"]
            <= baseline_macro["mean_normalized_sequence_energy_score_m"]
        ),
        "sequence_energy_not_worse_in_at_least_three_groups": (
            at_least_three_not_worse("mean_normalized_sequence_energy_score_m")
        ),
        "lag_error_not_worse_macro": (
            candidate_macro["median_absolute_lag_one_correlation_error"]
            <= baseline_macro["median_absolute_lag_one_correlation_error"]
        ),
        "lag_error_not_worse_in_at_least_three_groups": at_least_three_not_worse(
            "median_absolute_lag_one_correlation_error"
        ),
        "rmse_not_worse_macro": (
            candidate_macro["sample_mean_prediction_rmse_m"]
            <= baseline_macro["sample_mean_prediction_rmse_m"]
        ),
        "frame_energy_not_worse_macro": (
            candidate_macro["mean_energy_score_m"]
            <= baseline_macro["mean_energy_score_m"]
        ),
    }
    return {
        "maximum_absolute_autoregression": ceiling,
        "checks": checks,
        "all_predeclared_development_checks_passed": all(checks.values()),
        "baseline_station_fold_boundary_count": baseline_boundary_count,
        "candidate_station_fold_boundary_count": candidate_boundary_count,
        "negative_metric_delta_is_better": True,
    }


def run_expanded_ar_boundary_sensitivity(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Run the fixed v0.15.3 ceiling sweep and consolidate all baselines."""

    (
        gaussian_summary,
        gaussian_hashes,
        _aiohmm_summary,
        aiohmm_hashes,
        one_state_summary,
        one_state_hashes,
        corrected_summary,
        corrected_hashes,
        reference_configuration,
    ) = _validated_references(arguments)
    ensure_empty_output_directory(arguments.output_directory)

    candidate_summaries: dict[float, Mapping[str, Any]] = {}
    candidate_evaluation_rows: dict[float, Sequence[Mapping[str, Any]]] = {}
    candidate_station_rows: dict[float, Sequence[Mapping[str, Any]]] = {}
    for ceiling in FITTED_AR_CEILINGS:
        candidate_directory = (
            arguments.output_directory / "candidates" / _model_id(ceiling)
        )
        candidate_arguments = _candidate_arguments(
            arguments,
            ceiling=ceiling,
            output_directory=candidate_directory,
        )
        candidate_configuration = _configuration(candidate_arguments).to_dict()
        unexpected = {
            name: {"v0151": reference_configuration.get(name), "candidate": value}
            for name, value in candidate_configuration.items()
            if name != "maximum_absolute_autoregression"
            and reference_configuration.get(name) != value
        }
        if unexpected:
            raise ValueError(
                "v0.15.3 candidate changed more than the AR ceiling: "
                f"{unexpected}"
            )
        summary, status = _run_expanded_autoregressive(
            candidate_arguments,
            experiment=EXPERIMENT,
        )
        if status != 0:
            raise ValueError(f"v0.15.3 candidate failed: {ceiling}")
        summary.update(
            {
                "one_state_ar_reference_version": "0.15.1",
                "one_state_ar_reference_files_sha256": dict(one_state_hashes),
                "only_configuration_difference_from_v0151": {
                    "maximum_absolute_autoregression": {
                        "v0151": REFERENCE_AR_CEILING,
                        "candidate": ceiling,
                    }
                },
                "ar_ceiling_selected_after_held_out_evaluation": False,
                "candidate_is_part_of_predeclared_fixed_sweep": True,
            }
        )
        write_strict_json(
            candidate_directory / "one_state_ar_summary.json", summary
        )
        candidate_summaries[ceiling] = summary
        candidate_evaluation_rows[ceiling] = read_csv_rows(
            candidate_directory / "one_state_ar_evaluation.csv"
        )
        candidate_station_rows[ceiling] = read_csv_rows(
            candidate_directory / "one_state_ar_station_evaluation.csv"
        )

    gaussian_rows = read_csv_rows(
        arguments.gaussian_directory / "gaussian_grouped_evaluation.csv"
    )
    one_state_evaluation = read_csv_rows(
        arguments.one_state_ar_directory / "one_state_ar_evaluation.csv"
    )
    one_state_station = read_csv_rows(
        arguments.one_state_ar_directory / "one_state_ar_station_evaluation.csv"
    )
    corrected_evaluation = read_csv_rows(
        arguments.two_state_convergence_directory
        / "two_state_convergence_evaluation.csv"
    )

    unconditional_macro = _gaussian_macro(
        gaussian_summary, "unconditional_gaussian"
    )
    conditional_macro = _gaussian_macro(gaussian_summary, "conditional_gaussian")
    baseline_macro = _autoregressive_macro(one_state_summary)
    corrected_macro = _autoregressive_macro(corrected_summary)
    candidate_macros = {
        ceiling: _autoregressive_macro(summary)
        for ceiling, summary in candidate_summaries.items()
    }

    model_rows = [
        _comparison_row(
            model_id="unconditional_gaussian",
            model_family="unconditional_gaussian",
            version="0.14.0",
            state_count=None,
            ceiling=None,
            frozen=True,
            macro=unconditional_macro,
        ),
        _comparison_row(
            model_id="conditional_gaussian",
            model_family="conditional_gaussian",
            version="0.14.0",
            state_count=None,
            ceiling=None,
            frozen=True,
            macro=conditional_macro,
        ),
        _comparison_row(
            model_id="corrected_two_state_aiohmm",
            model_family="conditional_autoregressive_iohmm",
            version="0.15.2",
            state_count=2,
            ceiling=REFERENCE_AR_CEILING,
            frozen=True,
            macro=corrected_macro,
        ),
        _comparison_row(
            model_id=_model_id(REFERENCE_AR_CEILING),
            model_family="one_state_conditional_ar_gaussian",
            version="0.15.1",
            state_count=1,
            ceiling=REFERENCE_AR_CEILING,
            frozen=True,
            macro=baseline_macro,
        ),
    ]
    model_rows.extend(
        _comparison_row(
            model_id=_model_id(ceiling),
            model_family="one_state_conditional_ar_gaussian",
            version=VERSION,
            state_count=1,
            ceiling=ceiling,
            frozen=False,
            macro=candidate_macros[ceiling],
        )
        for ceiling in FITTED_AR_CEILINGS
    )

    fold_rows: list[dict[str, Any]] = []
    _append_fold_comparison_rows(
        fold_rows,
        model_id="unconditional_gaussian",
        ceiling=None,
        rows=_gaussian_fold_rows(gaussian_rows, model_name="unconditional_gaussian"),
    )
    _append_fold_comparison_rows(
        fold_rows,
        model_id="conditional_gaussian",
        ceiling=None,
        rows=_gaussian_fold_rows(gaussian_rows, model_name="conditional_gaussian"),
    )
    _append_fold_comparison_rows(
        fold_rows,
        model_id="corrected_two_state_aiohmm",
        ceiling=REFERENCE_AR_CEILING,
        rows=_autoregressive_fold_rows(corrected_evaluation),
    )
    _append_fold_comparison_rows(
        fold_rows,
        model_id=_model_id(REFERENCE_AR_CEILING),
        ceiling=REFERENCE_AR_CEILING,
        rows=_autoregressive_fold_rows(one_state_evaluation),
    )
    for ceiling in FITTED_AR_CEILINGS:
        _append_fold_comparison_rows(
            fold_rows,
            model_id=_model_id(ceiling),
            ceiling=ceiling,
            rows=_autoregressive_fold_rows(candidate_evaluation_rows[ceiling]),
        )

    station_rows = _station_comparison_rows(
        baseline_rows=one_state_station,
        candidate_rows_by_ceiling=candidate_station_rows,
    )
    baseline_boundary_count = _boundary_station_fold_count(
        one_state_station, ceiling=REFERENCE_AR_CEILING
    )
    paired_diagnostics: dict[str, Any] = {}
    decisions: dict[str, Any] = {}
    for ceiling in FITTED_AR_CEILINGS:
        paired = _paired_sample_metric_diagnostics(
            candidate_evaluation_rows[ceiling],
            one_state_evaluation,
            candidate_label="one_state_ar_cap_candidate",
            reference_label="one_state_ar_cap_0_980",
        )
        paired_diagnostics[_model_id(ceiling)] = paired
        decisions[_model_id(ceiling)] = _candidate_decision(
            ceiling=ceiling,
            summary=candidate_summaries[ceiling],
            baseline_macro=baseline_macro,
            candidate_macro=candidate_macros[ceiling],
            paired=paired,
            baseline_boundary_count=baseline_boundary_count,
            candidate_boundary_count=_boundary_station_fold_count(
                candidate_station_rows[ceiling], ceiling=ceiling
            ),
        )

    supported = [
        ceiling
        for ceiling in FITTED_AR_CEILINGS
        if decisions[_model_id(ceiling)][
            "all_predeclared_development_checks_passed"
        ]
    ]
    smallest_supported = min(supported) if supported else None
    comparison_path = (
        arguments.output_directory / "ar_boundary_model_comparison.csv"
    )
    fold_path = arguments.output_directory / "ar_boundary_fold_comparison.csv"
    station_path = (
        arguments.output_directory / "ar_boundary_station_comparison.csv"
    )
    diagnostics_path = (
        arguments.output_directory / "ar_boundary_sensitivity_diagnostics.png"
    )
    write_csv_rows(comparison_path, MODEL_COMPARISON_FIELDS, model_rows)
    write_csv_rows(fold_path, FOLD_COMPARISON_FIELDS, fold_rows)
    write_csv_rows(station_path, STATION_COMPARISON_FIELDS, station_rows)
    plot_expanded_ar_boundary_sensitivity(
        diagnostics_path,
        model_rows=model_rows,
        station_rows=station_rows,
        baseline_ceiling=REFERENCE_AR_CEILING,
    )

    baseline_pooled = one_state_summary.get(
        "primary_pooled_cross_validated_metrics"
    )
    if not isinstance(baseline_pooled, Mapping):
        raise ValueError("v0.15.1 pooled metrics are missing")
    observed_pooled_coverage = {
        _model_id(REFERENCE_AR_CEILING): float(
            baseline_pooled["marginal_95_coverage"]
        )
    }
    for ceiling, candidate in candidate_summaries.items():
        pooled = candidate.get("primary_pooled_cross_validated_metrics")
        if not isinstance(pooled, Mapping):
            raise ValueError("v0.15.3 candidate pooled metrics are missing")
        observed_pooled_coverage[_model_id(ceiling)] = float(
            pooled["marginal_95_coverage"]
        )

    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "one_state_ar_boundary_sensitivity_audit",
        "project_role": "canonical_thesis_implementation",
        "source_dataset_version": "0.13.1",
        "source_files_sha256": dict(one_state_summary["source_files_sha256"]),
        "gaussian_baseline_version": "0.14.0",
        "gaussian_baseline_files_sha256": dict(gaussian_hashes),
        "two_state_aiohmm_reference_version": "0.15.0",
        "two_state_aiohmm_reference_files_sha256": dict(aiohmm_hashes),
        "one_state_ar_reference_version": "0.15.1",
        "one_state_ar_reference_files_sha256": dict(one_state_hashes),
        "corrected_two_state_reference_version": "0.15.2",
        "corrected_two_state_reference_files_sha256": dict(corrected_hashes),
        "reference_ar_ceiling": REFERENCE_AR_CEILING,
        "predeclared_ar_ceilings": list(AR_CEILINGS),
        "fitted_candidate_ar_ceilings": list(FITTED_AR_CEILINGS),
        "only_varied_configuration_field": (
            "maximum_absolute_autoregression"
        ),
        "baseline_configuration": reference_configuration,
        "same_data_folds_transforms_architecture_fitting_sampling_and_metrics": True,
        "unconditional_gaussian_included_in_consolidated_comparison": True,
        "model_comparison_file": comparison_path.name,
        "fold_comparison_file": fold_path.name,
        "station_comparison_file": station_path.name,
        "candidate_directories": {
            _model_id(ceiling): str(
                (Path("candidates") / _model_id(ceiling)).as_posix()
            )
            for ceiling in FITTED_AR_CEILINGS
        },
        "candidate_primary_macro_deltas_from_v0151": {
            _model_id(ceiling): _same_schema_metric_deltas(
                candidate_macros[ceiling], baseline_macro
            )
            for ceiling in FITTED_AR_CEILINGS
        },
        "candidate_primary_macro_deltas_from_unconditional_gaussian": {
            _model_id(ceiling): _same_schema_metric_deltas(
                candidate_macros[ceiling], unconditional_macro
            )
            for ceiling in FITTED_AR_CEILINGS
        },
        "candidate_primary_macro_deltas_from_conditional_gaussian": {
            _model_id(ceiling): _same_schema_metric_deltas(
                candidate_macros[ceiling], conditional_macro
            )
            for ceiling in FITTED_AR_CEILINGS
        },
        "candidate_primary_macro_deltas_from_corrected_two_state": {
            _model_id(ceiling): _same_schema_metric_deltas(
                candidate_macros[ceiling], corrected_macro
            )
            for ceiling in FITTED_AR_CEILINGS
        },
        "paired_candidate_diagnostics_vs_v0151": paired_diagnostics,
        "predeclared_development_decisions": decisions,
        "development_supported_ar_ceilings": supported,
        "smallest_development_supported_ar_ceiling": smallest_supported,
        "development_result_classification": (
            "at_least_one_higher_ar_ceiling_passes_all_predeclared_checks"
            if supported
            else "no_higher_ar_ceiling_passes_all_predeclared_checks"
        ),
        "recorded_coverage_hypothesis": {
            "pooled_marginal_95_coverage_if_clipped_band_recovers": (
                RECORDED_POOLED_COVERAGE_HYPOTHESIS
            ),
            "observed_pooled_coverage_by_candidate": observed_pooled_coverage,
            "used_as_acceptance_or_selection_target": False,
        },
        "primary_group_independence": {
            "technical_group_count": len(
                one_state_summary["primary_clean_drive_ids"]
            ),
            "independent_journey_count": 1,
            "journey_level_generalization_estimated": False,
        },
        "ar_ceiling_selected_after_held_out_evaluation": False,
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "planner_model_frozen": False,
        "next_phase": (
            "review_v0153_then_freeze_development_residual_model_before_planner"
        ),
        "scientific_limitations": [
            (
                "All primary groups are separated portions of one same-day "
                "outing; this is within-outing development evidence only."
            ),
            (
                "The smallest supported ceiling rule is conservative development "
                "guidance, not an unbiased final hyperparameter selection."
            ),
            (
                "Independent clean outings are required before final selection "
                "or a journey-level generalization claim."
            ),
            (
                "RLMB remains a pseudo-reference and its independence from the "
                "EDP topology source is unresolved."
            ),
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    summary_path = arguments.output_directory / "ar_boundary_sensitivity_summary.json"
    output_hashes = {
        str(path.relative_to(arguments.output_directory).as_posix()): sha256_file(path)
        for path in sorted(arguments.output_directory.rglob("*"))
        if path.is_file() and path != summary_path
    }
    summary["output_files_sha256"] = output_hashes
    write_strict_json(summary_path, summary)
    return summary, 0


__all__ = [
    "AR_BOUNDARY_TOLERANCE",
    "AR_CEILINGS",
    "EXPERIMENT",
    "FITTED_AR_CEILINGS",
    "FOLD_COMPARISON_FIELDS",
    "MODEL_COMPARISON_FIELDS",
    "REFERENCE_AR_CEILING",
    "STATION_COMPARISON_FIELDS",
    "VERSION",
    "run_expanded_ar_boundary_sensitivity",
]
