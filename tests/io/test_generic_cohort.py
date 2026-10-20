"""Native small MCAP evidence, immutable cohort publications and raw-free replay."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import generic_cohort as policy
from lane_residuals.domain.artifact_registry import RegistryError
from lane_residuals.io import generic_cohort as cohort, artifact_registry as registry
from tests.io import test_artifact_registry as registry_fixtures
from tests.workflows import test_bounded_recording_readiness as bounded_fixtures
from lane_residuals.workflows import bounded_recording_readiness as bounded

pin = registry_fixtures.pin


class GenericCohortIOTests(unittest.TestCase):
    def setUp(self):
        self.native = registry_fixtures.ArtifactRegistryTests()
        self.native.setUp()
        self.addCleanup(self.native.doCleanups)
        self.metadata, self.registry_pin = self.native.create()
        self.root = self.native.root
        self.registry_directory = self.native.output
        self.output = self.native.project / "data/catalog/private/cohorts/001"
        self.raw = self.metadata["records"][0]["raw_sha256"]
        self.declaration = {"contract_revision": policy.DECLARATION_REVISION,
            "purpose": "owner_declared_physical_session_membership", "evidence_status": policy.EVIDENCE_STATUS,
            "declaration_text_private": "Synthetic owner statement.", "independence_basis_private": "Native synthetic MCAP.",
            "outings": [{"session_id_private": "existing-folder-id", "separate_physical_session": True, "raw_sha256": [self.raw]}]}
        self.manifest = {"contract_revision": policy.REVISION, "registry_sha256": self.registry_pin,
            "session_declaration_sha256": "", "scope_raw_sha256": [self.raw],
            "readiness_by_raw_sha256": {self.raw: self.native.args.expected_readiness_sha256},
            "legacy_development_outing_count": 1, "prior_successful_lock_sha256": None}
        self.declaration_path = self.root / "session-declaration.json"
        self.manifest_path = self.root / "cohort-manifest.json"
        self.write_inputs()

    def write_inputs(self):
        self.declaration_path.write_text(json.dumps(self.declaration))
        self.manifest["session_declaration_sha256"] = pin(self.declaration_path)
        self.manifest_path.write_text(json.dumps(self.manifest))

    def arguments(self):
        return dict(project_root=self.native.project, registry_directory=self.registry_directory,
            expected_registry_sha256=self.registry_pin, session_declaration=self.declaration_path,
            expected_session_declaration_sha256=pin(self.declaration_path), cohort_manifest=self.manifest_path,
            expected_cohort_manifest_sha256=pin(self.manifest_path), output_directory=self.output)

    def test_native_count_only_admission_failure_is_complete_and_raw_offline_replayable(self):
        self.native.fixture.fixture.raw.unlink()
        original = {p: pin(p) for p in self.registry_directory.rglob("*") if p.is_file()}
        result, h = cohort.create_cohort(**self.arguments())
        self.assertEqual(result["status"], "insufficient_independent_outings")
        self.assertEqual(result["outings"][0]["support"]["eligible_frame_count"], 2)
        self.assertEqual(cohort.load_cohort(self.output, h, self.registry_directory), result)
        self.assertEqual(original, {p: pin(p) for p in original})
        self.assertEqual({p.name for p in self.output.iterdir()}, cohort.FILES)
        self.assertFalse(result["model_admission_authorized"])

    def test_wrong_hash_or_source_pin_stops_before_output(self):
        for key in ("expected_registry_sha256", "expected_session_declaration_sha256", "expected_cohort_manifest_sha256"):
            args = self.arguments()
            args[key] = "0" * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                cohort.create_cohort(**args)
            self.assertFalse(self.output.exists())

    def test_unknown_readiness_cannot_replace_a_missing_or_failed_predecessor(self):
        self.manifest["readiness_by_raw_sha256"][self.raw] = "0" * 64
        self.write_inputs()
        with self.assertRaisesRegex(RegistryError, "selected_readiness_not_in_registry"):
            cohort.create_cohort(**self.arguments())
        self.assertFalse(self.output.exists())

    def test_hashing_an_edited_cached_role_cannot_make_it_authoritative(self):
        result, h = cohort.create_cohort(**self.arguments())
        result["roles_assigned"] = True
        result["outings"][0]["cohort_role"] = "final_test"
        path = self.output / cohort.COHORT_NAME
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "do_not_replay"):
            cohort.load_cohort(self.output, pin(path), self.registry_directory)

    def test_missing_or_extra_output_and_direct_symlink_fail(self):
        _, h = cohort.create_cohort(**self.arguments())
        extra = self.output / "extra"
        extra.write_text("unexpected")
        with self.assertRaisesRegex(RegistryError, "exact_file_set"):
            cohort.load_cohort(self.output, h, self.registry_directory)
        extra.unlink()
        alias = self.root / "cohort-alias"
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(RegistryError):
            cohort.load_cohort(alias, h, self.registry_directory)

    def test_no_overwrite_and_source_or_input_drift_before_publication(self):
        result, h = cohort.create_cohort(**self.arguments())
        with self.assertRaises(RegistryError):
            cohort.create_cohort(**self.arguments())
        self.assertEqual(cohort.load_cohort(self.output, h, self.registry_directory), result)
        self.output = self.output.with_name("002")
        original = cohort._runtime
        calls = []
        def drift(**kwargs):
            value = original(**kwargs)
            calls.append(1)
            if len(calls) > 1:
                value["runtime_source_sha256"] = "0" * 64
            return value
        with patch.object(cohort, "_runtime", side_effect=drift), self.assertRaisesRegex(RegistryError, "source_changed"):
            cohort.create_cohort(**self.arguments())
        self.assertFalse(self.output.exists())

    def test_traversal_fails_before_new_directories(self):
        before = set(self.native.project.rglob("*"))
        self.output = self.native.project / "data/catalog/private/new/../other"
        with self.assertRaises(RegistryError):
            cohort.create_cohort(**self.arguments())
        self.assertEqual(before, set(self.native.project.rglob("*")))

    def test_old_registry_cannot_omit_a_newer_project_reservation(self):
        self.native.manifest["additional_authorizations"] = []
        self.native.output = self.native.output.with_name("new-reservation")
        auth = deepcopy(self.native.fixture.auth)
        auth["authorized_raw_sha256"] = ["f" * 64]
        auth["registration_sha256"] = "e" * 64
        (self.native.authorizations / "numeric_export_authorization_new.json").write_text(json.dumps(auth))
        self.native.create()
        with self.assertRaisesRegex(RegistryError, "omits_project_history"):
            cohort.create_cohort(**self.arguments())
        self.assertFalse(self.output.exists())

    def test_publication_failure_leaves_no_complete_marker_and_parent_intact(self):
        original = (self.registry_directory / "registry.json").read_bytes()
        real_open = os.open
        def fail(path, *args, **kwargs):
            if Path(path) == self.output / cohort.COHORT_NAME:
                raise OSError("synthetic disk failure")
            return real_open(path, *args, **kwargs)
        with patch.object(cohort.os, "open", side_effect=fail), self.assertRaises(OSError):
            cohort.create_cohort(**self.arguments())
        self.assertFalse((self.output / cohort.COHORT_NAME).exists())
        self.assertEqual(original, (self.registry_directory / "registry.json").read_bytes())

    def test_raw_alias_is_rejected_before_endpoint_lstat(self):
        raw = self.native.fixture.fixture.raw.with_name("payload.bin")
        raw.write_bytes(self.native.fixture.fixture.raw.read_bytes())
        alias = self.root / "alias-directory"
        alias.symlink_to(raw.parent, target_is_directory=True)
        path = alias / raw.name
        store = registry.ObjectStore()
        store.raw_paths.add(str(raw))
        real_stat, real_lstat = os.stat, os.lstat
        touched = []
        def observer(original):
            def observe(p, *a, **k):
                if str(p) in {str(path), str(raw)}:
                    touched.append(p)
                return original(p, *a, **k)
            return observe
        with patch.object(os, "stat", side_effect=observer(real_stat)), \
                patch.object(os, "lstat", side_effect=observer(real_lstat)), \
                self.assertRaisesRegex(RegistryError, "raw_payload"):
            store.add(path)
        self.assertEqual(touched, [])

    def test_engineering_view_flags_and_whole_session_folds(self):
        class Archive:
            def __init__(self, pin):
                self.summary_sha256 = pin
        a, b, c = Archive("a" * 64), Archive("b" * 64), Archive("c" * 64)
        view = cohort.CohortDataset("d" * 64, (a, b, c), {a.summary_sha256: "one", b.summary_sha256: "one", c.summary_sha256: "two"})
        train, val = view.fold(training_sessions=["one"], validation_sessions=["two"])
        self.assertEqual(train, (a, b))
        self.assertEqual(val, (c,))
        with self.assertRaises(RegistryError):
            view.fold(training_sessions=["one"], validation_sessions=["one", "two"])
        with self.assertRaises(RegistryError):
            view.fold(training_sessions=["one"], validation_sessions=["missing"])
        with self.assertRaisesRegex(RegistryError, "real_fit_not_authorized"):
            view.require_model_admission()
        with self.assertRaises(ValueError):
            replace(view, model_admission_authorized=True)

    def prepare_seven_outing_lock(self):
        entries, scope, declarations, selected = [], [], [], {}
        for i in range(7):
            native = bounded_fixtures.BoundedWorkflowTests()
            native.setUp()
            self.addCleanup(native.doCleanups)
            native.prepare(times=tuple(2_000_000_000 + j * 250_000_000 for j in range(501)),
                           reference_offset=0.5 + i * 0.01)
            report, status = bounded.run_bounded_readiness(native.args)
            self.assertEqual(status, 0)
            self.assertEqual(report["recordings"][0]["readiness"]["complete_condition_support"]["frame_count"], 501)
            registration = json.loads((native.directory / "registration.json").read_text())
            raw = registration["recordings"][0]["raw_sha256"]
            scope.append(raw)
            ready = native.args.output_directory / bounded.REPORT_NAME
            selected[raw] = pin(ready)
            declarations.append({"session_id_private": f"synthetic-drive-{i}", "separate_physical_session": True,
                                 "raw_sha256": [raw]})
            entries.append({"registration_directory": str(native.directory),
                "expected_registration_sha256": pin(native.directory / "registration.json"),
                "reports": [{"role": role, "path": str(path), "expected_sha256": pin(path)} for role, path in
                    [("inventory", native.args.preserved_inventory_report), ("decode", native.args.preserved_decode_report),
                     ("readiness", ready)]]})
        self.native.manifest["registrations"] = entries
        self.native.output = self.native.output.with_name("seven-new-counts")
        _, self.registry_pin = self.native.create()
        self.registry_directory = self.native.output
        self.declaration["outings"] = declarations
        self.manifest.update(registry_sha256=self.registry_pin, scope_raw_sha256=sorted(scope),
                             readiness_by_raw_sha256=selected)
        self.write_inputs()
        result, h = cohort.create_cohort(**self.arguments())
        return result, h

    def test_native_seven_outings_500_frames_and_120_seconds_lock_without_numeric_exposure(self):
        result, h = self.prepare_seven_outing_lock()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["eligible_new_outing_count"], 7)
        self.assertEqual(sum(o["cohort_role"] == "final_test" for o in result["outings"]), 2)
        self.assertEqual(cohort.load_cohort(self.output, h, self.registry_directory), result)
        self.assertTrue(all(o["support"]["sequence_count"] == 501 for o in result["outings"]))
        self.assertFalse(result["model_admission_authorized"])

    def test_model_adapter_uses_strict_matched_arrays_and_rejects_final_and_outside_scope(self):
        pin_ = self.native.args.expected_summary_sha256
        result = {"status": "complete", "registry_sha256": self.registry_pin,
                  "outings": [{"raw_sha256": [self.raw], "cohort_role": "development", "session_id_private": "one"}]}
        with patch.object(cohort, "load_cohort", return_value=result):
            view = cohort.load_development_dataset(cohort_directory=self.output, expected_cohort_sha256="d" * 64,
                registry_directory=self.registry_directory, archive_sha256=[pin_])
            dataset = view.archives[0]
            np.testing.assert_array_equal(dataset.matched_residuals_m,
                dataset.geometry_residuals_m[dataset.arrays["conditioned_profile_indices"]])
            self.assertEqual(sum(len(s[0]) for s in dataset.matched_sequences()), len(dataset.conditions))
            self.assertFalse(view.model_admission_authorized)
            for role in ("final_test", "excluded"):
                result["outings"][0]["cohort_role"] = role
                with self.subTest(role=role), self.assertRaisesRegex(RegistryError, "final_or_excluded"):
                    cohort.load_development_dataset(cohort_directory=self.output, expected_cohort_sha256="d" * 64,
                        registry_directory=self.registry_directory, archive_sha256=[pin_])
            result["outings"] = []
            with self.assertRaisesRegex(RegistryError, "outside_frozen_scope"):
                cohort.load_development_dataset(cohort_directory=self.output, expected_cohort_sha256="d" * 64,
                    registry_directory=self.registry_directory, archive_sha256=[pin_])

    def test_snapshot_successful_lock_prevents_second_publication(self):
        # Pure support is synthetic and deliberately patched only inside this
        # publication-guard test; real support arithmetic is tested natively.
        actual = policy.build_cohort
        def complete(*args, **kwargs):
            value = actual(*args, **kwargs)
            value["cohort_lock_created"] = True
            return value
        with patch.object(policy, "build_cohort", side_effect=complete):
            cohort.create_cohort(**self.arguments())
            self.output = self.output.with_name("002")
            with self.assertRaisesRegex(RegistryError, "prior_successful_lock"):
                cohort.create_cohort(**self.arguments())
        self.assertFalse(self.output.exists())
