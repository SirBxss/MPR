"""Regression tests for the prospective steering-rate screen."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import a2_budget_pilot as budget, a2_rate_design as rate, planner_parameter_design as moments
from lane_residuals.domain import planner_parameter_selection as a2
from lane_residuals.domain.artifact_registry import RegistryError
from lane_residuals.domain.recording_ingestion import RecordingIngestionError
from lane_residuals.io import a2_budget_pilot as reader, development_experiment as original
from lane_residuals.workflows import a2_budget_pilot as prior, a2_rate_design as workflow
from lane_residuals.workflows.locked_development_export import write

from .test_a2_budget_pilot import PilotFixture


class A2RateDesignTests(unittest.TestCase):
    def test_upper_search_stops_at_first_new_failed_gate(self):
        outings = [str(i) for i in range(5)]
        panel = budget.Panel(tuple(budget.Sequence(oid, 0, 0, 3, (100_000_000, 100_000_000))
                                   for oid in outings), (), {})
        covariates = {oid: np.full((3, 1), 15.) for oid in outings}
        nominal = {"training_outing_ids": outings, "grid_best_tracking_by_outing": [1.] * 5}
        fail = "nominal_peak_envelope_failed"
        with patch.object(rate, "_candidate_reasons", side_effect=[[]] * 5 + [[fail]]) as gates:
            result = rate.diagnose(panel, covariates, nominal, extend_upper=True)
        self.assertEqual(gates.call_count, 6)
        self.assertEqual(result["upper_stop"], "first_upper_nominal_gate_failure")
        self.assertEqual(result["candidates"][-1]["curvature_rate_weight"], 32768.)
        self.assertEqual(result["candidates"][-1]["nominal_gate_failures"], [fail])
        self.assertEqual(result["feasible_candidates"], list(range(5)))
        for probe in result["synthetic_covariance_probes"]:
            self.assertNotIn("5", probe["losses_by_candidate"])
            if probe["choice"] == 4:
                self.assertEqual(probe["upper_boundary"], "adjacent_weight_failed_nominal_gate")

    def test_upper_bracket_reuses_pins_and_metadata_without_held_files(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            fixture = PilotFixture(project)
            versions = {"numpy": "unchanged_fixture"}
            pr60 = {"consumer_git_tree": workflow.PR60_TREE,
                    "consumer_runtime_source_sha256": workflow.PR60_RUNTIME,
                    "consumer_runtime_versions": versions}
            pr61 = {**pr60, "consumer_git_tree": workflow.PR61_TREE,
                    "consumer_runtime_source_sha256": workflow.PR61_RUNTIME}
            with patch.object(prior, "source_guard", return_value=pr60):
                args = fixture.arguments(root / "preflight")
                self.assertEqual(prior.preflight(**args)["status"], prior.READY)
            preflight = args["output"] / prior.PREFLIGHT
            with patch.object(prior, "source_guard", return_value=pr61):
                args.update(output=root / "design", preflight=preflight, preflight_sha256=original.sha(preflight))
                self.assertEqual(workflow.run_design(**args)["status"], workflow.COMPLETE)
            completed = args["output"] / workflow.RECEIPT
            fixture.numeric_paths[fixture.outings[-1]].unlink()
            args.update(output=root / "upper", previous_design=completed, previous_design_sha256=original.sha(completed))
            source = {**pr61, "consumer_git_tree": "4" * 40}
            changed_environment = {**source, "consumer_runtime_versions": {"numpy": "different"}}
            with (patch.object(prior, "source_guard", return_value=changed_environment),
                  patch.object(reader, "open_accepted_outing") as opened):
                with self.assertRaisesRegex(RecordingIngestionError, "rate_design_pr61_runtime_versions"):
                    workflow.run_design(**args)
                opened.assert_not_called()
                self.assertFalse(args["output"].exists())
            with (patch.object(prior, "source_guard", return_value=source),
                  patch.object(reader, "_read_member", wraps=reader._read_member) as members,
                  patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened):
                result = workflow.run_design(**args)
                self.assertEqual(result["status"], workflow.EXTENSION_COMPLETE)
                self.assertEqual(result["pr61_design_sha256"], args["previous_design_sha256"])
                self.assertFalse(result["calibration_budget_selection_authorized"])
                self.assertEqual(result["design"]["upper_stop"], "feasible_upper_cap")
                self.assertEqual(result["design"]["candidates"][-1]["curvature_rate_weight"], 1048576.)
                self.assertTrue(any(probe["upper_boundary"] == "tested_range_edge"
                                    for probe in result["design"]["synthetic_covariance_probes"]))
                self.assertTrue(all(call.kwargs == {"labels": False} for call in opened.call_args_list))
                self.assertEqual([call.args[0].outing_id for call in opened.call_args_list], fixture.outings[1:6])
                self.assertNotIn("residuals_m", [call.args[1] for call in members.call_args_list])
                self.assertTrue((args["output"] / workflow.EXTENSION_RECEIPT).exists())
                with self.assertRaises(FileExistsError):
                    workflow.run_design(**args)
            self.assertEqual(original.sha(completed), args["previous_design_sha256"])

    def test_rate_map_native_parity_and_analytic_expectation(self):
        rng = np.random.default_rng(1127)
        speeds = (12., 12.1, 12.2, 12.3)
        intervals = (.11, .09, .12)
        state = np.array([.015, -.001, .0003])
        profile = rng.normal(0, .02, 21)
        covariance = moments.unit_covariance(len(speeds), .9)
        sigma = .02
        # A symmetric quadrature with exactly this covariance. This avoids an MC tolerance.
        samples = np.linalg.cholesky(covariance).T * sigma * np.sqrt(len(covariance))
        profiles = np.concatenate((samples, -samples)).reshape((-1, len(speeds), 21))
        for cfg in rate.CONFIGS + rate.UPPER_CONFIGS:
            with self.subTest(rate=cfg.weight_curvature_rate):
                native = a2.plan_reference_step(lateral_error_m=state[0], heading_error_rad=state[1],
                    previous_curvature_correction_per_m=state[2], residual_profile_m=profile,
                    stations_m=np.asarray(a2.STATIONS_M), speed_mps=speeds[0], dt_s=.1, config=cfg)
                gain, offset = a2.control_map_for_config(cfg, speeds[0])
                self.assertAlmostEqual(float(state @ gain + profile @ offset),
                                       native.curvature_correction_per_m, places=12)
                matrix = moments.quadratic_map_for_config(speeds, intervals, cfg)
                nominal, _, _ = rate.nominal_summary(np.array(speeds), np.array(intervals), cfg)
                direct = a2.rollout_costs_for_config(profiles, speeds, intervals, cfg, a2.TASKS)["loss"].mean()
                self.assertAlmostEqual(direct, nominal[-1] + sigma ** 2 * np.sum(matrix * covariance), places=12)

    def test_frozen_tracking_anchor_and_practical_tradeoff(self):
        peaks = np.array([[2., 4.]])
        self.assertEqual(rate._candidate_reasons(np.array([1.2]), np.array([1.2]), np.array([.65]), peaks), [])
        self.assertIn("outing_tracking_over_original_grid_allowance",
                      rate._candidate_reasons(np.array([1.21]), np.array([1.2]), np.array([.65]), peaks))
        self.assertIn("nominal_peak_envelope_failed",
                      rate._candidate_reasons(np.array([1.2]), np.array([1.2]), np.array([.65]), peaks + 2))
        macro = np.array([[.9, .1, 1.1, 2.1], [1., .1, 1., 2.1]])
        self.assertEqual(len(rate.describe_tradeoffs([0, 1], macro)), 1)
        self.assertEqual(rate._loss_summary(macro[:, -1], [0, 1])["near_optimal_candidates"], [0, 1])

    def test_pinned_panel_metadata_only_and_preserved_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            fixture = PilotFixture(project)
            source = {"consumer_git_tree": workflow.PR60_TREE,
                      "consumer_runtime_source_sha256": workflow.PR60_RUNTIME}
            before = root / "pr60"
            args = fixture.arguments(root / "design")
            with patch.object(prior, "source_guard", return_value=source):
                report = prior.preflight(**{**args, "output": before})
                self.assertEqual(report["status"], prior.READY)
                preflight = before / prior.PREFLIGHT
                pin = original.sha(preflight)
                fixture.numeric_paths[fixture.outings[-1]].unlink()
                with patch.object(reader, "open_accepted_outing") as unopened:
                    with self.assertRaisesRegex(RegistryError, "experiment_input_digest_mismatch"):
                        workflow.run_design(preflight=preflight, preflight_sha256="0" * 64, **args)
                    with self.assertRaisesRegex(RegistryError, "registry_output_overlaps_immutable_input"):
                        workflow.run_design(preflight=preflight, preflight_sha256=pin,
                                            **{**args, "output": before / "invalid"})
                    unopened.assert_not_called()
                with (patch.object(reader, "_read_member", wraps=reader._read_member) as members,
                      patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened):
                    result = workflow.run_design(preflight=preflight, preflight_sha256=pin, **args)
                    self.assertEqual(result["status"], workflow.COMPLETE)
                    design = result["design"]
                    self.assertEqual(design["context_count"], 60)
                    self.assertEqual(len(design["candidates"]), 5)
                    self.assertEqual(design["original_grid_best_tracking"],
                                     report["design"]["nominal"]["grid_best_tracking_by_outing"])
                    self.assertEqual(result["panel_donor_index_sha256"], report["design"]["panel_donor_index_sha256"])
                    self.assertEqual([call.args[0].outing_id for call in opened.call_args_list], fixture.outings[1:6])
                    self.assertTrue(all(call.kwargs == {"labels": False} for call in opened.call_args_list))
                    self.assertNotIn("residuals_m", [call.args[1] for call in members.call_args_list])
                self.assertFalse(result["calibration_budget_selection_authorized"])
                self.assertTrue((args["output"] / workflow.RECEIPT).is_file())
                self.assertEqual(original.sha(preflight), pin)
                with self.assertRaises(FileExistsError):
                    workflow.run_design(preflight=preflight, preflight_sha256=pin, **args)
                tampered = before / "bad.private.json"
                report["design"]["panel_donor_index_sha256"] = "1" * 64
                write(tampered, report)
                with self.assertRaisesRegex(RecordingIngestionError, "rate_design_pr60_panel_parity"):
                    workflow.run_design(preflight=tampered, preflight_sha256=original.sha(tampered),
                                        **{**args, "output": root / "failed"})
