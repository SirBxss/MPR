from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.io.mcap import McapDependencyError
from lane_residuals.workflows import recording_pair_feasibility as workflow
from tests.io.test_recording_pair_diagnostics import diagnostic_count
from tests.io.test_recording_pair_feasibility import estimate, path
from lane_residuals.io.independent_outing_intake import _DecodedReference


class RecordingPairDiagnosticsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        raw = self.root / "raw"
        raw.mkdir()
        rows = []
        for i in range(4):
            p = raw / f"fixture_{i}.mcap"
            p.write_bytes(f"synthetic raw {i}".encode())
            rows.append({"relative_path": p.name, "size_bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        registration = self.root / "registration.json"
        registration.write_text(json.dumps({"files": rows}))
        reg_hash = hashlib.sha256(registration.read_bytes()).hexdigest()
        context = self.root / "context.json"
        context.write_text(json.dumps({"registration_sha256": reg_hash, "files": [
            {"relative_path": row["relative_path"], "size_bytes": row["size_bytes"],
             "sha256_from_registration_not_rehashed": row["sha256"]} for row in rows]}))
        context_hash = hashlib.sha256(context.read_bytes()).hexdigest()
        self.counts, self.details = diagnostic_count([estimate(0, 100, path()), _DecodedReference(0, 107, path())])
        self.preserved = self.root / "preserved.json"
        self.baseline = {
            "contract_revision": workflow.CONTRACT_REVISION, "status": "complete",
            "purpose": "recording_level_geometry_feasibility_without_session_provenance",
            "registration_sha256": reg_hash, "container_context_sha256": context_hash,
            "runtime_source_sha256": workflow.PRESERVED_SOURCE_SHA256, "raw_hashes_verified": True,
            "physical_session_provenance": "unavailable_owner_report_2026-09-20",
            "independent_outing_count": None, "roles_assigned": False, "cohort_lock_created": False,
            "causal_input_availability_checked": False, "residuals_computed": False,
            "recordings": [{"relative_path_private": row["relative_path"], "raw_sha256": row["sha256"],
                "size_bytes": row["size_bytes"], "status": "complete", "failure_code": None,
                "counts": deepcopy(self.counts)} for row in rows],
        }
        self.preserved.write_text(json.dumps(self.baseline))
        self.args = argparse.Namespace(mcap_root=raw, registration=registration, container_context=context,
            preserved_feasibility_report=self.preserved, scratch_directory=self.root,
            output_directory=self.root / "output")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("REGISTRATION_SHA256", reg_hash), ("CONTEXT_SHA256", context_hash),
                            ("PRESERVED_REPORT_SHA256", hashlib.sha256(self.preserved.read_bytes()).hexdigest())):
            self.stack.enter_context(patch.object(workflow, name, value))
        self.stack.enter_context(patch.object(workflow, "version", return_value="test-fixture"))
        self.stack.enter_context(patch.object(workflow, "_available_memory_bytes", return_value=8 * 1024**3))
        self.stack.enter_context(patch.object(workflow.shutil, "disk_usage", return_value=SimpleNamespace(free=12 * 1024**3)))
        self.imports = self.stack.enter_context(patch.object(workflow, "decoder_types"))
        self.inspect = self.stack.enter_context(patch.object(workflow, "inspect_recording_pairs",
            side_effect=lambda *args, **kwargs: self.complete_result()))

    def complete_result(self):
        return {"status": "complete", "failure_code": None,
                "counts": deepcopy(self.counts), "diagnostics": deepcopy(self.details)}

    def test_complete_mode_preserves_original_counts_and_adds_no_roles_or_residuals(self):
        before = self.preserved.read_bytes()
        report, status = workflow.run_recording_pair_feasibility(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(report["contract_revision"], workflow.DIAGNOSTIC_REVISION)
        self.assertEqual(report["preserved_feasibility_sha256"], hashlib.sha256(before).hexdigest())
        self.assertIsNone(report["independent_outing_count"])
        for key in ("roles_assigned", "cohort_lock_created", "causal_input_availability_checked", "residuals_computed"):
            self.assertIs(report[key], False)
        for row in report["recordings"]:
            self.assertIs(row["legacy_counts_match_preserved"], True)
            self.assertEqual(row["counts"], self.counts)
            self.assertEqual(row["diagnostics"], self.details)
        self.assertTrue(all(call.kwargs == {"include_diagnostics": True} for call in self.inspect.call_args_list))
        self.assertEqual(self.preserved.read_bytes(), before)
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()], [workflow.DIAGNOSTIC_OUTPUT_NAME])
        self.assertEqual(json.loads((self.args.output_directory / workflow.DIAGNOSTIC_OUTPUT_NAME).read_text()), report)
        with self.assertRaises(FileExistsError):
            workflow.run_recording_pair_feasibility(self.args)

    def test_any_old_count_drift_is_inconclusive_even_with_same_headline_counts(self):
        def inspect(path, scratch, **kwargs):
            result = self.complete_result()
            if path.name == "fixture_1.mcap":
                result["counts"]["estimate_descriptor_counts"] = {"unexpected": 1}
            return result
        self.inspect.side_effect = inspect
        report, status = workflow.run_recording_pair_feasibility(self.args)
        self.assertEqual(status, 3)
        row = report["recordings"][1]
        self.assertEqual(row["failure_code"], "preserved_counts_mismatch")
        self.assertIs(row["legacy_counts_match_preserved"], False)
        self.assertIsNone(row["counts"])
        self.assertIsNone(row["diagnostics"])
        self.assertIs(report["recordings"][0]["legacy_counts_match_preserved"], True)

    def test_preserved_byte_drift_stops_before_hashing_decoding_or_output(self):
        self.preserved.write_bytes(self.preserved.read_bytes() + b"\n")
        with patch.object(workflow, "sha256_file") as hashing:
            with self.assertRaisesRegex(ValueError, "preserved feasibility SHA-256"):
                workflow.run_recording_pair_feasibility(self.args)
            hashing.assert_not_called()
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_frozen_hash_does_not_replace_identity_completion_and_flag_validation(self):
        invalid = []
        for field, value in (("roles_assigned", 0), ("status", "inconclusive"),
                             ("runtime_source_sha256", "wrong")):
            payload = deepcopy(self.baseline)
            payload[field] = value
            invalid.append(payload)
        payload = deepcopy(self.baseline)
        payload["recordings"][0]["raw_sha256"] = "wrong"
        invalid.append(payload)
        payload = deepcopy(self.baseline)
        payload["recordings"][1] = deepcopy(payload["recordings"][0])
        invalid.append(payload)
        for payload in invalid:
            self.preserved.write_text(json.dumps(payload))
            with self.subTest(payload=payload), patch.object(workflow, "PRESERVED_REPORT_SHA256", hashlib.sha256(self.preserved.read_bytes()).hexdigest()):
                with self.assertRaises(ValueError):
                    workflow.run_recording_pair_feasibility(self.args)
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_incomplete_and_changed_files_discard_details_without_false_count_comparison(self):
        def inspect(path, scratch, **kwargs):
            if path.name == "fixture_1.mcap":
                return {"status": "inconclusive", "failure_code": "memory_limit", "counts": None, "diagnostics": None}
            if path.name == "fixture_2.mcap":
                path.write_bytes(b"changed")
            return self.complete_result()
        self.inspect.side_effect = inspect
        report, status = workflow.run_recording_pair_feasibility(self.args)
        self.assertEqual(status, 3)
        for row in report["recordings"][1:3]:
            self.assertIsNone(row["counts"])
            self.assertIsNone(row["diagnostics"])
            self.assertIsNone(row["legacy_counts_match_preserved"])
        self.assertEqual(report["recordings"][2]["failure_code"], "file_changed_during_decode")

    def test_broken_decoder_import_cannot_orphan_an_output_directory(self):
        self.imports.side_effect = McapDependencyError("broken fixture decoder install")
        with patch.object(workflow, "sha256_file") as hashing:
            with self.assertRaises(McapDependencyError):
                workflow.run_recording_pair_feasibility(self.args)
            hashing.assert_not_called()
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_new_mode_still_rehashes_all_raw_inputs_before_payloads(self):
        target = self.args.mcap_root / "fixture_3.mcap"
        target.write_bytes(b"x" * target.stat().st_size)
        with self.assertRaisesRegex(ValueError, "raw MCAP hash or file state"):
            workflow.run_recording_pair_feasibility(self.args)
        self.inspect.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_cli_passes_explicit_mode_and_preserves_exit_codes(self):
        from lane_residuals.cli.recording_pair_feasibility import main
        arguments = ["raw", "--registration", "reg.json", "--container-context", "context.json",
                     "--scratch-directory", "scratch", "--output-directory", "out",
                     "--preserved-feasibility-report", "pilot.json"]
        with patch("lane_residuals.cli.recording_pair_feasibility._bounded_run", return_value=({"status": "inconclusive"}, 3)) as run:
            self.assertEqual(main(arguments), 3)
            self.assertEqual(run.call_args.args[0].preserved_feasibility_report, Path("pilot.json"))


if __name__ == "__main__":
    unittest.main()
