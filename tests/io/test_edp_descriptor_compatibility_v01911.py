"""Two exact v2 entries; synthetic fixtures never contain private descriptors."""

import hashlib
import unittest
from unittest.mock import patch

from lane_residuals.domain import path_source_probe as probe
from lane_residuals.domain.geometry_validation import estimated_frame_from_message
from lane_residuals.domain.recording_readiness_bindings import classify
from lane_residuals.io.bounded_recording_readiness import REVISION
from tests.io.bounded_readiness_fixture import classes, messages, recording, remove_field, T
from tests.io.test_bounded_recording_readiness import inspect


SECOND_PIN = "lane_residuals.domain.path_source_probe.ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256"
FLAG_ABSENT = remove_field("DrivePath", "model_parameters_optional_flag")


def variant(file, odometry):
    FLAG_ABSENT(file, odometry)
    file.name = "synthetic_additional_v2_fixture.proto"
    root = next(m for m in file.message_type if m.name == "EstimatedDrivePaths")
    next(f for f in root.field if f.name == "time_stamp").type = 18  # sint64


def digest(message):
    return hashlib.sha256(message.DESCRIPTOR.file.serialized_pb).hexdigest()


def frame(message, **kwargs):
    return estimated_frame_from_message(message, message_index=0,
        log_time_ns=T+2_000_000_000, publish_time_ns=T+2_000_000_001, **kwargs)


class AdditionalEdpDescriptorTests(unittest.TestCase):
    def test_two_production_pins_are_distinct_and_original_is_unchanged(self):
        self.assertEqual(probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
            "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4")
        self.assertEqual(probe.ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
            "604f854d430cf394693b4fe8944b8bbd12d10959e33935e716d65955a0b2ab9a")
        self.assertNotEqual(probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
            probe.ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256)

    def test_secondary_entry_admits_fixture_without_replacing_original_entry(self):
        value=messages(mutate=variant)[0]
        self.assertFalse(probe.estimate_descriptor_support(value).supported)
        with patch(SECOND_PIN,digest(value)):
            support=probe.estimate_descriptor_support(value)
            self.assertTrue(support.supported)
            self.assertEqual(support.generation,"candidate_v2")
            self.assertFalse(support.model_parameters_optional_flag_required)
            self.assertEqual(support.missing_required_fields,())
            self.assertIsNone(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf")[1])
            self.assertTrue(frame(value).candidate_ready)
            self.assertEqual(probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
                "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4")

    def test_unknown_root_and_caller_fingerprint_cannot_admit(self):
        value=messages(mutate=variant)[0]
        support=probe.estimate_descriptor_support(value)
        self.assertEqual(support.failure_code,"unsupported_estimate_descriptor_generation")
        audit=frame(value,schema_fingerprint=probe.ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256)
        self.assertEqual(audit.conversion_state,"unsupported_estimate_descriptor_generation")
        self.assertFalse(audit.candidate_ready)

    def test_exact_root_mutation_does_not_inherit_secondary_entry(self):
        value=classes(variant)[0]()
        def changed(file,odometry):
            variant(file,odometry)
            file.name="unreviewed_schema_change.proto"
        other=classes(changed)[0]()
        with patch(SECOND_PIN,digest(value)):
            self.assertTrue(probe.estimate_descriptor_support(value).supported)
            self.assertNotEqual(digest(value),digest(other))
            self.assertEqual(probe.estimate_descriptor_support(other).failure_code,
                "unsupported_estimate_descriptor_generation")

    def test_recognized_secondary_entry_retains_flag_and_index_guards(self):
        for change in ("flag_present","unsigned_index","float_index","repeated_index","missing_index"):
            def mutate(file,odometry):
                if change!="flag_present":variant(file,odometry)
                model=next(m for m in file.message_type if m.name=="ClothoidSplineMinimalParameters")
                index=next(f for f in model.field if f.name=="index_0")
                if change=="unsigned_index":index.type=4
                elif change=="float_index":index.type=1
                elif change=="repeated_index":index.label=3
                elif change=="missing_index":
                    kept=[f for f in model.field if f.name!="index_0"]
                    del model.field[:];model.field.extend(kept)
            with self.subTest(change=change):
                value=classes(mutate)[0]()
                with patch(SECOND_PIN,digest(value)):
                    self.assertEqual(probe.estimate_descriptor_support(value).failure_code,
                        "candidate_v2_descriptor_contract_mismatch")

    def test_explicit_model_presence_error_and_sensor_rules_remain_required(self):
        value=messages(mutate=variant)[0]
        with patch(SECOND_PIN,digest(value)):
            self.assertTrue(frame(value).candidate_ready)
            value.drive_paths[0].ClearField("model_parameters")
            self.assertFalse(frame(value).candidate_ready)
        value=messages(mutate=variant)[0]
        with patch(SECOND_PIN,digest(value)):
            value.drive_paths[0].error=0
            self.assertFalse(frame(value).candidate_ready)
            value.drive_paths[0].error=1
            value.topology_source=0
            self.assertFalse(frame(value).candidate_ready)

    def test_confidence_clock_and_numeric_consumer_bindings_are_not_relaxed(self):
        for parent,name in (("DrivePath","drive_path_confidences"),("EstimatedDrivePaths","time_stamp"),("ClothoidSplineMinimalParameters","x_0")):
            def mutate(file,odometry):
                variant(file,odometry);remove_field(parent,name)(file,odometry)
            with self.subTest(field=name):
                value=classes(mutate)[0]()
                with patch(SECOND_PIN,digest(value)):
                    self.assertIsNotNone(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf")[1])

    def test_native_mcap_second_entry_keeps_complete_geometry_features_and_revision(self):
        value=classes(variant)[0]()
        with patch(SECOND_PIN,digest(value)):
            result=inspect(recording(mutate=variant))
        self.assertIsNone(result["failure_code"])
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
        self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],2)
        self.assertEqual(REVISION,"v0.19.11-bounded-recording-readiness-2026-10-15-a1")

    def test_unknown_version_retains_integrity_and_null_readiness(self):
        result=inspect(recording(mutate=variant))
        self.assertEqual(result["failure_code"],"scientific_binding_unsupported_estimate_descriptor")
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        self.assertIsNone(result["readiness"])

    def test_invalid_payload_values_remain_data_rejections_for_approved_entry(self):
        value=classes(variant)[0]()
        with patch(SECOND_PIN,digest(value)):
            for confidence in (None,0.,float("nan")):
                with self.subTest(confidence=confidence):
                    result=inspect(recording(mutate=variant,confidence=confidence))
                    self.assertIsNone(result["failure_code"])
                    self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
                    self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],0)
