"""Exercise the seven outing workflow with sealed synthetic inputs."""

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

from lane_residuals.domain import cached_planner_scenarios as scenarios
from lane_residuals.domain.spatial_planner_pilot import PEAK, REVISION as PILOT_REVISION, score_spatial_pilot
from lane_residuals.domain.spatial_planner_replication import PROTOCOL, REVISION, scores_match, summarize_outings
from lane_residuals.io import development_experiment as original
from lane_residuals.io.spatial_planner_pilot import SavedSpatialModels
from lane_residuals.modeling.matched_flow import CONFIGURATION, MatchedFlow
from lane_residuals.modeling.matched_gaussian import MatchedGaussian
from lane_residuals.workflows import cached_planner_scenarios, spatial_planner_replication as replication
from lane_residuals.workflows.locked_development_export import package, write
from tests.domain.test_cached_planner_scenarios import CachedScenarioPolicyTests


class SpatialPlannerReplicationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.ids = ["outing_" + str(i) for i in range(7)]
        self.folds = [{"fold_id": "hold_out_" + held, "validation_outing": held,
                       "training_outings": [other for other in self.ids if other != held]} for held in self.ids]
        self.blocks = []
        for i, outing in enumerate(self.ids):
            block = CachedScenarioPolicyTests().block()
            block.outing_id = outing
            block.y = block.y / (100 + i)
            block.archive.arrays["residuals_m"] = np.zeros((7, 21))
            block.x[:, 0] = [20, 20, 20, 20] if i == 0 else [20, 0, 0, 0]
            if i == 1:
                block.x[:, 0] = [38, 0, 0, 0]
            self.blocks.append(block)
        self.marker = {"protocol": {"stations_m": scenarios.PROTOCOL["stations_m"]}, "folds": self.folds,
                       **{key: "a" * 64 for key in ("row_manifest_sha256", "original_cohort_sha256",
                                                    "original_registry_sha256", "latest_registry_sha256")}}
        self.marker_pin = hashlib.sha256(original.encoded(self.marker)).hexdigest()
        self.inputs = SimpleNamespace(
            blocks=self.blocks, watched={}, unchanged=Mock(),
            request={"cohort_directory": str(self.root / "cohort"),
                     "original_registry_directory": str(self.root / "registry"),
                     "export_receipt": str(self.root / "export.json"), "descendants": []},
        )
        width = CONFIGURATION["hidden_width"]
        self.models = SavedSpatialModels(
            MatchedGaussian("unconditional_gaussian", np.zeros(21), np.ones(21), np.zeros(6), np.ones(6),
                            np.zeros(21), np.zeros((6, 21)), np.eye(21), 24, 1),
            MatchedFlow("unconditional", np.zeros(21), np.ones(21), np.zeros(6), np.ones(6),
                        np.zeros((22, width)), np.zeros(width), np.zeros((width, 21)), np.zeros(21),
                        (0.0,), 24, 24, 42),
            {"gaussian": "b" * 64, "flow": "c" * 64, "flow_solver_calibration": "d" * 64},
        )
        self.source = dict(consumer_git_commit="test", consumer_git_tree="test",
                           consumer_runtime_source_sha256="test")
        for target, name, result in (
            (original, "load_experiment", (self.inputs, self.marker)),
            (replication, "source_guard", self.source),
            (cached_planner_scenarios, "source_guard", self.source),
            (replication, "load_saved_models", self.models),
        ):
            patcher = patch.object(target, name, return_value=result)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.experiment = self.root / "experiment"
        _, scenario_zip = cached_planner_scenarios.prepare(
            project=self.project, experiment_directory=self.experiment,
            expected_experiment_sha256=self.marker_pin, expected_tree="test",
            expected_runtime="test", output_directory=self.root / "scenario")
        self.plan = {
            "revision": REVISION, "protocol": PROTOCOL, "planner_protocol": scenarios.PROTOCOL,
            "pilot_outing": self.ids[0], "pilot_source": self.source,
            "original_experiment_sha256": self.marker_pin, "scenario_zip_sha256": original.sha(scenario_zip),
            "flow_result_zip_sha256": "e" * 64,
            "folds": [{"fold": fold, "validation_archive_sha256": "a" * 64,
                       "saved_model_and_solver_sha256": self.models.hashes, "training_rows": 24,
                       "held_geometry_rows": 7, "held_complete_feature_rows": 4, "held_sequences": 2}
                      for fold in self.folds],
        }
        rows, arrays, _ = scenarios.prepare_scenario_rows(self.blocks[0], self.folds[0])
        draws = replication.draw_arms(np.concatenate([b.y for b in self.blocks[1:]]), self.models)
        self.pilot = {
            **{k: v for k, v in self.plan["folds"][0].items() if k != "validation_archive_sha256"},
            **{k: self.plan[k] for k in
               ("original_experiment_sha256", "scenario_zip_sha256", "flow_result_zip_sha256")},
            **replication.SCOPE,
            "status": "complete_recorded_spatial_planner_pilot", "revision": PILOT_REVISION,
            "protocol": PROTOCOL["scoring"], "source": self.source,
            "scores": score_spatial_pilot(arrays, rows, draws),
        }
        self.arguments = dict(project=self.project, experiment_directory=self.experiment,
                              scenario_zip=scenario_zip, flow_zip=self.root / "flow.zip",
                              expected_tree="test", expected_runtime="test", output=self.root / "replication")

    def seal(self):
        pilot_dir = self.root / "pilot"
        pilot_dir.mkdir()
        write(pilot_dir / "pilot_report.private.json", self.pilot)
        pilot_zip = self.root / "pilot.zip"
        package(pilot_zip, [(pilot_dir, "pilot")])
        self.plan["accepted_pilot_zip_sha256"] = original.sha(pilot_zip)
        plan_file = self.root / "plan.private.json"
        write(plan_file, self.plan)
        return dict(**self.arguments, pilot_zip=pilot_zip, manifest_path=plan_file,
                    manifest_sha256=original.sha(plan_file))

    def test_preflight_and_complete_run_keep_equal_outing_weights(self):
        args = self.seal()
        with patch.object(replication, "score_spatial_pilot", wraps=score_spatial_pilot) as scorer:
            preflight, result = replication.run(**args, preflight_only=True)
            self.assertIsNone(result)
            self.assertEqual(preflight["status"], "verified_replication_inputs_no_scores")
            scorer.assert_not_called()
            report, result = replication.run(**args)
            self.assertEqual(scorer.call_count, 7)
        self.assertTrue(report["pilot_score_parity_verified"])
        all_seven = report["summary"]["all_seven"]
        six = report["summary"]["six_beyond_pilot"]
        self.assertEqual(six["outing_ids"], self.ids[1:])
        self.assertEqual(six["speed_sensitivity"]["outings_without_common_support"], [self.ids[1]])
        self.assertIsNone(six["speed_sensitivity"]["macro"])
        with zipfile.ZipFile(result) as z:
            self.assertIsNone(z.testzip())
            scores = [json.loads(z.read("replication/" + i + "_scores.private.json"))["scores"]["primary"]
                      for i in self.ids]
        values = [p["arms"]["empirical"][PEAK]["crps"] for p in scores]
        self.assertAlmostEqual(all_seven["primary"]["arms"]["empirical"][PEAK]["crps"], sum(values) / 7)
        self.assertAlmostEqual(six["primary"]["arms"]["empirical"][PEAK]["crps"], sum(values[1:]) / 6)
        with self.assertRaisesRegex(ValueError, "new_output"):
            replication.run(**args)

    def test_pilot_parity_failure_blocks_six_other_outings(self):
        self.pilot = copy.deepcopy(self.pilot)
        self.pilot["scores"]["primary"]["arms"]["empirical"][PEAK]["crps"] += 0.01
        args = self.seal()
        with patch.object(replication, "score_spatial_pilot", wraps=score_spatial_pilot) as scorer:
            with self.assertRaisesRegex(ValueError, "pilot_parity_mismatch"):
                replication.run(**args)
            self.assertEqual(scorer.call_count, 1)
        self.assertTrue((args["output"] / "failure.private.json").exists())
        self.assertTrue((args["output"] / "outing_0_scores.private.json").exists())
        self.assertFalse(args["output"].with_name("replication_results.zip").exists())

    def test_missing_primary_support_stops_preflight(self):
        self.blocks[-1].x[:, 0] = 0
        args = self.seal()
        with self.assertRaisesRegex(ValueError, "eligibility"):
            replication.run(**args)
        self.assertFalse(args["output"].exists())

    def test_complete_common_support_is_averaged_per_outing(self):
        scores = {i: copy.deepcopy(self.pilot["scores"]) for i in self.ids}
        for index, value in enumerate(scores.values()):
            value["speed_sensitivity"]["plus_4_mps"]["replay"][PEAK]["mean"] = float(index)
        result = summarize_outings(scores, self.ids[0])
        for group, expected in (("all_seven", 3.0), ("six_beyond_pilot", 3.5)):
            speed = result[group]["speed_sensitivity"]
            self.assertEqual(speed["status"], "complete")
            self.assertEqual(speed["macro"]["plus_4_mps"]["replay"][PEAK]["mean"], expected)

    def test_parity_tolerance_does_not_apply_to_counts(self):
        self.assertTrue(scores_match({"score": 0.123}, {"score": 0.123 + 1e-13}))
        self.assertFalse(scores_match({"count": 1}, {"count": 1.0}))


if __name__ == "__main__":
    unittest.main()
