"""Synthetic section-firewall, policy, descriptor and resource regressions."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

from lane_residuals.io import velocity_summary_probe as probe
from lane_residuals.io.recording_inventory import MAGIC, read_inventory
from tests.io.test_recording_inventory import assemble, integer_map, record, string

try:
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
except ImportError:
    FileDescriptorSet = None


def descriptor():
    value = FileDescriptorSet()
    file = value.file.add(name="synthetic.proto", package="Test", syntax="proto3")
    msg = file.message_type.add(name="Velocity")
    msg.field.add(name="timestamp", number=1, type=4, label=1)
    msg.field.add(name="value", number=2, type=1, label=1)
    msg.field.add(name="qualifier", number=3, type=14, label=1, type_name=".Test.Quality")
    enum = file.enum_type.add(name="Quality")
    enum.value.add(name="UNSPECIFIED", number=0)
    enum.value.add(name="SYNTHETIC_VALID", number=7)
    return value.SerializeToString()


def fixture(*, unknown=False, missing=False, overlap=False):
    header = record(1, string("") + string("synthetic"))
    location = len(MAGIC + header)
    chunk = record(6, b"UNREADABLE_MESSAGE_PAYLOAD")
    prefix = MAGIC + header + chunk + record(15, struct.pack("<I", 0))
    raw = descriptor()
    schema = struct.pack("<H", 1) + string("Test.Velocity") + string("protobuf") + struct.pack("<I", len(raw)) + raw
    topics = probe.TOPICS[:-1] if missing else probe.TOPICS
    channels = b"".join(record(4, struct.pack("<HH", i, 1) + string(t) + string("protobuf") + struct.pack("<I", 0))
        for i, t in enumerate(topics, 1))
    # Unknown indexes conservatively select the chunk for each topic.
    entries = [] if unknown else [(i, location + len(chunk)) for i in range(1, len(topics)+1)]
    indexes = integer_map(entries)
    index_length = 100 if entries else 0
    if index_length:
        # The index records themselves are opaque to this summary-only probe.
        prefix = MAGIC + header + chunk + b"X" * index_length + record(15, struct.pack("<I", 0))
    index = record(8, struct.pack("<QQQQ", 2**63, 2**63+1, location, len(chunk)) + indexes +
        struct.pack("<Q", index_length) + string("zstd") + struct.pack("<QQ", 1, 99))
    if overlap:
        index *= 2
    return assemble(prefix, [(3, record(3, schema)), (4, channels), (8, index)])


@unittest.skipIf(FileDescriptorSet is None, "optional protobuf dependency")
class VelocitySummaryTests(unittest.TestCase):
    def inspect(self, raw):
        inventory = read_inventory(io.BytesIO(raw), len(raw))
        return probe.inspect_summary(io.BytesIO(raw), len(raw), inventory)

    def test_invalid_payload_never_read_or_decoded_and_shared_chunk_counted_once(self):
        raw = fixture()
        result, descriptors = self.inspect(raw)
        self.assertEqual(set(descriptors), {1})
        self.assertEqual(result["advertised_chunk_cost"]["direct_topics_union"]["chunk_count"], 1)
        self.assertEqual(result["advertised_chunk_cost"]["all_three_union"]["uncompressed_bytes"], 99)
        self.assertNotIn("UNREADABLE", json.dumps(result))

    def test_enum_numbers_are_evidence_not_hardcoded_validity(self):
        result, _ = self.inspect(fixture())
        declaration = result["declarations"]["1"]
        self.assertEqual(declaration["enums"][0]["values"][1]["number"], 7)
        fields = declaration["messages"][0]["fields"]
        self.assertIsNone(fields[1]["declared_default"])
        self.assertFalse(fields[1]["proto3_optional"])
        self.assertIsNone(fields[1]["oneof_index"])

    def test_unknown_index_included_conservatively(self):
        result, _ = self.inspect(fixture(unknown=True))
        self.assertEqual(result["unknown_channel_chunk_count"], 1)
        self.assertEqual(result["advertised_chunk_cost"][probe.TOPICS[2]]["chunk_count"], 1)

    def test_missing_topic_fails_without_fallback(self):
        with self.assertRaisesRegex(ValueError, "topics_missing"):
            self.inspect(fixture(missing=True))

    def test_changed_accepted_inventory_rejected(self):
        raw = fixture()
        with self.assertRaisesRegex(ValueError, "fresh_summary_differs"):
            probe.inspect_summary(io.BytesIO(raw), len(raw), {})

    def test_duplicate_chunk_ranges_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlapping_chunk_ranges"):
            self.inspect(fixture(overlap=True))

    def test_budget_stops_before_oversized_read(self):
        raw = fixture()
        with patch.object(probe, "MAX_READ_BYTES", 20), self.assertRaisesRegex(ValueError, "read_budget"):
            self.inspect(raw)

    def test_chunk_count_limit(self):
        with patch.object(probe, "MAX_CHUNKS", 0), self.assertRaisesRegex(ValueError, "chunk_count_budget"):
            self.inspect(fixture())

    def test_section_firewall_and_timeout(self):
        raw = fixture()
        guarded = probe.SummaryStream(io.BytesIO(raw), len(raw), time.monotonic()+10)
        guarded.seek(17 + struct.unpack("<Q", raw[9:17])[0])
        with self.assertRaisesRegex(ValueError, "data_section_read_forbidden"):
            guarded.read(1)
        guarded.deadline = 0
        with self.assertRaisesRegex(ValueError, "time_budget"):
            guarded.read(0)

    def prepare(self, base, role="development"):
        raw = fixture()
        raw_path = base / "input.mcap"
        raw_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        def save(name, value):
            data = (json.dumps(value)+"\n").encode()
            (base / name).write_bytes(data)
            return hashlib.sha256(data).hexdigest()
        cohort_sha = save("cohort.json", {"cohort_lock_created": True, "outings": [{"outing_id": "synthetic",
            "cohort_role": role, "raw_sha256": [digest]}]})
        inventory_sha = save("inventory.json", {"purpose": "development_only_recording_inventory", "recordings": [{
            "recording_id": "synthetic", "status": "complete", "raw_sha256": digest, "size_bytes": len(raw),
            "inventory": read_inventory(io.BytesIO(raw), len(raw))}]})
        request = {"revision": probe.REVISION, "outing_id": "synthetic", "recording_id": "synthetic", "raw_sha256": digest,
            "size_bytes": len(raw), "raw_path_private": str(raw_path), "cohort_file": "cohort.json", "cohort_sha256": cohort_sha,
            "inventory_file": "inventory.json", "inventory_sha256": inventory_sha}
        pin = save("request.json", request)
        return base/"request.json", pin, raw_path

    def test_complete_run_preserves_input_and_denies_training_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, pin, raw = self.prepare(base)
            before = raw.read_bytes()
            report = probe.run(request, pin, base/"result")
            self.assertEqual(raw.read_bytes(), before)
            self.assertEqual(report["status"], "complete")
            for key in ("current_full_raw_hash_verified", "model_fitted", "message_payloads_decoded",
                "numeric_conditions_exported", "speed_policy_adopted", "temporal_recovery_established"):
                self.assertIs(report[key], False)
            self.assertTrue((base/"result/schema_1.pb").exists())

    def test_final_role_rejected_before_any_raw_path_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, pin, _ = self.prepare(base, role="final")
            with patch.object(probe, "SummaryStream", side_effect=AssertionError("raw read")), \
                    patch.object(Path, "resolve", side_effect=AssertionError("raw resolve")), \
                    self.assertRaisesRegex(ValueError, "development_only"):
                probe.run(request, pin, base/"result")
            self.assertFalse((base/"result").exists())

    def test_request_digest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, _, _ = self.prepare(base)
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                probe.run(request, "0"*64, base/"result")

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, pin, _ = self.prepare(base)
            output = base/"result"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "output_must_be_new"):
                probe.run(request, pin, output)
            self.assertEqual(list(output.iterdir()), [])

    def test_failure_receipt_retained_without_success_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, pin, _ = self.prepare(base)
            with patch.object(probe, "MAX_READ_BYTES", 20), self.assertRaisesRegex(ValueError, "read_budget"):
                probe.run(request, pin, base/"result")
            report = json.loads((base/"result/report.private.json").read_text())
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual(report["failure_code"], "probe_read_budget")
            self.assertNotIn("declarations", report)

    def test_raw_change_during_read_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            request, pin, raw = self.prepare(base)
            original = probe.inspect_summary
            def changing(*args):
                result = original(*args)
                with raw.open("ab") as stream:
                    stream.write(b"changed")
                return result
            with patch.object(probe, "inspect_summary", side_effect=changing), self.assertRaisesRegex(ValueError, "raw_changed"):
                probe.run(request, pin, base/"result")

    def test_root_descriptor_must_exist(self):
        with self.assertRaisesRegex(ValueError, "schema_root_missing"):
            probe.describe(descriptor(), "Other.Root")
