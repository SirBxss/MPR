from contextlib import closing
import io
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.io import recording_ingestion as ingestion
from lane_residuals.io import exploratory_residuals as extraction
from lane_residuals.io.recording_pair_feasibility import MAX_CHUNK_BYTES, ResourceLimitError
from tests.io.test_exploratory_residuals import fixture, baseline, T, odometry


def indexed_summary(*, odometry_count=4, chunk_bytes=100):
    topics = list(ingestion.TOPIC_LIMITS)
    counts = {i: odometry_count if i == 3 else 2 for i in (1, 2, 3)}
    return SimpleNamespace(statistics=SimpleNamespace(chunk_count=1, channel_message_counts=counts,
        message_count=sum(counts.values()), message_start_time=2**63, message_end_time=2**63+1),
        chunk_indexes=[SimpleNamespace(chunk_length=chunk_bytes, uncompressed_size=chunk_bytes)],
        channels={i: SimpleNamespace(topic=topic, schema_id=i, message_encoding="protobuf") for i, topic in enumerate(topics, 1)},
        schemas={i: SimpleNamespace(name=f"schema{i}", encoding="protobuf", data=f"descriptor{i}".encode()) for i in (1,2,3)})


class RecordingReadinessIoTests(unittest.TestCase):
    def run_fixture(self, messages):
        with tempfile.TemporaryDirectory() as temporary, patch.object(ingestion, "_iter_messages", return_value=(item for item in messages)):
            result = ingestion.inspect_recording_readiness(Path("unused"), io.BytesIO(), Path(temporary))
            self.assertEqual(list(Path(temporary).iterdir()), [])
            return result

    def test_readiness_has_identical_geometry_and_diagnostics_without_residual_construction(self):
        messages = fixture()
        counts, diagnostics = baseline(messages)
        with patch.object(extraction, "aligned_residual") as residual:
            result = self.run_fixture(messages)
            residual.assert_not_called()
        self.assertEqual(result["counts"], counts)
        self.assertEqual(result["diagnostics"], diagnostics)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 2)
        self.assertEqual(result["complete_condition_support"]["transition_count"], 1)
        self.assertNotIn("candidates", result)
        self.assertNotIn("conditions", result)

    def test_future_speed_and_missing_features_keep_geometry_and_split_condition_sequences(self):
        messages = fixture(times=(T, T+100_000_000, T+200_000_000), no_confidence_at=1)
        result = self.run_fixture(messages)
        self.assertEqual(result["sensor_geometry_support"]["frame_count"], 3)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 2)
        self.assertEqual(result["complete_condition_support"]["transition_count"], 0)
        self.assertEqual(result["condition_failure_counts"]["estimate_features_estimate_confidence_empty"], 1)
        messages = fixture(times=(T,))
        messages[-1][3].timestamp = T+10_000_000
        messages.append(odometry(T-10_000_000, .4))
        result = self.run_fixture(messages)
        self.assertEqual(result["sensor_geometry_support"]["frame_count"], 1)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 0)
        self.assertEqual(result["condition_failure_counts"], {"speed_uses_future_source_sample": 1})

    def test_original_storage_order_is_reported_and_not_repaired(self):
        result = self.run_fixture(fixture(times=(T+100_000_000, T)))
        self.assertEqual(result["counts"]["sensor_anchored_h100_pair_count"], 2)
        self.assertEqual(result["source_clock_order"]["estimate"]["backward_step_count"], 1)
        self.assertEqual(result["log_clock_order"][ingestion.TOPICS[0]]["backward_step_count"], 1)
        self.assertEqual(result["sensor_geometry_support"]["sequence_count"], 2)

    def test_missing_source_timestamp_remains_in_pairing_and_clock_accounting(self):
        messages = fixture(); del messages[0][3].time_stamp
        result = self.run_fixture(messages)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["counts"]["estimate_message_count"], 2)
        self.assertEqual(result["counts"]["timestamp_pairing_counts"]["missing_time_first_positions"], 1)
        self.assertEqual(result["source_clock_order"]["estimate"]["missing_timestamp_count"], 1)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 1)

    def test_late_log_input_is_excluded_without_discarding_geometry(self):
        messages = fixture(times=(T,)); messages[-1][2].log_time = T+1_000_000_001
        result = self.run_fixture(messages)
        self.assertEqual(result["sensor_geometry_support"]["frame_count"], 1)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 0)
        self.assertEqual(result["condition_failure_counts"], {"speed_input_logged_after_estimate": 1})

    def test_incomplete_stream_discards_positive_prefix_and_private_spool(self):
        def interrupted():
            yield from fixture()
            raise RuntimeError("private coordinates and locator")
        result = self.run_fixture(interrupted())
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["failure_code"], "RuntimeError")
        for name in ("counts", "diagnostics", "source_clock_order", "complete_condition_support"):
            self.assertIsNone(result[name])

    def test_summary_retains_observed_resource_failure_without_payload_decode(self):
        for summary, code in ((indexed_summary(odometry_count=1_000_001), "advertised_topic_count_exceeds_resource_limit"),
                              (indexed_summary(chunk_bytes=MAX_CHUNK_BYTES+1), "advertised_chunk_exceeds_resource_limit")):
            reader = SimpleNamespace(get_summary=lambda: summary)
            with patch.object(ingestion, "decoder_types", return_value=(lambda *a, **k: reader, None)):
                metadata, failure = ingestion.indexed_metadata(io.BytesIO())
            self.assertEqual(failure, code)
            self.assertEqual(metadata["topics"][ingestion.DEFAULT_ODOMETRY_TOPIC]["advertised_message_count"], summary.statistics.channel_message_counts[3])
            self.assertEqual(metadata["log_start_ns_decimal"], str(2**63))

    def test_missing_index_has_no_scan_fallback_and_inconsistent_summary_is_explicit(self):
        reader = SimpleNamespace(get_summary=lambda: None)
        with patch.object(ingestion, "decoder_types", return_value=(lambda *a, **k: reader, None)):
            with self.assertRaisesRegex(ResourceLimitError, "no_scan_fallback"):
                ingestion.indexed_metadata(io.BytesIO())
        summary = indexed_summary(); summary.statistics.message_count += 1
        reader = SimpleNamespace(get_summary=lambda: summary)
        with patch.object(ingestion, "decoder_types", return_value=(lambda *a, **k: reader, None)):
            _, code = ingestion.indexed_metadata(io.BytesIO())
        self.assertEqual(code, "summary_message_count_mismatch")

    def test_actual_reader_summary_count_mismatch_discards_completed_positive_prefix(self):
        summary = indexed_summary()
        reader = SimpleNamespace(get_summary=lambda: summary,
            iter_decoded_messages=lambda **kwargs: (m for m in fixture(times=(T,))))
        with tempfile.TemporaryDirectory() as temporary, patch("lane_residuals.io.recording_pair_feasibility.decoder_types", return_value=(lambda *a, **k: reader, lambda: None)):
            result = ingestion.inspect_recording_readiness(Path("unused"), io.BytesIO(), Path(temporary))
            self.assertEqual(list(Path(temporary).iterdir()), [])
        self.assertEqual(result["failure_code"], "decoded_summary_topic_count_mismatch")
        self.assertIsNone(result["counts"])

    def test_new_odometry_budget_does_not_change_legacy_budget_or_permit_unbounded_decode(self):
        self.assertEqual(extraction.TOPIC_LIMITS[ingestion.DEFAULT_ODOMETRY_TOPIC], 300_000)
        self.assertEqual(ingestion.TOPIC_LIMITS[ingestion.DEFAULT_ODOMETRY_TOPIC], 1_000_000)
        with closing(sqlite3.connect(":memory:")) as db:
            store = extraction._OdometryStore(db, message_limit=1)
            store.add(*odometry(T, 0.))
            with self.assertRaises(ResourceLimitError): store.add(*odometry(T+1, .5))

    def test_residual_path_still_requires_preserved_counts_and_diagnostics(self):
        with closing(sqlite3.connect(":memory:")) as db:
            with self.assertRaisesRegex(ValueError, "preserved_observations_required"):
                extraction._scan_stream([], db, compute_residuals=True)

    def test_real_compressed_indexed_mcap_reuses_verified_open_descriptor_and_strict_inputs(self):
        try:
            from tests.io.recording_ingestion_fixture import write_recording
            import mcap
            import google.protobuf
        except ImportError: self.skipTest("MCAP extras not installed")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root/"pilot.mcap"
            write_recording(path, missing_confidence_at=1)
            with path.open("rb") as stream:
                identity = ingestion.sha256_stream(stream)
                metadata, code = ingestion.indexed_metadata(stream)
                result = ingestion.inspect_recording_readiness(path, stream, root)
                self.assertFalse(stream.closed)
                self.assertEqual(identity, ingestion.sha256_stream(stream))
            self.assertEqual(list(root.iterdir()), [path])
        self.assertIsNone(code)
        self.assertEqual(metadata["topics"][ingestion.DEFAULT_ODOMETRY_TOPIC]["advertised_message_count"], 4)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["counts"]["sensor_anchored_h100_pair_count"], 2)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 1)

    def test_real_mcap_missing_odometry_completes_with_geometry_and_explicit_empty_inputs(self):
        try:
            import mcap
            import google.protobuf
        except ImportError: self.skipTest("MCAP extras not installed")
        from tests.io.recording_ingestion_fixture import write_recording
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root/"pilot.mcap"; write_recording(path, include_odometry=False)
            with path.open("rb") as stream:
                result = ingestion.inspect_recording_readiness(path, stream, root)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["sensor_geometry_support"]["frame_count"], 2)
        self.assertEqual(result["complete_condition_support"]["frame_count"], 0)
        self.assertEqual(result["condition_failure_counts"], {"odometry_stream_empty": 2})
