"""Synthetic native four model lineage and real adapter lifecycle.

Only synthetic fixtures use reduced epochs and draws to keep the suite small.
Producer/source substitutions here cannot authorize any owner operation.
"""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from lane_residuals.io import development_experiment as previous, development_flow as contract
from lane_residuals.workflows import development_flow as workflow
from lane_residuals.modeling.matched_flow import MatchedFlow, CONFIGURATION
from lane_residuals.modeling.matched_flow_evaluation import comparison
from tests.workflows import test_development_one_state as legacy


class DevelopmentFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        legacy.DevelopmentOneStateTests.setUpClass()
        cls.addClassCleanup(legacy.DevelopmentOneStateTests.doClassCleanups)
        cls.native = legacy.DevelopmentOneStateTests()
        cls.native.setUp()
        cls.addClassCleanup(cls.native.doCleanups)
        _, cls.prior_pin = cls.native.prepare()
        if cls.native.train(cls.prior_pin, cls.native.adopt(cls.prior_pin)) != 0:
            raise AssertionError("Synthetic one state predecessor failed")

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.project = self.root/"project"
        shutil.copytree(self.native.project, self.project)
        self.source = self.native.source
        for p in (patch.object(contract, "ONE_STATE_SOURCE", tuple(self.source[k] for k in
                    ("consumer_git_commit", "consumer_git_tree", "consumer_runtime_source_sha256"))),
                  patch.object(workflow, "source_guard", return_value=self.source),
                  patch.dict(CONFIGURATION, epochs=2), patch.dict(contract.PROTOCOL, sample_count=8)):
            p.start(); self.addCleanup(p.stop)
        self.baseline = Path(self.native.request["result_zip"])
        self.request = {"contract_revision": contract.REVISION,
            "original_one_state_experiment_directory": str(self.native.folder),
            "expected_original_one_state_experiment_sha256": self.prior_pin,
            "one_state_ar_result_zip": str(self.baseline), "expected_one_state_ar_result_sha256": previous.sha(self.baseline),
            "experiment_directory": "outputs/experiments/private/flow001", "training_directory": "outputs/models/private/flow001",
            "authorization": "config/private/flow001.json", "result_zip": str(self.root/"results.zip")}
        self.path = self.root/"flow-request.json"
        self.common = dict(project=self.project, expected_tree="synthetic", expected_runtime="synthetic")

    @property
    def folder(self): return self.project/self.request["experiment_directory"]

    @property
    def output(self): return self.project/self.request["training_directory"]

    def prepare(self):
        self.path.write_bytes(previous.encoded(self.request))
        return workflow.prepare(**self.common, request_path=self.path, expected_request_sha256=previous.sha(self.path))

    def adopt(self, pin, adopted=True):
        value = contract.authorization_draft(pin)
        value["attestations"] = dict.fromkeys(value["attestations"], adopted)
        path = self.project/self.request["authorization"]
        path.write_bytes(previous.encoded(value))
        return path

    def train(self, pin, auth):
        with redirect_stdout(io.StringIO()):
            return workflow.train(**self.common, experiment_directory=self.folder, expected_experiment_sha256=pin,
                authorization_path=auth, expected_authorization_sha256=previous.sha(auth))

    def test_native_lineage_two_flows_saved_before_scores_six_models_and_plot(self):
        oldpin = previous.sha(self.baseline)
        with patch.object(workflow, "fit_matched_flow", side_effect=AssertionError("fit during prepare")):
            manifest, pin = self.prepare()
        self.assertEqual(len(manifest["folds"]), 5)
        self.assertEqual(self.train(pin, self.adopt(pin)), 0)
        receipt = json.loads((self.output/"run_receipt.json").read_text())
        self.assertEqual(receipt["status"], "complete_matched_flow_cross_validation")
        self.assertTrue(receipt["input_integrity_verified"])
        self.assertFalse(receipt["baseline_refitted"])
        self.assertFalse(receipt["transform_refitted"])
        self.assertEqual(len(receipt["completed"]), 10)
        self.assertEqual(len(receipt["comparison"]), 6)
        self.assertGreater((self.output/"comparison.png").stat().st_size, 10000)
        for row in receipt["completed"]:
            mode = row["model"].removeprefix("matched_").removesuffix("_flow")
            saved = json.loads((self.output/(row["fold"]["fold_id"]+"_"+mode+"_model.json")).read_text())
            state = MatchedFlow.from_dict(saved["state"])
            self.assertEqual(len(state.training_losses), 2)
            self.assertEqual(row["model_sha256"], previous.sha(self.output/(row["fold"]["fold_id"]+"_"+mode+"_model.json")))
            self.assertIsNone(row["metrics"]["mean_physical_joint_nll"])
            self.assertEqual(row["monte_carlo_diagnostics"]["draws_per_half"], 4)
        with zipfile.ZipFile(self.request["result_zip"]) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read("training/accepted_one_state_ar_result.zip"), self.baseline.read_bytes())
            for line in z.read("SHA256SUMS").decode().splitlines():
                h, n = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(), h)
        self.assertEqual(previous.sha(self.baseline), oldpin)

    def test_false_partial_nonboolean_and_missing_scope_authorization_refused_before_claim(self):
        _, pin = self.prepare()
        for value in (False, 1, "true"):
            auth = self.adopt(pin, value)
            with self.assertRaisesRegex(ValueError, "explicit_owner_authorization"): self.train(pin, auth)
        value = contract.authorization_draft(pin)
        value["attestations"] = dict.fromkeys(value["attestations"], True)
        value["attestations"]["restricted_original_short_support_scope_accepted"] = False
        auth.write_bytes(previous.encoded(value))
        with self.assertRaisesRegex(ValueError, "explicit_owner_authorization"): self.train(pin, auth)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.project/"outputs/fit_ledgers/private/matched_flow_v01927").exists())

    def test_solver_failure_preserves_model_checkpoint_and_report_blocks_later_fits_and_rename(self):
        _, pin = self.prepare(); auth = self.adopt(pin)
        original = workflow.fit_matched_flow
        with patch.object(workflow, "fit_matched_flow", wraps=original) as fitter, patch.object(workflow, "calibrate_solver", return_value={"passed": False, "selected_steps": None}):
            self.assertEqual(self.train(pin, auth), 2)
        self.assertEqual(fitter.call_count, 1)
        self.assertEqual(len(list(self.output.glob("*_model.json"))), 1)
        self.assertEqual(len(list(self.output.glob("*_epoch1.json"))), 1)
        self.assertEqual(len(list(self.output.glob("*_calibration.json"))), 1)
        self.assertEqual(len(list(self.output.glob("*_scores.json"))), 0)
        receipt = json.loads((self.output/"run_receipt.json").read_text())
        self.assertTrue(receipt["input_integrity_verified"])
        self.assertEqual(receipt["completed"], [])
        self.assertTrue(Path(self.request["result_zip"]).is_file())
        self.request.update(experiment_directory="outputs/experiments/private/rename", training_directory="outputs/models/private/rename", result_zip=str(self.root/"rename.zip"))
        with self.assertRaisesRegex(ValueError, "design_already_attempted"): self.prepare()

    def test_interrupt_and_packaging_failure_preserve_claim_and_partial(self):
        _, pin = self.prepare(); auth = self.adopt(pin)
        def partial(path, *args): path.write_bytes(b"preserved partial"); raise OSError("synthetic disk failure")
        with patch.object(workflow, "fit_matched_flow", side_effect=KeyboardInterrupt), patch.object(workflow, "package", side_effect=partial):
            self.assertEqual(self.train(pin, auth), 2)
        receipt = json.loads((self.output/"run_receipt.json").read_text())
        self.assertEqual(receipt["failures"][0]["failure_code"], "KeyboardInterrupt")
        self.assertTrue(Path(receipt["attempt_claim_path_private"]).is_file())
        self.assertTrue(Path(receipt["attempt_claim_path_private"]+".packaging_failure.json").is_file())
        self.assertEqual(Path(self.request["result_zip"]+".partial").read_bytes(), b"preserved partial")

    def test_protocol_repin_and_extra_files_cannot_change_design(self):
        manifest, pin = self.prepare(); changed = deepcopy(manifest)
        changed["protocol"]["configuration"]["epochs"] = 5
        marker = self.folder/"experiment.json"; marker.write_bytes(previous.encoded(changed))
        with self.assertRaisesRegex(ValueError, "cached_protocol"): contract.load_experiment(self.project, self.folder, previous.sha(marker))
        marker.write_bytes(previous.encoded(manifest)); (self.folder/"extra").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "exact_experiment_file_set"): contract.load_experiment(self.project, self.folder, pin)

    def test_unreviewed_predecessor_and_pin_refused(self):
        self.request["expected_one_state_ar_result_sha256"] = "a"*64
        with self.assertRaisesRegex(ValueError, "predecessor_digest"): self.prepare()
        self.request["expected_one_state_ar_result_sha256"] = previous.sha(self.baseline)
        with patch.object(contract, "ONE_STATE_SOURCE", ("a", "b", "c")), self.assertRaisesRegex(ValueError, "unreviewed_producer"):
            self.prepare()
        self.assertFalse(self.folder.exists())

    def test_input_drift_during_fit_invalidates_result(self):
        _, pin = self.prepare(); auth = self.adopt(pin); original = workflow.fit_matched_flow
        def drift(*args, **kwargs):
            result = original(*args, **kwargs); auth.write_text("{}"); return result
        with patch.object(workflow, "fit_matched_flow", side_effect=drift): self.assertEqual(self.train(pin, auth), 2)
        receipt = json.loads((self.output/"run_receipt.json").read_text())
        self.assertFalse(receipt["input_integrity_verified"])
        self.assertEqual(receipt["completed"], [])

    def test_known_raw_predecessor_refused_before_lstat(self):
        self.request["one_state_ar_result_zip"] = self.native.raw_path
        self.path.write_bytes(previous.encoded(self.request)); original = Path.lstat
        def observe(p, *args, **kwargs):
            if str(p) == self.native.raw_path: raise AssertionError("Raw endpoint queried")
            return original(p, *args, **kwargs)
        with patch.object(Path, "lstat", new=observe), self.assertRaisesRegex(ValueError, "known_raw_input"):
            contract.load_inputs(self.project, self.path, previous.sha(self.path))

    def test_missing_zip_parent_and_output_race_fail_before_claim(self):
        self.request["result_zip"] = str(self.root/"missing/result.zip")
        with self.assertRaisesRegex(ValueError, "zip_parent"): self.prepare()
        self.request["result_zip"] = str(self.root/"results.zip")
        _, pin = self.prepare(); auth = self.adopt(pin); original = contract.load_experiment
        def race(*args):
            result = original(*args); self.output.mkdir(parents=True); return result
        with patch.object(contract, "load_experiment", side_effect=race), self.assertRaisesRegex(ValueError, "new_output"): self.train(pin, auth)
        self.assertFalse((self.project/"outputs/fit_ledgers/private/matched_flow_v01927").exists())

    def test_missing_likelihood_is_not_zero_and_missing_lag_reports_support(self):
        rows = [{"model": "flow", "fold": {"fold_id": "one"}, "metrics": {
            "mean_physical_joint_nll": None, "median_absolute_lag_one_correlation_error": None,
            "intervals": {v: {"coverage": .5, "mean_width_m": .3} for v in ("0.5", "0.8", "0.95")},
            "profile_max_absolute_tail": {v: {"brier_score": .1} for v in ("0.5", "1.0", "2.0")}}}]
        summary = comparison(rows)["flow"]["metrics"]
        self.assertIsNone(summary["mean_physical_joint_nll"]["equal_outing_mean"])
        self.assertEqual(summary["median_absolute_lag_one_correlation_error"]["unassessed_outings"], 1)


if __name__ == "__main__":
    unittest.main()
