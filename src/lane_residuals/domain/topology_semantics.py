"""Pure EDP topology decoding and audit statistics.

The helpers in this module do not change the accepted geometry gate.  They
expose the raw protobuf enum evidence alongside the descriptor-based decode so
an unexpected topology source cannot be mistaken for a timing effect.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .geometry_validation import estimated_frame_from_message
from .path_source_probe import (
    _FIELD_VALUE_MISSING,
    _audit_one_path,
    _effective_field_value,
    _joint_audit_bindings,
    _repeated_values,
)


class ProtobufWireError(ValueError):
    """A payload could not be traversed as a protobuf wire message."""


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    if offset >= len(data):
        raise ProtobufWireError("truncated varint")
    raise ProtobufWireError("varint is longer than 10 bytes")


def _skip_value(data: bytes, offset: int, field_number: int, wire_type: int) -> int:
    if wire_type == 0:
        return _read_varint(data, offset)[1]
    if wire_type == 1:
        end = offset + 8
    elif wire_type == 2:
        length, offset = _read_varint(data, offset)
        end = offset + length
    elif wire_type == 3:
        while offset < len(data):
            key, offset = _read_varint(data, offset)
            nested_number, nested_type = key >> 3, key & 7
            if nested_type == 4:
                if nested_number != field_number:
                    raise ProtobufWireError("mismatched protobuf end-group")
                return offset
            offset = _skip_value(data, offset, nested_number, nested_type)
        raise ProtobufWireError("unterminated protobuf group")
    elif wire_type == 4:
        raise ProtobufWireError("unexpected protobuf end-group")
    elif wire_type == 5:
        end = offset + 4
    else:
        raise ProtobufWireError(f"invalid protobuf wire type {wire_type}")
    if end > len(data):
        raise ProtobufWireError("protobuf field extends beyond payload")
    return end


def extract_top_level_varint(
    payload: bytes, field_number: int
) -> tuple[bool, int | None, int]:
    """Return protobuf presence, last value, and occurrence count."""

    if field_number <= 0:
        raise ValueError("protobuf field number must be positive")
    values: list[int] = []
    offset = 0
    while offset < len(payload):
        key, offset = _read_varint(payload, offset)
        number, wire_type = key >> 3, key & 7
        if number == 0:
            raise ProtobufWireError("protobuf field number zero is invalid")
        if number == field_number:
            if wire_type != 0:
                raise ProtobufWireError("topology enum field is not a varint")
            value, offset = _read_varint(payload, offset)
            values.append(value)
        else:
            offset = _skip_value(payload, offset, number, wire_type)
    return (bool(values), values[-1] if values else None, len(values))


@dataclass(frozen=True)
class TopologyDecode:
    """Descriptor and raw-wire evidence for one EDP message."""

    message_index: int
    log_time_ns: int
    publish_time_ns: int
    source_time_ns: int | None
    schema_fingerprint: str | None
    topology_field_number: int
    topology_enum_type: str
    topology_wire_present: bool
    topology_wire_value: int | None
    topology_wire_occurrence_count: int
    topology_decoded_value: int | None
    topology_source_name: str
    topology_presence_evidence: str
    topology_wire_decode_consistent: bool
    estimator_state: str
    conversion_state: str
    total_drive_path_count: int
    selected_drive_path_count: int
    selected_drive_path_indices_json: str
    selected_drive_path_index: int | None

    def row(self) -> dict[str, Any]:
        return asdict(self)


def decode_topology_message(
    message: Any,
    *,
    raw_payload: bytes,
    message_index: int,
    log_time_ns: int,
    publish_time_ns: int,
    schema_fingerprint: str | None,
) -> TopologyDecode:
    """Decode one EDP message without altering conversion eligibility."""

    descriptor = getattr(message, "DESCRIPTOR", None)
    if descriptor is None:
        raise ValueError("EDP message descriptor is unavailable")
    bindings = _joint_audit_bindings(descriptor)
    field = bindings.topology_source
    if field is None or getattr(field, "enum_type", None) is None:
        raise ValueError("EDP topology_source enum descriptor is unavailable")
    value, _, presence = _effective_field_value(message, field)
    decoded_value: int | None
    if value is _FIELD_VALUE_MISSING:
        decoded_value = None
    else:
        try:
            decoded_value = int(value)
        except (TypeError, ValueError, OverflowError):
            decoded_value = None
    enum_value = (
        field.enum_type.values_by_number.get(decoded_value)
        if decoded_value is not None
        else None
    )
    source_name = (
        str(enum_value.name) if enum_value is not None else "UNKNOWN_ENUM_VALUE"
    )
    wire_present, wire_value, occurrences = extract_top_level_varint(
        raw_payload, int(field.number)
    )
    effective_wire = wire_value if wire_present else 0
    wire_consistent = decoded_value is not None and effective_wire == decoded_value

    paths = _repeated_values(message, bindings.drive_paths) or []
    audits = [
        _audit_one_path(
            path,
            message_index=message_index,
            path_index=index,
            bindings=bindings,
        )
        for index, path in enumerate(paths)
    ]
    selected = [item.path_index for item in audits if item.is_keep_lane]
    frame = estimated_frame_from_message(
        message,
        message_index=message_index,
        log_time_ns=log_time_ns,
        publish_time_ns=publish_time_ns,
        schema_fingerprint=schema_fingerprint,
    )
    import json

    return TopologyDecode(
        message_index=message_index,
        log_time_ns=int(log_time_ns),
        publish_time_ns=int(publish_time_ns),
        source_time_ns=frame.source_time_ns,
        schema_fingerprint=schema_fingerprint,
        topology_field_number=int(field.number),
        topology_enum_type=str(field.enum_type.full_name),
        topology_wire_present=wire_present,
        topology_wire_value=wire_value,
        topology_wire_occurrence_count=occurrences,
        topology_decoded_value=decoded_value,
        topology_source_name=source_name,
        topology_presence_evidence=presence,
        topology_wire_decode_consistent=wire_consistent,
        estimator_state=frame.estimator_state,
        conversion_state=frame.conversion_state,
        total_drive_path_count=len(paths),
        selected_drive_path_count=len(selected),
        selected_drive_path_indices_json=json.dumps(selected, separators=(",", ":")),
        selected_drive_path_index=selected[0] if len(selected) == 1 else None,
    )


def stable_counts(values: Sequence[Any]) -> str:
    """Return a deterministic compact JSON distribution."""

    import json

    counts = Counter("UNAVAILABLE" if value in {None, ""} else str(value) for value in values)
    return json.dumps(dict(sorted(counts.items())), separators=(",", ":"))


def numeric_summary(values: Sequence[Any]) -> dict[str, float | int | None]:
    """Finite count and fixed quantiles for a numeric audit variable."""

    finite: list[float] = []
    for value in values:
        if value in {None, ""}:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(number):
            finite.append(number)
    if not finite:
        return {key: None for key in ("count", "min", "q05", "q25", "q50", "q75", "q95", "max")}
    array = np.asarray(finite, dtype=np.float64)
    result: dict[str, float | int | None] = {
        "count": len(array),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }
    for label, quantile in (("q05", .05), ("q25", .25), ("q50", .5), ("q75", .75), ("q95", .95)):
        result[label] = float(np.quantile(array, quantile))
    return result


def topology_interpretation(
    numeric_value: int | None,
    name: str,
    *,
    all_wire_decodes_consistent: bool,
) -> dict[str, Any]:
    """Conservative schema/code interpretation, never timing inference."""

    if name == "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY":
        classification = "sensor_topology_estimate"
        independent_sensor_topology = True
        map_or_fused = False
    elif name == "ROAD_TOPOLOGY_SOURCE_LANE_MAP":
        classification = "lane_map_topology"
        independent_sensor_topology = False
        map_or_fused = True
    elif name == "ROAD_TOPOLOGY_SOURCE_ODOMETRY":
        classification = "odometry_topology"
        independent_sensor_topology = False
        map_or_fused = False
    else:
        classification = "unknown"
        independent_sensor_topology = None
        map_or_fused = None
    return {
        "numeric_value": numeric_value,
        "enum_name": name,
        "classification": classification,
        "independent_sensor_topology": independent_sensor_topology,
        "map_or_fused_topology": map_or_fused,
        "fusion_status": "unknown",
        "shares_upstream_information_with_rlmb": "unknown",
        "enum_or_schema_decoding_defect": False if all_wire_decodes_consistent else "unknown",
        "evidence_basis": [
            "embedded protobuf enum descriptor",
            "raw-wire versus descriptor-decoded numeric equality",
            "existing strict SENSOR_TOPOLOGY conversion gate",
        ],
        "timing_used_for_semantic_classification": False,
    }


__all__ = [
    "ProtobufWireError",
    "TopologyDecode",
    "decode_topology_message",
    "extract_top_level_varint",
    "numeric_summary",
    "stable_counts",
    "topology_interpretation",
]
