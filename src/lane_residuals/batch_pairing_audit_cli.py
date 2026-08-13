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

from .batch_pairing_audit import (
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
from .geometry_validation import GeometryValidationError
from .mcap_io import McapDependencyError, RoadMessageError
from .pairing_audit_cli import (
    DEFAULT_MAP_TOPIC,
    run_pairing_audit,
)
from .path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the diagnostic EDP--RLMB pairing audit independently for a "
            "predeclared corpus, then aggregate fixed 0--60 m and 0--100 m cohorts."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="MCAP files and/or directories scanned recursively for *.mcap",
    )
    parser.add_argument(
        "--drive-map",
        type=Path,
        required=True,
        help=(
            "private JSON object mapping every resolved MCAP basename to an exact "
            "drive/session label; output labels are replaced with opaque IDs"
        ),
    )
    parser.add_argument("--expected-file-count", type=int, default=10)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/pairing_batch_v045"),
    )
    parser.add_argument(
        "--max-pairs-per-recording",
        type=int,
        default=6,
        help="maximum overlay panels per recording; it never truncates CSV rows",
    )
    parser.add_argument(
        "--maximum-pair-delta-ms",
        type=float,
        default=None,
        help="optional predeclared source-timestamp gate; omitted by default",
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--map-max-segments", type=int, default=16)
    parser.add_argument("--map-max-junction-gap-m", type=float, default=1.0)
    parser.add_argument(
        "--map-max-junction-heading-deg",
        type=float,
        default=30.0,
    )
    parser.add_argument(
        "--recording-tail-window-s",
        type=float,
        default=5.0,
        help=(
            "predeclared final time window marked from the complete estimate-stream "
            "source-time envelope; independent of geometry and disagreement values"
        ),
    )
    parser.add_argument(
        "--primary-tail-threshold-m",
        type=float,
        default=None,
        help=(
            "optional predeclared 0--60 m per-pair RMS threshold; when omitted, "
            "outcome-tail flags remain empty"
        ),
    )
    parser.add_argument(
        "--full-tail-threshold-m",
        type=float,
        default=None,
        help=(
            "optional predeclared 0--100 m per-pair RMS threshold; when omitted, "
            "outcome-tail flags remain empty"
        ),
    )
    parser.add_argument(
        "--estimate-topic",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    )
    parser.add_argument("--map-topic", default=DEFAULT_MAP_TOPIC)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


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


def _plot_fixed_cohorts(path: Path, station_rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    overall = [row for row in station_rows if row["scope_type"] == "overall"]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), squeeze=False)
    for row_index, horizon in enumerate((60, 100)):
        rows = sorted(
            (row for row in overall if int(row["horizon_m"]) == horizon),
            key=lambda row: float(row["station_m"]),
        )
        stations = np.asarray([row["station_m"] for row in rows], dtype=np.float64)
        counts = [int(row["cohort_pair_count"]) for row in rows]
        if rows and counts and counts[0] > 0:
            median = np.asarray([row["lateral_median_m"] for row in rows], dtype=np.float64)
            p05 = np.asarray([row["lateral_p05_m"] for row in rows], dtype=np.float64)
            p95 = np.asarray([row["lateral_p95_m"] for row in rows], dtype=np.float64)
            rms = np.asarray([row["lateral_rms_m"] for row in rows], dtype=np.float64)
            axes[row_index, 0].plot(stations, median, color="tab:blue", label="median")
            axes[row_index, 0].fill_between(stations, p05, p95, color="tab:blue", alpha=0.2, label="5--95%")
            axes[row_index, 1].plot(stations, rms, color="tab:orange", marker="o", markersize=3)
            axes[row_index, 0].legend(loc="best")
        else:
            for axis in axes[row_index]:
                axis.text(0.5, 0.5, "No complete cohort", ha="center", va="center", transform=axis.transAxes)
        axes[row_index, 0].set_title(f"Fixed H{horizon} cohort: signed distribution")
        axes[row_index, 1].set_title(f"Fixed H{horizon} cohort: RMS")
        for axis in axes[row_index]:
            axis.set_xlabel("ego-relative station [m]")
            axis.set_ylabel("diagnostic lateral disagreement [m]")
            axis.grid(True, alpha=0.25)
            if counts:
                axis.text(0.02, 0.96, f"n={counts[0]} pairs at every station", transform=axis.transAxes, va="top")
    figure.suptitle("CONFIDENTIAL — fixed-cohort EDP–RLMB pseudo-residual diagnostics")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    figure.savefig(path, dpi=170)
    plt.close(figure)


def _plot_recording_summary(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    successful = [row for row in rows if row["status"] == "succeeded"]
    figure, axis = plt.subplots(figsize=(max(9.0, 0.8 * len(successful) + 3.0), 5.5))
    if successful:
        x = np.arange(len(successful), dtype=np.float64)
        h60 = [row["h60_median_pair_lateral_rms_m"] for row in successful]
        h100 = [row["h100_median_pair_lateral_rms_m"] for row in successful]
        axis.bar(x - 0.2, [0.0 if value is None else value for value in h60], width=0.4, label="H60")
        axis.bar(x + 0.2, [0.0 if value is None else value for value in h100], width=0.4, label="H100")
        axis.set_xticks(x, [row["recording_id"] for row in successful], rotation=45, ha="right")
        axis.legend()
    else:
        axis.text(0.5, 0.5, "No successful recordings", ha="center", va="center", transform=axis.transAxes)
    axis.set_ylabel("median per-pair lateral RMS [m]")
    axis.set_title("Recording-level fixed-cohort diagnostic summary")
    axis.grid(True, axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)


def _plot_temporal(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    drive_ids = sorted({str(row["drive_id"]) for row in rows})
    figure, axes = plt.subplots(max(1, len(drive_ids)), 1, figsize=(12, max(4.0, 3.4 * len(drive_ids))), squeeze=False)
    if not drive_ids:
        axes[0, 0].text(0.5, 0.5, "No temporal pairs", ha="center", va="center", transform=axes[0, 0].transAxes)
    for index, drive_id in enumerate(drive_ids):
        axis = axes[index, 0]
        drive_rows = [row for row in rows if row["drive_id"] == drive_id and row["drive_relative_source_time_s"] is not None]
        for key, label, color in (
            ("h60_pair_lateral_rms_m", "H60", "tab:blue"),
            ("h100_pair_lateral_rms_m", "H100", "tab:orange"),
        ):
            selected = [row for row in drive_rows if row[key] is not None]
            axis.plot(
                [row["drive_relative_source_time_s"] for row in selected],
                [row[key] for row in selected],
                marker=".",
                linewidth=0.8,
                markersize=3,
                color=color,
                label=label,
            )
        primary_threshold = next((row["h60_tail_threshold_m"] for row in drive_rows if row["h60_tail_threshold_m"] is not None), None)
        full_threshold = next((row["h100_tail_threshold_m"] for row in drive_rows if row["h100_tail_threshold_m"] is not None), None)
        if primary_threshold is not None:
            axis.axhline(primary_threshold, color="tab:blue", linestyle="--", alpha=0.6)
        if full_threshold is not None:
            axis.axhline(full_threshold, color="tab:orange", linestyle="--", alpha=0.6)
        axis.set_title(drive_id)
        axis.set_xlabel("drive-relative source time [s]")
        axis.set_ylabel("per-pair lateral RMS [m]")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best")
    figure.suptitle("CONFIDENTIAL — temporal pseudo-residual diagnostics")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    figure.savefig(path, dpi=170)
    plt.close(figure)


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        summary, status = run_batch(arguments)
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        BatchAggregationError,
        GeometryValidationError,
        McapDependencyError,
        RoadMessageError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "batch %s: %d/%d recordings succeeded",
        summary["status"],
        summary["successful_recording_count"],
        summary["resolved_file_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
