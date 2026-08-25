import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from lane_residuals.cli.expanded_aiohmm import main as aiohmm_main
from lane_residuals.cli.expanded_gaussian import main as gaussian_main
from lane_residuals.workflows.expanded_aiohmm import _result_classification
from tests.io.test_expanded_modeling_dataset import write_v0131_fixture


V015_PRE_REFACTOR_PARITY_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v015_pre_refactor_parity.json"
)


def _normalized_json(
    path: Path,
    omitted_keys: set[str],
) -> object:
    def normalize(value):
        if isinstance(value, dict):
            return {
                key: normalize(item)
                for key, item in sorted(value.items())
                if key not in omitted_keys
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return normalize(json.loads(path.read_text(encoding="utf-8")))


def _assert_json_numerically_close(
    expected: object,
    actual: object,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
    path: str = "$",
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError(
                f"{path}: expected object, got {type(actual).__name__}"
            )
        if set(expected) != set(actual):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            raise AssertionError(
                f"{path}: object keys differ; missing={missing}, extra={extra}"
            )
        for key in sorted(expected):
            _assert_json_numerically_close(
                expected[key],
                actual[key],
                relative_tolerance=relative_tolerance,
                absolute_tolerance=absolute_tolerance,
                path=f"{path}.{key}",
            )
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            raise AssertionError(
                f"{path}: expected list, got {type(actual).__name__}"
            )
        if len(expected) != len(actual):
            raise AssertionError(
                f"{path}: list lengths differ; expected={len(expected)}, "
                f"actual={len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual)
        ):
            _assert_json_numerically_close(
                expected_item,
                actual_item,
                relative_tolerance=relative_tolerance,
                absolute_tolerance=absolute_tolerance,
                path=f"{path}[{index}]",
            )
        return
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            raise AssertionError(
                f"{path}: expected numeric value, got {type(actual).__name__}"
            )
        if not math.isclose(
            expected,
            float(actual),
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            raise AssertionError(
                f"{path}: numerical parity failed; expected={expected!r}, "
                f"actual={actual!r}, rtol={relative_tolerance}, "
                f"atol={absolute_tolerance}"
            )
        return
    if type(expected) is not type(actual) or expected != actual:
        raise AssertionError(
            f"{path}: exact parity failed; expected={expected!r}, actual={actual!r}"
        )


class ExpandedAIOHMMWorkflowTests(unittest.TestCase):
    def test_numeric_parity_failure_reports_the_drifting_path(self) -> None:
        with self.assertRaisesRegex(
            AssertionError, r"\$\.models\[1\]\.coefficient"
        ):
            _assert_json_numerically_close(
                {"models": [{"coefficient": 0.1}, {"coefficient": 0.2}]},
                {"models": [{"coefficient": 0.1}, {"coefficient": 0.21}]},
                relative_tolerance=1e-9,
                absolute_tolerance=1e-10,
            )

    def test_result_classification_requires_explicit_temporal_evidence(self) -> None:
        complete = {
            "frame_energy_score_improved": True,
            "sequence_energy_score_improved": True,
            "lag_one_error_improved": True,
            "coverage_error_not_worse": True,
            "no_failed_restart": True,
            "all_selected_fits_converged": True,
        }
        temporal_only = dict(complete, frame_energy_score_improved=False)
        no_temporal_gain = dict(temporal_only, lag_one_error_improved=False)

        self.assertEqual(
            _result_classification(complete), "full_generative_acceptance_met"
        )
        self.assertEqual(
            _result_classification(temporal_only),
            "temporal_dependence_improved_but_full_generative_acceptance_not_met",
        )
        self.assertEqual(
            _result_classification(no_temporal_gain),
            "development_acceptance_not_met",
        )

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
                    "development_acceptance_not_met",
                },
            )
            self.assertEqual(
                summary["all_development_acceptance_checks_passed"],
                all(summary["development_acceptance_checks"].values()),
            )
            self.assertEqual(
                summary["evaluation_scheme"],
                "leave_one_clean_recording_group_out_within_one_outing",
            )
            self.assertFalse(
                summary["primary_group_independence"][
                    "journey_level_generalization_estimated"
                ]
            )
            fold_diagnostics = summary["sequence_energy_fold_diagnostics"]
            self.assertEqual(fold_diagnostics["fold_count"], 4)
            self.assertEqual(
                fold_diagnostics["aiohmm_better_fold_count"]
                + fold_diagnostics["conditional_gaussian_better_fold_count"]
                + fold_diagnostics["tied_fold_count"],
                4,
            )
            self.assertEqual(
                set(
                    fold_diagnostics[
                        "aiohmm_minus_conditional_gaussian_by_group_m"
                    ]
                ),
                {"drive_001", "drive_002", "drive_003", "drive_004"},
            )
            self.assertEqual(
                summary["constraint_boundary_diagnostics"]["complete_fit_count"],
                5,
            )
            self.assertTrue(
                summary["joint_likelihood_is_proper_observed_history_density_score"]
            )
            self.assertFalse(
                summary["joint_likelihood_measures_free_running_generation"]
            )
            self.assertTrue(
                (output / "expanded_aiohmm_diagnostics.png").stat().st_size > 0
            )

            with (output / "expanded_aiohmm_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluation_rows = list(csv.DictReader(handle))
            self.assertEqual(len(evaluation_rows), 6)
            self.assertEqual(
                sum(row["scope"] == "held_out_drive" for row in evaluation_rows), 4
            )
            held_out_rows = [
                row for row in evaluation_rows if row["scope"] == "held_out_drive"
            ]
            self.assertEqual(
                summary["primary_macro_drive_metrics"][
                    "maximum_autoregressive_coefficient"
                ],
                max(
                    float(row["maximum_autoregressive_coefficient"])
                    for row in held_out_rows
                ),
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

    def test_refactored_v015_matches_pre_refactor_reference(self) -> None:
        reference = json.loads(
            V015_PRE_REFACTOR_PARITY_REFERENCE.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_v0131_fixture(root / "v0131")
            gaussian = root / "gaussian"
            output = root / "aiohmm"
            self._write_gaussian(source, gaussian)

            status = aiohmm_main(self._arguments(source, gaussian, output))

            self.assertEqual(status, 0)
            for name, contract in reference["normalized_json_outputs"].items():
                expected = json.loads(
                    (
                        V015_PRE_REFACTOR_PARITY_REFERENCE.parent
                        / contract["reference_file"]
                    ).read_text(encoding="utf-8")
                )
                _assert_json_numerically_close(
                    expected,
                    _normalized_json(
                        output / name,
                        set(contract["omitted_keys"]),
                    ),
                    relative_tolerance=float(reference["relative_tolerance"]),
                    absolute_tolerance=float(reference["absolute_tolerance"]),
                )

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
