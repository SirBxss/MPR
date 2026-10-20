"""Strict native descendants and independent identity/ancestry misuse checks."""

from copy import copy, deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np

from lane_residuals.domain import artifact_registry as policy, generic_cohort
from lane_residuals.io import artifact_registry as registry, locked_development as locked
from tests.io import test_generic_cohort as fixtures
from tests.domain import test_generic_cohort as pure


class LockedDevelopmentPolicyTests(unittest.TestCase):
    def test_parent_hash_without_event_prefix_or_preserved_objects_is_insufficient(self):
        parent = {"events": [{"kind": "original"}]}
        child = {"events": [{"kind": "original"}, {"kind": "new"}], "parent_registry_sha256": "a" * 64}
        locked.preserve_ancestry(parent, {"b" * 64: b"bytes"}, "a" * 64, child, {"b" * 64: b"bytes"})
        for value, objects, code in [({**child, "parent_registry_sha256": "c" * 64}, {"b" * 64: b"bytes"}, "parent_chain"),
                ({**child, "events": list(reversed(child["events"]))}, {"b" * 64: b"bytes"}, "event_prefix"),
                (child, {"b" * 64: b"different"}, "objects_not_preserved")]:
            with self.subTest(code=code), self.assertRaisesRegex(policy.RegistryError, code):
                locked.preserve_ancestry(parent, {"b" * 64: b"bytes"}, "a" * 64, value, objects)

    def test_later_final_reservation_publication_or_possible_alias_invalidates_without_reroll(self):
        values = pure.fixture()
        result = pure.build(values)
        membership = generic_cohort.parse_declaration(values[2], set(values[0]))
        raw = next(o["raw_sha256"][0] for o in result["outings"] if o["cohort_role"] == "final_test")
        original_roles = deepcopy(result)
        for flag in ("permanent_development_reservation", "complete_publication_observed", "linked_development_exclusion"):
            metadata = deepcopy(values[1])
            next(r for r in metadata["records"] if r["raw_sha256"] == raw)[flag] = True
            with self.subTest(flag=flag), self.assertRaisesRegex(policy.RegistryError, "final_evidence_invalidated"):
                locked.check_identity_and_final(result, membership, values[1], metadata)
        metadata = deepcopy(values[1])
        development = next(o["raw_sha256"][0] for o in result["outings"] if o["cohort_role"] == "development")
        metadata["events"].append({"kind": "relationship", "claim": {
            "left": "raw:" + raw, "right": "raw:" + development, "status": "unresolved"}})
        with self.assertRaisesRegex(policy.RegistryError, "final_evidence_invalidated|identity_or_component_changed"):
            locked.check_identity_and_final(result, membership, values[1], metadata)
        self.assertEqual(result, original_roles)


class LockedDevelopmentIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = fixtures.GenericCohortIOTests()
        cls.template.setUp()
        cls.accepted, cls.accepted_pin = cls.template.prepare_seven_outing_lock()

    @classmethod
    def tearDownClass(cls):
        cls.template.doCleanups()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        template = self.template
        self.fixture = copy(template)
        self.fixture.native = copy(template.native)
        self.fixture.native.manifest = deepcopy(template.native.manifest)
        project = root / "project"
        shutil.copytree(template.native.project, project)
        def mapped(p):
            return project / p.relative_to(template.native.project)
        self.fixture.root = root
        self.fixture.native.root = root
        self.fixture.native.project = project
        self.fixture.native.authorizations = mapped(template.native.authorizations)
        self.fixture.native.adopted = mapped(template.native.adopted)
        self.fixture.native.manifest_path = root / "import.json"
        self.fixture.registry_directory = mapped(template.registry_directory)
        self.fixture.native.output = self.fixture.registry_directory
        self.fixture.native.last_snapshot = (self.fixture.registry_directory, template.registry_pin)
        self.fixture.output = mapped(template.output)
        self.cohort, self.pin = deepcopy(self.accepted), self.accepted_pin
        self.native = self.fixture.native
        self.kwargs = dict(cohort_directory=self.fixture.output, expected_cohort_sha256=self.pin,
                           original_registry_directory=self.fixture.registry_directory)
        self.development = [raw for o in self.cohort["outings"] if o["cohort_role"] == "development" for raw in o["raw_sha256"]]
        self.final = [raw for o in self.cohort["outings"] if o["cohort_role"] == "final_test" for raw in o["raw_sha256"]]

    def successor(self, relationships=(), auth=None):
        self.native.manifest.update(registrations=[], archives=[], relationships=list(relationships), additional_authorizations=[])
        if auth is not None:
            path = self.fixture.root / "new-consent.json"
            path.write_text(json.dumps(auth))
            self.native.manifest["additional_authorizations"] = [{"path": str(path), "expected_sha256": fixtures.pin(path)}]
        self.native.output = self.native.output.with_name(self.native.output.name + "-next")
        _, pin = self.native.create()
        return locked.RegistryCheckpoint(self.native.output, pin)

    def test_native_chain_original_lineage_and_raw_offline_target_preflight(self):
        checkpoint = self.successor()
        context = locked.load_context(**self.kwargs, descendants=[checkpoint])
        self.assertEqual(context.registry_sha256, checkpoint.sha256)
        self.assertEqual(len(locked.preflight_targets(context, self.development)), 5)
        files = locked.readiness_files(context, self.development[0])
        self.assertEqual(files["readiness.json"], context.readiness_by_raw[self.development[0]])
        locked.require_project_history(context, self.native.project)
        for values in ([self.final[0]], [self.fixture.raw], ["f" * 64], self.development[:1] * 2):
            with self.subTest(values=values), self.assertRaises(policy.RegistryError):
                locked.preflight_targets(context, values)
        # Only native registered paths are removed; all subsequent replay must
        # work without even querying their existence.
        original_stat, original_open = Path.stat, Path.open
        raw_paths = {p for r in context.metadata["records"] for p in r["canonical_paths_private"]}
        from unittest.mock import patch
        def guarded(call):
            def invoke(p, *a, **k):
                if str(p) in raw_paths:
                    raise AssertionError("raw endpoint queried")
                return call(p, *a, **k)
            return invoke
        with patch.object(Path, "stat", guarded(original_stat)), patch.object(Path, "open", guarded(original_open)):
            locked.load_context(**self.kwargs, descendants=[checkpoint])

    def test_omitted_intermediate_wrong_order_duplicate_and_wrong_digest_fail(self):
        one, two = self.successor(), self.successor()
        locked.load_context(**self.kwargs, descendants=[one, two])
        for chain in ([two], [two, one], [one, one], [replace(one, sha256="f" * 64)]):
            with self.subTest(chain=chain), self.assertRaises(ValueError):
                locked.load_context(**self.kwargs, descendants=chain)

    def test_stale_context_cannot_omit_new_project_consent(self):
        context = locked.load_context(**self.kwargs)
        auth = deepcopy(self.native.fixture.auth)
        files = locked.readiness_files(context, self.development[0])
        registration = registry.decode(context.original_objects[files["registration/registration.json"]])
        auth.update(authorized_raw_sha256=[self.development[0]], batch_id=registration["batch_id"],
                    registration_sha256=files["registration/registration.json"],
                    source_specification_sha256=files["registration/source_specification.json"],
                    preserved_readiness_report_sha256=files["readiness.json"])
        checkpoint = self.successor(auth=auth)
        with self.assertRaisesRegex(policy.RegistryError, "omits_project_history"):
            locked.require_project_history(context, self.native.project)
        locked.require_project_history(locked.load_context(**self.kwargs, descendants=[checkpoint]), self.native.project)

    def test_native_final_consent_and_late_unresolved_development_link_fail(self):
        evidence = self.fixture.declaration_path
        relationship = {"left": "raw:" + self.development[0], "right": "raw:" + self.development[1],
                        "status": "unresolved", "evidence": [{"path": str(evidence), "expected_sha256": fixtures.pin(evidence)}]}
        checkpoint = self.successor([relationship])
        with self.assertRaisesRegex(policy.RegistryError, "identity_or_component_changed"):
            locked.load_context(**self.kwargs, descendants=[checkpoint])

    def test_native_final_reservation_invalidates_all_development_access(self):
        auth = deepcopy(self.native.fixture.auth)
        context = locked.load_context(**self.kwargs)
        files = locked.readiness_files(context, self.final[0])
        registration = registry.decode(context.original_objects[files["registration/registration.json"]])
        auth.update(authorized_raw_sha256=[self.final[0]], batch_id=registration["batch_id"],
                    registration_sha256=files["registration/registration.json"],
                    source_specification_sha256=files["registration/source_specification.json"],
                    preserved_readiness_report_sha256=files["readiness.json"])
        checkpoint = self.successor(auth=auth)
        # Reject even before consuming any numeric object from the descendant.
        # Cached rows are not used to decide this early embargo check.
        array_pin = next(e["files"]["numeric/residuals.npz"] for e in context.metadata["events"] if e["kind"] == "archive")
        from unittest.mock import patch
        real_add = registry.ObjectStore.add
        def guarded(store, path, *args, **kwargs):
            if Path(path) == checkpoint.directory / "objects" / array_pin:
                raise AssertionError("descendant array read before final embargo")
            return real_add(store, path, *args, **kwargs)
        with patch.object(registry.ObjectStore, "add", guarded), self.assertRaisesRegex(policy.RegistryError, "final_evidence_invalidated"):
            locked.load_context(**self.kwargs, descendants=[checkpoint])

    def test_snapshot_reader_rejects_outside_old_archive_and_flags_cannot_be_enabled(self):
        with self.assertRaisesRegex(policy.RegistryError, "archive_not_development"):
            locked.load_development_dataset(**self.kwargs, archive_sha256=[self.native.args.expected_summary_sha256])
        view = locked.DescendantDataset(self.pin, (), {}, self.fixture.registry_pin)
        self.assertFalse(view.model_admission_authorized)
        with self.assertRaises(ValueError):
            replace(view, model_admission_authorized=True)
        with self.assertRaisesRegex(policy.RegistryError, "real_fit_not_authorized"):
            view.require_model_admission()

    def test_duplicate_recording_aliases_in_one_validated_dataset_are_rejected(self):
        # Exercise the adapter boundary with real validated arrays and an
        # explicitly substituted raw mapping; this is not archive validation.
        from unittest.mock import patch
        context = locked.load_context(**self.kwargs)
        pin = self.native.args.expected_summary_sha256
        archive = context.datasets[pin]
        raw = next(iter(archive.raw_sha256_by_recording.values()))
        alias = replace(archive, raw_sha256_by_recording={"original": raw, "duplicate-alias": raw})
        with patch.object(locked, "load_context", return_value=replace(context, datasets={pin: alias})), \
                self.assertRaisesRegex(policy.RegistryError, "duplicate_raw_alias"):
            locked.load_development_dataset(**self.kwargs, archive_sha256=[pin])
