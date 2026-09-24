from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

import numpy as np

from lane_residuals.domain.independent_outing_intake import EXPECTED_TOPOLOGY_SOURCE
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.domain.recording_pair_diagnostics import PairDiagnostics
from lane_residuals.io.independent_outing_intake import _DecodedReference, iter_geometry_records
from lane_residuals.io.mcap import RoadMessageError
from lane_residuals.io.recording_pair_feasibility import TOPICS, _count_geometry, inspect_recording_pairs
from lane_residuals.io.reference_diagnostics import reference_failure_detail
from tests.io.test_mcap_io import _vertex
from tests.io.test_recording_pair_feasibility import count, estimate, path


MAP_TOPOLOGY = "ROAD_TOPOLOGY_SOURCE_LANE_MAP"


def road_message():
    return SimpleNamespace(time_stamp=100, polyline_vertex_pool=[_vertex(-1., .5), _vertex(101., .5)],
        lane_segments=[SimpleNamespace(id=1, drive_path_range=SimpleNamespace(start=0, size=2),
            is_ego_lane=True, successor_lane_segment_indices=[], predecessor_lane_segment_indices=[])])


def decode_reference(message, *, details=True, schema="Adp.Perception.Road"):
    record = (SimpleNamespace(name=schema), SimpleNamespace(topic=TOPICS[1], message_encoding="protobuf"),
              SimpleNamespace(log_time=100, publish_time=100), message)
    return next(iter_geometry_records([record], collect_reference_diagnostics=details))


def diagnostic_count(records):
    accumulator = PairDiagnostics()
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
        counts = _count_geometry(iter(records), db, accumulator)
    return counts, accumulator.summary()


class ReferenceDiagnosticTests(unittest.TestCase):
    def test_distinguishes_empty_road_and_polyline_or_boundary_coordinate_failure(self):
        empty = road_message()
        empty.lane_segments = []
        bad_coordinate = SimpleNamespace(x=SimpleNamespace(mean=4., invalid_flags=1), y=0.)
        polyline = road_message()
        # Invalid unused entry still rejects the whole pool; no repair/filter.
        polyline.polyline_vertex_pool.append(bad_coordinate)
        boundary = road_message()
        boundary.boundary_vertex_pool = [bad_coordinate]
        for message, detail in (
            (empty, "road_fields:lane_segments_empty:none"),
            (polyline, "polyline_coordinates:vertex_pool_unreadable_coordinates:distributed_mean_invalid"),
            (boundary, "boundary_coordinates:vertex_pool_unreadable_coordinates:distributed_mean_invalid"),
        ):
            with self.subTest(detail=detail):
                old = decode_reference(message, details=False)
                new = decode_reference(message)
                self.assertEqual(old.failure_code, "map_RoadMessageError")
                self.assertEqual(new.failure_code, old.failure_code)
                self.assertEqual(new.source_time_ns, old.source_time_ns)
                self.assertIsNone(old.path)
                self.assertIsNone(new.path)
                self.assertIsNone(old.failure_detail)
                self.assertEqual(new.failure_detail, detail)

    def test_schema_and_required_field_failures_use_static_labels(self):
        self.assertEqual(decode_reference(road_message(), schema="wrong").failure_detail,
                         "schema:schema_or_encoding_mismatch:none")
        missing = road_message()
        del missing.lane_segments
        self.assertEqual(decode_reference(missing).failure_detail, "road_fields:required_field_missing:none")
        self.assertEqual(reference_failure_detail(RoadMessageError("secret payload 123.456"), "road_fields"),
                         "road_fields:road_message_or_segment_invalid:none")
        self.assertEqual(reference_failure_detail(GeometryValidationError("private code", "private value"), "private stage"),
                         "unclassified_stage:geometry_validation_error:none")

    def test_segment_failures_survive_ordering_rejection_without_payload_text(self):
        message = road_message()
        message.polyline_vertex_pool[0].x.mean = float("nan")
        record = decode_reference(message)
        self.assertEqual(record.failure_code, "map_map_ego_drive_path_not_unique")
        self.assertEqual(record.failure_detail, "ordered_ego_path:map_ego_drive_path_not_unique:none")
        self.assertEqual(dict(record.segment_failure_counts), {"invalid_geometry_values": 1})
        self.assertNotIn("nan", json.dumps(dict(record.segment_failure_counts)))

    def test_successful_geometry_is_byte_identical_and_default_details_stay_empty(self):
        message = road_message()
        old, new = decode_reference(message, details=False), decode_reference(message)
        self.assertIsNone(old.failure_code)
        self.assertIsNone(new.failure_detail)
        self.assertEqual(new.source_time_ns, old.source_time_ns)
        for name, value in vars(old.path).items():
            actual = getattr(new.path, name)
            if isinstance(value, np.ndarray):
                self.assertEqual(actual.dtype, value.dtype)
                self.assertEqual(actual.shape, value.shape)
                self.assertEqual(actual.tobytes(), value.tobytes())
            else:
                self.assertEqual(actual, value)
        self.assertEqual(old.segment_failure_counts, ())


class PairDiagnosticIoTests(unittest.TestCase):
    def fixture_records(self):
        epoch = 10**18
        failure = "road_fields:lane_segments_empty:none"
        unavailable = estimate(2, epoch + 2000, None)
        unavailable.frame.estimator_state = "unavailable"
        return [estimate(0, epoch, path()), estimate(1, epoch + 1000, path(), MAP_TOPOLOGY),
                unavailable, estimate(3, epoch + 3000, path()),
                estimate(4, epoch + 4000, path()), estimate(5, epoch + 5000, path(99.)),
                estimate(6, epoch + 6000, path()),
                _DecodedReference(0, epoch + 7, path(lateral=.5)),
                _DecodedReference(1, epoch + 980, path(lateral=.5)),
                _DecodedReference(2, epoch + 2003, None, "map_RoadMessageError", failure),
                _DecodedReference(3, epoch + 3000, None, "map_RoadMessageError", failure),
                _DecodedReference(4, epoch + 4000, path(lateral=2.)),
                _DecodedReference(5, epoch + 5000, path()),
                _DecodedReference(6, epoch + 6000, path(99.))]

    def test_counts_stay_equal_and_reference_failures_are_visible_when_estimate_also_fails(self):
        records = self.fixture_records()
        counts, details = diagnostic_count(records)
        self.assertEqual(counts, count(iter(records)))
        self.assertEqual(counts["anchored_h100_pair_count"], 2)
        self.assertEqual(counts["sensor_anchored_h100_pair_count"], 1)
        self.assertEqual(counts["pair_failure_counts"], {
            "estimate_invalid": 1, "map_RoadMessageError": 1,
            "anchor_distance_exceeds_1m_or_invalid": 1, "h100_estimate_coverage_incomplete": 1,
            "h100_reference_coverage_incomplete": 1})
        row = details["pair_outcomes_by_estimate_topology"][EXPECTED_TOPOLOGY_SOURCE]
        self.assertEqual(row["pair_count"], 6)
        self.assertEqual(row["reference_failure_counts"], {"road_fields:lane_segments_empty:none": 2})
        self.assertEqual(row["available_estimator_pair_count"], 5)
        self.assertEqual(row["reference_failure_counts_with_available_estimator"], {"road_fields:lane_segments_empty:none": 1})
        self.assertEqual(sum(row["outcome_counts"].values()), row["pair_count"])
        timing = details["timestamp_delta_summaries"]
        self.assertEqual([timing[key]["count"] for key in timing], [7, 2, 1])
        self.assertEqual(timing["anchored_h100_pairs"]["signed_reference_minus_estimate_ns"],
                         {"min": -20, "p50": -20, "p95": 7, "p99": 7, "max": 7})
        self.assertEqual(timing["sensor_anchored_h100_pairs"]["signed_reference_minus_estimate_ns"]["min"], 7)
        self.assertEqual((counts, details), diagnostic_count(list(reversed(records))))

    def test_ties_missing_times_and_failed_geometry_do_not_prefilter_matching(self):
        records = [estimate(0, 100, path()), estimate(1, 200, path()),
                   estimate(2, 200, None), estimate(3, None, path()),
                   _DecodedReference(0, 101, path()), _DecodedReference(1, 201, path()),
                   _DecodedReference(2, None, None, "map_RoadMessageError", "road_fields:lane_segments_empty:none")]
        counts, details = diagnostic_count(records)
        self.assertEqual(counts, count(iter(records)))
        self.assertEqual(details["timestamp_delta_summaries"]["all_numeric_pairs"]["count"], 1)
        self.assertEqual(counts["timestamp_pairing_counts"]["ambiguous_second_positions"], 1)
        self.assertEqual(sum(details["reference_failure_detail_counts"].values()), 1)
        self.assertEqual(sum(sum(row["reference_failure_counts"].values()) for row in details["pair_outcomes_by_estimate_topology"].values()), 0)

    def test_large_offsets_are_reported_without_creating_a_gate(self):
        huge = 2**63 + 1
        counts, details = diagnostic_count([estimate(0, 0, path()), _DecodedReference(0, huge, path())])
        self.assertEqual(counts["sensor_anchored_h100_pair_count"], 1)
        self.assertEqual(details["timestamp_delta_summaries"]["all_numeric_pairs"]["absolute_ns"]["max"], huge)

    def test_incomplete_stream_discards_all_details_and_cleans_disk_spool(self):
        def broken():
            yield from self.fixture_records()
            raise RuntimeError("private exception text")
        with tempfile.TemporaryDirectory() as temporary, patch(
                "lane_residuals.io.recording_pair_feasibility.iter_geometry_records", return_value=broken()):
            result = inspect_recording_pairs(Path("unused"), Path(temporary), include_diagnostics=True)
            self.assertEqual(list(Path(temporary).iterdir()), [])
        self.assertEqual(result, {"status": "inconclusive", "failure_code": "RuntimeError", "counts": None, "diagnostics": None})

    def test_diagnostic_accumulator_does_not_retain_payload_or_path_history(self):
        references = []
        largest_live = 0
        class Payload:
            pass
        def records():
            nonlocal largest_live
            for i in range(1000):
                payload, geometry = Payload(), path()
                references.extend((weakref.ref(payload), weakref.ref(geometry)))
                yield estimate(i, i, geometry, decoded=payload)
                largest_live = max(largest_live, sum(ref() is not None for ref in references))
        counts, details = diagnostic_count(records())
        self.assertEqual(counts["estimate_message_count"], 1000)
        self.assertLessEqual(largest_live, 4)
        self.assertTrue(all(ref() is None for ref in references))
        self.assertEqual(details["timestamp_delta_summaries"]["all_numeric_pairs"]["count"], 0)

    def test_real_protobuf_mcap_diagnostics_preserve_original_counts(self):
        try:
            from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
            from mcap.writer import Writer, CompressionType
        except ImportError:
            self.skipTest("MCAP extras not installed")
        descriptor = descriptor_pb2.FileDescriptorProto(name="diagnostic_fixture.proto", package="Adp.Perception", syntax="proto3")
        def message(name, specifications):
            result = descriptor.message_type.add(name=name)
            for number, (field_name, kind, repeated, target) in enumerate(specifications, 1):
                field = result.field.add(name=field_name, number=number, type=kind, label=3 if repeated else 1)
                if target:
                    field.type_name = ".Adp.Perception." + target
        message("Point", [("x", 1, False, None), ("y", 1, False, None)])
        message("Range", [("start", 5, False, None), ("size", 5, False, None)])
        message("Lane", [("id", 4, False, None), ("drive_path_range", 11, False, "Range"), ("is_ego_lane", 8, False, None)])
        message("Road", [("time_stamp", 4, False, None), ("polyline_vertex_pool", 11, True, "Point"), ("lane_segments", 11, True, "Lane")])
        pool = descriptor_pool.DescriptorPool()
        pool.Add(descriptor)
        Road = message_factory.GetMessageClass(pool.FindMessageTypeByName("Adp.Perception.Road"))
        good = Road(time_stamp=200)
        good.polyline_vertex_pool.add(x=-1., y=.5)
        good.polyline_vertex_pool.add(x=101., y=.5)
        lane = good.lane_segments.add(id=1, is_ego_lane=True)
        lane.drive_path_range.start, lane.drive_path_range.size = 0, 2
        bad = Road()
        bad.CopyFrom(good)
        bad.time_stamp = 300
        bad.polyline_vertex_pool[0].x = float("nan")
        descriptors = descriptor_pb2.FileDescriptorSet()
        descriptors.file.add().CopyFrom(descriptor)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "fixture.mcap"
            with raw.open("wb") as stream:
                writer = Writer(stream, compression=CompressionType.NONE, chunk_size=1)
                writer.start()
                schema = writer.register_schema("Adp.Perception.Road", "protobuf", descriptors.SerializeToString())
                channel = writer.register_channel(TOPICS[1], "protobuf", schema)
                for payload in (bad, Road(time_stamp=100), good):
                    writer.add_message(channel, payload.time_stamp, payload.SerializeToString(), payload.time_stamp)
                writer.finish()
            before = inspect_recording_pairs(raw, root)
            after = inspect_recording_pairs(raw, root, include_diagnostics=True)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["fixture.mcap"])
        self.assertEqual(after["status"], "complete")
        self.assertEqual(before["counts"], after["counts"])
        self.assertEqual(after["counts"]["reference_message_count"], 3)
        self.assertEqual(after["diagnostics"]["reference_failure_detail_counts"], {
            "road_fields:lane_segments_empty:none": 1, "ordered_ego_path:map_ego_drive_path_not_unique:none": 1})
        self.assertEqual(after["diagnostics"]["reference_segment_failure_counts"], {"invalid_geometry_values": 1})


if __name__ == "__main__":
    unittest.main()
