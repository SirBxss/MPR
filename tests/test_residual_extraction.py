import unittest
from types import SimpleNamespace

import numpy as np

from lane_residuals import (
    ComparatorGeometry,
    DebugSplineParameters,
    GeometryValidationError,
    SplineCurve,
    SplineParameters,
    compare_production_to_debug,
    compute_provisional_gt_residual,
    debug_frame_from_message,
    generate_spline_curve,
    production_error_matches_debug,
)


def _production(*, starts=(0.0, 10.0, 20.0), changes=(0.02, -0.01), y_0=0.0):
    return SplineParameters(
        x_0=0.0,
        y_0=y_0,
        theta_0=0.0,
        curvature_0=0.0,
        segment_starts=np.asarray(starts),
        curvature_change=np.asarray(changes),
        index_0=0,
        index_0_presence_evidence="implicit_default",
        index_0_explicitly_present=False,
    )


def _debug(*, lengths=(10.0, 10.0), changes=(0.02, -0.01), y_0=0.0):
    return DebugSplineParameters(
        x_0=0.0,
        y_0=y_0,
        theta_0=0.0,
        curvature_0=0.0,
        segment_length=np.asarray(lengths),
        curvature_change=np.asarray(changes),
    )


def _debug_message(*, keep_error=7, two_keep_lanes=False):
    estimate = SimpleNamespace(
        x_0=0.0,
        y_0=0.0,
        theta_0=0.0,
        curvature_0=0.0,
        segment_length=[10.0, 10.0],
        curvature_change=[0.02, -0.01],
    )
    keep = SimpleNamespace(
        role=SimpleNamespace(value=1),
        drive_path_error=SimpleNamespace(error=keep_error),
        estimate=estimate,
    )
    adjacent = SimpleNamespace(
        role=SimpleNamespace(value=2),
        drive_path_error=SimpleNamespace(error=7),
        estimate=estimate,
    )
    vertices = [keep, adjacent]
    if two_keep_lanes:
        vertices.append(keep)
    return SimpleNamespace(time_stamp=123, vertices=vertices)


class DebugSemanticTests(unittest.TestCase):
    def test_mapping_wrappers_match_ros1_object_wrappers(self):
        object_frame = debug_frame_from_message(
            _debug_message(),
            message_index=0,
            log_time_ns=10,
            publish_time_ns=11,
        )
        mapping_message = {
            "time_stamp": 123,
            "vertices": [
                {
                    "role": {"value": 1},
                    "drive_path_error": {"error": 7},
                    "estimate": {
                        "x_0": 0.0,
                        "y_0": 0.0,
                        "theta_0": 0.0,
                        "curvature_0": 0.0,
                        "segment_length": [10.0, 10.0],
                        "curvature_change": [0.02, -0.01],
                    },
                }
            ],
        }
        mapping_frame = debug_frame_from_message(
            mapping_message,
            message_index=0,
            log_time_ns=10,
            publish_time_ns=11,
        )
        self.assertTrue(mapping_frame.ready)
        np.testing.assert_allclose(
            mapping_frame.parameters.segment_length,
            object_frame.parameters.segment_length,
        )

    def test_debug_error_numbers_are_compared_by_semantic_symbol(self):
        self.assertTrue(
            production_error_matches_debug(
                "DRIVE_PATH_ERROR_HIGH_CHI_2_FOR_MINIMAL_DISTANCE",
                4,
            )
        )
        self.assertTrue(
            production_error_matches_debug(
                "DRIVE_PATH_ERROR_DRIVEN_DISTANCE_TOO_FAR_SINCE_LAST_UPDATE",
                10,
            )
        )
        self.assertFalse(
            production_error_matches_debug("DRIVE_PATH_ERROR_NO_ERROR", 4)
        )

    def test_debug_parser_selects_exactly_one_no_error_keep_lane(self):
        frame = debug_frame_from_message(
            _debug_message(),
            message_index=0,
            log_time_ns=10,
            publish_time_ns=11,
            schema_fingerprint="debug-schema",
        )
        self.assertTrue(frame.ready)
        self.assertEqual(frame.keep_lane_count, 1)
        self.assertEqual(frame.keep_lane_error_value, 7)
        np.testing.assert_allclose(frame.parameters.segment_length, [10.0, 10.0])

    def test_debug_parser_rejects_error_and_ambiguous_keep_lane(self):
        error = debug_frame_from_message(
            _debug_message(keep_error=4),
            message_index=0,
            log_time_ns=10,
            publish_time_ns=11,
        )
        ambiguous = debug_frame_from_message(
            _debug_message(two_keep_lanes=True),
            message_index=1,
            log_time_ns=12,
            publish_time_ns=13,
        )
        self.assertEqual(error.state, "debug_estimator_reported_error")
        self.assertFalse(error.ready)
        self.assertEqual(ambiguous.state, "debug_keep_lane_ambiguous")
        self.assertFalse(ambiguous.ready)

    def test_production_differences_match_debug_segment_lengths(self):
        audit = compare_production_to_debug(_production(), _debug())
        self.assertTrue(audit.passed)
        self.assertTrue(audit.segment_lengths_match)
        self.assertTrue(audit.curvature_changes_match)
        self.assertEqual(audit.maximum_segment_length_abs_difference, 0.0)

    def test_marginal_shape_match_cannot_hide_value_mismatch(self):
        length_mismatch = compare_production_to_debug(
            _production(),
            _debug(lengths=(9.0, 11.0)),
        )
        change_mismatch = compare_production_to_debug(
            _production(),
            _debug(changes=(0.02, 0.01)),
        )
        self.assertEqual(length_mismatch.failure_code, "debug_segment_lengths_mismatch")
        self.assertEqual(change_mismatch.failure_code, "debug_curvature_changes_mismatch")

    def test_float32_rounding_is_tolerated_but_material_error_is_not(self):
        rounded = _debug(
            lengths=np.asarray([10.0, 10.0], dtype=np.float32),
            changes=np.asarray([0.02, -0.01], dtype=np.float32),
        )
        self.assertTrue(compare_production_to_debug(_production(), rounded).passed)
        shifted = _debug(y_0=0.02)
        self.assertEqual(
            compare_production_to_debug(_production(), shifted).failure_code,
            "debug_initial_parameters_mismatch",
        )


class ProvisionalGroundTruthResidualTests(unittest.TestCase):
    def _ground_truth(self):
        stations = np.arange(0.0, 100.1, 1.0)
        return ComparatorGeometry(
            s=stations,
            x=stations,
            y=np.zeros_like(stations),
            heading=np.zeros_like(stations),
            curvature=np.zeros_like(stations),
        )

    def test_positive_normal_displacement_has_positive_residual(self):
        estimate = generate_spline_curve(
            _production(starts=(0.0, 100.0), changes=(0.0,), y_0=0.25),
            meaning="curvature_delta",
            extra_stations=tuple(range(0, 101, 5)),
        )
        residual = compute_provisional_gt_residual(estimate, self._ground_truth())
        np.testing.assert_allclose(residual.lateral_m, 0.25, atol=1e-12)
        np.testing.assert_allclose(residual.along_track_m, 0.0, atol=1e-12)
        self.assertEqual(residual.lateral_m.shape, (21,))
        self.assertFalse(residual.lateral_m.flags.writeable)

    def test_negative_normal_displacement_has_negative_residual(self):
        estimate = generate_spline_curve(
            _production(starts=(0.0, 100.0), changes=(0.0,), y_0=-0.1),
            meaning="curvature_delta",
        )
        residual = compute_provisional_gt_residual(estimate, self._ground_truth())
        np.testing.assert_allclose(residual.lateral_m, -0.1, atol=1e-12)

    def test_curved_ground_truth_uses_its_local_normal(self):
        stations = np.linspace(0.0, 20.0, 41)
        curvature = 0.04
        heading = curvature * stations
        gt_x = np.sin(heading) / curvature
        gt_y = (1.0 - np.cos(heading)) / curvature
        normal = np.column_stack((-np.sin(heading), np.cos(heading)))
        estimate_points = np.column_stack((gt_x, gt_y)) + 0.3 * normal
        estimate = SplineCurve(
            hypothesis="synthetic_offset",
            curvature_meaning="curvature_delta",
            anchor_policy="anchor_zero",
            s=stations,
            x=estimate_points[:, 0],
            y=estimate_points[:, 1],
            heading=heading,
            curvature=np.full_like(stations, curvature),
            curvature_rate=np.zeros_like(stations),
            maximum_quadrature_error_m=0.0,
            convergence_position_error_m=0.0,
            convergence_heading_error_rad=0.0,
            sampled_arc_length_deficit_m=0.0,
            invariant_status="synthetic",
        )
        ground_truth = ComparatorGeometry(
            s=stations,
            x=gt_x,
            y=gt_y,
            heading=heading,
            curvature=np.full_like(stations, curvature),
        )
        residual = compute_provisional_gt_residual(
            estimate,
            ground_truth,
            stations_m=(0.0, 5.0, 10.0, 15.0, 20.0),
        )
        np.testing.assert_allclose(residual.lateral_m, 0.3, atol=1e-12)
        np.testing.assert_allclose(residual.along_track_m, 0.0, atol=1e-12)

    def test_no_extrapolation_when_estimate_coverage_is_short(self):
        estimate = generate_spline_curve(
            _production(starts=(0.0, 50.0), changes=(0.0,)),
            meaning="curvature_delta",
        )
        with self.assertRaisesRegex(
            GeometryValidationError,
            "estimate domain does not cover",
        ):
            compute_provisional_gt_residual(estimate, self._ground_truth())

    def test_stations_must_be_strictly_increasing(self):
        estimate = generate_spline_curve(
            _production(starts=(0.0, 100.0), changes=(0.0,)),
            meaning="curvature_delta",
        )
        with self.assertRaisesRegex(GeometryValidationError, "strictly increasing"):
            compute_provisional_gt_residual(
                estimate,
                self._ground_truth(),
                stations_m=(0.0, 5.0, 5.0),
            )


if __name__ == "__main__":
    unittest.main()
