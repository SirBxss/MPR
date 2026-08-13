import unittest

import numpy as np

from lane_residuals import (
    GeometryValidationError,
    RoadFrame,
    RoadSegment,
    compare_ego_relative_paths,
    ego_relative_path_from_points,
    evenly_spaced_indices,
    mutual_nearest_timestamp_pairs,
    nearest_monotone_pairs_unbounded,
    origin_alignment_metrics,
    ordered_ego_lane_from_road_frame,
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
    def test_mutual_nearest_pairing_uses_complete_stream_positions(self) -> None:
        estimate_times = [26_000_000 + 80_000_000 * index for index in range(60)]
        map_times = [80_000_000 * index for index in range(60)]

        audit = mutual_nearest_timestamp_pairs(estimate_times, map_times)

        self.assertEqual(len(audit.pairs), 60)
        self.assertEqual(
            (audit.pairs[0].first_position, audit.pairs[0].second_position),
            (0, 0),
        )
        self.assertEqual(
            (audit.pairs[57].first_position, audit.pairs[57].second_position),
            (57, 57),
        )
        self.assertTrue(all(pair.delta_ns == 26_000_000 for pair in audit.pairs))

    def test_non_mutual_candidates_remain_unmatched(self) -> None:
        audit = mutual_nearest_timestamp_pairs([0, 100], [40])

        self.assertEqual(
            tuple((pair.first_position, pair.second_position) for pair in audit.pairs),
            ((0, 0),),
        )
        self.assertEqual(audit.unmatched_first_positions, (1,))
        self.assertEqual(audit.unmatched_second_positions, ())

    def test_explicit_gate_rejects_pair_without_consuming_messages(self) -> None:
        audit = mutual_nearest_timestamp_pairs(
            [0],
            [5_000_000_000],
            maximum_delta_ns=100_000_000,
        )

        self.assertEqual(audit.pairs, ())
        self.assertEqual(len(audit.rejected_by_gate), 1)
        self.assertEqual(audit.unmatched_first_positions, (0,))
        self.assertEqual(audit.unmatched_second_positions, (0,))

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

    @staticmethod
    def _topology_segment(
        *,
        segment_id: int,
        source_index: int,
        x_start: float,
        x_end: float,
        is_ego: bool,
        successors: tuple[int, ...] = (),
        predecessors: tuple[int, ...] = (),
    ) -> RoadSegment:
        return RoadSegment(
            segment_id=segment_id,
            x=[x_start, x_end],
            y=[0.0, 0.0],
            arc_length=[0.0, x_end - x_start],
            is_ego=is_ego,
            geometry_source="drive_path",
            source_index=source_index,
            successor_indices=successors,
            predecessor_indices=predecessors,
        )

    def test_ordered_lane_follows_unique_explicit_successor(self) -> None:
        first = self._topology_segment(
            segment_id=10,
            source_index=0,
            x_start=-5.0,
            x_end=50.0,
            is_ego=True,
            successors=(1,),
        )
        second = self._topology_segment(
            segment_id=20,
            source_index=1,
            x_start=50.0,
            x_end=125.0,
            is_ego=False,
            predecessors=(0,),
        )
        frame = RoadFrame(
            topic="/adp/road_lane_map_based",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
            sequence=0,
            source_time_ns=1,
            segments=(first, second),
        )

        lane = ordered_ego_lane_from_road_frame(frame, required_forward_m=100.0)

        self.assertEqual(lane.segment_indices, (0, 1))
        self.assertEqual(lane.segment_ids, (10, 20))
        self.assertEqual(lane.termination_reason, "required_forward_coverage_reached")
        self.assertTrue(lane.required_forward_coverage_reached)
        self.assertEqual(lane.reciprocal_predecessor_links, (True,))
        self.assertAlmostEqual(lane.path.forward_coverage_m, 125.0)

    def test_ordered_lane_never_guesses_at_successor_branch(self) -> None:
        first = self._topology_segment(
            segment_id=10,
            source_index=0,
            x_start=-5.0,
            x_end=50.0,
            is_ego=True,
            successors=(1, 2),
        )
        second = self._topology_segment(
            segment_id=20,
            source_index=1,
            x_start=50.0,
            x_end=125.0,
            is_ego=False,
            predecessors=(0,),
        )
        adjacent = RoadSegment(
            segment_id=30,
            x=[50.0, 125.0],
            y=[0.0, 4.0],
            arc_length=[0.0, 75.1],
            is_ego=False,
            geometry_source="drive_path",
            source_index=2,
            predecessor_indices=(0,),
        )
        frame = RoadFrame(
            topic="/adp/road_lane_map_based",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
            sequence=0,
            source_time_ns=1,
            segments=(first, second, adjacent),
        )

        lane = ordered_ego_lane_from_road_frame(frame, required_forward_m=100.0)

        self.assertEqual(lane.segment_indices, (0,))
        self.assertEqual(lane.termination_reason, "successor_branch_ambiguous")
        self.assertFalse(lane.required_forward_coverage_reached)

    def test_ordered_lane_stops_at_discontinuous_successor(self) -> None:
        first = self._topology_segment(
            segment_id=10,
            source_index=0,
            x_start=-5.0,
            x_end=50.0,
            is_ego=True,
            successors=(1,),
        )
        distant = self._topology_segment(
            segment_id=20,
            source_index=1,
            x_start=55.0,
            x_end=125.0,
            is_ego=False,
            predecessors=(0,),
        )
        frame = RoadFrame(
            topic="/adp/road_lane_map_based",
            schema_name="Adp.Perception.Road",
            log_time_ns=1,
            publish_time_ns=1,
            sequence=0,
            source_time_ns=1,
            segments=(first, distant),
        )

        lane = ordered_ego_lane_from_road_frame(
            frame,
            required_forward_m=100.0,
            max_junction_gap_m=1.0,
        )

        self.assertEqual(
            lane.termination_reason,
            "successor_junction_gap_exceeds_limit",
        )
        self.assertEqual(lane.segment_count, 1)


if __name__ == "__main__":
    unittest.main()
