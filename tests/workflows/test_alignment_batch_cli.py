import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lane_residuals.workflows.alignment_batch import (
    RECORDING_FIELDS,
    RecordingAlignmentData,
    run_alignment_batch,
)


class AlignmentBatchWorkflowTests(unittest.TestCase):
    @staticmethod
    def _recording(
        *,
        recording_id: str,
        drive_id: str,
        filename: str,
        source_delta_ms: float,
        rms_change: float,
    ) -> RecordingAlignmentData:
        pair = {
            "pair_index": 0,
            "estimate_message_index": 0,
            "map_message_index": 0,
            "estimate_source_time_ns_private": 100,
            "map_source_time_ns_private": 90,
            "source_delta_ms": source_delta_ms,
            "absolute_source_delta_ms": abs(source_delta_ms),
            "geometry_epoch_delta_ms": source_delta_ms,
            "edp_geometry_proxy_log_lag_ms": 1.0,
            "ego_motion_source_to_target_travel_m": 0.5,
            "pair_state": "aligned_h100_ready",
            "h60_aligned_eligible": True,
            "h100_aligned_eligible": True,
            "reference_anchor_station_m": 0.5,
            "anchor_distance_m": 0.08,
            "aligned_minus_native_h60_lateral_rms_m": rms_change,
            "aligned_minus_native_h100_lateral_rms_m": rms_change,
        }
        stations = tuple(
            {
                "pair_index": 0,
                "station_m": station,
                "native_lateral_m": 0.2,
                "aligned_lateral_m": 0.1,
                "h60_aligned_eligible": True,
                "h100_aligned_eligible": True,
            }
            for station in range(0, 101, 5)
        )
        return RecordingAlignmentData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=filename,
            status="succeeded",
            output_directory=f"recordings/{recording_id}",
            summary={
                "complete_stream_mutual_nearest_pair_count": 1,
                "h60_aligned_complete_pair_count": 1,
                "h100_aligned_complete_pair_count": 1,
                "median_absolute_source_delta_ms": abs(source_delta_ms),
                "median_absolute_geometry_epoch_delta_ms": abs(source_delta_ms),
                "median_edp_geometry_proxy_log_lag_ms": 1.0,
                "median_ego_motion_source_to_target_travel_m": 0.5,
                "median_reference_anchor_station_m": 0.5,
                "median_anchor_distance_m": 0.08,
                "median_aligned_minus_native_h60_pair_lateral_rms_m": 99.0,
                "median_aligned_minus_native_h100_pair_lateral_rms_m": 99.0,
            },
            pair_rows=(pair,),
            station_rows=stations,
        )

    def test_exact_manifest_batch_recomputes_pair_level_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.mcap"
            second = root / "second.mcap"
            first.touch()
            second.touch()
            mapping = root / "sessions.json"
            mapping.write_text(
                json.dumps(
                    {
                        "first.mcap": "physical-session-a",
                        "second.mcap": "physical-session-b",
                    }
                ),
                encoding="utf-8",
            )
            output = root / "alignment_batch"
            arguments = SimpleNamespace(
                inputs=(first, second),
                drive_map=mapping,
                expected_file_count=2,
                output_directory=output,
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                estimate_topic="/estimate",
                map_topic="/map",
                odometry_topic="/odometry",
                maximum_odometry_log_lag_ms=20.0,
                maximum_odometry_interpolation_gap_ms=20.0,
            )

            def fake_recording(**kwargs):
                index = int(kwargs["recording_id"].split("_")[-1])
                return self._recording(
                    recording_id=kwargs["recording_id"],
                    drive_id=kwargs["drive_id"],
                    filename=kwargs["mcap"].name,
                    source_delta_ms=20.0 if index == 1 else 30.0,
                    rms_change=0.1 if index == 1 else -0.1,
                )

            with patch(
                "lane_residuals.workflows.alignment_batch._run_one_recording",
                side_effect=fake_recording,
            ):
                summary, status = run_alignment_batch(arguments)

            self.assertEqual(status, 0)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["successful_recording_count"], 2)
            self.assertEqual(summary["drive_count"], 2)
            self.assertEqual(summary["h60_aligned_complete_pair_count"], 2)
            self.assertEqual(summary["h100_aligned_complete_pair_count"], 2)
            self.assertAlmostEqual(summary["median_absolute_source_delta_ms"], 25.0)
            self.assertAlmostEqual(
                summary["median_absolute_geometry_epoch_delta_ms"],
                25.0,
            )
            self.assertTrue(
                summary["explicit_ego_pose_motion_compensation_applied"]
            )
            self.assertAlmostEqual(
                summary[
                    "median_aligned_minus_native_h100_pair_lateral_rms_m"
                ],
                0.0,
            )
            self.assertTrue(summary["scope_metrics_recomputed_from_pair_rows"])
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "alignment_batch_comparison.png",
                    "alignment_batch_summary.json",
                    "alignment_pair_audit.csv",
                    "alignment_station_comparison.csv",
                    "batch_manifest.json",
                    "recording_alignment_summary.csv",
                },
            )
            with (output / "recording_alignment_summary.csv").open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
                self.assertEqual(tuple(rows[0]), RECORDING_FIELDS)
            self.assertEqual([row["recording_id"] for row in rows], [
                "recording_001",
                "recording_002",
            ])

    def test_drive_map_must_match_every_resolved_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcap = root / "only.mcap"
            mcap.touch()
            mapping = root / "sessions.json"
            mapping.write_text("{}", encoding="utf-8")
            arguments = SimpleNamespace(
                inputs=(mcap,),
                drive_map=mapping,
                expected_file_count=1,
                output_directory=root / "output",
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                estimate_topic="/estimate",
                map_topic="/map",
                odometry_topic="/odometry",
                maximum_odometry_log_lag_ms=20.0,
                maximum_odometry_interpolation_gap_ms=20.0,
            )
            with self.assertRaisesRegex(ValueError, "must match resolved basenames"):
                run_alignment_batch(arguments)

    def test_blank_optional_csv_metrics_do_not_break_aggregate_plot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcap = root / "only.mcap"
            mcap.touch()
            mapping = root / "sessions.json"
            mapping.write_text(
                json.dumps({"only.mcap": "physical-session-a"}),
                encoding="utf-8",
            )
            output = root / "alignment_batch"
            arguments = SimpleNamespace(
                inputs=(mcap,),
                drive_map=mapping,
                expected_file_count=1,
                output_directory=output,
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                estimate_topic="/estimate",
                map_topic="/map",
                odometry_topic="/odometry",
                maximum_odometry_log_lag_ms=20.0,
                maximum_odometry_interpolation_gap_ms=20.0,
            )
            base = self._recording(
                recording_id="recording_001",
                drive_id="physical-session-a",
                filename=mcap.name,
                source_delta_ms=20.0,
                rms_change=0.1,
            )
            pair = {
                **base.pair_rows[0],
                "aligned_minus_native_h100_lateral_rms_m": "",
            }
            stations = tuple(
                {**row, "native_lateral_m": ""} for row in base.station_rows
            )
            recording = RecordingAlignmentData(
                recording_id=base.recording_id,
                drive_id=base.drive_id,
                mcap_filename=base.mcap_filename,
                status=base.status,
                output_directory=base.output_directory,
                summary=base.summary,
                pair_rows=(pair,),
                station_rows=stations,
            )

            with patch(
                "lane_residuals.workflows.alignment_batch._run_one_recording",
                return_value=recording,
            ):
                summary, status = run_alignment_batch(arguments)

            self.assertEqual(status, 0)
            self.assertIsNone(
                summary[
                    "median_aligned_minus_native_h100_pair_lateral_rms_m"
                ]
            )
            self.assertTrue((output / "alignment_batch_comparison.png").is_file())


if __name__ == "__main__":
    unittest.main()
