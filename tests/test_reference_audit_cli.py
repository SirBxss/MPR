import argparse
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.geometry_validation import EstimatedFrameAudit, SplineParameters
from lane_residuals.reference_audit_cli import (
    RecordingAudit,
    _evaluate_candidates,
    _evaluate_estimator_semantics,
    _write_outputs,
)
from lane_residuals.residual_extraction import DebugFrameAudit, DebugSplineParameters


def _production_parameters() -> SplineParameters:
    return SplineParameters(
        x_0=0.0,
        y_0=0.0,
        theta_0=0.0,
        curvature_0=0.0,
        segment_starts=np.asarray([0.0, 100.0]),
        curvature_change=np.asarray([0.0]),
        index_0=0,
        index_0_presence_evidence="explicit",
        index_0_explicitly_present=True,
    )


def _debug_parameters() -> DebugSplineParameters:
    return DebugSplineParameters(
        x_0=0.0,
        y_0=0.0,
        theta_0=0.0,
        curvature_0=0.0,
        segment_length=np.asarray([100.0]),
        curvature_change=np.asarray([0.0]),
    )


class EstimatorSemanticEvaluationTests(unittest.TestCase):
    def test_uses_current_estimated_frame_fields_for_ready_and_error_frames(self) -> None:
        result = RecordingAudit(
            recording_id="recording_001",
            session_id="session_001",
            source_path=Path("private.mcap"),
        )
        result.estimates.extend(
            [
                EstimatedFrameAudit(
                    message_index=10,
                    log_time_ns=1_000,
                    publish_time_ns=1_000,
                    source_time_ns=1_000,
                    schema_fingerprint="production",
                    topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
                    total_path_count=1,
                    keep_lane_count=1,
                    keep_lane_error="DRIVE_PATH_ERROR_NO_ERROR",
                    estimator_state="available_no_error",
                    conversion_state="candidate_ready",
                    interval_count=1,
                    candidate=_production_parameters(),
                ),
                EstimatedFrameAudit(
                    message_index=11,
                    log_time_ns=2_000,
                    publish_time_ns=2_000,
                    source_time_ns=2_000,
                    schema_fingerprint="production",
                    topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
                    total_path_count=1,
                    keep_lane_count=1,
                    keep_lane_error="DRIVE_PATH_ERROR_OPTIMIZER_ERROR",
                    estimator_state="estimator_reported_error",
                    conversion_state="not_attempted_estimator_unavailable",
                    interval_count=1,
                ),
            ]
        )
        result.debug_frames.extend(
            [
                DebugFrameAudit(
                    message_index=20,
                    log_time_ns=1_000,
                    publish_time_ns=1_000,
                    source_time_ns=1_000,
                    state="debug_ready",
                    keep_lane_count=1,
                    keep_lane_error_value=7,
                    schema_fingerprint="debug",
                    parameters=_debug_parameters(),
                ),
                DebugFrameAudit(
                    message_index=21,
                    log_time_ns=2_000,
                    publish_time_ns=2_000,
                    source_time_ns=2_000,
                    state="debug_estimator_reported_error",
                    keep_lane_count=1,
                    keep_lane_error_value=6,
                    schema_fingerprint="debug",
                ),
            ]
        )

        curves, semantic_valid = _evaluate_estimator_semantics(
            result,
            maximum_delta_ms=0.0,
            max_step_m=1.0,
            stations_m=(0.0, 5.0, 100.0),
        )

        self.assertTrue(semantic_valid)
        self.assertEqual(set(curves), {10})
        self.assertEqual(curves[10].curvature_meaning, "curvature_rate")
        self.assertEqual(len(result.semantic_rows), 2)
        self.assertTrue(all(row["status_correspondence"] for row in result.semantic_rows))
        self.assertEqual(result.semantic_rows[0]["semantic_status"], "semantic_match")
        self.assertIsNone(result.semantic_rows[1]["semantic_status"])

    def test_candidate_audit_preserves_estimator_and_conversion_states(self) -> None:
        result = RecordingAudit(
            recording_id="recording_001",
            session_id="session_001",
            source_path=Path("private.mcap"),
        )
        result.estimates.append(
            EstimatedFrameAudit(
                message_index=10,
                log_time_ns=1_000,
                publish_time_ns=1_000,
                source_time_ns=1_000,
                schema_fingerprint="production",
                topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
                total_path_count=1,
                keep_lane_count=1,
                keep_lane_error="DRIVE_PATH_ERROR_NO_ERROR",
                estimator_state="available_no_error",
                conversion_state="candidate_ready",
                interval_count=1,
                candidate=_production_parameters(),
            )
        )
        arguments = argparse.Namespace(
            maximum_position_step_m=10.0,
            maximum_yaw_step_rad=0.5,
            pose_lsa_max_delta_ms=50.0,
        )

        counts = _evaluate_candidates(
            result,
            config={"conventions": {"centerline_positive_is_lane_left": False}},
            arguments=arguments,
            estimate_curves={},
            session_poses=(),
            session_lane_samples=(),
            session_direct_map=(),
            session_fused_comparator=(),
            primary_estimate_indices={10},
        )

        self.assertEqual(counts, (0, 0, False))
        self.assertEqual(result.frame_rows[0]["estimate_state"], "available_no_error")
        self.assertEqual(
            result.frame_rows[0]["estimate_conversion_state"], "candidate_ready"
        )
        self.assertEqual(
            result.frame_rows[0]["failure_code"], "estimate_not_semantically_ready"
        )


class ReferenceAuditOutputTests(unittest.TestCase):
    def test_unresolved_audit_writes_diagnostics_but_no_training_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            arguments = argparse.Namespace(
                output_directory=output,
                field_catalog_samples_per_topic=5,
                maximum_position_step_m=10.0,
                maximum_yaw_step_rad=0.5,
                expected_file_count=2,
                max_candidate_median_abs_m=None,
            )
            config = {
                "topics": {
                    "estimate": ("/estimate",),
                    "estimate_debug": ("/debug",),
                    "map_lane": ("/map",),
                    "map_pose": ("/pose",),
                    "lsa_centerline": ("/centerline",),
                    "fused_comparator": ("/fused",),
                },
                "fields": {},
                "conventions": {
                    "centerline_positive_is_lane_left": True,
                    "pose_is_stable_world_or_map_frame": False,
                    "pose_reference_point_confirmed": False,
                    "candidate_paths_share_estimate_frame": False,
                },
            }
            results = [
                RecordingAudit(
                    recording_id="recording_001",
                    session_id="session_001",
                    source_path=Path("private_1.mcap"),
                ),
                RecordingAudit(
                    recording_id="recording_002",
                    session_id="session_002",
                    source_path=Path("private_2.mcap"),
                ),
            ]
            summary = _write_outputs(
                results,
                config=config,
                arguments=arguments,
                semantic_by_recording={
                    "recording_001": False,
                    "recording_002": False,
                },
                direct_ready_total=0,
                reconstructed_ready_total=0,
                recordings_with_both=set(),
            )
            self.assertEqual(summary["decision"]["status"], "reference_unresolved")
            self.assertFalse(summary["thesis_scope_changed"])
            self.assertFalse(summary["generated_final_residual_dataset"])
            self.assertFalse(summary["fitted_statistical_model"])
            self.assertEqual(summary["version"], "0.4.4")
            self.assertEqual(
                summary["estimate_spline_reconstruction"],
                "curvature_rate",
            )
            self.assertFalse(summary["curvature_change_semantics_confirmed"])
            expected = {
                "reference_source_inventory.json",
                "decoded_field_catalog.json",
                "pose_source_audit.csv",
                "lsa_centerline_audit.csv",
                "debug_semantic_audit.csv",
                "duplicate_conflict_audit.csv",
                "reference_frame_eligibility.csv",
                "candidate_reference_metrics.csv",
                "reference_validation_summary.json",
            }
            self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))
            self.assertFalse(any(path.suffix == ".npz" for path in output.iterdir()))
            payload = json.loads(
                (output / "reference_validation_summary.json").read_text(encoding="utf-8")
            )
            self.assertFalse(payload["decision"]["driven_trajectory_is_ground_truth"])
            self.assertFalse(payload["decision"]["ego_lane_path_is_ground_truth"])


if __name__ == "__main__":
    unittest.main()
