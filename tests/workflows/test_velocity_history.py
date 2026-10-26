import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.workflows.velocity_history import run
from tests.io.velocity_history_fixture import fixture, write_archive


class CachedHistoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.archive, self.pin = write_archive(self.base, fixture(self.base))

    def test_success_outputs_only_diagnostics_and_preserves_input(self):
        with patch("lane_residuals.reporting.velocity_history.plot"):
            report = run(self.archive, self.pin, self.base/"result")
        self.assertEqual(report["status"], "complete_cached_history_diagnostic")
        self.assertFalse(report["raw_recording_opened"])
        self.assertFalse(report["model_fitted"])
        self.assertFalse(report["speed_feature_adopted"])
        self.assertTrue(report["original_analysis_replayed"])
        self.assertTrue((self.base/"result/history_frames.private.csv").exists())
        self.assertFalse(list((self.base/"result").glob("*.npz")))

    def test_existing_output_refused_before_reading_input(self):
        output = self.base/"result"; output.mkdir()
        with patch("lane_residuals.workflows.velocity_history.load_return", side_effect=AssertionError("not called")):
            with self.assertRaises(FileExistsError): run(self.archive, self.pin, output)

    def test_invalid_pin_creates_no_output(self):
        with self.assertRaises(ValueError): run(self.archive, "0"*64, self.base/"result")
        self.assertFalse((self.base/"result").exists())

    def test_plot_failure_preserves_incomplete_cached_report(self):
        with patch("lane_residuals.reporting.velocity_history.plot", side_effect=RuntimeError("synthetic plot failure")):
            with self.assertRaises(RuntimeError): run(self.archive, self.pin, self.base/"result")
        report = json.loads((self.base/"result/report.private.json").read_text())
        self.assertEqual(report["status"], "incomplete_cached_analysis")
        self.assertFalse(report["new_raw_payload_decoded"])

    def test_native_cli_produces_python_plots_without_raw_file(self):
        environment = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MPLBACKEND="Agg")
        process = subprocess.run([sys.executable, "-m", "lane_residuals.cli.velocity_history", "--result-zip", str(self.archive),
            "--result-sha256", self.pin, "--output", str(self.base/"native")], env=environment, capture_output=True, text=True, timeout=45)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("complete_cached_history_diagnostic", process.stdout)
        self.assertGreater((self.base/"native/history_comparison.png").stat().st_size, 1000)
        self.assertGreater((self.base/"native/history_comparison.pdf").stat().st_size, 1000)
        self.assertFalse(list(self.base.rglob("*.mcap")))


if __name__ == "__main__":
    unittest.main()
