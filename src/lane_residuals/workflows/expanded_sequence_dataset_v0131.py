"""Build v0.13.1 sequences with accepted-boundary odometry speed context."""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.conditional_features import (
    ConditionalFeatureError,
    derive_unsigned_odometry_speed,
)
from ..domain.expanded_sequence_dataset import (
    EXPECTED_TOPOLOGY_SOURCE,
    MAXIMUM_ANCHOR_DISTANCE_M,
)
from ..domain.expanded_sequence_dataset_v0131 import (
    BOUNDARY_CONTEXT_METHOD,
    PURPOSE,
    VERSION,
    BoundaryContextEvidence,
    boundary_context_eligible,
    boundary_context_rejection_reasons,
    standardization_contract_v0131,
)
from ..domain.geometry_validation import GeometryValidationError
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..io.expanded_sequence_dataset import (
    load_expanded_sequence_inputs,
    residual_profiles_by_pair,
    sha256_file,
    write_deterministic_npz,
)
from ..io.expanded_sequence_dataset_v0131 import (
    BoundaryOdometryStream,
    boundary_schemas_compatible,
    load_boundary_odometry_stream,
    load_v0130_baseline,
    validate_corrected_topology_lineage,
    validate_live_raw_hashes,
    validate_v0131_profile_archive,
)
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.expanded_sequence_dataset_v0131 import (
    plot_expanded_sequence_diagnostics_v0131,
)
from .conditional_features import ODOMETRY_SPEED_SOURCE, _resolve_mcap_files
from .expanded_sequence_dataset import (
    DRIVE_SUMMARY_FIELDS,
    EXCLUSION_FIELDS,
    PROFILE_AUDIT_FIELDS,
    SEQUENCE_MANIFEST_FIELDS,
    STITCH_FIELDS,
    _build_sequences_and_stitch_audit,
    _ensure_empty,
    _feature_rows,
    _make_audit_rows,
    _quantile,
    _strict_bool,
)


LOGGER = logging.getLogger(__name__)

PROFILE_AUDIT_V0131_FIELDS = PROFILE_AUDIT_FIELDS + (
    "speed_context_state",
    "speed_context_left_mcap_basename_private",
    "speed_context_right_mcap_basename_private",
    "speed_context_odometry_timestamps_ns_json_private",
)

BOUNDARY_CONTEXT_FIELDS = (
    "drive_id",
    "left_recording_id",
    "right_recording_id",
    "left_mcap_basename_private",
    "right_mcap_basename_private",
    "right_pair_index",
    "right_estimate_source_time_ns_private",
    "inventory_boundary_accepted",
    "same_physical_drive",
    "topology_source_continuous",
    "both_endpoints_sensor_h100",
    "immediate_sensor_h100_candidate",
    "estimate_timestamp_gap_ms",
    "estimate_timestamp_continuity_passes",
    "odometry_topic_present_both",
    "left_odometry_schema_identities_json",
    "right_odometry_schema_identities_json",
    "odometry_schema_compatible",
    "left_odometry_sample_count",
    "right_odometry_sample_count",
    "left_last_odometry_timestamp_ns_private",
    "right_first_odometry_timestamp_ns_private",
    "odometry_timestamps_strict_across_boundary",
    "recording_local_feature_state",
    "recording_local_failure_codes",
    "recording_local_failure_is_missing_history",
    "interpolation_succeeded",
    "interpolation_within_tolerance",
    "extrapolation_required",
    "both_mcaps_contributed",
    "contributing_mcap_basenames_json_private",
    "contributing_odometry_timestamps_ns_json_private",
    "derived_speed_mps",
    "feature_restored",
    "rejection_reasons",
)


def _manifest_paths(
    mcap_inputs: Sequence[Path], manifest: Mapping[str, Any]
) -> dict[str, Path]:
    resolved = _resolve_mcap_files(mcap_inputs)
    expected = {row["mcap_filename_private"] for row in manifest["recordings"]}
    if set(resolved) != expected:
        raise ValueError("raw MCAP inputs differ from exact v0.5.2 manifest")
    return resolved


def _pose_fields(speed: Any) -> dict[str, Any]:
    return {
        "speed_mps": speed.value_mps,
        "speed_evaluation_method": BOUNDARY_CONTEXT_METHOD,
        "speed_displacement_m": speed.displacement_m,
        "speed_displacement_interval_ms": speed.interval_ms,
        "speed_previous_target_timestamp_ns_private": speed.previous_pose.timestamp_ns,
        "speed_current_target_timestamp_ns_private": speed.current_pose.timestamp_ns,
        "speed_previous_lower_timestamp_ns_private": speed.previous_pose.lower_timestamp_ns,
        "speed_previous_upper_timestamp_ns_private": speed.previous_pose.upper_timestamp_ns,
        "speed_current_lower_timestamp_ns_private": speed.current_pose.lower_timestamp_ns,
        "speed_current_upper_timestamp_ns_private": speed.current_pose.upper_timestamp_ns,
        "speed_previous_interpolation_span_ms": speed.previous_pose.bracket_span_ms,
        "speed_current_interpolation_span_ms": speed.current_pose.bracket_span_ms,
    }


def _restore_boundary_odometry_features(
    *,
    messages: Sequence[Mapping[str, Any]],
    continuity_rows: Sequence[Mapping[str, Any]],
    features: dict[tuple[str, int], dict[str, Any]],
    resolved_paths: Mapping[str, Path],
    odometry_topic: str,
    maximum_odometry_gap_ns: int,
    maximum_contiguous_gap_ms: float,
    stream_loader: Callable[..., BoundaryOdometryStream] = load_boundary_odometry_stream,
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    """Restore only right endpoints whose frozen speed lacks prior-file history."""

    by_recording: dict[str, list[Mapping[str, Any]]] = {}
    for message in messages:
        by_recording.setdefault(str(message["recording_id"]), []).append(message)
    cache: dict[str, BoundaryOdometryStream] = {}
    restored: dict[tuple[str, int], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    def stream(basename: str) -> BoundaryOdometryStream:
        if basename not in cache:
            cache[basename] = stream_loader(
                resolved_paths[basename],
                basename_private=basename,
                topic=odometry_topic,
            )
        return cache[basename]

    for boundary in continuity_rows:
        left_id = str(boundary["left_recording_id"])
        right_id = str(boundary["right_recording_id"])
        left = by_recording[left_id][-1]
        right = by_recording[right_id][0]
        left_basename = str(left["mcap_basename_private"])
        right_basename = str(right["mcap_basename_private"])
        right_pair = int(right["pair_index"]) if right["pair_index"] != "" else -1
        key = (right_id, right_pair)
        feature = features.get(key)
        local_feature_state = "missing" if feature is None else str(feature.get("feature_state"))
        accepted = _strict_bool(boundary["stitchable"])
        same_drive = left["drive_id"] == right["drive_id"] == boundary["drive_id"]
        source_continuous = left["topology_source_name"] == right["topology_source_name"]
        sensor_h100 = (
            left["topology_source_name"] == EXPECTED_TOPOLOGY_SOURCE
            and right["topology_source_name"] == EXPECTED_TOPOLOGY_SOURCE
            and _strict_bool(left["h100_aligned_eligible"])
            and _strict_bool(right["h100_aligned_eligible"])
        )
        estimate_gap_ns = int(right["source_time_ns_private"]) - int(
            left["source_time_ns_private"]
        )
        estimate_time_ok = 0 < estimate_gap_ns <= maximum_contiguous_gap_ms * 1e6
        candidate = accepted and same_drive and source_continuous and sensor_h100 and estimate_time_ok
        local_failure = "" if feature is None else str(feature.get("failure_codes", ""))
        missing_history = (
            feature is not None
            and feature.get("feature_state") == "not_ready"
            and local_failure == "speed__odometry_reference_time_outside_coverage"
        )

        left_stream = right_stream = None
        topic_present = schema_ok = strict_across = False
        interpolation_ok = within_tolerance = both_contributed = False
        extrapolation_required = False
        speed = None
        interpolation_code = ""
        contributing_times: list[int] = []
        contributing_mcaps: list[str] = []
        if candidate:
            left_stream, right_stream = stream(left_basename), stream(right_basename)
            topic_present = left_stream.topic_present and right_stream.topic_present
            schema_ok = boundary_schemas_compatible(left_stream, right_stream)
            strict_across = (
                left_stream.strict_timestamps
                and right_stream.strict_timestamps
                and left_stream.samples[-1].timestamp_ns
                < right_stream.samples[0].timestamp_ns
            )
            if topic_present and schema_ok and strict_across and missing_history:
                combined = left_stream.samples + right_stream.samples
                try:
                    speed = derive_unsigned_odometry_speed(
                        combined,
                        int(right["source_time_ns_private"]),
                        maximum_bracket_gap_ns=maximum_odometry_gap_ns,
                    )
                    interpolation_ok = True
                    within_tolerance = (
                        speed.previous_pose.upper_timestamp_ns
                        - speed.previous_pose.lower_timestamp_ns
                        <= maximum_odometry_gap_ns
                        and speed.current_pose.upper_timestamp_ns
                        - speed.current_pose.lower_timestamp_ns
                        <= maximum_odometry_gap_ns
                    )
                    contributing_times = list(
                        dict.fromkeys(
                            (
                                speed.previous_pose.lower_timestamp_ns,
                                speed.previous_pose.upper_timestamp_ns,
                                speed.current_pose.lower_timestamp_ns,
                                speed.current_pose.upper_timestamp_ns,
                            )
                        )
                    )
                    left_times = {sample.timestamp_ns for sample in left_stream.samples}
                    right_times = {sample.timestamp_ns for sample in right_stream.samples}
                    for timestamp in contributing_times:
                        if timestamp in left_times:
                            contributing_mcaps.append(left_basename)
                        elif timestamp in right_times:
                            contributing_mcaps.append(right_basename)
                    contributing_mcaps = list(dict.fromkeys(contributing_mcaps))
                    both_contributed = set(contributing_mcaps) == {
                        left_basename,
                        right_basename,
                    }
                except (ConditionalFeatureError, GeometryValidationError, ValueError) as error:
                    interpolation_code = str(getattr(error, "code", type(error).__name__))
                    extrapolation_required = interpolation_code in {
                        "odometry_reference_time_outside_coverage",
                        "odometry_speed_history_outside_coverage",
                    }

        evidence = BoundaryContextEvidence(
            same_physical_drive=same_drive,
            inventory_boundary_accepted=accepted,
            topology_source_continuous=source_continuous,
            both_endpoints_sensor_h100=sensor_h100 and estimate_time_ok,
            odometry_topic_present_both=topic_present,
            odometry_schema_compatible=schema_ok,
            odometry_timestamps_strict_across_boundary=strict_across,
            recording_local_failure_is_missing_history=missing_history,
            interpolation_succeeded=interpolation_ok,
            interpolation_within_tolerance=within_tolerance,
            extrapolation_required=extrapolation_required,
            both_mcaps_contributed=both_contributed,
        )
        restored_ok = candidate and boundary_context_eligible(evidence)
        if restored_ok:
            assert feature is not None and speed is not None
            feature.update(_pose_fields(speed))
            feature["feature_state"] = "ready"
            feature["failure_codes"] = ""
            restored[key] = {
                "state": BOUNDARY_CONTEXT_METHOD,
                "left_mcap": left_basename,
                "right_mcap": right_basename,
                "timestamps": contributing_times,
            }
        reasons = list(boundary_context_rejection_reasons(evidence))
        if not estimate_time_ok:
            reasons.append("estimate_timestamp_continuity_failed")
        if interpolation_code:
            reasons.append(f"interpolation__{interpolation_code}")
        rows.append(
            {
                "drive_id": left["drive_id"],
                "left_recording_id": left_id,
                "right_recording_id": right_id,
                "left_mcap_basename_private": left_basename,
                "right_mcap_basename_private": right_basename,
                "right_pair_index": right["pair_index"],
                "right_estimate_source_time_ns_private": right["source_time_ns_private"],
                "inventory_boundary_accepted": accepted,
                "same_physical_drive": same_drive,
                "topology_source_continuous": source_continuous,
                "both_endpoints_sensor_h100": sensor_h100,
                "immediate_sensor_h100_candidate": candidate,
                "estimate_timestamp_gap_ms": estimate_gap_ns / 1e6,
                "estimate_timestamp_continuity_passes": estimate_time_ok,
                "odometry_topic_present_both": topic_present,
                "left_odometry_schema_identities_json": json.dumps(
                    [] if left_stream is None else left_stream.schema_identities,
                    separators=(",", ":"),
                ),
                "right_odometry_schema_identities_json": json.dumps(
                    [] if right_stream is None else right_stream.schema_identities,
                    separators=(",", ":"),
                ),
                "odometry_schema_compatible": schema_ok,
                "left_odometry_sample_count": 0 if left_stream is None else len(left_stream.samples),
                "right_odometry_sample_count": 0 if right_stream is None else len(right_stream.samples),
                "left_last_odometry_timestamp_ns_private": (
                    None if left_stream is None or not left_stream.samples
                    else left_stream.samples[-1].timestamp_ns
                ),
                "right_first_odometry_timestamp_ns_private": (
                    None if right_stream is None or not right_stream.samples
                    else right_stream.samples[0].timestamp_ns
                ),
                "odometry_timestamps_strict_across_boundary": strict_across,
                "recording_local_feature_state": local_feature_state,
                "recording_local_failure_codes": local_failure,
                "recording_local_failure_is_missing_history": missing_history,
                "interpolation_succeeded": interpolation_ok,
                "interpolation_within_tolerance": within_tolerance,
                "extrapolation_required": extrapolation_required,
                "both_mcaps_contributed": both_contributed,
                "contributing_mcap_basenames_json_private": json.dumps(
                    contributing_mcaps, separators=(",", ":")
                ),
                "contributing_odometry_timestamps_ns_json_private": json.dumps(
                    contributing_times, separators=(",", ":")
                ),
                "derived_speed_mps": None if speed is None else speed.value_mps,
                "feature_restored": restored_ok,
                "rejection_reasons": "" if restored_ok else ";".join(dict.fromkeys(reasons)),
            }
        )
    return rows, restored


def _parity_with_v0130(
    baseline: Mapping[str, np.ndarray], arrays: Mapping[str, np.ndarray]
) -> dict[str, Any]:
    baseline_keys = list(zip(baseline["recording_ids"], baseline["pair_indices"]))
    current_keys = list(zip(arrays["recording_ids"], arrays["pair_indices"]))
    current_index = {key: index for index, key in enumerate(current_keys)}
    missing = [key for key in baseline_keys if key not in current_index]
    residual_equal = feature_equal = not missing
    for base_index, key in enumerate(baseline_keys):
        if key not in current_index:
            continue
        index = current_index[key]
        residual_equal &= (
            baseline["residuals_m"][base_index].tobytes()
            == arrays["residuals_m"][index].tobytes()
        )
        feature_equal &= (
            baseline["conditions"][base_index].tobytes()
            == arrays["conditions"][index].tobytes()
        )
    added = [key for key in current_keys if key not in set(baseline_keys)]
    if not residual_equal or not feature_equal or missing:
        raise ValueError("v0.13.0 non-boundary tensor parity failed")
    return {
        "baseline_profile_count": len(baseline_keys),
        "common_profile_count": len(baseline_keys) - len(missing),
        "added_boundary_profile_count": len(added),
        "removed_profile_count": len(missing),
        "non_boundary_residual_bytes_identical": bool(residual_equal),
        "non_boundary_feature_bytes_identical": bool(feature_equal),
        "added_profile_keys": [
            {"recording_id": str(recording), "pair_index": int(pair)}
            for recording, pair in added
        ],
    }


def run_expanded_sequence_dataset_v0131(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], int]:
    """Build v0.13.1 without changing any v0.13.0 source or artifact."""

    maximum_gap_ms = float(arguments.maximum_contiguous_gap_ms)
    odometry_gap_ms = float(arguments.maximum_odometry_interpolation_gap_ms)
    if not math.isfinite(maximum_gap_ms) or maximum_gap_ms <= 0:
        raise ValueError("maximum-contiguous-gap-ms must be finite and positive")
    if not math.isfinite(odometry_gap_ms) or odometry_gap_ms < 0:
        raise ValueError("maximum-odometry-interpolation-gap-ms must be nonnegative")
    maximum_odometry_gap_ns = int(round(odometry_gap_ms * 1e6))
    inputs = load_expanded_sequence_inputs(
        alignment_directory=arguments.alignment_directory,
        topology_audit_directory=arguments.topology_audit_directory,
        expected_file_count=arguments.expected_file_count,
    )
    validate_corrected_topology_lineage(inputs, arguments.topology_audit_directory)
    baseline_arrays, baseline_summary, baseline_hashes = load_v0130_baseline(
        arguments.v0130_directory
    )
    resolved = _manifest_paths(arguments.mcap, inputs.alignment_manifest)
    live_raw_hashes = validate_live_raw_hashes(
        resolved, inputs.raw_mcap_sha256_by_basename
    )
    residual_profiles = residual_profiles_by_pair(inputs.station_rows)
    features, base_feature_failures = _feature_rows(
        mcap_inputs=arguments.mcap,
        manifest=inputs.alignment_manifest,
        pair_rows=inputs.alignment_pair_rows,
        profiles=residual_profiles,
        estimate_topic=arguments.estimate_topic,
        odometry_topic=arguments.odometry_topic,
        maximum_odometry_gap_ns=maximum_odometry_gap_ns,
        max_step_m=arguments.max_step_m,
    )
    boundary_rows, restored_context = _restore_boundary_odometry_features(
        messages=inputs.topology_message_rows,
        continuity_rows=inputs.continuity_rows,
        features=features,
        resolved_paths=resolved,
        odometry_topic=arguments.odometry_topic,
        maximum_odometry_gap_ns=maximum_odometry_gap_ns,
        maximum_contiguous_gap_ms=maximum_gap_ms,
    )
    audit_rows, eligible = _make_audit_rows(
        inputs.topology_message_rows, residual_profiles, features
    )
    boundary_by_key = {
        (row["right_recording_id"], int(row["right_pair_index"])): row
        for row in boundary_rows
        if row["right_pair_index"] != ""
        and _strict_bool(row["immediate_sensor_h100_candidate"])
    }
    for row in audit_rows:
        key = (
            (row["recording_id"], int(row["pair_index"]))
            if row["pair_index"] != ""
            else None
        )
        context = None if key is None else restored_context.get(key)
        boundary = None if key is None else boundary_by_key.get(key)
        if context is not None:
            row.update(
                {
                    "speed_context_state": context["state"],
                    "speed_context_left_mcap_basename_private": context["left_mcap"],
                    "speed_context_right_mcap_basename_private": context["right_mcap"],
                    "speed_context_odometry_timestamps_ns_json_private": json.dumps(
                        context["timestamps"], separators=(",", ":")
                    ),
                }
            )
        else:
            row.update(
                {
                    "speed_context_state": (
                        "boundary_context_rejected" if boundary is not None else "recording_local"
                    ),
                    "speed_context_left_mcap_basename_private": (
                        "" if boundary is None else boundary["left_mcap_basename_private"]
                    ),
                    "speed_context_right_mcap_basename_private": (
                        "" if boundary is None else boundary["right_mcap_basename_private"]
                    ),
                    "speed_context_odometry_timestamps_ns_json_private": "[]",
                }
            )
    sequences, stitch_rows = _build_sequences_and_stitch_audit(
        audit_rows,
        eligible,
        inputs.continuity_rows,
        maximum_gap_ms=maximum_gap_ms,
    )
    _ensure_empty(arguments.output_directory)

    sequence_rows: list[dict[str, Any]] = []
    for sequence in sequences:
        timestamps = np.asarray(
            [frame.estimate_source_time_ns_private for frame in sequence.frames],
            dtype=np.int64,
        )
        intervals = np.diff(timestamps).astype(float) / 1e6
        recordings = list(dict.fromkeys(frame.recording_id for frame in sequence.frames))
        mcaps = list(
            dict.fromkeys(frame.mcap_basename_private for frame in sequence.frames)
        )
        sequence_rows.append(
            {
                "sequence_id": sequence.sequence_id,
                "drive_id": sequence.drive_id,
                "drive_class": (
                    "clean_sensor"
                    if sequence.drive_id
                    in {"drive_001", "drive_002", "drive_003", "drive_004"}
                    else "mixed_source_sensor_fragment"
                ),
                "start_reasons": ";".join(sequence.start_reasons),
                "frame_count": sequence.length,
                "recording_count": len(recordings),
                "mcap_count": len(mcaps),
                "recording_ids_json": json.dumps(recordings, separators=(",", ":")),
                "mcap_basenames_json_private": json.dumps(mcaps, separators=(",", ":")),
                "first_timestamp_ns_private": int(timestamps[0]),
                "last_timestamp_ns_private": int(timestamps[-1]),
                "duration_s": (timestamps[-1] - timestamps[0]) / 1e9,
                "crosses_mcap": sequence.crosses_mcap,
                "minimum_interval_ms": (
                    None if not len(intervals) else float(np.min(intervals))
                ),
                "median_interval_ms": (
                    None if not len(intervals) else float(np.median(intervals))
                ),
                "maximum_interval_ms": (
                    None if not len(intervals) else float(np.max(intervals))
                ),
            }
        )

    drive_rows: list[dict[str, Any]] = []
    for drive in sorted({row["drive_id"] for row in audit_rows}):
        rows = [row for row in audit_rows if row["drive_id"] == drive]
        selected = [row for row in rows if row["profile_eligible"]]
        drive_sequences = [sequence for sequence in sequences if sequence.drive_id == drive]
        anchors = [float(row["anchor_distance_m"]) for row in selected]
        headings = [abs(float(row["anchor_heading_delta_rad"])) for row in selected]
        reasons = Counter(
            reason
            for row in rows
            for reason in row["exclusion_reasons"].split(";")
            if reason
        )
        drive_rows.append(
            {
                "drive_id": drive,
                "drive_class": (
                    "clean_sensor"
                    if drive in {"drive_001", "drive_002", "drive_003", "drive_004"}
                    else "mixed_source_sensor_fragment"
                ),
                "recording_count": len({row["recording_id"] for row in rows}),
                "candidate_message_count": len(rows),
                "eligible_profile_count": len(selected),
                "excluded_profile_count": len(rows) - len(selected),
                "sequence_count": len(drive_sequences),
                "cross_mcap_sequence_count": sum(
                    sequence.crosses_mcap for sequence in drive_sequences
                ),
                "stitched_boundary_count": sum(
                    _strict_bool(row["stitched"])
                    for row in stitch_rows
                    if row["drive_id"] == drive
                ),
                "topology_source_counts_json": json.dumps(
                    dict(
                        sorted(
                            Counter(
                                row["topology_source_name"] for row in rows
                            ).items()
                        )
                    ),
                    separators=(",", ":"),
                ),
                "exclusion_reason_counts_json": json.dumps(
                    dict(sorted(reasons.items())), separators=(",", ":")
                ),
                "anchor_distance_q50_m": _quantile(anchors, 0.5),
                "anchor_distance_q95_m": _quantile(anchors, 0.95),
                "anchor_distance_max_m": None if not anchors else max(anchors),
                "absolute_anchor_heading_q50_rad": _quantile(headings, 0.5),
                "absolute_anchor_heading_q95_rad": _quantile(headings, 0.95),
                "absolute_anchor_heading_max_rad": None if not headings else max(headings),
            }
        )

    all_reasons = sorted(
        {
            reason
            for row in audit_rows
            for reason in row["exclusion_reasons"].split(";")
            if reason
        }
    )
    exclusion_rows = [
        {
            "exclusion_reason": reason,
            "profile_count": sum(
                reason in row["exclusion_reasons"].split(";") for row in audit_rows
            ),
            "recording_count": len(
                {
                    row["recording_id"]
                    for row in audit_rows
                    if reason in row["exclusion_reasons"].split(";")
                }
            ),
            "drive_count": len(
                {
                    row["drive_id"]
                    for row in audit_rows
                    if reason in row["exclusion_reasons"].split(";")
                }
            ),
        }
        for reason in all_reasons
    ]

    profiles = [frame for sequence in sequences for frame in sequence.frames]
    context_for_profile = [restored_context.get(frame.key) for frame in profiles]
    arrays = {
        "residuals_m": np.stack([frame.residuals_m for frame in profiles]),
        "conditions": np.stack([frame.conditions for frame in profiles]),
        "timestamps_ns_private": np.asarray(
            [frame.estimate_source_time_ns_private for frame in profiles], dtype=np.int64
        ),
        "recording_ids": np.asarray([frame.recording_id for frame in profiles]),
        "drive_ids": np.asarray([frame.drive_id for frame in profiles]),
        "mcap_basenames_private": np.asarray(
            [frame.mcap_basename_private for frame in profiles]
        ),
        "sequence_ids": np.asarray(
            [sequence.sequence_id for sequence in sequences for _ in sequence.frames]
        ),
        "pair_indices": np.asarray([frame.pair_index for frame in profiles], dtype=np.int64),
        "estimate_message_indices": np.asarray(
            [frame.estimate_message_index for frame in profiles], dtype=np.int64
        ),
        "stations_m": np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64),
        "eligibility": np.ones(len(profiles), dtype=np.bool_),
        "exclusion_reasons": np.asarray(["" for _ in profiles]),
        "speed_context_states": np.asarray(
            ["recording_local" if item is None else item["state"] for item in context_for_profile]
        ),
        "speed_context_left_mcap_basenames_private": np.asarray(
            ["" if item is None else item["left_mcap"] for item in context_for_profile]
        ),
        "speed_context_right_mcap_basenames_private": np.asarray(
            ["" if item is None else item["right_mcap"] for item in context_for_profile]
        ),
        "speed_context_odometry_timestamps_ns_json_private": np.asarray(
            [
                "[]"
                if item is None
                else json.dumps(item["timestamps"], separators=(",", ":"))
                for item in context_for_profile
            ]
        ),
    }
    parity = _parity_with_v0130(baseline_arrays, arrays)
    archive = arguments.output_directory / "expanded_profile_dataset.npz"
    write_deterministic_npz(archive, arrays)
    validate_v0131_profile_archive(archive)
    write_csv_rows(
        arguments.output_directory / "profile_eligibility_audit.csv",
        PROFILE_AUDIT_V0131_FIELDS,
        audit_rows,
    )
    write_csv_rows(
        arguments.output_directory / "sequence_manifest.csv",
        SEQUENCE_MANIFEST_FIELDS,
        sequence_rows,
    )
    write_csv_rows(
        arguments.output_directory / "sequence_summary_by_drive.csv",
        DRIVE_SUMMARY_FIELDS,
        drive_rows,
    )
    write_csv_rows(
        arguments.output_directory / "cross_mcap_stitching_audit.csv",
        STITCH_FIELDS,
        stitch_rows,
    )
    write_csv_rows(
        arguments.output_directory / "boundary_odometry_context_audit.csv",
        BOUNDARY_CONTEXT_FIELDS,
        boundary_rows,
    )
    write_csv_rows(
        arguments.output_directory / "exclusion_reason_summary.csv",
        EXCLUSION_FIELDS,
        exclusion_rows,
    )
    write_strict_json(arguments.output_directory / "v0130_parity_audit.json", parity)
    plot_expanded_sequence_diagnostics_v0131(
        arguments.output_directory / "expanded_sequence_diagnostics.png",
        drive_rows=drive_rows,
        sequence_rows=sequence_rows,
        profile_rows=audit_rows,
    )

    immediate_count = sum(
        _strict_bool(row["immediate_sensor_h100_candidate"]) for row in boundary_rows
    )
    restored_count = len(restored_context)
    stitched_count = sum(_strict_bool(row["stitched"]) for row in stitch_rows)
    remaining_candidates = [
        row
        for row in boundary_rows
        if _strict_bool(row["immediate_sensor_h100_candidate"])
        and not _strict_bool(row["feature_restored"])
    ]
    clean_profiles = sum(
        frame.drive_id in {"drive_001", "drive_002", "drive_003", "drive_004"}
        for frame in profiles
    )
    clean_sequences = sum(
        sequence.drive_id in {"drive_001", "drive_002", "drive_003", "drive_004"}
        for sequence in sequences
    )
    headings = [abs(frame.anchor_heading_delta_rad) for frame in profiles]
    remaining_failures = Counter(base_feature_failures)
    remaining_failures["speed__odometry_reference_time_outside_coverage"] -= restored_count
    remaining_failures = Counter(
        {key: value for key, value in remaining_failures.items() if value > 0}
    )
    longest = max((sequence.length for sequence in sequences), default=0)
    summary = {
        "version": VERSION,
        "purpose": PURPOSE,
        "status": "complete",
        "audit_build_blockers": [],
        "downstream_modeling_constraints": [
            "train_validation_test_assignments_not_selected",
            "standardization_not_fitted",
            "model_hyperparameters_not_selected",
        ],
        "counting_semantics": {
            "exclusion_reason_counts": (
                "non_mutually_exclusive; one message may contribute to multiple reasons"
            )
        },
        "profile_count": len(profiles),
        "candidate_message_count": len(audit_rows),
        "excluded_message_count": len(audit_rows) - len(profiles),
        "sequence_count": len(sequences),
        "longest_sequence_frame_count": longest,
        "source_recording_count": len(inputs.alignment_manifest["recordings"]),
        "retained_recording_count": len({frame.recording_id for frame in profiles}),
        "drive_count": len({frame.drive_id for frame in profiles}),
        "clean_drive_ids": ["drive_001", "drive_002", "drive_003", "drive_004"],
        "mixed_source_drive_ids": ["drive_005", "drive_006", "drive_007", "drive_008"],
        "profile_count_by_drive_class": {
            "clean_sensor_drives_001_004": clean_profiles,
            "mixed_source_sensor_fragments_drives_005_008": len(profiles) - clean_profiles,
        },
        "sequence_count_by_drive_class": {
            "clean_sensor_drives_001_004": clean_sequences,
            "mixed_source_sensor_fragments_drives_005_008": len(sequences) - clean_sequences,
        },
        "eligible_absolute_anchor_heading_delta_rad": {
            "q50": _quantile(headings, 0.5),
            "q95": _quantile(headings, 0.95),
            "maximum": max(headings),
            "threshold_applied": False,
        },
        "profile_eligibility": {
            "required_topology_source": EXPECTED_TOPOLOGY_SOURCE,
            "h100_required": True,
            "exact_station_count": 21,
            "station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "maximum_anchor_distance_m_inclusive": MAXIMUM_ANCHOR_DISTANCE_M,
            "anchor_distance_rule_basis": "pre_model_geometric_validity_not_model_performance",
            "anchor_heading_threshold_applied": False,
            "valid_estimator_and_geometry_required": True,
            "finite_values_required": True,
        },
        "recording_038_h100_anchor_gate_exclusion_count": sum(
            row["recording_id"] == "recording_038"
            and _strict_bool(row["h100_aligned_eligible"])
            and "anchor_distance_exceeds_1m" in row["exclusion_reasons"]
            for row in audit_rows
        ),
        "maximum_contiguous_gap_ms": maximum_gap_ms,
        "cross_mcap_boundary_count": len(boundary_rows),
        "candidate_reconciliation": {
            "definition": "accepted_same_drive_time_contiguous_immediate_sensor_topology_h100_endpoints",
            "observed_count": immediate_count,
            "review_reference_count": 17,
            "matches_review_reference": immediate_count == 17,
            "reference_count_enforced": False,
        },
        "boundary_odometry_context": {
            "method": BOUNDARY_CONTEXT_METHOD,
            "restored_feature_count": restored_count,
            "remaining_candidate_count": len(remaining_candidates),
            "remaining_candidates": [
                {
                    "left_recording_id": row["left_recording_id"],
                    "right_recording_id": row["right_recording_id"],
                    "estimate_timestamp_gap_ms": row["estimate_timestamp_gap_ms"],
                    "rejection_reasons": row["rejection_reasons"],
                }
                for row in remaining_candidates
            ],
            "only_odometry_speed_uses_previous_mcap_context": True,
            "edp_path_cross_mcap_interpolation": False,
            "residual_cross_mcap_interpolation": False,
            "other_condition_cross_mcap_interpolation": False,
        },
        "stitched_cross_mcap_boundary_count": stitched_count,
        "v0130_parity": parity,
        "standardization": standardization_contract_v0131(),
        "split_assignments_selected": False,
        "model_hyperparameters_selected": False,
        "model_training_performed": False,
        "feature_contract": {
            "schema": "bmw_condition_schema_v1",
            "names": list(BMW_CONDITION_FEATURE_NAMES),
            "shape": [len(profiles), 6],
            "definitions_changed": False,
        },
        "residual_contract": {
            "shape": [len(profiles), 21],
            "stations_m": list(CANONICAL_MODEL_STATIONS_M),
        },
        "feature_extraction": {
            "speed_source": ODOMETRY_SPEED_SOURCE,
            "maximum_odometry_interpolation_gap_ms": odometry_gap_ms,
            "recording_local_default": True,
            "accepted_previous_mcap_odometry_context_only": True,
            "base_failure_counts": dict(sorted(base_feature_failures.items())),
            "remaining_failure_counts": dict(sorted(remaining_failures.items())),
        },
        "source_files_sha256": {
            **inputs.source_files_sha256,
            **{f"v0130/{name}": digest for name, digest in baseline_hashes.items()},
        },
        "live_raw_mcap_sha256_by_basename": live_raw_hashes,
    }
    write_strict_json(arguments.output_directory / "expanded_sequence_contract.json", summary)
    write_strict_json(
        arguments.output_directory / "train_only_standardization_metadata.json",
        standardization_contract_v0131(),
    )
    output_names = (
        "expanded_profile_dataset.npz",
        "profile_eligibility_audit.csv",
        "sequence_manifest.csv",
        "sequence_summary_by_drive.csv",
        "cross_mcap_stitching_audit.csv",
        "boundary_odometry_context_audit.csv",
        "exclusion_reason_summary.csv",
        "v0130_parity_audit.json",
        "expanded_sequence_contract.json",
        "train_only_standardization_metadata.json",
        "expanded_sequence_diagnostics.png",
    )
    manifest = {
        "version": VERSION,
        "purpose": PURPOSE,
        "status": "complete",
        "output_files": list(output_names),
        "archive_sha256": sha256_file(archive),
        "profile_count": len(profiles),
        "sequence_count": len(sequences),
        "boundary_feature_count": restored_count,
        "stitched_boundary_count": stitched_count,
        "split_assignments_selected": False,
        "model_hyperparameters_selected": False,
        "model_training_performed": False,
    }
    write_strict_json(arguments.output_directory / "expanded_sequence_manifest.json", manifest)
    generated = {
        name: sha256_file(arguments.output_directory / name)
        for name in (*output_names, "expanded_sequence_manifest.json")
    }
    provenance = {
        "version": VERSION,
        "purpose": PURPOSE,
        "corrected_topology_semantic_metadata_revision": (
            "rlmb_independence_explicitly_unknown"
        ),
        "source_files_sha256": summary["source_files_sha256"],
        "live_raw_mcap_sha256_by_basename": live_raw_hashes,
        "generated_outputs_sha256": generated,
    }
    write_strict_json(
        arguments.output_directory / "expanded_sequence_provenance.json", provenance
    )
    return summary, 0


__all__ = [
    "BOUNDARY_CONTEXT_FIELDS",
    "PROFILE_AUDIT_V0131_FIELDS",
    "_parity_with_v0130",
    "_restore_boundary_odometry_features",
    "run_expanded_sequence_dataset_v0131",
]
