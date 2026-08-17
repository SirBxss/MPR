import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.gaussian_baseline import main
from lane_residuals.domain.residual_dataset import CANONICAL_MODEL_STATIONS_M


class GaussianBaselineWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_alignment_batch(root: Path, *, version: str = "0.5.0") -> None:
        purpose = "ten_mcap_projection_based_reference_alignment_validation"
        summary = {
            "version": version,
            "purpose": purpose,
            "status": "complete",
            "blockers": [],
            "canonical_horizons_m": [60, 100],
            "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "h100_is_subset_of_h60": True,
            "h100_aligned_complete_pair_count": 4,
            "drive_grouping_source": "exact_private_basename_map",
            "drive_count": 2,
            "resolved_file_count": 2,
            "successful_recording_count": 2,
            "failed_recording_count": 0,
            "spatial_reference_alignment_applied": True,
            "explicit_ego_pose_motion_compensation_applied": False,
            "source_delta_used_numerically_for_alignment": False,
        }
        recordings = [
            {
                "recording_id": "recording_001",
                "drive_id": "drive_001",
                "mcap_filename_private": "first.mcap",
                "status": "succeeded",
            },
            {
                "recording_id": "recording_002",
                "drive_id": "drive_002",
                "mcap_filename_private": "second.mcap",
                "status": "succeeded",
            },
        ]
        manifest = {
            "version": version,
            "purpose": purpose,
            "status": "complete",
            "blockers": [],
            "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "drive_grouping_source": "exact_private_basename_map",
            "expected_file_count": 2,
            "resolved_file_count": 2,
            "successful_recording_count": 2,
            "recordings": recordings,
        }
        (root / "alignment_batch_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (root / "batch_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        pair_fields = (
            "recording_id",
            "drive_id",
            "pair_index",
            "estimate_message_index",
            "map_message_index",
            "estimate_source_time_ns_private",
            "map_source_time_ns_private",
            "source_delta_ms",
            "pair_state",
            "failure_code",
            "h60_aligned_eligible",
            "h100_aligned_eligible",
        )
        station_fields = (
            "recording_id",
            "drive_id",
            "pair_index",
            "station_m",
            "aligned_lateral_m",
            "h100_aligned_eligible",
        )
        with (root / "alignment_pair_audit.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=pair_fields)
            writer.writeheader()
            for recording_number, drive_number in ((1, 1), (2, 2)):
                for pair_index in (0, 1):
                    writer.writerow(
                        {
                            "recording_id": f"recording_{recording_number:03d}",
                            "drive_id": f"drive_{drive_number:03d}",
                            "pair_index": pair_index,
                            "estimate_message_index": pair_index,
                            "map_message_index": pair_index,
                            "estimate_source_time_ns_private": 900 + pair_index,
                            "map_source_time_ns_private": 100_900 + pair_index,
                            "source_delta_ms": -0.1,
                            "pair_state": "aligned_h100_ready",
                            "failure_code": "",
                            "h60_aligned_eligible": True,
                            "h100_aligned_eligible": True,
                        }
                    )
        with (root / "alignment_station_comparison.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=station_fields)
            writer.writeheader()
            for recording_number, drive_number in ((1, 1), (2, 2)):
                for pair_index in (0, 1):
                    for station in CANONICAL_MODEL_STATIONS_M:
                        writer.writerow(
                            {
                                "recording_id": f"recording_{recording_number:03d}",
                                "drive_id": f"drive_{drive_number:03d}",
                                "pair_index": pair_index,
                                "station_m": station,
                                "aligned_lateral_m": (
                                    0.01 * station
                                    + 0.1 * recording_number
                                    + 0.02 * pair_index
                                ),
                                "h100_aligned_eligible": True,
                            }
                        )

    def test_command_exports_vectors_and_drive_held_out_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alignment = root / "alignment"
            alignment.mkdir()
            self._write_alignment_batch(alignment)
            output = root / "model"

            status = main(
                [
                    str(alignment),
                    "--output-directory",
                    str(output),
                    "--regularization-m2",
                    "0.000001",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "gaussian_diagnostics.png",
                    "gaussian_evaluation.csv",
                    "gaussian_model.json",
                    "gaussian_station_evaluation.csv",
                    "gaussian_summary.json",
                    "residual_dataset_summary.json",
                    "residual_vectors.csv",
                },
            )
            dataset_summary = json.loads(
                (output / "residual_dataset_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(dataset_summary["vector_count"], 4)
            self.assertTrue(dataset_summary["constant_pair_count_at_every_station"])
            self.assertFalse(dataset_summary["available_case_rows_used"])
            gaussian_summary = json.loads(
                (output / "gaussian_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(gaussian_summary["evaluation_fold_count"], 2)
            self.assertEqual(
                gaussian_summary["cross_validated_test_vector_count"], 4
            )
            with (output / "gaussian_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[-1]["scope"], "overall_cross_validated")

    def test_motion_alignment_output_is_not_silently_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alignment = root / "alignment"
            alignment.mkdir()
            self._write_alignment_batch(alignment, version="0.5.1")
            output = root / "model"

            status = main([str(alignment), "--output-directory", str(output)])

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
