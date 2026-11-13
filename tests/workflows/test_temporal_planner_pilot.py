"""Exercise temporal preflight, sampling, scoring and preservation on synthetic inputs."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

from lane_residuals.domain import temporal_planner_pilot as policy
from lane_residuals.io import development_experiment as original
from lane_residuals.io.temporal_planner_pilot import TemporalModels
from lane_residuals.modeling.matched_stationary_ar import StationaryAR
from lane_residuals.workflows import temporal_planner_pilot as workflow
from lane_residuals.workflows.locked_development_export import write
from tests.domain import test_cached_planner_scenarios as scenario_fixture
from tests.modeling import test_matched_one_state_ar as model_fixture


class TemporalPilotWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_fixture.MatchedOneStateTests.setUpClass()
        cls.one = model_fixture.MatchedOneStateTests.state

    def test_normal_entry_preflight_and_scores_with_native_samplers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            held = scenario_fixture.CachedScenarioPolicyTests().block()
            held.y = held.y / 100
            held.x[:, 0] = 20
            held.archive.arrays["estimate_source_time_ns_decimal"] = np.array(
                [str(10**19+i*50_000_000) for i in range(7)])
            held.offsets = np.array([0, 4])
            train = SimpleNamespace(outing_id="train", y=np.full((40, 21), .01))
            fold = dict(fold_id="held", validation_outing=held.outing_id, training_outings=["train"])
            marker = dict(folds=[fold])
            inputs = SimpleNamespace(
                blocks=[held, train], watched={}, unchanged=Mock(),
                request=dict(cohort_directory=str(root/"cohort"), original_registry_directory=str(root/"registry"),
                             export_receipt=str(root/"export.json"), descendants=[]))
            old_inputs = SimpleNamespace(watched={}, unchanged=Mock(), temporal_inputs=SimpleNamespace(watched={}))
            models = TemporalModels(self.one.transform_source,
                                    StationaryAR(self.one.transform_source, .8, 35, (30., 30., 20., 735)), self.one,
                                    dict(conditional_gaussian="a"*64, stationary_ar="b"*64, one_state_ar="c"*64))
            rows, _, _, support = policy.prepare(held, fold)
            plan = dict(revision=policy.REVISION, protocol=policy.PROTOCOL,
                        expected_support=support,
                        scenario_rows_sha256=hashlib.sha256(original.encoded(rows)).hexdigest(),
                        original_experiment_directory="experiment", original_experiment_sha256="d"*64,
                        one_state_experiment_directory="one_experiment", one_state_experiment_sha256="e"*64,
                        one_state_result_sha256="f"*64, accepted_spatial_result_sha256="0"*64,
                        accepted_spatial_tree="accepted", fold=fold, saved_model_sha256=models.hashes)
            packet = root / "packet"
            packet.mkdir()
            manifest = packet / "temporal_manifest.private.json"
            write(manifest, plan)
            args = dict(project=project, manifest_path=manifest, manifest_pin=original.sha(manifest),
                        one_state_zip=root/"one.zip", spatial_zip=root/"spatial.zip",
                        expected_tree="synthetic", expected_runtime="synthetic", output=root/"result")
            with patch.object(workflow, "source_guard", return_value={}), \
                 patch.object(workflow.original, "load_experiment", return_value=(inputs, marker)), \
                 patch.object(workflow, "load_models", return_value=(old_inputs, models)), \
                 patch.object(workflow, "accepted_spatial", return_value={}), \
                 patch.object(workflow, "draw_arms", wraps=workflow.draw_arms) as sample:
                with self.assertRaisesRegex(ValueError, "output_inside_prior_evidence"):
                    workflow.run(**{**args, "output": packet / "result"}, preflight_only=True)
                preflight, result = workflow.run(**args, preflight_only=True)
                self.assertIsNone(result)
                self.assertEqual(preflight["status"], "verified_temporal_pilot_inputs_no_scores")
                sample.assert_not_called()
                self.assertFalse(args["output"].exists())
                report, result = workflow.run(**args)
                self.assertEqual(sample.call_count, 1)
                self.assertEqual(report["status"], "complete_short_temporal_planner_pilot")
                self.assertEqual(report["support"]["eligible_sequences"], 1)
                with self.assertRaisesRegex(ValueError, "new_output"):
                    workflow.run(**args)
                failed_args = {**args, "output": root / "failed_result"}
                inputs.unchanged.side_effect = [None, ValueError("synthetic_input_drift")]
                with self.assertRaisesRegex(ValueError, "synthetic_input_drift"):
                    workflow.run(**failed_args)
                self.assertTrue((failed_args["output"] / "scores.private.json").exists())
                self.assertTrue((failed_args["output"] / "failure.private.json").exists())
                self.assertFalse((failed_args["output"] / "temporal_report.private.json").exists())
                self.assertFalse((root / "failed_result_results.zip").exists())
            with zipfile.ZipFile(result) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("temporal/scores.private.json", archive.namelist())
                for line in archive.read("SHA256SUMS").decode().splitlines():
                    digest, name = line.split("  ", 1)
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
            self.assertFalse(report["model_refitted"])

    def test_prefix_controls_preserve_the_prefix_frame_ensembles(self):
        rng = np.random.default_rng(4)
        native = rng.normal(size=(128, 4, 21))
        offsets = np.array([0, 4])
        prefix = workflow.assemble_arms(np.zeros((1, 4, 21)), native[:64], native[:64],
                                       native[:64], native[:64], offsets)
        for frame in range(4):
            np.testing.assert_array_equal(np.sort(prefix["one_state_ar"][:, frame], axis=0),
                                          np.sort(prefix["one_state_ar_permuted"][:, frame], axis=0))


if __name__ == "__main__":
    unittest.main()
