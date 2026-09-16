from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from lane_residuals.cli.sensor_topology_feasibility import main
from lane_residuals.domain.independent_outing_intake import outing_fingerprint_sha256
from lane_residuals.io.sensor_topology_feasibility import RecordingInspection
from lane_residuals.workflows.sensor_topology_feasibility import (
    CONTRACT_REVISION,
    OUTPUT_NAMES,
    PRESERVED_CONTRACT_REVISION,
    RECORDING_FIELDS,
    _OLD_LOCK_FIELDS,
    _OLD_LOCK_OUTING_FIELDS,
    _OLD_OUTING_FIELDS,
    _OLD_RECORDING_FIELDS,
    _OLD_SUMMARY_FIELDS,
    run_sensor_topology_feasibility,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, fields: tuple[str, ...], row: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def _manifest(path: Path, basename: str) -> bytes:
    payload = {
        "version": "0.17",
        "purpose": "prospective_independent_outing_intake",
        "acquisition_batch_closed": True,
        "created_before_outcome_inspection": True,
        "legacy_development_outing_count": 1,
        "prior_successful_lock_sha256": None,
        "superseding_contract_amendment_id": None,
        "outings": [
            {
                "private_outing_label": "closed_batch01",
                "acquisition_start_utc": "2025-08-21T14:37:46+00:00",
                "separate_physical_session": True,
                "independence_basis_private": "synthetic test declaration",
                "mcap_basenames_private": [basename],
            }
        ],
    }
    raw = json.dumps(payload, indent=2).encode() + b"\n"
    path.write_bytes(raw)
    return raw


def _preserved(directory: Path, *, basename: str, raw_sha: str, manifest_sha: str) -> None:
    directory.mkdir()
    fingerprint = outing_fingerprint_sha256((raw_sha,))
    _write_csv(
        directory / "independent_outing_recordings.csv",
        _OLD_RECORDING_FIELDS,
        {
            "recording_id": "recording_001",
            "outing_id": "outing_001",
            "private_outing_label": "closed_batch01",
            "mcap_basename_private": basename,
            "relative_path_private": basename,
            "sha256": raw_sha,
        },
    )
    _write_csv(
        directory / "independent_outings.csv",
        _OLD_OUTING_FIELDS,
        {
            "outing_id": "outing_001",
            "private_outing_label": "closed_batch01",
            "acquisition_start_utc_private": "2025-08-21T14:37:46+00:00",
            "outing_fingerprint_sha256": fingerprint,
            "split_score_sha256": "",
            "split_rank": "",
            "cohort_role": "",
        },
    )
    amendment = {
        "amendment_id": "v0.17.1-edp-schema-v2-2026-09-07",
        "descriptor_identity_source": "sha256(message.DESCRIPTOR.file.serialized_pb)",
        "allowed_flag_absent_estimate_file_descriptor_sha256": (
            "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
        ),
        "legacy_estimate_file_descriptor_reference_sha256": (
            "f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f"
        ),
        "legacy_validity_rule": {
            "descriptor_rule": "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist",
            "field_name": "model_parameters_optional_flag",
            "field_number": 8,
            "protobuf_type": "bool",
            "explicit_presence_required": True,
            "required_value": True,
        },
        "observed_estimate_file_descriptor_sha256": [
            "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
        ],
        "amended_from_failed_audit": {
            "contract_revision": "v0.17.0-reviewed-2026-09-03-layout-c1",
            "manifest_sha256": manifest_sha,
            "output_sha256": {
                "independent_outing_recordings.csv": "1" * 64,
                "independent_outings.csv": "2" * 64,
                "independent_outing_lock.json": "3" * 64,
                "independent_outing_intake_summary.json": "4" * 64,
            },
        },
    }
    outing = {field: None for field in _OLD_LOCK_OUTING_FIELDS}
    outing.update(
        {
            "outing_id": "outing_001",
            "private_outing_label": "closed_batch01",
            "acquisition_start_utc_private": "2025-08-21T14:37:46+00:00",
            "mcap_sha256_by_basename_private": {basename: raw_sha},
            "outing_fingerprint_sha256": fingerprint,
            "technically_eligible": False,
            "raw_usable_recording_count": 1,
            "summed_usable_duration_ns": 0,
            "eligible_frame_count": 0,
            "sequence_count": 0,
        }
    )
    lock = {field: None for field in _OLD_LOCK_FIELDS}
    lock.update(
        {
            "version": "0.17.0",
            "purpose": "independent_outing_intake_and_cohort_lock",
            "contract_revision": PRESERVED_CONTRACT_REVISION,
            "status": "insufficient_independent_outings",
            "manifest": {
                "version": "0.17",
                "purpose": "prospective_independent_outing_intake",
                "sha256": manifest_sha,
            },
            "legacy_development_outing_count": 1,
            "raw_file_sha256_by_basename_private": {basename: raw_sha},
            "private_to_opaque_outing_id": {"closed_batch01": "outing_001"},
            "outings": [outing],
            "eligibility_rules": {
                "minimum_raw_usable_recording_count": 1,
                "minimum_summed_nonoverlapping_usable_duration_s": 120.0,
                "usable_source_intervals_must_be_strictly_monotonic_nonoverlapping": True,
                "required_topology_source": "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
                "maximum_anchor_distance_m_inclusive": 1.0,
                "minimum_eligible_h100_frame_count": 500,
                "maximum_sequence_gap_ms": 200.0,
                "odometry_speed_interval_ms": 50.0,
                "maximum_odometry_interpolation_gap_ms": 50.0,
                "maximum_spline_step_m": 0.25,
                "map_maximum_segments": 16,
                "map_maximum_junction_gap_m": 1.0,
                "map_maximum_junction_heading_deg": 29.999999999999996,
                "numeric_frame_values_exported": False,
            },
            "availability_gate": {
                "minimum_eligible_new_outing_count": 7,
                "eligible_new_outing_count": 0,
                "total_independent_outing_count_including_legacy": 1,
                "passed": False,
            },
            "split_contract": {
                "salt_ascii": "MPR-v0.17-final-split-v1",
                "fingerprint_encoding": "sorted lowercase raw SHA-256 ASCII plus LF; repeated entries retained",
                "score_encoding": "salt ASCII plus NUL plus outing fingerprint ASCII",
                "final_count_formula": "max(2, ceil((E + 1) / 5))",
                "final_count": None,
                "opaque_id_order": "ascending outing fingerprint bytes",
                "role_order": "ascending split-score bytes then fingerprint bytes",
            },
            "split_assignments_authorized": False,
            "role_counts": {"unassigned": 1},
            "attestations": {
                "verification_status": "declared_not_independently_verified",
                "acquisition_batch_closed": True,
                "created_before_outcome_inspection": True,
                "null_prior_successful_lock_declared": True,
                "outings": [
                    {
                        "outing_id": "outing_001",
                        "separate_physical_session": True,
                        "independence_basis_private": "synthetic test declaration",
                    }
                ],
            },
            "prior_successful_lock": {
                "declared_sha256": None,
                "supplied": False,
                "verified": False,
                "overlapping_raw_sha256_count": 0,
                "superseding_contract_amendment_id": None,
            },
            "final_outing_embargo": {
                "active": False,
                "allowed_evidence": [
                    "immutable_file_and_manifest_hashes",
                    "opaque_identity_and_cohort_role",
                    "raw_usability_and_fixed_eligibility_counts",
                    "fixed_exclusion_and_boundary_codes",
                ],
                "embargoed_numeric_evidence": True,
            },
            "schema_compatibility_amendment": amendment,
        }
    )
    _write_json(directory / "independent_outing_lock.json", lock)
    summary = {field: None for field in _OLD_SUMMARY_FIELDS}
    summary.update(
        {
            "version": "0.17.0",
            "purpose": "independent_outing_intake_and_cohort_lock",
            "contract_revision": PRESERVED_CONTRACT_REVISION,
            "status": "insufficient_independent_outings",
            "manifest_sha256": manifest_sha,
            "mcap_file_count": 1,
            "declared_new_outing_count": 1,
            "eligible_new_outing_count": 0,
            "ineligible_new_outing_count": 1,
            "legacy_development_outing_count": 1,
            "total_independent_outing_count_including_legacy": 1,
            "availability_gate": {
                "minimum_eligible_new_outing_count": 7,
                "passed": False,
            },
            "final_count": None,
            "role_counts": {"unassigned": 1},
            "attestation_status": "declared_not_independently_verified",
            "prior_successful_lock_sha256": None,
            "prior_successful_lock_verified": False,
            "overlapping_raw_sha256_count": 0,
            "summary_self_hash_recorded": False,
            "claim_limits": [
                "availability_and_locked_cohort_roles_only",
                "no_independent_journey_generalization_claim",
                "no_final_selection_or_benefit_claim",
                "rlmb_remains_a_pseudo_reference",
            ],
            "next_authorized_action": "retain_this_audit_and_acquire_more_outcome_blind_data",
            "schema_compatibility_amendment": amendment,
            "output_sha256": {
                name: _digest(directory / name)
                for name in (
                    "independent_outing_recordings.csv",
                    "independent_outings.csv",
                    "independent_outing_lock.json",
                )
            },
        }
    )
    _write_json(directory / "independent_outing_intake_summary.json", summary)


def _inspection(*, synchronized: int = 0) -> RecordingInspection:
    return RecordingInspection(
        sensor_topic_present=True,
        reference_topic_present=True,
        sensor_message_count=2,
        reference_message_count=2,
        sensor_decoded_count=2,
        reference_decoded_count=2,
        sensor_descriptor_file_sha256s=("a" * 64,),
        reference_descriptor_file_sha256s=("b" * 64,),
        sensor_source_timestamp_valid_count=2,
        reference_source_timestamp_valid_count=2,
        sensor_source_timestamps_strict=True,
        reference_source_timestamps_strict=True,
        explicit_ego_candidate_count=2,
        camera_boundary_segment_structure_count=2,
        camera_only_successor_chain_count=2,
        camera_chain_100m_span_count=1,
        reference_h100_ready_count=1,
        source_time_pair_count=2,
        synchronized_100m_candidate_count=synchronized,
        failure_codes=(() if synchronized else ("source_time_pair_unavailable",)),
        schema_inventory=(),
    )


class SensorTopologyWorkflowTests(unittest.TestCase):
    def _fixture(self, root: Path):
        corpus = root / "corpus"
        corpus.mkdir()
        raw = corpus / "chunk_0001.mcap"
        raw.write_bytes(b"synthetic-not-a-real-mcap")
        manifest = root / "manifest.json"
        manifest_raw = _manifest(manifest, raw.name)
        preserved = root / "preserved"
        _preserved(
            preserved,
            basename=raw.name,
            raw_sha=_digest(raw),
            manifest_sha=hashlib.sha256(manifest_raw).hexdigest(),
        )
        return corpus, manifest, preserved

    def test_complete_negative_audit_writes_exact_three_file_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, preserved = self._fixture(root)
            output = root / "output"
            status = run_sensor_topology_feasibility(
                corpus,
                acquisition_manifest=manifest,
                preserved_intake_directory=preserved,
                output_directory=output,
                recording_inspector=lambda _: _inspection(),
            )
            self.assertEqual(status, 3)
            self.assertEqual({path.name for path in output.iterdir()}, set(OUTPUT_NAMES))
            with (output / OUTPUT_NAMES[0]).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames or ()), RECORDING_FIELDS)
                row = next(reader)
            self.assertEqual(row["sensor_topic_present"], "true")
            summary = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
            self.assertEqual(summary["contract_revision"], CONTRACT_REVISION)
            self.assertEqual(summary["technical_feasibility_status"], "no_synchronized_100m_candidates")
            self.assertFalse(summary["scientific_target_adoption_authorized"])
            self.assertNotIn("coordinates", json.dumps(summary))
            self.assertEqual(
                set(summary),
                {
                    "version", "contract_revision", "purpose", "lineage_status",
                    "preserved_intake_contract_revision", "preserved_intake_lock_sha256",
                    "manifest_sha256", "raw_mcap_count", "raw_basename_sha256_map_sha256",
                    "topics", "minimum_sensor_chain_span_m", "maximum_source_delta_ms",
                    "sensor_chain_limits", "reference_chain_limits",
                    "sensor_descriptor_file_sha256s", "reference_descriptor_file_sha256s",
                    "sensor_message_count", "reference_message_count", "sensor_decoded_count",
                    "reference_decoded_count", "explicit_ego_candidate_count",
                    "camera_boundary_segment_structure_count", "camera_only_successor_chain_count",
                    "camera_chain_100m_span_count", "reference_h100_ready_count",
                    "source_time_pair_count", "synchronized_100m_candidate_count",
                    "recording_failure_counts", "output_sha256", "technical_feasibility_status",
                    "producer_provenance_status", "scientific_target_adoption_authorized",
                    "claim_limits", "next_authorized_action",
                },
            )

    def test_positive_audit_only_authorizes_frame_contract_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, preserved = self._fixture(root)
            output = root / "output"
            status = run_sensor_topology_feasibility(
                corpus,
                acquisition_manifest=manifest,
                preserved_intake_directory=preserved,
                output_directory=output,
                recording_inspector=lambda _: _inspection(synchronized=1),
            )
            self.assertEqual(status, 0)
            summary = json.loads((output / OUTPUT_NAMES[2]).read_text(encoding="utf-8"))
            self.assertEqual(
                summary["next_authorized_action"],
                "resolve_physical_frame_contract_and_predeclare_alignment_audit",
            )
            self.assertFalse(summary["scientific_target_adoption_authorized"])

    def test_lineage_tampering_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, preserved = self._fixture(root)
            with (preserved / "independent_outing_recordings.csv").open("a", encoding="utf-8") as handle:
                handle.write("tamper\n")
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "CSV row shape differs|hashes do not reconcile"):
                run_sensor_topology_feasibility(
                    corpus,
                    acquisition_manifest=manifest,
                    preserved_intake_directory=preserved,
                    output_directory=output,
                    recording_inspector=lambda _: _inspection(),
                )
            self.assertFalse(output.exists())

    def test_nested_lineage_tampering_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, preserved = self._fixture(root)
            lock_path = preserved / "independent_outing_lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["split_contract"]["score_encoding"] = "tampered"
            _write_json(lock_path, lock)
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "reviewed negative v0.17.1 intake"):
                run_sensor_topology_feasibility(
                    corpus,
                    acquisition_manifest=manifest,
                    preserved_intake_directory=preserved,
                    output_directory=output,
                    recording_inspector=lambda _: _inspection(),
                )
            self.assertFalse(output.exists())

    def test_injected_unknown_failure_code_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not contract-defined"):
            replace(_inspection(), failure_codes=("unreviewed_failure",))

    def test_nonoverwrite_and_deterministic_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, manifest, preserved = self._fixture(root)
            first = root / "first"
            second = root / "second"
            arguments = {
                "acquisition_manifest": manifest,
                "preserved_intake_directory": preserved,
                "recording_inspector": lambda _: _inspection(),
            }
            run_sensor_topology_feasibility(corpus, output_directory=first, **arguments)
            run_sensor_topology_feasibility(corpus, output_directory=second, **arguments)
            self.assertEqual(
                {name: (first / name).read_bytes() for name in OUTPUT_NAMES},
                {name: (second / name).read_bytes() for name in OUTPUT_NAMES},
            )
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                run_sensor_topology_feasibility(corpus, output_directory=first, **arguments)

    def test_cli_maps_usage_error_to_two(self) -> None:
        with patch(
            "lane_residuals.cli.sensor_topology_feasibility.run_sensor_topology_feasibility",
            side_effect=ValueError("synthetic lineage failure"),
        ):
            status = main(
                [
                    "raw",
                    "--acquisition-manifest", "manifest.json",
                    "--preserved-intake-directory", "preserved",
                    "--output-directory", "output",
                ]
            )
        self.assertEqual(status, 2)

    def test_cli_import_graph_excludes_prohibited_layers_transitively(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        code = (
            "import json, sys\n"
            "import lane_residuals.cli.sensor_topology_feasibility\n"
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
        loaded = json.loads(completed.stdout)
        forbidden = (
            "residual", "condition", "sequence", "model", "sampling", "planner",
            "evaluation", "visualization", "plotting", "legacy.preprocessing",
        )
        offending = []
        for name in loaded:
            components = name.split(".")[1:]
            if any(any(token in component for token in forbidden) for component in components):
                offending.append(name)
        self.assertFalse(offending, loaded)
        self.assertEqual(
            loaded,
            [
                "lane_residuals",
                "lane_residuals.cli",
                "lane_residuals.cli.sensor_topology_feasibility",
                "lane_residuals.domain",
                "lane_residuals.domain.independent_outing_intake",
                "lane_residuals.domain.sensor_topology_feasibility",
                "lane_residuals.io",
                "lane_residuals.io.sensor_topology_feasibility",
                "lane_residuals.workflows",
                "lane_residuals.workflows.sensor_topology_feasibility",
            ],
        )


if __name__ == "__main__":
    unittest.main()
