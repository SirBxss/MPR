"""Actual indexed/compressed containers, not a mocked generator memory claim."""

from contextlib import closing
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io.recording_pair_feasibility import MAX_CHUNK_BYTES, RecordingReadError, ResourceLimitError, TOPICS


class IndexedStorageReaderTests(unittest.TestCase):
    def setUp(self):
        try:
            from lane_residuals.io import indexed_storage_reader as storage
            from google.protobuf import descriptor_pb2, wrappers_pb2
            from mcap.writer import Writer, CompressionType
            from mcap_protobuf.decoder import DecoderFactory
        except ImportError:
            self.skipTest("MCAP extras not installed")
        self.storage = storage
        self.Writer, self.CompressionType, self.DecoderFactory = Writer, CompressionType, DecoderFactory
        self.descriptor_pb2, self.wrappers_pb2 = descriptor_pb2, wrappers_pb2
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def recording(self, *, compression="ZSTD", payload_bytes=8, count=3):
        path = self.root / (compression + ".mcap")
        message = self.wrappers_pb2.BytesValue(value=b"x" * payload_bytes)
        descriptors = self.descriptor_pb2.FileDescriptorSet()
        message.DESCRIPTOR.file.CopyToProto(descriptors.file.add())
        with path.open("wb") as stream:
            writer = self.Writer(stream, compression=getattr(self.CompressionType, compression), chunk_size=1)
            writer.start()
            schema = writer.register_schema(message.DESCRIPTOR.full_name, "protobuf", descriptors.SerializeToString())
            channel = writer.register_channel(TOPICS[0], "protobuf", schema)
            ignored = writer.register_channel("/ignored", "protobuf", schema)
            writer.add_message(ignored, 500, b"invalid unselected protobuf", 500)
            for i in range(count):
                writer.add_message(channel, 400-i, message.SerializeToString(), 300-i, sequence=i+10)
            writer.finish()
        return path

    def reader(self, stream):
        return self.storage.IndexedStorageReader(stream, record_size_limit=MAX_CHUNK_BYTES,
                                                  decoder_factories=[self.DecoderFactory()])

    def test_fields_and_decoded_values_match_upstream_for_all_supported_compressions(self):
        from mcap.reader import SeekingReader
        for compression in ("NONE", "ZSTD", "LZ4"):
            with self.subTest(compression=compression):
                raw = self.recording(compression=compression).read_bytes()
                upstream = SeekingReader(BytesIO(raw), decoder_factories=[self.DecoderFactory()])
                expected = list(upstream.iter_decoded_messages(topics=TOPICS, log_time_order=False))
                actual = list(self.reader(BytesIO(raw)).iter_decoded_messages(topics=TOPICS, log_time_order=False))
                # Each DecoderFactory builds its own descriptor pool/classes;
                # compare authoritative fields and protobuf bytes, not class identity.
                def values(items):
                    return [(item.schema, item.channel, item.message,
                             item.decoded_message.DESCRIPTOR.full_name,
                             item.decoded_message.SerializeToString()) for item in items]
                self.assertEqual(values(actual), values(expected))
                self.assertEqual([item.message.log_time for item in actual], [400, 399, 398])
                self.assertEqual([item.message.sequence for item in actual], [10, 11, 12])

    def test_first_yield_decompresses_only_one_selected_chunk(self):
        raw = self.recording().read_bytes()
        with patch.object(self.storage, "get_chunk_data_stream", wraps=self.storage.get_chunk_data_stream) as decompress:
            with closing(self.reader(BytesIO(raw)).iter_messages(topics=TOPICS, log_time_order=False)) as messages:
                self.assertEqual(next(messages)[2].sequence, 10)
                self.assertEqual(decompress.call_count, 1)
                self.assertEqual([item[2].sequence for item in messages], [11, 12])
                self.assertEqual(decompress.call_count, 3)

    def test_storage_order_is_byte_offset_order_even_if_summary_indexes_are_reversed(self):
        reader = self.reader(BytesIO(self.recording().read_bytes()))
        reader.get_summary().chunk_indexes.reverse()
        self.assertEqual([item[2].log_time for item in reader.iter_messages(topics=TOPICS, log_time_order=False)], [400, 399, 398])

    def test_missing_index_and_unsupported_time_queries_do_not_fall_back_to_scanning(self):
        reader = self.reader(BytesIO(self.recording().read_bytes()))
        for kwargs in ({}, {"log_time_order": False, "reverse": True}, {"log_time_order": False, "start_time": 0}):
            with self.assertRaisesRegex(RecordingReadError, "indexed_storage_order_without_time_filter_required"):
                list(reader.iter_messages(**kwargs))
        reader.get_summary().chunk_indexes.clear()
        with self.assertRaisesRegex(ResourceLimitError, "indexed_summary_required_no_scan_fallback"):
            list(reader.iter_messages(topics=TOPICS, log_time_order=False))

    def test_chunk_cap_and_index_header_identity_fail_closed(self):
        raw = self.recording().read_bytes()
        reader = self.reader(BytesIO(raw))
        selected = next(c for c in reader.get_summary().chunk_indexes if 1 in c.message_index_offsets)
        selected.uncompressed_size = MAX_CHUNK_BYTES + 1
        with self.assertRaisesRegex(ResourceLimitError, "advertised_chunk_exceeds_resource_limit"):
            list(reader.iter_messages(topics=TOPICS, log_time_order=False))
        reader = self.reader(BytesIO(raw))
        selected = next(c for c in reader.get_summary().chunk_indexes if 1 in c.message_index_offsets)
        selected.message_start_time -= 1
        with self.assertRaisesRegex(RecordingReadError, "indexed_chunk_header_mismatch"):
            list(reader.iter_messages(topics=TOPICS, log_time_order=False))

    def test_overlapping_index_ranges_and_changed_outer_opcode_are_rejected(self):
        raw = self.recording().read_bytes()
        reader = self.reader(BytesIO(raw))
        indexes = reader.get_summary().chunk_indexes
        indexes[1].chunk_start_offset = indexes[0].chunk_start_offset
        with self.assertRaisesRegex(RecordingReadError, "indexed_chunk_ranges_invalid_or_overlapping"):
            list(reader.iter_messages(topics=TOPICS, log_time_order=False))
        reader = self.reader(BytesIO(raw))
        selected = next(c for c in reader.get_summary().chunk_indexes if 1 in c.message_index_offsets)
        changed = bytearray(raw); changed[selected.chunk_start_offset] = 0
        reader._storage_source = BytesIO(changed)
        with self.assertRaisesRegex(RecordingReadError, "indexed_chunk_record_identity_or_length_mismatch"):
            list(reader.iter_messages(topics=TOPICS, log_time_order=False))

    def test_zstd_failure_codes_and_context_do_not_export_native_text(self):
        import zstandard
        cases = (("decompression error: Allocation error", "zstd_decompression_memory_limit", ResourceLimitError),
                 ("too much memory", "zstd_decoder_window_limit", ResourceLimitError),
                 ("Data corruption detected", "zstd_corrupt_or_incomplete_frame", RecordingReadError),
                 ("Dictionary mismatch", "zstd_dictionary_error", RecordingReadError),
                 ("unknown native failure", "zstd_decompression_failed", RecordingReadError))
        for native, code, kind in cases:
            with self.subTest(code=code):
                reader = self.reader(BytesIO(self.recording().read_bytes()))
                with patch.object(self.storage, "get_chunk_data_stream", side_effect=zstandard.ZstdError(native + " private/path payload")):
                    with self.assertRaises(kind) as raised:
                        list(reader.iter_messages(topics=TOPICS, log_time_order=False))
                self.assertEqual(str(raised.exception), code)
                context = raised.exception.reader_failure_context
                self.assertEqual(context["phase"], "chunk_decompression")
                self.assertEqual(context["exception_class"], "ZstdError")
                self.assertEqual(context["completed_selected_chunk_count"], 0)
                self.assertNotIn("private/path", json.dumps(context))

    def test_later_corrupt_selected_frame_nulls_all_readiness_and_cleans_spool(self):
        from lane_residuals.io.recording_ingestion import inspect_recording_readiness, TOPIC_LIMITS
        from tests.io.recording_ingestion_fixture import write_recording
        path = self.root / "geometry.mcap"; write_recording(path)
        raw = bytearray(path.read_bytes())
        reader = self.reader(BytesIO(raw))
        index = reader.get_summary().chunk_indexes[-1]
        chunk = next(self.storage.StreamReader(BytesIO(raw[index.chunk_start_offset:index.chunk_start_offset+index.chunk_length]),
                                              skip_magic=True, emit_chunks=True).records)
        offset = index.chunk_start_offset + index.chunk_length - len(chunk.data)
        raw[offset:offset+4] = b"\0" * 4
        path.write_bytes(raw)
        with path.open("rb") as stream:
            report = inspect_recording_readiness(path, stream, self.root)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["failure_code"], "zstd_decompression_failed")
        self.assertGreater(report["reader_failure_context"]["completed_selected_chunk_count"], 0)
        for key in ("counts", "diagnostics", "odometry", "source_clock_order", "log_clock_order",
                    "sensor_geometry_support", "complete_condition_support", "condition_failure_counts"):
            self.assertIsNone(report[key])
        self.assertFalse(any(p.name.startswith("mpr-ingestion-") for p in self.root.iterdir()))
        self.assertEqual(set(TOPIC_LIMITS), set((*TOPICS, "/adp/odometry")))

    def test_frame_content_size_and_uncompressed_length_are_checked_before_inner_records(self):
        raw = self.recording().read_bytes()
        reader = self.reader(BytesIO(raw))
        from types import SimpleNamespace
        with patch("zstandard.get_frame_parameters", return_value=SimpleNamespace(content_size=MAX_CHUNK_BYTES)):
            with self.assertRaisesRegex(RecordingReadError, "zstd_frame_content_size_mismatch"):
                list(reader.iter_messages(topics=TOPICS, log_time_order=False))
        reader = self.reader(BytesIO(raw))
        with patch.object(self.storage, "get_chunk_data_stream", return_value=(BytesIO(b""), 0)):
            with self.assertRaisesRegex(RecordingReadError, "chunk_uncompressed_size_mismatch"):
                list(reader.iter_messages(topics=TOPICS, log_time_order=False))

    def test_zstd_frame_without_declared_content_size_uses_bounded_chunk_size(self):
        import zstandard
        # This is valid ZSTD, not corruption. The MCAP header supplies the
        # already-capped size to the existing decoder's max_output_size.
        compress = zstandard.ZstdCompressor(write_content_size=False).compress
        with patch("mcap.writer.zstandard.compress", side_effect=compress):
            raw = self.recording().read_bytes()
        reader = self.reader(BytesIO(raw))
        index = reader.get_summary().chunk_indexes[-1]
        chunk = next(self.storage.StreamReader(BytesIO(raw[index.chunk_start_offset:index.chunk_start_offset+index.chunk_length]),
                                              skip_magic=True, emit_chunks=True).records)
        self.assertEqual(zstandard.get_frame_parameters(chunk.data).content_size, zstandard.CONTENTSIZE_UNKNOWN)
        self.assertEqual(len(list(reader.iter_messages(topics=TOPICS, log_time_order=False))), 3)

    def test_inner_record_bounds_channels_and_schema_identity_are_checked(self):
        import struct
        reader = self.reader(BytesIO(self.recording().read_bytes()))
        summary = reader.get_summary()
        payload = struct.pack("<HIQQ", 1, 0, 0, 0)
        cases = ((b"x", "chunk_inner_record_header_truncated"),
                 (struct.pack("<BQ", 5, 30)+payload, "chunk_inner_record_length_invalid"),
                 (struct.pack("<BQ", 5, 1)+b"x", "chunk_message_header_truncated"),
                 (struct.pack("<BQ", 5, 22)+struct.pack("<HIQQ", 999, 0, 0, 0), "chunk_message_channel_identity_mismatch"))
        for data, code in cases:
            with self.assertRaisesRegex(RecordingReadError, code):
                list(reader._messages(data, summary, set(TOPICS)))
        summary.schemas.clear()
        with self.assertRaisesRegex(RecordingReadError, "chunk_message_schema_identity_mismatch"):
            list(reader._messages(struct.pack("<BQ", 5, 22)+payload, summary, set(TOPICS)))

    def test_selected_payload_total_can_exceed_process_memory_cap_without_retention(self):
        # 512 MiB of decoded message bytes under a real 256 MiB AS cap. The
        # compressed file is tiny. Checking generator liveness alone missed
        # upstream's queue, which retained raw payloads before any yield.
        if sys.platform != "linux":
            self.skipTest("Linux RLIMIT_AS resource regression")
        path = self.recording(payload_bytes=4*1024**2, count=128)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        code = """import resource, sys
from pathlib import Path
from lane_residuals.io.recording_pair_feasibility import _iter_messages
resource.setrlimit(resource.RLIMIT_AS, (256*1024**2, resource.getrlimit(resource.RLIMIT_AS)[1]))
count = 0
for item in _iter_messages(Path(sys.argv[1])):
    count += 1
    del item
print(count)
"""
        environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2]/"src"),
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        result = subprocess.run([sys.executable, "-c", code, str(path)], env=environment,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "128")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def silently_changed_geometry_recording(self, *, enable_crcs=True):
        """Flip one compressed bit while retaining valid inner/protobuf structure.

        Select a fixture mutation by decoded properties rather than a writer-
        version-specific byte offset. CRC fields and index/record sizes stay
        unchanged, so only stored integrity checks can reject this mutation.
        """
        import struct
        import zstandard
        from tests.io.recording_ingestion_fixture import write_recording
        from tests.domain.test_exploratory_residuals import T
        path = self.root/"crc_geometry.mcap"
        write_recording(path, times=tuple(T+i*100_000_000 for i in range(6)), enable_crcs=enable_crcs)
        raw = path.read_bytes()
        reader = self.reader(BytesIO(raw)); summary = reader.get_summary()
        # A later EDP-only chunk: a completed positive prefix precedes it.
        index = [c for c in summary.chunk_indexes if 1 in c.message_index_offsets][-1]
        chunk = next(self.storage.StreamReader(BytesIO(raw[index.chunk_start_offset:index.chunk_start_offset+index.chunk_length]),
                                              skip_magic=True, emit_chunks=True).records)
        original = zstandard.decompress(chunk.data, chunk.uncompressed_size)
        self.assertEqual(original[0], 5)  # one Message, no embedded descriptors
        channel_id = struct.unpack_from("<H", original, 9)[0]
        channel = summary.channels[channel_id]
        decode = self.DecoderFactory().decoder_for(channel.message_encoding, summary.schemas[channel.schema_id])
        initial = decode(original[31:])
        initial_confidences = tuple(initial.drive_paths[0].drive_path_confidences)
        initial.drive_paths[0].ClearField("drive_path_confidences")
        other_fields = initial.SerializeToString()
        for position in range(len(chunk.data)):
            changed = bytearray(chunk.data); changed[position] ^= 1
            try:
                decoded = zstandard.decompress(changed, chunk.uncompressed_size)
                if len(decoded) != len(original) or decoded[:31] != original[:31]:
                    continue
                message = decode(decoded[31:])
                confidences = tuple(message.drive_paths[0].drive_path_confidences)
                message.drive_paths[0].ClearField("drive_path_confidences")
                if (message.SerializeToString() != other_fields or confidences == initial_confidences or
                        len(confidences) != len(initial_confidences) or not all(0 <= value <= 1 for value in confidences)):
                    continue
            except Exception:
                continue
            offset = index.chunk_start_offset+index.chunk_length-len(chunk.data)+position
            damaged = bytearray(raw); damaged[offset] ^= 1
            path.write_bytes(damaged)
            self.assertEqual(sum(a != b for a, b in zip(raw, damaged)), 1)
            self.assertEqual(chunk.uncompressed_crc != 0, enable_crcs)
            return path
        self.fail("No valid single-bit compressed fixture mutation was found")

    def test_readiness_rejects_silent_compressed_payload_change_with_stored_crc(self):
        from lane_residuals.io.recording_ingestion import inspect_recording_readiness, TOPIC_LIMITS
        from lane_residuals.io.recording_pair_feasibility import _iter_messages, inspect_recording_pairs
        path = self.silently_changed_geometry_recording()
        # The historical default still decodes the altered payload completely:
        # no decompressor/protobuf error or message-count drift catches it.
        self.assertEqual(len(list(_iter_messages(path, topic_limits=TOPIC_LIMITS))), 24)
        self.assertEqual(inspect_recording_pairs(path, self.root)["status"], "complete")
        with path.open("rb") as stream:
            report = inspect_recording_readiness(path, stream, self.root)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["failure_code"], "CRCValidationError")
        context = report["reader_failure_context"]
        self.assertEqual(context["phase"], "chunk_decompression")
        self.assertEqual(context["exception_class"], "CRCValidationError")
        self.assertGreater(context["completed_selected_chunk_count"], 0)
        for key in ("counts", "diagnostics", "odometry", "source_clock_order", "log_clock_order",
                    "sensor_geometry_support", "complete_condition_support", "condition_failure_counts"):
            self.assertIsNone(report[key])
        self.assertNotIn("crc_geometry.mcap", json.dumps(report))
        self.assertFalse(any(p.name.startswith("mpr-ingestion-") for p in self.root.iterdir()))

    def test_valid_stored_crcs_preserve_all_readiness_observations(self):
        from lane_residuals.io import recording_ingestion as ingestion
        from lane_residuals.io.recording_pair_feasibility import _iter_messages
        from tests.io.recording_ingestion_fixture import write_recording
        path = self.root/"valid_crc.mcap"; write_recording(path)
        with path.open("rb") as stream:
            verified = ingestion.inspect_recording_readiness(path, stream, self.root)
        def no_crc(*args, **kwargs):
            kwargs["validate_crcs"] = False
            return _iter_messages(*args, **kwargs)
        with patch.object(ingestion, "_iter_messages", side_effect=no_crc), path.open("rb") as stream:
            previous_policy = ingestion.inspect_recording_readiness(path, stream, self.root)
        self.assertEqual(verified, previous_policy)
        self.assertEqual(verified["status"], "complete")
        self.assertEqual(verified["sensor_geometry_support"]["frame_count"], 2)

    def test_zero_chunk_crcs_do_not_claim_integrity_or_reject_valid_format(self):
        from lane_residuals.io.recording_ingestion import inspect_recording_readiness
        path = self.silently_changed_geometry_recording(enable_crcs=False)
        with path.open("rb") as stream:
            report = inspect_recording_readiness(path, stream, self.root)
        # MCAP explicitly defines zero as no available chunk CRC. Enabling
        # validation cannot detect this valid-protobuf mutation in that case.
        self.assertEqual(report["status"], "complete")
        self.assertIsNone(report["reader_failure_context"])
