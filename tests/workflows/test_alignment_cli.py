import contextlib
import csv
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals.cli.alignment import main
from lane_residuals.domain.pairing import ego_relative_path_from_points
from lane_residuals.domain.motion import (
    OdometrySample,
    Pose2D,
    ego_frame_transform,
    transform_path_to_target_ego_frame,
)
from lane_residuals.workflows.alignment import (
    PAIR_FIELDS,
    STATION_FIELDS,
    run_alignment_audit,
)
from lane_residuals.workflows.pairing import _TimedPath


class AlignmentWorkflowTests(unittest.TestCase):
    @staticmethod
    def _timed_path(index: int, time_ns: int, path) -> _TimedPath:
        return _TimedPath(
            message_index=index,
            source_time_ns=time_ns,
            log_time_ns=time_ns,
            publish_time_ns=time_ns,
            geometry_state="geometry_ready",
            path=path,
        )

    @staticmethod
    def _arguments(output: Path) -> SimpleNamespace:
        return SimpleNamespace(
            mcap=Path("synthetic.mcap"),
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

    def test_missing_mcap_returns_argument_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(["missing.mcap"])
        self.assertEqual(status, 2)

    def test_synthetic_alignment_writes_validation_outputs(self) -> None:
        x = np.linspace(-5.0, 125.0, 1301)
        reference = ego_relative_path_from_points(
            np.column_stack((x, 0.002 * np.square(x))),
            source="reference",
        )
        target_transform = ego_frame_transform(
            Pose2D(0.0, 0.0, 0.0),
            Pose2D(0.6, 0.0, 0.0),
        )
        target_reference = transform_path_to_target_ego_frame(
            reference,
            target_transform,
        )
        estimate = ego_relative_path_from_points(
            target_reference.points,
            source="estimate",
        )
        estimates = [self._timed_path(4, 128_000_000, estimate)]
        references = [self._timed_path(7, 100_000_000, reference)]
        odometry = [
            OdometrySample(
                timestamp_ns=100_000_000,
                log_time_ns=100_000_000,
                publish_time_ns=100_000_000,
                pose=Pose2D(0.0, 0.0, 0.0),
            ),
            OdometrySample(
                timestamp_ns=128_000_000,
                log_time_ns=128_000_000,
                publish_time_ns=128_000_000,
                pose=Pose2D(0.6, 0.0, 0.0),
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "alignment"
            with patch(
                "lane_residuals.workflows.alignment._decode_paths",
                return_value=(
                    estimates,
                    references,
                    Counter(),
                    {"estimate_messages": 1, "map_messages": 1},
                ),
            ), patch(
                "lane_residuals.workflows.alignment.decode_odometry_samples",
                return_value=(odometry, Counter(), 2),
            ):
                summary = run_alignment_audit(self._arguments(output))

            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "alignment_pair_audit.csv",
                    "alignment_station_comparison.csv",
                    "alignment_comparison.png",
                    "alignment_summary.json",
                },
            )
            with (output / "alignment_pair_audit.csv").open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                pair_rows = list(csv.DictReader(stream))
                self.assertEqual(tuple(pair_rows[0]), PAIR_FIELDS)
            with (output / "alignment_station_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                station_rows = list(csv.DictReader(stream))
                self.assertEqual(tuple(station_rows[0]), STATION_FIELDS)
            with (output / "alignment_summary.json").open(
                "r", encoding="utf-8"
            ) as stream:
                persisted = json.load(stream)

        self.assertEqual(summary, persisted)
        self.assertEqual(summary["version"], "0.5.1")
        self.assertEqual(summary["complete_stream_mutual_nearest_pair_count"], 1)
        self.assertEqual(summary["h60_aligned_complete_pair_count"], 1)
        self.assertEqual(summary["h100_aligned_complete_pair_count"], 1)
        self.assertTrue(summary["h100_is_subset_of_h60"])
        self.assertTrue(summary["spatial_reference_alignment_applied"])
        self.assertTrue(summary["explicit_ego_pose_motion_compensation_applied"])
        self.assertFalse(summary["generated_final_residual_dataset"])
        self.assertGreater(summary["median_native_h100_pair_lateral_rms_m"], 1e-4)
        self.assertLess(summary["median_aligned_h100_pair_lateral_rms_m"], 1e-8)
        self.assertAlmostEqual(
            summary["median_absolute_geometry_epoch_delta_ms"],
            28.0,
        )
        self.assertAlmostEqual(
            summary["median_ego_motion_source_to_target_travel_m"],
            0.6,
        )
        self.assertEqual(len(station_rows), 21)
        self.assertAlmostEqual(float(pair_rows[0]["source_delta_ms"]), 28.0)
        self.assertAlmostEqual(
            float(pair_rows[0]["reference_anchor_station_m"]),
            0.6,
            places=2,
        )

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "alignment"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not empty"):
                run_alignment_audit(self._arguments(output))


if __name__ == "__main__":
    unittest.main()
