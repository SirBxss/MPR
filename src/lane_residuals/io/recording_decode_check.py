"""Selected Protobuf decodability with disk-backed indexes, never geometry."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import struct
from tempfile import TemporaryDirectory
import time
import zlib

from ..domain.recording_ingestion import RecordingIngestionError
from .recording_inventory import INVENTORY_REVISION, _Fields, _records

DECODE_REVISION = "v0.19.9-selected-stream-decode-check-2026-10-08-a1"
READER_IMPLEMENTATION = "v0.19.9-disk-index-selected-chunks-a1"
MAX_TOPICS = 16
MAX_TOPIC_MESSAGES = 1_000_000
MAX_TOTAL_MESSAGES = 2_000_000
MAX_CHUNK_BYTES = 128 * 1024**2
MAX_INDEX_BYTES = 512 * 1024**2
MAX_SCHEMA_BYTES = 16 * 1024**2
MAX_SCHEMAS = 64
MAX_CHANNELS = 256
MAX_PAYLOAD_BYTES = 8 * 1024**3
MAX_DECODE_SECONDS = 1800
MAX_PREDECESSOR_BYTES = 64 * 1024**2


def _fail(code):
    raise RecordingIngestionError(code)


def selected_topics(values):
    if (not isinstance(values, (tuple, list)) or not 1 <= len(values) <= MAX_TOPICS or
            any(not isinstance(v, str) or not v.startswith("/") or not 1 < len(v) <= 1024 for v in values) or
            len(set(values)) != len(values)):
        _fail("decode_explicit_unique_topics_required")
    return sorted(values)


def read_predecessor(path, registration, registration_hash):
    """Accept only complete original inventories with exact registered lineage."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_PREDECESSOR_BYTES + 1)
    if len(raw) > MAX_PREDECESSOR_BYTES:
        _fail("decode_inventory_report_budget_exceeded")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("decode_inventory_duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        _fail("decode_inventory_nonfinite_json")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
    keys = {"contract_revision", "purpose", "batch_id", "status", "registration_sha256", "source_specification_sha256",
        "technical_recording_count", "independent_outing_count", "message_payloads_decoded", "geometry_readiness_assessed",
        "residual_profiles_constructed", "numeric_conditions_exported", "reference_independence_proven", "model_fitted",
        "roles_assigned", "raw_cache_deletion_authorized", "runtime_versions", "runtime_source_sha256", "execution_limits",
        "resources_at_start", "recordings", "interpretation"}
    if (not isinstance(value, dict) or set(value) != keys or value.get("contract_revision") != INVENTORY_REVISION or
            value.get("purpose") != "development_only_recording_inventory" or value.get("status") != "complete" or
            value.get("batch_id") != registration["batch_id"] or
            value.get("registration_sha256") != registration_hash or
            value.get("source_specification_sha256") != registration["source_specification_sha256"] or
            type(value.get("technical_recording_count")) is not int or
            value.get("technical_recording_count") != len(registration["recordings"]) or
            value.get("independent_outing_count") is not None):
        _fail("decode_complete_inventory_lineage_required")
    for key in ("message_payloads_decoded", "geometry_readiness_assessed", "residual_profiles_constructed",
                "numeric_conditions_exported", "reference_independence_proven", "model_fitted", "roles_assigned",
                "raw_cache_deletion_authorized"):
        if value.get(key) is not False:
            _fail("decode_inventory_scientific_flags_invalid")
    rows = value.get("recordings")
    if not isinstance(rows, list) or len(rows) != len(registration["recordings"]):
        _fail("decode_inventory_recording_set_mismatch")
    for row, identity in zip(rows, registration["recordings"]):
        if (not isinstance(row, dict) or set(row) != {"recording_id", "raw_sha256", "size_bytes", "source_declaration_status",
                "status", "failure_code", "inventory"} or type(row.get("size_bytes")) is not int or
                row.get("status") != "complete" or row.get("failure_code") is not None or
                not isinstance(row.get("inventory"), dict) or
                any(row.get(key) != identity[key] for key in ("recording_id", "raw_sha256", "size_bytes"))):
            _fail("decode_inventory_recording_lineage_mismatch")
    return rows, hashlib.sha256(raw).hexdigest()


def check_dependencies():
    try:
        from mcap_protobuf.decoder import DecoderFactory
        from mcap.stream_reader import StreamReader
    except ImportError:
        _fail("decode_mcap_extra_required")


def _snapshot():
    values = {"process_virtual_memory_bytes": None, "process_resident_memory_bytes": None}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            key = {"VmSize:": "process_virtual_memory_bytes", "VmRSS:": "process_resident_memory_bytes"}.get(line.split()[0])
            if key:
                values[key] = int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return values


def failure_code(error):
    if isinstance(error, RecordingIngestionError):
        return error.code
    if isinstance(error, MemoryError):
        return "memory_limit"
    if type(error).__name__ == "ZstdError":
        text = str(error).lower()  # Classify locally; never expose native text.
        if any(v in text for v in ("allocation error", "not enough memory", "could not create decompression context")):
            return "zstd_decompression_memory_limit"
        if "too much memory" in text:
            return "zstd_decoder_window_limit"
        if "dictionary" in text:
            return "zstd_dictionary_error"
        if any(v in text for v in ("data corruption", "did not decompress full frame", "src size is incorrect")):
            return "zstd_corrupt_or_incomplete_frame"
        return "zstd_decompression_failed"
    return type(error).__name__


def _deadline(deadline):
    if time.monotonic() > deadline:
        _fail("decode_execution_timeout")


def _groups(stream, size, deadline):
    stream.seek(size - 28)
    start, _ = struct.unpack("<QQ", stream.read(16))
    position, result = start, {}
    # Inventory returns groups sorted by opcode, not necessarily file order.
    # Walk only bounded headers; do not materialize chunk-index records here.
    stream.seek(size - 20)
    offsets = struct.unpack("<Q", stream.read(8))[0]
    end = offsets or size - 37
    while position < end:
        _deadline(deadline)
        stream.seek(position)
        opcode, length = struct.unpack("<BQ", stream.read(9))
        if length > MAX_CHUNK_BYTES or position + 9 + length > end:
            _fail("decode_summary_record_extent_changed")
        if opcode not in result:
            result[opcode] = [position, position]
        result[opcode][1] = position + 9 + length
        position += 9 + length
    return result


def _selection(inventory, topics):
    channels = {r["channel_id"]: r for r in inventory["channels"]}
    schemas = {r["schema_id"]: r for r in inventory["schemas"]}
    selected = {key: row for key, row in channels.items() if row["topic"] in topics}
    if set(topics) != {r["topic"] for r in selected.values()}:
        _fail("decode_requested_topic_absent")
    if len(selected) > MAX_CHANNELS or len({r["schema_id"] for r in selected.values()}) > MAX_SCHEMAS:
        _fail("decode_selected_descriptor_count_budget_exceeded")
    totals = Counter()
    for row in selected.values():
        count = row["advertised_message_count"]
        if type(count) is not int or count < 0:
            _fail("decode_advertised_selected_counts_required")
        totals[row["topic"]] += count
        schema = schemas.get(row["schema_id"])
        if row["message_encoding"] != "protobuf" or schema is None or schema["encoding"] != "protobuf":
            _fail("decode_selected_protobuf_schema_required")
    if any(count > MAX_TOPIC_MESSAGES for count in totals.values()) or sum(totals.values()) > MAX_TOTAL_MESSAGES:
        _fail("decode_advertised_message_budget_exceeded")
    return channels, schemas, selected, totals


def _decoders(stream, groups, selected, schemas, deadline):
    from mcap.records import Schema
    from mcap_protobuf.decoder import DecoderFactory
    needed = {row["schema_id"] for row in selected.values()}
    factory, decoders, total_bytes = DecoderFactory(), {}, 0
    for _, opcode, _, raw in _records(stream, *groups[3], deadline):
        if opcode != 3:
            _fail("decode_schema_group_changed")
        fields = _Fields(raw, [0]); key = fields.integer("<H")
        if key not in needed:
            continue
        name, encoding, length = fields.string(), fields.string(), fields.integer("<I")
        total_bytes += length
        if total_bytes > MAX_SCHEMA_BYTES:
            _fail("decode_selected_descriptor_bytes_budget_exceeded")
        data = bytes(fields.take(length)); expected = schemas[key]
        if (name != expected["name"] or encoding != expected["encoding"] or length != expected["data_size_bytes"] or
                hashlib.sha256(data).hexdigest() != expected["data_sha256"]):
            _fail("decode_embedded_schema_changed")
        decoder = factory.decoder_for("protobuf", Schema(id=key, name=name, encoding=encoding, data=data))
        if decoder is None:
            _fail("decode_selected_schema_unsupported")
        decoders[key] = decoder
        del fields, data, raw
    if set(decoders) != needed:
        _fail("decode_embedded_schema_missing")
    return decoders


def _stage_indexes(stream, groups, selected, deadline, db, resource_check):
    if 8 not in groups:
        _fail("decode_indexed_chunks_required_no_scan_fallback")
    db.execute("CREATE TABLE chunks (offset INTEGER PRIMARY KEY, length INTEGER, index_length INTEGER, first TEXT, last TEXT, compression TEXT, compressed INTEGER, uncompressed INTEGER, selected INTEGER, unindexed INTEGER)")
    count, previous, listing_ordered = 0, -1, True
    selected_ids = set(selected)
    for _, opcode, _, raw in _records(stream, *groups[8], deadline):
        if opcode != 8:
            _fail("decode_chunk_index_group_changed")
        fields = _Fields(raw, [0])
        first, last, offset, length = [fields.integer("<Q") for _ in range(4)]
        entries = fields.integers(); index_length = fields.integer("<Q")
        compression = fields.string(); compressed, uncompressed = fields.integer("<Q"), fields.integer("<Q")
        include = not entries or bool(selected_ids.intersection(entries))
        if include and max(length, uncompressed) > MAX_CHUNK_BYTES:
            _fail("decode_selected_chunk_budget_exceeded")
        listing_ordered = listing_ordered and offset > previous; previous = offset
        try:
            db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (offset, length, index_length, str(first), str(last), compression, compressed, uncompressed, int(include), int(not entries)))
        except sqlite3.IntegrityError:
            _fail("decode_duplicate_chunk_offset")
        count += 1
        if count % 1024 == 0:
            db.commit(); resource_check()
        del fields, entries, raw
    db.commit()
    previous_end = 8
    for offset, length, index_length in db.execute("SELECT offset,length,index_length FROM chunks ORDER BY offset"):
        _deadline(deadline)
        if offset < previous_end:
            _fail("decode_overlapping_chunk_or_message_index_ranges")
        previous_end = offset + length + index_length
    return count, listing_ordered


def _support_record(opcode, raw, selected, schemas):
    fields = _Fields(raw, [0]); key = fields.integer("<H")
    if opcode == 3 and key in {r["schema_id"] for r in selected.values()}:
        name, encoding, length = fields.string(), fields.string(), fields.integer("<I")
        data = fields.take(length); expected = schemas[key]
        if (name != expected["name"] or encoding != expected["encoding"] or length != expected["data_size_bytes"] or
                hashlib.sha256(data).hexdigest() != expected["data_sha256"]):
            _fail("decode_in_chunk_schema_disagrees_with_summary")
    if opcode == 4 and key in selected:
        schema = fields.integer("<H"); topic, encoding = fields.string(), fields.string()
        values = fields.pairs(fields.string, fields.string); expected = selected[key]
        if (schema != expected["schema_id"] or topic != expected["topic"] or encoding != expected["message_encoding"] or
                len(values) != expected["metadata_entry_count"]):
            _fail("decode_in_chunk_channel_disagrees_with_summary")


def _messages(data, channels, schemas, selected, decoders, counts, deadline, state):
    position, records = 0, 0
    while position < len(data):
        if records % 256 == 0:
            _deadline(deadline)
        records += 1
        if len(data) - position < 9:
            _fail("decode_chunk_inner_record_header_truncated")
        opcode, size = struct.unpack_from("<BQ", data, position); position += 9
        end = position + size
        if opcode == 0 or size > MAX_CHUNK_BYTES or end > len(data):
            _fail("decode_chunk_inner_record_length_invalid")
        if opcode in (3, 4):
            _support_record(opcode, memoryview(data)[position:end], selected, schemas)
        if opcode == 5:
            if size < 22:
                _fail("decode_message_header_truncated")
            key = struct.unpack_from("<H", data, position)[0]
            if key not in channels:
                _fail("decode_message_channel_missing_from_summary")
            if key in selected:
                state.update(phase="payload_decode", channel_id=key, schema_id=selected[key]["schema_id"])
                payload = data[position + 22:end]
                if state["selected_payload_bytes_processed"] + len(payload) > MAX_PAYLOAD_BYTES:
                    _fail("decode_selected_payload_bytes_budget_exceeded")
                message = decoders[selected[key]["schema_id"]](payload)
                if not message.IsInitialized():
                    _fail("decode_protobuf_required_fields_missing")
                del message, payload
                counts[key] += 1
                state["decoded_selected_message_count"] += 1
                state["selected_payload_bytes_processed"] += size - 22
                if counts[key] > selected[key]["advertised_message_count"]:
                    _fail("decode_channel_count_exceeds_advertised")
                if state["decoded_selected_message_count"] > MAX_TOTAL_MESSAGES:
                    _fail("decode_actual_message_budget_exceeded")
                state.update(phase="chunk_records", channel_id=None, schema_id=None)
        position = end


def _decompress(chunk):
    """Bound actual output, including LZ4 frames with dishonest size metadata."""
    if chunk.compression == "zstd":
        import zstandard
        parameters = zstandard.get_frame_parameters(chunk.data)
        if parameters.window_size > MAX_CHUNK_BYTES:
            _fail("decode_zstd_frame_window_budget_exceeded")
        if parameters.content_size not in (zstandard.CONTENTSIZE_UNKNOWN, zstandard.CONTENTSIZE_ERROR, chunk.uncompressed_size):
            _fail("decode_zstd_frame_content_size_mismatch")
        data = zstandard.ZstdDecompressor().decompress(chunk.data,
            max_output_size=max(1, chunk.uncompressed_size), allow_extra_data=False)
    elif chunk.compression == "lz4":
        import lz4.frame
        decoder = lz4.frame.LZ4FrameDecompressor()
        data = decoder.decompress(chunk.data, max_length=chunk.uncompressed_size + 1)
        if not decoder.eof or decoder.unused_data:
            _fail("decode_lz4_frame_incomplete_oversize_or_trailing_data")
    else:
        data = chunk.data
    if len(data) != chunk.uncompressed_size:
        _fail("decode_chunk_uncompressed_size_mismatch")
    if chunk.uncompressed_crc and zlib.crc32(data) != chunk.uncompressed_crc:
        from mcap.stream_reader import CRCValidationError
        raise CRCValidationError(chunk.uncompressed_crc, zlib.crc32(data), chunk)
    return data


def check_decoding(stream, size, inventory, topics, scratch, resource_check=lambda: None):
    """Process selected indexed streams; complete return or safe failure context.

    No SeekingReader, whole index list, decoded-message retention, timestamps
    sorting, geometry/feature construction, scan fallback or raw writes.
    """
    state = {"phase": "selection", "indexed_chunk_ordinal": None, "chunk_start_offset_bytes": None,
        "completed_selected_chunk_count": 0, "decoded_selected_message_count": 0,
        "selected_payload_bytes_processed": 0, "channel_id": None, "schema_id": None, "compression": None}
    deadline = time.monotonic() + MAX_DECODE_SECONDS
    try:
        topics = selected_topics(topics)
        channels, schemas, selected, expected_topics = _selection(inventory, topics)
        state["phase"] = "schema_load"
        groups = _groups(stream, size, deadline)
        decoders = _decoders(stream, groups, selected, schemas, deadline)
        state["phase"] = "index_staging"
        with TemporaryDirectory(prefix="mpr-decode-index-", dir=scratch) as temporary:
            database = Path(temporary)/"index.sqlite"
            with closing(sqlite3.connect(database)) as db:
                for pragma in ("page_size=4096", "cache_size=-8192", "journal_mode=OFF", "synchronous=OFF", "temp_store=FILE",
                               f"max_page_count={MAX_INDEX_BYTES // 4096}"):
                    db.execute("PRAGMA " + pragma)
                indexed, ordered = _stage_indexes(stream, groups, selected, deadline, db, resource_check)
                if indexed != inventory["chunk_index_summary"]["indexed_chunk_count"]:
                    _fail("decode_index_count_disagrees_with_inventory")
                selected_count = db.execute("SELECT COUNT(*) FROM chunks WHERE selected=1").fetchone()[0]
                unindexed = db.execute("SELECT COUNT(*) FROM chunks WHERE selected=1 AND unindexed=1").fetchone()[0]
                counts, checked, unavailable = Counter(), 0, 0
                from mcap.records import Chunk
                from mcap.stream_reader import StreamReader
                for ordinal, row in enumerate(db.execute("SELECT * FROM chunks ORDER BY offset")):
                    offset, length, _, first, last, compression, compressed, uncompressed, include, _ = row
                    if not include:
                        continue
                    _deadline(deadline)
                    state.update(phase="resource_check", indexed_chunk_ordinal=ordinal, chunk_start_offset_bytes=offset,
                                 compression=compression if compression in ("", "zstd", "lz4") else "unsupported")
                    if state["completed_selected_chunk_count"] % 128 == 0:
                        resource_check()
                    state["phase"] = "chunk_read"
                    stream.seek(offset); raw = stream.read(length)
                    if len(raw) != length or struct.unpack_from("<BQ", raw) != (6, length - 9):
                        _fail("decode_chunk_record_identity_or_length_mismatch")
                    chunk = next(StreamReader(BytesIO(raw), skip_magic=True, emit_chunks=True,
                                              record_size_limit=MAX_CHUNK_BYTES).records)
                    del raw
                    if (not isinstance(chunk, Chunk) or chunk.uncompressed_size != uncompressed or len(chunk.data) != compressed or
                            chunk.compression != compression or chunk.message_start_time != int(first) or chunk.message_end_time != int(last)):
                        _fail("decode_actual_chunk_header_disagrees_with_index")
                    if compression not in ("", "zstd", "lz4"):
                        _fail("decode_selected_compression_unsupported")
                    state["phase"] = "chunk_decompression"
                    crc = chunk.uncompressed_crc
                    data = _decompress(chunk)
                    del chunk
                    if crc:
                        checked += 1
                    else:
                        unavailable += 1
                    state["phase"] = "chunk_records"
                    _messages(data, channels, schemas, selected, decoders, counts, deadline, state)
                    del data
                    state["completed_selected_chunk_count"] += 1
                state["phase"] = "count_reconciliation"
                if any(counts[key] != row["advertised_message_count"] for key, row in selected.items()):
                    _fail("decode_selected_channel_count_mismatch")
                if state["completed_selected_chunk_count"] != selected_count:
                    _fail("decode_selected_chunk_count_mismatch")
        versions = [{**{k: row[k] for k in ("channel_id", "schema_id", "topic", "message_encoding", "advertised_message_count")},
            "schema_name": schemas[row["schema_id"]]["name"], "schema_encoding": schemas[row["schema_id"]]["encoding"],
            "schema_data_sha256": schemas[row["schema_id"]]["data_sha256"], "decoded_message_count": counts[key]}
            for key, row in sorted(selected.items())]
        return {"summary_crc_status": inventory["summary_crc_status"], "indexed_chunk_count": indexed,
            "index_ranges_and_unique_offsets_validated": True, "summary_index_listing_in_physical_order": ordered,
            "selected_indexed_chunk_count": selected_count, "skipped_indexed_chunk_count": indexed - selected_count,
            "selected_chunks_without_channel_indexes": unindexed, "completed_selected_chunk_count": selected_count,
            "selected_chunk_crc": {"checked_nonzero_count": checked, "unavailable_zero_count": unavailable},
            "decoded_selected_message_count": sum(counts.values()),
            "selected_payload_bytes_processed": state["selected_payload_bytes_processed"],
            "channel_versions": versions,
            "topics": [{"topic": topic, "advertised_message_count": expected_topics[topic],
                "decoded_message_count": sum(counts[key] for key, row in selected.items() if row["topic"] == topic),
                "channel_version_count": sum(row["topic"] == topic for row in selected.values())} for topic in topics]}
    except Exception as error:
        error.reader_failure_context = {**state, "exception_class": type(error).__name__, **_snapshot()}
        raise
