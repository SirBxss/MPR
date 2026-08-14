import math
import unittest
from types import SimpleNamespace

import numpy as np

from lane_residuals import (
    THESIS_TARGET_QUESTION,
    CandidateGeometry,
    CenterlineWorldSample,
    LateralLaneSample,
    PoseSample,
    TimedMessage,
    build_hindsight_candidate,
    candidate_from_polyline,
    compare_reference_candidates,
    flatten_scalar_fields,
    reconstruct_centerline_samples,
    reference_decision,
    sample_candidate,
    summarize_field_catalog,
)
from lane_residuals.geometry_validation import GeometryValidationError


class FieldCatalogTests(unittest.TestCase):
    def test_nested_fields_and_repeated_values_are_catalogued(self) -> None:
        decoded = SimpleNamespace(
            distance_to_centerline=-0.25,
            pose=SimpleNamespace(x=1.0, y=2.0),
            values=[1.0, 2.0],
        )
        flattened = flatten_scalar_fields(decoded)
        self.assertEqual(flattened["distance_to_centerline"], (-0.25,))
        self.assertEqual(flattened["pose.x"], (1.0,))
        self.assertEqual(flattened["values[]"], (1.0, 2.0))

        message = TimedMessage(
            recording_id="recording_001",
            session_id="session_001",
            topic="/candidate",
            schema_name="Candidate",
            message_encoding="protobuf",
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
            source_time_ns=1,
            decoded=decoded,
        )
        catalog = summarize_field_catalog([message])
        row = next(item for item in catalog if item["field_path"] == "distance_to_centerline")
        self.assertEqual(row["minimum"], -0.25)
        self.assertEqual(row["maximum"], -0.25)


class ReconstructionTests(unittest.TestCase):
    def test_negative_right_offset_moves_reconstructed_center_left(self) -> None:
        poses = [
            PoseSample("recording_001", "session_001", 0, 0, 0.0, 0.0, 0.0)
        ]
        lanes = [
            LateralLaneSample(
                "recording_001", "session_001", 0, 0, -0.5
            )
        ]
        reconstructed = reconstruct_centerline_samples(
            poses,
            lanes,
            maximum_delta_ms=0.0,
            positive_offset_is_lane_left=True,
        )
        self.assertAlmostEqual(reconstructed[0].x_m, 0.0)
        self.assertAlmostEqual(reconstructed[0].y_m, 0.5)

    def test_boundary_offset_is_auxiliary_and_uses_declared_equation(self) -> None:
        sample = LateralLaneSample(
            "recording_001",
            "session_001",
            0,
            0,
            -0.2,
            distance_to_left_boundary_m=2.0,
            distance_to_right_boundary_m=1.6,
        )
        self.assertAlmostEqual(sample.boundary_derived_offset_m, -0.2)

    def test_hindsight_path_is_transformed_to_anchor_ego_frame(self) -> None:
        samples = [
            CenterlineWorldSample(
                "recording_001",
                "session_001",
                index * 100_000_000,
                10.0,
                float(index),
                math.pi / 2.0,
                False,
                False,
                "pose_plus_offset",
            )
            for index in range(0, 121)
        ]
        anchor = PoseSample(
            "recording_001", "session_001", 0, 0, 10.0, 0.0, math.pi / 2.0
        )
        candidate = build_hindsight_candidate(
            samples,
            anchor_pose=anchor,
            maximum_inter_sample_gap_s=0.2,
            minimum_future_distance_m=100.0,
        )
        self.assertGreaterEqual(candidate.s_m[-1], 100.0)
        self.assertAlmostEqual(candidate.x_m[50], 50.0, places=8)
        self.assertAlmostEqual(candidate.y_m[50], 0.0, places=8)

    def test_lane_change_blocks_insufficient_future_window(self) -> None:
        samples = [
            CenterlineWorldSample(
                "recording_001",
                "session_001",
                index * 100_000_000,
                float(index),
                0.0,
                0.0,
                index == 20,
                False,
                "pose_plus_offset",
            )
            for index in range(0, 121)
        ]
        anchor = PoseSample("recording_001", "session_001", 0, 0, 0.0, 0.0, 0.0)
        with self.assertRaisesRegex(GeometryValidationError, "required distance"):
            build_hindsight_candidate(
                samples,
                anchor_pose=anchor,
                maximum_inter_sample_gap_s=0.2,
                minimum_future_distance_m=100.0,
            )


class CandidateComparisonTests(unittest.TestCase):
    def test_identical_candidates_have_zero_disagreement(self) -> None:
        points = np.column_stack((np.arange(0.0, 101.0), np.zeros(101)))
        first = candidate_from_polyline(
            source="map", points=points, provenance="direct"
        )
        second = candidate_from_polyline(
            source="pose", points=points, provenance="reconstructed"
        )
        metrics = compare_reference_candidates(first, second)
        self.assertAlmostEqual(metrics["lateral_rms_m"], 0.0)
        self.assertAlmostEqual(metrics["heading_rms_rad"], 0.0)

    def test_candidate_sampling_never_extrapolates(self) -> None:
        candidate = CandidateGeometry(
            source="short",
            s_m=np.asarray([0.0, 50.0]),
            x_m=np.asarray([0.0, 50.0]),
            y_m=np.asarray([0.0, 0.0]),
            heading_rad=np.asarray([0.0, 0.0]),
            curvature_per_m=np.asarray([0.0, 0.0]),
            provenance="test",
        )
        with self.assertRaisesRegex(GeometryValidationError, "cover"):
            sample_candidate(candidate)


class ScientificGateTests(unittest.TestCase):
    def test_gate_never_promotes_driven_or_fused_path(self) -> None:
        decision = reference_decision(
            complete_corpus=True,
            estimator_semantics_valid=True,
            direct_map_candidate_frames=100,
            reconstructed_candidate_frames=100,
            sessions_with_both_candidates=2,
            candidate_lateral_median_abs_m=0.05,
            maximum_allowed_candidate_median_abs_m=0.10,
            pose_frame_confirmed=True,
            centerline_sign_confirmed=True,
            pose_reference_point_confirmed=True,
            candidate_frame_confirmed=True,
        )
        self.assertEqual(decision["status"], "pseudo_reference_supported")
        self.assertFalse(decision["driven_trajectory_is_ground_truth"])
        self.assertFalse(decision["ego_lane_path_is_ground_truth"])
        self.assertFalse(decision["final_residual_export_allowed"])
        self.assertEqual(decision["thesis_target_question"], THESIS_TARGET_QUESTION)

    def test_missing_predeclared_threshold_blocks_promotion(self) -> None:
        decision = reference_decision(
            complete_corpus=True,
            estimator_semantics_valid=True,
            direct_map_candidate_frames=100,
            reconstructed_candidate_frames=100,
            sessions_with_both_candidates=2,
            candidate_lateral_median_abs_m=0.05,
            maximum_allowed_candidate_median_abs_m=None,
            pose_frame_confirmed=True,
            centerline_sign_confirmed=True,
            pose_reference_point_confirmed=True,
            candidate_frame_confirmed=True,
        )
        self.assertEqual(decision["status"], "reference_unresolved")
        self.assertIn("candidate_agreement_threshold_not_predeclared", decision["blockers"])


if __name__ == "__main__":
    unittest.main()
