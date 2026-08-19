import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.sequence_dataset import main
from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    residual_column_name,
)
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.io.reports import write_csv_rows
from lane_residuals.io.sequence_dataset import load_sequence_dataset_npz


class SequenceDatasetWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_source(root: Path) -> Path:
        source = root / "conditional"
        source.mkdir()
        rows: list[dict[str, object]] = []
        specifications = (
            (
                "recording_001",
                "drive_a",
                (0, 1, 4, 5),
                (1_000_000_000, 1_080_000_000, 1_500_000_000, 1_580_000_000),
            ),
            (
                "recording_002",
                "drive_b",
                (0, 1, 2, 3),
                (3_000_000_000, 3_080_000_000, 3_160_000_000, 3_240_000_000),
            ),
        )
        for drive_number, (recording_id, drive_id, pairs, times) in enumerate(
            specifications,
            start=1,
        ):
            for local_index, (pair_index, source_time) in enumerate(zip(pairs, times)):
                row: dict[str, object] = {
                    "recording_id": recording_id,
                    "drive_id": drive_id,
                    "pair_index": pair_index,
                    "estimate_message_index": pair_index + 10,
                    "map_message_index": pair_index + 20,
                    "estimate_source_time_ns_private": source_time,
                    "map_source_time_ns_private": source_time + 100_000,
                    "source_delta_ms": -0.1,
                    "speed_mps": 10.0 + drive_number + local_index,
                    "estimated_mean_abs_curvature_per_m": (
                        0.001 * (drive_number + local_index)
                    ),
                    "estimated_curvature_delta_per_m": (
                        -0.002 + 0.001 * local_index
                    ),
                    "confidence_near_mean": 0.9 - 0.01 * local_index,
                    "confidence_middle_mean": 0.8 - 0.01 * local_index,
                    "confidence_far_mean": 0.7 - 0.01 * local_index,
                }
                for station_index, station in enumerate(CANONICAL_MODEL_STATIONS_M):
                    row[residual_column_name(station)] = (
                        0.03 * drive_number
                        + 0.01 * local_index
                        + 0.002 * np.sin(local_index + station_index / 4.0)
                    )
                rows.append(row)

        write_csv_rows(
            source / "conditional_cohort.csv",
            (*RESIDUAL_VECTOR_FIELDS, *BMW_CONDITION_FEATURE_NAMES),
            rows,
        )
        summary = {
            "version": "0.8.0",
            "status": "complete",
            "purpose": "frozen_complete_feature_conditional_h100_cohort",
            "feature_names": list(BMW_CONDITION_FEATURE_NAMES),
            "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "constant_pair_count_at_every_station": True,
            "selection_uses_residual_values": False,
            "cross_mcap_feature_extraction": False,
            "speed_extrapolation": False,
            "selected_vector_count": len(rows),
            "selected_vector_count_by_drive": {"drive_a": 4, "drive_b": 4},
            "selected_vector_count_by_recording": {
                "recording_001": 4,
                "recording_002": 4,
            },
        }
        (source / "conditional_cohort_summary.json").write_text(
            json.dumps(summary),
            encoding="utf-8",
        )
        return source

    def test_command_builds_gap_aware_physical_drive_folds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_source(root)
            output = root / "sequences"

            status = main([str(source), "--output-directory", str(output)])

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "sequential_dataset.npz",
                    "sequence_summary.csv",
                    "sequence_frame_index.csv",
                    "drive_fold_manifest.json",
                    "drive_fold_standardizers.json",
                    "sequence_dataset_diagnostics.png",
                    "sequential_dataset_summary.json",
                },
            )
            summary = json.loads(
                (output / "sequential_dataset_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["retained_frame_count"], 8)
            self.assertEqual(summary["sequence_count"], 3)
            self.assertEqual(summary["recording_count"], 2)
            self.assertEqual(summary["drive_count"], 2)
            self.assertEqual(
                summary["sequence_start_reason_counts"],
                {"pair_index_and_time_gap": 1, "recording_start": 2},
            )
            self.assertFalse(summary["model_training_performed"])
            self.assertFalse(summary["conditional_gaussian_finalized"])
            self.assertTrue(
                summary["additional_independent_drives_required_for_final_comparison"]
            )

            with (output / "sequence_summary.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                sequence_rows = list(csv.DictReader(handle))
            self.assertEqual(len(sequence_rows), 3)
            self.assertEqual(sequence_rows[1]["start_reason"], "pair_index_and_time_gap")
            self.assertEqual(sequence_rows[1]["preceding_pair_index_gap"], "3")

            fold_manifest = json.loads(
                (output / "drive_fold_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(fold_manifest["scheme"], "leave_one_physical_drive_out")
            self.assertFalse(fold_manifest["same_drive_may_cross_fold"])
            self.assertEqual(len(fold_manifest["folds"]), 2)
            for fold in fold_manifest["folds"]:
                self.assertNotIn(
                    fold["held_out_drive_id"],
                    fold["training_drive_ids"],
                )
                self.assertEqual(fold["training_frame_count"], 4)
                self.assertEqual(fold["test_frame_count"], 4)

            with np.load(output / "sequential_dataset.npz", allow_pickle=False) as data:
                self.assertEqual(data["conditions"].shape, (3, 4, 6))
                self.assertEqual(data["residuals_m"].shape, (3, 4, 21))
                self.assertEqual(data["lengths"].tolist(), [2, 2, 4])
                self.assertEqual(int(np.sum(data["valid_mask"])), 8 * 21)
            loaded = load_sequence_dataset_npz(output / "sequential_dataset.npz")
            self.assertEqual(loaded.frame_count, 8)
            self.assertEqual(loaded.drive_ids.tolist(), ["drive_a", "drive_a", "drive_b"])
            self.assertFalse(loaded.standardized)

    def test_source_summary_mismatch_fails_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_source(root)
            summary_path = source / "conditional_cohort_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["selected_vector_count"] = 9
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            output = root / "sequences"

            status = main([str(source), "--output-directory", str(output)])

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
