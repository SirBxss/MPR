"""v0.15.2 size-invariant convergence audit for the two-state AIOHMM."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.model_evaluation import DriveGroupedFold, build_leave_one_drive_out_folds
from ..io.expanded_modeling_dataset import load_expanded_modeling_dataset
from ..io.expanded_sequence_dataset import read_csv_rows
from ..io.model_evaluation import (
    load_expanded_aiohmm_baseline,
    load_expanded_gaussian_baseline,
    load_expanded_one_state_ar_baseline,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.aiohmm import (
    ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE,
    RELATIVE_TOTAL_LOG_PROBABILITY_CONVERGENCE,
    AIOHMMConfig,
)
from ..visualization.expanded_aiohmm_convergence import (
    plot_expanded_aiohmm_convergence_audit,
)
from .expanded_aiohmm import (
    ExpandedAutoregressiveExperiment,
    _latent_switching_classification,
    _run_expanded_autoregressive,
    _same_schema_metric_deltas,
)
from .sequence_aiohmm import _configuration
from .sequence_contract import sha256_file

VERSION = "0.15.2"
CONVERGENCE_TOLERANCE_PER_FRAME = 1e-3

EXPERIMENT = ExpandedAutoregressiveExperiment(
    version=VERSION,
    output_prefix="two_state_convergence",
    expected_state_count=2,
    purpose="two_state_aiohmm_size_invariant_convergence_audit",
    fold_models_purpose="v0152_clean_group_fold_two_state_convergence_models",
    state_count_rationale="unchanged_fixed_v0150_two_state_architecture",
    plot_subtitle=(
        "Two-state v0.15 model with absolute per-frame EM convergence"
    ),
    candidate_label="two_state_convergence",
    comparison_key=(
        "corrected_two_state_aiohmm_minus_conditional_gaussian_primary_macro_deltas"
    ),
    next_phase=(
        "review_corrected_two_state_evidence_then_run_separate_ar_boundary_audit"
    ),
    scientific_limitations=(
        (
            "The four clean technical groups are separated portions of one "
            "longer same-day outing, not four independent journeys."
        ),
        "Leave-one-group-out results do not estimate journey-level generalization.",
        (
            "This audit changes only the EM convergence scale and tolerance; "
            "it does not tune the model architecture."
        ),
        (
            "RLMB remains a pseudo-reference and independence from the EDP "
            "topology source is unknown."
        ),
        "Sample metrics retain finite Monte Carlo error under the recorded seed.",
    ),
)

CONVERGENCE_COMPARISON_FIELDS = (
    "fold_id",
    "held_out_drive_id",
    "reference_iteration_count",
    "corrected_iteration_count",
    "added_iteration_count",
    "reference_converged",
    "corrected_converged",
    "reference_training_joint_log_probability_standardized",
    "corrected_training_joint_log_probability_standardized",
    "corrected_minus_reference_training_joint_log_probability_standardized",
    "corrected_last_log_probability_improvement_standardized",
    "corrected_last_absolute_log_probability_improvement_per_frame_standardized",
    "corrected_last_convergence_measure",
)

SAMPLE_METRIC_FIELDS = (
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "absolute_marginal_95_coverage_error",
    "median_absolute_lag_one_correlation_error",
)


def _normalized_configuration(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Load old configurations while filling newly explicit default semantics."""

    return AIOHMMConfig.from_dict(payload).to_dict()


def _validate_only_convergence_changed(
    *,
    candidate: AIOHMMConfig,
    reference_summary: Mapping[str, Any],
    one_state_summary: Mapping[str, Any],
    restart_count: int,
) -> dict[str, dict[str, Any]]:
    reference_payload = reference_summary.get("configuration")
    one_state_payload = one_state_summary.get("configuration")
    if not isinstance(reference_payload, Mapping):
        raise ValueError("v0.15.0 AIOHMM configuration is missing")
    if not isinstance(one_state_payload, Mapping):
        raise ValueError("v0.15.1 one-state configuration is missing")
    reference = _normalized_configuration(reference_payload)
    one_state = _normalized_configuration(one_state_payload)
    candidate_payload = candidate.to_dict()

    if (
        reference["convergence_criterion"]
        != RELATIVE_TOTAL_LOG_PROBABILITY_CONVERGENCE
        or float(reference["convergence_tolerance"]) != 1e-4
    ):
        raise ValueError("v0.15.0 convergence contract is not the reviewed legacy rule")
    if (
        candidate_payload["convergence_criterion"]
        != ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE
        or float(candidate_payload["convergence_tolerance"])
        != CONVERGENCE_TOLERANCE_PER_FRAME
    ):
        raise ValueError("v0.15.2 convergence contract differs from the fixed audit")

    permitted = {"convergence_criterion", "convergence_tolerance"}
    unexpected = {
        name: {"v0150": reference[name], "v0152": value}
        for name, value in candidate_payload.items()
        if name not in permitted and reference.get(name) != value
    }
    if unexpected:
        raise ValueError(
            "v0.15.2 non-convergence hyperparameter drifted from v0.15.0: "
            f"{unexpected}"
        )

    one_state_permitted = {"state_count", "input_dependent_transitions"}
    one_state_drift = {
        name: {"v0150": value, "v0151": one_state.get(name)}
        for name, value in reference.items()
        if name not in one_state_permitted and one_state.get(name) != value
    }
    if one_state_drift:
        raise ValueError(
            "v0.15.1 non-architectural configuration differs from v0.15.0: "
            f"{one_state_drift}"
        )
    if (
        reference_summary.get("restart_count_per_fit") != restart_count
        or one_state_summary.get("restart_count_per_fit") != restart_count
    ):
        raise ValueError("v0.15.2 restart count differs from a frozen reference")

    return {
        "convergence_criterion": {
            "v0150": reference["convergence_criterion"],
            "v0152": candidate_payload["convergence_criterion"],
        },
        "convergence_tolerance": {
            "v0150": float(reference["convergence_tolerance"]),
            "v0152": float(candidate_payload["convergence_tolerance"]),
        },
    }


def _held_out_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("scope") != "held_out_drive":
            continue
        drive_id = str(row.get("held_out_drive_id", ""))
        if not drive_id or drive_id in result:
            raise ValueError("held-out AIOHMM comparison rows are ambiguous")
        result[drive_id] = row
    if not result:
        raise ValueError("held-out AIOHMM comparison rows are missing")
    return result


def _paired_sample_metric_diagnostics(
    candidate_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
    *,
    candidate_label: str,
    reference_label: str,
) -> dict[str, Any]:
    """Report paired technical-group wins for every sample-based metric."""

    candidate = _held_out_rows(candidate_rows)
    reference = _held_out_rows(reference_rows)
    if set(candidate) != set(reference):
        raise ValueError("paired AIOHMM technical-group rows differ")
    tolerance = 1e-12
    diagnostics: dict[str, Any] = {}
    for metric in SAMPLE_METRIC_FIELDS:
        deltas = {
            drive_id: float(candidate[drive_id][metric])
            - float(reference[drive_id][metric])
            for drive_id in sorted(candidate)
        }
        diagnostics[metric] = {
            "fold_count": len(deltas),
            f"{candidate_label}_better_fold_count": sum(
                value < -tolerance for value in deltas.values()
            ),
            f"{reference_label}_better_fold_count": sum(
                value > tolerance for value in deltas.values()
            ),
            "tied_fold_count": sum(
                abs(value) <= tolerance for value in deltas.values()
            ),
            f"{candidate_label}_minus_{reference_label}_by_group": deltas,
            "negative_delta_is_better": True,
        }
    return {
        "technical_groups_are_independent_journeys": False,
        "metrics": diagnostics,
    }


def _csv_bool(value: Any) -> bool:
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"invalid CSV boolean: {value!r}")


def _selected_restart_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    selected: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("status") != "complete" or not _csv_bool(row.get("selected")):
            continue
        fold_id = str(row.get("fold_id", ""))
        if not fold_id or fold_id in selected:
            raise ValueError("selected AIOHMM restart rows are ambiguous")
        selected[fold_id] = row
    if not selected:
        raise ValueError("selected AIOHMM restart rows are missing")
    return selected


def _convergence_comparison_rows(
    corrected_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    corrected = _selected_restart_rows(corrected_rows)
    reference = _selected_restart_rows(reference_rows)
    if set(corrected) != set(reference):
        raise ValueError("selected v0.15.0 and v0.15.2 fit sets differ")
    result: list[dict[str, Any]] = []
    for fold_id in sorted(corrected):
        current = corrected[fold_id]
        baseline = reference[fold_id]
        current_score = float(
            current["training_joint_log_probability_standardized"]
        )
        baseline_score = float(
            baseline["training_joint_log_probability_standardized"]
        )
        current_iterations = int(float(current["em_iteration_count"]))
        baseline_iterations = int(float(baseline["em_iteration_count"]))
        result.append(
            {
                "fold_id": fold_id,
                "held_out_drive_id": current.get("held_out_drive_id") or None,
                "reference_iteration_count": baseline_iterations,
                "corrected_iteration_count": current_iterations,
                "added_iteration_count": current_iterations - baseline_iterations,
                "reference_converged": _csv_bool(baseline["em_converged"]),
                "corrected_converged": _csv_bool(current["em_converged"]),
                "reference_training_joint_log_probability_standardized": (
                    baseline_score
                ),
                "corrected_training_joint_log_probability_standardized": (
                    current_score
                ),
                "corrected_minus_reference_training_joint_log_probability_standardized": (
                    current_score - baseline_score
                ),
                "corrected_last_log_probability_improvement_standardized": float(
                    current[
                        "em_last_log_probability_improvement_standardized"
                    ]
                ),
                "corrected_last_absolute_log_probability_improvement_per_frame_standardized": float(
                    current[
                        "em_last_absolute_log_probability_improvement_per_frame_standardized"
                    ]
                ),
                "corrected_last_convergence_measure": float(
                    current["em_last_convergence_measure"]
                ),
            }
        )
    return result


def _convergence_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    corrected_converged = [bool(row["corrected_converged"]) for row in rows]
    reference_converged = [bool(row["reference_converged"]) for row in rows]
    added = [int(row["added_iteration_count"]) for row in rows]
    score_deltas = [
        float(
            row[
                "corrected_minus_reference_training_joint_log_probability_standardized"
            ]
        )
        for row in rows
    ]
    return {
        "selected_fit_count": len(rows),
        "reference_converged_fit_count": sum(reference_converged),
        "corrected_converged_fit_count": sum(corrected_converged),
        "all_corrected_selected_fits_converged": all(corrected_converged),
        "minimum_added_iteration_count": min(added),
        "maximum_added_iteration_count": max(added),
        "mean_added_iteration_count": sum(added) / len(added),
        "minimum_training_log_probability_change_standardized": min(score_deltas),
        "maximum_training_log_probability_change_standardized": max(score_deltas),
    }


def _result_classification(
    *,
    convergence_resolved: bool,
    latent_switching_classification: str,
) -> str:
    if not convergence_resolved:
        return "corrected_two_state_selected_fit_nonconvergence_remains"
    if (
        latent_switching_classification
        == "no_predeclared_sample_metric_support_for_latent_switching"
    ):
        return "convergence_confound_resolved_without_latent_switching_support"
    return "convergence_confound_resolved_with_mixed_or_positive_switching_evidence"


def _validated_references(
    arguments: argparse.Namespace,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, str],
    Mapping[str, Any],
    Mapping[str, str],
    Mapping[str, str],
    Sequence[DriveGroupedFold],
    dict[str, dict[str, Any]],
]:
    source = load_expanded_modeling_dataset(arguments.expanded_sequence_directory)
    folds = build_leave_one_drive_out_folds(
        source.sequences, primary_drive_ids=source.clean_drive_ids
    )
    _gaussian_summary, gaussian_protocol, gaussian_hashes = (
        load_expanded_gaussian_baseline(
            arguments.gaussian_directory,
            source_files_sha256=source.source_files_sha256,
            folds=folds,
        )
    )
    monte_carlo = gaussian_protocol.get("monte_carlo")
    if not isinstance(monte_carlo, Mapping):
        raise ValueError("v0.14 Monte Carlo contract is missing")
    reference_summary, reference_hashes = load_expanded_aiohmm_baseline(
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
        aiohmm_files_sha256=reference_hashes,
        folds=folds,
        sample_count=arguments.sample_count,
        base_seed=arguments.seed,
    )
    differences = _validate_only_convergence_changed(
        candidate=_configuration(arguments),
        reference_summary=reference_summary,
        one_state_summary=one_state_summary,
        restart_count=arguments.restart_count,
    )
    return (
        reference_summary,
        reference_hashes,
        one_state_summary,
        one_state_hashes,
        gaussian_hashes,
        folds,
        differences,
    )


def run_expanded_aiohmm_convergence_audit(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Re-fit v0.15 with a per-frame criterion and compare frozen artifacts."""

    (
        reference_summary,
        reference_hashes,
        one_state_summary,
        one_state_hashes,
        _gaussian_hashes,
        _folds,
        configuration_differences,
    ) = _validated_references(arguments)

    summary, status = _run_expanded_autoregressive(
        arguments,
        experiment=EXPERIMENT,
    )
    corrected_evaluation = read_csv_rows(
        arguments.output_directory / "two_state_convergence_evaluation.csv"
    )
    corrected_restarts = read_csv_rows(
        arguments.output_directory / "two_state_convergence_restart_evaluation.csv"
    )
    reference_evaluation = read_csv_rows(
        arguments.aiohmm_directory / "expanded_aiohmm_evaluation.csv"
    )
    reference_restarts = read_csv_rows(
        arguments.aiohmm_directory / "expanded_aiohmm_restart_evaluation.csv"
    )
    one_state_evaluation = read_csv_rows(
        arguments.one_state_ar_directory / "one_state_ar_evaluation.csv"
    )

    corrected_macro = summary["primary_macro_drive_metrics"]
    reference_macro = reference_summary["primary_macro_drive_metrics"]
    one_state_macro = one_state_summary["primary_macro_drive_metrics"]
    corrected_minus_reference = _same_schema_metric_deltas(
        corrected_macro, reference_macro
    )
    corrected_minus_one_state = _same_schema_metric_deltas(
        corrected_macro, one_state_macro
    )
    one_state_minus_corrected = {
        key: -value for key, value in corrected_minus_one_state.items()
    }
    latent_classification = _latent_switching_classification(
        corrected_minus_one_state
    )
    convergence_rows = _convergence_comparison_rows(
        corrected_restarts, reference_restarts
    )
    convergence = _convergence_summary(convergence_rows)
    corrected_vs_reference_folds = _paired_sample_metric_diagnostics(
        corrected_evaluation,
        reference_evaluation,
        candidate_label="corrected_two_state_aiohmm",
        reference_label="v0150_two_state_aiohmm",
    )
    corrected_vs_one_state_folds = _paired_sample_metric_diagnostics(
        corrected_evaluation,
        one_state_evaluation,
        candidate_label="corrected_two_state_aiohmm",
        reference_label="one_state_ar",
    )

    comparison_path = (
        arguments.output_directory / "two_state_convergence_comparison.csv"
    )
    write_csv_rows(
        comparison_path,
        CONVERGENCE_COMPARISON_FIELDS,
        convergence_rows,
    )
    diagnostics_path = (
        arguments.output_directory / "two_state_convergence_diagnostics.png"
    )
    plot_expanded_aiohmm_convergence_audit(
        diagnostics_path,
        convergence_rows=convergence_rows,
        corrected_minus_reference=corrected_minus_reference,
        corrected_minus_one_state=corrected_minus_one_state,
        corrected_vs_one_state_folds=corrected_vs_one_state_folds,
    )

    summary.update(
        {
            "reference_two_state_aiohmm_version": "0.15.0",
            "reference_two_state_aiohmm_files_sha256": dict(reference_hashes),
            "one_state_ar_reference_version": "0.15.1",
            "one_state_ar_reference_files_sha256": dict(one_state_hashes),
            "only_intended_fit_difference_from_v0150": (
                "absolute per-frame EM convergence replaces relative total-log-"
                "probability convergence"
            ),
            "configuration_differences_from_v0150": configuration_differences,
            "corrected_two_state_minus_v0150_primary_macro_deltas": (
                corrected_minus_reference
            ),
            "corrected_two_state_minus_one_state_ar_primary_macro_deltas": (
                corrected_minus_one_state
            ),
            "one_state_ar_minus_corrected_two_state_primary_macro_deltas": (
                one_state_minus_corrected
            ),
            "corrected_latent_switching_result_classification": (
                latent_classification
            ),
            "selected_fit_convergence_comparison": convergence,
            "paired_sample_metrics_vs_v0150": corrected_vs_reference_folds,
            "paired_sample_metrics_vs_one_state_ar": (
                corrected_vs_one_state_folds
            ),
            "convergence_audit_result_classification": _result_classification(
                convergence_resolved=bool(
                    convergence["all_corrected_selected_fits_converged"]
                ),
                latent_switching_classification=latent_classification,
            ),
            "convergence_comparison_file": comparison_path.name,
            "ar_boundary_changed": False,
            "new_model_family_introduced": False,
        }
    )
    output_hashes = dict(summary["output_files_sha256"])
    output_hashes[comparison_path.name] = sha256_file(comparison_path)
    output_hashes[diagnostics_path.name] = sha256_file(diagnostics_path)
    summary["output_files_sha256"] = output_hashes
    write_strict_json(
        arguments.output_directory / "two_state_convergence_summary.json",
        summary,
    )
    return summary, status


__all__ = [
    "CONVERGENCE_COMPARISON_FIELDS",
    "CONVERGENCE_TOLERANCE_PER_FRAME",
    "EXPERIMENT",
    "SAMPLE_METRIC_FIELDS",
    "VERSION",
    "run_expanded_aiohmm_convergence_audit",
]
