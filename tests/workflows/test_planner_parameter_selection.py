"""Freeze choices before held evaluation, using a sealed synthetic cohort."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from lane_residuals.domain import planner_parameter_selection as policy
from lane_residuals.io import development_experiment as original
from lane_residuals.workflows import planner_parameter_selection as workflow
from lane_residuals.workflows.locked_development_export import write
from tests.io import parameter_selection_fixture as fixture


class PlannerParameterWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family=fixture.frozen_family()

    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.project=self.root/"project";self.project.mkdir()
        self.bundle=fixture.data(self.root,self.family)
        self.source=dict(consumer_git_commit="synthetic",consumer_git_tree="synthetic",consumer_runtime_source_sha256="synthetic")
        packet=self.root/"packet";packet.mkdir()
        self.manifest=packet/"selection_manifest.private.json"
        self.args=dict(project=self.project,manifest_path=self.manifest,flow_zip=self.root/"flow.zip",
            temporal_zip=self.root/"temporal.zip",expected_tree="synthetic",expected_runtime="synthetic",output=self.root/"result")
        for target,name,result in ((workflow,"source_guard",self.source),
            (workflow,"load_families",(self.bundle.native,{},self.bundle.marker,self.bundle.families)),
            (workflow,"accepted_temporal",self.bundle.checkpoint)):
            p=patch.object(target,name,return_value=result);p.start();self.addCleanup(p.stop)

    def seal(self):
        write(self.manifest,self.bundle.plan)
        return dict(**self.args,manifest_pin=original.sha(self.manifest))

    def fake_arms(self,pool,x,offsets,family,checkpoint=None):
        # Fast synthetic laws for orchestration tests. A separate test exercises
        # every native sampler, including both flow modes.
        if self.args["output"].exists():
            for oid in self.bundle.ids:self.assertTrue((self.args["output"]/(oid+"_design.private.json")).exists())
        rng=np.random.default_rng(193401)
        arms={name:np.zeros((1,len(x),21)) if name=="zero_disturbance" else rng.normal(0,.01,(64,len(x),21)) for name in policy.ARMS}
        if checkpoint:
            for name,values in arms.items():checkpoint(name,values)
        return arms

    def test_preflight_does_not_sample_solve_or_write_output(self):
        args=self.seal()
        with patch.object(workflow,"sample_arms") as sample,patch.object(policy,"response_costs") as solve:
            report,result=workflow.run(**args,preflight_only=True)
            sample.assert_not_called();solve.assert_not_called()
        self.assertIsNone(result)
        self.assertEqual(report["status"],"verified_parameter_selection_inputs_no_sampling_or_scores")
        self.assertEqual(len(report["fold_evidence"]),7)
        self.assertFalse(args["output"].exists())

    def test_design_only_does_not_sample_or_score_held(self):
        args=self.seal()
        with patch.object(workflow,"sample_arms") as sample,patch.object(policy,"evaluate_held") as held:
            report,result=workflow.run(**args,design_only=True)
            sample.assert_not_called();held.assert_not_called()
        self.assertEqual(report["status"],"complete_parameter_selection_design_ready")
        self.assertFalse(report["model_sampling_performed"]);self.assertFalse(report["held_scoring_performed"])
        with zipfile.ZipFile(result) as z:self.assertEqual(len(z.namelist()),11)
        self.assertFalse((args["output"]/"choices_frozen.private.json").exists())

    def test_uninformative_design_stops_full_run_before_real_sampling(self):
        args=self.seal();native=workflow.design_diagnostics
        def blocked(*a):
            report=native(*a);report["informative"]=False;report["reasons"]=["synthetic_noninformative"];return report
        with patch.object(workflow,"design_diagnostics",side_effect=blocked),patch.object(workflow,"sample_arms") as sample,patch.object(policy,"evaluate_held") as held:
            report,result=workflow.run(**args)
            sample.assert_not_called();held.assert_not_called()
        self.assertEqual(report["status"],"complete_parameter_selection_design_not_informative")
        self.assertTrue(result.exists());self.assertFalse((args["output"]/"choices_frozen.private.json").exists())

    def test_all_native_samplers_and_shared_grid_complete_one_fold(self):
        prepared=workflow.prepare_folds(self.bundle.inputs,self.bundle.marker,self.bundle.plan,self.bundle.checkpoint,self.bundle.families)[0]
        arms=workflow.sample_arms(prepared.training_pool,prepared.conditions,prepared.offsets,prepared.family)
        self.assertEqual(tuple(arms),policy.ARMS)
        grid=policy.grid_costs(arms,prepared.speeds,prepared.context_records)
        selected=policy.select_parameters(grid,[r["outing_id"] for r in prepared.context_records])
        self.assertEqual(len(selected["settings"]),6)
        self.assertTrue(all(np.isfinite(v).all() for v in arms.values()))

    def test_all_choices_are_written_before_any_held_scoring_and_zip_is_verified(self):
        args=self.seal();original_evaluate=policy.evaluate_held
        calls=[]
        def held(*positional):
            self.assertTrue((args["output"]/"choices_frozen.private.json").exists())
            for oid in self.bundle.ids:self.assertTrue((args["output"]/(oid+"_selection.private.json")).exists())
            calls.append("held")
            return original_evaluate(*positional)
        with patch.object(workflow,"sample_arms",side_effect=self.fake_arms),patch.object(policy,"evaluate_held",side_effect=held):
            report,result=workflow.run(**args)
        self.assertEqual(len(calls),7)
        self.assertTrue(report["all_choices_frozen_before_held_scoring"])
        self.assertFalse(report["model_refitted"]);self.assertFalse(report["planner_parameters_adopted"])
        with zipfile.ZipFile(result) as z:
            self.assertEqual(len(z.namelist()),90)
            self.assertIsNone(z.testzip())
            for line in z.read("SHA256SUMS").decode().splitlines():
                pin,name=line.split("  ",1);self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),pin)
            frozen=json.loads(z.read("parameter_selection/choices_frozen.private.json"))
            self.assertFalse(frozen["held_scoring_started"])
        self.assertRaisesRegex(ValueError,"new_output",workflow.run,**args)

    def test_failure_during_selection_preserves_prior_choices_without_held_scores(self):
        args=self.seal();counter=0
        def sample(*a,**kw):
            nonlocal counter
            counter+=1
            if counter==2:raise ValueError("synthetic_sample_failure")
            return self.fake_arms(*a,**kw)
        with patch.object(workflow,"sample_arms",side_effect=sample),patch.object(policy,"evaluate_held") as held:
            self.assertRaisesRegex(ValueError,"synthetic_sample_failure",workflow.run,**args)
            held.assert_not_called()
        self.assertTrue((args["output"]/"synthetic_0_selection.private.json").exists())
        self.assertTrue((args["output"]/"failure.private.json").exists())
        self.assertFalse((args["output"]/"choices_frozen.private.json").exists())

    def test_drift_stops_before_held_scoring_and_preserves_selection(self):
        args=self.seal();self.bundle.native.unchanged.side_effect=[None]*8+[ValueError("synthetic_drift")]
        with patch.object(workflow,"sample_arms",side_effect=self.fake_arms),patch.object(policy,"evaluate_held") as held:
            self.assertRaisesRegex(ValueError,"synthetic_drift",workflow.run,**args);held.assert_not_called()
        self.assertTrue((args["output"]/"synthetic_0_selection.private.json").exists())
        self.assertFalse(args["output"].with_name("result_results.zip").exists())

    def test_held_failure_preserves_all_choices_and_prior_held_scores(self):
        args=self.seal();native_evaluate=policy.evaluate_held;calls=0
        def held(*positional):
            nonlocal calls
            calls+=1
            if calls==2:raise ValueError("synthetic_held_failure")
            return native_evaluate(*positional)
        with patch.object(workflow,"sample_arms",side_effect=self.fake_arms),patch.object(policy,"evaluate_held",side_effect=held):
            self.assertRaisesRegex(ValueError,"synthetic_held_failure",workflow.run,**args)
        self.assertTrue((args["output"]/"choices_frozen.private.json").exists())
        self.assertTrue((args["output"]/"synthetic_0_held_scores.private.json").exists())
        failure=json.loads((args["output"]/"failure.private.json").read_bytes())
        self.assertEqual(failure["stage"],"held_residual_replay_synthetic_1")
        self.assertFalse(args["output"].with_name("result_results.zip").exists())

    def test_changed_frozen_choice_is_detected_before_publication(self):
        args=self.seal();native_evaluate=policy.evaluate_held;calls=0
        def held(*positional):
            nonlocal calls
            calls+=1
            if calls==7:
                path=args["output"]/"synthetic_0_selection.private.json"
                path.write_bytes(path.read_bytes()+b" ")
            return native_evaluate(*positional)
        with patch.object(workflow,"sample_arms",side_effect=self.fake_arms),patch.object(policy,"evaluate_held",side_effect=held):
            self.assertRaisesRegex(ValueError,"choices_changed",workflow.run,**args)
        self.assertTrue((args["output"]/"choices_frozen.private.json").exists())
        self.assertFalse(args["output"].with_name("result_results.zip").exists())

    def test_missing_context_or_changed_model_pin_blocks_preflight(self):
        self.bundle.plan["folds"][-1]["saved_model_sha256"]={**self.family.hashes,"conditional_flow":"9"*64}
        args=self.seal()
        with patch.object(workflow,"sample_arms") as sample:
            self.assertRaisesRegex(ValueError,"sealed_fold_evidence",workflow.run,**args,preflight_only=True)
            sample.assert_not_called()
        self.assertFalse(args["output"].exists())

    def test_output_inside_packet_or_previous_partial_is_rejected(self):
        args=self.seal()
        self.assertRaisesRegex(ValueError,"inside_prior_evidence",workflow.run,
            **{**args,"output":self.manifest.parent/"child"},preflight_only=True)
        args["output"].with_name("result_results.zip.partial").touch()
        self.assertRaisesRegex(ValueError,"new_output",workflow.run,**args,preflight_only=True)

    def test_held_residual_values_cannot_enter_own_training_context_or_empirical_pool(self):
        first=workflow.prepare_folds(self.bundle.inputs,self.bundle.marker,self.bundle.plan,self.bundle.checkpoint,self.bundle.families)[0]
        self.bundle.blocks[0].y[:]=1000.
        changed=workflow.prepare_folds(self.bundle.inputs,self.bundle.marker,self.bundle.plan,self.bundle.checkpoint,self.bundle.families)[0]
        np.testing.assert_array_equal(first.conditions,changed.conditions)
        np.testing.assert_array_equal(first.training_pool,changed.training_pool)
        arms=self.fake_arms(first.training_pool,first.conditions,first.offsets,first.family)
        left=policy.select_parameters(policy.grid_costs(arms,first.speeds,first.context_records),[r["outing_id"] for r in first.context_records])
        right=policy.select_parameters(policy.grid_costs(arms,changed.speeds,changed.context_records),[r["outing_id"] for r in changed.context_records])
        self.assertEqual(left,right)


if __name__=="__main__":
    unittest.main()
