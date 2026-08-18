"""Exact-manifest v0.7.1 audit of prediction-time conditional features."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..domain.conditional_features import (
    CANONICAL_CONDITION_STATIONS_M,
    CONFIDENCE_BUCKET_SIZE_M,
    ConditionalFeatureError,
    ODOMETRY_SPEED_INTERVAL_MS,
    derive_unsigned_odometry_speed,
    interpolate_longitudinal_speed,
    selected_keep_lane_confidences,
    summarize_estimate_conditions,
)
from ..domain.geometry_validation import (
    GeometryValidationError,
    estimated_frame_from_message,
    generate_spline_curve,
)
from ..domain.pairing import ego_relative_path_from_spline
from ..domain.residual_dataset import ResidualDatasetContractError, ResidualObservation
from ..io.mcap import iter_decoded_mcap_messages
from ..io.odometry import DEFAULT_ODOMETRY_TOPIC, decode_odometry_samples
from ..io.reports import write_csv_rows, write_strict_json
from ..io.vehicle import (
    DEFAULT_LONGITUDINAL_SPEED_TOPIC,
    decode_longitudinal_speed_samples,
)
from ..visualization.conditional_features import plot_conditional_feature_audit
from .gaussian_diagnostics import load_gaussian_baseline_artifacts

VERSION = "0.7.1"
ACCEPTED_ALIGNMENT_VERSION = "0.5.0"
ACCEPTED_ALIGNMENT_PURPOSE = (
    "ten_mcap_projection_based_reference_alignment_validation"
)
DEFAULT_ESTIMATE_TOPIC = "/adp/estimated_drive_paths"
DEFAULT_ESTIMATE_SCHEMA = "Adp.Perception.EstimatedDrivePaths"
DEFAULT_MAXIMUM_SPEED_INTERPOLATION_GAP_MS = 20.0
DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS = 20.0
DIRECT_SPEED_SOURCE = "direct_longitudinal_signal"
ODOMETRY_SPEED_SOURCE = "odometry_50ms_displacement"
SPEED_SOURCE_CHOICES = (DIRECT_SPEED_SOURCE, ODOMETRY_SPEED_SOURCE)


FEATURE_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "estimate_message_index",
    "estimate_source_time_ns_private",
    "feature_state",
    "failure_codes",
    "speed_source",
    "speed_is_signed",
    "speed_mps",
    "speed_evaluation_method",
    "speed_displacement_m",
    "speed_displacement_interval_ms",
    "speed_previous_target_timestamp_ns_private",
    "speed_current_target_timestamp_ns_private",
    "speed_previous_lower_timestamp_ns_private",
    "speed_previous_upper_timestamp_ns_private",
    "speed_current_lower_timestamp_ns_private",
    "speed_current_upper_timestamp_ns_private",
    "speed_previous_interpolation_span_ms",
    "speed_current_interpolation_span_ms",
    "estimated_mean_abs_curvature_per_m",
    "estimated_curvature_delta_per_m",
    "confidence_near_mean",
    "confidence_middle_mean",
    "confidence_far_mean",
    "confidence_minimum",
    "confidence_floor_fraction",
    "confidence_lateral_jump_detected",
    "confidence_bucket_count",
    "confidence_native_start_station_m",
    "confidence_native_end_station_m",
)

RECORDING_SUMMARY_FIELDS = (
    "recording_id",
    "drive_id",
    "mcap_filename_private",
    "status",
    "residual_vector_count",
    "feature_ready_count",
    "feature_ready_fraction",
    "estimate_message_count",
    "speed_source",
    "speed_is_signed",
    "speed_message_count",
    "valid_speed_sample_count",
    "median_speed_previous_interpolation_span_ms",
    "median_speed_current_interpolation_span_ms",
    "maximum_speed_previous_interpolation_span_ms",
    "maximum_speed_current_interpolation_span_ms",
    "failure_counts",
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
        raise ValueError(
            f"output directory is not empty: {path}; use a new audit directory"
        )
    path.mkdir(parents=True, exist_ok=True)


def _resolve_mcap_files(inputs: Sequence[Path]) -> dict[str, Path]:
    files: list[Path] = []
    for item in inputs:
        candidate = item.resolve()
        if candidate.is_file():
            if candidate.suffix.lower() != ".mcap":
                raise ValueError(f"input file is not an MCAP: {item}")
            files.append(candidate)
        elif candidate.is_dir():
            files.extend(
                path.resolve()
                for path in candidate.rglob("*.mcap")
                if path.is_file()
            )
        else:
            raise FileNotFoundError(f"MCAP input not found: {item}")
    unique_paths = sorted(set(files), key=lambda path: str(path))
    if not unique_paths:
        raise FileNotFoundError("no MCAP files were resolved")
    by_basename: dict[str, Path] = {}
    for path in unique_paths:
        if path.name in by_basename:
            raise ValueError(f"duplicate MCAP basename resolved: {path.name}")
        by_basename[path.name] = path
    return by_basename


@dataclass(frozen=True)
class ManifestRecording:
    recording_id: str
    drive_id: str
    basename: str
    path: Path = field(repr=False)


def _validated_manifest_recordings(
    *,
    alignment_batch_directory: Path,
    baseline_dataset_summary: Mapping[str, Any],
    mcap_inputs: Sequence[Path],
) -> tuple[Mapping[str, Any], tuple[ManifestRecording, ...]]:
    manifest_path = alignment_batch_directory / "batch_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"accepted batch manifest not found: {manifest_path}")
    source_hashes = baseline_dataset_summary.get("source_files_sha256")
    if not isinstance(source_hashes, Mapping):
        raise ResidualDatasetContractError(
            "baseline dataset summary lacks source file hashes"
        )
    expected_hash = source_hashes.get("batch_manifest.json")
    if not isinstance(expected_hash, str) or _sha256(manifest_path) != expected_hash:
        raise ResidualDatasetContractError(
            "alignment batch manifest does not match the v0.6.0 residual source"
        )
    manifest = _read_strict_json(manifest_path)
    if not isinstance(manifest, Mapping):
        raise ResidualDatasetContractError("batch manifest must be a JSON object")
    if manifest.get("version") != ACCEPTED_ALIGNMENT_VERSION:
        raise ResidualDatasetContractError("alignment manifest version must be 0.5.0")
    if manifest.get("purpose") != ACCEPTED_ALIGNMENT_PURPOSE:
        raise ResidualDatasetContractError("alignment manifest purpose is not accepted")
    if manifest.get("status") != "complete" or manifest.get("blockers") != []:
        raise ResidualDatasetContractError("alignment manifest must be complete")
    if manifest.get("drive_grouping_source") != "exact_private_basename_map":
        raise ResidualDatasetContractError("manifest grouping must be exact")
    if manifest.get("canonical_station_grid_m") != list(
        CANONICAL_CONDITION_STATIONS_M
    ):
        raise ResidualDatasetContractError("manifest station grid is not canonical H100")

    raw_recordings = manifest.get("recordings")
    if not isinstance(raw_recordings, list) or not raw_recordings:
        raise ResidualDatasetContractError("manifest recordings must be nonempty")
    resolved = _resolve_mcap_files(mcap_inputs)
    manifest_basenames: set[str] = set()
    recording_ids: set[str] = set()
    recordings: list[ManifestRecording] = []
    for raw in raw_recordings:
        if not isinstance(raw, Mapping):
            raise ResidualDatasetContractError("manifest recording must be an object")
        recording_id = str(raw.get("recording_id", "")).strip()
        drive_id = str(raw.get("drive_id", "")).strip()
        basename = str(raw.get("mcap_filename_private", "")).strip()
        if not recording_id or not drive_id or not basename:
            raise ResidualDatasetContractError(
                "manifest recording identifiers must be nonempty"
            )
        if raw.get("status") != "succeeded":
            raise ResidualDatasetContractError(
                f"manifest recording did not succeed: {recording_id}"
            )
        if recording_id in recording_ids or basename in manifest_basenames:
            raise ResidualDatasetContractError(
                "manifest recording IDs and basenames must be unique"
            )
        path = resolved.get(basename)
        if path is None:
            raise FileNotFoundError(f"manifest MCAP not resolved: {basename}")
        recording_ids.add(recording_id)
        manifest_basenames.add(basename)
        recordings.append(
            ManifestRecording(
                recording_id=recording_id,
                drive_id=drive_id,
                basename=basename,
                path=path,
            )
        )
    if set(resolved) != manifest_basenames:
        unexpected = sorted(set(resolved) - manifest_basenames)
        raise ResidualDatasetContractError(
            f"resolved MCAP set differs from exact manifest; unexpected={unexpected}"
        )
    return manifest, tuple(recordings)


def _base_row(observation: ResidualObservation) -> dict[str, Any]:
    return {
        "recording_id": observation.recording_id,
        "drive_id": observation.drive_id,
        "pair_index": observation.pair_index,
        "estimate_message_index": observation.estimate_message_index,
        "estimate_source_time_ns_private": (
            observation.estimate_source_time_ns_private
        ),
    }


@dataclass(frozen=True)
class RecordingFeatureResult:
    rows: tuple[dict[str, Any], ...] = field(repr=False)
    summary_row: dict[str, Any] = field(repr=False)
    failure_counts: Mapping[str, int] = field(repr=False)


def _extract_recording_features(
    recording: ManifestRecording,
    observations: Sequence[ResidualObservation],
    *,
    estimate_topic: str,
    speed_source: str,
    speed_topic: str,
    odometry_topic: str,
    maximum_speed_interpolation_gap_ns: int,
    maximum_odometry_interpolation_gap_ns: int,
    max_step_m: float,
) -> RecordingFeatureResult:
    target_by_index: dict[int, ResidualObservation] = {}
    for observation in observations:
        index = observation.estimate_message_index
        if index in target_by_index:
            raise ResidualDatasetContractError(
                f"duplicate estimate message index in {recording.recording_id}: {index}"
            )
        target_by_index[index] = observation

    if speed_source == DIRECT_SPEED_SOURCE:
        speed_samples, source_failures, speed_message_count = (
            decode_longitudinal_speed_samples(recording.path, topic=speed_topic)
        )
        speed_is_signed = True
    elif speed_source == ODOMETRY_SPEED_SOURCE:
        speed_samples, raw_failures, speed_message_count = decode_odometry_samples(
            recording.path,
            topic=odometry_topic,
        )
        speed_samples.sort(key=lambda sample: sample.timestamp_ns)
        source_failures = Counter(
            {f"speed_source__{code}": count for code, count in raw_failures.items()}
        )
        speed_is_signed = False
    else:
        raise ValueError(f"unsupported speed source: {speed_source}")
    condition_by_index: dict[int, dict[str, Any]] = {}
    condition_failure_by_index: dict[int, str] = {}
    estimate_message_count = 0
    for schema, channel, message, decoded in iter_decoded_mcap_messages(
        recording.path,
        topics=(estimate_topic,),
        include_ros1=False,
    ):
        message_index = estimate_message_count
        estimate_message_count += 1
        observation = target_by_index.get(message_index)
        if observation is None:
            continue
        schema_name = str(getattr(schema, "name", ""))
        encoding = str(getattr(channel, "message_encoding", "")).lower()
        if schema_name != DEFAULT_ESTIMATE_SCHEMA or encoding != "protobuf":
            condition_failure_by_index[message_index] = (
                "estimate__schema_or_encoding_mismatch"
            )
            continue
        try:
            frame = estimated_frame_from_message(
                decoded,
                message_index=message_index,
                log_time_ns=int(getattr(message, "log_time", 0)),
                publish_time_ns=int(getattr(message, "publish_time", 0)),
            )
            if frame.source_time_ns != observation.estimate_source_time_ns_private:
                raise ResidualDatasetContractError(
                    "raw EDP source timestamp does not reconcile with residual provenance "
                    f"for {recording.recording_id}/{observation.pair_index}"
                )
            if not frame.candidate_ready or frame.candidate is None:
                raise ConditionalFeatureError(
                    f"estimate_{frame.conversion_state}",
                    "accepted residual EDP geometry is no longer feature-ready",
                )
            curve = generate_spline_curve(
                frame.candidate,
                meaning="curvature_rate",
                anchor_policy="anchor_zero",
                max_step_m=max_step_m,
            )
            path = ego_relative_path_from_spline(curve)
            confidences = selected_keep_lane_confidences(decoded)
            condition_by_index[message_index] = asdict(
                summarize_estimate_conditions(curve, path, confidences)
            )
        except ResidualDatasetContractError:
            raise
        except (ConditionalFeatureError, GeometryValidationError, ValueError) as error:
            condition_failure_by_index[message_index] = (
                f"estimate__{getattr(error, 'code', type(error).__name__)}"
            )

    rows: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter(source_failures)
    previous_interpolation_spans: list[float] = []
    current_interpolation_spans: list[float] = []
    for observation in observations:
        row = _base_row(observation)
        row.update(
            {
                "speed_source": speed_source,
                "speed_is_signed": speed_is_signed,
            }
        )
        failures: list[str] = []
        condition = condition_by_index.get(observation.estimate_message_index)
        if condition is None:
            code = condition_failure_by_index.get(
                observation.estimate_message_index,
                "estimate__message_index_not_found",
            )
            failures.append(code)
            failure_counts[code] += 1
        else:
            row.update(condition)
        try:
            if speed_source == DIRECT_SPEED_SOURCE:
                speed = interpolate_longitudinal_speed(
                    speed_samples,
                    observation.estimate_source_time_ns_private,
                    maximum_bracket_gap_ns=maximum_speed_interpolation_gap_ns,
                )
                row.update(
                    {
                        "speed_mps": speed.value_mps,
                        "speed_evaluation_method": f"direct_{speed.method}",
                        "speed_displacement_interval_ms": 0.0,
                        "speed_previous_target_timestamp_ns_private": (
                            observation.estimate_source_time_ns_private
                        ),
                        "speed_current_target_timestamp_ns_private": (
                            observation.estimate_source_time_ns_private
                        ),
                        "speed_current_lower_timestamp_ns_private": (
                            speed.lower_timestamp_ns
                        ),
                        "speed_current_upper_timestamp_ns_private": (
                            speed.upper_timestamp_ns
                        ),
                        "speed_current_interpolation_span_ms": (
                            speed.bracket_span_ms
                        ),
                    }
                )
                current_interpolation_spans.append(speed.bracket_span_ms)
            else:
                speed = derive_unsigned_odometry_speed(
                    speed_samples,
                    observation.estimate_source_time_ns_private,
                    maximum_bracket_gap_ns=(
                        maximum_odometry_interpolation_gap_ns
                    ),
                )
                row.update(
                    {
                        "speed_mps": speed.value_mps,
                        "speed_evaluation_method": ODOMETRY_SPEED_SOURCE,
                        "speed_displacement_m": speed.displacement_m,
                        "speed_displacement_interval_ms": speed.interval_ms,
                        "speed_previous_target_timestamp_ns_private": (
                            speed.previous_pose.timestamp_ns
                        ),
                        "speed_current_target_timestamp_ns_private": (
                            speed.current_pose.timestamp_ns
                        ),
                        "speed_previous_lower_timestamp_ns_private": (
                            speed.previous_pose.lower_timestamp_ns
                        ),
                        "speed_previous_upper_timestamp_ns_private": (
                            speed.previous_pose.upper_timestamp_ns
                        ),
                        "speed_current_lower_timestamp_ns_private": (
                            speed.current_pose.lower_timestamp_ns
                        ),
                        "speed_current_upper_timestamp_ns_private": (
                            speed.current_pose.upper_timestamp_ns
                        ),
                        "speed_previous_interpolation_span_ms": (
                            speed.previous_pose.bracket_span_ms
                        ),
                        "speed_current_interpolation_span_ms": (
                            speed.current_pose.bracket_span_ms
                        ),
                    }
                )
                previous_interpolation_spans.append(
                    speed.previous_pose.bracket_span_ms
                )
                current_interpolation_spans.append(
                    speed.current_pose.bracket_span_ms
                )
        except (ConditionalFeatureError, GeometryValidationError) as error:
            code = f"speed__{error.code}"
            failures.append(code)
            failure_counts[code] += 1
        row["feature_state"] = "ready" if not failures else "not_ready"
        row["failure_codes"] = ";".join(sorted(failures))
        rows.append(row)

    ready_count = sum(row["feature_state"] == "ready" for row in rows)
    summary_row = {
        "recording_id": recording.recording_id,
        "drive_id": recording.drive_id,
        "mcap_filename_private": recording.basename,
        "status": "complete" if ready_count == len(rows) else "incomplete",
        "residual_vector_count": len(rows),
        "feature_ready_count": ready_count,
        "feature_ready_fraction": ready_count / len(rows),
        "estimate_message_count": estimate_message_count,
        "speed_source": speed_source,
        "speed_is_signed": speed_is_signed,
        "speed_message_count": speed_message_count,
        "valid_speed_sample_count": len(speed_samples),
        "median_speed_previous_interpolation_span_ms": (
            None
            if not previous_interpolation_spans
            else float(np.median(previous_interpolation_spans))
        ),
        "median_speed_current_interpolation_span_ms": (
            None
            if not current_interpolation_spans
            else float(np.median(current_interpolation_spans))
        ),
        "maximum_speed_previous_interpolation_span_ms": (
            None
            if not previous_interpolation_spans
            else float(np.max(previous_interpolation_spans))
        ),
        "maximum_speed_current_interpolation_span_ms": (
            None
            if not current_interpolation_spans
            else float(np.max(current_interpolation_spans))
        ),
        "failure_counts": json.dumps(dict(sorted(failure_counts.items()))),
    }
    return RecordingFeatureResult(
        rows=tuple(rows),
        summary_row=summary_row,
        failure_counts=dict(failure_counts),
    )


def _validate_arguments(arguments: argparse.Namespace) -> tuple[int, int]:
    if arguments.speed_source not in SPEED_SOURCE_CHOICES:
        raise ValueError(f"unsupported speed source: {arguments.speed_source}")
    speed_gap_ms = arguments.maximum_speed_interpolation_gap_ms
    if not math.isfinite(speed_gap_ms) or speed_gap_ms < 0.0:
        raise ValueError(
            "maximum-speed-interpolation-gap-ms must be finite and nonnegative"
        )
    odometry_gap_ms = arguments.maximum_odometry_interpolation_gap_ms
    if not math.isfinite(odometry_gap_ms) or odometry_gap_ms < 0.0:
        raise ValueError(
            "maximum-odometry-interpolation-gap-ms must be finite and nonnegative"
        )
    if not math.isfinite(arguments.max_step_m) or arguments.max_step_m <= 0.0:
        raise ValueError("max-step-m must be finite and positive")
    return (
        int(round(speed_gap_ms * 1_000_000.0)),
        int(round(odometry_gap_ms * 1_000_000.0)),
    )


def run_conditional_feature_audit(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Audit feature availability for every canonical residual vector."""

    maximum_speed_gap_ns, maximum_odometry_gap_ns = _validate_arguments(arguments)
    artifacts = load_gaussian_baseline_artifacts(
        arguments.gaussian_baseline_directory
    )
    manifest, recordings = _validated_manifest_recordings(
        alignment_batch_directory=arguments.alignment_batch_directory,
        baseline_dataset_summary=artifacts.dataset_summary,
        mcap_inputs=arguments.mcap,
    )
    observations_by_recording: dict[str, list[ResidualObservation]] = {
        recording.recording_id: [] for recording in recordings
    }
    drive_by_recording = {
        recording.recording_id: recording.drive_id for recording in recordings
    }
    for observation in artifacts.dataset.observations:
        expected_drive = drive_by_recording.get(observation.recording_id)
        if expected_drive is None or expected_drive != observation.drive_id:
            raise ResidualDatasetContractError(
                "residual observation does not reconcile with exact manifest"
            )
        observations_by_recording[observation.recording_id].append(observation)
    if any(not values for values in observations_by_recording.values()):
        raise ResidualDatasetContractError(
            "every manifest recording must contribute canonical residual vectors"
        )

    all_rows: list[dict[str, Any]] = []
    recording_rows: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()
    for recording in recordings:
        result = _extract_recording_features(
            recording,
            observations_by_recording[recording.recording_id],
            estimate_topic=arguments.estimate_topic,
            speed_source=arguments.speed_source,
            speed_topic=arguments.speed_topic,
            odometry_topic=arguments.odometry_topic,
            maximum_speed_interpolation_gap_ns=maximum_speed_gap_ns,
            maximum_odometry_interpolation_gap_ns=maximum_odometry_gap_ns,
            max_step_m=arguments.max_step_m,
        )
        all_rows.extend(result.rows)
        recording_rows.append(result.summary_row)
        failure_counts.update(result.failure_counts)
    if len(all_rows) != len(artifacts.dataset.observations):
        raise ResidualDatasetContractError("feature audit row count does not reconcile")

    _ensure_empty_output(arguments.output_directory)
    write_csv_rows(
        arguments.output_directory / "conditional_features.csv",
        FEATURE_FIELDS,
        all_rows,
    )
    write_csv_rows(
        arguments.output_directory / "conditional_feature_recording_summary.csv",
        RECORDING_SUMMARY_FIELDS,
        recording_rows,
    )
    plot_conditional_feature_audit(
        arguments.output_directory / "conditional_feature_audit.png",
        feature_rows=all_rows,
        recording_rows=recording_rows,
    )

    ready_rows = [row for row in all_rows if row["feature_state"] == "ready"]
    ready_by_drive = Counter(row["drive_id"] for row in ready_rows)
    total_by_drive = Counter(row["drive_id"] for row in all_rows)
    complete = len(ready_rows) == len(all_rows)
    baseline_names = (
        "residual_vectors.csv",
        "residual_dataset_summary.json",
        "gaussian_model.json",
        "gaussian_summary.json",
    )
    summary = {
        "version": VERSION,
        "status": "complete" if complete else "incomplete",
        "purpose": "exact_manifest_prediction_time_conditional_feature_audit",
        "source_baseline_version": "0.6.0",
        "source_baseline_files_sha256": {
            name: _sha256(arguments.gaussian_baseline_directory / name)
            for name in baseline_names
        },
        "source_alignment_manifest_sha256": _sha256(
            arguments.alignment_batch_directory / "batch_manifest.json"
        ),
        "source_alignment_manifest_version": manifest["version"],
        "drive_grouping_source": "accepted_exact_alignment_manifest",
        "recording_count": len(recordings),
        "drive_count": len(total_by_drive),
        "residual_vector_count": len(all_rows),
        "feature_ready_count": len(ready_rows),
        "feature_not_ready_count": len(all_rows) - len(ready_rows),
        "feature_ready_fraction": len(ready_rows) / len(all_rows),
        "feature_ready_count_by_drive": dict(sorted(ready_by_drive.items())),
        "residual_vector_count_by_drive": dict(sorted(total_by_drive.items())),
        "feature_failure_counts": dict(sorted(failure_counts.items())),
        "canonical_condition_horizon_m": 100,
        "canonical_condition_station_grid_m": list(
            CANONICAL_CONDITION_STATIONS_M
        ),
        "model_feature_fields": [
            "speed_mps",
            "estimated_mean_abs_curvature_per_m",
            "estimated_curvature_delta_per_m",
            "confidence_near_mean",
            "confidence_middle_mean",
            "confidence_far_mean",
        ],
        "speed_source": arguments.speed_source,
        "speed_topic": (
            arguments.speed_topic
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else arguments.odometry_topic
        ),
        "speed_units": "m/s",
        "speed_is_signed": arguments.speed_source == DIRECT_SPEED_SOURCE,
        "speed_reference": (
            "signed_longitudinal_speed_in_rear_axle_coordinates"
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else "unsigned_rear_axle_odometry_displacement_speed"
        ),
        "speed_timestamp_basis": (
            "direct_signal_message_timestamp_copied_from_odometry"
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else "estimate_source_time_and_exactly_50ms_earlier"
        ),
        "speed_interpolation": (
            "recording_local_linear_no_extrapolation"
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else (
                "recording_local_pose_interpolation_at_both_50ms_endpoints; "
                "euclidean_displacement_divided_by_0.05s; no_extrapolation"
            )
        ),
        "speed_displacement_interval_ms": (
            None
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else ODOMETRY_SPEED_INTERVAL_MS
        ),
        "speed_direction_limitation": (
            None
            if arguments.speed_source == DIRECT_SPEED_SOURCE
            else "reverse_motion_sign_is_not_observable_from_displacement_magnitude"
        ),
        "maximum_speed_interpolation_gap_ms": (
            arguments.maximum_speed_interpolation_gap_ms
        ),
        "maximum_odometry_interpolation_gap_ms": (
            arguments.maximum_odometry_interpolation_gap_ms
        ),
        "estimate_topic": arguments.estimate_topic,
        "estimate_matching": "exact_recording_local_message_index_and_source_time",
        "estimate_curvature_semantics": "validated_provisional_curvature_rate",
        "confidence_bucket_size_m": CONFIDENCE_BUCKET_SIZE_M,
        "confidence_native_basis": "selected_keep_lane_native_spline_arc_length",
        "confidence_ego_mapping": (
            "canonical ego-relative bin centers mapped to native spline station; "
            "no padding or extrapolation"
        ),
        "confidence_regions_ego_relative_m": {
            "near": [0, 30],
            "middle": [30, 65],
            "far": [65, 100],
        },
        "lane_width_included": False,
        "lane_width_exclusion_reason": (
            "available Road value is a fused per-segment minimum, not an "
            "ego-position measurement"
        ),
        "conditional_model_trained": False,
        "cohort_selection_performed": False,
        "next_decision": (
            "If feature coverage is adequate, freeze the complete conditional "
            "cohort and compare a drive-held-out conditional Gaussian with the "
            "unconditional v0.6.0 baseline on that identical cohort."
        ),
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "pair_count_is_independent_sample_size": False,
        "confidentiality": (
            "Outputs contain or derive from private BMW measurements."
        ),
    }
    write_strict_json(
        arguments.output_directory / "conditional_feature_summary.json",
        summary,
    )
    return summary, 0 if complete else 3


__all__ = [
    "DEFAULT_ESTIMATE_SCHEMA",
    "DEFAULT_ESTIMATE_TOPIC",
    "DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS",
    "DEFAULT_MAXIMUM_SPEED_INTERPOLATION_GAP_MS",
    "DIRECT_SPEED_SOURCE",
    "FEATURE_FIELDS",
    "ManifestRecording",
    "ODOMETRY_SPEED_SOURCE",
    "RECORDING_SUMMARY_FIELDS",
    "SPEED_SOURCE_CHOICES",
    "VERSION",
    "run_conditional_feature_audit",
]
