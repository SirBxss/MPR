import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from lane_residuals.workflows import speed_mechanism as workflow
from tests.domain.test_speed_mechanism import row,support


class MechanismWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.loaded={"request_sha256":"a"*64,"experiment_sha256":"b"*64,"cohort_sha256":"c"*64,"registry_sha256":"d"*64,
            "provenance":"synthetic_fixture_only","unchanged":Mock(),"protected_output_roots":(),"outings":[{"outing_id":f"synthetic_{i}",
                "rows":[row(0),row(1,False,False)],"original_support":support(),"previously_examined":i==0,"audit_sha256":"e"*64} for i in range(3)]}

    def run_audit(self):
        with patch.object(workflow,"load",return_value=self.loaded):
            return workflow.run(self.base,self.base/"request.json","a"*64,self.base/"result")

    def test_synthetic_workflow_outputs_only_private_diagnostics_and_python_plots(self):
        result=self.run_audit()
        self.assertEqual(result["status"],"complete_cached_speed_mechanism_audit")
        self.assertEqual(len(list((self.base/"result").iterdir())),6)
        self.assertGreater((self.base/"result/speed_mechanism.png").stat().st_size,1000)
        for key in ("raw_recording_opened","direct_velocity_rule_evaluated","new_training_arrays_exported","training_dataset_modified",
                "speed_feature_adopted","model_fitted","physical_causal_availability_proven","cohort_wide_temporal_recovery_established"):
            self.assertIs(result[key],False)
        self.loaded["unchanged"].assert_called_once()
        self.assertFalse(list(self.base.rglob("*.npz")))

    def test_existing_output_or_bad_input_never_creates_result(self):
        output=self.base/"existing";output.mkdir()
        with patch.object(workflow,"load",side_effect=AssertionError("not called")):
            with self.assertRaises(FileExistsError):workflow.run(self.base,self.base/"x.json","a"*64,output)
        with patch.object(workflow,"load",side_effect=ValueError("bad input")):
            with self.assertRaises(ValueError):workflow.run(self.base,self.base/"x.json","a"*64,self.base/"absent")
        self.assertFalse((self.base/"absent").exists())

    def test_late_integrity_drift_preserves_incomplete_report(self):
        self.loaded["unchanged"].side_effect=ValueError("synthetic late drift")
        with patch("lane_residuals.reporting.speed_mechanism.plot"):
            with self.assertRaises(ValueError):self.run_audit()
        report=json.loads((self.base/"result/report.private.json").read_text())
        self.assertEqual(report["status"],"incomplete_cached_speed_mechanism_audit")
        self.assertEqual(report["failure_class"],"ValueError")

    def test_snapshot_nesting_is_refused_before_native_input_loading(self):
        folder=self.base/"snapshot";folder.mkdir();(folder/"registry.json").write_text("malformed marker is sufficient")
        with patch.object(workflow,"load",side_effect=AssertionError("not called")):
            with self.assertRaisesRegex(ValueError,"inside_immutable_snapshot"):
                workflow.run(self.base,self.base/"request.json","a"*64,folder/"result")
        self.assertEqual({p.name for p in folder.iterdir()},{"registry.json"})

    def test_explicit_experiment_input_nesting_is_refused_before_output_creation(self):
        folder=self.base/"experiment";folder.mkdir();self.loaded["protected_output_roots"]=(folder,)
        with patch.object(workflow,"load",return_value=self.loaded):
            with self.assertRaisesRegex(ValueError,"overlaps_immutable_input"):
                workflow.run(self.base,self.base/"request.json","a"*64,folder/"result")
        self.assertFalse(list(folder.iterdir()))

    def test_plot_failure_preserves_incomplete_report(self):
        with patch("lane_residuals.reporting.speed_mechanism.plot",side_effect=RuntimeError("synthetic plot failure")):
            with self.assertRaises(RuntimeError):self.run_audit()
        report=json.loads((self.base/"result/report.private.json").read_text())
        self.assertEqual(report["status"],"incomplete_cached_speed_mechanism_audit")

    def test_native_cli_help_and_refusal_of_raw_option(self):
        env=dict(os.environ,MPLBACKEND="Agg")
        result=subprocess.run([sys.executable,"-m","lane_residuals.cli.speed_mechanism","--help"],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn("--raw",result.stdout)
        result=subprocess.run([sys.executable,"-m","lane_residuals.cli.speed_mechanism","--raw","forbidden.mcap"],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,2)


if __name__ == "__main__":unittest.main()
