import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class ExpandedAIOHMMWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_gaussian(source: Path, output: Path) -> None:
        status = gaussian_main(
            [
                str(source),
                "--output-directory",
                str(output),
                "--sample-count",
                "8",
                "--seed",
                "1400",
            ]
        )
        if status != 0:
            raise AssertionError("v0.14 fixture generation failed")

    @staticmethod
    def _arguments(source: Path, gaussian: Path, output: Path) -> list[str]:
        return [
            str(source),
            "--gaussian-directory",
            str(gaussian),
            "--output-directory",
            str(output),
            "--restart-count",
            "1",
            "--maximum-em-iterations",
            "3",
            "--minimum-em-iterations",
            "2",
            "--transition-adam-steps",
            "2",
            "--minimum-effective-state-observations",
            "2",
            "--minimum-state-occupancy-fraction",
            "0.001",
            "--sample-count",
            "8",
            "--seed",
            "1400",
            "--log-level",
            "ERROR",
        ]

    def test_command_reuses_v014_folds_and_separates_mixed_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            output = root / "aiohmm"
            self._write_gaussian(source, gaussian)

            status = aiohmm_main(self._arguments(source, gaussian, output))

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "expanded_aiohmm_diagnostics.png",
                    "expanded_aiohmm_evaluation.csv",
                    "expanded_aiohmm_fold_models.json",
                    "expanded_aiohmm_frame_evaluation.csv",
                    "expanded_aiohmm_model.json",
                    "expanded_aiohmm_restart_evaluation.csv",
                    "expanded_aiohmm_state_evaluation.csv",
                    "expanded_aiohmm_station_evaluation.csv",
                    "expanded_aiohmm_summary.json",
                },
            )
            summary = json.loads(
                (output / "expanded_aiohmm_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["version"], "0.15.0")
            self.assertEqual(summary["state_count"], 2)
            self.assertEqual(summary["primary_frame_count"], 20)
            self.assertEqual(summary["supplementary_frame_count"], 5)
            self.assertTrue(summary["same_folds_transforms_and_metrics_as_v0140_gaussian"])
            self.assertFalse(summary["automatic_state_count_selection_performed"])
            self.assertFalse(summary["held_out_drives_used_for_state_count_or_restart_selection"])
            self.assertTrue(summary["mixed_source_results_are_supplementary_only"])
            self.assertFalse(summary["final_model_selection_authorized"])
            self.assertIn(
                summary["result_classification"],
                {
                    "full_generative_acceptance_met",
                    (
                        "temporal_dependence_improved_but_full_generative_"
                        "acceptance_not_met"
                    ),
                },
            )
            self.assertEqual(
                summary["all_development_acceptance_checks_passed"],
                all(summary["development_acceptance_checks"].values()),
            )

            with (output / "expanded_aiohmm_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluation_rows = list(csv.DictReader(handle))
            self.assertEqual(len(evaluation_rows), 6)
            self.assertEqual(
                sum(row["scope"] == "held_out_drive" for row in evaluation_rows), 4
            )
            self.assertEqual(
                sum(
                    row["scope"] == "supplementary_mixed_transfer"
                    for row in evaluation_rows
                ),
                1,
            )
            with (output / "expanded_aiohmm_frame_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            self.assertEqual(len(frame_rows), 25)
            self.assertTrue(all(row["recording_id"] for row in frame_rows))
            self.assertTrue(all(row["mcap_basename_private"] for row in frame_rows))

    def test_tampered_gaussian_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            output = root / "aiohmm"
            self._write_gaussian(source, gaussian)
            with (gaussian / "gaussian_grouped_evaluation.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("tampered\n")

            status = aiohmm_main(self._arguments(source, gaussian, output))

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_nonfixed_state_count_is_rejected_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            output = root / "aiohmm"
            self._write_gaussian(source, gaussian)
            arguments = self._arguments(source, gaussian, output)
            arguments.extend(["--state-count", "3"])

            status = aiohmm_main(arguments)

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
