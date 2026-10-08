import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.cli import recording_ingestion as cli
from lane_residuals.workflows import recording_ingestion as registration
from lane_residuals.workflows import recording_inventory as workflow
from lane_residuals.io import recording_inventory as inventory
from tests.domain.test_recording_ingestion import specification
from tests.io.test_recording_inventory import fixture


class InventoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.raw = self.root/"arbitrary basename.mcap"; self.raw.write_bytes(fixture())
        self.specification = self.root/"source.private.json"
        self.spec = specification(str(self.raw))
        self.directory = self.root/"registration"
        self.args = argparse.Namespace(registration_directory=self.directory, scratch_directory=self.root,
                                       output_directory=self.root/"inventory")
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(registration, "_available_memory_bytes", return_value=8*1024**3))
        stack.enter_context(patch.object(registration.shutil, "disk_usage", return_value=SimpleNamespace(free=12*1024**3)))

    def register(self):
        self.specification.write_text(json.dumps(self.spec))
        return registration.run_registration(argparse.Namespace(specification=self.specification, output_directory=self.directory))

    def test_generic_inventory_uses_existing_registration_and_exports_only_metadata(self):
        self.register()
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        with patch.object(registration, "decoder_types") as decoder, patch.object(workflow, "sha256_stream", wraps=workflow.sha256_stream) as hasher:
            report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(hasher.call_count, 1)
        decoder.assert_not_called()
        self.assertEqual(report["recordings"][0]["inventory"]["topics"][0]["advertised_message_count"], 3)
        self.assertIsNone(report["independent_outing_count"])
        for key in ("message_payloads_decoded", "geometry_readiness_assessed", "residual_profiles_constructed",
                    "numeric_conditions_exported", "reference_independence_proven", "model_fitted", "roles_assigned",
                    "raw_cache_deletion_authorized"):
            self.assertIs(report[key], False)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()], [workflow.REPORT_NAME])
        self.assertNotIn(str(self.raw), json.dumps(report))
        self.assertNotIn("PRIVATE", json.dumps(report))
        with self.assertRaisesRegex(ValueError, "new_absent_output"):
            workflow.run_inventory(self.args)

    def test_dangling_output_symlink_is_rejected_before_hashing(self):
        self.register()
        self.args.output_directory.symlink_to(self.root/"missing")
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "new_absent_output"):
                workflow.run_inventory(self.args)
            hasher.assert_not_called()

    def test_tampering_and_raw_identity_mismatch_stop_before_summary_and_output(self):
        self.register()
        spec = self.directory/registration.SPECIFICATION_NAME
        before = spec.read_bytes(); spec.write_bytes(before+b" ")
        with patch.object(workflow, "read_inventory") as reader:
            with self.assertRaisesRegex(ValueError, "registration_lineage_mismatch"):
                workflow.run_inventory(self.args)
            spec.write_bytes(before)
            self.raw.write_bytes(b"X"*self.raw.stat().st_size)
            with self.assertRaisesRegex(ValueError, "registered_raw_hash_or_size_changed"):
                workflow.run_inventory(self.args)
            reader.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_initial_resource_failure_is_exit_two_without_hash_or_output(self):
        self.register()
        with patch.object(registration, "_available_memory_bytes", return_value=1), patch.object(workflow, "sha256_stream") as hasher:
            status = cli.main(["inventory", "--registration-directory", str(self.directory),
                "--scratch-directory", str(self.root), "--output-directory", str(self.args.output_directory)])
        self.assertEqual(status, 2); hasher.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())
        with patch.object(registration.shutil, "disk_usage", return_value=SimpleNamespace(free=1)):
            with self.assertRaisesRegex(ValueError, "scratch_free_space_below_10gib"):
                workflow.run_inventory(self.args)

    def test_post_hash_resource_failure_is_preserved_inconclusive_with_null_inventory(self):
        self.register()
        with patch.object(registration, "_available_memory_bytes", side_effect=[8*1024**3, 1]), patch.object(workflow, "read_inventory") as reader:
            report, status = workflow.run_inventory(self.args)
            reader.assert_not_called()
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "available_memory_below_6gib")
        self.assertIsNone(report["recordings"][0]["inventory"])

    def test_crc_and_late_parser_failures_never_publish_prefix_counts_or_exception_text(self):
        self.register()
        for error in (ValueError("private coordinates and path"), MemoryError()):
            with patch.object(workflow, "read_inventory", side_effect=error):
                report, status = workflow.run_inventory(self.args)
            self.assertEqual(status, 3)
            self.assertIsNone(report["recordings"][0]["inventory"])
            self.assertNotIn("private coordinates", json.dumps(report))
            self.args.output_directory = self.root/("next"+type(error).__name__)
        raw = bytearray(fixture()); raw[-40] ^= 1; self.raw.write_bytes(raw)
        # Register this new fixture in a separate immutable registration.
        self.directory = self.root/"crc_registration"; self.register()
        self.args.registration_directory = self.directory
        report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "inventory_summary_crc_mismatch")

    def test_same_verified_descriptor_is_used_and_path_replacement_discards_inventory(self):
        self.register()
        def inspect(stream, size):
            self.assertEqual(workflow.sha256_stream(stream), hashlib.sha256(fixture()).hexdigest())
            other = self.root/"replacement"; other.write_bytes(fixture(crc=False)); os.replace(other, self.raw)
            return inventory.read_inventory(stream, size)
        with patch.object(workflow, "read_inventory", side_effect=inspect):
            report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "file_changed_before_report_publish")
        self.assertIsNone(report["recordings"][0]["inventory"])

    def test_registration_mutation_after_summary_discards_the_whole_result(self):
        self.register()
        def inspect(stream, size):
            value = inventory.read_inventory(stream, size)
            source = self.directory/registration.SPECIFICATION_NAME
            source.write_bytes(source.read_bytes()+b" ")
            return value
        with patch.object(workflow, "read_inventory", side_effect=inspect):
            report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "registration_changed_before_report_publish")
        self.assertIsNone(report["recordings"][0]["inventory"])

    def test_multiple_recordings_keep_individual_results_without_outing_or_pooled_counts(self):
        other = self.root/"second.mcap"; other.write_bytes(fixture(crc=False))
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="second", local_path_private=str(other))
        self.spec["recordings"].append(second); self.register()
        report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(report["technical_recording_count"], 2)
        self.assertIsNone(report["independent_outing_count"])
        self.assertEqual([r["inventory"]["summary_crc_status"] for r in report["recordings"]], ["validated", "unavailable"])
        self.assertNotIn("pooled_counts", report)

    def test_later_file_processing_invalidates_earlier_mutated_file(self):
        other = self.root/"second.mcap"; other.write_bytes(fixture(crc=False))
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="second", local_path_private=str(other))
        self.spec["recordings"].append(second); self.register()
        def inspect(stream, size):
            value = inventory.read_inventory(stream, size)
            if Path(stream.name) == other: self.raw.write_bytes(b"X"*self.raw.stat().st_size)
            return value
        with patch.object(workflow, "read_inventory", side_effect=inspect):
            report, status = workflow.run_inventory(self.args)
        self.assertEqual(status, 3)
        self.assertIsNone(report["recordings"][0]["inventory"])
        self.assertEqual(report["recordings"][1]["status"], "complete")

    def test_cli_inventory_applies_process_limit_before_workflow_and_restores_it(self):
        previous = resource.getrlimit(resource.RLIMIT_AS)
        def inspect(arguments):
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            self.assertLessEqual(soft, cli.PROCESS_ADDRESS_SPACE_BYTES)
            self.assertEqual(hard, previous[1])
            return {}, 0
        with patch.object(workflow, "run_inventory", side_effect=inspect):
            self.assertEqual(cli.main(["inventory", "--registration-directory", "r", "--scratch-directory", "s", "--output-directory", "o"]), 0)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), previous)

    def test_cli_help_documents_inventory_and_rejects_readiness_successor_flag(self):
        command = [sys.executable, "-m", "lane_residuals.cli.recording_ingestion", "inventory", "--help"]
        result = subprocess.run(command, text=True, capture_output=True, check=True)
        self.assertIn("--registration-directory", result.stdout)
        self.assertNotIn("--preserved-readiness-report", result.stdout)
        with self.assertRaises(SystemExit) as error:
            cli.main(["inventory", "--registration-directory", "r", "--scratch-directory", "s", "--output-directory", "o", "--preserved-readiness-report", "old"])
        self.assertEqual(error.exception.code, 2)

    def test_actual_cli_prepare_register_inventory_never_loads_a_payload_decoder(self):
        root_repo = Path(__file__).resolve().parents[2]
        env = {**os.environ, "PYTHONPATH": str(root_repo/"src"), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        code = """from unittest.mock import patch
from types import SimpleNamespace
import sys
from lane_residuals.cli.recording_ingestion import main
with patch('lane_residuals.workflows.recording_ingestion._available_memory_bytes', return_value=8*1024**3), patch('lane_residuals.workflows.recording_ingestion.shutil.disk_usage', return_value=SimpleNamespace(free=12*1024**3)):
 status = main(sys.argv[1:])
if any(name == 'mcap' or name.startswith(('mcap.', 'mcap_protobuf.')) for name in sys.modules):
 raise SystemExit('unexpected payload reader import')
sys.exit(status)
"""
        commands = [
            ["prepare", "--mcap-file", str(self.raw), "--batch-id", "new_batch", "--recording-id", "pilot", "--output-specification", str(self.specification)],
            ["register", "--specification", str(self.specification), "--output-directory", str(self.directory)],
            ["inventory", "--registration-directory", str(self.directory), "--scratch-directory", str(self.root), "--output-directory", str(self.args.output_directory)],
        ]
        for arguments in commands:
            result = subprocess.run([sys.executable, "-c", code, *arguments], cwd=root_repo, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.args.output_directory/workflow.REPORT_NAME).read_text())
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["recordings"][0]["inventory"]["schemas"][0]["encoding"], "unknown-encoding")
