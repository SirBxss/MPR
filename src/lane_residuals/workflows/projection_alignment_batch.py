"""Corpus-independent exact-manifest native projection alignment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.batch_pairing import HORIZON_100_M
from ..domain.corpus_inventory import exact_drive_map_coverage
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.projection_alignment import plot_alignment_comparison
from .projection_alignment import PAIR_FIELDS, STATION_FIELDS, run_alignment_audit
from .batch_pairing import _resolve_mcaps
from .corpus_inventory import load_drive_map_pairs

LOGGER = logging.getLogger(__name__)
VERSION = "0.5.2"
PURPOSE = "exact_manifest_projection_based_reference_alignment_validation"
ALIGNMENT_SEMANTICS = "v0.5.0_native_spatial_projection"
CORPUS_PROVENANCE_FILES = (
    "corpus_inventory_summary.json",
    "recording_continuity.csv",
    "proposed_session_groups.json",
)
BATCH_OUTPUT_FILES = (
    "recording_alignment_summary.csv",
    "alignment_pair_audit.csv",
    "alignment_station_comparison.csv",
    "alignment_batch_comparison.png",
    "alignment_batch_summary.json",
    "batch_manifest.json",
)


@dataclass(frozen=True)
class RecordingAlignmentData:
    """One recording's alignment outputs and exact manifest assignment."""

    recording_id: str
    drive_id: str
    mcap_filename: str
    status: str
    output_directory: str
    summary: Mapping[str, Any] = field(default_factory=dict, repr=False)
    pair_rows: tuple[Mapping[str, Any], ...] = field(default_factory=tuple, repr=False)
    station_rows: tuple[Mapping[str, Any], ...] = field(
        default_factory=tuple,
        repr=False,
    )
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


def _read_csv(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(
            f"output directory is not empty: {path}; use a new batch directory"
        )
    path.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=reject_constant)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _exact_drive_assignments(
    drive_map_path: Path,
    files: Sequence[Path],
) -> tuple[dict[Path, str], dict[Path, str]]:
    pairs = load_drive_map_pairs(drive_map_path)
    assignments, issues = exact_drive_map_coverage(
        [path.name for path in files], pairs
    )
    if any(issues.values()):
        raise ValueError(
            "drive map must cover every resolved basename exactly once; "
            + ", ".join(
                f"{name}={list(values)}" for name, values in issues.items() if values
            )
        )
    labels = sorted(set(assignments.values()))
    opaque = {label: f"drive_{index:03d}" for index, label in enumerate(labels, 1)}
    ordered = sorted(files, key=lambda path: (path.name, str(path)))
    recording_ids = {
        path: f"recording_{index:03d}" for index, path in enumerate(ordered, 1)
    }
    drive_ids = {path: opaque[assignments[path.name]] for path in files}
    return recording_ids, drive_ids


def _validate_corpus_inventory(
    directory: Path,
    files: Sequence[Path],
) -> dict[str, str]:
    for filename in CORPUS_PROVENANCE_FILES:
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"required corpus inventory output not found: {path}")
    summary = _read_json(directory / "corpus_inventory_summary.json")
    if summary.get("status") != "complete":
        raise ValueError("corpus inventory status must be complete")
    if summary.get("exact_drive_map_coverage") is not True:
        raise ValueError("corpus inventory must prove exact drive-map coverage")
    if summary.get("mcap_file_count") != len(files):
        raise ValueError("corpus inventory file count does not match resolved MCAPs")
    if summary.get("unusable_file_count") != 0:
        raise ValueError("corpus inventory must contain zero unusable files")
    if summary.get("rejected_boundary_count") != 0:
        raise ValueError("corpus inventory must contain zero rejected boundaries")
    groups_payload = _read_json(directory / "proposed_session_groups.json")
    if groups_payload.get("cross_mcap_sequence_stitching_performed") is not False:
        raise ValueError("corpus inventory must not have stitched sequences")
    raw_groups = groups_payload.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("proposed session groups must be a nonempty list")
    grouped_basenames: list[str] = []
    for raw_group in raw_groups:
        if not isinstance(raw_group, Mapping):
            raise ValueError("each proposed session group must be an object")
        basenames = raw_group.get("mcap_basenames_private")
        if not isinstance(basenames, list) or not basenames:
            raise ValueError("each proposed session group must list MCAP basenames")
        grouped_basenames.extend(str(value) for value in basenames)
    expected_basenames = sorted(path.name for path in files)
    if sorted(grouped_basenames) != expected_basenames or len(
        set(grouped_basenames)
    ) != len(grouped_basenames):
        raise ValueError("proposed session groups do not exactly cover resolved MCAPs")
    with (directory / "recording_continuity.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        edges = list(csv.DictReader(handle))
    expected_edge_count = len(files) - len(raw_groups)
    if len(edges) != expected_edge_count:
        raise ValueError("continuity edge count does not reconcile with session groups")
    if any(
        str(row.get("stitchable", "")).lower() != "true"
        or bool(row.get("rejection_codes"))
        for row in edges
    ):
        raise ValueError("every within-session corpus boundary must be stitchable")
    return {
        filename: _sha256(directory / filename)
        for filename in CORPUS_PROVENANCE_FILES
    }


def _validate_arguments(arguments: argparse.Namespace) -> None:
    if arguments.expected_file_count < 1:
        raise ValueError("expected-file-count must be positive")
    if arguments.max_step_m <= 0.0 or not math.isfinite(arguments.max_step_m):
        raise ValueError("max-step-m must be finite and positive")
    if arguments.map_max_segments < 1:
        raise ValueError("map-max-segments must be positive")
    if (
        arguments.map_max_junction_gap_m < 0.0
        or not math.isfinite(arguments.map_max_junction_gap_m)
    ):
        raise ValueError("map-max-junction-gap-m must be finite and nonnegative")
    if (
        arguments.map_max_junction_heading_deg < 0.0
        or arguments.map_max_junction_heading_deg > 180.0
        or not math.isfinite(arguments.map_max_junction_heading_deg)
    ):
        raise ValueError(
            "map-max-junction-heading-deg must be finite and within [0, 180]"
        )
    if arguments.maximum_pair_delta_ms is not None and (
        arguments.maximum_pair_delta_ms < 0.0
        or not math.isfinite(arguments.maximum_pair_delta_ms)
    ):
        raise ValueError("maximum-pair-delta-ms must be finite and nonnegative")


def _run_one_recording(
    *,
    mcap: Path,
    recording_id: str,
    drive_id: str,
    output_directory: Path,
    arguments: argparse.Namespace,
) -> RecordingAlignmentData:
    single_arguments = SimpleNamespace(
        mcap=mcap,
        output_directory=output_directory,
        maximum_pair_delta_ms=arguments.maximum_pair_delta_ms,
        max_step_m=arguments.max_step_m,
        map_max_segments=arguments.map_max_segments,
        map_max_junction_gap_m=arguments.map_max_junction_gap_m,
        map_max_junction_heading_deg=arguments.map_max_junction_heading_deg,
        estimate_topic=arguments.estimate_topic,
        map_topic=arguments.map_topic,
    )
    try:
        summary = run_alignment_audit(single_arguments)
        return RecordingAlignmentData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=mcap.name,
            status="succeeded",
            output_directory=str(output_directory),
            summary=summary,
            pair_rows=_read_csv(output_directory / "alignment_pair_audit.csv"),
            station_rows=_read_csv(
                output_directory / "alignment_station_comparison.csv"
            ),
        )
    except Exception as error:  # one failed recording must remain visible
        LOGGER.error("%s failed: %s", recording_id, error)
        return RecordingAlignmentData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=mcap.name,
            status="failed",
            output_directory=str(output_directory),
            error_code=type(error).__name__,
            error_message=str(error),
        )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("alignment batch rows must not contain NaN or infinity")
    return result


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1"}


def _median_from_rows(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [
        number
        for row in rows
        if (number := _optional_float(row.get(key))) is not None
    ]
    return None if not values else float(np.median(np.asarray(values)))


def _recording_summary_rows(
    recordings: Sequence[RecordingAlignmentData],
) -> list[dict[str, Any]]:
    fields = (
        "complete_stream_mutual_nearest_pair_count",
        "h60_aligned_complete_pair_count",
        "h100_aligned_complete_pair_count",
        "median_absolute_source_delta_ms",
        "median_reference_anchor_station_m",
        "median_anchor_distance_m",
        "median_aligned_minus_native_h60_pair_lateral_rms_m",
        "median_aligned_minus_native_h100_pair_lateral_rms_m",
    )
    rows: list[dict[str, Any]] = []
    for recording in recordings:
        row = {
            "recording_id": recording.recording_id,
            "drive_id": recording.drive_id,
            "mcap_filename_private": recording.mcap_filename,
            "status": recording.status,
            "error_code": recording.error_code,
            "error_message": recording.error_message,
        }
        row.update(
            {
                name: recording.summary.get(name) if recording.succeeded else None
                for name in fields
            }
        )
        rows.append(row)
    return rows


RECORDING_FIELDS = (
    "recording_id",
    "drive_id",
    "mcap_filename_private",
    "status",
    "error_code",
    "error_message",
    "complete_stream_mutual_nearest_pair_count",
    "h60_aligned_complete_pair_count",
    "h100_aligned_complete_pair_count",
    "median_absolute_source_delta_ms",
    "median_reference_anchor_station_m",
    "median_anchor_distance_m",
    "median_aligned_minus_native_h60_pair_lateral_rms_m",
    "median_aligned_minus_native_h100_pair_lateral_rms_m",
)


def _h100_vectors_are_complete(
    pair_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
) -> bool:
    expected_stations = tuple(float(value) for value in HORIZON_100_M)
    eligible = {
        (str(row["recording_id"]), str(row["pair_index"]))
        for row in pair_rows
        if _as_bool(row.get("h100_aligned_eligible"))
    }
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in station_rows:
        if not _as_bool(row.get("h100_aligned_eligible")):
            continue
        key = (str(row["recording_id"]), str(row["pair_index"]))
        grouped.setdefault(key, []).append(row)
    if set(grouped) != eligible:
        return False
    for rows in grouped.values():
        try:
            stations = tuple(float(row["station_m"]) for row in rows)
            residuals = tuple(float(row["aligned_lateral_m"]) for row in rows)
        except (KeyError, TypeError, ValueError):
            return False
        if stations != expected_stations or not all(math.isfinite(value) for value in residuals):
            return False
    return True


def run_alignment_batch(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Run native projection alignment for an arbitrary exact manifest."""

    _validate_arguments(arguments)
    files = _resolve_mcaps(arguments.inputs)
    recording_ids, drive_ids = _exact_drive_assignments(arguments.drive_map, files)
    corpus_hashes = _validate_corpus_inventory(
        arguments.corpus_inventory_directory,
        files,
    )
    source_hashes = {
        "drive_map_private_json": _sha256(arguments.drive_map),
        **corpus_hashes,
    }
    _ensure_empty_output(arguments.output_directory)

    initial_manifest = {
        "version": VERSION,
        "purpose": PURPOSE,
        "alignment_semantics": ALIGNMENT_SEMANTICS,
        "spatial_reference_alignment_applied": True,
        "explicit_ego_pose_motion_compensation_applied": False,
        "source_delta_used_numerically_for_alignment": False,
        "accepted_for_modeling": True,
        "status": "running",
        "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files),
        "file_count_matches": len(files) == arguments.expected_file_count,
        "drive_grouping_source": "exact_private_basename_map",
        "corpus_continuity_source": "accepted_complete_expanded_corpus_inventory",
        "source_files_sha256": source_hashes,
        "canonical_horizons_m": [60, 100],
        "canonical_station_grid_m": list(HORIZON_100_M),
        "recordings": [
            {
                "recording_id": recording_ids[path],
                "drive_id": drive_ids[path],
                "mcap_filename_private": path.name,
                "status": "pending",
            }
            for path in files
        ],
    }
    write_strict_json(
        arguments.output_directory / "batch_manifest.json",
        initial_manifest,
    )

    recordings: list[RecordingAlignmentData] = []
    for path in files:
        recording_id = recording_ids[path]
        LOGGER.info("validating alignment for %s (%s)", recording_id, path.name)
        recordings.append(
            _run_one_recording(
                mcap=path,
                recording_id=recording_id,
                drive_id=drive_ids[path],
                output_directory=(
                    arguments.output_directory / "recordings" / recording_id
                ),
                arguments=arguments,
            )
        )

    pair_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    for recording in recordings:
        if not recording.succeeded:
            continue
        pair_rows.extend(
            {
                "recording_id": recording.recording_id,
                "drive_id": recording.drive_id,
                **row,
            }
            for row in recording.pair_rows
        )
        station_rows.extend(
            {
                "recording_id": recording.recording_id,
                "drive_id": recording.drive_id,
                **row,
            }
            for row in recording.station_rows
        )

    recording_rows = _recording_summary_rows(recordings)
    write_csv_rows(
        arguments.output_directory / "recording_alignment_summary.csv",
        RECORDING_FIELDS,
        recording_rows,
    )
    write_csv_rows(
        arguments.output_directory / "alignment_pair_audit.csv",
        ("recording_id", "drive_id", *PAIR_FIELDS),
        pair_rows,
    )
    write_csv_rows(
        arguments.output_directory / "alignment_station_comparison.csv",
        ("recording_id", "drive_id", *STATION_FIELDS),
        station_rows,
    )
    plot_alignment_comparison(
        arguments.output_directory / "alignment_batch_comparison.png",
        pair_rows=pair_rows,
        station_rows=station_rows,
    )

    failed = [recording for recording in recordings if not recording.succeeded]
    h60_rows = [row for row in pair_rows if _as_bool(row.get("h60_aligned_eligible"))]
    h100_rows = [
        row for row in pair_rows if _as_bool(row.get("h100_aligned_eligible"))
    ]
    blockers: list[str] = []
    if len(files) != arguments.expected_file_count:
        blockers.append("resolved_file_count_mismatch")
    if failed:
        blockers.append("one_or_more_alignment_recordings_failed")
    if not h60_rows:
        blockers.append("no_complete_aligned_h60_pairs")
    if not h100_rows:
        blockers.append("no_complete_aligned_h100_pairs")
    if any(
        _as_bool(row.get("h100_aligned_eligible"))
        and not _as_bool(row.get("h60_aligned_eligible"))
        for row in pair_rows
    ):
        blockers.append("h100_not_subset_of_h60")
    if not _h100_vectors_are_complete(pair_rows, station_rows):
        blockers.append("h100_vectors_not_complete_21_station_rows")

    summary = {
        "version": VERSION,
        "purpose": PURPOSE,
        "alignment_semantics": ALIGNMENT_SEMANTICS,
        "accepted_for_modeling": True,
        "status": "complete" if not blockers else "incomplete",
        "blockers": blockers,
        "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files),
        "successful_recording_count": sum(item.succeeded for item in recordings),
        "failed_recording_count": len(failed),
        "drive_count": len({item.drive_id for item in recordings}),
        "mutual_nearest_pair_count": len(pair_rows),
        "h60_aligned_complete_pair_count": len(h60_rows),
        "h100_aligned_complete_pair_count": len(h100_rows),
        "h100_is_subset_of_h60": "h100_not_subset_of_h60" not in blockers,
        "canonical_horizons_m": [60, 100],
        "canonical_station_grid_m": list(HORIZON_100_M),
        "median_absolute_source_delta_ms": _median_from_rows(
            pair_rows,
            "absolute_source_delta_ms",
        ),
        "median_reference_anchor_station_m": _median_from_rows(
            pair_rows,
            "reference_anchor_station_m",
        ),
        "median_anchor_distance_m": _median_from_rows(
            pair_rows,
            "anchor_distance_m",
        ),
        "median_aligned_minus_native_h60_pair_lateral_rms_m": _median_from_rows(
            pair_rows,
            "aligned_minus_native_h60_lateral_rms_m",
        ),
        "median_aligned_minus_native_h100_pair_lateral_rms_m": _median_from_rows(
            pair_rows,
            "aligned_minus_native_h100_lateral_rms_m",
        ),
        "scope_metrics_recomputed_from_pair_rows": True,
        "timestamp_pairing_crosses_recording_boundaries": False,
        "drive_grouping_source": "exact_private_basename_map",
        "corpus_continuity_source": "accepted_complete_expanded_corpus_inventory",
        "source_files_sha256": source_hashes,
        "pair_count_is_independent_sample_size": False,
        "source_delta_used_numerically_for_alignment": False,
        "spatial_reference_alignment_applied": True,
        "explicit_ego_pose_motion_compensation_applied": False,
        "model_eligible_vectors_require_complete_21_stations": True,
        "available_case_rows_accepted_for_modeling": False,
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "generated_final_residual_dataset": False,
        "trained_statistical_model": False,
        "next_decision": (
            "Review per-recording and per-drive anchor shifts, projection "
            "distances, aligned coverage, and native-versus-aligned changes; "
            "then freeze eligibility before exporting H100 model vectors."
        ),
        "confidentiality": (
            "Outputs contain BMW-derived timestamps and measurements and must remain private."
        ),
    }
    write_strict_json(
        arguments.output_directory / "alignment_batch_summary.json",
        summary,
    )
    final_manifest = {
        **initial_manifest,
        "status": summary["status"],
        "successful_recording_count": summary["successful_recording_count"],
        "failed_recording_count": summary["failed_recording_count"],
        "blockers": blockers,
        "recordings": [
            {
                "recording_id": item.recording_id,
                "drive_id": item.drive_id,
                "mcap_filename_private": item.mcap_filename,
                "status": item.status,
                "output_directory": item.output_directory,
                "error_code": item.error_code,
                "error_message": item.error_message,
            }
            for item in recordings
        ],
    }
    write_strict_json(
        arguments.output_directory / "batch_manifest.json",
        final_manifest,
    )
    provenance = {
        "version": VERSION,
        "purpose": PURPOSE,
        "alignment_semantics": ALIGNMENT_SEMANTICS,
        "explicit_ego_pose_motion_compensation_applied": False,
        "source_delta_used_numerically_for_alignment": False,
        "accepted_for_modeling": True,
        "source_files_sha256": source_hashes,
        "generated_batch_outputs_sha256": {
            filename: _sha256(arguments.output_directory / filename)
            for filename in BATCH_OUTPUT_FILES
        },
    }
    write_strict_json(
        arguments.output_directory / "batch_output_provenance.json",
        provenance,
    )
    return summary, 0 if not blockers else 3


__all__ = [
    "RECORDING_FIELDS",
    "RecordingAlignmentData",
    "run_alignment_batch",
]
