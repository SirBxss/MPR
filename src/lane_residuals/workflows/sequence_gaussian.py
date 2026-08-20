"""Drive-held-out v0.10.0 sequence-contract conditional Gaussian workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    ResidualDatasetContractError,
)
from ..domain.sequence_dataset import SequenceStandardizer
from ..io.reports import write_csv_rows, write_strict_json
from ..io.sequence_dataset import load_sequence_dataset_npz
from ..modeling.base import SampleResult
from ..modeling.sequence_evaluation import (
    SequenceSampleEvaluation,
    evaluate_sequence_samples,
    physical_sample_result,
)
from ..modeling.sequence_gaussian import SequenceConditionalGaussian
from ..visualization.sequence_gaussian import plot_sequence_gaussian_diagnostics

VERSION = "0.10.0"
ACCEPTED_SEQUENCE_VERSION = "0.9.0"
ACCEPTED_SEQUENCE_PURPOSE = "common_three_model_sequential_dataset"
REQUIRED_INPUT_FILES = frozenset(
    {
        "sequential_dataset.npz",
        "sequence_summary.csv",
        "sequence_frame_index.csv",
        "drive_fold_manifest.json",
        "drive_fold_standardizers.json",
        "sequence_dataset_diagnostics.png",
        "sequential_dataset_summary.json",
    }
)
EVALUATION_FIELDS = (
    "scope",
    "held_out_drive_id",
    "training_drive_ids",
    "training_sequence_count",
    "training_frame_count",
    "test_sequence_count",
    "test_frame_count",
    "sample_count",
    "mean_joint_negative_log_likelihood_standardized",
    "mean_joint_negative_log_likelihood_physical",
    "mean_squared_mahalanobis_per_dimension",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "marginal_95_coverage",
    "median_observed_lag_one_correlation",
    "median_generated_lag_one_correlation",
    "median_absolute_lag_one_correlation_error",
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
)
FRAME_FIELDS = (
    "sequence_id",
    "sequence_frame_index",
    "recording_id",
    "drive_id",
    "pair_index",
    "joint_negative_log_likelihood_standardized",
    "joint_negative_log_likelihood_physical",
    "squared_mahalanobis_per_dimension",
    "sample_mean_prediction_rmse_m",
    "energy_score_m",
)


def _read_strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _validated_sources(
    input_directory: Path,
) -> tuple[Any, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    if not input_directory.is_dir():
        raise FileNotFoundError(f"v0.9.0 sequence directory not found: {input_directory}")
    actual_files = {path.name for path in input_directory.iterdir() if path.is_file()}
    if actual_files != REQUIRED_INPUT_FILES:
        raise ResidualDatasetContractError(
            "v0.9.0 sequence directory filename set differs from the contract"
        )
    summary = _read_strict_json(input_directory / "sequential_dataset_summary.json")
    manifest = _read_strict_json(input_directory / "drive_fold_manifest.json")
    standardizers = _read_strict_json(
        input_directory / "drive_fold_standardizers.json"
    )
    if not all(isinstance(value, Mapping) for value in (summary, manifest, standardizers)):
        raise ResidualDatasetContractError("v0.9.0 JSON roots must be objects")
    if (
        summary.get("version") != ACCEPTED_SEQUENCE_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose") != ACCEPTED_SEQUENCE_PURPOSE
    ):
        raise ResidualDatasetContractError("v0.9.0 sequence summary is not accepted")
    if summary.get("data_role") != "development_only":
        raise ResidualDatasetContractError("sequence data role must remain development-only")
    if summary.get("final_model_selection_authorized") is not False:
        raise ResidualDatasetContractError("final model selection cannot be authorized")
    expected_hashes = summary.get("output_files_sha256")
    if not isinstance(expected_hashes, Mapping):
        raise ResidualDatasetContractError("source output hashes are missing")
    expected_hashed_names = REQUIRED_INPUT_FILES - {"sequential_dataset_summary.json"}
    if set(expected_hashes) != expected_hashed_names:
        raise ResidualDatasetContractError("source output hash set is incomplete")
    for name, expected in expected_hashes.items():
        path = input_directory / str(name)
        if not path.is_file() or _sha256(path) != expected:
            raise ResidualDatasetContractError(f"source hash mismatch: {name}")

    dataset = load_sequence_dataset_npz(input_directory / "sequential_dataset.npz")
    if dataset.standardized:
        raise ResidualDatasetContractError("v0.9.0 source tensor must be physical-unit")
    if dataset.frame_count != summary.get("retained_frame_count"):
        raise ResidualDatasetContractError("source frame count does not reconcile")
    if dataset.sequence_count != summary.get("sequence_count"):
        raise ResidualDatasetContractError("source sequence count does not reconcile")
    if len(set(dataset.drive_ids.tolist())) != summary.get("drive_count"):
        raise ResidualDatasetContractError("source drive count does not reconcile")
    if (
        manifest.get("version") != ACCEPTED_SEQUENCE_VERSION
        or manifest.get("status") != "complete"
        or manifest.get("scheme") != "leave_one_physical_drive_out"
        or manifest.get("same_drive_may_cross_fold") is not False
    ):
        raise ResidualDatasetContractError("source drive-fold manifest is not accepted")
    if (
        standardizers.get("version") != ACCEPTED_SEQUENCE_VERSION
        or standardizers.get("status") != "complete"
    ):
        raise ResidualDatasetContractError("source fold standardizers are not accepted")
    return dataset, summary, manifest, standardizers


def _fold_contracts(
    dataset: Any,
    manifest: Mapping[str, Any],
    standardizer_payload: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], SequenceStandardizer]]:
    folds = manifest.get("folds")
    payloads = standardizer_payload.get("standardizers")
    if not isinstance(folds, list) or not isinstance(payloads, Mapping):
        raise ResidualDatasetContractError("fold definitions or transforms are missing")
    all_drives = set(dataset.drive_ids.tolist())
    all_sequences = set(dataset.sequence_ids.tolist())
    result: list[tuple[Mapping[str, Any], SequenceStandardizer]] = []
    held_out_drives: set[str] = set()
    held_out_sequences: set[str] = set()
    for fold in folds:
        if not isinstance(fold, Mapping):
            raise ResidualDatasetContractError("fold entries must be objects")
        fold_id = str(fold.get("fold_id", ""))
        held_out = str(fold.get("held_out_drive_id", ""))
        training_drives = tuple(sorted(str(value) for value in fold.get("training_drive_ids", ())))
        if (
            not fold_id
            or held_out not in all_drives
            or held_out in training_drives
            or set(training_drives) | {held_out} != all_drives
        ):
            raise ResidualDatasetContractError(f"invalid physical-drive fold: {fold_id}")
        if fold_id not in payloads:
            raise ResidualDatasetContractError(f"missing fold standardizer: {fold_id}")
        standardizer = SequenceStandardizer.from_dict(payloads[fold_id])
        if standardizer.train_drive_ids != training_drives:
            raise ResidualDatasetContractError(f"fold transform drive mismatch: {fold_id}")
        recomputed = SequenceStandardizer.fit(
            dataset,
            train_drive_ids=training_drives,
            minimum_scale=standardizer.minimum_scale,
        )
        for stored_values, recomputed_values in (
            (standardizer.condition_mean, recomputed.condition_mean),
            (standardizer.condition_scale, recomputed.condition_scale),
            (standardizer.residual_mean_m, recomputed.residual_mean_m),
            (standardizer.residual_scale_m, recomputed.residual_scale_m),
        ):
            if not np.allclose(
                stored_values,
                recomputed_values,
                rtol=0.0,
                atol=1e-12,
            ):
                raise ResidualDatasetContractError(
                    f"fold transform does not reproduce training rows: {fold_id}"
                )
        training_sequences = set(str(value) for value in fold.get("training_sequence_ids", ()))
        test_sequences = set(str(value) for value in fold.get("test_sequence_ids", ()))
        expected_training = set(
            dataset.sequence_ids[np.isin(dataset.drive_ids, training_drives)].tolist()
        )
        expected_test = set(dataset.sequence_ids[dataset.drive_ids == held_out].tolist())
        if training_sequences != expected_training or test_sequences != expected_test:
            raise ResidualDatasetContractError(f"fold sequence mismatch: {fold_id}")
        if (
            fold.get("training_frame_count") != recomputed.training_frame_count
            or fold.get("test_frame_count")
            != int(np.sum(dataset.lengths[dataset.drive_ids == held_out]))
        ):
            raise ResidualDatasetContractError(f"fold frame count mismatch: {fold_id}")
        if (
            training_sequences & test_sequences
            or training_sequences | test_sequences != all_sequences
        ):
            raise ResidualDatasetContractError(f"fold sequence leakage: {fold_id}")
        held_out_drives.add(held_out)
        held_out_sequences.update(test_sequences)
        result.append((fold, standardizer))
    if (
        len(result) != len(all_drives)
        or held_out_drives != all_drives
        or held_out_sequences != all_sequences
    ):
        raise ResidualDatasetContractError("folds do not test every drive and sequence once")
    if set(payloads) != {str(fold["fold_id"]) for fold in folds}:
        raise ResidualDatasetContractError("unexpected fold standardizer payload")
    return result


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
    log_probability_standardized: np.ndarray,
    log_probability_physical: np.ndarray,
    squared_mahalanobis: np.ndarray,
    sample_evaluation: SequenceSampleEvaluation,
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
        "mean_joint_negative_log_likelihood_standardized": float(
            -np.mean(log_probability_standardized)
        ),
        "mean_joint_negative_log_likelihood_physical": float(
            -np.mean(log_probability_physical)
        ),
        "mean_squared_mahalanobis_per_dimension": float(
            np.mean(squared_mahalanobis) / len(CANONICAL_MODEL_STATIONS_M)
        ),
        "sample_mean_prediction_rmse_m": (
            sample_evaluation.pooled_mean_prediction_rmse_m
        ),
        "mean_energy_score_m": sample_evaluation.mean_energy_score_m,
        "marginal_95_coverage": sample_evaluation.marginal_95_coverage,
        "median_observed_lag_one_correlation": float(
            np.median(sample_evaluation.observed_lag_one_correlation)
        ),
        "median_generated_lag_one_correlation": float(np.median(generated_median)),
        "median_absolute_lag_one_correlation_error": (
            sample_evaluation.median_absolute_lag_one_correlation_error
        ),
        "temporal_dependency_order": 0,
    }


def _station_rows(
    *,
    scope: str,
    held_out_drive_id: str | None,
    test_frame_count: int,
    evaluation: SequenceSampleEvaluation,
) -> list[dict[str, Any]]:
    generated = evaluation.generated_lag_one_correlation_by_sample
    generated_median = np.median(generated, axis=0)
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
                generated[:, index],
                0.05,
            ),
            "generated_p95_lag_one_correlation": np.quantile(
                generated[:, index],
                0.95,
            ),
            "absolute_lag_one_correlation_error": abs(
                generated_median[index]
                - evaluation.observed_lag_one_correlation[index]
            ),
        }
        for index, station in enumerate(CANONICAL_MODEL_STATIONS_M)
    ]


def run_sequence_gaussian(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Evaluate the conditional Gaussian under the common sequence contract."""

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

    dataset, source_summary, manifest, standardizer_payload = _validated_sources(
        arguments.sequential_dataset_directory
    )
    fold_contracts = _fold_contracts(dataset, manifest, standardizer_payload)
    _ensure_empty_output(arguments.output_directory)

    combined_sample_values = np.zeros(
        (sample_count, *dataset.residuals_m.shape),
        dtype=np.float64,
    )
    combined_log_standardized = np.zeros(dataset.time_mask.shape, dtype=np.float64)
    combined_log_physical = np.zeros_like(combined_log_standardized)
    combined_squared = np.zeros_like(combined_log_standardized)
    evaluation_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    fold_models: dict[str, Any] = {}

    for fold_index, (fold, standardizer) in enumerate(fold_contracts):
        fold_id = str(fold["fold_id"])
        held_out = str(fold["held_out_drive_id"])
        training_drives = tuple(str(value) for value in fold["training_drive_ids"])
        standardized = standardizer.standardized_copy(dataset)
        training = standardized.select_drive_ids(training_drives)
        test = standardized.select_drive_ids((held_out,))
        raw_test = dataset.select_drive_ids((held_out,))
        model = SequenceConditionalGaussian(
            covariance_regularization=regularization
        )
        fit_report = model.fit(training, test)
        log_standardized = model.log_probability(test)
        squared = model.squared_mahalanobis(test)
        jacobian = float(np.sum(np.log(standardizer.residual_scale_m)))
        log_physical = np.zeros_like(log_standardized)
        log_physical[test.time_mask] = log_standardized[test.time_mask] - jacobian
        standardized_samples = model.sample(
            test.conditions,
            test.lengths,
            sample_count=sample_count,
            seed=seed + fold_index,
            valid_mask=test.valid_mask,
        )
        physical_samples = physical_sample_result(
            standardized_samples,
            standardizer,
        )
        sample_evaluation = evaluate_sequence_samples(raw_test, physical_samples)
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
                log_probability_standardized=log_standardized[test.time_mask],
                log_probability_physical=log_physical[test.time_mask],
                squared_mahalanobis=squared[test.time_mask],
                sample_evaluation=sample_evaluation,
            )
        )
        station_rows.extend(
            _station_rows(
                scope="held_out_drive",
                held_out_drive_id=held_out,
                test_frame_count=test.frame_count,
                evaluation=sample_evaluation,
            )
        )
        full_indices = np.flatnonzero(dataset.drive_ids == held_out)
        combined_sample_values[:, full_indices] = physical_samples.values
        combined_log_standardized[full_indices] = log_standardized
        combined_log_physical[full_indices] = log_physical
        combined_squared[full_indices] = squared
        fold_models[fold_id] = {
            "held_out_drive_id": held_out,
            "training_drive_ids": list(training_drives),
            "standardizer_source": "drive_fold_standardizers.json",
            "fit_report": {
                "training_sequence_count": fit_report.training_sequence_count,
                "validation_sequence_count": fit_report.validation_sequence_count,
                "metrics": dict(fit_report.metrics),
                "warnings": list(fit_report.warnings),
            },
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
            log_probability_standardized=(
                combined_log_standardized[dataset.time_mask]
            ),
            log_probability_physical=combined_log_physical[dataset.time_mask],
            squared_mahalanobis=combined_squared[dataset.time_mask],
            sample_evaluation=overall_evaluation,
        )
    )
    station_rows.extend(
        _station_rows(
            scope="overall_cross_validated",
            held_out_drive_id=None,
            test_frame_count=dataset.frame_count,
            evaluation=overall_evaluation,
        )
    )

    frame_rows: list[dict[str, Any]] = []
    for sequence_index in range(dataset.sequence_count):
        length = int(dataset.lengths[sequence_index])
        for frame_index in range(length):
            frame_rows.append(
                {
                    "sequence_id": dataset.sequence_ids[sequence_index],
                    "sequence_frame_index": frame_index,
                    "recording_id": dataset.recording_ids[sequence_index],
                    "drive_id": dataset.drive_ids[sequence_index],
                    "pair_index": dataset.pair_indices[sequence_index, frame_index],
                    "joint_negative_log_likelihood_standardized": (
                        -combined_log_standardized[sequence_index, frame_index]
                    ),
                    "joint_negative_log_likelihood_physical": (
                        -combined_log_physical[sequence_index, frame_index]
                    ),
                    "squared_mahalanobis_per_dimension": (
                        combined_squared[sequence_index, frame_index]
                        / len(CANONICAL_MODEL_STATIONS_M)
                    ),
                    "sample_mean_prediction_rmse_m": (
                        overall_evaluation.frame_rmse_m[
                            sequence_index,
                            frame_index,
                        ]
                    ),
                    "energy_score_m": overall_evaluation.frame_energy_score_m[
                        sequence_index,
                        frame_index,
                    ],
                }
            )

    write_csv_rows(
        arguments.output_directory / "gaussian_sequence_evaluation.csv",
        EVALUATION_FIELDS,
        evaluation_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_sequence_station_evaluation.csv",
        STATION_FIELDS,
        station_rows,
    )
    write_csv_rows(
        arguments.output_directory / "gaussian_sequence_frame_evaluation.csv",
        FRAME_FIELDS,
        frame_rows,
    )
    write_strict_json(
        arguments.output_directory / "gaussian_sequence_fold_models.json",
        {
            "version": VERSION,
            "status": "complete",
            "purpose": "leave_one_physical_drive_out_sequence_gaussian_models",
            "models": fold_models,
        },
    )

    all_data_standardizer = SequenceStandardizer.fit(
        dataset,
        train_drive_ids=tuple(sorted(set(dataset.drive_ids.tolist()))),
    )
    all_data_standardized = all_data_standardizer.standardized_copy(dataset)
    final_model = SequenceConditionalGaussian(
        covariance_regularization=regularization
    )
    final_report = final_model.fit(all_data_standardized)
    write_strict_json(
        arguments.output_directory / "gaussian_sequence_model.json",
        {
            "version": VERSION,
            "status": "complete",
            "role": "descriptive_all_development_data_fit_after_evaluation",
            "not_an_untouched_final_model": True,
            "standardizer": all_data_standardizer.to_dict(),
            "fit_report": {
                "training_sequence_count": final_report.training_sequence_count,
                "metrics": dict(final_report.metrics),
                "warnings": list(final_report.warnings),
            },
            "model": final_model.to_dict(),
        },
    )
    plot_sequence_gaussian_diagnostics(
        arguments.output_directory / "gaussian_sequence_diagnostics.png",
        stations_m=CANONICAL_MODEL_STATIONS_M,
        evaluation_rows=evaluation_rows,
        station_rows=station_rows,
    )

    output_names = (
        "gaussian_sequence_evaluation.csv",
        "gaussian_sequence_station_evaluation.csv",
        "gaussian_sequence_frame_evaluation.csv",
        "gaussian_sequence_fold_models.json",
        "gaussian_sequence_model.json",
        "gaussian_sequence_diagnostics.png",
    )
    overall_row = next(
        row for row in evaluation_rows if row["scope"] == "overall_cross_validated"
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "common_sequence_contract_conditional_gaussian_temporal_null",
        "project_role": "canonical_thesis_implementation",
        "source_sequence_version": source_summary["version"],
        "source_files_sha256": {
            name: _sha256(arguments.sequential_dataset_directory / name)
            for name in sorted(REQUIRED_INPUT_FILES)
        },
        "output_files_sha256": {
            name: _sha256(arguments.output_directory / name)
            for name in output_names
        },
        "model_name": "sequence_conditional_gaussian",
        "model_family": "conditional_multivariate_gaussian",
        "feature_schema": source_summary["feature_schema"],
        "feature_names": source_summary["feature_names"],
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "sequence_count": dataset.sequence_count,
        "frame_count": dataset.frame_count,
        "drive_count": len(set(dataset.drive_ids.tolist())),
        "evaluation_scheme": "leave_one_physical_drive_out",
        "same_sequence_folds_as_future_models": True,
        "fold_standardization_source": "v0.9.0_training_drive_only",
        "covariance_regularization_standardized2": regularization,
        "sample_count": sample_count,
        "random_seed": seed,
        "sample_metrics_are_common_to_all_model_families": True,
        "energy_score_definition": (
            "mean_norm_sample_minus_observation_minus_half_mean_norm_independent_sample_pairs"
        ),
        "temporal_dependency_order": 0,
        "temporally_conditionally_independent": True,
        "sequence_shape_used_without_transition_state": True,
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
        "data_role": "development_only",
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "final_all_data_fit_is_descriptive_only": True,
        "next_model_phase": "aiohmm_on_identical_sequences_folds_and_metrics",
        "pair_count_is_independent_sample_size": False,
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "scientific_limitations": [
            "The Gaussian uses no recurrent or transition state.",
            "Only two physical drives are available for development evaluation.",
            "RLMB is a pseudo-reference, not independent physical ground truth.",
            "Sample metrics have finite Monte Carlo error under the recorded seed.",
        ],
        "confidentiality": "Model outputs derive from private BMW measurements.",
    }
    write_strict_json(
        arguments.output_directory / "gaussian_sequence_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "EVALUATION_FIELDS",
    "FRAME_FIELDS",
    "STATION_FIELDS",
    "VERSION",
    "run_sequence_gaussian",
]
