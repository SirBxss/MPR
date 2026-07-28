import unittest
from types import SimpleNamespace

import numpy as np

from lane_residuals import road_frame_from_message, topic_probe_from_summary
from lane_residuals.mcap_io import road_frames_from_decoded_messages


def _value(mean: float) -> SimpleNamespace:
    return SimpleNamespace(mean=mean)


def _vertex(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(
        x=_value(x),
        y=_value(y),
        heading=_value(0.0),
        curvature=_value(0.0),
    )


def _range(start: int, size: int) -> SimpleNamespace:
    return SimpleNamespace(start=start, size=size)


class McapRoadMessageTests(unittest.TestCase):
    def test_road_message_preserves_geometry_timestamps_and_metadata(self) -> None:
        message = SimpleNamespace(
            time_stamp=SimpleNamespace(seconds=12, fractional_seconds=345),
            polyline_vertex_pool=[
                _vertex(-1.0, 0.2),
                _vertex(0.0, 0.2),
                _vertex(1.0, 0.2),
                _vertex(2.0, 0.2),
            ],
            polyline_arc_length_pool=[0.0, 1.0, 2.0, 3.0],
            lane_segments=[
                SimpleNamespace(
                    id=7,
                    drive_path_range=SimpleNamespace(start=0, size=4),
                    is_ego_lane=True,
                    quality=9,
                )
            ],
            quality=3,
            topology_source=4,
        )

        frame = road_frame_from_message(
            message,
            topic="/reference",
            schema_name="Adp.Perception.Road",
            log_time_ns=1_000,
            publish_time_ns=900,
            sequence=5,
        )

        self.assertEqual(frame.source_time_ns, 12_000_000_345)
        self.assertEqual(frame.sequence, 5)
        self.assertEqual(frame.metadata_dict, {"quality": 3, "topology_source": 4})
        self.assertEqual(len(frame.segments), 1)
        segment = frame.segments[0]
        self.assertEqual(segment.segment_id, 7)
        self.assertTrue(segment.is_ego)
        self.assertEqual(segment.quality, 9)
        np.testing.assert_allclose(segment.x, [-1.0, 0.0, 1.0, 2.0])
        np.testing.assert_allclose(segment.y, 0.2)
        np.testing.assert_allclose(segment.arc_length, [0.0, 1.0, 2.0, 3.0])
        self.assertEqual(segment.geometry_source, "drive_path")

    def test_sensor_centerline_is_constructed_from_paired_boundaries(self) -> None:
        x = np.linspace(-5.0, 60.0, 14)
        boundary_vertices = [
            *[_vertex(value, 1.8) for value in x],
            *[_vertex(value, -1.8) for value in x],
        ]
        message = SimpleNamespace(
            time_stamp=100,
            ego_lane_segment_indices=[0],
            polyline_vertex_pool=[],
            polyline_arc_length_pool=[],
            boundary_vertex_pool=boundary_vertices,
            lane_boundary_pool=[
                SimpleNamespace(geometry=_range(0, len(x))),
                SimpleNamespace(geometry=_range(len(x), len(x))),
            ],
            lane_segments=[
                SimpleNamespace(
                    id=10,
                    drive_path_range=_range(2**63 - 1, 0),
                    left_lane_boundary_ranges=SimpleNamespace(
                        camera_based=_range(0, 1),
                    ),
                    right_lane_boundary_ranges=SimpleNamespace(
                        camera_based=_range(1, 1),
                    ),
                )
            ],
        )

        frame = road_frame_from_message(
            message,
            topic="/sensor",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
        )

        self.assertEqual(len(frame.segments), 1)
        segment = frame.segments[0]
        self.assertTrue(segment.is_ego)
        self.assertEqual(segment.geometry_source, "paired_boundaries")
        np.testing.assert_allclose(segment.x, x)
        np.testing.assert_allclose(segment.y, 0.0, atol=1e-12)

    def test_message_level_ego_segment_id_is_used(self) -> None:
        message = SimpleNamespace(
            time_stamp=100,
            ego_lane_segment_id=20,
            polyline_vertex_pool=[
                _vertex(0.0, 0.0),
                _vertex(1.0, 0.0),
                _vertex(0.0, 1.0),
                _vertex(1.0, 1.0),
            ],
            polyline_arc_length_pool=[0.0, 1.0, 0.0, 1.0],
            lane_segments=[
                SimpleNamespace(
                    id=10,
                    drive_path_range=SimpleNamespace(start=0, size=2),
                ),
                SimpleNamespace(
                    id=20,
                    drive_path_range=SimpleNamespace(start=2, size=2),
                ),
            ],
        )

        frame = road_frame_from_message(
            message,
            topic="/road",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
        )

        self.assertEqual(
            [(segment.segment_id, segment.is_ego) for segment in frame.segments],
            [(10, False), (20, True)],
        )

    def test_invalid_segment_ranges_are_not_silently_indexed(self) -> None:
        message = SimpleNamespace(
            polyline_vertex_pool=[_vertex(0.0, 0.0), _vertex(1.0, 0.0)],
            polyline_arc_length_pool=[0.0, 1.0],
            lane_segments=[
                SimpleNamespace(
                    id=1,
                    drive_path_range=SimpleNamespace(start=1, size=10),
                )
            ],
        )

        frame = road_frame_from_message(
            message,
            topic="/road",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
        )

        self.assertEqual(frame.segments, ())
        self.assertEqual(len(frame.segment_extractions), 1)
        extraction = frame.segment_extractions[0]
        self.assertFalse(extraction.reconstruction_succeeded)
        self.assertIn(
            "left lane-boundary ranges are missing",
            extraction.failure_reason,
        )

    def test_all_rejected_decoded_messages_remain_auditable(self) -> None:
        schema = SimpleNamespace(name="Adp.Perception.Road")
        channel = SimpleNamespace(
            topic="/sensor",
            message_encoding="protobuf",
        )
        mcap_message = SimpleNamespace(
            log_time=1,
            publish_time=1,
            sequence=0,
        )
        invalid = SimpleNamespace(
            polyline_vertex_pool=[],
            boundary_vertex_pool=[],
            lane_boundary_pool=[],
            lane_segments=[
                SimpleNamespace(
                    id=1,
                    drive_path_range=_range(2**63 - 1, 0),
                )
            ],
        )

        grouped = road_frames_from_decoded_messages(
            [(schema, channel, mcap_message, invalid)],
            topics=["/sensor"],
        )

        self.assertEqual(len(grouped["/sensor"]), 1)
        extraction = grouped["/sensor"][0].segment_extractions[0]
        self.assertFalse(extraction.reconstruction_succeeded)
        self.assertEqual(extraction.segment_id, 1)
        self.assertIn("left lane-boundary", extraction.failure_reason)

    def test_failed_ego_segment_and_surviving_adjacent_lane_are_both_kept(self) -> None:
        message = SimpleNamespace(
            ego_lane_segment_indices=[0],
            polyline_vertex_pool=[
                _vertex(-5.0, 3.5),
                _vertex(60.0, 3.5),
            ],
            polyline_arc_length_pool=[0.0, 65.0],
            boundary_vertex_pool=[],
            lane_boundary_pool=[],
            lane_segments=[
                SimpleNamespace(
                    id=10,
                    drive_path_range=_range(2**63 - 1, 0),
                ),
                SimpleNamespace(
                    id=11,
                    drive_path_range=_range(0, 2),
                ),
            ],
        )

        frame = road_frame_from_message(
            message,
            topic="/sensor",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
        )

        self.assertEqual(
            [(item.segment_id, item.is_ego) for item in frame.segments],
            [(11, False)],
        )
        self.assertTrue(frame.ego_metadata_present)
        self.assertEqual(
            [
                (
                    item.segment_id,
                    item.is_ego,
                    item.reconstruction_succeeded,
                )
                for item in frame.segment_extractions
            ],
            [(10, True, False), (11, False, True)],
        )

    def test_direct_path_topic_probe_reports_encoding_without_decoding(self) -> None:
        summary = SimpleNamespace(
            channels={
                7: SimpleNamespace(
                    topic="/em/road/ego_lane_path",
                    schema_id=3,
                    message_encoding="ros1",
                ),
                8: SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    schema_id=4,
                    message_encoding="protobuf",
                ),
            },
            schemas={
                3: SimpleNamespace(name="road_msgs/Road", encoding="ros1msg"),
                4: SimpleNamespace(
                    name="Adp.Perception.EstimatedDrivePaths",
                    encoding="protobuf",
                ),
            },
            statistics=SimpleNamespace(
                channel_message_counts={7: 251, 8: 251},
            ),
        )

        records = topic_probe_from_summary(summary)

        self.assertEqual([record.message_count for record in records], [251, 251])
        self.assertEqual(records[0].message_encodings, ("ros1",))
        self.assertEqual(
            records[1].schema_names,
            ("Adp.Perception.EstimatedDrivePaths",),
        )
        self.assertFalse(any(
            record.supported_by_current_road_decoder for record in records
        ))


if __name__ == "__main__":
    unittest.main()
