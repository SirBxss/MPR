import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.workflows.velocity_source_ties import run
from tests.io.velocity_history_fixture import fixture, write_archive


class SourceTieWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.archive, self.pin = write_archive(self.base, fixture(self.base))

    def test_diagnostic_output_and_exact_input_preservation(self):
        with patch("lane_residuals.reporting.velocity_source_ties.plot"):
            report = run(self.archive, self.pin, self.base/"result")
        self.assertEqual(report["status"], "complete_cached_source_tie_audit")
        for key in ("raw_recording_opened", "new_raw_payload_decoded", "model_fitted", "speed_feature_adopted", "new_training_arrays_exported"):
            self.assertIs(report[key], False)
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(), self.pin)
        self.assertEqual({p.name for p in (self.base/"result").iterdir()},
            {"report.private.json", "paired_frames.private.csv", "support_comparison.private.csv"})

    def test_existing_output_and_bad_input_create_no_new_output(self):
        output = self.base/"existing"; output.mkdir()
        with patch("lane_residuals.workflows.velocity_source_ties.load_return", side_effect=AssertionError("not called")):
            with self.assertRaises(FileExistsError): run(self.archive, self.pin, output)
        with self.assertRaises(ValueError): run(self.archive, "0"*64, self.base/"invalid")
        self.assertFalse((self.base/"invalid").exists())

    def test_failure_preserves_incomplete_diagnostic(self):
        with patch("lane_residuals.reporting.velocity_source_ties.plot", side_effect=RuntimeError("synthetic plot failure")):
            with self.assertRaises(RuntimeError): run(self.archive, self.pin, self.base/"result")
        report = json.loads((self.base/"result/report.private.json").read_text())
        self.assertEqual(report["status"], "incomplete_cached_source_tie_audit")
        self.assertEqual(report["failure_class"], "RuntimeError")

    def test_native_cli_uses_cached_zip_and_outputs_python_figures(self):
        environment = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MPLBACKEND="Agg")
        result = subprocess.run([sys.executable, "-m", "lane_residuals.cli.velocity_source_ties",
            "--result-zip", str(self.archive), "--result-sha256", self.pin, "--output", str(self.base/"native")],
            env=environment, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("complete_cached_source_tie_audit", result.stdout)
        for extension in ("png", "pdf"):
            self.assertGreater((self.base/f"native/source_tie_comparison.{extension}").stat().st_size, 1000)
        self.assertFalse(list(self.base.rglob("*.mcap")))
        self.assertFalse(list((self.base/"native").rglob("*.npz")))


if __name__ == "__main__":
    unittest.main()
