from contextlib import closing
from io import BytesIO
from pathlib import Path
import json
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from lane_residuals.io import recording_decode_check as decoder
from lane_residuals.io.bounded_recording_readiness import ScientificSink, TOPIC_LIMITS
from lane_residuals.io.exploratory_residuals import _scan_stream
from lane_residuals.io.recording_inventory import read_inventory
from lane_residuals.io.recording_readiness_resources import Observations, Workspace
from tests.io.bounded_readiness_fixture import recording, messages, stream_items, remove_field, classes, T


def inspect(raw):
    with tempfile.TemporaryDirectory() as temp:
        scratch=Path(temp);observations=Observations();observations.phase("descriptor_binding")
        inventory=read_inventory(BytesIO(raw),len(raw));deadline=time.monotonic()+1800
        with Workspace(scratch,lambda:None,observations,deadline) as workspace:
            sink=ScientificSink(workspace)
            integrity=decoder.check_decoding(BytesIO(raw),len(raw),inventory,sorted(TOPIC_LIMITS),scratch,
                workspace.checkpoint,scientific_sink=sink,processing_deadline=deadline,index_connection=workspace.index)
            observations.phase("scientific_finalize")
            readiness,availability,checked=sink.finalize()
            result={"integrity":integrity,"readiness":readiness,"availability":availability,"causality":checked,
                "failure_code":sink.failure_code,"bindings":sink.binding_observations,"observations":observations.summary()}
        assert list(scratch.iterdir())==[]
        return result


class BoundedScienceTests(unittest.TestCase):
    def test_ambiguous_projection_is_common_h100_attrition_and_other_pair_survives(self):
        result=inspect(recording(ambiguous_reference=True))
        self.assertIsNone(result["failure_code"])
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        readiness=result["readiness"]
        code="h100_reference_alignment_projection_ambiguous"
        self.assertEqual(readiness["counts"]["pair_failure_counts"],{code:1})
        stage=readiness["exclusive_attrition"]["stages"][5]
        self.assertEqual(stage,{"stage":"common_h100","input_count":2,"rejected_count":1,
            "remaining_count":1,"failure_code_counts":{code:1}})
        self.assertEqual(readiness["sensor_geometry_support"]["frame_count"],1)
        self.assertEqual(readiness["complete_condition_support"]["frame_count"],1)

    def test_real_compressions_equal_old_counts_features_and_default_decoder_bytes(self):
        for compression in ("NONE","ZSTD","LZ4"):
            raw=recording(compression=compression)
            result=inspect(raw);readiness=result["readiness"]
            self.assertIsNone(result["failure_code"]);self.assertTrue(result["causality"])
            self.assertEqual(readiness["sensor_geometry_support"]["frame_count"],2)
            self.assertEqual(readiness["complete_condition_support"]["transition_count"],1)
            with closing(sqlite3.connect(":memory:")) as db:
                db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role,position))")
                old=_scan_stream(stream_items(messages()),db)
            for key in ("counts","diagnostics","odometry"):
                self.assertEqual(readiness[key],old[key])
            with tempfile.TemporaryDirectory() as temp:
                old_integrity=decoder.check_decoding(BytesIO(raw),len(raw),read_inventory(BytesIO(raw),len(raw)),sorted(TOPIC_LIMITS),Path(temp))
            self.assertEqual(json.dumps(result["integrity"],sort_keys=True),json.dumps(old_integrity,sort_keys=True))
            stages=readiness["exclusive_attrition"]["stages"]
            self.assertEqual(len(stages),9);self.assertEqual(stages[-1]["remaining_count"],2)
            for a,b in zip(stages,stages[1:]):self.assertEqual(a["remaining_count"],b["input_count"])

    def test_confidence_missing_is_unsupported_but_empty_invalid_are_measured_zero(self):
        result=inspect(recording(mutate=remove_field("DrivePath","drive_path_confidences")))
        self.assertEqual(result["failure_code"],"scientific_binding_unsupported_estimate_descriptor")
        self.assertIsNone(result["readiness"]);self.assertEqual(result["availability"],"not_assessed")
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        binding=next(b for b in result["bindings"] if b["role"]=="estimate")
        self.assertEqual(binding["binding_failure_code"],"estimate_descriptor_fields_unsupported")
        for confidence in (None,0.,float("nan")):
            result=inspect(recording(confidence=confidence))
            self.assertIsNone(result["failure_code"]);self.assertTrue(result["causality"])
            self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
            self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],0)
            self.assertEqual(result["readiness"]["exclusive_attrition"]["stages"][-1]["rejected_count"],2)

    def test_zero_geometry_values_complete_but_reference_binding_failure_unknown(self):
        result=inspect(recording(invalid_geometry=True))
        self.assertIsNone(result["failure_code"])
        self.assertEqual(result["readiness"]["counts"]["timestamp_pairing_counts"]["pairs"],2)
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],0)
        result=inspect(recording(mutate=remove_field("Point","y")))
        self.assertEqual(result["failure_code"],"scientific_binding_unsupported_reference_descriptor")
        self.assertIsNone(result["readiness"])

    def test_odometry_poison_or_binding_keeps_geometry_and_false_causality(self):
        for options in ({"no_odometry":True},{"invalid_odometry":True},{"mutate":remove_field("OdometryState","yaw_angle")}):
            result=inspect(recording(**options))
            self.assertIsNone(result["failure_code"]);self.assertFalse(result["causality"])
            self.assertEqual(result["availability"],"unavailable_odometry")
            self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
            self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],0)
            codes=result["readiness"]["exclusive_attrition"]["stages"][-1]["failure_code_counts"]
            self.assertEqual(sum(codes.values()),2)

    def test_odometry_poison_zero_candidates_still_unavailable_and_overrides_feature_failure(self):
        result=inspect(recording(invalid_geometry=True,invalid_odometry=True))
        self.assertEqual(result["availability"],"unavailable_odometry")
        result=inspect(recording(invalid_odometry=True,confidence=None))
        readiness=result["readiness"]
        self.assertIn("estimate_features_estimate_confidence_empty",readiness["condition_failure_counts"])
        self.assertEqual(readiness["exclusive_attrition"]["stages"][-1]["failure_code_counts"],{"odometry_stream_invalid_or_schema_changed":2})

    def test_zero_message_unsupported_versions_are_bound_and_estimate_has_precedence(self):
        bad_estimate=classes(remove_field("DrivePath","drive_path_confidences"))[0]
        bad_reference=classes(remove_field("Point","y"))[1]
        result=inspect(recording(extra_streams=(("/adp/estimated_drive_paths",bad_estimate,()),("/adp/road_lane_map_based",bad_reference,()))))
        self.assertEqual(result["failure_code"],"scientific_binding_unsupported_estimate_descriptor")
        self.assertEqual(len(result["bindings"]),5)
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        bad_odometry=classes(remove_field("OdometryState","yaw_angle"))[2]
        result=inspect(recording(extra_streams=(("/adp/odometry",bad_odometry,()),)))
        self.assertIsNone(result["failure_code"]);self.assertEqual(result["availability"],"unavailable_odometry")
        self.assertEqual(result["readiness"]["odometry"]["failure_counts"],{})
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
        self.assertEqual(result["readiness"]["exclusive_attrition"]["stages"][-1]["failure_code_counts"],{"odometry_stream_invalid_or_schema_changed":2})

    def test_multiple_valid_odometry_schema_identities_poison_without_message_failures(self):
        def rename(_,odometry):odometry.name="second_odometry_fixture.proto"
        other=classes(rename)[2]
        value=other(timestamp=T,x_position=.5)
        result=inspect(recording(extra_streams=(("/adp/odometry",other,(value,)),)))
        self.assertEqual(result["availability"],"unavailable_odometry")
        self.assertEqual(len(result["readiness"]["odometry"]["schema_counts"]),2)
        self.assertEqual(result["readiness"]["odometry"]["failure_counts"],{})

    def test_single_segment_without_successor_short_reference_and_sequence_gaps(self):
        result=inspect(recording(times=(T,T+300_000_000)))
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["sequence_count"],2)
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["transition_count"],0)
        short=inspect(recording(reference_length=50.))
        self.assertEqual(short["readiness"]["counts"]["h100_pair_count"],0)
        self.assertEqual(short["readiness"]["exclusive_attrition"]["stages"][5]["rejected_count"],2)

    def test_crc_zero_storage_order_and_logs_do_not_change_default_reader(self):
        result=inspect(recording(crcs=False,times=(T+100_000_000,T)))
        self.assertEqual(result["integrity"]["selected_chunk_crc"]["checked_nonzero_count"],0)
        self.assertEqual(result["readiness"]["source_clock_order"]["estimate"]["backward_step_count"],1)

    def test_descriptor_precheck_precedes_all_payload_science_and_no_whole_summary(self):
        from mcap.reader import SeekingReader
        with patch.object(SeekingReader,"get_summary",side_effect=AssertionError("whole summary forbidden")), \
                patch("lane_residuals.io.bounded_recording_readiness.iter_geometry_records",side_effect=AssertionError("unsupported geometry invoked")):
            result=inspect(recording(mutate=remove_field("DrivePath","drive_path_confidences")))
        self.assertEqual(result["failure_code"],"scientific_binding_unsupported_estimate_descriptor")

    def test_scientific_exception_continues_full_container_and_unknown_code_nulls(self):
        with patch("lane_residuals.io.bounded_recording_readiness._estimate_features",side_effect=MemoryError):
            result=inspect(recording())
        self.assertEqual(result["failure_code"],"memory_limit")
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        self.assertIsNone(result["readiness"])
        from lane_residuals.domain.recording_readiness import exclusive_attrition
        result=inspect(recording())
        counts=result["readiness"]["counts"].copy();counts["pair_failure_counts"]={"estimate_future_unknown_label":1}
        with self.assertRaisesRegex(ValueError,"scientific_attrition_unclassified_failure"):
            exclusive_attrition(counts,[],True)

    def test_coverage_failure_precedes_anchor_when_both_fail(self):
        result=inspect(recording(reference_length=50.,reference_offset=2.))
        stages=result["readiness"]["exclusive_attrition"]["stages"]
        self.assertEqual(stages[5]["failure_code_counts"],{"h100_reference_coverage_incomplete":2})
        self.assertEqual(stages[6]["rejected_count"],0)
        self.assertEqual(stages[6]["input_count"],0)

    def test_insufficient_confidence_bucket_coverage_remains_data(self):
        result=inspect(recording(confidence_count=1))
        self.assertIsNone(result["failure_code"]);self.assertTrue(result["causality"])
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
        self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],0)
        self.assertEqual(result["readiness"]["condition_failure_counts"],{"estimate_features_estimate_confidence_h100_coverage_incomplete":2})

    def test_missing_clock_values_uint64_and_duplicate_times_keep_full_stream_pairing(self):
        for times in ((0,T),(T,T),(2**63+500_000_000,2**63+600_000_000)):
            def unsigned_clock(file,_):
                root=next(m for m in file.message_type if m.name=="EstimatedDrivePaths")
                next(f for f in root.field if f.name=="time_stamp").type=4
            result=inspect(recording(times=times,mutate=unsigned_clock))
            self.assertIsNone(result["failure_code"])
            self.assertEqual(result["readiness"]["counts"]["estimate_message_count"],2)
            self.assertEqual(result["readiness"]["exclusive_attrition"]["stages"][0]["input_count"],2)
