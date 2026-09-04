#!/usr/bin/env python3
"""Independently verify one initial v0.17 intake bundle without decoding MCAPs.

This script deliberately uses only the Python standard library and imports no
``lane_residuals`` module. It reads immutable bytes, fixed counts, identities,
and cohort roles permitted by the final-outing embargo. It writes nothing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = "0.17.0"
MANIFEST_VERSION = "0.17"
PURPOSE = "independent_outing_intake_and_cohort_lock"
MANIFEST_PURPOSE = "prospective_independent_outing_intake"
CONTRACT_REVISION = "v0.17.0-reviewed-2026-09-03-layout-c1"
SPLIT_SALT = b"MPR-v0.17-final-split-v1"
MINIMUM_ELIGIBLE_NEW_OUTING_COUNT = 7
MINIMUM_USABLE_DURATION_S = 120.0
MINIMUM_ELIGIBLE_FRAME_COUNT = 500

ELIGIBILITY_RULES = {
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
SPLIT_CONTRACT_BASE = {
    "salt_ascii": SPLIT_SALT.decode("ascii"),
    "fingerprint_encoding": (
        "sorted lowercase raw SHA-256 ASCII plus LF; repeated entries retained"
    ),
    "score_encoding": "salt ASCII plus NUL plus outing fingerprint ASCII",
    "final_count_formula": "max(2, ceil((E + 1) / 5))",
    "opaque_id_order": "ascending outing fingerprint bytes",
    "role_order": "ascending split-score bytes then fingerprint bytes",
}
ALLOWED_EMBARGO_EVIDENCE = [
    "immutable_file_and_manifest_hashes",
    "opaque_identity_and_cohort_role",
    "raw_usability_and_fixed_eligibility_counts",
    "fixed_exclusion_and_boundary_codes",
]
CLAIM_LIMITS = [
    "availability_and_locked_cohort_roles_only",
    "no_independent_journey_generalization_claim",
    "no_final_selection_or_benefit_claim",
    "rlmb_remains_a_pseudo_reference",
]

OUTPUT_NAMES = (
    "independent_outing_recordings.csv",
    "independent_outings.csv",
    "independent_outing_lock.json",
    "independent_outing_intake_summary.json",
)

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

MANIFEST_FIELDS = frozenset(
    {
        "version",
        "purpose",
        "acquisition_batch_closed",
        "created_before_outcome_inspection",
        "legacy_development_outing_count",
        "prior_successful_lock_sha256",
        "superseding_contract_amendment_id",
        "outings",
    }
)
MANIFEST_OUTING_FIELDS = frozenset(
    {
        "private_outing_label",
        "acquisition_start_utc",
        "separate_physical_session",
        "independence_basis_private",
        "mcap_basenames_private",
    }
)
LOCK_FIELDS = frozenset(
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
    }
)
LOCK_OUTING_FIELDS = frozenset(
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
SUMMARY_FIELDS = frozenset(
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
    }
)


class VerificationError(ValueError):
    """A stable fail-closed bundle-verification error."""


def _typed_json_equal(actual: Any, expected: Any) -> bool:
    """Compare decoded JSON without treating booleans as numeric values."""

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
            and all(
                _typed_json_equal(actual_value, expected_value)
                for actual_value, expected_value in zip(actual, expected)
            )
        )
    return type(actual) is type(expected) and actual == expected


def _exact_fields(value: Any, expected: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationError(f"{name} must be a JSON object")
    actual = set(value)
    if actual != expected:
        raise VerificationError(
            f"{name} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _read_strict_json(path: Path) -> tuple[Any, bytes]:
    if not path.is_file():
        raise VerificationError(f"required JSON file is missing: {path}")
    raw = path.read_bytes()

    def reject_constant(value: str) -> None:
        raise VerificationError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except UnicodeDecodeError as error:
        raise VerificationError(f"JSON file must be UTF-8: {path}") from error
    except json.JSONDecodeError as error:
        raise VerificationError(f"JSON file is malformed: {path}") from error
    return payload, raw


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lowercase_sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise VerificationError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise VerificationError(f"{name} must be a JSON boolean")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise VerificationError(f"{name} must be a nonnegative integer")
    return value


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"{name} must be a nonempty string")
    return value


def _timezone_aware_iso8601(value: Any, name: str) -> str:
    text = _nonempty_string(value, name)
    parse_value = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as error:
        raise VerificationError(f"{name} must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise VerificationError(f"{name} must include a UTC offset")
    return text


def _csv_bool(value: str | None, name: str, *, nullable: bool = False) -> bool | None:
    if nullable and (value is None or value == ""):
        return None
    if value not in {"True", "False"}:
        raise VerificationError(f"{name} must be True or False in the CSV")
    return value == "True"


def _csv_int(value: str | None, name: str, *, nullable: bool = False) -> int | None:
    if nullable and (value is None or value == ""):
        return None
    if value is None or not value.isdigit():
        raise VerificationError(f"{name} must be a nonnegative integer in the CSV")
    return int(value)


def _csv_float(value: str | None, name: str, *, nullable: bool = False) -> float | None:
    if nullable and (value is None or value == ""):
        return None
    try:
        parsed = float(value) if value is not None else math.nan
    except ValueError as error:
        raise VerificationError(f"{name} must be numeric in the CSV") from error
    if not math.isfinite(parsed) or parsed < 0.0:
        raise VerificationError(f"{name} must be finite and nonnegative in the CSV")
    return parsed


def _outing_fingerprint(digests: Sequence[str]) -> str:
    if not digests:
        raise VerificationError("outing fingerprint requires raw file hashes")
    values = sorted(_lowercase_sha256(value, "raw MCAP hash") for value in digests)
    return _sha256_bytes(b"".join(value.encode("ascii") + b"\n" for value in values))


def _split_score(fingerprint: str) -> str:
    validated = _lowercase_sha256(fingerprint, "outing fingerprint")
    return _sha256_bytes(SPLIT_SALT + b"\0" + validated.encode("ascii"))


def _discover_raw_mcaps(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise VerificationError(f"raw MCAP root is not a directory: {root}")
    result: dict[str, Path] = {}
    duplicate_basenames: set[str] = set()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file() and item.suffix.lower() == ".mcap"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.name in result:
            duplicate_basenames.add(path.name)
        result[path.name] = path
    if duplicate_basenames:
        raise VerificationError(
            f"raw MCAP basenames are not unique: {sorted(duplicate_basenames)}"
        )
    if not result:
        raise VerificationError("raw MCAP root contains no .mcap files")
    return result


def _read_csv(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise VerificationError(f"required CSV file is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise VerificationError(f"unexpected CSV header: {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise VerificationError(f"CSV row has missing or extra columns: {path.name}")
    return rows


def _manifest_outings(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    if manifest["version"] != MANIFEST_VERSION or manifest["purpose"] != MANIFEST_PURPOSE:
        raise VerificationError("manifest identity differs from v0.17")
    if manifest["acquisition_batch_closed"] is not True:
        raise VerificationError("manifest acquisition batch is not closed")
    if manifest["created_before_outcome_inspection"] is not True:
        raise VerificationError("manifest prospective attestation is not true")
    if type(manifest["legacy_development_outing_count"]) is not int or manifest[
        "legacy_development_outing_count"
    ] != 1:
        raise VerificationError("manifest legacy outing count must be integer 1")
    if manifest["prior_successful_lock_sha256"] is not None:
        raise VerificationError("this verifier accepts only an initial v0.17 lock")
    if manifest["superseding_contract_amendment_id"] is not None:
        raise VerificationError("initial manifest amendment identifier must be null")
    raw_outings = manifest["outings"]
    if not isinstance(raw_outings, list) or not raw_outings:
        raise VerificationError("manifest outings must be a nonempty array")

    by_label: dict[str, tuple[str, ...]] = {}
    label_by_basename: dict[str, str] = {}
    for index, raw_outing in enumerate(raw_outings):
        outing = _exact_fields(
            raw_outing, MANIFEST_OUTING_FIELDS, f"manifest outings[{index}]"
        )
        label = _nonempty_string(
            outing["private_outing_label"], f"manifest outings[{index}] label"
        )
        if label in by_label:
            raise VerificationError("manifest outing labels are not unique")
        if outing["separate_physical_session"] is not True:
            raise VerificationError("manifest separate-session attestation is not true")
        _timezone_aware_iso8601(
            outing["acquisition_start_utc"], f"manifest outings[{index}] timestamp"
        )
        _nonempty_string(
            outing["independence_basis_private"],
            f"manifest outings[{index}] independence basis",
        )
        raw_basenames = outing["mcap_basenames_private"]
        if not isinstance(raw_basenames, list) or not raw_basenames:
            raise VerificationError("manifest outing must declare MCAP basenames")
        basenames: list[str] = []
        for value in raw_basenames:
            basename = _nonempty_string(value, "manifest MCAP basename")
            if (
                basename != basename.replace("\\", "/").split("/")[-1]
                or not basename.lower().endswith(".mcap")
            ):
                raise VerificationError("manifest MCAP entry is not an unqualified basename")
            if basename in label_by_basename:
                raise VerificationError("manifest MCAP basenames are not globally unique")
            label_by_basename[basename] = label
            basenames.append(basename)
        by_label[label] = tuple(basenames)
    return by_label, label_by_basename


def _validate_output_directory(output: Path) -> None:
    if not output.is_dir():
        raise VerificationError(f"intake output is not a directory: {output}")
    children = tuple(output.iterdir())
    actual = {item.name for item in children}
    if actual != set(OUTPUT_NAMES) or any(not item.is_file() for item in children):
        raise VerificationError(
            f"intake output file set differs: missing={sorted(set(OUTPUT_NAMES) - actual)}, "
            f"extra={sorted(actual - set(OUTPUT_NAMES))}"
        )


def verify_intake_bundle(
    raw_mcap_root: Path,
    acquisition_manifest: Path,
    intake_output_directory: Path,
) -> dict[str, Any]:
    """Verify initial-lock bytes, identities, assignments, and CSV reconciliation."""

    raw_root = raw_mcap_root.expanduser().resolve()
    manifest_path = acquisition_manifest.expanduser().resolve()
    output = intake_output_directory.expanduser().resolve()
    _validate_output_directory(output)

    manifest_payload, manifest_bytes = _read_strict_json(manifest_path)
    manifest = _exact_fields(manifest_payload, MANIFEST_FIELDS, "acquisition manifest")
    manifest_by_label, label_by_basename = _manifest_outings(manifest)
    manifest_sha256 = _sha256_bytes(manifest_bytes)

    lock_payload, lock_bytes = _read_strict_json(output / OUTPUT_NAMES[2])
    summary_payload, _ = _read_strict_json(output / OUTPUT_NAMES[3])
    lock = _exact_fields(lock_payload, LOCK_FIELDS, "intake lock")
    summary = _exact_fields(summary_payload, SUMMARY_FIELDS, "intake summary")

    for name, payload in (("lock", lock), ("summary", summary)):
        if payload["version"] != VERSION or payload["purpose"] != PURPOSE:
            raise VerificationError(f"{name} identity differs from v0.17.0")
        if payload["contract_revision"] != CONTRACT_REVISION:
            raise VerificationError(f"{name} contract revision differs")
    if lock["status"] != summary["status"]:
        raise VerificationError("lock and summary statuses differ")
    if lock["status"] not in {"locked", "insufficient_independent_outings"}:
        raise VerificationError("unrecognized v0.17 lock status")
    if not _typed_json_equal(lock["eligibility_rules"], ELIGIBILITY_RULES):
        raise VerificationError("fixed eligibility rules differ from v0.17")

    split_contract = lock["split_contract"]
    if not isinstance(split_contract, Mapping):
        raise VerificationError("split contract must be an object")
    expected_split_fields = set(SPLIT_CONTRACT_BASE) | {"final_count"}
    if set(split_contract) != expected_split_fields:
        raise VerificationError("split contract fields differ from v0.17")
    for key, value in SPLIT_CONTRACT_BASE.items():
        if not _typed_json_equal(split_contract[key], value):
            raise VerificationError(f"split contract differs at {key}")

    lock_manifest = _exact_fields(
        lock["manifest"], frozenset({"version", "purpose", "sha256"}), "lock manifest"
    )
    if (
        lock_manifest["version"] != MANIFEST_VERSION
        or lock_manifest["purpose"] != MANIFEST_PURPOSE
        or _lowercase_sha256(lock_manifest["sha256"], "lock manifest hash")
        != manifest_sha256
        or _lowercase_sha256(summary["manifest_sha256"], "summary manifest hash")
        != manifest_sha256
    ):
        raise VerificationError("manifest SHA-256 lineage does not reconcile")

    expected_hashed_outputs = set(OUTPUT_NAMES[:3])
    output_hashes = summary["output_sha256"]
    if not isinstance(output_hashes, Mapping) or set(output_hashes) != expected_hashed_outputs:
        raise VerificationError("summary output hash map differs")
    for name in OUTPUT_NAMES[:3]:
        declared = _lowercase_sha256(output_hashes[name], f"summary hash for {name}")
        if declared != _sha256_file(output / name):
            raise VerificationError(f"output SHA-256 mismatch: {name}")
    if summary["summary_self_hash_recorded"] is not False:
        raise VerificationError("summary must not record a recursive self-hash")

    raw_paths = _discover_raw_mcaps(raw_root)
    if set(raw_paths) != set(label_by_basename):
        raise VerificationError("raw root and manifest basename coverage differ")
    raw_hashes = {
        basename: _sha256_file(raw_paths[basename]) for basename in sorted(raw_paths)
    }
    lock_raw = lock["raw_file_sha256_by_basename_private"]
    if not isinstance(lock_raw, Mapping) or set(lock_raw) != set(raw_hashes):
        raise VerificationError("lock raw-file hash map coverage differs")
    for basename, digest in raw_hashes.items():
        if _lowercase_sha256(lock_raw[basename], f"lock raw hash for {basename}") != digest:
            raise VerificationError(f"raw MCAP SHA-256 mismatch: {basename}")

    raw_lock_outings = lock["outings"]
    if not isinstance(raw_lock_outings, list) or len(raw_lock_outings) != len(
        manifest_by_label
    ):
        raise VerificationError("lock outing count differs from manifest")
    lock_by_label: dict[str, Mapping[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    eligibility: dict[str, bool] = {}
    reconciled_raw: dict[str, str] = {}
    for index, raw_outing in enumerate(raw_lock_outings):
        outing = _exact_fields(raw_outing, LOCK_OUTING_FIELDS, f"lock outings[{index}]")
        label = _nonempty_string(outing["private_outing_label"], "lock private label")
        if label in lock_by_label or label not in manifest_by_label:
            raise VerificationError("lock outing labels do not reconcile")
        manifest_outing = next(
            item for item in manifest["outings"] if item["private_outing_label"] == label
        )
        if outing["acquisition_start_utc_private"] != manifest_outing[
            "acquisition_start_utc"
        ]:
            raise VerificationError(f"lock acquisition timestamp mismatch: {label}")
        local_raw = outing["mcap_sha256_by_basename_private"]
        if not isinstance(local_raw, Mapping) or set(local_raw) != set(
            manifest_by_label[label]
        ):
            raise VerificationError(f"lock raw map differs for outing {label}")
        local_digests: list[str] = []
        for basename in manifest_by_label[label]:
            digest = _lowercase_sha256(local_raw[basename], "lock outing raw hash")
            if digest != raw_hashes[basename] or basename in reconciled_raw:
                raise VerificationError("lock nested raw-file maps do not reconcile")
            reconciled_raw[basename] = digest
            local_digests.append(digest)
        fingerprint = _lowercase_sha256(
            outing["outing_fingerprint_sha256"], "lock outing fingerprint"
        )
        if fingerprint != _outing_fingerprint(local_digests):
            raise VerificationError(f"outing fingerprint mismatch: {label}")
        fingerprints[label] = fingerprint
        eligibility[label] = _exact_bool(
            outing["technically_eligible"], "outing eligibility"
        )
        for count_field in (
            "raw_usable_recording_count",
            "summed_usable_duration_ns",
            "eligible_frame_count",
            "sequence_count",
        ):
            _nonnegative_int(outing[count_field], f"outing {count_field}")
        lock_by_label[label] = outing
    if reconciled_raw != raw_hashes:
        raise VerificationError("lock nested raw-file map coverage differs")
    if len(set(fingerprints.values())) != len(fingerprints):
        raise VerificationError("lock outing fingerprints are not unique")

    expected_ids = {
        label: f"outing_{index:03d}"
        for index, label in enumerate(
            sorted(fingerprints, key=lambda value: bytes.fromhex(fingerprints[value])),
            1,
        )
    }
    identity_map = lock["private_to_opaque_outing_id"]
    if not isinstance(identity_map, Mapping) or dict(identity_map) != expected_ids:
        raise VerificationError("private-to-opaque outing identity map differs")
    for label, outing in lock_by_label.items():
        if outing["outing_id"] != expected_ids[label]:
            raise VerificationError(f"opaque outing ID mismatch: {label}")
    if [outing["outing_id"] for outing in lock["outings"]] != sorted(
        expected_ids.values()
    ):
        raise VerificationError("lock outings are not in opaque-ID order")

    eligible_labels = {label for label, value in eligibility.items() if value}
    eligible_count = len(eligible_labels)
    declared_count = len(manifest_by_label)
    gate_passed = eligible_count >= MINIMUM_ELIGIBLE_NEW_OUTING_COUNT
    expected_status = "locked" if gate_passed else "insufficient_independent_outings"
    if lock["status"] != expected_status:
        raise VerificationError("status differs from the seven-outing gate")
    if _exact_bool(lock["split_assignments_authorized"], "split authorization") != gate_passed:
        raise VerificationError("split authorization differs from availability gate")

    lock_gate = _exact_fields(
        lock["availability_gate"],
        frozenset(
            {
                "minimum_eligible_new_outing_count",
                "eligible_new_outing_count",
                "total_independent_outing_count_including_legacy",
                "passed",
            }
        ),
        "lock availability gate",
    )
    summary_gate = _exact_fields(
        summary["availability_gate"],
        frozenset({"minimum_eligible_new_outing_count", "passed"}),
        "summary availability gate",
    )
    if (
        _nonnegative_int(
            lock_gate["minimum_eligible_new_outing_count"],
            "lock minimum eligible outing count",
        )
        != MINIMUM_ELIGIBLE_NEW_OUTING_COUNT
        or _nonnegative_int(
            lock_gate["eligible_new_outing_count"], "lock eligible outing count"
        )
        != eligible_count
        or _nonnegative_int(
            lock_gate["total_independent_outing_count_including_legacy"],
            "lock total independent outing count",
        )
        != eligible_count + 1
        or lock_gate["passed"] is not gate_passed
        or _nonnegative_int(
            summary_gate["minimum_eligible_new_outing_count"],
            "summary minimum eligible outing count",
        )
        != MINIMUM_ELIGIBLE_NEW_OUTING_COUNT
        or summary_gate["passed"] is not gate_passed
    ):
        raise VerificationError("availability-gate fields do not reconcile")
    if (
        _nonnegative_int(
            summary["declared_new_outing_count"], "summary declared outing count"
        )
        != declared_count
        or _nonnegative_int(
            summary["eligible_new_outing_count"], "summary eligible outing count"
        )
        != eligible_count
        or _nonnegative_int(
            summary["ineligible_new_outing_count"], "summary ineligible outing count"
        )
        != declared_count - eligible_count
        or _nonnegative_int(
            summary["legacy_development_outing_count"],
            "summary legacy development outing count",
        )
        != 1
        or _nonnegative_int(
            summary["total_independent_outing_count_including_legacy"],
            "summary total independent outing count",
        )
        != eligible_count + 1
        or _nonnegative_int(
            lock["legacy_development_outing_count"],
            "lock legacy development outing count",
        )
        != 1
    ):
        raise VerificationError("summary outing counts do not reconcile")

    if gate_passed:
        final_count = max(2, math.ceil((eligible_count + 1) / 5))
        if (
            not 2 <= final_count < eligible_count
            or _nonnegative_int(summary["final_count"], "summary final count")
            != final_count
        ):
            raise VerificationError("final-outing count differs from the fixed formula")
        expected_scores = {
            label: _split_score(fingerprints[label]) for label in eligible_labels
        }
        split_order = sorted(
            eligible_labels,
            key=lambda label: (
                bytes.fromhex(expected_scores[label]),
                bytes.fromhex(fingerprints[label]),
            ),
        )
        expected_ranks = {label: index for index, label in enumerate(split_order, 1)}
    else:
        final_count = None
        expected_scores = {}
        expected_ranks = {}
        if summary["final_count"] is not None:
            raise VerificationError("failed gate must have null final count")
    if split_contract["final_count"] != final_count:
        raise VerificationError("lock split-contract final count differs")

    expected_roles: dict[str, str | None] = {}
    for label, outing in lock_by_label.items():
        if not gate_passed:
            score = rank = role = None
        elif label not in eligible_labels:
            score = rank = None
            role = "excluded"
        else:
            score = expected_scores[label]
            rank = expected_ranks[label]
            role = "final_test" if rank <= (final_count or 0) else "development"
        if (
            outing["split_score_sha256"] != score
            or outing["split_rank"] != rank
            or outing["cohort_role"] != role
        ):
            raise VerificationError(f"split assignment mismatch: {label}")
        expected_roles[label] = role

    expected_role_counts = dict(
        sorted(Counter(role or "unassigned" for role in expected_roles.values()).items())
    )
    for source, counts in (("lock", lock["role_counts"]), ("summary", summary["role_counts"])):
        if (
            not isinstance(counts, Mapping)
            or any(type(value) is not int or value < 0 for value in counts.values())
            or dict(counts) != expected_role_counts
        ):
            raise VerificationError(f"{source} role counts do not reconcile")
    prior = _exact_fields(
        lock["prior_successful_lock"],
        frozenset(
            {
                "declared_sha256",
                "supplied",
                "verified",
                "overlapping_raw_sha256_count",
                "superseding_contract_amendment_id",
            }
        ),
        "initial prior-lock evidence",
    )
    if not _typed_json_equal(
        prior,
        {
            "declared_sha256": None,
            "supplied": False,
            "verified": False,
            "overlapping_raw_sha256_count": 0,
            "superseding_contract_amendment_id": None,
        },
    ):
        raise VerificationError("initial prior-lock evidence differs")
    if (
        summary["prior_successful_lock_sha256"] is not None
        or summary["prior_successful_lock_verified"] is not False
        or summary["overlapping_raw_sha256_count"] != 0
    ):
        raise VerificationError("summary prior-lock evidence differs")

    attestations = _exact_fields(
        lock["attestations"],
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
    )
    if (
        attestations["verification_status"] != "declared_not_independently_verified"
        or attestations["acquisition_batch_closed"] is not True
        or attestations["created_before_outcome_inspection"] is not True
        or attestations["null_prior_successful_lock_declared"] is not True
    ):
        raise VerificationError("lock batch attestations differ")
    raw_attestation_outings = attestations["outings"]
    if not isinstance(raw_attestation_outings, list) or len(
        raw_attestation_outings
    ) != declared_count:
        raise VerificationError("lock outing attestations do not reconcile")
    attestation_by_id: dict[str, Mapping[str, Any]] = {}
    manifest_detail_by_label = {
        item["private_outing_label"]: item for item in manifest["outings"]
    }
    for index, raw_attestation in enumerate(raw_attestation_outings):
        attestation = _exact_fields(
            raw_attestation,
            frozenset(
                {"outing_id", "separate_physical_session", "independence_basis_private"}
            ),
            f"lock attestations.outings[{index}]",
        )
        outing_id = _nonempty_string(attestation["outing_id"], "attested outing ID")
        if outing_id in attestation_by_id or outing_id not in expected_ids.values():
            raise VerificationError("lock outing attestation identities differ")
        label = next(label for label, value in expected_ids.items() if value == outing_id)
        if (
            attestation["separate_physical_session"] is not True
            or attestation["independence_basis_private"]
            != manifest_detail_by_label[label]["independence_basis_private"]
        ):
            raise VerificationError(f"lock outing attestation mismatch: {outing_id}")
        attestation_by_id[outing_id] = attestation
    if set(attestation_by_id) != set(expected_ids.values()):
        raise VerificationError("lock outing attestation coverage differs")

    recordings = _read_csv(output / OUTPUT_NAMES[0], RECORDING_FIELDS)
    outings_csv = _read_csv(output / OUTPUT_NAMES[1], OUTING_FIELDS)
    if len(recordings) != len(raw_hashes) or _nonnegative_int(
        summary["mcap_file_count"], "summary MCAP file count"
    ) != len(raw_hashes):
        raise VerificationError("recording counts do not reconcile")
    recording_by_basename: dict[str, Mapping[str, str]] = {}
    recording_ids: set[str] = set()
    for row in recordings:
        basename = row["mcap_basename_private"]
        if basename in recording_by_basename or basename not in raw_hashes:
            raise VerificationError("recording CSV basename coverage differs")
        if row["sha256"] != raw_hashes[basename]:
            raise VerificationError(f"recording CSV raw hash mismatch: {basename}")
        label = label_by_basename[basename]
        if row["private_outing_label"] != label or row["outing_id"] != expected_ids[label]:
            raise VerificationError(f"recording CSV outing identity mismatch: {basename}")
        relative = row["relative_path_private"]
        relative_path = PurePosixPath(relative)
        expected_relative = raw_paths[basename].relative_to(raw_root).as_posix()
        if (
            not relative
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or "\\" in relative
            or relative_path.name != basename
            or relative != expected_relative
        ):
            raise VerificationError(f"recording CSV relative path is invalid: {basename}")
        if _csv_int(row["file_size_bytes"], "recording file size") != raw_paths[
            basename
        ].stat().st_size:
            raise VerificationError(f"recording CSV file size mismatch: {basename}")
        recording_id = _nonempty_string(row["recording_id"], "recording ID")
        if recording_id in recording_ids:
            raise VerificationError("recording CSV IDs are not unique")
        expected_recording_id = f"recording_{sorted(raw_hashes).index(basename) + 1:03d}"
        if recording_id != expected_recording_id:
            raise VerificationError(f"recording CSV ID mismatch: {basename}")
        for field in (
            "raw_readable",
            "raw_empty",
            "raw_usable",
            "estimate_source_timestamps_strictly_increasing",
            "required_topic_schema_compatible",
            "estimate_topic_present",
            "estimate_topic_schema_compatible",
            "map_topic_present",
            "map_topic_schema_compatible",
            "odometry_topic_present",
            "odometry_topic_schema_compatible",
            "eligible_sequence_stitched_to_previous",
        ):
            _csv_bool(row[field], f"recording {field}")
        _csv_bool(
            row["boundary_to_previous_stitchable"],
            "recording boundary_to_previous_stitchable",
            nullable=True,
        )
        for field in (
            "estimate_source_timestamp_count",
            "estimate_missing_source_timestamp_count",
            "estimate_topic_message_count",
            "map_topic_message_count",
            "odometry_topic_message_count",
            "decoded_estimate_message_count",
            "decoded_map_message_count",
            "topology_gate_candidate_count",
            "sensor_topology_candidate_count",
            "lane_map_topology_candidate_count",
            "unknown_or_other_topology_candidate_count",
            "h100_geometry_ready_count",
            "h100_eligible_frame_count",
            "sequence_count_touching_recording",
        ):
            _csv_int(row[field], f"recording {field}")
        for field in (
            "chronological_index_within_outing",
            "internal_start_log_time_ns_private",
            "internal_end_log_time_ns_private",
            "first_estimate_source_time_ns_private",
            "last_estimate_source_time_ns_private",
        ):
            _csv_int(row[field], f"recording {field}", nullable=True)
        _csv_float(
            row["estimate_source_duration_s"],
            "recording estimate_source_duration_s",
            nullable=True,
        )
        topology_count = _csv_int(
            row["topology_gate_candidate_count"], "recording topology count"
        )
        topology_parts = sum(
            int(_csv_int(row[field], f"recording {field}") or 0)
            for field in (
                "sensor_topology_candidate_count",
                "lane_map_topology_candidate_count",
                "unknown_or_other_topology_candidate_count",
            )
        )
        if topology_count != topology_parts:
            raise VerificationError(f"recording topology counts mismatch: {basename}")
        recording_ids.add(recording_id)
        recording_by_basename[basename] = row
    if set(recording_by_basename) != set(raw_hashes):
        raise VerificationError("recording CSV basename coverage differs")
    if [row["recording_id"] for row in recordings] != [
        f"recording_{index:03d}" for index in range(1, len(recordings) + 1)
    ]:
        raise VerificationError("recording CSV rows are not in deterministic basename order")

    if len(outings_csv) != declared_count:
        raise VerificationError("outing CSV row count differs")
    csv_labels: set[str] = set()
    aggregate_raw_usable = 0
    aggregate_duration_ns = 0
    aggregate_eligible_frames = 0
    aggregate_sequences = 0
    for row in outings_csv:
        label = row["private_outing_label"]
        if label in csv_labels or label not in lock_by_label:
            raise VerificationError("outing CSV labels do not reconcile")
        csv_labels.add(label)
        lock_outing = lock_by_label[label]
        manifest_outing = manifest_detail_by_label[label]
        expected_score = lock_outing["split_score_sha256"]
        expected_rank = lock_outing["split_rank"]
        expected_role = expected_roles[label]
        if (
            row["outing_id"] != expected_ids[label]
            or row["acquisition_start_utc_private"]
            != manifest_outing["acquisition_start_utc"]
            or row["separate_physical_session_declared"] != "True"
            or row["independence_basis_private"]
            != manifest_outing["independence_basis_private"]
            or row["outing_fingerprint_sha256"] != fingerprints[label]
            or row["technically_eligible"] != str(eligibility[label])
            or row["split_score_sha256"] != (expected_score or "")
            or row["split_rank"] != ("" if expected_rank is None else str(expected_rank))
            or row["cohort_role"] != (expected_role or "")
        ):
            raise VerificationError(f"outing CSV assignment mismatch: {label}")

        recording_count = int(
            _csv_int(row["recording_count"], "outing recording_count") or 0
        )
        raw_usable_count = int(
            _csv_int(
                row["raw_usable_recording_count"], "outing raw_usable_recording_count"
            )
            or 0
        )
        duration_s = float(
            _csv_float(row["summed_usable_duration_s"], "outing duration") or 0.0
        )
        topology_count = int(
            _csv_int(
                row["topology_gate_candidate_count"], "outing topology candidate count"
            )
            or 0
        )
        non_sensor_count = int(
            _csv_int(
                row["non_sensor_topology_candidate_count"],
                "outing non-sensor topology count",
            )
            or 0
        )
        eligible_frames = int(
            _csv_int(row["eligible_frame_count"], "outing eligible frame count") or 0
        )
        sequence_count = int(
            _csv_int(row["sequence_count"], "outing sequence count") or 0
        )
        retained_frames = int(
            _csv_int(
                row["retained_eligible_frame_count"],
                "outing retained eligible frame count",
            )
            or 0
        )
        monotonic = bool(
            _csv_bool(
                row["usable_intervals_monotonic_nonoverlapping"],
                "outing usable interval state",
            )
        )
        expected_flags = {
            "has_raw_usable_recording": raw_usable_count >= 1,
            "usable_duration_gate_passes": (
                monotonic and duration_s >= MINIMUM_USABLE_DURATION_S
            ),
            "topology_gate_passes": non_sensor_count == 0,
            "eligible_frame_count_gate_passes": (
                eligible_frames >= MINIMUM_ELIGIBLE_FRAME_COUNT
            ),
            "sequence_integrity_passes": (
                sequence_count >= 1 and retained_frames == eligible_frames
            ),
        }
        for field, expected in expected_flags.items():
            if _csv_bool(row[field], f"outing {field}") is not expected:
                raise VerificationError(f"outing eligibility flag mismatch: {label}/{field}")
        expected_eligible = all(expected_flags.values())
        if expected_eligible is not eligibility[label]:
            raise VerificationError(f"outing technical eligibility mismatch: {label}")
        expected_failure_codes: list[str] = []
        if not expected_flags["has_raw_usable_recording"]:
            expected_failure_codes.append("no_raw_usable_recording")
        if not monotonic:
            expected_failure_codes.append(
                "usable_source_intervals_overlap_or_are_not_monotonic"
            )
        if duration_s < MINIMUM_USABLE_DURATION_S:
            expected_failure_codes.append("usable_duration_below_120s")
        if not expected_flags["topology_gate_passes"]:
            expected_failure_codes.append("mixed_or_unknown_topology_source")
        if not expected_flags["eligible_frame_count_gate_passes"]:
            expected_failure_codes.append("eligible_frame_count_below_500")
        if not expected_flags["sequence_integrity_passes"]:
            expected_failure_codes.append("eligible_sequence_integrity_failed")
        if row["failure_codes"] != ";".join(sorted(expected_failure_codes)):
            raise VerificationError(f"outing failure codes mismatch: {label}")

        recording_group = [
            item for item in recordings if item["private_outing_label"] == label
        ]
        recording_duration = sum(
            float(
                _csv_float(
                    item["estimate_source_duration_s"],
                    "usable recording duration",
                    nullable=True,
                )
                or 0.0
            )
            for item in recording_group
            if _csv_bool(item["raw_usable"], "recording raw_usable")
        )
        if (
            recording_count != len(manifest_by_label[label])
            or recording_count != len(recording_group)
            or raw_usable_count
            != sum(
                bool(_csv_bool(item["raw_usable"], "recording raw_usable"))
                for item in recording_group
            )
            or not math.isclose(
                duration_s,
                recording_duration,
                rel_tol=0.0,
                abs_tol=max(1, recording_count) * 1e-9,
            )
            or topology_count
            != sum(
                int(
                    _csv_int(
                        item["topology_gate_candidate_count"],
                        "recording topology count",
                    )
                    or 0
                )
                for item in recording_group
            )
            or non_sensor_count
            != sum(
                int(
                    _csv_int(
                        item["lane_map_topology_candidate_count"],
                        "recording lane-map topology count",
                    )
                    or 0
                )
                + int(
                    _csv_int(
                        item["unknown_or_other_topology_candidate_count"],
                        "recording unknown topology count",
                    )
                    or 0
                )
                for item in recording_group
            )
            or eligible_frames
            != sum(
                int(
                    _csv_int(
                        item["h100_eligible_frame_count"],
                        "recording eligible frame count",
                    )
                    or 0
                )
                for item in recording_group
            )
        ):
            raise VerificationError(f"outing and recording CSV counts mismatch: {label}")
        if (
            lock_outing["raw_usable_recording_count"] != raw_usable_count
            or lock_outing["summed_usable_duration_ns"] / 1e9 != duration_s
            or lock_outing["eligible_frame_count"] != eligible_frames
            or lock_outing["sequence_count"] != sequence_count
        ):
            raise VerificationError(f"outing CSV and lock counts mismatch: {label}")
        aggregate_raw_usable += raw_usable_count
        aggregate_duration_ns += lock_outing["summed_usable_duration_ns"]
        aggregate_eligible_frames += eligible_frames
        aggregate_sequences += sequence_count
    if csv_labels != set(lock_by_label):
        raise VerificationError("outing CSV label coverage differs")
    if [row["outing_id"] for row in outings_csv] != sorted(expected_ids.values()):
        raise VerificationError("outing CSV rows are not in opaque-ID order")
    if (
        type(summary["raw_usable_recording_count"]) is not int
        or summary["raw_usable_recording_count"] != aggregate_raw_usable
        or type(summary["summed_usable_duration_s"]) not in {int, float}
        or summary["summed_usable_duration_s"] != aggregate_duration_ns / 1e9
        or type(summary["eligible_h100_frame_count"]) is not int
        or summary["eligible_h100_frame_count"] != aggregate_eligible_frames
        or type(summary["eligible_sequence_count"]) is not int
        or summary["eligible_sequence_count"] != aggregate_sequences
    ):
        raise VerificationError("summary technical counts do not reconcile")

    failure_counts: Counter[str] = Counter()
    for row in recordings:
        failure_counts.update(code for code in row["failure_codes"].split(";") if code)
        failure_counts.update(
            code
            for code in row["boundary_codes"].split(";")
            if code and code not in {"outing_start", "accepted_cross_mcap_continuity"}
        )
    for row in outings_csv:
        failure_counts.update(code for code in row["failure_codes"].split(";") if code)
    if summary["failure_code_counts_non_mutually_exclusive"] != dict(
        sorted(failure_counts.items())
    ):
        raise VerificationError("summary failure-code counts do not reconcile")
    if (
        summary["attestation_status"] != "declared_not_independently_verified"
        or not _typed_json_equal(summary["claim_limits"], CLAIM_LIMITS)
        or summary["next_authorized_action"]
        != (
            "independently_reconcile_the_lock_before_any_embargoed_evaluation"
            if gate_passed
            else "retain_this_audit_and_acquire_more_outcome_blind_data"
        )
    ):
        raise VerificationError("summary claim boundary differs from v0.17")

    embargo = _exact_fields(
        lock["final_outing_embargo"],
        frozenset({"active", "allowed_evidence", "embargoed_numeric_evidence"}),
        "final-outing embargo",
    )
    if (
        embargo["active"] is not gate_passed
        or not _typed_json_equal(
            embargo["allowed_evidence"], ALLOWED_EMBARGO_EVIDENCE
        )
        or embargo["embargoed_numeric_evidence"] is not True
    ):
        raise VerificationError("final-outing embargo state differs from lock status")

    return {
        "version": VERSION,
        "verification_status": "passed",
        "verification_scope": "lineage_identity_split_and_report_reconciliation_only",
        "technical_evidence_redecoded": False,
        "lock_status": lock["status"],
        "manifest_sha256": manifest_sha256,
        "lock_sha256": _sha256_bytes(lock_bytes),
        "raw_mcap_count": len(raw_hashes),
        "declared_new_outing_count": declared_count,
        "eligible_new_outing_count": eligible_count,
        "final_count": final_count,
        "split_assignments_authorized": gate_passed,
        "files_written": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify an initial v0.17 intake bundle using only "
            "hash, count, identity, and cohort-role evidence."
        )
    )
    parser.add_argument("raw_mcap_root", type=Path)
    parser.add_argument("--acquisition-manifest", required=True, type=Path)
    parser.add_argument("--intake-output-directory", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = verify_intake_bundle(
            arguments.raw_mcap_root,
            arguments.acquisition_manifest,
            arguments.intake_output_directory,
        )
    except (OSError, TypeError, ValueError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["VerificationError", "main", "verify_intake_bundle"]
