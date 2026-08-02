"""Descriptor-driven inspection of direct-path Protobuf messages.

This module intentionally does not convert a production message into geometry.
It first establishes the real field structure and observed presence patterns so
that a later extractor is based on evidence rather than names borrowed from a
debug or ROS schema.

The generated report contains schema names, field metadata, enum symbols,
presence counts, and repeated-field lengths. It never exports raw coordinates
or scalar numeric payload values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from .mcap_io import (
    McapDependencyError,
    RoadMessageError,
    _iter_decoded_mcap_messages,
    _source_time_ns,
)

DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC = "/adp/estimated_drive_paths"
DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA = "Adp.Perception.EstimatedDrivePaths"

_FIELD_TYPE_NAMES = {
    1: "double",
    2: "float",
    3: "int64",
    4: "uint64",
    5: "int32",
    6: "fixed64",
    7: "fixed32",
    8: "bool",
    9: "string",
    10: "group",
    11: "message",
    12: "bytes",
    13: "uint32",
    14: "enum",
    15: "sfixed32",
    16: "sfixed64",
    17: "sint32",
    18: "sint64",
}
_LABEL_NAMES = {1: "optional", 2: "required", 3: "repeated"}
_MESSAGE_TYPE = 11
_ENUM_TYPE = 14
_BOOL_TYPE = 8
_REPEATED_LABEL = 3


@dataclass(frozen=True)
class ProtobufFieldProbe:
    """Schema and observed-presence evidence for one nested field path."""

    path: str
    number: int
    protobuf_type: str
    label: str
    message_type: str | None
    enum_type: str | None
    enum_symbols: tuple[str, ...]
    oneof: str | None
    semantic_tags: tuple[str, ...]
    present_in_sampled_messages: int
    observed_occurrences: int
    repeated_length_min: int | None
    repeated_length_median: float | None
    repeated_length_max: int | None
    observed_enum_symbols: tuple[str, ...]
    observed_boolean_values: tuple[bool, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "path": self.path,
            "number": self.number,
            "protobuf_type": self.protobuf_type,
            "label": self.label,
            "message_type": self.message_type,
            "enum_type": self.enum_type,
            "enum_symbols": list(self.enum_symbols),
            "oneof": self.oneof,
            "semantic_tags": list(self.semantic_tags),
            "present_in_sampled_messages": self.present_in_sampled_messages,
            "observed_occurrences": self.observed_occurrences,
            "repeated_length": (
                None
                if self.repeated_length_min is None
                else {
                    "minimum": self.repeated_length_min,
                    "median": self.repeated_length_median,
                    "maximum": self.repeated_length_max,
                }
            ),
            "observed_enum_symbols": list(self.observed_enum_symbols),
            "observed_boolean_values": list(self.observed_boolean_values),
        }


@dataclass(frozen=True)
class ProtobufPathSourceProbe:
    """Privacy-preserving structural report for one direct-path topic."""

    topic: str
    schema_name: str
    schema_fingerprint_sha256: str | None
    decoded_messages_seen: int
    sampled_messages: int
    source_timestamp_present_messages: int
    max_schema_depth: int
    raw_numeric_values_exported: bool
    fields: tuple[ProtobufFieldProbe, ...]

    @property
    def semantic_candidates(self) -> dict[str, list[str]]:
        """Group field paths by the semantics needed for path extraction."""

        grouped: dict[str, list[str]] = {}
        for field in self.fields:
            for tag in field.semantic_tags:
                grouped.setdefault(tag, []).append(field.path)
        return {tag: sorted(paths) for tag, paths in sorted(grouped.items())}

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable structural report."""

        return {
            "interpretation": (
                "descriptor and observed-presence audit only; no geometry is "
                "decoded into Path2D yet"
            ),
            "topic": self.topic,
            "schema_name": self.schema_name,
            "schema_fingerprint_sha256": self.schema_fingerprint_sha256,
            "decoded_messages_seen": self.decoded_messages_seen,
            "sampled_messages": self.sampled_messages,
            "source_timestamp_present_messages": (
                self.source_timestamp_present_messages
            ),
            "max_schema_depth": self.max_schema_depth,
            "raw_numeric_values_exported": self.raw_numeric_values_exported,
            "observed_presence_note": (
                "Counts prefer Protobuf ListFields() and fall back to "
                "descriptor-driven inspection for generated wrappers; proto3 "
                "scalar default values and empty repeated fields may not be "
                "listed, so zero observed presence is not proof that a schema "
                "field is unavailable"
            ),
            "semantic_candidates": self.semantic_candidates,
            "fields": [field.to_dict() for field in self.fields],
            "next_decision": (
                "confirm the keep-lane path, validity/error, timestamp, initial "
                "pose, initial curvature, segment-length, and curvature-change "
                "field paths before implementing clothoid conversion"
            ),
        }


@dataclass
class _Observation:
    """Mutable aggregation state used while sampling decoded messages."""

    sampled_message_indices: set[int]
    occurrences: int
    repeated_lengths: list[int]
    enum_symbols: set[str]
    boolean_values: set[bool]


def _descriptor_full_name(descriptor: Any) -> str | None:
    value = getattr(descriptor, "full_name", None)
    return str(value) if value else None


def _enum_symbols(field: Any) -> tuple[str, ...]:
    enum_type = getattr(field, "enum_type", None)
    values = getattr(enum_type, "values", ()) if enum_type is not None else ()
    return tuple(str(value.name) for value in values)


def _semantic_tags(path: str, field: Any) -> tuple[str, ...]:
    """Classify candidate fields conservatively from schema evidence."""

    normalized = path.lower()
    compact = normalized.replace("_", "")
    enum_text = " ".join(symbol.lower() for symbol in _enum_symbols(field))
    tags: set[str] = set()

    if any(token in normalized for token in ("timestamp", "time_stamp", ".time")):
        tags.add("source_timestamp")
    if (
        "lane_role" in normalized
        or normalized.endswith(".role")
        or "keeplane" in enum_text.replace("_", "")
    ):
        tags.add("lane_role_or_keep_lane")
    if any(
        token in normalized
        for token in (
            "error",
            "valid",
            "qualifier",
            "availability",
            "status",
        )
    ):
        tags.add("validity_or_error")
    if any(
        token in compact
        for token in ("x0", "y0", "initialx", "initialy", "startx", "starty")
    ):
        tags.add("initial_position")
    if any(
        token in compact
        for token in ("theta0", "heading0", "yaw0", "initialheading", "initialyaw")
    ):
        tags.add("initial_heading")
    if any(
        token in compact
        for token in ("curvature0", "kappa0", "initialcurvature", "initialkappa")
    ):
        tags.add("initial_curvature")
    if "segmentlength" in compact or "arclength" in compact:
        tags.add("segment_lengths")
    if any(
        token in compact
        for token in ("curvaturechange", "deltacurvature", "curvaturerate")
    ):
        tags.add("curvature_changes")
    if any(
        token in normalized
        for token in ("drive_path", "drivepath", "spline", "path_estimate")
    ):
        tags.add("path_container_or_geometry")
    return tuple(sorted(tags))


def _schema_fields(
    descriptor: Any,
    *,
    max_depth: int,
) -> dict[str, Any]:
    fields: dict[str, Any] = {}

    def visit(
        current: Any,
        *,
        prefix: str,
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        for field in getattr(current, "fields", ()):
            name = str(field.name)
            path = f"{prefix}.{name}" if prefix else name
            fields[path] = field
            message_type = getattr(field, "message_type", None)
            full_name = _descriptor_full_name(message_type)
            if (
                int(getattr(field, "type", 0)) == _MESSAGE_TYPE
                and message_type is not None
                and depth < max_depth
                and (full_name is None or full_name not in ancestors)
            ):
                next_ancestors = (
                    ancestors
                    if full_name is None
                    else ancestors | frozenset((full_name,))
                )
                visit(
                    message_type,
                    prefix=path,
                    depth=depth + 1,
                    ancestors=next_ancestors,
                )

    root_name = _descriptor_full_name(descriptor)
    visit(
        descriptor,
        prefix="",
        depth=1,
        ancestors=frozenset(() if root_name is None else (root_name,)),
    )
    return fields


_FIELD_VALUE_MISSING = object()


def _field_value(message: Any, field_name: str) -> Any:
    """Read one generated-field value from a message or wrapper object."""

    if isinstance(message, Mapping):
        return message.get(field_name, _FIELD_VALUE_MISSING)
    return getattr(message, field_name, _FIELD_VALUE_MISSING)


def _descriptor_field_is_present(
    message: Any,
    field: Any,
    value: Any,
) -> bool:
    """Approximate ``ListFields`` presence for descriptor-backed wrappers.

    Some production decoders expose ``DESCRIPTOR`` and generated attributes but
    not the complete ``google.protobuf.message.Message`` API.  This fallback
    deliberately follows normal Protobuf presence semantics where they are
    available and otherwise treats only non-default scalar values and non-empty
    repeated values as observed.  No scalar value is written to the report.
    """

    if value is _FIELD_VALUE_MISSING:
        return False

    field_name = str(field.name)
    repeated = int(getattr(field, "label", 0)) == _REPEATED_LABEL
    if repeated:
        try:
            return len(value) > 0
        except TypeError:
            return False

    containing_oneof = getattr(field, "containing_oneof", None)
    which_oneof = getattr(message, "WhichOneof", None)
    if containing_oneof is not None and callable(which_oneof):
        try:
            return which_oneof(str(containing_oneof.name)) == field_name
        except (TypeError, ValueError, NotImplementedError):
            pass

    has_field = getattr(message, "HasField", None)
    if callable(has_field):
        try:
            return bool(has_field(field_name))
        except (TypeError, ValueError, NotImplementedError):
            # Proto3 scalars without explicit presence raise ValueError.
            pass

    field_type = int(getattr(field, "type", 0))
    if field_type == _MESSAGE_TYPE:
        return value is not None

    if bool(getattr(field, "has_presence", False)):
        return value is not None

    default = getattr(field, "default_value", _FIELD_VALUE_MISSING)
    if default is _FIELD_VALUE_MISSING:
        return value is not None
    try:
        differs = value != default
        return bool(differs)
    except (TypeError, ValueError):
        return value is not None


def _listed_fields_with_descriptor(
    message: Any,
    *,
    descriptor: Any | None,
) -> Sequence[tuple[Any, Any]]:
    """Return observed fields from a full Protobuf message or thin wrapper."""

    list_fields = getattr(message, "ListFields", None)
    if callable(list_fields):
        try:
            return tuple(list_fields())
        except (TypeError, NotImplementedError):
            # Continue with descriptor-driven traversal for generated wrappers.
            pass

    effective_descriptor = (
        descriptor
        if descriptor is not None
        else getattr(message, "DESCRIPTOR", None)
    )
    if effective_descriptor is None:
        raise RoadMessageError(
            "decoded direct-path message exposes neither Protobuf ListFields() "
            "nor a usable descriptor"
        )

    observed: list[tuple[Any, Any]] = []
    for field in getattr(effective_descriptor, "fields", ()):
        value = _field_value(message, str(field.name))
        if _descriptor_field_is_present(message, field, value):
            observed.append((field, value))
    return tuple(observed)


def _enum_symbol(field: Any, value: Any) -> str:
    enum_type = getattr(field, "enum_type", None)
    values_by_number: Mapping[int, Any] = (
        getattr(enum_type, "values_by_number", {}) if enum_type is not None else {}
    )
    try:
        descriptor = values_by_number.get(int(value))
    except (TypeError, ValueError, OverflowError):
        descriptor = None
    return str(descriptor.name) if descriptor is not None else f"UNKNOWN_{value}"


def _observe_message(
    message: Any,
    *,
    sample_index: int,
    observations: dict[str, _Observation],
    descriptor: Any | None = None,
    prefix: str = "",
    max_depth: int,
    depth: int = 1,
    max_repeated_items: int = 16,
) -> None:
    for field, value in _listed_fields_with_descriptor(
        message,
        descriptor=descriptor,
    ):
        name = str(field.name)
        path = f"{prefix}.{name}" if prefix else name
        observation = observations.setdefault(
            path,
            _Observation(set(), 0, [], set(), set()),
        )
        observation.sampled_message_indices.add(sample_index)
        observation.occurrences += 1

        repeated = int(getattr(field, "label", 0)) == _REPEATED_LABEL
        values: list[Any]
        if repeated:
            values = list(value)
            observation.repeated_lengths.append(len(values))
        else:
            values = [value]

        field_type = int(getattr(field, "type", 0))
        if field_type == _ENUM_TYPE:
            observation.enum_symbols.update(
                _enum_symbol(field, item) for item in values
            )
        elif field_type == _BOOL_TYPE:
            observation.boolean_values.update(bool(item) for item in values)
        elif field_type == _MESSAGE_TYPE and depth < max_depth:
            for item in values[:max_repeated_items]:
                _observe_message(
                    item,
                    sample_index=sample_index,
                    observations=observations,
                    descriptor=getattr(field, "message_type", None),
                    prefix=path,
                    max_depth=max_depth,
                    depth=depth + 1,
                    max_repeated_items=max_repeated_items,
                )


def _schema_fingerprint(descriptor: Any) -> str | None:
    file_descriptor = getattr(descriptor, "file", None)
    serialized = getattr(file_descriptor, "serialized_pb", None)
    if not isinstance(serialized, bytes):
        return None
    return hashlib.sha256(serialized).hexdigest()


def probe_decoded_protobuf_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    topic: str = DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    expected_schema_name: str = DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    max_messages: int = 20,
    max_schema_depth: int = 6,
) -> ProtobufPathSourceProbe:
    """Inspect decoded messages without exporting numeric payload values."""

    if not topic:
        raise ValueError("topic must not be empty")
    if max_messages < 1:
        raise ValueError("max_messages must be at least one")
    if max_schema_depth < 1:
        raise ValueError("max_schema_depth must be at least one")

    samples: list[Any] = []
    decoded_seen = 0
    schema_name: str | None = None
    for schema, channel, _, decoded in decoded_messages:
        if str(getattr(channel, "topic", "")) != topic:
            continue
        decoded_seen += 1
        current_schema = str(getattr(schema, "name", ""))
        if current_schema != expected_schema_name:
            raise RoadMessageError(
                f'topic "{topic}" uses schema "{current_schema}", '
                f'expected "{expected_schema_name}"'
            )
        if str(getattr(channel, "message_encoding", "")).lower() != "protobuf":
            raise RoadMessageError(f'topic "{topic}" is not encoded as Protobuf')
        schema_name = current_schema
        if len(samples) < max_messages:
            samples.append(decoded)
        if len(samples) >= max_messages:
            break

    if not samples or schema_name is None:
        raise RoadMessageError(f'no decodable Protobuf messages found on "{topic}"')

    descriptor = getattr(samples[0], "DESCRIPTOR", None)
    if descriptor is None:
        raise RoadMessageError(
            f'decoded messages on "{topic}" do not expose a Protobuf descriptor'
        )

    fields_by_path = _schema_fields(descriptor, max_depth=max_schema_depth)
    observations: dict[str, _Observation] = {}
    source_timestamp_present = 0
    for sample_index, message in enumerate(samples):
        if _source_time_ns(message) is not None:
            source_timestamp_present += 1
        _observe_message(
            message,
            sample_index=sample_index,
            observations=observations,
            descriptor=descriptor,
            max_depth=max_schema_depth,
        )

    output_fields: list[ProtobufFieldProbe] = []
    for path, field in sorted(fields_by_path.items()):
        observation = observations.get(
            path,
            _Observation(set(), 0, [], set(), set()),
        )
        repeated_lengths = observation.repeated_lengths
        message_type = _descriptor_full_name(getattr(field, "message_type", None))
        enum_type = _descriptor_full_name(getattr(field, "enum_type", None))
        containing_oneof = getattr(field, "containing_oneof", None)
        output_fields.append(
            ProtobufFieldProbe(
                path=path,
                number=int(field.number),
                protobuf_type=_FIELD_TYPE_NAMES.get(
                    int(getattr(field, "type", 0)),
                    f"unknown_{getattr(field, 'type', 0)}",
                ),
                label=_LABEL_NAMES.get(
                    int(getattr(field, "label", 0)),
                    f"unknown_{getattr(field, 'label', 0)}",
                ),
                message_type=message_type,
                enum_type=enum_type,
                enum_symbols=_enum_symbols(field),
                oneof=(
                    None
                    if containing_oneof is None
                    else str(containing_oneof.name)
                ),
                semantic_tags=_semantic_tags(path, field),
                present_in_sampled_messages=len(
                    observation.sampled_message_indices
                ),
                observed_occurrences=observation.occurrences,
                repeated_length_min=(
                    min(repeated_lengths) if repeated_lengths else None
                ),
                repeated_length_median=(
                    float(median(repeated_lengths)) if repeated_lengths else None
                ),
                repeated_length_max=(
                    max(repeated_lengths) if repeated_lengths else None
                ),
                observed_enum_symbols=tuple(sorted(observation.enum_symbols)),
                observed_boolean_values=tuple(
                    sorted(observation.boolean_values)
                ),
            )
        )

    return ProtobufPathSourceProbe(
        topic=topic,
        schema_name=schema_name,
        schema_fingerprint_sha256=_schema_fingerprint(descriptor),
        decoded_messages_seen=decoded_seen,
        sampled_messages=len(samples),
        source_timestamp_present_messages=source_timestamp_present,
        max_schema_depth=max_schema_depth,
        raw_numeric_values_exported=False,
        fields=tuple(output_fields),
    )


def inspect_protobuf_path_source(
    path: str | Path,
    *,
    topic: str = DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    expected_schema_name: str = DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    max_messages: int = 20,
    max_schema_depth: int = 6,
) -> ProtobufPathSourceProbe:
    """Decode and structurally inspect one Protobuf path-source topic."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"MCAP file not found: {source}")
    try:
        decoded = _iter_decoded_mcap_messages(source, topics=(topic,))
        return probe_decoded_protobuf_messages(
            decoded,
            topic=topic,
            expected_schema_name=expected_schema_name,
            max_messages=max_messages,
            max_schema_depth=max_schema_depth,
        )
    except ImportError as error:
        raise McapDependencyError(
            'MCAP support is not installed. Run: pip install -e ".[mcap]"'
        ) from error


def save_protobuf_path_source_probe(
    report: ProtobufPathSourceProbe,
    path: str | Path,
) -> Path:
    """Write one structural report as formatted JSON."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(report.to_dict(), stream, indent=2)
        stream.write("\n")
    return destination
