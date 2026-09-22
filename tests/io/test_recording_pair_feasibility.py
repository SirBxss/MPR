from __future__ import annotations

from contextlib import closing
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

import numpy as np

from lane_residuals.domain.independent_outing_intake import EXPECTED_TOPOLOGY_SOURCE
from lane_residuals.domain.pairing import ego_relative_path_from_points, mutual_nearest_timestamp_pairs
from lane_residuals.io.independent_outing_intake import (
    _DecodedEstimate, _DecodedReference, _decode_geometry_streams,
    _h100_geometry, iter_geometry_records,
)
from lane_residuals.io.recording_pair_feasibility import (
    MAX_CHUNK_BYTES, ResourceLimitError, TOPICS, _count_geometry,
    _indexed_summary, _iter_messages, _pack_path, _unpack_path, inspect_recording_pairs,
)
from tests.domain.test_geometry_validation import _estimated_schema, _path, _root_message
from tests.io.test_mcap_io import _vertex


def path(length=101.0, lateral=0.0):
    return ego_relative_path_from_points(np.array([[-1., lateral], [0., lateral], [length, lateral]]), source="fixture")


def estimate(index, time, geometry, topology=EXPECTED_TOPOLOGY_SOURCE, decoded=None):
    return _DecodedEstimate(index, time, SimpleNamespace(topology_source=topology,
        estimator_state="available_no_error"), None, geometry, "a" * 64, decoded,
        "estimate_invalid" if geometry is None else None)


def count(records):
    with tempfile.TemporaryDirectory() as temporary:
        with closing(sqlite3.connect(str(Path(temporary) / "test.sqlite"))) as db:
            db.execute("PRAGMA cache_size=-1024")
            db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
            return _count_geometry(records, db)


class RecordingPairIoTests(unittest.TestCase):
    def test_spool_roundtrip_preserves_path_arrays_and_alignment_boundaries(self):
        for lateral in (0.0, 1.0, np.nextafter(1., 2.)):
            original = path(lateral=lateral)
            restored = _unpack_path(_pack_path(original))
            for name in ("stations_m", "x_m", "y_m", "heading_rad", "origin_footpoint_m"):
                self.assertEqual(getattr(original, name).tobytes(), getattr(restored, name).tobytes())
            self.assertEqual(_h100_geometry(path(), original), _h100_geometry(path(), restored))
        self.assertIsNone(_unpack_path(_pack_path(None)))

    def test_complete_pairing_precedes_geometry_and_preserves_ties_and_missing_times(self):
        estimates = [estimate(0, 100, path()), estimate(1, 200, None),
                     estimate(2, 300, path()), estimate(3, 300, path()),
                     estimate(4, None, path()), estimate(5, 500, path())]
        references = [_DecodedReference(i, t, p) for i, (t, p) in enumerate(
            ((101, path(lateral=0.5)), (201, path()), (301, path()), (501, path(99.))))]
        result = count(iter(estimates + references))
        audit = mutual_nearest_timestamp_pairs([e.source_time_ns for e in estimates],
                                              [r.source_time_ns for r in references])
        self.assertEqual(result["timestamp_pairing_counts"]["pairs"], len(audit.pairs))
        self.assertEqual(result["timestamp_pairing_counts"]["ambiguous_second_positions"], 1)
        self.assertEqual(result["timestamp_pairing_counts"]["missing_time_first_positions"], 1)
        self.assertEqual(result["h100_pair_count"], 1)
        self.assertEqual(result["sensor_anchored_h100_pair_count"], 1)
        self.assertEqual(result["pair_failure_counts"], {"estimate_invalid": 1, "h100_reference_coverage_incomplete": 1})
        self.assertEqual(result, count(iter(list(reversed(estimates)) + list(reversed(references)))))

    def test_topology_and_anchor_do_not_enter_timestamp_selection(self):
        records = [estimate(0, 100, path(), "ROAD_TOPOLOGY_SOURCE_LANE_MAP"),
                   estimate(1, 200, path()),
                   _DecodedReference(0, 100, path(lateral=0.5)),
                   _DecodedReference(1, 200, path(lateral=1.00001))]
        result = count(iter(records))
        self.assertEqual(result["h100_pair_count"], 2)
        self.assertEqual(result["anchored_h100_pair_count"], 1)
        self.assertEqual(result["sensor_anchored_h100_pair_count"], 0)

    def test_long_stream_releases_messages_and_geometry_before_next_record(self):
        references = []
        largest_live = 0
        class Payload:
            pass
        def records():
            nonlocal largest_live
            for i in range(1500):
                payload = Payload()
                geometry = path()
                references.extend((weakref.ref(payload), weakref.ref(geometry)))
                yield estimate(i, i, geometry, decoded=payload)
                largest_live = max(largest_live, sum(ref() is not None for ref in references))
        result = count(records())
        self.assertEqual(result["estimate_message_count"], 1500)
        self.assertLessEqual(largest_live, 4)
        self.assertEqual(sum(ref() is not None for ref in references), 0)

    def test_incomplete_stream_discards_positive_prefix_and_removes_spool(self):
        def broken():
            yield estimate(0, 100, path())
            yield _DecodedReference(0, 100, path())
            raise RuntimeError("private payload detail must not be reported")
        with tempfile.TemporaryDirectory() as temporary, patch(
            "lane_residuals.io.recording_pair_feasibility.iter_geometry_records", return_value=broken()):
            result = inspect_recording_pairs(Path("not_read.mcap"), Path(temporary))
            self.assertEqual(list(Path(temporary).iterdir()), [])
        self.assertEqual(result, {"status": "inconclusive", "failure_code": "RuntimeError", "counts": None})

    def test_message_budget_is_an_inconclusive_execution_limit(self):
        def many():
            for i in range(4):
                yield estimate(i, i, None)
        with tempfile.TemporaryDirectory() as temporary, patch(
            "lane_residuals.io.recording_pair_feasibility.MAX_MESSAGES_PER_TOPIC", 3), patch(
            "lane_residuals.io.recording_pair_feasibility.iter_geometry_records", return_value=many()):
            result = inspect_recording_pairs(Path("not_read.mcap"), Path(temporary))
        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["counts"])

    def test_summary_requires_complete_indexes_counts_and_small_chunks(self):
        summary = SimpleNamespace(statistics=SimpleNamespace(chunk_count=1,
            channel_message_counts={1: 2}, message_count=2),
            chunk_indexes=[SimpleNamespace(chunk_length=100, uncompressed_size=100)],
            channels={1: SimpleNamespace(topic=TOPICS[0])})
        reader = SimpleNamespace(get_summary=lambda: summary)
        self.assertEqual(_indexed_summary(reader)[1], {TOPICS[0]: 2, TOPICS[1]: 0})
        summary.chunk_indexes[0].uncompressed_size = MAX_CHUNK_BYTES + 1
        with self.assertRaises(ResourceLimitError):
            _indexed_summary(reader)
        summary.chunk_indexes = []
        with self.assertRaises(ResourceLimitError):
            _indexed_summary(reader)

    def test_shared_iterator_matches_legacy_conversion_and_keeps_failed_records(self):
        schema = _estimated_schema()
        good = _root_message(schema, [_path(schema, starts=(-5., 0., 120.))], timestamp=100)
        bad = _root_message(schema, [_path(schema, model_flag=False)], timestamp=200)
        reference = SimpleNamespace(time_stamp=100, polyline_vertex_pool=[_vertex(-1., 0.5), _vertex(101., 0.5)],
            polyline_arc_length_pool=[0., 102.], lane_segments=[SimpleNamespace(id=1,
                drive_path_range=SimpleNamespace(start=0, size=2), is_ego_lane=True,
                successor_lane_segment_indices=[], predecessor_lane_segment_indices=[])])
        messages = [(SimpleNamespace(name=name), SimpleNamespace(topic=topic, message_encoding="protobuf"),
                     SimpleNamespace(log_time=100, publish_time=100), message)
                    for topic, name, message in ((TOPICS[0], "Adp.Perception.EstimatedDrivePaths", good),
                        (TOPICS[1], "Adp.Perception.Road", reference),
                        (TOPICS[0], "Adp.Perception.EstimatedDrivePaths", bad))]
        records = list(iter_geometry_records(iter(messages)))
        self.assertIsNotNone(records[0].path)
        self.assertIsNotNone(records[1].path)
        self.assertIsNone(records[2].path)
        self.assertEqual([r.message_index for r in records], [0, 0, 1])
        with patch("lane_residuals.io.independent_outing_intake.iter_decoded_mcap_messages", return_value=iter(messages)):
            estimates, references, failures = _decode_geometry_streams(Path("fixture"))
        self.assertEqual(failures, ())
        self.assertEqual([e.source_time_ns for e in estimates], [100, 200])
        self.assertEqual(estimates[1].failure_code, records[2].failure_code)
        np.testing.assert_array_equal(estimates[0].path.points, records[0].path.points)
        np.testing.assert_array_equal(references[0].path.points, records[1].path.points)

    def test_real_mcap_reader_uses_storage_order_and_ignores_other_topics(self):
        try:
            from google.protobuf import descriptor_pb2, timestamp_pb2
            from mcap.writer import Writer, CompressionType
        except ImportError:
            self.skipTest("MCAP extras not installed")
        message = timestamp_pb2.Timestamp(seconds=10)
        descriptors = descriptor_pb2.FileDescriptorSet()
        message.DESCRIPTOR.file.CopyToProto(descriptors.file.add())
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "fixture.mcap"
            with target.open("wb") as stream:
                writer = Writer(stream, compression=CompressionType.NONE, chunk_size=1)
                writer.start()
                schema = writer.register_schema(message.DESCRIPTOR.full_name, "protobuf", descriptors.SerializeToString())
                channel = writer.register_channel(TOPICS[0], "protobuf", schema)
                ignored = writer.register_channel("/unrequested", "protobuf", schema)
                writer.add_message(channel, 300, message.SerializeToString(), 300)
                writer.add_message(ignored, 200, b"invalid protobuf", 200)
                writer.add_message(channel, 100, message.SerializeToString(), 100)
                writer.finish()
            self.assertEqual([item[2].log_time for item in _iter_messages(target)], [300, 100])
            result = inspect_recording_pairs(target, Path(temporary))
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["counts"]["estimate_message_count"], 2)
            self.assertEqual(result["counts"]["h100_pair_count"], 0)


if __name__ == "__main__":
    unittest.main()
