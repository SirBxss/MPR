"""Inventory tests use unreadable message bytes: payload validity is separate."""

import hashlib
import io
import json
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib
from pathlib import Path

from lane_residuals.io import recording_inventory as inventory


def record(opcode, data):
    return struct.pack("<BQ", opcode, len(data)) + data


def string(value):
    raw = value.encode()
    return struct.pack("<I", len(raw)) + raw


def integer_map(pairs):
    raw = b"".join(struct.pack("<HQ", key, value) for key, value in pairs)
    return struct.pack("<I", len(raw)) + raw


def fixture(*, crc=True, counts=True, statistics=True, offsets=True, chunk_repeats=1,
            schema=b"unknown opaque descriptor", channel_schema=1, extra_groups=(), metadata=True):
    header = record(1, string("unknown-profile") + string("private producer name"))
    chunk_start = len(inventory.MAGIC + header)
    chunk = record(6, b"not a decodable chunk")
    metadata_record = record(12, b"PRIVATE SOURCE LOCATOR; do not inspect") if metadata else b""
    data = chunk + metadata_record + record(15, struct.pack("<I", 0))
    schema_data = struct.pack("<H", 1) + string("Unknown.Schema") + string("unknown-encoding") + struct.pack("<I", len(schema)) + schema
    private = string("build-key") + string("private configuration")
    channel = struct.pack("<HH", 7, channel_schema) + string("/new/topic") + string("opaque") + struct.pack("<I", len(private)) + private
    chunk_index = struct.pack("<QQQQ", 2**63, 2**63 + 4, chunk_start, len(chunk)) + integer_map([]) + struct.pack("<Q", 0) + string("zstd") + struct.pack("<QQ", 4, 10)
    stats = struct.pack("<QHIIIIQQ", 3, 1, 1, 0, int(metadata), chunk_repeats, 2**63, 2**63+4) + integer_map([(7, 3)] if counts else [])
    groups = [(3, record(3, schema_data)), (4, record(4, channel)), (8, record(8, chunk_index) * chunk_repeats)]
    if statistics:
        groups.append((11, record(11, stats)))
    if metadata:
        groups.append((13, record(13, struct.pack("<QQ", chunk_start+len(chunk), len(metadata_record)) + string("PRIVATE metadata name"))))
    groups.extend(extra_groups)
    return assemble(inventory.MAGIC + header + data, groups, crc=crc, offsets=offsets)


def assemble(prefix, groups, *, crc=True, offsets=True):
    summary_start = len(prefix)
    offset_records, summary, position = [], b"", summary_start
    for opcode, raw in groups:
        offset_records.append(record(14, struct.pack("<BQQ", opcode, position, len(raw))))
        summary += raw
        position += len(raw)
    offset_start = position if offsets else 0
    offset_bytes = b"".join(offset_records) if offsets else b""
    footer_prefix = struct.pack("<BQQQ", 2, 20, summary_start, offset_start)
    checksum = zlib.crc32(summary + offset_bytes + footer_prefix) if crc else 0
    return prefix + summary + offset_bytes + footer_prefix + struct.pack("<I", checksum) + inventory.MAGIC


def split(raw):
    start, offsets = struct.unpack("<QQ", raw[-28:-12])
    position, groups = start, []
    while position < (offsets or len(raw)-37):
        opcode, size = struct.unpack("<BQ", raw[position:position+9])
        groups.append((opcode, raw[position:position+9+size]))
        position += 9+size
    return raw[:start], groups


class InventoryIoTests(unittest.TestCase):
    def read(self, raw):
        return inventory.read_inventory(io.BytesIO(raw), len(raw))

    def test_unknown_schema_and_private_metadata_are_inventoried_without_payload_reads(self):
        raw = fixture()
        prefix, _ = split(raw)
        header_end = 17 + struct.unpack("<Q", raw[9:17])[0]
        data_end = len(prefix)-13
        class SummaryOnly(io.BytesIO):
            def read(self, size=-1):
                if header_end <= self.tell() < data_end:
                    raise AssertionError("message/metadata data section was read")
                return super().read(size)
        result = inventory.read_inventory(SummaryOnly(raw), len(raw))
        self.assertEqual(result["summary_crc_status"], "validated")
        self.assertEqual(result["topics"], [{"topic": "/new/topic", "channel_count": 1, "advertised_message_count": 3}])
        self.assertEqual(result["schemas"][0]["data_sha256"], hashlib.sha256(b"unknown opaque descriptor").hexdigest())
        self.assertEqual(result["channels"][0]["metadata_entry_count"], 1)
        self.assertEqual(result["advertised_statistics"]["log_start_ns_decimal"], str(2**63))
        self.assertEqual(result["auxiliary_indexes"]["metadata_index_count"], 1)
        for secret in ("private producer", "private configuration", "PRIVATE", "unknown opaque descriptor"):
            self.assertNotIn(secret, json.dumps(result))

    def test_crc_zero_statistics_absence_and_unavailable_count_map_remain_explicit(self):
        for options in ({"crc": False}, {"statistics": False}, {"counts": False}):
            result = self.read(fixture(**options))
            if options.get("crc") is False:
                self.assertEqual(result["summary_crc_status"], "unavailable")
            else:
                self.assertIsNone(result["topics"][0]["advertised_message_count"])
            if options.get("statistics") is False:
                self.assertIsNone(result["advertised_statistics"])

    def test_summary_crc_corruption_fails_before_publishing_counts(self):
        raw = bytearray(fixture()); prefix, _ = split(raw)
        raw[len(prefix)+15] ^= 1
        with self.assertRaisesRegex(ValueError, "summary_crc_mismatch"):
            self.read(raw)

    def test_summary_without_offsets_and_extension_fields_are_supported(self):
        prefix, groups = split(fixture())
        opcode, raw = groups[0]
        groups[0] = (opcode, record(opcode, raw[9:] + b"future extension"))
        result = self.read(assemble(prefix, groups, offsets=False))
        self.assertFalse(result["summary_offsets_present"])
        self.assertEqual(len(result["schemas"]), 1)

    def test_standard_writer_empty_offset_group_is_allowed_but_duplicates_are_rejected(self):
        raw = fixture(crc=False)
        start, offsets = struct.unpack("<QQ", raw[-28:-12])
        empty = record(14, struct.pack("<BQQ", 10, offsets, 0))
        changed = raw[:-37]+empty+raw[-37:]
        self.assertEqual(self.read(changed)["summary_offsets_present"], True)
        duplicated = raw[:-37]+empty+empty+raw[-37:]
        with self.assertRaisesRegex(ValueError, "summary_offset_mismatch"):
            self.read(duplicated)

    def test_advertised_zero_is_distinct_from_unavailable_counts(self):
        prefix, groups = split(fixture(counts=False))
        stats = bytearray(groups[3][1][9:]); stats[:8] = struct.pack("<Q", 0); stats[26:42] = struct.pack("<QQ", 0, 0)
        groups[3] = (11, record(11, stats))
        chunk = bytearray(groups[2][1][9:]); chunk[:16] = struct.pack("<QQ", 0, 0)
        groups[2] = (8, record(8, chunk))
        result = self.read(assemble(prefix, groups))
        self.assertEqual(result["channels"][0]["advertised_message_count"], 0)

    def test_schema_zero_channel_is_legal_and_multiple_versions_on_one_topic_are_kept(self):
        result = self.read(fixture(channel_schema=0))
        self.assertEqual(result["channels"][0]["schema_id"], 0)
        prefix, groups = split(fixture(statistics=False))
        other_schema = record(3, struct.pack("<H", 2) + string("Unknown.Schema") + string("other") + struct.pack("<I", 1) + b"x")
        groups[0] = (3, groups[0][1] + other_schema)
        other_channel = record(4, struct.pack("<HH", 8, 2) + string("/new/topic") + string("other") + struct.pack("<I", 0))
        groups[1] = (4, groups[1][1] + other_channel)
        result = self.read(assemble(prefix, groups))
        self.assertEqual(len(result["schemas"]), 2)
        self.assertEqual(result["topics"][0]["channel_count"], 2)
        self.assertIsNone(result["topics"][0]["advertised_message_count"])

    def test_duplicate_ids_missing_schema_and_invalid_maps_fail_closed(self):
        prefix, groups = split(fixture())
        for index, code in ((0, "duplicate_schema_id"), (1, "duplicate_channel_id")):
            changed = list(groups); changed[index] = (groups[index][0], groups[index][1]*2)
            with self.assertRaisesRegex(ValueError, code): self.read(assemble(prefix, changed))
        with self.assertRaisesRegex(ValueError, "channel_schema_missing"):
            self.read(fixture(channel_schema=99))
        changed = list(groups)
        stats = changed[3][1][9:51] + integer_map([(7, 1), (7, 2)])
        changed[3] = (11, record(11, stats))
        with self.assertRaisesRegex(ValueError, "duplicate_map_entry"):
            self.read(assemble(prefix, changed))

    def test_inconsistent_statistics_and_chunk_bounds_are_not_accepted(self):
        prefix, groups = split(fixture())
        changed = list(groups); stats = bytearray(changed[3][1][9:]); stats[0] = 4
        changed[3] = (11, record(11, stats))
        with self.assertRaisesRegex(ValueError, "message_count_mismatch"):
            self.read(assemble(prefix, changed))
        changed = list(groups); chunk = bytearray(changed[2][1][9:]); chunk[16:24] = struct.pack("<Q", len(prefix)+1)
        changed[2] = (8, record(8, chunk))
        with self.assertRaisesRegex(ValueError, "invalid_chunk_index"):
            self.read(assemble(prefix, changed))
        changed = list(groups); stats = bytearray(changed[3][1][9:]); stats[34:42] = struct.pack("<Q", 2**63)
        changed[3] = (11, record(11, stats))
        with self.assertRaisesRegex(ValueError, "chunk_time_mismatch"):
            self.read(assemble(prefix, changed))

    def test_oversized_record_summary_text_timeout_and_record_count_fail_before_unbounded_read(self):
        raw = fixture()
        for name, limit, code in (("MAX_RECORD_BYTES", 10, "invalid_header"),
                                   ("MAX_SUMMARY_BYTES", 10, "summary_budget"),
                                   ("MAX_TEXT_BYTES", 1, "text_budget"),
                                   ("MAX_SUMMARY_RECORDS", 1, "record_count_budget")):
            with patch.object(inventory, name, limit):
                with self.assertRaisesRegex(ValueError, code): self.read(raw)
        with patch.object(inventory.time, "monotonic", side_effect=[0, 301]):
            with self.assertRaisesRegex(ValueError, "summary_timeout"): self.read(raw)
        prefix, groups = split(raw)
        groups[0] = (3, struct.pack("<BQ", 3, inventory.MAX_RECORD_BYTES+1))
        with self.assertRaisesRegex(ValueError, "record_budget"): self.read(assemble(prefix, groups))

    def test_invalid_magic_footer_no_summary_and_group_offsets_are_explicit(self):
        raw = fixture()
        for changed, code in ((b"x"+raw[1:], "not_mcap"), (raw[:-1]+b"x", "invalid_footer")):
            with self.assertRaisesRegex(ValueError, code): self.read(changed)
        no_summary = raw[:-28] + struct.pack("<QQI", 0, 0, 0) + inventory.MAGIC
        with self.assertRaisesRegex(ValueError, "summary_absent_no_scan_fallback"): self.read(no_summary)
        changed = bytearray(fixture(crc=False)); _, offsets = struct.unpack("<QQ", changed[-28:-12]); changed[offsets+10] = 0
        with self.assertRaisesRegex(ValueError, "summary_offset_mismatch"): self.read(changed)

    def test_large_chunk_index_group_retains_no_index_list(self):
        raw = fixture(chunk_repeats=20_000)
        result = self.read(raw)
        self.assertEqual(result["chunk_index_summary"]["indexed_chunk_count"], 20_000)
        self.assertNotIn("chunk_indexes", result)
        self.assertLess(len(json.dumps(result)), 5000)

    def test_truncation_utf8_regrouping_and_auxiliary_count_conflicts_fail_closed(self):
        prefix, groups = split(fixture())
        cases = []
        altered = list(groups); altered[0] = (3, record(3, b"\x01\x00\xff")); cases.append((altered, "field_outside"))
        altered = list(groups); raw = bytearray(altered[0][1][9:]); raw[6] = 255
        altered[0] = (3, record(3, raw)); cases.append((altered, "invalid_utf8"))
        cases.append((groups + [groups[0]], "not_grouped"))
        altered = list(groups); raw = bytearray(altered[3][1][9:]); raw[18:22] = struct.pack("<I", 0)
        altered[3] = (11, record(11, raw)); cases.append((altered, "auxiliary_count_mismatch"))
        for altered, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code): self.read(assemble(prefix, altered))

    def test_real_mcap_writer_parity_with_standard_summary_and_no_decoder(self):
        try:
            from mcap.writer import Writer, CompressionType
            from mcap.reader import SeekingReader
        except ImportError:
            self.skipTest("optional MCAP dependency unavailable")
        for offsets in (False, True):
            with self.subTest(offsets=offsets), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)/"real.mcap"
                with path.open("wb") as stream:
                    writer = Writer(stream, compression=CompressionType.ZSTD, chunk_size=1, use_summary_offsets=offsets)
                    writer.start()
                    schema = writer.register_schema("Unrecognized", "opaque", b"not a protobuf descriptor")
                    channel = writer.register_channel("/unrecognized", "opaque", schema)
                    for time in (100, 200, 300): writer.add_message(channel, time, b"not decodable", time)
                    writer.add_metadata("private", {"source": "private locator"})
                    writer.finish()
                with path.open("rb") as stream:
                    result = inventory.read_inventory(stream, path.stat().st_size)
                    stream.seek(0)
                    summary = SeekingReader(stream).get_summary()
                self.assertEqual(result["advertised_statistics"]["message_count"], summary.statistics.message_count)
                self.assertEqual(result["chunk_index_summary"]["indexed_chunk_count"], len(summary.chunk_indexes))
                self.assertEqual(result["auxiliary_indexes"]["metadata_index_count"], 1)
                self.assertEqual(result["summary_crc_status"], "validated")
