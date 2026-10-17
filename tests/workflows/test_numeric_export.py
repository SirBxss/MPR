"""Real synthetic MCAP export/validator conformance; no private recordings."""

import argparse
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from lane_residuals.domain import numeric_export as policy
from lane_residuals.domain.geometry_validation import GeometryValidationError
from lane_residuals.io import numeric_archive, numeric_residuals
from lane_residuals.io.numeric_export_inputs import load_inputs
from lane_residuals.workflows import bounded_recording_readiness as bounded
from lane_residuals.workflows import numeric_export as workflow
from lane_residuals.cli import recording_ingestion as ingestion_cli, numeric_archive as validation_cli
from tests.workflows import test_bounded_recording_readiness as fixtures
from tests.io import bounded_readiness_fixture as synthetic


class NumericExportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BoundedWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def prepare(self, **options):
        fixture = self.fixture
        fixture.prepare(**options)
        self.ready, status = bounded.run_bounded_readiness(fixture.args)
        self.assertEqual(status, 0)
        path = fixture.args.output_directory/bounded.REPORT_NAME
        authorization = self.root/"synthetic-explicit-reservation.json"
        self.arguments = argparse.Namespace(**vars(fixture.args))
        self.arguments.output_directory = self.root/"numeric"
        self.arguments.preserved_readiness_report = path
        self.arguments.expected_readiness_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.arguments.exposure_authorization = authorization
        self.auth = {"contract_revision": policy.AUTHORIZATION_REVISION, "purpose": policy.AUTHORIZATION_PURPOSE,
            "batch_id": self.ready["batch_id"], "registration_sha256": self.ready["registration_sha256"],
            "source_specification_sha256": self.ready["source_specification_sha256"],
            "preserved_readiness_report_sha256": self.arguments.expected_readiness_sha256,
            "authorized_raw_sha256": sorted(r["raw_sha256"] for r in self.ready["recordings"]),
            "attestations": dict.fromkeys(policy.ATTESTATIONS, True)}
        self.set_authorization(self.auth)

    def set_authorization(self, value):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.arguments.exposure_authorization.write_bytes(raw)
        self.arguments.expected_exposure_authorization_sha256 = hashlib.sha256(raw).hexdigest()

    def export(self):
        self.report, self.status = workflow.run_export(self.arguments)
        return self.report

    def validation_arguments(self):
        args = argparse.Namespace(**vars(self.arguments))
        args.export_directory = args.output_directory
        args.expected_summary_sha256 = hashlib.sha256((args.export_directory/policy.SUMMARY).read_bytes()).hexdigest()
        args.validation_receipt = self.root/"validation.json"
        return args

    def rehash(self):
        directory = self.arguments.output_directory
        summary = json.loads((directory/policy.SUMMARY).read_text())
        summary["artifacts_sha256"] = {name: hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in (policy.AUDIT, policy.ARCHIVE)}
        (directory/policy.SUMMARY).write_text(json.dumps(summary))

    def mutate_predecessor(self, value):
        self.arguments.preserved_readiness_report.write_text(json.dumps(value))
        self.arguments.expected_readiness_sha256 = hashlib.sha256(self.arguments.preserved_readiness_report.read_bytes()).hexdigest()
        authorization = {**self.auth, "preserved_readiness_report_sha256": self.arguments.expected_readiness_sha256}
        self.set_authorization(authorization)

    def assert_inconclusive(self):
        self.assertEqual(self.status, 3)
        self.assertEqual(self.report["status"], "inconclusive")
        self.assertEqual({p.name for p in self.arguments.output_directory.iterdir()}, {policy.SUMMARY})
        for key in ("pre_residual_candidate_count", "pre_residual_complete_condition_count", "condition_failure_counts", "residual_failure_counts", "support"):
            self.assertIsNone(self.report[key])
        self.assertFalse(self.report["residuals_exported"])

    def test_real_complete_export_exact_lineage_one_hash_and_raw_free_validation(self):
        self.prepare()
        original = workflow.sha256_stream
        handles = []
        def hashed(stream):
            handles.append(stream)
            return original(stream)
        original_decode = workflow.decoder.check_decoding
        def decoded(stream, *args, **kw):
            self.assertIs(stream, handles[0])
            return original_decode(stream, *args, **kw)
        with patch.object(workflow, "sha256_stream", side_effect=hashed), patch.object(workflow.decoder, "check_decoding", side_effect=decoded):
            self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertEqual(len(handles), 1)
        self.assertEqual(set(self.report), policy.SUMMARY_FIELDS)
        self.assertEqual(self.report["support"]["geometric_profile_count"], 2)
        row = self.report["recordings"][0]
        self.assertEqual(row["readiness"], self.ready["recordings"][0]["readiness"])
        self.assertEqual(row["observer_failure_counts"], {})
        with np.load(self.arguments.output_directory/policy.ARCHIVE, allow_pickle=False) as arrays:
            np.testing.assert_allclose(arrays["residuals_m"], -.5, atol=1e-12)
            self.assertEqual(arrays["recording_id"].dtype, np.dtype("<U48"))
            self.assertEqual(arrays["conditions"].shape, (2, 6))
        self.fixture.raw.unlink()
        receipt, status = workflow.run_validation(self.validation_arguments())
        self.assertEqual(status, 0)
        self.assertIs(receipt["raw_opened"], False)
        self.assertIs(receipt["model_admission_authorized"], False)

    def test_geometry_only_empty_confidence_keeps_observable_zero_length(self):
        self.prepare(confidence=None);self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["support"]["geometric_profile_count"], 2)
        self.assertEqual(self.report["support"]["conditioned_profile_count"], 0)
        audit = json.loads((self.arguments.output_directory/policy.AUDIT).read_text())
        self.assertEqual([r["confidence_vector_length"] for r in audit["rows"]], [0, 0])

    def test_no_odometry_and_empty_geometry_complete_empty_shapes(self):
        self.prepare(no_odometry=True, reference_length=20.);self.export()
        self.assertEqual(self.status, 0, self.report)
        with np.load(self.arguments.output_directory/policy.ARCHIVE, allow_pickle=False) as arrays:
            self.assertEqual(arrays["residuals_m"].shape, (0, 21))
            self.assertEqual(arrays["conditions"].shape, (0, 6))
            self.assertEqual(arrays["geometry_sequence_offsets"].tolist(), [0])

    def test_explicit_authorization_rejects_invalid_selection_before_hash_and_output(self):
        self.prepare()
        variants = []
        for key, value in (("authorized_raw_sha256", []), ("authorized_raw_sha256", ["0"*64]),
                ("batch_id", "wrong"), ("registration_sha256", "0"*64), ("extra", True)):
            variants.append({**self.auth, key: value})
        for value in (False, 1, "true"):
            changed = deepcopy(self.auth)
            changed["attestations"]["explicit_numeric_export_selection"] = value
            variants.append(changed)
        variants += [b'{"duplicate":1,"duplicate":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff', b' '*65_537]
        for value in variants:
            with self.subTest(value=repr(value)[:80]):
                self.set_authorization(value)
                with patch.object(workflow, "sha256_stream") as hasher:
                    with self.assertRaises((ValueError, UnicodeError)):
                        workflow.run_export(self.arguments)
                    hasher.assert_not_called()
                self.assertFalse(self.arguments.output_directory.exists())

    def test_candidate_observation_failure_invalidates_after_science(self):
        self.prepare()
        with patch.object(numeric_residuals, "_metadata", side_effect=AttributeError("synthetic")):
            self.export()
        self.assert_inconclusive()
        row = self.report["recordings"][0]
        self.assertEqual(row["failure_code"], "numeric_candidate_observation_missing")
        self.assertEqual(row["observer_failure_counts"], {"numeric_observer_metadata_unavailable": 2})

    def test_non_candidate_observation_failure_does_not_change_science(self):
        self.prepare(reference_length=20.)
        with patch.object(numeric_residuals, "_metadata", side_effect=AttributeError("synthetic")):
            self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["recordings"][0]["readiness"], self.ready["recordings"][0]["readiness"])

    def test_memory_and_workflow_errors_are_not_harmless_observer_failures(self):
        self.prepare()
        from lane_residuals.domain.recording_ingestion import RecordingIngestionError
        for error in (MemoryError(), RecordingIngestionError("readiness_processing_time_limit")):
            with patch.object(numeric_residuals, "_metadata", side_effect=error):
                self.export()
            self.assert_inconclusive()
            self.assertEqual(self.report["recordings"][0]["observer_failure_counts"], {})
            for path in self.arguments.output_directory.iterdir():path.unlink()
            self.arguments.output_directory.rmdir()

    def test_geometry_parity_contradiction_is_batch_failure_not_row_loss(self):
        self.prepare()
        with patch.object(numeric_residuals, "aligned_residual", side_effect=GeometryValidationError("reference_alignment_projection_ambiguous", "synthetic")):
            self.export()
        self.assert_inconclusive()

    def test_only_nonfinite_residual_is_an_allowed_row_exclusion(self):
        self.prepare()
        with patch.object(numeric_residuals, "aligned_residual", side_effect=GeometryValidationError("residual_non_finite", "synthetic")):
            self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["residual_failure_counts"], {"residual_non_finite": 2})
        self.assertEqual(self.report["support"]["geometric_profile_count"], 0)

    def test_late_authorization_mutation_invalidates_whole_batch(self):
        self.prepare(second=True)
        original = workflow.decoder.check_decoding
        calls = 0
        def decoded(*args, **kw):
            nonlocal calls
            result = original(*args, **kw);calls += 1
            if calls == 2:
                self.arguments.exposure_authorization.write_bytes(self.arguments.exposure_authorization.read_bytes()+b" ")
            return result
        with patch.object(workflow.decoder, "check_decoding", side_effect=decoded):self.export()
        self.assertEqual(calls, 2)
        self.assert_inconclusive()

    def test_fresh_readiness_drift_cannot_construct_residuals(self):
        self.prepare()
        original = workflow.ScientificSink.finalize
        def drift(sink):
            result = original(sink)
            result[0]["counts"]["pairing_maximum_delta_ns"] = 0
            return result
        with patch.object(workflow.ScientificSink, "finalize", drift), patch.object(numeric_residuals, "aligned_residual") as construct:
            self.export();construct.assert_not_called()
        self.assert_inconclusive()

    def test_validator_rejects_unpinned_summary_and_no_receipt(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        args = self.validation_arguments()
        args.expected_summary_sha256 = "0"*64
        with self.assertRaises(ValueError):workflow.run_validation(args)
        self.assertFalse(args.validation_receipt.exists())

    def test_changed_audit_with_coherent_artifact_rehash_still_fails_semantics(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        directory = self.arguments.output_directory
        audit = json.loads((directory/policy.AUDIT).read_text())
        audit["rows"][0]["estimate_source_time_ns_decimal_private"] = "02000000000"
        (directory/policy.AUDIT).write_text(json.dumps(audit))
        summary = json.loads((directory/policy.SUMMARY).read_text())
        summary["artifacts_sha256"][policy.AUDIT] = hashlib.sha256((directory/policy.AUDIT).read_bytes()).hexdigest()
        (directory/policy.SUMMARY).write_text(json.dumps(summary))
        with self.assertRaises(ValueError):workflow.run_validation(self.validation_arguments())

    def test_npz_header_and_uncompressed_size_are_checked_before_loading(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        directory = self.arguments.output_directory
        with zipfile.ZipFile(directory/policy.ARCHIVE) as archive:
            members = {info.filename: archive.read(info) for info in archive.infolist()}
        members["residuals_m.npy"] = members["residuals_m.npy"].replace(b"'<f8'", b"'>f8'", 1)
        with zipfile.ZipFile(directory/policy.ARCHIVE, "w") as archive:
            for name, raw in members.items():archive.writestr(name, raw)
        summary = json.loads((directory/policy.SUMMARY).read_text())
        summary["artifacts_sha256"][policy.ARCHIVE] = hashlib.sha256((directory/policy.ARCHIVE).read_bytes()).hexdigest()
        (directory/policy.SUMMARY).write_text(json.dumps(summary))
        with patch.object(numeric_archive.np, "load", side_effect=AssertionError("allocation forbidden")) as loader:
            with self.assertRaises(ValueError):workflow.run_validation(self.validation_arguments())
            loader.assert_not_called()

    def test_existing_output_is_never_modified(self):
        self.prepare();self.arguments.output_directory.mkdir()
        marker = self.arguments.output_directory/"owner-file";marker.write_text("keep")
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaises(ValueError):workflow.run_export(self.arguments)
            hasher.assert_not_called()
        self.assertEqual(marker.read_text(), "keep")

    def test_full_uint64_source_clocks_survive_real_mcap_and_sqlite(self):
        def unsigned_clock(file, _):
            root = next(m for m in file.message_type if m.name == "EstimatedDrivePaths")
            next(f for f in root.field if f.name == "time_stamp").type = 4
        self.prepare(times=(2**64-100_000_001, 2**64-1), mutate=unsigned_clock);self.export()
        self.assertEqual(self.status, 0, self.report)
        with np.load(self.arguments.output_directory/policy.ARCHIVE, allow_pickle=False) as arrays:
            self.assertEqual(arrays["estimate_source_time_ns_decimal"].tolist(), [str(2**64-100_000_001), str(2**64-1)])

    def test_maximum_registration_identifier_survives_real_export(self):
        original = fixtures.specification
        def source(path):
            result = original(path);result["recordings"][0]["recording_id"] = "a"+"x"*47
            return result
        with patch.object(fixtures, "specification", side_effect=source):self.prepare()
        self.export();self.assertEqual(self.status, 0, self.report)
        with np.load(self.arguments.output_directory/policy.ARCHIVE, allow_pickle=False) as arrays:
            self.assertEqual(arrays["recording_id"].tolist(), ["a"+"x"*47]*2)

    def test_invalid_confidence_values_are_observed_without_becoming_features(self):
        self.prepare(confidence=float("nan"));self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["support"]["conditioned_profile_count"], 0)
        audit = json.loads((self.arguments.output_directory/policy.AUDIT).read_text())
        self.assertEqual([r["confidence_vector_length"] for r in audit["rows"]], [40, 40])

    def test_reordered_multi_path_message_uses_declared_keep_lane(self):
        def mutate_messages(**kwargs):
            values = original(**kwargs)
            for value in values:
                if not value.DESCRIPTOR.full_name.endswith("EstimatedDrivePaths"):continue
                old = type(value.drive_paths[0])();old.CopyFrom(value.drive_paths[0])
                value.ClearField("drive_paths")
                other = value.drive_paths.add();other.CopyFrom(old);other.role = 2
                del other.drive_path_confidences[:];other.drive_path_confidences.extend([.2]*3)
                value.drive_paths.add().CopyFrom(old)
            return values
        original = synthetic.messages
        with patch.object(synthetic, "messages", side_effect=mutate_messages):self.prepare()
        self.export();self.assertEqual(self.status, 0, self.report)
        audit = json.loads((self.arguments.output_directory/policy.AUDIT).read_text())
        self.assertEqual([r["confidence_vector_length"] for r in audit["rows"]], [40, 40])

    def test_supported_zero_message_schema_version_is_retained(self):
        def variant(file, _):file.name = "another_synthetic_version.proto"
        estimate = synthetic.classes(variant)[0]
        self.prepare(extra_streams=((synthetic.TOPICS[0], estimate, []),));self.export()
        self.assertEqual(self.status, 0, self.report)
        bindings = self.report["recordings"][0]["binding_observations"]
        self.assertEqual(sum(b["role"] == "estimate" for b in bindings), 2)
        self.assertEqual(self.report["recordings"][0]["readiness"], self.ready["recordings"][0]["readiness"])

    def test_future_source_odometry_preserves_rejection_and_evidence(self):
        O = synthetic.classes()[2]
        t = synthetic.T
        poses = [O(timestamp=time, x_position=x) for time, x in ((t-50_000_000, 0.), (t-10_000_000, .4), (t+10_000_000, .6))]
        self.prepare(no_odometry=True, extra_streams=((synthetic.TOPICS[2], O, poses),));self.export()
        self.assertEqual(self.status, 0, self.report)
        self.assertGreater(self.report["condition_failure_counts"].get("speed_uses_future_source_sample", 0), 0)
        self.assertEqual(self.report["support"]["conditioned_profile_count"], 0)

    def test_missing_and_late_used_log_evidence_is_exported_exactly(self):
        original = synthetic.stream_items
        def changed(values):
            for schema, channel, message, value in original(values):
                if channel.topic == synthetic.TOPICS[2]:message.log_time = 0
                yield schema, channel, message, value
        with patch.object(synthetic, "stream_items", side_effect=changed):self.prepare()
        self.export();self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["condition_failure_counts"].get("speed_log_time_unavailable"), 2)
        audit = json.loads((self.arguments.output_directory/policy.AUDIT).read_text())
        self.assertTrue(all(r["speed_bracket_evidence"]["minimum_input_log_time_ns_decimal_private"] == "0" for r in audit["rows"]))

    def test_initial_resource_boundary_is_checked_before_raw_hash(self):
        self.prepare()
        from types import SimpleNamespace
        boundary = bounded.INITIAL_SCRATCH_BYTES+policy.ARTIFACT_RESERVE_BYTES
        with patch.object(bounded.shutil, "disk_usage", return_value=SimpleNamespace(free=boundary-1)), patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "19point5gib"):workflow.run_export(self.arguments)
            hasher.assert_not_called()
        with patch.object(bounded.shutil, "disk_usage", return_value=SimpleNamespace(free=boundary)):
            self.assertEqual(workflow._resources(self.root, initial=True)["scratch_free_bytes"], boundary)

    def test_authorization_symlink_and_wrong_digest_are_preflight_errors(self):
        self.prepare();path = self.arguments.exposure_authorization
        saved = self.root/"authorization-target";path.rename(saved);path.symlink_to(saved)
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaises(ValueError):workflow.run_export(self.arguments)
            hasher.assert_not_called()
        path.unlink();saved.rename(path)
        self.arguments.expected_exposure_authorization_sha256 = "0"*64
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaises(ValueError):workflow.run_export(self.arguments)
            hasher.assert_not_called()

    def test_negative_rejected_source_time_remains_observational(self):
        original = synthetic.messages
        def rejected(**kwargs):
            values = original(**kwargs)
            values[0].time_stamp = -1;values[0].drive_paths[0].error = 2
            return values
        with patch.object(synthetic, "messages", side_effect=rejected):self.prepare()
        self.export();self.assertEqual(self.status, 0, self.report)
        self.assertEqual(self.report["recordings"][0]["observer_failure_counts"], {"numeric_observer_metadata_unavailable": 1})

    def test_retagging_a_bad_readiness_report_does_not_override_semantics(self):
        self.prepare()
        bads = []
        for key, value in (("status", "inconclusive"), ("runtime_source_sha256", "0"*64), ("scientific_adapter_revision", "wrong"), ("roles_assigned", True)):
            bads.append({**self.ready, key: value})
        changed = deepcopy(self.ready);changed["recordings"][0]["readiness"]["counts"]["surprise"] = 0;bads.append(changed)
        changed = deepcopy(self.ready);changed["recordings"][0]["readiness"]["sensor_geometry_support"]["frame_count"] = True;bads.append(changed)
        for value in bads:
            self.mutate_predecessor(value)
            with patch.object(workflow, "sha256_stream") as hasher:
                with self.assertRaises(ValueError):workflow.run_export(self.arguments)
                hasher.assert_not_called()

    def test_later_recording_failure_cannot_publish_earlier_numeric_arrays(self):
        self.prepare(second=True)
        original = numeric_residuals.collect_candidates
        calls = 0
        def failed(*args):
            nonlocal calls
            calls += 1
            if calls == 2:raise sqlite3.OperationalError("database or disk is full")
            return original(*args)
        with patch.object(workflow, "collect_candidates", side_effect=failed):self.export()
        self.assert_inconclusive()
        self.assertEqual(self.report["recordings"][0]["status"], "complete")
        self.assertTrue(all(r["outcome_exposure"] is None for r in self.report["recordings"]))

    def test_late_raw_replacement_invalidates_all_publication(self):
        self.prepare();original = workflow.collect_candidates
        def changed(*args):
            result = original(*args)
            other = self.root/"replacement";other.write_bytes(self.fixture.raw.read_bytes());os.replace(other, self.fixture.raw)
            return result
        with patch.object(workflow, "collect_candidates", side_effect=changed):self.export()
        self.assert_inconclusive()

    def test_serialization_failure_removes_owned_numeric_files(self):
        self.prepare()
        with patch.object(np.lib.format, "write_array", side_effect=MemoryError()):self.export()
        self.assert_inconclusive()
        self.assertFalse(any(p.name.startswith("mpr-numeric-publication-") for p in self.root.iterdir()))

    def test_standalone_receipt_cannot_change_registration_directory(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        args = self.validation_arguments();args.validation_receipt = self.fixture.directory/"receipt.json"
        with self.assertRaises(ValueError):workflow.run_validation(args)
        self.assertFalse(args.validation_receipt.exists())

    def test_directory_and_member_symlinks_are_not_valid_archives(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        args = self.validation_arguments()
        link = self.root/"export-link";link.symlink_to(args.export_directory, target_is_directory=True)
        args.export_directory = link
        with self.assertRaises(ValueError):workflow.run_validation(args)
        path = self.arguments.output_directory/policy.AUDIT
        other = self.root/"audit-target";path.rename(other);path.symlink_to(other)
        with self.assertRaises(ValueError):workflow.run_validation(self.validation_arguments())

    def test_independent_mapping_support_and_exposure_mutations_are_rejected(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        directory = self.arguments.output_directory
        original_summary = (directory/policy.SUMMARY).read_bytes()
        original_audit = (directory/policy.AUDIT).read_bytes()
        for mutation in ("mapping", "row_code", "clock", "causality", "exposure", "support", "observer", "policy"):
            with self.subTest(mutation=mutation):
                summary = json.loads(original_summary);audit = json.loads(original_audit)
                if mutation == "mapping":audit["rows"][0]["estimate_message_index"] = 1
                elif mutation == "row_code":audit["rows"][0]["residual_failure_code"] = "ValueError"
                elif mutation == "clock":audit["rows"][0]["signed_reference_minus_estimate_ns_decimal"] = "1"
                elif mutation == "causality":audit["rows"][0]["speed_bracket_evidence"]["minimum_input_log_time_ns_decimal_private"] = "0"
                elif mutation == "exposure":summary["recordings"][0]["outcome_exposure"]["final_test_eligible"] = True
                elif mutation == "support":summary["support"]["geometry_sequences"][0]["duration_ns"] += 1
                elif mutation == "observer":summary["recordings"][0]["observer_failure_counts"] = {"hidden": 1}
                elif mutation == "policy":summary["estimate_admission_policy"]["flag_absent_v2_root_file_sha256"] = []
                (directory/policy.AUDIT).write_text(json.dumps(audit))
                (directory/policy.SUMMARY).write_text(json.dumps(summary));self.rehash()
                with self.assertRaises(ValueError):workflow.run_validation(self.validation_arguments())
                self.assertFalse(self.validation_arguments().validation_receipt.exists())

    def test_npz_shapes_dtypes_nonfinite_mappings_sequences_and_trailing_data_fail(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        directory = self.arguments.output_directory
        original = (directory/policy.ARCHIVE).read_bytes()
        with np.load(io.BytesIO(original), allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
        for mutation in ("endian", "fortran", "object", "shape", "nonfinite", "subset", "offsets", "missing", "extra", "trailing", "npy_trailing"):
            with self.subTest(mutation=mutation):
                data = {name: value.copy() for name, value in arrays.items()}
                if mutation == "endian":data["residuals_m"] = data["residuals_m"].astype(">f8")
                elif mutation == "fortran":data["residuals_m"] = np.asfortranarray(data["residuals_m"])
                elif mutation == "object":data["residuals_m"] = data["residuals_m"].astype(object)
                elif mutation == "shape":data["conditions"] = data["conditions"][:, :5]
                elif mutation == "nonfinite":data["conditions"][0, 0] = float("nan")
                elif mutation == "subset":data["conditioned_profile_indices"] = data["conditioned_profile_indices"][::-1]
                elif mutation == "offsets":data["geometry_sequence_offsets"] = np.asarray([0, 1, 2], dtype="<i8")
                elif mutation == "missing":data.pop("conditions")
                elif mutation == "extra":data["hidden"] = np.zeros(1)
                with (directory/policy.ARCHIVE).open("wb") as stream:np.savez(stream, **data)
                if mutation == "trailing":
                    with (directory/policy.ARCHIVE).open("ab") as stream:stream.write(b"trailing")
                elif mutation == "npy_trailing":
                    with zipfile.ZipFile(directory/policy.ARCHIVE) as archive:members = {i.filename: archive.read(i) for i in archive.infolist()}
                    members["conditions.npy"] += b"trailing"
                    with zipfile.ZipFile(directory/policy.ARCHIVE, "w") as archive:
                        for name, value in members.items():archive.writestr(name, value)
                self.rehash()
                with self.assertRaises(ValueError):workflow.run_validation(self.validation_arguments())
                self.assertFalse(self.validation_arguments().validation_receipt.exists())

    def test_output_device_mismatch_is_preflight_without_raw_hash(self):
        self.prepare();parent = self.root/"another-device";parent.mkdir()
        self.arguments.output_directory = parent/"numeric"
        original = Path.stat
        def state(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == parent:
                values = list(result);values[2] += 1
                return os.stat_result(values)
            return result
        with patch.object(Path, "stat", state), patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "device_mismatch"):workflow.run_export(self.arguments)
            hasher.assert_not_called()

    def test_standalone_does_not_stat_or_open_missing_raw(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        self.fixture.raw.unlink()
        original_stat, original_open = Path.stat, Path.open
        def stat(path, *args, **kwargs):
            if path == self.fixture.raw:raise AssertionError("raw stat forbidden")
            return original_stat(path, *args, **kwargs)
        def opened(path, *args, **kwargs):
            if path == self.fixture.raw:raise AssertionError("raw open forbidden")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "stat", stat), patch.object(Path, "open", opened):
            receipt, status = workflow.run_validation(self.validation_arguments())
        self.assertEqual(status, 0)
        self.assertFalse(receipt["raw_opened"])

    def test_late_publication_failure_preserves_an_unrelated_new_file(self):
        self.prepare();original = workflow.os.replace
        output = self.arguments.output_directory
        def replaced(source, target):
            if Path(target) == output/policy.ARCHIVE:
                (output/"owner-file").write_text("keep")
                raise OSError("synthetic failure")
            return original(source, target)
        with patch.object(workflow.os, "replace", side_effect=replaced):self.export()
        self.assertEqual(self.status, 3)
        self.assertEqual((output/"owner-file").read_text(), "keep")
        self.assertFalse((output/policy.SUMMARY).exists())
        self.assertFalse((output/policy.AUDIT).exists())

    def test_late_artifact_mutation_cannot_receive_a_success_receipt(self):
        self.prepare();self.export();self.assertEqual(self.status, 0, self.report)
        args = self.validation_arguments();original = workflow._write_json
        def changed(path, *a, **kw):
            result = original(path, *a, **kw)
            if path.name.startswith(".numeric-validation-"):
                with (args.export_directory/policy.AUDIT).open("ab") as stream:stream.write(b" ")
            return result
        with patch.object(workflow, "_write_json", side_effect=changed):
            with self.assertRaises(ValueError):workflow.run_validation(args)
        self.assertFalse(args.validation_receipt.exists())
        self.assertFalse(any(p.name.startswith(".numeric-validation-") for p in self.root.iterdir()))

    def test_cli_export_dispatch_requires_explicit_lineage_and_authorization(self):
        values = ["export-residuals"]
        for name in ("registration-directory", "scratch-directory", "output-directory", "preserved-inventory-report", "preserved-decode-report",
                "preserved-readiness-report", "exposure-authorization", "expected-readiness-sha256", "expected-exposure-authorization-sha256"):
            values += ["--"+name, "synthetic-unused"]
        for topic in synthetic.TOPICS:values += ["--topic", topic]
        with patch.object(ingestion_cli, "_bounded_run", return_value=({}, 3)) as dispatch:
            self.assertEqual(ingestion_cli.main(values), 3)
        self.assertEqual(dispatch.call_args.args[0].command, "export-residuals")

    def test_cli_process_limit_restored_on_export_failure_and_validation_error(self):
        import resource
        before = resource.getrlimit(resource.RLIMIT_AS)
        with patch.object(workflow, "run_export", side_effect=ValueError("synthetic")):
            with self.assertRaises(ValueError):ingestion_cli._bounded_run(argparse.Namespace(command="export-residuals"))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), before)
        values = []
        for name in ("registration-directory", "preserved-inventory-report", "preserved-decode-report", "preserved-readiness-report", "exposure-authorization",
                "expected-readiness-sha256", "expected-exposure-authorization-sha256", "export-directory", "expected-summary-sha256", "validation-receipt"):
            values += ["--"+name, "synthetic-unused"]
        for topic in synthetic.TOPICS:values += ["--topic", topic]
        with patch.object(workflow, "run_validation", side_effect=zipfile.BadZipFile("PRIVATE-DETAIL")), self.assertLogs(level="ERROR") as logs:
            self.assertEqual(validation_cli.main(values), 2)
        self.assertNotIn("PRIVATE-DETAIL", " ".join(logs.output))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), before)

    def test_publication_deadline_never_leaves_a_complete_archive(self):
        self.prepare()
        from lane_residuals.domain.recording_ingestion import RecordingIngestionError
        with patch.object(workflow, "_checkpoint", side_effect=RecordingIngestionError("numeric_serialization_or_validation_time_limit")):
            self.export()
        self.assertEqual(self.status, 3)
        self.assertFalse(self.arguments.output_directory.exists())
        self.assertFalse(any(p.name.startswith("mpr-numeric-publication-") for p in self.root.iterdir()))

    def test_duplicate_and_partial_authorizations_cannot_select_rows(self):
        self.prepare(second=True)
        original = deepcopy(self.auth)
        for hashes in (original["authorized_raw_sha256"][:1], original["authorized_raw_sha256"][::-1],
                original["authorized_raw_sha256"]*2, original["authorized_raw_sha256"]+["f"*64]):
            self.set_authorization({**original, "authorized_raw_sha256": hashes})
            with patch.object(workflow, "sha256_stream") as hasher:
                with self.assertRaises(ValueError):workflow.run_export(self.arguments)
                hasher.assert_not_called()

    def test_per_record_caps_do_not_bypass_aggregate_advertised_edp_limit(self):
        self.prepare(second=True)
        inventory = deepcopy(self.fixture.inventory);decode = deepcopy(self.fixture.decode)
        for r in inventory["recordings"]:
            for row in r["inventory"]["channels"]+r["inventory"]["topics"]:
                if row["topic"] == synthetic.TOPICS[0]:row["advertised_message_count"] = 60_000
            r["inventory"]["advertised_statistics"]["message_count"] += 59_998
        self.arguments.preserved_inventory_report.write_text(json.dumps(inventory))
        decode["preserved_inventory_report_sha256"] = hashlib.sha256(self.arguments.preserved_inventory_report.read_bytes()).hexdigest()
        for record in decode["recordings"]:
            checked = record["decode_check"]
            for row in checked["channel_versions"]+checked["topics"]:
                if row["topic"] == synthetic.TOPICS[0]:row.update(advertised_message_count=60_000, decoded_message_count=60_000)
            checked["decoded_selected_message_count"] += 59_998
        self.arguments.preserved_decode_report.write_text(json.dumps(decode))
        with patch.object(workflow, "sha256_stream") as hasher:
            with self.assertRaisesRegex(ValueError, "numeric_aggregate_edp_limit"):workflow.run_export(self.arguments)
            hasher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
