"""Strict Protobuf inspection for the v0.18.1 structural feasibility audit."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.sensor_topology_feasibility import (
    MAXIMUM_CHAIN_SEGMENTS,
    MAXIMUM_JUNCTION_GAP_M,
    MAXIMUM_JUNCTION_HEADING_DEG,
    SensorChainAudit,
    SensorSegment,
    SensorTopologyAuditError,
    audit_sensor_chain,
    concatenate_boundaries,
    midpoint_from_boundaries,
    mutual_nearest_timestamp_pairs,
)

SENSOR_TOPIC = "/adp/lane_topology_sensor_based"
REFERENCE_TOPIC = "/adp/road_lane_map_based"
EXPECTED_SCHEMA_NAME = "Adp.Perception.Road"
EXPECTED_SCHEMA_ENCODING = "protobuf"
EXPECTED_MESSAGE_ENCODING = "protobuf"
DESCRIPTOR_IDENTITY_RULE = "sha256(message.DESCRIPTOR.file.serialized_pb)"
INT64_MAX = 9_223_372_036_854_775_807
FLT_MAX = 3.4028234663852886e38

TYPE_FLOAT = 2
TYPE_INT64 = 3
TYPE_UINT64 = 4
TYPE_MESSAGE = 11
TYPE_UINT32 = 13
TYPE_ENUM = 14
TYPE_SINT64 = 18
LABEL_OPTIONAL = 1
LABEL_REPEATED = 3

FAILURE_CODES = frozenset(
    {
        "sensor_topic_missing",
        "reference_topic_missing",
        "sensor_schema_or_encoding_mismatch",
        "reference_schema_or_encoding_mismatch",
        "sensor_descriptor_unavailable",
        "reference_descriptor_unavailable",
        "sensor_required_structure_drift",
        "reference_required_structure_drift",
        "sensor_topology_source_invalid",
        "sensor_stream_decode_failed",
        "reference_stream_decode_failed",
        "sensor_source_timestamp_invalid",
        "reference_source_timestamp_invalid",
        "sensor_source_timestamps_not_strict",
        "reference_source_timestamps_not_strict",
        "sensor_ego_metadata_missing",
        "sensor_ego_metadata_invalid",
        "sensor_ego_segment_not_unique",
        "sensor_unexpected_direct_path",
        "sensor_non_camera_boundary_present",
        "sensor_camera_boundary_range_invalid",
        "sensor_camera_boundary_provenance_invalid",
        "sensor_camera_boundary_geometry_invalid",
        "sensor_camera_boundary_width_implausible",
        "sensor_camera_chain_ambiguous",
        "sensor_camera_chain_cycle",
        "sensor_camera_chain_limit_exceeded",
        "sensor_camera_chain_junction_invalid",
        "sensor_camera_chain_100m_span_unavailable",
        "reference_ego_drive_path_not_unique",
        "reference_successor_chain_invalid",
        "reference_h100_coverage_incomplete",
        "source_time_pair_unavailable",
    }
)
AUDIT_SUPPORT_STATUSES = frozenset(
    {
        "structure_conformant",
        "descriptor_unavailable",
        "required_structure_drift",
        "decode_failed",
    }
)


class SensorTopologyIOError(ValueError):
    """A recording could not be audited without violating the contract."""


@dataclass(frozen=True)
class SchemaInventoryItem:
    topic: str
    message_count: int
    mcap_schema_names: tuple[str, ...]
    mcap_schema_encodings: tuple[str, ...]
    message_encodings: tuple[str, ...]
    descriptor_file_sha256: str | None
    root_message_full_name: str | None
    field_inventory: tuple[dict[str, object], ...]
    audit_support_status: str

    def __post_init__(self) -> None:
        if self.topic not in {SENSOR_TOPIC, REFERENCE_TOPIC}:
            raise ValueError("schema inventory topic is outside the fixed audit topics")
        if type(self.message_count) is not int or self.message_count < 0:
            raise ValueError("schema inventory message_count must be a nonnegative integer")
        if self.audit_support_status not in AUDIT_SUPPORT_STATUSES:
            raise ValueError("schema inventory support status is not contract-defined")
        for name, values in (
            ("mcap_schema_names", self.mcap_schema_names),
            ("mcap_schema_encodings", self.mcap_schema_encodings),
            ("message_encodings", self.message_encodings),
        ):
            if tuple(sorted(set(values))) != values or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise ValueError(f"{name} must be sorted, unique, nonempty strings")
        if self.descriptor_file_sha256 is not None and (
            len(self.descriptor_file_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.descriptor_file_sha256
            )
        ):
            raise ValueError("descriptor identity must be a lowercase SHA-256")
        if (self.descriptor_file_sha256 is None) != (
            self.root_message_full_name is None
        ):
            raise ValueError("descriptor identity and root message name must co-occur")

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "message_count": self.message_count,
            "mcap_schema_names": list(self.mcap_schema_names),
            "mcap_schema_encodings": list(self.mcap_schema_encodings),
            "message_encodings": list(self.message_encodings),
            "descriptor_file_sha256": self.descriptor_file_sha256,
            "root_message_full_name": self.root_message_full_name,
            "field_inventory": [dict(item) for item in self.field_inventory],
            "audit_support_status": self.audit_support_status,
        }


@dataclass(frozen=True)
class RecordingInspection:
    sensor_topic_present: bool
    reference_topic_present: bool
    sensor_message_count: int
    reference_message_count: int
    sensor_decoded_count: int
    reference_decoded_count: int
    sensor_descriptor_file_sha256s: tuple[str, ...]
    reference_descriptor_file_sha256s: tuple[str, ...]
    sensor_source_timestamp_valid_count: int
    reference_source_timestamp_valid_count: int
    sensor_source_timestamps_strict: bool
    reference_source_timestamps_strict: bool
    explicit_ego_candidate_count: int
    camera_boundary_segment_structure_count: int
    camera_only_successor_chain_count: int
    camera_chain_100m_span_count: int
    reference_h100_ready_count: int
    source_time_pair_count: int
    synchronized_100m_candidate_count: int
    failure_codes: tuple[str, ...]
    schema_inventory: tuple[SchemaInventoryItem, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "sensor_topic_present",
            "reference_topic_present",
            "sensor_source_timestamps_strict",
            "reference_source_timestamps_strict",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise ValueError(f"{field_name} must be Boolean")
        count_names = (
            "sensor_message_count",
            "reference_message_count",
            "sensor_decoded_count",
            "reference_decoded_count",
            "sensor_source_timestamp_valid_count",
            "reference_source_timestamp_valid_count",
            "explicit_ego_candidate_count",
            "camera_boundary_segment_structure_count",
            "camera_only_successor_chain_count",
            "camera_chain_100m_span_count",
            "reference_h100_ready_count",
            "source_time_pair_count",
            "synchronized_100m_candidate_count",
        )
        for field_name in count_names:
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a nonnegative integer")
        if self.sensor_decoded_count > self.sensor_message_count:
            raise ValueError("sensor decoded count exceeds container message count")
        if self.reference_decoded_count > self.reference_message_count:
            raise ValueError("reference decoded count exceeds container message count")
        if self.sensor_source_timestamp_valid_count > self.sensor_decoded_count:
            raise ValueError("sensor valid timestamp count exceeds decoded count")
        if self.reference_source_timestamp_valid_count > self.reference_decoded_count:
            raise ValueError("reference valid timestamp count exceeds decoded count")
        if self.sensor_source_timestamps_strict and (
            self.sensor_decoded_count == 0
            or self.sensor_source_timestamp_valid_count != self.sensor_decoded_count
        ):
            raise ValueError("strict sensor timestamps require a complete nonempty stream")
        if self.reference_source_timestamps_strict and (
            self.reference_decoded_count == 0
            or self.reference_source_timestamp_valid_count != self.reference_decoded_count
        ):
            raise ValueError("strict reference timestamps require a complete nonempty stream")
        if not (
            self.camera_chain_100m_span_count
            <= self.camera_only_successor_chain_count
            <= self.camera_boundary_segment_structure_count
            <= self.explicit_ego_candidate_count
            <= self.sensor_decoded_count
        ):
            raise ValueError("sensor structural counts violate prerequisite ordering")
        if self.reference_h100_ready_count > self.reference_decoded_count:
            raise ValueError("reference-ready count exceeds decoded reference count")
        if self.source_time_pair_count > min(
            self.sensor_decoded_count, self.reference_decoded_count
        ):
            raise ValueError("source-time pair count exceeds decoded stream counts")
        if self.synchronized_100m_candidate_count > min(
            self.source_time_pair_count,
            self.camera_chain_100m_span_count,
            self.reference_h100_ready_count,
        ):
            raise ValueError("synchronized candidate count exceeds its prerequisite counts")
        for field_name in (
            "sensor_descriptor_file_sha256s",
            "reference_descriptor_file_sha256s",
        ):
            values = getattr(self, field_name)
            if tuple(sorted(set(values))) != values or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in values
            ):
                raise ValueError(f"{field_name} must contain sorted unique lowercase SHA-256s")
        if tuple(sorted(set(self.failure_codes))) != self.failure_codes:
            raise ValueError("recording failure codes must be sorted and unique")
        unknown = set(self.failure_codes) - FAILURE_CODES
        if unknown:
            raise ValueError(f"recording failure codes are not contract-defined: {sorted(unknown)}")


def _strict_int(value: object, *, code: str, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise SensorTopologyAuditError(code, f"{name} must be a non-Boolean integer")
    return int(value)


def _descriptor(message: Any) -> Any:
    descriptor = getattr(message, "DESCRIPTOR", None)
    file_descriptor = getattr(descriptor, "file", None)
    serialized = getattr(file_descriptor, "serialized_pb", None)
    if descriptor is None or not isinstance(serialized, bytes):
        raise SensorTopologyIOError("message-owned descriptor is unavailable")
    return descriptor


def descriptor_file_sha256(message: Any) -> str:
    descriptor = _descriptor(message)
    return hashlib.sha256(descriptor.file.serialized_pb).hexdigest()


def _field(descriptor: Any, number: int) -> Any:
    fields = getattr(descriptor, "fields_by_number", {})
    field = fields.get(number)
    if field is None:
        raise SensorTopologyIOError(f"required field number {number} is missing")
    return field


def _value(message: Any, number: int) -> Any:
    field = _field(_descriptor(message), number)
    return getattr(message, field.name)


def _referenced_name(field: Any) -> str | None:
    referenced = getattr(field, "message_type", None) or getattr(field, "enum_type", None)
    return None if referenced is None else str(referenced.full_name)


def _field_label(field: Any) -> int:
    """Return the Protobuf label across protobuf 4.x through 7.x."""

    repeated = getattr(field, "is_repeated", None)
    required = getattr(field, "is_required", None)
    if repeated is not None or required is not None:
        if bool(repeated):
            return LABEL_REPEATED
        if bool(required):
            return 2
        return LABEL_OPTIONAL
    label = getattr(field, "label", None)
    if label is not None:
        return int(label)
    if bool(repeated):
        return LABEL_REPEATED
    if bool(required):
        return 2
    return LABEL_OPTIONAL


def _require(
    descriptor: Any,
    number: int,
    field_type: int,
    label: int,
    *,
    referenced_suffix: str | None = None,
) -> Any:
    field = _field(descriptor, number)
    if int(field.type) != field_type or _field_label(field) != label:
        raise SensorTopologyIOError(f"field {descriptor.full_name}#{number} kind or label drifted")
    if referenced_suffix is not None:
        name = _referenced_name(field)
        expected = referenced_suffix
        actual = name
        matches = bool(
            actual is not None
            and (
                actual == expected
                if "." in referenced_suffix
                else actual.rsplit(".", 1)[-1] == expected
            )
        )
        if not matches:
            raise SensorTopologyIOError(
                f"field {descriptor.full_name}#{number} referenced type drifted"
            )
    return field


def _root_identity(descriptor: Any) -> None:
    full_name = str(descriptor.full_name)
    parts = full_name.rsplit(".", 1)
    if len(parts) != 2 or parts[1] != "Road" or parts[0].lower() != "adp.perception":
        raise SensorTopologyIOError("root message must be Adp.Perception.Road")


def _enum_contains(
    field: Any,
    number: int,
    accepted_symbols: frozenset[str],
) -> None:
    values = getattr(getattr(field, "enum_type", None), "values", ())
    if not any(
        int(value.number) == number and str(value.name) in accepted_symbols
        for value in values
    ):
        raise SensorTopologyIOError(
            f"enum for {field.full_name} lacks reviewed value {number}"
        )


def validate_sensor_descriptor(message: Any) -> None:
    """Validate every field the sensor audit consumes, by number and kind."""

    road = _descriptor(message)
    _root_identity(road)
    topology = _require(
        road,
        4,
        TYPE_ENUM,
        LABEL_OPTIONAL,
        referenced_suffix="Adp.Perception.RoadTopologySource",
    )
    _enum_contains(
        topology,
        4,
        frozenset(
            {
                "SENSOR_TOPOLOGY",
                "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
            }
        ),
    )
    _require(road, 5, TYPE_SINT64, LABEL_OPTIONAL)
    _require(road, 6, TYPE_SINT64, LABEL_REPEATED)
    segment_field = _require(road, 7, TYPE_MESSAGE, LABEL_REPEATED, referenced_suffix="RoadLaneSegment")
    boundary_field = _require(road, 9, TYPE_MESSAGE, LABEL_REPEATED, referenced_suffix="RoadLaneBoundary")
    vertex_field = _require(road, 12, TYPE_MESSAGE, LABEL_REPEATED, referenced_suffix="Adp.PolylineVertex")
    _require(road, 13, TYPE_FLOAT, LABEL_REPEATED)

    segment = segment_field.message_type
    _require(segment, 6, TYPE_INT64, LABEL_REPEATED)
    range_field = _require(segment, 11, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Range")
    left = _require(segment, 12, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="BoundaryRanges")
    _require(segment, 13, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="BoundaryRanges")
    ranges = left.message_type
    for number in (1, 2, 3):
        _require(ranges, number, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Range")
    range_descriptor = range_field.message_type
    _require(range_descriptor, 1, TYPE_INT64, LABEL_OPTIONAL)
    _require(range_descriptor, 2, TYPE_INT64, LABEL_OPTIONAL)

    boundary = boundary_field.message_type
    _require(boundary, 1, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Range")
    source = _require(
        boundary,
        4,
        TYPE_ENUM,
        LABEL_OPTIONAL,
        referenced_suffix="Adp.LaneBoundarySource",
    )
    _enum_contains(
        source,
        1,
        frozenset({"CAMERA", "LANE_BOUNDARY_SOURCE_CAMERA"}),
    )
    vertex = vertex_field.message_type
    x_field = _require(vertex, 1, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Adp.Common.NormalDistributedValueF")
    _require(vertex, 2, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Adp.Common.NormalDistributedValueF")
    wrapper = x_field.message_type
    _require(wrapper, 1, TYPE_FLOAT, LABEL_OPTIONAL)
    _require(wrapper, 2, TYPE_FLOAT, LABEL_OPTIONAL)
    _require(wrapper, 3, TYPE_UINT32, LABEL_OPTIONAL)


def _reference_descriptor_supported(message: Any) -> None:
    road = _descriptor(message)
    _root_identity(road)
    _require(road, 5, TYPE_SINT64, LABEL_OPTIONAL)
    _require(road, 6, TYPE_SINT64, LABEL_REPEATED)
    segment = _require(road, 7, TYPE_MESSAGE, LABEL_REPEATED, referenced_suffix="RoadLaneSegment").message_type
    vertex = _require(road, 10, TYPE_MESSAGE, LABEL_REPEATED, referenced_suffix="Adp.PolylineVertex").message_type
    _require(road, 11, TYPE_FLOAT, LABEL_REPEATED)
    range_descriptor = _require(segment, 11, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Range").message_type
    _require(segment, 1, TYPE_UINT64, LABEL_OPTIONAL)
    _require(segment, 6, TYPE_INT64, LABEL_REPEATED)
    _require(range_descriptor, 1, TYPE_INT64, LABEL_OPTIONAL)
    _require(range_descriptor, 2, TYPE_INT64, LABEL_OPTIONAL)
    wrapper = _require(vertex, 1, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Adp.Common.NormalDistributedValueF").message_type
    _require(vertex, 2, TYPE_MESSAGE, LABEL_OPTIONAL, referenced_suffix="Adp.Common.NormalDistributedValueF")
    _require(wrapper, 1, TYPE_FLOAT, LABEL_OPTIONAL)


def recursive_field_inventory(message: Any) -> tuple[dict[str, object], ...]:
    """Return a deterministic descriptor-only inventory with no option values."""

    root = _descriptor(message)
    pending = [root]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    while pending:
        descriptor = pending.pop()
        name = str(descriptor.full_name)
        if name in seen:
            continue
        seen.add(name)
        for field in sorted(descriptor.fields, key=lambda item: (item.number, item.name)):
            referenced = _referenced_name(field)
            rows.append(
                {
                    "full_name": str(field.full_name),
                    "number": int(field.number),
                    "label": _field_label(field),
                    "kind": int(field.type),
                    "referenced_full_name": referenced,
                    "oneof_name": (
                        None
                        if getattr(field, "containing_oneof", None) is None
                        else str(field.containing_oneof.name)
                    ),
                }
            )
            if getattr(field, "message_type", None) is not None:
                pending.append(field.message_type)
    return tuple(sorted(rows, key=lambda item: (str(item["full_name"]), int(item["number"]))))


def _range(value: Any, *, code: str, name: str) -> tuple[int, int]:
    start = _strict_int(_value(value, 1), code=code, name=f"{name}.start")
    size = _strict_int(_value(value, 2), code=code, name=f"{name}.size")
    return start, size


def _sentinel(value: Any, *, code: str, name: str) -> None:
    if _range(value, code=code, name=name) != (INT64_MAX, 0):
        raise SensorTopologyAuditError(code, f"{name} is not the exact unwritten sentinel")


def _slice(start: int, size: int, length: int, *, code: str, name: str, minimum: int = 1) -> slice:
    if start < 0 or size < minimum or start > length or size > length - start:
        raise SensorTopologyAuditError(code, f"{name} is empty or out of bounds")
    return slice(start, start + size)


def _wrapper_mean(wrapper: Any) -> float:
    flags = _strict_int(
        _value(wrapper, 3),
        code="sensor_camera_boundary_geometry_invalid",
        name="invalid_flags",
    )
    if not 0 <= flags <= 255 or flags & 0x01:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "coordinate mean is marked invalid",
        )
    mean = _value(wrapper, 1)
    if isinstance(mean, bool) or not isinstance(mean, (int, float, np.number)):
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "coordinate mean is not numeric",
        )
    result = float(mean)
    if not math.isfinite(result) or result >= FLT_MAX:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "coordinate mean is non-finite or FLT_MAX sentinel",
        )
    return result


def _boundary_points(boundary: Any, vertices: Sequence[Any], arcs: Sequence[Any]) -> np.ndarray:
    source = _strict_int(
        _value(boundary, 4),
        code="sensor_camera_boundary_provenance_invalid",
        name="boundary source",
    )
    if source != 1:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_provenance_invalid",
            "boundary source is not CAMERA (1)",
        )
    start, size = _range(
        _value(boundary, 1),
        code="sensor_camera_boundary_geometry_invalid",
        name="boundary geometry",
    )
    vertex_slice = _slice(
        start,
        size,
        len(vertices),
        code="sensor_camera_boundary_geometry_invalid",
        name="boundary vertex range",
        minimum=2,
    )
    arc_slice = _slice(
        start,
        size,
        len(arcs),
        code="sensor_camera_boundary_geometry_invalid",
        name="boundary arc range",
        minimum=2,
    )
    arc = np.asarray(tuple(arcs[arc_slice]), dtype=np.float64)
    if (
        not np.all(np.isfinite(arc))
        or float(arc[0]) != 0.0
        or np.any(np.diff(arc) < 0.0)
        or float(arc[-1]) <= 0.0
    ):
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "boundary arc slice violates the stored-order contract",
        )
    return np.asarray(
        [
            (_wrapper_mean(_value(vertex, 1)), _wrapper_mean(_value(vertex, 2)))
            for vertex in vertices[vertex_slice]
        ],
        dtype=np.float64,
    )


def _camera_side(
    boundary_ranges: Any,
    boundary_pool: Sequence[Any],
    vertices: Sequence[Any],
    arcs: Sequence[Any],
    *,
    side: str,
) -> tuple[np.ndarray, ...]:
    for number, source_name in ((1, "map_based"), (3, "artificial")):
        _sentinel(
            _value(boundary_ranges, number),
            code="sensor_non_camera_boundary_present",
            name=f"{side}.{source_name}",
        )
    start, size = _range(
        _value(boundary_ranges, 2),
        code="sensor_camera_boundary_range_invalid",
        name=f"{side}.camera_based",
    )
    selected = boundary_pool[
        _slice(
            start,
            size,
            len(boundary_pool),
            code="sensor_camera_boundary_range_invalid",
            name=f"{side}.camera_based",
        )
    ]
    return tuple(_boundary_points(boundary, vertices, arcs) for boundary in selected)


def sensor_segments_from_message(message: Any) -> tuple[SensorSegment, ...]:
    segments = tuple(_value(message, 7))
    boundary_pool = tuple(_value(message, 9))
    vertices = tuple(_value(message, 12))
    arcs = tuple(_value(message, 13))
    result: list[SensorSegment] = []
    for segment in segments:
        successors = tuple(_value(segment, 6))
        try:
            _sentinel(
                _value(segment, 11),
                code="sensor_unexpected_direct_path",
                name="drive_path_range",
            )
            left_ranges = _value(segment, 12)
            right_ranges = _value(segment, 13)
            left_camera = _range(
                _value(left_ranges, 2),
                code="sensor_camera_boundary_range_invalid",
                name="left.camera_based",
            )
            right_camera = _range(
                _value(right_ranges, 2),
                code="sensor_camera_boundary_range_invalid",
                name="right.camera_based",
            )
            if left_camera == (INT64_MAX, 0) and right_camera == (INT64_MAX, 0):
                for ranges, side in ((left_ranges, "left"), (right_ranges, "right")):
                    for number, source_name in ((1, "map_based"), (3, "artificial")):
                        _sentinel(
                            _value(ranges, number),
                            code="sensor_non_camera_boundary_present",
                            name=f"{side}.{source_name}",
                        )
                result.append(
                    SensorSegment(None, successors, empty_map_influenced_termination=True)
                )
                continue
            left = concatenate_boundaries(
                _camera_side(left_ranges, boundary_pool, vertices, arcs, side="left")
            )
            right = concatenate_boundaries(
                _camera_side(right_ranges, boundary_pool, vertices, arcs, side="right")
            )
            midpoint = midpoint_from_boundaries(left, right)
            result.append(SensorSegment(midpoint, successors))
        except SensorTopologyAuditError as error:
            result.append(SensorSegment(None, successors, failure_code=error.code))
    return tuple(result)


def sensor_message_audit(message: Any) -> SensorChainAudit:
    validate_sensor_descriptor(message)
    topology = _value(message, 4)
    if isinstance(topology, bool) or not isinstance(topology, Integral) or int(topology) != 4:
        return SensorChainAudit(False, False, False, False, ("sensor_topology_source_invalid",))
    return audit_sensor_chain(tuple(_value(message, 6)), sensor_segments_from_message(message))


def source_timestamp(message: Any) -> int | None:
    value = _value(message, 5)
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        return None
    return int(value)


def _direct_points(message: Any, segment: Any) -> np.ndarray:
    _strict_int(
        _value(segment, 1),
        code="reference_successor_chain_invalid",
        name="reference segment id",
    )
    vertices = tuple(_value(message, 10))
    start, size = _range(
        _value(segment, 11),
        code="reference_successor_chain_invalid",
        name="reference drive path",
    )
    selected = vertices[
        _slice(
            start,
            size,
            len(vertices),
            code="reference_successor_chain_invalid",
            name="reference drive path",
            minimum=2,
        )
    ]
    def reference_mean(wrapper: Any) -> float:
        descriptor = _descriptor(wrapper)
        flag_field = getattr(descriptor, "fields_by_number", {}).get(3)
        if flag_field is not None:
            flags = _strict_int(
                getattr(wrapper, flag_field.name),
                code="reference_h100_coverage_incomplete",
                name="reference coordinate invalid_flags",
            )
            if flags == 255 or flags & 0x01:
                raise SensorTopologyAuditError(
                    "reference_h100_coverage_incomplete",
                    "reference coordinate mean is marked invalid",
                )
        value = _value(wrapper, 1)
        if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
            raise SensorTopologyAuditError(
                "reference_h100_coverage_incomplete",
                "reference coordinate mean is not numeric",
            )
        return float(value)

    points = np.asarray(
        [
            (
                reference_mean(_value(vertex, 1)),
                reference_mean(_value(vertex, 2)),
            )
            for vertex in selected
        ],
        dtype=np.float64,
    )
    arcs = tuple(_value(message, 11))
    if len(arcs) == len(vertices):
        selected_arcs = np.asarray(arcs[start : start + size], dtype=np.float64)
        if len(selected_arcs) != len(points) or not np.all(np.isfinite(selected_arcs)):
            raise SensorTopologyAuditError(
                "reference_h100_coverage_incomplete",
                "reference arc-length slice is invalid",
            )
    if not np.all(np.isfinite(points)) or len(points) < 2:
        raise SensorTopologyAuditError(
            "reference_successor_chain_invalid",
            "reference drive path is non-finite or too short",
        )
    increments = np.linalg.norm(np.diff(points, axis=0), axis=1)
    points = points[np.concatenate(([True], increments > 1e-7))]
    if len(points) < 2:
        raise SensorTopologyAuditError(
            "reference_successor_chain_invalid",
            "reference drive path collapses below two distinct points",
        )
    return points


def _origin_forward_coverage(points: np.ndarray) -> float:
    increments = np.linalg.norm(np.diff(points, axis=0), axis=1)
    if not np.all(np.isfinite(increments)) or np.any(increments <= 0.0):
        raise SensorTopologyAuditError(
            "reference_successor_chain_invalid",
            "reference path is degenerate",
        )
    geometry = points
    for _ in range(2):
        increments = np.linalg.norm(np.diff(geometry, axis=0), axis=1)
        station = np.concatenate(([0.0], np.cumsum(increments)))
        starts = geometry[:-1]
        vectors = np.diff(geometry, axis=0)
        fractions = np.einsum("ij,ij->i", -starts, vectors) / np.square(increments)
        fractions = np.clip(fractions, 0.0, 1.0)
        projections = starts + fractions[:, None] * vectors
        distances = np.linalg.norm(projections, axis=1)
        best = int(np.argmin(distances))
        projected_stations = station[:-1] + fractions * increments
        close = np.flatnonzero(distances <= float(distances[best]) + 1e-3)
        if len(close) > 1 and float(np.ptp(projected_stations[close])) > 1.0:
            raise SensorTopologyAuditError(
                "reference_successor_chain_invalid",
                "reference ego-origin projection is ambiguous",
            )
        heading = math.atan2(float(vectors[best, 1]), float(vectors[best, 0]))
        if math.cos(heading) < 0.0:
            geometry = geometry[::-1].copy()
            continue
        return float(station[-1] - projected_stations[best])
    raise AssertionError("reference orientation loop did not terminate")


def reference_h100_ready(message: Any) -> tuple[bool, str | None]:
    """Reproduce the accepted RLMB unique-chain and forward-coverage gates."""

    try:
        _reference_descriptor_supported(message)
        segments = tuple(_value(message, 7))
        ego_raw = tuple(_value(message, 6))
        if len(ego_raw) != 1:
            return False, "reference_ego_drive_path_not_unique"
        ego = _strict_int(
            ego_raw[0],
            code="reference_ego_drive_path_not_unique",
            name="reference ego index",
        )
        if ego < 0 or ego >= len(segments):
            return False, "reference_ego_drive_path_not_unique"
        current = ego
        visited = {ego}
        chain = _direct_points(message, segments[ego])
        while _origin_forward_coverage(chain) + 1e-9 < 100.0:
            if len(visited) >= MAXIMUM_CHAIN_SEGMENTS:
                return False, "reference_successor_chain_invalid"
            successors = tuple(_value(segments[current], 6))
            if len(successors) != 1:
                return False, "reference_successor_chain_invalid"
            successor = _strict_int(
                successors[0],
                code="reference_successor_chain_invalid",
                name="reference successor",
            )
            if successor < 0 or successor >= len(segments) or successor in visited:
                return False, "reference_successor_chain_invalid"
            candidate = _direct_points(message, segments[successor])
            gap = float(np.linalg.norm(chain[-1] - candidate[0]))
            first_heading = math.atan2(*(np.diff(chain[-2:], axis=0)[0][::-1]))
            second_heading = math.atan2(*(np.diff(candidate[:2], axis=0)[0][::-1]))
            delta = abs((second_heading - first_heading + math.pi) % (2 * math.pi) - math.pi)
            if gap > MAXIMUM_JUNCTION_GAP_M + 1e-12 or delta > math.radians(MAXIMUM_JUNCTION_HEADING_DEG) + 1e-12:
                return False, "reference_successor_chain_invalid"
            if gap <= 1e-7:
                candidate = candidate[1:]
            chain = np.vstack((chain, candidate))
            current = successor
            visited.add(successor)
        return True, None
    except (SensorTopologyAuditError, SensorTopologyIOError, TypeError, ValueError, OverflowError):
        return False, "reference_h100_coverage_incomplete"


def _strict_stream(times: Sequence[int | None]) -> bool:
    return bool(times) and all(value is not None for value in times) and all(
        int(second) > int(first)
        for first, second in zip(times, times[1:])
    )


def inspect_decoded_recording(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    container_probes: Mapping[str, Any] | None = None,
) -> RecordingInspection:
    """Inspect decoded MCAP tuples without exporting payload values."""

    messages: dict[str, list[Any]] = {SENSOR_TOPIC: [], REFERENCE_TOPIC: []}
    metadata: dict[str, list[tuple[str, str, str, Any]]] = {
        SENSOR_TOPIC: [],
        REFERENCE_TOPIC: [],
    }
    failures: set[str] = set()
    for schema, channel, _record, decoded in decoded_messages:
        topic = str(channel.topic)
        if topic not in messages:
            continue
        schema_name = str(schema.name)
        schema_encoding = str(schema.encoding).lower()
        message_encoding = str(channel.message_encoding).lower()
        messages[topic].append(decoded)
        metadata[topic].append((schema_name, schema_encoding, message_encoding, decoded))
        if (
            schema_name != EXPECTED_SCHEMA_NAME
            or schema_encoding != EXPECTED_SCHEMA_ENCODING
            or message_encoding != EXPECTED_MESSAGE_ENCODING
        ):
            failures.add(
                "sensor_schema_or_encoding_mismatch"
                if topic == SENSOR_TOPIC
                else "reference_schema_or_encoding_mismatch"
            )

    probes = {} if container_probes is None else dict(container_probes)
    sensor_probe = probes.get(SENSOR_TOPIC)
    reference_probe = probes.get(REFERENCE_TOPIC)
    sensor_present = (
        bool(messages[SENSOR_TOPIC])
        if sensor_probe is None
        else bool(sensor_probe.present)
    )
    reference_present = (
        bool(messages[REFERENCE_TOPIC])
        if reference_probe is None
        else bool(reference_probe.present)
    )
    sensor_message_count = (
        len(messages[SENSOR_TOPIC])
        if sensor_probe is None
        else int(sensor_probe.message_count)
    )
    reference_message_count = (
        len(messages[REFERENCE_TOPIC])
        if reference_probe is None
        else int(reference_probe.message_count)
    )
    for topic, probe in (
        (SENSOR_TOPIC, sensor_probe),
        (REFERENCE_TOPIC, reference_probe),
    ):
        if probe is None or not probe.present:
            continue
        if (
            set(probe.schema_names) != {EXPECTED_SCHEMA_NAME}
            or {value.lower() for value in probe.schema_encodings}
            != {EXPECTED_SCHEMA_ENCODING}
            or {value.lower() for value in probe.message_encodings}
            != {EXPECTED_MESSAGE_ENCODING}
        ):
            failures.add(
                "sensor_schema_or_encoding_mismatch"
                if topic == SENSOR_TOPIC
                else "reference_schema_or_encoding_mismatch"
            )
    if not sensor_present:
        failures.add("sensor_topic_missing")
    if not reference_present:
        failures.add("reference_topic_missing")

    inventory_groups: dict[tuple[str, str | None, str], list[tuple[str, str, str, Any]]] = defaultdict(list)
    supported_by_message: dict[int, bool] = {}
    for topic, records in metadata.items():
        for schema_name, schema_encoding, message_encoding, message in records:
            exact_container = (
                schema_name == EXPECTED_SCHEMA_NAME
                and schema_encoding == EXPECTED_SCHEMA_ENCODING
                and message_encoding == EXPECTED_MESSAGE_ENCODING
            )
            try:
                descriptor = _descriptor(message)
                digest = hashlib.sha256(descriptor.file.serialized_pb).hexdigest()
            except SensorTopologyIOError:
                digest = None
                status = "descriptor_unavailable"
                supported_by_message[id(message)] = False
                failures.add(
                    "sensor_descriptor_unavailable"
                    if topic == SENSOR_TOPIC
                    else "reference_descriptor_unavailable"
                )
            else:
                try:
                    validator = (
                        validate_sensor_descriptor
                        if topic == SENSOR_TOPIC
                        else _reference_descriptor_supported
                    )
                    validator(message)
                except SensorTopologyIOError:
                    status = "required_structure_drift"
                    supported_by_message[id(message)] = False
                    failures.add(
                        "sensor_required_structure_drift"
                        if topic == SENSOR_TOPIC
                        else "reference_required_structure_drift"
                    )
                else:
                    status = "structure_conformant"
                    supported_by_message[id(message)] = exact_container
            inventory_groups[(topic, digest, status)].append(
                (schema_name, schema_encoding, message_encoding, message)
            )

    inventory: list[SchemaInventoryItem] = []
    for (topic, digest, status), group in sorted(
        inventory_groups.items(), key=lambda item: (item[0][0], item[0][1] or "", item[0][2])
    ):
        example = group[0][3]
        inventory.append(
            SchemaInventoryItem(
                topic=topic,
                message_count=len(group),
                mcap_schema_names=tuple(sorted({item[0] for item in group})),
                mcap_schema_encodings=tuple(sorted({item[1] for item in group})),
                message_encodings=tuple(sorted({item[2] for item in group})),
                descriptor_file_sha256=digest,
                root_message_full_name=(None if digest is None else str(_descriptor(example).full_name)),
                field_inventory=(
                    () if digest is None else recursive_field_inventory(example)
                ),
                audit_support_status=status,
            )
        )

    sensor_times: list[int | None] = []
    sensor_audits: list[SensorChainAudit] = []
    for message in messages[SENSOR_TOPIC]:
        try:
            sensor_times.append(source_timestamp(message))
            if supported_by_message.get(id(message), False):
                audit = sensor_message_audit(message)
            else:
                audit = SensorChainAudit(False, False, False, False, ())
        except (SensorTopologyAuditError, SensorTopologyIOError, TypeError, ValueError, OverflowError):
            sensor_times.append(None)
            audit = SensorChainAudit(False, False, False, False, ("sensor_stream_decode_failed",))
        sensor_audits.append(audit)
        failures.update(audit.failure_codes)

    reference_times: list[int | None] = []
    reference_ready: list[bool] = []
    for message in messages[REFERENCE_TOPIC]:
        try:
            reference_times.append(source_timestamp(message))
            if supported_by_message.get(id(message), False):
                ready, failure = reference_h100_ready(message)
            else:
                ready, failure = False, None
        except (SensorTopologyAuditError, SensorTopologyIOError, TypeError, ValueError, OverflowError):
            reference_times.append(None)
            ready, failure = False, "reference_stream_decode_failed"
        reference_ready.append(ready)
        if failure:
            failures.add(failure)

    sensor_strict = _strict_stream(sensor_times)
    reference_strict = _strict_stream(reference_times)
    if sensor_times and any(value is None for value in sensor_times):
        failures.add("sensor_source_timestamp_invalid")
    if reference_times and any(value is None for value in reference_times):
        failures.add("reference_source_timestamp_invalid")
    if sensor_times and not sensor_strict:
        failures.add("sensor_source_timestamps_not_strict")
    if reference_times and not reference_strict:
        failures.add("reference_source_timestamps_not_strict")

    pairs = ()
    sensor_supported = bool(messages[SENSOR_TOPIC]) and all(
        supported_by_message.get(id(message), False)
        for message in messages[SENSOR_TOPIC]
    )
    reference_supported = bool(messages[REFERENCE_TOPIC]) and all(
        supported_by_message.get(id(message), False)
        for message in messages[REFERENCE_TOPIC]
    )
    if sensor_strict and reference_strict and sensor_supported and reference_supported:
        pair_audit = mutual_nearest_timestamp_pairs(
            [int(value) for value in sensor_times if value is not None],
            [int(value) for value in reference_times if value is not None],
        )
        pairs = pair_audit.pairs
    if not pairs:
        failures.add("source_time_pair_unavailable")
    synchronized = sum(
        sensor_audits[pair.first_position].camera_chain_100m_span
        and reference_ready[pair.second_position]
        for pair in pairs
    )
    return RecordingInspection(
        sensor_topic_present=sensor_present,
        reference_topic_present=reference_present,
        sensor_message_count=sensor_message_count,
        reference_message_count=reference_message_count,
        sensor_decoded_count=len(messages[SENSOR_TOPIC]),
        reference_decoded_count=len(messages[REFERENCE_TOPIC]),
        sensor_descriptor_file_sha256s=tuple(
            sorted(
                {
                    item.descriptor_file_sha256
                    for item in inventory
                    if item.topic == SENSOR_TOPIC and item.descriptor_file_sha256 is not None
                }
            )
        ),
        reference_descriptor_file_sha256s=tuple(
            sorted(
                {
                    item.descriptor_file_sha256
                    for item in inventory
                    if item.topic == REFERENCE_TOPIC and item.descriptor_file_sha256 is not None
                }
            )
        ),
        sensor_source_timestamp_valid_count=sum(value is not None for value in sensor_times),
        reference_source_timestamp_valid_count=sum(value is not None for value in reference_times),
        sensor_source_timestamps_strict=sensor_strict,
        reference_source_timestamps_strict=reference_strict,
        explicit_ego_candidate_count=sum(item.explicit_ego_candidate for item in sensor_audits),
        camera_boundary_segment_structure_count=sum(item.initial_segment_structure for item in sensor_audits),
        camera_only_successor_chain_count=sum(item.camera_only_successor_chain for item in sensor_audits),
        camera_chain_100m_span_count=sum(item.camera_chain_100m_span for item in sensor_audits),
        reference_h100_ready_count=sum(reference_ready),
        source_time_pair_count=len(pairs),
        synchronized_100m_candidate_count=int(synchronized),
        failure_codes=tuple(sorted(failures)),
        schema_inventory=tuple(inventory),
    )


def inspect_mcap_recording(path: Path) -> RecordingInspection:
    """Stream the two fixed topics from one MCAP recording."""

    from .mcap import inspect_mcap_topics, iter_decoded_mcap_messages

    probes = inspect_mcap_topics(path, topics=(SENSOR_TOPIC, REFERENCE_TOPIC))
    probe_by_topic = {item.topic: item for item in probes}
    records: list[tuple[Any, Any, Any, Any]] = []
    try:
        records.extend(
            iter_decoded_mcap_messages(
                path,
                topics=(SENSOR_TOPIC, REFERENCE_TOPIC),
            )
        )
        return inspect_decoded_recording(
            records,
            container_probes=probe_by_topic,
        )
    except Exception:
        partial = inspect_decoded_recording(
            records,
            container_probes=probe_by_topic,
        )
        failures = set(partial.failure_codes)
        failures.update(
            ("sensor_stream_decode_failed", "reference_stream_decode_failed")
        )
        decode_inventory = list(partial.schema_inventory)
        for topic in (SENSOR_TOPIC, REFERENCE_TOPIC):
            probe = probe_by_topic[topic]
            decoded_count = sum(
                str(record[1].topic) == topic for record in records
            )
            remaining_count = max(0, int(probe.message_count) - decoded_count)
            if remaining_count == 0:
                continue
            decode_inventory.append(
                SchemaInventoryItem(
                    topic=topic,
                    message_count=remaining_count,
                    mcap_schema_names=tuple(sorted(probe.schema_names)),
                    mcap_schema_encodings=tuple(
                        sorted(value.lower() for value in probe.schema_encodings)
                    ),
                    message_encodings=tuple(
                        sorted(value.lower() for value in probe.message_encodings)
                    ),
                    descriptor_file_sha256=None,
                    root_message_full_name=None,
                    field_inventory=(),
                    audit_support_status="decode_failed",
                )
            )
        return replace(
            partial,
            failure_codes=tuple(sorted(failures)),
            schema_inventory=tuple(decode_inventory),
        )
