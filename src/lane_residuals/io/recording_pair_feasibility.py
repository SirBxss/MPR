"""Disk-backed EDP/RLMB geometry feasibility, without session declarations."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import fields
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any, Iterable

import numpy as np

from ..domain.independent_outing_intake import EXPECTED_TOPOLOGY_SOURCE, MAXIMUM_ANCHOR_DISTANCE_M
from ..domain.pairing import EgoRelativePath, mutual_nearest_timestamp_pairs
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from .independent_outing_intake import (
    DEFAULT_MAP_TOPIC, _DecodedEstimate, _h100_geometry, iter_geometry_records,
)
from .mcap import McapDependencyError


TOPICS = (DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC, DEFAULT_MAP_TOPIC)
MAX_MESSAGES_PER_TOPIC = 100_000
MAX_CHUNK_BYTES = 128 * 1024**2
MAX_SPOOL_BYTES = 8 * 1024**3


class ResourceLimitError(RuntimeError):
    """An execution limit, never evidence of missing or invalid geometry."""


class RecordingReadError(ValueError):
    """A static, payload-free completeness failure code."""


def _indexed_summary(reader: Any) -> tuple[Any, dict[str, int]]:
    summary = reader.get_summary()
    if summary is None or summary.statistics is None or not summary.chunk_indexes:
        raise ResourceLimitError("indexed_summary_required_no_scan_fallback")
    stats = summary.statistics
    if stats.chunk_count != len(summary.chunk_indexes) or not stats.channel_message_counts:
        raise ResourceLimitError("complete_summary_statistics_required")
    # Checking all indexed chunks is conservative: limits stop the audit rather
    # than selectively discarding messages in a large chunk.
    if any(max(c.chunk_length, c.uncompressed_size) > MAX_CHUNK_BYTES
           for c in summary.chunk_indexes):
        raise ResourceLimitError("advertised_chunk_exceeds_resource_limit")
    if set(stats.channel_message_counts) - set(summary.channels):
        raise RecordingReadError("summary_channel_identity_mismatch")
    if sum(stats.channel_message_counts.values()) != stats.message_count:
        raise RecordingReadError("summary_message_count_mismatch")
    counts = {topic: sum(stats.channel_message_counts.get(key, 0)
                         for key, channel in summary.channels.items()
                         if channel.topic == topic) for topic in TOPICS}
    if any(count > MAX_MESSAGES_PER_TOPIC for count in counts.values()):
        raise ResourceLimitError("advertised_topic_count_exceeds_resource_limit")
    return summary, counts


def _iter_messages(path: Path):
    try:
        from mcap.reader import SeekingReader
        from mcap_protobuf.decoder import DecoderFactory
    except ImportError as error:
        raise McapDependencyError('Install the project MCAP extra: pip install -e ".[mcap]"') from error
    with path.open("rb") as stream:
        reader = SeekingReader(stream, decoder_factories=[DecoderFactory()],
                               record_size_limit=MAX_CHUNK_BYTES)
        _, expected = _indexed_summary(reader)
        actual: Counter[str] = Counter()
        # Storage order avoids the log-time merge queue retaining geometry or
        # payloads from many overlapping chunks. Matching below uses complete
        # source-time streams and is invariant to this ordering for count outputs.
        for record in reader.iter_decoded_messages(topics=TOPICS, log_time_order=False):
            topic = record[1].topic
            actual[topic] += 1
            if actual[topic] > MAX_MESSAGES_PER_TOPIC:
                raise ResourceLimitError("decoded_topic_count_exceeds_resource_limit")
            yield record
        if any(actual[topic] != expected[topic] for topic in TOPICS):
            raise RecordingReadError("decoded_summary_topic_count_mismatch")


def _pack_path(path: EgoRelativePath | None) -> bytes | None:
    if path is None:
        return None
    buffer = BytesIO()
    np.savez(buffer, **{field.name: getattr(path, field.name) for field in fields(EgoRelativePath)})
    return buffer.getvalue()


def _unpack_path(payload: bytes | None) -> EgoRelativePath | None:
    if payload is None:
        return None
    with np.load(BytesIO(payload), allow_pickle=False) as archive:
        values = {name: value.item() if value.ndim == 0 else value.copy()
                  for name in archive.files for value in (archive[name],)}
    return EgoRelativePath(**values)


def _count_geometry(records: Iterable[Any], connection: sqlite3.Connection) -> dict[str, Any]:
    times: dict[str, list[int | None]] = {"estimate": [], "reference": []}
    topology_counts: Counter[str] = Counter()
    conversion_failures: Counter[str] = Counter()
    descriptor_counts: Counter[str] = Counter()
    # Only scalar timestamp streams survive this pass. Reconstructed paths go
    # to a private temporary SQLite file, with a bounded page cache.
    for record in records:
        role = "estimate" if isinstance(record, _DecodedEstimate) else "reference"
        if len(times[role]) >= MAX_MESSAGES_PER_TOPIC:
            raise ResourceLimitError("decoded_topic_count_exceeds_resource_limit")
        index = len(times[role])
        times[role].append(record.source_time_ns)
        frame = record.frame if role == "estimate" else None
        topology = "UNAVAILABLE_ENUM_VALUE" if frame is None else frame.topology_source
        if role == "estimate":
            topology_counts[topology] += 1
            if record.descriptor_file_sha256 is not None:
                descriptor_counts[record.descriptor_file_sha256] += 1
        if record.failure_code is not None:
            conversion_failures[record.failure_code] += 1
        metadata = json.dumps({"topology": topology, "failure": record.failure_code,
                               "estimator_available": bool(frame is not None and
                                   frame.estimator_state == "available_no_error")})
        connection.execute("INSERT INTO geometry VALUES (?, ?, ?, ?)",
                           (role, index, metadata, _pack_path(record.path)))
        # Avoid retaining the final decoded message during the pairing pass.
        del record, frame
    connection.commit()
    pairing = mutual_nearest_timestamp_pairs(times["estimate"], times["reference"])
    counts = {"h100_pair_count": 0, "anchored_h100_pair_count": 0,
              "sensor_anchored_h100_pair_count": 0}
    pair_failures: Counter[str] = Counter()
    candidate_topologies: Counter[str] = Counter()

    def read(role: str, position: int):
        metadata, geometry = connection.execute(
            "SELECT metadata, path FROM geometry WHERE role = ? AND position = ?",
            (role, position)).fetchone()
        return json.loads(metadata), _unpack_path(geometry)

    for pair in pairing.pairs:
        estimate_info, estimate = read("estimate", pair.first_position)
        reference_info, reference = read("reference", pair.second_position)
        if estimate is None:
            pair_failures[estimate_info["failure"] or "estimate_geometry_not_ready"] += 1
        elif reference is None:
            pair_failures[reference_info["failure"] or "map_geometry_not_ready"] += 1
        else:
            ready, distance, failure = _h100_geometry(estimate, reference)
            if not ready:
                pair_failures[failure or "h100_geometry_not_ready"] += 1
            else:
                counts["h100_pair_count"] += 1
                if distance is not None and math.isfinite(distance) and distance <= MAXIMUM_ANCHOR_DISTANCE_M:
                    counts["anchored_h100_pair_count"] += 1
                    candidate_topologies[estimate_info["topology"]] += 1
                    if estimate_info["estimator_available"] and estimate_info["topology"] == EXPECTED_TOPOLOGY_SOURCE:
                        counts["sensor_anchored_h100_pair_count"] += 1
                else:
                    pair_failures["anchor_distance_exceeds_1m_or_invalid"] += 1
        del estimate, reference
    return {
        "estimate_message_count": len(times["estimate"]),
        "reference_message_count": len(times["reference"]),
        "timestamp_pairing_counts": {field.name: len(getattr(pairing, field.name))
                                     for field in fields(pairing)},
        "pairing_maximum_delta_ns": None,
        "estimate_topology_counts": dict(sorted(topology_counts.items())),
        "estimate_descriptor_counts": dict(sorted(descriptor_counts.items())),
        "conversion_failure_counts": dict(sorted(conversion_failures.items())),
        "pair_failure_counts": dict(sorted(pair_failures.items())),
        "anchored_h100_topology_counts": dict(sorted(candidate_topologies.items())),
        **counts,
    }


def inspect_recording_pairs(path: Path, scratch_directory: Path) -> dict[str, Any]:
    """Return complete counts or an explicitly inconclusive result, never a prefix."""

    try:
        with TemporaryDirectory(prefix="mpr-geometry-", dir=scratch_directory) as temporary:
            with closing(sqlite3.connect(str(Path(temporary) / "geometry.sqlite"))) as connection:
                connection.execute("PRAGMA page_size=4096")
                connection.execute("PRAGMA cache_size=-4096")
                connection.execute("PRAGMA mmap_size=0")
                connection.execute("PRAGMA temp_store=FILE")
                connection.execute(f"PRAGMA max_page_count={MAX_SPOOL_BYTES // 4096}")
                connection.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
                records = iter_geometry_records(_iter_messages(path))
                with closing(records):
                    counts = _count_geometry(records, connection)
        return {"status": "complete", "failure_code": None, "counts": counts}
    except McapDependencyError:
        raise
    except (ResourceLimitError, RecordingReadError, MemoryError) as error:
        code = "memory_limit" if isinstance(error, MemoryError) else str(error)
        return {"status": "inconclusive", "failure_code": code, "counts": None}
    except Exception as error:
        # Do not leak payload values from an exception or turn partial counts
        # into a negative geometry finding. Disk-full and decode errors are
        # execution failures, with no automatic threshold change or retry.
        return {"status": "inconclusive", "failure_code": type(error).__name__, "counts": None}
