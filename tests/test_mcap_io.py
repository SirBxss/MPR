import unittest
from types import SimpleNamespace

import numpy as np

from lane_residuals import RoadMessageError, road_frame_from_message


def _value(mean: float) -> SimpleNamespace:
    return SimpleNamespace(mean=mean)


def _vertex(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(
        x=_value(x),
        y=_value(y),
        heading=_value(0.0),
        curvature=_value(0.0),
    )


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

        with self.assertRaisesRegex(RoadMessageError, "no valid road segments"):
            road_frame_from_message(
                message,
                topic="/road",
                schema_name="Adp.Perception.Road",
                log_time_ns=1,
                publish_time_ns=1,
            )


if __name__ == "__main__":
    unittest.main()
