"""Real native synthetic exports, immutable snapshots and raw-free loading."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import numpy as np

from lane_residuals.domain import artifact_registry as policy
from lane_residuals.io import artifact_registry as registry
from lane_residuals.io.generic_dataset import load_generic_archive
from lane_residuals.io.exploratory_archive import load_exploratory_archive
from tests.workflows import test_numeric_export as native_fixtures


def pin(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ArtifactRegistryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = native_fixtures.NumericExportTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.prepare()
        self.fixture.export()
        self.assertEqual(self.fixture.status,0)
        from lane_residuals.workflows.numeric_export import run_validation
        self.args = self.fixture.validation_arguments()
        self.assertEqual(run_validation(self.args)[1],0)
        self.root = self.fixture.root
        self.project = self.root/"project with spaces"
        self.project.mkdir()
        subprocess.run(["git","init","-q",str(self.project)],check=True)
        (self.project/".gitignore").write_text("data/\nconfig/private/\n")
        self.authorizations = self.project/"config/private"
        self.authorizations.mkdir(parents=True)
        self.adopted = self.authorizations/"numeric_export_authorization_synthetic.json"
        shutil.copyfile(self.args.exposure_authorization,self.adopted)
        self.manifest_path = self.root/"import.json"
        archive = {k: str(getattr(self.args,k)) if isinstance(getattr(self.args,k),Path) else getattr(self.args,k)
            for k in registry.ARCHIVE_INPUT_FIELDS if k != "expected_validation_receipt_sha256"}
        archive["expected_validation_receipt_sha256"] = pin(self.args.validation_receipt)
        self.manifest = dict(contract_revision=policy.MANIFEST_REVISION,registrations=[],archives=[archive],relationships=[],additional_authorizations=[])
        self.output = self.project/"data/catalog/private/snapshot001"

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def create(self, **kwargs):
        self.write_manifest()
        if not kwargs and hasattr(self,"last_snapshot"):
            kwargs=dict(previous_directory=self.last_snapshot[0],expected_previous_sha256=self.last_snapshot[1])
        result=registry.import_evidence(self.manifest_path, project_root=self.project,output_directory=self.output,**kwargs)
        self.last_snapshot=(self.output,result[1])
        return result

    def test_raw_offline_exact_matched_rows_resets_and_no_fit(self):
        self.fixture.fixture.raw.unlink()
        before = {p:pin(p) for p in self.args.export_directory.iterdir()}
        metadata, h = self.create()
        view = registry.load_registry_dataset(self.output,h,[self.args.expected_summary_sha256])
        dataset = view.archives[0]
        self.assertEqual(dataset.geometry_residuals_m.shape,(2,21))
        np.testing.assert_array_equal(dataset.matched_residuals_m,dataset.geometry_residuals_m[dataset.arrays["conditioned_profile_indices"]])
        self.assertFalse(dataset.conditions.flags.writeable)
        self.assertFalse(dataset.matched_residuals_m.flags.writeable)
        seq = list(dataset.matched_sequences())
        self.assertEqual(len(seq),1)
        self.assertEqual(seq[0][0].shape,(2,21))
        self.assertTrue(all(r["permanent_development_reservation"] and r["complete_publication_observed"] for r in metadata["records"]))
        self.assertEqual(before,{p:pin(p) for p in before})
        for object_ in [view,dataset]:
            with self.assertRaisesRegex(policy.RegistryError,"no_model_admission"):
                object_.require_model_admission()
        self.assertFalse(view.model_admission_authorized)

    def test_duplicate_import_is_idempotent_and_old_reservation_survives_source_removal(self):
        metadata,h = self.create()
        events = metadata["events"]
        original = (self.output/"registry.json").read_bytes()
        old = self.output;self.output=self.output.with_name("snapshot002")
        again,h2 = self.create(previous_directory=old,expected_previous_sha256=h)
        self.assertEqual(again["events"],events)
        self.assertEqual(again["records"],metadata["records"])
        self.assertEqual((old/"registry.json").read_bytes(),original)
        self.adopted.unlink();self.args.exposure_authorization.unlink()
        shutil.rmtree(self.args.export_directory)
        self.manifest.update(archives=[],registrations=[])
        self.output=self.output.with_name("snapshot003")
        restored,h3 = self.create(previous_directory=old,expected_previous_sha256=h)
        self.assertTrue(restored["records"][0]["permanent_development_reservation"])
        registry.load_registry_dataset(self.output,h3,[self.args.expected_summary_sha256])

    def test_failed_or_unrun_adopted_authorization_is_captured_without_archive(self):
        auth = deepcopy(self.fixture.auth);auth["authorized_raw_sha256"]=["f"*64]
        auth["registration_sha256"]="e"*64
        path=self.authorizations/"numeric_export_authorization_unrun.json";path.write_text(json.dumps(auth))
        metadata,_=self.create()
        value=next(r for r in metadata["records"] if r["raw_sha256"]=="f"*64)
        self.assertTrue(value["permanent_development_reservation"])
        self.assertFalse(value["complete_publication_observed"])
        self.assertIsNone(value["size_bytes"])

    def test_renamed_and_external_authorizations_are_retained_without_copying_unrelated_config(self):
        auth=deepcopy(self.fixture.auth);auth["authorized_raw_sha256"]=["f"*64];auth["registration_sha256"]="e"*64
        (self.authorizations/"renamed-consent.json").write_text(json.dumps(auth))
        unrelated=self.authorizations/"unrelated.json";unrelated.write_text('{"configuration":"unrelated"}')
        external=self.root/"external-adopted.json";auth["authorized_raw_sha256"]=["d"*64];external.write_text(json.dumps(auth))
        self.manifest["additional_authorizations"]=[dict(path=str(external),expected_sha256=pin(external))]
        metadata,_=self.create()
        self.assertEqual({r["raw_sha256"] for r in metadata["records"]},{self.fixture.auth["authorized_raw_sha256"][0],"f"*64,"d"*64})
        self.assertNotIn(pin(unrelated),metadata["objects_sha256"])

    def test_false_draft_not_adopted_partial_and_nonboolean_stop_without_output(self):
        auth=deepcopy(self.fixture.auth)
        auth["attestations"]=dict.fromkeys(auth["attestations"],False)
        path=self.authorizations/"numeric_export_authorization_draft.json";path.write_text(json.dumps(auth))
        metadata,_=self.create()
        self.assertFalse(any(e.get("sha256")==pin(path) for e in metadata["events"]))
        self.output=self.output.with_name("partial")
        auth["attestations"]["explicit_numeric_export_selection"]=True;path.write_text(json.dumps(auth))
        with self.assertRaisesRegex(policy.RegistryError,"partial_authorization"):
            self.create()
        self.assertFalse(self.output.exists())
        auth["attestations"]["explicit_numeric_export_selection"]=1;path.write_text(json.dumps(auth))
        with self.assertRaises(policy.RegistryError):self.create()
        self.assertFalse(self.output.exists())

    def test_registry_index_edit_object_drift_and_unpinned_previous_are_rejected(self):
        metadata,h=self.create()
        with self.assertRaises(policy.RegistryError):registry.load_registry(self.output,"0"*64)
        altered=deepcopy(metadata);altered["records"][0]["permanent_development_reservation"]=False
        p=self.output/"registry.json";p.write_text(json.dumps(altered))
        with self.assertRaisesRegex(policy.RegistryError,"cached_index"):
            registry.load_registry(self.output,pin(p))
        p.write_text(json.dumps(metadata))
        one=next((self.output/"objects").iterdir());one.write_bytes(one.read_bytes()+b" ")
        with self.assertRaises(policy.RegistryError):registry.load_registry(self.output,pin(p))
        old=self.output;self.output=self.output.with_name("unbound")
        with self.assertRaisesRegex(policy.RegistryError,"previous_snapshot_pin_required"):
            self.create(previous_directory=old)
        self.assertFalse(self.output.exists())

    def test_archive_hash_and_receipt_drift_fail_before_output(self):
        original=deepcopy(self.manifest)
        for key in ["expected_summary_sha256","expected_validation_receipt_sha256","expected_readiness_sha256","expected_exposure_authorization_sha256"]:
            self.manifest=deepcopy(original);self.manifest["archives"][0][key]="0"*64
            with self.subTest(key=key),self.assertRaises(ValueError):self.create()
            self.assertFalse(self.output.exists())

    def test_unsupported_producer_and_historical_consumer_remain_rejected(self):
        summary=self.args.export_directory/"numeric_export.json"
        value=json.loads(summary.read_text());value["runtime_source_sha256"]="0"*64;summary.write_text(json.dumps(value))
        self.args.expected_summary_sha256=pin(summary)
        with self.assertRaisesRegex(policy.RegistryError,"producer_not_supported"):
            load_generic_archive(self.args)
        with self.assertRaises(ValueError):load_exploratory_archive(self.args.export_directory)

    def test_conflicting_session_links_block_dataset_and_unresolved_links_exclude(self):
        raw=self.fixture.auth["authorized_raw_sha256"][0]
        evidence=self.root/"session-declaration.txt";evidence.write_text("synthetic owner session evidence")
        def link(right,status="confirmed"):
            return dict(left="raw:"+raw,right=right,status=status,evidence=[dict(path=str(evidence),expected_sha256=pin(evidence))])
        self.manifest["relationships"]=[link("session:one"),link("session:two")]
        metadata,h=self.create()
        self.assertTrue(metadata["records"][0]["session_link_conflict"])
        with self.assertRaisesRegex(policy.RegistryError,"session_conflict"):
            registry.load_registry_dataset(self.output,h,[self.args.expected_summary_sha256])
        self.output=self.output.with_name("potential")
        self.manifest["relationships"]=[link("raw:"+"f"*64,"unresolved")]
        metadata,h=self.create()
        other=next(r for r in metadata["records"] if r["raw_sha256"]=="f"*64)
        self.assertTrue(other["linked_development_exclusion"])
        self.assertTrue(other["session_link_unresolved"])

    def test_private_output_and_existing_destination_preserved(self):
        self.write_manifest()
        with self.assertRaises(policy.RegistryError):
            registry.import_evidence(self.manifest_path,project_root=self.project,output_directory=self.project/"public")
        self.output.mkdir(parents=True);(self.output/"keep").write_text("user")
        with self.assertRaises(policy.RegistryError):self.create()
        self.assertEqual((self.output/"keep").read_text(),"user")

    def test_registration_only_never_infers_outing_from_source_locator(self):
        self.manifest["archives"]=[]
        self.adopted.unlink()
        self.manifest["registrations"]=[dict(registration_directory=str(self.args.registration_directory),
            expected_registration_sha256=pin(self.args.registration_directory/"registration.json"),reports=[])]
        metadata,h=self.create()
        value=metadata["records"][0]
        self.assertFalse(value["permanent_development_reservation"])
        self.assertFalse(value["independent_outing_admitted"])
        self.assertEqual(value["declared_physical_session_ids"],[])
        self.assertEqual(value["raw_cache_observations"],[])

    def test_raw_metadata_observation_is_explicit_and_never_claims_byte_verification(self):
        metadata,h=self.create(observe_cache=True)
        value=metadata["records"][0]["raw_cache_observations"][-1]
        self.assertEqual(value["state"],"present_unverified")
        self.assertFalse(metadata["raw_cache_deletion_authorized"])

    def test_authorization_drift_during_publication_stops_before_commit_marker(self):
        self.write_manifest()
        original=registry.ObjectStore.unchanged
        calls=[]
        def changed(store):
            calls.append(True)
            if len(calls)==1:self.adopted.write_text("{}")
            return original(store)
        with patch.object(registry.ObjectStore,"unchanged",changed),self.assertRaises(ValueError):
            registry.import_evidence(self.manifest_path,project_root=self.project,output_directory=self.output)
        self.assertFalse((self.output/"registry.json").exists())

    def test_two_valid_archives_of_same_raw_cannot_duplicate_dataset_rows(self):
        from lane_residuals.workflows.numeric_export import run_validation
        self.fixture.arguments.output_directory=self.root/"numeric-second"
        self.fixture.export()
        second=self.fixture.validation_arguments()
        second.validation_receipt=self.root/"validation-second.json"
        self.assertEqual(run_validation(second)[1],0)
        entry={k:str(getattr(second,k)) if isinstance(getattr(second,k),Path) else getattr(second,k)
            for k in registry.ARCHIVE_INPUT_FIELDS if k!="expected_validation_receipt_sha256"}
        entry["expected_validation_receipt_sha256"]=pin(second.validation_receipt)
        self.manifest["archives"].append(entry)
        metadata,h=self.create()
        self.assertEqual(len(metadata["records"]),1)
        with self.assertRaisesRegex(policy.RegistryError,"duplicate_raw_in_dataset"):
            registry.load_registry_dataset(self.output,h,[self.args.expected_summary_sha256,second.expected_summary_sha256])

    def test_registration_report_lineage_and_original_receipt_claims_are_checked(self):
        self.manifest["registrations"]=[dict(registration_directory=str(self.args.registration_directory),
            expected_registration_sha256=pin(self.args.registration_directory/"registration.json"),
            reports=[dict(role="readiness",path=str(self.args.preserved_readiness_report),expected_sha256=pin(self.args.preserved_readiness_report))])]
        metadata,h=self.create()
        self.assertEqual(len(metadata["records"]),1)
        self.output=self.output.with_name("bad-receipt")
        receipt=json.loads(self.args.validation_receipt.read_text());receipt["geometric_profile_count"]=99
        self.args.validation_receipt.write_text(json.dumps(receipt))
        self.manifest["archives"][0]["expected_validation_receipt_sha256"]=pin(self.args.validation_receipt)
        with self.assertRaises(ValueError):self.create()
        self.assertFalse(self.output.exists())

    def test_cli_import_verify_and_failed_verify_restore_process_limit(self):
        import resource
        from lane_residuals.cli.artifact_registry import main
        self.write_manifest();before=resource.getrlimit(resource.RLIMIT_AS)
        self.assertEqual(main(["import","--manifest",str(self.manifest_path),"--project-root",str(self.project),"--output-directory",str(self.output)]),0)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),before)
        h=pin(self.output/"registry.json")
        self.assertEqual(main(["verify","--registry-directory",str(self.output),"--expected-registry-sha256",h]),0)
        self.assertEqual(main(["verify","--registry-directory",str(self.output),"--expected-registry-sha256","0"*64]),2)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),before)

    def test_cold_rebuild_and_stale_parent_cannot_drop_adopted_reservations(self):
        metadata,h=self.create();old=self.output
        auth=deepcopy(self.fixture.auth);auth["registration_sha256"]="e"*64;auth["authorized_raw_sha256"]=["f"*64]
        p=self.authorizations/"another.json";p.write_text(json.dumps(auth))
        self.output=old.with_name("snapshot002");_,h2=self.create(previous_directory=old,expected_previous_sha256=h)
        p.unlink();self.manifest.update(archives=[],registrations=[]);self.write_manifest()
        target=old.with_name("snapshot003")
        with self.assertRaisesRegex(policy.RegistryError,"previous_required_preserve"):
            registry.import_evidence(self.manifest_path,project_root=self.project,output_directory=target)
        with self.assertRaisesRegex(policy.RegistryError,"previous_omits"):
            registry.import_evidence(self.manifest_path,project_root=self.project,output_directory=target,
                previous_directory=old,expected_previous_sha256=h)
        self.output=target
        state,h3=self.create(previous_directory=old.with_name("snapshot002"),expected_previous_sha256=h2)
        self.assertTrue(next(r for r in state["records"] if r["raw_sha256"]=="f"*64)["permanent_development_reservation"])

    def test_project_writer_lock_prevents_competing_snapshots(self):
        import fcntl
        private=self.project/"data/catalog/private";private.mkdir(parents=True)
        self.write_manifest()
        with (private/".registry-write.lock").open("w") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(policy.RegistryError,"another_import"):
                registry.import_evidence(self.manifest_path,project_root=self.project,output_directory=self.output)
        self.assertFalse(self.output.exists())
