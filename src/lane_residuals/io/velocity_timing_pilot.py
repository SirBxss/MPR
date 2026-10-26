"""One fixed indexed log-window probe; no residual extraction or model fitting."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
from tempfile import TemporaryDirectory
import time
import zipfile

from ..domain.velocity_timing import TOPICS, AGE_NS
from . import recording_decode_check as decoder
from .recording_inventory import read_inventory
from .recording_readiness_resources import configure
from .velocity_summary_probe import pinned_json, require, scope

REVISION = "v0.19.20-velocity-timing-pilot-a2"
LIMITS = {"maximum_raw_file_bytes": 2*1024**3, "hash_seconds": 120,
    "processing_seconds": 120, "metadata_read_bytes": 128*1024**2,
    "selected_chunk_read_bytes": 128*1024**2, "expanded_chunk_bytes": 512*1024**2,
    "single_chunk_bytes": 4*1024**2, "selected_chunks": 2048,
    "decoded_messages": 50000, "index_database_bytes": 32*1024**2}
WINDOW_NS, PADDING_NS = 12_000_000_000, 1_000_000_000


def design_sha256(request):
    """Canonical scientific identities, independent of JSON formatting/paths."""
    identity = request["summary_scope"]
    value = {"revision": request["revision"], "identity": {k: identity[k] for k in
        ("outing_id", "recording_id", "raw_sha256", "size_bytes", "cohort_sha256", "inventory_sha256")},
        "numeric_summary_sha256": request["numeric_summary_sha256"],
        "window_start_log_ns": str(int(request["window_start_log_ns"])),
        "window_end_log_ns": str(int(request["window_end_log_ns"])),
        "padding_ns": PADDING_NS, "exploratory_age_ns": AGE_NS}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixed_window_start(rows):
    """Earliest sustained geometry run, independent of speed/condition validity."""
    first, previous = None, None
    for row in rows:
        if not row["residual_available"]:
            first, previous = None, None
            continue
        t = int(row["estimate_source_time_ns_decimal_private"])
        log = int(row["estimate_log_time_ns_decimal_private"])
        adjacent = previous is not None and row["recording_id"] == previous["recording_id"] and \
            row["estimate_message_index"] == previous["estimate_message_index"]+1 and row["pair_index"] == previous["pair_index"]+1 and \
            0 < t-int(previous["estimate_source_time_ns_decimal_private"]) <= 200_000_000 and \
            log >= int(previous["estimate_log_time_ns_decimal_private"])
        if not adjacent:
            first = row
        if t-int(first["estimate_source_time_ns_decimal_private"]) >= WINDOW_NS and \
                log-int(first["estimate_log_time_ns_decimal_private"]) >= WINDOW_NS:
            return int(first["estimate_log_time_ns_decimal_private"])
        previous = row
    raise ValueError("pilot_no_sustained_geometry_window")


def load_request(path, pin):
    path = Path(path).absolute()
    request = pinned_json(path, pin)
    require(set(request) == {"revision", "summary_scope", "numeric_summary_file", "numeric_summary_sha256",
        "audit_file", "numeric_file", "window_start_log_ns", "window_end_log_ns"}, "pilot_request_fields")
    require(request["revision"] == REVISION, "pilot_revision")
    expected = scope(request["summary_scope"], path.parent)
    numeric = pinned_json(path.parent/request["numeric_summary_file"], request["numeric_summary_sha256"])
    require(numeric["status"] == "complete" and numeric["preserved_inventory_report_sha256"] ==
        request["summary_scope"]["inventory_sha256"], "pilot_numeric_inventory_lineage")
    audit = pinned_json(path.parent/request["audit_file"], numeric["artifacts_sha256"]["candidate_audit.json"])
    rows = audit["rows"]
    require(bool(rows) and all(r["recording_id"] == request["summary_scope"]["recording_id"] for r in rows), "pilot_cached_recording_mismatch")
    start, end = int(request["window_start_log_ns"]), int(request["window_end_log_ns"])
    require(start == fixed_window_start(rows) and end-start == WINDOW_NS, "pilot_fixed_sustained_geometry_window")
    targets = [r for r in rows if start <= int(r["estimate_log_time_ns_decimal_private"]) < end]
    require(bool(targets), "pilot_empty_target_window")
    # Only the accepted old speed column is read; neither X nor residual Y is fitted/exported.
    with (path.parent/request["numeric_file"]).open("rb") as stream:
        payload = stream.read(16*1024**2+1)
    require(len(payload) <= 16*1024**2 and hashlib.sha256(payload).hexdigest() ==
        numeric["artifacts_sha256"]["residuals.npz"], "pilot_numeric_payload_digest")
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        require(sum(i.file_size for i in archive.infolist()) <= 64*1024**2, "pilot_numeric_expansion_budget")
    import numpy as np
    with np.load(BytesIO(payload), allow_pickle=False) as arrays:
        indices, candidates, conditions = arrays["conditioned_profile_indices"], arrays["candidate_index"], arrays["conditions"]
        require(len(indices) == len(conditions) and conditions.ndim == 2 and conditions.shape[1] == 6, "pilot_old_condition_layout")
        old_speed = {int(candidates[i]): float(v[0]) for i, v in zip(indices, conditions)}
    require(all(math.isfinite(v) for v in old_speed.values()), "pilot_old_speed_nonfinite")
    return request, expected, targets, old_speed


class Metered:
    def __init__(self, stream, deadline):
        self.stream, self.deadline = stream, deadline
        self.phase = "metadata"
        self.used = {"metadata": 0, "selected_chunk": 0}

    def seek(self, offset):
        self.stream.seek(offset)

    def tell(self):
        return self.stream.tell()

    def read(self, size):
        require(time.monotonic() <= self.deadline, "pilot_processing_timeout")
        require(type(size) is int and size >= 0 and self.used[self.phase]+size <= LIMITS[self.phase+"_read_bytes"], "pilot_read_budget")
        raw = self.stream.read(size)
        self.used[self.phase] += len(raw)
        require(len(raw) == size, "pilot_truncated_read")
        return raw


def file_identity(stream):
    value = os.fstat(stream.fileno())
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def verify_raw(stream, identity):
    require(0 < identity["size_bytes"] <= LIMITS["maximum_raw_file_bytes"], "pilot_raw_file_budget")
    require(file_identity(stream)[2] == identity["size_bytes"], "pilot_raw_size_changed")
    stream.seek(0)
    digest, count = hashlib.sha256(), 0
    started = time.monotonic()
    while count < identity["size_bytes"]:
        require(time.monotonic()-started <= LIMITS["hash_seconds"], "pilot_hash_timeout")
        raw = stream.read(min(1024**2, identity["size_bytes"]-count))
        require(bool(raw), "pilot_raw_hash_truncated")
        digest.update(raw)
        count += len(raw)
    require(digest.hexdigest() == identity["raw_sha256"], "pilot_raw_hash_mismatch")
    return {"bytes": count, "elapsed_seconds": time.monotonic()-started, "sha256": digest.hexdigest()}


class Sink:
    def __init__(self, selected, window):
        self.selected, self.window = selected, window
        self.records = []
        self.chunk_bounds = None

    def consume(self, key, log, publish, message):
        require(self.chunk_bounds[0] <= log <= self.chunk_bounds[1], "pilot_message_outside_index_log_bounds")
        if not self.window[0] <= log <= self.window[1]:
            return
        topic = self.selected[key]["topic"]
        present = True
        outer, standstill = None, None
        if topic == TOPICS[1]:
            present = message.HasField("velocity")
            outer, standstill = int(message.qualifier), int(message.status_velocity_near_standstill)
            message = message.velocity
        value = float(message.value)
        self.records.append({"topic": topic, "log_ns": str(log), "publish_ns": str(publish),
            "source_ns": str(int(message.timestamp)), "value": value if math.isfinite(value) else None,
            "qualifier": int(message.qualifier), "outer_qualifier": outer, "standstill_status": standstill,
            "nested_present": present, "non_default_decoded_fields": [f.name for f, _ in message.ListFields()]})


def prepare_window(stream, size, expected, window, scratch):
    """Summary/index-only affordability check; no hash, claim or message reads."""
    started = time.monotonic()
    deadline = started+LIMITS["processing_seconds"]
    metered = Metered(stream, deadline)
    require(read_inventory(metered, size) == expected, "pilot_fresh_inventory_changed")
    channels, schemas, selected, _ = decoder._selection(expected, TOPICS)
    require(all(sum(c["topic"] == t for c in selected.values()) == 1 for t in TOPICS), "pilot_ambiguous_topics")
    roots = {TOPICS[0]: "Adp.QualifiedTimedFloat64", TOPICS[1]: "Adp.VehicleVelocity"}
    require(all(schemas[c["schema_id"]]["name"] == roots[c["topic"]] for c in selected.values()), "pilot_root_schema_mismatch")
    groups = decoder._groups(metered, size, deadline)
    decoders = decoder._decoders(metered, groups, selected, schemas, deadline)
    calls = [0]
    def bounded(function):
        def decode(payload):
            require(calls[0] < LIMITS["decoded_messages"], "pilot_message_count_budget")
            calls[0] += 1
            return function(payload)
        return decode
    decoders = {key: bounded(value) for key, value in decoders.items()}
    with TemporaryDirectory(prefix="mpr-velocity-index-", dir=scratch) as temporary:
        with closing(sqlite3.connect(Path(temporary)/"index.sqlite")) as db:
            configure(db, LIMITS["index_database_bytes"])
            indexed, _ = decoder._stage_indexes(metered, groups, selected, deadline, db, lambda: None)
            require(indexed == expected["chunk_index_summary"]["indexed_chunk_count"], "pilot_index_count_changed")
            plan = [r for r in db.execute("SELECT * FROM chunks WHERE selected=1 ORDER BY offset")
                if int(r[3]) <= window[1] and int(r[4]) >= window[0]]
            require(bool(plan) and len(plan) <= LIMITS["selected_chunks"], "pilot_window_chunk_count_budget")
            require(sum(r[1] for r in plan) <= LIMITS["selected_chunk_read_bytes"] and
                sum(r[7] for r in plan) <= LIMITS["expanded_chunk_bytes"] and
                all(max(r[1], r[7]) <= LIMITS["single_chunk_bytes"] for r in plan), "pilot_planned_window_budget")
    upper = sum(c["advertised_message_count"] for c in selected.values())
    require(upper <= LIMITS["decoded_messages"], "pilot_advertised_message_count_budget")
    elapsed = time.monotonic()-started
    require(elapsed <= LIMITS["processing_seconds"], "pilot_processing_timeout")
    summary = {"indexed_chunks": indexed, "window_chunks": len(plan),
        "selected_chunk_record_bytes": sum(r[1] for r in plan), "expanded_chunk_bytes": sum(r[7] for r in plan),
        "selected_recording_message_upper_bound": upper, "metadata_bytes_read": metered.used["metadata"],
        "metadata_elapsed_seconds": elapsed, "padded_window_log_ns": [str(v) for v in window],
        "payload_decode_performed_during_planning": False, "full_raw_hash_performed_during_planning": False}
    return {"channels": channels, "schemas": schemas, "selected": selected, "decoders": decoders,
        "metered": metered, "window": window, "plan": plan, "summary": summary}


def decode_prepared(prepared):
    """Consume an already affordable plan, without a second metadata pass."""
    from mcap.records import Chunk
    from mcap.stream_reader import StreamReader
    started = time.monotonic()
    metered = prepared["metered"]
    deadline = started+LIMITS["processing_seconds"]-prepared["summary"]["metadata_elapsed_seconds"]
    metered.deadline = deadline  # Hash time is separate from processing time.
    sink = Sink(prepared["selected"], prepared["window"])
    counts, crc_checked, expanded = Counter(), 0, 0
    state = {"decoded_selected_message_count": 0, "selected_payload_bytes_processed": 0}
    for row in prepared["plan"]:
        offset, length, _, first, last, compression, compressed, uncompressed, _, _ = row
        require(time.monotonic() <= deadline, "pilot_processing_timeout")
        metered.phase = "selected_chunk"
        metered.seek(offset)
        raw = metered.read(length)
        require(struct.unpack_from("<BQ", raw) == (6, length-9), "pilot_chunk_record_changed")
        chunk = next(StreamReader(BytesIO(raw), skip_magic=True, emit_chunks=True,
            record_size_limit=LIMITS["single_chunk_bytes"]).records)
        require(isinstance(chunk, Chunk) and chunk.uncompressed_size == uncompressed and len(chunk.data) == compressed and
            chunk.compression == compression and chunk.message_start_time == int(first) and chunk.message_end_time == int(last),
            "pilot_chunk_header_changed")
        require(compression in ("", "zstd", "lz4"), "pilot_compression_unsupported")
        data = decoder._decompress(chunk)
        expanded += len(data)
        crc_checked += bool(chunk.uncompressed_crc)
        sink.chunk_bounds = (int(first), int(last))
        decoder._messages(data, prepared["channels"], prepared["schemas"], prepared["selected"],
            prepared["decoders"], counts, deadline, state, sink)
        require(state["decoded_selected_message_count"] <= LIMITS["decoded_messages"], "pilot_message_count_budget")
        del raw, data, chunk
    return sink.records, {"indexed_chunks": prepared["summary"]["indexed_chunks"], "window_chunks": len(prepared["plan"]),
        "nonzero_chunk_crcs_checked": crc_checked,
        "zero_chunk_crcs_unavailable": len(prepared["plan"])-crc_checked, "read_bytes_by_phase": metered.used,
        "expanded_chunk_bytes": expanded, "decoded_selected_messages_in_touched_chunks": state["decoded_selected_message_count"],
        "messages_retained_in_padded_log_window": len(sink.records),
        "elapsed_seconds": time.monotonic()-started+prepared["summary"]["metadata_elapsed_seconds"],
        "padded_window_log_ns": [str(v) for v in prepared["window"]], "full_recording_decoded": False}


def decode_window(stream, size, expected, window, scratch):
    """Convenience wrapper for synthetic reader checks, not an owner bypass."""
    return decode_prepared(prepare_window(stream, size, expected, window, scratch))
