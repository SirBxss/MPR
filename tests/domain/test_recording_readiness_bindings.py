import hashlib
import unittest
from unittest.mock import patch

from lane_residuals.domain.recording_readiness_bindings import classify
from lane_residuals.domain.path_source_probe import ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256, estimate_descriptor_support
from tests.io.bounded_readiness_fixture import classes, descriptor_files, remove_field


def message(file,name):return next(m for m in file.message_type if m.name==name)
def field(file,parent,name):return next(f for f in message(file,parent).field if f.name==name)


class BindingTests(unittest.TestCase):
    def check(self,role,mutate=None):
        kind=classes(mutate)[("estimate","reference","odometry").index(role)]
        return classify(kind(),role,kind.DESCRIPTOR.full_name,"protobuf")[1]

    def test_complete_three_roles_and_values_do_not_affect_binding(self):
        for role,kind in zip(("estimate","reference","odometry"),classes()):
            digest,cause=classify(kind(),role,kind.DESCRIPTOR.full_name,"protobuf")
            self.assertIsNone(cause);self.assertEqual(digest,hashlib.sha256(kind.DESCRIPTOR.file.serialized_pb).hexdigest())

    def test_missing_reference_required_paths_and_partial_direct_entries_are_unsupported(self):
        for parent,name in (("Road","time_stamp"),("Lane","is_ego_lane"),("Road","polyline_vertex_pool"),("Lane","drive_path_range"),("Point","y"),("Range","size"),("Lane","id")):
            with self.subTest(parent=parent,name=name):
                self.assertEqual(self.check("reference",remove_field(parent,name)),"reference_descriptor_fields_unsupported")

    def test_wrong_types_cardinality_distributed_mean_and_optional_entries(self):
        def coordinate(file,_):
            message=file.message_type.add(name="Distributed")
            message.field.add(name="other",number=1,type=1,label=1)
            x=field(file,"Point","x");x.type=11;x.type_name=".Adp.Perception.Distributed"
        def boundary(file,_):
            bad=file.message_type.add(name="BadBoundaryPoint");bad.field.add(name="x",number=1,type=1,label=1)
            message(file,"Road").field.add(name="boundary_vertex_pool",number=88,type=11,type_name=".Adp.Perception.BadBoundaryPoint",label=3)
        changes=[coordinate,boundary,
            lambda f,o:setattr(field(f,"Lane","id"),"type",1),
            lambda f,o:setattr(field(f,"Road","lane_segments"),"label",1),
            lambda f,o:message(f,"Lane").field.add(name="successor_lane_segment_indices",number=88,type=5,label=1),
            lambda f,o:message(f,"Road").field.add(name="ego_lane_segment_id",number=88,type=8,label=1)]
        for change in changes:
            with self.subTest(change=change):self.assertEqual(self.check("reference",change),"reference_descriptor_fields_unsupported")

    def test_optional_successors_and_dominated_aliases_remain_optional(self):
        def change(file,_):
            message(file,"Lane").field.add(name="successor_lane_segment_indices",number=88,type=13,label=3)
            message(file,"Road").field.add(name="polyline_vertex_pool_",json_name="dominatedPool",number=89,type=9,label=1)
        self.assertIsNone(self.check("reference",change))

    def test_complete_direct_clock_does_not_hide_malformed_declared_fallback(self):
        def header(file,_):
            child=file.message_type.add(name="Header")
            child.field.add(name="other",number=1,type=4,label=1)
            message(file,"Road").field.add(name="header",number=88,type=11,type_name=".Adp.Perception.Header",label=1)
        def seconds(file,_):
            child=file.message_type.add(name="Time")
            child.field.add(name="seconds",number=1,type=1,label=1)
            value=field(file,"Road","time_stamp");value.type=11;value.type_name=".Adp.Perception.Time"
        for change in (header,seconds):self.assertEqual(self.check("reference",change),"reference_descriptor_fields_unsupported")

    def test_presence_based_clock_aliases_validate_all_candidates(self):
        def bad(file,_):message(file,"Road").field.add(name="timestamp",number=88,type=9,label=1)
        def good(file,_):message(file,"Road").field.add(name="timestamp",number=88,type=4,label=1)
        self.assertEqual(self.check("reference",bad),"reference_descriptor_fields_unsupported")
        self.assertIsNone(self.check("reference",good))

    def test_estimate_clock_topology_qualifier_and_confidence_shapes(self):
        for parent,name in (("EstimatedDrivePaths","time_stamp"),("EstimatedDrivePaths","topology_source"),("DrivePath","drive_path_confidences")):
            with self.subTest(parent=parent,name=name):
                self.assertEqual(self.check("estimate",remove_field(parent,name)),"estimate_descriptor_fields_unsupported")
        for kind in (8,9,12):
            def change(file,_,kind=kind):field(file,"DrivePath","drive_path_confidences").type=kind
            self.assertEqual(self.check("estimate",change),"estimate_descriptor_fields_unsupported")
        for symbol in ("ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY","LANE_ROLE_KEEP_LANE","DRIVE_PATH_ERROR_NO_ERROR"):
            def change(file,_,symbol=symbol):
                for enum in file.enum_type:
                    for value in enum.value:
                        if value.name==symbol:value.name="REMOVED_"+symbol
            self.assertEqual(self.check("estimate",change),"estimate_descriptor_fields_unsupported")

    def test_non_map_rule_applies_to_repeated_messages_and_confidences(self):
        def mapped(parent,name,key_type=5,value_type=1,value_name=None):
            def change(file,_):
                owner=message(file,parent);target=field(file,parent,name)
                child=owner.nested_type.add(name="MapEntry");child.options.map_entry=True
                child.field.add(name="key",number=1,type=key_type,label=1)
                value=child.field.add(name="value",number=2,type=value_type,label=1)
                if value_name:value.type_name=value_name
                target.type=11;target.type_name=".Adp.Perception."+parent+".MapEntry";target.label=3
            return change
        self.assertEqual(self.check("estimate",mapped("DrivePath","drive_path_confidences")),"estimate_descriptor_fields_unsupported")
        self.assertEqual(self.check("reference",mapped("Road","polyline_vertex_pool",value_type=11,value_name=".Adp.Perception.Point")),"reference_descriptor_fields_unsupported")
        # Generation precedence is explicit: a map entry lacks the historical
        # flag/index path, so do not relabel a known generation failure.
        self.assertEqual(self.check("estimate",mapped("EstimatedDrivePaths","drive_paths",value_type=11,value_name=".Adp.Perception.DrivePath")),"unsupported_estimate_descriptor_generation")

    def test_flag_absent_generation_is_still_exact_root_file_allowlist(self):
        change=remove_field("DrivePath","model_parameters_optional_flag")
        E,_,_=classes(change);value=E();digest=hashlib.sha256(value.DESCRIPTOR.file.serialized_pb).hexdigest()
        self.assertEqual(ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,"dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4")
        self.assertEqual(self.check("estimate",change),"unsupported_estimate_descriptor_generation")
        # As in legacy generation tests, substitute only the synthetic fixture
        # allowlist in this test. Production's exact pin is never modified.
        with patch("lane_residuals.domain.path_source_probe.ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",digest):
            self.assertEqual(estimate_descriptor_support(value).generation,"candidate_v2")
            self.assertIsNone(classify(value,"estimate",value.DESCRIPTOR.full_name,"protobuf")[1])
        self.assertEqual(classify(value,"estimate","Caller-supplied.hash","protobuf")[1],"estimate_schema_or_encoding_mismatch")

    def test_ego_enum_flags_require_declared_true_number_and_schema_identity(self):
        for number in (1,2):
            def change(file,_,number=number):
                enum=file.enum_type.add(name="EgoFlag");enum.value.add(name="EGO_UNKNOWN",number=0);enum.value.add(name="EGO_VALUE",number=number)
                value=field(file,"Lane","is_ego_lane");value.type=14;value.type_name=".Adp.Perception.EgoFlag"
            self.assertEqual(self.check("reference",change),None if number==1 else "reference_descriptor_fields_unsupported")
        E,R,O=classes()
        self.assertEqual(classify(R(),"reference",R.DESCRIPTOR.full_name,"ros1")[1],"map_schema_or_encoding_mismatch")
        self.assertEqual(self.check("odometry",remove_field("OdometryState","yaw_angle")),"odometry_descriptor_fields_unsupported")
