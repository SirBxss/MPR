import unittest

import numpy as np

from lane_residuals.domain.alignment import (
    compare_spatially_aligned_paths,
    project_point_to_path,
)
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.domain.motion import (
    OdometrySample,
    Pose2D,
    ego_frame_transform,
    interpolate_odometry_pose,
    latest_odometry_at_or_before_log_time,
    transform_path_to_target_ego_frame,
)
from lane_residuals.domain.pairing import (
    compare_ego_relative_paths,
    ego_relative_path_from_points,
)


class SpatialReferenceAlignmentTests(unittest.TestCase):
    def test_projected_reference_station_becomes_comparison_zero(self) -> None:
        reference_x = np.linspace(-5.0, 125.0, 1301)
        reference = ego_relative_path_from_points(
            np.column_stack((reference_x, np.zeros_like(reference_x))),
            source="reference",
        )
        estimate_x = np.linspace(0.6, 120.6, 1201)
        estimate = ego_relative_path_from_points(
            np.column_stack((estimate_x, np.full_like(estimate_x, 0.2))),
            source="estimate",
        )

        native = compare_ego_relative_paths(
            estimate,
            reference,
            stations_m=(0.0, 5.0, 10.0),
        )
        aligned = compare_spatially_aligned_paths(
            estimate,
            reference,
            stations_m=(0.0, 5.0, 10.0),
        )

        self.assertAlmostEqual(aligned.reference_anchor_station_m, 0.6, places=9)
        self.assertAlmostEqual(aligned.anchor_distance_m, 0.2, places=9)
        np.testing.assert_allclose(native.along_track_m, 0.6, atol=1e-9)
        np.testing.assert_allclose(
            aligned.disagreement.along_track_m,
            0.0,
            atol=1e-9,
        )
        np.testing.assert_allclose(
            aligned.disagreement.lateral_m,
            0.2,
            atol=1e-9,
        )

    def test_alignment_recovers_same_curved_geometry_after_longitudinal_shift(self) -> None:
        x = np.linspace(-5.0, 125.0, 1301)
        y = 0.002 * np.square(x)
        reference = ego_relative_path_from_points(
            np.column_stack((x, y)),
            source="reference",
        )
        shifted = x[x >= 0.6]
        estimate = ego_relative_path_from_points(
            np.column_stack((shifted, 0.002 * np.square(shifted))),
            source="estimate",
        )
        stations = tuple(float(value) for value in range(0, 101, 5))

        native = compare_ego_relative_paths(
            estimate,
            reference,
            stations_m=stations,
        )
        aligned = compare_spatially_aligned_paths(
            estimate,
            reference,
            stations_m=stations,
        )

        self.assertGreater(native.lateral_rms_m, 1e-4)
        self.assertLess(aligned.disagreement.lateral_rms_m, 1e-8)
        self.assertAlmostEqual(aligned.reference_anchor_station_m, 0.6, places=3)

    def test_alignment_never_extrapolates_reference(self) -> None:
        reference = ego_relative_path_from_points(
            [[-5.0, 0.0], [100.0, 0.0]],
            source="reference",
        )
        estimate = ego_relative_path_from_points(
            [[0.6, 0.0], [110.0, 0.0]],
            source="estimate",
        )

        with self.assertRaisesRegex(
            GeometryValidationError,
            "does not cover every requested station after alignment",
        ):
            compare_spatially_aligned_paths(
                estimate,
                reference,
                stations_m=(0.0, 100.0),
            )

    def test_separated_equally_close_reference_sections_fail_closed(self) -> None:
        reference = ego_relative_path_from_points(
            [
                [-10.0, 0.0],
                [10.0, 0.0],
                [20.0, 10.0],
                [-20.0, 10.0],
                [-10.0, 2.0],
                [10.0, 2.0],
            ],
            source="reference",
            orient_toward_positive_x=False,
        )

        with self.assertRaisesRegex(GeometryValidationError, "equally close"):
            project_point_to_path(
                [0.0, 1.0],
                reference,
                ambiguity_distance_tolerance_m=1e-9,
            )

    def test_invalid_station_grid_is_rejected(self) -> None:
        path = ego_relative_path_from_points(
            [[-5.0, 0.0], [120.0, 0.0]],
            source="path",
        )
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            compare_spatially_aligned_paths(
                path,
                path,
                stations_m=(0.0, 5.0, 5.0),
            )

    def test_odometry_transform_recovers_common_curved_geometry(self) -> None:
        x = np.linspace(-10.0, 130.0, 1401)
        reference = ego_relative_path_from_points(
            np.column_stack((x, 0.002 * np.square(x))),
            source="reference_at_source_time",
        )
        transform = ego_frame_transform(
            Pose2D(0.0, 0.0, 0.0),
            Pose2D(0.6, 0.0, 0.0),
        )
        transformed_reference = transform_path_to_target_ego_frame(
            reference,
            transform,
        )
        estimate = ego_relative_path_from_points(
            transformed_reference.points,
            source="estimate_at_target_time",
        )

        aligned = compare_spatially_aligned_paths(
            estimate,
            transformed_reference,
            stations_m=tuple(float(value) for value in range(0, 101, 5)),
        )

        self.assertAlmostEqual(
            aligned.reference_anchor_station_m,
            0.6,
            places=2,
        )
        self.assertLess(aligned.disagreement.lateral_rms_m, 1e-8)
        self.assertLess(aligned.disagreement.lateral_max_abs_m, 1e-8)

    def test_odometry_interpolation_uses_shortest_yaw_arc(self) -> None:
        samples = (
            OdometrySample(
                timestamp_ns=100,
                log_time_ns=100,
                publish_time_ns=100,
                pose=Pose2D(0.0, 0.0, np.deg2rad(179.0)),
            ),
            OdometrySample(
                timestamp_ns=200,
                log_time_ns=200,
                publish_time_ns=200,
                pose=Pose2D(2.0, 4.0, np.deg2rad(-179.0)),
            ),
        )

        result = interpolate_odometry_pose(
            samples,
            150,
            maximum_bracket_gap_ns=100,
        )

        self.assertAlmostEqual(result.pose.x_m, 1.0)
        self.assertAlmostEqual(result.pose.y_m, 2.0)
        self.assertAlmostEqual(abs(result.pose.yaw_rad), np.pi)
        self.assertAlmostEqual(result.fraction, 0.5)

    def test_latest_odometry_proxy_is_selected_by_mcap_log_order(self) -> None:
        samples = (
            OdometrySample(100, 1_000, 1_000, Pose2D(0.0, 0.0, 0.0)),
            OdometrySample(200, 2_000, 2_000, Pose2D(1.0, 0.0, 0.0)),
        )

        selected, lag_ns = latest_odometry_at_or_before_log_time(
            samples,
            2_025,
            maximum_log_lag_ns=50,
        )

        self.assertEqual(selected.timestamp_ns, 200)
        self.assertEqual(lag_ns, 25)
        with self.assertRaisesRegex(GeometryValidationError, "too old"):
            latest_odometry_at_or_before_log_time(
                samples,
                2_100,
                maximum_log_lag_ns=50,
            )


if __name__ == "__main__":
    unittest.main()
