"""Indexed metadata and bounded readiness, using the reviewed EDP/RLMB rules."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory

from ..domain.recording_ingestion import ClockOrderSummary, summarize_support
from .exploratory_residuals import _scan_stream
from .independent_outing_intake import _DecodedEstimate
from .mcap import McapDependencyError
from .odometry import DEFAULT_ODOMETRY_TOPIC
from .recording_pair_feasibility import (
    MAX_CHUNK_BYTES, MAX_MESSAGES_PER_TOPIC, MAX_SPOOL_BYTES, TOPICS,
    RecordingReadError, ResourceLimitError, _indexed_summary, _iter_messages, decoder_types,
)

# This new consumer has its own declared odometry budget (about 2.8 h at 100 Hz).
# Historical batch02 still uses 300,000. No selection or speed rule changes.
TOPIC_LIMITS = {**{topic: MAX_MESSAGES_PER_TOPIC for topic in TOPICS}, DEFAULT_ODOMETRY_TOPIC: 1_000_000}


def file_state(path=None, *, stream=None):
    state = os.fstat(stream.fileno()) if stream is not None else path.stat()
    if not stat.S_ISREG(state.st_mode):
        raise ValueError("regular_mcap_file_required")
    return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns


def sha256_stream(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def indexed_metadata(stream):
    """Read only the index; retain advertised counts even when a cap blocks decoding."""
    SeekingReader, _ = decoder_types()
    stream.seek(0)
    reader = SeekingReader(stream, record_size_limit=MAX_CHUNK_BYTES)
    summary = reader.get_summary()
    if summary is None or summary.statistics is None:
        raise ResourceLimitError("indexed_summary_required_no_scan_fallback")
    stats = summary.statistics
    topics = {}
    for topic in TOPIC_LIMITS:
        channels = []
        for key, channel in sorted(summary.channels.items()):
            if channel.topic != topic:
                continue
            schema = summary.schemas.get(channel.schema_id)
            channels.append({"channel_id": key, "message_encoding": channel.message_encoding,
                "schema_name": None if schema is None else schema.name,
                "schema_encoding": None if schema is None else schema.encoding,
                "descriptor_sha256": None if schema is None else hashlib.sha256(schema.data).hexdigest(),
                "advertised_message_count": stats.channel_message_counts.get(key, 0)})
        topics[topic] = {"channels": channels, "advertised_message_count": sum(c["advertised_message_count"] for c in channels)}
    metadata = {"indexed_chunk_count": len(summary.chunk_indexes),
        "advertised_message_count_all_topics": stats.message_count,
        "log_start_ns_decimal": str(stats.message_start_time), "log_end_ns_decimal": str(stats.message_end_time),
        "maximum_advertised_chunk_bytes": max((max(c.chunk_length, c.uncompressed_size) for c in summary.chunk_indexes), default=0),
        "topics": topics}
    try:
        _indexed_summary(reader, topic_limits=TOPIC_LIMITS)
    except (ResourceLimitError, RecordingReadError) as error:
        return metadata, str(error)
    return metadata, None


def inconclusive_readiness(code):
    return {"status": "inconclusive", "failure_code": code, "counts": None, "diagnostics": None,
            "odometry": None, "source_clock_order": None, "log_clock_order": None,
            "sensor_geometry_support": None, "complete_condition_support": None, "condition_failure_counts": None}


def inspect_recording_readiness(path: Path, stream, scratch: Path):
    """Never construct residual targets or export numeric input values."""
    source_order = {role: ClockOrderSummary() for role in ("estimate", "reference")}
    log_order = {topic: ClockOrderSummary() for topic in TOPIC_LIMITS}

    def observe(record):
        role = "estimate" if isinstance(record, _DecodedEstimate) else "reference"
        source_order[role].add(record.source_time_ns)

    def messages():
        with closing(_iter_messages(path, topic_limits=TOPIC_LIMITS, stream=stream)) as records:
            for item in records:
                log_order[item[1].topic].add(item[2].log_time)
                yield item

    try:
        with TemporaryDirectory(prefix="mpr-ingestion-", dir=scratch) as temporary:
            with closing(sqlite3.connect(str(Path(temporary) / "geometry.sqlite"))) as db:
                db.execute("PRAGMA page_size=4096")
                db.execute("PRAGMA cache_size=-4096")
                db.execute("PRAGMA mmap_size=0")
                db.execute("PRAGMA temp_store=FILE")
                db.execute(f"PRAGMA max_page_count={MAX_SPOOL_BYTES // 4096}")
                db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
                with closing(messages()) as records:
                    result = _scan_stream(records, db, odometry_message_limit=TOPIC_LIMITS[DEFAULT_ODOMETRY_TOPIC], on_record=observe)
        rows = result["candidates"]
        conditions = [row for row in rows if row["conditions"] is not None]
        failures = Counter(code for row in rows for code in row["condition_failure_codes"])
        return {"status": "complete", "failure_code": None, "counts": result["counts"], "diagnostics": result["diagnostics"],
                "odometry": result["odometry"], "source_clock_order": {k: v.summary() for k, v in source_order.items()},
                "log_clock_order": {k: v.summary() for k, v in log_order.items()},
                "sensor_geometry_support": summarize_support(rows), "complete_condition_support": summarize_support(conditions),
                "condition_failure_counts": dict(sorted(failures.items()))}
    except McapDependencyError:
        raise
    except (ResourceLimitError, RecordingReadError) as error:
        return inconclusive_readiness(str(error))
    except MemoryError:
        return inconclusive_readiness("memory_limit")
    except Exception as error:
        return inconclusive_readiness(type(error).__name__)
