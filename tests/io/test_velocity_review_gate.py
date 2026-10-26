import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lane_residuals.io import velocity_review_gate as gate


class SourceGateTests(unittest.TestCase):
    def setUp(self):
        self.runtime, self.request = "a"*64, "b"*64
        self.head, self.tree, self.reviewed = "c"*40, "d"*40, "e"*40
        self.pull = {"number": 45, "merged_at": "synthetic", "merge_commit_sha": self.head, "head": {"sha": self.reviewed}}
        self.run = {"id": 10, "head_sha": self.reviewed, "path": ".github/workflows/tests.yml", "status": "completed", "conclusion": "success", "run_attempt": 1}
        self.jobs = [{"id": i, "name": name, "status": "completed", "conclusion": "success"} for i, name in enumerate(sorted(gate.JOBS))]

    def git(self, _, *args):
        return {("branch", "--show-current"): "main", ("status", "--porcelain"): "",
            ("rev-parse", "HEAD"): self.head, ("rev-parse", "HEAD^{tree}"): self.tree,
            ("rev-parse", "refs/remotes/origin/main"): self.head}[args]

    def api(self, endpoint):
        if endpoint == "commits/main":
            return {"sha": self.head, "commit": {"tree": {"sha": self.tree}}}
        if endpoint.endswith("/pulls?per_page=10"):
            return [self.pull]
        if endpoint == "commits/"+self.reviewed:
            return {"commit": {"tree": {"sha": self.tree}}}
        if endpoint.startswith("actions/runs?"):
            return {"workflow_runs": [self.run]}
        if endpoint.startswith("actions/runs/10/jobs"):
            return {"jobs": self.jobs}
        raise AssertionError(endpoint)

    def evidence(self):
        with patch.object(gate, "git", side_effect=self.git), patch.object(gate, "runtime_sha256", return_value=self.runtime), patch.object(gate, "api", side_effect=self.api):
            return gate.source_evidence(Path.cwd(), self.runtime, self.request)

    def test_live_merged_head_exact_tree_and_all_three_jobs(self):
        value = self.evidence()
        self.assertEqual(value["commit"], self.head)
        self.assertEqual(len(value["ci_jobs"]), 3)

    def test_feature_branch_rejected_without_network(self):
        with patch.object(gate, "git", return_value="feature/unmerged"), patch.object(gate, "api", side_effect=AssertionError("network")), \
                self.assertRaisesRegex(ValueError, "merged_main_required"):
            gate.source_evidence(Path.cwd(), self.runtime, self.request)

    def test_runtime_mismatch_cannot_be_self_certified(self):
        with patch.object(gate, "git", side_effect=self.git), patch.object(gate, "runtime_sha256", return_value="wrong"), \
                patch.object(gate, "api", side_effect=AssertionError("network")), self.assertRaisesRegex(ValueError, "runtime_source_mismatch"):
            gate.source_evidence(Path.cwd(), self.runtime, self.request)

    def test_missing_merge_blocks(self):
        self.pull["merged_at"] = None
        with self.assertRaisesRegex(ValueError, "unique_merged_pr"):
            self.evidence()

    def test_failed_ci_and_missing_job_block(self):
        self.run["conclusion"] = "failure"
        with self.assertRaisesRegex(ValueError, "ci_not_success"):
            self.evidence()
        self.run["conclusion"] = "success"
        self.jobs.pop()
        with self.assertRaisesRegex(ValueError, "three_ci_jobs"):
            self.evidence()

    def test_a_newer_failed_run_is_not_hidden_by_old_success(self):
        good = dict(self.run)
        bad = dict(self.run, id=11, conclusion="failure")
        old_api = self.api
        def api(endpoint):
            return {"workflow_runs": [good, bad]} if endpoint.startswith("actions/runs?") else old_api(endpoint)
        with patch.object(gate, "git", side_effect=self.git), patch.object(gate, "runtime_sha256", return_value=self.runtime), \
                patch.object(gate, "api", side_effect=api), self.assertRaisesRegex(ValueError, "ci_not_success"):
            gate.source_evidence(Path.cwd(), self.runtime, self.request)

    def test_review_go_and_immutable_seal_required(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); note = base/"review.md"; note.write_text("Synthetic independent GO")
            with self.assertRaisesRegex(ValueError, "review_go_required"):
                gate.seal(base, self.runtime, self.request, note, base/"gate.json")
            with patch.object(gate, "source_evidence", return_value={"runtime_sha256": self.runtime}):
                pin = gate.seal(base, self.runtime, self.request, note, base/"gate.json", independent_review_go=True)
                gate.validate(base, base/"gate.json", pin, self.runtime, self.request)
                note.write_text("changed")
                with self.assertRaisesRegex(ValueError, "review_note_changed"):
                    gate.validate(base, base/"gate.json", pin, self.runtime, self.request)

    def test_changed_head_or_ci_invalidates_seal(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); note = base/"review.md"; note.write_text("Synthetic GO")
            with patch.object(gate, "source_evidence", return_value={"commit": "old"}):
                pin = gate.seal(base, self.runtime, self.request, note, base/"gate.json", independent_review_go=True)
            with patch.object(gate, "source_evidence", return_value={"commit": "changed"}), self.assertRaisesRegex(ValueError, "gate_source_or_ci_changed"):
                gate.validate(base, base/"gate.json", pin, self.runtime, self.request)
