import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.sequence_dataset import main as sequence_dataset_main
from lane_residuals.cli.sequence_gaussian import main
from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    residual_column_name,
)
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.io.reports import write_csv_rows


class SequenceGaussianWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_v090(root: Path) -> Path:
        source = root / "conditional"
        source.mkdir()
        rng = np.random.default_rng(81)
        coefficients = rng.normal(scale=0.025, size=(6, 21))
        rows: list[dict[str, object]] = []
        for drive_number in (1, 2):
            for pair_index in range(12):
                condition = rng.normal(size=6)
                residual = 0.02 * drive_number + condition @ coefficients
                residual += rng.normal(scale=0.015, size=21)
                source_time = (
                    drive_number * 3_000_000_000 + pair_index * 80_000_000
                )
                row: dict[str, object] = {
                    "recording_id": f"recording_{drive_number:03d}",
                    "drive_id": f"drive_{drive_number:03d}",
                    "pair_index": pair_index,
                    "estimate_message_index": pair_index + 10,
                    "map_message_index": pair_index + 20,
                    "estimate_source_time_ns_private": source_time,
                    "map_source_time_ns_private": source_time + 100_000,
                    "source_delta_ms": -0.1,
                    "speed_mps": 15.0 + condition[0],
                    "estimated_mean_abs_curvature_per_m": 0.02 + condition[1],
                    "estimated_curvature_delta_per_m": condition[2],
                    "confidence_near_mean": 0.8 + 0.02 * condition[3],
                    "confidence_middle_mean": 0.7 + 0.02 * condition[4],
                    "confidence_far_mean": 0.6 + 0.02 * condition[5],
                }
                for index, station in enumerate(CANONICAL_MODEL_STATIONS_M):
                    row[residual_column_name(station)] = residual[index]
                rows.append(row)
        write_csv_rows(
            source / "conditional_cohort.csv",
            (*RESIDUAL_VECTOR_FIELDS, *BMW_CONDITION_FEATURE_NAMES),
            rows,
        )
        (source / "conditional_cohort_summary.json").write_text(
            json.dumps(
                {
                    "version": "0.8.0",
                    "status": "complete",
                    "purpose": "frozen_complete_feature_conditional_h100_cohort",
                    "feature_names": list(BMW_CONDITION_FEATURE_NAMES),
                    "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
                    "constant_pair_count_at_every_station": True,
                    "selection_uses_residual_values": False,
                    "cross_mcap_feature_extraction": False,
                    "speed_extrapolation": False,
                    "selected_vector_count": 24,
                    "selected_vector_count_by_drive": {
                        "drive_001": 12,
                        "drive_002": 12,
                    },
                    "selected_vector_count_by_recording": {
                        "recording_001": 12,
                        "recording_002": 12,
                    },
                }
            ),
            encoding="utf-8",
        )
        output = root / "sequences"
        status = sequence_dataset_main(
            [str(source), "--output-directory", str(output)]
        )
        if status != 0:
            raise AssertionError("synthetic v0.9.0 fixture failed")
        return output

    def test_command_evaluates_temporal_null_on_exact_drive_folds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_v090(root)
            output = root / "gaussian"

            status = main(
                [
                    str(source),
                    "--output-directory",
                    str(output),
                    "--covariance-regularization-standardized2",
                    "0.0001",
                    "--sample-count",
                    "20",
                    "--seed",
                    "41",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "gaussian_sequence_evaluation.csv",
                    "gaussian_sequence_station_evaluation.csv",
                    "gaussian_sequence_frame_evaluation.csv",
                    "gaussian_sequence_fold_models.json",
                    "gaussian_sequence_model.json",
                    "gaussian_sequence_diagnostics.png",
                    "gaussian_sequence_summary.json",
                },
            )
            summary = json.loads(
                (output / "gaussian_sequence_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["version"], "0.10.0")
            self.assertEqual(summary["sequence_count"], 2)
            self.assertEqual(summary["frame_count"], 24)
            self.assertEqual(summary["sample_count"], 20)
            self.assertTrue(summary["temporally_conditionally_independent"])
            self.assertEqual(summary["temporal_dependency_order"], 0)
            self.assertFalse(summary["final_model_selection_authorized"])
            self.assertTrue(
                summary["sample_metrics_are_common_to_all_model_families"]
            )
            metrics = summary["cross_validated_metrics"]
            self.assertTrue(np.isfinite(metrics["mean_energy_score_m"]))
            self.assertTrue(np.isfinite(metrics["sample_mean_prediction_rmse_m"]))

            with (output / "gaussian_sequence_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluations = list(csv.DictReader(handle))
            self.assertEqual(len(evaluations), 3)
            self.assertEqual(
                sum(row["scope"] == "held_out_drive" for row in evaluations),
                2,
            )
            with (output / "gaussian_sequence_station_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                station_rows = list(csv.DictReader(handle))
            self.assertEqual(len(station_rows), 3 * 21)
            with (output / "gaussian_sequence_frame_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            self.assertEqual(len(frame_rows), 24)

    def test_source_hash_change_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_v090(root)
            with (source / "sequence_summary.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("changed\n")
            output = root / "gaussian"

            status = main([str(source), "--output-directory", str(output)])

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
