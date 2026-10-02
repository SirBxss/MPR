"""Reusable development registration and readiness; no cohort, export or fit."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import logging
from pathlib import Path
import platform
import resource
import shutil

from ..domain.recording_ingestion import (
    CONTRACT_REVISION, SOURCE_FIELDS, SPECIFICATION_VERSION, RecordingIngestionError,
    parse_specification, source_declaration_status,
)
from ..io.corpus_inventory import sha256_file
from ..io.independent_outing_intake import read_strict_json_with_bytes
from ..io.recording_ingestion import (
    TOPIC_LIMITS, file_state, inconclusive_readiness, indexed_metadata, inspect_recording_readiness, sha256_stream,
)
from ..io.recording_pair_feasibility import MAX_CHUNK_BYTES, MAX_SPOOL_BYTES, STORAGE_READER_IMPLEMENTATION, RecordingReadError, ResourceLimitError, decoder_types
from ..io.reports import write_strict_json
from .recording_pair_feasibility import _available_memory_bytes, MINIMUM_AVAILABLE_MEMORY_BYTES, MINIMUM_FREE_SCRATCH_BYTES

LOGGER = logging.getLogger(__name__)
REGISTRATION_NAME = "registration.json"
SPECIFICATION_NAME = "source_specification.json"
REPORT_NAME = "recording_readiness.json"


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _new_output(path):
    output = path.expanduser().absolute()
    if output.exists():
        raise RecordingIngestionError("new_absent_output_directory_required")
    return output


def _runtime(*, include_compression=False):
    versions = {"python": platform.python_version()}
    names = ("mcap", "mcap-protobuf-support", "protobuf", "numpy")
    for name in names + (("zstandard", "lz4") if include_compression else ()):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    package = Path(__file__).resolve().parents[1]
    hashes = {p.relative_to(package).as_posix(): sha256_file(p) for p in sorted(package.rglob("*.py"))}
    return {"runtime_versions": versions,
            "runtime_source_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def run_prepare(arguments):
    """Make a truthful one-recording draft from an existing absolute local file."""
    output = _new_output(arguments.output_specification)
    path = arguments.mcap_file.expanduser().resolve(strict=True)
    if file_state(path)[2] <= 0:
        raise RecordingIngestionError("nonempty_mcap_file_required")
    source = dict.fromkeys(SOURCE_FIELDS)
    source.update(merged_input_mcap_count=arguments.merged_input_mcap_count,
                  source_recording_id_private=arguments.source_recording_id,
                  export_settings_private=arguments.export_settings)
    specification = {"schema_version": SPECIFICATION_VERSION, "batch_id": arguments.batch_id,
        "purpose": "development_only", "recordings": [{"recording_id": arguments.recording_id,
        "local_path_private": str(path), "source": source}]}
    parse_specification(specification)
    write_strict_json(output, specification)
    LOGGER.info("Prepared one development-only declaration; unavailable provenance stays null")
    return specification, 0


def run_registration(arguments):
    output = _new_output(arguments.output_directory)
    specification, raw = read_strict_json_with_bytes(arguments.specification.expanduser())
    parse_specification(specification)
    rows, seen_paths, seen_hashes, states = [], set(), set(), []
    for index, row in enumerate(specification["recordings"], 1):
        path = Path(row["local_path_private"]).resolve(strict=True)
        if path in seen_paths:
            raise RecordingIngestionError("duplicate_resolved_mcap_path")
        seen_paths.add(path)
        LOGGER.info("Hashing recording %d/%d; large files can take several minutes", index, len(specification["recordings"]))
        with path.open("rb") as stream:
            before = file_state(stream=stream)
            if before[2] <= 0:
                raise RecordingIngestionError("nonempty_mcap_file_required")
            digest = sha256_stream(stream)
            if file_state(stream=stream) != before or file_state(path) != before:
                raise RecordingIngestionError("file_changed_during_registration")
        if digest in seen_hashes:
            raise RecordingIngestionError("duplicate_raw_sha256_in_batch")
        seen_hashes.add(digest)
        states.append((path, before))
        rows.append({"recording_id": row["recording_id"], "canonical_path_private": str(path),
                     "raw_sha256": digest, "size_bytes": before[2]})
    if any(file_state(path) != state for path, state in states):
        raise RecordingIngestionError("file_changed_before_registration_publish")
    registration = {"contract_revision": CONTRACT_REVISION, "purpose": "development_only",
        "batch_id": specification["batch_id"], "source_specification_sha256": hashlib.sha256(raw).hexdigest(),
        "recordings": rows, **_runtime()}
    output.mkdir(parents=True, exist_ok=False)
    (output / SPECIFICATION_NAME).write_bytes(raw)
    write_strict_json(output / REGISTRATION_NAME, registration)
    LOGGER.info("Registered %d technical recordings; no MCAP payload decoded", len(rows))
    return registration, 0


def _registration(directory):
    directory = directory.expanduser().resolve(strict=True)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != {SPECIFICATION_NAME, REGISTRATION_NAME}:
        raise RecordingIngestionError("exact_registration_file_set_required")
    specification, spec_bytes = read_strict_json_with_bytes(directory / SPECIFICATION_NAME)
    parse_specification(specification)
    registration, registration_bytes = read_strict_json_with_bytes(directory / REGISTRATION_NAME)
    expected_keys = {"contract_revision", "purpose", "batch_id", "source_specification_sha256", "recordings",
                     "runtime_versions", "runtime_source_sha256"}
    if (not isinstance(registration, dict) or set(registration) != expected_keys or
            registration["contract_revision"] != CONTRACT_REVISION or registration["purpose"] != "development_only" or
            registration["batch_id"] != specification["batch_id"] or
            registration["source_specification_sha256"] != hashlib.sha256(spec_bytes).hexdigest()):
        raise RecordingIngestionError("registration_lineage_mismatch")
    versions = registration["runtime_versions"]
    if (not _sha256(registration["runtime_source_sha256"]) or not isinstance(versions, dict) or
            set(versions) != {"python", "mcap", "mcap-protobuf-support", "protobuf", "numpy"} or
            not isinstance(versions["python"], str) or
            any(v is not None and (not isinstance(v, str) or not v) for v in versions.values())):
        raise RecordingIngestionError("invalid_registration_runtime_fingerprint")
    rows = registration["recordings"]
    if not isinstance(rows, list) or len(rows) != len(specification["recordings"]):
        raise RecordingIngestionError("registration_recording_coverage_mismatch")
    identities, paths = set(), set()
    for row, declared in zip(rows, specification["recordings"]):
        if (not isinstance(row, dict) or set(row) != {"recording_id", "canonical_path_private", "raw_sha256", "size_bytes"} or
                row["recording_id"] != declared["recording_id"] or
                not _sha256(row["raw_sha256"]) or
                type(row["size_bytes"]) is not int or row["size_bytes"] <= 0):
            raise RecordingIngestionError("invalid_registered_identity")
        path = Path(declared["local_path_private"]).resolve(strict=True)
        if row["canonical_path_private"] != str(path) or path in paths or row["raw_sha256"] in identities:
            raise RecordingIngestionError("registration_path_or_identity_mismatch")
        paths.add(path)
        identities.add(row["raw_sha256"])
        if file_state(path)[2] != row["size_bytes"]:
            raise RecordingIngestionError("registered_raw_size_changed")
    return specification, registration, hashlib.sha256(registration_bytes).hexdigest()


def _resources(scratch):
    available = _available_memory_bytes()
    free = shutil.disk_usage(scratch).free
    if available < MINIMUM_AVAILABLE_MEMORY_BYTES:
        raise RecordingIngestionError("available_memory_below_6gib")
    if free < MINIMUM_FREE_SCRATCH_BYTES:
        raise RecordingIngestionError("scratch_free_space_below_10gib")
    return {"mem_available_bytes": available, "scratch_free_bytes": free}


def _preserved_readiness(arguments, registration, digest):
    path = getattr(arguments, "preserved_readiness_report", None)
    if path is None:
        return None, None
    report, raw = read_strict_json_with_bytes(path.expanduser())
    if (not isinstance(report, dict) or report.get("contract_revision") != CONTRACT_REVISION or
            report.get("purpose") != "development_only_recording_readiness" or
            report.get("status") != "inconclusive" or report.get("batch_id") != registration["batch_id"] or
            report.get("registration_sha256") != digest or
            report.get("source_specification_sha256") != registration["source_specification_sha256"] or
            report.get("technical_recording_count") != 1 or report.get("independent_outing_count") is not None or
            any(report.get(key) is not False for key in ("roles_assigned", "cohort_lock_created", "model_fitted",
                "residual_profiles_constructed", "numeric_conditions_exported", "raw_cache_deletion_authorized"))):
        raise RecordingIngestionError("preserved_readiness_lineage_mismatch")
    rows = report.get("recordings")
    if not isinstance(rows, list) or len(rows) != 1 or len(registration["recordings"]) != 1:
        raise RecordingIngestionError("one_zstd_predecessor_recording_required")
    row, identity = rows[0], registration["recordings"][0]
    if (not isinstance(row, dict) or any(row.get(key) != identity[key] for key in ("recording_id", "raw_sha256", "size_bytes")) or
            row.get("status") != "inconclusive" or row.get("failure_code") != "ZstdError" or
            not isinstance(row.get("indexed_metadata"), dict) or
            any(key not in row or row[key] is not None for key in ("counts", "diagnostics", "odometry", "source_clock_order",
                "log_clock_order", "sensor_geometry_support", "complete_condition_support", "condition_failure_counts"))):
        raise RecordingIngestionError("preserved_zstd_readiness_identity_or_state_mismatch")
    return report, hashlib.sha256(raw).hexdigest()


def run_readiness(arguments):
    output = _new_output(arguments.output_directory)
    specification, registration, digest = _registration(arguments.registration_directory)
    preserved, preserved_digest = _preserved_readiness(arguments, registration, digest)
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir():
        raise RecordingIngestionError("existing_scratch_directory_required")
    resources = _resources(scratch)
    decoder_types()
    runtime = _runtime(include_compression=True)
    results, states = [], []
    for index, (identity, declaration) in enumerate(zip(registration["recordings"], specification["recordings"]), 1):
        path = Path(identity["canonical_path_private"])
        LOGGER.info("Verifying raw bytes %d/%d; large files can take several minutes", index, len(registration["recordings"]))
        with path.open("rb") as stream:
            before = file_state(stream=stream)
            if before[2] != identity["size_bytes"] or sha256_stream(stream) != identity["raw_sha256"]:
                raise RecordingIngestionError("registered_raw_hash_or_size_changed")
            if file_state(stream=stream) != before or file_state(path) != before:
                raise RecordingIngestionError("file_changed_during_raw_verification")
            metadata = None
            try:
                _resources(scratch)
                metadata, code = indexed_metadata(stream)
                if preserved is not None and metadata != preserved["recordings"][index - 1]["indexed_metadata"]:
                    raise RecordingReadError("preserved_indexed_metadata_mismatch")
                if code is not None:
                    result = inconclusive_readiness(code)
                else:
                    LOGGER.info("Auditing recording %d/%d with disk-backed geometry and odometry", index, len(registration["recordings"]))
                    result = inspect_recording_readiness(path, stream, scratch)
            except (ResourceLimitError, RecordingReadError, RecordingIngestionError) as error:
                # These are only MPR-authored, payload-free codes.
                code = str(error)
                result = inconclusive_readiness(code)
            except MemoryError:
                result = inconclusive_readiness("memory_limit")
            except Exception as error:
                result = inconclusive_readiness(type(error).__name__)
            try:
                unchanged = file_state(stream=stream) == before and file_state(path) == before
            except OSError:
                unchanged = False
            if not unchanged:
                result, metadata = inconclusive_readiness("file_changed_during_audit"), None
        states.append((path, before))
        results.append({"recording_id": identity["recording_id"], "raw_sha256": identity["raw_sha256"],
            "size_bytes": identity["size_bytes"], "source_declaration_status": source_declaration_status(declaration["source"]),
            "indexed_metadata": metadata, **result})
    for row, (path, before) in zip(results, states):
        try:
            unchanged = file_state(path) == before
        except OSError:
            unchanged = False
        if not unchanged:
            row.update(inconclusive_readiness("file_changed_before_report_publish"), indexed_metadata=None)
    # Raw counts must remain reproducible from the preserved metadata snapshot.
    # Check its exact bytes again after a potentially long multi-recording run.
    directory = arguments.registration_directory.expanduser().resolve()
    try:
        metadata_unchanged = ({p.name for p in directory.iterdir()} == {SPECIFICATION_NAME, REGISTRATION_NAME} and
            sha256_file(directory / REGISTRATION_NAME) == digest and
            sha256_file(directory / SPECIFICATION_NAME) == registration["source_specification_sha256"])
    except OSError:
        metadata_unchanged = False
    if not metadata_unchanged:
        for row in results:
            row.update(inconclusive_readiness("registration_changed_before_report_publish"), indexed_metadata=None)
    if preserved_digest is not None:
        try:
            predecessor_unchanged = sha256_file(arguments.preserved_readiness_report.expanduser()) == preserved_digest
        except OSError:
            predecessor_unchanged = False
        if not predecessor_unchanged:
            for row in results:
                row.update(inconclusive_readiness("preserved_readiness_changed_before_report_publish"), indexed_metadata=None)
    complete = all(row["status"] == "complete" for row in results)
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    report = {"contract_revision": CONTRACT_REVISION, "purpose": "development_only_recording_readiness",
        "batch_id": registration["batch_id"], "status": "complete" if complete else "inconclusive",
        "registration_sha256": digest, "source_specification_sha256": registration["source_specification_sha256"],
        "reader_implementation": STORAGE_READER_IMPLEMENTATION, "preserved_readiness_report_sha256": preserved_digest,
        "technical_recording_count": len(results), "independent_outing_count": None,
        "roles_assigned": False, "cohort_lock_created": False, "model_fitted": False,
        "residual_profiles_constructed": False, "numeric_conditions_exported": False,
        "recorded_input_causality_checked_for_all_recordings": complete,
        "physical_input_availability_proven": False, "reference_independence_proven": False,
        "raw_cache_deletion_authorized": False, **runtime,
        "execution_limits": {"topic_message_limits": TOPIC_LIMITS, "maximum_chunk_bytes": MAX_CHUNK_BYTES,
            "maximum_spool_bytes": MAX_SPOOL_BYTES,
            "process_address_space_soft_limit_bytes": None if soft == resource.RLIM_INFINITY else soft,
            "minimum_mem_available_bytes": MINIMUM_AVAILABLE_MEMORY_BYTES,
            "minimum_scratch_free_bytes": MINIMUM_FREE_SCRATCH_BYTES},
        "resources_at_start": resources, "recordings": results,
        "interpretation": "EDP/RLMB geometry and six-input readiness under the existing H100, anchor, ungated source-time pairing, 50 ms speed and storage-order sequence rules. RLMB remains a pseudo-reference. Merged chunks, source-recording identifiers and source declarations do not establish independent outings. Missing geometry in a completed stream and an inconclusive execution are distinct. No numeric conditions, residual archive, split, fit, raw deletion or final-data admission."}
    output.mkdir(parents=True, exist_ok=False)
    write_strict_json(output / REPORT_NAME, report)
    LOGGER.info("Readiness %s; no residual archive, outing roles or model produced", report["status"])
    return report, 0 if complete else 3
