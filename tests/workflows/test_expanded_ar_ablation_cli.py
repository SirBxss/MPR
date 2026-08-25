import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_ar_ablation import main as ar_ablation_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class ExpandedARAblationWorkflowTests(unittest.TestCase):
    @staticmethod
    def _model_arguments() -> list[str]:
        return [
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

    @classmethod
    def _write_references(
        cls, source: Path, gaussian: Path, aiohmm: Path
    ) -> None:
        gaussian_status = gaussian_main(
            [
                str(source),
                "--output-directory",
                str(gaussian),
                "--sample-count",
                "8",
                "--seed",
                "1400",
            ]
        )
        if gaussian_status != 0:
            raise AssertionError("v0.14 fixture generation failed")
        aiohmm_status = aiohmm_main(
            [
                str(source),
                "--gaussian-directory",
                str(gaussian),
                "--output-directory",
                str(aiohmm),
                *cls._model_arguments(),
            ]
        )
        if aiohmm_status != 0:
            raise AssertionError("v0.15 fixture generation failed")

    @classmethod
    def _arguments(
        cls, source: Path, gaussian: Path, aiohmm: Path, output: Path
    ) -> list[str]:
        return [
            str(source),
            "--gaussian-directory",
            str(gaussian),
            "--aiohmm-directory",
            str(aiohmm),
            "--output-directory",
            str(output),
            *cls._model_arguments(),
        ]

    def test_command_is_exact_one_state_ablation_of_v015(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            output = root / "one_state_ar"
            self._write_references(source, gaussian, aiohmm)

            status = ar_ablation_main(
                self._arguments(source, gaussian, aiohmm, output)
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "one_state_ar_diagnostics.png",
                    "one_state_ar_evaluation.csv",
                    "one_state_ar_fold_models.json",
                    "one_state_ar_frame_evaluation.csv",
                    "one_state_ar_model.json",
                    "one_state_ar_restart_evaluation.csv",
                    "one_state_ar_state_evaluation.csv",
                    "one_state_ar_station_evaluation.csv",
                    "one_state_ar_summary.json",
                },
            )
            summary = json.loads(
                (output / "one_state_ar_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["version"], "0.15.1")
            self.assertEqual(summary["state_count"], 1)
            self.assertFalse(summary["latent_state_switching"])
            self.assertFalse(summary["input_dependent_state_transitions_effective"])
            self.assertTrue(
                summary[
                    "same_folds_transforms_hyperparameters_sampling_and_metrics_as_v0150"
                ]
            )
            self.assertEqual(summary["two_state_aiohmm_reference_version"], "0.15.0")
            self.assertEqual(
                set(
                    summary[
                        "one_state_ar_minus_two_state_aiohmm_primary_macro_deltas"
                    ]
                ),
                {
                    "absolute_marginal_95_coverage_error",
                    "mean_energy_score_m",
                    "mean_joint_negative_log_likelihood_physical",
                    "mean_normalized_sequence_energy_score_m",
                    "median_absolute_lag_one_correlation_error",
                    "sample_mean_prediction_rmse_m",
                },
            )
            self.assertIn(
                summary["latent_switching_result_classification"],
                {
                    "latent_switching_improves_all_predeclared_sample_metrics",
                    "mixed_evidence_for_latent_switching",
                    "no_predeclared_sample_metric_support_for_latent_switching",
                },
            )
            paired = summary["paired_sequence_energy_two_state_comparison"]
            self.assertEqual(paired["fold_count"], 4)
            self.assertFalse(
                paired["independent_journey_level_inference_authorized"]
            )
            self.assertGreater(
                (output / "one_state_ar_diagnostics.png").stat().st_size, 0
            )

            with (output / "one_state_ar_state_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                state_rows = list(csv.DictReader(handle))
            self.assertTrue(state_rows)
            self.assertTrue(
                all(
                    row["state_label_interpretation"]
                    == "single_component_no_latent_state_switching"
                    for row in state_rows
                )
            )
            self.assertTrue(
                all(float(row["posterior_state_occupancy"]) == 1.0 for row in state_rows)
            )

    def test_tampered_v015_reference_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            output = root / "one_state_ar"
            self._write_references(source, gaussian, aiohmm)
            with (aiohmm / "expanded_aiohmm_evaluation.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("tampered\n")

            status = ar_ablation_main(
                self._arguments(source, gaussian, aiohmm, output)
            )

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_hyperparameter_drift_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            output = root / "one_state_ar"
            self._write_references(source, gaussian, aiohmm)
            arguments = self._arguments(source, gaussian, aiohmm, output)
            arguments.extend(["--maximum-absolute-autoregression", "0.90"])

            status = ar_ablation_main(arguments)

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
