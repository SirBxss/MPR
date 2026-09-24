from __future__ import annotations

import unittest
import numpy as np

from lane_residuals.domain.exploratory_residuals import aligned_residual, checked_speed, sequence_layout, build_archive
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.domain.motion import OdometrySample, Pose2D
from lane_residuals.domain.pairing import ego_relative_path_from_points

T = 1_000_000_000


def pose(time, x, log=T, publish=T):
    return OdometrySample(time, log, publish, Pose2D(x, 0., 0.))


def row(index, time, *, recording="recording_01", pair=None, conditions=True, residual=True):
    return {"recording_id": recording, "candidate_index": index, "pair_index": index if pair is None else pair,
        "estimate_message_index": index, "reference_message_index": index,
        "estimate_source_time_ns_private": time, "reference_source_time_ns_private": time,
        "residuals_m": [0.25] * 21 if residual else None, "conditions": [10., 0., 0., .5, .5, .5] if conditions else None}


class ExploratoryDomainTests(unittest.TestCase):
    def test_origin_projection_and_positive_left_sign_on_rotated_paths(self):
        angle = .73
        rotate = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        for offset in (.25, -.4):
            estimate = ego_relative_path_from_points(np.array([[5., offset], [65., offset], [120., offset]]) @ rotate.T, source="estimate")
            reference = ego_relative_path_from_points(np.array([[-20., 0.], [0., 0.], [140., 0.]]) @ rotate.T, source="reference")
            residuals, distance, station = aligned_residual(estimate, reference)
            np.testing.assert_allclose(residuals, offset, atol=1e-12)
            self.assertAlmostEqual(distance, abs(offset))
            self.assertAlmostEqual(station, 5.)
            self.assertEqual(len(residuals), 21)

    def test_short_reference_and_excessive_anchor_are_not_extrapolated_or_repaired(self):
        estimate = ego_relative_path_from_points([[-1., 0.], [110., 0.]], source="estimate")
        for points in ([[-1., 0.], [99., 0.]], [[-1., 1.0001], [110., 1.0001]]):
            reference = ego_relative_path_from_points(points, source="reference")
            with self.assertRaises(GeometryValidationError):
                aligned_residual(estimate, reference)

    def test_speed_definition_kept_with_causal_interpolation_of_past_endpoint(self):
        samples = [pose(T - 60_000_000, -.1), pose(T - 40_000_000, .1), pose(T, .5)]
        speed, evidence, failures = checked_speed(samples, T, T)
        self.assertAlmostEqual(speed, 10.)
        self.assertEqual(failures, ())
        self.assertEqual(evidence["previous_upper_timestamp_ns_private"], T - 40_000_000)
        self.assertEqual(evidence["current_upper_timestamp_ns_private"], T)

    def test_future_source_and_late_log_are_rejected_independently_without_speed_imputation(self):
        cases = [([pose(T - 50_000_000, 0.), pose(T - 10_000_000, .4), pose(T + 10_000_000, .6)], "speed_uses_future_source_sample"),
                 ([pose(T - 50_000_000, 0.), pose(T, .5, log=T + 1)], "speed_input_logged_after_estimate"),
                 ([pose(T - 50_000_000, 0.), pose(T, .5, log=0)], "speed_log_time_unavailable")]
        for samples, failure in cases:
            speed, evidence, failures = checked_speed(samples, T, T)
            self.assertIsNone(speed)
            self.assertEqual(failures, (failure,))
            self.assertIn("current_upper_timestamp_ns_private", evidence)

    def test_integer_sequence_gaps_do_not_bridge_files_exclusions_or_nonmonotonic_times(self):
        rows = [row(0,T), row(1,T+200_000_000), row(3,T+300_000_000),
                row(4,T+300_000_000), row(5,T+500_000_001), row(6,T+600_000_000,recording="recording_02")]
        offsets, sequences = sequence_layout(rows)
        self.assertEqual(offsets, [0,2,3,4,5,6])
        self.assertEqual(sum(s["transition_count"] for s in sequences), 1)
        self.assertEqual(sequences[0]["duration_ns"], 200_000_000)
        self.assertIn("estimate_index_gap", sequences[1]["start_reasons"])
        self.assertIn("timestamp_non_monotonic", sequences[2]["start_reasons"])
        self.assertIn("temporal_gap_exceeds_200ms", sequences[3]["start_reasons"])
        self.assertEqual(sequences[4]["start_reasons"], ["recording_boundary"])

    def test_missing_conditions_keep_geometric_vectors_but_break_conditioned_sequences(self):
        candidates = [row(0,T), row(1,T+100_000_000,conditions=False), row(2,T+200_000_000), row(3,T+300_000_000,residual=False)]
        arrays, support = build_archive(candidates)
        self.assertEqual(arrays["residuals_m"].shape, (3,21))
        self.assertEqual(arrays["conditions"].shape, (2,6))
        np.testing.assert_array_equal(arrays["conditioned_profile_indices"], [0,2])
        np.testing.assert_array_equal(arrays["geometry_sequence_offsets"], [0,3])
        np.testing.assert_array_equal(arrays["conditioned_sequence_offsets"], [0,1,2])
        self.assertEqual(support["conditioned_transition_count"], 0)

    def test_empty_shapes_and_uint64_precision_are_preserved_without_object_arrays(self):
        arrays, support = build_archive([])
        self.assertEqual(arrays["residuals_m"].shape, (0,21))
        self.assertEqual(arrays["conditions"].shape, (0,6))
        np.testing.assert_array_equal(arrays["conditioned_sequence_offsets"], [0])
        self.assertEqual(support["geometry_sequences"], [])
        value = 2**64-1
        arrays, _ = build_archive([row(0,value)])
        self.assertEqual(arrays["estimate_source_time_ns_decimal"][0], str(value))
        self.assertTrue(all(a.dtype.kind != "O" for a in arrays.values()))
