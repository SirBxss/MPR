"""Strict manifest and outcome-blind MCAP inspection for v0.17 intake."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.alignment import project_point_to_path
from ..domain.conditional_features import (
    ConditionalFeatureError,
    derive_unsigned_odometry_speed,
    selected_keep_lane_confidences,
    summarize_estimate_conditions,
)
from ..domain.geometry_validation import (
    EstimatedFrameAudit,
    GeometryValidationError,
    SplineCurve,
    estimated_frame_from_message,
    generate_spline_curve,
)
from ..domain.independent_outing_intake import (
    EXPECTED_TOPOLOGY_SOURCE,
    FrameTechnicalEvidence,
    MAXIMUM_ANCHOR_DISTANCE_M,
    MAXIMUM_SEQUENCE_GAP_NS,
    ODOMETRY_INTERPOLATION_GAP_NS,
    RecordingTechnicalEvidence,
)
from ..domain.pairing import (
    EgoRelativePath,
    mutual_nearest_timestamp_pairs,
    ego_relative_path_from_spline,
    ordered_ego_lane_from_road_frame,
)
from ..domain.path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from .expanded_sequence_dataset_v0131 import (
    BoundaryOdometryStream,
    boundary_schemas_compatible,
    load_boundary_odometry_stream,
)
from .mcap import (
    RoadMessageError,
    iter_decoded_mcap_messages,
    road_frame_from_message,
    source_time_ns_from_message,
)
from .odometry import DEFAULT_ODOMETRY_TOPIC


DEFAULT_MAP_TOPIC = "/adp/road_lane_map_based"
DEFAULT_MAP_SCHEMA = "Adp.Perception.Road"
MAXIMUM_SPLINE_STEP_M = 0.25
MAP_MAXIMUM_SEGMENTS = 16
MAP_MAXIMUM_JUNCTION_GAP_M = 1.0
MAP_MAXIMUM_JUNCTION_HEADING_RAD = math.radians(30.0)


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON object key: {key}")
        payload[key] = value
    return payload


def read_strict_json_with_bytes(path: Path) -> tuple[Any, bytes]:
    """Read exact bytes and reject duplicate keys and non-finite constants."""

    source = path.expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"JSON file not found: {source}")
    raw = source.read_bytes()

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=reject_constant,
        )
    except UnicodeDecodeError as error:
        raise ValueError(f"JSON file must be UTF-8: {source}") from error
    return payload, raw


def discover_mcaps(root: Path) -> tuple[Path, ...]:
    """Discover every case-insensitive MCAP recursively in stable POSIX order."""

    source = root.expanduser()
    if not source.exists():
        raise FileNotFoundError(f"MCAP root not found: {source}")
    if not source.is_dir():
        raise ValueError(f"MCAP root must be a directory: {source}")
    resolved = source.resolve()
    files = tuple(
        sorted(
            (
                item.resolve()
                for item in resolved.rglob("*")
                if item.is_file() and item.suffix.lower() == ".mcap"
            ),
            key=lambda item: item.relative_to(resolved).as_posix(),
        )
    )
    if not files:
        raise ValueError(f"no MCAP files found recursively under {source}")
    return files


@dataclass(frozen=True)
class _DecodedEstimate:
    message_index: int
    source_time_ns: int | None
    frame: EstimatedFrameAudit | None
    curve: SplineCurve | None
    path: EgoRelativePath | None
    decoded: Any = None
    failure_code: str | None = None


@dataclass(frozen=True)
class _DecodedReference:
    message_index: int
    source_time_ns: int | None
    path: EgoRelativePath | None
    failure_code: str | None = None


def _decode_geometry_streams(
    path: Path,
) -> tuple[list[_DecodedEstimate], list[_DecodedReference], tuple[str, ...]]:
    estimates: list[_DecodedEstimate] = []
    references: list[_DecodedReference] = []
    stream_failures: list[str] = []
    try:
        iterator = iter_decoded_mcap_messages(
            path,
            topics=(DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC, DEFAULT_MAP_TOPIC),
            include_ros1=False,
        )
        for schema, channel, message, decoded in iterator:
            topic = str(getattr(channel, "topic", ""))
            schema_name = str(getattr(schema, "name", ""))
            encoding = str(getattr(channel, "message_encoding", "")).lower()
            log_time = int(getattr(message, "log_time", 0))
            publish_time = int(getattr(message, "publish_time", 0))
            source_time = source_time_ns_from_message(decoded)
            if source_time is not None and int(source_time) < 0:
                source_time = None
            if topic == DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC:
                index = len(estimates)
                frame: EstimatedFrameAudit | None = None
                curve: SplineCurve | None = None
                estimate_path: EgoRelativePath | None = None
                failure: str | None = None
                if (
                    schema_name != DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA
                    or encoding != "protobuf"
                ):
                    failure = "estimate_schema_or_encoding_mismatch"
                else:
                    try:
                        frame = estimated_frame_from_message(
                            decoded,
                            message_index=index,
                            log_time_ns=log_time,
                            publish_time_ns=publish_time,
                            require_sensor_topology=False,
                        )
                        source_time = frame.source_time_ns
                        if not frame.candidate_ready or frame.candidate is None:
                            failure = f"estimate_{frame.conversion_state}"
                        else:
                            curve = generate_spline_curve(
                                frame.candidate,
                                meaning="curvature_rate",
                                anchor_policy="anchor_zero",
                                max_step_m=MAXIMUM_SPLINE_STEP_M,
                                extra_stations=CANONICAL_MODEL_STATIONS_M,
                            )
                            estimate_path = ego_relative_path_from_spline(curve)
                    except (GeometryValidationError, TypeError, ValueError) as error:
                        failure = f"estimate_{getattr(error, 'code', type(error).__name__)}"
                estimates.append(
                    _DecodedEstimate(
                        message_index=index,
                        source_time_ns=(None if source_time is None else int(source_time)),
                        frame=frame,
                        curve=curve,
                        path=estimate_path,
                        decoded=decoded,
                        failure_code=failure,
                    )
                )
            elif topic == DEFAULT_MAP_TOPIC:
                index = len(references)
                reference_path: EgoRelativePath | None = None
                failure = None
                if schema_name != DEFAULT_MAP_SCHEMA or encoding != "protobuf":
                    failure = "map_schema_or_encoding_mismatch"
                else:
                    try:
                        road = road_frame_from_message(
                            decoded,
                            topic=topic,
                            schema_name=schema_name,
                            log_time_ns=log_time,
                            publish_time_ns=publish_time,
                            sequence=index,
                        )
                        source_time = road.source_time_ns
                        ordered = ordered_ego_lane_from_road_frame(
                            road,
                            required_forward_m=max(CANONICAL_MODEL_STATIONS_M),
                            max_segments=MAP_MAXIMUM_SEGMENTS,
                            max_junction_gap_m=MAP_MAXIMUM_JUNCTION_GAP_M,
                            max_junction_heading_delta_rad=(
                                MAP_MAXIMUM_JUNCTION_HEADING_RAD
                            ),
                        )
                        reference_path = ordered.path
                    except (
                        GeometryValidationError,
                        RoadMessageError,
                        TypeError,
                        ValueError,
                    ) as error:
                        failure = f"map_{getattr(error, 'code', type(error).__name__)}"
                references.append(
                    _DecodedReference(
                        message_index=index,
                        source_time_ns=(None if source_time is None else int(source_time)),
                        path=reference_path,
                        failure_code=failure,
                    )
                )
    except Exception as error:
        stream_failures.append(f"geometry_stream_decode_failed:{type(error).__name__}")
        # A partial prefix cannot prove complete-corpus topology or H100
        # eligibility. Discard it so the fixed support gate fails closed.
        estimates.clear()
        references.clear()
    return estimates, references, tuple(sorted(set(stream_failures)))


def _h100_geometry(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
) -> tuple[bool, float | None, str | None]:
    """Check the frozen spatial-alignment geometry without calculating residuals."""

    try:
        projection = project_point_to_path(estimate.origin_footpoint_m, reference)
    except (GeometryValidationError, TypeError, ValueError) as error:
        return False, None, f"h100_{getattr(error, 'code', type(error).__name__)}"
    stations = np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64)
    tolerance = 1e-9
    estimate_ready = (
        stations[0] >= estimate.stations_m[0] - tolerance
        and stations[-1] <= estimate.stations_m[-1] + tolerance
    )
    reference_stations = projection.station_m + stations
    reference_ready = (
        reference_stations[0] >= reference.stations_m[0] - tolerance
        and reference_stations[-1] <= reference.stations_m[-1] + tolerance
    )
    if not estimate_ready:
        return False, projection.distance_m, "h100_estimate_coverage_incomplete"
    if not reference_ready:
        return False, projection.distance_m, "h100_reference_coverage_incomplete"
    return True, projection.distance_m, None


def _load_odometry(path: Path) -> tuple[BoundaryOdometryStream | None, str | None]:
    try:
        return (
            load_boundary_odometry_stream(
                path,
                basename_private=path.name,
                topic=DEFAULT_ODOMETRY_TOPIC,
            ),
            None,
        )
    except Exception as error:
        return None, f"odometry_stream_decode_failed:{type(error).__name__}"


def _boundary_speed_available(
    *,
    timestamp_ns: int,
    previous_path: Path,
    current_path: Path,
    previous_frame: FrameTechnicalEvidence,
    current_topology_candidate: bool,
    current_topology_source: str,
) -> tuple[bool, str | None]:
    if (
        not previous_frame.topology_gate_candidate
        or previous_frame.topology_source_name != EXPECTED_TOPOLOGY_SOURCE
        or not current_topology_candidate
        or current_topology_source != EXPECTED_TOPOLOGY_SOURCE
        or previous_frame.source_time_ns is None
        or not 0 < timestamp_ns - previous_frame.source_time_ns <= MAXIMUM_SEQUENCE_GAP_NS
    ):
        return False, "boundary_context_endpoint_ineligible"
    left, left_error = _load_odometry(previous_path)
    right, right_error = _load_odometry(current_path)
    if left is None or right is None:
        return False, left_error or right_error or "boundary_odometry_unavailable"
    if not boundary_schemas_compatible(left, right):
        return False, "boundary_odometry_schema_incompatible"
    if (
        not left.strict_timestamps
        or not right.strict_timestamps
        or left.samples[-1].timestamp_ns >= right.samples[0].timestamp_ns
    ):
        return False, "boundary_odometry_timestamps_not_strict"
    try:
        speed = derive_unsigned_odometry_speed(
            left.samples + right.samples,
            timestamp_ns,
            maximum_bracket_gap_ns=ODOMETRY_INTERPOLATION_GAP_NS,
        )
    except (ConditionalFeatureError, GeometryValidationError, ValueError) as error:
        return False, f"boundary_speed_{getattr(error, 'code', type(error).__name__)}"
    contributing = {
        value
        for value in (
            speed.previous_pose.lower_timestamp_ns,
            speed.previous_pose.upper_timestamp_ns,
            speed.current_pose.lower_timestamp_ns,
            speed.current_pose.upper_timestamp_ns,
        )
    }
    left_times = {sample.timestamp_ns for sample in left.samples}
    right_times = {sample.timestamp_ns for sample in right.samples}
    if not contributing.intersection(left_times) or not contributing.intersection(right_times):
        return False, "boundary_context_did_not_use_both_mcaps"
    return True, None


def inspect_recording_technical_evidence(
    path: Path,
    *,
    raw_usable: bool,
    previous_path: Path | None = None,
    boundary_accepted: bool = False,
    previous_last_frame: FrameTechnicalEvidence | None = None,
) -> RecordingTechnicalEvidence:
    """Inspect one recording and retain only fixed technical states and counts."""

    estimates, references, stream_failures = _decode_geometry_streams(path)
    pairing = mutual_nearest_timestamp_pairs(
        [item.source_time_ns for item in estimates],
        [item.source_time_ns for item in references],
    )
    reference_by_estimate = {
        pair.first_position: references[pair.second_position] for pair in pairing.pairs
    }
    local_odometry, odometry_error = _load_odometry(path)
    recording_failures = list(stream_failures)
    if odometry_error is not None:
        recording_failures.append(odometry_error)

    frames: list[FrameTechnicalEvidence] = []
    for position, estimate in enumerate(estimates):
        failures: list[str] = []
        if not raw_usable:
            failures.append("raw_file_unusable")
        frame = estimate.frame
        topology_source = (
            "UNAVAILABLE_ENUM_VALUE" if frame is None else frame.topology_source
        )
        reference = reference_by_estimate.get(position)
        h100_ready = False
        anchor_distance: float | None = None
        if estimate.path is None:
            failures.append(estimate.failure_code or "estimate_geometry_not_ready")
        elif reference is None:
            failures.append("reference_pair_unavailable")
        elif reference.path is None:
            failures.append(reference.failure_code or "map_geometry_not_ready")
        else:
            h100_ready, anchor_distance, alignment_failure = _h100_geometry(
                estimate.path, reference.path
            )
            if alignment_failure is not None:
                failures.append(alignment_failure)
        topology_candidate = bool(
            frame is not None
            and frame.estimator_state == "available_no_error"
            and estimate.path is not None
            and reference is not None
            and reference.path is not None
            and h100_ready
        )
        if topology_source != EXPECTED_TOPOLOGY_SOURCE:
            failures.append("topology_source_not_sensor_topology")
        anchor_ready = bool(
            anchor_distance is not None
            and math.isfinite(anchor_distance)
            and anchor_distance <= MAXIMUM_ANCHOR_DISTANCE_M
        )
        if h100_ready and not anchor_ready:
            failures.append("anchor_distance_exceeds_1m_or_invalid")

        inputs_ready = False
        input_failure: str | None = None
        if estimate.curve is not None and estimate.path is not None:
            try:
                confidences = selected_keep_lane_confidences(estimate.decoded)
                values = summarize_estimate_conditions(
                    estimate.curve, estimate.path, confidences
                )
                finite_values = np.asarray(
                    (
                        values.estimated_mean_abs_curvature_per_m,
                        values.estimated_curvature_delta_per_m,
                        values.confidence_near_mean,
                        values.confidence_middle_mean,
                        values.confidence_far_mean,
                    ),
                    dtype=np.float64,
                )
                if not np.all(np.isfinite(finite_values)):
                    raise ConditionalFeatureError(
                        "estimate_inputs_non_finite", "causal inputs must be finite"
                    )
                if estimate.source_time_ns is None or local_odometry is None:
                    raise ConditionalFeatureError(
                        "odometry_reference_time_outside_coverage",
                        "odometry input is unavailable",
                    )
                derive_unsigned_odometry_speed(
                    local_odometry.samples,
                    estimate.source_time_ns,
                    maximum_bracket_gap_ns=ODOMETRY_INTERPOLATION_GAP_NS,
                )
                inputs_ready = True
            except (ConditionalFeatureError, GeometryValidationError, ValueError) as error:
                input_failure = str(getattr(error, "code", type(error).__name__))

        if (
            not inputs_ready
            and input_failure == "odometry_reference_time_outside_coverage"
            and estimate.message_index == 0
            and boundary_accepted
            and previous_path is not None
            and previous_last_frame is not None
            and estimate.source_time_ns is not None
        ):
            inputs_ready, boundary_failure = _boundary_speed_available(
                timestamp_ns=estimate.source_time_ns,
                previous_path=previous_path,
                current_path=path,
                previous_frame=previous_last_frame,
                current_topology_candidate=topology_candidate,
                current_topology_source=topology_source,
            )
            if not inputs_ready:
                input_failure = boundary_failure
        if not inputs_ready:
            failures.append(f"causal_inputs_{input_failure or 'not_ready'}")

        eligible = bool(
            raw_usable
            and estimate.source_time_ns is not None
            and topology_source == EXPECTED_TOPOLOGY_SOURCE
            and topology_candidate
            and h100_ready
            and anchor_ready
            and inputs_ready
        )
        frames.append(
            FrameTechnicalEvidence(
                estimate_message_index=estimate.message_index,
                source_time_ns=estimate.source_time_ns,
                topology_source_name=topology_source,
                topology_gate_candidate=topology_candidate,
                h100_geometry_ready=h100_ready,
                anchor_distance_within_limit=anchor_ready,
                causal_inputs_available=inputs_ready,
                raw_usable=raw_usable,
                eligible=eligible,
                failure_codes=tuple(sorted(set(failures))),
            )
        )
    return RecordingTechnicalEvidence(
        estimate_message_count=len(estimates),
        map_message_count=len(references),
        frames=tuple(frames),
        failure_codes=tuple(sorted(set(recording_failures))),
    )


__all__ = [
    "DEFAULT_MAP_SCHEMA",
    "DEFAULT_MAP_TOPIC",
    "MAP_MAXIMUM_JUNCTION_GAP_M",
    "MAP_MAXIMUM_JUNCTION_HEADING_RAD",
    "MAP_MAXIMUM_SEGMENTS",
    "MAXIMUM_SPLINE_STEP_M",
    "discover_mcaps",
    "inspect_recording_technical_evidence",
    "read_strict_json_with_bytes",
]
