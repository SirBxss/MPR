import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.workflows import velocity_timing_pilot as workflow
from tests.io.velocity_timing_fixture import prepare


class PilotWorkflowTests(unittest.TestCase):
    def setUp(self):
        try:
            from lane_residuals.io.recording_decode_check import check_dependencies
            check_dependencies()
        except (ImportError, ValueError):
            self.skipTest("optional MCAP extras not installed")
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request, self.pin, self.raw = prepare(self.root)
        self.source = {"commit": "synthetic", "tree": "synthetic"}

    def run_pilot(self, output):
        return workflow.run(project=self.root, request_path=self.request, request_sha256=self.pin,
            gate_path=self.root/"gate.json", gate_sha256="f"*64, expected_runtime="r"*64, output=output)

    def mocks(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.object(workflow.gate, "validate", return_value=self.source))
        stack.enter_context(patch.object(workflow.gate, "runtime_sha256", return_value="r"*64))
        stack.enter_context(patch.object(workflow.gate, "git", return_value="synthetic"))
        stack.enter_context(patch.object(workflow, "resources", return_value={"synthetic": True}))
        return stack

    def test_native_synthetic_decode_analysis_and_python_plots(self):
        before = self.raw.read_bytes()
        with self.mocks():
            report = self.run_pilot(self.root/"result")
        self.assertEqual(self.raw.read_bytes(), before)
        self.assertEqual(report["status"], "complete_local_exploratory_timing_pilot")
        self.assertTrue(report["current_full_raw_hash_verified"])
        self.assertFalse(report["training_dataset_modified"])
        self.assertEqual(report["decode"]["messages_retained_in_padded_log_window"], 6)
        self.assertGreater((self.root/"result/01_velocity_observations.png").stat().st_size, 1000)
        self.assertGreater((self.root/"result/02_local_support_screen.png").stat().st_size, 1000)

    def test_gate_failure_precedes_raw_inspection_and_attempt_creation(self):
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path.suffix == ".mcap":
                raise AssertionError("raw path inspected before gate")
            return original_resolve(path, *args, **kwargs)
        with patch.object(workflow.gate, "validate", side_effect=ValueError("pilot_test_gate")), \
                patch.object(Path, "resolve", resolve), \
                patch.object(workflow, "verify_raw", side_effect=AssertionError("raw touched")), self.assertRaisesRegex(ValueError, "test_gate"):
            self.run_pilot(self.root/"result")
        self.assertFalse((self.root/"result").exists())
        self.assertFalse((self.root/"outputs").exists())

    def test_failed_hash_preserves_receipt_and_denies_renamed_retry(self):
        with self.mocks(), patch.object(workflow, "verify_raw", side_effect=ValueError("pilot_test_hash")), self.assertRaisesRegex(ValueError, "test_hash"):
            self.run_pilot(self.root/"result")
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["status"], "incomplete")
        with self.mocks(), self.assertRaises(FileExistsError):
            self.run_pilot(self.root/"renamed")

    def test_interrupt_retains_started_attempt_and_incomplete_report(self):
        with self.mocks(), patch.object(workflow, "verify_raw", side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.run_pilot(self.root/"result")
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["failure_class"], "KeyboardInterrupt")

    def test_modified_raw_file_cannot_produce_complete_result(self):
        original = workflow.decode_window
        def changed(*args):
            value = original(*args)
            with self.raw.open("ab") as stream:
                stream.write(b"modified")
            return value
        with self.mocks(), patch.object(workflow, "decode_window", side_effect=changed), self.assertRaisesRegex(ValueError, "raw_changed_during_decode"):
            self.run_pilot(self.root/"result")
