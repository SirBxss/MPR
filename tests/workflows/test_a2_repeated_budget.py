"""Checks the repeated-budget support intersection and metadata-only contract."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import a2_budget_pilot as pilot, a2_rate_design as rate, a2_repeated_budget as support
from lane_residuals.domain.artifact_registry import RegistryError
from lane_residuals.io import a2_budget_pilot as reader, development_experiment as original
from lane_residuals.workflows import a2_budget_pilot as prior, a2_rate_design as rate_workflow, a2_repeated_budget as workflow
from lane_residuals.workflows.locked_development_export import write
from tests.workflows.test_a2_budget_pilot import PilotFixture


class RepeatedBudgetTests(unittest.TestCase):
    def test_all_subsets_use_the_same_intersection_without_bridge_or_retarget(self):
        outings = ("a", "b", "c", "d", "e")
        offsets = {oid: np.array([0, 4, 8]) for oid in outings}
        contexts = tuple(pilot.Sequence(oid, 0, 0, 3, (100_000_000,) * 2) for oid in outings)
        all_donors = {oid: [(0, 1), (4, 5)] for oid in outings}
        missing_one = {oid: values for oid, values in all_donors.items() if oid != "e"}
        parent = pilot.Panel(contexts, (all_donors,) * 4 + (missing_one,), {})
        common, evidence = support.support_panel(parent, offsets)
        self.assertEqual(common.contexts, contexts[:4])
        self.assertEqual(common.donors, (all_donors,) * 4)
        self.assertEqual(evidence["common_context_indices"], [0, 1, 2, 3])
        self.assertEqual(evidence["common_contexts_by_outing"]["e"], 0)
        self.assertEqual(evidence["reasons"], ["missing_common_contexts_for_calibration_outing"])
        self.assertEqual([sum(row["budget"] == n for row in evidence["subsets"]) for n in pilot.BUDGETS], [5, 10, 1])
        singleton = next(row for row in evidence["subsets"] if row["outing_ids"] == ["e"])
        self.assertEqual(singleton["windows_by_context"], [4, 4, 4, 4, 0])
        self.assertEqual(singleton["frames"], 8)
        self.assertTrue(singleton["native_fit_resources_supported"])
        self.assertEqual(evidence["subsets"][-1]["windows_by_context"], [20, 20, 20, 20, 16])

    def test_owner_preflight_replays_receipts_and_reads_calibration_metadata_only(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            fixture = PilotFixture(project)
            env = {"numpy": "fixture"}
            source60 = {"consumer_git_tree": rate_workflow.PR60_TREE,
                        "consumer_runtime_source_sha256": rate_workflow.PR60_RUNTIME,
                        "consumer_runtime_versions": env}
            source62 = {**source60, "consumer_git_tree": workflow.PR62_TREE,
                        "consumer_runtime_source_sha256": workflow.PR62_RUNTIME}
            args = fixture.arguments(root / "pr60")
            with patch.object(prior, "source_guard", return_value=source60):
                report60 = prior.preflight(**args)
            preflight = args["output"] / prior.PREFLIGHT
            fixture.numeric_paths[fixture.outings[-1]].unlink()
            self.assertFalse(fixture.numeric_paths[fixture.outings[0]].exists())
            inputs = reader.load_pinned_inputs(project, fixture.experiment, args["experiment_sha256"],
                                               args["archive_set_sha256"])
            plan, panel, covariates, _ = prior._preflight_plan(inputs)
            # Use a synthetic stop with the same six-index design contract as PR 62.
            reasons = [["nominal_peak_envelope_failed"], *[[] for _ in support.CANDIDATES],
                       ["outing_tracking_over_original_grid_allowance"]]
            with patch.object(rate, "_candidate_reasons", side_effect=reasons):
                design = rate.diagnose(panel, covariates, plan["nominal"], extend_upper=True)
            previous = root / "pr62"
            previous.mkdir()
            receipt = previous / rate_workflow.EXTENSION_RECEIPT
            stored = {
                "source": source62, "status": rate_workflow.EXTENSION_COMPLETE,
                "revision": rate_workflow.EXTENSION_REVISION, "protocol": rate.EXTENSION_PROTOCOL, "design": design,
                "pr60_preflight_sha256": original.sha(preflight),
                "panel_donor_index_sha256": report60["design"]["panel_donor_index_sha256"],
                "experiment_sha256": args["experiment_sha256"], "accepted_archive_set_sha256": args["archive_set_sha256"],
                "calibration_budget_selection_authorized": False, "residual_arrays_decoded": False,
                "model_fit_attempted": False, "outer_held_numeric_opened": False, "inner_audit_numeric_opened": False,
            }
            write(receipt, stored)
            args.update(output=root / "new", preflight=preflight, preflight_sha256=original.sha(preflight),
                        rate_receipt=receipt, rate_receipt_sha256=original.sha(receipt))
            with patch.object(reader, "open_accepted_outing") as opened:
                with self.assertRaisesRegex(RegistryError, "experiment_input_digest_mismatch"):
                    workflow.preflight(**{**args, "rate_receipt_sha256": "f" * 64})
                opened.assert_not_called()
                self.assertFalse(args["output"].exists())
            with (patch.object(prior, "source_guard", return_value=source62),
                  patch.object(rate, "_candidate_reasons", side_effect=reasons + [[] for _ in support.CANDIDATES]),
                  patch.object(reader, "_read_member", wraps=reader._read_member) as members,
                  patch.object(reader, "open_accepted_outing", wraps=reader.open_accepted_outing) as opened):
                result = workflow.preflight(**args)
                self.assertEqual(result["status"], workflow.READY)
                self.assertEqual(result["support"]["common_context_count"], 60)
                self.assertEqual(len(result["support"]["subsets"]), 16)
                self.assertEqual([row["candidate"] for row in result["nominal_fixed_grid"]], list(support.CANDIDATES))
                self.assertEqual([call.args[0].outing_id for call in opened.call_args_list], fixture.outings[1:6])
                self.assertTrue(all(call.kwargs == {"labels": False} for call in opened.call_args_list))
                self.assertEqual({call.args[1] for call in members.call_args_list}, set(reader.METADATA))
                self.assertFalse(result["calibration_budget_selection_authorized"])
                with self.assertRaises(FileExistsError):
                    workflow.preflight(**args)
            self.assertEqual(original.sha(receipt), args["rate_receipt_sha256"])
