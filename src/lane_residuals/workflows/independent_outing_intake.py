"""Transactional v0.17 independent-outing intake and cohort lock."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..domain.corpus_inventory import (
    McapInventoryRecord,
    chronological_records,
    continuity_edges,
)
from ..domain.independent_outing_intake import (
    CONTRACT_REVISION,
    EXPECTED_TOPOLOGY_SOURCE,
    MANIFEST_PURPOSE,
    MANIFEST_VERSION,
    MAXIMUM_ANCHOR_DISTANCE_M,
    MAXIMUM_SEQUENCE_GAP_NS,
    MINIMUM_ELIGIBLE_FRAME_COUNT,
    MINIMUM_ELIGIBLE_NEW_OUTING_COUNT,
    MINIMUM_USABLE_DURATION_NS,
    ODOMETRY_INTERPOLATION_GAP_NS,
    PURPOSE,
    SPLIT_SALT,
    VERSION,
    AcquisitionManifest,
    CohortAssignment,
    FrameTechnicalEvidence,
    ManifestOuting,
    OutingEligibility,
    OutingEligibilityEvidence,
    RecordingTechnicalEvidence,
    assign_cohorts,
    evaluate_outing_eligibility,
    outing_fingerprint_sha256,
    parse_acquisition_manifest,
)
from ..domain.path_source_probe import (
    ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
    ESTIMATE_DESCRIPTOR_IDENTITY_SOURCE,
    LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
)
from ..io.corpus_inventory import inspect_mcap_for_inventory, sha256_file
from ..io.independent_outing_intake import (
    MAP_MAXIMUM_JUNCTION_GAP_M,
    MAP_MAXIMUM_JUNCTION_HEADING_RAD,
    MAP_MAXIMUM_SEGMENTS,
    MAXIMUM_SPLINE_STEP_M,
    discover_mcaps,
    inspect_recording_technical_evidence,
    read_strict_json_with_bytes,
)
from ..io.reports import write_csv_rows, write_strict_json


RECORDING_FIELDS = (
    "recording_id",
    "outing_id",
    "private_outing_label",
    "mcap_basename_private",
    "relative_path_private",
    "file_size_bytes",
    "sha256",
    "raw_readable",
    "raw_empty",
    "duplicate_of_recording_id",
    "raw_usable",
    "chronological_index_within_outing",
    "internal_start_log_time_ns_private",
    "internal_end_log_time_ns_private",
    "first_estimate_source_time_ns_private",
    "last_estimate_source_time_ns_private",
    "estimate_source_duration_s",
    "estimate_source_timestamp_count",
    "estimate_missing_source_timestamp_count",
    "estimate_source_timestamps_strictly_increasing",
    "required_topic_schema_compatible",
    "estimate_topic_present",
    "estimate_topic_message_count",
    "estimate_topic_schema_compatible",
    "map_topic_present",
    "map_topic_message_count",
    "map_topic_schema_compatible",
    "odometry_topic_present",
    "odometry_topic_message_count",
    "odometry_topic_schema_compatible",
    "decoded_estimate_message_count",
    "decoded_map_message_count",
    "topology_gate_candidate_count",
    "sensor_topology_candidate_count",
    "lane_map_topology_candidate_count",
    "unknown_or_other_topology_candidate_count",
    "h100_geometry_ready_count",
    "h100_eligible_frame_count",
    "sequence_count_touching_recording",
    "boundary_to_previous_stitchable",
    "eligible_sequence_stitched_to_previous",
    "failure_codes",
    "boundary_codes",
)

OUTING_FIELDS = (
    "outing_id",
    "private_outing_label",
    "acquisition_start_utc_private",
    "separate_physical_session_declared",
    "independence_basis_private",
    "recording_count",
    "raw_usable_recording_count",
    "summed_usable_duration_s",
    "usable_intervals_monotonic_nonoverlapping",
    "topology_gate_candidate_count",
    "non_sensor_topology_candidate_count",
    "eligible_frame_count",
    "sequence_count",
    "retained_eligible_frame_count",
    "has_raw_usable_recording",
    "usable_duration_gate_passes",
    "topology_gate_passes",
    "eligible_frame_count_gate_passes",
    "sequence_integrity_passes",
    "technically_eligible",
    "outing_fingerprint_sha256",
    "split_score_sha256",
    "split_rank",
    "cohort_role",
    "failure_codes",
)

OUTPUT_NAMES = (
    "independent_outing_recordings.csv",
    "independent_outings.csv",
    "independent_outing_lock.json",
    "independent_outing_intake_summary.json",
)

SCHEMA_COMPATIBILITY_AMENDMENT_ID = "v0.17.1-edp-schema-v2-2026-09-07"
LEGACY_FAILED_AUDIT_CONTRACT_REVISION = (
    "v0.17.0-reviewed-2026-09-03-layout-c1"
)
SCHEMA_COMPATIBILITY_FIELD = "schema_compatibility_amendment"

LOCK_TOP_LEVEL_FIELDS = frozenset(
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
        SCHEMA_COMPATIBILITY_FIELD,
    }
)

SUMMARY_TOP_LEVEL_FIELDS = frozenset(
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
        SCHEMA_COMPATIBILITY_FIELD,
    }
)

_LEGACY_FAILED_LOCK_FIELDS = LOCK_TOP_LEVEL_FIELDS - {
    SCHEMA_COMPATIBILITY_FIELD
}
_LEGACY_FAILED_SUMMARY_FIELDS = SUMMARY_TOP_LEVEL_FIELDS - {
    SCHEMA_COMPATIBILITY_FIELD
}
_LOCK_OUTING_FIELDS = frozenset(
    {
        "outing_id",
        "private_outing_label",
        "acquisition_start_utc_private",
        "mcap_sha256_by_basename_private",
        "outing_fingerprint_sha256",
        "technically_eligible",
        "raw_usable_recording_count",
        "summed_usable_duration_ns",
        "eligible_frame_count",
        "sequence_count",
        "split_score_sha256",
        "split_rank",
        "cohort_role",
    }
)
_SCHEMA_AMENDMENT_FIELDS = frozenset(
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
_LEGACY_VALIDITY_RULE = {
    "descriptor_rule": (
        "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist"
    ),
    "field_name": "model_parameters_optional_flag",
    "field_number": 8,
    "protobuf_type": "bool",
    "explicit_presence_required": True,
    "required_value": True,
}


@dataclass(frozen=True)
class _SequenceAudit:
    sequence_count: int
    retained_eligible_frame_count: int
    sequence_ids_by_recording: Mapping[str, tuple[int, ...]]
    stitched_to_previous_by_recording: Mapping[str, bool]


@dataclass(frozen=True)
class _OutingResult:
    manifest: ManifestOuting
    assignment: CohortAssignment
    records: tuple[McapInventoryRecord, ...]
    technical_by_recording: Mapping[str, RecordingTechnicalEvidence]
    eligibility: OutingEligibility
    evidence: OutingEligibilityEvidence
    sequence_audit: _SequenceAudit


InventoryInspector = Callable[..., McapInventoryRecord]
TechnicalInspector = Callable[..., RecordingTechnicalEvidence]


def _validate_output_target(path: Path) -> Path:
    target = path.expanduser().resolve()
    if target.exists():
        raise ValueError(f"output directory must not already exist: {path}")
    return target


def _validate_exact_coverage(
    files: Sequence[Path], manifest: AcquisitionManifest
) -> dict[str, Path]:
    by_basename: dict[str, Path] = {}
    duplicates: set[str] = set()
    for path in files:
        if path.name in by_basename:
            duplicates.add(path.name)
        by_basename[path.name] = path
    if duplicates:
        raise ValueError(f"discovered MCAP basenames are not unique: {sorted(duplicates)}")
    expected = set(manifest.basename_to_private_label)
    actual = set(by_basename)
    if actual != expected:
        raise ValueError(
            "manifest does not exactly cover discovered MCAPs: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return by_basename


def _hash_files(files_by_basename: Mapping[str, Path]) -> dict[str, str]:
    return {
        basename: sha256_file(files_by_basename[basename])
        for basename in sorted(files_by_basename)
    }


def _exact_mapping_fields(
    value: Any,
    expected: frozenset[str],
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{name} schema differs: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _read_exact_csv(
    path: Path,
    expected_fields: tuple[str, ...],
) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"required failed-audit CSV is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise ValueError(f"failed-audit CSV schema differs: {path.name}")
        rows = list(reader)
    if any(
        None in row or any(value is None for value in row.values())
        for row in rows
    ):
        raise ValueError(f"failed-audit CSV row shape differs: {path.name}")
    return rows


def _validate_failed_audit_directory(
    *,
    supplied_directory: Path | None,
    manifest: AcquisitionManifest,
    manifest_sha256: str,
    current_hashes: Mapping[str, str],
) -> dict[str, Any] | None:
    """Reconcile one immutable failed v0.17.0 audit before any output write."""

    if supplied_directory is None:
        return None
    if manifest.prior_successful_lock_sha256 is not None:
        raise ValueError(
            "--amended-from-failed-intake-directory is forbidden when the "
            "manifest declares a prior successful lock"
        )
    source = supplied_directory.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"failed-audit directory is not a directory: {source}")
    children = tuple(source.iterdir())
    actual_names = {item.name for item in children}
    if actual_names != set(OUTPUT_NAMES) or any(not item.is_file() for item in children):
        raise ValueError(
            "failed-audit file set differs: "
            f"missing={sorted(set(OUTPUT_NAMES) - actual_names)}, "
            f"extra={sorted(actual_names - set(OUTPUT_NAMES))}"
        )

    lock_payload, _ = read_strict_json_with_bytes(source / OUTPUT_NAMES[2])
    summary_payload, _ = read_strict_json_with_bytes(source / OUTPUT_NAMES[3])
    lock = _exact_mapping_fields(
        lock_payload,
        _LEGACY_FAILED_LOCK_FIELDS,
        "failed-audit lock",
    )
    summary = _exact_mapping_fields(
        summary_payload,
        _LEGACY_FAILED_SUMMARY_FIELDS,
        "failed-audit summary",
    )

    nested_fields = (
        (lock.get("manifest"), frozenset({"version", "purpose", "sha256"}), "lock manifest"),
        (
            lock.get("availability_gate"),
            frozenset(
                {
                    "minimum_eligible_new_outing_count",
                    "eligible_new_outing_count",
                    "total_independent_outing_count_including_legacy",
                    "passed",
                }
            ),
            "lock availability gate",
        ),
        (
            summary.get("availability_gate"),
            frozenset({"minimum_eligible_new_outing_count", "passed"}),
            "summary availability gate",
        ),
        (
            lock.get("prior_successful_lock"),
            frozenset(
                {
                    "declared_sha256",
                    "supplied",
                    "verified",
                    "overlapping_raw_sha256_count",
                    "superseding_contract_amendment_id",
                }
            ),
            "lock prior-successful-lock evidence",
        ),
        (
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
            "lock attestations",
        ),
        (
            lock.get("final_outing_embargo"),
            frozenset({"active", "allowed_evidence", "embargoed_numeric_evidence"}),
            "lock final-outing embargo",
        ),
    )
    for value, expected, name in nested_fields:
        _exact_mapping_fields(value, expected, f"failed-audit {name}")

    split_contract = _exact_mapping_fields(
        lock.get("split_contract"),
        frozenset(
            {
                "salt_ascii",
                "fingerprint_encoding",
                "score_encoding",
                "final_count_formula",
                "final_count",
                "opaque_id_order",
                "role_order",
            }
        ),
        "failed-audit split contract",
    )
    old_outings = lock.get("outings")
    if not isinstance(old_outings, list) or not old_outings:
        raise ValueError("failed-audit lock outings are missing")
    for index, raw_outing in enumerate(old_outings):
        outing = _exact_mapping_fields(
            raw_outing,
            _LOCK_OUTING_FIELDS,
            f"failed-audit lock outings[{index}]",
        )
        if any(
            outing.get(field) is not None
            for field in ("split_score_sha256", "split_rank", "cohort_role")
        ):
            raise ValueError("failed audit contains an assigned cohort role")

    attestations = lock["attestations"]
    raw_attestation_outings = attestations["outings"]
    if not isinstance(raw_attestation_outings, list):
        raise ValueError("failed-audit outing attestations must be an array")
    for index, raw_attestation in enumerate(raw_attestation_outings):
        _exact_mapping_fields(
            raw_attestation,
            frozenset(
                {"outing_id", "separate_physical_session", "independence_basis_private"}
            ),
            f"failed-audit attestations.outings[{index}]",
        )

    lock_manifest = lock["manifest"]
    initial_prior = lock["prior_successful_lock"]
    expected_initial_prior = {
        "declared_sha256": None,
        "supplied": False,
        "verified": False,
        "overlapping_raw_sha256_count": 0,
        "superseding_contract_amendment_id": None,
    }
    if (
        lock.get("version") != VERSION
        or summary.get("version") != VERSION
        or lock.get("purpose") != PURPOSE
        or summary.get("purpose") != PURPOSE
        or lock.get("contract_revision") != LEGACY_FAILED_AUDIT_CONTRACT_REVISION
        or summary.get("contract_revision") != LEGACY_FAILED_AUDIT_CONTRACT_REVISION
        or lock.get("status") != "insufficient_independent_outings"
        or summary.get("status") != "insufficient_independent_outings"
        or lock.get("split_assignments_authorized") is not False
        or split_contract.get("final_count") is not None
        or summary.get("final_count") is not None
        or lock.get("role_counts") != {"unassigned": len(old_outings)}
        or summary.get("role_counts") != {"unassigned": len(old_outings)}
        or dict(initial_prior) != expected_initial_prior
        or summary.get("prior_successful_lock_sha256") is not None
        or summary.get("prior_successful_lock_verified") is not False
        or summary.get("overlapping_raw_sha256_count") != 0
        or lock_manifest.get("version") != MANIFEST_VERSION
        or lock_manifest.get("purpose") != MANIFEST_PURPOSE
        or lock_manifest.get("sha256") != manifest_sha256
        or summary.get("manifest_sha256") != manifest_sha256
    ):
        raise ValueError("supplied directory is not a reconciled failed v0.17.0 audit")

    old_raw_map = _strict_prior_raw_map(lock)
    if old_raw_map != dict(current_hashes):
        raise ValueError("failed-audit raw-file hash map differs from current corpus")

    recordings = _read_exact_csv(source / OUTPUT_NAMES[0], RECORDING_FIELDS)
    outings_csv = _read_exact_csv(source / OUTPUT_NAMES[1], OUTING_FIELDS)
    recording_raw_map: dict[str, str] = {}
    for row in recordings:
        basename = row["mcap_basename_private"]
        digest = row["sha256"]
        if basename in recording_raw_map:
            raise ValueError("failed-audit recordings contain a duplicate basename")
        recording_raw_map[basename] = digest
    if recording_raw_map != dict(current_hashes):
        raise ValueError("failed-audit recording CSV differs from current corpus")
    if len(outings_csv) != len(old_outings) or any(
        row["split_score_sha256"]
        or row["split_rank"]
        or row["cohort_role"]
        for row in outings_csv
    ):
        raise ValueError("failed-audit outing CSV contains a cohort assignment")

    output_hashes = {
        name: sha256_file(source / name) for name in OUTPUT_NAMES
    }
    old_sibling_hashes = summary.get("output_sha256")
    if (
        not isinstance(old_sibling_hashes, Mapping)
        or set(old_sibling_hashes) != set(OUTPUT_NAMES[:3])
        or any(
            old_sibling_hashes.get(name) != output_hashes[name]
            for name in OUTPUT_NAMES[:3]
        )
    ):
        raise ValueError("failed-audit sibling output hashes do not reconcile")

    return {
        "contract_revision": LEGACY_FAILED_AUDIT_CONTRACT_REVISION,
        "manifest_sha256": manifest_sha256,
        "output_sha256": dict(sorted(output_hashes.items())),
    }


def _schema_compatibility_amendment(
    *,
    observed_descriptor_hashes: Sequence[str],
    amended_from_failed_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed = tuple(sorted(set(observed_descriptor_hashes)))
    for digest in observed:
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("observed estimate descriptor identity is invalid")
    payload = {
        "amendment_id": SCHEMA_COMPATIBILITY_AMENDMENT_ID,
        "descriptor_identity_source": ESTIMATE_DESCRIPTOR_IDENTITY_SOURCE,
        "allowed_flag_absent_estimate_file_descriptor_sha256": (
            ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256
        ),
        "legacy_estimate_file_descriptor_reference_sha256": (
            LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256
        ),
        "legacy_validity_rule": dict(_LEGACY_VALIDITY_RULE),
        "observed_estimate_file_descriptor_sha256": list(observed),
        "amended_from_failed_audit": (
            None
            if amended_from_failed_audit is None
            else dict(amended_from_failed_audit)
        ),
    }
    if set(payload) != _SCHEMA_AMENDMENT_FIELDS:
        raise AssertionError("schema-compatibility amendment shape changed")
    return payload


def _manifest_fingerprints(
    manifest: AcquisitionManifest,
    hashes_by_basename: Mapping[str, str],
) -> dict[str, str]:
    return {
        outing.private_outing_label: outing_fingerprint_sha256(
            [hashes_by_basename[name] for name in outing.mcap_basenames_private]
        )
        for outing in manifest.outings
    }


def _strict_prior_raw_map(payload: Mapping[str, Any]) -> dict[str, str]:
    raw = payload.get("raw_file_sha256_by_basename_private")
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("prior successful lock raw-file hash map is missing")
    result: dict[str, str] = {}
    for basename, digest in raw.items():
        if (
            not isinstance(basename, str)
            or not basename
            or basename != basename.replace("\\", "/").split("/")[-1]
        ):
            raise ValueError("prior successful lock contains an invalid basename")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("prior successful lock contains an invalid raw SHA-256")
        result[basename] = digest
    outings = payload.get("outings")
    if not isinstance(outings, list) or not outings:
        raise ValueError("prior successful lock outing records are missing")
    identity_map = payload.get("private_to_opaque_outing_id")
    if (
        not isinstance(identity_map, Mapping)
        or not identity_map
        or any(
            not isinstance(label, str) or not isinstance(outing_id, str)
            for label, outing_id in identity_map.items()
        )
    ):
        raise ValueError("prior successful lock identity map is missing")
    reconstructed: dict[str, str] = {}
    outing_ids: set[str] = set()
    outing_fingerprints: set[str] = set()
    private_labels: set[str] = set()
    for outing in outings:
        if not isinstance(outing, Mapping):
            raise ValueError("prior successful lock outing record is invalid")
        outing_id = outing.get("outing_id")
        private_label = outing.get("private_outing_label")
        outing_suffix = (
            outing_id.removeprefix("outing_")
            if isinstance(outing_id, str) and outing_id.startswith("outing_")
            else ""
        )
        if (
            not isinstance(outing_id, str)
            or not outing_id.startswith("outing_")
            or len(outing_suffix) < 3
            or not outing_suffix.isdigit()
            or outing_suffix != f"{int(outing_suffix):03d}"
            or int(outing_suffix) < 1
            or outing_id in outing_ids
            or not isinstance(private_label, str)
            or not private_label
            or private_label in private_labels
            or identity_map.get(private_label) != outing_id
        ):
            raise ValueError("prior successful lock outing identity is invalid")
        local = outing.get("mcap_sha256_by_basename_private")
        if not isinstance(local, Mapping) or not local:
            raise ValueError("prior successful lock outing raw-file map is missing")
        local_digests: list[str] = []
        for basename, digest in local.items():
            if (
                not isinstance(basename, str)
                or not basename
                or basename != basename.replace("\\", "/").split("/")[-1]
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or basename in reconstructed
                or result.get(basename) != digest
            ):
                raise ValueError("prior successful lock raw-file maps do not reconcile")
            reconstructed[basename] = digest
            local_digests.append(digest)
        fingerprint = outing.get("outing_fingerprint_sha256")
        if (
            not isinstance(fingerprint, str)
            or fingerprint != outing_fingerprint_sha256(local_digests)
            or fingerprint in outing_fingerprints
        ):
            raise ValueError("prior successful lock outing fingerprint is invalid")
        outing_ids.add(outing_id)
        outing_fingerprints.add(fingerprint)
        private_labels.add(private_label)
    if reconstructed != result:
        raise ValueError("prior successful lock raw-file map coverage is inconsistent")
    if set(identity_map) != private_labels or set(identity_map.values()) != outing_ids:
        raise ValueError("prior successful lock identity map does not reconcile")
    return result


def _validate_prior_lock(
    *,
    manifest: AcquisitionManifest,
    supplied_path: Path | None,
    current_hashes: Mapping[str, str],
) -> dict[str, Any]:
    if manifest.prior_successful_lock_sha256 is None:
        if supplied_path is not None:
            raise ValueError("--prior-successful-lock is forbidden for an initial lock")
        return {
            "declared_sha256": None,
            "supplied": False,
            "verified": False,
            "overlapping_raw_sha256_count": 0,
            "superseding_contract_amendment_id": None,
        }
    if supplied_path is None:
        raise ValueError("--prior-successful-lock is required by the manifest")
    payload, raw = read_strict_json_with_bytes(supplied_path)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.prior_successful_lock_sha256:
        raise ValueError("prior successful lock SHA-256 does not match the manifest")
    if not isinstance(payload, Mapping):
        raise ValueError("prior successful lock must be a JSON object")
    prior_revision = payload.get("contract_revision")
    expected_fields = (
        LOCK_TOP_LEVEL_FIELDS
        if prior_revision == CONTRACT_REVISION
        else _LEGACY_FAILED_LOCK_FIELDS
        if prior_revision == LEGACY_FAILED_AUDIT_CONTRACT_REVISION
        else frozenset()
    )
    if not expected_fields or set(payload) != expected_fields:
        raise ValueError("prior successful lock top-level schema differs")
    availability_gate = payload.get("availability_gate")
    manifest_evidence = payload.get("manifest")
    embargo = payload.get("final_outing_embargo")
    if (
        payload.get("version") != VERSION
        or payload.get("purpose") != PURPOSE
        or prior_revision
        not in {CONTRACT_REVISION, LEGACY_FAILED_AUDIT_CONTRACT_REVISION}
        or payload.get("status") != "locked"
        or type(payload.get("legacy_development_outing_count")) is not int
        or payload["legacy_development_outing_count"] != 1
        or not isinstance(availability_gate, Mapping)
        or availability_gate.get("passed") is not True
        or type(availability_gate.get("eligible_new_outing_count")) is not int
        or availability_gate["eligible_new_outing_count"]
        < MINIMUM_ELIGIBLE_NEW_OUTING_COUNT
        or not isinstance(manifest_evidence, Mapping)
        or manifest_evidence.get("version") != MANIFEST_VERSION
        or manifest_evidence.get("purpose") != MANIFEST_PURPOSE
        or not isinstance(manifest_evidence.get("sha256"), str)
        or len(manifest_evidence["sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in manifest_evidence["sha256"]
        )
        or payload.get("split_assignments_authorized") is not True
        or not isinstance(embargo, Mapping)
        or embargo.get("active") is not True
    ):
        raise ValueError("prior successful lock is not a successful v0.17 lock")
    prior_map = _strict_prior_raw_map(payload)
    overlap = len(set(prior_map.values()).intersection(current_hashes.values()))
    if overlap < 1:
        raise ValueError(
            "prior successful lock has no overlapping raw content; use a separate study/version"
        )
    return {
        "declared_sha256": digest,
        "supplied": True,
        "verified": True,
        "overlapping_raw_sha256_count": overlap,
        "superseding_contract_amendment_id": (
            manifest.superseding_contract_amendment_id
        ),
    }


def _assign_content_duplicates(
    records: Sequence[McapInventoryRecord],
    fingerprint_by_outing_id: Mapping[str, str],
) -> tuple[McapInventoryRecord, ...]:
    """Mark later duplicates without letting labels, paths, or timestamps choose outings."""

    by_hash: dict[str, list[McapInventoryRecord]] = defaultdict(list)
    for record in records:
        if record.sha256 is not None:
            by_hash[record.sha256].append(record)
    duplicate_of: dict[str, str] = {}
    for group in by_hash.values():
        if len(group) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda item: (
                fingerprint_by_outing_id.get(item.drive_id or "", ""),
                item.basename,
                item.relative_path,
            ),
        )
        first = ordered[0].recording_id
        for record in ordered[1:]:
            duplicate_of[record.recording_id] = first
    return tuple(
        replace(record, duplicate_of_recording_id=duplicate_of.get(record.recording_id))
        for record in records
    )


def _topic(record: McapInventoryRecord, role: str) -> Any:
    return next(item for item in record.topics if item.role == role)


def _build_sequences(
    records: Sequence[McapInventoryRecord],
    technical_by_recording: Mapping[str, RecordingTechnicalEvidence],
    edge_by_right_recording: Mapping[str, Any],
) -> _SequenceAudit:
    sequence_count = 0
    retained = 0
    active_sequence: int | None = None
    previous_frame: FrameTechnicalEvidence | None = None
    previous_recording_id: str | None = None
    sequence_ids: dict[str, set[int]] = defaultdict(set)
    stitched: dict[str, bool] = {record.recording_id: False for record in records}

    for record in records:
        frames = technical_by_recording[record.recording_id].frames
        if not frames:
            active_sequence = None
            previous_frame = None
            previous_recording_id = None
            continue
        for frame in frames:
            crosses = (
                previous_recording_id is not None
                and previous_recording_id != record.recording_id
            )
            gap_ok = bool(
                previous_frame is not None
                and previous_frame.source_time_ns is not None
                and frame.source_time_ns is not None
                and 0 < frame.source_time_ns - previous_frame.source_time_ns <= MAXIMUM_SEQUENCE_GAP_NS
            )
            boundary_ok = True
            if crosses:
                edge = edge_by_right_recording.get(record.recording_id)
                boundary_ok = edge is not None and edge.stitchable
            continuation = bool(
                active_sequence is not None
                and previous_frame is not None
                and previous_frame.eligible
                and frame.eligible
                and gap_ok
                and boundary_ok
            )
            if frame.eligible:
                if not continuation:
                    sequence_count += 1
                    active_sequence = sequence_count
                elif crosses:
                    stitched[record.recording_id] = True
                assert active_sequence is not None
                retained += 1
                sequence_ids[record.recording_id].add(active_sequence)
            else:
                active_sequence = None
            previous_frame = frame
            previous_recording_id = record.recording_id
    return _SequenceAudit(
        sequence_count=sequence_count,
        retained_eligible_frame_count=retained,
        sequence_ids_by_recording={
            key: tuple(sorted(value)) for key, value in sequence_ids.items()
        },
        stitched_to_previous_by_recording=stitched,
    )


def _usable_interval_evidence(
    records: Sequence[McapInventoryRecord],
) -> tuple[int, bool]:
    usable = [record for record in records if record.usable]
    duration = sum(record.relevant_duration_ns or 0 for record in usable)
    monotonic = all(
        left.last_estimate_source_time_ns is not None
        and right.first_estimate_source_time_ns is not None
        and right.first_estimate_source_time_ns > left.last_estimate_source_time_ns
        for left, right in zip(usable, usable[1:])
    )
    return duration, monotonic


def _join(values: Sequence[str]) -> str:
    return ";".join(sorted(set(value for value in values if value)))


def _recording_row(
    *,
    record: McapInventoryRecord,
    technical: RecordingTechnicalEvidence,
    private_label: str,
    sequence_audit: _SequenceAudit,
    edge_by_right_recording: Mapping[str, Any],
) -> dict[str, Any]:
    estimate_topic = _topic(record, "estimate")
    map_topic = _topic(record, "map")
    odometry_topic = _topic(record, "odometry")
    sources = Counter(
        frame.topology_source_name
        for frame in technical.frames
        if frame.topology_gate_candidate
    )
    lane_map_count = sum(
        count for name, count in sources.items() if "LANE_MAP" in name
    )
    unknown_count = technical.non_sensor_topology_candidate_count - lane_map_count
    frame_failures = [code for frame in technical.frames for code in frame.failure_codes]
    failures = list(record.failure_codes) + list(technical.failure_codes) + frame_failures
    if record.duplicate_of_recording_id is not None:
        failures.append("duplicate_content")
    edge = edge_by_right_recording.get(record.recording_id)
    boundary_codes = (
        ("outing_start",)
        if edge is None
        else ("accepted_cross_mcap_continuity",)
        if edge.stitchable
        else edge.rejection_codes
    )
    return {
        "recording_id": record.recording_id,
        "outing_id": record.drive_id,
        "private_outing_label": private_label,
        "mcap_basename_private": record.basename,
        "relative_path_private": record.relative_path,
        "file_size_bytes": record.file_size_bytes,
        "sha256": record.sha256,
        "raw_readable": record.readable,
        "raw_empty": record.empty,
        "duplicate_of_recording_id": record.duplicate_of_recording_id,
        "raw_usable": record.usable,
        "chronological_index_within_outing": record.chronological_index_within_drive,
        "internal_start_log_time_ns_private": record.internal_start_log_time_ns,
        "internal_end_log_time_ns_private": record.internal_end_log_time_ns,
        "first_estimate_source_time_ns_private": record.first_estimate_source_time_ns,
        "last_estimate_source_time_ns_private": record.last_estimate_source_time_ns,
        "estimate_source_duration_s": (
            None if record.relevant_duration_ns is None else record.relevant_duration_ns / 1e9
        ),
        "estimate_source_timestamp_count": record.estimate_source_timestamp_count,
        "estimate_missing_source_timestamp_count": record.estimate_missing_source_timestamp_count,
        "estimate_source_timestamps_strictly_increasing": record.estimate_source_timestamps_strictly_increasing,
        "required_topic_schema_compatible": record.required_topics_and_schemas_compatible,
        "estimate_topic_present": estimate_topic.present,
        "estimate_topic_message_count": estimate_topic.message_count,
        "estimate_topic_schema_compatible": estimate_topic.compatible,
        "map_topic_present": map_topic.present,
        "map_topic_message_count": map_topic.message_count,
        "map_topic_schema_compatible": map_topic.compatible,
        "odometry_topic_present": odometry_topic.present,
        "odometry_topic_message_count": odometry_topic.message_count,
        "odometry_topic_schema_compatible": odometry_topic.compatible,
        "decoded_estimate_message_count": technical.estimate_message_count,
        "decoded_map_message_count": technical.map_message_count,
        "topology_gate_candidate_count": technical.topology_candidate_count,
        "sensor_topology_candidate_count": technical.sensor_topology_candidate_count,
        "lane_map_topology_candidate_count": lane_map_count,
        "unknown_or_other_topology_candidate_count": unknown_count,
        "h100_geometry_ready_count": sum(frame.h100_geometry_ready for frame in technical.frames),
        "h100_eligible_frame_count": technical.eligible_frame_count,
        "sequence_count_touching_recording": len(
            sequence_audit.sequence_ids_by_recording.get(record.recording_id, ())
        ),
        "boundary_to_previous_stitchable": None if edge is None else edge.stitchable,
        "eligible_sequence_stitched_to_previous": (
            sequence_audit.stitched_to_previous_by_recording.get(record.recording_id, False)
        ),
        "failure_codes": _join(failures),
        "boundary_codes": _join(boundary_codes),
    }


def _outing_row(result: _OutingResult) -> dict[str, Any]:
    return {
        "outing_id": result.assignment.outing_id,
        "private_outing_label": result.manifest.private_outing_label,
        "acquisition_start_utc_private": result.manifest.acquisition_start_utc,
        "separate_physical_session_declared": result.manifest.separate_physical_session,
        "independence_basis_private": result.manifest.independence_basis_private,
        "recording_count": len(result.records),
        "raw_usable_recording_count": result.evidence.raw_usable_recording_count,
        "summed_usable_duration_s": result.evidence.usable_duration_ns / 1e9,
        "usable_intervals_monotonic_nonoverlapping": result.evidence.usable_intervals_monotonic_nonoverlapping,
        "topology_gate_candidate_count": result.evidence.topology_candidate_count,
        "non_sensor_topology_candidate_count": result.evidence.non_sensor_topology_candidate_count,
        "eligible_frame_count": result.evidence.eligible_frame_count,
        "sequence_count": result.evidence.sequence_count,
        "retained_eligible_frame_count": result.evidence.retained_eligible_frame_count,
        "has_raw_usable_recording": result.eligibility.has_raw_usable_recording,
        "usable_duration_gate_passes": result.eligibility.usable_duration_passes,
        "topology_gate_passes": result.eligibility.topology_passes,
        "eligible_frame_count_gate_passes": result.eligibility.eligible_frame_count_passes,
        "sequence_integrity_passes": result.eligibility.sequence_integrity_passes,
        "technically_eligible": result.eligibility.technically_eligible,
        "outing_fingerprint_sha256": result.assignment.outing_fingerprint_sha256,
        "split_score_sha256": result.assignment.split_score_sha256,
        "split_rank": result.assignment.split_rank,
        "cohort_role": result.assignment.cohort_role,
        "failure_codes": _join(result.eligibility.failure_codes),
    }


def _lock_payload(
    *,
    manifest: AcquisitionManifest,
    manifest_sha256: str,
    hashes_by_basename: Mapping[str, str],
    results: Sequence[_OutingResult],
    availability_passed: bool,
    final_count: int | None,
    prior_evidence: Mapping[str, Any],
    schema_compatibility_amendment: Mapping[str, Any],
) -> dict[str, Any]:
    eligible_count = sum(item.eligibility.technically_eligible for item in results)
    role_counts = Counter(
        item.assignment.cohort_role or "unassigned" for item in results
    )
    return {
        "version": VERSION,
        "purpose": PURPOSE,
        "contract_revision": CONTRACT_REVISION,
        "status": "locked" if availability_passed else "insufficient_independent_outings",
        "manifest": {
            "version": MANIFEST_VERSION,
            "purpose": MANIFEST_PURPOSE,
            "sha256": manifest_sha256,
        },
        "legacy_development_outing_count": manifest.legacy_development_outing_count,
        "raw_file_sha256_by_basename_private": dict(sorted(hashes_by_basename.items())),
        "private_to_opaque_outing_id": {
            item.manifest.private_outing_label: item.assignment.outing_id
            for item in sorted(results, key=lambda value: value.manifest.private_outing_label)
        },
        "outings": [
            {
                "outing_id": item.assignment.outing_id,
                "private_outing_label": item.manifest.private_outing_label,
                "acquisition_start_utc_private": item.manifest.acquisition_start_utc,
                "mcap_sha256_by_basename_private": {
                    name: hashes_by_basename[name]
                    for name in sorted(item.manifest.mcap_basenames_private)
                },
                "outing_fingerprint_sha256": item.assignment.outing_fingerprint_sha256,
                "technically_eligible": item.eligibility.technically_eligible,
                "raw_usable_recording_count": item.evidence.raw_usable_recording_count,
                "summed_usable_duration_ns": item.evidence.usable_duration_ns,
                "eligible_frame_count": item.evidence.eligible_frame_count,
                "sequence_count": item.evidence.sequence_count,
                "split_score_sha256": item.assignment.split_score_sha256,
                "split_rank": item.assignment.split_rank,
                "cohort_role": item.assignment.cohort_role,
            }
            for item in sorted(results, key=lambda value: value.assignment.outing_id)
        ],
        "eligibility_rules": {
            "minimum_raw_usable_recording_count": 1,
            "minimum_summed_nonoverlapping_usable_duration_s": (
                MINIMUM_USABLE_DURATION_NS / 1e9
            ),
            "usable_source_intervals_must_be_strictly_monotonic_nonoverlapping": True,
            "required_topology_source": EXPECTED_TOPOLOGY_SOURCE,
            "maximum_anchor_distance_m_inclusive": MAXIMUM_ANCHOR_DISTANCE_M,
            "minimum_eligible_h100_frame_count": MINIMUM_ELIGIBLE_FRAME_COUNT,
            "maximum_sequence_gap_ms": MAXIMUM_SEQUENCE_GAP_NS / 1e6,
            "odometry_speed_interval_ms": ODOMETRY_INTERPOLATION_GAP_NS / 1e6,
            "maximum_odometry_interpolation_gap_ms": ODOMETRY_INTERPOLATION_GAP_NS / 1e6,
            "maximum_spline_step_m": MAXIMUM_SPLINE_STEP_M,
            "map_maximum_segments": MAP_MAXIMUM_SEGMENTS,
            "map_maximum_junction_gap_m": MAP_MAXIMUM_JUNCTION_GAP_M,
            "map_maximum_junction_heading_deg": math.degrees(
                MAP_MAXIMUM_JUNCTION_HEADING_RAD
            ),
            "numeric_frame_values_exported": False,
        },
        "availability_gate": {
            "minimum_eligible_new_outing_count": MINIMUM_ELIGIBLE_NEW_OUTING_COUNT,
            "eligible_new_outing_count": eligible_count,
            "total_independent_outing_count_including_legacy": (
                eligible_count + manifest.legacy_development_outing_count
            ),
            "passed": availability_passed,
        },
        "split_contract": {
            "salt_ascii": SPLIT_SALT.decode("ascii"),
            "fingerprint_encoding": "sorted lowercase raw SHA-256 ASCII plus LF; repeated entries retained",
            "score_encoding": "salt ASCII plus NUL plus outing fingerprint ASCII",
            "final_count_formula": "max(2, ceil((E + 1) / 5))",
            "final_count": final_count,
            "opaque_id_order": "ascending outing fingerprint bytes",
            "role_order": "ascending split-score bytes then fingerprint bytes",
        },
        "split_assignments_authorized": availability_passed,
        "role_counts": dict(sorted(role_counts.items())),
        "attestations": {
            "verification_status": "declared_not_independently_verified",
            "acquisition_batch_closed": manifest.acquisition_batch_closed,
            "created_before_outcome_inspection": manifest.created_before_outcome_inspection,
            "null_prior_successful_lock_declared": (
                manifest.prior_successful_lock_sha256 is None
            ),
            "outings": [
                {
                    "outing_id": item.assignment.outing_id,
                    "separate_physical_session": item.manifest.separate_physical_session,
                    "independence_basis_private": item.manifest.independence_basis_private,
                }
                for item in sorted(results, key=lambda value: value.assignment.outing_id)
            ],
        },
        "prior_successful_lock": dict(prior_evidence),
        "final_outing_embargo": {
            "active": availability_passed,
            "allowed_evidence": [
                "immutable_file_and_manifest_hashes",
                "opaque_identity_and_cohort_role",
                "raw_usability_and_fixed_eligibility_counts",
                "fixed_exclusion_and_boundary_codes",
            ],
            "embargoed_numeric_evidence": True,
        },
        SCHEMA_COMPATIBILITY_FIELD: dict(schema_compatibility_amendment),
    }


def _summary_payload(
    *,
    manifest: AcquisitionManifest,
    manifest_sha256: str,
    results: Sequence[_OutingResult],
    availability_passed: bool,
    final_count: int | None,
    prior_evidence: Mapping[str, Any],
    output_hashes: Mapping[str, str],
    recording_rows: Sequence[Mapping[str, Any]],
    schema_compatibility_amendment: Mapping[str, Any],
) -> dict[str, Any]:
    eligible_count = sum(item.eligibility.technically_eligible for item in results)
    roles = Counter(item.assignment.cohort_role or "unassigned" for item in results)
    failures: Counter[str] = Counter()
    for row in recording_rows:
        failures.update(code for code in str(row["failure_codes"]).split(";") if code)
        failures.update(
            code
            for code in str(row["boundary_codes"]).split(";")
            if code
            and code not in {"outing_start", "accepted_cross_mcap_continuity"}
        )
    for item in results:
        failures.update(item.eligibility.failure_codes)
    return {
        "version": VERSION,
        "purpose": PURPOSE,
        "status": "locked" if availability_passed else "insufficient_independent_outings",
        "contract_revision": CONTRACT_REVISION,
        "manifest_sha256": manifest_sha256,
        "mcap_file_count": sum(len(item.records) for item in results),
        "declared_new_outing_count": len(results),
        "eligible_new_outing_count": eligible_count,
        "ineligible_new_outing_count": len(results) - eligible_count,
        "legacy_development_outing_count": manifest.legacy_development_outing_count,
        "total_independent_outing_count_including_legacy": (
            eligible_count + manifest.legacy_development_outing_count
        ),
        "raw_usable_recording_count": sum(
            item.evidence.raw_usable_recording_count for item in results
        ),
        "summed_usable_duration_s": sum(
            item.evidence.usable_duration_ns for item in results
        )
        / 1e9,
        "eligible_h100_frame_count": sum(
            item.evidence.eligible_frame_count for item in results
        ),
        "eligible_sequence_count": sum(item.evidence.sequence_count for item in results),
        "availability_gate": {
            "minimum_eligible_new_outing_count": MINIMUM_ELIGIBLE_NEW_OUTING_COUNT,
            "passed": availability_passed,
        },
        "final_count": final_count,
        "role_counts": dict(sorted(roles.items())),
        "failure_code_counts_non_mutually_exclusive": dict(sorted(failures.items())),
        "attestation_status": "declared_not_independently_verified",
        "prior_successful_lock_sha256": prior_evidence["declared_sha256"],
        "prior_successful_lock_verified": prior_evidence["verified"],
        "overlapping_raw_sha256_count": prior_evidence[
            "overlapping_raw_sha256_count"
        ],
        "output_sha256": dict(sorted(output_hashes.items())),
        "summary_self_hash_recorded": False,
        "claim_limits": [
            "availability_and_locked_cohort_roles_only",
            "no_independent_journey_generalization_claim",
            "no_final_selection_or_benefit_claim",
            "rlmb_remains_a_pseudo_reference",
        ],
        "next_authorized_action": (
            "independently_reconcile_the_lock_before_any_embargoed_evaluation"
            if availability_passed
            else "retain_this_audit_and_acquire_more_outcome_blind_data"
        ),
        SCHEMA_COMPATIBILITY_FIELD: dict(schema_compatibility_amendment),
    }


def _write_outputs_transactionally(
    *,
    output_directory: Path,
    recording_rows: Sequence[Mapping[str, Any]],
    outing_rows: Sequence[Mapping[str, Any]],
    lock_payload: Mapping[str, Any],
    summary_factory: Callable[[Mapping[str, str]], Mapping[str, Any]],
) -> Mapping[str, Any]:
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.tmp-", dir=output_directory.parent
        )
    )
    try:
        recordings_path = temporary / OUTPUT_NAMES[0]
        outings_path = temporary / OUTPUT_NAMES[1]
        lock_path = temporary / OUTPUT_NAMES[2]
        write_csv_rows(recordings_path, RECORDING_FIELDS, recording_rows)
        write_csv_rows(outings_path, OUTING_FIELDS, outing_rows)
        write_strict_json(lock_path, lock_payload)
        hashes = {
            name: sha256_file(temporary / name) for name in OUTPUT_NAMES[:3]
        }
        summary = dict(summary_factory(hashes))
        write_strict_json(temporary / OUTPUT_NAMES[3], summary)
        if set(path.name for path in temporary.iterdir()) != set(OUTPUT_NAMES):
            raise AssertionError("v0.17 workflow generated an unexpected file set")
        temporary.rename(output_directory)
        return summary
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def run_independent_outing_intake(
    arguments: argparse.Namespace,
    *,
    inventory_inspector: InventoryInspector | None = None,
    technical_inspector: TechnicalInspector | None = None,
) -> tuple[dict[str, Any], int]:
    """Run the reviewed intake without serializing numeric frame values."""

    output_directory = _validate_output_target(arguments.output_directory)
    manifest_payload, manifest_bytes = read_strict_json_with_bytes(
        arguments.acquisition_manifest
    )
    manifest = parse_acquisition_manifest(manifest_payload)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    root = arguments.new_mcap_root.expanduser().resolve()
    files = discover_mcaps(root)
    files_by_basename = _validate_exact_coverage(files, manifest)
    hashes_by_basename = _hash_files(files_by_basename)
    fingerprints = _manifest_fingerprints(manifest, hashes_by_basename)
    provisional_assignments, _, _ = assign_cohorts(fingerprints, ())
    prior_evidence = _validate_prior_lock(
        manifest=manifest,
        supplied_path=arguments.prior_successful_lock,
        current_hashes=hashes_by_basename,
    )
    amended_from_failed_audit = _validate_failed_audit_directory(
        supplied_directory=getattr(
            arguments,
            "amended_from_failed_intake_directory",
            None,
        ),
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        current_hashes=hashes_by_basename,
    )

    inspect_inventory = inventory_inspector or inspect_mcap_for_inventory
    inspect_technical = technical_inspector or inspect_recording_technical_evidence
    label_by_basename = manifest.basename_to_private_label
    assignment_by_label = provisional_assignments
    recording_id_by_basename = {
        basename: f"recording_{index:03d}"
        for index, basename in enumerate(sorted(files_by_basename), 1)
    }
    inspected = [
        inspect_inventory(
            files_by_basename[basename],
            root=root,
            recording_id=recording_id_by_basename[basename],
            drive_id=assignment_by_label[label_by_basename[basename]].outing_id,
            precomputed_sha256=hashes_by_basename[basename],
        )
        for basename in sorted(files_by_basename)
    ]
    fingerprint_by_outing_id = {
        assignment_by_label[label].outing_id: fingerprint
        for label, fingerprint in fingerprints.items()
    }
    records = chronological_records(
        _assign_content_duplicates(inspected, fingerprint_by_outing_id)
    )
    edges = continuity_edges(records, maximum_source_gap_ns=MAXIMUM_SEQUENCE_GAP_NS)
    edge_by_right = {edge.right_recording_id: edge for edge in edges}

    technical_by_recording: dict[str, RecordingTechnicalEvidence] = {}
    previous_record: McapInventoryRecord | None = None
    previous_technical: RecordingTechnicalEvidence | None = None
    for record in records:
        same_outing = (
            previous_record is not None and previous_record.drive_id == record.drive_id
        )
        edge = edge_by_right.get(record.recording_id) if same_outing else None
        technical = inspect_technical(
            Path(record.path),
            raw_usable=record.usable,
            previous_path=(Path(previous_record.path) if same_outing else None),
            boundary_accepted=(edge is not None and edge.stitchable),
            previous_last_frame=(
                previous_technical.frames[-1]
                if same_outing and previous_technical is not None and previous_technical.frames
                else None
            ),
        )
        technical_by_recording[record.recording_id] = technical
        previous_record = record
        previous_technical = technical

    manifest_by_label = {
        outing.private_outing_label: outing for outing in manifest.outings
    }
    records_by_outing: dict[str, list[McapInventoryRecord]] = defaultdict(list)
    for record in records:
        assert record.drive_id is not None
        records_by_outing[record.drive_id].append(record)

    preliminary: dict[str, tuple[OutingEligibility, OutingEligibilityEvidence, _SequenceAudit]] = {}
    for label, assignment in assignment_by_label.items():
        outing_records = tuple(records_by_outing[assignment.outing_id])
        sequence_audit = _build_sequences(
            outing_records, technical_by_recording, edge_by_right
        )
        duration_ns, monotonic = _usable_interval_evidence(outing_records)
        technical = [technical_by_recording[item.recording_id] for item in outing_records]
        evidence = OutingEligibilityEvidence(
            raw_usable_recording_count=sum(item.usable for item in outing_records),
            usable_duration_ns=duration_ns,
            usable_intervals_monotonic_nonoverlapping=monotonic,
            topology_candidate_count=sum(item.topology_candidate_count for item in technical),
            non_sensor_topology_candidate_count=sum(
                item.non_sensor_topology_candidate_count for item in technical
            ),
            eligible_frame_count=sum(item.eligible_frame_count for item in technical),
            sequence_count=sequence_audit.sequence_count,
            retained_eligible_frame_count=sequence_audit.retained_eligible_frame_count,
        )
        preliminary[label] = (
            evaluate_outing_eligibility(evidence),
            evidence,
            sequence_audit,
        )
    eligible_labels = [
        label for label, (eligibility, _, _) in preliminary.items()
        if eligibility.technically_eligible
    ]
    assignments, final_count, availability_passed = assign_cohorts(
        fingerprints, eligible_labels
    )
    results = [
        _OutingResult(
            manifest=manifest_by_label[label],
            assignment=assignments[label],
            records=tuple(records_by_outing[assignments[label].outing_id]),
            technical_by_recording=technical_by_recording,
            eligibility=preliminary[label][0],
            evidence=preliminary[label][1],
            sequence_audit=preliminary[label][2],
        )
        for label in fingerprints
    ]
    # Opaque IDs are fingerprint-only, so eligibility cannot change them.
    if any(
        provisional_assignments[label].outing_id != assignments[label].outing_id
        for label in fingerprints
    ):
        raise AssertionError("opaque outing IDs changed during eligibility evaluation")

    result_by_outing_id = {item.assignment.outing_id: item for item in results}
    recording_rows = [
        _recording_row(
            record=record,
            technical=technical_by_recording[record.recording_id],
            private_label=result_by_outing_id[record.drive_id or ""].manifest.private_outing_label,
            sequence_audit=result_by_outing_id[record.drive_id or ""].sequence_audit,
            edge_by_right_recording=edge_by_right,
        )
        for record in sorted(records, key=lambda item: item.basename)
    ]
    outing_rows = [_outing_row(item) for item in sorted(results, key=lambda value: value.assignment.outing_id)]
    observed_descriptor_hashes = tuple(
        sorted(
            {
                digest
                for technical in technical_by_recording.values()
                for digest in technical.estimate_file_descriptor_sha256
            }
        )
    )
    decoded_estimate_count = sum(
        technical.estimate_message_count
        for technical in technical_by_recording.values()
    )
    if bool(observed_descriptor_hashes) is not bool(decoded_estimate_count):
        raise ValueError(
            "observed estimate descriptor identities do not reconcile with "
            "decoded estimate messages"
        )
    schema_compatibility_amendment = _schema_compatibility_amendment(
        observed_descriptor_hashes=observed_descriptor_hashes,
        amended_from_failed_audit=amended_from_failed_audit,
    )
    lock = _lock_payload(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        hashes_by_basename=hashes_by_basename,
        results=results,
        availability_passed=availability_passed,
        final_count=final_count,
        prior_evidence=prior_evidence,
        schema_compatibility_amendment=schema_compatibility_amendment,
    )
    summary = _write_outputs_transactionally(
        output_directory=output_directory,
        recording_rows=recording_rows,
        outing_rows=outing_rows,
        lock_payload=lock,
        summary_factory=lambda hashes: _summary_payload(
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            results=results,
            availability_passed=availability_passed,
            final_count=final_count,
            prior_evidence=prior_evidence,
            output_hashes=hashes,
            recording_rows=recording_rows,
            schema_compatibility_amendment=schema_compatibility_amendment,
        ),
    )
    return dict(summary), 0 if availability_passed else 3


__all__ = [
    "LOCK_TOP_LEVEL_FIELDS",
    "OUTING_FIELDS",
    "OUTPUT_NAMES",
    "RECORDING_FIELDS",
    "SUMMARY_TOP_LEVEL_FIELDS",
    "run_independent_outing_intake",
]
