"""Build the v0.9.0 common sequential dataset from a frozen v0.8.0 cohort."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    ResidualDatasetContractError,
    residual_column_name,
)
from ..domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
    SequenceFrame,
    SequenceStandardizer,
    SequentialResidualDataset,
    build_contiguous_sequences,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.sequence_dataset import plot_sequence_dataset_diagnostics

VERSION = "0.9.0"
ACCEPTED_COHORT_VERSION = "0.8.0"
ACCEPTED_COHORT_PURPOSE = "frozen_complete_feature_conditional_h100_cohort"

SEQUENCE_SUMMARY_FIELDS = (
    "sequence_id",
    "recording_id",
    "drive_id",
    "segment_index",
    "start_reason",
    "preceding_pair_index_gap",
    "preceding_time_gap_ms",
    "start_pair_index",
    "end_pair_index",
    "frame_count",
    "duration_s",
    "minimum_interval_ms",
    "median_interval_ms",
    "maximum_interval_ms",
)
FRAME_INDEX_FIELDS = (
    "sequence_id",
    "sequence_frame_index",
    "recording_id",
    "drive_id",
    "pair_index",
    "estimate_message_index",
    "estimate_source_time_ns_private",
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


def _required_nonnegative_integer(row: Mapping[str, Any], key: str) -> int:
    raw = str(row.get(key, "")).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be an integer") from error
    if value < 0:
        raise ResidualDatasetContractError(f"{key} must be nonnegative")
    return value


def _required_finite_float(row: Mapping[str, Any], key: str) -> float:
    raw = str(row.get(key, "")).strip()
    try:
        value = float(raw)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be numeric") from error
    if not math.isfinite(value):
        raise ResidualDatasetContractError(f"{key} must be finite")
    return value


def _required_summary_integer(summary: Mapping[str, Any], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResidualDatasetContractError(f"{key} must be a nonnegative integer")
    return value


def _load_source_frames(
    input_directory: Path,
) -> tuple[list[SequenceFrame], Mapping[str, Any]]:
    cohort_path = input_directory / "conditional_cohort.csv"
    summary_path = input_directory / "conditional_cohort_summary.json"
    for path in (cohort_path, summary_path):
        if not path.is_file():
            raise FileNotFoundError(f"required v0.8.0 cohort output not found: {path}")
    summary = _read_strict_json(summary_path)
    if not isinstance(summary, Mapping):
        raise ResidualDatasetContractError("conditional cohort summary must be an object")
    if summary.get("version") != ACCEPTED_COHORT_VERSION:
        raise ResidualDatasetContractError("conditional cohort version must be 0.8.0")
    if summary.get("status") != "complete":
        raise ResidualDatasetContractError("conditional cohort must be complete")
    if summary.get("purpose") != ACCEPTED_COHORT_PURPOSE:
        raise ResidualDatasetContractError("conditional cohort purpose is not accepted")
    if summary.get("feature_names") != list(BMW_CONDITION_FEATURE_NAMES):
        raise ResidualDatasetContractError("BMW condition schema differs from v1")
    if summary.get("canonical_station_grid_m") != list(
        CANONICAL_MODEL_STATIONS_M
    ):
        raise ResidualDatasetContractError("conditional cohort grid must be H100")
    if summary.get("constant_pair_count_at_every_station") is not True:
        raise ResidualDatasetContractError("sequential source must use complete H100 rows")
    if summary.get("selection_uses_residual_values") is not False:
        raise ResidualDatasetContractError("source cohort selection used residual outcomes")
    if summary.get("cross_mcap_feature_extraction") is not False:
        raise ResidualDatasetContractError("cross-MCAP feature extraction is forbidden")
    if summary.get("speed_extrapolation") is not False:
        raise ResidualDatasetContractError("speed extrapolation is forbidden")

    expected_header = (*RESIDUAL_VECTOR_FIELDS, *BMW_CONDITION_FEATURE_NAMES)
    with cohort_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected_header:
            raise ResidualDatasetContractError(
                "conditional_cohort.csv header differs from the v0.8.0 contract"
            )
        rows = list(reader)
    if _required_summary_integer(summary, "selected_vector_count") != len(rows):
        raise ResidualDatasetContractError("source cohort row count does not reconcile")

    frames: list[SequenceFrame] = []
    for row_number, row in enumerate(rows, start=2):
        recording_id = str(row.get("recording_id", "")).strip()
        drive_id = str(row.get("drive_id", "")).strip()
        if not recording_id or not drive_id:
            raise ResidualDatasetContractError(
                f"empty cohort provenance at row {row_number}"
            )
        try:
            frames.append(
                SequenceFrame(
                    recording_id=recording_id,
                    drive_id=drive_id,
                    pair_index=_required_nonnegative_integer(row, "pair_index"),
                    estimate_message_index=_required_nonnegative_integer(
                        row,
                        "estimate_message_index",
                    ),
                    estimate_source_time_ns_private=_required_nonnegative_integer(
                        row,
                        "estimate_source_time_ns_private",
                    ),
                    conditions=np.asarray(
                        [
                            _required_finite_float(row, name)
                            for name in BMW_CONDITION_FEATURE_NAMES
                        ],
                        dtype=np.float64,
                    ),
                    residuals_m=np.asarray(
                        [
                            _required_finite_float(
                                row,
                                residual_column_name(station),
                            )
                            for station in CANONICAL_MODEL_STATIONS_M
                        ],
                        dtype=np.float64,
                    ),
                )
            )
        except (TypeError, ValueError) as error:
            raise ResidualDatasetContractError(
                f"invalid sequential source row {row_number}: {error}"
            ) from error

    actual_drive_counts = dict(sorted(Counter(frame.drive_id for frame in frames).items()))
    actual_recording_counts = dict(
        sorted(Counter(frame.recording_id for frame in frames).items())
    )
    if summary.get("selected_vector_count_by_drive") != actual_drive_counts:
        raise ResidualDatasetContractError("source drive counts do not reconcile")
    if summary.get("selected_vector_count_by_recording") != actual_recording_counts:
        raise ResidualDatasetContractError("source recording counts do not reconcile")
    return frames, summary


def _sequence_summary_rows(
    dataset: SequentialResidualDataset,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence in dataset.sequences:
        intervals = sequence.interval_ms
        rows.append(
            {
                "sequence_id": sequence.sequence_id,
                "recording_id": sequence.recording_id,
                "drive_id": sequence.drive_id,
                "segment_index": sequence.segment_index,
                "start_reason": sequence.start_reason,
                "preceding_pair_index_gap": sequence.preceding_pair_index_gap,
                "preceding_time_gap_ms": sequence.preceding_time_gap_ms,
                "start_pair_index": sequence.frames[0].pair_index,
                "end_pair_index": sequence.frames[-1].pair_index,
                "frame_count": sequence.length,
                "duration_s": sequence.duration_s,
                "minimum_interval_ms": (
                    float(np.min(intervals)) if len(intervals) else None
                ),
                "median_interval_ms": (
                    float(np.median(intervals)) if len(intervals) else None
                ),
                "maximum_interval_ms": (
                    float(np.max(intervals)) if len(intervals) else None
                ),
            }
        )
    return rows


def _frame_index_rows(
    dataset: SequentialResidualDataset,
) -> list[dict[str, Any]]:
    return [
        {
            "sequence_id": sequence.sequence_id,
            "sequence_frame_index": frame_index,
            "recording_id": frame.recording_id,
            "drive_id": frame.drive_id,
            "pair_index": frame.pair_index,
            "estimate_message_index": frame.estimate_message_index,
            "estimate_source_time_ns_private": (
                frame.estimate_source_time_ns_private
            ),
        }
        for sequence in dataset.sequences
        for frame_index, frame in enumerate(sequence.frames)
    ]


def _save_raw_dataset_npz(
    path: Path,
    dataset: SequentialResidualDataset,
) -> None:
    padded = dataset.to_padded()
    np.savez_compressed(
        path,
        schema_version=np.asarray(VERSION),
        standardized=np.asarray(False),
        sequence_ids=padded.sequence_ids,
        recording_ids=padded.recording_ids,
        drive_ids=padded.drive_ids,
        lengths=padded.lengths,
        conditions=padded.conditions,
        residuals_m=padded.residuals_m,
        valid_mask=padded.valid_mask,
        pair_indices=padded.pair_indices,
        estimate_message_indices=padded.estimate_message_indices,
        estimate_source_times_ns_private=(
            padded.estimate_source_times_ns_private
        ),
        feature_names=np.asarray(padded.feature_names),
        stations_m=np.asarray(padded.stations_m, dtype=np.float64),
    )


def _raw_lag_one_correlations(
    dataset: SequentialResidualDataset,
) -> np.ndarray:
    correlations: list[float] = []
    for station_index in range(len(CANONICAL_MODEL_STATIONS_M)):
        previous: list[float] = []
        current: list[float] = []
        for sequence in dataset.sequences:
            previous.extend(
                frame.residuals_m[station_index]
                for frame in sequence.frames[:-1]
            )
            current.extend(
                frame.residuals_m[station_index]
                for frame in sequence.frames[1:]
            )
        if len(previous) < 2 or np.std(previous) == 0.0 or np.std(current) == 0.0:
            correlations.append(float("nan"))
        else:
            correlations.append(float(np.corrcoef(previous, current)[0, 1]))
    values = np.asarray(correlations, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ResidualDatasetContractError(
            "raw lag-one correlations require nonconstant station residuals"
        )
    return values


def run_sequence_dataset(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Create the shared physical-unit sequence dataset without fitting a model."""

    maximum_gap_ms = float(arguments.maximum_contiguous_gap_ms)
    if not math.isfinite(maximum_gap_ms) or maximum_gap_ms <= 0.0:
        raise ValueError("maximum-contiguous-gap-ms must be finite and positive")
    frames, source_summary = _load_source_frames(
        arguments.conditional_gaussian_directory
    )
    dataset = build_contiguous_sequences(
        frames,
        maximum_contiguous_gap_ms=maximum_gap_ms,
    )
    if dataset.frame_count != len(frames):
        raise ResidualDatasetContractError("sequence construction lost source frames")
    if len(dataset.drive_ids) < 2:
        raise ResidualDatasetContractError(
            "development fold construction requires at least two physical drives"
        )

    _ensure_empty_output(arguments.output_directory)
    sequence_rows = _sequence_summary_rows(dataset)
    frame_rows = _frame_index_rows(dataset)
    write_csv_rows(
        arguments.output_directory / "sequence_summary.csv",
        SEQUENCE_SUMMARY_FIELDS,
        sequence_rows,
    )
    write_csv_rows(
        arguments.output_directory / "sequence_frame_index.csv",
        FRAME_INDEX_FIELDS,
        frame_rows,
    )
    raw_npz_path = arguments.output_directory / "sequential_dataset.npz"
    _save_raw_dataset_npz(raw_npz_path, dataset)

    padded = dataset.to_padded()
    folds: list[dict[str, Any]] = []
    standardizers: dict[str, Any] = {}
    for held_out_drive_id in dataset.drive_ids:
        training_drive_ids = tuple(
            drive_id
            for drive_id in dataset.drive_ids
            if drive_id != held_out_drive_id
        )
        standardizer = SequenceStandardizer.fit(
            padded,
            train_drive_ids=training_drive_ids,
        )
        fold_id = f"held_out_{held_out_drive_id}"
        training_sequences = [
            sequence.sequence_id
            for sequence in dataset.sequences
            if sequence.drive_id in training_drive_ids
        ]
        test_sequences = [
            sequence.sequence_id
            for sequence in dataset.sequences
            if sequence.drive_id == held_out_drive_id
        ]
        folds.append(
            {
                "fold_id": fold_id,
                "training_drive_ids": list(training_drive_ids),
                "held_out_drive_id": held_out_drive_id,
                "training_sequence_ids": training_sequences,
                "test_sequence_ids": test_sequences,
                "training_sequence_count": len(training_sequences),
                "test_sequence_count": len(test_sequences),
                "training_frame_count": int(
                    sum(
                        sequence.length
                        for sequence in dataset.sequences
                        if sequence.drive_id in training_drive_ids
                    )
                ),
                "test_frame_count": int(
                    sum(
                        sequence.length
                        for sequence in dataset.sequences
                        if sequence.drive_id == held_out_drive_id
                    )
                ),
            }
        )
        standardizers[fold_id] = standardizer.to_dict()
    fold_manifest = {
        "version": VERSION,
        "status": "complete",
        "purpose": "physical_drive_grouped_development_folds",
        "scheme": "leave_one_physical_drive_out",
        "frame_level_random_split": False,
        "recording_level_random_split": False,
        "same_drive_may_cross_fold": False,
        "data_role": "development_only",
        "untouched_final_test_present": False,
        "hyperparameter_selection_authorized": False,
        "folds": folds,
    }
    write_strict_json(
        arguments.output_directory / "drive_fold_manifest.json",
        fold_manifest,
    )
    write_strict_json(
        arguments.output_directory / "drive_fold_standardizers.json",
        {
            "version": VERSION,
            "status": "complete",
            "purpose": "training_drive_only_fold_standardizers",
            "standardizers": standardizers,
        },
    )

    raw_lag_correlations = _raw_lag_one_correlations(dataset)
    plot_sequence_dataset_diagnostics(
        arguments.output_directory / "sequence_dataset_diagnostics.png",
        dataset=dataset,
        raw_lag_one_correlations=raw_lag_correlations,
    )

    intervals = np.concatenate(
        [
            sequence.interval_ms
            for sequence in dataset.sequences
            if sequence.length > 1
        ]
    )
    start_reason_counts = Counter(
        sequence.start_reason for sequence in dataset.sequences
    )
    sequence_counts_by_drive = Counter(
        sequence.drive_id for sequence in dataset.sequences
    )
    frame_counts_by_drive = Counter(
        frame.drive_id for frame in frames
    )
    output_names = (
        "sequential_dataset.npz",
        "sequence_summary.csv",
        "sequence_frame_index.csv",
        "drive_fold_manifest.json",
        "drive_fold_standardizers.json",
        "sequence_dataset_diagnostics.png",
    )
    summary = {
        "version": VERSION,
        "status": "complete",
        "purpose": "common_three_model_sequential_dataset",
        "project_role": "canonical_thesis_implementation",
        "source_cohort_version": source_summary["version"],
        "source_cohort_purpose": source_summary["purpose"],
        "source_files_sha256": {
            "conditional_cohort.csv": _sha256(
                arguments.conditional_gaussian_directory
                / "conditional_cohort.csv"
            ),
            "conditional_cohort_summary.json": _sha256(
                arguments.conditional_gaussian_directory
                / "conditional_cohort_summary.json"
            ),
        },
        "output_files_sha256": {
            name: _sha256(arguments.output_directory / name)
            for name in output_names
        },
        "feature_schema": "bmw_condition_schema_v1",
        "feature_names": list(BMW_CONDITION_FEATURE_NAMES),
        "feature_count": len(BMW_CONDITION_FEATURE_NAMES),
        "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
        "dimension": len(CANONICAL_MODEL_STATIONS_M),
        "source_frame_count": len(frames),
        "retained_frame_count": dataset.frame_count,
        "sequence_count": len(dataset.sequences),
        "recording_count": len({frame.recording_id for frame in frames}),
        "drive_count": len(dataset.drive_ids),
        "sequence_count_by_drive": dict(sorted(sequence_counts_by_drive.items())),
        "frame_count_by_drive": dict(sorted(frame_counts_by_drive.items())),
        "sequence_start_reason_counts": dict(sorted(start_reason_counts.items())),
        "maximum_contiguous_gap_ms": maximum_gap_ms,
        "minimum_within_sequence_interval_ms": float(np.min(intervals)),
        "median_within_sequence_interval_ms": float(np.median(intervals)),
        "maximum_within_sequence_interval_ms": float(np.max(intervals)),
        "total_within_sequence_duration_s": float(
            sum(sequence.duration_s for sequence in dataset.sequences)
        ),
        "minimum_sequence_frame_count": min(
            sequence.length for sequence in dataset.sequences
        ),
        "maximum_sequence_frame_count": max(
            sequence.length for sequence in dataset.sequences
        ),
        "raw_residual_lag_one_correlation_by_station": {
            f"{int(station):03d}m": float(raw_lag_correlations[index])
            for index, station in enumerate(CANONICAL_MODEL_STATIONS_M)
        },
        "median_raw_residual_lag_one_correlation": float(
            np.median(raw_lag_correlations)
        ),
        "model_training_performed": False,
        "conditional_gaussian_finalized": False,
        "conditional_gaussian_status": (
            "v0.8.0_baseline_complete_feature_and_regularization_review_pending"
        ),
        "data_role": "development_only",
        "untouched_final_test_drive_count": 0,
        "final_model_selection_authorized": False,
        "additional_independent_drives_required_for_final_comparison": True,
        "next_model_phase": "gaussian_sequence_parity_then_aiohmm",
        "pair_count_is_independent_sample_size": False,
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "confidentiality": "Dataset contains private BMW-derived measurements.",
    }
    write_strict_json(
        arguments.output_directory / "sequential_dataset_summary.json",
        summary,
    )
    return summary, 0


__all__ = [
    "ACCEPTED_COHORT_VERSION",
    "FRAME_INDEX_FIELDS",
    "SEQUENCE_SUMMARY_FIELDS",
    "VERSION",
    "run_sequence_dataset",
]
