"""Exercise the seven fold orchestration and real samplers on synthetic data."""

from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

from lane_residuals.domain import temporal_planner_pilot as pilot, temporal_planner_replication as policy
from lane_residuals.io import development_experiment as original
from lane_residuals.io.temporal_planner_pilot import TemporalModels
from lane_residuals.io.temporal_planner_replication import load_pilot
from lane_residuals.modeling.aiohmm import AutoregressiveInputOutputHMM
from lane_residuals.modeling.matched_one_state_ar import OneStateAR
from lane_residuals.modeling.matched_stationary_ar import StationaryAR
from lane_residuals.workflows import temporal_planner_replication as workflow
from lane_residuals.workflows.locked_development_export import package, write
from tests.domain import test_cached_planner_scenarios as scenario_fixture
from tests.modeling import test_matched_one_state_ar as model_fixture


class TemporalReplicationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_fixture.MatchedOneStateTests.setUpClass()
        base = replace(model_fixture.MatchedOneStateTests.state.transform_source, training_rows=24)
        payload = model_fixture.MatchedOneStateTests.state.model.to_dict()
        payload["training_frame_count"] = 24  # Synthetic fixture population only.
        one = OneStateAR(base, AutoregressiveInputOutputHMM.from_dict(payload))
        cls.models = TemporalModels(base, StationaryAR(base, .8, 18, (10., 10., 5., 378)), one,
                                    dict(conditional_gaussian="a"*64, stationary_ar="b"*64, one_state_ar="c"*64))

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        ids = ["synthetic_" + str(i) for i in range(7)]
        self.folds = [dict(fold_id=outing, validation_outing=outing,
                           training_outings=[other for other in ids if other != outing]) for outing in ids]
        self.blocks = []
        for i, outing in enumerate(ids):
            block = scenario_fixture.CachedScenarioPolicyTests().block()
            block.outing_id = outing
            block.y = block.y / (100+i)
            block.x[:, 0] = 20
            block.offsets = np.array([0, 4])
            block.archive.arrays["estimate_source_time_ns_decimal"] = np.array(
                [str(10**19 + j*50_000_000) for j in range(7)])
            self.blocks.append(block)
        self.inputs = SimpleNamespace(blocks=self.blocks, watched={}, unchanged=Mock(),
             request=dict(cohort_directory=str(self.root/"cohort"), original_registry_directory=str(self.root/"registry"),
                          export_receipt=str(self.root/"export.json"), descendants=[]))
        self.native = SimpleNamespace(watched={}, unchanged=Mock(), temporal_inputs=SimpleNamespace(watched={}))
        self.source = dict(consumer_git_commit="synthetic", consumer_git_tree="synthetic",
                           consumer_runtime_source_sha256="synthetic")
        self.plan = dict(revision=policy.REVISION, protocol=policy.PROTOCOL,
             original_experiment_directory="original", original_experiment_sha256="d"*64,
             one_state_experiment_directory="one", one_state_experiment_sha256="e"*64,
             one_state_result_sha256="f"*64, accepted_spatial_result_sha256="0"*64,
             accepted_spatial_tree="synthetic", pilot_outing=ids[0], pilot_source=self.source, folds=[])
        self.records = []
        for fold, block in zip(self.folds, self.blocks):
            rows, arrays, records, support = pilot.prepare(block, fold)
            self.records.append(records)
            self.plan["folds"].append(dict(fold=fold, expected_support=support, training_rows=24,
                validation_archive_sha256=block.archive.summary_sha256, saved_model_sha256=self.models.hashes,
                scenario_rows_sha256=hashlib.sha256(original.encoded(rows)).hexdigest()))
        first = self.plan["folds"][0]
        held = self.blocks[0]
        _, arrays, _, _ = pilot.prepare(held, self.folds[0])
        arms = workflow.draw_arms(np.concatenate([b.y for b in self.blocks[1:]]), held.x, held.offsets, self.models)
        scores = pilot.score(arrays, self.records[0], arms)
        prefix = workflow.assemble_arms(arms["nominal"], arms["empirical"][:64], arms["conditional_gaussian"][:64],
                                        arms["stationary_ar"][:64], arms["one_state_ar"][:64], held.offsets)
        self.pilot_scores = scores
        self.pilot_manifest = {k: self.plan[k] for k in ("original_experiment_directory", "original_experiment_sha256",
             "one_state_experiment_directory", "one_state_experiment_sha256", "one_state_result_sha256",
             "accepted_spatial_result_sha256", "accepted_spatial_tree")}
        self.pilot_manifest.update(revision=pilot.REVISION, protocol=pilot.PROTOCOL,
             **{k: first[k] for k in ("fold", "expected_support", "saved_model_sha256", "scenario_rows_sha256")})
        self.pilot_report = dict(revision=pilot.REVISION, status="complete_short_temporal_planner_pilot",
             protocol=pilot.PROTOCOL, source=self.source, fold=first["fold"], support=first["expected_support"],
             saved_model_sha256=first["saved_model_sha256"], scenario_rows_sha256=first["scenario_rows_sha256"],
             training_rows=24, scores=policy.aggregates(scores),
             prefix_scores=policy.aggregates(pilot.score(arrays, self.records[0], prefix)),
             **{k: False for k in ("raw_payload_opened", "model_refitted", "new_recordings_admitted", "final_evaluation_authorized")})
        for target, name, result in ((workflow, "source_guard", self.source),
             (workflow.original, "load_experiment", (self.inputs, dict(folds=self.folds))),
             (workflow, "load_all_models", (self.native, {f["fold_id"]: self.models for f in self.folds})),
             (workflow, "accepted_spatial", {})):
            p = patch.object(target, name, return_value=result)
            p.start()
            self.addCleanup(p.stop)

    def seal(self):
        evidence = self.root / "pilot"
        evidence.mkdir()
        write(evidence/"temporal_manifest.private.json", self.pilot_manifest)
        self.plan["accepted_pilot_manifest_sha256"] = original.sha(evidence/"temporal_manifest.private.json")
        self.pilot_report["manifest_sha256"] = self.plan["accepted_pilot_manifest_sha256"]
        write(evidence/"temporal_report.private.json", self.pilot_report)
        write(evidence/"scores.private.json", self.pilot_scores)
        write(evidence/"sequences.private.json", self.records[0])
        archive = self.root / "pilot.zip"
        package(archive, [(evidence, "temporal")])
        self.plan["accepted_pilot_result_sha256"] = original.sha(archive)
        packet = self.root / "packet"
        packet.mkdir()
        manifest = packet / "replication_manifest.private.json"
        write(manifest, self.plan)
        return dict(project=self.project, manifest_path=manifest, manifest_pin=original.sha(manifest),
                    one_state_zip=self.root/"one.zip", spatial_zip=self.root/"spatial.zip", pilot_zip=archive,
                    expected_tree="synthetic", expected_runtime="synthetic", output=self.root/"result")

    def test_preflight_then_seven_native_sampler_folds_and_checksum_return(self):
        args = self.seal()
        with patch.object(workflow, "draw_arms", wraps=workflow.draw_arms) as sample:
            report, result = workflow.run(**args, preflight_only=True)
            sample.assert_not_called()
            self.assertIsNone(result)
            self.assertEqual(len(report["fold_support"]), 7)
            self.assertFalse(args["output"].exists())
            report, result = workflow.run(**args)
            self.assertEqual(sample.call_count, 7)
        self.assertTrue(report["pilot_score_parity_verified"])
        self.assertEqual(report["status"], "complete_development_temporal_replication")
        self.assertFalse(report["model_refitted"])
        self.assertEqual(report["summary"]["six_beyond_pilot"]["outing_count"], 6)
        with zipfile.ZipFile(result) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), 31)
            for line in archive.read("SHA256SUMS").decode().splitlines():
                pin, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), pin)
        self.assertRaisesRegex(ValueError, "new_output", workflow.run, **args)

    def test_main_or_prefix_parity_failure_blocks_sampling_other_outings(self):
        self.pilot_report["prefix_scores"]["arms"]["nominal"][policy.ENERGY] += .01
        args = self.seal()
        with patch.object(workflow, "draw_arms", wraps=workflow.draw_arms) as sample:
            self.assertRaisesRegex(ValueError, "pilot_parity_mismatch", workflow.run, **args)
            self.assertEqual(sample.call_count, 1)
        self.assertTrue((args["output"]/"synthetic_0_scores.private.json").exists())
        self.assertTrue((args["output"]/"failure.private.json").exists())
        self.assertFalse(args["output"].with_name("result_results.zip").exists())

    def test_coherent_but_different_pilot_main_scores_stop_after_one_fold(self):
        self.pilot_scores["sequence_scores"][0]["arms"]["nominal"][policy.ENERGY] += .1
        self.pilot_scores["arms"]["nominal"][policy.ENERGY] += .1
        self.pilot_report["scores"] = policy.aggregates(self.pilot_scores)
        args = self.seal()
        with patch.object(workflow, "draw_arms", wraps=workflow.draw_arms) as sample:
            self.assertRaisesRegex(ValueError, "pilot_parity_mismatch", workflow.run, **args)
            self.assertEqual(sample.call_count, 1)

    def test_prefix_failure_keeps_main_scores_and_original_censuses(self):
        args = self.seal()
        original_score = pilot.score
        def fail_prefix(arrays, records, arms):
            if len(arms["one_state_ar"]) == 64:
                raise ValueError("synthetic_prefix_failure")
            return original_score(arrays, records, arms)
        with patch.object(workflow.scoring, "score", side_effect=fail_prefix):
            self.assertRaisesRegex(ValueError, "prefix_failure", workflow.run, **args)
        self.assertTrue((args["output"]/"synthetic_0_scores.private.json").exists())
        self.assertTrue((args["output"]/"synthetic_6_sequences.private.json").exists())
        self.assertFalse((args["output"]/"synthetic_0_prefix_scores.private.json").exists())

    def test_changed_reviewed_state_pin_blocks_preflight(self):
        self.plan["folds"][-1]["saved_model_sha256"] = {**self.models.hashes, "one_state_ar": "9"*64}
        args = self.seal()
        with patch.object(workflow, "draw_arms") as sample:
            self.assertRaisesRegex(ValueError, "fold_evidence_mismatch", workflow.run, **args, preflight_only=True)
            sample.assert_not_called()
        self.assertFalse(args["output"].exists())

    def test_input_drift_preserves_first_scores_and_blocks_remaining_outings(self):
        args = self.seal()
        self.inputs.unchanged.side_effect = [None, ValueError("synthetic_drift")]
        with patch.object(workflow, "draw_arms", wraps=workflow.draw_arms) as sample:
            self.assertRaisesRegex(ValueError, "synthetic_drift", workflow.run, **args)
            self.assertEqual(sample.call_count, 1)
        self.assertTrue((args["output"]/"synthetic_0_scores.private.json").exists())
        self.assertTrue((args["output"]/"failure.private.json").exists())
        self.assertFalse((args["output"]/"replication_report.private.json").exists())

    def test_output_inside_packet_or_existing_partial_is_rejected(self):
        args = self.seal()
        self.assertRaisesRegex(ValueError, "inside_prior_evidence", workflow.run,
                               **{**args, "output": args["manifest_path"].parent/"child"}, preflight_only=True)
        args["output"].with_name("result_results.zip.partial").touch()
        self.assertRaisesRegex(ValueError, "new_output", workflow.run, **args, preflight_only=True)

    def test_last_fold_empty_or_budget_failure_stops_before_sampling(self):
        args = self.seal()
        with patch.object(workflow, "draw_arms") as sample:
            self.blocks[-1].x[:, 0] = 0
            self.assertRaisesRegex(ValueError, "empty_primary_fold", workflow.run, **args, preflight_only=True)
            self.blocks[-1].x[:, 0] = 20
            with patch.object(workflow, "MAX_SAMPLED_PADDED_FRAMES", 1):
                self.assertRaisesRegex(ValueError, "sampling_budget", workflow.run, **args, preflight_only=True)
            sample.assert_not_called()
        self.assertFalse(args["output"].exists())

    def test_reader_rejects_scope_or_aggregate_drift(self):
        self.pilot_report["model_refitted"] = True
        args = self.seal()
        self.assertRaisesRegex(ValueError, "accepted_pilot_lineage", load_pilot, args["pilot_zip"],
                               self.plan["accepted_pilot_result_sha256"], self.plan)


if __name__ == "__main__":
    unittest.main()
