import argparse
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.reference_audit_cli import RecordingAudit, _write_outputs


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
