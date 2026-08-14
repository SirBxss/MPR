"""Fail-closed semantic geometry validation for direct estimated paths.

This module deliberately does not create residual training data.  It keeps the
estimator state, conversion state, synchronization state, and comparator state
separate so that an estimator-reported failure cannot disappear through
filtering.  Geometry is generated only for exactly one metadata-confirmed
``KEEP_LANE + NO_ERROR`` path with a complete, finite spline structure.

The production field ``curvature_change`` has unresolved semantics.  Two
finite, explicitly named hypotheses are evaluated:

``curvature_rate__anchor_zero``
    Each value is the curvature derivative on its interval.

``curvature_delta__anchor_zero``
    Each value is the total curvature change over its interval.

Both assume that ``segment_starts`` are spline boundaries and that the initial
state is located at station zero.  An ``index_0`` anchor is available only when
the field is explicitly present; an implicit Protobuf default is not evidence
for its domain meaning.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from ..mcap_io import RoadMessageError, RoadSegment, road_frame_from_message
from .path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    _FIELD_VALUE_MISSING,
    _audit_one_path,
    _effective_enum_symbol,
    _effective_field_value,
    _joint_audit_bindings,
    _repeated_values,
)
from ..preprocessing import project_points_to_polyline

FloatArray = NDArray[np.float64]

DEFAULT_COMPARATOR_TOPIC = "/em/road/ego_lane_path"
DEFAULT_COMPARATOR_SCHEMA = "road_msgs/Road"
EXPECTED_TOPOLOGY_SOURCE = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"

CurvatureMeaning = Literal["curvature_rate", "curvature_delta"]
AnchorPolicy = Literal["anchor_zero", "explicit_index_anchor"]


class GeometryValidationError(ValueError):
    """Fail-closed validation failure with a stable code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class SplineParameters:
    """Internal numeric spline parameters; never serialize this object."""

    x_0: float = field(repr=False)
    y_0: float = field(repr=False)
    theta_0: float = field(repr=False)
    curvature_0: float = field(repr=False)
    segment_starts: FloatArray = field(repr=False)
    curvature_change: FloatArray = field(repr=False)
    index_0: int = field(repr=False)
    index_0_presence_evidence: str
    index_0_explicitly_present: bool

    def __post_init__(self) -> None:
        scalars = np.asarray(
            (self.x_0, self.y_0, self.theta_0, self.curvature_0),
            dtype=np.float64,
        )
        starts = np.asarray(self.segment_starts, dtype=np.float64)
        changes = np.asarray(self.curvature_change, dtype=np.float64)
        if not np.all(np.isfinite(scalars)):
            raise GeometryValidationError(
                "non_finite_initial_parameters",
                "initial pose and curvature must be finite",
            )
        if starts.ndim != 1 or len(starts) < 2:
            raise GeometryValidationError(
                "segment_starts_too_short",
                "segment_starts must contain at least two boundaries",
            )
        if not np.all(np.isfinite(starts)):
            raise GeometryValidationError(
                "non_finite_segment_starts",
                "segment_starts must be finite",
            )
        if not np.all(np.diff(starts) > 0.0):
            raise GeometryValidationError(
                "non_increasing_segment_starts",
                "segment_starts must be strictly increasing",
            )
        if changes.ndim != 1 or len(changes) != len(starts) - 1:
            raise GeometryValidationError(
                "interval_count_mismatch",
                "curvature_change count must equal boundary count minus one",
            )
        if not np.all(np.isfinite(changes)):
            raise GeometryValidationError(
                "non_finite_curvature_change",
                "curvature_change must be finite",
            )
        if isinstance(self.index_0, bool) or not isinstance(
            self.index_0,
            (int, np.integer),
        ):
            raise GeometryValidationError(
                "index_anchor_not_integer",
                "index_0 must be an integer",
            )
        if int(self.index_0) < 0 or int(self.index_0) >= len(starts):
            raise GeometryValidationError(
                "index_anchor_out_of_range",
                "index_0 must reference one supplied boundary",
            )
        object.__setattr__(self, "segment_starts", starts)
        object.__setattr__(self, "curvature_change", changes)
        object.__setattr__(self, "index_0", int(self.index_0))

    @property
    def interval_count(self) -> int:
        return len(self.curvature_change)


@dataclass(frozen=True)
class EstimatedFrameAudit:
    """One pre-synchronization row for every decoded estimate message."""

    message_index: int
    log_time_ns: int
    publish_time_ns: int
    source_time_ns: int | None
    schema_fingerprint: str | None
    topology_source: str
    total_path_count: int
    keep_lane_count: int
    keep_lane_error: str | None
    estimator_state: str
    conversion_state: str
    interval_count: int | None
    payload_fingerprint: str | None = field(default=None, repr=False)
    candidate: SplineParameters | None = field(default=None, repr=False)

    @property
    def candidate_ready(self) -> bool:
        return self.conversion_state == "candidate_ready" and self.candidate is not None


@dataclass(frozen=True)
class ComparatorGeometry:
    """Internal comparator geometry at native road-message stations."""

    s: FloatArray = field(repr=False)
    x: FloatArray = field(repr=False)
    y: FloatArray = field(repr=False)
    heading: FloatArray = field(repr=False)
    curvature: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        arrays = [
            np.asarray(value, dtype=np.float64)
            for value in (self.s, self.x, self.y, self.heading, self.curvature)
        ]
        if any(array.ndim != 1 for array in arrays):
            raise GeometryValidationError(
                "comparator_arrays_not_vectors",
                "comparator arrays must be one-dimensional",
            )
        if len(arrays[0]) < 2 or len({len(array) for array in arrays}) != 1:
            raise GeometryValidationError(
                "comparator_array_count_mismatch",
                "comparator arrays must have equal length of at least two",
            )
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise GeometryValidationError(
                "comparator_non_finite",
                "comparator arrays must be finite",
            )
        if not np.all(np.diff(arrays[0]) > 0.0):
            raise GeometryValidationError(
                "comparator_stations_not_increasing",
                "comparator stations must be strictly increasing",
            )
        if not arrays[0][0] <= 0.0 <= arrays[0][-1]:
            raise GeometryValidationError(
                "comparator_zero_outside_domain",
                "comparator native station domain must contain zero",
            )
        for name, array in zip(
            ("s", "x", "y", "heading", "curvature"),
            arrays,
        ):
            object.__setattr__(self, name, array)

    @property
    def points(self) -> FloatArray:
        return np.column_stack((self.x, self.y))


@dataclass(frozen=True)
class ComparatorFrameAudit:
    """One decoded comparator message, including unusable geometry."""

    message_index: int
    log_time_ns: int
    publish_time_ns: int
    source_time_ns: int | None
    state: str
    payload_fingerprint: str | None = field(default=None, repr=False)
    geometry: ComparatorGeometry | None = field(default=None, repr=False)


@dataclass(frozen=True)
class SplineCurve:
    """A curve generated under one explicit semantic hypothesis."""

    hypothesis: str
    curvature_meaning: CurvatureMeaning
    anchor_policy: AnchorPolicy
    s: FloatArray = field(repr=False)
    x: FloatArray = field(repr=False)
    y: FloatArray = field(repr=False)
    heading: FloatArray = field(repr=False)
    curvature: FloatArray = field(repr=False)
    curvature_rate: FloatArray = field(repr=False)
    maximum_quadrature_error_m: float
    convergence_position_error_m: float
    convergence_heading_error_rad: float
    sampled_arc_length_deficit_m: float
    invariant_status: str

    @property
    def points(self) -> FloatArray:
        return np.column_stack((self.x, self.y))


@dataclass(frozen=True)
class SynchronizationPair:
    """One monotone, one-to-one timestamp pair."""

    estimate_index: int
    comparator_index: int
    source_delta_ns: int
    log_delta_ns: int


@dataclass(frozen=True)
class SynchronizationAudit:
    """Maximum-cardinality, minimum-offset synchronization result."""

    pairs: tuple[SynchronizationPair, ...]
    unmatched_estimate_indices: tuple[int, ...]
    unmatched_comparator_indices: tuple[int, ...]
    ambiguous_estimate_indices: tuple[int, ...]
    ambiguous_comparator_indices: tuple[int, ...]


@dataclass(frozen=True)
class HypothesisMetrics:
    """Diagnostic discrepancies against a comparator, never ground truth."""

    hypothesis: str
    status: str
    failure_code: str | None
    common_coverage_m: float | None = None
    station_count: int | None = None
    lateral_rms_m: float | None = None
    lateral_median_abs_m: float | None = None
    lateral_p95_abs_m: float | None = None
    lateral_max_abs_m: float | None = None
    along_track_rms_m: float | None = None
    heading_rms_rad: float | None = None
    heading_p95_abs_rad: float | None = None
    curvature_rms_per_m: float | None = None
    endpoint_position_error_m: float | None = None
    initial_position_error_m: float | None = None
    initial_heading_error_rad: float | None = None
    initial_curvature_error_per_m: float | None = None
    symmetric_chamfer_m: float | None = None
    symmetric_hausdorff_m: float | None = None
    projection_monotonic_fraction: float | None = None
    maximum_abs_curvature_per_m: float | None = None
    maximum_abs_curvature_rate_per_m2: float | None = None
    self_intersection_detected: bool | None = None


@dataclass(frozen=True)
class DecodedRecording:
    """Decoded per-recording evidence before corpus aggregation."""

    estimated_frames: tuple[EstimatedFrameAudit, ...]
    comparator_frames: tuple[ComparatorFrameAudit, ...]
    estimate_schema_fingerprints: tuple[str, ...]
    comparator_schema_fingerprints: tuple[str, ...]
    scan_complete: bool


def _schema_fingerprint(schema: Any, decoded: Any | None = None) -> str | None:
    data = getattr(schema, "data", None)
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(bytes(data)).hexdigest()
    descriptor = getattr(decoded, "DESCRIPTOR", None)
    file_descriptor = getattr(descriptor, "file", None)
    serialized = getattr(file_descriptor, "serialized_pb", None)
    if isinstance(serialized, bytes):
        return hashlib.sha256(serialized).hexdigest()
    return None


def _payload_fingerprint(message: Any) -> str | None:
    serialize = getattr(message, "SerializeToString", None)
    if not callable(serialize):
        return None
    try:
        try:
            payload = serialize(deterministic=True)
        except TypeError:
            payload = serialize()
    except (TypeError, ValueError, NotImplementedError):
        return None
    return hashlib.sha256(bytes(payload)).hexdigest()


def _numeric_scalar(message: Any, field_descriptor: Any) -> float:
    value, present, evidence = _effective_field_value(message, field_descriptor)
    if value is _FIELD_VALUE_MISSING or evidence in {
        "explicit_absent",
        "schema_field_unavailable",
        "value_unavailable",
    }:
        raise GeometryValidationError(
            "initial_parameters_unavailable",
            f"required scalar {field_descriptor.name} is unavailable",
        )
    if not present and evidence != "implicit_default":
        raise GeometryValidationError(
            "initial_parameters_unavailable",
            f"presence of scalar {field_descriptor.name} is unconfirmed",
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GeometryValidationError(
            "initial_parameters_unreadable",
            f"scalar {field_descriptor.name} is not numeric",
        ) from error
    if not math.isfinite(number):
        raise GeometryValidationError(
            "non_finite_initial_parameters",
            f"scalar {field_descriptor.name} is not finite",
        )
    return number


def _spline_parameters_from_path(
    path_message: Any,
    *,
    bindings: Any,
) -> SplineParameters:
    model, model_present, evidence = _effective_field_value(
        path_message,
        bindings.model_parameters,
    )
    if (
        not model_present
        or model is _FIELD_VALUE_MISSING
        or model is None
        or evidence in {"explicit_absent", "value_unavailable"}
    ):
        raise GeometryValidationError(
            "model_parameters_absent",
            "model_parameters are not explicitly available",
        )
    starts = _repeated_values(model, bindings.segment_starts)
    changes = _repeated_values(model, bindings.curvature_change)
    if starts is None:
        raise GeometryValidationError(
            "segment_starts_unavailable",
            "segment_starts are unavailable",
        )
    if changes is None:
        raise GeometryValidationError(
            "curvature_change_unavailable",
            "curvature_change values are unavailable",
        )
    index_value, index_present, index_evidence = _effective_field_value(
        model,
        bindings.index_0,
    )
    if index_value is _FIELD_VALUE_MISSING:
        raise GeometryValidationError(
            "index_anchor_unavailable",
            "index_0 accessor is unavailable",
        )
    try:
        index = int(index_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GeometryValidationError(
            "index_anchor_not_integer",
            "index_0 is not an integer",
        ) from error
    return SplineParameters(
        x_0=_numeric_scalar(model, bindings.x_0),
        y_0=_numeric_scalar(model, bindings.y_0),
        theta_0=_numeric_scalar(model, bindings.theta_0),
        curvature_0=_numeric_scalar(model, bindings.curvature_0),
        segment_starts=np.asarray(starts, dtype=np.float64),
        curvature_change=np.asarray(changes, dtype=np.float64),
        index_0=index,
        index_0_presence_evidence=index_evidence,
        index_0_explicitly_present=bool(index_present),
    )


def estimated_frame_from_message(
    message: Any,
    *,
    message_index: int,
    log_time_ns: int,
    publish_time_ns: int,
    schema_fingerprint: str | None = None,
    payload_fingerprint: str | None = None,
) -> EstimatedFrameAudit:
    """Extract one estimate message without substituting another lane."""

    descriptor = getattr(message, "DESCRIPTOR", None)
    if descriptor is None:
        raise GeometryValidationError(
            "estimate_descriptor_missing",
            "estimated path message has no Protobuf descriptor",
        )
    bindings = _joint_audit_bindings(descriptor)
    missing = bindings.missing_required()
    source_time_ns = _source_time(message)
    topology_source = "UNAVAILABLE_ENUM_VALUE"
    if bindings.topology_source is not None:
        topology_source, _ = _effective_enum_symbol(
            message,
            bindings.topology_source,
        )
    path_values = _repeated_values(message, bindings.drive_paths) or []
    path_audits = [
        _audit_one_path(
            path,
            message_index=message_index,
            path_index=path_index,
            bindings=bindings,
        )
        for path_index, path in enumerate(path_values)
    ]
    keep_lane = [item for item in path_audits if item.is_keep_lane]
    keep_lane_error = keep_lane[0].error_symbol if len(keep_lane) == 1 else None

    if not keep_lane:
        estimator_state = "keep_lane_missing"
    elif len(keep_lane) > 1:
        estimator_state = "keep_lane_ambiguous"
    elif keep_lane[0].error_symbol in {
        "UNAVAILABLE_ENUM_VALUE",
        "UNKNOWN_ENUM_VALUE",
    }:
        estimator_state = "estimator_status_unavailable"
    elif not keep_lane[0].is_no_error:
        estimator_state = "estimator_reported_error"
    else:
        estimator_state = "available_no_error"

    candidate: SplineParameters | None = None
    interval_count: int | None = (
        keep_lane[0].curvature_change_count if len(keep_lane) == 1 else None
    )
    if estimator_state != "available_no_error":
        conversion_state = "not_attempted_estimator_unavailable"
    elif missing:
        conversion_state = "schema_bindings_incomplete"
    elif source_time_ns is None:
        conversion_state = "source_timestamp_missing"
    elif topology_source != EXPECTED_TOPOLOGY_SOURCE:
        conversion_state = "unexpected_topology_source"
    elif not keep_lane[0].model_structure_valid:
        conversion_state = "model_structure_invalid"
    elif keep_lane[0].model_parameters_optional_flag_value is not True:
        conversion_state = "model_flag_not_true"
    else:
        selected_path = path_values[keep_lane[0].path_index]
        try:
            candidate = _spline_parameters_from_path(
                selected_path,
                bindings=bindings,
            )
        except GeometryValidationError as error:
            conversion_state = error.code
        else:
            conversion_state = "candidate_ready"
            interval_count = candidate.interval_count

    return EstimatedFrameAudit(
        message_index=message_index,
        log_time_ns=int(log_time_ns),
        publish_time_ns=int(publish_time_ns),
        source_time_ns=source_time_ns,
        schema_fingerprint=schema_fingerprint,
        topology_source=topology_source,
        total_path_count=len(path_values),
        keep_lane_count=len(keep_lane),
        keep_lane_error=keep_lane_error,
        estimator_state=estimator_state,
        conversion_state=conversion_state,
        interval_count=interval_count,
        payload_fingerprint=payload_fingerprint or _payload_fingerprint(message),
        candidate=candidate,
    )


def _source_time(message: Any) -> int | None:
    # Local import avoids making a private helper part of the public API while
    # keeping timestamp semantics identical across the package.
    from ..mcap_io import _source_time_ns

    return _source_time_ns(message)


def _strict_comparator_geometry(message: Any, *, topic: str, schema_name: str,
                                log_time_ns: int, publish_time_ns: int,
                                sequence: int) -> ComparatorGeometry:
    qualifier_object = None
    for name in ("event_data_qualifier", "event_data_qualifier_"):
        if isinstance(message, Mapping) and name in message:
            qualifier_object = message[name]
            break
        if hasattr(message, name):
            qualifier_object = getattr(message, name)
            break
    if qualifier_object is not None:
        qualifier = None
        for name in ("qualifier", "qualifier_"):
            if isinstance(qualifier_object, Mapping) and name in qualifier_object:
                qualifier = qualifier_object[name]
                break
            if hasattr(qualifier_object, name):
                qualifier = getattr(qualifier_object, name)
                break
        if qualifier is not None:
            try:
                qualifier_value = int(qualifier)
            except (TypeError, ValueError, OverflowError) as error:
                raise GeometryValidationError(
                    "comparator_qualifier_unreadable",
                    "comparator availability qualifier is not an integer",
                ) from error
            if qualifier_value not in (0, 1):
                raise GeometryValidationError(
                    "comparator_reported_unavailable",
                    "comparator event qualifier reports unavailable or invalid data",
                )
    frame = road_frame_from_message(
        message,
        topic=topic,
        schema_name=schema_name,
        log_time_ns=log_time_ns,
        publish_time_ns=publish_time_ns,
        sequence=sequence,
    )
    ego_segments = [segment for segment in frame.segments if segment.is_ego is True]
    if len(ego_segments) != 1:
        raise GeometryValidationError(
            "comparator_ego_segment_not_unique",
            "comparator must expose exactly one metadata-confirmed ego segment",
        )
    segment: RoadSegment = ego_segments[0]
    if segment.geometry_source != "drive_path":
        raise GeometryValidationError(
            "comparator_not_direct_drive_path",
            "boundary-derived comparator geometry is not allowed",
        )
    if segment.heading is None or segment.curvature is None:
        raise GeometryValidationError(
            "comparator_differential_geometry_missing",
            "comparator heading and curvature must be available",
        )
    return ComparatorGeometry(
        s=np.asarray(segment.arc_length, dtype=np.float64),
        x=np.asarray(segment.x, dtype=np.float64),
        y=np.asarray(segment.y, dtype=np.float64),
        heading=np.asarray(segment.heading, dtype=np.float64),
        curvature=np.asarray(segment.curvature, dtype=np.float64),
    )


def comparator_frame_from_message(
    message: Any,
    *,
    message_index: int,
    log_time_ns: int,
    publish_time_ns: int,
    topic: str = DEFAULT_COMPARATOR_TOPIC,
    schema_name: str = DEFAULT_COMPARATOR_SCHEMA,
    payload_fingerprint: str | None = None,
) -> ComparatorFrameAudit:
    """Extract a strict metadata-confirmed direct comparator path."""

    source_time_ns = _source_time(message)
    if source_time_ns is None:
        return ComparatorFrameAudit(
            message_index=message_index,
            log_time_ns=int(log_time_ns),
            publish_time_ns=int(publish_time_ns),
            source_time_ns=None,
            state="source_timestamp_missing",
            payload_fingerprint=payload_fingerprint,
        )
    try:
        geometry = _strict_comparator_geometry(
            message,
            topic=topic,
            schema_name=schema_name,
            log_time_ns=log_time_ns,
            publish_time_ns=publish_time_ns,
            sequence=message_index,
        )
    except (RoadMessageError, GeometryValidationError) as error:
        code = getattr(error, "code", "comparator_road_message_invalid")
        return ComparatorFrameAudit(
            message_index=message_index,
            log_time_ns=int(log_time_ns),
            publish_time_ns=int(publish_time_ns),
            source_time_ns=source_time_ns,
            state=str(code),
            payload_fingerprint=payload_fingerprint,
        )
    return ComparatorFrameAudit(
        message_index=message_index,
        log_time_ns=int(log_time_ns),
        publish_time_ns=int(publish_time_ns),
        source_time_ns=source_time_ns,
        state="comparator_ready",
        payload_fingerprint=payload_fingerprint,
        geometry=geometry,
    )


def decode_recording_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    estimate_topic: str = DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    estimate_schema: str = DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    comparator_topic: str = DEFAULT_COMPARATOR_TOPIC,
    comparator_schema: str = DEFAULT_COMPARATOR_SCHEMA,
    max_messages_per_topic: int | None = None,
) -> DecodedRecording:
    """Decode both topics in one pass while preserving every estimate row."""

    if max_messages_per_topic is not None and max_messages_per_topic < 1:
        raise ValueError("max_messages_per_topic must be positive or None")
    estimated: list[EstimatedFrameAudit] = []
    comparator: list[ComparatorFrameAudit] = []
    estimate_hashes: set[str] = set()
    comparator_hashes: set[str] = set()
    limited = False

    def raw_payload_fingerprint(mcap_message: Any) -> str | None:
        payload = getattr(mcap_message, "data", None)
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            return None
        return hashlib.sha256(bytes(payload)).hexdigest()

    for schema, channel, mcap_message, decoded in decoded_messages:
        topic = str(getattr(channel, "topic", ""))
        if topic not in {estimate_topic, comparator_topic}:
            continue
        if topic == estimate_topic:
            if max_messages_per_topic is not None and len(estimated) >= max_messages_per_topic:
                limited = True
                continue
            current_schema = str(getattr(schema, "name", ""))
            encoding = str(getattr(channel, "message_encoding", "")).lower()
            if current_schema != estimate_schema or encoding != "protobuf":
                raise GeometryValidationError(
                    "estimate_schema_or_encoding_mismatch",
                    f"unexpected estimate schema/encoding: {current_schema}/{encoding}",
                )
            fingerprint = _schema_fingerprint(schema, decoded)
            if fingerprint is not None:
                estimate_hashes.add(fingerprint)
            estimated.append(
                estimated_frame_from_message(
                    decoded,
                    message_index=len(estimated),
                    log_time_ns=int(getattr(mcap_message, "log_time", 0)),
                    publish_time_ns=int(getattr(mcap_message, "publish_time", 0)),
                    schema_fingerprint=fingerprint,
                    payload_fingerprint=raw_payload_fingerprint(mcap_message),
                )
            )
        else:
            if max_messages_per_topic is not None and len(comparator) >= max_messages_per_topic:
                limited = True
                continue
            current_schema = str(getattr(schema, "name", ""))
            encoding = str(getattr(channel, "message_encoding", "")).lower()
            if current_schema != comparator_schema or encoding != "ros1":
                raise GeometryValidationError(
                    "comparator_schema_or_encoding_mismatch",
                    f"unexpected comparator schema/encoding: {current_schema}/{encoding}",
                )
            fingerprint = _schema_fingerprint(schema, decoded)
            if fingerprint is not None:
                comparator_hashes.add(fingerprint)
            comparator.append(
                comparator_frame_from_message(
                    decoded,
                    message_index=len(comparator),
                    log_time_ns=int(getattr(mcap_message, "log_time", 0)),
                    publish_time_ns=int(getattr(mcap_message, "publish_time", 0)),
                    topic=comparator_topic,
                    schema_name=comparator_schema,
                    payload_fingerprint=raw_payload_fingerprint(mcap_message),
                )
            )
    return DecodedRecording(
        estimated_frames=tuple(estimated),
        comparator_frames=tuple(comparator),
        estimate_schema_fingerprints=tuple(sorted(estimate_hashes)),
        comparator_schema_fingerprints=tuple(sorted(comparator_hashes)),
        scan_complete=not limited,
    )


def _curvature_rates(
    parameters: SplineParameters,
    meaning: CurvatureMeaning,
) -> FloatArray:
    if meaning == "curvature_rate":
        return parameters.curvature_change.copy()
    if meaning == "curvature_delta":
        return parameters.curvature_change / np.diff(parameters.segment_starts)
    raise ValueError(f"unsupported curvature meaning: {meaning}")


_LEGENDRE_CACHE: dict[int, tuple[FloatArray, FloatArray]] = {}


def _legendre(order: int) -> tuple[FloatArray, FloatArray]:
    cached = _LEGENDRE_CACHE.get(order)
    if cached is None:
        nodes, weights = np.polynomial.legendre.leggauss(order)
        cached = (
            np.asarray(nodes, dtype=np.float64),
            np.asarray(weights, dtype=np.float64),
        )
        _LEGENDRE_CACHE[order] = cached
    return cached


def _quadrature_displacement(
    theta: float,
    curvature: float,
    curvature_rate: float,
    distance: float,
    *,
    order: int,
) -> tuple[float, float]:
    nodes, weights = _legendre(order)
    half = 0.5 * distance
    station = half * (nodes + 1.0)
    angles = theta + curvature * station + 0.5 * curvature_rate * station**2
    return (
        float(half * np.dot(weights, np.cos(angles))),
        float(half * np.dot(weights, np.sin(angles))),
    )


def _advance_state(
    state: tuple[float, float, float, float],
    distance: float,
    curvature_rate: float,
    *,
    quadrature_tolerance_m: float,
    subdivision_depth: int = 0,
    maximum_subdivision_depth: int = 12,
) -> tuple[tuple[float, float, float, float], float]:
    x, y, theta, curvature = state
    if abs(curvature_rate) <= 1e-14:
        if abs(curvature) <= 1e-14:
            dx = distance * math.cos(theta)
            dy = distance * math.sin(theta)
        else:
            end_heading = theta + curvature * distance
            dx = (math.sin(end_heading) - math.sin(theta)) / curvature
            dy = -(math.cos(end_heading) - math.cos(theta)) / curvature
        error = 0.0
    else:
        dx8, dy8 = _quadrature_displacement(
            theta,
            curvature,
            curvature_rate,
            distance,
            order=8,
        )
        dx16, dy16 = _quadrature_displacement(
            theta,
            curvature,
            curvature_rate,
            distance,
            order=16,
        )
        error = math.hypot(dx16 - dx8, dy16 - dy8)
        if not math.isfinite(error):
            raise GeometryValidationError(
                "quadrature_not_converged",
                "8/16-point Gauss-Legendre displacement did not converge",
            )
        if error > quadrature_tolerance_m:
            if subdivision_depth >= maximum_subdivision_depth:
                raise GeometryValidationError(
                    "quadrature_not_converged",
                    "adaptive Gauss-Legendre subdivision limit was reached",
                )
            midpoint_state, first_error = _advance_state(
                state,
                0.5 * distance,
                curvature_rate,
                quadrature_tolerance_m=0.5 * quadrature_tolerance_m,
                subdivision_depth=subdivision_depth + 1,
                maximum_subdivision_depth=maximum_subdivision_depth,
            )
            final_state, second_error = _advance_state(
                midpoint_state,
                0.5 * distance,
                curvature_rate,
                quadrature_tolerance_m=0.5 * quadrature_tolerance_m,
                subdivision_depth=subdivision_depth + 1,
                maximum_subdivision_depth=maximum_subdivision_depth,
            )
            return final_state, max(first_error, second_error)
        dx, dy = dx16, dy16
    next_theta = theta + curvature * distance + 0.5 * curvature_rate * distance**2
    next_curvature = curvature + curvature_rate * distance
    result = (x + dx, y + dy, next_theta, next_curvature)
    if not all(math.isfinite(value) for value in result):
        raise GeometryValidationError(
            "generated_geometry_non_finite",
            "spline integration produced a non-finite state",
        )
    return result, error


def _sample_stations(
    boundaries: FloatArray,
    *,
    anchor: float,
    max_step_m: float,
    extra_stations: Sequence[float] = (),
    max_points: int,
) -> FloatArray:
    values: list[float] = [float(anchor), *map(float, boundaries)]
    for left, right in pairwise(boundaries):
        count = max(1, int(math.ceil((right - left) / max_step_m)))
        values.extend(np.linspace(left, right, count + 1).tolist())
    values.extend(
        float(value)
        for value in extra_stations
        if boundaries[0] <= float(value) <= boundaries[-1]
    )
    stations = np.unique(np.asarray(values, dtype=np.float64))
    if len(stations) > max_points:
        raise GeometryValidationError(
            "maximum_output_points_exceeded",
            f"spline sampling would create {len(stations)} points",
        )
    return stations


def _generate_once(
    parameters: SplineParameters,
    *,
    meaning: CurvatureMeaning,
    anchor_policy: AnchorPolicy,
    max_step_m: float,
    quadrature_tolerance_m: float,
    max_points: int,
    extra_stations: Sequence[float] = (),
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, float]:
    boundaries = parameters.segment_starts
    rates = _curvature_rates(parameters, meaning)
    if anchor_policy == "anchor_zero":
        anchor = 0.0
        if not boundaries[0] <= anchor <= boundaries[-1]:
            raise GeometryValidationError(
                "anchor_zero_outside_domain",
                "station zero is outside the supplied spline domain",
            )
    elif anchor_policy == "explicit_index_anchor":
        if not parameters.index_0_explicitly_present:
            raise GeometryValidationError(
                "index_anchor_not_explicit",
                "implicit Protobuf index_0 default is not semantic evidence",
            )
        anchor = float(boundaries[parameters.index_0])
    else:
        raise ValueError(f"unsupported anchor policy: {anchor_policy}")
    if not math.isfinite(max_step_m) or max_step_m <= 0.0:
        raise ValueError("max_step_m must be finite and positive")
    if not math.isfinite(quadrature_tolerance_m) or quadrature_tolerance_m <= 0.0:
        raise ValueError("quadrature_tolerance_m must be finite and positive")

    stations = _sample_stations(
        boundaries,
        anchor=anchor,
        max_step_m=max_step_m,
        extra_stations=extra_stations,
        max_points=max_points,
    )
    anchor_indices = np.flatnonzero(np.isclose(stations, anchor, atol=1e-12, rtol=0.0))
    if len(anchor_indices) != 1:
        raise GeometryValidationError(
            "anchor_sampling_ambiguous",
            "anchor station could not be represented uniquely",
        )
    anchor_index = int(anchor_indices[0])
    states = np.empty((len(stations), 4), dtype=np.float64)
    states[anchor_index] = (
        parameters.x_0,
        parameters.y_0,
        parameters.theta_0,
        parameters.curvature_0,
    )
    step_errors: list[float] = []

    def interval_rate(left: float, right: float) -> float:
        midpoint = 0.5 * (left + right)
        index = int(np.searchsorted(boundaries, midpoint, side="right") - 1)
        index = min(max(index, 0), len(rates) - 1)
        if not boundaries[index] - 1e-12 <= midpoint <= boundaries[index + 1] + 1e-12:
            raise GeometryValidationError(
                "sampling_crosses_unknown_interval",
                "sampling step does not belong to a supplied spline interval",
            )
        return float(rates[index])

    for index in range(anchor_index + 1, len(stations)):
        left, right = float(stations[index - 1]), float(stations[index])
        states[index], error = _advance_state(
            tuple(states[index - 1]),
            right - left,
            interval_rate(left, right),
            quadrature_tolerance_m=quadrature_tolerance_m,
        )
        step_errors.append(error)
    for index in range(anchor_index - 1, -1, -1):
        lower, upper = float(stations[index]), float(stations[index + 1])
        states[index], error = _advance_state(
            tuple(states[index + 1]),
            lower - upper,
            interval_rate(lower, upper),
            quadrature_tolerance_m=quadrature_tolerance_m,
        )
        step_errors.append(error)

    midpoint = 0.5 * (stations[:-1] + stations[1:])
    interval_indices = np.searchsorted(boundaries, midpoint, side="right") - 1
    interval_indices = np.clip(interval_indices, 0, len(rates) - 1)
    sampled_rates = np.empty(len(stations), dtype=np.float64)
    sampled_rates[:-1] = rates[interval_indices]
    sampled_rates[-1] = rates[-1]

    chords = np.hypot(np.diff(states[:, 0]), np.diff(states[:, 1]))
    support = np.diff(stations)
    if np.any(chords > support + 1e-8):
        raise GeometryValidationError(
            "chord_exceeds_arc_length",
            "generated chord length exceeds its station interval",
        )
    return (
        stations,
        states[:, 0],
        states[:, 1],
        states[:, 2],
        states[:, 3],
        sampled_rates,
        max(step_errors, default=0.0),
    )


def generate_spline_curve(
    parameters: SplineParameters,
    *,
    meaning: CurvatureMeaning,
    anchor_policy: AnchorPolicy = "anchor_zero",
    max_step_m: float = 0.25,
    quadrature_tolerance_m: float = 1e-9,
    convergence_position_tolerance_m: float = 1e-3,
    convergence_heading_tolerance_rad: float = 1e-4,
    max_points: int = 20_000,
    extra_stations: Sequence[float] = (),
) -> SplineCurve:
    """Generate and convergence-check one explicitly labelled hypothesis."""

    fine = _generate_once(
        parameters,
        meaning=meaning,
        anchor_policy=anchor_policy,
        max_step_m=max_step_m / 2.0,
        quadrature_tolerance_m=quadrature_tolerance_m,
        max_points=max_points,
        extra_stations=extra_stations,
    )
    coarse = _generate_once(
        parameters,
        meaning=meaning,
        anchor_policy=anchor_policy,
        max_step_m=max_step_m,
        quadrature_tolerance_m=quadrature_tolerance_m,
        max_points=max_points,
        extra_stations=extra_stations,
    )
    fine_s, fine_x, fine_y, fine_heading, fine_curvature, fine_rate, fine_error = fine
    coarse_s, coarse_x, coarse_y, coarse_heading, _, _, _ = coarse
    x_on_coarse = np.interp(coarse_s, fine_s, fine_x)
    y_on_coarse = np.interp(coarse_s, fine_s, fine_y)
    fine_unwrapped = np.unwrap(fine_heading)
    coarse_unwrapped = np.unwrap(coarse_heading)
    heading_on_coarse = np.interp(coarse_s, fine_s, fine_unwrapped)
    position_error = float(
        np.max(np.hypot(x_on_coarse - coarse_x, y_on_coarse - coarse_y))
    )
    heading_error = float(np.max(np.abs(heading_on_coarse - coarse_unwrapped)))
    if position_error > convergence_position_tolerance_m:
        raise GeometryValidationError(
            "position_discretization_not_converged",
            "halving the sampling step changed position beyond tolerance",
        )
    if heading_error > convergence_heading_tolerance_rad:
        raise GeometryValidationError(
            "heading_discretization_not_converged",
            "halving the sampling step changed heading beyond tolerance",
        )
    sampled_length = float(np.sum(np.hypot(np.diff(fine_x), np.diff(fine_y))))
    support_length = float(fine_s[-1] - fine_s[0])
    arc_length_deficit = support_length - sampled_length
    if arc_length_deficit < -1e-8:
        raise GeometryValidationError(
            "sampled_length_exceeds_support",
            "sampled curve is longer than the spline station domain",
        )
    if arc_length_deficit > max(1e-3, 1e-5 * support_length):
        raise GeometryValidationError(
            "sampled_arc_length_not_converged",
            "sampled polyline length differs from spline support beyond tolerance",
        )
    hypothesis = f"{meaning}__{anchor_policy}"
    return SplineCurve(
        hypothesis=hypothesis,
        curvature_meaning=meaning,
        anchor_policy=anchor_policy,
        s=fine_s,
        x=fine_x,
        y=fine_y,
        heading=fine_heading,
        curvature=fine_curvature,
        curvature_rate=fine_rate,
        maximum_quadrature_error_m=fine_error,
        convergence_position_error_m=position_error,
        convergence_heading_error_rad=heading_error,
        sampled_arc_length_deficit_m=arc_length_deficit,
        invariant_status="passed",
    )


def generate_spline_hypotheses(
    parameters: SplineParameters,
    *,
    include_explicit_index_anchor: bool = False,
    **kwargs: Any,
) -> tuple[tuple[SplineCurve, ...], tuple[tuple[str, str], ...]]:
    """Generate the finite hypothesis family and retain every failure code."""

    policies: tuple[AnchorPolicy, ...] = (
        ("anchor_zero", "explicit_index_anchor")
        if include_explicit_index_anchor
        else ("anchor_zero",)
    )
    curves: list[SplineCurve] = []
    failures: list[tuple[str, str]] = []
    for meaning in ("curvature_rate", "curvature_delta"):
        for policy in policies:
            name = f"{meaning}__{policy}"
            try:
                curves.append(
                    generate_spline_curve(
                        parameters,
                        meaning=meaning,
                        anchor_policy=policy,
                        **kwargs,
                    )
                )
            except GeometryValidationError as error:
                failures.append((name, error.code))
    return tuple(curves), tuple(failures)


def _wrap_angle(values: FloatArray | float) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    return (array + np.pi) % (2.0 * np.pi) - np.pi


def _self_intersects(points: FloatArray) -> bool:
    """Detect non-adjacent planar segment intersections."""

    def orientation(a: FloatArray, b: FloatArray, c: FloatArray) -> float:
        return float(np.cross(b - a, c - a))

    segment_count = len(points) - 1
    for first in range(segment_count):
        a, b = points[first], points[first + 1]
        for second in range(first + 2, segment_count):
            if first == 0 and second == segment_count - 1:
                continue
            c, d = points[second], points[second + 1]
            if (
                max(a[0], b[0]) < min(c[0], d[0])
                or max(c[0], d[0]) < min(a[0], b[0])
                or max(a[1], b[1]) < min(c[1], d[1])
                or max(c[1], d[1]) < min(a[1], b[1])
            ):
                continue
            if orientation(a, b, c) * orientation(a, b, d) < 0.0 and orientation(c, d, a) * orientation(c, d, b) < 0.0:
                return True
    return False


def _symmetric_distances(first: FloatArray, second: FloatArray) -> tuple[float, float]:
    first_projection = project_points_to_polyline(second, first).distances
    second_projection = project_points_to_polyline(first, second).distances
    chamfer = 0.5 * (float(np.mean(first_projection)) + float(np.mean(second_projection)))
    hausdorff = max(float(np.max(first_projection)), float(np.max(second_projection)))
    return chamfer, hausdorff


def compare_curve_to_comparator(
    curve: SplineCurve,
    comparator: ComparatorGeometry,
    *,
    minimum_common_coverage_m: float = 20.0,
) -> HypothesisMetrics:
    """Compare without fitted alignment, station shift, scaling, or reflection."""

    lower = max(float(curve.s[0]), float(comparator.s[0]))
    upper = min(float(curve.s[-1]), float(comparator.s[-1]))
    coverage = upper - lower
    if coverage < minimum_common_coverage_m:
        return HypothesisMetrics(
            hypothesis=curve.hypothesis,
            status="comparison_failed",
            failure_code="insufficient_common_coverage",
            common_coverage_m=max(0.0, coverage),
        )
    mask = (comparator.s >= lower) & (comparator.s <= upper)
    stations = comparator.s[mask]
    if len(stations) < 2:
        return HypothesisMetrics(
            hypothesis=curve.hypothesis,
            status="comparison_failed",
            failure_code="insufficient_comparator_stations",
            common_coverage_m=coverage,
        )
    hypothesis_x = np.interp(stations, curve.s, curve.x)
    hypothesis_y = np.interp(stations, curve.s, curve.y)
    hypothesis_heading = np.interp(stations, curve.s, np.unwrap(curve.heading))
    hypothesis_curvature = np.interp(stations, curve.s, curve.curvature)
    reference_x = comparator.x[mask]
    reference_y = comparator.y[mask]
    reference_heading = np.unwrap(comparator.heading[mask])
    reference_curvature = comparator.curvature[mask]
    difference = np.column_stack(
        (hypothesis_x - reference_x, hypothesis_y - reference_y)
    )
    tangent = np.column_stack((np.cos(reference_heading), np.sin(reference_heading)))
    normal = np.column_stack((-np.sin(reference_heading), np.cos(reference_heading)))
    along = np.einsum("ij,ij->i", tangent, difference)
    lateral = np.einsum("ij,ij->i", normal, difference)
    heading_error = _wrap_angle(hypothesis_heading - reference_heading)
    curvature_error = hypothesis_curvature - reference_curvature

    common_curve_points = np.column_stack((hypothesis_x, hypothesis_y))
    reference_points = np.column_stack((reference_x, reference_y))
    projection = project_points_to_polyline(reference_points, common_curve_points)
    monotonic = np.diff(projection.stations) >= -1e-6
    chamfer, hausdorff = _symmetric_distances(common_curve_points, reference_points)

    zero_station = 0.0
    initial_available = lower <= zero_station <= upper
    if initial_available:
        hx0 = float(np.interp(zero_station, curve.s, curve.x))
        hy0 = float(np.interp(zero_station, curve.s, curve.y))
        rh0 = float(np.interp(zero_station, comparator.s, np.unwrap(comparator.heading)))
        rx0 = float(np.interp(zero_station, comparator.s, comparator.x))
        ry0 = float(np.interp(zero_station, comparator.s, comparator.y))
        hk0 = float(np.interp(zero_station, curve.s, curve.curvature))
        rk0 = float(np.interp(zero_station, comparator.s, comparator.curvature))
        hh0 = float(np.interp(zero_station, curve.s, np.unwrap(curve.heading)))
        initial_position = math.hypot(hx0 - rx0, hy0 - ry0)
        initial_heading = float(abs(_wrap_angle(hh0 - rh0)))
        initial_curvature = abs(hk0 - rk0)
    else:
        initial_position = initial_heading = initial_curvature = None

    absolute_lateral = np.abs(lateral)
    absolute_heading = np.abs(heading_error)
    endpoint_error = float(np.linalg.norm(common_curve_points[-1] - reference_points[-1]))
    return HypothesisMetrics(
        hypothesis=curve.hypothesis,
        status="comparison_completed",
        failure_code=None,
        common_coverage_m=coverage,
        station_count=len(stations),
        lateral_rms_m=float(np.sqrt(np.mean(lateral**2))),
        lateral_median_abs_m=float(np.median(absolute_lateral)),
        lateral_p95_abs_m=float(np.percentile(absolute_lateral, 95)),
        lateral_max_abs_m=float(np.max(absolute_lateral)),
        along_track_rms_m=float(np.sqrt(np.mean(along**2))),
        heading_rms_rad=float(np.sqrt(np.mean(heading_error**2))),
        heading_p95_abs_rad=float(np.percentile(absolute_heading, 95)),
        curvature_rms_per_m=float(np.sqrt(np.mean(curvature_error**2))),
        endpoint_position_error_m=endpoint_error,
        initial_position_error_m=initial_position,
        initial_heading_error_rad=initial_heading,
        initial_curvature_error_per_m=initial_curvature,
        symmetric_chamfer_m=chamfer,
        symmetric_hausdorff_m=hausdorff,
        projection_monotonic_fraction=(
            1.0 if len(monotonic) == 0 else float(np.mean(monotonic))
        ),
        maximum_abs_curvature_per_m=float(np.max(np.abs(curve.curvature))),
        maximum_abs_curvature_rate_per_m2=float(np.max(np.abs(curve.curvature_rate))),
        self_intersection_detected=_self_intersects(curve.points),
    )


def _ambiguous_timestamp_indices(
    times: Sequence[int],
    other_times: Sequence[int],
    *,
    tolerance_ns: int,
) -> set[int]:
    ambiguous: set[int] = set()
    for index, value in enumerate(times):
        distances = [
            abs(value - other)
            for other in other_times
            if abs(value - other) <= tolerance_ns
        ]
        if distances:
            minimum = min(distances)
            if sum(distance == minimum for distance in distances) > 1:
                ambiguous.add(index)
    return ambiguous


def synchronize_estimate_and_comparator(
    estimates: Sequence[EstimatedFrameAudit],
    comparators: Sequence[ComparatorFrameAudit],
    *,
    max_delta_ms: float,
) -> SynchronizationAudit:
    """Maximize monotone pair count, then minimize total absolute delta."""

    if not math.isfinite(max_delta_ms) or max_delta_ms < 0.0:
        raise ValueError("max_delta_ms must be finite and nonnegative")
    tolerance_ns = int(round(max_delta_ms * 1_000_000.0))
    valid_estimates = [item for item in estimates if item.source_time_ns is not None]
    valid_comparators = [item for item in comparators if item.source_time_ns is not None]
    valid_estimates.sort(key=lambda item: (int(item.source_time_ns), item.message_index))
    valid_comparators.sort(key=lambda item: (int(item.source_time_ns), item.message_index))
    estimate_times = [int(item.source_time_ns) for item in valid_estimates]
    comparator_times = [int(item.source_time_ns) for item in valid_comparators]
    ambiguous_estimate_positions = _ambiguous_timestamp_indices(
        estimate_times,
        comparator_times,
        tolerance_ns=tolerance_ns,
    )
    ambiguous_comparator_positions = _ambiguous_timestamp_indices(
        comparator_times,
        estimate_times,
        tolerance_ns=tolerance_ns,
    )

    n, m = len(valid_estimates), len(valid_comparators)
    counts = np.zeros((n + 1, m + 1), dtype=np.int32)
    costs = np.zeros((n + 1, m + 1), dtype=np.int64)
    decisions = np.zeros((n + 1, m + 1), dtype=np.int8)
    # decision priority for exact objective ties: match, skip estimate, skip comparator
    for i in range(1, n + 1):
        decisions[i, 0] = 1
    for j in range(1, m + 1):
        decisions[0, j] = 2

    def better(candidate: tuple[int, int, int], current: tuple[int, int, int]) -> bool:
        candidate_count, candidate_cost, candidate_priority = candidate
        current_count, current_cost, current_priority = current
        return (
            candidate_count > current_count
            or (
                candidate_count == current_count
                and (
                    candidate_cost < current_cost
                    or (
                        candidate_cost == current_cost
                        and candidate_priority > current_priority
                    )
                )
            )
        )

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = (int(counts[i - 1, j]), int(costs[i - 1, j]), 1)
            decision = 1
            skip_comparator = (
                int(counts[i, j - 1]),
                int(costs[i, j - 1]),
                0,
            )
            if better(skip_comparator, best):
                best = skip_comparator
                decision = 2
            delta = estimate_times[i - 1] - comparator_times[j - 1]
            allowed = (
                abs(delta) <= tolerance_ns
                and (i - 1) not in ambiguous_estimate_positions
                and (j - 1) not in ambiguous_comparator_positions
            )
            if allowed:
                matched = (
                    int(counts[i - 1, j - 1]) + 1,
                    int(costs[i - 1, j - 1]) + abs(delta),
                    2,
                )
                if better(matched, best):
                    best = matched
                    decision = 3
            counts[i, j], costs[i, j], decisions[i, j] = best[0], best[1], decision

    pairs: list[SynchronizationPair] = []
    i, j = n, m
    while i > 0 or j > 0:
        decision = int(decisions[i, j])
        if decision == 3:
            estimate = valid_estimates[i - 1]
            comparator = valid_comparators[j - 1]
            pairs.append(
                SynchronizationPair(
                    estimate_index=estimate.message_index,
                    comparator_index=comparator.message_index,
                    source_delta_ns=int(estimate.source_time_ns) - int(comparator.source_time_ns),
                    log_delta_ns=estimate.log_time_ns - comparator.log_time_ns,
                )
            )
            i -= 1
            j -= 1
        elif decision == 1:
            i -= 1
        elif decision == 2:
            j -= 1
        else:
            break
    pairs.reverse()
    paired_estimates = {pair.estimate_index for pair in pairs}
    paired_comparators = {pair.comparator_index for pair in pairs}
    ambiguous_estimate_indices = tuple(
        sorted(valid_estimates[index].message_index for index in ambiguous_estimate_positions)
    )
    ambiguous_comparator_indices = tuple(
        sorted(valid_comparators[index].message_index for index in ambiguous_comparator_positions)
    )
    return SynchronizationAudit(
        pairs=tuple(pairs),
        unmatched_estimate_indices=tuple(
            item.message_index
            for item in estimates
            if item.message_index not in paired_estimates
            and item.message_index not in ambiguous_estimate_indices
        ),
        unmatched_comparator_indices=tuple(
            item.message_index
            for item in comparators
            if item.message_index not in paired_comparators
            and item.message_index not in ambiguous_comparator_indices
        ),
        ambiguous_estimate_indices=ambiguous_estimate_indices,
        ambiguous_comparator_indices=ambiguous_comparator_indices,
    )


def contiguous_state_runs(
    frames: Sequence[EstimatedFrameAudit],
) -> tuple[tuple[str, int], ...]:
    """Return ordered estimator-state run lengths without crossing files."""

    if not frames:
        return ()
    runs: list[tuple[str, int]] = []
    current = frames[0].estimator_state
    length = 1
    for frame in frames[1:]:
        if frame.estimator_state == current:
            length += 1
        else:
            runs.append((current, length))
            current = frame.estimator_state
            length = 1
    runs.append((current, length))
    return tuple(runs)


def state_transition_counts(
    frames: Sequence[EstimatedFrameAudit],
) -> tuple[tuple[str, str, int], ...]:
    counts = Counter(
        (left.estimator_state, right.estimator_state)
        for left, right in pairwise(frames)
    )
    return tuple(
        (source, target, count)
        for (source, target), count in sorted(counts.items())
    )


def metrics_to_dict(metrics: HypothesisMetrics) -> dict[str, object]:
    """Serialize diagnostic scalars with no geometry arrays."""

    return {
        key: value
        for key, value in metrics.__dict__.items()
    }


def audit_counts(frames: Sequence[EstimatedFrameAudit]) -> dict[str, object]:
    """Return denominator-preserving availability/conversion counts."""

    estimator = Counter(frame.estimator_state for frame in frames)
    conversion = Counter(frame.conversion_state for frame in frames)
    intervals = Counter(
        frame.interval_count
        for frame in frames
        if frame.interval_count is not None
    )
    return {
        "decoded_estimate_messages": len(frames),
        "estimator_states": dict(sorted(estimator.items())),
        "conversion_states": dict(sorted(conversion.items())),
        "candidate_ready_messages": sum(frame.candidate_ready for frame in frames),
        "interval_count_distribution": {
            str(count): frequency for count, frequency in sorted(intervals.items())
        },
        "counts_reconcile": sum(estimator.values()) == len(frames),
    }
