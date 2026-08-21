"""Read-only MCAP metadata extraction for the expanded-corpus audit."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..domain.corpus_inventory import McapInventoryRecord, TopicCompatibility
from ..domain.path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)
from .mcap import McapDependencyError, iter_decoded_mcap_messages, source_time_ns_from_message
from .odometry import DEFAULT_ODOMETRY_SCHEMA, DEFAULT_ODOMETRY_TOPIC


DEFAULT_MAP_TOPIC = "/adp/road_lane_map_based"
DEFAULT_MAP_SCHEMA = "Adp.Perception.Road"


@dataclass(frozen=True)
class RequiredTopic:
    role: str
    topic: str
    schema_name: str


DEFAULT_REQUIRED_TOPICS = (
    RequiredTopic(
        "estimate",
        DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
        DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    ),
    RequiredTopic("map", DEFAULT_MAP_TOPIC, DEFAULT_MAP_SCHEMA),
    RequiredTopic("odometry", DEFAULT_ODOMETRY_TOPIC, DEFAULT_ODOMETRY_SCHEMA),
)


@dataclass(frozen=True)
class FilenameTimeHints:
    start: str | None
    end: str | None
    duration_ms: float | None
    mcap_identifier: int | None


_FILENAME_PATTERN = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_"
    r"(?P<end>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}).*"
    r"_MCAP_(?P<identifier>\d+)(?:\.mcap)$",
    re.IGNORECASE,
)


def parse_filename_time_hints(basename: str) -> FilenameTimeHints:
    """Parse filename timestamps as non-authoritative wall-clock hints."""

    match = _FILENAME_PATTERN.match(basename)
    if match is None:
        return FilenameTimeHints(None, None, None, None)
    try:
        start = datetime.strptime(match.group("start"), "%Y-%m-%d_%H-%M-%S")
        end = datetime.strptime(match.group("end"), "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return FilenameTimeHints(None, None, None, int(match.group("identifier")))
    return FilenameTimeHints(
        start=start.isoformat(),
        end=end.isoformat(),
        duration_ms=(end - start).total_seconds() * 1000.0,
        mcap_identifier=int(match.group("identifier")),
    )


def sha256_file(path: Path, *, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _topic_records(summary: object, required: Sequence[RequiredTopic]) -> tuple[TopicCompatibility, ...]:
    channels = getattr(summary, "channels", {}) or {}
    schemas = getattr(summary, "schemas", {}) or {}
    statistics = getattr(summary, "statistics", None)
    counts = (
        getattr(statistics, "channel_message_counts", {}) or {}
        if statistics is not None
        else {}
    )
    records: list[TopicCompatibility] = []
    for specification in required:
        matching = [
            (channel_id, channel)
            for channel_id, channel in channels.items()
            if str(getattr(channel, "topic", "")) == specification.topic
        ]
        schema_names: set[str] = set()
        schema_encodings: set[str] = set()
        message_encodings: set[str] = set()
        message_count = 0
        for channel_id, channel in matching:
            message_count += int(counts.get(channel_id, 0))
            encoding = str(getattr(channel, "message_encoding", ""))
            if encoding:
                message_encodings.add(encoding)
            schema = schemas.get(getattr(channel, "schema_id", None))
            if schema is not None:
                name = str(getattr(schema, "name", ""))
                schema_encoding = str(getattr(schema, "encoding", ""))
                if name:
                    schema_names.add(name)
                if schema_encoding:
                    schema_encodings.add(schema_encoding)
        records.append(
            TopicCompatibility(
                role=specification.role,
                topic=specification.topic,
                expected_schema_name=specification.schema_name,
                present=bool(matching),
                message_count=message_count,
                schema_names=tuple(sorted(schema_names)),
                schema_encodings=tuple(sorted(schema_encodings)),
                message_encodings=tuple(sorted(message_encodings)),
            )
        )
    return tuple(records)


def _absent_topic_records(
    required: Sequence[RequiredTopic],
) -> tuple[TopicCompatibility, ...]:
    return tuple(
        TopicCompatibility(
            role=item.role,
            topic=item.topic,
            expected_schema_name=item.schema_name,
            present=False,
            message_count=0,
            schema_names=(),
            schema_encodings=(),
            message_encodings=(),
        )
        for item in required
    )


def inspect_mcap_for_inventory(
    path: Path,
    *,
    root: Path,
    recording_id: str,
    drive_id: str | None,
    required_topics: Sequence[RequiredTopic] = DEFAULT_REQUIRED_TOPICS,
) -> McapInventoryRecord:
    """Hash and inspect one MCAP while retaining every failure as evidence."""

    try:
        from mcap.reader import make_reader
    except ImportError as error:
        raise McapDependencyError(
            'MCAP inspection requires the optional dependencies; install with pip install -e ".[mcap]"'
        ) from error

    source = path.resolve()
    root = root.resolve()
    try:
        relative_path = str(source.relative_to(root))
    except ValueError:
        relative_path = source.name
    hints = parse_filename_time_hints(source.name)
    size = source.stat().st_size
    digest: str | None = None
    failures: list[str] = []
    try:
        digest = sha256_file(source)
    except OSError as error:
        failures.append(f"sha256_unreadable:{type(error).__name__}")

    if size == 0:
        failures.append("empty_file")
        return McapInventoryRecord(
            path=str(source),
            basename=source.name,
            relative_path=relative_path,
            recording_id=recording_id,
            drive_id=drive_id,
            file_size_bytes=size,
            sha256=digest,
            readable=False,
            empty=True,
            internal_start_log_time_ns=None,
            internal_end_log_time_ns=None,
            first_estimate_source_time_ns=None,
            last_estimate_source_time_ns=None,
            estimate_source_timestamp_count=0,
            estimate_missing_source_timestamp_count=0,
            estimate_source_timestamps_strictly_increasing=False,
            filename_start=hints.start,
            filename_end=hints.end,
            filename_duration_ms=hints.duration_ms,
            mcap_identifier=hints.mcap_identifier,
            filename_internal_time_disagreement=False,
            topics=_absent_topic_records(required_topics),
            failure_codes=tuple(failures),
        )

    try:
        with source.open("rb") as stream:
            summary = make_reader(stream).get_summary()
    except Exception as error:
        failures.append(f"unreadable_mcap:{type(error).__name__}")
        summary = None

    if summary is None:
        if not failures:
            failures.append("unreadable_mcap:no_summary")
        return McapInventoryRecord(
            path=str(source),
            basename=source.name,
            relative_path=relative_path,
            recording_id=recording_id,
            drive_id=drive_id,
            file_size_bytes=size,
            sha256=digest,
            readable=False,
            empty=False,
            internal_start_log_time_ns=None,
            internal_end_log_time_ns=None,
            first_estimate_source_time_ns=None,
            last_estimate_source_time_ns=None,
            estimate_source_timestamp_count=0,
            estimate_missing_source_timestamp_count=0,
            estimate_source_timestamps_strictly_increasing=False,
            filename_start=hints.start,
            filename_end=hints.end,
            filename_duration_ms=hints.duration_ms,
            mcap_identifier=hints.mcap_identifier,
            filename_internal_time_disagreement=False,
            topics=_absent_topic_records(required_topics),
            failure_codes=tuple(failures),
        )

    statistics = getattr(summary, "statistics", None)
    message_count = int(getattr(statistics, "message_count", 0) or 0)
    empty = message_count == 0
    start_ns = (
        int(getattr(statistics, "message_start_time")) if statistics is not None else None
    )
    end_ns = (
        int(getattr(statistics, "message_end_time")) if statistics is not None else None
    )
    if empty:
        failures.append("empty_mcap")
    if start_ns is None or end_ns is None or end_ns < start_ns:
        failures.append("invalid_internal_log_time_range")
    topics = _topic_records(summary, required_topics)
    for topic in topics:
        failures.extend(f"{topic.role}:{code}" for code in topic.failure_codes)

    source_times: list[int] = []
    missing_source_times = 0
    estimate_topic = next(item.topic for item in required_topics if item.role == "estimate")
    try:
        for _schema, _channel, _message, decoded in iter_decoded_mcap_messages(
            source,
            topics=(estimate_topic,),
            include_ros1=False,
        ):
            timestamp = source_time_ns_from_message(decoded)
            if timestamp is None:
                missing_source_times += 1
            else:
                source_times.append(int(timestamp))
    except Exception as error:
        failures.append(f"estimate_decode_failed:{type(error).__name__}")
    strictly_increasing = bool(source_times) and all(
        right > left for left, right in zip(source_times, source_times[1:])
    )
    if not source_times:
        failures.append("estimate_source_timestamps_unavailable")
    elif not strictly_increasing:
        failures.append("estimate_source_timestamp_reset_or_duplicate")
    if missing_source_times:
        failures.append("estimate_source_timestamp_missing")

    internal_duration_ms = (
        None if start_ns is None or end_ns is None else (end_ns - start_ns) / 1_000_000.0
    )
    filename_disagreement = (
        hints.duration_ms is not None
        and internal_duration_ms is not None
        and abs(hints.duration_ms - internal_duration_ms) > 1_000.0
    )
    if filename_disagreement:
        failures.append("filename_internal_duration_disagreement")

    return McapInventoryRecord(
        path=str(source),
        basename=source.name,
        relative_path=relative_path,
        recording_id=recording_id,
        drive_id=drive_id,
        file_size_bytes=size,
        sha256=digest,
        readable=True,
        empty=empty,
        internal_start_log_time_ns=start_ns,
        internal_end_log_time_ns=end_ns,
        first_estimate_source_time_ns=source_times[0] if source_times else None,
        last_estimate_source_time_ns=source_times[-1] if source_times else None,
        estimate_source_timestamp_count=len(source_times),
        estimate_missing_source_timestamp_count=missing_source_times,
        estimate_source_timestamps_strictly_increasing=strictly_increasing,
        filename_start=hints.start,
        filename_end=hints.end,
        filename_duration_ms=hints.duration_ms,
        mcap_identifier=hints.mcap_identifier,
        filename_internal_time_disagreement=filename_disagreement,
        topics=topics,
        failure_codes=tuple(sorted(set(failures))),
    )


__all__ = [
    "DEFAULT_REQUIRED_TOPICS",
    "FilenameTimeHints",
    "RequiredTopic",
    "inspect_mcap_for_inventory",
    "parse_filename_time_hints",
    "sha256_file",
]
