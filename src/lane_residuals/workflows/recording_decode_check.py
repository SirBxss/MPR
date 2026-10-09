"""Verified inventory to selected-stream decoding, with no scientific adapter."""

from __future__ import annotations

import logging
import json
from pathlib import Path
import resource

from ..domain.recording_ingestion import RecordingIngestionError, source_declaration_status
from ..io.corpus_inventory import sha256_file
from ..io.recording_ingestion import file_state, sha256_stream
from ..io.recording_inventory import read_inventory
from ..io import recording_decode_check as io
from ..io.reports import write_strict_json
from .recording_ingestion import REGISTRATION_NAME, SPECIFICATION_NAME, _new_output, _registration, _resources, _runtime
from .recording_pair_feasibility import MINIMUM_AVAILABLE_MEMORY_BYTES, MINIMUM_FREE_SCRATCH_BYTES

LOGGER = logging.getLogger(__name__)
REPORT_NAME = "recording_decode_check.json"


def _inconclusive(row, code, context=None):
    # Keep the first cause and explicit subsequent identity invalidations.
    if row["failure_code"] is None:
        row.update(failure_code=code, reader_failure_context=context)
    elif code != row["failure_code"] and code not in row["invalidation_codes"]:
        row["invalidation_codes"].append(code)
    row.update(status="inconclusive", decode_check=None)


def run_decode_check(arguments):
    if arguments.output_directory.expanduser().is_symlink():
        raise RecordingIngestionError("new_absent_output_directory_required")
    output = _new_output(arguments.output_directory)
    topics = io.selected_topics(arguments.topic)
    specification, registration, digest = _registration(arguments.registration_directory)
    predecessor = arguments.preserved_inventory_report.expanduser()
    preserved, preserved_hash = io.read_predecessor(predecessor, registration, digest)
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir():
        raise RecordingIngestionError("existing_scratch_directory_required")
    resources = _resources(scratch)
    io.check_dependencies()
    runtime = _runtime(include_compression=True)
    results, states = [], []
    for index, (identity, declaration, old) in enumerate(zip(registration["recordings"], specification["recordings"], preserved), 1):
        path = Path(identity["canonical_path_private"])
        LOGGER.info("Verifying raw bytes %d/%d for decode check; large files can take several minutes", index, len(preserved))
        with path.open("rb") as stream:
            before = file_state(stream=stream)
            if before[2] != identity["size_bytes"] or sha256_stream(stream) != identity["raw_sha256"]:
                raise RecordingIngestionError("registered_raw_hash_or_size_changed")
            if file_state(stream=stream) != before or file_state(path) != before:
                raise RecordingIngestionError("file_changed_during_raw_verification")
            row = {"recording_id": identity["recording_id"], "raw_sha256": identity["raw_sha256"], "size_bytes": identity["size_bytes"],
                "source_declaration_status": source_declaration_status(declaration["source"]), "status": "complete",
                "failure_code": None, "invalidation_codes": [], "reader_failure_context": None, "decode_check": None}
            try:
                _resources(scratch)
                fresh = read_inventory(stream, before[2])
                # JSON comparison preserves number/bool types, unlike dict equality.
                if (json.dumps(fresh, sort_keys=True, allow_nan=False) != json.dumps(old["inventory"], sort_keys=True, allow_nan=False) or
                        old.get("source_declaration_status") != row["source_declaration_status"]):
                    raise RecordingIngestionError("decode_preserved_inventory_mismatch")
                LOGGER.info("Checking selected streams %d/%d with disk-backed indexes; no geometry", index, len(preserved))
                row["decode_check"] = io.check_decoding(stream, before[2], fresh, topics, scratch, lambda: _resources(scratch))
            except Exception as error:
                if isinstance(error, RecordingIngestionError) and error.code == "decode_preserved_inventory_mismatch":
                    raise  # A drifted dependency must not produce a successor report.
                _inconclusive(row, io.failure_code(error), getattr(error, "reader_failure_context", None))
            try:
                unchanged = file_state(stream=stream) == before and file_state(path) == before
            except OSError:
                unchanged = False
            if not unchanged:
                _inconclusive(row, "file_changed_during_decode_check")
        results.append(row); states.append((path, before))
    for row, (path, before) in zip(results, states):
        try:
            unchanged = file_state(path) == before
        except OSError:
            unchanged = False
        if not unchanged:
            _inconclusive(row, "file_changed_before_report_publish")
    directory = arguments.registration_directory.expanduser().resolve()
    try:
        unchanged = ({p.name for p in directory.iterdir()} == {REGISTRATION_NAME, SPECIFICATION_NAME} and
            sha256_file(directory/REGISTRATION_NAME) == digest and
            sha256_file(directory/SPECIFICATION_NAME) == registration["source_specification_sha256"])
    except OSError:
        unchanged = False
    if not unchanged:
        for row in results:
            _inconclusive(row, "registration_changed_before_report_publish")
    try:
        unchanged = sha256_file(predecessor) == preserved_hash
    except OSError:
        unchanged = False
    if not unchanged:
        for row in results:
            _inconclusive(row, "preserved_inventory_changed_before_report_publish")
    complete = all(row["status"] == "complete" for row in results)
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    report = {"contract_revision": io.DECODE_REVISION, "purpose": "development_only_recording_decode_check",
        "batch_id": registration["batch_id"], "status": "complete" if complete else "inconclusive",
        "registration_sha256": digest, "source_specification_sha256": registration["source_specification_sha256"],
        "preserved_inventory_report_sha256": preserved_hash, "selected_topics": topics,
        "reader_implementation": io.READER_IMPLEMENTATION, "selected_payload_decoding_enabled": True,
        "selected_chunk_crc_validation_enabled": True, "technical_recording_count": len(results), "independent_outing_count": None,
        "geometry_readiness_assessed": False, "residual_profiles_constructed": False, "numeric_conditions_exported": False,
        "reference_independence_proven": False, "model_fitted": False, "roles_assigned": False, "raw_cache_deletion_authorized": False,
        **runtime, "resources_at_start": resources,
        "execution_limits": {"maximum_selected_topics": io.MAX_TOPICS, "maximum_messages_per_topic": io.MAX_TOPIC_MESSAGES,
            "maximum_selected_messages_per_recording": io.MAX_TOTAL_MESSAGES, "maximum_selected_chunk_bytes": io.MAX_CHUNK_BYTES,
            "maximum_index_database_bytes": io.MAX_INDEX_BYTES, "maximum_selected_schema_bytes": io.MAX_SCHEMA_BYTES,
            "maximum_selected_schema_count": io.MAX_SCHEMAS, "maximum_selected_channel_count": io.MAX_CHANNELS,
            "maximum_selected_payload_bytes": io.MAX_PAYLOAD_BYTES, "maximum_decode_seconds_per_recording": io.MAX_DECODE_SECONDS,
            "maximum_preserved_inventory_bytes": io.MAX_PREDECESSOR_BYTES,
            "process_address_space_soft_limit_bytes": None if soft == resource.RLIM_INFINITY else soft,
            "minimum_mem_available_bytes": MINIMUM_AVAILABLE_MEMORY_BYTES, "minimum_scratch_free_bytes": MINIMUM_FREE_SCRATCH_BYTES},
        "recordings": results,
        "interpretation": "Complete means the selected indexed streams decoded and reconciled with the preserved inventory on freshly verified registered bytes. Nonzero stored CRCs are validated for selected chunks; zero is unavailable. Unselected payloads are not decoded. This is not a complete-file integrity certificate, scientific schema/geometry validation, H100 residual support, causal-input check, ground truth, independent-outing admission, model fit or deletion readiness. Inconclusive full-stream counts are null; failure context is execution progress only."}
    output.mkdir(parents=True, exist_ok=False)
    write_strict_json(output/REPORT_NAME, report)
    LOGGER.info("Decode check %s; no geometry, residuals or model produced", report["status"])
    return report, 0 if complete else 3
