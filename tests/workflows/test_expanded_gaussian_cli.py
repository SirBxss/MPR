import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_gaussian import main
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class ExpandedGaussianWorkflowTests(unittest.TestCase):
    def test_command_uses_four_clean_drive_folds_and_separates_mixed_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            output = root / "gaussian"

            status = main(
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

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "drive_grouped_evaluation_contract.json",
                    "gaussian_grouped_diagnostics.png",
                    "gaussian_grouped_evaluation.csv",
                    "gaussian_grouped_frame_evaluation.csv",
                    "gaussian_grouped_models.json",
                    "gaussian_grouped_station_evaluation.csv",
                    "gaussian_grouped_summary.json",
                },
            )
            protocol = json.loads(
                (output / "drive_grouped_evaluation_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(protocol["fold_count"], 4)
            self.assertFalse(protocol["random_frame_splits_permitted"])
            self.assertFalse(protocol["final_model_selection_authorized"])
            self.assertTrue(
                protocol["supplementary_cohort"][
                    "never_used_for_fit_or_primary_model_comparison"
                ]
            )
            for fold in protocol["folds"]:
                self.assertNotIn(
                    fold["held_out_drive_id"], fold["training_drive_ids"]
                )
                self.assertEqual(len(fold["training_drive_ids"]), 3)

            summary = json.loads(
                (output / "gaussian_grouped_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["version"], "0.14.0")
            self.assertEqual(summary["primary_frame_count"], 20)
            self.assertEqual(summary["supplementary_frame_count"], 5)
            self.assertEqual(
                set(summary["models"]),
                {"unconditional_gaussian", "conditional_gaussian"},
            )
            self.assertFalse(summary["final_model_selection_authorized"])

            with (output / "gaussian_grouped_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluation_rows = list(csv.DictReader(handle))
            self.assertEqual(len(evaluation_rows), 12)
            self.assertEqual(
                sum(row["scope"] == "primary_held_out_drive" for row in evaluation_rows),
                8,
            )
            self.assertEqual(
                sum(
                    row["scope"] == "supplementary_mixed_transfer"
                    for row in evaluation_rows
                ),
                2,
            )
            with (output / "gaussian_grouped_frame_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            self.assertEqual(len(frame_rows), 50)
            self.assertTrue(all(row["recording_id"] for row in frame_rows))
            self.assertTrue(all(row["mcap_basename_private"] for row in frame_rows))

    def test_invalid_source_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            (source / "sequence_summary_by_drive.csv").write_text(
                "changed\n", encoding="utf-8"
            )
            output = root / "gaussian"

            status = main([str(source), "--output-directory", str(output)])

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
