"""Exact-manifest batch validation for odometry-compensated alignment."""

from __future__ import annotations

import argparse
import csv
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.batch_pairing import HORIZON_100_M
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.alignment import plot_alignment_comparison
from .alignment import PAIR_FIELDS, STATION_FIELDS, run_alignment_audit
from .batch_pairing import _load_drive_assignments, _resolve_mcaps

LOGGER = logging.getLogger(__name__)


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
    if (
        arguments.maximum_odometry_log_lag_ms < 0.0
        or not math.isfinite(arguments.maximum_odometry_log_lag_ms)
    ):
        raise ValueError(
            "maximum-odometry-log-lag-ms must be finite and nonnegative"
        )
    if (
        arguments.maximum_odometry_interpolation_gap_ms < 0.0
        or not math.isfinite(arguments.maximum_odometry_interpolation_gap_ms)
    ):
        raise ValueError(
            "maximum-odometry-interpolation-gap-ms must be finite and nonnegative"
        )


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
        odometry_topic=arguments.odometry_topic,
        maximum_odometry_log_lag_ms=arguments.maximum_odometry_log_lag_ms,
        maximum_odometry_interpolation_gap_ms=(
            arguments.maximum_odometry_interpolation_gap_ms
        ),
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


def _median_absolute_from_rows(
    rows: Sequence[Mapping[str, Any]],
    key: str,
) -> float | None:
    values = [
        abs(number)
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
        "median_absolute_geometry_epoch_delta_ms",
        "median_edp_geometry_proxy_log_lag_ms",
        "median_ego_motion_source_to_target_travel_m",
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
    "median_absolute_geometry_epoch_delta_ms",
    "median_edp_geometry_proxy_log_lag_ms",
    "median_ego_motion_source_to_target_travel_m",
    "median_reference_anchor_station_m",
    "median_anchor_distance_m",
    "median_aligned_minus_native_h60_pair_lateral_rms_m",
    "median_aligned_minus_native_h100_pair_lateral_rms_m",
)


def run_alignment_batch(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Run alignment validation for the exact recording manifest and aggregate."""

    _validate_arguments(arguments)
    files = _resolve_mcaps(arguments.inputs)
    recording_ids, drive_ids = _load_drive_assignments(arguments.drive_map, files)
    _ensure_empty_output(arguments.output_directory)

    initial_manifest = {
        "version": "0.5.1",
        "purpose": "ten_mcap_odometry_motion_compensated_alignment_validation",
        "status": "running",
        "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files),
        "file_count_matches": len(files) == arguments.expected_file_count,
        "drive_grouping_source": "exact_private_basename_map",
        "odometry_topic": arguments.odometry_topic,
        "edp_geometry_time_proxy_basis": (
            "last_odometry_log_at_or_before_estimate_log"
        ),
        "maximum_odometry_log_lag_ms": arguments.maximum_odometry_log_lag_ms,
        "maximum_odometry_interpolation_gap_ms": (
            arguments.maximum_odometry_interpolation_gap_ms
        ),
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

    summary = {
        "version": "0.5.1",
        "purpose": "ten_mcap_odometry_motion_compensated_alignment_validation",
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
        "median_absolute_geometry_epoch_delta_ms": _median_absolute_from_rows(
            pair_rows,
            "geometry_epoch_delta_ms",
        ),
        "median_edp_geometry_proxy_log_lag_ms": _median_from_rows(
            pair_rows,
            "edp_geometry_proxy_log_lag_ms",
        ),
        "median_ego_motion_source_to_target_travel_m": _median_from_rows(
            pair_rows,
            "ego_motion_source_to_target_travel_m",
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
        "pair_count_is_independent_sample_size": False,
        "source_delta_used_numerically_for_alignment": False,
        "edp_geometry_time_proxy_basis": (
            "last_odometry_log_at_or_before_estimate_log"
        ),
        "edp_geometry_epoch_exactly_published": False,
        "spatial_reference_alignment_applied": True,
        "explicit_ego_pose_motion_compensation_applied": True,
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "generated_final_residual_dataset": False,
        "trained_statistical_model": False,
        "next_decision": (
            "Review odometry proxy lag, geometry-epoch motion, anchor shifts, "
            "coverage, and native-versus-compensated residual changes; then "
            "freeze eligibility before exporting H100 model vectors."
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
    return summary, 0 if not blockers else 3


__all__ = [
    "RECORDING_FIELDS",
    "RecordingAlignmentData",
    "run_alignment_batch",
]
