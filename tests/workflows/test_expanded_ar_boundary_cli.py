import csv
import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_aiohmm_convergence import (
    main as convergence_main,
)
from lane_residuals.cli.expanded_ar_ablation import main as ar_ablation_main
from lane_residuals.cli.expanded_ar_boundary import main as ar_boundary_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from lane_residuals.io.expanded_sequence_dataset import sha256_file
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


class ExpandedARBoundaryWorkflowTests(unittest.TestCase):
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
        convergence: Path,
    ) -> None:
        if (
            gaussian_main(
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
            != 0
        ):
            raise AssertionError("v0.14 fixture generation failed")
        if (
            aiohmm_main(
                [
                    str(source),
                    "--gaussian-directory",
                    str(gaussian),
                    "--output-directory",
                    str(aiohmm),
                    *cls._model_arguments(),
                ]
            )
            != 0
        ):
            raise AssertionError("v0.15 fixture generation failed")
        if (
            ar_ablation_main(
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
            != 0
        ):
            raise AssertionError("v0.15.1 fixture generation failed")
        if (
            convergence_main(
                [
                    str(source),
                    "--gaussian-directory",
                    str(gaussian),
                    "--aiohmm-directory",
                    str(aiohmm),
                    "--one-state-ar-directory",
                    str(one_state),
                    "--output-directory",
                    str(convergence),
                    *cls._model_arguments(),
                ]
            )
            != 0
        ):
            raise AssertionError("v0.15.2 fixture generation failed")

    @classmethod
    def _arguments(
        cls,
        source: Path,
        gaussian: Path,
        aiohmm: Path,
        one_state: Path,
        convergence: Path,
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
            "--two-state-convergence-directory",
            str(convergence),
            "--output-directory",
            str(output),
            *cls._model_arguments(),
        ]

    def test_command_varies_only_the_predeclared_ar_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            convergence = root / "convergence"
            output = root / "ar_boundary"
            self._write_references(
                source, gaussian, aiohmm, one_state, convergence
            )

            status = ar_boundary_main(
                self._arguments(
                    source,
                    gaussian,
                    aiohmm,
                    one_state,
                    convergence,
                    output,
                )
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "candidates",
                    "ar_boundary_model_comparison.csv",
                    "ar_boundary_fold_comparison.csv",
                    "ar_boundary_station_comparison.csv",
                    "ar_boundary_sensitivity_diagnostics.png",
                    "ar_boundary_sensitivity_summary.json",
                },
            )
            candidate_names = {
                "one_state_ar_cap_0_990",
                "one_state_ar_cap_0_995",
                "one_state_ar_cap_0_999",
            }
            self.assertEqual(
                {path.name for path in (output / "candidates").iterdir()},
                candidate_names,
            )
            for name in candidate_names:
                candidate = output / "candidates" / name
                self.assertEqual(len([path for path in candidate.iterdir()]), 9)
                payload = json.loads(
                    (candidate / "one_state_ar_summary.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(payload["version"], "0.15.3")
                self.assertEqual(payload["state_count"], 1)
                self.assertEqual(
                    set(payload["only_configuration_difference_from_v0151"]),
                    {"maximum_absolute_autoregression"},
                )

            summary = json.loads(
                (output / "ar_boundary_sensitivity_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["version"], "0.15.3")
            self.assertEqual(
                summary["predeclared_ar_ceilings"],
                [0.98, 0.99, 0.995, 0.999],
            )
            self.assertEqual(
                summary["only_varied_configuration_field"],
                "maximum_absolute_autoregression",
            )
            self.assertTrue(
                summary[
                    "unconditional_gaussian_included_in_consolidated_comparison"
                ]
            )
            self.assertFalse(summary["final_model_selection_authorized"])
            self.assertFalse(
                summary["recorded_coverage_hypothesis"]
                ["used_as_acceptance_or_selection_target"]
            )
            self.assertEqual(
                summary["output_files_sha256"],
                {
                    str(path.relative_to(output).as_posix()): sha256_file(path)
                    for path in output.rglob("*")
                    if path.is_file()
                    and path.name != "ar_boundary_sensitivity_summary.json"
                },
            )

            with (output / "ar_boundary_model_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                model_rows = list(csv.DictReader(handle))
            self.assertEqual(len(model_rows), 7)
            self.assertEqual(
                {row["model_id"] for row in model_rows},
                {
                    "unconditional_gaussian",
                    "conditional_gaussian",
                    "corrected_two_state_aiohmm",
                    "one_state_ar_cap_0_980",
                    *candidate_names,
                },
            )
            with (output / "ar_boundary_fold_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                fold_rows = list(csv.DictReader(handle))
            self.assertEqual(len(fold_rows), 7 * 4)
            with (output / "ar_boundary_station_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                station_rows = list(csv.DictReader(handle))
            self.assertEqual(len(station_rows), 4 * 21)
            self.assertGreater(
                (output / "ar_boundary_sensitivity_diagnostics.png").stat().st_size,
                0,
            )

    def test_tampered_v0152_reference_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            convergence = root / "convergence"
            output = root / "ar_boundary"
            self._write_references(
                source, gaussian, aiohmm, one_state, convergence
            )
            with (convergence / "two_state_convergence_evaluation.csv").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write("tampered\n")

            status = ar_boundary_main(
                self._arguments(
                    source,
                    gaussian,
                    aiohmm,
                    one_state,
                    convergence,
                    output,
                )
            )

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_nonbaseline_cli_ceiling_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            aiohmm = root / "aiohmm"
            one_state = root / "one_state"
            convergence = root / "convergence"
            output = root / "ar_boundary"
            self._write_references(
                source, gaussian, aiohmm, one_state, convergence
            )
            arguments = self._arguments(
                source,
                gaussian,
                aiohmm,
                one_state,
                convergence,
                output,
            )
            arguments.extend(["--maximum-absolute-autoregression", "0.90"])

            status = ar_boundary_main(arguments)

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
