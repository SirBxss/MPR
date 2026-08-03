"""Descriptor-driven structural and joint-semantic direct-path inspection.

This module intentionally does not convert a production message into geometry.
It first establishes the real field structure and observed presence patterns so
that a later extractor is based on evidence rather than names borrowed from a
debug or ROS schema.

The generated report contains schema names, field metadata, enum symbols,
presence counts, repeated-field lengths, and privacy-safe per-path tuples. It
checks role, error, model presence, finiteness, ordering, and count consistency
jointly without exporting coordinates or scalar numeric payload values.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any

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
_DEFAULT_MAX_REPEATED_ITEMS_PER_FIELD = 64


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
    is_map: bool
    semantic_tags: tuple[str, ...]
    present_in_sampled_messages: int
    observed_occurrences: int
    presence_evidence: tuple[str, ...]
    repeated_length_min: int | None
    repeated_length_median: float | None
    repeated_length_max: int | None
    nested_message_items_inspected: int | None
    nested_message_items_truncated: int | None
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
            "is_map": self.is_map,
            "semantic_tags": list(self.semantic_tags),
            "present_in_sampled_messages": self.present_in_sampled_messages,
            "observed_occurrences": self.observed_occurrences,
            "presence_evidence": list(self.presence_evidence),
            "repeated_length": (
                None
                if self.repeated_length_min is None
                else {
                    "minimum": self.repeated_length_min,
                    "median": self.repeated_length_median,
                    "maximum": self.repeated_length_max,
                }
            ),
            "nested_message_items_inspected": (self.nested_message_items_inspected),
            "nested_message_items_truncated": (self.nested_message_items_truncated),
            "observed_enum_symbols": list(self.observed_enum_symbols),
            "observed_boolean_values": list(self.observed_boolean_values),
        }


@dataclass(frozen=True)
class ProtobufPathSemanticTuple:
    """Privacy-safe joint evidence for one path in one sampled message."""

    message_index: int
    path_index: int
    role_symbol: str
    role_value_source: str
    error_symbol: str
    error_value_source: str
    model_parameters_present: bool
    model_parameters_presence_evidence: str
    model_parameters_optional_flag_present: bool
    model_parameters_optional_flag_value: bool | None
    model_parameters_optional_flag_presence_evidence: str
    segment_starts_count: int | None
    curvature_change_count: int | None
    drive_path_confidences_count: int | None
    drive_path_confidences_all_finite: bool | None
    lane_topology_ids_count: int | None
    index_0_present: bool
    index_0_presence_evidence: str
    initial_parameter_fields_available: tuple[str, ...]
    initial_parameters_all_finite: bool | None
    segment_starts_all_finite: bool | None
    segment_starts_strictly_increasing: bool | None
    curvature_changes_all_finite: bool | None
    interval_count_matches: bool | None
    model_structure_valid: bool
    is_keep_lane: bool
    is_no_error: bool
    is_keep_lane_no_error: bool
    is_joint_audit_candidate: bool
    candidate_status: str
    failure_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return joint path evidence without numeric model parameters."""

        return {
            "message_index": self.message_index,
            "path_index": self.path_index,
            "role": self.role_symbol,
            "role_value_source": self.role_value_source,
            "error": self.error_symbol,
            "error_value_source": self.error_value_source,
            "model_parameters_present": self.model_parameters_present,
            "model_parameters_presence_evidence": (
                self.model_parameters_presence_evidence
            ),
            "model_parameters_optional_flag_present": (
                self.model_parameters_optional_flag_present
            ),
            "model_parameters_optional_flag_value": (
                self.model_parameters_optional_flag_value
            ),
            "model_parameters_optional_flag_presence_evidence": (
                self.model_parameters_optional_flag_presence_evidence
            ),
            "array_counts": {
                "segment_starts": self.segment_starts_count,
                "curvature_change": self.curvature_change_count,
                "drive_path_confidences": self.drive_path_confidences_count,
                "lane_topology_ids": self.lane_topology_ids_count,
            },
            "drive_path_confidences_all_finite": (
                self.drive_path_confidences_all_finite
            ),
            "index_0_present": self.index_0_present,
            "index_0_presence_evidence": self.index_0_presence_evidence,
            "initial_parameter_fields_available": list(
                self.initial_parameter_fields_available
            ),
            "checks": {
                "initial_parameters_all_finite": (self.initial_parameters_all_finite),
                "segment_starts_all_finite": (self.segment_starts_all_finite),
                "segment_starts_strictly_increasing": (
                    self.segment_starts_strictly_increasing
                ),
                "curvature_changes_all_finite": (self.curvature_changes_all_finite),
                "interval_count_matches": self.interval_count_matches,
                "model_structure_valid": self.model_structure_valid,
            },
            "is_keep_lane": self.is_keep_lane,
            "is_no_error": self.is_no_error,
            "is_keep_lane_no_error": self.is_keep_lane_no_error,
            "is_joint_audit_candidate": (self.is_joint_audit_candidate),
            "candidate_status": self.candidate_status,
            "failure_codes": list(self.failure_codes),
        }


@dataclass(frozen=True)
class ProtobufMessageSemanticAudit:
    """Derived joint-path counts for one sampled root message."""

    message_index: int
    source_timestamp_present: bool
    topology_source_symbol: str | None
    total_path_count: int
    inspected_path_count: int
    truncated_path_count: int
    keep_lane_path_count: int
    no_error_path_count: int
    keep_lane_no_error_path_count: int
    structurally_valid_keep_lane_no_error_path_count: int
    joint_audit_candidate_path_count: int
    safe_for_later_conversion: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe message summary."""

        return {
            "message_index": self.message_index,
            "source_timestamp_present": self.source_timestamp_present,
            "topology_source": self.topology_source_symbol,
            "total_path_count": self.total_path_count,
            "inspected_path_count": self.inspected_path_count,
            "truncated_path_count": self.truncated_path_count,
            "keep_lane_path_count": self.keep_lane_path_count,
            "no_error_path_count": self.no_error_path_count,
            "keep_lane_no_error_path_count": (self.keep_lane_no_error_path_count),
            "structurally_valid_keep_lane_no_error_path_count": (
                self.structurally_valid_keep_lane_no_error_path_count
            ),
            "joint_audit_candidate_path_count": (self.joint_audit_candidate_path_count),
            "safe_for_later_conversion": self.safe_for_later_conversion,
        }


@dataclass(frozen=True)
class ProtobufJointPathSemanticAudit:
    """Joint role/error/model audit for the sampled direct paths."""

    status: str
    missing_required_fields: tuple[str, ...]
    field_bindings: tuple[tuple[str, str | None], ...]
    messages: tuple[ProtobufMessageSemanticAudit, ...]
    paths: tuple[ProtobufPathSemanticTuple, ...]
    role_counts: tuple[tuple[str, int], ...]
    error_counts: tuple[tuple[str, int], ...]
    role_error_counts: tuple[tuple[str, str, int], ...]
    failure_counts: tuple[tuple[str, int], ...]
    summary_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        """Return the privacy-safe joint semantic audit."""

        return {
            "status": self.status,
            "interpretation": (
                "joint role/error/model-structure audit only; candidate paths "
                "are not converted to geometry and are not training data"
            ),
            "raw_numeric_values_exported": False,
            "candidate_definitions": {
                "keep_lane_no_error": (
                    "the same decoded path has LANE_ROLE_KEEP_LANE and an "
                    "enum symbol ending in _NO_ERROR"
                ),
                "model_structure_valid": (
                    "model parameters are present; the four initial scalar "
                    "fields are available and finite; segment starts and "
                    "curvature changes are finite; segment starts are "
                    "strictly increasing; and interval counts match"
                ),
                "joint_audit_candidate": (
                    "keep_lane_no_error and model_structure_valid are true, "
                    "and model_parameters_optional_flag is explicitly true"
                ),
            },
            "model_flag_warning": (
                "model_parameters_optional_flag is reported literally; its "
                "domain meaning still requires authoritative documentation"
            ),
            "candidate_warning": (
                "a joint_audit_candidate is necessary but not sufficient for "
                "conversion; spline semantics, frame, units, sign conventions, "
                "and signal independence remain unresolved"
            ),
            "missing_required_fields": list(self.missing_required_fields),
            "field_bindings": dict(self.field_bindings),
            "summary": dict(self.summary_counts),
            "paths_by_role": dict(self.role_counts),
            "paths_by_error": dict(self.error_counts),
            "failures_by_code": dict(self.failure_counts),
            "role_error_combinations": [
                {"role": role, "error": error, "count": count}
                for role, error, count in self.role_error_counts
            ],
            "messages": [message.to_dict() for message in self.messages],
            "paths": [path.to_dict() for path in self.paths],
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
    max_repeated_items_per_field: int
    raw_numeric_values_exported: bool
    fields: tuple[ProtobufFieldProbe, ...]
    joint_path_semantics: ProtobufJointPathSemanticAudit

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
            "max_repeated_items_per_field": (self.max_repeated_items_per_field),
            "raw_numeric_values_exported": self.raw_numeric_values_exported,
            "observed_presence_note": (
                "Counts prefer Protobuf ListFields() and fall back to "
                "descriptor-driven inspection for generated wrappers; proto3 "
                "scalar default values and empty repeated fields may not be "
                "listed, descriptor_inferred presence is less certain than "
                "list_fields presence, and repeated-length summaries are "
                "conditional on observed non-empty containers; zero observed "
                "presence is not proof that a schema field is unavailable"
            ),
            "map_field_note": (
                "map containers and lengths are reported, but their synthetic "
                "entry messages are not recursively inspected"
            ),
            "semantic_candidates": self.semantic_candidates,
            "fields": [field.to_dict() for field in self.fields],
            "joint_path_semantics": self.joint_path_semantics.to_dict(),
            "next_decision": (
                "review joint keep-lane/no-error/model-structure evidence, then "
                "confirm segment-start, curvature-change, coordinate-frame, "
                "unit, sign, and index_0 semantics before implementing "
                "clothoid conversion"
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
    presence_evidence: set[str]
    nested_message_items_inspected: int
    nested_message_items_truncated: int


def _descriptor_full_name(descriptor: Any) -> str | None:
    value = getattr(descriptor, "full_name", None)
    return str(value) if value else None


def _enum_symbols(field: Any) -> tuple[str, ...]:
    enum_type = getattr(field, "enum_type", None)
    values = getattr(enum_type, "values", ()) if enum_type is not None else ()
    return tuple(str(value.name) for value in values)


def _field_is_map(field: Any) -> bool:
    """Return whether a repeated message field represents a Protobuf map."""

    message_type = getattr(field, "message_type", None)
    get_options = getattr(message_type, "GetOptions", None)
    if not callable(get_options):
        return False
    try:
        options = get_options()
    except (TypeError, NotImplementedError):
        return False
    return bool(getattr(options, "map_entry", False))


def _semantic_tags(path: str, field: Any) -> tuple[str, ...]:
    """Classify candidate fields conservatively from schema evidence."""

    normalized = path.lower()
    leaf = normalized.rsplit(".", maxsplit=1)[-1]
    leaf_compact = leaf.replace("_", "")
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
    if leaf_compact in {
        "x0",
        "y0",
        "initialx",
        "initialy",
        "startx",
        "starty",
    }:
        tags.add("initial_position")
    if leaf_compact in {
        "theta0",
        "heading0",
        "yaw0",
        "initialheading",
        "initialyaw",
    }:
        tags.add("initial_heading")
    if leaf_compact in {
        "curvature0",
        "kappa0",
        "initialcurvature",
        "initialkappa",
    }:
        tags.add("initial_curvature")
    if "segmentlength" in leaf_compact or "arclength" in leaf_compact:
        tags.add("segment_lengths")
    if leaf_compact in {"segmentstarts", "segmentboundaries"}:
        tags.add("segment_starts_or_boundaries")
    if any(
        token in leaf_compact
        for token in ("curvaturechange", "deltacurvature", "curvaturerate")
    ):
        tags.add("curvature_changes")
    if leaf_compact in {"index0", "startindex", "anchorindex"}:
        tags.add("index_or_anchor")
    if leaf_compact in {"topologysource", "roadtopologysource"}:
        tags.add("topology_source")
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


def _descriptor_boolean_flag(field: Any, name: str) -> bool | None:
    """Read a bool-like descriptor property across Protobuf runtimes.

    Python Protobuf 7 removed ``FieldDescriptor.label``.  Its replacements are
    normally bool properties, while some descriptor-backed wrappers expose
    equivalent zero-argument methods.  Returning ``None`` distinguishes an
    unavailable API from a legitimate ``False`` value.
    """

    try:
        value = getattr(field, name)
    except (AttributeError, NotImplementedError):
        return None
    if callable(value):
        try:
            value = value()
        except (TypeError, NotImplementedError):
            return None
    if value is None:
        return None
    return bool(value)


def _legacy_field_label(field: Any) -> int | None:
    """Return the pre-Protobuf-7 numeric field label when available."""

    try:
        value = field.label
    except (AttributeError, NotImplementedError):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _field_is_repeated(field: Any) -> bool:
    """Return repeated cardinality using the modern API with legacy fallback."""

    modern = _descriptor_boolean_flag(field, "is_repeated")
    if modern is not None:
        return modern
    return _legacy_field_label(field) == _REPEATED_LABEL


def _field_cardinality_name(field: Any) -> str:
    """Return a stable cardinality name across Protobuf 4 through 7."""

    repeated = _descriptor_boolean_flag(field, "is_repeated")
    required = _descriptor_boolean_flag(field, "is_required")
    if repeated is True:
        return "repeated"
    if required is True:
        return "required"

    # Prefer the modern properties even when an older runtime still exposes
    # deprecated ``label`` and would warn when it is accessed.
    if repeated is not None or required is not None:
        return "optional"

    legacy_label = _legacy_field_label(field)
    if legacy_label is not None:
        return _LABEL_NAMES.get(legacy_label, f"unknown_{legacy_label}")
    return "unknown"


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
    repeated = _field_is_repeated(field)
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
) -> Sequence[tuple[Any, Any, str]]:
    """Return observed fields from a full Protobuf message or thin wrapper."""

    list_fields = getattr(message, "ListFields", None)
    if callable(list_fields):
        try:
            return tuple(
                (field, value, "list_fields") for field, value in list_fields()
            )
        except (TypeError, NotImplementedError):
            # Continue with descriptor-driven traversal for generated wrappers.
            pass

    effective_descriptor = (
        descriptor if descriptor is not None else getattr(message, "DESCRIPTOR", None)
    )
    if effective_descriptor is None:
        raise RoadMessageError(
            "decoded direct-path message exposes neither Protobuf ListFields() "
            "nor a usable descriptor"
        )

    observed: list[tuple[Any, Any, str]] = []
    for field in getattr(effective_descriptor, "fields", ()):
        value = _field_value(message, str(field.name))
        if _descriptor_field_is_present(message, field, value):
            observed.append((field, value, "descriptor_inferred"))
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
    # Do not leak an unknown numeric payload through a generated symbol name.
    return str(descriptor.name) if descriptor is not None else "UNKNOWN_ENUM_VALUE"


@dataclass(frozen=True)
class _JointAuditBindings:
    """Exact production fields used by the v0.3.7 joint audit."""

    drive_paths: Any | None
    topology_source: Any | None
    role: Any | None
    error: Any | None
    model_parameters: Any | None
    model_parameters_optional_flag: Any | None
    drive_path_confidences: Any | None
    lane_topology_ids: Any | None
    x_0: Any | None
    y_0: Any | None
    theta_0: Any | None
    curvature_0: Any | None
    segment_starts: Any | None
    curvature_change: Any | None
    index_0: Any | None

    def public_paths(self) -> tuple[tuple[str, str | None], ...]:
        """Return schema paths only, never message values."""

        def present(field: Any | None, path: str) -> str | None:
            return path if field is not None else None

        return (
            ("drive_paths", present(self.drive_paths, "drive_paths")),
            (
                "topology_source",
                present(self.topology_source, "topology_source"),
            ),
            ("role", present(self.role, "drive_paths.role")),
            ("error", present(self.error, "drive_paths.error")),
            (
                "model_parameters",
                present(
                    self.model_parameters,
                    "drive_paths.model_parameters",
                ),
            ),
            (
                "model_parameters_optional_flag",
                present(
                    self.model_parameters_optional_flag,
                    "drive_paths.model_parameters_optional_flag",
                ),
            ),
            (
                "drive_path_confidences",
                present(
                    self.drive_path_confidences,
                    "drive_paths.drive_path_confidences",
                ),
            ),
            (
                "lane_topology_ids",
                present(
                    self.lane_topology_ids,
                    "drive_paths.lane_topology_ids",
                ),
            ),
            (
                "x_0",
                present(
                    self.x_0,
                    "drive_paths.model_parameters.x_0",
                ),
            ),
            (
                "y_0",
                present(
                    self.y_0,
                    "drive_paths.model_parameters.y_0",
                ),
            ),
            (
                "theta_0",
                present(
                    self.theta_0,
                    "drive_paths.model_parameters.theta_0",
                ),
            ),
            (
                "curvature_0",
                present(
                    self.curvature_0,
                    "drive_paths.model_parameters.curvature_0",
                ),
            ),
            (
                "segment_starts",
                present(
                    self.segment_starts,
                    "drive_paths.model_parameters.segment_starts",
                ),
            ),
            (
                "curvature_change",
                present(
                    self.curvature_change,
                    "drive_paths.model_parameters.curvature_change",
                ),
            ),
            (
                "index_0",
                present(
                    self.index_0,
                    "drive_paths.model_parameters.index_0",
                ),
            ),
        )

    def missing_required(self) -> tuple[str, ...]:
        """Return fields needed for a strict joint audit candidate."""

        required = {
            "drive_paths": self.drive_paths,
            "role": self.role,
            "error": self.error,
            "model_parameters": self.model_parameters,
            "model_parameters_optional_flag": (self.model_parameters_optional_flag),
            "x_0": self.x_0,
            "y_0": self.y_0,
            "theta_0": self.theta_0,
            "curvature_0": self.curvature_0,
            "segment_starts": self.segment_starts,
            "curvature_change": self.curvature_change,
        }
        return tuple(sorted(name for name, field in required.items() if field is None))


def _field_by_name(descriptor: Any | None, name: str) -> Any | None:
    if descriptor is None:
        return None
    for field in getattr(descriptor, "fields", ()):
        if str(getattr(field, "name", "")) == name:
            return field
    return None


def _joint_audit_bindings(root_descriptor: Any) -> _JointAuditBindings:
    drive_paths = _field_by_name(root_descriptor, "drive_paths")
    path_descriptor = getattr(drive_paths, "message_type", None)
    model_parameters = _field_by_name(path_descriptor, "model_parameters")
    model_descriptor = getattr(model_parameters, "message_type", None)
    return _JointAuditBindings(
        drive_paths=drive_paths,
        topology_source=_field_by_name(root_descriptor, "topology_source"),
        role=_field_by_name(path_descriptor, "role"),
        error=_field_by_name(path_descriptor, "error"),
        model_parameters=model_parameters,
        model_parameters_optional_flag=_field_by_name(
            path_descriptor,
            "model_parameters_optional_flag",
        ),
        drive_path_confidences=_field_by_name(
            path_descriptor,
            "drive_path_confidences",
        ),
        lane_topology_ids=_field_by_name(
            path_descriptor,
            "lane_topology_ids",
        ),
        x_0=_field_by_name(model_descriptor, "x_0"),
        y_0=_field_by_name(model_descriptor, "y_0"),
        theta_0=_field_by_name(model_descriptor, "theta_0"),
        curvature_0=_field_by_name(model_descriptor, "curvature_0"),
        segment_starts=_field_by_name(model_descriptor, "segment_starts"),
        curvature_change=_field_by_name(model_descriptor, "curvature_change"),
        index_0=_field_by_name(model_descriptor, "index_0"),
    )


def _effective_field_value(
    message: Any,
    field: Any | None,
) -> tuple[Any, bool, str]:
    """Read a value plus exact/inferred/default presence evidence."""

    if field is None:
        return _FIELD_VALUE_MISSING, False, "schema_field_unavailable"
    name = str(field.name)
    value = _field_value(message, name)
    if value is _FIELD_VALUE_MISSING:
        return value, False, "value_unavailable"

    descriptor = getattr(message, "DESCRIPTOR", None)
    try:
        listed = _listed_fields_with_descriptor(
            message,
            descriptor=descriptor,
        )
    except RoadMessageError:
        listed = ()
    for listed_field, _, evidence in listed:
        if str(getattr(listed_field, "name", "")) == name:
            return value, True, evidence

    has_field = getattr(message, "HasField", None)
    if callable(has_field):
        try:
            if bool(has_field(name)):
                return value, True, "has_field"
            return value, False, "explicit_absent"
        except (TypeError, ValueError, NotImplementedError):
            pass

    if _field_is_repeated(field):
        return value, False, "implicit_empty"
    if int(getattr(field, "type", 0)) == _MESSAGE_TYPE:
        return value, False, "message_presence_unconfirmed"
    if _descriptor_boolean_flag(field, "has_presence") is True:
        return value, False, "explicit_absent"
    return value, False, "implicit_default"


def _effective_enum_symbol(
    message: Any,
    field: Any | None,
) -> tuple[str, str]:
    value, present, evidence = _effective_field_value(message, field)
    if value is _FIELD_VALUE_MISSING or evidence in {
        "explicit_absent",
        "schema_field_unavailable",
        "value_unavailable",
    }:
        return "UNAVAILABLE_ENUM_VALUE", evidence
    if field is None:
        return "UNAVAILABLE_ENUM_VALUE", evidence
    source = evidence if present else "implicit_default"
    return _enum_symbol(field, value), source


def _repeated_values(message: Any, field: Any | None) -> list[Any] | None:
    if field is None:
        return None
    value = _field_value(message, str(field.name))
    if value is _FIELD_VALUE_MISSING or value is None:
        return None
    try:
        return list(value)
    except TypeError:
        return None


def _is_finite_numeric(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _all_finite(values: Sequence[Any] | None) -> bool | None:
    if values is None:
        return None
    return all(_is_finite_numeric(value) for value in values)


def _strictly_increasing(values: Sequence[Any] | None) -> bool | None:
    if values is None:
        return None
    if len(values) < 2 or not all(_is_finite_numeric(value) for value in values):
        return False
    return all(float(left) < float(right) for left, right in pairwise(values))


def _audit_one_path(
    path_message: Any,
    *,
    message_index: int,
    path_index: int,
    bindings: _JointAuditBindings,
) -> ProtobufPathSemanticTuple:
    role_symbol, role_source = _effective_enum_symbol(path_message, bindings.role)
    error_symbol, error_source = _effective_enum_symbol(path_message, bindings.error)

    model_value, model_present, model_evidence = _effective_field_value(
        path_message,
        bindings.model_parameters,
    )
    model_usable = (
        model_present
        and model_value is not _FIELD_VALUE_MISSING
        and model_value is not None
    )

    flag_value_raw, flag_present, flag_evidence = _effective_field_value(
        path_message,
        bindings.model_parameters_optional_flag,
    )
    flag_value = (
        None if flag_value_raw is _FIELD_VALUE_MISSING else bool(flag_value_raw)
    )

    confidence_values = _repeated_values(
        path_message,
        bindings.drive_path_confidences,
    )
    topology_ids = _repeated_values(path_message, bindings.lane_topology_ids)

    initial_names = ("x_0", "y_0", "theta_0", "curvature_0")
    initial_fields = tuple(getattr(bindings, name) for name in initial_names)
    available_initial_names: list[str] = []
    initial_finite_checks: list[bool] = []
    segment_starts: list[Any] | None = None
    curvature_change: list[Any] | None = None
    index_present = False
    index_evidence = "model_parameters_unavailable"

    if model_usable:
        for name, field in zip(initial_names, initial_fields):
            value, present, evidence = _effective_field_value(model_value, field)
            usable_default = evidence == "implicit_default"
            if value is not _FIELD_VALUE_MISSING and (present or usable_default):
                available_initial_names.append(name)
                initial_finite_checks.append(_is_finite_numeric(value))
        segment_starts = _repeated_values(model_value, bindings.segment_starts)
        curvature_change = _repeated_values(
            model_value,
            bindings.curvature_change,
        )
        _, index_present, index_evidence = _effective_field_value(
            model_value,
            bindings.index_0,
        )

    initial_all_finite = (
        (
            len(available_initial_names) == len(initial_names)
            and all(initial_finite_checks)
        )
        if model_usable
        else None
    )
    starts_all_finite = _all_finite(segment_starts)
    starts_increasing = _strictly_increasing(segment_starts)
    changes_all_finite = _all_finite(curvature_change)
    interval_count_matches = (
        None
        if segment_starts is None or curvature_change is None
        else len(segment_starts) >= 2
        and len(curvature_change) == len(segment_starts) - 1
    )
    model_structure_valid = bool(
        model_usable
        and initial_all_finite is True
        and segment_starts is not None
        and len(segment_starts) >= 2
        and starts_all_finite is True
        and starts_increasing is True
        and curvature_change is not None
        and changes_all_finite is True
        and interval_count_matches is True
    )

    is_keep_lane = role_symbol == "LANE_ROLE_KEEP_LANE"
    is_no_error = error_symbol == "DRIVE_PATH_ERROR_NO_ERROR"
    is_keep_lane_no_error = is_keep_lane and is_no_error
    is_joint_candidate = bool(
        is_keep_lane_no_error and model_structure_valid and flag_value is True
    )

    failure_codes: list[str] = []
    if role_symbol in {"UNAVAILABLE_ENUM_VALUE", "UNKNOWN_ENUM_VALUE"}:
        failure_codes.append("role_unavailable_or_unknown")
    elif not is_keep_lane:
        failure_codes.append("not_keep_lane")
    elif error_symbol in {"UNAVAILABLE_ENUM_VALUE", "UNKNOWN_ENUM_VALUE"}:
        failure_codes.append("error_unavailable_or_unknown")
    elif not is_no_error:
        failure_codes.append("drive_path_error")
    else:
        if not model_usable:
            failure_codes.append("model_parameters_absent")
        if model_usable and len(available_initial_names) != len(initial_names):
            failure_codes.append("initial_parameters_unavailable")
        if (
            model_usable
            and initial_all_finite is False
            and (len(available_initial_names) == len(initial_names))
        ):
            failure_codes.append("non_finite_initial_parameters")
        if segment_starts is None:
            failure_codes.append("segment_starts_unavailable")
        elif len(segment_starts) < 2:
            failure_codes.append("segment_starts_too_short")
        elif starts_all_finite is False:
            failure_codes.append("non_finite_segment_starts")
        elif starts_increasing is False:
            failure_codes.append("non_increasing_segment_starts")
        if curvature_change is None:
            failure_codes.append("curvature_change_unavailable")
        elif changes_all_finite is False:
            failure_codes.append("non_finite_curvature_change")
        if interval_count_matches is False:
            failure_codes.append("interval_count_mismatch")
        if flag_value is not True:
            failure_codes.append("model_parameters_optional_flag_not_true")

    if is_joint_candidate:
        candidate_status = "joint_audit_candidate"
    elif not is_keep_lane:
        candidate_status = "excluded_non_keep_lane"
    elif not is_no_error:
        candidate_status = "excluded_error"
    elif not model_structure_valid:
        candidate_status = "failed_model_structure"
    else:
        candidate_status = "failed_model_flag"

    return ProtobufPathSemanticTuple(
        message_index=message_index,
        path_index=path_index,
        role_symbol=role_symbol,
        role_value_source=role_source,
        error_symbol=error_symbol,
        error_value_source=error_source,
        model_parameters_present=model_usable,
        model_parameters_presence_evidence=model_evidence,
        model_parameters_optional_flag_present=flag_present,
        model_parameters_optional_flag_value=flag_value,
        model_parameters_optional_flag_presence_evidence=flag_evidence,
        segment_starts_count=(None if segment_starts is None else len(segment_starts)),
        curvature_change_count=(
            None if curvature_change is None else len(curvature_change)
        ),
        drive_path_confidences_count=(
            None if confidence_values is None else len(confidence_values)
        ),
        drive_path_confidences_all_finite=_all_finite(confidence_values),
        lane_topology_ids_count=(None if topology_ids is None else len(topology_ids)),
        index_0_present=index_present,
        index_0_presence_evidence=index_evidence,
        initial_parameter_fields_available=tuple(available_initial_names),
        initial_parameters_all_finite=initial_all_finite,
        segment_starts_all_finite=starts_all_finite,
        segment_starts_strictly_increasing=starts_increasing,
        curvature_changes_all_finite=changes_all_finite,
        interval_count_matches=interval_count_matches,
        model_structure_valid=model_structure_valid,
        is_keep_lane=is_keep_lane,
        is_no_error=is_no_error,
        is_keep_lane_no_error=is_keep_lane_no_error,
        is_joint_audit_candidate=is_joint_candidate,
        candidate_status=candidate_status,
        failure_codes=tuple(failure_codes),
    )


def _audit_joint_path_semantics(
    samples: Sequence[Any],
    *,
    descriptor: Any,
    max_paths_per_message: int,
) -> ProtobufJointPathSemanticAudit:
    bindings = _joint_audit_bindings(descriptor)
    missing_required = bindings.missing_required()
    audited_paths: list[ProtobufPathSemanticTuple] = []
    audited_messages: list[ProtobufMessageSemanticAudit] = []

    for message_index, message in enumerate(samples):
        path_values = _repeated_values(message, bindings.drive_paths) or []
        inspected_values = path_values[:max_paths_per_message]
        message_paths = [
            _audit_one_path(
                path,
                message_index=message_index,
                path_index=path_index,
                bindings=bindings,
            )
            for path_index, path in enumerate(inspected_values)
        ]
        audited_paths.extend(message_paths)

        topology_symbol = None
        if bindings.topology_source is not None:
            topology_symbol, _ = _effective_enum_symbol(
                message,
                bindings.topology_source,
            )
        keep_lane_count = sum(path.is_keep_lane for path in message_paths)
        no_error_count = sum(path.is_no_error for path in message_paths)
        joint_count = sum(path.is_keep_lane_no_error for path in message_paths)
        structurally_valid_joint_count = sum(
            path.is_keep_lane_no_error and path.model_structure_valid
            for path in message_paths
        )
        candidate_count = sum(path.is_joint_audit_candidate for path in message_paths)
        truncated = max(0, len(path_values) - len(inspected_values))
        audited_messages.append(
            ProtobufMessageSemanticAudit(
                message_index=message_index,
                source_timestamp_present=_source_time_ns(message) is not None,
                topology_source_symbol=topology_symbol,
                total_path_count=len(path_values),
                inspected_path_count=len(inspected_values),
                truncated_path_count=truncated,
                keep_lane_path_count=keep_lane_count,
                no_error_path_count=no_error_count,
                keep_lane_no_error_path_count=joint_count,
                structurally_valid_keep_lane_no_error_path_count=(
                    structurally_valid_joint_count
                ),
                joint_audit_candidate_path_count=candidate_count,
                safe_for_later_conversion=(candidate_count == 1 and truncated == 0),
            )
        )

    role_counts = Counter(path.role_symbol for path in audited_paths)
    error_counts = Counter(path.error_symbol for path in audited_paths)
    role_error_counts = Counter(
        (path.role_symbol, path.error_symbol) for path in audited_paths
    )
    failure_counts = Counter(
        code for path in audited_paths for code in path.failure_codes
    )
    keep_lane_counts = Counter(
        min(message.keep_lane_path_count, 2) for message in audited_messages
    )
    candidate_counts = Counter(
        min(message.joint_audit_candidate_path_count, 2) for message in audited_messages
    )
    total_truncated = sum(message.truncated_path_count for message in audited_messages)
    status = (
        "required_schema_fields_missing"
        if missing_required
        else "completed_with_truncation"
        if total_truncated
        else "completed"
    )
    summary = {
        "sampled_messages": len(samples),
        "messages_with_source_timestamp": sum(
            message.source_timestamp_present for message in audited_messages
        ),
        "total_paths": sum(message.total_path_count for message in audited_messages),
        "inspected_paths": len(audited_paths),
        "truncated_paths": total_truncated,
        "keep_lane_paths": sum(path.is_keep_lane for path in audited_paths),
        "no_error_paths": sum(path.is_no_error for path in audited_paths),
        "keep_lane_no_error_paths": sum(
            path.is_keep_lane_no_error for path in audited_paths
        ),
        "structurally_valid_keep_lane_no_error_paths": sum(
            path.is_keep_lane_no_error and path.model_structure_valid
            for path in audited_paths
        ),
        "joint_audit_candidate_paths": sum(
            path.is_joint_audit_candidate for path in audited_paths
        ),
        "messages_with_no_keep_lane": keep_lane_counts[0],
        "messages_with_exactly_one_keep_lane": keep_lane_counts[1],
        "messages_with_multiple_keep_lane": keep_lane_counts[2],
        "messages_with_no_joint_audit_candidate": candidate_counts[0],
        "messages_with_exactly_one_joint_audit_candidate": candidate_counts[1],
        "messages_with_multiple_joint_audit_candidates": candidate_counts[2],
        "messages_safe_for_later_conversion": sum(
            message.safe_for_later_conversion for message in audited_messages
        ),
    }
    return ProtobufJointPathSemanticAudit(
        status=status,
        missing_required_fields=missing_required,
        field_bindings=bindings.public_paths(),
        messages=tuple(audited_messages),
        paths=tuple(audited_paths),
        role_counts=tuple(sorted(role_counts.items())),
        error_counts=tuple(sorted(error_counts.items())),
        role_error_counts=tuple(
            (role, error, count)
            for (role, error), count in sorted(role_error_counts.items())
        ),
        failure_counts=tuple(sorted(failure_counts.items())),
        summary_counts=tuple(summary.items()),
    )


def _observe_message(
    message: Any,
    *,
    sample_index: int,
    observations: dict[str, _Observation],
    descriptor: Any | None = None,
    prefix: str = "",
    max_depth: int,
    depth: int = 1,
    max_repeated_items: int = _DEFAULT_MAX_REPEATED_ITEMS_PER_FIELD,
) -> None:
    for field, value, presence_evidence in _listed_fields_with_descriptor(
        message,
        descriptor=descriptor,
    ):
        name = str(field.name)
        path = f"{prefix}.{name}" if prefix else name
        observation = observations.setdefault(
            path,
            _Observation(set(), 0, [], set(), set(), set(), 0, 0),
        )
        observation.sampled_message_indices.add(sample_index)
        observation.occurrences += 1
        observation.presence_evidence.add(presence_evidence)

        repeated = _field_is_repeated(field)
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
        elif (
            field_type == _MESSAGE_TYPE
            and depth < max_depth
            and not _field_is_map(field)
        ):
            inspected_values = values[:max_repeated_items]
            observation.nested_message_items_inspected += len(inspected_values)
            observation.nested_message_items_truncated += max(
                0,
                len(values) - len(inspected_values),
            )
            for item in inspected_values:
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
    max_repeated_items_per_field: int = (_DEFAULT_MAX_REPEATED_ITEMS_PER_FIELD),
) -> ProtobufPathSourceProbe:
    """Inspect decoded messages without exporting numeric payload values."""

    if not topic:
        raise ValueError("topic must not be empty")
    if max_messages < 1:
        raise ValueError("max_messages must be at least one")
    if max_schema_depth < 1:
        raise ValueError("max_schema_depth must be at least one")
    if max_repeated_items_per_field < 1:
        raise ValueError("max_repeated_items_per_field must be at least one")

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
            max_repeated_items=max_repeated_items_per_field,
        )

    output_fields: list[ProtobufFieldProbe] = []
    for path, field in sorted(fields_by_path.items()):
        observation = observations.get(
            path,
            _Observation(set(), 0, [], set(), set(), set(), 0, 0),
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
                label=_field_cardinality_name(field),
                message_type=message_type,
                enum_type=enum_type,
                enum_symbols=_enum_symbols(field),
                oneof=(
                    None if containing_oneof is None else str(containing_oneof.name)
                ),
                is_map=_field_is_map(field),
                semantic_tags=_semantic_tags(path, field),
                present_in_sampled_messages=len(observation.sampled_message_indices),
                observed_occurrences=observation.occurrences,
                presence_evidence=tuple(sorted(observation.presence_evidence)),
                repeated_length_min=(
                    min(repeated_lengths) if repeated_lengths else None
                ),
                repeated_length_median=(
                    float(median(repeated_lengths)) if repeated_lengths else None
                ),
                repeated_length_max=(
                    max(repeated_lengths) if repeated_lengths else None
                ),
                nested_message_items_inspected=(
                    observation.nested_message_items_inspected
                    if (
                        _field_is_repeated(field)
                        and int(getattr(field, "type", 0)) == _MESSAGE_TYPE
                        and not _field_is_map(field)
                    )
                    else None
                ),
                nested_message_items_truncated=(
                    observation.nested_message_items_truncated
                    if (
                        _field_is_repeated(field)
                        and int(getattr(field, "type", 0)) == _MESSAGE_TYPE
                        and not _field_is_map(field)
                    )
                    else None
                ),
                observed_enum_symbols=tuple(sorted(observation.enum_symbols)),
                observed_boolean_values=tuple(sorted(observation.boolean_values)),
            )
        )

    joint_path_semantics = _audit_joint_path_semantics(
        samples,
        descriptor=descriptor,
        max_paths_per_message=max_repeated_items_per_field,
    )
    return ProtobufPathSourceProbe(
        topic=topic,
        schema_name=schema_name,
        schema_fingerprint_sha256=_schema_fingerprint(descriptor),
        decoded_messages_seen=decoded_seen,
        sampled_messages=len(samples),
        source_timestamp_present_messages=source_timestamp_present,
        max_schema_depth=max_schema_depth,
        max_repeated_items_per_field=max_repeated_items_per_field,
        raw_numeric_values_exported=False,
        fields=tuple(output_fields),
        joint_path_semantics=joint_path_semantics,
    )


def inspect_protobuf_path_source(
    path: str | Path,
    *,
    topic: str = DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    expected_schema_name: str = DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    max_messages: int = 20,
    max_schema_depth: int = 6,
    max_repeated_items_per_field: int = (_DEFAULT_MAX_REPEATED_ITEMS_PER_FIELD),
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
            max_repeated_items_per_field=max_repeated_items_per_field,
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
