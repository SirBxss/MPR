"""Development-only velocity descriptor evidence and advertised I/O planning.

No message decoder, raw hash pass, training admission or speed policy lives here.
The reviewed request pins an accepted cohort snapshot; it is not a new split.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import time

from .recording_inventory import MAGIC, _Fields, _records, read_inventory

REVISION = "v0.19.19-velocity-summary-probe-a1"
TOPICS = ("/adp/velocity_vehicle_longitudinal", "/adp/vehicle_velocity", "/adp/odometry")
MAX_READ_BYTES = 128 * 1024**2
MAX_SECONDS = 60
MAX_CHUNKS = 100_000
MAX_JSON_BYTES = 8 * 1024**2


def require(condition, code):
    if not condition:
        raise ValueError(code)


def pinned_json(path, pin):
    require(isinstance(pin, str) and len(pin) == 64 and all(c in "0123456789abcdef" for c in pin), "probe_invalid_pin")
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "probe_json_budget")
    require(hashlib.sha256(raw).hexdigest() == pin, "probe_json_digest_mismatch")
    return json.loads(raw)


def scope(request, base):
    """Reject non-development roles before looking at the raw path, even stat()."""
    require(set(request) == {"revision", "outing_id", "recording_id", "raw_sha256", "size_bytes",
        "raw_path_private", "cohort_file", "cohort_sha256", "inventory_file", "inventory_sha256"}, "probe_request_fields")
    require(request["revision"] == REVISION, "probe_request_revision")
    cohort = pinned_json(base / request["cohort_file"], request["cohort_sha256"])
    require(cohort.get("cohort_lock_created") is True, "probe_locked_cohort_required")
    outings = [r for r in cohort["outings"] if r["outing_id"] == request["outing_id"]]
    require(len(outings) == 1 and outings[0]["cohort_role"] == "development", "probe_development_only")
    require(request["raw_sha256"] in outings[0]["raw_sha256"], "probe_raw_not_in_development_outing")
    inventory = pinned_json(base / request["inventory_file"], request["inventory_sha256"])
    rows = [r for r in inventory["recordings"] if r["recording_id"] == request["recording_id"]]
    require(inventory.get("purpose") == "development_only_recording_inventory" and len(rows) == 1,
        "probe_inventory_scope")
    row = rows[0]
    require(row["status"] == "complete" and row["raw_sha256"] == request["raw_sha256"] and
        type(request["size_bytes"]) is int and row["size_bytes"] == request["size_bytes"], "probe_inventory_identity")
    return row["inventory"]


class SummaryStream:
    """Read budget and section firewall; data-section reads are impossible here."""
    def __init__(self, stream, size, deadline):
        self.stream, self.deadline = stream, deadline
        self.bytes_read = 0
        self.allowed = ((0, 17), (size - 37, size))
        require(size >= 45, "probe_not_mcap")
        self.seek(0)
        prefix = self.read(17)
        require(prefix[:8] == MAGIC and prefix[8] == 1, "probe_not_mcap")
        header_end = 17 + struct.unpack("<Q", prefix[9:])[0]
        self.seek(size - 37)
        footer = self.read(37)
        require(footer[:9] == struct.pack("<BQ", 2, 20) and footer[29:] == MAGIC, "probe_footer")
        self.summary_start, self.offset_start = struct.unpack("<QQ", footer[9:25])
        self.summary_end = self.offset_start or size - 37
        require(17 <= header_end <= 65536 and header_end <= self.summary_start - 13 and
            self.summary_start <= self.summary_end <= size - 37, "probe_sections_or_header_budget")
        self.allowed = ((0, header_end), (self.summary_start - 13, size))

    def seek(self, offset):
        self.stream.seek(offset)

    def tell(self):
        return self.stream.tell()

    def read(self, size):
        require(time.monotonic() <= self.deadline, "probe_time_budget")
        position = self.tell()
        require(type(size) is int and size >= 0 and any(a <= position and position + size <= b for a, b in self.allowed),
            "probe_data_section_read_forbidden")
        require(self.bytes_read + size <= MAX_READ_BYTES, "probe_read_budget")
        raw = self.stream.read(size)
        self.bytes_read += len(raw)
        require(len(raw) == size, "probe_truncated")
        return raw


def describe(raw, root_name):
    """Export declarations, including enums/presence hints; infer no units/clocks."""
    from google.protobuf.descriptor_pb2 import FileDescriptorSet, FieldDescriptorProto
    descriptor = FileDescriptorSet.FromString(raw)
    require(len(descriptor.file) <= 256, "probe_descriptor_file_budget")
    messages, enums, files = [], [], []

    def enum(value, parent):
        enums.append({"name": parent + value.name, "values": [{"name": v.name, "number": v.number} for v in value.value]})

    def message(value, parent, syntax):
        name = parent + value.name
        messages.append({"name": name, "syntax": syntax, "oneofs": [o.name for o in value.oneof_decl],
            "fields": [{"name": f.name, "number": f.number, "type": FieldDescriptorProto.Type.Name(f.type),
                "type_name": f.type_name, "label": FieldDescriptorProto.Label.Name(f.label),
                "proto3_optional": f.proto3_optional, "oneof_index": f.oneof_index if f.HasField("oneof_index") else None,
                "declared_default": f.default_value if f.HasField("default_value") else None} for f in value.field]})
        require(sum(len(m["fields"]) for m in messages) <= 20000, "probe_descriptor_field_budget")
        for e in value.enum_type:
            enum(e, name + ".")
        for m in value.nested_type:
            message(m, name + ".", syntax)

    for file in descriptor.file:
        syntax = file.syntax or "proto2"
        files.append({"name": file.name, "package": file.package, "syntax": syntax, "dependencies": list(file.dependency)})
        parent = file.package + "." if file.package else ""
        for value in file.enum_type:
            enum(value, parent)
        for value in file.message_type:
            message(value, parent, syntax)
    require(any(m["name"] == root_name for m in messages), "probe_schema_root_missing")
    return {"root_name": root_name, "files": files, "messages": messages, "enums": enums,
        "interpretation": "Declarations only. Units, coordinate/reference point, qualifier meanings and timestamp clock/availability need producer evidence. Omitted proto3 scalars may decode to defaults; a default is not validity evidence."}


def inspect_summary(stream, size, expected):
    deadline = time.monotonic() + MAX_SECONDS
    guarded = SummaryStream(stream, size, deadline)
    observed = read_inventory(guarded, size)
    require(observed == expected, "probe_fresh_summary_differs_from_accepted_inventory")
    channels = [r for r in observed["channels"] if r["topic"] in TOPICS]
    require(all(sum(r["topic"] == t for r in channels) == 1 for t in TOPICS), "probe_topics_missing_or_ambiguous")
    require(all(r["message_encoding"] == "protobuf" and r["schema_id"] for r in channels), "probe_protobuf_required")
    schemas = {r["schema_id"]: r for r in observed["schemas"]}
    wanted = {r["schema_id"] for r in channels}
    descriptors, declarations = {}, {}
    costs = {name: {"chunk_count": 0, "chunk_record_bytes": 0, "uncompressed_bytes": 0,
        "maximum_chunk_bytes": 0} for name in (*TOPICS, "direct_topics_union", "all_three_union")}
    by_topic = {r["topic"]: r["channel_id"] for r in channels}
    groups = {r["opcode"]: r for r in observed["summary_record_groups"]}
    require(3 in groups and 8 in groups, "probe_indexed_summary_required")
    # Inventory has already validated grouped summary records. One second pass
    # extracts just the three descriptors and aggregates indexes without payload.
    ranges, unknown = [], 0
    for offset, opcode, length, raw in _records(guarded, guarded.summary_start, guarded.summary_end, deadline):
        fields = _Fields(raw, [0])
        if opcode == 3:
            key = fields.integer("<H")
            if key in wanted:
                name, encoding = fields.string(), fields.string()
                data = bytes(fields.take(fields.integer("<I")))
                expected_schema = schemas[key]
                require(encoding == "protobuf" and name == expected_schema["name"] and
                    len(data) == expected_schema["data_size_bytes"] and
                    hashlib.sha256(data).hexdigest() == expected_schema["data_sha256"], "probe_descriptor_identity")
                descriptors[key] = data
                declarations[str(key)] = describe(data, name)
        elif opcode == 8:
            first, last, location, chunk_length = [fields.integer("<Q") for _ in range(4)]
            entries = fields.integers()
            index_length = fields.integer("<Q")
            fields.string()  # Compression name is already retained by inventory.
            fields.integer("<Q")
            uncompressed = fields.integer("<Q")
            require(len(ranges) < MAX_CHUNKS, "probe_chunk_count_budget")
            ranges.append((location, location + chunk_length + index_length))
            unknown += int(not entries)
            selected = {t for t, key in by_topic.items() if not entries or key in entries}
            names = set(selected)
            if selected.intersection(TOPICS[:2]):
                names.add("direct_topics_union")
            if selected:
                names.add("all_three_union")
            for name in names:
                cost = costs[name]
                cost["chunk_count"] += 1
                cost["chunk_record_bytes"] += chunk_length
                cost["uncompressed_bytes"] += uncompressed
                cost["maximum_chunk_bytes"] = max(cost["maximum_chunk_bytes"], chunk_length, uncompressed)
    require(set(descriptors) == wanted, "probe_descriptors_incomplete")
    previous_end = 8
    for start, end in sorted(ranges):
        require(start >= previous_end, "probe_overlapping_chunk_ranges")
        previous_end = end
    return {"channels": channels, "schemas": [schemas[k] for k in sorted(wanted)], "declarations": declarations,
        "advertised_chunk_cost": costs, "unknown_channel_chunk_count": unknown,
        "summary_crc_status": observed["summary_crc_status"], "raw_bytes_read": guarded.bytes_read,
        "elapsed_seconds": time.monotonic() - deadline + MAX_SECONDS}, descriptors


def run(request_path, request_sha256, output):
    request_path, output = Path(request_path).absolute(), Path(output).absolute()
    request = pinned_json(request_path, request_sha256)
    expected = scope(request, request_path.parent)
    # Reject output collisions before raw access; exclusive creation follows.
    require(not output.exists() and not output.is_symlink(), "probe_output_must_be_new")
    require(output.parent.is_dir() and not output.parent.is_symlink(), "probe_output_parent_required")
    path = Path(request["raw_path_private"])
    require(path.is_absolute() and not path.is_symlink() and path.resolve() == path, "probe_canonical_raw_path_required")
    require(path not in (output, output.parent), "probe_output_input_collision")
    output.mkdir()
    report = {"revision": REVISION, "request_sha256": request_sha256, "outing_id": request["outing_id"],
        "recording_id": request["recording_id"], "registered_raw_sha256_provenance_only": request["raw_sha256"],
        "current_full_raw_hash_verified": False, "model_fitted": False, "message_payloads_decoded": False,
        "numeric_conditions_exported": False, "speed_policy_adopted": False, "temporal_recovery_established": False,
        "limits": {"read_bytes": MAX_READ_BYTES, "cooperative_seconds": MAX_SECONDS, "chunks": MAX_CHUNKS},
        "interpretation": "Summary-only evidence on one development recording. Advertised chunk costs are not measured decode costs or message validity. Matching accepted summaries does not verify the full current raw-file hash. No units, clock availability, speed eligibility or recovered sequence claim follows."}
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size == request["size_bytes"], "probe_raw_size_or_type_changed")
            evidence, descriptors = inspect_summary(stream, before.st_size, expected)
            after = os.fstat(stream.fileno())
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "probe_raw_changed_during_read")
        report.update(status="complete", **evidence)
        for key, raw in descriptors.items():
            (output / f"schema_{key}.pb").write_bytes(raw)
    except BaseException as error:
        report.update(status="incomplete", failure_class=type(error).__name__)
        # Fixed internal codes only; third-party exception text stays private.
        if type(error) is ValueError and str(error).startswith("probe_"):
            report["failure_code"] = str(error)
        raise
    finally:
        (output / "report.private.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
