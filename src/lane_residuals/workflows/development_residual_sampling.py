"""Generate planner-facing residual sequences from the frozen v0.15.4 model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.reports import write_strict_json
from ..modeling.development_residual import DevelopmentResidualModel
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.15.4"
INPUT_KEYS = frozenset({"conditions", "lengths", "sequence_ids", "feature_names"})
SAMPLES_FILENAME = "sampled_residual_sequences.npz"
SUMMARY_FILENAME = "sampled_residual_sequences_summary.json"


def _load_condition_sequences(
    path: Path,
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.str_]]:
    if not path.is_file():
        raise FileNotFoundError(f"planner condition archive not found: {path}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != INPUT_KEYS:
                raise ValueError(
                    "planner condition archive keys must be exactly "
                    f"{sorted(INPUT_KEYS)}"
                )
            conditions = np.asarray(archive["conditions"], dtype=np.float64)
            raw_lengths = np.asarray(archive["lengths"])
            raw_sequence_ids = np.asarray(archive["sequence_ids"])
            raw_feature_names = np.asarray(archive["feature_names"])
            if raw_lengths.dtype == np.bool_ or not np.issubdtype(
                raw_lengths.dtype, np.integer
            ):
                raise TypeError("planner condition lengths must use an integer dtype")
            if raw_sequence_ids.dtype.kind not in {"U", "S"}:
                raise TypeError("planner sequence IDs must use a string dtype")
            if raw_feature_names.dtype.kind not in {"U", "S"}:
                raise TypeError("planner feature names must use a string dtype")
            lengths = np.asarray(raw_lengths, dtype=np.int64)
            sequence_ids = np.asarray(raw_sequence_ids, dtype=np.str_)
            feature_names = tuple(
                str(value)
                for value in np.asarray(raw_feature_names, dtype=np.str_).tolist()
            )
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"invalid planner condition archive: {error}") from error
    if feature_names != BMW_CONDITION_FEATURE_NAMES:
        raise ValueError("planner condition feature order differs from BMW schema v1")
    if conditions.ndim != 3 or conditions.shape[2] != len(feature_names):
        raise ValueError("planner conditions must have shape [B,T,6]")
    if lengths.shape != (conditions.shape[0],):
        raise ValueError("planner condition lengths must have shape [B]")
    if sequence_ids.shape != (conditions.shape[0],):
        raise ValueError("planner sequence IDs must have shape [B]")
    if any(not value for value in sequence_ids.tolist()) or len(
        set(sequence_ids.tolist())
    ) != len(sequence_ids):
        raise ValueError("planner sequence IDs must be nonempty and unique")
    return conditions, lengths, sequence_ids


def run_development_residual_sampling(
    *,
    model_path: Path,
    condition_archive: Path,
    output_directory: Path,
    sample_count: int,
    seed: int,
) -> tuple[dict[str, Any], int]:
    """Sample physical H100 residuals without applying them to planner geometry."""

    if isinstance(sample_count, bool) or not isinstance(
        sample_count, (int, np.integer)
    ):
        raise TypeError("sample_count must be an integer")
    if sample_count < 1:
        raise ValueError("sample_count must be positive")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    model = DevelopmentResidualModel.load(model_path)
    conditions, lengths, sequence_ids = _load_condition_sequences(
        condition_archive
    )
    samples = model.sample(
        conditions,
        lengths,
        sample_count=sample_count,
        seed=seed,
    )

    ensure_empty_output_directory(output_directory)
    sample_path = output_directory / SAMPLES_FILENAME
    np.savez_compressed(
        sample_path,
        residual_samples_m=samples.values,
        lengths=samples.lengths,
        stations_m=samples.stations_m,
        sequence_ids=sequence_ids,
        feature_names=np.asarray(model.feature_names, dtype=np.str_),
    )
    summary: dict[str, Any] = {
        "version": VERSION,
        "status": "complete",
        "purpose": "planner_facing_development_residual_sequence_sampling",
        "development_model_file_sha256": sha256_file(model_path),
        "condition_archive_sha256": sha256_file(condition_archive),
        "sample_file": SAMPLES_FILENAME,
        "sample_file_sha256": sha256_file(sample_path),
        "sample_count": sample_count,
        "random_seed": seed,
        "sequence_count": int(len(lengths)),
        "maximum_sequence_length": int(conditions.shape[1]),
        "active_frame_count": int(np.sum(lengths)),
        "feature_names_in_required_order": list(model.feature_names),
        "stations_m": list(model.stations_m),
        "residual_unit": "m",
        "residual_definition": (
            "EDP estimate minus spatially aligned RLMB pseudo-reference, "
            "projected onto the pseudo-reference left unit normal"
        ),
        "positive_direction": (
            "left of the pseudo-reference with respect to increasing station"
        ),
        "sampling_is_free_running": True,
        "generated_previous_residual_used": True,
        "sequence_reset_applied_once_per_input_sequence": True,
        "independent_frame_sampling_used": False,
        "path_geometry_modified": False,
        "planner_executed": False,
        "planner_benefit_claimed": False,
        "final_model_selection_authorized": False,
        "next_phase": (
            "apply_sampled_signed_offsets_through_the_reviewed_BMW_"
            "reference_path_adapter"
        ),
        "confidentiality": (
            "Samples derive from a model fitted to private BMW measurements."
        ),
    }
    write_strict_json(output_directory / SUMMARY_FILENAME, summary)
    return summary, 0


__all__ = [
    "INPUT_KEYS",
    "SAMPLES_FILENAME",
    "SUMMARY_FILENAME",
    "VERSION",
    "run_development_residual_sampling",
]
