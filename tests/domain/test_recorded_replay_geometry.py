import unittest

import numpy as np

from lane_residuals.domain.exploratory_residuals import aligned_residual
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.domain.motion import Pose2D
from lane_residuals.domain.pairing import ego_relative_path_from_points
from lane_residuals.domain.recorded_replay_geometry import check_recorded_replay_geometry


class RecordedReplayGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        x = np.arange(-10.0, 151.0)
        self.reference = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))), source="reference"
        )
        self.estimate = ego_relative_path_from_points(
            np.column_stack((x + 0.75, np.full_like(x, 0.25)))[10:],
            source="estimate",
        )
        profile, distance, station = aligned_residual(self.estimate, self.reference)
        self.archive = {
            "archived_residual_m": profile,
            "archived_anchor_station_m": station,
            "archived_anchor_distance_m": distance,
        }

    def test_keeps_residual_anchor_distinct_from_projected_vehicle(self) -> None:
        geometry = check_recorded_replay_geometry(
            self.estimate, self.reference, ego_pose_in_path_frame=Pose2D(4.0, 0.5, 0.2),
            **self.archive,
        )
        self.assertAlmostEqual(geometry.residual_anchor_station_m, 0.75)
        self.assertAlmostEqual(geometry.ego_reference_station_m, 4.0)
        self.assertAlmostEqual(geometry.initial_lateral_error_m, 0.5)
        self.assertAlmostEqual(geometry.initial_heading_error_rad, 0.2)
        np.testing.assert_allclose(
            geometry.residual_stations_from_ego_m, np.arange(0, 101, 5) - 3.25
        )
        np.testing.assert_allclose(geometry.reference_points_m[0], [0.75, 0.0])
        self.assertFalse(geometry.residual_stations_from_ego_m.flags.writeable)
        self.assertFalse(geometry.reference_points_m.flags.writeable)

    def test_preserves_forward_gap_when_residual_starts_ahead_of_ego(self) -> None:
        geometry = check_recorded_replay_geometry(
            self.estimate, self.reference, ego_pose_in_path_frame=Pose2D(0.0, 0.0, 0.0),
            **self.archive,
        )
        np.testing.assert_allclose(
            geometry.residual_stations_from_ego_m, np.arange(0, 101, 5) + 0.75
        )

    def test_uses_reference_tangent_for_signed_initial_state(self) -> None:
        x = np.arange(-30.0, 151.0)
        angle = 0.4
        tangent = np.array([np.cos(angle), np.sin(angle)])
        normal = np.array([-tangent[1], tangent[0]])
        points = x[:, None] * tangent
        reference = ego_relative_path_from_points(points, source="reference")
        estimate = ego_relative_path_from_points(points + 0.25 * normal, source="estimate")
        profile, distance, station = aligned_residual(estimate, reference)
        ego = 4 * tangent - 0.3 * normal
        geometry = check_recorded_replay_geometry(
            estimate,
            reference,
            ego_pose_in_path_frame=Pose2D(*ego, angle - 0.1 + 2 * np.pi),
            archived_residual_m=profile,
            archived_anchor_station_m=station,
            archived_anchor_distance_m=distance,
        )
        self.assertAlmostEqual(geometry.initial_lateral_error_m, -0.3)
        self.assertAlmostEqual(geometry.initial_heading_error_rad, -0.1)

    def test_preserves_archive_alignment(self) -> None:
        for key, wrong in (
            ("archived_anchor_station_m", 0.50),
            ("archived_anchor_distance_m", 0.50),
            ("archived_residual_m", [-0.25] * 21),
        ):
            with self.subTest(key=key):
                archive = {**self.archive, key: wrong}
                with self.assertRaises(GeometryValidationError) as cm:
                    check_recorded_replay_geometry(
                        self.estimate, self.reference,
                        ego_pose_in_path_frame=Pose2D(4.0, 0.0, 0.0), **archive,
                    )
                self.assertEqual(cm.exception.code, "replay_archive_alignment_mismatch")

    def test_rejects_profile_with_wrong_station_count(self) -> None:
        archive = {**self.archive, "archived_residual_m": [0.25] * 20}
        with self.assertRaises(GeometryValidationError) as cm:
            check_recorded_replay_geometry(
                self.estimate, self.reference,
                ego_pose_in_path_frame=Pose2D(4.0, 0.0, 0.0), **archive,
            )
        self.assertEqual(cm.exception.code, "replay_archived_residual_invalid")

    def test_rejects_ego_projection_clipped_to_reference_endpoint(self) -> None:
        with self.assertRaises(GeometryValidationError) as cm:
            check_recorded_replay_geometry(
                self.estimate, self.reference,
                ego_pose_in_path_frame=Pose2D(-20.0, 0.0, 0.0), **self.archive,
            )
        self.assertEqual(cm.exception.code, "replay_ego_projection_at_reference_endpoint")
