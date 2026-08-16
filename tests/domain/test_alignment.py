import unittest

import numpy as np

from lane_residuals.domain.alignment import (
    compare_spatially_aligned_paths,
    project_point_to_path,
)
from lane_residuals.domain.geometry_validation import GeometryValidationError
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


if __name__ == "__main__":
    unittest.main()
