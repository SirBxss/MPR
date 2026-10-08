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
from lane_residuals.io import recording_decode_check as io
from lane_residuals.workflows import recording_decode_check as workflow
from lane_residuals.workflows import recording_ingestion as registration
from lane_residuals.workflows import recording_inventory as inventory
from tests.domain.test_recording_ingestion import specification
from tests.io.recording_decode_fixture import recording


class DecodeCheckWorkflowTests(unittest.TestCase):
    def setUp(self):
        try:
            io.check_dependencies()
        except (ImportError, ValueError):
            self.skipTest("MCAP extras not installed")
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.raw = self.root/"file with spaces.mcap"
        self.raw.write_bytes(recording())
        self.source = self.root/"source.private.json"; self.spec = specification(str(self.raw))
        self.directory = self.root/"registration"; self.pred_dir = self.root/"inventory"
        self.args = argparse.Namespace(registration_directory=self.directory, scratch_directory=self.root,
            output_directory=self.root/"decode", preserved_inventory_report=self.pred_dir/inventory.REPORT_NAME, topic=["/selected"])
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(registration, "_available_memory_bytes", return_value=8*1024**3))
        stack.enter_context(patch.object(registration.shutil, "disk_usage", return_value=SimpleNamespace(free=12*1024**3)))

    def prepare(self):
        self.source.write_text(json.dumps(self.spec))
        registration.run_registration(argparse.Namespace(specification=self.source, output_directory=self.directory))
        return inventory.run_inventory(argparse.Namespace(registration_directory=self.directory, scratch_directory=self.root,
                                                       output_directory=self.pred_dir))[0]

    def test_complete_uses_one_hash_same_descriptor_and_has_no_scientific_side_effects(self):
        self.prepare(); before = {str(p): p.read_bytes() for p in [*self.directory.iterdir(), self.args.preserved_inventory_report]}
        handles, original = [], workflow.sha256_stream
        def hasher(stream):
            handles.append(stream); return original(stream)
        with patch.object(workflow, "sha256_stream", side_effect=hasher), patch.object(workflow.io, "check_decoding", wraps=io.check_decoding) as reader, \
                patch.object(registration, "inspect_recording_readiness") as geometry, patch.object(registration, "decoder_types") as old_reader:
            # Preserve the real decoder while observing the same open stream.
            original_check = reader._mock_wraps
            reader.side_effect = lambda stream, *args: (self.assertIs(stream, handles[0]), original_check(stream, *args))[1]
            report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 0); self.assertEqual(len(handles), 1)
        geometry.assert_not_called(); old_reader.assert_not_called()
        self.assertEqual(before, {p: Path(p).read_bytes() for p in before})
        self.assertIsNone(report["independent_outing_count"])
        for key in ("geometry_readiness_assessed", "residual_profiles_constructed", "numeric_conditions_exported",
                    "reference_independence_proven", "model_fitted", "roles_assigned", "raw_cache_deletion_authorized"):
            self.assertIs(report[key], False)
        self.assertEqual(report["recordings"][0]["decode_check"]["decoded_selected_message_count"], 3)
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()], [workflow.REPORT_NAME])
        self.assertNotIn(str(self.raw), json.dumps(report)); self.assertNotIn("PRIVATE", json.dumps(report))
        with self.assertRaisesRegex(ValueError, "new_absent_output"):
            workflow.run_decode_check(self.args)

    def test_inconclusive_predecessor_and_scientific_flags_stop_before_raw_hash(self):
        report = self.prepare()
        for change in ({"status": "inconclusive"}, {"model_fitted": True}, {"registration_sha256": "0"*64}, {"technical_recording_count": True}):
            bad = {**report, **change}; self.args.preserved_inventory_report.write_text(json.dumps(bad))
            with patch.object(workflow, "sha256_stream") as hasher:
                with self.assertRaisesRegex(ValueError, "decode_"):
                    workflow.run_decode_check(self.args)
                hasher.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_duplicate_json_keys_nonfinite_constants_and_report_size_are_rejected(self):
        self.prepare()
        for raw in ('{"x": 1, "x": 2}', '{"x": NaN}'):
            self.args.preserved_inventory_report.write_text(raw)
            with self.assertRaisesRegex(ValueError, "duplicate_json_key|nonfinite_json"):
                workflow.run_decode_check(self.args)
        with patch.object(io, "MAX_PREDECESSOR_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "report_budget"):
                workflow.run_decode_check(self.args)

    def test_semantic_inventory_tampering_stops_before_payload_or_output(self):
        report = self.prepare(); report["recordings"][0]["inventory"]["channels"][0]["advertised_message_count"] += 1
        self.args.preserved_inventory_report.write_text(json.dumps(report))
        with patch.object(io, "check_decoding") as decode:
            with self.assertRaisesRegex(ValueError, "decode_preserved_inventory_mismatch"):
                workflow.run_decode_check(self.args)
        decode.assert_not_called(); self.assertFalse(self.args.output_directory.exists())

    def test_extra_predecessor_keys_and_integer_type_drift_are_rejected(self):
        report = self.prepare(); original = deepcopy(report)
        report["unexpected"] = 1
        self.args.preserved_inventory_report.write_text(json.dumps(report))
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "lineage_required"):
                workflow.run_decode_check(self.args)
            hasher.assert_not_called()
        original["recordings"][0]["inventory"]["chunk_index_summary"]["indexed_chunk_count"] = 4.0
        self.args.preserved_inventory_report.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, "preserved_inventory_mismatch"):
            workflow.run_decode_check(self.args)
        self.assertFalse(self.args.output_directory.exists())

    def test_registration_and_raw_tampering_stop_before_inventory_or_output(self):
        self.prepare(); source = self.directory/registration.SPECIFICATION_NAME
        original = source.read_bytes(); source.write_bytes(original+b" ")
        with patch.object(workflow, "read_inventory") as reader:
            with self.assertRaisesRegex(ValueError, "registration_lineage_mismatch"):
                workflow.run_decode_check(self.args)
            source.write_bytes(original); self.raw.write_bytes(b"X"*self.raw.stat().st_size)
            with self.assertRaisesRegex(ValueError, "registered_raw_hash_or_size_changed"):
                workflow.run_decode_check(self.args)
            reader.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_initial_resource_failure_returns_two_without_hash_or_output(self):
        self.prepare()
        with patch.object(registration, "_available_memory_bytes", return_value=1), patch.object(workflow, "sha256_stream") as hasher:
            self.assertEqual(cli.main(self.command()), 2); hasher.assert_not_called()
        self.assertFalse(self.args.output_directory.exists())

    def test_post_hash_resource_failure_is_reported_three_with_null_result(self):
        self.prepare()
        with patch.object(registration, "_available_memory_bytes", side_effect=[8*1024**3, 1]):
            report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "available_memory_below_6gib")
        self.assertIsNone(report["recordings"][0]["decode_check"])

    def test_later_bad_payload_never_publishes_successful_prefix_as_full_counts(self):
        self.raw.write_bytes(recording(invalid_last=True)); self.prepare()
        report, status = workflow.run_decode_check(self.args)
        row = report["recordings"][0]; self.assertEqual(status, 3); self.assertIsNone(row["decode_check"])
        self.assertEqual(row["reader_failure_context"]["decoded_selected_message_count"], 2)
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertFalse(any(p.name.startswith("mpr-decode-index-") for p in self.root.iterdir()))

    def test_memory_and_native_errors_use_static_codes_and_null_counts(self):
        self.prepare()
        for error in (MemoryError(), ValueError("PRIVATE coordinates /path")):
            with patch.object(io, "check_decoding", side_effect=error):
                report, status = workflow.run_decode_check(self.args)
            self.assertEqual(status, 3); self.assertIsNone(report["recordings"][0]["decode_check"])
            self.assertNotIn("PRIVATE", json.dumps(report))
            self.args.output_directory = self.root/"next"

    def test_path_replacement_invalidates_completed_counts(self):
        self.prepare(); original = io.check_decoding
        def replace(stream, *arguments):
            result = original(stream, *arguments); other = self.root/"replacement"
            other.write_bytes(self.raw.read_bytes()); os.replace(other, self.raw); return result
        with patch.object(io, "check_decoding", side_effect=replace):
            report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 3); row = report["recordings"][0]
        self.assertIsNone(row["decode_check"])
        self.assertEqual(row["failure_code"], "file_changed_during_decode_check")
        self.assertIn("file_changed_before_report_publish", row["invalidation_codes"])

    def test_later_identity_drift_does_not_erase_the_original_decoding_failure(self):
        self.prepare()
        def fail(*_):
            self.raw.write_bytes(b"X"*self.raw.stat().st_size)
            raise MemoryError()
        with patch.object(io, "check_decoding", side_effect=fail):
            report, status = workflow.run_decode_check(self.args)
        row = report["recordings"][0]; self.assertEqual(status, 3)
        self.assertEqual(row["failure_code"], "memory_limit")
        self.assertEqual(row["invalidation_codes"], ["file_changed_during_decode_check", "file_changed_before_report_publish"])
        self.assertIsNone(row["decode_check"])

    def test_predecessor_or_registration_change_invalidates_success_before_publication(self):
        self.prepare(); original = io.check_decoding
        def mutate(stream, *arguments):
            result = original(stream, *arguments)
            self.args.preserved_inventory_report.write_bytes(self.args.preserved_inventory_report.read_bytes()+b" ")
            source = self.directory/registration.SPECIFICATION_NAME; source.write_bytes(source.read_bytes()+b" ")
            return result
        with patch.object(io, "check_decoding", side_effect=mutate):
            report, status = workflow.run_decode_check(self.args)
        row = report["recordings"][0]; self.assertEqual(status, 3); self.assertIsNone(row["decode_check"])
        self.assertEqual(row["failure_code"], "registration_changed_before_report_publish")
        self.assertIn("preserved_inventory_changed_before_report_publish", row["invalidation_codes"])

    def test_multiple_files_keep_individual_results_and_do_not_pool_or_assign_outings(self):
        other = self.root/"second.mcap"; other.write_bytes(recording(invalid_last=True))
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="second", local_path_private=str(other))
        self.spec["recordings"].append(second); self.prepare()
        report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 3); self.assertEqual(report["technical_recording_count"], 2)
        self.assertEqual([r["status"] for r in report["recordings"]], ["complete", "inconclusive"])
        self.assertIsNone(report["independent_outing_count"]); self.assertNotIn("pooled_counts", report)

    def test_later_processing_invalidates_an_earlier_changed_file(self):
        other = self.root/"second.mcap"; other.write_bytes(recording(count=2))
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="second", local_path_private=str(other))
        self.spec["recordings"].append(second); self.prepare(); original = io.check_decoding
        def change(stream, *arguments):
            value = original(stream, *arguments)
            if Path(stream.name) == other:
                self.raw.write_bytes(b"X"*self.raw.stat().st_size)
            return value
        with patch.object(io, "check_decoding", side_effect=change):
            report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 3); self.assertIsNone(report["recordings"][0]["decode_check"])
        self.assertEqual(report["recordings"][1]["status"], "complete")

    def test_missing_topic_is_not_zero_decoded_messages(self):
        self.prepare(); self.args.topic = ["/absent"]
        report, status = workflow.run_decode_check(self.args)
        self.assertEqual(status, 3); self.assertIsNone(report["recordings"][0]["decode_check"])
        self.assertEqual(report["recordings"][0]["failure_code"], "decode_requested_topic_absent")

    def test_dangling_output_symlink_and_duplicate_selection_fail_before_hashing(self):
        self.prepare(); self.args.output_directory.symlink_to(self.root/"missing")
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "new_absent_output"):
                workflow.run_decode_check(self.args)
            hasher.assert_not_called()
        self.args.output_directory = self.root/"new"; self.args.topic *= 2
        with self.assertRaisesRegex(ValueError, "explicit_unique_topics"):
            workflow.run_decode_check(self.args)

    def command(self):
        return ["decode-check", "--registration-directory", str(self.directory), "--scratch-directory", str(self.root),
            "--preserved-inventory-report", str(self.args.preserved_inventory_report), "--topic", "/selected",
            "--output-directory", str(self.args.output_directory)]

    def test_cli_limits_restore_and_no_readiness_successor_argument(self):
        previous = resource.getrlimit(resource.RLIMIT_AS)
        def inspect(_):
            self.assertLessEqual(resource.getrlimit(resource.RLIMIT_AS)[0], cli.PROCESS_ADDRESS_SPACE_BYTES)
            return {}, 0
        with patch.object(workflow, "run_decode_check", side_effect=inspect):
            self.assertEqual(cli.main(self.command()), 0)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), previous)
        with self.assertRaises(SystemExit) as error:
            cli.main([*self.command(), "--preserved-readiness-report", "old"])
        self.assertEqual(error.exception.code, 2)

    def test_actual_cli_succeeds_in_plain_and_optimized_modes_without_invoking_geometry(self):
        self.prepare(); repo = Path(__file__).resolve().parents[2]
        env = {**os.environ, "PYTHONPATH": str(repo/"src"), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        code = """from unittest.mock import patch
from types import SimpleNamespace
import sys
from lane_residuals.cli.recording_ingestion import main
with patch('lane_residuals.workflows.recording_ingestion._available_memory_bytes', return_value=8*1024**3), patch('lane_residuals.workflows.recording_ingestion.shutil.disk_usage', return_value=SimpleNamespace(free=12*1024**3)), patch('lane_residuals.workflows.recording_ingestion.inspect_recording_readiness', side_effect=RuntimeError('forbidden scientific call')):
 sys.exit(main(sys.argv[1:]))
"""
        for index, flags in enumerate(([], ["-O"], ["-OO"])):
            self.args.output_directory = self.root/f"cli_{index}"
            result = subprocess.run([sys.executable, *flags, "-c", code, *self.command()], cwd=repo, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((self.args.output_directory/workflow.REPORT_NAME).read_text())["status"], "complete")
