from io import BytesIO
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.io import recording_decode_check as io
from lane_residuals.io.recording_inventory import read_inventory
from tests.io.recording_decode_fixture import recording, rewrite, records, inflated_statistics


class DecodeCheckIoTests(unittest.TestCase):
    def setUp(self):
        try:
            io.check_dependencies()
        except (ImportError, ValueError):
            self.skipTest("MCAP extras not installed")
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def check(self, raw, inventory=None, topics=None, resource_check=lambda: None):
        inventory = read_inventory(BytesIO(raw), len(raw)) if inventory is None else inventory
        return io.check_decoding(BytesIO(raw), len(raw), inventory, topics or ["/selected"], self.root, resource_check)

    def test_standard_writer_compressions_reconcile_without_seeking_summary_or_unselected_decoder(self):
        from mcap.reader import SeekingReader
        for compression in ("NONE", "ZSTD", "LZ4"):
            with self.subTest(compression=compression), patch.object(SeekingReader, "get_summary", side_effect=AssertionError("full summary forbidden")):
                result = self.check(recording(compression=compression))
            self.assertEqual(result["decoded_selected_message_count"], 3)
            self.assertEqual(result["topics"][0]["advertised_message_count"], 3)
            self.assertEqual(result["selected_chunk_crc"]["checked_nonzero_count"], 3)
            self.assertEqual(result["skipped_indexed_chunk_count"], 1)
            self.assertEqual(list(self.root.iterdir()), [])
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_multiple_versions_same_topic_have_individual_counts_and_descriptor_hashes(self):
        result = self.check(recording(multi=True, count=5))
        self.assertEqual(result["topics"][0]["decoded_message_count"], 5)
        self.assertEqual(result["topics"][0]["channel_version_count"], 2)
        self.assertEqual([r["decoded_message_count"] for r in result["channel_versions"]], [3, 2])
        self.assertEqual(len({r["schema_data_sha256"] for r in result["channel_versions"]}), 2)

    def test_decoded_values_and_physical_order_match_the_existing_chunk_reader(self):
        from lane_residuals.io.indexed_storage_reader import IndexedStorageReader
        from mcap_protobuf.decoder import DecoderFactory
        for compression in ("NONE", "ZSTD", "LZ4"):
            raw = recording(compression=compression, multi=True, count=5)
            old = IndexedStorageReader(BytesIO(raw), decoder_factories=[DecoderFactory()], validate_crcs=True)
            expected = [item.decoded_message.value for item in old.iter_decoded_messages(topics=["/selected"], log_time_order=False)]
            observed, original = [], io._decoders
            def decoders(*arguments):
                def wrap(function):
                    def decode(payload):
                        message = function(payload); observed.append(message.value); return message
                    return decode
                return {key: wrap(function) for key, function in original(*arguments).items()}
            with self.subTest(compression=compression), patch.object(io, "_decoders", side_effect=decoders):
                result = self.check(raw)
            self.assertEqual(observed, expected)
            self.assertEqual(result["decoded_selected_message_count"], len(expected))

    def test_zero_crc_is_unavailable_and_zero_messages_are_not_missing_counts(self):
        result = self.check(recording(crcs=False))
        self.assertEqual(result["selected_chunk_crc"], {"checked_nonzero_count": 0, "unavailable_zero_count": 3})
        result = self.check(recording(count=0))
        self.assertEqual(result["decoded_selected_message_count"], 0)
        self.assertEqual(result["channel_versions"][0]["advertised_message_count"], 0)

    def test_missing_statistics_absent_topics_and_unsupported_encoding_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "advertised_selected_counts_required"):
            self.check(recording(statistics=False))
        with self.assertRaisesRegex(ValueError, "requested_topic_absent"):
            self.check(recording(), topics=["/absent"])
        with self.assertRaisesRegex(ValueError, "selected_protobuf_schema_required"):
            self.check(recording(), topics=["/ignored"])

    def test_channel_indexes_absent_require_conservative_chunk_inspection(self):
        from mcap.writer import IndexType
        result = self.check(recording(index_types=IndexType.CHUNK))
        self.assertEqual(result["decoded_selected_message_count"], 3)
        self.assertEqual(result["selected_chunks_without_channel_indexes"], 4)
        self.assertEqual(result["skipped_indexed_chunk_count"], 0)

    def test_reverse_index_listing_preserves_physical_message_order_and_unsigned_clocks(self):
        raw = recording(epoch=2**63+900)
        raw = rewrite(raw, 8, lambda data: b"".join(reversed(records(data))))
        seen, original = [], io._decoders
        def decoders(*arguments):
            result = original(*arguments)
            def wrap(function):
                def decode(payload):
                    message = function(payload); seen.append(message.value); return message
                return decode
            return {key: wrap(value) for key, value in result.items()}
        with patch.object(io, "_decoders", side_effect=decoders):
            result = self.check(raw)
        self.assertFalse(result["summary_index_listing_in_physical_order"])
        self.assertEqual(seen, [b"sample-0", b"sample-1", b"sample-2"])

    def test_duplicate_offsets_and_overlapping_message_index_ranges_fail_before_decoding(self):
        raw = recording()
        duplicate = rewrite(raw, 8, lambda data: b"".join([*records(data)[:-1], records(data)[0]]))
        with self.assertRaisesRegex(ValueError, "duplicate_chunk_offset"):
            self.check(duplicate)
        def overlap(data):
            values = records(data); first = bytearray(values[0]); map_length = struct.unpack_from("<I", first, 41)[0]
            offset = 45+map_length; size = struct.unpack_from("<Q", first, offset)[0]
            struct.pack_into("<Q", first, offset, size+1); values[0] = bytes(first)
            return b"".join(values)
        with self.assertRaisesRegex(ValueError, "overlapping_chunk_or_message_index_ranges"):
            self.check(rewrite(raw, 8, overlap))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_crc_corruption_is_detected_before_selected_payload_decoding(self):
        from mcap.reader import SeekingReader
        raw = bytearray(recording(compression="NONE"))
        index = SeekingReader(BytesIO(raw)).get_summary().chunk_indexes[-1]
        raw[index.chunk_start_offset+index.chunk_length-1] ^= 1
        with self.assertRaises(Exception) as error:
            self.check(raw)
        self.assertEqual(type(error.exception).__name__, "CRCValidationError")
        context = error.exception.reader_failure_context
        self.assertEqual(context["decoded_selected_message_count"], 2)
        self.assertEqual(context["phase"], "chunk_decompression")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_late_protobuf_failure_context_is_progress_not_completed_counts(self):
        with self.assertRaises(Exception) as error:
            self.check(recording(invalid_last=True))
        context = error.exception.reader_failure_context
        self.assertEqual(context["decoded_selected_message_count"], 2)
        self.assertEqual(context["phase"], "payload_decode")
        self.assertNotIn("PRIVATE", json.dumps(context))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unselected_bad_wire_bytes_in_selected_chunk_are_never_decoded(self):
        result = self.check(recording(same_chunk=True))
        self.assertEqual(result["decoded_selected_message_count"], 3)
        self.assertEqual(result["selected_indexed_chunk_count"], 1)

    def test_bad_schema_and_missing_required_protobuf_fields_are_not_geometry_failures(self):
        with self.assertRaises(Exception) as error:
            self.check(recording(bad_schema=True))
        self.assertEqual(error.exception.reader_failure_context["phase"], "schema_load")
        with self.assertRaisesRegex(ValueError, "protobuf_required_fields_missing"):
            self.check(recording(count=1, required=True))

    def test_actual_counts_must_match_advertised_statistics(self):
        with self.assertRaisesRegex(ValueError, "selected_channel_count_mismatch") as error:
            self.check(inflated_statistics(recording()))
        self.assertEqual(error.exception.reader_failure_context["phase"], "count_reconciliation")
        self.assertEqual(error.exception.reader_failure_context["decoded_selected_message_count"], 3)

    def test_missing_chunk_indexes_have_no_scan_fallback(self):
        raw = recording(); inventory = read_inventory(BytesIO(raw), len(raw))
        with patch.object(io, "_groups", return_value={3: io._groups(BytesIO(raw), len(raw), float("inf"))[3]}):
            with self.assertRaisesRegex(ValueError, "indexed_chunks_required_no_scan_fallback"):
                self.check(raw, inventory)

    def test_selected_descriptor_message_chunk_and_payload_budgets_stop(self):
        raw = recording()
        for name, limit, code in (("MAX_SCHEMA_BYTES", 1, "descriptor_bytes_budget"),
                                  ("MAX_TOPIC_MESSAGES", 2, "advertised_message_budget"),
                                  ("MAX_PAYLOAD_BYTES", 1, "selected_payload_bytes_budget")):
            with self.subTest(limit=name), patch.object(io, name, limit):
                with self.assertRaisesRegex(ValueError, code):
                    self.check(raw)
        original = io._stage_indexes
        def limited(*arguments):
            with patch.object(io, "MAX_CHUNK_BYTES", 1):
                return original(*arguments)
        with patch.object(io, "_stage_indexes", side_effect=limited):
            with self.assertRaisesRegex(ValueError, "selected_chunk_budget"):
                self.check(raw)

    def test_index_database_budget_and_resources_cleanup_on_failure(self):
        with patch.object(io, "MAX_INDEX_BYTES", 4096):
            with self.assertRaises(Exception):
                self.check(recording())
        def stop():
            raise ValueError("PRIVATE RESOURCE DETAIL")
        with self.assertRaises(Exception) as error:
            self.check(recording(), resource_check=stop)
        self.assertNotIn("PRIVATE", json.dumps(error.exception.reader_failure_context))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cooperative_deadline_stops_and_cleans_indexes(self):
        with patch.object(io, "MAX_DECODE_SECONDS", -1):
            with self.assertRaisesRegex(ValueError, "execution_timeout"):
                self.check(recording())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bounded_lz4_and_zstd_unknown_size_and_trailing_data(self):
        import lz4.frame
        import zstandard
        def chunk(compression, data, size):
            return SimpleNamespace(compression=compression, data=data, uncompressed_size=size, uncompressed_crc=0)
        for data in (b"", b"test"*100):
            encoded = zstandard.ZstdCompressor(write_content_size=False).compress(data)
            self.assertEqual(io._decompress(chunk("zstd", encoded, len(data))), data)
        with self.assertRaisesRegex(ValueError, "lz4_frame_incomplete_oversize"):
            io._decompress(chunk("lz4", lz4.frame.compress(b"x"*1024**2), 1))
        for compression, encoded in (("zstd", zstandard.ZstdCompressor().compress(b"abc")), ("lz4", lz4.frame.compress(b"abc"))):
            with self.subTest(compression=compression), self.assertRaises(Exception):
                io._decompress(chunk(compression, encoded+b"EXTRA", 3))

    def test_native_failure_categories_never_expose_exception_text(self):
        import zstandard
        for text, code in (("Allocation error", "zstd_decompression_memory_limit"), ("too much memory", "zstd_decoder_window_limit"),
                           ("Dictionary mismatch", "zstd_dictionary_error"), ("Data corruption", "zstd_corrupt_or_incomplete_frame"),
                           ("Unknown", "zstd_decompression_failed")):
            error = zstandard.ZstdError(text+" PRIVATE COORDINATES")
            self.assertEqual(io.failure_code(error), code)

    def test_descriptor_count_and_total_message_ceilings_are_applied(self):
        for name, limit, code in (("MAX_SCHEMAS", 0, "descriptor_count_budget"),
                                  ("MAX_CHANNELS", 0, "descriptor_count_budget"),
                                  ("MAX_TOTAL_MESSAGES", 2, "advertised_message_budget")):
            with self.subTest(limit=name), patch.object(io, name, limit):
                with self.assertRaisesRegex(ValueError, code):
                    self.check(recording())

    def test_zstd_known_content_size_and_window_are_bounded_before_decompression(self):
        import zstandard
        encoded = zstandard.ZstdCompressor().compress(b"abc")
        chunk = SimpleNamespace(compression="zstd", data=encoded, uncompressed_size=2, uncompressed_crc=0)
        with self.assertRaisesRegex(ValueError, "content_size_mismatch"):
            io._decompress(chunk)
        chunk.uncompressed_size = 3
        with patch.object(zstandard, "get_frame_parameters", return_value=SimpleNamespace(window_size=io.MAX_CHUNK_BYTES+1)):
            with self.assertRaisesRegex(ValueError, "window_budget_exceeded"):
                io._decompress(chunk)

    def test_actual_chunk_header_must_match_the_selected_index(self):
        def change(data):
            values = records(data); last = bytearray(values[-1]); value = struct.unpack_from("<Q", last, len(last)-8)[0]
            struct.pack_into("<Q", last, len(last)-8, value+1); values[-1] = bytes(last)
            return b"".join(values)
        with self.assertRaisesRegex(ValueError, "actual_chunk_header_disagrees_with_index") as error:
            self.check(rewrite(recording(), 8, change))
        self.assertEqual(error.exception.reader_failure_context["phase"], "chunk_read")

    def test_timeout_during_index_staging_discards_and_cleans_database(self):
        original = io._stage_indexes
        def expire(stream, groups, selected, deadline, db, resource_check):
            return original(stream, groups, selected, 0, db, resource_check)
        with patch.object(io, "_stage_indexes", side_effect=expire):
            with self.assertRaisesRegex(ValueError, "summary_timeout"):
                self.check(recording())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_topic_selection_requires_explicit_unique_exact_names(self):
        for values in ([], ["selected"], ["/selected", "/selected"], ["/"]):
            with self.assertRaisesRegex(ValueError, "explicit_unique_topics"):
                io.selected_topics(values)

    def test_inner_header_lengths_and_selected_support_records_are_checked(self):
        raw = recording(same_chunk=True); inventory = read_inventory(BytesIO(raw), len(raw))
        channels, schemas, selected, _ = io._selection(inventory, ["/selected"])
        decoders = io._decoders(BytesIO(raw), io._groups(BytesIO(raw), len(raw), float("inf")), selected, schemas, float("inf"))
        from collections import Counter
        state = {"selected_payload_bytes_processed": 0, "decoded_selected_message_count": 0}
        for data, code in ((b"x", "record_header_truncated"), (struct.pack("<BQ", 5, 100), "record_length_invalid"),
                           (struct.pack("<BQ", 5, 1)+b"x", "message_header_truncated")):
            with self.assertRaisesRegex(ValueError, code):
                io._messages(data, channels, schemas, selected, decoders, Counter(), float("inf"), state)
        from tests.io.test_recording_inventory import string
        bad_channel = struct.pack("<HH", 1, 1)+string("/wrong")+string("protobuf")+struct.pack("<I", 0)
        with self.assertRaisesRegex(ValueError, "in_chunk_channel_disagrees"):
            io._support_record(4, bad_channel, selected, schemas)
