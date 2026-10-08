"""Bounded MCAP summary inventory; never read or decompress message records.

The MCAP specification makes summaries optional and permits extension fields.
Missing summaries are inconclusive for this consumer; unknown payload encodings
are inventoried without constructing a decoder. Counts remain advertised.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import struct
import time
import zlib

from ..domain.recording_ingestion import RecordingIngestionError

INVENTORY_REVISION = "v0.19.8-registered-mcap-inventory-2026-10-08-a1"
MAGIC = b"\x89MCAP0\r\n"
MAX_RECORD_BYTES = 128 * 1024**2
MAX_SUMMARY_BYTES = 1024**3
MAX_TEXT_BYTES = 16 * 1024**2
MAX_SUMMARY_RECORDS = 2_000_000
MAX_SUMMARY_SECONDS = 300
BLOCK_BYTES = 1024**2
SUMMARY_OPCODES = {3, 4, 8, 10, 11, 13}


def _fail(code):
    raise RecordingIngestionError(code)


def _exact(stream, size):
    raw = stream.read(size)
    if len(raw) != size:
        _fail("inventory_truncated_record")
    return raw


class _Fields:
    """Read length-prefixed fields within a single capped record."""

    def __init__(self, raw, text_budget):
        self.raw, self.position, self.text_budget = raw, 0, text_budget

    def take(self, size):
        end = self.position + size
        if end > len(self.raw):
            _fail("inventory_field_outside_record")
        result = memoryview(self.raw)[self.position:end]
        self.position = end
        return result

    def integer(self, kind):
        return struct.unpack(kind, self.take(struct.calcsize(kind)))[0]

    def string(self):
        size = self.integer("<I")
        self.text_budget[0] += size
        if self.text_budget[0] > MAX_TEXT_BYTES:
            _fail("inventory_text_budget_exceeded")
        try:
            return bytes(self.take(size)).decode("utf-8")
        except UnicodeDecodeError:
            _fail("inventory_invalid_utf8")

    def pairs(self, key, value, *, item_bytes=None):
        size = self.integer("<I")
        end = self.position + size
        if end > len(self.raw) or (item_bytes is not None and size % item_bytes):
            _fail("inventory_invalid_map_length")
        result = {}
        while self.position < end:
            k, v = key(), value()
            if self.position > end or k in result:
                _fail("inventory_invalid_or_duplicate_map_entry")
            result[k] = v
        return result

    def integers(self):
        return self.pairs(lambda: self.integer("<H"), lambda: self.integer("<Q"), item_bytes=10)


def _records(stream, start, end, deadline):
    stream.seek(start)
    count = 0
    while stream.tell() < end:
        if time.monotonic() > deadline:
            _fail("inventory_summary_timeout")
        offset = stream.tell()
        if end - offset < 9:
            _fail("inventory_truncated_record_header")
        opcode, size = struct.unpack("<BQ", _exact(stream, 9))
        if size > MAX_RECORD_BYTES:
            _fail("inventory_record_budget_exceeded")
        if opcode == 0 or size > end - stream.tell():
            _fail("inventory_record_outside_section")
        count += 1
        if count > MAX_SUMMARY_RECORDS:
            _fail("inventory_record_count_budget_exceeded")
        raw = _exact(stream, size)
        yield offset, opcode, size + 9, raw
        del raw


def _crc(stream, start, end, footer_prefix, stored, deadline):
    if stored == 0:
        return "unavailable"
    stream.seek(start)
    remaining, value = end - start, 0
    while remaining:
        if time.monotonic() > deadline:
            _fail("inventory_summary_timeout")
        block = _exact(stream, min(BLOCK_BYTES, remaining))
        value = zlib.crc32(block, value)
        remaining -= len(block)
    value = zlib.crc32(footer_prefix, value)
    if value != stored:
        _fail("inventory_summary_crc_mismatch")
    return "validated"


def read_inventory(stream, size_bytes):
    """Summarize Header/Summary/Footer from the already verified raw descriptor.

    Retention is one record plus bounded schema/channel text and scalar maps,
    never the complete chunk-index list. File-level metadata/attachments are
    indexed only: their actual records and values are not inspected.
    """
    deadline = time.monotonic() + MAX_SUMMARY_SECONDS
    if size_bytes < 45:
        _fail("inventory_not_mcap")
    stream.seek(0)
    if _exact(stream, 8) != MAGIC:
        _fail("inventory_not_mcap")
    stream.seek(size_bytes - 37)
    footer = _exact(stream, 37)
    if footer[29:] != MAGIC or footer[:9] != struct.pack("<BQ", 2, 20):
        _fail("inventory_invalid_footer")
    start, offsets, stored_crc = struct.unpack("<QQI", footer[9:29])
    footer_start = size_bytes - 37
    stream.seek(8)
    opcode, header_size = struct.unpack("<BQ", _exact(stream, 9))
    if opcode != 1 or header_size > MAX_RECORD_BYTES or 17 + header_size > footer_start:
        _fail("inventory_invalid_header")
    text_budget = [0]
    fields = _Fields(_exact(stream, header_size), text_budget)
    profile, library = fields.string(), fields.string()
    header_end = 17 + header_size
    if not start:
        _fail("inventory_summary_absent_no_scan_fallback")
    end = offsets or footer_start
    if not header_end + 13 <= start <= end <= footer_start or (offsets and offsets == footer_start):
        _fail("inventory_invalid_summary_extent")
    if footer_start - start > MAX_SUMMARY_BYTES:
        _fail("inventory_summary_budget_exceeded")
    # Check the immediate DataEnd marker, not its data-section CRC.
    stream.seek(start - 13)
    if _exact(stream, 9) != struct.pack("<BQ", 15, 4):
        _fail("inventory_data_end_marker_missing")
    crc_status = _crc(stream, start, footer_start, footer[:25], stored_crc, deadline)
    schemas, channels, statistics, groups = {}, {}, None, {}
    chunks, attachments, metadata_indexes = 0, 0, 0
    maxima = dict.fromkeys(("record_length_bytes", "compressed_bytes", "uncompressed_bytes"), 0)
    compressions, chunk_channels = Counter(), set()
    chunk_min = chunk_max = None
    previous_opcode = None
    for offset, opcode, length, raw in _records(stream, start, end, deadline):
        if opcode not in SUMMARY_OPCODES:
            _fail("inventory_unsupported_summary_opcode")
        if opcode != previous_opcode:
            if opcode in groups:
                _fail("inventory_summary_opcode_not_grouped")
            groups[opcode] = [offset, 0, 0]
        groups[opcode][1] += length
        groups[opcode][2] += 1
        previous_opcode = opcode
        fields = _Fields(raw, text_budget)
        if opcode == 3:
            identifier = fields.integer("<H")
            name, encoding = fields.string(), fields.string()
            data_size = fields.integer("<I")
            data = fields.take(data_size)
            if not identifier or identifier in schemas:
                _fail("inventory_invalid_or_duplicate_schema_id")
            schemas[identifier] = {"schema_id": identifier, "name": name, "encoding": encoding,
                "data_size_bytes": data_size, "data_sha256": hashlib.sha256(data).hexdigest()}
            del data
        elif opcode == 4:
            identifier, schema = fields.integer("<H"), fields.integer("<H")
            topic, encoding = fields.string(), fields.string()
            values = fields.pairs(fields.string, fields.string)
            if identifier in channels:
                _fail("inventory_duplicate_channel_id")
            channels[identifier] = {"channel_id": identifier, "schema_id": schema, "topic": topic,
                "message_encoding": encoding, "metadata_entry_count": len(values)}
            del values
        elif opcode == 8:
            first, last, location, chunk_length = [fields.integer("<Q") for _ in range(4)]
            entries = fields.integers()
            index_length = fields.integer("<Q")
            compression = fields.string()
            compressed, uncompressed = fields.integer("<Q"), fields.integer("<Q")
            if (first > last or location < header_end or chunk_length < 9 or
                    location + chunk_length + index_length > start - 13 or compressed > chunk_length or
                    any(not location + chunk_length <= p < location + chunk_length + index_length for p in entries.values())):
                _fail("inventory_invalid_chunk_index")
            chunk_channels.update(entries)
            chunks += 1
            maxima["record_length_bytes"] = max(maxima["record_length_bytes"], chunk_length)
            maxima["compressed_bytes"] = max(maxima["compressed_bytes"], compressed)
            maxima["uncompressed_bytes"] = max(maxima["uncompressed_bytes"], uncompressed)
            compressions[compression if compression in ("", "zstd", "lz4") else "other"] += 1
            if first or last:  # Both zero can also describe a chunk with no messages.
                chunk_min = first if chunk_min is None else min(chunk_min, first)
                chunk_max = last if chunk_max is None else max(chunk_max, last)
            del entries
        elif opcode == 11:
            if statistics is not None:
                _fail("inventory_duplicate_statistics")
            values = [fields.integer(k) for k in ("<Q", "<H", "<I", "<I", "<I", "<I", "<Q", "<Q")]
            statistics = dict(zip(("message_count", "schema_count", "channel_count", "attachment_count",
                "metadata_count", "chunk_count", "message_start_time", "message_end_time"), values))
            statistics["channel_message_counts"] = fields.integers()
        else:
            location, record_length = fields.integer("<Q"), fields.integer("<Q")
            if location < header_end or record_length < 9 or location + record_length > start - 13:
                _fail("inventory_invalid_auxiliary_index")
            if opcode == 10:
                for _ in range(3):
                    fields.integer("<Q")
                fields.string()
                fields.string()
                attachments += 1
            else:
                fields.string()
                metadata_indexes += 1
        # Backward-compatible extension fields are intentionally not interpreted.
        del fields, raw
    if offsets:
        observed, seen_offsets = {}, set()
        for _, opcode, _, raw in _records(stream, offsets, footer_start, deadline):
            if opcode != 14:
                _fail("inventory_invalid_summary_offset_opcode")
            fields = _Fields(raw, text_budget)
            group, location, length = fields.integer("<B"), fields.integer("<Q"), fields.integer("<Q")
            empty_group = group in SUMMARY_OPCODES and group not in groups and length == 0 and start <= location <= end
            if group in seen_offsets or (not empty_group and (group not in groups or [location, length] != groups[group][:2])):
                _fail("inventory_summary_offset_mismatch")
            seen_offsets.add(group)
            if not empty_group:
                observed[group] = True
            del fields, raw
        if set(observed) != set(groups):
            _fail("inventory_summary_offset_coverage_mismatch")
    if not groups:
        _fail("inventory_empty_summary")
    if any(row["schema_id"] and row["schema_id"] not in schemas for row in channels.values()):
        _fail("inventory_channel_schema_missing")
    if chunk_channels - set(channels):
        _fail("inventory_chunk_channel_missing")
    counts = None
    if statistics is not None:
        counts = statistics["channel_message_counts"] or None
        if (statistics["schema_count"] != len(schemas) or statistics["channel_count"] != len(channels) or
                statistics["chunk_count"] != chunks or statistics["message_start_time"] > statistics["message_end_time"]):
            _fail("inventory_statistics_structure_mismatch")
        if counts is not None and (set(counts) - set(channels) or sum(counts.values()) != statistics["message_count"]):
            _fail("inventory_statistics_message_count_mismatch")
        if attachments > statistics["attachment_count"] or metadata_indexes > statistics["metadata_count"]:
            _fail("inventory_statistics_auxiliary_count_mismatch")
        if chunk_min is not None and (statistics["message_count"] == 0 or
                chunk_min < statistics["message_start_time"] or chunk_max > statistics["message_end_time"]):
            _fail("inventory_statistics_chunk_time_mismatch")
        if statistics["message_count"] == 0:
            counts = {}  # Zero is proved by the advertised total, not guessed from an absent map.
        statistics = {**{k: v for k, v in statistics.items() if k not in
            ("channel_message_counts", "message_start_time", "message_end_time")},
            "log_start_ns_decimal": str(statistics["message_start_time"]),
            "log_end_ns_decimal": str(statistics["message_end_time"])}
    topic_counts = {}
    for identifier, row in sorted(channels.items()):
        row["advertised_message_count"] = None if counts is None else counts.get(identifier, 0)
        topic_counts.setdefault(row["topic"], []).append(row["advertised_message_count"])
    topics = [{"topic": topic, "channel_count": len(values),
               "advertised_message_count": None if any(v is None for v in values) else sum(values)}
              for topic, values in sorted(topic_counts.items())]
    return {"summary_crc_status": crc_status, "summary_bytes": footer_start - start,
        "summary_record_groups": [{"opcode": op, "record_count": v[2], "total_bytes": v[1]} for op, v in sorted(groups.items())],
        "summary_offsets_present": bool(offsets), "header_profile_present": bool(profile),
        "header_library_present": bool(library),
        "header_library_sha256": hashlib.sha256(library.encode()).hexdigest() if library else None,
        "schemas": [schemas[k] for k in sorted(schemas)], "channels": [channels[k] for k in sorted(channels)],
        "topics": topics, "advertised_statistics": statistics,
        "chunk_index_summary": {"indexed_chunk_count": chunks, "compression_counts": dict(sorted(compressions.items())),
            "maximum_advertised_chunk_sizes": maxima,
            "index_order_and_global_chunk_uniqueness_verified": False},
        "auxiliary_indexes": {"metadata_index_count": metadata_indexes, "attachment_index_count": attachments,
            "metadata_records_inspected": False, "attachment_records_inspected": False}}
