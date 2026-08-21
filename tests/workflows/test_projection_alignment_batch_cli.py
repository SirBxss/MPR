import csv
import hashlib
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals.domain.pairing import ego_relative_path_from_points
from lane_residuals.workflows.pairing import _TimedPath
from lane_residuals.workflows.projection_alignment import run_alignment_audit
from lane_residuals.workflows.projection_alignment_batch import (
    BATCH_OUTPUT_FILES,
    PURPOSE,
    RecordingAlignmentData,
    run_alignment_batch,
)
from lane_residuals.visualization.projection_alignment import (
    plot_alignment_comparison,
)


class ProjectionAlignmentBatchWorkflowTests(unittest.TestCase):
    def test_batch_plot_treats_blank_optional_csv_values_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "comparison.png"
            plot_alignment_comparison(
                output_path,
                pair_rows=[
                    {
                        "source_delta_ms": "10.0",
                        "aligned_minus_native_h100_lateral_rms_m": "",
                    }
                ],
                station_rows=[
                    {
                        "station_m": "0.0",
                        "aligned_lateral_m": "0.1",
                        "native_lateral_m": "",
                    }
                ],
            )
            self.assertTrue(output_path.is_file())

    @staticmethod
    def _write_inventory(root: Path, basenames: list[str]) -> Path:
        inventory = root / "inventory"
        inventory.mkdir()
        (inventory / "corpus_inventory_summary.json").write_text(
            json.dumps(
                {
                    "version": "0.12.1",
                    "status": "complete",
                    "exact_drive_map_coverage": True,
                    "mcap_file_count": len(basenames),
                    "unusable_file_count": 0,
                    "rejected_boundary_count": 0,
                }
            ),
            encoding="utf-8",
        )
        (inventory / "proposed_session_groups.json").write_text(
            json.dumps(
                {
                    "cross_mcap_sequence_stitching_performed": False,
                    "groups": [
                        {
                            "block_id": f"block_{index:03d}",
                            "mcap_basenames_private": [basename],
                        }
                        for index, basename in enumerate(basenames, 1)
                    ],
                }
            ),
            encoding="utf-8",
        )
        with (inventory / "recording_continuity.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            csv.DictWriter(
                handle, fieldnames=("stitchable", "rejection_codes")
            ).writeheader()
        return inventory

    @staticmethod
    def _recording(recording_id: str, drive_id: str, basename: str) -> RecordingAlignmentData:
        pair = {
            "pair_index": 0,
            "estimate_message_index": 4,
            "map_message_index": 7,
            "estimate_source_time_ns_private": 128_000_000,
            "map_source_time_ns_private": 100_000_000,
            "source_delta_ms": 28.0,
            "absolute_source_delta_ms": 28.0,
            "pair_state": "aligned_h100_ready",
            "failure_code": None,
            "h60_aligned_eligible": True,
            "h100_aligned_eligible": True,
            "reference_anchor_station_m": 0.5,
            "anchor_distance_m": 0.08,
            "aligned_minus_native_h60_lateral_rms_m": 0.01,
            "aligned_minus_native_h100_lateral_rms_m": 0.02,
        }
        stations = tuple(
            {
                "pair_index": 0,
                "station_m": float(station),
                "native_lateral_m": 0.2,
                "aligned_lateral_m": 0.1 + station / 1000.0,
                "h60_aligned_eligible": True,
                "h100_aligned_eligible": True,
            }
            for station in range(0, 101, 5)
        )
        return RecordingAlignmentData(
            recording_id=recording_id,
            drive_id=drive_id,
            mcap_filename=basename,
            status="succeeded",
            output_directory=f"recordings/{recording_id}",
            summary={
                "complete_stream_mutual_nearest_pair_count": 1,
                "h60_aligned_complete_pair_count": 1,
                "h100_aligned_complete_pair_count": 1,
                "median_absolute_source_delta_ms": 28.0,
                "median_reference_anchor_station_m": 0.5,
                "median_anchor_distance_m": 0.08,
                "median_aligned_minus_native_h60_pair_lateral_rms_m": 0.01,
                "median_aligned_minus_native_h100_pair_lateral_rms_m": 0.02,
            },
            pair_rows=(pair,),
            station_rows=stations,
        )

    def test_v052_batch_is_exact_manifest_native_and_hashes_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / "a.mcap", root / "b.mcap"]
            for index, path in enumerate(files):
                path.write_bytes(f"mcap-{index}".encode())
            drive_map = root / "sessions.private.json"
            drive_map.write_text(
                json.dumps({"a.mcap": "session-a", "b.mcap": "session-b"}),
                encoding="utf-8",
            )
            inventory = self._write_inventory(root, [path.name for path in files])
            output = root / "output"
            arguments = SimpleNamespace(
                inputs=tuple(files),
                drive_map=drive_map,
                corpus_inventory_directory=inventory,
                expected_file_count=2,
                output_directory=output,
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                estimate_topic="/estimate",
                map_topic="/map",
            )

            def fake_recording(**kwargs):
                return self._recording(
                    kwargs["recording_id"], kwargs["drive_id"], kwargs["mcap"].name
                )

            with patch(
                "lane_residuals.workflows.projection_alignment_batch._run_one_recording",
                side_effect=fake_recording,
            ):
                summary, status = run_alignment_batch(arguments)

            self.assertEqual(status, 0)
            self.assertEqual(summary["version"], "0.5.2")
            self.assertEqual(summary["purpose"], PURPOSE)
            self.assertEqual(
                summary["alignment_semantics"],
                "v0.5.0_native_spatial_projection",
            )
            self.assertFalse(summary["explicit_ego_pose_motion_compensation_applied"])
            self.assertFalse(summary["source_delta_used_numerically_for_alignment"])
            self.assertTrue(summary["accepted_for_modeling"])
            self.assertEqual(summary["h60_aligned_complete_pair_count"], 2)
            self.assertEqual(summary["h100_aligned_complete_pair_count"], 2)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {*BATCH_OUTPUT_FILES, "batch_output_provenance.json"},
            )
            provenance = json.loads(
                (output / "batch_output_provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                set(provenance["source_files_sha256"]),
                {
                    "drive_map_private_json",
                    "corpus_inventory_summary.json",
                    "recording_continuity.csv",
                    "proposed_session_groups.json",
                },
            )
            for name, digest in provenance["generated_batch_outputs_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_native_projection_is_independent_of_numeric_source_delta(self) -> None:
        x = np.linspace(-5.0, 125.0, 1301)
        path = ego_relative_path_from_points(
            np.column_stack((x, 0.002 * np.square(x))),
            source="synthetic",
        )

        def timed(index: int, source_time: int) -> _TimedPath:
            return _TimedPath(
                message_index=index,
                source_time_ns=source_time,
                log_time_ns=source_time,
                publish_time_ns=source_time,
                geometry_state="geometry_ready",
                path=path,
            )

        station_profiles = []
        deltas = (1_000_000, 150_000_000)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for run_index, delta in enumerate(deltas):
                output = root / f"run-{run_index}"
                with patch(
                    "lane_residuals.workflows.projection_alignment._decode_paths",
                    return_value=(
                        [timed(4, 1_000_000_000 + delta)],
                        [timed(7, 1_000_000_000)],
                        Counter(),
                        {"estimate_messages": 1, "map_messages": 1},
                    ),
                ):
                    summary = run_alignment_audit(
                        SimpleNamespace(
                            mcap=Path("synthetic.mcap"),
                            output_directory=output,
                            maximum_pair_delta_ms=None,
                            max_step_m=0.25,
                            map_max_segments=16,
                            map_max_junction_gap_m=1.0,
                            map_max_junction_heading_deg=30.0,
                            estimate_topic="/estimate",
                            map_topic="/map",
                        )
                    )
                with (output / "alignment_station_comparison.csv").open(
                    newline="", encoding="utf-8"
                ) as handle:
                    station_profiles.append(
                        [float(row["aligned_lateral_m"]) for row in csv.DictReader(handle)]
                    )
                self.assertEqual(summary["version"], "0.5.2")
                self.assertFalse(summary["source_delta_used_numerically_for_alignment"])
                self.assertEqual(summary["h100_aligned_complete_pair_count"], 1)
        np.testing.assert_allclose(station_profiles[0], station_profiles[1], atol=0.0)


@unittest.skipUnless(
    os.environ.get("MPR_RUN_PRIVATE_ALIGNMENT_PARITY") == "1",
    "set MPR_RUN_PRIVATE_ALIGNMENT_PARITY=1 after generating the private v0.5.2 batch",
)
class PrivateHistoricalProjectionParityTests(unittest.TestCase):
    def test_original_ten_mcaps_match_historical_v050_numerically(self) -> None:
        historical = Path(
            "outputs/diagnostics/validation/reference_alignment_batch_v050"
        )
        current = Path(
            "outputs/diagnostics/validation/reference_alignment_batch_v052_expanded"
        )
        self.assertTrue(historical.is_dir())
        self.assertTrue(current.is_dir())

        def rows(directory: Path, name: str) -> list[dict[str, str]]:
            with (directory / name).open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))

        old_pairs = rows(historical, "alignment_pair_audit.csv")
        new_pairs = rows(current, "alignment_pair_audit.csv")
        original_recordings = {f"recording_{index:03d}" for index in range(1, 11)}
        new_pairs = [row for row in new_pairs if row["recording_id"] in original_recordings]
        pair_key = lambda row: (row["recording_id"], int(row["pair_index"]))
        old_pairs.sort(key=pair_key)
        new_pairs.sort(key=pair_key)
        self.assertEqual(len(new_pairs), len(old_pairs))
        for old, new in zip(old_pairs, new_pairs):
            self.assertEqual(pair_key(old), pair_key(new))
            for field in (
                "estimate_message_index",
                "map_message_index",
                "h60_aligned_eligible",
                "h100_aligned_eligible",
                "pair_state",
                "failure_code",
            ):
                self.assertEqual(new[field], old[field])

        old_stations = rows(historical, "alignment_station_comparison.csv")
        new_stations = [
            row
            for row in rows(current, "alignment_station_comparison.csv")
            if row["recording_id"] in original_recordings
        ]
        station_key = lambda row: (
            row["recording_id"],
            int(row["pair_index"]),
            float(row["station_m"]),
        )
        old_stations.sort(key=station_key)
        new_stations.sort(key=station_key)
        self.assertEqual(len(new_stations), len(old_stations))
        for old, new in zip(old_stations, new_stations):
            self.assertEqual(station_key(old), station_key(new))
            self.assertEqual(new["h100_aligned_eligible"], old["h100_aligned_eligible"])
            self.assertAlmostEqual(
                float(new["aligned_lateral_m"]),
                float(old["aligned_lateral_m"]),
                places=12,
            )

        old_summary = json.loads(
            (historical / "alignment_batch_summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(old_pairs), old_summary["mutual_nearest_pair_count"])
        self.assertEqual(
            sum(row["h60_aligned_eligible"] == "True" for row in new_pairs),
            old_summary["h60_aligned_complete_pair_count"],
        )
        self.assertEqual(
            sum(row["h100_aligned_eligible"] == "True" for row in new_pairs),
            old_summary["h100_aligned_complete_pair_count"],
        )
        metrics = {
            "median_absolute_source_delta_ms": "absolute_source_delta_ms",
            "median_reference_anchor_station_m": "reference_anchor_station_m",
            "median_anchor_distance_m": "anchor_distance_m",
            "median_aligned_minus_native_h60_pair_lateral_rms_m": (
                "aligned_minus_native_h60_lateral_rms_m"
            ),
            "median_aligned_minus_native_h100_pair_lateral_rms_m": (
                "aligned_minus_native_h100_lateral_rms_m"
            ),
        }
        for summary_field, row_field in metrics.items():
            values = [float(row[row_field]) for row in new_pairs if row[row_field]]
            self.assertAlmostEqual(
                float(np.median(np.asarray(values))),
                old_summary[summary_field],
                places=12,
            )


if __name__ == "__main__":
    unittest.main()
