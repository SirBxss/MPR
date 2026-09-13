from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MACRO_FIELDS = (
    "model_id",
    "model_family",
    "artifact_version",
    "state_count",
    "maximum_absolute_autoregression",
    "is_frozen_reference",
    "mean_joint_negative_log_likelihood_physical",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_absolute_lag_one_correlation_error",
)

FOLD_FIELDS = (
    "model_id",
    "maximum_absolute_autoregression",
    "held_out_drive_id",
    "sample_mean_prediction_rmse_m",
    "mean_energy_score_m",
    "mean_normalized_sequence_energy_score_m",
    "marginal_95_coverage",
    "absolute_marginal_95_coverage_error",
    "median_absolute_lag_one_correlation_error",
)

MODEL_VERSIONS = {
    "unconditional_gaussian": "0.14.0",
    "conditional_gaussian": "0.14.0",
    "corrected_two_state_aiohmm": "0.15.2",
    "one_state_ar_cap_0_980": "0.15.1",
    "one_state_ar_cap_0_990": "0.15.3",
    "one_state_ar_cap_0_995": "0.15.3",
    "one_state_ar_cap_0_999": "0.15.3",
}


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_comparison(directory: Path, *, two_state_nll: float) -> None:
    directory.mkdir(parents=True)
    macro_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    for index, (model_id, version) in enumerate(MODEL_VERSIONS.items()):
        rmse = 0.30 + index * 0.01
        frame_energy = 0.80 + index * 0.01
        sequence_energy = 0.20 + index * 0.01
        coverage = 0.94 - index * 0.005
        coverage_error = abs(coverage - 0.95)
        lag_one = 0.01 + index * 0.01
        nll = two_state_nll if model_id == "corrected_two_state_aiohmm" else -30.0 + index
        macro_rows.append(
            {
                "model_id": model_id,
                "model_family": "synthetic_test_family",
                "artifact_version": version,
                "state_count": "",
                "maximum_absolute_autoregression": "",
                "is_frozen_reference": "True",
                "mean_joint_negative_log_likelihood_physical": nll,
                "sample_mean_prediction_rmse_m": rmse,
                "mean_energy_score_m": frame_energy,
                "mean_normalized_sequence_energy_score_m": sequence_energy,
                "marginal_95_coverage": coverage,
                "absolute_marginal_95_coverage_error": coverage_error,
                "median_absolute_lag_one_correlation_error": lag_one,
            }
        )
        for drive_index in range(4):
            fold_rows.append(
                {
                    "model_id": model_id,
                    "maximum_absolute_autoregression": "",
                    "held_out_drive_id": f"drive_{drive_index + 1:03d}",
                    "sample_mean_prediction_rmse_m": rmse,
                    "mean_energy_score_m": frame_energy,
                    "mean_normalized_sequence_energy_score_m": sequence_energy,
                    "marginal_95_coverage": coverage,
                    "absolute_marginal_95_coverage_error": coverage_error,
                    "median_absolute_lag_one_correlation_error": lag_one,
                }
            )
    _write_csv(
        directory / "ar_boundary_model_comparison.csv",
        MACRO_FIELDS,
        macro_rows,
    )
    _write_csv(
        directory / "ar_boundary_fold_comparison.csv",
        FOLD_FIELDS,
        fold_rows,
    )


class ModelComparisonReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[2]
        self.script = (
            self.repository / "scripts" / "inspection" / "render_model_comparison.py"
        )

    def _run(self, source: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(self.script),
                str(source),
                "--output",
                str(output),
            ],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_renderer_is_deterministic_and_values_come_from_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            changed_source = root / "changed_source"
            _write_comparison(source, two_state_nll=-42.345)
            _write_comparison(changed_source, two_state_nll=-52.765)

            first = root / "first.svg"
            second = root / "second.svg"
            changed = root / "changed.svg"
            for output in (first, second):
                result = self._run(source, output)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Final model selection authorized: false", result.stdout)
            changed_result = self._run(changed_source, changed)
            self.assertEqual(changed_result.returncode, 0, changed_result.stderr)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotEqual(first.read_bytes(), changed.read_bytes())
            self.assertIn("-42.345", first.read_text(encoding="utf-8"))
            self.assertIn("-52.765", changed.read_text(encoding="utf-8"))
            script = self.script.read_text(encoding="utf-8")
            self.assertNotIn("0.359354", script)
            self.assertNotIn("-42.335", script)

    def test_renderer_fails_closed_on_input_or_output_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            _write_comparison(source, two_state_nll=-42.345)
            macro = source / "ar_boundary_model_comparison.csv"
            macro.write_text(
                macro.read_text(encoding="utf-8").replace(
                    "artifact_version", "unexpected_version_field", 1
                ),
                encoding="utf-8",
            )
            result = self._run(source, root / "invalid.svg")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unexpected CSV schema", result.stderr)
            self.assertFalse((root / "invalid.svg").exists())

            extension_result = self._run(source, root / "invalid.txt")
            self.assertEqual(extension_result.returncode, 2)
            self.assertIn("must end in .png or .svg", extension_result.stderr)


if __name__ == "__main__":
    unittest.main()
