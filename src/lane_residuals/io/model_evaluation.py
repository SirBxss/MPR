"""Strict loading of the frozen expanded-data model-evaluation baseline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.model_evaluation import DriveGroupedFold
from .expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    read_json_object,
    sha256_file,
)

GAUSSIAN_VERSION = "0.14.0"
GAUSSIAN_REQUIRED_FILES = frozenset(
    {
        "drive_grouped_evaluation_contract.json",
        "gaussian_grouped_evaluation.csv",
        "gaussian_grouped_station_evaluation.csv",
        "gaussian_grouped_frame_evaluation.csv",
        "gaussian_grouped_models.json",
        "gaussian_grouped_diagnostics.png",
        "gaussian_grouped_summary.json",
    }
)


def load_expanded_gaussian_baseline(
    directory: str | Path,
    *,
    source_files_sha256: Mapping[str, str],
    folds: Sequence[DriveGroupedFold],
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    """Validate v0.14 as the immutable comparison protocol for later models."""

    source = Path(directory)
    if not source.is_dir():
        raise FileNotFoundError(f"v0.14.0 Gaussian directory not found: {source}")
    actual = {path.name for path in source.iterdir() if path.is_file()}
    if actual != GAUSSIAN_REQUIRED_FILES:
        raise ExpandedSequenceContractError(
            "v0.14.0 Gaussian directory filename set differs from the contract"
        )
    summary = read_json_object(source / "gaussian_grouped_summary.json")
    protocol = read_json_object(source / "drive_grouped_evaluation_contract.json")
    if (
        summary.get("version") != GAUSSIAN_VERSION
        or summary.get("status") != "complete"
        or summary.get("purpose") != "expanded_drive_grouped_gaussian_rebaseline"
    ):
        raise ExpandedSequenceContractError("v0.14.0 Gaussian summary is not accepted")
    if (
        protocol.get("version") != GAUSSIAN_VERSION
        or protocol.get("status") != "complete"
        or protocol.get("purpose")
        != "leakage_safe_drive_grouped_thesis_model_evaluation_contract"
    ):
        raise ExpandedSequenceContractError("v0.14.0 evaluation protocol is not accepted")
    if summary.get("final_model_selection_authorized") is not False:
        raise ExpandedSequenceContractError("v0.14.0 cannot authorize final selection")
    if (
        summary.get("source_dataset_version") != "0.13.1"
        or summary.get("evaluation_scheme")
        != "leave_one_clean_physical_drive_out"
        or summary.get("random_frame_splits_used") is not False
        or summary.get("mixed_source_results_are_supplementary_only") is not True
        or protocol.get("fold_count") != len(folds)
        or protocol.get("untouched_final_test_drive_count") != 0
    ):
        raise ExpandedSequenceContractError("v0.14.0 evaluation policy differs")
    expected_outputs = summary.get("output_files_sha256")
    hashed_names = GAUSSIAN_REQUIRED_FILES - {"gaussian_grouped_summary.json"}
    if not isinstance(expected_outputs, Mapping) or set(expected_outputs) != hashed_names:
        raise ExpandedSequenceContractError("v0.14.0 output hash set differs")
    hashes: dict[str, str] = {}
    for name in sorted(GAUSSIAN_REQUIRED_FILES):
        digest = sha256_file(source / name)
        hashes[name] = digest
        if name != "gaussian_grouped_summary.json" and expected_outputs.get(name) != digest:
            raise ExpandedSequenceContractError(f"v0.14.0 output hash mismatch: {name}")
    expected_source = dict(
        sorted((str(key), str(value)) for key, value in source_files_sha256.items())
    )
    if (
        summary.get("source_files_sha256") != expected_source
        or protocol.get("source_files_sha256") != expected_source
    ):
        raise ExpandedSequenceContractError("v0.14.0 source lineage differs from v0.13.1")
    stored_folds = protocol.get("folds")
    expected_folds = [fold.to_dict() for fold in folds]
    if stored_folds != expected_folds:
        raise ExpandedSequenceContractError("v0.14.0 clean-drive folds or transforms differ")
    if summary.get("primary_clean_drive_ids") != [
        fold.held_out_drive_id for fold in folds
    ]:
        raise ExpandedSequenceContractError("v0.14.0 primary drive cohort differs")
    if (
        protocol.get("split_scheme") != "leave_one_clean_physical_drive_out"
        or protocol.get("random_frame_splits_permitted") is not False
        or protocol.get("same_physical_drive_may_cross_fold") is not False
        or protocol.get("supplementary_cohort", {}).get(
            "never_used_for_fit_or_primary_model_comparison"
        )
        is not True
    ):
        raise ExpandedSequenceContractError("v0.14.0 split policy differs")
    models = summary.get("models")
    if not isinstance(models, Mapping) or set(models) != {
        "unconditional_gaussian",
        "conditional_gaussian",
    }:
        raise ExpandedSequenceContractError("v0.14.0 Gaussian models are incomplete")
    monte_carlo = protocol.get("monte_carlo")
    if (
        not isinstance(monte_carlo, Mapping)
        or monte_carlo.get("common_random_numbers_across_gaussian_baselines") is not True
        or summary.get("sample_count") != monte_carlo.get("sample_count")
        or summary.get("random_seed") != monte_carlo.get("base_seed")
    ):
        raise ExpandedSequenceContractError("v0.14.0 Monte Carlo protocol differs")
    return summary, protocol, hashes


__all__ = [
    "GAUSSIAN_REQUIRED_FILES",
    "GAUSSIAN_VERSION",
    "load_expanded_gaussian_baseline",
]
