"""Same-estimator debug semantics and low-level discrepancy helpers.

The earlier real-data workflow that promoted the fused ego-lane path to
provisional ground truth has been withdrawn.  The active v0.3.9 command is the
reference-candidate audit in :mod:`lane_residuals.reference_audit_cli`.

The debug parsing and production/debug comparison functions remain valid.  The
legacy residual geometry helper remains only for synthetic regression tests;
it must not be used on MCAP data until a lane-reference candidate has passed the
new scientific gate.  No function here fits a statistical model.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .geometry_validation import (
    DEFAULT_COMPARATOR_SCHEMA,
    DEFAULT_COMPARATOR_TOPIC,
    EstimatedFrameAudit,
    ComparatorFrameAudit,
    GeometryValidationError,
    SplineCurve,
    SplineParameters,
    comparator_frame_from_message,
    estimated_frame_from_message,
)
from .mcap_io import _source_time_ns
from .path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)

FloatArray = NDArray[np.float64]

DEFAULT_DEBUG_TOPIC = "/em/road/estimated_drive_paths_debug"
DEFAULT_DEBUG_SCHEMA = "estimated_drive_paths_debug_msgs/EstimatedDrivePathsDebug"
DEFAULT_RESIDUAL_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))

DEBUG_KEEP_LANE_VALUE = 1
DEBUG_NO_ERROR_VALUE = 7

_DEBUG_ERROR_SUFFIX_BY_VALUE = {
    0: "UNINITIALIZED",
    1: "CROSSES_ITSELF",
    2: "SEGMENT_BENDS_TOO_STRONG",
    3: "HIGH_CHI_2_FOR_ENTIRE_GRAPH",
    4: "HIGH_CHI_2_FOR_MINIMAL_DISTANCE",
    5: "HIGH_CHI_2_FOR_KEEP_DISTANCE",
    6: "OPTIMIZER_ERROR",
    7: "NO_ERROR",
    8: "NEGATIVE_SEGMENT_LENGTH_ERROR",
    9: "HIGH_CHI_2_FOR_MINIMAL_DISTANCE_FROM_OBSTACLE",
    10: "DRIVEN_DISTANCE_TOO_FAR_SINCE_LAST_UPDATE",
    11: "LATERAL_DISTANCE_TOO_HIGH",
    12: "TOO_HIGH_SEGMENT_LENGTH",
    13: "EGO_PROJECTION_FAILED",
}


@dataclass(frozen=True)
class DebugSplineParameters:
    """Internal same-estimator debug parameters; never serialize directly."""

    x_0: float = field(repr=False)
    y_0: float = field(repr=False)
    theta_0: float = field(repr=False)
    curvature_0: float = field(repr=False)
    segment_length: FloatArray = field(repr=False)
    curvature_change: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        scalars = np.asarray(
            (self.x_0, self.y_0, self.theta_0, self.curvature_0),
            dtype=np.float64,
        )
        lengths = np.asarray(self.segment_length, dtype=np.float64)
        changes = np.asarray(self.curvature_change, dtype=np.float64)
        if not np.all(np.isfinite(scalars)):
            raise GeometryValidationError(
                "debug_non_finite_initial_parameters",
                "debug initial pose and curvature must be finite",
            )
        if lengths.ndim != 1 or len(lengths) < 1:
            raise GeometryValidationError(
                "debug_segment_lengths_empty",
                "debug segment_length must contain at least one interval",
            )
        if not np.all(np.isfinite(lengths)) or not np.all(lengths > 0.0):
            raise GeometryValidationError(
                "debug_segment_lengths_invalid",
                "debug segment lengths must be finite and positive",
            )
        if changes.ndim != 1 or len(changes) != len(lengths):
            raise GeometryValidationError(
                "debug_interval_count_mismatch",
                "debug curvature_change count must equal segment_length count",
            )
        if not np.all(np.isfinite(changes)):
            raise GeometryValidationError(
                "debug_curvature_change_non_finite",
                "debug curvature_change values must be finite",
            )
        object.__setattr__(self, "segment_length", lengths)
        object.__setattr__(self, "curvature_change", changes)

    @property
    def interval_count(self) -> int:
        return len(self.segment_length)


@dataclass(frozen=True)
class DebugFrameAudit:
    """One decoded debug message and its strict keep-lane selection state."""

    message_index: int
    log_time_ns: int
    publish_time_ns: int
    source_time_ns: int | None
    state: str
    keep_lane_count: int
    keep_lane_error_value: int | None
    schema_fingerprint: str | None
    payload_fingerprint: str | None = field(default=None, repr=False)
    parameters: DebugSplineParameters | None = field(default=None, repr=False)

    @property
    def ready(self) -> bool:
        return self.state == "debug_ready" and self.parameters is not None


@dataclass(frozen=True)
class DebugSemanticAudit:
    """Frame-local evidence that production and debug parameters agree."""

    status: str
    failure_code: str | None
    initial_parameter_count: int
    interval_count: int | None
    maximum_initial_abs_difference: float | None
    maximum_segment_length_abs_difference: float | None
    maximum_curvature_change_abs_difference: float | None
    segment_lengths_match: bool
    curvature_changes_match: bool
    initial_parameters_match: bool

    @property
    def passed(self) -> bool:
        return self.status == "semantic_match"


@dataclass(frozen=True)
class ResidualFrame:
    """One complete fixed-station residual vector and QA diagnostics."""

    stations_m: FloatArray = field(repr=False)
    lateral_m: FloatArray = field(repr=False)
    along_track_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)
    curvature_per_m: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        arrays = [
            np.asarray(value, dtype=np.float64)
            for value in (
                self.stations_m,
                self.lateral_m,
                self.along_track_m,
                self.heading_rad,
                self.curvature_per_m,
            )
        ]
        if len(arrays[0]) < 1 or len({len(value) for value in arrays}) != 1:
            raise GeometryValidationError(
                "residual_array_count_mismatch",
                "all residual arrays must have the same nonzero length",
            )
        if not all(value.ndim == 1 and np.all(np.isfinite(value)) for value in arrays):
            raise GeometryValidationError(
                "residual_arrays_invalid",
                "residual arrays must be finite vectors",
            )
        if len(arrays[0]) > 1 and not np.all(np.diff(arrays[0]) > 0.0):
            raise GeometryValidationError(
                "residual_stations_not_increasing",
                "residual stations must be strictly increasing",
            )
        for name, value in zip(
            (
                "stations_m",
                "lateral_m",
                "along_track_m",
                "heading_rad",
                "curvature_per_m",
            ),
            arrays,
        ):
            value.setflags(write=False)
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class DecodedResidualRecording:
    """Withdrawn three-stream container retained for backward compatibility."""

    estimated_frames: tuple[EstimatedFrameAudit, ...]
    ground_truth_frames: tuple[ComparatorFrameAudit, ...]
    debug_frames: tuple[DebugFrameAudit, ...]
    estimate_schema_fingerprints: tuple[str, ...]
    ground_truth_schema_fingerprints: tuple[str, ...]
    debug_schema_fingerprints: tuple[str, ...]
    scan_complete: bool


def production_error_matches_debug(
    production_symbol: str | None,
    debug_value: int | None,
) -> bool:
    """Compare production/debug error semantics without trusting enum numbers."""

    if production_symbol is None or debug_value is None:
        return False
    suffix = _DEBUG_ERROR_SUFFIX_BY_VALUE.get(int(debug_value))
    if suffix is None:
        return False
    normalized = str(production_symbol).upper()
    return normalized == suffix or normalized.endswith(f"_{suffix}")


_MISSING = object()


def _member(value: Any, names: Sequence[str], *, default: Any = _MISSING) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    if default is _MISSING:
        raise GeometryValidationError(
            "debug_field_missing",
            f"debug message is missing required field: {'/'.join(names)}",
        )
    return default


def _sequence(value: Any, names: Sequence[str]) -> tuple[Any, ...]:
    raw = _member(value, names, default=None)
    if raw is None or isinstance(raw, (str, bytes, bytearray, Mapping)):
        raise GeometryValidationError(
            "debug_repeated_field_unavailable",
            f"debug repeated field is unavailable: {'/'.join(names)}",
        )
    try:
        return tuple(raw)
    except TypeError as error:
        raise GeometryValidationError(
            "debug_repeated_field_unreadable",
            f"debug repeated field is unreadable: {'/'.join(names)}",
        ) from error


def _finite_float(value: Any, name: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GeometryValidationError(
            "debug_numeric_field_unreadable",
            f"debug field {name} is not numeric",
        ) from error
    if not math.isfinite(converted):
        raise GeometryValidationError(
            "debug_numeric_field_non_finite",
            f"debug field {name} is not finite",
        )
    return converted


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise GeometryValidationError(
            "debug_integer_field_unreadable",
            f"debug field {name} is not an integer",
        )
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GeometryValidationError(
            "debug_integer_field_unreadable",
            f"debug field {name} is not an integer",
        ) from error


def _nested_integer(value: Any, outer_names: Sequence[str], inner_names: Sequence[str], name: str) -> int:
    outer = _member(value, outer_names)
    return _integer(_member(outer, inner_names), name)


def _debug_parameters(vertex: Any) -> DebugSplineParameters:
    estimate = _member(vertex, ("estimate", "estimate_"))
    lengths = _sequence(estimate, ("segment_length", "segment_length_"))
    changes = _sequence(estimate, ("curvature_change", "curvature_change_"))
    return DebugSplineParameters(
        x_0=_finite_float(_member(estimate, ("x_0",)), "x_0"),
        y_0=_finite_float(_member(estimate, ("y_0",)), "y_0"),
        theta_0=_finite_float(_member(estimate, ("theta_0",)), "theta_0"),
        curvature_0=_finite_float(
            _member(estimate, ("curvature_0",)),
            "curvature_0",
        ),
        segment_length=np.asarray(
            [_finite_float(item, "segment_length") for item in lengths],
            dtype=np.float64,
        ),
        curvature_change=np.asarray(
            [_finite_float(item, "curvature_change") for item in changes],
            dtype=np.float64,
        ),
    )


def debug_frame_from_message(
    message: Any,
    *,
    message_index: int,
    log_time_ns: int,
    publish_time_ns: int,
    schema_fingerprint: str | None = None,
    payload_fingerprint: str | None = None,
) -> DebugFrameAudit:
    """Select exactly one no-error keep-lane debug estimate."""

    source_time_ns = _source_time_ns(message)
    try:
        vertices = _sequence(message, ("vertices", "vertices_"))
    except GeometryValidationError as error:
        return DebugFrameAudit(
            message_index=message_index,
            log_time_ns=int(log_time_ns),
            publish_time_ns=int(publish_time_ns),
            source_time_ns=source_time_ns,
            state=error.code,
            keep_lane_count=0,
            keep_lane_error_value=None,
            schema_fingerprint=schema_fingerprint,
            payload_fingerprint=payload_fingerprint,
        )

    keep_lane: list[tuple[Any, int | None]] = []
    for vertex in vertices:
        try:
            role = _nested_integer(
                vertex,
                ("role", "role_"),
                ("value", "value_"),
                "role.value",
            )
        except GeometryValidationError:
            continue
        if role != DEBUG_KEEP_LANE_VALUE:
            continue
        try:
            error_value = _nested_integer(
                vertex,
                ("drive_path_error", "drive_path_error_"),
                ("error", "error_"),
                "drive_path_error.error",
            )
        except GeometryValidationError:
            error_value = None
        keep_lane.append((vertex, error_value))

    if not keep_lane:
        state = "debug_keep_lane_missing"
        error_value = None
    elif len(keep_lane) > 1:
        state = "debug_keep_lane_ambiguous"
        error_value = None
    else:
        error_value = keep_lane[0][1]
        if error_value is None:
            state = "debug_estimator_status_unavailable"
        elif error_value != DEBUG_NO_ERROR_VALUE:
            state = "debug_estimator_reported_error"
        elif source_time_ns is None:
            state = "debug_source_timestamp_missing"
        else:
            try:
                parameters = _debug_parameters(keep_lane[0][0])
            except GeometryValidationError as error:
                state = error.code
            else:
                return DebugFrameAudit(
                    message_index=message_index,
                    log_time_ns=int(log_time_ns),
                    publish_time_ns=int(publish_time_ns),
                    source_time_ns=source_time_ns,
                    state="debug_ready",
                    keep_lane_count=1,
                    keep_lane_error_value=error_value,
                    schema_fingerprint=schema_fingerprint,
                    payload_fingerprint=payload_fingerprint,
                    parameters=parameters,
                )

    return DebugFrameAudit(
        message_index=message_index,
        log_time_ns=int(log_time_ns),
        publish_time_ns=int(publish_time_ns),
        source_time_ns=source_time_ns,
        state=state,
        keep_lane_count=len(keep_lane),
        keep_lane_error_value=error_value,
        schema_fingerprint=schema_fingerprint,
        payload_fingerprint=payload_fingerprint,
    )


def compare_production_to_debug(
    production: SplineParameters,
    debug: DebugSplineParameters,
    *,
    absolute_tolerance: float = 1e-5,
    relative_tolerance: float = 1e-5,
) -> DebugSemanticAudit:
    """Verify the exact production-to-debug parameter correspondence."""

    if not math.isfinite(absolute_tolerance) or absolute_tolerance < 0.0:
        raise ValueError("absolute_tolerance must be finite and nonnegative")
    if not math.isfinite(relative_tolerance) or relative_tolerance < 0.0:
        raise ValueError("relative_tolerance must be finite and nonnegative")

    production_lengths = np.diff(production.segment_starts)
    if len(production_lengths) != debug.interval_count:
        return DebugSemanticAudit(
            status="semantic_mismatch",
            failure_code="debug_interval_count_mismatch",
            initial_parameter_count=4,
            interval_count=None,
            maximum_initial_abs_difference=None,
            maximum_segment_length_abs_difference=None,
            maximum_curvature_change_abs_difference=None,
            segment_lengths_match=False,
            curvature_changes_match=False,
            initial_parameters_match=False,
        )

    production_initial = np.asarray(
        (
            production.x_0,
            production.y_0,
            production.theta_0,
            production.curvature_0,
        ),
        dtype=np.float64,
    )
    debug_initial = np.asarray(
        (debug.x_0, debug.y_0, debug.theta_0, debug.curvature_0),
        dtype=np.float64,
    )
    initial_difference = np.abs(production_initial - debug_initial)
    length_difference = np.abs(production_lengths - debug.segment_length)
    change_difference = np.abs(production.curvature_change - debug.curvature_change)
    initial_match = bool(
        np.allclose(
            production_initial,
            debug_initial,
            atol=absolute_tolerance,
            rtol=relative_tolerance,
        )
    )
    length_match = bool(
        np.allclose(
            production_lengths,
            debug.segment_length,
            atol=absolute_tolerance,
            rtol=relative_tolerance,
        )
    )
    change_match = bool(
        np.allclose(
            production.curvature_change,
            debug.curvature_change,
            atol=absolute_tolerance,
            rtol=relative_tolerance,
        )
    )
    passed = initial_match and length_match and change_match
    if passed:
        failure_code = None
    elif not initial_match:
        failure_code = "debug_initial_parameters_mismatch"
    elif not length_match:
        failure_code = "debug_segment_lengths_mismatch"
    else:
        failure_code = "debug_curvature_changes_mismatch"
    return DebugSemanticAudit(
        status="semantic_match" if passed else "semantic_mismatch",
        failure_code=failure_code,
        initial_parameter_count=4,
        interval_count=debug.interval_count,
        maximum_initial_abs_difference=float(np.max(initial_difference)),
        maximum_segment_length_abs_difference=float(np.max(length_difference)),
        maximum_curvature_change_abs_difference=float(np.max(change_difference)),
        segment_lengths_match=length_match,
        curvature_changes_match=change_match,
        initial_parameters_match=initial_match,
    )


def _wrap_angle(values: FloatArray) -> FloatArray:
    return (values + np.pi) % (2.0 * np.pi) - np.pi


def compute_provisional_gt_residual(
    estimate: SplineCurve,
    ground_truth: Any,
    *,
    stations_m: Sequence[float] = DEFAULT_RESIDUAL_STATIONS_M,
    domain_tolerance_m: float = 1e-9,
) -> ResidualFrame:
    """Compute signed same-station discrepancy without extrapolation.

    This is a legacy synthetic-test helper, not the active real-MCAP workflow.
    The displacement is ``estimate - reference_candidate``.  Its lateral
    component is positive along ``(-sin(theta_ref), cos(theta_ref))``.  A caller
    must not call the result lane-estimation error unless the reference has
    independently passed the v0.3.9 reference-candidate gate.
    """

    stations = np.asarray(stations_m, dtype=np.float64)
    if stations.ndim != 1 or len(stations) < 1 or not np.all(np.isfinite(stations)):
        raise GeometryValidationError(
            "residual_stations_invalid",
            "residual stations must be a finite nonempty vector",
        )
    if len(stations) > 1 and not np.all(np.diff(stations) > 0.0):
        raise GeometryValidationError(
            "residual_stations_not_increasing",
            "residual stations must be strictly increasing",
        )
    if not math.isfinite(domain_tolerance_m) or domain_tolerance_m < 0.0:
        raise ValueError("domain_tolerance_m must be finite and nonnegative")

    estimate_lower, estimate_upper = float(estimate.s[0]), float(estimate.s[-1])
    gt_lower, gt_upper = float(ground_truth.s[0]), float(ground_truth.s[-1])
    lower, upper = float(stations[0]), float(stations[-1])
    if lower < estimate_lower - domain_tolerance_m or upper > estimate_upper + domain_tolerance_m:
        raise GeometryValidationError(
            "estimate_station_coverage_incomplete",
            "estimate domain does not cover every requested station",
        )
    if lower < gt_lower - domain_tolerance_m or upper > gt_upper + domain_tolerance_m:
        raise GeometryValidationError(
            "ground_truth_station_coverage_incomplete",
            "provisional ground-truth domain does not cover every requested station",
        )

    estimate_x = np.interp(stations, estimate.s, estimate.x)
    estimate_y = np.interp(stations, estimate.s, estimate.y)
    estimate_heading = np.interp(stations, estimate.s, np.unwrap(estimate.heading))
    estimate_curvature = np.interp(stations, estimate.s, estimate.curvature)
    gt_x = np.interp(stations, ground_truth.s, ground_truth.x)
    gt_y = np.interp(stations, ground_truth.s, ground_truth.y)
    gt_heading = np.interp(stations, ground_truth.s, np.unwrap(ground_truth.heading))
    gt_curvature = np.interp(stations, ground_truth.s, ground_truth.curvature)
    difference = np.column_stack((estimate_x - gt_x, estimate_y - gt_y))
    tangent = np.column_stack((np.cos(gt_heading), np.sin(gt_heading)))
    normal = np.column_stack((-np.sin(gt_heading), np.cos(gt_heading)))
    return ResidualFrame(
        stations_m=stations,
        lateral_m=np.einsum("ij,ij->i", normal, difference),
        along_track_m=np.einsum("ij,ij->i", tangent, difference),
        heading_rad=_wrap_angle(estimate_heading - gt_heading),
        curvature_per_m=estimate_curvature - gt_curvature,
    )


def _schema_fingerprint(schema: Any, decoded: Any | None = None) -> str | None:
    raw = getattr(schema, "data", None)
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return hashlib.sha256(bytes(raw)).hexdigest()
    descriptor = getattr(decoded, "DESCRIPTOR", None)
    serialized = getattr(getattr(descriptor, "file", None), "serialized_pb", None)
    if isinstance(serialized, bytes):
        return hashlib.sha256(serialized).hexdigest()
    return None


def _raw_payload_fingerprint(message: Any) -> str | None:
    payload = getattr(message, "data", None)
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        return None
    return hashlib.sha256(bytes(payload)).hexdigest()


def decode_residual_recording_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    max_messages_per_topic: int | None = None,
) -> DecodedResidualRecording:
    """Reject the withdrawn fused-ego-lane provisional-GT decoder."""

    raise GeometryValidationError(
        "withdrawn_provisional_gt_decoder",
        "use reference_audit_cli; fused ego_lane_path is not ground truth",
    )

    if max_messages_per_topic is not None and max_messages_per_topic < 1:
        raise ValueError("max_messages_per_topic must be positive or None")
    estimates: list[EstimatedFrameAudit] = []
    ground_truth: list[ComparatorFrameAudit] = []
    debug: list[DebugFrameAudit] = []
    fingerprints: dict[str, set[str]] = {
        "estimate": set(),
        "ground_truth": set(),
        "debug": set(),
    }
    limited = False
    topics = {
        DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
        DEFAULT_COMPARATOR_TOPIC,
        DEFAULT_DEBUG_TOPIC,
    }
    for schema, channel, mcap_message, decoded in decoded_messages:
        topic = str(getattr(channel, "topic", ""))
        if topic not in topics:
            continue
        fingerprint = _schema_fingerprint(schema, decoded)
        payload_fingerprint = _raw_payload_fingerprint(mcap_message)
        current_schema = str(getattr(schema, "name", ""))
        encoding = str(getattr(channel, "message_encoding", "")).lower()
        log_time = int(getattr(mcap_message, "log_time", 0))
        publish_time = int(getattr(mcap_message, "publish_time", 0))
        if topic == DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC:
            if max_messages_per_topic is not None and len(estimates) >= max_messages_per_topic:
                limited = True
                continue
            if current_schema != DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA or encoding != "protobuf":
                raise GeometryValidationError(
                    "estimate_schema_or_encoding_mismatch",
                    f"unexpected estimate schema/encoding: {current_schema}/{encoding}",
                )
            if fingerprint is not None:
                fingerprints["estimate"].add(fingerprint)
            estimates.append(
                estimated_frame_from_message(
                    decoded,
                    message_index=len(estimates),
                    log_time_ns=log_time,
                    publish_time_ns=publish_time,
                    schema_fingerprint=fingerprint,
                    payload_fingerprint=payload_fingerprint,
                )
            )
        elif topic == DEFAULT_COMPARATOR_TOPIC:
            if max_messages_per_topic is not None and len(ground_truth) >= max_messages_per_topic:
                limited = True
                continue
            if current_schema != DEFAULT_COMPARATOR_SCHEMA or encoding != "ros1":
                raise GeometryValidationError(
                    "ground_truth_schema_or_encoding_mismatch",
                    f"unexpected provisional-GT schema/encoding: {current_schema}/{encoding}",
                )
            if fingerprint is not None:
                fingerprints["ground_truth"].add(fingerprint)
            ground_truth.append(
                comparator_frame_from_message(
                    decoded,
                    message_index=len(ground_truth),
                    log_time_ns=log_time,
                    publish_time_ns=publish_time,
                    topic=DEFAULT_COMPARATOR_TOPIC,
                    schema_name=DEFAULT_COMPARATOR_SCHEMA,
                    payload_fingerprint=payload_fingerprint,
                )
            )
        else:
            if max_messages_per_topic is not None and len(debug) >= max_messages_per_topic:
                limited = True
                continue
            if current_schema != DEFAULT_DEBUG_SCHEMA or encoding != "ros1":
                raise GeometryValidationError(
                    "debug_schema_or_encoding_mismatch",
                    f"unexpected debug schema/encoding: {current_schema}/{encoding}",
                )
            if fingerprint is not None:
                fingerprints["debug"].add(fingerprint)
            debug.append(
                debug_frame_from_message(
                    decoded,
                    message_index=len(debug),
                    log_time_ns=log_time,
                    publish_time_ns=publish_time,
                    schema_fingerprint=fingerprint,
                    payload_fingerprint=payload_fingerprint,
                )
            )
    return DecodedResidualRecording(
        estimated_frames=tuple(estimates),
        ground_truth_frames=tuple(ground_truth),
        debug_frames=tuple(debug),
        estimate_schema_fingerprints=tuple(sorted(fingerprints["estimate"])),
        ground_truth_schema_fingerprints=tuple(sorted(fingerprints["ground_truth"])),
        debug_schema_fingerprints=tuple(sorted(fingerprints["debug"])),
        scan_complete=not limited,
    )
