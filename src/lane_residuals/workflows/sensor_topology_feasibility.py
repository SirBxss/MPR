"""Lineage-locked orchestration for the v0.18.1 structural feasibility audit."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from ..domain.independent_outing_intake import (
    AcquisitionManifest,
    outing_fingerprint_sha256,
    parse_acquisition_manifest,
)
from ..domain.sensor_topology_feasibility import (
    MAXIMUM_CHAIN_SEGMENTS,
    MAXIMUM_JUNCTION_GAP_M,
    MAXIMUM_JUNCTION_HEADING_DEG,
    MAXIMUM_MEDIAN_WIDTH_M,
    MINIMUM_CHAIN_SPAN_M,
    MINIMUM_MEDIAN_WIDTH_M,
)
from ..io.sensor_topology_feasibility import (
    DESCRIPTOR_IDENTITY_RULE,
    REFERENCE_TOPIC,
    SENSOR_TOPIC,
    RecordingInspection,
    SchemaInventoryItem,
)

VERSION = "0.18.1"
CONTRACT_REVISION = "v0.18.1-review-candidate-2026-09-17-reference-uint64-a1"
PRESERVED_CONTRACT_REVISION = "v0.17.1-reviewed-2026-09-07-schema-v2-a1"
PRESERVED_FAILED_CONTRACT_REVISION = "v0.17.0-reviewed-2026-09-03-layout-c1"
PURPOSE = "sensor_topology_100m_structural_feasibility"
OUTPUT_NAMES = (
    "sensor_topology_recordings.csv",
    "sensor_topology_schema_inventory.json",
    "sensor_topology_feasibility_summary.json",
)
PRESERVED_OUTPUT_NAMES = (
    "independent_outing_recordings.csv",
    "independent_outings.csv",
    "independent_outing_lock.json",
    "independent_outing_intake_summary.json",
)
RECORDING_FIELDS = (
    "relative_path_private",
    "basename_private",
    "file_size_bytes",
    "file_sha256",
    "sensor_topic_present",
    "reference_topic_present",
    "sensor_message_count",
    "reference_message_count",
    "sensor_decoded_count",
    "reference_decoded_count",
    "sensor_descriptor_file_sha256s",
    "reference_descriptor_file_sha256s",
    "sensor_source_timestamp_valid_count",
    "reference_source_timestamp_valid_count",
    "sensor_source_timestamps_strict",
    "reference_source_timestamps_strict",
    "explicit_ego_candidate_count",
    "camera_boundary_segment_structure_count",
    "camera_only_successor_chain_count",
    "camera_chain_100m_span_count",
    "reference_h100_ready_count",
    "source_time_pair_count",
    "synchronized_100m_candidate_count",
    "failure_codes",
)

_OLD_RECORDING_FIELDS = (
    "recording_id", "outing_id", "private_outing_label", "mcap_basename_private",
    "relative_path_private", "file_size_bytes", "sha256", "raw_readable", "raw_empty",
    "duplicate_of_recording_id", "raw_usable", "chronological_index_within_outing",
    "internal_start_log_time_ns_private", "internal_end_log_time_ns_private",
    "first_estimate_source_time_ns_private", "last_estimate_source_time_ns_private",
    "estimate_source_duration_s", "estimate_source_timestamp_count",
    "estimate_missing_source_timestamp_count", "estimate_source_timestamps_strictly_increasing",
    "required_topic_schema_compatible", "estimate_topic_present", "estimate_topic_message_count",
    "estimate_topic_schema_compatible", "map_topic_present", "map_topic_message_count",
    "map_topic_schema_compatible", "odometry_topic_present", "odometry_topic_message_count",
    "odometry_topic_schema_compatible", "decoded_estimate_message_count", "decoded_map_message_count",
    "topology_gate_candidate_count", "sensor_topology_candidate_count",
    "lane_map_topology_candidate_count", "unknown_or_other_topology_candidate_count",
    "h100_geometry_ready_count", "h100_eligible_frame_count", "sequence_count_touching_recording",
    "boundary_to_previous_stitchable", "eligible_sequence_stitched_to_previous",
    "failure_codes", "boundary_codes",
)
_OLD_OUTING_FIELDS = (
    "outing_id", "private_outing_label", "acquisition_start_utc_private",
    "separate_physical_session_declared", "independence_basis_private", "recording_count",
    "raw_usable_recording_count", "summed_usable_duration_s",
    "usable_intervals_monotonic_nonoverlapping", "topology_gate_candidate_count",
    "non_sensor_topology_candidate_count", "eligible_frame_count", "sequence_count",
    "retained_eligible_frame_count", "has_raw_usable_recording", "usable_duration_gate_passes",
    "topology_gate_passes", "eligible_frame_count_gate_passes", "sequence_integrity_passes",
    "technically_eligible", "outing_fingerprint_sha256", "split_score_sha256", "split_rank",
    "cohort_role", "failure_codes",
)
_OLD_LOCK_FIELDS = frozenset(
    {
        "version", "purpose", "contract_revision", "status", "manifest",
        "legacy_development_outing_count", "raw_file_sha256_by_basename_private",
        "private_to_opaque_outing_id", "outings", "eligibility_rules", "availability_gate",
        "split_contract", "split_assignments_authorized", "role_counts", "attestations",
        "prior_successful_lock", "final_outing_embargo", "schema_compatibility_amendment",
    }
)
_OLD_SUMMARY_FIELDS = frozenset(
    {
        "version", "purpose", "status", "contract_revision", "manifest_sha256",
        "mcap_file_count", "declared_new_outing_count", "eligible_new_outing_count",
        "ineligible_new_outing_count", "legacy_development_outing_count",
        "total_independent_outing_count_including_legacy", "raw_usable_recording_count",
        "summed_usable_duration_s", "eligible_h100_frame_count", "eligible_sequence_count",
        "availability_gate", "final_count", "role_counts",
        "failure_code_counts_non_mutually_exclusive", "attestation_status",
        "prior_successful_lock_sha256", "prior_successful_lock_verified",
        "overlapping_raw_sha256_count", "output_sha256", "summary_self_hash_recorded",
        "claim_limits", "next_authorized_action", "schema_compatibility_amendment",
    }
)
_OLD_LOCK_OUTING_FIELDS = frozenset(
    {
        "outing_id", "private_outing_label", "acquisition_start_utc_private",
        "mcap_sha256_by_basename_private", "outing_fingerprint_sha256", "technically_eligible",
        "raw_usable_recording_count", "summed_usable_duration_ns", "eligible_frame_count",
        "sequence_count", "split_score_sha256", "split_rank", "cohort_role",
    }
)
_OLD_SCHEMA_AMENDMENT_FIELDS = frozenset(
    {
        "amendment_id",
        "descriptor_identity_source",
        "allowed_flag_absent_estimate_file_descriptor_sha256",
        "legacy_estimate_file_descriptor_reference_sha256",
        "legacy_validity_rule",
        "observed_estimate_file_descriptor_sha256",
        "amended_from_failed_audit",
    }
)
_OLD_LEGACY_VALIDITY_RULE = {
    "descriptor_rule": "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist",
    "field_name": "model_parameters_optional_flag",
    "field_number": 8,
    "protobuf_type": "bool",
    "explicit_presence_required": True,
    "required_value": True,
}
_OLD_ELIGIBILITY_RULES = {
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
}
_OLD_SPLIT_CONTRACT_BASE = {
    "salt_ascii": "MPR-v0.17-final-split-v1",
    "fingerprint_encoding": "sorted lowercase raw SHA-256 ASCII plus LF; repeated entries retained",
    "score_encoding": "salt ASCII plus NUL plus outing fingerprint ASCII",
    "final_count_formula": "max(2, ceil((E + 1) / 5))",
    "opaque_id_order": "ascending outing fingerprint bytes",
    "role_order": "ascending split-score bytes then fingerprint bytes",
}
_OLD_ALLOWED_EMBARGO_EVIDENCE = [
    "immutable_file_and_manifest_hashes",
    "opaque_identity_and_cohort_role",
    "raw_usability_and_fixed_eligibility_counts",
    "fixed_exclusion_and_boundary_codes",
]
_OLD_CLAIM_LIMITS = [
    "availability_and_locked_cohort_roles_only",
    "no_independent_journey_generalization_claim",
    "no_final_selection_or_benefit_claim",
    "rlmb_remains_a_pseudo_reference",
]
_OLD_INITIAL_PRIOR = {
    "declared_sha256": None,
    "supplied": False,
    "verified": False,
    "overlapping_raw_sha256_count": 0,
    "superseding_contract_amendment_id": None,
}
_OLD_AMENDMENT_ID = "v0.17.1-edp-schema-v2-2026-09-07"
_OLD_ALLOWED_FLAG_ABSENT_DESCRIPTOR = (
    "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
)
_OLD_LEGACY_DESCRIPTOR = (
    "f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f"
)
CLAIM_LIMITS = (
    "structural_feasibility_only",
    "rlmb_is_pseudo_reference_not_ground_truth",
    "ltsb_boundary_geometry_is_camera_derived_but_topology_is_map_influenced",
    "ltsb_centreline_is_consumer_derived_not_producer_defined",
    "physical_frame_equivalence_not_established",
    "no_cross_topic_geometry_alignment_or_h100_residual_pair",
    "no_residual_condition_sequence_model_planner_or_figure",
    "no_cohort_role_or_independent_outing_generalization",
)

RecordingInspector = Callable[[Path], RecordingInspection]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    raw = path.read_bytes()

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path.name}: {key}")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid strict JSON: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload, raw


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise ValueError(
            f"{name} schema differs: missing={sorted(fields - actual)}, extra={sorted(actual - fields)}"
        )
    return value


def _typed_json_equal(actual: Any, expected: Any) -> bool:
    """Compare decoded JSON without accepting Boolean/integer equivalence."""

    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(_typed_json_equal(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_typed_json_equal(left, right) for left, right in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def _lowercase_sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"historical CSV schema differs: {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"historical CSV row shape differs: {path.name}")
    return rows


def _discover(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise ValueError(f"MCAP root is not a directory: {root}")
    result: dict[str, Path] = {}
    duplicates: set[str] = set()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file() and item.suffix.lower() == ".mcap"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.name in result:
            duplicates.add(path.name)
        result[path.name] = path
    if duplicates:
        raise ValueError(f"MCAP basenames are not unique: {sorted(duplicates)}")
    if not result:
        raise ValueError("MCAP root contains no .mcap files")
    return result


def _raw_map_hash(raw_hashes: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for basename in sorted(raw_hashes):
        digest.update(basename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw_hashes[basename].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _validate_preserved_intake(
    directory: Path,
    *,
    manifest: AcquisitionManifest,
    manifest_sha256: str,
    raw_hashes: Mapping[str, str],
) -> dict[str, str]:
    if not directory.is_dir():
        raise ValueError(f"preserved intake directory is not a directory: {directory}")
    children = tuple(directory.iterdir())
    names = {item.name for item in children}
    if names != set(PRESERVED_OUTPUT_NAMES) or any(not item.is_file() for item in children):
        raise ValueError(
            "preserved intake file set differs: "
            f"missing={sorted(set(PRESERVED_OUTPUT_NAMES) - names)}, "
            f"extra={sorted(names - set(PRESERVED_OUTPUT_NAMES))}"
        )
    lock, lock_bytes = _strict_json(directory / PRESERVED_OUTPUT_NAMES[2])
    summary, _ = _strict_json(directory / PRESERVED_OUTPUT_NAMES[3])
    _exact(lock, _OLD_LOCK_FIELDS, "preserved v0.17.1 lock")
    _exact(summary, _OLD_SUMMARY_FIELDS, "preserved v0.17.1 summary")
    lock_manifest = _exact(
        lock.get("manifest"),
        frozenset({"version", "purpose", "sha256"}),
        "preserved manifest evidence",
    )
    lock_availability = _exact(
        lock.get("availability_gate"),
        frozenset(
            {
                "minimum_eligible_new_outing_count",
                "eligible_new_outing_count",
                "total_independent_outing_count_including_legacy",
                "passed",
            }
        ),
        "preserved lock availability gate",
    )
    summary_availability = _exact(
        summary.get("availability_gate"),
        frozenset({"minimum_eligible_new_outing_count", "passed"}),
        "preserved summary availability gate",
    )
    split_contract = _exact(
        lock.get("split_contract"),
        frozenset(set(_OLD_SPLIT_CONTRACT_BASE) | {"final_count"}),
        "preserved split contract",
    )
    prior = _exact(
        lock.get("prior_successful_lock"),
        frozenset(_OLD_INITIAL_PRIOR),
        "preserved prior-lock evidence",
    )
    attestations = _exact(
        lock.get("attestations"),
        frozenset(
            {
                "verification_status",
                "acquisition_batch_closed",
                "created_before_outcome_inspection",
                "null_prior_successful_lock_declared",
                "outings",
            }
        ),
        "preserved attestations",
    )
    embargo = _exact(
        lock.get("final_outing_embargo"),
        frozenset({"active", "allowed_evidence", "embargoed_numeric_evidence"}),
        "preserved final-outing embargo",
    )
    lock_outings = lock.get("outings")
    if not isinstance(lock_outings, list) or len(lock_outings) != len(manifest.outings):
        raise ValueError("preserved intake lock outing coverage differs from the manifest")
    manifest_by_label = {item.private_outing_label: item for item in manifest.outings}
    if (
        lock.get("version") != "0.17.0"
        or summary.get("version") != "0.17.0"
        or lock.get("purpose") != "independent_outing_intake_and_cohort_lock"
        or summary.get("purpose") != "independent_outing_intake_and_cohort_lock"
        or lock.get("contract_revision") != PRESERVED_CONTRACT_REVISION
        or summary.get("contract_revision") != PRESERVED_CONTRACT_REVISION
        or lock.get("status") != "insufficient_independent_outings"
        or summary.get("status") != "insufficient_independent_outings"
        or lock.get("split_assignments_authorized") is not False
        or not _typed_json_equal(lock.get("eligibility_rules"), _OLD_ELIGIBILITY_RULES)
        or not all(
            _typed_json_equal(split_contract[key], value)
            for key, value in _OLD_SPLIT_CONTRACT_BASE.items()
        )
        or split_contract.get("final_count") is not None
        or summary.get("final_count") is not None
        or lock.get("legacy_development_outing_count") != 1
        or summary.get("legacy_development_outing_count") != 1
        or summary.get("mcap_file_count") != len(raw_hashes)
        or summary.get("declared_new_outing_count") != len(manifest.outings)
        or summary.get("eligible_new_outing_count") != 0
        or summary.get("ineligible_new_outing_count") != len(manifest.outings)
        or summary.get("total_independent_outing_count_including_legacy") != 1
        or not _typed_json_equal(prior, _OLD_INITIAL_PRIOR)
        or summary.get("prior_successful_lock_sha256") is not None
        or summary.get("prior_successful_lock_verified") is not False
        or summary.get("overlapping_raw_sha256_count") != 0
        or summary.get("summary_self_hash_recorded") is not False
        or summary.get("attestation_status") != "declared_not_independently_verified"
        or not _typed_json_equal(summary.get("claim_limits"), _OLD_CLAIM_LIMITS)
        or summary.get("next_authorized_action")
        != "retain_this_audit_and_acquire_more_outcome_blind_data"
        or lock_manifest.get("sha256") != manifest_sha256
        or lock_manifest.get("version") != "0.17"
        or lock_manifest.get("purpose") != "prospective_independent_outing_intake"
        or summary.get("manifest_sha256") != manifest_sha256
    ):
        raise ValueError("preserved directory is not the reviewed negative v0.17.1 intake")
    expected_roles = {"unassigned": len(lock_outings)}
    if lock.get("role_counts") != expected_roles or summary.get("role_counts") != expected_roles:
        raise ValueError("preserved role counts do not reconcile")
    expected_lock_availability = {
        "minimum_eligible_new_outing_count": 7,
        "eligible_new_outing_count": 0,
        "total_independent_outing_count_including_legacy": 1,
        "passed": False,
    }
    if not _typed_json_equal(lock_availability, expected_lock_availability) or not _typed_json_equal(
        summary_availability,
        {"minimum_eligible_new_outing_count": 7, "passed": False},
    ):
        raise ValueError("preserved availability gate does not reconcile")
    if not _typed_json_equal(
        embargo,
        {
            "active": False,
            "allowed_evidence": _OLD_ALLOWED_EMBARGO_EVIDENCE,
            "embargoed_numeric_evidence": True,
        },
    ):
        raise ValueError("preserved final-outing embargo differs")
    if (
        attestations.get("verification_status") != "declared_not_independently_verified"
        or attestations.get("acquisition_batch_closed") is not True
        or attestations.get("created_before_outcome_inspection") is not True
        or attestations.get("null_prior_successful_lock_declared") is not True
    ):
        raise ValueError("preserved batch attestations differ")
    preserved_map = lock.get("raw_file_sha256_by_basename_private")
    if not isinstance(preserved_map, Mapping) or dict(preserved_map) != dict(raw_hashes):
        raise ValueError("preserved raw basename/SHA-256 map differs")
    for basename, digest in preserved_map.items():
        _lowercase_sha256(digest, f"preserved raw hash for {basename}")

    lock_by_label: dict[str, Mapping[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    for index, raw_outing in enumerate(lock_outings):
        outing = _exact(raw_outing, _OLD_LOCK_OUTING_FIELDS, f"preserved outing {index}")
        label = outing.get("private_outing_label")
        if not isinstance(label, str) or label not in manifest_by_label or label in lock_by_label:
            raise ValueError("preserved outing labels do not reconcile with the manifest")
        expected_basenames = set(manifest_by_label[label].mcap_basenames_private)
        local = outing.get("mcap_sha256_by_basename_private")
        if not isinstance(local, Mapping) or set(local) != expected_basenames or any(
            local[basename] != raw_hashes[basename] for basename in expected_basenames
        ):
            raise ValueError("preserved outing raw-file map differs from the manifest")
        fingerprint = outing_fingerprint_sha256(tuple(local.values()))
        if outing.get("outing_fingerprint_sha256") != fingerprint:
            raise ValueError("preserved content-only outing fingerprint differs")
        if (
            outing.get("acquisition_start_utc_private")
            != manifest_by_label[label].acquisition_start_utc
            or outing.get("technically_eligible") is not False
            or any(
                outing.get(field) is not None
                for field in ("split_score_sha256", "split_rank", "cohort_role")
            )
            or any(
                type(outing.get(field)) is not int or outing[field] < 0
                for field in (
                    "raw_usable_recording_count",
                    "summed_usable_duration_ns",
                    "eligible_frame_count",
                    "sequence_count",
                )
            )
        ):
            raise ValueError("preserved outing state differs from the negative intake")
        lock_by_label[label] = outing
        fingerprints[label] = fingerprint
    expected_ids = {
        label: f"outing_{position:03d}"
        for position, label in enumerate(
            sorted(fingerprints, key=lambda value: bytes.fromhex(fingerprints[value])),
            1,
        )
    }
    private_to_opaque = lock.get("private_to_opaque_outing_id")
    if not isinstance(private_to_opaque, Mapping) or dict(private_to_opaque) != expected_ids:
        raise ValueError("preserved private-to-opaque outing map differs")
    if any(lock_by_label[label].get("outing_id") != expected_ids[label] for label in expected_ids):
        raise ValueError("preserved lock outing IDs differ")

    raw_attestations = attestations.get("outings")
    if not isinstance(raw_attestations, list) or len(raw_attestations) != len(expected_ids):
        raise ValueError("preserved outing attestations do not reconcile")
    attestation_ids: set[str] = set()
    for index, raw_attestation in enumerate(raw_attestations):
        attestation = _exact(
            raw_attestation,
            frozenset({"outing_id", "separate_physical_session", "independence_basis_private"}),
            f"preserved outing attestation {index}",
        )
        outing_id = attestation.get("outing_id")
        labels = [label for label, expected_id in expected_ids.items() if expected_id == outing_id]
        if len(labels) != 1 or outing_id in attestation_ids:
            raise ValueError("preserved outing attestation identity differs")
        label = labels[0]
        if (
            attestation.get("separate_physical_session") is not True
            or attestation.get("independence_basis_private")
            != manifest_by_label[label].independence_basis_private
        ):
            raise ValueError("preserved outing attestation content differs")
        attestation_ids.add(str(outing_id))

    recordings = _read_csv(directory / PRESERVED_OUTPUT_NAMES[0], _OLD_RECORDING_FIELDS)
    outings_csv = _read_csv(directory / PRESERVED_OUTPUT_NAMES[1], _OLD_OUTING_FIELDS)
    csv_map: dict[str, str] = {}
    for row in recordings:
        basename = row["mcap_basename_private"]
        if basename in csv_map:
            raise ValueError("preserved recordings CSV contains a duplicate basename")
        label = row["private_outing_label"]
        relative = PurePosixPath(row["relative_path_private"])
        if (
            basename not in raw_hashes
            or label != manifest.basename_to_private_label[basename]
            or row["outing_id"] != expected_ids[label]
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.name != basename
        ):
            raise ValueError("preserved recordings CSV lineage differs")
        csv_map[basename] = row["sha256"]
    if len(csv_map) != len(recordings) or csv_map != dict(raw_hashes):
        raise ValueError("preserved recordings CSV raw map differs")
    csv_outings: dict[str, dict[str, str]] = {}
    for row in outings_csv:
        label = row["private_outing_label"]
        if label in csv_outings or label not in lock_by_label:
            raise ValueError("preserved outings CSV labels differ")
        if (
            row["outing_id"] != expected_ids[label]
            or row["acquisition_start_utc_private"]
            != manifest_by_label[label].acquisition_start_utc
            or row["outing_fingerprint_sha256"] != fingerprints[label]
            or row["split_score_sha256"]
            or row["split_rank"]
            or row["cohort_role"]
        ):
            raise ValueError("preserved outings CSV contains a cohort assignment or lineage mismatch")
        csv_outings[label] = row
    if len(csv_outings) != len(lock_outings):
        raise ValueError("preserved outings CSV contains a cohort assignment")
    output_hashes = {name: _sha256(directory / name) for name in PRESERVED_OUTPUT_NAMES}
    sibling = summary.get("output_sha256")
    if not isinstance(sibling, Mapping) or set(sibling) != set(PRESERVED_OUTPUT_NAMES[:3]) or any(
        sibling.get(name) != output_hashes[name] for name in PRESERVED_OUTPUT_NAMES[:3]
    ):
        raise ValueError("preserved sibling output hashes do not reconcile")
    amendment = _exact(
        lock.get("schema_compatibility_amendment"),
        _OLD_SCHEMA_AMENDMENT_FIELDS,
        "preserved schema compatibility amendment",
    )
    summary_amendment = summary.get("schema_compatibility_amendment")
    if not _typed_json_equal(amendment, summary_amendment):
        raise ValueError("preserved schema amendment does not reconcile")
    if (
        amendment.get("amendment_id") != _OLD_AMENDMENT_ID
        or amendment.get("descriptor_identity_source") != DESCRIPTOR_IDENTITY_RULE
        or amendment.get("allowed_flag_absent_estimate_file_descriptor_sha256")
        != _OLD_ALLOWED_FLAG_ABSENT_DESCRIPTOR
        or amendment.get("legacy_estimate_file_descriptor_reference_sha256")
        != _OLD_LEGACY_DESCRIPTOR
        or not _typed_json_equal(amendment.get("legacy_validity_rule"), _OLD_LEGACY_VALIDITY_RULE)
    ):
        raise ValueError("preserved schema amendment constants differ")
    observed = amendment.get("observed_estimate_file_descriptor_sha256")
    if not isinstance(observed, list):
        raise ValueError("preserved observed descriptor identities must be an array")
    observed_validated = [
        _lowercase_sha256(value, "preserved observed descriptor identity")
        for value in observed
    ]
    if observed_validated != sorted(set(observed_validated)):
        raise ValueError("preserved observed descriptor identities are not sorted and unique")
    failed_lineage = _exact(
        amendment.get("amended_from_failed_audit"),
        frozenset({"contract_revision", "manifest_sha256", "output_sha256"}),
        "preserved failed-audit lineage",
    )
    failed_hashes = failed_lineage.get("output_sha256")
    if (
        failed_lineage.get("contract_revision") != PRESERVED_FAILED_CONTRACT_REVISION
        or failed_lineage.get("manifest_sha256") != manifest_sha256
        or not isinstance(failed_hashes, Mapping)
        or set(failed_hashes) != set(PRESERVED_OUTPUT_NAMES)
    ):
        raise ValueError("preserved failed-audit lineage differs")
    for name, digest in failed_hashes.items():
        _lowercase_sha256(digest, f"preserved failed-audit hash for {name}")
    return {
        "contract_revision": PRESERVED_CONTRACT_REVISION,
        "lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
    }


def _csv_scalar(value: object) -> object:
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, tuple):
        return ";".join(str(item) for item in value)
    return value


def _merge_inventory(items: Sequence[SchemaInventoryItem]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str | None, str], list[SchemaInventoryItem]] = {}
    for item in items:
        grouped.setdefault((item.topic, item.descriptor_file_sha256, item.audit_support_status), []).append(item)
    result: list[dict[str, object]] = []
    for key in sorted(grouped, key=lambda value: (value[0], value[1] is None, value[1] or "", value[2])):
        group = grouped[key]
        inventories = {json.dumps(item.field_inventory, sort_keys=True) for item in group}
        roots = {item.root_message_full_name for item in group}
        if len(inventories) != 1 or len(roots) != 1:
            raise ValueError("one descriptor identity produced inconsistent inventory")
        result.append(
            {
                "topic": key[0],
                "message_count": sum(item.message_count for item in group),
                "mcap_schema_names": sorted({value for item in group for value in item.mcap_schema_names}),
                "mcap_schema_encodings": sorted({value for item in group for value in item.mcap_schema_encodings}),
                "message_encodings": sorted({value for item in group for value in item.message_encodings}),
                "descriptor_file_sha256": key[1],
                "root_message_full_name": next(iter(roots)),
                "field_inventory": [dict(value) for value in group[0].field_inventory],
                "audit_support_status": key[2],
            }
        )
    return result


def run_sensor_topology_feasibility(
    mcap_root: Path,
    *,
    acquisition_manifest: Path,
    preserved_intake_directory: Path,
    output_directory: Path,
    recording_inspector: RecordingInspector | None = None,
) -> int:
    """Validate immutable lineage, audit each recording, and write three files."""

    root = mcap_root.expanduser().resolve()
    manifest_path = acquisition_manifest.expanduser().resolve()
    preserved = preserved_intake_directory.expanduser().resolve()
    target = output_directory.expanduser().resolve()
    if target.exists():
        raise ValueError(f"output directory must not already exist: {output_directory}")
    manifest_payload, manifest_bytes = _strict_json(manifest_path)
    manifest = parse_acquisition_manifest(manifest_payload)
    files = _discover(root)
    expected = set(manifest.basename_to_private_label)
    if set(files) != expected:
        raise ValueError(
            "manifest does not exactly cover recursive MCAP root: "
            f"missing={sorted(expected - set(files))}, extra={sorted(set(files) - expected)}"
        )
    raw_hashes = {basename: _sha256(files[basename]) for basename in sorted(files)}
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    lineage = _validate_preserved_intake(
        preserved,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        raw_hashes=raw_hashes,
    )
    if recording_inspector is None:
        from ..io.sensor_topology_feasibility import inspect_mcap_recording

        recording_inspector = inspect_mcap_recording

    rows: list[dict[str, object]] = []
    inspections: list[RecordingInspection] = []
    inventory_items: list[SchemaInventoryItem] = []
    for basename in sorted(files):
        path = files[basename]
        inspection = recording_inspector(path)
        inspections.append(inspection)
        inventory_items.extend(inspection.schema_inventory)
        rows.append(
            {
                "relative_path_private": path.relative_to(root).as_posix(),
                "basename_private": basename,
                "file_size_bytes": path.stat().st_size,
                "file_sha256": raw_hashes[basename],
                **{
                    field: _csv_scalar(getattr(inspection, field))
                    for field in RECORDING_FIELDS[4:]
                },
            }
        )

    schema_inventory = {
        "version": VERSION,
        "contract_revision": CONTRACT_REVISION,
        "purpose": "sensor_topology_schema_inventory",
        "descriptor_identity_rule": DESCRIPTOR_IDENTITY_RULE,
        "topics": _merge_inventory(inventory_items),
    }
    failure_counts = Counter(
        code for inspection in inspections for code in inspection.failure_codes
    )
    totals = {
        field: sum(int(getattr(item, field)) for item in inspections)
        for field in (
            "sensor_message_count", "reference_message_count", "sensor_decoded_count",
            "reference_decoded_count", "explicit_ego_candidate_count",
            "camera_boundary_segment_structure_count", "camera_only_successor_chain_count",
            "camera_chain_100m_span_count", "reference_h100_ready_count",
            "source_time_pair_count", "synchronized_100m_candidate_count",
        )
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        recordings_path = temporary / OUTPUT_NAMES[0]
        with recordings_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RECORDING_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        inventory_path = temporary / OUTPUT_NAMES[1]
        inventory_path.write_text(
            json.dumps(schema_inventory, indent=2, sort_keys=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        synchronized = totals["synchronized_100m_candidate_count"]
        summary = {
            "version": VERSION,
            "contract_revision": CONTRACT_REVISION,
            "purpose": PURPOSE,
            "lineage_status": "passed",
            "preserved_intake_contract_revision": lineage["contract_revision"],
            "preserved_intake_lock_sha256": lineage["lock_sha256"],
            "manifest_sha256": manifest_sha256,
            "raw_mcap_count": len(files),
            "raw_basename_sha256_map_sha256": _raw_map_hash(raw_hashes),
            "topics": {"estimate": SENSOR_TOPIC, "reference": REFERENCE_TOPIC},
            "minimum_sensor_chain_span_m": MINIMUM_CHAIN_SPAN_M,
            "maximum_source_delta_ms": 50.0,
            "sensor_chain_limits": {
                "max_segments": MAXIMUM_CHAIN_SEGMENTS,
                "maximum_junction_gap_m": MAXIMUM_JUNCTION_GAP_M,
                "maximum_junction_heading_deg": MAXIMUM_JUNCTION_HEADING_DEG,
                "minimum_median_width_m": MINIMUM_MEDIAN_WIDTH_M,
                "maximum_median_width_m": MAXIMUM_MEDIAN_WIDTH_M,
            },
            "reference_chain_limits": {
                "max_segments": MAXIMUM_CHAIN_SEGMENTS,
                "maximum_junction_gap_m": MAXIMUM_JUNCTION_GAP_M,
                "maximum_junction_heading_deg": MAXIMUM_JUNCTION_HEADING_DEG,
            },
            "sensor_descriptor_file_sha256s": sorted(
                {value for item in inspections for value in item.sensor_descriptor_file_sha256s}
            ),
            "reference_descriptor_file_sha256s": sorted(
                {value for item in inspections for value in item.reference_descriptor_file_sha256s}
            ),
            **totals,
            "recording_failure_counts": dict(sorted(failure_counts.items())),
            "output_sha256": {
                OUTPUT_NAMES[0]: _sha256(recordings_path),
                OUTPUT_NAMES[1]: _sha256(inventory_path),
            },
            "technical_feasibility_status": (
                "synchronized_100m_candidates_observed"
                if synchronized > 0
                else "no_synchronized_100m_candidates"
            ),
            "producer_provenance_status": "source_traced_frame_contract_unresolved",
            "scientific_target_adoption_authorized": False,
            "claim_limits": list(CLAIM_LIMITS),
            "next_authorized_action": (
                "resolve_physical_frame_contract_and_predeclare_alignment_audit"
                if synchronized > 0
                else "retain_negative_audit_and_review_schema_or_acquisition_configuration"
            ),
        }
        (temporary / OUTPUT_NAMES[2]).write_text(
            json.dumps(summary, indent=2, sort_keys=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if target.exists():
            raise ValueError(f"output directory appeared during audit: {output_directory}")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return 0 if totals["synchronized_100m_candidate_count"] > 0 else 3
