"""v0.14 leakage-safe Gaussian re-baseline on accepted expanded sequences."""

from __future__ import annotations

import argparse
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ..domain.model_evaluation import DriveGroupedFold, build_leave_one_drive_out_folds
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import PaddedSequenceDataset, SequenceStandardizer
from ..io.expanded_modeling_dataset import (
    ExpandedModelingDataset,
    load_expanded_modeling_dataset,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..modeling.base import FitReport, ProbabilisticSequenceModel, SampleResult
from ..modeling.sequence_evaluation import (
    SequenceSampleEvaluation,
    evaluate_sequence_samples,
    physical_sample_result,
)
from ..modeling.sequence_gaussian import SequenceConditionalGaussian
from ..modeling.sequence_unconditional_gaussian import SequenceUnconditionalGaussian
from ..visualization.expanded_gaussian import plot_expanded_gaussian_diagnostics
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.14.0"
MODEL_NAMES = ("unconditional_gaussian", "conditional_gaussian")

EVALUATION_FIELDS = (
    "model_name",
    "model_family",
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
    "mean_frame_negative_log_likelihood_standardized",
    "mean_frame_negative_log_likelihood_physical",
    "mean_squared_mahalanobis_per_dimension",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_observed_lag_one_correlation",
    "median_generated_lag_one_correlation",
    "median_absolute_lag_one_correlation_error",
    "condition_feature_count",
    "temporal_dependency_order",
)

STATION_FIELDS = (
    "model_name",
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
)

FRAME_FIELDS = (
    "model_name",
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
    "frame_negative_log_likelihood_standardized",
    "frame_negative_log_likelihood_physical",
    "squared_mahalanobis_per_dimension",
    "sample_mean_prediction_rmse_m",
    "energy_score_m",
)


def _model(model_name: str, regularization: float) -> ProbabilisticSequenceModel:
    if model_name == "unconditional_gaussian":
        return SequenceUnconditionalGaussian(
            covariance_regularization=regularization
        )
    if model_name == "conditional_gaussian":
        return SequenceConditionalGaussian(
            covariance_regularization=regularization
        )
    raise ValueError(f"unknown Gaussian baseline: {model_name}")


def _model_family(model_name: str) -> str:
    if model_name == "unconditional_gaussian":
        return "unconditional_multivariate_gaussian"
    return "linear_conditional_multivariate_gaussian"


def _condition_feature_count(model_name: str) -> int:
    return 0 if model_name == "unconditional_gaussian" else 6


def _fit_report_payload(report: FitReport) -> dict[str, Any]:
    return {
        "model_name": report.model_name,
        "training_sequence_count": report.training_sequence_count,
        "validation_sequence_count": report.validation_sequence_count,
        "metrics": dict(report.metrics),
        "warnings": list(report.warnings),
    }


def _model_payload(model: ProbabilisticSequenceModel) -> Mapping[str, Any]:
    payload = getattr(model, "to_dict", None)
    if payload is None:
        raise ValueError(f"{model.model_name} is not serializable")
    result = payload()
    if not isinstance(result, Mapping):
        raise ValueError(f"{model.model_name} serialization is invalid")
    return result


def _evaluate(
    model: ProbabilisticSequenceModel,
    *,
    standardized_test: PaddedSequenceDataset,
    physical_test: PaddedSequenceDataset,
    standardizer: SequenceStandardizer,
    sample_count: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, SampleResult, SequenceSampleEvaluation]:
    log_standardized = model.log_probability(standardized_test)
    squared_method = getattr(model, "squared_mahalanobis", None)
    if squared_method is None:
        raise ValueError(f"{model.model_name} lacks Gaussian Mahalanobis diagnostics")
    squared = squared_method(standardized_test)
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
    return log_standardized, log_physical, squared, physical_samples, evaluation


def _evaluation_row(
    *,
    model_name: str,
    scope: str,
    cohort_role: str,
    held_out_drive_id: str | None,
    training_drive_ids: Sequence[str],
    test_drive_ids: Sequence[str],
    training_sequence_count: int | None,
    training_frame_count: int | None,
    test: PaddedSequenceDataset,
    sample_count: int,
    log_standardized: np.ndarray,
    log_physical: np.ndarray,
    squared: np.ndarray,
    evaluation: SequenceSampleEvaluation,
) -> dict[str, Any]:
    generated = evaluation.generated_median_lag_one_correlation
    return {
        "model_name": model_name,
        "model_family": _model_family(model_name),
        "scope": scope,
        "cohort_role": cohort_role,
        "held_out_drive_id": held_out_drive_id,
        "training_drive_ids": ";".join(training_drive_ids),
        "test_drive_ids": ";".join(test_drive_ids),
        "training_sequence_count": training_sequence_count,
        "training_frame_count": training_frame_count,
        "test_sequence_count": test.sequence_count,
        "test_frame_count": test.frame_count,
        "sample_count": sample_count,
        "mean_frame_negative_log_likelihood_standardized": float(
            -np.mean(log_standardized[test.time_mask])
        ),
        "mean_frame_negative_log_likelihood_physical": float(
            -np.mean(log_physical[test.time_mask])
        ),
        "mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared[test.time_mask]) / len(CANONICAL_MODEL_STATIONS_M)
        ),
        "sample_mean_prediction_rmse_m": evaluation.pooled_mean_prediction_rmse_m,
        "mean_energy_score_m": evaluation.mean_energy_score_m,
        "mean_normalized_sequence_energy_score_m": (
            evaluation.mean_normalized_sequence_energy_score_m
        ),
        "marginal_95_coverage": evaluation.marginal_95_coverage,
        "absolute_marginal_95_coverage_error": abs(
            evaluation.marginal_95_coverage - 0.95
        ),
        "median_observed_lag_one_correlation": float(
            np.median(evaluation.observed_lag_one_correlation)
        ),
        "median_generated_lag_one_correlation": float(np.median(generated)),
        "median_absolute_lag_one_correlation_error": (
            evaluation.median_absolute_lag_one_correlation_error
        ),
        "condition_feature_count": _condition_feature_count(model_name),
        "temporal_dependency_order": 0,
    }


def _station_rows(
    *,
    model_name: str,
    scope: str,
    cohort_role: str,
    held_out_drive_id: str | None,
    test_frame_count: int,
    evaluation: SequenceSampleEvaluation,
) -> list[dict[str, Any]]:
    generated = evaluation.generated_lag_one_correlation_by_sample
    generated_median = np.median(generated, axis=0)
    return [
        {
            "model_name": model_name,
            "scope": scope,
            "cohort_role": cohort_role,
            "held_out_drive_id": held_out_drive_id,
            "station_m": station,
            "test_frame_count": test_frame_count,
            "sample_mean_prediction_rmse_m": evaluation.station_rmse_m[index],
            "sample_mean_prediction_bias_m": evaluation.station_bias_m[index],
            "marginal_95_coverage": evaluation.station_coverage_95[index],
            "observed_lag_one_correlation": evaluation.observed_lag_one_correlation[index],
            "generated_median_lag_one_correlation": generated_median[index],
            "generated_p05_lag_one_correlation": np.quantile(generated[:, index], 0.05),
            "generated_p95_lag_one_correlation": np.quantile(generated[:, index], 0.95),
            "absolute_lag_one_correlation_error": abs(
                generated_median[index] - evaluation.observed_lag_one_correlation[index]
            ),
        }
        for index, station in enumerate(CANONICAL_MODEL_STATIONS_M)
    ]


def _provenance_lookup(
    source: ExpandedModelingDataset,
) -> dict[tuple[str, int], tuple[str, str]]:
    result: dict[tuple[str, int], tuple[str, str]] = {}
    for sequence_index, sequence_id in enumerate(source.sequences.sequence_ids):
        length = int(source.sequences.lengths[sequence_index])
        for frame_index in range(length):
            key = (str(sequence_id), frame_index)
            result[key] = (
                str(source.recording_ids_by_frame[sequence_index, frame_index]),
                str(
                    source.mcap_basenames_by_frame_private[
                        sequence_index, frame_index
                    ]
                ),
            )
    return result


def _frame_rows(
    *,
    model_name: str,
    scope: str,
    cohort_role: str,
    dataset: PaddedSequenceDataset,
    provenance: Mapping[tuple[str, int], tuple[str, str]],
    log_standardized: np.ndarray,
    log_physical: np.ndarray,
    squared: np.ndarray,
    evaluation: SequenceSampleEvaluation,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence_index, raw_length in enumerate(dataset.lengths):
        sequence_id = str(dataset.sequence_ids[sequence_index])
        for frame_index in range(int(raw_length)):
            recording_id, basename = provenance[(sequence_id, frame_index)]
            rows.append(
                {
                    "model_name": model_name,
                    "scope": scope,
                    "cohort_role": cohort_role,
                    "sequence_id": sequence_id,
                    "sequence_frame_index": frame_index,
                    "recording_id": recording_id,
                    "drive_id": dataset.drive_ids[sequence_index],
                    "mcap_basename_private": basename,
                    "pair_index": dataset.pair_indices[sequence_index, frame_index],
                    "estimate_message_index": (
                        dataset.estimate_message_indices[sequence_index, frame_index]
                    ),
                    "estimate_source_time_ns_private": (
                        dataset.estimate_source_times_ns_private[
                            sequence_index, frame_index
                        ]
                    ),
                    "frame_negative_log_likelihood_standardized": (
                        -log_standardized[sequence_index, frame_index]
                    ),
                    "frame_negative_log_likelihood_physical": (
                        -log_physical[sequence_index, frame_index]
                    ),
                    "squared_mahalanobis_per_dimension": (
                        squared[sequence_index, frame_index]
                        / len(CANONICAL_MODEL_STATIONS_M)
                    ),
                    "sample_mean_prediction_rmse_m": (
                        evaluation.frame_rmse_m[sequence_index, frame_index]
                    ),
                    "energy_score_m": (
                        evaluation.frame_energy_score_m[sequence_index, frame_index]
                    ),
                }
            )
    return rows


def _protocol_payload(
    source: ExpandedModelingDataset,
    folds: Sequence[DriveGroupedFold],
    *,
    regularization: float,
    sample_count: int,
    seed: int,
) -> dict[str, Any]:
    primary = source.primary
    supplementary = source.supplementary
    return {
        "version": VERSION,
        "status": "complete",
        "purpose": "leakage_safe_drive_grouped_thesis_model_evaluation_contract",
        "source_dataset_version": "0.13.1",
        "source_files_sha256": dict(source.source_files_sha256),
        "primary_cohort": {
            "role": "development_primary_clean_sensor_drives",
            "drive_ids": list(source.clean_drive_ids),
            "drive_count": len(source.clean_drive_ids),
            "sequence_count": primary.sequence_count,
            "frame_count": primary.frame_count,
        },
        "supplementary_cohort": {
            "role": "mixed_source_fragments_transfer_check_only",
            "never_used_for_fit_or_primary_model_comparison": True,
            "drive_ids": list(source.mixed_drive_ids),
            "drive_count": len(source.mixed_drive_ids),
            "sequence_count": supplementary.sequence_count,
            "frame_count": supplementary.frame_count,
        },
        "split_scheme": "leave_one_clean_physical_drive_out",
        "random_frame_splits_permitted": False,
        "same_physical_drive_may_cross_fold": False,
        "fold_count": len(folds),
        "folds": [fold.to_dict() for fold in folds],
        "standardization_policy": "fit_on_each_fold_training_drives_only",
        "hyperparameter_selection": {
            "performed": False,
            "policy": "fixed_before_outer_evaluation",
            "covariance_regularization_standardized2": regularization,
        },
        "monte_carlo": {
            "sample_count": sample_count,
            "base_seed": seed,
            "common_random_numbers_across_gaussian_baselines": True,
        },
        "primary_cross_model_metrics": [
            "sample_mean_prediction_rmse_m",
            "mean_energy_score_m",
            "mean_normalized_sequence_energy_score_m",
            "marginal_95_coverage",
            "median_absolute_lag_one_correlation_error",
        ],
        "normalized_sequence_energy_score_definition": (
            "energy score on each flattened [time,21] sequence with Euclidean "
            "distances divided by sqrt(sequence_length*21), then averaged"
        ),
        "secondary_density_metric": "mean_frame_negative_log_likelihood_physical",
        "macro_and_pooled_reporting": True,
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
    }


def _metric_subset(row: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {
        "model_name",
        "model_family",
        "scope",
        "cohort_role",
        "held_out_drive_id",
        "training_drive_ids",
        "test_drive_ids",
        "training_sequence_count",
        "training_frame_count",
    }
    return {key: row[key] for key in EVALUATION_FIELDS if key not in ignored}


def _macro_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    names = (
        "mean_frame_negative_log_likelihood_physical",
        "mean_squared_mahalanobis_per_dimension",
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "marginal_95_coverage",
        "absolute_marginal_95_coverage_error",
        "median_absolute_lag_one_correlation_error",
    )
    return {name: float(np.mean([float(row[name]) for row in rows])) for name in names}


def run_expanded_gaussian(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Run two Gaussian nulls on identical clean-drive folds and rows."""

    regularization = float(arguments.covariance_regularization_standardized2)
    if not math.isfinite(regularization) or regularization <= 0.0:
        raise ValueError("covariance regularization must be finite and positive")
    sample_count = arguments.sample_count
    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
        or sample_count < 4
        or sample_count % 2 != 0
    ):
        raise ValueError("sample-count must be an even integer of at least four")
    seed = arguments.seed
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    source = load_expanded_modeling_dataset(arguments.expanded_sequence_directory)
    if len(source.clean_drive_ids) != 4:
        raise ValueError("v0.14 primary protocol requires exactly four clean drives")
    folds = build_leave_one_drive_out_folds(
        source.sequences,
        primary_drive_ids=source.clean_drive_ids,
    )
    ensure_empty_output_directory(arguments.output_directory)
    protocol = _protocol_payload(
        source,
        folds,
        regularization=regularization,
        sample_count=sample_count,
        seed=seed,
    )
    write_strict_json(
        arguments.output_directory / "drive_grouped_evaluation_contract.json",
        protocol,
    )

    primary = source.primary
    supplementary = source.supplementary
    provenance = _provenance_lookup(source)
    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    models_payload: dict[str, Any] = {}

    for model_name in MODEL_NAMES:
        combined_samples = np.zeros(
            (sample_count, *primary.residuals_m.shape), dtype=np.float64
        )
        combined_log_standardized = np.zeros(primary.time_mask.shape, dtype=np.float64)
        combined_log_physical = np.zeros_like(combined_log_standardized)
        combined_squared = np.zeros_like(combined_log_standardized)
        fold_payloads: dict[str, Any] = {}
        for fold_index, fold in enumerate(folds):
            standardized = fold.standardizer.standardized_copy(primary)
            training = standardized.select_drive_ids(fold.training_drive_ids)
            test = standardized.select_drive_ids((fold.held_out_drive_id,))
            physical_test = primary.select_drive_ids((fold.held_out_drive_id,))
            fitted = _model(model_name, regularization)
            fit_report = fitted.fit(training)
            log_standardized, log_physical, squared, samples, evaluation = _evaluate(
                fitted,
                standardized_test=test,
                physical_test=physical_test,
                standardizer=fold.standardizer,
                sample_count=sample_count,
                seed=seed + fold_index,
            )
            row = _evaluation_row(
                model_name=model_name,
                scope="primary_held_out_drive",
                cohort_role="clean_sensor_primary",
                held_out_drive_id=fold.held_out_drive_id,
                training_drive_ids=fold.training_drive_ids,
                test_drive_ids=(fold.held_out_drive_id,),
                training_sequence_count=training.sequence_count,
                training_frame_count=training.frame_count,
                test=physical_test,
                sample_count=sample_count,
                log_standardized=log_standardized,
                log_physical=log_physical,
                squared=squared,
                evaluation=evaluation,
            )
            evaluation_rows.append(row)
            station_rows.extend(
                _station_rows(
                    model_name=model_name,
                    scope="primary_held_out_drive",
                    cohort_role="clean_sensor_primary",
                    held_out_drive_id=fold.held_out_drive_id,
                    test_frame_count=physical_test.frame_count,
                    evaluation=evaluation,
                )
            )
            primary_indices = np.flatnonzero(
                primary.drive_ids == fold.held_out_drive_id
            )
            combined_samples[:, primary_indices] = samples.values
            combined_log_standardized[primary_indices] = log_standardized
            combined_log_physical[primary_indices] = log_physical
            combined_squared[primary_indices] = squared
            fold_payloads[fold.fold_id] = {
                "held_out_drive_id": fold.held_out_drive_id,
                "training_drive_ids": list(fold.training_drive_ids),
                "standardizer": fold.standardizer.to_dict(),
                "fit_report": _fit_report_payload(fit_report),
                "model": _model_payload(fitted),
            }

        pooled_samples = SampleResult(
            values=combined_samples,
            lengths=primary.lengths,
            stations_m=CANONICAL_MODEL_STATIONS_M,
            standardized=False,
            valid_mask=primary.valid_mask,
        )
        pooled_evaluation = evaluate_sequence_samples(primary, pooled_samples)
        pooled_row = _evaluation_row(
            model_name=model_name,
            scope="primary_cross_validated",
            cohort_role="clean_sensor_primary",
            held_out_drive_id=None,
            training_drive_ids=(),
            test_drive_ids=source.clean_drive_ids,
            training_sequence_count=None,
            training_frame_count=None,
            test=primary,
            sample_count=sample_count,
            log_standardized=combined_log_standardized,
            log_physical=combined_log_physical,
            squared=combined_squared,
            evaluation=pooled_evaluation,
        )
        evaluation_rows.append(pooled_row)
        station_rows.extend(
            _station_rows(
                model_name=model_name,
                scope="primary_cross_validated",
                cohort_role="clean_sensor_primary",
                held_out_drive_id=None,
                test_frame_count=primary.frame_count,
                evaluation=pooled_evaluation,
            )
        )
        frame_rows.extend(
            _frame_rows(
                model_name=model_name,
                scope="primary_cross_validated",
                cohort_role="clean_sensor_primary",
                dataset=primary,
                provenance=provenance,
                log_standardized=combined_log_standardized,
                log_physical=combined_log_physical,
                squared=combined_squared,
                evaluation=pooled_evaluation,
            )
        )
        del combined_samples, pooled_samples

        all_clean_standardizer = SequenceStandardizer.fit(
            source.sequences,
            train_drive_ids=source.clean_drive_ids,
        )
        all_standardized = all_clean_standardizer.standardized_copy(source.sequences)
        clean_training = all_standardized.select_drive_ids(source.clean_drive_ids)
        mixed_test = all_standardized.select_drive_ids(source.mixed_drive_ids)
        descriptive_model = _model(model_name, regularization)
        descriptive_report = descriptive_model.fit(clean_training)
        mixed_log_standardized, mixed_log_physical, mixed_squared, mixed_samples, mixed_evaluation = _evaluate(
            descriptive_model,
            standardized_test=mixed_test,
            physical_test=supplementary,
            standardizer=all_clean_standardizer,
            sample_count=sample_count,
            seed=seed + 1000,
        )
        mixed_row = _evaluation_row(
            model_name=model_name,
            scope="supplementary_mixed_transfer",
            cohort_role="mixed_source_fragments_supplementary",
            held_out_drive_id=None,
            training_drive_ids=source.clean_drive_ids,
            test_drive_ids=source.mixed_drive_ids,
            training_sequence_count=clean_training.sequence_count,
            training_frame_count=clean_training.frame_count,
            test=supplementary,
            sample_count=sample_count,
            log_standardized=mixed_log_standardized,
            log_physical=mixed_log_physical,
            squared=mixed_squared,
            evaluation=mixed_evaluation,
        )
        evaluation_rows.append(mixed_row)
        station_rows.extend(
            _station_rows(
                model_name=model_name,
                scope="supplementary_mixed_transfer",
                cohort_role="mixed_source_fragments_supplementary",
                held_out_drive_id=None,
                test_frame_count=supplementary.frame_count,
                evaluation=mixed_evaluation,
            )
        )
        frame_rows.extend(
            _frame_rows(
                model_name=model_name,
                scope="supplementary_mixed_transfer",
                cohort_role="mixed_source_fragments_supplementary",
                dataset=supplementary,
                provenance=provenance,
                log_standardized=mixed_log_standardized,
                log_physical=mixed_log_physical,
                squared=mixed_squared,
                evaluation=mixed_evaluation,
            )
        )
        models_payload[model_name] = {
            "fold_models": fold_payloads,
            "descriptive_all_clean_fit": {
                "role": "fit_on_all_clean_development_drives_after_cross_validation",
                "not_an_untouched_final_model": True,
                "standardizer": all_clean_standardizer.to_dict(),
                "fit_report": _fit_report_payload(descriptive_report),
                "model": _model_payload(descriptive_model),
            },
        }

    write_csv_rows(
        arguments.output_directory / "gaussian_grouped_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_grouped_station_evaluation.csv",
        STATION_FIELDS,
        station_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_grouped_frame_evaluation.csv",
        FRAME_FIELDS,
        frame_rows,
    )
    write_strict_json(
        arguments.output_directory / "gaussian_grouped_models.json",
        {
            "version": VERSION,
            "status": "complete",
            "purpose": "drive_grouped_gaussian_fold_and_descriptive_models",
            "models": models_payload,
        },
    )
    plot_expanded_gaussian_diagnostics(
        arguments.output_directory / "gaussian_grouped_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        evaluation_rows=evaluation_rows,
        station_rows=station_rows,
    )

    by_model: dict[str, Any] = {}
    for model_name in MODEL_NAMES:
        pooled = next(
            row
            for row in evaluation_rows
            if row["model_name"] == model_name
            and row["scope"] == "primary_cross_validated"
        )
        fold_rows = [
            row
            for row in evaluation_rows
            if row["model_name"] == model_name
            and row["scope"] == "primary_held_out_drive"
        ]
        mixed = next(
            row
            for row in evaluation_rows
            if row["model_name"] == model_name
            and row["scope"] == "supplementary_mixed_transfer"
        )
        by_model[model_name] = {
            "primary_pooled_cross_validated_metrics": _metric_subset(pooled),
            "primary_macro_drive_metrics": _macro_metrics(fold_rows),
            "supplementary_mixed_transfer_metrics": _metric_subset(mixed),
        }
    lower_is_better = (
        "mean_frame_negative_log_likelihood_physical",
        "sample_mean_prediction_rmse_m",
        "mean_energy_score_m",
        "mean_normalized_sequence_energy_score_m",
        "absolute_marginal_95_coverage_error",
        "median_absolute_lag_one_correlation_error",
    )
    deltas = {
        name: (
            by_model["conditional_gaussian"]["primary_macro_drive_metrics"][name]
            - by_model["unconditional_gaussian"]["primary_macro_drive_metrics"][name]
        )
        for name in lower_is_better
    }
    output_names = (
        "drive_grouped_evaluation_contract.json",
        "gaussian_grouped_evaluation.csv",
        "gaussian_grouped_station_evaluation.csv",
        "gaussian_grouped_frame_evaluation.csv",
        "gaussian_grouped_models.json",
        "gaussian_grouped_diagnostics.png",
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "expanded_drive_grouped_gaussian_rebaseline",
        "project_role": "canonical_thesis_implementation",
        "source_dataset_version": "0.13.1",
        "source_files_sha256": dict(source.source_files_sha256),
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
        "evaluation_scheme": "leave_one_clean_physical_drive_out",
        "fold_count": len(folds),
        "random_frame_splits_used": False,
        "fold_standardization": "training_drives_only",
        "model_hyperparameter_selection_performed": False,
        "covariance_regularization_standardized2": regularization,
        "sample_count": sample_count,
        "random_seed": seed,
        "models": by_model,
        "conditional_minus_unconditional_primary_macro_deltas": deltas,
        "delta_interpretation": "negative_is_better_for_every_reported_delta",
        "mixed_source_results_are_supplementary_only": True,
        "sample_metrics_are_common_to_all_thesis_model_families": True,
        "temporal_dependency_order": 0,
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "next_phase": "aiohmm_on_identical_v0.14_primary_cohort_folds_transforms_and_metrics",
        "scientific_limitations": [
            "Only four clean physical drives support primary development evaluation.",
            "Mixed-source fragments are not exchangeable with the clean primary cohort.",
            "RLMB remains a pseudo-reference and independence from the EDP topology source is unknown.",
            "Gaussian sample metrics retain finite Monte Carlo error under the recorded seed.",
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "gaussian_grouped_summary.json", summary
    )
    return summary, 0


__all__ = [
    "EVALUATION_FIELDS",
    "FRAME_FIELDS",
    "MODEL_NAMES",
    "STATION_FIELDS",
    "VERSION",
    "run_expanded_gaussian",
]
