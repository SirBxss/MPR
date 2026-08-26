"""Build immutable v0.16 reference-planner scenario archives."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.expanded_sequence_dataset_v0131 import validate_v0131_profile_archive
from ..io.reports import write_strict_json
from .sequence_contract import ensure_empty_output_directory, sha256_file

VERSION = "0.16.0"
SCENARIO_FILENAME = "reference_planner_scenarios.npz"
CONDITION_FILENAME = "planner_condition_sequences.npz"
SUMMARY_FILENAME = "reference_planner_scenario_summary.json"
PRIMARY_CLEAN_DRIVES = frozenset({"drive_001", "drive_002", "drive_003", "drive_004"})
V0131_OUTPUT_NAMES = frozenset(
    {
        "expanded_profile_dataset.npz", "profile_eligibility_audit.csv",
        "sequence_manifest.csv", "sequence_summary_by_drive.csv",
        "cross_mcap_stitching_audit.csv", "boundary_odometry_context_audit.csv",
        "exclusion_reason_summary.csv", "v0130_parity_audit.json",
        "expanded_sequence_contract.json", "train_only_standardization_metadata.json",
        "expanded_sequence_diagnostics.png",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON dependency {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON dependency must be an object: {path}")
    return payload


def _validate_dataset_lineage(directory: Path) -> Path:
    manifest = _read_json(directory / "expanded_sequence_manifest.json")
    contract = _read_json(directory / "expanded_sequence_contract.json")
    provenance = _read_json(directory / "expanded_sequence_provenance.json")
    expected = {
        "version": "0.13.1",
        "purpose": "quality_gated_expanded_sensor_topology_sequential_dataset_with_boundary_odometry_context",
    }
    for label, payload in (("manifest", manifest), ("contract", contract)):
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ValueError(f"v0.13.1 {label} identity differs")
        if payload.get("status") != "complete":
            raise ValueError(f"v0.13.1 {label} is incomplete")
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError("v0.13.1 provenance identity differs")
    output_names = manifest.get("output_files")
    generated = provenance.get("generated_outputs_sha256")
    if not isinstance(output_names, list) or set(output_names) != V0131_OUTPUT_NAMES:
        raise ValueError("v0.13.1 manifest output list differs")
    if not isinstance(generated, dict) or set(generated) != set(
        [*output_names, "expanded_sequence_manifest.json"]
    ):
        raise ValueError("v0.13.1 generated-output hash set differs")
    for name, digest in generated.items():
        path = directory / str(name)
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"v0.13.1 generated output drifted: {name}")
    profile_path = directory / "expanded_profile_dataset.npz"
    if manifest.get("archive_sha256") != sha256_file(profile_path):
        raise ValueError("v0.13.1 archive hash differs from manifest")
    return profile_path


def _validate_alignment_lineage(directory: Path) -> Path:
    station_path = directory / "alignment_station_comparison.csv"
    summary = _read_json(directory / "alignment_batch_summary.json")
    if summary.get("version") != "0.5.2" or summary.get("status") != "complete":
        raise ValueError("alignment batch is not a complete v0.5.2 result")
    provenance = _read_json(directory / "batch_output_provenance.json")
    generated = provenance.get("generated_batch_outputs_sha256")
    if not isinstance(generated, dict) or generated.get(station_path.name) != sha256_file(station_path):
        raise ValueError("alignment station CSV differs from v0.5.2 provenance")
    return station_path


def _read_station_paths(path: Path) -> dict[tuple[str, int], np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    grouped: dict[tuple[str, int], dict[float, tuple[float, float]]] = {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "recording_id", "pair_index", "station_m",
            "aligned_reference_x_m", "aligned_reference_y_m",
            "h100_aligned_eligible",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("alignment station CSV lacks required v0.5.2 fields")
        for row in reader:
            if row["h100_aligned_eligible"] != "True":
                continue
            try:
                key = (row["recording_id"], int(row["pair_index"]))
                station = float(row["station_m"])
                point = (float(row["aligned_reference_x_m"]), float(row["aligned_reference_y_m"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("invalid alignment station row") from error
            if station in grouped.setdefault(key, {}):
                raise ValueError(f"duplicate alignment station row for {key}")
            grouped[key][station] = point
    expected = tuple(float(value) for value in CANONICAL_MODEL_STATIONS_M)
    return {
        key: np.asarray([values[station] for station in expected], dtype=np.float64)
        for key, values in grouped.items()
        if tuple(sorted(values)) == expected
    }


def run_reference_planner_scenario_build(
    *, expanded_dataset_directory: Path, alignment_directory: Path,
    output_directory: Path,
) -> tuple[dict[str, Any], int]:
    """Join the primary clean v0.13.1 sequences to aligned RLMB H100 paths."""

    profile_path = _validate_dataset_lineage(expanded_dataset_directory)
    station_path = _validate_alignment_lineage(alignment_directory)
    validate_v0131_profile_archive(profile_path)
    paths_by_key = _read_station_paths(station_path)
    with np.load(profile_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    selected = [
        index for index, drive in enumerate(arrays["drive_ids"])
        if str(drive) in PRIMARY_CLEAN_DRIVES
    ]
    if not selected:
        raise ValueError("v0.13.1 archive contains no primary clean-drive frames")
    sequence_order: list[str] = []
    frames_by_sequence: dict[str, list[int]] = {}
    for index in selected:
        sequence_id = str(arrays["sequence_ids"][index])
        if sequence_id not in frames_by_sequence:
            sequence_order.append(sequence_id)
            frames_by_sequence[sequence_id] = []
        frames_by_sequence[sequence_id].append(index)
    lengths = np.asarray([len(frames_by_sequence[item]) for item in sequence_order], dtype=np.int64)
    if np.any(lengths < 2):
        raise ValueError("planner scenario contains a singleton sequence")
    maximum_time, batch = int(np.max(lengths)), len(sequence_order)
    conditions = np.zeros((batch, maximum_time, 6), dtype=np.float64)
    timestamps = np.zeros((batch, maximum_time), dtype=np.int64)
    paths = np.zeros((batch, maximum_time, 21, 2), dtype=np.float64)
    for sequence_index, sequence_id in enumerate(sequence_order):
        previous_timestamp = -1
        for time_index, frame_index in enumerate(frames_by_sequence[sequence_id]):
            key = (str(arrays["recording_ids"][frame_index]), int(arrays["pair_indices"][frame_index]))
            if key not in paths_by_key:
                raise ValueError(f"eligible v0.13.1 frame lacks complete H100 path: {key}")
            timestamp = int(arrays["timestamps_ns_private"][frame_index])
            if timestamp <= previous_timestamp:
                raise ValueError(f"sequence timestamps are not strictly increasing: {sequence_id}")
            previous_timestamp = timestamp
            conditions[sequence_index, time_index] = arrays["conditions"][frame_index]
            timestamps[sequence_index, time_index] = timestamp
            paths[sequence_index, time_index] = paths_by_key[key]
    sequence_ids = np.asarray(sequence_order, dtype=np.str_)
    feature_names = np.asarray(BMW_CONDITION_FEATURE_NAMES, dtype=np.str_)
    stations = np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64)
    ensure_empty_output_directory(output_directory)
    scenario_path = output_directory / SCENARIO_FILENAME
    np.savez_compressed(
        scenario_path, conditions=conditions, feature_names=feature_names,
        lengths=lengths, nominal_paths_xy_m=paths, sequence_ids=sequence_ids,
        stations_m=stations, timestamps_ns=timestamps,
    )
    condition_path = output_directory / CONDITION_FILENAME
    np.savez_compressed(
        condition_path, conditions=conditions, lengths=lengths,
        sequence_ids=sequence_ids, feature_names=feature_names,
    )
    summary: dict[str, Any] = {
        "version": VERSION, "status": "complete",
        "purpose": "primary_clean_reference_planner_scenario_build",
        "included_drive_ids": sorted(PRIMARY_CLEAN_DRIVES),
        "sequence_count": batch, "active_frame_count": int(np.sum(lengths)),
        "maximum_sequence_length": maximum_time,
        "stations_m": [float(value) for value in stations],
        "feature_names_in_required_order": list(BMW_CONDITION_FEATURE_NAMES),
        "expanded_profile_dataset_sha256": sha256_file(profile_path),
        "alignment_station_comparison_sha256": sha256_file(station_path),
        "scenario_file": SCENARIO_FILENAME,
        "scenario_file_sha256": sha256_file(scenario_path),
        "condition_file": CONDITION_FILENAME,
        "condition_file_sha256": sha256_file(condition_path),
        "ego_relative_paths_are_not_stitched_globally": True,
        "planner_benefit_claimed": False,
    }
    write_strict_json(output_directory / SUMMARY_FILENAME, summary)
    return summary, 0


__all__ = ["CONDITION_FILENAME", "PRIMARY_CLEAN_DRIVES", "SCENARIO_FILENAME", "SUMMARY_FILENAME", "V0131_OUTPUT_NAMES", "VERSION", "run_reference_planner_scenario_build"]
