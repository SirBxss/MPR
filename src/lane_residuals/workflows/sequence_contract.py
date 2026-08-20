"""Shared validation for model workflows consuming the v0.9 sequence contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..domain.residual_dataset import ResidualDatasetContractError
from ..domain.sequence_dataset import PaddedSequenceDataset, SequenceStandardizer
from ..io.sequence_dataset import load_sequence_dataset_npz

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


def read_strict_json(path: Path) -> Any:
    """Load JSON while rejecting JavaScript-style non-finite constants."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_empty_output_directory(path: Path) -> None:
    """Create an output directory only when no prior result can be overwritten."""

    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def load_validated_sequence_sources(
    input_directory: Path,
) -> tuple[
    PaddedSequenceDataset,
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
]:
    """Load the exact, hash-reconciled v0.9 dataset and fold evidence."""

    if not input_directory.is_dir():
        raise FileNotFoundError(
            f"v0.9.0 sequence directory not found: {input_directory}"
        )
    actual_files = {path.name for path in input_directory.iterdir() if path.is_file()}
    if actual_files != REQUIRED_INPUT_FILES:
        raise ResidualDatasetContractError(
            "v0.9.0 sequence directory filename set differs from the contract"
        )
    summary = read_strict_json(input_directory / "sequential_dataset_summary.json")
    manifest = read_strict_json(input_directory / "drive_fold_manifest.json")
    standardizers = read_strict_json(
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
        raise ResidualDatasetContractError(
            "sequence data role must remain development-only"
        )
    if summary.get("final_model_selection_authorized") is not False:
        raise ResidualDatasetContractError("final model selection cannot be authorized")
    expected_hashes = summary.get("output_files_sha256")
    if not isinstance(expected_hashes, Mapping):
        raise ResidualDatasetContractError("source output hashes are missing")
    expected_hashed_names = REQUIRED_INPUT_FILES - {
        "sequential_dataset_summary.json"
    }
    if set(expected_hashes) != expected_hashed_names:
        raise ResidualDatasetContractError("source output hash set is incomplete")
    for name, expected in expected_hashes.items():
        path = input_directory / str(name)
        if not path.is_file() or sha256_file(path) != expected:
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
        raise ResidualDatasetContractError(
            "source drive-fold manifest is not accepted"
        )
    if (
        standardizers.get("version") != ACCEPTED_SEQUENCE_VERSION
        or standardizers.get("status") != "complete"
    ):
        raise ResidualDatasetContractError(
            "source fold standardizers are not accepted"
        )
    return dataset, summary, manifest, standardizers


def validated_fold_contracts(
    dataset: PaddedSequenceDataset,
    manifest: Mapping[str, Any],
    standardizer_payload: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], SequenceStandardizer]]:
    """Recompute transforms and enforce exact leave-one-drive-out membership."""

    folds = manifest.get("folds")
    payloads = standardizer_payload.get("standardizers")
    if not isinstance(folds, list) or not isinstance(payloads, Mapping):
        raise ResidualDatasetContractError(
            "fold definitions or transforms are missing"
        )
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
        training_drives = tuple(
            sorted(str(value) for value in fold.get("training_drive_ids", ()))
        )
        if (
            not fold_id
            or held_out not in all_drives
            or held_out in training_drives
            or set(training_drives) | {held_out} != all_drives
        ):
            raise ResidualDatasetContractError(
                f"invalid physical-drive fold: {fold_id}"
            )
        if fold_id not in payloads:
            raise ResidualDatasetContractError(
                f"missing fold standardizer: {fold_id}"
            )
        standardizer = SequenceStandardizer.from_dict(payloads[fold_id])
        if standardizer.train_drive_ids != training_drives:
            raise ResidualDatasetContractError(
                f"fold transform drive mismatch: {fold_id}"
            )
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
                stored_values, recomputed_values, rtol=0.0, atol=1e-12
            ):
                raise ResidualDatasetContractError(
                    f"fold transform does not reproduce training rows: {fold_id}"
                )
        training_sequences = set(
            str(value) for value in fold.get("training_sequence_ids", ())
        )
        test_sequences = set(
            str(value) for value in fold.get("test_sequence_ids", ())
        )
        expected_training = set(
            dataset.sequence_ids[np.isin(dataset.drive_ids, training_drives)].tolist()
        )
        expected_test = set(
            dataset.sequence_ids[dataset.drive_ids == held_out].tolist()
        )
        if training_sequences != expected_training or test_sequences != expected_test:
            raise ResidualDatasetContractError(
                f"fold sequence mismatch: {fold_id}"
            )
        if (
            fold.get("training_frame_count") != recomputed.training_frame_count
            or fold.get("test_frame_count")
            != int(np.sum(dataset.lengths[dataset.drive_ids == held_out]))
        ):
            raise ResidualDatasetContractError(
                f"fold frame count mismatch: {fold_id}"
            )
        if (
            training_sequences & test_sequences
            or training_sequences | test_sequences != all_sequences
        ):
            raise ResidualDatasetContractError(
                f"fold sequence leakage: {fold_id}"
            )
        held_out_drives.add(held_out)
        held_out_sequences.update(test_sequences)
        result.append((fold, standardizer))
    if (
        len(result) != len(all_drives)
        or held_out_drives != all_drives
        or held_out_sequences != all_sequences
    ):
        raise ResidualDatasetContractError(
            "folds do not test every drive and sequence once"
        )
    if set(payloads) != {str(fold["fold_id"]) for fold in folds}:
        raise ResidualDatasetContractError(
            "unexpected fold standardizer payload"
        )
    return result


__all__ = [
    "ACCEPTED_SEQUENCE_PURPOSE",
    "ACCEPTED_SEQUENCE_VERSION",
    "REQUIRED_INPUT_FILES",
    "ensure_empty_output_directory",
    "load_validated_sequence_sources",
    "read_strict_json",
    "sha256_file",
    "validated_fold_contracts",
]
