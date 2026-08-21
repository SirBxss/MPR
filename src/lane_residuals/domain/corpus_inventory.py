"""Fail-closed continuity decisions for an MCAP corpus.

This module deliberately knows nothing about filenames beyond already-parsed
diagnostic hints.  In particular, physical drive identity is supplied by the
private manifest and is never inferred from an MCAP identifier or timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence


MAXIMUM_STITCH_SOURCE_GAP_NS = 200_000_000


@dataclass(frozen=True)
class TopicCompatibility:
    """Container metadata for one required topic in one recording."""

    role: str
    topic: str
    expected_schema_name: str
    present: bool
    message_count: int
    schema_names: tuple[str, ...]
    schema_encodings: tuple[str, ...]
    message_encodings: tuple[str, ...]

    @property
    def signature(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return self.schema_names, self.schema_encodings, self.message_encodings

    @property
    def compatible(self) -> bool:
        return (
            self.present
            and self.message_count > 0
            and self.schema_names == (self.expected_schema_name,)
            and tuple(value.lower() for value in self.schema_encodings)
            == ("protobuf",)
            and tuple(value.lower() for value in self.message_encodings)
            == ("protobuf",)
        )

    @property
    def failure_codes(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.present:
            failures.append("required_topic_missing")
        elif self.message_count == 0:
            failures.append("required_topic_empty")
        if self.present and self.schema_names != (self.expected_schema_name,):
            failures.append("required_schema_name_mismatch")
        if self.present and tuple(value.lower() for value in self.schema_encodings) != (
            "protobuf",
        ):
            failures.append("required_schema_encoding_mismatch")
        if self.present and tuple(value.lower() for value in self.message_encodings) != (
            "protobuf",
        ):
            failures.append("required_message_encoding_mismatch")
        return tuple(failures)


@dataclass(frozen=True)
class McapInventoryRecord:
    """All evidence needed to assess one file and its neighboring edges."""

    path: str
    basename: str
    relative_path: str
    recording_id: str
    drive_id: str | None
    file_size_bytes: int
    sha256: str | None
    readable: bool
    empty: bool
    internal_start_log_time_ns: int | None
    internal_end_log_time_ns: int | None
    first_estimate_source_time_ns: int | None
    last_estimate_source_time_ns: int | None
    estimate_source_timestamp_count: int
    estimate_missing_source_timestamp_count: int
    estimate_source_timestamps_strictly_increasing: bool
    filename_start: str | None
    filename_end: str | None
    filename_duration_ms: float | None
    mcap_identifier: int | None
    filename_internal_time_disagreement: bool
    topics: tuple[TopicCompatibility, ...]
    failure_codes: tuple[str, ...] = ()
    duplicate_of_recording_id: str | None = None
    chronological_index_within_drive: int | None = None
    filename_order_disagrees_with_internal_order: bool = False

    @property
    def internal_duration_ns(self) -> int | None:
        if self.internal_start_log_time_ns is None or self.internal_end_log_time_ns is None:
            return None
        return self.internal_end_log_time_ns - self.internal_start_log_time_ns

    @property
    def relevant_duration_ns(self) -> int | None:
        if (
            self.first_estimate_source_time_ns is None
            or self.last_estimate_source_time_ns is None
        ):
            return None
        return self.last_estimate_source_time_ns - self.first_estimate_source_time_ns

    @property
    def required_topics_and_schemas_compatible(self) -> bool:
        return bool(self.topics) and all(topic.compatible for topic in self.topics)

    @property
    def usable(self) -> bool:
        return (
            self.drive_id is not None
            and self.readable
            and not self.empty
            and self.duplicate_of_recording_id is None
            and self.internal_duration_ns is not None
            and self.internal_duration_ns >= 0
            and self.first_estimate_source_time_ns is not None
            and self.last_estimate_source_time_ns is not None
            and self.estimate_missing_source_timestamp_count == 0
            and self.estimate_source_timestamps_strictly_increasing
            and self.required_topics_and_schemas_compatible
            and not any(code.startswith("estimate_decode_failed:") for code in self.failure_codes)
        )


@dataclass(frozen=True)
class ContinuityEdge:
    """A fail-closed decision for two chronologically adjacent MCAPs."""

    drive_id: str
    left_recording_id: str
    right_recording_id: str
    left_basename: str
    right_basename: str
    internal_log_gap_ns: int | None
    relevant_source_gap_ns: int | None
    filename_gap_ms: float | None
    filename_internal_gap_disagreement: bool
    identifier_delta: int | None
    identifier_discontinuity: bool
    same_drive_label: bool
    internal_log_times_compatible: bool
    relevant_source_timestamps_strictly_increasing: bool
    source_gap_within_limit: bool
    required_topics_schemas_compatible: bool
    overlap_detected: bool
    timestamp_reset_detected: bool
    pair_index_boundary_state: str
    stitchable: bool
    rejection_codes: tuple[str, ...]


@dataclass(frozen=True)
class SessionGroup:
    """One provisional block connected only by verified stitchable edges."""

    block_id: str
    drive_id: str
    recording_ids: tuple[str, ...]
    mcap_basenames: tuple[str, ...]
    first_estimate_source_time_ns: int | None
    last_estimate_source_time_ns: int | None
    usable_duration_ns: int


def assign_duplicate_evidence(
    records: Sequence[McapInventoryRecord],
) -> tuple[McapInventoryRecord, ...]:
    """Mark byte-identical later files without silently dropping either copy."""

    first_by_hash: dict[str, str] = {}
    assigned: list[McapInventoryRecord] = []
    for record in sorted(records, key=lambda item: (item.basename, item.relative_path)):
        duplicate_of = None
        if record.sha256:
            duplicate_of = first_by_hash.get(record.sha256)
            first_by_hash.setdefault(record.sha256, record.recording_id)
        assigned.append(replace(record, duplicate_of_recording_id=duplicate_of))
    return tuple(assigned)


def chronological_records(
    records: Sequence[McapInventoryRecord],
) -> tuple[McapInventoryRecord, ...]:
    """Sort by authoritative internal evidence and annotate filename-order conflicts."""

    def key(record: McapInventoryRecord) -> tuple[object, ...]:
        time = record.first_estimate_source_time_ns
        if time is None:
            time = record.internal_start_log_time_ns
        return (
            record.drive_id or "",
            time is None,
            time if time is not None else 0,
            record.basename,
            record.relative_path,
        )

    result: list[McapInventoryRecord] = []
    by_drive: dict[str, list[McapInventoryRecord]] = {}
    unassigned: list[McapInventoryRecord] = []
    for record in records:
        if record.drive_id is None:
            unassigned.append(record)
        else:
            by_drive.setdefault(record.drive_id, []).append(record)

    for drive_id in sorted(by_drive):
        group = sorted(by_drive[drive_id], key=key)
        internal_order = [item.recording_id for item in group]
        filename_order = [
            item.recording_id
            for item in sorted(
                group,
                key=lambda item: (
                    item.filename_start is None,
                    item.filename_start or "",
                    item.basename,
                    item.relative_path,
                ),
            )
        ]
        disagreement = internal_order != filename_order
        result.extend(
            replace(
                item,
                chronological_index_within_drive=index,
                filename_order_disagrees_with_internal_order=disagreement,
            )
            for index, item in enumerate(group, 1)
        )
    result.extend(sorted(unassigned, key=lambda item: (item.basename, item.relative_path)))
    return tuple(result)


def assess_continuity_edge(
    left: McapInventoryRecord,
    right: McapInventoryRecord,
    *,
    maximum_source_gap_ns: int = MAXIMUM_STITCH_SOURCE_GAP_NS,
) -> ContinuityEdge:
    """Assess an adjacent edge; every missing prerequisite rejects the edge."""

    if maximum_source_gap_ns < 0:
        raise ValueError("maximum_source_gap_ns must be nonnegative")
    same_drive = left.drive_id is not None and left.drive_id == right.drive_id
    internal_gap = (
        None
        if left.internal_end_log_time_ns is None
        or right.internal_start_log_time_ns is None
        else right.internal_start_log_time_ns - left.internal_end_log_time_ns
    )
    source_gap = (
        None
        if left.last_estimate_source_time_ns is None
        or right.first_estimate_source_time_ns is None
        else right.first_estimate_source_time_ns - left.last_estimate_source_time_ns
    )
    internal_compatible = internal_gap is not None and internal_gap >= 0
    source_increasing = source_gap is not None and source_gap > 0
    source_gap_ok = source_gap is not None and 0 < source_gap <= maximum_source_gap_ns
    topic_pairs = {topic.role: topic for topic in left.topics}, {
        topic.role: topic for topic in right.topics
    }
    left_topics, right_topics = topic_pairs
    schemas_compatible = (
        left.required_topics_and_schemas_compatible
        and right.required_topics_and_schemas_compatible
        and set(left_topics) == set(right_topics)
        and all(
            left_topics[role].signature == right_topics[role].signature
            for role in left_topics
        )
    )
    filename_gap = None
    if left.filename_end is not None and right.filename_start is not None:
        from datetime import datetime

        filename_gap = (
            datetime.fromisoformat(right.filename_start)
            - datetime.fromisoformat(left.filename_end)
        ).total_seconds() * 1000.0
    filename_disagreement = (
        filename_gap is not None
        and internal_gap is not None
        and abs(filename_gap - internal_gap / 1_000_000.0) > 1_000.0
    )
    identifier_delta = (
        None
        if left.mcap_identifier is None or right.mcap_identifier is None
        else right.mcap_identifier - left.mcap_identifier
    )
    identifier_discontinuity = identifier_delta is not None and identifier_delta != 1
    overlap = internal_gap is not None and internal_gap < 0
    timestamp_reset = (
        not left.estimate_source_timestamps_strictly_increasing
        or not right.estimate_source_timestamps_strictly_increasing
        or source_gap is not None
        and source_gap <= 0
    )

    rejection_codes: list[str] = []
    if not same_drive:
        rejection_codes.append("drive_label_mismatch_or_missing")
    if not left.usable:
        rejection_codes.append("left_file_unusable")
    if not right.usable:
        rejection_codes.append("right_file_unusable")
    if internal_gap is None:
        rejection_codes.append("internal_log_time_range_unavailable")
    elif not internal_compatible:
        rejection_codes.append("internal_log_time_overlap")
    if not source_increasing:
        rejection_codes.append("relevant_source_time_not_strictly_increasing")
    elif not source_gap_ok:
        rejection_codes.append("relevant_source_time_gap_exceeds_200_ms")
    if not schemas_compatible:
        rejection_codes.append("required_topic_or_schema_incompatible")

    return ContinuityEdge(
        drive_id=left.drive_id or right.drive_id or "unassigned",
        left_recording_id=left.recording_id,
        right_recording_id=right.recording_id,
        left_basename=left.basename,
        right_basename=right.basename,
        internal_log_gap_ns=internal_gap,
        relevant_source_gap_ns=source_gap,
        filename_gap_ms=filename_gap,
        filename_internal_gap_disagreement=filename_disagreement,
        identifier_delta=identifier_delta,
        identifier_discontinuity=identifier_discontinuity,
        same_drive_label=same_drive,
        internal_log_times_compatible=internal_compatible,
        relevant_source_timestamps_strictly_increasing=source_increasing,
        source_gap_within_limit=source_gap_ok,
        required_topics_schemas_compatible=schemas_compatible,
        overlap_detected=overlap,
        timestamp_reset_detected=timestamp_reset,
        pair_index_boundary_state="recording_local_reset_allowed_not_a_stitch_gate",
        stitchable=not rejection_codes,
        rejection_codes=tuple(rejection_codes),
    )


def continuity_edges(
    records: Sequence[McapInventoryRecord],
    *,
    maximum_source_gap_ns: int = MAXIMUM_STITCH_SOURCE_GAP_NS,
) -> tuple[ContinuityEdge, ...]:
    """Assess adjacent files within each explicit drive label."""

    edges: list[ContinuityEdge] = []
    by_drive: dict[str, list[McapInventoryRecord]] = {}
    for record in records:
        if record.drive_id is not None:
            by_drive.setdefault(record.drive_id, []).append(record)
    for drive_id in sorted(by_drive):
        group = sorted(
            by_drive[drive_id],
            key=lambda item: (
                item.chronological_index_within_drive is None,
                item.chronological_index_within_drive or 0,
                item.basename,
            ),
        )
        edges.extend(
            assess_continuity_edge(left, right, maximum_source_gap_ns=maximum_source_gap_ns)
            for left, right in zip(group, group[1:])
        )
    return tuple(edges)


def proposed_session_groups(
    records: Sequence[McapInventoryRecord],
    edges: Sequence[ContinuityEdge],
) -> tuple[SessionGroup, ...]:
    """Group only stitchable edges; this proposal never mutates the drive map."""

    edge_by_right = {edge.right_recording_id: edge for edge in edges}
    groups: list[SessionGroup] = []
    current: list[McapInventoryRecord] = []
    block_number = 0

    def emit(items: Sequence[McapInventoryRecord]) -> None:
        nonlocal block_number
        if not items:
            return
        block_number += 1
        sources = [
            value
            for item in items
            for value in (
                item.first_estimate_source_time_ns,
                item.last_estimate_source_time_ns,
            )
            if value is not None
        ]
        groups.append(
            SessionGroup(
                block_id=f"continuous_block_{block_number:03d}",
                drive_id=items[0].drive_id or "unassigned",
                recording_ids=tuple(item.recording_id for item in items),
                mcap_basenames=tuple(item.basename for item in items),
                first_estimate_source_time_ns=min(sources) if sources else None,
                last_estimate_source_time_ns=max(sources) if sources else None,
                usable_duration_ns=sum(item.relevant_duration_ns or 0 for item in items if item.usable),
            )
        )

    for record in records:
        if record.drive_id is None:
            emit(current)
            current = []
            emit((record,))
            continue
        edge = edge_by_right.get(record.recording_id)
        if current and edge is not None and edge.stitchable:
            current.append(record)
        else:
            emit(current)
            current = [record]
    emit(current)
    return tuple(groups)


def exact_drive_map_coverage(
    basenames: Sequence[str],
    manifest_pairs: Sequence[tuple[str, str]],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Validate exact one-to-one basename coverage, including duplicate JSON keys."""

    discovered_counts: dict[str, int] = {}
    for basename in basenames:
        discovered_counts[basename] = discovered_counts.get(basename, 0) + 1
    manifest_counts: dict[str, int] = {}
    assignments: dict[str, str] = {}
    invalid_entries: list[str] = []
    for key, value in manifest_pairs:
        if not isinstance(key, str) or not key or not isinstance(value, str) or not value.strip():
            invalid_entries.append(str(key))
            continue
        manifest_counts[key] = manifest_counts.get(key, 0) + 1
        assignments[key] = value.strip()
    discovered = set(discovered_counts)
    mapped = set(manifest_counts)
    issues = {
        "missing_basenames": tuple(sorted(discovered - mapped)),
        "extra_basenames": tuple(sorted(mapped - discovered)),
        "duplicate_discovered_basenames": tuple(
            sorted(name for name, count in discovered_counts.items() if count != 1)
        ),
        "duplicate_drive_map_basenames": tuple(
            sorted(name for name, count in manifest_counts.items() if count != 1)
        ),
        "invalid_drive_map_entries": tuple(sorted(invalid_entries)),
    }
    ambiguous = {
        *issues["duplicate_discovered_basenames"],
        *issues["duplicate_drive_map_basenames"],
    }
    usable_assignments = {
        key: value
        for key, value in assignments.items()
        if key in discovered and key not in ambiguous
    }
    return usable_assignments, issues


__all__ = [
    "ContinuityEdge",
    "MAXIMUM_STITCH_SOURCE_GAP_NS",
    "McapInventoryRecord",
    "SessionGroup",
    "TopicCompatibility",
    "assess_continuity_edge",
    "assign_duplicate_evidence",
    "chronological_records",
    "continuity_edges",
    "exact_drive_map_coverage",
    "proposed_session_groups",
]
