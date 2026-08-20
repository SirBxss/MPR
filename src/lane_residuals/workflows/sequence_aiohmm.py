"""Drive-held-out v0.11.0 AIOHMM workflow on the common sequence contract."""

from __future__ import annotations

import argparse
from dataclasses import replace
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import PaddedSequenceDataset, SequenceStandardizer
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.aiohmm import AIOHMMConfig, AutoregressiveInputOutputHMM
from ..modeling.base import FitReport, SampleResult
from ..modeling.sequence_evaluation import (
    SequenceSampleEvaluation,
    evaluate_sequence_samples,
    physical_sample_result,
)
from ..visualization.sequence_aiohmm import plot_sequence_aiohmm_diagnostics
from .sequence_contract import (
    REQUIRED_INPUT_FILES,
    ensure_empty_output_directory,
    load_validated_sequence_sources,
    sha256_file,
    validated_fold_contracts,
)

LOGGER = logging.getLogger(__name__)
VERSION = "0.11.0"
RESTART_SEED_STRIDE = 1009

EVALUATION_FIELDS = (
    "scope",
    "held_out_drive_id",
    "training_drive_ids",
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
    "marginal_95_coverage",
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

FRAME_FIELDS = (
    "sequence_id",
    "sequence_frame_index",
    "recording_id",
    "drive_id",
    "pair_index",
    "joint_filter_negative_log_likelihood_standardized",
    "joint_filter_negative_log_likelihood_physical",
    "sample_mean_prediction_rmse_m",
    "energy_score_m",
    "maximum_posterior_state_index",
    "maximum_posterior_state_probability",
    "posterior_state_entropy_nats",
)

STATE_FIELDS = (
    "scope",
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

RESTART_FIELDS = (
    "scope",
    "fold_id",
    "held_out_drive_id",
    "restart_index",
    "initialization_seed",
    "status",
    "selected",
    "selection_criterion",
    "training_joint_log_probability_standardized",
    "training_mean_joint_negative_log_likelihood_standardized",
    "em_iteration_count",
    "em_best_iteration_index",
    "em_converged",
    "minimum_state_occupancy_fraction",
    "maximum_absolute_autoregressive_coefficient",
    "transition_matrix_rms_difference_from_selected",
    "state_occupancy_l1_difference_from_selected",
    "warning_count",
    "error_message",
)


def _configuration(arguments: argparse.Namespace) -> AIOHMMConfig:
    """Create and validate one fixed architecture configuration from CLI values."""

    return AIOHMMConfig(
        state_count=arguments.state_count,
        maximum_em_iterations=arguments.maximum_em_iterations,
        minimum_em_iterations=arguments.minimum_em_iterations,
        convergence_tolerance=arguments.convergence_tolerance,
        regression_ridge_penalty=arguments.regression_ridge_penalty,
        emission_parameter_pooling_penalty=(
            arguments.emission_parameter_pooling_penalty
        ),
        state_covariance_pooling=arguments.state_covariance_pooling,
        covariance_diagonal_shrinkage=(
            arguments.covariance_diagonal_shrinkage
        ),
        covariance_minimum_eigenvalue=(
            arguments.covariance_minimum_eigenvalue
        ),
        minimum_effective_state_observations=(
            arguments.minimum_effective_state_observations
        ),
        maximum_absolute_autoregression=(
            arguments.maximum_absolute_autoregression
        ),
        transition_l2_penalty=arguments.transition_l2_penalty,
        transition_learning_rate=arguments.transition_learning_rate,
        transition_adam_steps=arguments.transition_adam_steps,
        initial_probability_smoothing=arguments.initial_probability_smoothing,
        minimum_state_occupancy_fraction=(
            arguments.minimum_state_occupancy_fraction
        ),
        initialization_seed=arguments.initialization_seed,
        input_dependent_transitions=True,
    )


def _fit_report_payload(report: FitReport) -> dict[str, Any]:
    return {
        "training_sequence_count": report.training_sequence_count,
        "validation_sequence_count": report.validation_sequence_count,
        "metrics": dict(report.metrics),
        "warnings": list(report.warnings),
    }


def _fit_restarts(
    training: PaddedSequenceDataset,
    *,
    base_config: AIOHMMConfig,
    restart_count: int,
    seed_offset: int,
    scope: str,
    fold_id: str,
    held_out_drive_id: str | None,
) -> tuple[
    AutoregressiveInputOutputHMM,
    FitReport,
    list[dict[str, Any]],
]:
    """Fit same-architecture restarts and select only by training likelihood."""

    successful: list[
        tuple[
            int,
            AutoregressiveInputOutputHMM,
            FitReport,
            float,
            np.ndarray,
            np.ndarray,
        ]
    ] = []
    rows: list[dict[str, Any]] = []
    for restart_index in range(restart_count):
        initialization_seed = (
            base_config.initialization_seed
            + seed_offset
            + restart_index * RESTART_SEED_STRIDE
        )
        config = replace(base_config, initialization_seed=initialization_seed)
        LOGGER.info(
            "fitting %s restart %d/%d (seed=%d)",
            fold_id,
            restart_index + 1,
            restart_count,
            initialization_seed,
        )
        try:
            model = AutoregressiveInputOutputHMM(config)
            report = model.fit(training)
            joint_log_probability = float(
                np.sum(model.sequence_log_probability(training))
            )
            transition_mean, _transition_std, _count = (
                model.transition_probability_summary(
                    training.conditions, training.lengths
                )
            )
            occupancies = model.state_occupancies
            successful.append(
                (
                    restart_index,
                    model,
                    report,
                    joint_log_probability,
                    transition_mean,
                    occupancies,
                )
            )
            rows.append(
                {
                    "scope": scope,
                    "fold_id": fold_id,
                    "held_out_drive_id": held_out_drive_id,
                    "restart_index": restart_index,
                    "initialization_seed": initialization_seed,
                    "status": "complete",
                    "selected": False,
                    "selection_criterion": (
                        "highest_training_joint_log_probability_same_fixed_architecture"
                    ),
                    "training_joint_log_probability_standardized": (
                        joint_log_probability
                    ),
                    "training_mean_joint_negative_log_likelihood_standardized": (
                        report.metrics[
                            "training_mean_joint_negative_log_likelihood_standardized"
                        ]
                    ),
                    "em_iteration_count": report.metrics["em_iteration_count"],
                    "em_best_iteration_index": report.metrics[
                        "em_best_iteration_index"
                    ],
                    "em_converged": bool(report.metrics["em_converged"]),
                    "minimum_state_occupancy_fraction": report.metrics[
                        "minimum_state_occupancy_fraction"
                    ],
                    "maximum_absolute_autoregressive_coefficient": report.metrics[
                        "maximum_absolute_autoregressive_coefficient"
                    ],
                    "transition_matrix_rms_difference_from_selected": None,
                    "state_occupancy_l1_difference_from_selected": None,
                    "warning_count": len(report.warnings),
                    "error_message": None,
                }
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            rows.append(
                {
                    "scope": scope,
                    "fold_id": fold_id,
                    "held_out_drive_id": held_out_drive_id,
                    "restart_index": restart_index,
                    "initialization_seed": initialization_seed,
                    "status": "failed",
                    "selected": False,
                    "selection_criterion": (
                        "highest_training_joint_log_probability_same_fixed_architecture"
                    ),
                    "training_joint_log_probability_standardized": None,
                    "training_mean_joint_negative_log_likelihood_standardized": None,
                    "em_iteration_count": None,
                    "em_best_iteration_index": None,
                    "em_converged": None,
                    "minimum_state_occupancy_fraction": None,
                    "maximum_absolute_autoregressive_coefficient": None,
                    "transition_matrix_rms_difference_from_selected": None,
                    "state_occupancy_l1_difference_from_selected": None,
                    "warning_count": 0,
                    "error_message": str(error),
                }
            )
    if not successful:
        errors = [str(row["error_message"]) for row in rows]
        raise ValueError(f"all AIOHMM restarts failed for {fold_id}: {errors}")
    selected = max(successful, key=lambda values: values[3])
    selected_index, selected_model, selected_report, _score, selected_transition, selected_occupancy = selected
    successful_by_index = {values[0]: values for values in successful}
    for row in rows:
        restart_index = int(row["restart_index"])
        if row["status"] != "complete":
            continue
        values = successful_by_index[restart_index]
        row["selected"] = restart_index == selected_index
        row["transition_matrix_rms_difference_from_selected"] = float(
            np.sqrt(np.mean(np.square(values[4] - selected_transition)))
        )
        row["state_occupancy_l1_difference_from_selected"] = float(
            np.sum(np.abs(values[5] - selected_occupancy))
        )
    return selected_model, selected_report, rows


def _posterior_tensor(
    dataset: PaddedSequenceDataset,
    posteriors: Sequence[np.ndarray],
    *,
    state_count: int,
) -> np.ndarray:
    if len(posteriors) != dataset.sequence_count:
        raise ValueError("posterior sequence count differs from the dataset")
    values = np.zeros(
        (*dataset.time_mask.shape, state_count), dtype=np.float64
    )
    for sequence_index, (posterior, raw_length) in enumerate(
        zip(posteriors, dataset.lengths)
    ):
        length = int(raw_length)
        if posterior.shape != (length, state_count):
            raise ValueError("posterior state tensor has an invalid shape")
        values[sequence_index, :length] = posterior
    return values


def _posterior_statistics(
    posterior: np.ndarray,
    time_mask: np.ndarray,
) -> dict[str, Any]:
    active = posterior[time_mask]
    if len(active) < 1 or not np.allclose(np.sum(active, axis=1), 1.0, atol=1e-8):
        raise ValueError("posterior probabilities do not cover active frames")
    entropy = -np.sum(active * np.log(np.maximum(active, 1e-300)), axis=1)
    occupancies = np.mean(active, axis=0)
    return {
        "entropy": entropy,
        "mean_entropy": float(np.mean(entropy)),
        "mean_maximum_probability": float(np.mean(np.max(active, axis=1))),
        "occupancies": occupancies,
        "minimum_occupancy": float(np.min(occupancies)),
        "maximum_occupancy": float(np.max(occupancies)),
    }


def _transition_diagnostics(
    model: AutoregressiveInputOutputHMM,
    dataset: PaddedSequenceDataset,
) -> dict[str, Any]:
    mean_matrix, standard_deviation_matrix, transition_count = (
        model.transition_probability_summary(dataset.conditions, dataset.lengths)
    )
    self_transition = np.diag(mean_matrix)
    dwell = 1.0 / np.maximum(1.0 - self_transition, 1e-12)
    return {
        "mean_matrix": mean_matrix,
        "standard_deviation_matrix": standard_deviation_matrix,
        "transition_count": transition_count,
        "mean_self_transition_probability": float(np.mean(self_transition)),
        "mean_transition_probability_standard_deviation": float(
            np.mean(standard_deviation_matrix)
        ),
        "minimum_expected_dwell_frames": float(np.min(dwell)),
        "maximum_expected_dwell_frames": float(np.max(dwell)),
        "dwell_frames": dwell,
    }


def _evaluation_row(
    *,
    scope: str,
    held_out_drive_id: str | None,
    training_drive_ids: Sequence[str],
    training_sequence_count: int | None,
    training_frame_count: int | None,
    test_sequence_count: int,
    test_frame_count: int,
    sample_count: int,
    state_count: int,
    restart_count: int,
    log_probability_standardized: np.ndarray,
    log_probability_physical: np.ndarray,
    sample_evaluation: SequenceSampleEvaluation,
    posterior_statistics: Mapping[str, Any],
    transition_diagnostics: Mapping[str, Any],
    autoregressive_coefficients: np.ndarray,
) -> dict[str, Any]:
    generated_median = sample_evaluation.generated_median_lag_one_correlation
    return {
        "scope": scope,
        "held_out_drive_id": held_out_drive_id,
        "training_drive_ids": ";".join(training_drive_ids),
        "training_sequence_count": training_sequence_count,
        "training_frame_count": training_frame_count,
        "test_sequence_count": test_sequence_count,
        "test_frame_count": test_frame_count,
        "sample_count": sample_count,
        "state_count": state_count,
        "restart_count": restart_count,
        "mean_joint_negative_log_likelihood_standardized": float(
            -np.mean(log_probability_standardized)
        ),
        "mean_joint_negative_log_likelihood_physical": float(
            -np.mean(log_probability_physical)
        ),
        "sample_mean_prediction_rmse_m": (
            sample_evaluation.pooled_mean_prediction_rmse_m
        ),
        "mean_energy_score_m": sample_evaluation.mean_energy_score_m,
        "marginal_95_coverage": sample_evaluation.marginal_95_coverage,
        "median_observed_lag_one_correlation": float(
            np.median(sample_evaluation.observed_lag_one_correlation)
        ),
        "median_generated_lag_one_correlation": float(
            np.median(generated_median)
        ),
        "median_absolute_lag_one_correlation_error": (
            sample_evaluation.median_absolute_lag_one_correlation_error
        ),
        "mean_posterior_state_entropy_nats": posterior_statistics[
            "mean_entropy"
        ],
        "mean_maximum_posterior_state_probability": posterior_statistics[
            "mean_maximum_probability"
        ],
        "minimum_posterior_state_occupancy": posterior_statistics[
            "minimum_occupancy"
        ],
        "maximum_posterior_state_occupancy": posterior_statistics[
            "maximum_occupancy"
        ],
        "mean_self_transition_probability": transition_diagnostics[
            "mean_self_transition_probability"
        ],
        "mean_transition_probability_standard_deviation": (
            transition_diagnostics[
                "mean_transition_probability_standard_deviation"
            ]
        ),
        "minimum_expected_dwell_frames": transition_diagnostics[
            "minimum_expected_dwell_frames"
        ],
        "maximum_expected_dwell_frames": transition_diagnostics[
            "maximum_expected_dwell_frames"
        ],
        "minimum_autoregressive_coefficient": float(
            np.min(autoregressive_coefficients)
        ),
        "median_autoregressive_coefficient": float(
            np.median(autoregressive_coefficients)
        ),
        "maximum_autoregressive_coefficient": float(
            np.max(autoregressive_coefficients)
        ),
        "temporal_dependency_order": 1,
    }


def _station_rows(
    *,
    scope: str,
    held_out_drive_id: str | None,
    test_frame_count: int,
    evaluation: SequenceSampleEvaluation,
    autoregressive_station_summary: np.ndarray,
) -> list[dict[str, Any]]:
    generated = evaluation.generated_lag_one_correlation_by_sample
    generated_median = np.median(generated, axis=0)
    if autoregressive_station_summary.shape != (
        len(CANONICAL_MODEL_STATIONS_M),
    ):
        raise ValueError("autoregressive station summary does not cover H100")
    return [
        {
            "scope": scope,
            "held_out_drive_id": held_out_drive_id,
            "station_m": station,
            "test_frame_count": test_frame_count,
            "sample_mean_prediction_rmse_m": evaluation.station_rmse_m[index],
            "sample_mean_prediction_bias_m": evaluation.station_bias_m[index],
            "marginal_95_coverage": evaluation.station_coverage_95[index],
            "observed_lag_one_correlation": (
                evaluation.observed_lag_one_correlation[index]
            ),
            "generated_median_lag_one_correlation": generated_median[index],
            "generated_p05_lag_one_correlation": np.quantile(
                generated[:, index], 0.05
            ),
            "generated_p95_lag_one_correlation": np.quantile(
                generated[:, index], 0.95
            ),
            "absolute_lag_one_correlation_error": abs(
                generated_median[index]
                - evaluation.observed_lag_one_correlation[index]
            ),
            "median_model_autoregressive_coefficient": (
                autoregressive_station_summary[index]
            ),
        }
        for index, station in enumerate(CANONICAL_MODEL_STATIONS_M)
    ]


def _state_rows(
    *,
    scope: str,
    fold_id: str,
    held_out_drive_id: str | None,
    model: AutoregressiveInputOutputHMM,
    posterior_occupancies: np.ndarray,
    transition_diagnostics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mean_matrix = np.asarray(transition_diagnostics["mean_matrix"])
    standard_deviation_matrix = np.asarray(
        transition_diagnostics["standard_deviation_matrix"]
    )
    dwell = np.asarray(transition_diagnostics["dwell_frames"])
    autoregression = model.autoregressive_coefficients
    covariances = model.covariances
    profile_rms = model.state_profile_rms_standardized
    initial = model.initial_probabilities
    training_occupancy = model.state_occupancies
    rows: list[dict[str, Any]] = []
    for state_index in range(model.config.state_count):
        row_probabilities = mean_matrix[state_index]
        transition_entropy = -np.sum(
            row_probabilities
            * np.log(np.maximum(row_probabilities, 1e-300))
        )
        rows.append(
            {
                "scope": scope,
                "fold_id": fold_id,
                "held_out_drive_id": held_out_drive_id,
                "state_index": state_index,
                "state_label_interpretation": (
                    "canonical_diagnostic_label_not_physical_class"
                ),
                "posterior_state_occupancy": posterior_occupancies[state_index],
                "training_state_occupancy": training_occupancy[state_index],
                "initial_probability": initial[state_index],
                "zero_condition_intercept_profile_rms_standardized": (
                    profile_rms[state_index]
                ),
                "minimum_autoregressive_coefficient": np.min(
                    autoregression[state_index]
                ),
                "median_autoregressive_coefficient": np.median(
                    autoregression[state_index]
                ),
                "maximum_autoregressive_coefficient": np.max(
                    autoregression[state_index]
                ),
                "minimum_covariance_eigenvalue_standardized2": np.min(
                    np.linalg.eigvalsh(covariances[state_index])
                ),
                "mean_self_transition_probability": mean_matrix[
                    state_index, state_index
                ],
                "self_transition_probability_standard_deviation": (
                    standard_deviation_matrix[state_index, state_index]
                ),
                "expected_dwell_frames_from_mean_self_transition": dwell[
                    state_index
                ],
                "mean_transition_row_entropy_nats": transition_entropy,
            }
        )
    return rows


def run_sequence_aiohmm(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Fit and evaluate the fixed-development AIOHMM without held-out tuning."""

    config = _configuration(arguments)
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
    if (
        isinstance(restart_count, bool)
        or not isinstance(restart_count, int)
        or restart_count < 1
    ):
        raise ValueError("restart-count must be a positive integer")

    dataset, source_summary, manifest, standardizer_payload = (
        load_validated_sequence_sources(arguments.sequential_dataset_directory)
    )
    fold_contracts = validated_fold_contracts(
        dataset, manifest, standardizer_payload
    )
    ensure_empty_output_directory(arguments.output_directory)

    combined_sample_values = np.zeros(
        (sample_count, *dataset.residuals_m.shape), dtype=np.float64
    )
    combined_log_standardized = np.zeros(
        dataset.time_mask.shape, dtype=np.float64
    )
    combined_log_physical = np.zeros_like(combined_log_standardized)
    combined_posterior = np.zeros(
        (*dataset.time_mask.shape, config.state_count), dtype=np.float64
    )
    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    restart_rows: list[dict[str, Any]] = []
    fold_models: dict[str, Any] = {}
    fold_autoregression: list[np.ndarray] = []

    for fold_index, (fold, standardizer) in enumerate(fold_contracts):
        fold_id = str(fold["fold_id"])
        held_out = str(fold["held_out_drive_id"])
        training_drives = tuple(
            str(value) for value in fold["training_drive_ids"]
        )
        LOGGER.info(
            "evaluating %s: train=%s, held-out=%s",
            fold_id,
            ",".join(training_drives),
            held_out,
        )
        standardized = standardizer.standardized_copy(dataset)
        training = standardized.select_drive_ids(training_drives)
        test = standardized.select_drive_ids((held_out,))
        raw_test = dataset.select_drive_ids((held_out,))
        model, fit_report, fold_restart_rows = _fit_restarts(
            training,
            base_config=config,
            restart_count=restart_count,
            seed_offset=fold_index * restart_count * RESTART_SEED_STRIDE,
            scope="held_out_drive_fold",
            fold_id=fold_id,
            held_out_drive_id=held_out,
        )
        restart_rows.extend(fold_restart_rows)
        log_standardized = model.log_probability(test)
        jacobian = float(np.sum(np.log(standardizer.residual_scale_m)))
        log_physical = np.zeros_like(log_standardized)
        log_physical[test.time_mask] = (
            log_standardized[test.time_mask] - jacobian
        )
        standardized_samples = model.sample(
            test.conditions,
            test.lengths,
            sample_count=sample_count,
            seed=sample_seed + fold_index,
            valid_mask=test.valid_mask,
        )
        physical_samples = physical_sample_result(
            standardized_samples, standardizer
        )
        sample_evaluation = evaluate_sequence_samples(
            raw_test, physical_samples
        )
        posterior = _posterior_tensor(
            test,
            model.posterior_state_probabilities(test),
            state_count=config.state_count,
        )
        posterior_statistics = _posterior_statistics(
            posterior, test.time_mask
        )
        transition_diagnostics = _transition_diagnostics(model, test)
        evaluation_rows.append(
            _evaluation_row(
                scope="held_out_drive",
                held_out_drive_id=held_out,
                training_drive_ids=training_drives,
                training_sequence_count=training.sequence_count,
                training_frame_count=training.frame_count,
                test_sequence_count=test.sequence_count,
                test_frame_count=test.frame_count,
                sample_count=sample_count,
                state_count=config.state_count,
                restart_count=restart_count,
                log_probability_standardized=log_standardized[test.time_mask],
                log_probability_physical=log_physical[test.time_mask],
                sample_evaluation=sample_evaluation,
                posterior_statistics=posterior_statistics,
                transition_diagnostics=transition_diagnostics,
                autoregressive_coefficients=(
                    model.autoregressive_coefficients
                ),
            )
        )
        station_rows.extend(
            _station_rows(
                scope="held_out_drive",
                held_out_drive_id=held_out,
                test_frame_count=test.frame_count,
                evaluation=sample_evaluation,
                autoregressive_station_summary=np.median(
                    model.autoregressive_coefficients, axis=0
                ),
            )
        )
        state_rows.extend(
            _state_rows(
                scope="held_out_drive_test_posterior",
                fold_id=fold_id,
                held_out_drive_id=held_out,
                model=model,
                posterior_occupancies=posterior_statistics["occupancies"],
                transition_diagnostics=transition_diagnostics,
            )
        )
        full_indices = np.flatnonzero(dataset.drive_ids == held_out)
        combined_sample_values[:, full_indices] = physical_samples.values
        combined_log_standardized[full_indices] = log_standardized
        combined_log_physical[full_indices] = log_physical
        combined_posterior[full_indices] = posterior
        fold_autoregression.append(model.autoregressive_coefficients)
        fold_models[fold_id] = {
            "held_out_drive_id": held_out,
            "training_drive_ids": list(training_drives),
            "standardizer_source": "drive_fold_standardizers.json",
            "held_out_drive_not_used_for_restart_selection": True,
            "restart_selection": (
                "highest_training_joint_log_probability_same_fixed_architecture"
            ),
            "fit_report": _fit_report_payload(fit_report),
            "model": model.to_dict(),
        }

    combined_samples = SampleResult(
        values=combined_sample_values,
        lengths=dataset.lengths,
        stations_m=CANONICAL_MODEL_STATIONS_M,
        standardized=False,
        valid_mask=dataset.valid_mask,
    )
    overall_evaluation = evaluate_sequence_samples(dataset, combined_samples)
    overall_posterior_statistics = _posterior_statistics(
        combined_posterior, dataset.time_mask
    )
    fold_test_rows = [
        row for row in evaluation_rows if row["scope"] == "held_out_drive"
    ]
    weights = np.asarray(
        [float(row["test_frame_count"]) for row in fold_test_rows],
        dtype=np.float64,
    )
    weights /= np.sum(weights)
    aggregate_transition_diagnostics = {
        key: float(
            np.sum(
                weights
                * np.asarray([float(row[key]) for row in fold_test_rows])
            )
        )
        for key in (
            "mean_self_transition_probability",
            "mean_transition_probability_standard_deviation",
        )
    }
    aggregate_transition_diagnostics["minimum_expected_dwell_frames"] = min(
        float(row["minimum_expected_dwell_frames"]) for row in fold_test_rows
    )
    aggregate_transition_diagnostics["maximum_expected_dwell_frames"] = max(
        float(row["maximum_expected_dwell_frames"]) for row in fold_test_rows
    )
    all_fold_ar = np.concatenate(fold_autoregression, axis=0)
    evaluation_rows.append(
        _evaluation_row(
            scope="overall_cross_validated",
            held_out_drive_id=None,
            training_drive_ids=(),
            training_sequence_count=None,
            training_frame_count=None,
            test_sequence_count=dataset.sequence_count,
            test_frame_count=dataset.frame_count,
            sample_count=sample_count,
            state_count=config.state_count,
            restart_count=restart_count,
            log_probability_standardized=(
                combined_log_standardized[dataset.time_mask]
            ),
            log_probability_physical=combined_log_physical[dataset.time_mask],
            sample_evaluation=overall_evaluation,
            posterior_statistics=overall_posterior_statistics,
            transition_diagnostics=aggregate_transition_diagnostics,
            autoregressive_coefficients=all_fold_ar,
        )
    )
    station_rows.extend(
        _station_rows(
            scope="overall_cross_validated",
            held_out_drive_id=None,
            test_frame_count=dataset.frame_count,
            evaluation=overall_evaluation,
            autoregressive_station_summary=np.median(all_fold_ar, axis=0),
        )
    )

    active_combined_posterior = combined_posterior[dataset.time_mask]
    active_entropy = -np.sum(
        active_combined_posterior
        * np.log(np.maximum(active_combined_posterior, 1e-300)),
        axis=1,
    )
    frame_rows: list[dict[str, Any]] = []
    active_offset = 0
    for sequence_index in range(dataset.sequence_count):
        length = int(dataset.lengths[sequence_index])
        for frame_index in range(length):
            probabilities = combined_posterior[sequence_index, frame_index]
            frame_rows.append(
                {
                    "sequence_id": dataset.sequence_ids[sequence_index],
                    "sequence_frame_index": frame_index,
                    "recording_id": dataset.recording_ids[sequence_index],
                    "drive_id": dataset.drive_ids[sequence_index],
                    "pair_index": dataset.pair_indices[
                        sequence_index, frame_index
                    ],
                    "joint_filter_negative_log_likelihood_standardized": (
                        -combined_log_standardized[
                            sequence_index, frame_index
                        ]
                    ),
                    "joint_filter_negative_log_likelihood_physical": (
                        -combined_log_physical[sequence_index, frame_index]
                    ),
                    "sample_mean_prediction_rmse_m": (
                        overall_evaluation.frame_rmse_m[
                            sequence_index, frame_index
                        ]
                    ),
                    "energy_score_m": overall_evaluation.frame_energy_score_m[
                        sequence_index, frame_index
                    ],
                    "maximum_posterior_state_index": int(
                        np.argmax(probabilities)
                    ),
                    "maximum_posterior_state_probability": float(
                        np.max(probabilities)
                    ),
                    "posterior_state_entropy_nats": active_entropy[
                        active_offset
                    ],
                }
            )
            active_offset += 1
    if active_offset != dataset.frame_count:
        raise ValueError("frame posterior rows do not reconcile")

    all_data_standardizer = SequenceStandardizer.fit(
        dataset,
        train_drive_ids=tuple(sorted(set(dataset.drive_ids.tolist()))),
    )
    all_data_standardized = all_data_standardizer.standardized_copy(dataset)
    final_model, final_report, final_restart_rows = _fit_restarts(
        all_data_standardized,
        base_config=config,
        restart_count=restart_count,
        seed_offset=len(fold_contracts) * restart_count * RESTART_SEED_STRIDE,
        scope="descriptive_all_development_data",
        fold_id="all_development_data",
        held_out_drive_id=None,
    )
    restart_rows.extend(final_restart_rows)
    final_posterior = _posterior_tensor(
        all_data_standardized,
        final_model.posterior_state_probabilities(all_data_standardized),
        state_count=config.state_count,
    )
    final_posterior_statistics = _posterior_statistics(
        final_posterior, all_data_standardized.time_mask
    )
    final_transition_diagnostics = _transition_diagnostics(
        final_model, all_data_standardized
    )
    state_rows.extend(
        _state_rows(
            scope="descriptive_all_development_data_fit",
            fold_id="all_development_data",
            held_out_drive_id=None,
            model=final_model,
            posterior_occupancies=final_posterior_statistics["occupancies"],
            transition_diagnostics=final_transition_diagnostics,
        )
    )

    write_csv_rows(
        arguments.output_directory / "aiohmm_sequence_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "aiohmm_sequence_station_evaluation.csv",
        STATION_FIELDS,
        station_rows,
    )
    write_csv_rows(
        arguments.output_directory / "aiohmm_sequence_frame_evaluation.csv",
        FRAME_FIELDS,
        frame_rows,
    )
    write_csv_rows(
        arguments.output_directory / "aiohmm_sequence_state_evaluation.csv",
        STATE_FIELDS,
        state_rows,
    )
    write_csv_rows(
        arguments.output_directory / "aiohmm_sequence_restart_evaluation.csv",
        RESTART_FIELDS,
        restart_rows,
    )
    write_strict_json(
        arguments.output_directory / "aiohmm_sequence_fold_models.json",
        {
            "version": VERSION,
            "status": "complete",
            "purpose": "leave_one_physical_drive_out_aiohmm_models",
            "state_count_fixed_before_held_out_evaluation": True,
            "models": fold_models,
        },
    )
    write_strict_json(
        arguments.output_directory / "aiohmm_sequence_model.json",
        {
            "version": VERSION,
            "status": "complete",
            "role": "descriptive_all_development_data_fit_after_evaluation",
            "not_an_untouched_final_model": True,
            "standardizer": all_data_standardizer.to_dict(),
            "fit_report": _fit_report_payload(final_report),
            "model": final_model.to_dict(),
        },
    )
    plot_sequence_aiohmm_diagnostics(
        arguments.output_directory / "aiohmm_sequence_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        evaluation_rows=evaluation_rows,
        station_rows=station_rows,
        state_rows=state_rows,
        final_transition_matrix=final_transition_diagnostics["mean_matrix"],
        final_autoregressive_coefficients=(
            final_model.autoregressive_coefficients
        ),
    )

    output_names = (
        "aiohmm_sequence_evaluation.csv",
        "aiohmm_sequence_station_evaluation.csv",
        "aiohmm_sequence_frame_evaluation.csv",
        "aiohmm_sequence_state_evaluation.csv",
        "aiohmm_sequence_restart_evaluation.csv",
        "aiohmm_sequence_fold_models.json",
        "aiohmm_sequence_model.json",
        "aiohmm_sequence_diagnostics.png",
    )
    overall_row = next(
        row
        for row in evaluation_rows
        if row["scope"] == "overall_cross_validated"
    )
    failed_restart_count = sum(
        row["status"] == "failed" for row in restart_rows
    )
    nonconverged_selected_count = sum(
        bool(row["selected"]) and not bool(row["em_converged"])
        for row in restart_rows
        if row["status"] == "complete"
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "common_sequence_contract_autoregressive_input_output_hmm",
        "project_role": "canonical_thesis_implementation",
        "source_sequence_version": source_summary["version"],
        "source_files_sha256": {
            name: sha256_file(arguments.sequential_dataset_directory / name)
            for name in sorted(REQUIRED_INPUT_FILES)
        },
        "output_files_sha256": {
            name: sha256_file(arguments.output_directory / name)
            for name in output_names
        },
        "model_name": "autoregressive_input_output_hmm",
        "model_family": "autoregressive_input_output_hidden_markov_model",
        "feature_schema": source_summary["feature_schema"],
        "feature_names": source_summary["feature_names"],
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "sequence_count": dataset.sequence_count,
        "frame_count": dataset.frame_count,
        "drive_count": len(set(dataset.drive_ids.tolist())),
        "evaluation_scheme": "leave_one_physical_drive_out",
        "same_sequence_folds_as_v0100_gaussian": True,
        "fold_standardization_source": "v0.9.0_training_drive_only",
        "state_count": config.state_count,
        "state_count_role": "fixed_exploratory_default",
        "automatic_state_count_selection_performed": False,
        "held_out_drives_used_for_state_count_or_restart_selection": False,
        "restart_count_per_fit": restart_count,
        "restart_selection_criterion": (
            "highest_training_joint_log_probability_same_fixed_architecture"
        ),
        "failed_restart_count": failed_restart_count,
        "selected_fit_nonconvergence_count": nonconverged_selected_count,
        "configuration": config.to_dict(),
        "sample_count": sample_count,
        "sampling_random_seed": sample_seed,
        "sample_metrics_are_common_to_all_model_families": True,
        "likelihood_is_teacher_forced_secondary_metric": True,
        "sampling_is_free_running": True,
        "energy_score_definition": (
            "mean_norm_sample_minus_observation_minus_half_mean_norm_independent_sample_pairs"
        ),
        "temporal_dependency_order": 1,
        "input_dependent_transitions": True,
        "stationwise_autoregressive_emissions": True,
        "sequence_reset_prior": (
            "state_independent_training_marginal_conditional_gaussian"
        ),
        "sequence_reset_prior_uses_held_out_rows": False,
        "emission_parameter_pooling_penalty": (
            config.emission_parameter_pooling_penalty
        ),
        "state_specific_spatial_covariance": True,
        "state_covariance_pooling": config.state_covariance_pooling,
        "cross_validated_metrics": {
            key: overall_row[key]
            for key in EVALUATION_FIELDS
            if key
            not in {
                "scope",
                "held_out_drive_id",
                "training_drive_ids",
                "training_sequence_count",
                "training_frame_count",
            }
        },
        "state_labels_are_physical_classes": False,
        "state_labels_are_canonicalized_for_diagnostics": True,
        "data_role": "development_only",
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "final_all_data_fit_is_descriptive_only": True,
        "pair_count_is_independent_sample_size": False,
        "next_phase": (
            "review_aiohmm_against_v0100_then_collect_independent_drives_or_run_predeclared_feature_ablations"
        ),
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "scientific_limitations": [
            "Only two physical drives are available for development evaluation.",
            "The fixed three-state architecture is exploratory and is not selected evidence.",
            "Hidden-state labels are exchangeable diagnostics, not physical driving regimes.",
            "Teacher-forced density and free-running generation answer different questions.",
            "RLMB is a pseudo-reference, not independent physical ground truth.",
            "The accepted target retains the documented approximately 23.5 ms timing mismatch as label noise.",
            "Sample metrics have finite Monte Carlo error under the recorded seed.",
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "aiohmm_sequence_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "EVALUATION_FIELDS",
    "FRAME_FIELDS",
    "RESTART_FIELDS",
    "STATE_FIELDS",
    "STATION_FIELDS",
    "VERSION",
    "run_sequence_aiohmm",
]
