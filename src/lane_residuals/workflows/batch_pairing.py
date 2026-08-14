"""Ten-recording batch diagnostic for EDP--RLMB pseudo-residuals."""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.batch_pairing import (
    CANONICAL_STATIONS_M,
    BatchAggregationError,
    RecordingAuditData,
    aggregate_fixed_cohorts,
    aggregate_rlmb_chains,
    detect_drive_overlaps,
    load_recording_audit,
    recording_summary_rows,
    source_time_envelope,
    temporal_diagnostic_rows,
    write_csv_rows,
    write_strict_json,
)
from ..domain.geometry_validation import GeometryValidationError
from ..io.mcap import McapDependencyError, RoadMessageError
from .pairing import (
    DEFAULT_MAP_TOPIC,
    run_pairing_audit,
)
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..visualization.batch_pairing import (
    plot_fixed_cohorts as _plot_fixed_cohorts,
    plot_recording_summary as _plot_recording_summary,
    plot_temporal as _plot_temporal,
)


LOGGER = logging.getLogger(__name__)


def _validate_arguments(arguments: argparse.Namespace) -> None:
    if arguments.expected_file_count < 1:
        raise ValueError("expected-file-count must be positive")
    if arguments.max_pairs_per_recording < 1:
        raise ValueError("max-pairs-per-recording must be positive")
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
        arguments.recording_tail_window_s < 0.0
        or not math.isfinite(arguments.recording_tail_window_s)
    ):
        raise ValueError("recording-tail-window-s must be finite and nonnegative")
    for name in ("primary_tail_threshold_m", "full_tail_threshold_m"):
        value = getattr(arguments, name)
        if value is not None and (value <= 0.0 or not math.isfinite(value)):
            raise ValueError(name.replace("_", "-") + " must be finite and positive")


def _resolve_mcaps(inputs: Sequence[Path]) -> tuple[Path, ...]:
    files: list[Path] = []
    for raw in inputs:
        path = raw.expanduser()
        if path.is_file():
            if path.suffix.lower() != ".mcap":
                raise ValueError(f"input file is not an MCAP: {path}")
            files.append(path.resolve())
        elif path.is_dir():
            files.extend(item.resolve() for item in path.rglob("*.mcap") if item.is_file())
        else:
            raise FileNotFoundError(f"input path not found: {path}")
    unique = sorted(set(files), key=lambda path: (path.name, str(path)))
    if not unique:
        raise ValueError("no MCAP files were resolved")
    basenames = [path.name for path in unique]
    if len(set(basenames)) != len(basenames):
        raise ValueError("duplicate MCAP basenames make the drive map ambiguous")
    return tuple(unique)


def _load_drive_assignments(
    drive_map_path: Path,
    files: Sequence[Path],
) -> tuple[dict[Path, str], dict[Path, str]]:
    if not drive_map_path.is_file():
        raise FileNotFoundError(f"drive map not found: {drive_map_path}")
    with drive_map_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and key and value.strip()
        for key, value in payload.items()
    ):
        raise ValueError("drive map must be a JSON object of basename: nonempty label")
    basenames = {path.name for path in files}
    if set(payload) != basenames:
        missing = sorted(basenames - set(payload))
        extra = sorted(set(payload) - basenames)
        raise ValueError(
            "drive map must match resolved basenames exactly; "
            f"missing={missing}, extra={extra}"
        )
    labels = sorted({payload[path.name].strip() for path in files})
    opaque_drives = {label: f"drive_{index:03d}" for index, label in enumerate(labels, 1)}
    ordered_files = sorted(files, key=lambda path: path.name)
    recording_ids = {
        path: f"recording_{index:03d}" for index, path in enumerate(ordered_files, 1)
    }
    drive_ids = {
        path: opaque_drives[payload[path.name].strip()] for path in files
    }
    return recording_ids, drive_ids


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(
            f"output directory is not empty: {path}; use a new directory for each batch"
        )
    path.mkdir(parents=True, exist_ok=True)


def _validate_recording_counts(recording: RecordingAuditData) -> None:
    if not recording.succeeded:
        return
    summary = recording.summary
    estimate_messages = int(summary["estimate_messages"])
    map_messages = int(summary["map_messages"])
    accepted = int(summary["complete_stream_mutual_nearest_pair_count"])
    unmatched_estimate = int(summary["unmatched_estimate_message_count"])
    unmatched_map = int(summary["unmatched_map_message_count"])
    if accepted + unmatched_estimate != estimate_messages:
        raise BatchAggregationError(
            f"estimate temporal counts do not reconcile in {recording.recording_id}"
        )
    if accepted + unmatched_map != map_messages:
        raise BatchAggregationError(
            f"map temporal counts do not reconcile in {recording.recording_id}"
        )
    if len(recording.pair_rows) != accepted:
        raise BatchAggregationError(
            f"pair rows do not reconcile in {recording.recording_id}"
        )
    if len(recording.chain_rows) != map_messages:
        raise BatchAggregationError(
            f"RLMB chain rows do not reconcile in {recording.recording_id}"
        )


def _run_one_recording(
    *,
    mcap: Path,
    recording_id: str,
    drive_id: str,
    output_directory: Path,
    arguments: argparse.Namespace,
) -> RecordingAuditData:
    single_arguments = SimpleNamespace(
        mcap=mcap,
        estimate_topic=arguments.estimate_topic,
        map_topic=arguments.map_topic,
        max_step_m=arguments.max_step_m,
        max_pairs=arguments.max_pairs_per_recording,
        maximum_pair_delta_ms=arguments.maximum_pair_delta_ms,
        output_directory=output_directory,
        map_max_segments=arguments.map_max_segments,
        map_max_junction_gap_m=arguments.map_max_junction_gap_m,
        map_max_junction_heading_deg=arguments.map_max_junction_heading_deg,
    )
    try:
        run_pairing_audit(single_arguments, stations_m=CANONICAL_STATIONS_M)
        recording = load_recording_audit(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=mcap.name,
            output_directory=output_directory,
        )
        _validate_recording_counts(recording)
        return recording
    except Exception as error:  # one bad recording must not abort the corpus
        LOGGER.error("%s failed: %s", recording_id, error)
        return RecordingAuditData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=mcap.name,
            status="failed",
            output_directory=str(output_directory),
            error_code=type(error).__name__,
            error_message=str(error),
        )


def _manifest_entries(recordings: Sequence[RecordingAuditData]) -> list[dict[str, Any]]:
    return [
        {
            "recording_id": recording.recording_id,
            "drive_id": recording.drive_id,
            "mcap_filename_private": recording.mcap_filename,
            "status": recording.status,
            "output_directory": recording.output_directory,
            "error_code": recording.error_code,
            "error_message": recording.error_message,
        }
        for recording in recordings
    ]


def run_batch(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Run all recordings independently, aggregate evidence, and return exit status."""

    _validate_arguments(arguments)
    files = _resolve_mcaps(arguments.inputs)
    recording_ids, drive_ids = _load_drive_assignments(arguments.drive_map, files)
    _ensure_empty_output(arguments.output_directory)

    initial_manifest = {
        "version": "0.4.5",
        "purpose": "ten_mcap_edp_rlmb_batch_diagnostic",
        "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files),
        "file_count_matches": len(files) == arguments.expected_file_count,
        "canonical_horizons_m": [60, 100],
        "canonical_station_grid_m": list(CANONICAL_STATIONS_M),
        "drive_grouping_source": "exact_private_basename_map",
        "status": "running",
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
    write_strict_json(arguments.output_directory / "batch_manifest.json", initial_manifest)

    recordings: list[RecordingAuditData] = []
    for path in files:
        recording_id = recording_ids[path]
        LOGGER.info("auditing %s (%s)", recording_id, path.name)
        recordings.append(
            _run_one_recording(
                mcap=path,
                recording_id=recording_id,
                drive_id=drive_ids[path],
                output_directory=arguments.output_directory / "recordings" / recording_id,
                arguments=arguments,
            )
        )

    station_rows, horizon_rows, _ = aggregate_fixed_cohorts(recordings)
    chain_summary = aggregate_rlmb_chains(recordings)
    temporal_rows = temporal_diagnostic_rows(
        recordings,
        recording_tail_window_s=arguments.recording_tail_window_s,
        primary_tail_threshold_m=arguments.primary_tail_threshold_m,
        full_tail_threshold_m=arguments.full_tail_threshold_m,
    )
    per_recording_rows = recording_summary_rows(recordings, horizon_rows, temporal_rows)
    overlaps = detect_drive_overlaps(recordings)

    write_csv_rows(
        arguments.output_directory / "recording_summary.csv",
        tuple(per_recording_rows[0].keys()) if per_recording_rows else (
            "recording_id", "drive_id", "mcap_filename_private", "status"
        ),
        per_recording_rows,
    )
    write_csv_rows(
        arguments.output_directory / "scope_horizon_metrics.csv",
        tuple(horizon_rows[0].keys()),
        horizon_rows,
    )
    write_csv_rows(
        arguments.output_directory / "scope_station_metrics.csv",
        tuple(station_rows[0].keys()),
        station_rows,
    )
    temporal_fields = tuple(temporal_rows[0].keys()) if temporal_rows else (
        "recording_id", "drive_id", "pair_index"
    )
    write_csv_rows(
        arguments.output_directory / "temporal_tail_events.csv",
        temporal_fields,
        temporal_rows,
    )
    write_strict_json(arguments.output_directory / "rlmb_chain_summary.json", chain_summary)
    _plot_fixed_cohorts(arguments.output_directory / "fixed_cohort_station_profiles.png", station_rows)
    _plot_recording_summary(arguments.output_directory / "recording_horizon_summary.png", per_recording_rows)
    _plot_temporal(arguments.output_directory / "temporal_diagnostic_events.png", temporal_rows)

    failed = [recording for recording in recordings if not recording.succeeded]
    missing_envelopes = [
        recording.recording_id
        for recording in recordings
        if recording.succeeded and source_time_envelope(recording) is None
    ]
    overall_horizons = {
        str(row["horizon_m"]): dict(row)
        for row in horizon_rows
        if row["scope_type"] == "overall"
    }
    blockers: list[str] = []
    if len(files) != arguments.expected_file_count:
        blockers.append("resolved_file_count_mismatch")
    if failed:
        blockers.append("one_or_more_recording_audits_failed")
    if overlaps:
        blockers.append("same_drive_source_time_ranges_overlap_or_share_a_boundary")
    if missing_envelopes:
        blockers.append("complete_estimate_source_time_envelope_unavailable")
    if int(overall_horizons.get("60", {}).get("cohort_pair_count", 0)) == 0:
        blockers.append("no_complete_h60_pairs")
    if int(overall_horizons.get("100", {}).get("cohort_pair_count", 0)) == 0:
        blockers.append("no_complete_h100_pairs")

    batch_summary = {
        "version": "0.4.5",
        "purpose": "ten_mcap_edp_rlmb_batch_diagnostic",
        "status": "complete" if not blockers else "incomplete",
        "blockers": blockers,
        "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files),
        "successful_recording_count": sum(recording.succeeded for recording in recordings),
        "failed_recording_count": len(failed),
        "drive_count": len({recording.drive_id for recording in recordings}),
        "canonical_horizons_m": [60, 100],
        "canonical_station_grid_m": list(CANONICAL_STATIONS_M),
        "overall_fixed_cohort_metrics": overall_horizons,
        "same_drive_source_time_overlaps": overlaps,
        "recordings_without_complete_estimate_time_envelope": missing_envelopes,
        "timestamp_pairing_crosses_recording_boundaries": False,
        "scope_metrics_are_recomputed_from_underlying_pair_station_rows": True,
        "pair_count_is_independent_sample_size": False,
        "drive_and_recording_grouping_required_for_later_splits": True,
        "outcome_tail_thresholds": {
            "h60_pair_rms_m": arguments.primary_tail_threshold_m,
            "h100_pair_rms_m": arguments.full_tail_threshold_m,
            "predeclared": (
                arguments.primary_tail_threshold_m is not None
                or arguments.full_tail_threshold_m is not None
            ),
            "when_absent_flags_are_null": True,
        },
        "recording_tail_window_s": arguments.recording_tail_window_s,
        "coordinate_frame_equivalence_confirmed": False,
        "timestamp_motion_compensation_applied": False,
        "map_signal_role": "pseudo_reference_candidate",
        "diagnostic_disagreement_is_lane_estimation_error": False,
        "generated_final_residual_dataset": False,
        "trained_statistical_model": False,
        "confidentiality": "Outputs contain BMW-derived measurements and must remain private.",
        "next_decision": (
            "Review fixed-cohort coverage, per-drive disagreement, temporal tails, "
            "and source-time overlap evidence before defining a provisional modelling dataset."
        ),
    }
    write_strict_json(arguments.output_directory / "batch_summary.json", batch_summary)
    final_manifest = {
        **initial_manifest,
        "status": batch_summary["status"],
        "successful_recording_count": batch_summary["successful_recording_count"],
        "failed_recording_count": batch_summary["failed_recording_count"],
        "recordings": _manifest_entries(recordings),
        "blockers": blockers,
    }
    write_strict_json(arguments.output_directory / "batch_manifest.json", final_manifest)
    return batch_summary, 0 if not blockers else 3
