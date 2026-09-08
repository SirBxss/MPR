from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lane_residuals.cli.independent_outing_intake import main
from lane_residuals.domain.corpus_inventory import McapInventoryRecord, TopicCompatibility
from lane_residuals.domain.independent_outing_intake import (
    CONTRACT_REVISION,
    EXPECTED_TOPOLOGY_SOURCE,
    FrameTechnicalEvidence,
    RecordingTechnicalEvidence,
)
from lane_residuals.domain.path_source_probe import (
    ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
    ESTIMATE_DESCRIPTOR_IDENTITY_SOURCE,
    LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
)
from lane_residuals.io.reports import write_strict_json as _write_strict_json
from lane_residuals.workflows.independent_outing_intake import (
    SCHEMA_COMPATIBILITY_AMENDMENT_ID,
    OUTPUT_NAMES,
    OUTING_FIELDS,
    RECORDING_FIELDS,
    run_independent_outing_intake,
)
from scripts.inspection.verify_v017_intake_bundle import (
    VerificationError,
    verify_intake_bundle,
)


# Importing any lane_residuals submodule first executes the legacy root package
# initializer. Its eager compatibility re-exports include gaussian/modeling and
# plotting definitions. The v0.17 modules do not directly depend on those
# layers; this exact transitive graph makes the pre-existing footprint explicit
# and forces review before it can change silently.
FROZEN_INTAKE_MODULE_ALLOWLIST = frozenset(
    {
        "lane_residuals",
        "lane_residuals.batch_pairing_audit",
        "lane_residuals.cli",
        "lane_residuals.cli.independent_outing_intake",
        "lane_residuals.domain",
        "lane_residuals.domain.alignment",
        "lane_residuals.domain.alignment_contract",
        "lane_residuals.domain.batch_pairing",
        "lane_residuals.domain.conditional_features",
        "lane_residuals.domain.corpus_inventory",
        "lane_residuals.domain.edp_transitions",
        "lane_residuals.domain.expanded_sequence_dataset",
        "lane_residuals.domain.expanded_sequence_dataset_v0131",
        "lane_residuals.domain.geometry_validation",
        "lane_residuals.domain.independent_outing_intake",
        "lane_residuals.domain.motion",
        "lane_residuals.domain.pairing",
        "lane_residuals.domain.path_source_probe",
        "lane_residuals.domain.reference",
        "lane_residuals.domain.residual_dataset",
        "lane_residuals.domain.residuals",
        "lane_residuals.domain.sequence_dataset",
        "lane_residuals.edp_transition_audit",
        "lane_residuals.gaussian",
        "lane_residuals.geometry_validation",
        "lane_residuals.io",
        "lane_residuals.io.corpus_inventory",
        "lane_residuals.io.expanded_sequence_dataset",
        "lane_residuals.io.expanded_sequence_dataset_v0131",
        "lane_residuals.io.independent_outing_intake",
        "lane_residuals.io.mcap",
        "lane_residuals.io.odometry",
        "lane_residuals.io.reports",
        "lane_residuals.legacy",
        "lane_residuals.legacy.association_cli",
        "lane_residuals.legacy.plotting",
        "lane_residuals.legacy.preprocessing",
        "lane_residuals.legacy.provisional_residuals",
        "lane_residuals.mcap_io",
        "lane_residuals.modeling",
        "lane_residuals.modeling.gaussian",
        "lane_residuals.pairing_audit",
        "lane_residuals.path_source_probe",
        "lane_residuals.plotting",
        "lane_residuals.preprocessing",
        "lane_residuals.reference_audit",
        "lane_residuals.residual_extraction",
        "lane_residuals.residuals",
        "lane_residuals.workflows",
        "lane_residuals.workflows.independent_outing_intake",
    }
)


def _compatible_topics(message_count: int = 500) -> tuple[TopicCompatibility, ...]:
    return tuple(
        TopicCompatibility(
            role=role,
            topic=topic,
            expected_schema_name=schema,
            present=True,
            message_count=message_count,
            schema_names=(schema,),
            schema_encodings=("protobuf",),
            message_encodings=("protobuf",),
        )
        for role, topic, schema in (
            ("estimate", "/adp/estimated_drive_paths", "Adp.Perception.EstimatedDrivePaths"),
            ("map", "/adp/road_lane_map_based", "Adp.Perception.Road"),
            ("odometry", "/adp/odometry", "Adp.OdometryState"),
        )
    )


def _basename_number(path: Path) -> int:
    digits = "".join(character for character in path.stem if character.isdigit())
    return int(digits or "1")


class _SyntheticInspectors:
    def __init__(self) -> None:
        self.duration_ns_by_basename: dict[str, int] = {}
        self.frame_count_by_basename: dict[str, int] = {}
        self.topology_by_basename: dict[str, str] = {}
        self.source_start_by_basename: dict[str, int] = {}
        self.descriptor_hashes_by_basename: dict[str, tuple[str, ...]] = {}

    def inventory(
        self,
        path: Path,
        *,
        root: Path,
        recording_id: str,
        drive_id: str | None,
        precomputed_sha256: str,
        **_: object,
    ) -> McapInventoryRecord:
        number = _basename_number(path)
        start = self.source_start_by_basename.get(path.name, number * 1_000_000_000_000)
        duration = self.duration_ns_by_basename.get(path.name, 120_000_000_000)
        return McapInventoryRecord(
            path=str(path.resolve()),
            basename=path.name,
            relative_path=path.resolve().relative_to(root.resolve()).as_posix(),
            recording_id=recording_id,
            drive_id=drive_id,
            file_size_bytes=path.stat().st_size,
            sha256=precomputed_sha256,
            readable=True,
            empty=False,
            internal_start_log_time_ns=start,
            internal_end_log_time_ns=start + duration,
            first_estimate_source_time_ns=start,
            last_estimate_source_time_ns=start + duration,
            estimate_source_timestamp_count=500,
            estimate_missing_source_timestamp_count=0,
            estimate_source_timestamps_strictly_increasing=True,
            filename_start=None,
            filename_end=None,
            filename_duration_ms=None,
            mcap_identifier=None,
            filename_internal_time_disagreement=False,
            topics=_compatible_topics(),
        )

    def technical(self, path: Path, *, raw_usable: bool, **_: object) -> RecordingTechnicalEvidence:
        number = _basename_number(path)
        start = self.source_start_by_basename.get(path.name, number * 1_000_000_000_000)
        count = self.frame_count_by_basename.get(path.name, 500)
        topology = self.topology_by_basename.get(path.name, EXPECTED_TOPOLOGY_SOURCE)
        frames = tuple(
            FrameTechnicalEvidence(
                estimate_message_index=index,
                source_time_ns=start + index * 100_000_000,
                topology_source_name=topology,
                topology_gate_candidate=True,
                h100_geometry_ready=True,
                anchor_distance_within_limit=True,
                causal_inputs_available=True,
                raw_usable=raw_usable,
                eligible=raw_usable and topology == EXPECTED_TOPOLOGY_SOURCE,
                failure_codes=(
                    ()
                    if raw_usable and topology == EXPECTED_TOPOLOGY_SOURCE
                    else ("synthetic_fixed_gate_failure",)
                ),
            )
            for index in range(count)
        )
        return RecordingTechnicalEvidence(
            estimate_message_count=count,
            map_message_count=count,
            frames=frames,
            estimate_file_descriptor_sha256=(
                self.descriptor_hashes_by_basename.get(
                    path.name,
                    (LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,),
                )
            ),
        )


def _outing(label: str, basename: str, hour: int) -> dict[str, object]:
    return {
        "private_outing_label": label,
        "acquisition_start_utc": f"2026-09-03T{hour:02d}:00:00+00:00",
        "separate_physical_session": True,
        "independence_basis_private": f"separate session declaration {label}",
        "mcap_basenames_private": [basename],
    }


def _manifest_payload(
    outings: list[dict[str, object]],
    *,
    prior_hash: str | None = None,
    amendment: str | None = None,
) -> dict[str, object]:
    return {
        "version": "0.17",
        "purpose": "prospective_independent_outing_intake",
        "acquisition_batch_closed": True,
        "created_before_outcome_inspection": True,
        "legacy_development_outing_count": 1,
        "prior_successful_lock_sha256": prior_hash,
        "superseding_contract_amendment_id": amendment,
        "outings": outings,
    }


def _write_manifest(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _make_corpus(root: Path, count: int = 7, *, nested: bool = False) -> tuple[Path, list[str]]:
    corpus = root / "new-mcaps"
    corpus.mkdir(parents=True)
    names: list[str] = []
    for index in range(1, count + 1):
        name = f"new_outing_{index:02d}.mcap"
        destination = corpus / (f"nested-{index % 2}" if nested else "")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / name).write_bytes(f"immutable-mcap-{index}".encode("ascii"))
        names.append(name)
    return corpus, names


def _arguments(
    root: Path,
    manifest: Path,
    output: Path,
    prior: Path | None = None,
    amended_from_failed: Path | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        new_mcap_root=root,
        acquisition_manifest=manifest,
        output_directory=output,
        prior_successful_lock=prior,
        amended_from_failed_intake_directory=amended_from_failed,
        log_level="INFO",
    )


def _downgrade_to_legacy_audit(output: Path) -> None:
    lock_path = output / "independent_outing_lock.json"
    summary_path = output / "independent_outing_intake_summary.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    lock.pop("schema_compatibility_amendment")
    summary.pop("schema_compatibility_amendment")
    lock["contract_revision"] = "v0.17.0-reviewed-2026-09-03-layout-c1"
    summary["contract_revision"] = "v0.17.0-reviewed-2026-09-03-layout-c1"
    _write_strict_json(lock_path, lock)
    summary["output_sha256"]["independent_outing_lock.json"] = hashlib.sha256(
        lock_path.read_bytes()
    ).hexdigest()
    _write_strict_json(summary_path, summary)


class IndependentOutingWorkflowTests(unittest.TestCase):
    def _success_fixture(
        self, root: Path, *, nested: bool = False
    ) -> tuple[Path, Path, _SyntheticInspectors]:
        corpus, names = _make_corpus(root, nested=nested)
        outings = [_outing(f"private-{index}", name, index) for index, name in enumerate(names, 1)]
        manifest = _write_manifest(root / "acquisition.private.json", _manifest_payload(outings))
        return corpus, manifest, _SyntheticInspectors()

    @staticmethod
    def _run(
        arguments: argparse.Namespace, inspectors: _SyntheticInspectors
    ) -> tuple[dict[str, object], int]:
        return run_independent_outing_intake(
            arguments,
            inventory_inspector=inspectors.inventory,
            technical_inspector=inspectors.technical,
        )

    def test_success_writes_exact_deterministic_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            output_a, output_b = root / "output-a", root / "output-b"
            summary, status = self._run(_arguments(corpus, manifest, output_a), inspectors)
            second, second_status = self._run(_arguments(corpus, manifest, output_b), inspectors)

            self.assertEqual((status, second_status), (0, 0))
            self.assertEqual(summary, second)
            self.assertEqual(set(OUTPUT_NAMES), {path.name for path in output_a.iterdir()})
            for name in OUTPUT_NAMES:
                self.assertEqual((output_a / name).read_bytes(), (output_b / name).read_bytes())
            lock = json.loads((output_a / "independent_outing_lock.json").read_text())
            self.assertEqual(
                set(lock),
                {
                    "version",
                    "purpose",
                    "contract_revision",
                    "status",
                    "manifest",
                    "legacy_development_outing_count",
                    "raw_file_sha256_by_basename_private",
                    "private_to_opaque_outing_id",
                    "outings",
                    "eligibility_rules",
                    "availability_gate",
                    "split_contract",
                    "split_assignments_authorized",
                    "role_counts",
                    "attestations",
                    "prior_successful_lock",
                    "final_outing_embargo",
                    "schema_compatibility_amendment",
                },
            )
            self.assertEqual(
                set(summary),
                {
                    "version",
                    "purpose",
                    "status",
                    "contract_revision",
                    "manifest_sha256",
                    "mcap_file_count",
                    "declared_new_outing_count",
                    "eligible_new_outing_count",
                    "ineligible_new_outing_count",
                    "legacy_development_outing_count",
                    "total_independent_outing_count_including_legacy",
                    "raw_usable_recording_count",
                    "summed_usable_duration_s",
                    "eligible_h100_frame_count",
                    "eligible_sequence_count",
                    "availability_gate",
                    "final_count",
                    "role_counts",
                    "failure_code_counts_non_mutually_exclusive",
                    "attestation_status",
                    "prior_successful_lock_sha256",
                    "prior_successful_lock_verified",
                    "overlapping_raw_sha256_count",
                    "output_sha256",
                    "summary_self_hash_recorded",
                    "claim_limits",
                    "next_authorized_action",
                    "schema_compatibility_amendment",
                },
            )
            expected_amendment = {
                "amendment_id": SCHEMA_COMPATIBILITY_AMENDMENT_ID,
                "descriptor_identity_source": ESTIMATE_DESCRIPTOR_IDENTITY_SOURCE,
                "allowed_flag_absent_estimate_file_descriptor_sha256": (
                    ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256
                ),
                "legacy_estimate_file_descriptor_reference_sha256": (
                    LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256
                ),
                "legacy_validity_rule": {
                    "descriptor_rule": (
                        "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist"
                    ),
                    "field_name": "model_parameters_optional_flag",
                    "field_number": 8,
                    "protobuf_type": "bool",
                    "explicit_presence_required": True,
                    "required_value": True,
                },
                "observed_estimate_file_descriptor_sha256": [
                    LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256
                ],
                "amended_from_failed_audit": None,
            }
            self.assertEqual(lock["contract_revision"], CONTRACT_REVISION)
            self.assertEqual(
                lock["schema_compatibility_amendment"], expected_amendment
            )
            self.assertEqual(
                summary["schema_compatibility_amendment"], expected_amendment
            )
            self.assertEqual(lock["status"], "locked")
            self.assertTrue(lock["split_assignments_authorized"])
            self.assertEqual(lock["availability_gate"]["eligible_new_outing_count"], 7)
            self.assertEqual(lock["split_contract"]["final_count"], 2)
            self.assertEqual(lock["role_counts"], {"development": 5, "final_test": 2})
            self.assertFalse(lock["eligibility_rules"]["numeric_frame_values_exported"])
            self.assertNotIn(
                "outing_start",
                summary["failure_code_counts_non_mutually_exclusive"],
            )

    def test_layout_change_only_changes_recording_path_and_inherited_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flat = root / "flat"
            nested = root / "nested"
            flat.mkdir()
            nested.mkdir()
            corpus_a, names = _make_corpus(flat)
            corpus_b, _ = _make_corpus(nested, nested=True)
            outings = [_outing(f"private-{index}", name, index) for index, name in enumerate(names, 1)]
            manifest = _write_manifest(root / "same-manifest.json", _manifest_payload(outings))
            inspectors = _SyntheticInspectors()
            output_a, output_b = root / "a", root / "b"
            self._run(_arguments(corpus_a, manifest, output_a), inspectors)
            self._run(_arguments(corpus_b, manifest, output_b), inspectors)

            for name in ("independent_outings.csv", "independent_outing_lock.json"):
                self.assertEqual((output_a / name).read_bytes(), (output_b / name).read_bytes())
            self.assertNotEqual(
                (output_a / "independent_outing_recordings.csv").read_bytes(),
                (output_b / "independent_outing_recordings.csv").read_bytes(),
            )
            summary_a = json.loads((output_a / "independent_outing_intake_summary.json").read_text())
            summary_b = json.loads((output_b / "independent_outing_intake_summary.json").read_text())
            hashes_a = summary_a.pop("output_sha256")
            hashes_b = summary_b.pop("output_sha256")
            self.assertEqual(summary_a, summary_b)
            self.assertNotEqual(
                hashes_a["independent_outing_recordings.csv"],
                hashes_b["independent_outing_recordings.csv"],
            )
            self.assertEqual(hashes_a["independent_outings.csv"], hashes_b["independent_outings.csv"])
            self.assertEqual(hashes_a["independent_outing_lock.json"], hashes_b["independent_outing_lock.json"])

    def test_observed_descriptor_identities_are_sorted_unique_union(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            inspectors.descriptor_hashes_by_basename["new_outing_01.mcap"] = (
                ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
                LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
            )
            summary, _ = self._run(
                _arguments(corpus, manifest, root / "output"), inspectors
            )
            self.assertEqual(
                summary["schema_compatibility_amendment"][
                    "observed_estimate_file_descriptor_sha256"
                ],
                sorted(
                    {
                        ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
                        LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
                    }
                ),
            )

    def test_split_is_invariant_to_names_labels_times_and_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus_a, names_a = _make_corpus(root / "first")
            second_root = root / "second"
            second_root.mkdir()
            corpus_b = second_root / "new-mcaps"
            (corpus_b / "nested").mkdir(parents=True)
            names_b: list[str] = []
            for index, original in enumerate(names_a, 1):
                renamed = f"cosmetic_name_{8 - index:02d}.mcap"
                (corpus_b / "nested" / renamed).write_bytes((corpus_a / original).read_bytes())
                names_b.append(renamed)
            outings_a = [_outing(f"private-{i}", name, i) for i, name in enumerate(names_a, 1)]
            outings_b = [
                _outing(f"renamed-private-{i}", name, 20 - i)
                for i, name in enumerate(names_b, 1)
            ][::-1]
            manifest_a = _write_manifest(root / "a.json", _manifest_payload(outings_a))
            manifest_b = _write_manifest(root / "b.json", _manifest_payload(outings_b))
            output_a, output_b = root / "out-a", root / "out-b"
            inspectors = _SyntheticInspectors()
            self._run(_arguments(corpus_a, manifest_a, output_a), inspectors)
            self._run(_arguments(corpus_b, manifest_b, output_b), inspectors)

            def by_fingerprint(path: Path) -> dict[str, tuple[str, str, str, str]]:
                with path.open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                return {
                    row["outing_fingerprint_sha256"]: (
                        row["outing_id"],
                        row["split_score_sha256"],
                        row["split_rank"],
                        row["cohort_role"],
                    )
                    for row in rows
                }

            self.assertEqual(
                by_fingerprint(output_a / "independent_outings.csv"),
                by_fingerprint(output_b / "independent_outings.csv"),
            )

    def test_gate_failure_writes_all_outputs_without_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, names = _make_corpus(root, count=6)
            manifest = _write_manifest(
                root / "manifest.json",
                _manifest_payload([_outing(f"private-{i}", name, i) for i, name in enumerate(names, 1)]),
            )
            output = root / "output"
            summary, status = self._run(_arguments(corpus, manifest, output), _SyntheticInspectors())
            self.assertEqual(status, 3)
            self.assertEqual(summary["status"], "insufficient_independent_outings")
            self.assertEqual(set(OUTPUT_NAMES), {path.name for path in output.iterdir()})
            with (output / "independent_outings.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(all(row["cohort_role"] == "" for row in rows))
            self.assertTrue(all(row["split_rank"] == "" for row in rows))
            lock = json.loads((output / "independent_outing_lock.json").read_text())
            self.assertFalse(lock["split_assignments_authorized"])
            self.assertFalse(lock["final_outing_embargo"]["active"])

    def test_failed_audit_lineage_is_additive_deterministic_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, names = _make_corpus(root, count=1)
            manifest = _write_manifest(
                root / "manifest.json",
                _manifest_payload([_outing("private-1", names[0], 1)]),
            )
            inspectors = _SyntheticInspectors()
            failed = root / "failed-v0170"
            _, first_status = self._run(
                _arguments(corpus, manifest, failed), inspectors
            )
            self.assertEqual(first_status, 3)
            _downgrade_to_legacy_audit(failed)
            legacy_result = verify_intake_bundle(corpus, manifest, failed)
            self.assertEqual(legacy_result["verification_status"], "passed")
            self.assertEqual(
                legacy_result["contract_revision"],
                "v0.17.0-reviewed-2026-09-03-layout-c1",
            )

            outputs = (root / "amended-a", root / "amended-b")
            summaries = []
            for output in outputs:
                summary, status = self._run(
                    _arguments(
                        corpus,
                        manifest,
                        output,
                        amended_from_failed=failed,
                    ),
                    inspectors,
                )
                self.assertEqual(status, 3)
                summaries.append(summary)
            self.assertEqual(summaries[0], summaries[1])
            for name in OUTPUT_NAMES:
                self.assertEqual(
                    (outputs[0] / name).read_bytes(),
                    (outputs[1] / name).read_bytes(),
                )

            expected_hashes = {
                name: hashlib.sha256((failed / name).read_bytes()).hexdigest()
                for name in OUTPUT_NAMES
            }
            amendment = summaries[0]["schema_compatibility_amendment"]
            self.assertEqual(
                amendment["amended_from_failed_audit"],
                {
                    "contract_revision": (
                        "v0.17.0-reviewed-2026-09-03-layout-c1"
                    ),
                    "manifest_sha256": hashlib.sha256(
                        manifest.read_bytes()
                    ).hexdigest(),
                    "output_sha256": dict(sorted(expected_hashes.items())),
                },
            )
            with (outputs[0] / OUTPUT_NAMES[1]).open(
                encoding="utf-8", newline=""
            ) as handle:
                self.assertTrue(
                    all(not row["cohort_role"] for row in csv.DictReader(handle))
                )
            result = verify_intake_bundle(
                corpus,
                manifest,
                outputs[0],
                failed,
            )
            self.assertEqual(result["verification_status"], "passed")
            self.assertEqual(result["contract_revision"], CONTRACT_REVISION)
            self.assertEqual(
                result["schema_compatibility_amendment_id"],
                SCHEMA_COMPATIBILITY_AMENDMENT_ID,
            )

    def test_failed_audit_reconciliation_rejects_drift_before_output(self) -> None:
        mutations = (
            (
                "extra file",
                "file set differs",
                lambda failed: (failed / "extra.txt").write_text(
                    "extra", encoding="utf-8"
                ),
            ),
            (
                "status",
                "not a reconciled failed",
                lambda failed: self._mutate_json(
                    failed / OUTPUT_NAMES[2],
                    lambda payload: payload.__setitem__("status", "locked"),
                ),
            ),
            (
                "schema",
                "schema differs",
                lambda failed: self._mutate_json(
                    failed / OUTPUT_NAMES[2],
                    lambda payload: payload.__setitem__("unexpected", True),
                ),
            ),
            (
                "recording hash",
                "recording CSV differs",
                lambda failed: self._mutate_recording_hash(
                    failed / OUTPUT_NAMES[0]
                ),
            ),
            (
                "sibling hash",
                "sibling output hashes",
                lambda failed: self._mutate_json(
                    failed / OUTPUT_NAMES[3],
                    lambda payload: payload["output_sha256"].__setitem__(
                        OUTPUT_NAMES[0], "0" * 64
                    ),
                ),
            ),
        )
        for name, expected_error, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                corpus, names = _make_corpus(root, count=1)
                manifest = _write_manifest(
                    root / "manifest.json",
                    _manifest_payload([_outing("private-1", names[0], 1)]),
                )
                inspectors = _SyntheticInspectors()
                failed = root / "failed"
                self._run(_arguments(corpus, manifest, failed), inspectors)
                _downgrade_to_legacy_audit(failed)
                mutate(failed)
                output = root / "amended"
                with self.assertRaisesRegex(ValueError, expected_error):
                    self._run(
                        _arguments(
                            corpus,
                            manifest,
                            output,
                            amended_from_failed=failed,
                        ),
                        inspectors,
                    )
                self.assertFalse(output.exists())

    @staticmethod
    def _mutate_json(path: Path, mutation) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutation(payload)
        _write_strict_json(path, payload)

    @staticmethod
    def _mutate_recording_hash(path: Path) -> None:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["sha256"] = "0" * 64
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RECORDING_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_verifier_requires_and_rechecks_supplied_failed_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, names = _make_corpus(root, count=1)
            manifest = _write_manifest(
                root / "manifest.json",
                _manifest_payload([_outing("private-1", names[0], 1)]),
            )
            inspectors = _SyntheticInspectors()
            failed = root / "failed"
            amended = root / "amended"
            self._run(_arguments(corpus, manifest, failed), inspectors)
            _downgrade_to_legacy_audit(failed)
            self._run(
                _arguments(
                    corpus,
                    manifest,
                    amended,
                    amended_from_failed=failed,
                ),
                inspectors,
            )
            with self.assertRaisesRegex(
                VerificationError, "schema compatibility amendment differs"
            ):
                verify_intake_bundle(corpus, manifest, amended)
            (failed / OUTPUT_NAMES[0]).write_bytes(
                (failed / OUTPUT_NAMES[0]).read_bytes() + b"\n"
            )
            with self.assertRaisesRegex(
                VerificationError,
                "recording CSV|sibling output hashes",
            ):
                verify_intake_bundle(corpus, manifest, amended, failed)

    def test_120_second_and_500_frame_boundaries_are_inclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            output = root / "output"
            summary, status = self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertEqual(status, 0)
            self.assertEqual(summary["eligible_new_outing_count"], 7)

            second_root = root / "below"
            second_root.mkdir()
            corpus, manifest, inspectors = self._success_fixture(second_root)
            inspectors.duration_ns_by_basename["new_outing_01.mcap"] = 119_999_999_999
            inspectors.frame_count_by_basename["new_outing_02.mcap"] = 499
            summary, status = self._run(
                _arguments(corpus, manifest, second_root / "output"), inspectors
            )
            self.assertEqual(status, 3)
            self.assertEqual(summary["eligible_new_outing_count"], 5)

    def test_non_sensor_candidate_excludes_complete_outing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            inspectors.topology_by_basename["new_outing_07.mcap"] = (
                "ROAD_TOPOLOGY_SOURCE_LANE_MAP"
            )
            output = root / "output"
            summary, status = self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertEqual(status, 3)
            self.assertEqual(summary["eligible_new_outing_count"], 6)
            with (output / "independent_outings.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            excluded = next(row for row in rows if row["private_outing_label"] == "private-7")
            self.assertEqual(excluded["technically_eligible"], "False")
            self.assertIn("mixed_or_unknown_topology_source", excluded["failure_codes"])

    def test_cross_mcap_boundaries_join_or_split_without_losing_frames(self) -> None:
        for boundary_gap_ns, expected_sequences, expected_stitches in (
            (100_000_000, 1, 1),
            (300_000_000, 2, 0),
        ):
            with self.subTest(boundary_gap_ns=boundary_gap_ns):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    corpus, names = _make_corpus(root)
                    extra = "new_outing_01b.mcap"
                    (corpus / extra).write_bytes(b"immutable-mcap-1b")
                    outings = [
                        _outing(f"private-{i}", name, i)
                        for i, name in enumerate(names, 1)
                    ]
                    outings[0]["mcap_basenames_private"] = [names[0], extra]
                    manifest = _write_manifest(
                        root / "manifest.json", _manifest_payload(outings)
                    )
                    inspectors = _SyntheticInspectors()
                    first_start = 1_000_000_000_000
                    inspectors.source_start_by_basename[names[0]] = first_start
                    inspectors.source_start_by_basename[extra] = (
                        first_start + 120_000_000_000 + boundary_gap_ns
                    )
                    inspectors.frame_count_by_basename[names[0]] = 1201
                    output = root / "output"
                    summary, status = self._run(
                        _arguments(corpus, manifest, output), inspectors
                    )
                    self.assertEqual(status, 0)
                    self.assertEqual(summary["eligible_h100_frame_count"], 4701)
                    with (output / "independent_outings.csv").open(
                        encoding="utf-8", newline=""
                    ) as handle:
                        rows = list(csv.DictReader(handle))
                    first = next(
                        row for row in rows if row["private_outing_label"] == "private-1"
                    )
                    self.assertEqual(int(first["sequence_count"]), expected_sequences)
                    self.assertEqual(int(first["retained_eligible_frame_count"]), 1701)
                    with (output / "independent_outing_recordings.csv").open(
                        encoding="utf-8", newline=""
                    ) as handle:
                        recording_rows = list(csv.DictReader(handle))
                    self.assertEqual(
                        sum(row["eligible_sequence_stitched_to_previous"] == "True" for row in recording_rows),
                        expected_stitches,
                    )

    def test_overlapping_usable_intervals_exclude_the_outing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, names = _make_corpus(root)
            extra = "new_outing_01b.mcap"
            (corpus / extra).write_bytes(b"immutable-mcap-1b")
            outings = [_outing(f"private-{i}", name, i) for i, name in enumerate(names, 1)]
            outings[0]["mcap_basenames_private"] = [names[0], extra]
            manifest = _write_manifest(root / "manifest.json", _manifest_payload(outings))
            inspectors = _SyntheticInspectors()
            first_start = 1_000_000_000_000
            inspectors.source_start_by_basename[names[0]] = first_start
            inspectors.source_start_by_basename[extra] = first_start + 119_000_000_000
            output = root / "output"
            summary, status = self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertEqual(status, 3)
            self.assertEqual(summary["eligible_new_outing_count"], 6)
            with (output / "independent_outings.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            first = next(row for row in rows if row["private_outing_label"] == "private-1")
            self.assertEqual(first["usable_intervals_monotonic_nonoverlapping"], "False")
            self.assertIn(
                "usable_source_intervals_overlap_or_are_not_monotonic",
                first["failure_codes"],
            )

    def test_duplicate_content_is_retained_and_later_copy_is_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, names = _make_corpus(root)
            duplicate = corpus / "new_outing_01_copy.mcap"
            duplicate.write_bytes((corpus / names[0]).read_bytes())
            outings = [_outing(f"private-{i}", name, i) for i, name in enumerate(names, 1)]
            outings[0]["mcap_basenames_private"] = [names[0], duplicate.name]
            manifest = _write_manifest(root / "manifest.json", _manifest_payload(outings))
            output = root / "output"
            summary, status = self._run(
                _arguments(corpus, manifest, output), _SyntheticInspectors()
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["mcap_file_count"], 8)
            with (output / "independent_outing_recordings.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            duplicates = [row for row in rows if row["duplicate_of_recording_id"]]
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(duplicates[0]["raw_usable"], "False")
            self.assertIn("duplicate_content", duplicates[0]["failure_codes"])

    def test_exact_recursive_coverage_and_unique_basename_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            (corpus / "undeclared.MCAP").write_bytes(b"extra")
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "exactly cover") as caught:
                self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertIn("missing=[]", str(caught.exception))
            self.assertIn("extra=['undeclared.MCAP']", str(caught.exception))
            self.assertFalse(output.exists())

            (corpus / "undeclared.MCAP").unlink()
            nested = corpus / "nested"
            nested.mkdir()
            (nested / "new_outing_01.mcap").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "basenames are not unique"):
                self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertFalse(output.exists())

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            output = root / "output"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_partial_serialization_failure_leaves_no_output_or_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            output = root / "output"

            def fail_on_summary(path: Path, payload: object, **kwargs: object) -> None:
                if path.name == "independent_outing_intake_summary.json":
                    raise OSError("synthetic serialization failure")
                _write_strict_json(path, payload, **kwargs)

            with patch(
                "lane_residuals.workflows.independent_outing_intake.write_strict_json",
                side_effect=fail_on_summary,
            ):
                with self.assertRaisesRegex(OSError, "synthetic serialization failure"):
                    self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertFalse(output.exists())
            self.assertFalse(any(path.name.startswith(".output.tmp-") for path in root.iterdir()))

    def test_output_hashes_and_private_path_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root, nested=True)
            output = root / "output"
            self._run(_arguments(corpus, manifest, output), inspectors)
            summary = json.loads((output / "independent_outing_intake_summary.json").read_text())
            self.assertEqual(set(summary["output_sha256"]), set(OUTPUT_NAMES[:3]))
            for name, digest in summary["output_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            absolute = str(root.resolve()).encode("utf-8")
            self.assertTrue(all(absolute not in (output / name).read_bytes() for name in OUTPUT_NAMES))
            with (output / OUTPUT_NAMES[0]).open(encoding="utf-8", newline="") as handle:
                headers = tuple(next(csv.reader(handle)))
            self.assertEqual(headers, RECORDING_FIELDS)
            with (output / OUTPUT_NAMES[1]).open(encoding="utf-8", newline="") as handle:
                headers = tuple(next(csv.reader(handle)))
            self.assertEqual(headers, OUTING_FIELDS)

    def test_outputs_have_no_embargoed_numeric_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            output = root / "output"
            self._run(_arguments(corpus, manifest, output), inspectors)
            forbidden_key_fragments = ("residual", "condition", "model", "planner", "figure")

            def keys(value: object) -> list[str]:
                if isinstance(value, dict):
                    return [str(key) for key in value] + [item for child in value.values() for item in keys(child)]
                if isinstance(value, list):
                    return [item for child in value for item in keys(child)]
                return []

            for name in OUTPUT_NAMES[2:]:
                payload = json.loads((output / name).read_text())
                for key in keys(payload):
                    self.assertFalse(any(fragment in key.lower() for fragment in forbidden_key_fragments), key)
            csv_headers = tuple(RECORDING_FIELDS) + tuple(OUTING_FIELDS)
            for header in csv_headers:
                self.assertFalse(any(fragment in header.lower() for fragment in forbidden_key_fragments), header)

    def test_successful_prior_lock_supersession_requires_exact_hash_and_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial_root = root / "initial"
            initial_root.mkdir()
            corpus, manifest, inspectors = self._success_fixture(initial_root)
            first_output = initial_root / "output"
            self._run(_arguments(corpus, manifest, first_output), inspectors)
            _downgrade_to_legacy_audit(first_output)
            prior = first_output / "independent_outing_lock.json"
            prior_hash = hashlib.sha256(prior.read_bytes()).hexdigest()

            next_root = root / "next"
            next_root.mkdir()
            next_corpus, names = _make_corpus(next_root)
            (next_corpus / names[0]).write_bytes((corpus / names[0]).read_bytes())
            for index, name in enumerate(names[1:], 2):
                (next_corpus / name).write_bytes(
                    f"superseding-immutable-mcap-{index}".encode("ascii")
                )
            outings = [_outing(f"next-private-{i}", name, i) for i, name in enumerate(names, 1)]
            next_manifest = _write_manifest(
                next_root / "manifest.json",
                _manifest_payload(outings, prior_hash=prior_hash, amendment="reviewed-amendment-001"),
            )
            output = next_root / "output"
            summary, status = self._run(
                _arguments(next_corpus, next_manifest, output, prior), _SyntheticInspectors()
            )
            self.assertEqual(status, 0)
            self.assertTrue(summary["prior_successful_lock_verified"])
            self.assertEqual(summary["overlapping_raw_sha256_count"], 1)
            lock = json.loads((output / "independent_outing_lock.json").read_text())
            self.assertEqual(lock["prior_successful_lock"]["declared_sha256"], prior_hash)
            self.assertEqual(lock["prior_successful_lock"]["overlapping_raw_sha256_count"], 1)

    def test_prior_lock_cli_coupling_hash_status_map_and_overlap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root)
            with self.assertRaisesRegex(ValueError, "forbidden"):
                self._run(_arguments(corpus, manifest, root / "out", root / "anything"), inspectors)

            superseding_payload = json.loads(manifest.read_text())
            superseding_payload["prior_successful_lock_sha256"] = "a" * 64
            superseding_payload["superseding_contract_amendment_id"] = "reviewed-a"
            superseding = _write_manifest(root / "superseding.json", superseding_payload)
            with self.assertRaisesRegex(ValueError, "required"):
                self._run(_arguments(corpus, superseding, root / "out"), inspectors)

            prior_root = root / "prior-case"
            prior_root.mkdir()
            prior_corpus, prior_manifest, prior_inspectors = self._success_fixture(prior_root)
            for index, path in enumerate(sorted(prior_corpus.rglob("*.mcap")), 1):
                path.write_bytes(f"prior-only-mcap-{index}".encode("ascii"))
            prior_output = prior_root / "output"
            self._run(
                _arguments(prior_corpus, prior_manifest, prior_output),
                prior_inspectors,
            )
            prior = prior_output / "independent_outing_lock.json"
            prior_payload = json.loads(prior.read_text(encoding="utf-8"))
            superseding_payload["prior_successful_lock_sha256"] = "0" * 64
            superseding = _write_manifest(root / "superseding.json", superseding_payload)
            with self.assertRaisesRegex(ValueError, "SHA-256 does not match"):
                self._run(_arguments(corpus, superseding, root / "out", prior), inspectors)

            superseding_payload["prior_successful_lock_sha256"] = hashlib.sha256(prior.read_bytes()).hexdigest()
            superseding = _write_manifest(root / "superseding.json", superseding_payload)
            with self.assertRaisesRegex(ValueError, "no overlapping raw content"):
                self._run(_arguments(corpus, superseding, root / "out", prior), inspectors)

            tampered = root / "prior-tampered.json"
            prior_payload["status"] = "insufficient_independent_outings"
            tampered.write_text(json.dumps(prior_payload, sort_keys=True) + "\n", encoding="utf-8")
            superseding_payload["prior_successful_lock_sha256"] = hashlib.sha256(tampered.read_bytes()).hexdigest()
            superseding = _write_manifest(root / "superseding.json", superseding_payload)
            with self.assertRaisesRegex(ValueError, "not a successful"):
                self._run(_arguments(corpus, superseding, root / "out", tampered), inspectors)

            prior_payload["status"] = "locked"
            first_basename = next(iter(prior_payload["outings"][0]["mcap_sha256_by_basename_private"]))
            prior_payload["outings"][0]["mcap_sha256_by_basename_private"][first_basename] = "e" * 64
            tampered.write_text(json.dumps(prior_payload, sort_keys=True) + "\n", encoding="utf-8")
            superseding_payload["prior_successful_lock_sha256"] = hashlib.sha256(tampered.read_bytes()).hexdigest()
            superseding = _write_manifest(root / "superseding.json", superseding_payload)
            with self.assertRaisesRegex(ValueError, "do not reconcile"):
                self._run(_arguments(corpus, superseding, root / "out", tampered), inspectors)

    def test_manifest_duplicate_json_key_is_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, _, inspectors = self._success_fixture(root)
            manifest = root / "duplicate.json"
            manifest.write_text('{"version":"0.17","version":"0.17"}\n', encoding="utf-8")
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                self._run(_arguments(corpus, manifest, output), inspectors)
            self.assertFalse(output.exists())

    def test_intake_modules_do_not_directly_import_forbidden_layers(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        paths = (
            repository / "src/lane_residuals/cli/independent_outing_intake.py",
            repository / "src/lane_residuals/domain/independent_outing_intake.py",
            repository / "src/lane_residuals/io/independent_outing_intake.py",
            repository / "src/lane_residuals/workflows/independent_outing_intake.py",
        )
        forbidden = ("model", "sampling", "planner", "evaluation", "visualization")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            modules = [
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            ] + [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            ]
            for module in modules:
                self.assertFalse(any(part in module.split(".") for part in forbidden), module)

    def test_intake_cli_module_graph_matches_frozen_allowlist(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        code = (
            "import json, sys\n"
            "import lane_residuals.cli.independent_outing_intake\n"
            "print(json.dumps(sorted(name for name in sys.modules "
            "if name.startswith('lane_residuals'))))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository,
            env={**os.environ, "PYTHONPATH": str(repository / "src")},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        loaded = frozenset(json.loads(completed.stdout))
        self.assertEqual(loaded, FROZEN_INTAKE_MODULE_ALLOWLIST)

    def test_read_only_verifier_reconciles_initial_bundle_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, inspectors = self._success_fixture(root, nested=True)
            output = root / "output"
            self._run(_arguments(corpus, manifest, output), inspectors)
            tracked = (
                manifest,
                *sorted(corpus.rglob("*.mcap")),
                *sorted(output.iterdir()),
            )
            before = {path: path.read_bytes() for path in tracked}

            result = verify_intake_bundle(corpus, manifest, output)

            self.assertEqual(result["verification_status"], "passed")
            self.assertEqual(result["lock_status"], "locked")
            self.assertEqual(result["raw_mcap_count"], 7)
            self.assertEqual(result["eligible_new_outing_count"], 7)
            self.assertEqual(result["final_count"], 2)
            self.assertTrue(result["split_assignments_authorized"])
            self.assertEqual(result["files_written"], 0)
            self.assertEqual(before, {path: path.read_bytes() for path in tracked})
            self.assertEqual(
                set(OUTPUT_NAMES), {path.name for path in output.iterdir()}
            )

    def test_read_only_verifier_rejects_manifest_raw_and_output_drift(self) -> None:
        def tamper_split_assignment(
            corpus: Path, manifest: Path, output: Path
        ) -> None:
            del corpus, manifest
            lock_path = output / "independent_outing_lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["outings"][0]["cohort_role"] = "final_test"
            _write_strict_json(lock_path, lock)
            summary_path = output / "independent_outing_intake_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["output_sha256"]["independent_outing_lock.json"] = (
                hashlib.sha256(lock_path.read_bytes()).hexdigest()
            )
            _write_strict_json(summary_path, summary)

        cases = (
            (
                "manifest",
                "manifest SHA-256 lineage",
                lambda corpus, manifest, output: manifest.write_bytes(
                    manifest.read_bytes() + b"\n"
                ),
            ),
            (
                "raw",
                "raw MCAP SHA-256 mismatch",
                lambda corpus, manifest, output: next(
                    iter(sorted(corpus.rglob("*.mcap")))
                ).write_bytes(b"tampered-raw-mcap"),
            ),
            (
                "output",
                "output SHA-256 mismatch",
                lambda corpus, manifest, output: (
                    output / "independent_outing_recordings.csv"
                ).write_bytes(
                    (output / "independent_outing_recordings.csv").read_bytes() + b"\n"
                ),
            ),
            ("split", "split assignment mismatch", tamper_split_assignment),
        )
        for name, message, mutate in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                corpus, manifest, inspectors = self._success_fixture(root)
                output = root / "output"
                self._run(_arguments(corpus, manifest, output), inspectors)
                mutate(corpus, manifest, output)
                with self.assertRaisesRegex(VerificationError, message):
                    verify_intake_bundle(corpus, manifest, output)

    def test_data_arrival_runbook_tracks_frozen_first_lock_surface(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        runbook = (
            repository / "docs/independent_outing_data_arrival_runbook.md"
        ).read_text(encoding="utf-8")
        first_lock = runbook.split("<!-- first-lock-command:start -->", 1)[1].split(
            "<!-- first-lock-command:end -->", 1
        )[0]
        normalized_runbook = " ".join(runbook.split())
        self.assertIn(
            "python -m lane_residuals.cli.independent_outing_intake", first_lock
        )
        self.assertNotIn("--prior-successful-lock", first_lock)
        self.assertIn("verify_v017_intake_bundle.py", runbook)
        self.assertIn("config/private/independent_outings_v017.private.json", runbook)
        self.assertIn("at least 7 technically eligible", normalized_runbook)
        self.assertIn("120.0 seconds", normalized_runbook)
        self.assertIn("500 eligible H100 frames", normalized_runbook)
        for status in ("0", "2", "3"):
            self.assertIn(f"Exit status `{status}`", runbook)
        for output_name in OUTPUT_NAMES:
            self.assertIn(output_name, runbook)

        verifier_path = repository / "scripts/inspection/verify_v017_intake_bundle.py"
        tree = ast.parse(
            verifier_path.read_text(encoding="utf-8"), filename=str(verifier_path)
        )
        imported_modules = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ] + [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        self.assertFalse(
            any(
                module == "lane_residuals" or module.startswith("lane_residuals.")
                for module in imported_modules
            )
        )


class IndependentOutingCliTests(unittest.TestCase):
    @patch("lane_residuals.cli.independent_outing_intake.run_independent_outing_intake")
    def test_cli_accepts_failed_audit_lineage_directory(self, run) -> None:
        run.return_value = (
            {
                "mcap_file_count": 1,
                "declared_new_outing_count": 1,
                "eligible_new_outing_count": 0,
                "status": "insufficient_independent_outings",
            },
            3,
        )
        status = main(
            [
                "new-root",
                "--acquisition-manifest",
                "manifest.json",
                "--output-directory",
                "output",
                "--amended-from-failed-intake-directory",
                "failed-v0170",
            ]
        )
        self.assertEqual(status, 3)
        arguments = run.call_args.args[0]
        self.assertEqual(
            arguments.amended_from_failed_intake_directory,
            Path("failed-v0170"),
        )

    @patch("lane_residuals.cli.independent_outing_intake.run_independent_outing_intake")
    def test_cli_returns_success_and_insufficient_statuses(self, run) -> None:
        summary = {
            "mcap_file_count": 7,
            "declared_new_outing_count": 7,
            "eligible_new_outing_count": 7,
            "status": "locked",
        }
        for workflow_status in (0, 3):
            with self.subTest(workflow_status=workflow_status):
                run.reset_mock()
                run.return_value = (summary, workflow_status)
                status = main(
                    [
                        "new-root",
                        "--acquisition-manifest",
                        "manifest.json",
                        "--output-directory",
                        "output",
                    ]
                )
                self.assertEqual(status, workflow_status)
                run.assert_called_once()

    @patch(
        "lane_residuals.cli.independent_outing_intake.run_independent_outing_intake",
        side_effect=ValueError("strict contract failure"),
    )
    def test_cli_usage_failure_returns_two(self, run) -> None:
        status = main(
            [
                "new-root",
                "--acquisition-manifest",
                "manifest.json",
                "--output-directory",
                "output",
                "--log-level",
                "ERROR",
            ]
        )
        self.assertEqual(status, 2)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
