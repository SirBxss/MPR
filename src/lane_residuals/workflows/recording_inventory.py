"""Registered-file, metadata-only inventory independent of residual targets."""

from __future__ import annotations

import logging
from pathlib import Path
import resource

from ..domain.recording_ingestion import RecordingIngestionError, source_declaration_status
from ..io.corpus_inventory import sha256_file
from ..io.recording_ingestion import file_state, sha256_stream
from ..io.recording_inventory import (
    INVENTORY_REVISION, MAX_RECORD_BYTES, MAX_SUMMARY_BYTES, MAX_SUMMARY_RECORDS,
    MAX_SUMMARY_SECONDS, MAX_TEXT_BYTES, read_inventory,
)
from ..io.reports import write_strict_json
from .recording_ingestion import (
    REGISTRATION_NAME, SPECIFICATION_NAME, _new_output, _registration, _resources, _runtime,
)
from .recording_pair_feasibility import MINIMUM_AVAILABLE_MEMORY_BYTES, MINIMUM_FREE_SCRATCH_BYTES

LOGGER = logging.getLogger(__name__)
REPORT_NAME = "recording_inventory.json"


def _inconclusive(row, code):
    row.update(status="inconclusive", failure_code=code, inventory=None)


def run_inventory(arguments):
    if arguments.output_directory.expanduser().is_symlink():
        raise RecordingIngestionError("new_absent_output_directory_required")
    output = _new_output(arguments.output_directory)
    specification, registration, digest = _registration(arguments.registration_directory)
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir():
        raise RecordingIngestionError("existing_scratch_directory_required")
    resources = _resources(scratch)
    runtime = _runtime()
    results, states = [], []
    for index, (identity, declaration) in enumerate(zip(registration["recordings"], specification["recordings"]), 1):
        path = Path(identity["canonical_path_private"])
        LOGGER.info("Verifying raw bytes %d/%d for inventory; large files can take several minutes", index, len(registration["recordings"]))
        with path.open("rb") as stream:
            before = file_state(stream=stream)
            if before[2] != identity["size_bytes"] or sha256_stream(stream) != identity["raw_sha256"]:
                raise RecordingIngestionError("registered_raw_hash_or_size_changed")
            if file_state(stream=stream) != before or file_state(path) != before:
                raise RecordingIngestionError("file_changed_during_raw_verification")
            row = {"recording_id": identity["recording_id"], "raw_sha256": identity["raw_sha256"],
                "size_bytes": identity["size_bytes"],
                "source_declaration_status": source_declaration_status(declaration["source"]),
                "status": "complete", "failure_code": None, "inventory": None}
            try:
                _resources(scratch)
                LOGGER.info("Inventorying summary %d/%d; no message payload decoding", index, len(registration["recordings"]))
                row["inventory"] = read_inventory(stream, before[2])
            except RecordingIngestionError as error:
                _inconclusive(row, error.code)
            except MemoryError:
                _inconclusive(row, "memory_limit")
            except Exception as error:
                _inconclusive(row, type(error).__name__)
            try:
                unchanged = file_state(stream=stream) == before and file_state(path) == before
            except OSError:
                unchanged = False
            if not unchanged:
                _inconclusive(row, "file_changed_during_inventory")
        states.append((path, before))
        results.append(row)
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
            sha256_file(directory / REGISTRATION_NAME) == digest and
            sha256_file(directory / SPECIFICATION_NAME) == registration["source_specification_sha256"])
    except OSError:
        unchanged = False
    if not unchanged:
        for row in results:
            _inconclusive(row, "registration_changed_before_report_publish")
    complete = all(row["status"] == "complete" for row in results)
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    report = {"contract_revision": INVENTORY_REVISION, "purpose": "development_only_recording_inventory",
        "batch_id": registration["batch_id"], "status": "complete" if complete else "inconclusive",
        "registration_sha256": digest, "source_specification_sha256": registration["source_specification_sha256"],
        "technical_recording_count": len(results), "independent_outing_count": None,
        "message_payloads_decoded": False, "geometry_readiness_assessed": False,
        "residual_profiles_constructed": False, "numeric_conditions_exported": False,
        "reference_independence_proven": False, "model_fitted": False, "roles_assigned": False,
        "raw_cache_deletion_authorized": False, **runtime,
        "execution_limits": {"maximum_record_bytes": MAX_RECORD_BYTES, "maximum_summary_bytes": MAX_SUMMARY_BYTES,
            "maximum_summary_records_per_section": MAX_SUMMARY_RECORDS,
            "maximum_text_bytes": MAX_TEXT_BYTES, "maximum_summary_seconds_per_recording": MAX_SUMMARY_SECONDS,
            "process_address_space_soft_limit_bytes": None if soft == resource.RLIM_INFINITY else soft,
            "minimum_mem_available_bytes": MINIMUM_AVAILABLE_MEMORY_BYTES,
            "minimum_scratch_free_bytes": MINIMUM_FREE_SCRATCH_BYTES},
        "resources_at_start": resources, "recordings": results,
        "interpretation": "Complete means the bounded MCAP summary inventory completed on verified registered bytes. Counts and chunk sizes are advertised, not decoded. Nonzero summary CRC is checked; zero means unavailable. Message chunks, their CRCs, file-level metadata values and attachments are not decoded or validated. Unknown encodings need a separate adapter. Topic presence does not establish geometry, residual pairs, clocks, producer identity, ground truth, independent outings or deletion readiness."}
    output.mkdir(parents=True, exist_ok=False)
    write_strict_json(output / REPORT_NAME, report)
    LOGGER.info("Inventory %s; no geometry, residuals or model produced", report["status"])
    return report, 0 if complete else 3
