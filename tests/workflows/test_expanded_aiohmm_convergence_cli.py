import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_aiohmm_convergence import (
    _parser as convergence_parser,
    main as convergence_main,
)
from lane_residuals.cli.expanded_ar_ablation import main as ar_ablation_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from lane_residuals.io.expanded_sequence_dataset import sha256_file
from lane_residuals.modeling.aiohmm import (
    ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE,
)
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class ExpandedAIOHMMConvergenceWorkflowTests(unittest.TestCase):
    def test_help_text_formats_without_percent_interpolation_error(self) -> None:
        help_text = convergence_parser().format_help()

        self.assertIn("unchanged fixed 5% v0.15 occupancy floor", help_text)

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
        cls,
        source: Path,
        gaussian: Path,
        aiohmm: Path,
        one_state: Path,
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
        one_state_status = ar_ablation_main(
            [
                str(source),
                "--gaussian-directory",
                str(gaussian),
                "--aiohmm-directory",
                str(aiohmm),
                "--output-directory",
                str(one_state),
                *cls._model_arguments(),
            ]
        )
        if one_state_status != 0:
            raise AssertionError("v0.15.1 fixture generation failed")

    @classmethod
    def _arguments(
        cls,
        source: Path,
        gaussian: Path,
        aiohmm: Path,
        one_state: Path,
        output: Path,
    ) -> list[str]:
        return [
            str(source),
            "--gaussian-directory",
            str(gaussian),
            "--aiohmm-directory",
            str(aiohmm),
            "--one-state-ar-directory",
            str(one_state),
            "--output-directory",
            str(output),
            *cls._model_arguments(),
        ]

    def test_command_changes_only_the_convergence_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            output = root / "convergence"
            self._write_references(source, gaussian, aiohmm, one_state)

            status = convergence_main(
                self._arguments(source, gaussian, aiohmm, one_state, output)
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "two_state_convergence_comparison.csv",
                    "two_state_convergence_diagnostics.png",
                    "two_state_convergence_evaluation.csv",
                    "two_state_convergence_fold_models.json",
                    "two_state_convergence_frame_evaluation.csv",
                    "two_state_convergence_model.json",
                    "two_state_convergence_restart_evaluation.csv",
                    "two_state_convergence_state_evaluation.csv",
                    "two_state_convergence_station_evaluation.csv",
                    "two_state_convergence_summary.json",
                },
            )
            summary = json.loads(
                (output / "two_state_convergence_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["version"], "0.15.2")
            self.assertEqual(summary["state_count"], 2)
            self.assertEqual(
                summary["configuration"]["convergence_criterion"],
                ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE,
            )
            self.assertEqual(
                summary["configuration"]["convergence_tolerance"], 1e-3
            )
            self.assertEqual(
                set(summary["configuration_differences_from_v0150"]),
                {"convergence_criterion", "convergence_tolerance"},
            )
            self.assertEqual(summary["reference_two_state_aiohmm_version"], "0.15.0")
            self.assertEqual(summary["one_state_ar_reference_version"], "0.15.1")
            self.assertFalse(summary["ar_boundary_changed"])
            self.assertFalse(summary["new_model_family_introduced"])
            self.assertEqual(
                summary["selected_fit_convergence_comparison"]["selected_fit_count"],
                5,
            )
            self.assertEqual(
                set(summary["paired_sample_metrics_vs_one_state_ar"]["metrics"]),
                {
                    "sample_mean_prediction_rmse_m",
                    "mean_energy_score_m",
                    "mean_normalized_sequence_energy_score_m",
                    "absolute_marginal_95_coverage_error",
                    "median_absolute_lag_one_correlation_error",
                },
            )
            with (output / "two_state_convergence_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertTrue(
                all(
                    row[
                        "corrected_last_absolute_log_probability_improvement_per_frame_standardized"
                    ]
                    for row in rows
                )
            )
            self.assertGreater(
                (output / "two_state_convergence_diagnostics.png").stat().st_size,
                0,
            )
            self.assertEqual(
                summary["output_files_sha256"],
                {
                    path.name: sha256_file(path)
                    for path in output.iterdir()
                    if path.name != "two_state_convergence_summary.json"
                },
            )

    def test_tampered_one_state_reference_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            output = root / "convergence"
            self._write_references(source, gaussian, aiohmm, one_state)
            with (one_state / "one_state_ar_evaluation.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("tampered\n")

            status = convergence_main(
                self._arguments(source, gaussian, aiohmm, one_state, output)
            )

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_nonconvergence_hyperparameter_drift_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            output = root / "convergence"
            self._write_references(source, gaussian, aiohmm, one_state)
            arguments = self._arguments(
                source, gaussian, aiohmm, one_state, output
            )
            arguments.extend(["--maximum-absolute-autoregression", "0.90"])

            status = convergence_main(arguments)

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_tolerance_drift_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            output = root / "convergence"
            self._write_references(source, gaussian, aiohmm, one_state)
            arguments = self._arguments(
                source, gaussian, aiohmm, one_state, output
            )
            arguments.extend(["--convergence-tolerance", "0.0005"])

            status = convergence_main(arguments)

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
