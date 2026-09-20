from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.workflows import recording_pair_feasibility as workflow


class RecordingPairWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        raw = self.root / "raw"
        raw.mkdir()
        rows = []
        for i in range(4):
            p = raw / f"fixture_{i}.mcap"
            p.write_bytes(f"private synthetic input {i}".encode())
            rows.append({"relative_path": p.name, "size_bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        registration = self.root / "registration.json"
        registration.write_text(json.dumps({"files": rows}))
        reg_hash = hashlib.sha256(registration.read_bytes()).hexdigest()
        context = self.root / "context.json"
        context.write_text(json.dumps({"registration_sha256": reg_hash, "files": [
            {"relative_path": row["relative_path"], "size_bytes": row["size_bytes"],
             "sha256_from_registration_not_rehashed": row["sha256"]} for row in rows]}))
        self.args = argparse.Namespace(mcap_root=raw, registration=registration,
            container_context=context, scratch_directory=self.root, output_directory=self.root / "output")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(workflow, "REGISTRATION_SHA256", reg_hash))
        self.stack.enter_context(patch.object(workflow, "CONTEXT_SHA256", hashlib.sha256(context.read_bytes()).hexdigest()))
        self.stack.enter_context(patch.object(workflow, "version", return_value="test-fixture"))
        self.stack.enter_context(patch.object(workflow, "_available_memory_bytes", return_value=8 * 1024**3))
        self.stack.enter_context(patch.object(workflow.shutil, "disk_usage", return_value=SimpleNamespace(free=12 * 1024**3)))
        self.inspect = self.stack.enter_context(patch.object(workflow, "inspect_recording_pairs",
            return_value={"status": "complete", "failure_code": None,
                          "counts": {"sensor_anchored_h100_pair_count": 0}}))

    def test_complete_zero_geometry_is_not_an_outing_lock_or_failed_execution(self):
        report, status = workflow.run_recording_pair_feasibility(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "complete")
        self.assertIsNone(report["independent_outing_count"])
        for name in ("roles_assigned", "cohort_lock_created", "causal_input_availability_checked", "residuals_computed"):
            self.assertIs(report[name], False)
        self.assertEqual(len(report["recordings"]), 4)
        self.assertEqual(self.inspect.call_count, 4)
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()], [workflow.OUTPUT_NAME])
        with self.assertRaises(FileExistsError):
            workflow.run_recording_pair_feasibility(self.args)

    def test_cli_applies_process_cap_and_restores_stricter_existing_limits(self):
        import resource
        from lane_residuals.cli.recording_pair_feasibility import _bounded_run
        for previous, expected in (((resource.RLIM_INFINITY, resource.RLIM_INFINITY), 4 * 1024**3),
                                   ((2 * 1024**3, 3 * 1024**3), 2 * 1024**3)):
            with patch.object(resource, "getrlimit", return_value=previous), patch.object(resource, "setrlimit") as set_limit, patch.object(
                workflow, "run_recording_pair_feasibility", side_effect=ValueError("test stop")):
                with self.assertRaisesRegex(ValueError, "test stop"):
                    _bounded_run(self.args)
                self.assertEqual(set_limit.call_args_list[0].args, (resource.RLIMIT_AS, (expected, previous[1])))
                self.assertEqual(set_limit.call_args_list[-1].args, (resource.RLIMIT_AS, previous))

    def test_same_size_raw_drift_blocks_all_payload_reads_and_output(self):
        target = self.args.mcap_root / "fixture_3.mcap"
        target.write_bytes(b"x" * target.stat().st_size)
        with self.assertRaisesRegex(ValueError, "hash or file state"):
            workflow.run_recording_pair_feasibility(self.args)
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_report_drift_and_extra_files_are_rejected_before_decode(self):
        original = self.args.container_context.read_bytes()
        self.args.container_context.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "context SHA-256"):
            workflow.run_recording_pair_feasibility(self.args)
        self.args.container_context.write_bytes(original)
        (self.args.mcap_root / "extra.MCAP").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "four-file"):
            workflow.run_recording_pair_feasibility(self.args)
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_resource_guard_is_usage_failure_before_any_raw_scan(self):
        with patch.object(workflow, "_available_memory_bytes", return_value=2 * 1024**3), patch.object(workflow, "sha256_file") as hashing:
            with self.assertRaisesRegex(ValueError, "MemAvailable"):
                workflow.run_recording_pair_feasibility(self.args)
            hashing.assert_not_called()
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_incomplete_file_and_mutation_have_null_counts(self):
        def inspect(path, scratch):
            if path.name == "fixture_1.mcap":
                return {"status": "inconclusive", "failure_code": "memory_limit", "counts": None}
            if path.name == "fixture_2.mcap":
                path.write_bytes(b"modified")
            return {"status": "complete", "failure_code": None, "counts": {"sensor_anchored_h100_pair_count": 5}}
        self.inspect.side_effect = inspect
        report, status = workflow.run_recording_pair_feasibility(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["recordings"][1]["counts"])
        self.assertIsNone(report["recordings"][2]["counts"])
        self.assertEqual(report["recordings"][2]["failure_code"], "file_changed_during_decode")
        self.assertFalse(report["cohort_lock_created"])


if __name__ == "__main__":
    unittest.main()
