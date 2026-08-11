import unittest

import numpy as np

from lane_residuals import (
    GeometryValidationError,
    RoadFrame,
    RoadSegment,
    compare_ego_relative_paths,
    ego_relative_path_from_points,
    evenly_spaced_indices,
    nearest_monotone_pairs_unbounded,
    origin_alignment_metrics,
    sample_ego_relative_path,
    select_unique_ego_drive_path,
)


class EgoFootpointTests(unittest.TestCase):
    def test_origin_projection_defines_relative_station_zero(self) -> None:
        points = np.asarray([[-5.0, 0.2], [0.0, 0.2], [120.0, 0.2]])
        path = ego_relative_path_from_points(points, source="reference")

        self.assertAlmostEqual(path.origin_distance_m, 0.2)
        np.testing.assert_allclose(path.origin_footpoint_m, [0.0, 0.2])
        self.assertAlmostEqual(path.stations_m[1], 0.0)
        self.assertAlmostEqual(path.backward_coverage_m, 5.0)
        self.assertAlmostEqual(path.forward_coverage_m, 120.0)

    def test_reversed_vertex_order_is_explicitly_normalized(self) -> None:
        points = np.asarray([[120.0, 0.0], [0.0, 0.0], [-5.0, 0.0]])
        path = ego_relative_path_from_points(points, source="reference")

        self.assertTrue(path.reversed_to_positive_x)
        self.assertGreater(np.cos(path.origin_heading_rad), 0.0)
        self.assertAlmostEqual(path.forward_coverage_m, 120.0)

    def test_origin_projection_ambiguity_fails_closed(self) -> None:
        points = np.asarray(
            [
                [-10.0, 0.0],
                [10.0, 0.0],
                [20.0, 10.0],
                [-20.0, 10.0],
                [-10.0, 0.0005],
                [10.0, 0.0005],
            ]
        )
        with self.assertRaisesRegex(
            GeometryValidationError,
            "equally close",
        ):
            ego_relative_path_from_points(points, source="ambiguous")


class DiagnosticDisagreementTests(unittest.TestCase):
    def test_reference_normal_defines_lateral_sign(self) -> None:
        x = np.linspace(-5.0, 120.0, 126)
        reference = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))),
            source="reference",
        )
        estimate = ego_relative_path_from_points(
            np.column_stack((x, np.full_like(x, 0.3))),
            source="estimate",
        )
        disagreement = compare_ego_relative_paths(reference=reference, estimate=estimate)

        np.testing.assert_allclose(disagreement.lateral_m, 0.3, atol=1e-12)
        np.testing.assert_allclose(disagreement.along_track_m, 0.0, atol=1e-12)
        self.assertEqual(disagreement.lateral_m.shape, (21,))

    def test_no_extrapolation_for_short_forward_path(self) -> None:
        path = ego_relative_path_from_points(
            [[-5.0, 0.0], [50.0, 0.0]],
            source="short",
        )
        with self.assertRaisesRegex(GeometryValidationError, "does not cover"):
            sample_ego_relative_path(path)

    def test_alignment_metrics_are_raw_not_corrected(self) -> None:
        x = np.linspace(-5.0, 120.0, 126)
        reference = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))),
            source="reference",
        )
        estimate = ego_relative_path_from_points(
            np.column_stack((x, np.full_like(x, 0.4))),
            source="estimate",
        )
        metrics = origin_alignment_metrics(estimate, reference)

        self.assertAlmostEqual(metrics["footpoint_separation_m"], 0.4)
        self.assertAlmostEqual(metrics["footpoint_dy_m"], 0.4)


class PairSelectionTests(unittest.TestCase):
    def test_unbounded_pairing_exposes_signed_delta(self) -> None:
        pairs = nearest_monotone_pairs_unbounded(
            [100_000_000, 200_000_000, 300_000_000],
            [90_000_000, 210_000_000, 310_000_000],
        )
        self.assertEqual(
            pairs,
            (
                (0, 0, 10_000_000),
                (1, 1, -10_000_000),
                (2, 2, -10_000_000),
            ),
        )

    def test_even_selection_includes_both_ends(self) -> None:
        indices = evenly_spaced_indices(101, 5)
        self.assertEqual(indices, (0, 25, 50, 75, 100))


class MapPathSelectionTests(unittest.TestCase):
    def _segment(self, segment_id: int, is_ego: bool) -> RoadSegment:
        return RoadSegment(
            segment_id=segment_id,
            x=[-5.0, 120.0],
            y=[0.0, 0.0],
            arc_length=[0.0, 125.0],
            is_ego=is_ego,
            geometry_source="drive_path",
        )

    def test_exactly_one_metadata_confirmed_map_path_is_required(self) -> None:
        frame = RoadFrame(
            topic="/adp/road_lane_map_based",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
            sequence=0,
            source_time_ns=1,
            segments=(self._segment(1, True), self._segment(2, False)),
        )
        self.assertEqual(select_unique_ego_drive_path(frame).segment_id, 1)

        ambiguous = RoadFrame(
            topic=frame.topic,
            schema_name=frame.schema_name,
            log_time_ns=1,
            publish_time_ns=1,
            sequence=0,
            source_time_ns=1,
            segments=(self._segment(1, True), self._segment(2, True)),
        )
        with self.assertRaisesRegex(GeometryValidationError, "exactly one"):
            select_unique_ego_drive_path(ambiguous)


if __name__ == "__main__":
    unittest.main()
