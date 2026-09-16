from __future__ import annotations

import hashlib
import unittest
from types import SimpleNamespace

try:
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
except ImportError:  # The optional MCAP extra supplies Protobuf in CI/production.
    descriptor_pb2 = descriptor_pool = message_factory = None

from lane_residuals.io.sensor_topology_feasibility import (
    FLT_MAX,
    INT64_MAX,
    REFERENCE_TOPIC,
    SENSOR_TOPIC,
    descriptor_file_sha256,
    inspect_decoded_recording,
    reference_h100_ready,
    sensor_message_audit,
)


def _field(message, name, number, field_type, label=None, type_name=None):
    field = message.field.add()
    field.name = name
    field.number = number
    field.type = field_type
    field.label = (
        descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        if label is None
        else label
    )
    if type_name:
        field.type_name = type_name


def _road_class(
    *,
    include_boundary_arc_pool=True,
    extra_field=False,
    boundary_arc_type=None,
    lane_segments_label=None,
    boundary_message_name="RoadLaneBoundary",
    topology_sensor_symbol="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
    boundary_camera_symbol="LANE_BOUNDARY_SOURCE_CAMERA",
):
    common = descriptor_pb2.FileDescriptorProto(
        name="synthetic_common.proto",
        package="Adp.Common",
        syntax="proto3",
    )
    wrapper = common.message_type.add(name="NormalDistributedValueF")
    _field(wrapper, "mean", 1, descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT)
    _field(wrapper, "standard_deviation", 2, descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT)
    _field(wrapper, "invalid_flags", 3, descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)

    geometry = descriptor_pb2.FileDescriptorProto(
        name="synthetic_geometry.proto",
        package="Adp",
        syntax="proto3",
    )
    geometry.dependency.append("synthetic_common.proto")
    vertex = geometry.message_type.add(name="PolylineVertex")
    _field(vertex, "x", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Common.NormalDistributedValueF")
    _field(vertex, "y", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Common.NormalDistributedValueF")
    boundary_source = geometry.enum_type.add(name="LaneBoundarySource")
    boundary_source.value.add(name="LANE_BOUNDARY_SOURCE_INVALID", number=0)
    boundary_source.value.add(name=boundary_camera_symbol, number=1)

    file = descriptor_pb2.FileDescriptorProto(
        name="synthetic_sensor_topology.proto",
        package="Adp.Perception",
        syntax="proto3",
    )
    file.dependency.extend(("synthetic_common.proto", "synthetic_geometry.proto"))
    topology = file.enum_type.add(name="RoadTopologySource")
    for name, number in (
        ("ROAD_TOPOLOGY_SOURCE_UNKNOWN", 0),
        ("ROAD_TOPOLOGY_SOURCE_LANE_MAP", 3),
        (topology_sensor_symbol, 4),
    ):
        topology.value.add(name=name, number=number)

    range_message = file.message_type.add(name="Range")
    _field(range_message, "start", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    _field(range_message, "size", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    ranges = file.message_type.add(name="BoundaryRanges")
    for name, number in (("map_based", 1), ("camera_based", 2), ("artificial", 3)):
        _field(ranges, name, number, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Perception.Range")
    boundary = file.message_type.add(name=boundary_message_name)
    _field(boundary, "geometry", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Perception.Range")
    _field(boundary, "source", 4, descriptor_pb2.FieldDescriptorProto.TYPE_ENUM, type_name=".Adp.LaneBoundarySource")
    segment = file.message_type.add(name="RoadLaneSegment")
    _field(segment, "id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    _field(segment, "successor_lane_segment_indices", 6, descriptor_pb2.FieldDescriptorProto.TYPE_INT64, label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED)
    _field(segment, "drive_path_range", 11, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Perception.Range")
    _field(segment, "left_lane_boundary_ranges", 12, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Perception.BoundaryRanges")
    _field(segment, "right_lane_boundary_ranges", 13, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, type_name=".Adp.Perception.BoundaryRanges")
    road = file.message_type.add(name="Road")
    _field(road, "topology_source", 4, descriptor_pb2.FieldDescriptorProto.TYPE_ENUM, type_name=".Adp.Perception.RoadTopologySource")
    _field(road, "time_stamp", 5, descriptor_pb2.FieldDescriptorProto.TYPE_SINT64)
    _field(road, "ego_lane_segment_indices", 6, descriptor_pb2.FieldDescriptorProto.TYPE_SINT64, label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED)
    _field(
        road,
        "lane_segments",
        7,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        label=(
            descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            if lane_segments_label is None
            else lane_segments_label
        ),
        type_name=".Adp.Perception.RoadLaneSegment",
    )
    _field(
        road,
        "lane_boundary_pool",
        9,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type_name=f".Adp.Perception.{boundary_message_name}",
    )
    _field(road, "polyline_vertex_pool", 10, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED, type_name=".Adp.PolylineVertex")
    _field(road, "polyline_arc_length_pool", 11, descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT, label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED)
    _field(road, "boundary_vertex_pool", 12, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED, type_name=".Adp.PolylineVertex")
    if include_boundary_arc_pool:
        _field(
            road,
            "boundary_arc_length_pool",
            13,
            (
                descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT
                if boundary_arc_type is None
                else boundary_arc_type
            ),
            label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        )
    if extra_field:
        _field(road, "unrelated_generation_marker", 18, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(common)
    pool.Add(geometry)
    pool.Add(file)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("Adp.Perception.Road"))


ROAD = None if descriptor_pb2 is None else _road_class()
ROAD_EXTRA = None if descriptor_pb2 is None else _road_class(extra_field=True)
ROAD_DRIFT = None if descriptor_pb2 is None else _road_class(include_boundary_arc_pool=False)
ROAD_TYPE_DRIFT = (
    None
    if descriptor_pb2 is None
    else _road_class(boundary_arc_type=descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE)
)
ROAD_LABEL_DRIFT = (
    None
    if descriptor_pb2 is None
    else _road_class(lane_segments_label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL)
)
ROAD_REFERENCE_DRIFT = (
    None
    if descriptor_pb2 is None
    else _road_class(boundary_message_name="AlternateRoadLaneBoundary")
)
ROAD_TOPOLOGY_ENUM_DRIFT = (
    None
    if descriptor_pb2 is None
    else _road_class(topology_sensor_symbol="NOT_SENSOR_TOPOLOGY")
)
ROAD_BOUNDARY_ENUM_DRIFT = (
    None
    if descriptor_pb2 is None
    else _road_class(boundary_camera_symbol="NOT_CAMERA")
)


def _set_range(value, start, size):
    value.start = start
    value.size = size


def _vertex(pool, x, y):
    value = pool.add()
    value.x.mean = x
    value.x.invalid_flags = 0
    value.y.mean = y
    value.y.invalid_flags = 0


def sensor_message(timestamp=1_000_000_000, *, road_class=None):
    road = (ROAD if road_class is None else road_class)(topology_source=4, time_stamp=timestamp)
    road.ego_lane_segment_indices.append(0)
    segment = road.lane_segments.add()
    segment.id = 10
    _set_range(segment.drive_path_range, INT64_MAX, 0)
    for ranges in (segment.left_lane_boundary_ranges, segment.right_lane_boundary_ranges):
        _set_range(ranges.map_based, INT64_MAX, 0)
        _set_range(ranges.artificial, INT64_MAX, 0)
    _set_range(segment.left_lane_boundary_ranges.camera_based, 0, 1)
    _set_range(segment.right_lane_boundary_ranges.camera_based, 1, 1)
    left = road.lane_boundary_pool.add(source=1)
    right = road.lane_boundary_pool.add(source=1)
    _set_range(left.geometry, 0, 2)
    _set_range(right.geometry, 2, 2)
    _vertex(road.boundary_vertex_pool, 0.0, 2.0)
    _vertex(road.boundary_vertex_pool, 120.0, 2.0)
    _vertex(road.boundary_vertex_pool, 0.0, -2.0)
    _vertex(road.boundary_vertex_pool, 120.0, -2.0)
    road.boundary_arc_length_pool.extend((0.0, 120.0, 0.0, 120.0))
    return road


def reference_message(timestamp=1_000_000_000):
    road = ROAD(time_stamp=timestamp)
    road.ego_lane_segment_indices.append(0)
    segment = road.lane_segments.add()
    segment.id = 10
    _set_range(segment.drive_path_range, 0, 2)
    _vertex(road.polyline_vertex_pool, 0.0, 0.0)
    _vertex(road.polyline_vertex_pool, 120.0, 0.0)
    road.polyline_arc_length_pool.extend((0.0, 120.0))
    return road


def _tuple(topic, message, *, schema="Adp.Perception.Road", encoding="protobuf"):
    return (
        SimpleNamespace(name=schema, encoding=encoding),
        SimpleNamespace(topic=topic, message_encoding=encoding),
        SimpleNamespace(log_time=0, publish_time=0, sequence=0),
        message,
    )


class _ValueProxy:
    def __init__(self, wrapped, overrides):
        self.DESCRIPTOR = wrapped.DESCRIPTOR
        self._wrapped = wrapped
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._wrapped, name)


@unittest.skipUnless(descriptor_pb2 is not None, "Protobuf optional dependency is unavailable")
class SensorTopologyIOTests(unittest.TestCase):
    def test_descriptor_identity_comes_from_message_file_bytes(self) -> None:
        message = sensor_message()
        self.assertEqual(
            descriptor_file_sha256(message),
            hashlib.sha256(message.DESCRIPTOR.file.serialized_pb).hexdigest(),
        )

    def test_whole_message_topology_requires_literal_non_boolean_integer_four(self) -> None:
        base = sensor_message()
        for value in (0, 3, True, 4.0):
            with self.subTest(value=value):
                result = sensor_message_audit(_ValueProxy(base, {"topology_source": value}))
                self.assertEqual(result.failure_codes, ("sensor_topology_source_invalid",))

    def test_exact_direct_path_sentinel_and_camera_provenance_fail_closed(self) -> None:
        direct = sensor_message()
        _set_range(direct.lane_segments[0].drive_path_range, 0, 0)
        self.assertEqual(sensor_message_audit(direct).failure_codes, ("sensor_unexpected_direct_path",))
        source = sensor_message()
        source.lane_boundary_pool[0].source = 0
        self.assertEqual(
            sensor_message_audit(source).failure_codes,
            ("sensor_camera_boundary_provenance_invalid",),
        )

    def test_non_camera_ranges_pool_bounds_wrappers_and_arcs_fail_closed(self) -> None:
        non_camera = sensor_message()
        _set_range(non_camera.lane_segments[0].left_lane_boundary_ranges.map_based, 0, 0)
        self.assertEqual(
            sensor_message_audit(non_camera).failure_codes,
            ("sensor_non_camera_boundary_present",),
        )

        bad_range = sensor_message()
        _set_range(bad_range.lane_segments[0].left_lane_boundary_ranges.camera_based, 9, 1)
        self.assertEqual(
            sensor_message_audit(bad_range).failure_codes,
            ("sensor_camera_boundary_range_invalid",),
        )

        bad_indirection = sensor_message()
        _set_range(bad_indirection.lane_boundary_pool[0].geometry, 9, 2)
        self.assertEqual(
            sensor_message_audit(bad_indirection).failure_codes,
            ("sensor_camera_boundary_geometry_invalid",),
        )

        invalid_wrapper = sensor_message()
        invalid_wrapper.boundary_vertex_pool[0].x.invalid_flags = 1
        self.assertEqual(
            sensor_message_audit(invalid_wrapper).failure_codes,
            ("sensor_camera_boundary_geometry_invalid",),
        )

        base = sensor_message()
        boolean_flags = _ValueProxy(
            base.boundary_vertex_pool[0].x,
            {"invalid_flags": True},
        )
        boolean_vertex = _ValueProxy(
            base.boundary_vertex_pool[0],
            {"x": boolean_flags},
        )
        boolean_pool = [boolean_vertex, *base.boundary_vertex_pool[1:]]
        self.assertEqual(
            sensor_message_audit(
                _ValueProxy(base, {"boundary_vertex_pool": boolean_pool})
            ).failure_codes,
            ("sensor_camera_boundary_geometry_invalid",),
        )

        sentinel_mean = _ValueProxy(
            base.boundary_vertex_pool[0].x,
            {"mean": FLT_MAX},
        )
        sentinel_vertex = _ValueProxy(
            base.boundary_vertex_pool[0],
            {"x": sentinel_mean},
        )
        sentinel_pool = [sentinel_vertex, *base.boundary_vertex_pool[1:]]
        self.assertEqual(
            sensor_message_audit(
                _ValueProxy(base, {"boundary_vertex_pool": sentinel_pool})
            ).failure_codes,
            ("sensor_camera_boundary_geometry_invalid",),
        )

        for arc_values in (
            (0.0, float("nan"), 0.0, 120.0),
            (1.0, 120.0, 0.0, 120.0),
            (0.0, -1.0, 0.0, 120.0),
            (0.0, 0.0, 0.0, 120.0),
        ):
            with self.subTest(arc_values=arc_values):
                invalid_arc = sensor_message()
                invalid_arc.boundary_arc_length_pool[:] = arc_values
                self.assertEqual(
                    sensor_message_audit(invalid_arc).failure_codes,
                    ("sensor_camera_boundary_geometry_invalid",),
                )

    def test_recording_counts_only_time_paired_dual_structural_availability(self) -> None:
        result = inspect_decoded_recording(
            (
                _tuple(SENSOR_TOPIC, sensor_message()),
                _tuple(REFERENCE_TOPIC, reference_message()),
            )
        )
        self.assertEqual(result.sensor_decoded_count, 1)
        self.assertEqual(result.camera_chain_100m_span_count, 1)
        self.assertEqual(result.reference_h100_ready_count, 1)
        self.assertEqual(result.source_time_pair_count, 1)
        self.assertEqual(result.synchronized_100m_candidate_count, 1)
        self.assertEqual(len(result.schema_inventory), 2)

        failed_geometry = sensor_message()
        failed_geometry.boundary_vertex_pool[0].x.invalid_flags = 1
        filtered = inspect_decoded_recording(
            (
                _tuple(SENSOR_TOPIC, failed_geometry),
                _tuple(REFERENCE_TOPIC, reference_message()),
            )
        )
        self.assertEqual(filtered.source_time_pair_count, 1)
        self.assertEqual(filtered.camera_chain_100m_span_count, 0)
        self.assertEqual(filtered.synchronized_100m_candidate_count, 0)

    def test_invalid_or_non_strict_source_time_disables_all_pairs(self) -> None:
        result = inspect_decoded_recording(
            (
                _tuple(SENSOR_TOPIC, sensor_message(1_000)),
                _tuple(SENSOR_TOPIC, sensor_message(1_000)),
                _tuple(REFERENCE_TOPIC, reference_message(1_000)),
            )
        )
        self.assertFalse(result.sensor_source_timestamps_strict)
        self.assertEqual(result.source_time_pair_count, 0)
        self.assertIn("sensor_source_timestamps_not_strict", result.failure_codes)

    def test_reference_readiness_reuses_invalid_wrapper_gate(self) -> None:
        reference = reference_message()
        reference.polyline_vertex_pool[0].x.invalid_flags = 1
        result = inspect_decoded_recording(
            (
                _tuple(SENSOR_TOPIC, sensor_message()),
                _tuple(REFERENCE_TOPIC, reference),
            )
        )
        self.assertEqual(result.reference_h100_ready_count, 0)
        self.assertEqual(result.synchronized_100m_candidate_count, 0)
        self.assertIn("reference_h100_coverage_incomplete", result.failure_codes)

        branched = ROAD(time_stamp=1_000_000_000)
        branched.ego_lane_segment_indices.append(0)
        segment = branched.lane_segments.add(id=1)
        segment.successor_lane_segment_indices.extend((1, 2))
        _set_range(segment.drive_path_range, 0, 2)
        _vertex(branched.polyline_vertex_pool, 0.0, 0.0)
        _vertex(branched.polyline_vertex_pool, 60.0, 0.0)
        branched.polyline_arc_length_pool.extend((0.0, 60.0))
        self.assertEqual(
            reference_h100_ready(branched),
            (False, "reference_successor_chain_invalid"),
        )

        cycle = ROAD(time_stamp=1_000_000_000)
        cycle.ego_lane_segment_indices.append(0)
        first = cycle.lane_segments.add(id=1)
        first.successor_lane_segment_indices.append(1)
        _set_range(first.drive_path_range, 0, 2)
        second = cycle.lane_segments.add(id=2)
        second.successor_lane_segment_indices.append(0)
        _set_range(second.drive_path_range, 2, 2)
        for x in (0.0, 60.0, 60.0, 80.0):
            _vertex(cycle.polyline_vertex_pool, x, 0.0)
        cycle.polyline_arc_length_pool.extend((0.0, 60.0, 0.0, 20.0))
        self.assertEqual(
            reference_h100_ready(cycle),
            (False, "reference_successor_chain_invalid"),
        )

    def test_schema_mismatch_is_retained_and_does_not_use_another_topic(self) -> None:
        result = inspect_decoded_recording(
            (_tuple(SENSOR_TOPIC, sensor_message(), schema="Wrong.Road"),)
        )
        self.assertIn("sensor_schema_or_encoding_mismatch", result.failure_codes)
        self.assertIn("reference_topic_missing", result.failure_codes)
        self.assertEqual(result.source_time_pair_count, 0)

    def test_required_field_drift_fails_closed_before_pairing(self) -> None:
        drifted_classes = (
            ROAD_DRIFT,
            ROAD_TYPE_DRIFT,
            ROAD_LABEL_DRIFT,
            ROAD_REFERENCE_DRIFT,
            ROAD_TOPOLOGY_ENUM_DRIFT,
            ROAD_BOUNDARY_ENUM_DRIFT,
        )
        for road_class in drifted_classes:
            with self.subTest(road_class=road_class):
                drifted = road_class(topology_source=4, time_stamp=1_000_000_000)
                result = inspect_decoded_recording(
                    (
                        _tuple(SENSOR_TOPIC, drifted),
                        _tuple(REFERENCE_TOPIC, reference_message()),
                    )
                )
                self.assertIn("sensor_required_structure_drift", result.failure_codes)
                self.assertEqual(result.source_time_pair_count, 0)
                self.assertEqual(result.synchronized_100m_candidate_count, 0)
                drift_items = [
                    item
                    for item in result.schema_inventory
                    if item.topic == SENSOR_TOPIC
                    and item.audit_support_status == "required_structure_drift"
                ]
                self.assertEqual(len(drift_items), 1)
                self.assertIsNotNone(drift_items[0].descriptor_file_sha256)
                self.assertTrue(drift_items[0].field_inventory)

    def test_conformant_descriptor_generations_remain_separate_inventory_entries(self) -> None:
        result = inspect_decoded_recording(
            (
                _tuple(SENSOR_TOPIC, sensor_message(1_000_000_000)),
                _tuple(SENSOR_TOPIC, sensor_message(1_100_000_000, road_class=ROAD_EXTRA)),
                _tuple(REFERENCE_TOPIC, reference_message(1_000_000_000)),
            )
        )
        sensor_items = [item for item in result.schema_inventory if item.topic == SENSOR_TOPIC]
        self.assertEqual(len(sensor_items), 2)
        self.assertEqual(
            {item.audit_support_status for item in sensor_items},
            {"structure_conformant"},
        )
        self.assertEqual(len(result.sensor_descriptor_file_sha256s), 2)


if __name__ == "__main__":
    unittest.main()
