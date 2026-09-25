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

import numpy as np

from lane_residuals.io import exploratory_residuals as extraction
from lane_residuals.io.mcap import McapDependencyError
from lane_residuals.workflows import exploratory_residuals as workflow
from tests.io.test_exploratory_residuals import fixture, baseline


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class ExploratoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);raw=self.root/"raw";raw.mkdir()
        identities=[]
        for i in range(4):
            p=raw/f"fixture_{i}.mcap";p.write_bytes(f"synthetic raw {i}".encode())
            identities.append({"relative_path":p.name,"size_bytes":p.stat().st_size,"sha256":digest(p)})
        registration=self.root/"registration.json";registration.write_text(json.dumps({"files":identities}))
        context=self.root/"context.json";context.write_text(json.dumps({"registration_sha256":digest(registration),"files":[
            {"relative_path":r["relative_path"],"size_bytes":r["size_bytes"],"sha256_from_registration_not_rehashed":r["sha256"]} for r in identities]}))
        self.messages=fixture();self.counts,self.details=baseline(self.messages)
        self.preserved=self.root/"pilot.json";self.diagnostic=self.root/"diagnostic.json"
        self.payload={"contract_revision":workflow.pilot.CONTRACT_REVISION,"status":"complete",
            "purpose":"recording_level_geometry_feasibility_without_session_provenance",
            "registration_sha256":digest(registration),"container_context_sha256":digest(context),
            "runtime_source_sha256":workflow.pilot.PRESERVED_SOURCE_SHA256,"raw_hashes_verified":True,
            "physical_session_provenance":"unavailable_owner_report_2026-09-20","independent_outing_count":None,
            "roles_assigned":False,"cohort_lock_created":False,"causal_input_availability_checked":False,"residuals_computed":False,
            "recordings":[{"relative_path_private":r["relative_path"],"raw_sha256":r["sha256"],"size_bytes":r["size_bytes"],
                "status":"complete","failure_code":None,"counts":deepcopy(self.counts)} for r in identities]}
        self.preserved.write_text(json.dumps(self.payload))
        self.diagnostic_payload=deepcopy(self.payload)
        self.diagnostic_payload.update(contract_revision=workflow.pilot.DIAGNOSTIC_REVISION,
            purpose="recording_level_reference_failures_and_numeric_pair_timing",preserved_feasibility_sha256=digest(self.preserved),
            runtime_source_sha256=workflow.DIAGNOSTICS_SOURCE_SHA256)
        for r in self.diagnostic_payload["recordings"]:r.update(legacy_counts_match_preserved=True,diagnostics=deepcopy(self.details))
        self.diagnostic.write_text(json.dumps(self.diagnostic_payload))
        self.args=argparse.Namespace(mcap_root=raw,registration=registration,container_context=context,
            preserved_feasibility_report=self.preserved,preserved_diagnostics_report=self.diagnostic,
            scratch_directory=self.root,output_directory=self.root/"output")
        stack=ExitStack();self.addCleanup(stack.close)
        for name,value in (("REGISTRATION_SHA256",digest(registration)),("CONTEXT_SHA256",digest(context)),("PRESERVED_REPORT_SHA256",digest(self.preserved))):
            stack.enter_context(patch.object(workflow.pilot,name,value))
        stack.enter_context(patch.object(workflow,"DIAGNOSTICS_SHA256",digest(self.diagnostic)))
        stack.enter_context(patch.object(workflow,"version",return_value="synthetic-fixture"))
        stack.enter_context(patch.object(workflow.pilot,"_available_memory_bytes",return_value=8*1024**3))
        stack.enter_context(patch.object(workflow.shutil,"disk_usage",return_value=SimpleNamespace(free=12*1024**3)))
        self.imports=stack.enter_context(patch.object(workflow,"decoder_types"))
        self.reader=stack.enter_context(patch.object(extraction,"_iter_messages",side_effect=lambda *args,**kwargs:(message for message in self.messages)))

    def test_complete_end_to_end_contract_keeps_all_recordings_separate_and_archive_is_deterministic(self):
        before=(self.preserved.read_bytes(),self.diagnostic.read_bytes())
        report,status=workflow.run_exploratory_residuals(self.args)
        self.assertEqual(status,0)
        self.assertEqual(report["candidate_count"],8)
        self.assertEqual(report["support"]["geometric_profile_count"],8)
        self.assertEqual(report["support"]["conditioned_transition_count"],4)
        self.assertTrue(report["recorded_input_causality_checked"])
        self.assertIsNone(report["independent_outing_count"])
        for name in ("roles_assigned","cohort_lock_created","model_fitted","standardizers_fitted","physical_input_availability_proven"):
            self.assertIs(report[name],False)
        self.assertEqual(set(p.name for p in self.args.output_directory.iterdir()),{workflow.SUMMARY_NAME,workflow.AUDIT_NAME,workflow.ARCHIVE_NAME})
        for name,sha in report["artifacts_sha256"].items():self.assertEqual(digest(self.args.output_directory/name),sha)
        with np.load(self.args.output_directory/workflow.ARCHIVE_NAME,allow_pickle=False) as a:
            np.testing.assert_array_equal(a["conditioned_sequence_offsets"],[0,2,4,6,8])
            self.assertEqual(a["residuals_m"].shape,(8,21));self.assertEqual(a["conditions"].shape,(8,6))
        audit=json.loads((self.args.output_directory/workflow.AUDIT_NAME).read_text())
        self.assertEqual([r["candidate_index"] for r in audit["rows"]],list(range(8)))
        self.assertNotIn("conditions",audit["rows"][0])
        self.assertEqual(before,(self.preserved.read_bytes(),self.diagnostic.read_bytes()))
        hashes=report["artifacts_sha256"]
        self.args.output_directory=self.root/"second"
        again,status=workflow.run_exploratory_residuals(self.args)
        self.assertEqual(again["artifacts_sha256"],hashes)
        with self.assertRaises(FileExistsError):workflow.run_exploratory_residuals(self.args)

    def test_one_incomplete_recording_exports_only_inconclusive_summary_no_partial_dataset(self):
        def records(path,**kwargs):
            yield from self.messages
            if path.name=="fixture_1.mcap":raise RuntimeError("private details")
        self.reader.side_effect=records
        report,status=workflow.run_exploratory_residuals(self.args)
        self.assertEqual(status,3)
        self.assertIsNone(report["support"]);self.assertIsNone(report["candidate_count"])
        self.assertFalse(report["residuals_exported"])
        self.assertEqual(list(p.name for p in self.args.output_directory.iterdir()),[workflow.SUMMARY_NAME])
        self.assertEqual(report["recordings"][1]["failure_code"],"RuntimeError")
        self.assertNotIn("private details",json.dumps(report))

    def test_both_preserved_byte_guards_run_before_hashing_decoding_or_output(self):
        for target in (self.preserved,self.diagnostic):
            before=target.read_bytes();target.write_bytes(before+b" ")
            with patch.object(workflow,"sha256_file") as hasher:
                with self.assertRaises(ValueError):workflow.run_exploratory_residuals(self.args)
                hasher.assert_not_called()
            self.reader.assert_not_called();self.assertFalse(self.args.output_directory.exists())
            target.write_bytes(before)

    def test_diagnostic_type_identity_and_nested_counts_must_match_even_if_hash_is_rebased_in_fixture(self):
        for mutation in ("flag","identity","counts"):
            payload=deepcopy(self.diagnostic_payload)
            if mutation=="flag":payload["roles_assigned"]=0
            elif mutation=="identity":payload["recordings"][0]["raw_sha256"]="a"*64
            else:payload["recordings"][0]["counts"]["estimate_descriptor_counts"]={"changed":2}
            self.diagnostic.write_text(json.dumps(payload))
            with patch.object(workflow,"DIAGNOSTICS_SHA256",digest(self.diagnostic)):
                with self.assertRaises(ValueError):workflow.run_exploratory_residuals(self.args)
            self.reader.assert_not_called();self.assertFalse(self.args.output_directory.exists())

    def test_broken_decoder_import_and_raw_byte_drift_cannot_create_output(self):
        self.imports.side_effect=McapDependencyError("broken install")
        with patch.object(workflow,"sha256_file") as hasher:
            with self.assertRaises(McapDependencyError):workflow.run_exploratory_residuals(self.args)
            hasher.assert_not_called()
        self.imports.side_effect=None
        path=self.args.mcap_root/"fixture_3.mcap";path.write_bytes(b"X"*path.stat().st_size)
        with self.assertRaises(ValueError):workflow.run_exploratory_residuals(self.args)
        self.reader.assert_not_called();self.assertFalse(self.args.output_directory.exists())

    def test_final_file_state_check_catches_prior_recording_mutation(self):
        def records(path,**kwargs):
            yield from self.messages
            if path.name=="fixture_3.mcap":
                first=self.args.mcap_root/"fixture_0.mcap";first.write_bytes(b"X"*first.stat().st_size)
        self.reader.side_effect=records
        report,status=workflow.run_exploratory_residuals(self.args)
        self.assertEqual(status,3)
        self.assertEqual(report["recordings"][0]["failure_code"],"file_changed_before_export")
        self.assertEqual(report["artifacts_sha256"],{})
        self.assertFalse((self.args.output_directory/workflow.ARCHIVE_NAME).exists())

    def test_no_complete_features_still_exports_geometric_profiles_with_empty_condition_arrays(self):
        self.messages=[m for m in self.messages if m[1].topic!=extraction.DEFAULT_ODOMETRY_TOPIC]
        report,status=workflow.run_exploratory_residuals(self.args)
        self.assertEqual(status,0)
        self.assertEqual(report["support"]["geometric_profile_count"],8)
        self.assertEqual(report["support"]["conditioned_profile_count"],0)
        self.assertEqual(report["condition_failure_counts"],{"odometry_stream_empty":8})
        with np.load(self.args.output_directory/workflow.ARCHIVE_NAME,allow_pickle=False) as a:
            self.assertEqual(a["conditions"].shape,(0,6))
            np.testing.assert_array_equal(a["conditioned_sequence_offsets"],[0])

    def test_cli_requires_both_reports_propagates_status_and_preserves_stricter_limit(self):
        from lane_residuals.cli import exploratory_residuals as cli
        import resource
        argv=[str(self.args.mcap_root)]
        for name in ("registration","container_context","preserved_feasibility_report","preserved_diagnostics_report","scratch_directory","output_directory"):
            argv.extend(["--"+name.replace("_","-"),str(getattr(self.args,name))])
        with patch.object(cli,"_bounded_run",return_value=({},3)) as run:
            self.assertEqual(cli.main(argv),3)
            self.assertEqual(run.call_args.args[0].preserved_diagnostics_report,self.diagnostic)
        previous=(2*1024**3,8*1024**3)
        with patch.object(resource,"getrlimit",return_value=previous),patch.object(resource,"setrlimit") as setlimit,patch.object(workflow,"run_exploratory_residuals",side_effect=ValueError("fixture")):
            with self.assertRaises(ValueError):cli._bounded_run(self.args)
            self.assertEqual(setlimit.call_count,2)
            self.assertEqual(setlimit.call_args_list[0].args,(resource.RLIMIT_AS,previous))
            self.assertEqual(setlimit.call_args_list[1].args,(resource.RLIMIT_AS,previous))
