"""Two exact v2 entries; synthetic fixtures never contain private descriptors."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.domain import path_source_probe as probe
from lane_residuals.domain.geometry_validation import estimated_frame_from_message
from lane_residuals.domain.recording_readiness_bindings import classify
from lane_residuals.io.bounded_recording_readiness import REVISION
from lane_residuals.io.independent_outing_intake import (
    _decode_geometry_streams, inspect_recording_technical_evidence,
)
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
        log_time_ns=T+2_000_000_000, publish_time_ns=T+2_000_000_001,
        allow_bounded_v01911_edp=True, **kwargs)


def bounded_support(message):
    return probe.estimate_descriptor_support(message, allow_bounded_v01911_edp=True)


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
        self.assertFalse(bounded_support(value).supported)
        with patch(SECOND_PIN,digest(value)):
            support=bounded_support(value)
            self.assertTrue(support.supported)
            self.assertEqual(support.generation,"candidate_v2")
            self.assertFalse(support.model_parameters_optional_flag_required)
            self.assertEqual(support.missing_required_fields,())
            self.assertIsNone(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf",allow_bounded_v01911_edp=True)[1])
            self.assertTrue(frame(value).candidate_ready)
            self.assertEqual(probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
                "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4")

    def test_unknown_root_and_caller_fingerprint_cannot_admit(self):
        value=messages(mutate=variant)[0]
        support=bounded_support(value)
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
            self.assertTrue(bounded_support(value).supported)
            self.assertNotEqual(digest(value),digest(other))
            self.assertEqual(bounded_support(other).failure_code,
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
                    self.assertEqual(bounded_support(value).failure_code,
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
                    self.assertIsNotNone(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf",allow_bounded_v01911_edp=True)[1])

    def test_native_mcap_second_entry_keeps_complete_geometry_features_and_revision(self):
        value=classes(variant)[0]()
        with patch(SECOND_PIN,digest(value)):
            result=inspect(recording(mutate=variant))
        self.assertIsNone(result["failure_code"])
        self.assertEqual(result["integrity"]["decoded_selected_message_count"],8)
        self.assertEqual(result["readiness"]["sensor_geometry_support"]["frame_count"],2)
        self.assertEqual(result["readiness"]["complete_condition_support"]["frame_count"],2)
        self.assertEqual(REVISION,"v0.19.11-bounded-recording-readiness-2026-10-16-a2")

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

    def test_second_entry_requires_explicit_bounded_policy_at_each_shared_boundary(self):
        value=messages(mutate=variant)[0]
        with patch(SECOND_PIN,digest(value)):
            self.assertFalse(probe.estimate_descriptor_support(value).supported)
            self.assertTrue(bounded_support(value).supported)
            self.assertEqual(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf")[1],
                "unsupported_estimate_descriptor_generation")
            default=estimated_frame_from_message(value,message_index=0,
                log_time_ns=T+2_000_000_000,publish_time_ns=T+2_000_000_001)
            self.assertFalse(default.candidate_ready)
            self.assertTrue(frame(value).candidate_ready)
            self.assertIsNone(inspect(recording(mutate=variant))["failure_code"])

    def test_original_entry_remains_supported_with_default_and_bounded_policies(self):
        value=messages(mutate=variant)[0]
        original="lane_residuals.domain.path_source_probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256"
        with patch(original,digest(value)):
            self.assertTrue(probe.estimate_descriptor_support(value).supported)
            self.assertTrue(bounded_support(value).supported)

    def test_historical_lock_technical_consumer_cannot_admit_second_root(self):
        value=classes(variant)[0]()
        with tempfile.TemporaryDirectory() as temp,patch(SECOND_PIN,digest(value)):
            path=Path(temp)/"synthetic.mcap";path.write_bytes(recording(mutate=variant))
            estimates,references,failures=_decode_geometry_streams(path)
            self.assertEqual(failures,())
            self.assertEqual((len(estimates),len(references)),(2,2))
            for estimate in estimates:
                self.assertIsNone(estimate.path)
                self.assertEqual(estimate.failure_code,
                    "estimate_unsupported_estimate_descriptor_generation")
            evidence=inspect_recording_technical_evidence(path,raw_usable=True)
            self.assertEqual(evidence.estimate_message_count,2)
            self.assertEqual(evidence.estimate_file_descriptor_sha256,(digest(value),))
            self.assertTrue(evidence.frames)
            for item in evidence.frames:
                self.assertFalse(item.topology_gate_candidate)
                self.assertFalse(item.h100_geometry_ready)
                self.assertFalse(item.eligible)
                self.assertIn("estimate_unsupported_estimate_descriptor_generation",item.failure_codes)

    def test_bounded_policy_is_boolean_and_never_accepts_a_caller_hash(self):
        value=messages(mutate=variant)[0]
        for invalid in (None,1,"true",frozenset((digest(value),))):
            with self.subTest(value=invalid),self.assertRaisesRegex(ValueError,"must be bool"):
                probe.estimate_descriptor_support(value,allow_bounded_v01911_edp=invalid)

    def test_evidenced_enum_numbering_and_unset_implicit_defaults_fail_closed(self):
        def enum_variant(file,odometry):
            variant(file,odometry)
            error=next(e for e in file.enum_type if e.name=="DrivePathError")
            next(v for v in error.value if v.name=="DRIVE_PATH_ERROR_NO_ERROR").number=7
            error.value.add(name="DRIVE_PATH_ERROR_CROSSES_ITSELF",number=1)
        value=messages(mutate=enum_variant)[0]
        with patch(SECOND_PIN,digest(value)):
            self.assertFalse(value.drive_paths[0].DESCRIPTOR.fields_by_name["error"].has_presence)
            self.assertFalse(value.drive_paths[0].DESCRIPTOR.fields_by_name["role"].has_presence)
            self.assertFalse(frame(value).candidate_ready)  # 1 is an error, not success.
            value.drive_paths[0].error=7
            self.assertTrue(frame(value).candidate_ready)
            value.drive_paths[0].ClearField("error")
            self.assertFalse(frame(value).candidate_ready)  # 0 is UNINITIALIZED.
            value.drive_paths[0].error=7
            value.drive_paths[0].ClearField("role")
            self.assertFalse(frame(value).candidate_ready)  # 0 is UNKNOWN.
