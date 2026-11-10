"""Exercise the owner workflow on artificial cache and frozen model fixtures."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

from lane_residuals.domain.cached_planner_scenarios import PROTOCOL
from lane_residuals.io.development_experiment import encoded, sha
from lane_residuals.io.spatial_planner_pilot import SavedSpatialModels
from lane_residuals.modeling.matched_flow import CONFIGURATION, MatchedFlow
from lane_residuals.modeling.matched_gaussian import MatchedGaussian
from lane_residuals.workflows import cached_planner_scenarios, spatial_planner_pilot
from tests.domain import test_cached_planner_scenarios


class SpatialPlannerPilotWorkflowTests(unittest.TestCase):
    def test_replays_cache_draws_and_publishes_verified_archive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            held = test_cached_planner_scenarios.CachedScenarioPolicyTests().block()
            held.archive.arrays["residuals_m"] = np.zeros((7, 21))
            held.y = held.y / 100
            train = SimpleNamespace(outing_id="outing_b", y=np.full((8, 21), 0.05))
            fold = {"fold_id": "held", "validation_outing": held.outing_id,
                    "training_outings": [train.outing_id]}
            marker = {"protocol": {"stations_m": PROTOCOL["stations_m"]}, "folds": [fold],
                      **{key: "a" * 64 for key in ("row_manifest_sha256", "original_cohort_sha256",
                                                   "original_registry_sha256", "latest_registry_sha256")}}
            request = {"cohort_directory": str(root / "cohort"),
                       "original_registry_directory": str(root / "registry"),
                       "export_receipt": str(root / "export.json"), "descendants": []}
            inputs = SimpleNamespace(blocks=[held, train], request=request, unchanged=Mock(), watched={})
            h = CONFIGURATION["hidden_width"]
            models = SavedSpatialModels(
                MatchedGaussian("unconditional_gaussian", np.zeros(21), np.ones(21),
                                np.zeros(6), np.ones(6), np.zeros(21), np.zeros((6, 21)), np.eye(21), 8, 1),
                MatchedFlow("unconditional", np.zeros(21), np.ones(21), np.zeros(6), np.ones(6),
                            np.zeros((22, h)), np.zeros(h), np.zeros((h, 21)), np.zeros(21), (0.0,), 8, 8, 42),
                {},
            )
            pin = hashlib.sha256(encoded(marker)).hexdigest()
            folder = root / "experiment"
            args = dict(project=project, experiment_directory=folder,
                        expected_tree="synthetic", expected_runtime="synthetic")
            with patch.object(cached_planner_scenarios.original, "load_experiment", return_value=(inputs, marker)), \
                 patch.object(cached_planner_scenarios, "source_guard", return_value={}), \
                 patch.object(spatial_planner_pilot, "source_guard", return_value={}), \
                 patch.object(spatial_planner_pilot, "load_saved_models", return_value=models):
                _, scenarios = cached_planner_scenarios.prepare(
                    **args, expected_experiment_sha256=pin, output_directory=root / "scenario")
                run_args = dict(**args, experiment_sha256=pin, scenario_zip=scenarios,
                                flow_zip=root / "synthetic_flow.zip", flow_sha256="b" * 64,
                                output=root / "pilot")
                with self.assertRaisesRegex(ValueError, "pilot_input_zip_digest_mismatch"):
                    spatial_planner_pilot.run(**run_args, scenario_sha256="c" * 64)
                self.assertFalse(run_args["output"].exists())
                report, result = spatial_planner_pilot.run(**run_args, scenario_sha256=sha(scenarios))
                with self.assertRaisesRegex(ValueError, "preserve_existing"):
                    spatial_planner_pilot.run(**run_args, scenario_sha256=sha(scenarios))
            self.assertEqual(report["status"], "complete_recorded_spatial_planner_pilot")
            self.assertEqual(report["scores"]["primary"]["rows"], 1)
            self.assertEqual(report["held_geometry_rows"], 7)
            self.assertEqual(report["training_rows"], 8)
            self.assertFalse(report["model_refitted"])
            with zipfile.ZipFile(result) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {"pilot/pilot_report.private.json", "SHA256SUMS"})


if __name__ == "__main__":
    unittest.main()
