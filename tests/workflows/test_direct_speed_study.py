from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import direct_speed_study as io
from lane_residuals.workflows import direct_speed_study as workflow
from tests.io.direct_speed_study_fixture import fixture


class StudyWorkflowTests(unittest.TestCase):
    def setUp(self):
        try:
            io.decoder.check_dependencies()
        except (ImportError,ValueError):
            self.skipTest("optional MCAP extras not installed")
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs,_,self.path,self.pin = fixture(self.root)
        with patch.object(io.original,"load_experiment",return_value=(self.inputs,{})):
            self.loaded = io.load(self.root,self.path,self.pin)
        self.inputs.unchanged.reset_mock()
        self.source = {"commit":"synthetic","tree":"synthetic"}

    def mocks(self):
        stack = ExitStack()
        stack.enter_context(patch.object(workflow,"load",return_value=self.loaded))
        stack.enter_context(patch.object(workflow.gate,"validate",return_value=self.source))
        stack.enter_context(patch.object(workflow.gate,"runtime_sha256",return_value="r"*64))
        stack.enter_context(patch.object(workflow.gate,"git",side_effect=lambda _,*args:"" if args[0] == "status" else "synthetic"))
        stack.enter_context(patch.object(workflow,"resources",return_value={"synthetic":True}))
        return stack

    def run_study(self,name="result"):
        return workflow.run(project=self.root,request_path=self.path,request_sha256=self.pin,
            gate_path=self.root/"gate.json",gate_sha256="g"*64,expected_runtime="r"*64,output=self.root/name)

    def test_native_synthetic_reader_analysis_population_and_python_figures(self):
        before = {c["raw_path_private"]:Path(c["raw_path_private"]).read_bytes() for c in self.loaded["cases"]}
        with self.mocks():report = self.run_study()
        self.assertEqual(report["status"],"complete_bounded_direct_speed_development_study")
        self.assertEqual(report["claims_created"],2)
        self.assertEqual(report["population"]["station_summary_count"],63)
        self.inputs.unchanged.assert_called_once()
        for path,value in before.items():self.assertEqual(Path(path).read_bytes(),value)
        self.assertGreater((self.root/"result/direct_speed_windows.png").stat().st_size,1000)
        self.assertGreater((self.root/"result/cached_population_difference.pdf").stat().st_size,1000)
        self.assertFalse(list((self.root/"result").rglob("*.npz")))
        for key in ("model_fitted","training_dataset_modified","speed_feature_adopted","final_outings_exposed"):
            self.assertIs(report[key],False)

    def test_live_gate_failure_precedes_all_raw_access_and_population_statistics(self):
        original = Path.resolve
        def resolve(path,*args,**kwargs):
            if path.suffix == ".mcap":raise AssertionError("raw resolve before GO")
            return original(path,*args,**kwargs)
        with self.mocks(),patch.object(workflow.gate,"validate",side_effect=ValueError("no GO")),patch.object(Path,"resolve",resolve), \
                patch.object(workflow,"population",side_effect=AssertionError("numeric outcome before GO")):
            with self.assertRaisesRegex(ValueError,"no GO"):self.run_study()
        self.assertFalse((self.root/"result").exists())
        self.assertFalse((self.root/"outputs").exists())

    def test_all_plans_precede_any_claim_hash_or_payload(self):
        original = workflow.prepare;calls = []
        def plan(*args):
            calls.append(1)
            if len(calls) == 2:raise ValueError("pilot_planned_window_budget")
            return original(*args)
        with self.mocks(),patch.object(workflow,"prepare",side_effect=plan),patch.object(workflow,"verify_raw",side_effect=AssertionError("hash")), \
                patch.object(workflow,"decode_prepared",side_effect=AssertionError("payload")):
            with self.assertRaisesRegex(ValueError,"planned_window_budget"):self.run_study()
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["claims_created"],0)
        self.assertFalse(report["raw_hash_started"])
        self.assertFalse((self.root/"outputs").exists())

    def test_both_durable_claims_precede_hash_and_renamed_retry_is_denied(self):
        def fail(*_):
            self.assertEqual(len(list((self.root/"outputs/private/direct_speed_study_attempts").glob("*.started.json"))),2)
            raise ValueError("study_test_hash")
        with self.mocks(),patch.object(workflow,"verify_raw",side_effect=fail):
            with self.assertRaisesRegex(ValueError,"test_hash"):self.run_study()
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["claims_created"],2)
        self.assertTrue(report["raw_hash_started"])
        self.assertFalse(report["payload_decode_started"])
        with self.mocks(),patch.object(workflow,"prepare",side_effect=AssertionError("repeated raw plan")):
            with self.assertRaisesRegex(ValueError,"already_claimed"):self.run_study("renamed")
        self.assertFalse((self.root/"renamed").exists())

    def test_decode_interrupt_and_analysis_failure_keep_available_evidence(self):
        with self.mocks(),patch.object(workflow,"analyze",side_effect=ValueError("study_analysis_failure")):
            with self.assertRaisesRegex(ValueError,"analysis_failure"):self.run_study()
        folder = self.root/"result/synthetic_1"
        self.assertTrue((folder/"velocity_updates.private.csv").exists())
        self.assertTrue((folder/"original_candidate_audit.private.json").exists())
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["cases"][0]["phase"],"payload_decode_complete")
        self.assertEqual(report["status"],"incomplete_bounded_direct_speed_development_study")

    def test_keyboard_interrupt_preserves_incomplete_phase(self):
        with self.mocks(),patch.object(workflow,"verify_raw",side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):self.run_study()
        report = json.loads((self.root/"result/report.private.json").read_text())
        self.assertEqual(report["failure_class"],"KeyboardInterrupt")
        self.assertEqual(report["phase"],"raw_hash_started")

    def test_raw_identity_changes_cannot_complete(self):
        original = workflow.decode_prepared
        def decode(*args):
            records,report = original(*args)
            with Path(self.loaded["cases"][0]["raw_path_private"]).open("ab") as stream:stream.write(b"drift")
            return records,report
        with self.mocks(),patch.object(workflow,"decode_prepared",side_effect=decode):
            with self.assertRaisesRegex(ValueError,"raw_changed_during_decode"):self.run_study()
        self.assertEqual(json.loads((self.root/"result/report.private.json").read_text())["status"],"incomplete_bounded_direct_speed_development_study")

    def test_existing_output_and_snapshot_nesting_fail_before_loading(self):
        (self.root/"result").mkdir()
        with patch.object(workflow,"load",side_effect=AssertionError("load")):
            with self.assertRaisesRegex(ValueError,"fresh_canonical"):self.run_study()
        snapshot = self.root/"snapshot";snapshot.mkdir();(snapshot/"registry.json").write_text("marker")
        with patch.object(workflow,"load",side_effect=AssertionError("load")):
            with self.assertRaisesRegex(ValueError,"inside_immutable_snapshot"):self.run_study("snapshot/result")

    def test_watched_input_or_late_source_drift_keeps_incomplete_report(self):
        self.inputs.unchanged.side_effect = ValueError("experiment_input_changed")
        with self.mocks():
            with self.assertRaisesRegex(ValueError,"input_changed"):self.run_study()
        self.assertEqual(json.loads((self.root/"result/report.private.json").read_text())["failure_code"],"experiment_input_changed")

    def test_cli_has_no_subset_offset_or_threshold_switch(self):
        env = dict(os.environ)
        result = subprocess.run([sys.executable,"-m","lane_residuals.cli.direct_speed_study","run","--help"],capture_output=True,text=True,env=env,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        for option in ("--raw","--offset","--age","--outing","--window"):
            self.assertNotIn(option,result.stdout)
