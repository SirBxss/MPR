import json
import hashlib
import os
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
        original = workflow.decode_prepared
        def changed(*args):
            value = original(*args)
            with self.raw.open("ab") as stream:
                stream.write(b"modified")
            return value
        with self.mocks(), patch.object(workflow, "decode_prepared", side_effect=changed), self.assertRaisesRegex(ValueError, "raw_changed_during_decode"):
            self.run_pilot(self.root/"result")

    def test_reformatted_request_cannot_repeat_a_started_design(self):
        with self.mocks(), patch.object(workflow, "verify_raw", side_effect=ValueError("pilot_test_hash")), self.assertRaises(ValueError):
            self.run_pilot(self.root/"result")
        self.request.write_text(json.dumps(json.loads(self.request.read_text()), indent=3))
        new_pin = hashlib.sha256(self.request.read_bytes()).hexdigest()
        self.assertNotEqual(new_pin, self.pin)
        self.pin = new_pin
        with self.mocks(), patch.object(workflow, "prepare_window", side_effect=AssertionError("metadata reread")), self.assertRaises(FileExistsError):
            self.run_pilot(self.root/"renamed")

    def test_budget_failure_creates_no_claim_and_does_not_hash(self):
        with self.mocks(), patch.dict(workflow.LIMITS, selected_chunk_read_bytes=0), \
                patch.object(workflow, "verify_raw", side_effect=AssertionError("hash before plan")), self.assertRaisesRegex(ValueError, "planned_window_budget"):
            self.run_pilot(self.root/"result")
        self.assertFalse((self.root/"outputs").exists())
        self.assertFalse((self.root/"result").exists())

    def test_fifo_is_rejected_without_claim_or_blocking_open(self):
        self.raw.unlink()
        os.mkfifo(self.raw)
        with self.mocks(), self.assertRaisesRegex(ValueError, "regular_registered_raw"):
            self.run_pilot(self.root/"result")
        self.assertFalse((self.root/"outputs").exists())

    def test_figure_legend_names_the_combined_mask(self):
        from lane_residuals.reporting.velocity_timing import plot
        from lane_residuals.domain.velocity_timing import TOPICS
        import matplotlib.pyplot as plt
        screens = [{"topic": topic, "edp_log_ns": "100", "recorded_clock_screen_met": True,
            "local_hypothetical_complete": False, "old_complete": False, "old_speed_mps": None} for topic in TOPICS]
        stats = {topic: {"local_hypothetical_complete_under_screen": {"maximum_span_s": 0.}} for topic in TOPICS}
        report = {"window_start_log_ns": "100", "window_end_log_ns": "12000000100",
            "analysis": {"local_original_complete": {"maximum_span_s": 0.}, "topics": stats}}
        try:
            with patch.object(plt, "close"):
                plot(self.root, [], screens, report)
                axes = plt.figure(plt.get_fignums()[-1]).axes[0]
                labels = axes.get_legend_handles_labels()[1]
                self.assertTrue(all("local hypothetical complete" in label for label in labels[:2]))
                self.assertFalse(any("raised = screen met" in label for label in labels))
                self.assertEqual(axes.collections[0].get_offsets()[0, 1], 0.)
        finally:
            plt.close("all")
