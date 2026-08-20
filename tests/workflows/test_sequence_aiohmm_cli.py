import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.sequence_aiohmm import main
from lane_residuals.cli.sequence_dataset import main as sequence_dataset_main
from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    residual_column_name,
)
from lane_residuals.domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from lane_residuals.io.reports import write_csv_rows


class SequenceAIOHMMWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_v090(root: Path) -> Path:
        source = root / "conditional"
        source.mkdir()
        generator = np.random.default_rng(118)
        coefficients = generator.normal(scale=0.02, size=(6, 21))
        rows: list[dict[str, object]] = []
        for drive_number in (1, 2):
            previous = np.zeros(21, dtype=np.float64)
            for pair_index in range(36):
                condition = generator.normal(size=6)
                state_offset = 0.08 if (pair_index // 9) % 2 else -0.06
                residual = (
                    state_offset
                    + condition @ coefficients
                    + 0.78 * previous
                    + generator.normal(scale=0.02, size=21)
                )
                previous = residual
                source_time = (
                    drive_number * 5_000_000_000 + pair_index * 80_000_000
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
                    "selected_vector_count": 72,
                    "selected_vector_count_by_drive": {
                        "drive_001": 36,
                        "drive_002": 36,
                    },
                    "selected_vector_count_by_recording": {
                        "recording_001": 36,
                        "recording_002": 36,
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

    @staticmethod
    def _arguments(source: Path, output: Path) -> list[str]:
        return [
            str(source),
            "--output-directory",
            str(output),
            "--state-count",
            "2",
            "--restart-count",
            "2",
            "--maximum-em-iterations",
            "4",
            "--minimum-em-iterations",
            "2",
            "--transition-adam-steps",
            "5",
            "--minimum-effective-state-observations",
            "2",
            "--minimum-state-occupancy-fraction",
            "0.001",
            "--sample-count",
            "20",
            "--initialization-seed",
            "71",
            "--seed",
            "83",
            "--log-level",
            "ERROR",
        ]

    def test_command_evaluates_fixed_aiohmm_on_exact_drive_folds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_v090(root)
            output = root / "aiohmm"

            status = main(self._arguments(source, output))

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "aiohmm_sequence_evaluation.csv",
                    "aiohmm_sequence_station_evaluation.csv",
                    "aiohmm_sequence_frame_evaluation.csv",
                    "aiohmm_sequence_state_evaluation.csv",
                    "aiohmm_sequence_restart_evaluation.csv",
                    "aiohmm_sequence_fold_models.json",
                    "aiohmm_sequence_model.json",
                    "aiohmm_sequence_diagnostics.png",
                    "aiohmm_sequence_summary.json",
                },
            )
            summary = json.loads(
                (output / "aiohmm_sequence_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["version"], "0.11.0")
            self.assertEqual(summary["sequence_count"], 2)
            self.assertEqual(summary["frame_count"], 72)
            self.assertEqual(summary["state_count"], 2)
            self.assertEqual(summary["restart_count_per_fit"], 2)
            self.assertFalse(summary["automatic_state_count_selection_performed"])
            self.assertEqual(
                summary["sequence_reset_prior"],
                "state_independent_training_marginal_conditional_gaussian",
            )
            self.assertFalse(summary["sequence_reset_prior_uses_held_out_rows"])
            self.assertFalse(
                summary["held_out_drives_used_for_state_count_or_restart_selection"]
            )
            self.assertFalse(summary["final_model_selection_authorized"])
            metrics = summary["cross_validated_metrics"]
            self.assertTrue(np.isfinite(metrics["mean_energy_score_m"]))
            self.assertTrue(
                np.isfinite(metrics["median_generated_lag_one_correlation"])
            )

            with (output / "aiohmm_sequence_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluations = list(csv.DictReader(handle))
            self.assertEqual(len(evaluations), 3)
            with (output / "aiohmm_sequence_station_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                station_rows = list(csv.DictReader(handle))
            self.assertEqual(len(station_rows), 3 * 21)
            with (output / "aiohmm_sequence_frame_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            self.assertEqual(len(frame_rows), 72)
            with (output / "aiohmm_sequence_state_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                state_rows = list(csv.DictReader(handle))
            self.assertEqual(len(state_rows), 6)
            with (output / "aiohmm_sequence_restart_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                restart_rows = list(csv.DictReader(handle))
            self.assertEqual(len(restart_rows), 6)
            self.assertEqual(sum(row["selected"] == "True" for row in restart_rows), 3)

    def test_source_hash_change_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_v090(root)
            with (source / "sequence_summary.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("changed\n")
            output = root / "aiohmm"

            status = main(self._arguments(source, output))

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
