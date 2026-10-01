import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lane_residuals.cli import recording_ingestion as cli
from lane_residuals.io import recording_ingestion as ingestion
from lane_residuals.workflows import recording_ingestion as workflow
from tests.domain.test_recording_ingestion import specification
from tests.io.test_exploratory_residuals import fixture
from tests.io.test_recording_ingestion import indexed_summary


class RecordingIngestionWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.raw = self.root/"pilot.mcap"; self.raw.write_bytes(b"synthetic raw identity")
        self.specification = self.root/"source.private.json"
        self.spec = specification(str(self.raw)); self.save_spec()
        self.registration = self.root/"registration"
        self.args = argparse.Namespace(registration_directory=self.registration, scratch_directory=self.root,
                                       output_directory=self.root/"report")
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(workflow, "_available_memory_bytes", return_value=8*1024**3))
        stack.enter_context(patch.object(workflow.shutil, "disk_usage", return_value=SimpleNamespace(free=12*1024**3)))
        self.imports = stack.enter_context(patch.object(workflow, "decoder_types"))
        reader = SimpleNamespace(get_summary=lambda: indexed_summary())
        stack.enter_context(patch.object(ingestion, "decoder_types", return_value=(lambda *a, **k: reader, None)))
        self.messages = fixture()
        self.reader = stack.enter_context(patch.object(ingestion, "_iter_messages", side_effect=lambda *a, **k: (m for m in self.messages)))

    def save_spec(self):
        self.specification.write_text(json.dumps(self.spec))

    def register(self):
        return workflow.run_registration(argparse.Namespace(specification=self.specification, output_directory=self.registration))

    def test_prepare_uses_actual_existing_path_and_keeps_unknown_fields_null(self):
        output = self.root/"draft.private.json"
        args = argparse.Namespace(output_specification=output, mcap_file=self.raw, batch_id="batch03_pilot001",
            recording_id="pilot_001", merged_input_mcap_count=180, source_recording_id="export_uuid", export_settings="MCAP; merge enabled; display timezone unknown")
        with patch.object(workflow, "sha256_stream") as hasher:
            draft, status = workflow.run_prepare(args)
            hasher.assert_not_called()
        self.assertEqual(status, 0)
        self.assertEqual(draft["recordings"][0]["local_path_private"], str(self.raw))
        self.assertIsNone(draft["recordings"][0]["source"]["physical_session_id_private"])
        with self.assertRaises(ValueError): workflow.run_prepare(args)
        self.assertEqual(self.raw.read_bytes(), b"synthetic raw identity")

    def test_registration_hashes_raw_bytes_and_preserves_exact_source_specification_without_decoding(self):
        before = self.specification.read_bytes()
        registration, status = self.register()
        self.assertEqual(status, 0)
        self.assertEqual(registration["recordings"][0]["raw_sha256"], hashlib.sha256(self.raw.read_bytes()).hexdigest())
        self.assertEqual((self.registration/workflow.SPECIFICATION_NAME).read_bytes(), before)
        self.assertEqual({p.name for p in self.registration.iterdir()}, {workflow.SPECIFICATION_NAME, workflow.REGISTRATION_NAME})
        self.reader.assert_not_called()
        self.imports.assert_not_called()
        with self.assertRaises(ValueError): self.register()

    def test_duplicate_resolved_paths_and_identical_raw_exports_are_not_double_counted(self):
        other = self.root/"other.mcap"; other.write_bytes(self.raw.read_bytes())
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="other", local_path_private=str(other))
        self.spec["recordings"].append(second); self.save_spec()
        with self.assertRaisesRegex(ValueError, "duplicate_raw_sha256"):
            self.register()
        self.assertFalse(self.registration.exists())
        other.unlink(); other.symlink_to(self.raw)
        with self.assertRaisesRegex(ValueError, "duplicate_resolved_mcap_path"):
            self.register()
        self.assertFalse(self.registration.exists())

    def test_complete_generic_readiness_retains_support_without_any_numeric_dataset_or_outing_admission(self):
        self.register()
        before = {p.name: p.read_bytes() for p in self.registration.iterdir()}
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 0)
        self.assertEqual(report["technical_recording_count"], 1)
        self.assertEqual(report["recordings"][0]["complete_condition_support"]["transition_count"], 1)
        self.assertEqual(report["recordings"][0]["source_declaration_status"]["claimed_merged_input_mcap_count"], 180)
        self.assertIsNone(report["independent_outing_count"])
        for key in ("roles_assigned", "cohort_lock_created", "model_fitted", "residual_profiles_constructed",
                    "numeric_conditions_exported", "reference_independence_proven", "raw_cache_deletion_authorized"):
            self.assertIs(report[key], False)
        self.assertEqual([p.name for p in self.args.output_directory.iterdir()], [workflow.REPORT_NAME])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.registration.iterdir()})
        self.assertNotIn(str(self.raw), json.dumps(report))
        self.assertNotIn("local_path_private", json.dumps(report))

    def test_registration_tampering_and_raw_byte_changes_fail_before_decode_or_output(self):
        self.register()
        source = self.registration/workflow.SPECIFICATION_NAME
        before = source.read_bytes(); source.write_bytes(before+b" ")
        with self.assertRaisesRegex(ValueError, "registration_lineage_mismatch"):
            workflow.run_readiness(self.args)
        self.reader.assert_not_called(); self.assertFalse(self.args.output_directory.exists())
        source.write_bytes(before)
        self.raw.write_bytes(b"X"*self.raw.stat().st_size)
        with self.assertRaisesRegex(ValueError, "registered_raw_hash_or_size_changed"):
            workflow.run_readiness(self.args)
        self.reader.assert_not_called(); self.assertFalse(self.args.output_directory.exists())

    def test_resource_preflight_preserves_index_counts_and_does_not_decode_a_prefix(self):
        self.register()
        with patch.object(workflow, "indexed_metadata", return_value=({"advertised_odometry": 1_000_001}, "advertised_topic_count_exceeds_resource_limit")):
            report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 3)
        row = report["recordings"][0]
        self.assertEqual(row["indexed_metadata"]["advertised_odometry"], 1_000_001)
        self.assertIsNone(row["counts"]); self.assertIsNone(row["complete_condition_support"])
        self.reader.assert_not_called()

    def test_verified_descriptor_is_reused_and_path_replacement_invalidates_completed_counts(self):
        self.register()
        def messages(path, *, stream, **kwargs):
            self.assertFalse(stream.closed)
            self.assertEqual(ingestion.sha256_stream(stream), hashlib.sha256(b"synthetic raw identity").hexdigest())
            replacement = self.root/"replacement"; replacement.write_bytes(b"replacement bytes")
            os.replace(replacement, path)
            self.assertEqual(ingestion.sha256_stream(stream), hashlib.sha256(b"synthetic raw identity").hexdigest())
            yield from self.messages
        self.reader.side_effect = messages
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 3)
        self.assertIsNone(report["recordings"][0]["counts"])
        self.assertIsNone(report["recordings"][0]["indexed_metadata"])
        self.assertTrue(self.raw.exists())

    def test_missing_index_or_midstream_decode_failure_is_inconclusive_with_null_support(self):
        self.register()
        def interrupted(*args, **kwargs):
            yield from self.messages
            raise RuntimeError("private payload coordinates")
        self.reader.side_effect = interrupted
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "RuntimeError")
        self.assertIsNone(report["recordings"][0]["counts"])
        self.assertNotIn("private payload", json.dumps(report))
        self.assertFalse(any(p.name.startswith("mpr-ingestion-") for p in self.root.iterdir()))

    def test_same_declared_session_is_retained_but_files_never_stitch_or_acquire_roles(self):
        other = self.root/"other.mcap"; other.write_bytes(b"a different raw identity")
        source = self.spec["recordings"][0]["source"]
        source.update(physical_session_id_private="same_physical_drive", physical_session_evidence_private="provider declaration")
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="other", local_path_private=str(other))
        self.spec["recordings"].append(second); self.save_spec(); self.register()
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 0)
        self.assertIsNone(report["independent_outing_count"])
        self.assertEqual([r["complete_condition_support"]["transition_count"] for r in report["recordings"]], [1, 1])
        self.assertTrue(all(r["source_declaration_status"]["physical_session_declared_with_evidence"] for r in report["recordings"]))

    def test_later_recording_mutation_of_earlier_raw_invalidates_earlier_counts(self):
        other = self.root/"other.mcap"; other.write_bytes(b"different identity")
        second = deepcopy(self.spec["recordings"][0]); second.update(recording_id="other", local_path_private=str(other))
        self.spec["recordings"].append(second); self.save_spec(); self.register()
        def messages(path, **kwargs):
            if path == other: self.raw.write_bytes(b"changed earlier file")
            yield from self.messages
        self.reader.side_effect = messages
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "file_changed_before_report_publish")
        self.assertIsNone(report["recordings"][0]["counts"])
        self.assertFalse(report["recorded_input_causality_checked_for_all_recordings"])

    def test_preserved_source_metadata_mutation_during_audit_invalidates_observations(self):
        self.register()
        def messages(*args, **kwargs):
            source = self.registration/workflow.SPECIFICATION_NAME
            source.write_bytes(source.read_bytes()+b" ")
            yield from self.messages
        self.reader.side_effect = messages
        report, status = workflow.run_readiness(self.args)
        self.assertEqual(status, 3)
        self.assertEqual(report["recordings"][0]["failure_code"], "registration_changed_before_report_publish")
        self.assertIsNone(report["recordings"][0]["counts"])

    def test_ram_and_disk_guards_reject_before_output_and_payloads(self):
        self.register()
        for name, value in (("_available_memory_bytes", 1024),):
            with patch.object(workflow, name, return_value=value):
                with self.assertRaisesRegex(ValueError, "available_memory_below_6gib"):
                    workflow.run_readiness(self.args)
        with patch.object(workflow.shutil, "disk_usage", return_value=SimpleNamespace(free=1024)):
            with self.assertRaisesRegex(ValueError, "scratch_free_space_below_10gib"):
                workflow.run_readiness(self.args)
        self.reader.assert_not_called(); self.assertFalse(self.args.output_directory.exists())


class RecordingIngestionCliTests(unittest.TestCase):
    def test_raw_exception_payloads_are_not_logged_and_allocation_limit_is_restored(self):
        with patch.object(cli, "_bounded_run", side_effect=RuntimeError("private locator coordinate")), self.assertLogs(level="ERROR") as logs:
            status = cli.main(["register", "--specification", "unused", "--output-directory", "unused"])
        self.assertEqual(status, 2)
        self.assertNotIn("private locator", " ".join(logs.output))
        args = argparse.Namespace(command="register")
        with patch("resource.getrlimit", return_value=(-1, -1)), patch("resource.setrlimit") as limit, patch.object(workflow, "run_registration", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError): cli._bounded_run(args)
        self.assertEqual([c.args[1] for c in limit.call_args_list], [(4*1024**3, -1), (-1, -1)])

    def test_actual_cli_subprocess_prepare_register_and_compressed_mcap_audit(self):
        try:
            import mcap
            import google.protobuf
        except ImportError: self.skipTest("MCAP extras not installed")
        from tests.io.recording_ingestion_fixture import write_recording
        root_repo = Path(__file__).resolve().parents[2]
        environment = {**os.environ, "PYTHONPATH": str(root_repo/"src"), "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); raw = root/"pilot.mcap"; write_recording(raw)
            spec, registry, report_dir = root/"source.private.json", root/"registry", root/"audit"
            def run(arguments):
                # Fixture resource readings keep CI host load/disk out of this
                # CLI integration test; the subprocess still enforces real AS.
                code = "from unittest.mock import patch; from types import SimpleNamespace; import sys; from lane_residuals.cli.recording_ingestion import main\nwith patch('lane_residuals.workflows.recording_ingestion._available_memory_bytes',return_value=8*1024**3), patch('lane_residuals.workflows.recording_ingestion.shutil.disk_usage',return_value=SimpleNamespace(free=12*1024**3)):\n sys.exit(main(sys.argv[1:]))"
                result = subprocess.run([sys.executable, "-c", code, *arguments], cwd=root_repo, env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            run(["prepare", "--mcap-file", str(raw), "--batch-id", "pilot", "--recording-id", "recording_001",
                 "--merged-input-mcap-count", "180", "--output-specification", str(spec)])
            run(["register", "--specification", str(spec), "--output-directory", str(registry)])
            run(["audit", "--registration-directory", str(registry), "--scratch-directory", str(root), "--output-directory", str(report_dir)])
            report = json.loads((report_dir/workflow.REPORT_NAME).read_text())
            self.assertEqual(report["execution_limits"]["process_address_space_soft_limit_bytes"], 4*1024**3)
            self.assertEqual(report["recordings"][0]["sensor_geometry_support"]["frame_count"], 2)
            self.assertEqual(report["recordings"][0]["complete_condition_support"]["frame_count"], 2)
            self.assertFalse(report["residual_profiles_constructed"])
            self.assertTrue(raw.exists())
