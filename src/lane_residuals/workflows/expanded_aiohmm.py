"""v0.15 AIOHMM evaluation on the frozen v0.14 clean-drive protocol."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.model_evaluation import build_leave_one_drive_out_folds
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import PaddedSequenceDataset, SequenceStandardizer
from ..io.expanded_modeling_dataset import ExpandedModelingDataset, load_expanded_modeling_dataset
from ..io.expanded_sequence_dataset import read_csv_rows
from ..io.model_evaluation import load_expanded_gaussian_baseline
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.aiohmm import AutoregressiveInputOutputHMM
from ..modeling.base import SampleResult
from ..modeling.sequence_evaluation import (
    SequenceSampleEvaluation,
    evaluate_sequence_samples,
    physical_sample_result,
)
from ..visualization.sequence_aiohmm import plot_sequence_aiohmm_diagnostics
from .sequence_aiohmm import (
    RESTART_FIELDS,
    RESTART_SEED_STRIDE,
    _configuration,
    _evaluation_row,
    _fit_report_payload,
    _fit_restarts,
    _posterior_statistics,
    _posterior_tensor,
    _state_rows,
    _station_rows,
    _transition_diagnostics,
)
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.15.0"

EVALUATION_FIELDS = (
    "scope",
    "cohort_role",
    "held_out_drive_id",
    "training_drive_ids",
    "test_drive_ids",
    "training_sequence_count",
    "training_frame_count",
    "test_sequence_count",
    "test_frame_count",
    "sample_count",
    "state_count",
    "restart_count",
    "mean_joint_negative_log_likelihood_standardized",
    "mean_joint_negative_log_likelihood_physical",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_observed_lag_one_correlation",
    "median_generated_lag_one_correlation",
    "median_absolute_lag_one_correlation_error",
    "mean_posterior_state_entropy_nats",
    "mean_maximum_posterior_state_probability",
    "minimum_posterior_state_occupancy",
    "maximum_posterior_state_occupancy",
    "mean_self_transition_probability",
    "mean_transition_probability_standard_deviation",
    "minimum_expected_dwell_frames",
    "maximum_expected_dwell_frames",
    "minimum_autoregressive_coefficient",
    "median_autoregressive_coefficient",
    "maximum_autoregressive_coefficient",
    "temporal_dependency_order",
)

STATION_FIELDS = (
    "scope",
    "cohort_role",
    "held_out_drive_id",
    "station_m",
    "test_frame_count",
    "sample_mean_prediction_rmse_m",
    "sample_mean_prediction_bias_m",
    "marginal_95_coverage",
    "observed_lag_one_correlation",
    "generated_median_lag_one_correlation",
    "generated_p05_lag_one_correlation",
    "generated_p95_lag_one_correlation",
    "absolute_lag_one_correlation_error",
    "median_model_autoregressive_coefficient",
)

STATE_FIELDS = (
    "scope",
    "cohort_role",
    "fold_id",
    "held_out_drive_id",
    "state_index",
    "state_label_interpretation",
    "posterior_state_occupancy",
    "training_state_occupancy",
    "initial_probability",
    "zero_condition_intercept_profile_rms_standardized",
    "minimum_autoregressive_coefficient",
    "median_autoregressive_coefficient",
    "maximum_autoregressive_coefficient",
    "minimum_covariance_eigenvalue_standardized2",
    "mean_self_transition_probability",
    "self_transition_probability_standard_deviation",
    "expected_dwell_frames_from_mean_self_transition",
    "mean_transition_row_entropy_nats",
)

FRAME_FIELDS = (
    "scope",
    "cohort_role",
    "sequence_id",
    "sequence_frame_index",
    "recording_id",
    "drive_id",
    "mcap_basename_private",
    "pair_index",
    "estimate_message_index",
    "estimate_source_time_ns_private",
    "joint_filter_negative_log_likelihood_standardized",
    "joint_filter_negative_log_likelihood_physical",
    "sample_mean_prediction_rmse_m",
    "energy_score_m",
    "maximum_posterior_state_index",
    "maximum_posterior_state_probability",
    "posterior_state_entropy_nats",
)


def _expanded_evaluation_row(
    *,
    scope: str,
    cohort_role: str,
    held_out_drive_id: str | None,
    training_drive_ids: Sequence[str],
    test_drive_ids: Sequence[str],
    training_sequence_count: int | None,
    training_frame_count: int | None,
    test: PaddedSequenceDataset,
    sample_count: int,
    state_count: int,
    restart_count: int,
    log_standardized: np.ndarray,
    log_physical: np.ndarray,
    evaluation: SequenceSampleEvaluation,
    posterior_statistics: Mapping[str, Any],
    transition_diagnostics: Mapping[str, Any],
    autoregressive_coefficients: np.ndarray,
) -> dict[str, Any]:
    row = _evaluation_row(
        scope=scope,
        held_out_drive_id=held_out_drive_id,
        training_drive_ids=training_drive_ids,
        training_sequence_count=training_sequence_count,
        training_frame_count=training_frame_count,
        test_sequence_count=test.sequence_count,
        test_frame_count=test.frame_count,
        sample_count=sample_count,
        state_count=state_count,
        restart_count=restart_count,
        log_probability_standardized=log_standardized[test.time_mask],
        log_probability_physical=log_physical[test.time_mask],
        sample_evaluation=evaluation,
        posterior_statistics=posterior_statistics,
        transition_diagnostics=transition_diagnostics,
        autoregressive_coefficients=autoregressive_coefficients,
    )
    row["cohort_role"] = cohort_role
    row["test_drive_ids"] = ";".join(test_drive_ids)
    row["absolute_marginal_95_coverage_error"] = abs(
        float(row["marginal_95_coverage"]) - 0.95
    )
    row["mean_normalized_sequence_energy_score_m"] = (
        evaluation.mean_normalized_sequence_energy_score_m
    )
    return row


def _expanded_station_rows(
    *,
    scope: str,
    cohort_role: str,
    held_out_drive_id: str | None,
    test_frame_count: int,
    evaluation: SequenceSampleEvaluation,
    autoregressive_station_summary: np.ndarray,
) -> list[dict[str, Any]]:
    rows = _station_rows(
        scope=scope,
        held_out_drive_id=held_out_drive_id,
        test_frame_count=test_frame_count,
        evaluation=evaluation,
        autoregressive_station_summary=autoregressive_station_summary,
    )
    for row in rows:
        row["cohort_role"] = cohort_role
    return rows


def _expanded_state_rows(
    *,
    scope: str,
    cohort_role: str,
    fold_id: str,
    held_out_drive_id: str | None,
    model: AutoregressiveInputOutputHMM,
    posterior_occupancies: np.ndarray,
    transition_diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = _state_rows(
        scope=scope,
        fold_id=fold_id,
        held_out_drive_id=held_out_drive_id,
        model=model,
        posterior_occupancies=posterior_occupancies,
        transition_diagnostics=transition_diagnostics,
    )
    for row in rows:
        row["cohort_role"] = cohort_role
    return rows


def _provenance_lookup(
    source: ExpandedModelingDataset,
) -> dict[tuple[str, int], tuple[str, str]]:
    result: dict[tuple[str, int], tuple[str, str]] = {}
    for sequence_index, sequence_id in enumerate(source.sequences.sequence_ids):
        for frame_index in range(int(source.sequences.lengths[sequence_index])):
            result[(str(sequence_id), frame_index)] = (
                str(source.recording_ids_by_frame[sequence_index, frame_index]),
                str(source.mcap_basenames_by_frame_private[sequence_index, frame_index]),
            )
    return result


def _frame_rows(
    *,
    scope: str,
    cohort_role: str,
    dataset: PaddedSequenceDataset,
    provenance: Mapping[tuple[str, int], tuple[str, str]],
    log_standardized: np.ndarray,
    log_physical: np.ndarray,
    evaluation: SequenceSampleEvaluation,
    posterior: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence_index, raw_length in enumerate(dataset.lengths):
        sequence_id = str(dataset.sequence_ids[sequence_index])
        for frame_index in range(int(raw_length)):
            probabilities = posterior[sequence_index, frame_index]
            entropy = -float(
                np.sum(probabilities * np.log(np.maximum(probabilities, 1e-300)))
            )
            recording_id, basename = provenance[(sequence_id, frame_index)]
            rows.append(
                {
                    "scope": scope,
                    "cohort_role": cohort_role,
                    "sequence_id": sequence_id,
                    "sequence_frame_index": frame_index,
                    "recording_id": recording_id,
                    "drive_id": dataset.drive_ids[sequence_index],
                    "mcap_basename_private": basename,
                    "pair_index": dataset.pair_indices[sequence_index, frame_index],
                    "estimate_message_index": dataset.estimate_message_indices[
                        sequence_index, frame_index
                    ],
                    "estimate_source_time_ns_private": (
                        dataset.estimate_source_times_ns_private[
                            sequence_index, frame_index
                        ]
                    ),
                    "joint_filter_negative_log_likelihood_standardized": (
                        -log_standardized[sequence_index, frame_index]
                    ),
                    "joint_filter_negative_log_likelihood_physical": (
                        -log_physical[sequence_index, frame_index]
                    ),
                    "sample_mean_prediction_rmse_m": evaluation.frame_rmse_m[
                        sequence_index, frame_index
                    ],
                    "energy_score_m": evaluation.frame_energy_score_m[
                        sequence_index, frame_index
                    ],
                    "maximum_posterior_state_index": int(np.argmax(probabilities)),
                    "maximum_posterior_state_probability": float(
                        np.max(probabilities)
                    ),
                    "posterior_state_entropy_nats": entropy,
                }
            )
    return rows


def _evaluate_model(
    model: AutoregressiveInputOutputHMM,
    *,
    standardized_test: PaddedSequenceDataset,
    physical_test: PaddedSequenceDataset,
    standardizer: SequenceStandardizer,
    sample_count: int,
    seed: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    SampleResult,
    SequenceSampleEvaluation,
    np.ndarray,
    Mapping[str, Any],
    Mapping[str, Any],
]:
    log_standardized = model.log_probability(standardized_test)
    jacobian = float(np.sum(np.log(standardizer.residual_scale_m)))
    log_physical = np.zeros_like(log_standardized)
    log_physical[standardized_test.time_mask] = (
        log_standardized[standardized_test.time_mask] - jacobian
    )
    standardized_samples = model.sample(
        standardized_test.conditions,
        standardized_test.lengths,
        sample_count=sample_count,
        seed=seed,
        valid_mask=standardized_test.valid_mask,
    )
    physical_samples = physical_sample_result(standardized_samples, standardizer)
    evaluation = evaluate_sequence_samples(physical_test, physical_samples)
    posterior = _posterior_tensor(
        standardized_test,
        model.posterior_state_probabilities(standardized_test),
        state_count=model.config.state_count,
    )
    posterior_statistics = _posterior_statistics(
        posterior, standardized_test.time_mask
    )
    transition_diagnostics = _transition_diagnostics(model, standardized_test)
    return (
        log_standardized,
        log_physical,
        physical_samples,
        evaluation,
        posterior,
        posterior_statistics,
        transition_diagnostics,
    )


def _aggregate_transition_diagnostics(
    fold_rows: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    weights = np.asarray(
        [float(row["test_frame_count"]) for row in fold_rows], dtype=np.float64
    )
    weights /= np.sum(weights)
    result = {
        key: float(
            np.sum(weights * np.asarray([float(row[key]) for row in fold_rows]))
        )
        for key in (
            "mean_self_transition_probability",
            "mean_transition_probability_standard_deviation",
        )
    }
    result["minimum_expected_dwell_frames"] = min(
        float(row["minimum_expected_dwell_frames"]) for row in fold_rows
    )
    result["maximum_expected_dwell_frames"] = max(
        float(row["maximum_expected_dwell_frames"]) for row in fold_rows
    )
    return result


def _macro_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    mean_fields = (
        "mean_joint_negative_log_likelihood_physical",
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "marginal_95_coverage",
        "absolute_marginal_95_coverage_error",
        "median_absolute_lag_one_correlation_error",
        "minimum_posterior_state_occupancy",
        "median_autoregressive_coefficient",
    )
    result = {
        field: float(np.mean([float(row[field]) for row in rows]))
        for field in mean_fields
    }
    result["maximum_autoregressive_coefficient"] = max(
        float(row["maximum_autoregressive_coefficient"]) for row in rows
    )
    return result


def _result_classification(acceptance_checks: Mapping[str, bool]) -> str:
    """Describe only the evidence explicitly represented by the checks."""

    if all(acceptance_checks.values()):
        return "full_generative_acceptance_met"
    if acceptance_checks["lag_one_error_improved"]:
        return "temporal_dependence_improved_but_full_generative_acceptance_not_met"
    return "development_acceptance_not_met"


def _sequence_energy_fold_diagnostics(
    aiohmm_rows: Sequence[Mapping[str, Any]],
    gaussian_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Return paired descriptive fold evidence without claiming independence."""

    gaussian_by_drive: dict[str, float] = {}
    for row in gaussian_rows:
        if (
            row.get("model_name") != "conditional_gaussian"
            or row.get("scope") != "primary_held_out_drive"
        ):
            continue
        drive_id = str(row.get("held_out_drive_id", ""))
        if not drive_id or drive_id in gaussian_by_drive:
            raise ValueError("v0.14 conditional Gaussian fold rows are ambiguous")
        gaussian_by_drive[drive_id] = float(
            row["mean_normalized_sequence_energy_score_m"]
        )

    aiohmm_by_drive = {
        str(row["held_out_drive_id"]): float(
            row["mean_normalized_sequence_energy_score_m"]
        )
        for row in aiohmm_rows
    }
    if set(aiohmm_by_drive) != set(gaussian_by_drive):
        raise ValueError("v0.14 and v0.15 held-out group rows differ")

    deltas = {
        drive_id: aiohmm_by_drive[drive_id] - gaussian_by_drive[drive_id]
        for drive_id in sorted(aiohmm_by_drive)
    }
    tie_tolerance_m = 1e-12
    return {
        "fold_count": len(deltas),
        "aiohmm_better_fold_count": sum(
            delta < -tie_tolerance_m for delta in deltas.values()
        ),
        "conditional_gaussian_better_fold_count": sum(
            delta > tie_tolerance_m for delta in deltas.values()
        ),
        "tied_fold_count": sum(
            abs(delta) <= tie_tolerance_m for delta in deltas.values()
        ),
        "aiohmm_minus_conditional_gaussian_by_group_m": deltas,
        "negative_delta_is_better": True,
        "independent_journey_level_inference_authorized": False,
    }


def _constraint_boundary_diagnostics(
    restart_rows: Sequence[Mapping[str, Any]],
    *,
    minimum_occupancy: float,
    maximum_autoregression: float,
) -> dict[str, Any]:
    """Count completed fits whose reported solution touches configured bounds."""

    complete = [row for row in restart_rows if row["status"] == "complete"]
    occupancy_tolerance = 1e-3
    autoregression_tolerance = 1e-10
    occupancy_count = sum(
        float(row["minimum_state_occupancy_fraction"])
        <= minimum_occupancy + occupancy_tolerance
        for row in complete
    )
    autoregression_count = sum(
        float(row["maximum_absolute_autoregressive_coefficient"])
        >= maximum_autoregression - autoregression_tolerance
        for row in complete
    )
    return {
        "complete_fit_count": len(complete),
        "minimum_occupancy_boundary_fit_count": occupancy_count,
        "maximum_autoregression_boundary_fit_count": autoregression_count,
        "minimum_occupancy_boundary_tolerance": occupancy_tolerance,
        "maximum_autoregression_boundary_tolerance": autoregression_tolerance,
        "all_complete_fits_touch_both_boundaries": bool(complete)
        and occupancy_count == len(complete)
        and autoregression_count == len(complete),
    }


def _metric_subset(row: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {
        "scope",
        "cohort_role",
        "held_out_drive_id",
        "training_drive_ids",
        "test_drive_ids",
        "training_sequence_count",
        "training_frame_count",
    }
    return {field: row[field] for field in EVALUATION_FIELDS if field not in ignored}


def run_expanded_aiohmm(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Evaluate a fixed two-state AIOHMM without held-out model selection."""

    config = _configuration(arguments)
    if config.state_count != 2:
        raise ValueError("v0.15 fixes two states after the documented v0.11 collapse")
    sample_count = arguments.sample_count
    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
        or sample_count < 4
        or sample_count % 2 != 0
    ):
        raise ValueError("sample-count must be an even integer of at least four")
    sample_seed = arguments.seed
    if isinstance(sample_seed, bool) or not isinstance(sample_seed, int) or sample_seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    restart_count = arguments.restart_count
    if isinstance(restart_count, bool) or not isinstance(restart_count, int) or restart_count < 1:
        raise ValueError("restart-count must be a positive integer")

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
    gaussian_evaluation_rows = read_csv_rows(
        arguments.gaussian_directory / "gaussian_grouped_evaluation.csv"
    )
    monte_carlo = gaussian_protocol.get("monte_carlo", {})
    if (
        monte_carlo.get("sample_count") != sample_count
        or monte_carlo.get("base_seed") != sample_seed
    ):
        raise ValueError("AIOHMM sample count and seed must match the frozen v0.14 protocol")
    ensure_empty_output_directory(arguments.output_directory)

    primary = source.primary
    supplementary = source.supplementary
    provenance = _provenance_lookup(source)
    combined_samples = np.zeros(
        (sample_count, *primary.residuals_m.shape), dtype=np.float64
    )
    combined_log_standardized = np.zeros(primary.time_mask.shape, dtype=np.float64)
    combined_log_physical = np.zeros_like(combined_log_standardized)
    combined_posterior = np.zeros(
        (*primary.time_mask.shape, config.state_count), dtype=np.float64
    )
    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    restart_rows: list[dict[str, Any]] = []
    fold_models: dict[str, Any] = {}
    fold_autoregression: list[np.ndarray] = []

    for fold_index, fold in enumerate(folds):
        standardized = fold.standardizer.standardized_copy(primary)
        training = standardized.select_drive_ids(fold.training_drive_ids)
        test = standardized.select_drive_ids((fold.held_out_drive_id,))
        physical_test = primary.select_drive_ids((fold.held_out_drive_id,))
        model, fit_report, fitted_restart_rows = _fit_restarts(
            training,
            base_config=config,
            restart_count=restart_count,
            seed_offset=fold_index * restart_count * RESTART_SEED_STRIDE,
            scope="primary_held_out_drive_fold",
            fold_id=fold.fold_id,
            held_out_drive_id=fold.held_out_drive_id,
        )
        restart_rows.extend(fitted_restart_rows)
        (
            log_standardized,
            log_physical,
            samples,
            evaluation,
            posterior,
            posterior_statistics,
            transition_diagnostics,
        ) = _evaluate_model(
            model,
            standardized_test=test,
            physical_test=physical_test,
            standardizer=fold.standardizer,
            sample_count=sample_count,
            seed=sample_seed + fold_index,
        )
        evaluation_rows.append(
            _expanded_evaluation_row(
                scope="held_out_drive",
                cohort_role="clean_sensor_primary",
                held_out_drive_id=fold.held_out_drive_id,
                training_drive_ids=fold.training_drive_ids,
                test_drive_ids=(fold.held_out_drive_id,),
                training_sequence_count=training.sequence_count,
                training_frame_count=training.frame_count,
                test=physical_test,
                sample_count=sample_count,
                state_count=config.state_count,
                restart_count=restart_count,
                log_standardized=log_standardized,
                log_physical=log_physical,
                evaluation=evaluation,
                posterior_statistics=posterior_statistics,
                transition_diagnostics=transition_diagnostics,
                autoregressive_coefficients=model.autoregressive_coefficients,
            )
        )
        station_rows.extend(
            _expanded_station_rows(
                scope="held_out_drive",
                cohort_role="clean_sensor_primary",
                held_out_drive_id=fold.held_out_drive_id,
                test_frame_count=physical_test.frame_count,
                evaluation=evaluation,
                autoregressive_station_summary=np.median(
                    model.autoregressive_coefficients, axis=0
                ),
            )
        )
        state_rows.extend(
            _expanded_state_rows(
                scope="held_out_drive_test_posterior",
                cohort_role="clean_sensor_primary",
                fold_id=fold.fold_id,
                held_out_drive_id=fold.held_out_drive_id,
                model=model,
                posterior_occupancies=posterior_statistics["occupancies"],
                transition_diagnostics=transition_diagnostics,
            )
        )
        indices = np.flatnonzero(primary.drive_ids == fold.held_out_drive_id)
        combined_samples[:, indices] = samples.values
        combined_log_standardized[indices] = log_standardized
        combined_log_physical[indices] = log_physical
        combined_posterior[indices] = posterior
        fold_autoregression.append(model.autoregressive_coefficients)
        fold_models[fold.fold_id] = {
            "held_out_drive_id": fold.held_out_drive_id,
            "training_drive_ids": list(fold.training_drive_ids),
            "standardizer": fold.standardizer.to_dict(),
            "held_out_drive_not_used_for_restart_selection": True,
            "fit_report": _fit_report_payload(fit_report),
            "model": model.to_dict(),
        }

    pooled_samples = SampleResult(
        values=combined_samples,
        lengths=primary.lengths,
        stations_m=CANONICAL_MODEL_STATIONS_M,
        standardized=False,
        valid_mask=primary.valid_mask,
    )
    pooled_evaluation = evaluate_sequence_samples(primary, pooled_samples)
    pooled_posterior_statistics = _posterior_statistics(
        combined_posterior, primary.time_mask
    )
    fold_rows = [row for row in evaluation_rows if row["scope"] == "held_out_drive"]
    aggregate_transition = _aggregate_transition_diagnostics(fold_rows)
    all_fold_ar = np.concatenate(fold_autoregression, axis=0)
    pooled_row = _expanded_evaluation_row(
        scope="overall_cross_validated",
        cohort_role="clean_sensor_primary",
        held_out_drive_id=None,
        training_drive_ids=(),
        test_drive_ids=source.clean_drive_ids,
        training_sequence_count=None,
        training_frame_count=None,
        test=primary,
        sample_count=sample_count,
        state_count=config.state_count,
        restart_count=restart_count,
        log_standardized=combined_log_standardized,
        log_physical=combined_log_physical,
        evaluation=pooled_evaluation,
        posterior_statistics=pooled_posterior_statistics,
        transition_diagnostics=aggregate_transition,
        autoregressive_coefficients=all_fold_ar,
    )
    evaluation_rows.append(pooled_row)
    station_rows.extend(
        _expanded_station_rows(
            scope="overall_cross_validated",
            cohort_role="clean_sensor_primary",
            held_out_drive_id=None,
            test_frame_count=primary.frame_count,
            evaluation=pooled_evaluation,
            autoregressive_station_summary=np.median(all_fold_ar, axis=0),
        )
    )
    frame_rows = _frame_rows(
        scope="overall_cross_validated",
        cohort_role="clean_sensor_primary",
        dataset=primary,
        provenance=provenance,
        log_standardized=combined_log_standardized,
        log_physical=combined_log_physical,
        evaluation=pooled_evaluation,
        posterior=combined_posterior,
    )
    del combined_samples, pooled_samples

    all_clean_standardizer = SequenceStandardizer.fit(
        source.sequences, train_drive_ids=source.clean_drive_ids
    )
    all_standardized = all_clean_standardizer.standardized_copy(source.sequences)
    clean_training = all_standardized.select_drive_ids(source.clean_drive_ids)
    mixed_test = all_standardized.select_drive_ids(source.mixed_drive_ids)
    final_model, final_report, final_restart_rows = _fit_restarts(
        clean_training,
        base_config=config,
        restart_count=restart_count,
        seed_offset=len(folds) * restart_count * RESTART_SEED_STRIDE,
        scope="descriptive_all_clean_development_data",
        fold_id="all_clean_development_data",
        held_out_drive_id=None,
    )
    restart_rows.extend(final_restart_rows)
    (
        mixed_log_standardized,
        mixed_log_physical,
        _mixed_samples,
        mixed_evaluation,
        mixed_posterior,
        mixed_posterior_statistics,
        mixed_transition_diagnostics,
    ) = _evaluate_model(
        final_model,
        standardized_test=mixed_test,
        physical_test=supplementary,
        standardizer=all_clean_standardizer,
        sample_count=sample_count,
        seed=sample_seed + 1000,
    )
    mixed_row = _expanded_evaluation_row(
        scope="supplementary_mixed_transfer",
        cohort_role="mixed_source_fragments_supplementary",
        held_out_drive_id=None,
        training_drive_ids=source.clean_drive_ids,
        test_drive_ids=source.mixed_drive_ids,
        training_sequence_count=clean_training.sequence_count,
        training_frame_count=clean_training.frame_count,
        test=supplementary,
        sample_count=sample_count,
        state_count=config.state_count,
        restart_count=restart_count,
        log_standardized=mixed_log_standardized,
        log_physical=mixed_log_physical,
        evaluation=mixed_evaluation,
        posterior_statistics=mixed_posterior_statistics,
        transition_diagnostics=mixed_transition_diagnostics,
        autoregressive_coefficients=final_model.autoregressive_coefficients,
    )
    evaluation_rows.append(mixed_row)
    station_rows.extend(
        _expanded_station_rows(
            scope="supplementary_mixed_transfer",
            cohort_role="mixed_source_fragments_supplementary",
            held_out_drive_id=None,
            test_frame_count=supplementary.frame_count,
            evaluation=mixed_evaluation,
            autoregressive_station_summary=np.median(
                final_model.autoregressive_coefficients, axis=0
            ),
        )
    )
    state_rows.extend(
        _expanded_state_rows(
            scope="supplementary_mixed_test_posterior",
            cohort_role="mixed_source_fragments_supplementary",
            fold_id="all_clean_development_data",
            held_out_drive_id=None,
            model=final_model,
            posterior_occupancies=mixed_posterior_statistics["occupancies"],
            transition_diagnostics=mixed_transition_diagnostics,
        )
    )
    frame_rows.extend(
        _frame_rows(
            scope="supplementary_mixed_transfer",
            cohort_role="mixed_source_fragments_supplementary",
            dataset=supplementary,
            provenance=provenance,
            log_standardized=mixed_log_standardized,
            log_physical=mixed_log_physical,
            evaluation=mixed_evaluation,
            posterior=mixed_posterior,
        )
    )
    final_posterior = _posterior_tensor(
        clean_training,
        final_model.posterior_state_probabilities(clean_training),
        state_count=config.state_count,
    )
    final_posterior_statistics = _posterior_statistics(
        final_posterior, clean_training.time_mask
    )
    final_transition_diagnostics = _transition_diagnostics(final_model, clean_training)
    state_rows.extend(
        _expanded_state_rows(
            scope="descriptive_all_clean_fit",
            cohort_role="clean_sensor_primary",
            fold_id="all_clean_development_data",
            held_out_drive_id=None,
            model=final_model,
            posterior_occupancies=final_posterior_statistics["occupancies"],
            transition_diagnostics=final_transition_diagnostics,
        )
    )

    write_csv_rows(
        arguments.output_directory / "expanded_aiohmm_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "expanded_aiohmm_station_evaluation.csv",
        STATION_FIELDS,
        station_rows,
    )
    write_csv_rows(
        arguments.output_directory / "expanded_aiohmm_frame_evaluation.csv",
        FRAME_FIELDS,
        frame_rows,
    )
    write_csv_rows(
        arguments.output_directory / "expanded_aiohmm_state_evaluation.csv",
        STATE_FIELDS,
        state_rows,
    )
    write_csv_rows(
        arguments.output_directory / "expanded_aiohmm_restart_evaluation.csv",
        RESTART_FIELDS,
        restart_rows,
    )
    write_strict_json(
        arguments.output_directory / "expanded_aiohmm_fold_models.json",
        {
            "version": VERSION,
            "status": "complete",
            "purpose": "v014_clean_drive_fold_aiohmm_models",
            "state_count_fixed_before_evaluation": True,
            "models": fold_models,
        },
    )
    write_strict_json(
        arguments.output_directory / "expanded_aiohmm_model.json",
        {
            "version": VERSION,
            "status": "complete",
            "role": "descriptive_all_clean_development_fit_after_cross_validation",
            "not_an_untouched_final_model": True,
            "standardizer": all_clean_standardizer.to_dict(),
            "fit_report": _fit_report_payload(final_report),
            "model": final_model.to_dict(),
        },
    )
    plot_sequence_aiohmm_diagnostics(
        arguments.output_directory / "expanded_aiohmm_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        evaluation_rows=evaluation_rows,
        station_rows=station_rows,
        state_rows=state_rows,
        final_transition_matrix=final_transition_diagnostics["mean_matrix"],
        final_autoregressive_coefficients=final_model.autoregressive_coefficients,
        version=VERSION,
        subtitle=(
            "Two-state within-outing recording-group model; state labels are not "
            "physical classes"
        ),
        held_out_metric_title="Recording-group-held-out sample metrics",
    )

    macro = _macro_metrics(fold_rows)
    gaussian_macro = gaussian_summary["models"]["conditional_gaussian"][
        "primary_macro_drive_metrics"
    ]
    comparison = {
        "mean_joint_negative_log_likelihood_physical": (
            macro["mean_joint_negative_log_likelihood_physical"]
            - float(gaussian_macro["mean_frame_negative_log_likelihood_physical"])
        ),
        "sample_mean_prediction_rmse_m": (
            macro["sample_mean_prediction_rmse_m"]
            - float(gaussian_macro["sample_mean_prediction_rmse_m"])
        ),
        "mean_energy_score_m": (
            macro["mean_energy_score_m"]
            - float(gaussian_macro["mean_energy_score_m"])
        ),
        "mean_normalized_sequence_energy_score_m": (
            macro["mean_normalized_sequence_energy_score_m"]
            - float(gaussian_macro["mean_normalized_sequence_energy_score_m"])
        ),
        "absolute_marginal_95_coverage_error": (
            macro["absolute_marginal_95_coverage_error"]
            - float(gaussian_macro["absolute_marginal_95_coverage_error"])
        ),
        "median_absolute_lag_one_correlation_error": (
            macro["median_absolute_lag_one_correlation_error"]
            - float(gaussian_macro["median_absolute_lag_one_correlation_error"])
        ),
    }
    output_names = (
        "expanded_aiohmm_evaluation.csv",
        "expanded_aiohmm_station_evaluation.csv",
        "expanded_aiohmm_frame_evaluation.csv",
        "expanded_aiohmm_state_evaluation.csv",
        "expanded_aiohmm_restart_evaluation.csv",
        "expanded_aiohmm_fold_models.json",
        "expanded_aiohmm_model.json",
        "expanded_aiohmm_diagnostics.png",
    )
    failed_restart_count = sum(row["status"] == "failed" for row in restart_rows)
    selected_nonconverged_count = sum(
        row["status"] == "complete"
        and bool(row["selected"])
        and not bool(row["em_converged"])
        for row in restart_rows
    )
    acceptance_checks = {
        "frame_energy_score_improved": comparison["mean_energy_score_m"] < 0.0,
        "sequence_energy_score_improved": (
            comparison["mean_normalized_sequence_energy_score_m"] < 0.0
        ),
        "lag_one_error_improved": (
            comparison["median_absolute_lag_one_correlation_error"] < 0.0
        ),
        "coverage_error_not_worse": (
            comparison["absolute_marginal_95_coverage_error"] <= 0.0
        ),
        "no_failed_restart": failed_restart_count == 0,
        "all_selected_fits_converged": selected_nonconverged_count == 0,
    }
    sequence_energy_fold_diagnostics = _sequence_energy_fold_diagnostics(
        fold_rows, gaussian_evaluation_rows
    )
    constraint_boundary_diagnostics = _constraint_boundary_diagnostics(
        restart_rows,
        minimum_occupancy=config.minimum_state_occupancy_fraction,
        maximum_autoregression=config.maximum_absolute_autoregression,
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "expanded_clean_drive_autoregressive_input_output_hmm",
        "project_role": "canonical_thesis_implementation",
        "source_dataset_version": "0.13.1",
        "source_files_sha256": dict(source.source_files_sha256),
        "gaussian_baseline_version": "0.14.0",
        "gaussian_baseline_files_sha256": gaussian_hashes,
        "gaussian_protocol_sha256": gaussian_hashes[
            "drive_grouped_evaluation_contract.json"
        ],
        "output_files_sha256": {
            name: sha256_file(arguments.output_directory / name)
            for name in output_names
        },
        "primary_clean_drive_ids": list(source.clean_drive_ids),
        "primary_sequence_count": primary.sequence_count,
        "primary_frame_count": primary.frame_count,
        "supplementary_mixed_drive_ids": list(source.mixed_drive_ids),
        "supplementary_sequence_count": supplementary.sequence_count,
        "supplementary_frame_count": supplementary.frame_count,
        "evaluation_scheme": "leave_one_clean_recording_group_out_within_one_outing",
        "legacy_v014_evaluation_scheme_label": gaussian_summary["evaluation_scheme"],
        "primary_group_independence": {
            "technical_group_count": len(source.clean_drive_ids),
            "independent_journey_count": 1,
            "groups_are_separated_portions_of_one_longer_same_day_outing": True,
            "journey_level_generalization_estimated": False,
        },
        "same_folds_transforms_and_metrics_as_v0140_gaussian": True,
        "random_frame_splits_used": False,
        "state_count": config.state_count,
        "state_count_rationale": (
            "fixed_two_state_parsimony_after_v0110_three_state_occupancy_collapse"
        ),
        "automatic_state_count_selection_performed": False,
        "held_out_drives_used_for_state_count_or_restart_selection": False,
        "restart_count_per_fit": restart_count,
        "restart_selection_criterion": (
            "highest_training_joint_log_probability_same_fixed_architecture"
        ),
        "configuration": config.to_dict(),
        "failed_restart_count": failed_restart_count,
        "selected_fit_nonconvergence_count": selected_nonconverged_count,
        "sample_count": sample_count,
        "sampling_random_seed": sample_seed,
        "joint_likelihood_is_proper_observed_history_density_score": True,
        "joint_likelihood_uses_observed_previous_target": True,
        "joint_likelihood_measures_free_running_generation": False,
        "sampling_is_free_running": True,
        "normalized_sequence_energy_score_definition": (
            "energy score on each flattened [time,21] sequence with Euclidean "
            "distances divided by sqrt(sequence_length*21), then averaged"
        ),
        "primary_pooled_cross_validated_metrics": _metric_subset(pooled_row),
        "primary_macro_drive_metrics": macro,
        "supplementary_mixed_transfer_metrics": _metric_subset(mixed_row),
        "aiohmm_minus_conditional_gaussian_primary_macro_deltas": comparison,
        "density_metric_deltas": {
            "mean_joint_negative_log_likelihood_physical": comparison[
                "mean_joint_negative_log_likelihood_physical"
            ]
        },
        "sample_based_metric_deltas": {
            key: value
            for key, value in comparison.items()
            if key != "mean_joint_negative_log_likelihood_physical"
        },
        "delta_interpretation": "negative_is_better_for_every_reported_delta",
        "sequence_energy_fold_diagnostics": sequence_energy_fold_diagnostics,
        "sequence_energy_gate_interpretation": (
            "predeclared binary gate is retained; descriptive fold evidence is "
            "underpowered and does not estimate independent-journey generalization"
        ),
        "constraint_boundary_diagnostics": constraint_boundary_diagnostics,
        "development_acceptance_checks": acceptance_checks,
        "all_development_acceptance_checks_passed": all(
            acceptance_checks.values()
        ),
        "result_classification": _result_classification(acceptance_checks),
        "mixed_source_results_are_supplementary_only": True,
        "state_labels_are_physical_classes": False,
        "temporal_dependency_order": 1,
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "next_phase": "review_v015_against_v014_before_any_rcgan_or_feature_expansion",
        "scientific_limitations": [
            (
                "The four clean technical groups are separated portions of one "
                "longer same-day outing, not four independent journeys."
            ),
            "Leave-one-group-out results do not estimate journey-level generalization.",
            "Two states are a fixed parsimonious correction, not a held-out selected optimum.",
            (
                "Observed-history joint density and free-running generation are both "
                "valid but answer different questions."
            ),
            (
                "RLMB remains a pseudo-reference and independence from the EDP "
                "topology source is unknown."
            ),
            "Sample metrics retain finite Monte Carlo error under the recorded seed.",
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "expanded_aiohmm_summary.json", summary
    )
    return summary, 0


__all__ = [
    "EVALUATION_FIELDS",
    "FRAME_FIELDS",
    "STATE_FIELDS",
    "STATION_FIELDS",
    "VERSION",
    "run_expanded_aiohmm",
]
