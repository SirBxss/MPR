"""Native synthetic export orchestration; owner data and frozen pins stay private."""

from contextlib import redirect_stdout
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from lane_residuals.domain import artifact_registry as policy, numeric_export as numeric
from lane_residuals.io import artifact_registry as registry, locked_development as locked
from lane_residuals.workflows import locked_development_export as workflow
from lane_residuals.cli import recording_ingestion, numeric_archive
from lane_residuals.workflows.recording_ingestion import _runtime
from tests.io import test_locked_development as fixtures


class LockedDevelopmentExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.LockedDevelopmentIOTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.LockedDevelopmentIOTests.tearDownClass()

    def setUp(self):
        self.fixture = fixtures.LockedDevelopmentIOTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.project = self.fixture.native.project
        self.root = self.fixture.fixture.root
        with (self.project / ".gitignore").open("a") as stream:
            stream.write("outputs/\n")
        self.context = locked.load_context(**self.fixture.kwargs)
        self.runtime = _runtime(include_compression=True)["runtime_source_sha256"]
        # This is a native current-source fixture, never a production allowlist
        # update or evidence of a run in the owner's exact frozen environment.
        source = patch.object(policy, "ACCEPTED_NUMERIC_PRODUCER", self.runtime)
        source.start()
        self.addCleanup(source.stop)
        subprocess.run(["git", "-C", str(self.project), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(self.project), "-c", "user.name=Synthetic", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "synthetic controller fixture"], check=True)
        self.tree = subprocess.check_output(["git", "-C", str(self.project), "rev-parse", "HEAD^{tree}"], text=True).strip()
        self.release = self.root / "frozen-fixture"
        shutil.copytree(Path(__file__).resolve().parents[2] / "src", self.release / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
        source_files = {p.relative_to(self.release).as_posix(): workflow.sha(p) for p in self.release.rglob("*") if p.is_file()}
        self.release_pin = self.root / "SOURCE_RELEASE_PIN.json"
        self.release_pin.write_text(json.dumps({"files": source_files}))
        self.plan = {"contract_revision": workflow.REVISION, "cohort_directory": str(self.fixture.fixture.output),
            "expected_cohort_sha256": self.fixture.pin, "original_registry_directory": str(self.fixture.fixture.registry_directory),
            "expected_original_registry_sha256": self.fixture.fixture.registry_pin, "descendants": [],
            "frozen_release_directory": str(self.release), "frozen_release_pin": str(self.release_pin),
            "expected_frozen_release_pin_sha256": workflow.sha(self.release_pin),
            "collection_lock_path": "outputs/run_receipts/synthetic-collection.lock", "targets": [],
            "attempt_directory": "outputs/run_receipts/locked-synthetic001", "result_zip": str(self.root / "result.zip")}
        (self.project / "outputs/run_receipts").mkdir(parents=True)
        for i, raw in enumerate(self.fixture.development[:2]):
            files = locked.readiness_files(self.context, raw)
            reg = registry.decode(self.context.original_objects[files["registration/registration.json"]])
            auth = {"contract_revision": numeric.AUTHORIZATION_REVISION, "purpose": numeric.AUTHORIZATION_PURPOSE,
                "batch_id": reg["batch_id"], "registration_sha256": files["registration/registration.json"],
                "source_specification_sha256": files["registration/source_specification.json"],
                "preserved_readiness_report_sha256": files["readiness.json"], "authorized_raw_sha256": [raw],
                "attestations": dict.fromkeys(numeric.ATTESTATIONS, True)}
            p = self.root / f"owner-adopted-{i}.json"
            p.write_text(json.dumps(auth))
            self.plan["targets"].append({"raw_sha256": raw, "authorization": str(p), "expected_authorization_sha256": workflow.sha(p),
                "numeric_output": f"data/derived/synthetic-{i}", "reserved_registry": f"data/catalog/private/reserved-{i}",
                "complete_registry": f"data/catalog/private/complete-{i}"})
        self.plan_path = self.root / "plan.json"
        self.version_patch = patch.object(workflow, "versions", return_value=workflow.FROZEN_VERSIONS)
        self.version_patch.start()
        self.addCleanup(self.version_patch.stop)
        self.resource_patch = patch.object(workflow, "resources", return_value={"mem_available_bytes": 20 * 1024**3,
                                                                               "scratch_free_bytes": 30 * 1024**3})
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)

    @property
    def attempt(self):
        return self.project / self.plan["attempt_directory"]

    def execute(self, runner=None):
        self.plan_path.write_text(json.dumps(self.plan))
        kwargs = dict(project_root=self.project, plan_path=self.plan_path, expected_plan_sha256=workflow.sha(self.plan_path),
                      expected_consumer_tree=self.tree, expected_consumer_runtime=self.runtime)
        if runner is None:
            return workflow.execute(**kwargs)
        with patch.object(workflow, "logged", side_effect=runner):
            return workflow.execute(**kwargs)

    def native_command(self, command, release, log, fds):
        if command[2] == "lane_residuals.cli.recording_ingestion":
            index = int(log.name.split("_")[1]) - 1
            reservation = self.project / self.plan["targets"][index]["reserved_registry"]
            self.assertTrue((reservation / "registry.json").is_file())
            self.assertEqual(len(fds), 2)
            # The actual native synthetic exporter and standalone validator run
            # in process solely to reuse test-only producer allowlists.
            with log.open("x") as stream, redirect_stdout(stream):
                return recording_ingestion.main(command[3:])
        with log.open("x") as stream, redirect_stdout(stream):
            return numeric_archive.main(command[3:])

    def test_two_native_exports_reserve_first_validate_publish_and_read_matched_rows(self):
        self.assertEqual(self.execute(self.native_command), 0)
        receipt = json.loads((self.attempt / "run_receipt.json").read_text())
        self.assertEqual(receipt["status"], "complete_locked_development_exports")
        self.assertTrue(receipt["input_integrity_verified"])
        self.assertFalse(receipt["model_admission_authorized"])
        self.assertEqual(receipt["consumer_git_tree"], self.tree)
        self.assertEqual(receipt["consumer_runtime_source_sha256"], self.runtime)
        self.assertEqual(receipt["producer_runtime_versions"], workflow.FROZEN_VERSIONS)
        self.assertEqual(receipt["plan_sha256"], workflow.sha(self.plan_path))
        self.assertEqual((self.attempt / "ISSUED_PLAN.private.json").read_bytes(), self.plan_path.read_bytes())
        self.assertEqual(len(receipt["descendants"]), 4)
        self.assertEqual(set(receipt["stages"].values()), {0})
        chain = [locked.RegistryCheckpoint(Path(c["directory"]), c["sha256"]) for c in receipt["descendants"]]
        view = locked.load_development_dataset(**self.fixture.kwargs, descendants=chain,
                                               archive_sha256=receipt["matched_archives_sha256"])
        self.assertEqual(len(view.archives), 2)
        for archive in view.archives:
            np.testing.assert_array_equal(archive.matched_residuals_m,
                                          archive.geometry_residuals_m[archive.arrays["conditioned_profile_indices"]])
            self.assertEqual(len(archive.conditions), 501)
            self.assertEqual(sum(len(y) for y, _, _ in archive.matched_sequences()), 501)
            self.assertFalse(archive.conditions.flags.writeable)
        labels = list(view.session_id_by_archive.values())
        self.assertEqual(tuple(map(len, view.fold(training_sessions=labels[:1], validation_sessions=labels[1:]))), (1, 1))
        with zipfile.ZipFile(self.plan["result_zip"]) as archive:
            self.assertIsNone(archive.testzip())
            manifest = dict(line.split("  ", 1)[::-1] for line in archive.read("SHA256SUMS").decode().splitlines())
            self.assertEqual(set(archive.namelist()), set(manifest) | {"SHA256SUMS"})
            self.assertTrue(all(hashlib.sha256(archive.read(name)).hexdigest() == h for name, h in manifest.items()))
        result_pin = workflow.sha(Path(self.plan["result_zip"]))
        with self.assertRaises(policy.RegistryError):
            self.execute(self.native_command)
        self.assertEqual(workflow.sha(Path(self.plan["result_zip"])), result_pin)

    def test_final_target_refuses_before_attempt_or_reservation_even_in_mixed_plan(self):
        self.plan["targets"][1]["raw_sha256"] = self.fixture.final[0]
        before = set(self.project.rglob("*"))
        with self.assertRaisesRegex(policy.RegistryError, "not_development"):
            self.execute()
        self.assertEqual(before, set(self.project.rglob("*")))
        self.assertFalse(self.attempt.exists())

    def test_authorization_raw_endpoint_is_rejected_before_stat_or_open(self):
        import os
        raw = next(r["canonical_paths_private"][0] for r in self.context.metadata["records"]
                   if r["raw_sha256"] == self.plan["targets"][0]["raw_sha256"])
        self.plan["targets"][0]["authorization"] = raw
        def guarded(call):
            def invoke(p, *a, **k):
                if isinstance(p, (str, bytes, os.PathLike)) and os.fsdecode(p) == raw:
                    raise AssertionError("raw endpoint queried before guard")
                return call(p, *a, **k)
            return invoke
        with patch.object(os, "stat", guarded(os.stat)), patch.object(os, "lstat", guarded(os.lstat)), \
                patch.object(os, "open", guarded(os.open)), self.assertRaisesRegex(policy.RegistryError, "raw_payload"):
            self.execute()
        self.assertFalse(self.attempt.exists())

    def test_false_draft_and_wrong_lineage_cannot_be_adopted_by_controller(self):
        target = self.plan["targets"][0]
        auth_path = Path(target["authorization"])
        auth = json.loads(auth_path.read_text())
        for mutate, code in [(lambda a: a.update(attestations=dict.fromkeys(a["attestations"], False)), "not_adopted"),
                             (lambda a: a.update(preserved_readiness_report_sha256="f" * 64), "lineage_mismatch")]:
            value = deepcopy(auth)
            mutate(value)
            auth_path.write_text(json.dumps(value))
            target["expected_authorization_sha256"] = workflow.sha(auth_path)
            with self.subTest(code=code), self.assertRaisesRegex(policy.RegistryError, code):
                self.execute()
            self.assertFalse(self.attempt.exists())

    def test_unselected_final_consent_and_version_drift_stop_before_attempt(self):
        with patch.object(workflow, "versions", return_value={**workflow.FROZEN_VERSIONS, "mcap": "1.6.0"}), \
                self.assertRaisesRegex(policy.RegistryError, "versions_changed"):
            self.execute()
        self.assertFalse(self.attempt.exists())
        auth = json.loads(Path(self.plan["targets"][0]["authorization"]).read_text())
        auth["authorized_raw_sha256"] = [self.fixture.final[0]]
        (self.project / "config/private/final-consent.json").write_text(json.dumps(auth))
        with self.assertRaisesRegex(policy.RegistryError, "unselected_new_authorization"):
            self.execute()
        self.assertFalse(self.attempt.exists())

    def test_nested_output_and_writer_race_stop_without_attempt(self):
        original = self.plan["targets"][0]["reserved_registry"]
        self.plan["targets"][0]["reserved_registry"] = str(self.fixture.fixture.registry_directory / "nested")
        with patch.object(workflow.tempfile, "TemporaryDirectory", side_effect=AssertionError("replay temporary created")), \
                self.assertRaises(policy.RegistryError):
            self.execute()
        self.assertFalse(self.attempt.exists())
        self.plan["targets"][0]["reserved_registry"] = original
        lock = self.project / "data/catalog/private/.registry-write.lock"
        with lock.open("r+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(policy.RegistryError, "another_writer"):
                self.execute()
        self.assertFalse(self.attempt.exists())

    def test_native_stage_failure_preserves_reservation_receipt_zip_and_stops_following_targets(self):
        self.assertEqual(self.execute(lambda *args: 3), 2)
        receipt = json.loads((self.attempt / "run_receipt.json").read_text())
        self.assertEqual(receipt["failures"][0]["stage"], "target_001_numeric_export")
        self.assertEqual(receipt["stages"]["target_001_numeric_export"], 3)
        self.assertEqual(len(receipt["targets"]), 1)
        self.assertEqual(len(receipt["descendants"]), 1)
        self.assertTrue(receipt["input_integrity_verified"])
        self.assertTrue(Path(self.plan["result_zip"]).is_file())
        self.assertFalse((self.project / self.plan["targets"][1]["reserved_registry"]).exists())
        result_pin = workflow.sha(Path(self.plan["result_zip"]))
        with self.assertRaises(policy.RegistryError):
            self.execute(lambda *args: 0)
        self.assertEqual(workflow.sha(Path(self.plan["result_zip"])), result_pin)

    def test_interrupt_is_returned_as_130_and_keeps_reservation_and_result(self):
        def interrupted(*args):
            raise KeyboardInterrupt()
        self.assertEqual(self.execute(interrupted), 130)
        receipt = json.loads((self.attempt / "run_receipt.json").read_text())
        self.assertEqual(receipt["failures"][0]["failure_code"], "KeyboardInterrupt")
        self.assertTrue(Path(self.plan["result_zip"]).is_file())
        self.assertEqual(len(receipt["descendants"]), 1)

    def test_postflight_source_drift_cannot_be_reported_as_success(self):
        def drift(*args):
            source = next((self.release / "src").rglob("*.py"))
            source.write_text(source.read_text() + "\n# synthetic drift\n")
            return 3
        self.assertEqual(self.execute(drift), 2)
        receipt = json.loads((self.attempt / "run_receipt.json").read_text())
        self.assertFalse(receipt["input_integrity_verified"])
        self.assertEqual(receipt["failures"][-1]["stage"], "postflight_integrity")
