from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

import numpy as np

from lane_residuals.domain.exploratory_residuals import build_archive
from lane_residuals.domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA
from lane_residuals.io import exploratory_residuals as extraction
from lane_residuals.io.independent_outing_intake import iter_geometry_records
from lane_residuals.io.recording_pair_feasibility import TOPICS, _iter_messages, _indexed_summary, ResourceLimitError, RecordingReadError
from lane_residuals.io.odometry import DEFAULT_ODOMETRY_TOPIC
from tests.domain.test_geometry_validation import _estimated_schema, _root_message, _path
from tests.io.test_recording_pair_diagnostics import road_message, diagnostic_count
from tests.domain.test_exploratory_residuals import T


def odometry(time, x, *, log=T+1_000_000_000, yaw=0.):
    return (SimpleNamespace(name="Adp.OdometryState", data=b"odometry_fixture"),
        SimpleNamespace(topic=DEFAULT_ODOMETRY_TOPIC, message_encoding="protobuf"),
        SimpleNamespace(log_time=log, publish_time=log),
        SimpleNamespace(timestamp=time, x_position=x, y_position=0., yaw_angle=yaw))


def fixture(times=(T, T+100_000_000), *, no_confidence_at=None):
    schema = _estimated_schema()
    schema.path.fields_by_name = {field.name:field for field in schema.path_fields}
    messages = []
    for i, time in enumerate(times):
        candidate = _path(schema, starts=(-5., 0., 120.))
        candidate.drive_path_confidences = [] if i == no_confidence_at else [.5] * 40
        estimate = _root_message(schema, [candidate], timestamp=time)
        road = road_message()
        road.time_stamp = time
        for topic, name, decoded in ((TOPICS[0], DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA, estimate), (TOPICS[1], "Adp.Perception.Road", road)):
            messages.append((SimpleNamespace(name=name, data=b"schema"), SimpleNamespace(topic=topic, message_encoding="protobuf"),
                SimpleNamespace(log_time=time+1_000_000_000, publish_time=time+1_000_000_000), decoded))
        messages.extend((odometry(time-50_000_000, i), odometry(time, i+.5)))
    return messages


def baseline(messages):
    return diagnostic_count(list(iter_geometry_records([m for m in messages if m[1].topic != DEFAULT_ODOMETRY_TOPIC], collect_reference_diagnostics=True)))


def extract(messages, counts=None, diagnostics=None):
    if counts is None:
        counts, diagnostics = baseline(messages)
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
        return extraction._extract_stream(iter(messages), db, counts, diagnostics)


class ExploratoryIoTests(unittest.TestCase):
    def test_geometry_and_diagnostics_parity_with_actual_feature_extraction(self):
        messages = fixture()
        counts, details = baseline(messages)
        self.assertEqual(counts["sensor_anchored_h100_pair_count"], 2)
        result = extract(messages)
        self.assertEqual(result["counts"], counts)
        self.assertTrue(result["diagnostics_match_preserved"])
        for candidate in result["candidates"]:
            np.testing.assert_allclose(candidate["residuals_m"], -.5, atol=1e-12)
            np.testing.assert_allclose(candidate["conditions"], [10.,0.,0.,.5,.5,.5], atol=1e-12)
            self.assertEqual(candidate["condition_failure_codes"], [])
        self.assertEqual(result["input_ready_sequence_count_before_residuals"], 1)
        self.assertEqual(result["odometry"]["message_count"], 4)

    def test_missing_estimate_features_keep_residuals_and_exclusion_evidence(self):
        result = extract(fixture(no_confidence_at=1))
        arrays, support = build_archive(result["candidates"])
        self.assertEqual(arrays["residuals_m"].shape, (2,21))
        self.assertEqual(arrays["conditions"].shape, (1,6))
        self.assertIn("estimate_features_estimate_confidence_empty", result["candidates"][1]["condition_failure_codes"])

    def test_late_and_future_odometry_have_explicit_evidence_without_filtering_geometry(self):
        messages = fixture(times=(T,))
        messages[-1][3].timestamp = T+10_000_000
        messages.append(odometry(T-10_000_000,.4))
        result = extract(messages)
        row = result["candidates"][0]
        self.assertIsNotNone(row["residuals_m"])
        self.assertIsNone(row["conditions"])
        self.assertIn("speed_uses_future_source_sample", row["condition_failure_codes"])
        self.assertEqual(row["speed_bracket_evidence"]["current_upper_timestamp_ns_private"], T+10_000_000)
        messages = fixture(times=(T,))
        messages[-1][2].log_time = T+1_000_000_001
        row = extract(messages)["candidates"][0]
        self.assertEqual(row["condition_failure_codes"], ["speed_input_logged_after_estimate"])

    def test_identical_odometry_duplicates_coalesce_earliest_and_conflicts_remain_unusable(self):
        messages = fixture(times=(T,))
        messages[-1][2].log_time = T+1_000_000_010
        messages.append(odometry(T,.5,log=T))
        result = extract(messages)
        self.assertIsNotNone(result["candidates"][0]["conditions"])
        self.assertEqual(result["odometry"]["duplicate_timestamp_group_count"], 1)
        messages.append(odometry(T,.6,log=T))
        result = extract(messages)
        self.assertIsNone(result["candidates"][0]["conditions"])
        self.assertIsNotNone(result["candidates"][0]["residuals_m"])
        self.assertEqual(result["odometry"]["conflicting_timestamp_group_count"], 1)
        self.assertEqual(result["odometry"]["discarded_conflicting_message_count"], 3)

    def test_missing_or_invalid_odometry_does_not_discard_geometric_profiles(self):
        for invalid in (False, True):
            messages = fixture(times=(T,))
            if invalid:
                messages[-1][3].x_position = float("nan")
                expected = "odometry_stream_invalid_or_schema_changed"
            else:
                messages = [m for m in messages if m[1].topic != DEFAULT_ODOMETRY_TOPIC]
                expected = "odometry_stream_empty"
            result = extract(messages)
            row = result["candidates"][0]
            self.assertEqual(row["condition_failure_codes"], [expected])
            self.assertIsNotNone(row["residuals_m"])
            self.assertIsNone(row["conditions"])

    def test_no_residuals_computed_before_full_count_and_diagnostic_parity(self):
        messages = fixture()
        for drift in ("counts", "diagnostics", "candidate_count"):
            counts, details = baseline(messages)
            if drift == "counts": counts["estimate_descriptor_counts"] = {"changed": 2}
            elif drift == "diagnostics": details["reference_segment_failure_counts"] = {"changed": 1}
            else: counts["sensor_anchored_h100_pair_count"] = 1
            with patch.object(extraction, "aligned_residual") as residual:
                with self.assertRaises(RecordingReadError):
                    extract(messages, counts, details)
                residual.assert_not_called()

    def test_incomplete_stream_discards_candidates_and_cleans_spool_without_payload_leak(self):
        messages = fixture()
        counts, details = baseline(messages)
        def interrupted():
            yield from messages
            raise RuntimeError("private payload must not appear")
        with tempfile.TemporaryDirectory() as temporary, patch.object(extraction,"_iter_messages",return_value=interrupted()), patch.object(extraction,"aligned_residual") as residual:
            result = extraction.inspect_recording_residuals(Path("unused"),Path(temporary),counts,details)
            self.assertEqual(list(Path(temporary).iterdir()), [])
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["failure_code"], "RuntimeError")
        self.assertIsNone(result["candidates"])
        self.assertIsNone(result["counts"])
        residual.assert_not_called()

    def test_odometry_stream_retains_scalars_on_disk_not_payload_history(self):
        refs = []
        with closing(sqlite3.connect(":memory:")) as db:
            store = extraction._OdometryStore(db)
            for i in range(1000):
                item = odometry(T+i,float(i))
                # SimpleNamespace is not weak-referenceable; a small subclass is.
                class Payload:
                    pass
                decoded = Payload()
                decoded.__dict__.update(item[3].__dict__)
                refs.append(weakref.ref(decoded))
                store.add(*item[:3], decoded)
                del decoded, item
            self.assertTrue(all(ref() is None for ref in refs))
            self.assertEqual(store.summary()["distinct_valid_timestamp_count"], 1000)
            self.assertFalse(any(isinstance(v,list) for v in store.__dict__.values()))

    def test_summary_and_decoded_odometry_caps_are_explicit(self):
        summary = SimpleNamespace(statistics=SimpleNamespace(chunk_count=1, channel_message_counts={1:300001},message_count=300001),
            chunk_indexes=[SimpleNamespace(chunk_length=100,uncompressed_size=100)],
            channels={1:SimpleNamespace(topic=DEFAULT_ODOMETRY_TOPIC)})
        with self.assertRaises(ResourceLimitError):
            _indexed_summary(SimpleNamespace(get_summary=lambda:summary),topic_limits=extraction.TOPIC_LIMITS)
        with closing(sqlite3.connect(":memory:")) as db, patch.dict(extraction.TOPIC_LIMITS,{DEFAULT_ODOMETRY_TOPIC:1}):
            store = extraction._OdometryStore(db)
            store.add(*odometry(T,0.))
            with self.assertRaises(ResourceLimitError):store.add(*odometry(T+1,0.))

    def test_uint64_odometry_keys_order_exactly_and_bool_is_rejected(self):
        self.assertLess(extraction._time_key(2**63),extraction._time_key(2**63+1))
        self.assertEqual(int(extraction._time_key(2**64-1)),2**64-1)
        for value in (True,-1,2**64,1.0):
            with self.assertRaises(ValueError):extraction._time_key(value)

    def test_real_indexed_mcap_odometry_reader_and_store(self):
        try:
            from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
            from mcap.writer import Writer, CompressionType
        except ImportError:self.skipTest("MCAP extras not installed")
        descriptor = descriptor_pb2.FileDescriptorProto(name="odometry_extraction.proto",package="Adp",syntax="proto3")
        message = descriptor.message_type.add(name="OdometryState")
        for number,(name,kind) in enumerate((("timestamp",4),("x_position",1),("y_position",1),("yaw_angle",1)),1):
            message.field.add(name=name,number=number,type=kind,label=1)
        pool=descriptor_pool.DescriptorPool();pool.Add(descriptor)
        Odo=message_factory.GetMessageClass(pool.FindMessageTypeByName("Adp.OdometryState"))
        descriptors=descriptor_pb2.FileDescriptorSet();descriptors.file.add().CopyFrom(descriptor)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);raw=root/"odometry.mcap"
            with raw.open("wb") as stream:
                writer=Writer(stream,compression=CompressionType.NONE,chunk_size=1);writer.start()
                schema=writer.register_schema("Adp.OdometryState","protobuf",descriptors.SerializeToString())
                channel=writer.register_channel(DEFAULT_ODOMETRY_TOPIC,"protobuf",schema)
                for time,x in ((T,.5),(T-50_000_000,0.)):
                    writer.add_message(channel,T,Odo(timestamp=time,x_position=x).SerializeToString(),T)
                writer.finish()
            self.assertEqual(list(_iter_messages(raw)), [])  # legacy reads only EDP/RLMB
            with closing(sqlite3.connect(":memory:")) as db:
                store=extraction._OdometryStore(db)
                for record in _iter_messages(raw,topic_limits=extraction.TOPIC_LIMITS):store.add(*record)
                speed,_,failures=store.speed(T,T)
                self.assertAlmostEqual(speed,10.)
                self.assertEqual(failures,())
                self.assertEqual(store.summary()["message_count"],2)
