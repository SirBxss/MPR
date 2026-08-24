"""Strict model-facing loading for the accepted v0.13.1 dataset.

The expanded archive is frame-major because it is an immutable data product.
The thesis models consume padded sequences.  This module performs that one
deterministic conversion while retaining per-frame recording provenance and
failing closed on source hashes, cohort roles, ordering, and continuity.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    PaddedSequenceDataset,
)
from .expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    read_json_object,
    sha256_file,
)

VERSION = "0.13.1"
PURPOSE = (
    "quality_gated_expanded_sensor_topology_sequential_dataset_"
    "with_boundary_odometry_context"
)
CLEAN_DRIVE_CLASS = "clean_sensor"
MIXED_DRIVE_CLASS = "mixed_source_sensor_fragment"

REQUIRED_SOURCE_FILES = frozenset(
    {
        "expanded_profile_dataset.npz",
        "profile_eligibility_audit.csv",
        "sequence_manifest.csv",
        "sequence_summary_by_drive.csv",
        "cross_mcap_stitching_audit.csv",
        "boundary_odometry_context_audit.csv",
        "exclusion_reason_summary.csv",
        "v0130_parity_audit.json",
        "expanded_sequence_diagnostics.png",
        "expanded_sequence_contract.json",
        "train_only_standardization_metadata.json",
        "expanded_sequence_manifest.json",
        "expanded_sequence_provenance.json",
    }
)

REQUIRED_ARCHIVE_FIELDS = frozenset(
    {
        "conditions",
        "drive_ids",
        "eligibility",
        "estimate_message_indices",
        "exclusion_reasons",
        "mcap_basenames_private",
        "pair_indices",
        "recording_ids",
        "residuals_m",
        "sequence_ids",
        "speed_context_left_mcap_basenames_private",
        "speed_context_odometry_timestamps_ns_json_private",
        "speed_context_right_mcap_basenames_private",
        "speed_context_states",
        "stations_m",
        "timestamps_ns_private",
    }
)


@dataclass(frozen=True)
class ExpandedModelingDataset:
    """Validated physical-unit tensors plus exact per-frame provenance."""

    sequences: PaddedSequenceDataset
    recording_ids_by_frame: NDArray[np.str_] = field(repr=False)
    mcap_basenames_by_frame_private: NDArray[np.str_] = field(repr=False)
    clean_drive_ids: tuple[str, ...]
    mixed_drive_ids: tuple[str, ...]
    drive_class_by_id: Mapping[str, str]
    source_files_sha256: Mapping[str, str]
    source_contract: Mapping[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        recordings = np.asarray(self.recording_ids_by_frame, dtype=np.str_)
        basenames = np.asarray(self.mcap_basenames_by_frame_private, dtype=np.str_)
        expected_shape = self.sequences.time_mask.shape
        if recordings.shape != expected_shape or basenames.shape != expected_shape:
            raise ValueError("expanded frame provenance must have shape [B,T]")
        time_mask = self.sequences.time_mask
        if np.any(recordings[time_mask] == "") or np.any(basenames[time_mask] == ""):
            raise ValueError("active expanded frames require complete provenance")
        if np.any(recordings[~time_mask] != "") or np.any(basenames[~time_mask] != ""):
            raise ValueError("expanded frame provenance padding must be empty")
        all_drives = set(self.sequences.drive_ids.tolist())
        clean = set(self.clean_drive_ids)
        mixed = set(self.mixed_drive_ids)
        if not clean or clean & mixed or clean | mixed != all_drives:
            raise ValueError("clean and mixed drive cohorts must partition the dataset")
        if set(self.drive_class_by_id) != all_drives:
            raise ValueError("drive classes must cover every physical drive")
        if any(self.drive_class_by_id[value] != CLEAN_DRIVE_CLASS for value in clean):
            raise ValueError("clean drive class metadata is inconsistent")
        if any(self.drive_class_by_id[value] != MIXED_DRIVE_CLASS for value in mixed):
            raise ValueError("mixed drive class metadata is inconsistent")
        recordings.setflags(write=False)
        basenames.setflags(write=False)
        object.__setattr__(self, "recording_ids_by_frame", recordings)
        object.__setattr__(self, "mcap_basenames_by_frame_private", basenames)

    @property
    def primary(self) -> PaddedSequenceDataset:
        """Return the clean-sensor cohort used for primary evaluation."""

        return self.sequences.select_drive_ids(self.clean_drive_ids)

    @property
    def supplementary(self) -> PaddedSequenceDataset:
        """Return mixed-source fragments used only for secondary transfer checks."""

        return self.sequences.select_drive_ids(self.mixed_drive_ids)


def _read_sequence_classes(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    by_sequence: dict[str, str] = {}
    by_drive: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sequence_id", "drive_id", "drive_class", "frame_count"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ExpandedSequenceContractError("sequence manifest columns differ")
        for row in reader:
            sequence_id = row["sequence_id"]
            drive_id = row["drive_id"]
            drive_class = row["drive_class"]
            if not sequence_id or not drive_id or drive_class not in {
                CLEAN_DRIVE_CLASS,
                MIXED_DRIVE_CLASS,
            }:
                raise ExpandedSequenceContractError("invalid sequence cohort metadata")
            if sequence_id in by_sequence:
                raise ExpandedSequenceContractError("duplicate sequence manifest row")
            previous = by_drive.setdefault(drive_id, drive_class)
            if previous != drive_class:
                raise ExpandedSequenceContractError("one drive has multiple cohort roles")
            by_sequence[sequence_id] = drive_class
    if not by_sequence:
        raise ExpandedSequenceContractError("sequence manifest is empty")
    return by_sequence, by_drive


def _validate_source_directory(
    directory: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"v0.13.1 dataset directory not found: {directory}")
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != REQUIRED_SOURCE_FILES:
        raise ExpandedSequenceContractError(
            "v0.13.1 dataset directory filename set differs from the contract"
        )
    contract = read_json_object(directory / "expanded_sequence_contract.json")
    manifest = read_json_object(directory / "expanded_sequence_manifest.json")
    provenance = read_json_object(directory / "expanded_sequence_provenance.json")
    for name, payload in (("contract", contract), ("manifest", manifest)):
        if (
            payload.get("version") != VERSION
            or payload.get("purpose") != PURPOSE
            or payload.get("status") != "complete"
        ):
            raise ExpandedSequenceContractError(f"v0.13.1 {name} is not accepted")
        if payload.get("split_assignments_selected") is not False:
            raise ExpandedSequenceContractError("source split assignments must be unset")
        if payload.get("model_training_performed") is not False:
            raise ExpandedSequenceContractError("source must precede model training")
    if contract.get("model_hyperparameters_selected") is not False:
        raise ExpandedSequenceContractError("source model hyperparameters must be unset")
    generated = provenance.get("generated_outputs_sha256")
    expected_hashed = REQUIRED_SOURCE_FILES - {"expanded_sequence_provenance.json"}
    if not isinstance(generated, Mapping) or set(generated) != expected_hashed:
        raise ExpandedSequenceContractError("v0.13.1 generated hash set differs")
    actual_hashes: dict[str, str] = {}
    for name in sorted(REQUIRED_SOURCE_FILES):
        digest = sha256_file(directory / name)
        actual_hashes[name] = digest
        if name != "expanded_sequence_provenance.json" and generated.get(name) != digest:
            raise ExpandedSequenceContractError(f"v0.13.1 provenance mismatch: {name}")
    if manifest.get("archive_sha256") != actual_hashes["expanded_profile_dataset.npz"]:
        raise ExpandedSequenceContractError("v0.13.1 archive hash does not reconcile")
    return contract, manifest, actual_hashes


def _padded_from_archive(
    archive: Path,
    *,
    expected_profile_count: int,
    expected_sequence_count: int,
) -> tuple[PaddedSequenceDataset, NDArray[np.str_], NDArray[np.str_]]:
    try:
        with np.load(archive, allow_pickle=False) as payload:
            if set(payload.files) != REQUIRED_ARCHIVE_FIELDS:
                raise ExpandedSequenceContractError("v0.13.1 archive fields differ")
            count = len(payload["drive_ids"])
            if count != expected_profile_count or count < 2:
                raise ExpandedSequenceContractError("expanded profile count differs")
            conditions = np.asarray(payload["conditions"], dtype=np.float64)
            residuals = np.asarray(payload["residuals_m"], dtype=np.float64)
            sequence_ids = np.asarray(payload["sequence_ids"], dtype=np.str_)
            drive_ids = np.asarray(payload["drive_ids"], dtype=np.str_)
            recording_ids = np.asarray(payload["recording_ids"], dtype=np.str_)
            basenames = np.asarray(payload["mcap_basenames_private"], dtype=np.str_)
            pair_indices = np.asarray(payload["pair_indices"], dtype=np.int64)
            message_indices = np.asarray(
                payload["estimate_message_indices"], dtype=np.int64
            )
            timestamps = np.asarray(payload["timestamps_ns_private"], dtype=np.int64)
            eligibility = np.asarray(payload["eligibility"], dtype=np.bool_)
            exclusions = np.asarray(payload["exclusion_reasons"], dtype=np.str_)
            stations = np.asarray(payload["stations_m"], dtype=np.float64)
    except (OSError, ValueError) as error:
        if isinstance(error, ExpandedSequenceContractError):
            raise
        raise ExpandedSequenceContractError(f"invalid v0.13.1 archive: {error}") from error

    if conditions.shape != (count, len(BMW_CONDITION_FEATURE_NAMES)):
        raise ExpandedSequenceContractError("expanded conditions must be [N,6]")
    if residuals.shape != (count, len(CANONICAL_MODEL_STATIONS_M)):
        raise ExpandedSequenceContractError("expanded residuals must be [N,21]")
    if not np.array_equal(stations, CANONICAL_MODEL_STATIONS_M):
        raise ExpandedSequenceContractError("expanded station grid differs from H100")
    vectors = (
        sequence_ids,
        drive_ids,
        recording_ids,
        basenames,
        pair_indices,
        message_indices,
        timestamps,
        eligibility,
        exclusions,
    )
    if any(values.shape != (count,) for values in vectors):
        raise ExpandedSequenceContractError("expanded frame vectors must be [N]")
    if (
        not np.all(np.isfinite(conditions))
        or not np.all(np.isfinite(residuals))
        or not np.all(eligibility)
        or np.any(exclusions != "")
        or np.any(sequence_ids == "")
        or np.any(drive_ids == "")
        or np.any(recording_ids == "")
        or np.any(basenames == "")
    ):
        raise ExpandedSequenceContractError("expanded retained frames are incomplete")

    ordered_ids: list[str] = []
    slices: list[slice] = []
    start = 0
    closed: set[str] = set()
    while start < count:
        sequence_id = str(sequence_ids[start])
        if sequence_id in closed:
            raise ExpandedSequenceContractError("sequence rows are not one canonical block")
        stop = start + 1
        while stop < count and sequence_ids[stop] == sequence_id:
            stop += 1
        ordered_ids.append(sequence_id)
        slices.append(slice(start, stop))
        closed.add(sequence_id)
        start = stop
    if len(ordered_ids) != expected_sequence_count:
        raise ExpandedSequenceContractError("expanded sequence count differs")

    lengths = np.asarray([item.stop - item.start for item in slices], dtype=np.int64)
    maximum_length = int(np.max(lengths))
    sequence_count = len(slices)
    padded_conditions = np.zeros((sequence_count, maximum_length, 6), dtype=np.float64)
    padded_residuals = np.zeros((sequence_count, maximum_length, 21), dtype=np.float64)
    valid_mask = np.zeros((sequence_count, maximum_length, 21), dtype=np.bool_)
    padded_pairs = np.full((sequence_count, maximum_length), -1, dtype=np.int64)
    padded_messages = np.full_like(padded_pairs, -1)
    padded_times = np.full_like(padded_pairs, -1)
    padded_recordings = np.full((sequence_count, maximum_length), "", dtype=recording_ids.dtype)
    padded_basenames = np.full((sequence_count, maximum_length), "", dtype=basenames.dtype)
    sequence_drives: list[str] = []
    sequence_recording_labels: list[str] = []
    for sequence_index, item in enumerate(slices):
        length = int(lengths[sequence_index])
        unique_drives = set(drive_ids[item].tolist())
        if len(unique_drives) != 1:
            raise ExpandedSequenceContractError("one sequence crosses physical drives")
        if np.any(np.diff(timestamps[item]) <= 0):
            raise ExpandedSequenceContractError("sequence timestamps do not increase")
        padded_conditions[sequence_index, :length] = conditions[item]
        padded_residuals[sequence_index, :length] = residuals[item]
        valid_mask[sequence_index, :length] = True
        padded_pairs[sequence_index, :length] = pair_indices[item]
        padded_messages[sequence_index, :length] = message_indices[item]
        padded_times[sequence_index, :length] = timestamps[item]
        padded_recordings[sequence_index, :length] = recording_ids[item]
        padded_basenames[sequence_index, :length] = basenames[item]
        sequence_drives.append(next(iter(unique_drives)))
        recording_order = tuple(dict.fromkeys(recording_ids[item].tolist()))
        sequence_recording_labels.append(";".join(recording_order))

    dataset = PaddedSequenceDataset(
        sequence_ids=ordered_ids,
        recording_ids=sequence_recording_labels,
        drive_ids=sequence_drives,
        conditions=padded_conditions,
        residuals_m=padded_residuals,
        valid_mask=valid_mask,
        lengths=lengths,
        pair_indices=padded_pairs,
        estimate_message_indices=padded_messages,
        estimate_source_times_ns_private=padded_times,
        feature_names=BMW_CONDITION_FEATURE_NAMES,
        stations_m=CANONICAL_MODEL_STATIONS_M,
        standardized=False,
    )
    return dataset, padded_recordings, padded_basenames


def load_expanded_modeling_dataset(directory: str | Path) -> ExpandedModelingDataset:
    """Load v0.13.1 and expose the fixed clean-primary/mixed-secondary cohorts."""

    source = Path(directory)
    contract, manifest, hashes = _validate_source_directory(source)
    profile_count = contract.get("profile_count")
    sequence_count = contract.get("sequence_count")
    if (
        isinstance(profile_count, bool)
        or not isinstance(profile_count, int)
        or isinstance(sequence_count, bool)
        or not isinstance(sequence_count, int)
    ):
        raise ExpandedSequenceContractError("expanded contract counts are invalid")
    if (
        manifest.get("profile_count") != profile_count
        or manifest.get("sequence_count") != sequence_count
    ):
        raise ExpandedSequenceContractError("expanded manifest counts do not reconcile")
    sequences, recordings, basenames = _padded_from_archive(
        source / "expanded_profile_dataset.npz",
        expected_profile_count=profile_count,
        expected_sequence_count=sequence_count,
    )
    sequence_classes, drive_classes = _read_sequence_classes(
        source / "sequence_manifest.csv"
    )
    if set(sequence_classes) != set(sequences.sequence_ids.tolist()):
        raise ExpandedSequenceContractError("sequence manifest/archive IDs differ")
    for sequence_id, drive_id in zip(sequences.sequence_ids, sequences.drive_ids):
        if drive_classes.get(str(drive_id)) != sequence_classes[str(sequence_id)]:
            raise ExpandedSequenceContractError("sequence/archive cohort roles differ")
    clean = tuple(sorted(str(value) for value in contract.get("clean_drive_ids", ())))
    mixed = tuple(
        sorted(str(value) for value in contract.get("mixed_source_drive_ids", ()))
    )
    if clean != tuple(sorted(key for key, value in drive_classes.items() if value == CLEAN_DRIVE_CLASS)):
        raise ExpandedSequenceContractError("clean drive IDs differ from the manifest")
    if mixed != tuple(sorted(key for key, value in drive_classes.items() if value == MIXED_DRIVE_CLASS)):
        raise ExpandedSequenceContractError("mixed drive IDs differ from the manifest")
    if sequences.frame_count != profile_count or sequences.sequence_count != sequence_count:
        raise ExpandedSequenceContractError("expanded padded counts do not reconcile")
    return ExpandedModelingDataset(
        sequences=sequences,
        recording_ids_by_frame=recordings,
        mcap_basenames_by_frame_private=basenames,
        clean_drive_ids=clean,
        mixed_drive_ids=mixed,
        drive_class_by_id=dict(sorted(drive_classes.items())),
        source_files_sha256=dict(sorted(hashes.items())),
        source_contract=contract,
    )


__all__ = [
    "CLEAN_DRIVE_CLASS",
    "ExpandedModelingDataset",
    "MIXED_DRIVE_CLASS",
    "PURPOSE",
    "REQUIRED_ARCHIVE_FIELDS",
    "REQUIRED_SOURCE_FILES",
    "VERSION",
    "load_expanded_modeling_dataset",
]
