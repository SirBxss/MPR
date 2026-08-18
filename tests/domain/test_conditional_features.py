import unittest
from types import SimpleNamespace

import numpy as np

from lane_residuals.domain.conditional_features import (
    ConditionalFeatureError,
    LongitudinalSpeedSample,
    ODOMETRY_SPEED_INTERVAL_NS,
    coalesce_identical_odometry_timestamps,
    derive_unsigned_odometry_speed,
    interpolate_longitudinal_speed,
    selected_keep_lane_confidences,
    summarize_estimate_conditions,
)
from lane_residuals.domain.geometry_validation import SplineCurve
from lane_residuals.domain.motion import OdometrySample, Pose2D
from lane_residuals.domain.pairing import ego_relative_path_from_spline


class ConditionalFeatureTests(unittest.TestCase):
    @staticmethod
    def _odometry_sample(timestamp_ns: int, x_m: float, y_m: float = 0.0):
        return OdometrySample(
            timestamp_ns=timestamp_ns,
            log_time_ns=timestamp_ns,
            publish_time_ns=timestamp_ns,
            pose=Pose2D(x_m=x_m, y_m=y_m, yaw_rad=0.0),
        )

    def test_speed_interpolation_is_recording_local_and_gap_limited(self) -> None:
        samples = (
            LongitudinalSpeedSample(100_000_000, 10.0, 1, 1),
            LongitudinalSpeedSample(110_000_000, 12.0, 2, 2),
        )

        result = interpolate_longitudinal_speed(
            samples,
            105_000_000,
            maximum_bracket_gap_ns=20_000_000,
        )

        self.assertEqual(result.method, "linear")
        self.assertAlmostEqual(result.value_mps, 11.0)
        self.assertAlmostEqual(result.bracket_span_ms, 10.0)
        with self.assertRaisesRegex(
            ConditionalFeatureError,
            "declared gap",
        ):
            interpolate_longitudinal_speed(
                samples,
                105_000_000,
                maximum_bracket_gap_ns=5_000_000,
            )

    def test_odometry_speed_uses_fixed_50ms_endpoint_interpolation(self) -> None:
        samples = (
            self._odometry_sample(90_000_000, 0.9),
            self._odometry_sample(110_000_000, 1.1),
            self._odometry_sample(140_000_000, 1.4),
            self._odometry_sample(160_000_000, 1.6),
        )

        result = derive_unsigned_odometry_speed(
            samples,
            150_000_000,
            maximum_bracket_gap_ns=30_000_000,
        )

        self.assertEqual(result.interval_ns, ODOMETRY_SPEED_INTERVAL_NS)
        self.assertEqual(result.previous_pose.timestamp_ns, 100_000_000)
        self.assertEqual(result.current_pose.timestamp_ns, 150_000_000)
        self.assertAlmostEqual(result.displacement_m, 0.5)
        self.assertAlmostEqual(result.value_mps, 10.0)
        self.assertAlmostEqual(result.previous_pose.bracket_span_ms, 20.0)
        self.assertAlmostEqual(result.current_pose.bracket_span_ms, 20.0)

    def test_odometry_speed_is_unsigned_and_never_extrapolates(self) -> None:
        samples = (
            self._odometry_sample(100_000_000, 1.0),
            self._odometry_sample(150_000_000, 0.5),
        )

        reverse = derive_unsigned_odometry_speed(
            samples,
            150_000_000,
            maximum_bracket_gap_ns=50_000_000,
        )

        self.assertAlmostEqual(reverse.value_mps, 10.0)
        with self.assertRaisesRegex(ValueError, "outside odometry coverage"):
            derive_unsigned_odometry_speed(
                samples,
                160_000_000,
                maximum_bracket_gap_ns=50_000_000,
            )

    def test_pose_identical_duplicate_odometry_timestamps_are_coalesced(self) -> None:
        later = OdometrySample(
            timestamp_ns=100_000_000,
            log_time_ns=12,
            publish_time_ns=12,
            pose=Pose2D(1.0, 2.0, 0.1),
        )
        earlier = OdometrySample(
            timestamp_ns=100_000_000,
            log_time_ns=10,
            publish_time_ns=10,
            pose=Pose2D(1.0, 2.0, 0.1),
        )

        result = coalesce_identical_odometry_timestamps(
            (
                self._odometry_sample(110_000_000, 1.1),
                later,
                earlier,
                self._odometry_sample(90_000_000, 0.9),
            )
        )

        self.assertEqual(
            [sample.timestamp_ns for sample in result.samples],
            [90_000_000, 100_000_000, 110_000_000],
        )
        self.assertEqual(result.samples[1].log_time_ns, 10)
        self.assertEqual(result.input_sample_count, 4)
        self.assertEqual(result.distinct_timestamp_count, 3)
        self.assertEqual(result.duplicate_timestamp_group_count, 1)
        self.assertEqual(result.duplicate_message_count, 1)
        self.assertEqual(result.coalesced_duplicate_message_count, 1)
        self.assertEqual(result.conflicting_timestamp_group_count, 0)
        self.assertEqual(result.discarded_conflicting_message_count, 0)
        self.assertEqual(result.maximum_timestamp_multiplicity, 2)

    def test_conflicting_duplicate_odometry_timestamp_group_is_discarded(self) -> None:
        result = coalesce_identical_odometry_timestamps(
            (
                self._odometry_sample(90_000_000, 0.9),
                self._odometry_sample(100_000_000, 1.0),
                self._odometry_sample(100_000_000, 1.000001),
                self._odometry_sample(110_000_000, 1.1),
            )
        )

        self.assertEqual(
            [sample.timestamp_ns for sample in result.samples],
            [90_000_000, 110_000_000],
        )
        self.assertEqual(result.duplicate_timestamp_group_count, 1)
        self.assertEqual(result.duplicate_message_count, 1)
        self.assertEqual(result.coalesced_duplicate_message_count, 0)
        self.assertEqual(result.conflicting_timestamp_group_count, 1)
        self.assertEqual(result.discarded_conflicting_message_count, 2)

    def test_geometry_and_confidence_are_mapped_from_native_to_ego_stations(self) -> None:
        native_s = np.linspace(0.0, 120.0, 121)
        curve = SplineCurve(
            hypothesis="synthetic",
            curvature_meaning="curvature_rate",
            anchor_policy="anchor_zero",
            s=native_s,
            x=native_s - 10.0,
            y=np.zeros_like(native_s),
            heading=np.zeros_like(native_s),
            curvature=0.001 * native_s,
            curvature_rate=np.full_like(native_s, 0.001),
            maximum_quadrature_error_m=0.0,
            convergence_position_error_m=0.0,
            convergence_heading_error_rad=0.0,
            sampled_arc_length_deficit_m=0.0,
            invariant_status="passed",
        )
        path = ego_relative_path_from_spline(curve)
        confidences = tuple(0.10 + 0.01 * index for index in range(24))

        result = summarize_estimate_conditions(curve, path, confidences)

        self.assertAlmostEqual(result.estimated_mean_abs_curvature_per_m, 0.06)
        self.assertAlmostEqual(result.estimated_curvature_delta_per_m, 0.10)
        self.assertAlmostEqual(
            result.confidence_near_mean,
            np.mean(confidences[2:8]),
        )
        self.assertAlmostEqual(
            result.confidence_middle_mean,
            np.mean(confidences[8:15]),
        )
        self.assertAlmostEqual(
            result.confidence_far_mean,
            np.mean(confidences[15:22]),
        )

    def test_confidence_never_pads_beyond_native_coverage(self) -> None:
        native_s = np.linspace(0.0, 120.0, 121)
        curve = SplineCurve(
            hypothesis="synthetic",
            curvature_meaning="curvature_rate",
            anchor_policy="anchor_zero",
            s=native_s,
            x=native_s - 10.0,
            y=np.zeros_like(native_s),
            heading=np.zeros_like(native_s),
            curvature=np.zeros_like(native_s),
            curvature_rate=np.zeros_like(native_s),
            maximum_quadrature_error_m=0.0,
            convergence_position_error_m=0.0,
            convergence_heading_error_rad=0.0,
            sampled_arc_length_deficit_m=0.0,
            invariant_status="passed",
        )
        path = ego_relative_path_from_spline(curve)

        with self.assertRaisesRegex(
            ConditionalFeatureError,
            "do not cover",
        ):
            summarize_estimate_conditions(curve, path, (0.5,) * 10)

    def test_unique_keep_lane_confidence_is_selected_by_enum_symbol(self) -> None:
        enum = SimpleNamespace(
            values_by_number={
                1: SimpleNamespace(name="LANE_ROLE_KEEP_LANE"),
                2: SimpleNamespace(name="LANE_ROLE_CHANGE_LANE"),
            }
        )
        role_field = SimpleNamespace(enum_type=enum)
        descriptor = SimpleNamespace(fields_by_name={"role": role_field})
        keep = SimpleNamespace(
            DESCRIPTOR=descriptor,
            role=1,
            drive_path_confidences=[0.2, 0.4],
        )
        change = SimpleNamespace(
            DESCRIPTOR=descriptor,
            role=2,
            drive_path_confidences=[0.9],
        )

        result = selected_keep_lane_confidences(
            SimpleNamespace(drive_paths=[change, keep])
        )

        self.assertEqual(result, (0.2, 0.4))


if __name__ == "__main__":
    unittest.main()
