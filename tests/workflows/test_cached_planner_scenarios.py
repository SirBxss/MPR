from contextlib import ExitStack
import builtins
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from lane_residuals.workflows import cached_planner_scenarios as workflow
from tests.workflows import test_development_experiment as fixtures


class CachedPlannerScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.DevelopmentExperimentTests.setUpClass()
        cls.addClassCleanup(fixtures.DevelopmentExperimentTests.doClassCleanups)
        fixture = fixtures.DevelopmentExperimentTests()
        fixture.setUp()
        cls.addClassCleanup(fixture.doCleanups)
        cls.fixture = fixture
        _, cls.pin = fixture.prepare()

    def test_native_cache_preparation_without_raw_models_or_planner_scores(self):
        fixture = self.fixture
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "scenario"
            def guarded(function):
                def call(path, *args, **kwargs):
                    if isinstance(path, (str, bytes, os.PathLike)):
                        value = os.fsdecode(path).lower()
                        if value.endswith((".mcap", ".mcap.zst")):
                            raise AssertionError("raw endpoint requested during cached preparation")
                    return function(path, *args, **kwargs)
                return call
            for obj, name in ((os, "stat"), (os, "lstat"), (os, "open"), (builtins, "open"), (io, "open")):
                stack.enter_context(patch.object(obj, name, guarded(getattr(obj, name))))
            for module, name in (
                ("lane_residuals.modeling.matched_gaussian.MatchedGaussian", "sample"),
                ("lane_residuals.modeling.matched_flow", "fit_matched_flow"),
                ("lane_residuals.modeling.matched_flow", "sample_matched_flow"),
                ("lane_residuals.domain.reference_planner", "plan_reference_step"),
                ("lane_residuals.domain.reference_planner", "plan_reference_horizon"),
            ):
                stack.enter_context(patch(module + "." + name, side_effect=AssertionError("model or planner operation")))
            stack.enter_context(patch.object(workflow, "source_guard", return_value=fixture.source))
            report, result = workflow.prepare(
                project=fixture.project, experiment_directory=fixture.experiment,
                expected_experiment_sha256=self.pin, expected_tree="synthetic",
                expected_runtime="synthetic", output_directory=output,
            )
            self.assertEqual(report["status"], "complete_cached_spatial_scenario_preparation")
            self.assertEqual(report["summary"]["original_complete_rows"], 501)
            self.assertEqual(report["fold"]["validation_outing"], "outing_001")
            self.assertFalse(report["raw_payload_opened"])
            self.assertFalse(report["model_sampling_executed"])
            self.assertFalse(report["planner_scoring_executed"])
            with zipfile.ZipFile(result) as archive:
                self.assertIsNone(archive.testzip())
                for line in archive.read("SHA256SUMS").decode().splitlines():
                    digest, name = line.split("  ", 1)
                    import hashlib
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
            with np.load(output / "scenario_arrays.npz", allow_pickle=False) as archive:
                self.assertEqual(archive["residuals_m"].shape, (501, 21))
                self.assertEqual(len(archive["eligible"]), 501)
            report_path = output / "scenario_manifest.private.json"
            self.assertEqual(json.loads(report_path.read_text()), report)
            with self.assertRaisesRegex(ValueError, "preserve_existing"):
                workflow.prepare(
                    project=fixture.project, experiment_directory=fixture.experiment,
                    expected_experiment_sha256=self.pin, expected_tree="synthetic",
                    expected_runtime="synthetic", output_directory=output,
                )

    def test_wrong_pin_is_rejected_before_output(self):
        fixture = self.fixture
        with tempfile.TemporaryDirectory() as directory, patch.object(workflow, "source_guard", return_value=fixture.source):
            output = Path(directory) / "scenario"
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                workflow.prepare(
                    project=fixture.project, experiment_directory=fixture.experiment,
                    expected_experiment_sha256="f" * 64, expected_tree="synthetic",
                    expected_runtime="synthetic", output_directory=output,
                )
            self.assertFalse(output.exists())


class ScenarioFailureTests(unittest.TestCase):
    def arguments(self, root):
        from types import SimpleNamespace
        from lane_residuals.domain import cached_planner_scenarios as policy
        from tests.domain import test_cached_planner_scenarios as small
        from unittest.mock import Mock
        project = root / "project"
        project.mkdir()
        block = small.CachedScenarioPolicyTests().block()
        fold = {"validation_outing": block.outing_id, "training_outings": ["outing_b"], "fold_id": "held"}
        request = {"cohort_directory": str(root / "cohort"),
                   "original_registry_directory": str(root / "registry"),
                   "export_receipt": str(root / "export.json"), "descendants": []}
        inputs = SimpleNamespace(blocks=[block], request=request, unchanged=Mock())
        marker = {"protocol": {"stations_m": policy.PROTOCOL["stations_m"]}, "folds": [fold],
                  **{key: "a" * 64 for key in ("row_manifest_sha256", "original_cohort_sha256",
                     "original_registry_sha256", "latest_registry_sha256")}}
        arguments = dict(
            project=project, experiment_directory=root / "original",
            expected_experiment_sha256="a" * 64, expected_tree="synthetic",
            expected_runtime="synthetic", output_directory=root / "new",
        )
        return inputs, marker, arguments

    def test_failure_preserves_rows_and_packages_partial_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs, marker, arguments = self.arguments(Path(directory))
            with patch.object(workflow.original, "load_experiment", return_value=(inputs, marker)), \
                 patch.object(workflow, "source_guard", return_value={}), \
                 patch.object(workflow.np, "savez_compressed", side_effect=OSError("synthetic storage failure")):
                with self.assertRaisesRegex(OSError, "storage failure"):
                    workflow.prepare(**arguments)
            output = arguments["output_directory"]
            self.assertTrue((output / "scenario_rows.private.json").is_file())
            self.assertTrue((output / "failure.private.json").is_file())
            self.assertFalse((output / "scenario_manifest.private.json").exists())
            with zipfile.ZipFile(output.with_name(output.name + "_results.zip")) as archive:
                self.assertIn("scenarios/failure.private.json", archive.namelist())
                self.assertIsNone(archive.testzip())

    def test_input_drift_refuses_completion_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs, marker, arguments = self.arguments(Path(directory))
            inputs.unchanged.side_effect = [None, ValueError("input drift")]
            with patch.object(workflow.original, "load_experiment", return_value=(inputs, marker)), \
                 patch.object(workflow, "source_guard", return_value={}):
                with self.assertRaisesRegex(ValueError, "input drift"):
                    workflow.prepare(**arguments)
            output = arguments["output_directory"]
            self.assertTrue((output / "scenario_arrays.npz").is_file())
            self.assertTrue((output / "failure.private.json").is_file())
            self.assertFalse((output / "scenario_manifest.private.json").exists())

    def test_output_inside_existing_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, marker, arguments = self.arguments(root)
            (root / "run_receipt.json").write_text("{}")
            with patch.object(workflow.original, "load_experiment", return_value=(inputs, marker)), \
                 patch.object(workflow, "source_guard", return_value={}):
                with self.assertRaisesRegex(ValueError, "prior_evidence"):
                    workflow.prepare(**arguments)
            self.assertFalse(arguments["output_directory"].exists())
