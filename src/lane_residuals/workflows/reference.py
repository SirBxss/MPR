"""Corpus CLI for v0.3.9 reference-candidate discovery and validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.geometry_validation import (
    ComparatorFrameAudit,
    EstimatedFrameAudit,
    GeometryValidationError,
    generate_spline_curve,
    estimated_frame_from_message,
    synchronize_estimate_and_comparator,
)
from ..io.mcap import (
    McapDependencyError,
    RoadMessageError,
    _source_time_ns,
    iter_decoded_mcap_messages,
    road_frame_from_message,
)
from ..domain.reference import (
    DEFAULT_REFERENCE_STATIONS_M,
    THESIS_TARGET_QUESTION,
    THESIS_TARGET_VARIABLE,
    CandidateGeometry,
    CenterlineWorldSample,
    LateralLaneSample,
    PoseSample,
    TimedMessage,
    audit_pose_continuity,
    boolean_scalar,
    build_hindsight_candidate,
    candidate_from_polyline,
    compare_estimate_to_candidate,
    compare_reference_candidates,
    finite_scalar,
    nearest_monotone_pairs,
    reconstruct_centerline_samples,
    reference_decision,
    resolve_first_path,
    sample_candidate,
    summarize_field_catalog,
)
from ..legacy.provisional_residuals import (
    DebugFrameAudit,
    compare_production_to_debug,
    debug_frame_from_message,
    production_error_matches_debug,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimedCandidate:
    message_index: int
    time_ns: int
    geometry: CandidateGeometry = field(repr=False)


@dataclass
class RecordingAudit:
    recording_id: str
    session_id: str
    source_path: Path
    status: str = "completed"
    error_code: str | None = None
    scan_complete: bool = True
    messages: list[TimedMessage] = field(default_factory=list)
    all_topic_inventory: list[dict[str, Any]] = field(default_factory=list)
    estimates: list[EstimatedFrameAudit] = field(default_factory=list)
    debug_frames: list[DebugFrameAudit] = field(default_factory=list)
    direct_map: list[TimedCandidate] = field(default_factory=list)
    fused_comparator: list[TimedCandidate] = field(default_factory=list)
    poses: list[PoseSample] = field(default_factory=list)
    lane_samples: list[LateralLaneSample] = field(default_factory=list)
    topic_counts: Counter[str] = field(default_factory=Counter)
    extraction_failures: Counter[str] = field(default_factory=Counter)
    semantic_rows: list[dict[str, Any]] = field(default_factory=list)
    frame_rows: list[dict[str, Any]] = field(default_factory=list)
    metric_rows: list[dict[str, Any]] = field(default_factory=list)


def _resolve_mcap_files(inputs: Sequence[Path]) -> tuple[Path, ...]:
    paths: dict[Path, None] = {}
    for raw in inputs:
        candidate = raw.expanduser()
        if candidate.is_file():
            if candidate.suffix.lower() != ".mcap":
                raise ValueError(f"input is not an MCAP file: {candidate}")
            paths[candidate.resolve()] = None
        elif candidate.is_dir():
            for path in candidate.rglob("*.mcap"):
                if path.is_file():
                    paths[path.resolve()] = None
        else:
            raise FileNotFoundError(f"MCAP input not found: {candidate}")
    if not paths:
        raise ValueError("no MCAP files were resolved")
    return tuple(sorted(paths, key=lambda path: str(path).casefold()))


def _load_session_map(path: Path, files: Sequence[Path]) -> dict[Path, str]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, Mapping) or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in payload.items()
    ):
        raise ValueError("session map must be a JSON object of basename: label")
    basenames = [file.name for file in files]
    if len(set(basenames)) != len(basenames):
        raise ValueError("duplicate MCAP basenames make the session map ambiguous")
    missing = sorted(name for name in basenames if name not in payload)
    extra = sorted(name for name in payload if name not in set(basenames))
    if missing or extra:
        raise ValueError(
            "session map must match resolved basenames exactly; "
            f"missing={missing}, extra={extra}"
        )
    labels = sorted({str(payload[name]) for name in basenames})
    opaque = {label: f"session_{index:03d}" for index, label in enumerate(labels, 1)}
    return {file: opaque[str(payload[file.name])] for file in files}


def _load_signal_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, Mapping):
        raise ValueError("signal config must be a JSON object")
    topics = payload.get("topics")
    fields = payload.get("fields")
    conventions = payload.get("conventions")
    if not isinstance(topics, Mapping) or not isinstance(fields, Mapping):
        raise ValueError("signal config requires object-valued topics and fields")
    if not isinstance(conventions, Mapping):
        raise ValueError("signal config requires a conventions object")
    required_roles = {
        "estimate",
        "estimate_debug",
        "map_lane",
        "map_pose",
        "lsa_centerline",
        "fused_comparator",
    }
    missing_roles = sorted(required_roles - set(topics))
    if missing_roles:
        raise ValueError(f"signal config is missing topic roles: {missing_roles}")
    normalized_topics: dict[str, tuple[str, ...]] = {}
    for role, raw in topics.items():
        values = (raw,) if isinstance(raw, str) else tuple(raw) if isinstance(raw, list) else ()
        if not values or not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"topic role {role!r} must be a string or string list")
        normalized_topics[str(role)] = tuple(dict.fromkeys(values))
    normalized_fields: dict[str, tuple[str, ...]] = {}
    for name, raw in fields.items():
        values = (raw,) if isinstance(raw, str) else tuple(raw) if isinstance(raw, list) else ()
        if values and not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"field mapping {name!r} must contain strings")
        normalized_fields[str(name)] = values
    result = dict(payload)
    result["topics"] = normalized_topics
    result["fields"] = normalized_fields
    result["conventions"] = dict(conventions)
    return result


def _topic_role(config: Mapping[str, Any], topic: str) -> str | None:
    roles = [
        role for role, values in config["topics"].items() if topic in values
    ]
    if len(roles) > 1:
        raise ValueError(f"topic {topic!r} is assigned to multiple roles: {roles}")
    return roles[0] if roles else None


def _configured_paths(config: Mapping[str, Any], name: str) -> tuple[str, ...]:
    return tuple(config["fields"].get(name, ()))


def _optional_numeric(decoded: Any, config: Mapping[str, Any], name: str) -> float | None:
    paths = _configured_paths(config, name)
    if not paths:
        return None
    try:
        _, raw = resolve_first_path(decoded, paths)
        return finite_scalar(raw, logical_name=name)
    except (KeyError, GeometryValidationError):
        return None


def _required_numeric(decoded: Any, config: Mapping[str, Any], name: str) -> float:
    paths = _configured_paths(config, name)
    if not paths:
        raise GeometryValidationError(
            "field_mapping_missing", f"no configured paths for {name}"
        )
    try:
        _, raw = resolve_first_path(decoded, paths)
    except KeyError as error:
        raise GeometryValidationError(
            "field_mapping_unresolved", f"none of the configured paths resolved for {name}"
        ) from error
    return finite_scalar(raw, logical_name=name)


def _optional_flag(decoded: Any, config: Mapping[str, Any], name: str) -> bool | None:
    paths = _configured_paths(config, name)
    if not paths:
        return None
    try:
        _, raw = resolve_first_path(decoded, paths)
        return boolean_scalar(raw, logical_name=name)
    except (KeyError, GeometryValidationError):
        return None


def _schema_fingerprint(schema: Any, decoded: Any) -> str | None:
    raw = getattr(schema, "data", None)
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return hashlib.sha256(bytes(raw)).hexdigest()
    descriptor = getattr(decoded, "DESCRIPTOR", None)
    serialized = getattr(getattr(descriptor, "file", None), "serialized_pb", None)
    return hashlib.sha256(serialized).hexdigest() if isinstance(serialized, bytes) else None


def _payload_fingerprint(message: Any) -> str | None:
    raw = getattr(message, "data", None)
    return (
        hashlib.sha256(bytes(raw)).hexdigest()
        if isinstance(raw, (bytes, bytearray, memoryview))
        else None
    )


def _inspect_all_topic_metadata(path: Path) -> list[dict[str, Any]]:
    """Inventory every channel from the MCAP summary without decoding payloads."""

    try:
        from mcap.reader import make_reader
    except ImportError as error:
        raise McapDependencyError(
            'MCAP inspection requires the optional "mcap" dependencies'
        ) from error
    with path.open("rb") as stream:
        summary = make_reader(stream).get_summary()
    if summary is None:
        raise RoadMessageError("MCAP file has no readable summary")
    channels = getattr(summary, "channels", {}) or {}
    schemas = getattr(summary, "schemas", {}) or {}
    statistics = getattr(summary, "statistics", None)
    counts = (
        getattr(statistics, "channel_message_counts", {}) or {}
        if statistics is not None
        else {}
    )
    grouped: dict[str, dict[str, Any]] = {}
    for channel_id, channel in channels.items():
        topic = str(getattr(channel, "topic", ""))
        if not topic:
            continue
        row = grouped.setdefault(
            topic,
            {
                "topic": topic,
                "message_count": 0,
                "schema_names": set(),
                "schema_encodings": set(),
                "message_encodings": set(),
            },
        )
        row["message_count"] += int(counts.get(channel_id, 0))
        encoding = str(getattr(channel, "message_encoding", ""))
        if encoding:
            row["message_encodings"].add(encoding)
        schema = schemas.get(getattr(channel, "schema_id", None))
        if schema is not None:
            schema_name = str(getattr(schema, "name", ""))
            schema_encoding = str(getattr(schema, "encoding", ""))
            if schema_name:
                row["schema_names"].add(schema_name)
            if schema_encoding:
                row["schema_encodings"].add(schema_encoding)
    return [
        {
            **row,
            "schema_names": sorted(row["schema_names"]),
            "schema_encodings": sorted(row["schema_encodings"]),
            "message_encodings": sorted(row["message_encodings"]),
        }
        for _, row in sorted(grouped.items())
    ]


def _candidate_from_road_message(
    decoded: Any,
    *,
    topic: str,
    schema_name: str,
    log_time_ns: int,
    publish_time_ns: int,
    message_index: int,
    source: str,
) -> TimedCandidate:
    frame = road_frame_from_message(
        decoded,
        topic=topic,
        schema_name=schema_name,
        log_time_ns=log_time_ns,
        publish_time_ns=publish_time_ns,
        sequence=message_index,
    )
    candidates = [
        segment
        for segment in frame.segments
        if segment.is_ego is True and segment.geometry_source == "drive_path"
    ]
    if len(candidates) != 1:
        raise GeometryValidationError(
            "map_ego_drive_path_not_unique",
            "road message must expose exactly one metadata-confirmed ego drive path",
        )
    segment = candidates[0]
    geometry = candidate_from_polyline(
        source=source,
        points=segment.points,
        stations_m=segment.arc_length,
        provenance=(
            "direct_map_lane_drive_path"
            if source == "direct_map_lane"
            else "fused_ego_lane_comparator"
        ),
    )
    time_ns = frame.source_time_ns
    if time_ns is None:
        raise GeometryValidationError(
            "road_source_time_missing", "road candidate requires a source timestamp"
        )
    return TimedCandidate(message_index=message_index, time_ns=time_ns, geometry=geometry)


def _pose_sample(
    message: TimedMessage,
    config: Mapping[str, Any],
) -> PoseSample:
    if message.source_time_ns is None:
        raise GeometryValidationError("pose_source_time_missing", "pose source time missing")
    yaw = _required_numeric(message.decoded, config, "pose_yaw_rad")
    valid = _optional_flag(message.decoded, config, "pose_valid")
    return PoseSample(
        recording_id=message.recording_id,
        session_id=message.session_id,
        message_index=message.message_index,
        time_ns=message.source_time_ns,
        x_m=_required_numeric(message.decoded, config, "pose_x_m"),
        y_m=_required_numeric(message.decoded, config, "pose_y_m"),
        yaw_rad=yaw,
        valid=True if valid is None else valid,
    )


def _lane_sample(
    message: TimedMessage,
    config: Mapping[str, Any],
) -> LateralLaneSample:
    if message.source_time_ns is None:
        raise GeometryValidationError(
            "centerline_source_time_missing", "centreline source time missing"
        )
    valid = _optional_flag(message.decoded, config, "centerline_valid")
    change_flags = [
        value
        for value in (
            _optional_flag(message.decoded, config, "lane_change_left"),
            _optional_flag(message.decoded, config, "lane_change_right"),
        )
        if value is not None
    ]
    ambiguity = _optional_flag(message.decoded, config, "road_ambiguity_detected")
    return LateralLaneSample(
        recording_id=message.recording_id,
        session_id=message.session_id,
        message_index=message.message_index,
        time_ns=message.source_time_ns,
        distance_to_centerline_m=_required_numeric(
            message.decoded, config, "distance_to_centerline_m"
        ),
        distance_to_left_boundary_m=_optional_numeric(
            message.decoded, config, "distance_to_left_boundary_m"
        ),
        distance_to_right_boundary_m=_optional_numeric(
            message.decoded, config, "distance_to_right_boundary_m"
        ),
        lane_change_detected=any(change_flags),
        road_ambiguity_detected=False if ambiguity is None else ambiguity,
        valid=True if valid is None else valid,
    )


def _validate_stations(raw: Sequence[float]) -> tuple[float, ...]:
    values = np.asarray(raw, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.all(np.isfinite(values)):
        raise ValueError("stations must be a finite vector of at least two values")
    if values[0] < 0.0 or not np.all(np.diff(values) > 0.0):
        raise ValueError("stations must be nonnegative and strictly increasing")
    return tuple(float(value) for value in values)


def _process_recording(
    path: Path,
    *,
    recording_id: str,
    session_id: str,
    config: Mapping[str, Any],
    arguments: argparse.Namespace,
) -> RecordingAudit:
    result = RecordingAudit(
        recording_id=recording_id,
        session_id=session_id,
        source_path=path,
    )
    requested_topics = tuple(
        dict.fromkeys(
            topic for values in config["topics"].values() for topic in values
        )
    )
    per_topic_seen: Counter[str] = Counter()
    try:
        result.all_topic_inventory = _inspect_all_topic_metadata(path)
        iterator = iter_decoded_mcap_messages(
            path, topics=requested_topics, include_ros1=True
        )
        for schema, channel, mcap_message, decoded in iterator:
            topic = str(getattr(channel, "topic", ""))
            if topic not in requested_topics:
                continue
            if (
                arguments.max_messages_per_topic is not None
                and per_topic_seen[topic] >= arguments.max_messages_per_topic
            ):
                result.scan_complete = False
                continue
            message_index = per_topic_seen[topic]
            per_topic_seen[topic] += 1
            result.topic_counts[topic] += 1
            role = _topic_role(config, topic)
            schema_name = str(getattr(schema, "name", ""))
            log_time_ns = int(getattr(mcap_message, "log_time", 0))
            publish_time_ns = int(getattr(mcap_message, "publish_time", 0))
            timed = TimedMessage(
                recording_id=recording_id,
                session_id=session_id,
                topic=topic,
                schema_name=schema_name,
                message_encoding=str(getattr(channel, "message_encoding", "")),
                message_index=message_index,
                log_time_ns=log_time_ns,
                publish_time_ns=publish_time_ns,
                source_time_ns=_source_time_ns(decoded),
                decoded=decoded,
                schema_fingerprint=_schema_fingerprint(schema, decoded),
                payload_fingerprint=_payload_fingerprint(mcap_message),
            )
            result.messages.append(timed)
            try:
                if role == "estimate":
                    result.estimates.append(
                        estimated_frame_from_message(
                            decoded,
                            message_index=message_index,
                            log_time_ns=log_time_ns,
                            publish_time_ns=publish_time_ns,
                            schema_fingerprint=timed.schema_fingerprint,
                            payload_fingerprint=timed.payload_fingerprint,
                        )
                    )
                elif role == "estimate_debug":
                    result.debug_frames.append(
                        debug_frame_from_message(
                            decoded,
                            message_index=message_index,
                            log_time_ns=log_time_ns,
                            publish_time_ns=publish_time_ns,
                            schema_fingerprint=timed.schema_fingerprint,
                            payload_fingerprint=timed.payload_fingerprint,
                        )
                    )
                elif role == "map_lane":
                    result.direct_map.append(
                        _candidate_from_road_message(
                            decoded,
                            topic=topic,
                            schema_name=schema_name,
                            log_time_ns=log_time_ns,
                            publish_time_ns=publish_time_ns,
                            message_index=message_index,
                            source="direct_map_lane",
                        )
                    )
                elif role == "fused_comparator":
                    result.fused_comparator.append(
                        _candidate_from_road_message(
                            decoded,
                            topic=topic,
                            schema_name=schema_name,
                            log_time_ns=log_time_ns,
                            publish_time_ns=publish_time_ns,
                            message_index=message_index,
                            source="fused_ego_lane_comparator",
                        )
                    )
                elif role == "map_pose":
                    result.poses.append(_pose_sample(timed, config))
                elif role == "lsa_centerline":
                    result.lane_samples.append(_lane_sample(timed, config))
            except (GeometryValidationError, RoadMessageError, KeyError, ValueError) as error:
                result.extraction_failures[getattr(error, "code", type(error).__name__)] += 1
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        result.status = "file_failed"
        result.error_code = getattr(error, "code", type(error).__name__)
        result.scan_complete = False
    return result


def _session_origins(results: Sequence[RecordingAudit]) -> dict[str, int]:
    origins: dict[str, int] = {}
    for result in results:
        times = [
            message.source_time_ns
            if message.source_time_ns is not None
            else message.publish_time_ns
            for message in result.messages
        ]
        if times:
            origins[result.session_id] = min(origins.get(result.session_id, min(times)), min(times))
    return origins


def _relative_time_s(time_ns: int | None, session_id: str, origins: Mapping[str, int]) -> float | None:
    if time_ns is None or session_id not in origins:
        return None
    return (int(time_ns) - int(origins[session_id])) / 1e9


def _evaluate_estimator_semantics(
    result: RecordingAudit,
    *,
    maximum_delta_ms: float,
    max_step_m: float,
    stations_m: Sequence[float],
) -> tuple[dict[int, Any], bool]:
    sync = synchronize_estimate_and_comparator(
        result.estimates,
        result.debug_frames,  # structural protocol is shared
        max_delta_ms=maximum_delta_ms,
    )
    debug_by_index = {item.message_index: item for item in result.debug_frames}
    estimates_by_index = {item.message_index: item for item in result.estimates}
    curves: dict[int, Any] = {}
    all_status_match = (
        bool(result.estimates)
        and bool(result.debug_frames)
        and len(sync.pairs) == len(result.estimates)
    )
    all_candidate_semantics_match = True
    for pair in sync.pairs:
        estimate = estimates_by_index[pair.estimate_index]
        debug = debug_by_index[pair.comparator_index]
        status_match = production_error_matches_debug(
            estimate.keep_lane_error, debug.keep_lane_error_value
        )
        semantic = None
        curve_status = None
        if estimate.candidate:
            if not debug.ready or debug.parameters is None:
                all_candidate_semantics_match = False
                curve_status = "debug_not_ready"
            else:
                semantic = compare_production_to_debug(estimate.candidate, debug.parameters)
                all_candidate_semantics_match &= semantic.passed
                if semantic.passed:
                    try:
                        curves[estimate.message_index] = generate_spline_curve(
                            estimate.candidate,
                            meaning="curvature_rate",
                            anchor_policy="anchor_zero",
                            max_step_m=max_step_m,
                            extra_stations=stations_m,
                        )
                        curve_status = "curve_ready"
                    except GeometryValidationError as error:
                        all_candidate_semantics_match = False
                        curve_status = error.code
        all_status_match &= status_match
        result.semantic_rows.append(
            {
                "recording_id": result.recording_id,
                "session_id": result.session_id,
                "estimate_frame_index": estimate.message_index,
                "status_correspondence": status_match,
                "semantic_status": None if semantic is None else semantic.status,
                "semantic_failure_code": None if semantic is None else semantic.failure_code,
                "curve_status": curve_status,
                "source_delta_ms": pair.source_delta_ns / 1e6,
            }
        )
    return curves, bool(all_status_match and all_candidate_semantics_match)


def _driven_world_samples(poses: Sequence[PoseSample]) -> tuple[CenterlineWorldSample, ...]:
    return tuple(
        CenterlineWorldSample(
            recording_id=item.recording_id,
            session_id=item.session_id,
            time_ns=item.time_ns,
            x_m=item.x_m,
            y_m=item.y_m,
            heading_rad=item.yaw_rad,
            lane_change_detected=False,
            road_ambiguity_detected=False,
            provenance="realised_vehicle_trajectory__diagnostic_only",
        )
        for item in sorted(poses, key=lambda value: value.time_ns)
        if item.valid
    )


def _nearest_candidate(
    time_ns: int,
    candidates: Sequence[TimedCandidate],
    *,
    maximum_delta_ms: float,
) -> TimedCandidate | None:
    if not candidates:
        return None
    pairs = nearest_monotone_pairs(
        [time_ns], [item.time_ns for item in candidates], maximum_delta_ms=maximum_delta_ms
    )
    return None if not pairs else candidates[pairs[0][1]]


def _nearest_pose(
    time_ns: int,
    poses: Sequence[PoseSample],
    *,
    maximum_delta_ms: float,
) -> PoseSample | None:
    if not poses:
        return None
    pairs = nearest_monotone_pairs(
        [time_ns], [item.time_ns for item in poses], maximum_delta_ms=maximum_delta_ms
    )
    return None if not pairs else poses[pairs[0][1]]


def _deduplicate_poses(poses: Sequence[PoseSample]) -> tuple[PoseSample, ...]:
    """Keep one deterministic sample per session timestamp.

    Conflicting payloads are independently reported by the corpus duplicate
    audit and block reference promotion.
    """

    unique: dict[tuple[str, int], PoseSample] = {}
    for item in sorted(
        poses, key=lambda value: (value.session_id, value.time_ns, value.recording_id)
    ):
        unique.setdefault((item.session_id, item.time_ns), item)
    return tuple(unique.values())


def _deduplicate_lane_samples(
    samples: Sequence[LateralLaneSample],
) -> tuple[LateralLaneSample, ...]:
    unique: dict[tuple[str, int], LateralLaneSample] = {}
    for item in sorted(
        samples, key=lambda value: (value.session_id, value.time_ns, value.recording_id)
    ):
        unique.setdefault((item.session_id, item.time_ns), item)
    return tuple(unique.values())


def _deduplicate_candidates(
    candidates: Sequence[TimedCandidate],
) -> tuple[TimedCandidate, ...]:
    unique: dict[int, TimedCandidate] = {}
    for item in sorted(candidates, key=lambda value: (value.time_ns, value.message_index)):
        unique.setdefault(item.time_ns, item)
    return tuple(unique.values())


def _append_metric(
    rows: list[dict[str, Any]],
    *,
    result: RecordingAudit,
    estimate_index: int,
    time_ns: int,
    comparison: str,
    metrics: Mapping[str, float],
) -> None:
    rows.append(
        {
            "recording_id": result.recording_id,
            "session_id": result.session_id,
            "estimate_frame_index": estimate_index,
            "source_time_ns_private": time_ns,
            "comparison": comparison,
            **metrics,
        }
    )


def _evaluate_candidates(
    result: RecordingAudit,
    *,
    config: Mapping[str, Any],
    arguments: argparse.Namespace,
    estimate_curves: Mapping[int, Any],
    session_poses: Sequence[PoseSample],
    session_lane_samples: Sequence[LateralLaneSample],
    session_direct_map: Sequence[TimedCandidate],
    session_fused_comparator: Sequence[TimedCandidate],
    primary_estimate_indices: set[int],
) -> tuple[int, int, bool]:
    conventions = config["conventions"]
    centerline_samples: tuple[CenterlineWorldSample, ...] = ()
    continuity = audit_pose_continuity(
        session_poses,
        maximum_position_jump_m=arguments.maximum_position_step_m,
        maximum_yaw_jump_rad=arguments.maximum_yaw_step_rad,
    )
    if continuity["position_jump_count"] or continuity["yaw_jump_count"]:
        result.extraction_failures["pose_continuity_gate_failed"] += 1
    else:
        try:
            centerline_samples = reconstruct_centerline_samples(
                session_poses,
                session_lane_samples,
                maximum_delta_ms=arguments.pose_lsa_max_delta_ms,
                positive_offset_is_lane_left=bool(
                    conventions.get("centerline_positive_is_lane_left", False)
                ),
            )
        except GeometryValidationError as error:
            result.extraction_failures[error.code] += 1
    driven_samples = _driven_world_samples(session_poses)
    direct_ready_count = 0
    reconstructed_ready_count = 0
    both_in_recording = False
    for estimate in result.estimates:
        time_ns = estimate.source_time_ns
        frame_row: dict[str, Any] = {
            "recording_id": result.recording_id,
            "session_id": result.session_id,
            "estimate_frame_index": estimate.message_index,
            "estimate_state": estimate.estimator_state,
            "estimate_conversion_state": estimate.conversion_state,
            "debug_semantics_ready": estimate.message_index in estimate_curves,
            "direct_map_candidate_ready": False,
            "pose_offset_candidate_ready": False,
            "driven_trajectory_ready_diagnostic_only": False,
            "fused_comparator_ready": False,
            "failure_code": None,
        }
        if estimate.message_index not in primary_estimate_indices:
            frame_row["failure_code"] = "cross_chunk_duplicate_estimate"
            result.frame_rows.append(frame_row)
            continue
        if time_ns is None or estimate.message_index not in estimate_curves:
            frame_row["failure_code"] = (
                "estimate_source_time_missing" if time_ns is None else "estimate_not_semantically_ready"
            )
            result.frame_rows.append(frame_row)
            continue
        curve = estimate_curves[estimate.message_index]
        direct = _nearest_candidate(
            time_ns,
            session_direct_map,
            maximum_delta_ms=arguments.comparison_max_delta_ms,
        )
        fused = _nearest_candidate(
            time_ns,
            session_fused_comparator,
            maximum_delta_ms=arguments.comparison_max_delta_ms,
        )
        if direct is not None:
            try:
                sample_candidate(direct.geometry, arguments.stations_m)
            except GeometryValidationError as error:
                frame_row["failure_code"] = error.code
                direct = None
        if fused is not None:
            try:
                sample_candidate(fused.geometry, arguments.stations_m)
            except GeometryValidationError:
                fused = None
        anchor = _nearest_pose(
            time_ns, session_poses, maximum_delta_ms=arguments.pose_lsa_max_delta_ms
        )
        reconstructed = None
        driven = None
        if anchor is not None:
            try:
                reconstructed = build_hindsight_candidate(
                    centerline_samples,
                    anchor_pose=anchor,
                    maximum_inter_sample_gap_s=arguments.maximum_inter_sample_gap_s,
                    minimum_future_distance_m=max(arguments.stations_m),
                    maximum_stationary_duration_s=arguments.maximum_stationary_duration_s,
                    stationary_step_threshold_m=arguments.stationary_step_threshold_m,
                )
            except GeometryValidationError as error:
                frame_row["failure_code"] = error.code
            try:
                driven = build_hindsight_candidate(
                    driven_samples,
                    anchor_pose=anchor,
                    maximum_inter_sample_gap_s=arguments.maximum_inter_sample_gap_s,
                    minimum_future_distance_m=max(arguments.stations_m),
                    maximum_stationary_duration_s=arguments.maximum_stationary_duration_s,
                    stationary_step_threshold_m=arguments.stationary_step_threshold_m,
                )
            except GeometryValidationError:
                driven = None
        frame_row["direct_map_candidate_ready"] = direct is not None
        frame_row["pose_offset_candidate_ready"] = reconstructed is not None
        frame_row["driven_trajectory_ready_diagnostic_only"] = driven is not None
        frame_row["fused_comparator_ready"] = fused is not None
        direct_ready_count += int(direct is not None)
        reconstructed_ready_count += int(reconstructed is not None)
        both_in_recording |= direct is not None and reconstructed is not None
        if bool(conventions.get("candidate_paths_share_estimate_frame", False)):
            for name, candidate in (
                ("estimate_vs_direct_map_lane", None if direct is None else direct.geometry),
                ("estimate_vs_pose_offset_centerline", reconstructed),
                ("estimate_vs_fused_comparator", None if fused is None else fused.geometry),
            ):
                if candidate is None:
                    continue
                try:
                    discrepancy = compare_estimate_to_candidate(
                        curve, candidate, stations_m=arguments.stations_m
                    )
                except GeometryValidationError:
                    continue
                _append_metric(
                    result.metric_rows,
                    result=result,
                    estimate_index=estimate.message_index,
                    time_ns=time_ns,
                    comparison=name,
                    metrics={
                        "lateral_rms_m": discrepancy.lateral_rms_m,
                        "lateral_median_abs_m": float(np.median(np.abs(discrepancy.lateral_m))),
                        "lateral_max_abs_m": discrepancy.lateral_max_abs_m,
                        "heading_rms_rad": float(
                            np.sqrt(np.mean(np.square(discrepancy.heading_rad)))
                        ),
                    },
                )
        if (
            bool(conventions.get("candidate_paths_share_estimate_frame", False))
            and direct is not None
            and reconstructed is not None
        ):
            try:
                metrics = compare_reference_candidates(
                    direct.geometry, reconstructed, stations_m=arguments.stations_m
                )
                _append_metric(
                    result.metric_rows,
                    result=result,
                    estimate_index=estimate.message_index,
                    time_ns=time_ns,
                    comparison="direct_map_lane_vs_pose_offset_centerline",
                    metrics=metrics,
                )
            except GeometryValidationError:
                pass
        if (
            bool(conventions.get("candidate_paths_share_estimate_frame", False))
            and reconstructed is not None
            and fused is not None
        ):
            try:
                metrics = compare_reference_candidates(
                    reconstructed, fused.geometry, stations_m=arguments.stations_m
                )
                _append_metric(
                    result.metric_rows,
                    result=result,
                    estimate_index=estimate.message_index,
                    time_ns=time_ns,
                    comparison="pose_offset_centerline_vs_fused_comparator",
                    metrics=metrics,
                )
            except GeometryValidationError:
                pass
        if driven is not None and reconstructed is not None:
            try:
                metrics = compare_reference_candidates(
                    driven, reconstructed, stations_m=arguments.stations_m
                )
                _append_metric(
                    result.metric_rows,
                    result=result,
                    estimate_index=estimate.message_index,
                    time_ns=time_ns,
                    comparison="driven_trajectory_vs_pose_offset_centerline__diagnostic_only",
                    metrics=metrics,
                )
            except GeometryValidationError:
                pass
        result.frame_rows.append(frame_row)
    return direct_ready_count, reconstructed_ready_count, both_in_recording


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _duplicate_audit(messages: Sequence[TimedMessage]) -> tuple[list[dict[str, Any]], bool]:
    groups: dict[tuple[str, str, int], list[TimedMessage]] = defaultdict(list)
    for message in messages:
        time_ns = message.source_time_ns if message.source_time_ns is not None else message.publish_time_ns
        groups[(message.session_id, message.topic, int(time_ns))].append(message)
    rows: list[dict[str, Any]] = []
    conflict = False
    for (session_id, topic, _), group in sorted(groups.items()):
        recordings = {item.recording_id for item in group}
        if len(group) < 2 or len(recordings) < 2:
            continue
        payloads = {item.payload_fingerprint for item in group}
        current_conflict = len(payloads) > 1
        conflict |= current_conflict
        rows.append(
            {
                "session_id": session_id,
                "topic": topic,
                "recording_count": len(recordings),
                "duplicate_count": len(group),
                "status": "conflict" if current_conflict else "identical_duplicate",
            }
        )
    return rows, conflict


def _write_outputs(
    results: Sequence[RecordingAudit],
    *,
    config: Mapping[str, Any],
    arguments: argparse.Namespace,
    semantic_by_recording: Mapping[str, bool],
    direct_ready_total: int,
    reconstructed_ready_total: int,
    recordings_with_both: set[str],
) -> dict[str, Any]:
    output = arguments.output_directory
    output.mkdir(parents=True, exist_ok=True)
    origins = _session_origins(results)
    all_messages = [message for result in results for message in result.messages]
    all_frame_rows = [row for result in results for row in result.frame_rows]
    all_semantic_rows = [row for result in results for row in result.semantic_rows]
    all_metric_rows = [row for result in results for row in result.metric_rows]
    for row in all_metric_rows:
        row["session_relative_source_time_s"] = _relative_time_s(
            row.pop("source_time_ns_private"), row["session_id"], origins
        )
    for row in all_frame_rows:
        estimate = next(
            (
                item
                for result in results
                if result.recording_id == row["recording_id"]
                for item in result.estimates
                if item.message_index == row["estimate_frame_index"]
            ),
            None,
        )
        row["session_relative_source_time_s"] = _relative_time_s(
            None if estimate is None else estimate.source_time_ns,
            row["session_id"],
            origins,
        )
    catalog = summarize_field_catalog(
        all_messages,
        maximum_messages_per_topic=arguments.field_catalog_samples_per_topic,
    )
    inventory_topics: list[dict[str, Any]] = []
    for topic in sorted({message.topic for message in all_messages}):
        topic_messages = [message for message in all_messages if message.topic == topic]
        schemas = sorted({message.schema_name for message in topic_messages})
        fingerprints = sorted(
            {message.schema_fingerprint for message in topic_messages if message.schema_fingerprint}
        )
        times = sorted(
            message.source_time_ns
            for message in topic_messages
            if message.source_time_ns is not None
        )
        gaps = np.diff(np.asarray(times, dtype=np.int64)) / 1e9 if len(times) > 1 else np.asarray([])
        inventory_topics.append(
            {
                "role": _topic_role(config, topic),
                "topic": topic,
                "decoded_message_count": len(topic_messages),
                "recording_count": len({message.recording_id for message in topic_messages}),
                "schema_names": schemas,
                "schema_fingerprint_count": len(fingerprints),
                "source_timestamp_count": len(times),
                "median_rate_hz": (
                    None
                    if len(gaps) == 0 or not np.any(gaps > 0.0)
                    else float(1.0 / np.median(gaps[gaps > 0.0]))
                ),
            }
        )
    _write_json(
        output / "reference_source_inventory.json",
        {
            "version": "0.4.5",
            "purpose": "reference_candidate_discovery",
            "topics": inventory_topics,
            "all_topic_metadata_by_recording": [
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "topic_count": len(result.all_topic_inventory),
                    "topics": result.all_topic_inventory,
                }
                for result in results
            ],
            "recordings": [
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "status": result.status,
                    "scan_complete": result.scan_complete,
                    "topic_counts": dict(result.topic_counts),
                    "extraction_failures": dict(result.extraction_failures),
                }
                for result in results
            ],
        },
    )
    _write_json(output / "decoded_field_catalog.json", {"fields": catalog})

    pose_rows: list[dict[str, Any]] = []
    for result in results:
        audit = audit_pose_continuity(
            result.poses,
            maximum_position_jump_m=arguments.maximum_position_step_m,
            maximum_yaw_jump_rad=arguments.maximum_yaw_step_rad,
        )
        pose_rows.append(
            {
                "recording_id": result.recording_id,
                "session_id": result.session_id,
                "source_role": "map_pose",
                **audit,
                "stable_frame_operator_confirmed": bool(
                    config["conventions"].get("pose_is_stable_world_or_map_frame", False)
                ),
                "reference_point_operator_confirmed": bool(
                    config["conventions"].get("pose_reference_point_confirmed", False)
                ),
            }
        )
    for session_id in sorted({result.session_id for result in results}):
        session_pose_samples = _deduplicate_poses(
            [
                pose
                for result in results
                if result.session_id == session_id
                for pose in result.poses
            ]
        )
        audit = audit_pose_continuity(
            session_pose_samples,
            maximum_position_jump_m=arguments.maximum_position_step_m,
            maximum_yaw_jump_rad=arguments.maximum_yaw_step_rad,
        )
        pose_rows.append(
            {
                "recording_id": "session_aggregate",
                "session_id": session_id,
                "source_role": "map_pose_session_aggregate",
                **audit,
                "stable_frame_operator_confirmed": bool(
                    config["conventions"].get("pose_is_stable_world_or_map_frame", False)
                ),
                "reference_point_operator_confirmed": bool(
                    config["conventions"].get("pose_reference_point_confirmed", False)
                ),
            }
        )
    for result in results:
        for role in ("odometry", "gnss", "transforms"):
            supporting = [
                message
                for message in result.messages
                if _topic_role(config, message.topic) == role
            ]
            if not supporting:
                continue
            times = sorted(
                message.source_time_ns
                if message.source_time_ns is not None
                else message.publish_time_ns
                for message in supporting
            )
            deltas = (
                np.diff(np.asarray(times, dtype=np.int64)) / 1e9
                if len(times) > 1
                else np.asarray([])
            )
            positive = deltas[deltas > 0.0]
            pose_rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "source_role": f"{role}_supporting_only",
                    "sample_count": len(supporting),
                    "duration_s": 0.0 if len(times) < 2 else (times[-1] - times[0]) / 1e9,
                    "median_rate_hz": (
                        None if len(positive) == 0 else float(1.0 / np.median(positive))
                    ),
                    "maximum_position_step_m": None,
                    "maximum_yaw_step_rad": None,
                    "position_jump_count": None,
                    "yaw_jump_count": None,
                    "stable_frame_operator_confirmed": False,
                    "reference_point_operator_confirmed": False,
                }
            )
    _write_csv(
        output / "pose_source_audit.csv",
        (
            "recording_id",
            "session_id",
            "source_role",
            "sample_count",
            "duration_s",
            "median_rate_hz",
            "maximum_position_step_m",
            "maximum_yaw_step_rad",
            "position_jump_count",
            "yaw_jump_count",
            "stable_frame_operator_confirmed",
            "reference_point_operator_confirmed",
        ),
        pose_rows,
    )
    lsa_rows: list[dict[str, Any]] = []
    for result in results:
        for sample in result.lane_samples:
            boundary = sample.boundary_derived_offset_m
            lsa_rows.append(
                {
                    "recording_id": result.recording_id,
                    "session_id": result.session_id,
                    "message_index": sample.message_index,
                    "session_relative_source_time_s": _relative_time_s(
                        sample.time_ns, result.session_id, origins
                    ),
                    "distance_to_centerline_m": sample.distance_to_centerline_m,
                    "boundary_derived_offset_m": boundary,
                    "direct_minus_boundary_m": (
                        None if boundary is None else sample.distance_to_centerline_m - boundary
                    ),
                    "lane_change_detected": sample.lane_change_detected,
                    "road_ambiguity_detected": sample.road_ambiguity_detected,
                    "valid": sample.valid,
                }
            )
    _write_csv(
        output / "lsa_centerline_audit.csv",
        (
            "recording_id",
            "session_id",
            "message_index",
            "session_relative_source_time_s",
            "distance_to_centerline_m",
            "boundary_derived_offset_m",
            "direct_minus_boundary_m",
            "lane_change_detected",
            "road_ambiguity_detected",
            "valid",
        ),
        lsa_rows,
    )
    _write_csv(
        output / "reference_frame_eligibility.csv",
        (
            "recording_id",
            "session_id",
            "estimate_frame_index",
            "session_relative_source_time_s",
            "estimate_state",
            "estimate_conversion_state",
            "debug_semantics_ready",
            "direct_map_candidate_ready",
            "pose_offset_candidate_ready",
            "driven_trajectory_ready_diagnostic_only",
            "fused_comparator_ready",
            "failure_code",
        ),
        all_frame_rows,
    )
    _write_csv(
        output / "candidate_reference_metrics.csv",
        (
            "recording_id",
            "session_id",
            "estimate_frame_index",
            "session_relative_source_time_s",
            "comparison",
            "lateral_rms_m",
            "lateral_median_abs_m",
            "lateral_max_abs_m",
            "heading_rms_rad",
        ),
        all_metric_rows,
    )
    _write_csv(
        output / "debug_semantic_audit.csv",
        (
            "recording_id",
            "session_id",
            "estimate_frame_index",
            "status_correspondence",
            "semantic_status",
            "semantic_failure_code",
            "curve_status",
            "source_delta_ms",
        ),
        all_semantic_rows,
    )
    duplicate_rows, duplicate_conflict = _duplicate_audit(all_messages)
    _write_csv(
        output / "duplicate_conflict_audit.csv",
        ("session_id", "topic", "recording_count", "duplicate_count", "status"),
        duplicate_rows,
    )
    corpus_complete = (
        len(results) == arguments.expected_file_count
        and all(result.status == "completed" and result.scan_complete for result in results)
        and not duplicate_conflict
        and len({result.session_id for result in results}) >= 2
    )
    cross_rows = [
        row
        for row in all_metric_rows
        if row["comparison"] == "direct_map_lane_vs_pose_offset_centerline"
    ]
    candidate_median = (
        None
        if not cross_rows
        else float(np.median([row["lateral_median_abs_m"] for row in cross_rows]))
    )
    sessions_with_both = len(
        {
            next(result.session_id for result in results if result.recording_id == recording_id)
            for recording_id in recordings_with_both
        }
    )
    decision = reference_decision(
        complete_corpus=corpus_complete,
        estimator_semantics_valid=all(semantic_by_recording.values()) and bool(semantic_by_recording),
        direct_map_candidate_frames=direct_ready_total,
        reconstructed_candidate_frames=reconstructed_ready_total,
        sessions_with_both_candidates=sessions_with_both,
        candidate_lateral_median_abs_m=candidate_median,
        maximum_allowed_candidate_median_abs_m=arguments.max_candidate_median_abs_m,
        pose_frame_confirmed=bool(
            config["conventions"].get("pose_is_stable_world_or_map_frame", False)
        ),
        centerline_sign_confirmed=bool(
            config["conventions"].get("centerline_positive_is_lane_left", False)
        ),
        pose_reference_point_confirmed=bool(
            config["conventions"].get("pose_reference_point_confirmed", False)
        ),
        candidate_frame_confirmed=bool(
            config["conventions"].get("candidate_paths_share_estimate_frame", False)
        ),
    )
    summary = {
        "version": "0.4.5",
        "purpose": "reference_candidate_reconstruction_and_validation",
        "thesis_scope_changed": False,
        "thesis_target_question": THESIS_TARGET_QUESTION,
        "thesis_target_variable": THESIS_TARGET_VARIABLE,
        "estimate_role": "lane_estimate",
        "reference_candidates": [
            "direct_map_lane_geometry",
            "pose_plus_distance_to_centerline",
        ],
        "diagnostic_only_sources": [
            "realised_vehicle_trajectory",
            "fused_ego_lane_path",
        ],
        "corpus_complete": corpus_complete,
        "expected_file_count": arguments.expected_file_count,
        "processed_file_count": len(results),
        "session_count": len({result.session_id for result in results}),
        "estimator_semantics_valid": all(semantic_by_recording.values()) and bool(semantic_by_recording),
        "estimate_spline_reconstruction": "curvature_rate",
        "curvature_change_semantics_confirmed": False,
        "direct_map_candidate_frame_count": direct_ready_total,
        "pose_offset_candidate_frame_count": reconstructed_ready_total,
        "sessions_with_both_candidates": sessions_with_both,
        "candidate_cross_check_frame_count": len(cross_rows),
        "candidate_cross_check_median_abs_lateral_m": candidate_median,
        "predeclared_max_candidate_median_abs_m": arguments.max_candidate_median_abs_m,
        "decision": decision,
        "generated_final_residual_dataset": False,
        "fitted_statistical_model": False,
        "confidentiality": (
            "Outputs contain BMW-derived field names and measurements and must remain private."
        ),
    }
    _write_json(output / "reference_validation_summary.json", summary)
    return summary


def run_reference_audit(arguments: argparse.Namespace) -> dict[str, Any]:
    """Execute reference-candidate discovery and write the audit outputs."""
    files = _resolve_mcap_files(arguments.mcap_inputs)
    sessions = _load_session_map(arguments.session_map, files)
    config = _load_signal_config(arguments.signal_config)
    results = [
        _process_recording(
            path,
            recording_id=f"recording_{index:03d}",
            session_id=sessions[path],
            config=config,
            arguments=arguments,
        )
        for index, path in enumerate(files, 1)
    ]
    semantic_by_recording: dict[str, bool] = {}
    direct_total = 0
    reconstructed_total = 0
    recordings_with_both: set[str] = set()
    poses_by_session: dict[str, list[PoseSample]] = defaultdict(list)
    lanes_by_session: dict[str, list[LateralLaneSample]] = defaultdict(list)
    direct_by_session: dict[str, list[TimedCandidate]] = defaultdict(list)
    fused_by_session: dict[str, list[TimedCandidate]] = defaultdict(list)
    for result in results:
        poses_by_session[result.session_id].extend(result.poses)
        lanes_by_session[result.session_id].extend(result.lane_samples)
        direct_by_session[result.session_id].extend(result.direct_map)
        fused_by_session[result.session_id].extend(result.fused_comparator)
    session_poses = {
        key: _deduplicate_poses(values) for key, values in poses_by_session.items()
    }
    session_lanes = {
        key: _deduplicate_lane_samples(values) for key, values in lanes_by_session.items()
    }
    session_direct = {
        key: _deduplicate_candidates(values) for key, values in direct_by_session.items()
    }
    session_fused = {
        key: _deduplicate_candidates(values) for key, values in fused_by_session.items()
    }
    primary_estimates: dict[str, set[int]] = defaultdict(set)
    seen_estimate_times: set[tuple[str, int]] = set()
    for result in results:
        for estimate in result.estimates:
            if estimate.source_time_ns is None:
                primary_estimates[result.recording_id].add(estimate.message_index)
                continue
            key = (result.session_id, int(estimate.source_time_ns))
            if key in seen_estimate_times:
                continue
            seen_estimate_times.add(key)
            primary_estimates[result.recording_id].add(estimate.message_index)
    for result in results:
        curves, semantic_valid = _evaluate_estimator_semantics(
            result,
            maximum_delta_ms=arguments.comparison_max_delta_ms,
            max_step_m=arguments.max_step_m,
            stations_m=arguments.stations_m,
        )
        semantic_by_recording[result.recording_id] = semantic_valid
        direct, reconstructed, both = _evaluate_candidates(
            result,
            config=config,
            arguments=arguments,
            estimate_curves=curves,
            session_poses=session_poses.get(result.session_id, ()),
            session_lane_samples=session_lanes.get(result.session_id, ()),
            session_direct_map=session_direct.get(result.session_id, ()),
            session_fused_comparator=session_fused.get(result.session_id, ()),
            primary_estimate_indices=primary_estimates.get(result.recording_id, set()),
        )
        direct_total += direct
        reconstructed_total += reconstructed
        if both:
            recordings_with_both.add(result.recording_id)
    return _write_outputs(
        results,
        config=config,
        arguments=arguments,
        semantic_by_recording=semantic_by_recording,
        direct_ready_total=direct_total,
        reconstructed_ready_total=reconstructed_total,
        recordings_with_both=recordings_with_both,
    )
