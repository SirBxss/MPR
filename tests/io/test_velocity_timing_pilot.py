from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import velocity_timing_pilot as pilot
from lane_residuals.io.recording_inventory import read_inventory
from tests.io.velocity_timing_fixture import recording, prepare, row, LOG


class VelocityPilotIoTests(unittest.TestCase):
    def setUp(self):
        try:
            pilot.decoder.check_dependencies()
        except (ImportError, ValueError):
            self.skipTest("optional MCAP extras not installed")

    def check(self, raw):
        with tempfile.TemporaryDirectory() as temp:
            return pilot.decode_window(BytesIO(raw), len(raw), read_inventory(BytesIO(raw), len(raw)),
                (LOG-1_000_000_000, LOG+13_000_000_000), temp)

    def test_three_compressions_and_zero_timestamps_without_unselected_decoding(self):
        for compression in ("NONE", "ZSTD", "LZ4"):
            with self.subTest(compression=compression):
                records, report = self.check(recording(compression))
                self.assertEqual(len(records), 6)
                self.assertEqual(report["decoded_selected_messages_in_touched_chunks"], 6)
                self.assertLess(report["window_chunks"], report["indexed_chunks"])
                self.assertEqual(sum(r["source_ns"] == "0" for r in records), 3)

    def test_window_budget_fails_before_any_decompression(self):
        with patch.dict(pilot.LIMITS, selected_chunk_read_bytes=0), \
                patch.object(pilot.decoder, "_decompress", side_effect=AssertionError("payload touched")), \
                self.assertRaisesRegex(ValueError, "planned_window_budget"):
            self.check(recording())

    def test_single_chunk_and_expansion_budgets(self):
        for key in ("single_chunk_bytes", "expanded_chunk_bytes", "selected_chunks"):
            with self.subTest(key=key), patch.dict(pilot.LIMITS, {key: 0}), self.assertRaises(ValueError):
                self.check(recording())

    def test_actual_message_limit_is_enforced_before_next_decode(self):
        with patch.dict(pilot.LIMITS, decoded_messages=1), self.assertRaisesRegex(ValueError, "message_count_budget"):
            self.check(recording())

    def test_meter_and_deadline_do_not_allow_unbounded_reads(self):
        meter = pilot.Metered(BytesIO(b"a"), 0)
        with self.assertRaisesRegex(ValueError, "processing_timeout"):
            meter.read(1)

    def test_raw_hash_mismatch_and_size_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            request, pin, raw = prepare(Path(temp))
            q, _, _, _ = pilot.load_request(request, pin)
            identity = dict(q["summary_scope"], raw_sha256="0"*64)
            with raw.open("rb") as stream, self.assertRaisesRegex(ValueError, "raw_hash_mismatch"):
                pilot.verify_raw(stream, identity)
            with raw.open("rb") as stream, patch.dict(pilot.LIMITS, maximum_raw_file_bytes=1), self.assertRaisesRegex(ValueError, "raw_file_budget"):
                pilot.verify_raw(stream, identity)

    def test_cached_final_role_rejected_before_raw_stat_or_numeric_load(self):
        with tempfile.TemporaryDirectory() as temp:
            request, pin, _ = prepare(Path(temp), "final")
            with patch.object(pilot, "verify_raw", side_effect=AssertionError("raw touched")), self.assertRaisesRegex(ValueError, "development_only"):
                pilot.load_request(request, pin)

    def test_fixed_geometry_selection_preserves_gap_and_ignores_old_speed_mask(self):
        rows = [row(i) for i in range(150)]
        rows[10]["residual_available"] = False
        for r in rows:
            r["conditions_available"] = False
        self.assertEqual(pilot.fixed_window_start(rows), int(rows[11]["estimate_log_time_ns_decimal_private"]))

    def test_changed_fresh_inventory_rejected(self):
        raw = recording()
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, "fresh_inventory_changed"):
            pilot.decode_window(BytesIO(raw), len(raw), {}, (LOG, LOG+1), temp)

    def test_corrupt_chunk_crc_rejected(self):
        from mcap.reader import SeekingReader
        raw = bytearray(recording("NONE"))
        summary = SeekingReader(BytesIO(raw)).get_summary()
        selected = next(c for c in summary.chunk_indexes if c.message_start_time == LOG-10_000_000)
        raw[selected.chunk_start_offset+selected.chunk_length-1] ^= 1
        with self.assertRaises(Exception) as caught:
            self.check(bytes(raw))
        self.assertEqual(type(caught.exception).__name__, "CRCValidationError")
