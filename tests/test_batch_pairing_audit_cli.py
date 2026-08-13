import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lane_residuals.batch_pairing_audit import RecordingAuditData
from lane_residuals.batch_pairing_audit_cli import (
    _load_drive_assignments,
    _run_one_recording,
    run_batch,
)


class BatchPairingAuditCliTests(unittest.TestCase):
    @staticmethod
    def _synthetic_success(
        recording_id: str,
        drive_id: str,
        filename: str,
        source_time_ns: int,
    ) -> RecordingAuditData:
        pair = {
            "pair_index": "0",
            "estimate_message_index": "0",
            "map_message_index": "0",
            "estimate_source_time_ns_private": str(source_time_ns),
            "diagnostic_primary_lateral_rms_m": "0.2",
            "diagnostic_lateral_rms_m": "0.2",
        }
        stations = tuple(
            {
                "pair_index": "0",
                "station_m": str(station),
                "diagnostic_lateral_m": "0.2",
            }
            for station in range(0, 101, 5)
        )
        chain = {
            "segment_count": "1",
            "termination_reason": "required_forward_coverage_reached",
            "actual_forward_coverage_m": "110",
            "junction_gaps_m": "",
            "junction_heading_deltas_rad": "",
            "reciprocal_predecessor_links": "",
        }
        return RecordingAuditData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=filename,
            status="succeeded",
            output_directory=f"recordings/{recording_id}",
            summary={
                "estimate_messages": 1,
                "map_messages": 1,
                "complete_stream_mutual_nearest_pair_count": 1,
                "unmatched_estimate_message_count": 0,
                "unmatched_map_message_count": 0,
            },
            pair_rows=(pair,),
            station_rows=stations,
            chain_rows=(chain,),
            inventory_rows=(
                {
                    "topic_role": "estimate",
                    "source_time_ns_private": str(source_time_ns),
                },
            ),
        )

    def test_drive_map_must_match_basenames_exactly_and_is_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = (root / "a.mcap", root / "b.mcap")
            for path in files:
                path.touch()
            drive_map = root / "drives.json"
            drive_map.write_text(
                json.dumps({"a.mcap": "secret-A", "b.mcap": "secret-A"}),
                encoding="utf-8",
            )
            recording_ids, drive_ids = _load_drive_assignments(drive_map, files)
            self.assertEqual(set(recording_ids.values()), {"recording_001", "recording_002"})
            self.assertEqual(set(drive_ids.values()), {"drive_001"})
            self.assertNotIn("secret-A", drive_ids.values())

    def test_one_recording_failure_is_returned_instead_of_raised(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcap = root / "broken.mcap"
            mcap.touch()
            arguments = argparse.Namespace(
                estimate_topic="/estimate",
                map_topic="/map",
                max_step_m=0.25,
                max_pairs_per_recording=2,
                maximum_pair_delta_ms=None,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
            )
            with patch(
                "lane_residuals.batch_pairing_audit_cli.run_pairing_audit",
                side_effect=RuntimeError("synthetic decode failure"),
            ):
                result = _run_one_recording(
                    mcap=mcap,
                    recording_id="recording_002",
                    drive_id="drive_001",
                    output_directory=root / "out",
                    arguments=arguments,
                )
            self.assertIsInstance(result, RecordingAuditData)
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_code, "RuntimeError")
            self.assertIn("synthetic decode failure", result.error_message)

    def test_batch_continues_after_middle_recording_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / f"chunk_{index}.mcap" for index in range(1, 4)]
            for path in files:
                path.touch()
            drive_map = root / "drives.json"
            drive_map.write_text(
                json.dumps(
                    {
                        "chunk_1.mcap": "drive-a",
                        "chunk_2.mcap": "drive-b",
                        "chunk_3.mcap": "drive-c",
                    }
                ),
                encoding="utf-8",
            )
            arguments = argparse.Namespace(
                inputs=files,
                drive_map=drive_map,
                expected_file_count=3,
                output_directory=root / "batch",
                max_pairs_per_recording=2,
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                recording_tail_window_s=5.0,
                primary_tail_threshold_m=None,
                full_tail_threshold_m=None,
                estimate_topic="/estimate",
                map_topic="/map",
            )

            def synthetic_result(**kwargs):
                if kwargs["recording_id"] == "recording_002":
                    return RecordingAuditData(
                        recording_id="recording_002",
                        drive_id=kwargs["drive_id"],
                        mcap_filename=kwargs["mcap"].name,
                        status="failed",
                        output_directory=str(kwargs["output_directory"]),
                        error_code="synthetic_failure",
                        error_message="injected",
                    )
                return self._synthetic_success(
                    kwargs["recording_id"],
                    kwargs["drive_id"],
                    kwargs["mcap"].name,
                    0 if kwargs["recording_id"] == "recording_001" else 1_000_000_000,
                )

            with patch(
                "lane_residuals.batch_pairing_audit_cli._run_one_recording",
                side_effect=synthetic_result,
            ):
                summary, status = run_batch(arguments)

            self.assertEqual(status, 3)
            self.assertEqual(summary["successful_recording_count"], 2)
            self.assertEqual(summary["failed_recording_count"], 1)
            self.assertIn("one_or_more_recording_audits_failed", summary["blockers"])
            manifest = json.loads(
                (arguments.output_directory / "batch_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                [row["status"] for row in manifest["recordings"]],
                ["succeeded", "failed", "succeeded"],
            )
            scope_metrics = (
                arguments.output_directory / "scope_horizon_metrics.csv"
            ).read_text(encoding="utf-8")
            self.assertIn("overall,overall,100,2", scope_metrics)


if __name__ == "__main__":
    unittest.main()
