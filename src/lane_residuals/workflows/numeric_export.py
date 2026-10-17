"""Versioned registered MCAP-to-numeric export and separate raw-free validation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time

import numpy as np

from ..domain import numeric_export as policy
from ..domain.recording_ingestion import RecordingIngestionError, source_declaration_status
from ..io import recording_decode_check as decoder
from ..io.bounded_recording_readiness import REVISION as READINESS_REVISION, ScientificSink
from ..io.numeric_export_inputs import equal, load_inputs, read_bytes
from ..io.numeric_residuals import NumericObserver, collect_candidates
from ..io.recording_ingestion import file_state, sha256_stream
from ..io.recording_inventory import read_inventory
from ..io.recording_readiness_resources import Observations, Workspace, check_configuration, scientific_failure
from . import bounded_recording_readiness as bounded
from .recording_ingestion import _new_output, _runtime

LOGGER = logging.getLogger(__name__)
SEMANTICS_BASIS = "reviewed_interface_2_3_same_major_compatibility_assumption_and_unconfirmed_5m_confidence_bucket"


def limits():
    result = bounded._limits()
    result.update(minimum_initial_scratch_free_bytes=bounded.INITIAL_SCRATCH_BYTES+policy.ARTIFACT_RESERVE_BYTES,
        maximum_aggregate_advertised_edp_messages=policy.MAX_EDP, maximum_candidate_audit_bytes=policy.MAX_AUDIT_BYTES,
        maximum_numeric_summary_bytes=policy.MAX_SUMMARY_BYTES, maximum_npz_compressed_bytes=policy.MAX_NPZ_BYTES,
        maximum_npz_uncompressed_bytes=policy.MAX_NPZ_BYTES, maximum_artifact_staging_bytes=policy.ARTIFACT_RESERVE_BYTES,
        maximum_publication_seconds=policy.PUBLICATION_SECONDS, maximum_standalone_validation_seconds=policy.PUBLICATION_SECONDS)
    return result


def _resources(scratch, *, initial=False):
    result = bounded._resources(scratch)
    policy.require(not initial or result["scratch_free_bytes"] >= bounded.INITIAL_SCRATCH_BYTES+policy.ARTIFACT_RESERVE_BYTES,
        "numeric_initial_scratch_below_19point5gib")
    return result


def _checkpoint(deadline, scratch=None):
    policy.require(time.monotonic() <= deadline, "numeric_serialization_or_validation_time_limit")
    if scratch is not None:
        _resources(scratch)


def _write_json(path, value, maximum, checkpoint):
    encoder = json.JSONEncoder(sort_keys=True, allow_nan=False, separators=(",", ":"))
    count, pending = 0, 0
    with path.open("xb") as stream:
        for index, fragment in enumerate(encoder.iterencode(value)):
            raw = fragment.encode("utf-8")
            count += len(raw);pending += len(raw)
            policy.require(count+1 <= maximum, "numeric_json_publication_size_limit")
            if pending >= 1024**2 or index % 1024 == 0:
                checkpoint();pending = 0
            stream.write(raw)
        stream.write(b"\n");stream.flush();os.fsync(stream.fileno())
    checkpoint()


def _digest(path, maximum, checkpoint):
    raw, _ = read_bytes(path, maximum, checkpoint)
    return hashlib.sha256(raw).hexdigest()


def _summary(context, rows, candidates, start_resources, complete):
    for row in rows:
        row["outcome_exposure"] = dict(policy.EXPOSURE) if complete else None
    support = policy.build_numeric_archive(candidates)[1] if complete else None
    return {"contract_revision": policy.REVISION, "purpose": policy.PURPOSE, "status": "complete" if complete else "inconclusive",
        "failure_code": None if complete else next((r["failure_code"] for r in rows if r["failure_code"]), "numeric_publication_failed"),
        "batch_id": context.registration["batch_id"], "registration_sha256": context.registration_hash,
        "source_specification_sha256": context.registration["source_specification_sha256"], **context.hashes,
        "preserved_readiness_contract_revision": READINESS_REVISION, "preserved_readiness_runtime_source_sha256": context.readiness["runtime_source_sha256"],
        **context.runtime, "reader_implementation": decoder.READER_IMPLEMENTATION, "scientific_policy_revision": policy.REVISION,
        "estimate_admission_policy": policy.admission_policy(), "confidence_bucket_semantics": policy.CONFIDENCE_SEMANTICS,
        "outcome_exposure_policy": policy.EXPOSURE_POLICY, "schema_semantics_basis": SEMANTICS_BASIS,
        "schema_semantics_deployed_producer_retraced": False, "resources_at_start": start_resources, "execution_limits": limits(),
        "technical_recording_count": len(rows), "independent_outing_count": None, "roles_assigned": False,
        "cohort_lock_created": False, "model_fitted": False, "standardizers_fitted": False, "residuals_exported": complete,
        "numeric_conditions_exported": complete,
        "recorded_input_causality_checked_for_all_recordings": all(r["status"] == "complete" and r["recorded_input_causality_checked"] for r in rows),
        "physical_input_availability_proven": False, "reference_independence_proven": False, "raw_cache_deletion_authorized": False,
        "pre_residual_candidate_count": len(candidates) if complete else None,
        "pre_residual_complete_condition_count": sum(r["conditions"] is not None for r in candidates) if complete else None,
        "condition_failure_counts": policy.failures(candidates, "condition_failure_codes") if complete else None,
        "residual_failure_counts": policy.failures(candidates, "residual_failure_code") if complete else None,
        "support": support, "recordings": rows, "artifacts_sha256": {},
        "interpretation": "Development-only recording-local SENSOR EDP minus spatially aligned RLMB pseudo-residuals. Permanent development reservation and actual complete publication are distinct. No independent outing admission, split, fit, physical ground truth or raw retirement. Confidence width and same-major compatibility remain explicit assumptions."}


def _row(identity, declaration):
    return {"recording_id": identity["recording_id"], "raw_sha256": identity["raw_sha256"], "size_bytes": identity["size_bytes"],
        "source_declaration_status": source_declaration_status(declaration["source"]), "status": "complete", "failure_code": None,
        "invalidation_codes": [], "reader_failure_context": None, "binding_observations": None, "stream_integrity": None,
        "readiness": None, "condition_availability": "not_assessed", "recorded_input_causality_checked": False,
        "readiness_matches_preserved": None, "execution_observations": None, "candidate_start": None, "candidate_stop": None,
        "residual_failure_counts": None, "support": None, "outcome_exposure": None, "observer_failure_counts": None}


def _invalidate(row, code, context=None):
    bounded._inconclusive(row, code, context)
    if code in ("numeric_preserved_readiness_mismatch", "numeric_staged_readiness_mismatch"):
        row["readiness_matches_preserved"] = False
    row.update(candidate_start=None, candidate_stop=None, residual_failure_counts=None, support=None)


def _raw_unchanged(states):
    for path, state in states:
        policy.require(bounded._same_file(path, state), "numeric_raw_changed_before_publication")


def _preflight(arguments, context):
    output = _new_output(arguments.output_directory)
    policy.require(not output.is_symlink(), "new_absent_output_directory_required")
    parent = output.parent.resolve(strict=True)
    policy.require(parent.is_dir(), "numeric_existing_output_parent_required")
    scratch = arguments.scratch_directory.expanduser().resolve(strict=True)
    policy.require(scratch.is_dir(), "existing_scratch_directory_required")
    policy.require(parent.stat().st_dev == scratch.stat().st_dev, "numeric_output_scratch_device_mismatch")
    registration = arguments.registration_directory.expanduser().resolve(strict=True)
    for target in (output.resolve(), scratch):
        policy.require(not target.is_relative_to(registration), "numeric_output_or_scratch_overlaps_registration")
    for path in context.states:
        policy.require(not path.resolve().is_relative_to(output.resolve()) and not output.resolve().is_relative_to(path.resolve()), "numeric_output_overlaps_input")
    for identity in context.registration["recordings"]:
        path = Path(identity["canonical_path_private"])
        policy.require(not output.resolve().is_relative_to(path) and not path.is_relative_to(output.resolve()), "numeric_output_overlaps_raw")
    start_resources = _resources(scratch, initial=True)
    decoder.check_dependencies()
    import zstandard, lz4.frame  # noqa: F401; resolve native codecs before raw access.
    check_configuration(scratch)
    return output, scratch, start_resources


def _publish(output, scratch, context, rows, candidates, start_resources, raw_states, deadline):
    from ..io.numeric_archive import validate_archive
    # Reserve five seconds inside the same 300-second cap for a null failure marker.
    checkpoint = lambda: _checkpoint(deadline-5, scratch)
    complete = all(row["status"] == "complete" for row in rows)
    summary = _summary(context, rows, candidates, start_resources, complete)
    owned_output = False
    installed = {}
    try:
        with tempfile.TemporaryDirectory(prefix="mpr-numeric-publication-", dir=scratch) as temporary:
            staging = Path(temporary)
            def storage_check():
                checkpoint()
                total = sum(max(p.stat().st_size, p.stat().st_blocks*512) for folder in (staging, output) if folder.exists() for p in folder.iterdir() if p.is_file())
                policy.require(total <= policy.ARTIFACT_RESERVE_BYTES, "numeric_artifact_staging_limit")
            if complete:
                arrays, _ = policy.build_numeric_archive(candidates)
                policy.require(sum(a.nbytes+16_384 for a in arrays.values()) <= policy.MAX_NPZ_BYTES, "numeric_npz_uncompressed_size_limit")
                storage_check()
                # Store members one at a time, checking both size and deadline between them.
                import zipfile
                with zipfile.ZipFile(staging/policy.ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, array in arrays.items():
                        storage_check()
                        with archive.open(name+".npy", "w", force_zip64=True) as stream:
                            np.lib.format.write_array(stream, array, allow_pickle=False)
                        policy.require((staging/policy.ARCHIVE).stat().st_size <= policy.MAX_NPZ_BYTES, "numeric_npz_compressed_size_limit")
                with (staging/policy.ARCHIVE).open("rb") as stream:
                    os.fsync(stream.fileno())
                _write_json(staging/policy.AUDIT, {"contract_revision": policy.REVISION, "rows": [policy.audit_row(r) for r in candidates]}, policy.MAX_AUDIT_BYTES, storage_check)
                summary["artifacts_sha256"] = {name: _digest(staging/name, maximum, storage_check)
                    for name, maximum in ((policy.AUDIT, policy.MAX_AUDIT_BYTES), (policy.ARCHIVE, policy.MAX_NPZ_BYTES))}
            _write_json(staging/policy.SUMMARY, summary, policy.MAX_SUMMARY_BYTES, storage_check)
            if complete:
                validate_archive(staging, _digest(staging/policy.SUMMARY, policy.MAX_SUMMARY_BYTES, storage_check), context, checkpoint=storage_check)
            context.unchanged(storage_check)
            _raw_unchanged(raw_states)
            policy.require(output.parent.resolve().stat().st_dev == scratch.stat().st_dev, "numeric_output_scratch_device_mismatch")
            output.mkdir(exist_ok=False)
            owned_output = True
            policy.require(output.stat().st_dev == scratch.stat().st_dev and not output.is_symlink(), "numeric_output_scratch_device_mismatch")
            for name in (policy.AUDIT, policy.ARCHIVE) if complete else ():
                os.replace(staging/name, output/name)
                installed[output/name] = file_state(output/name)
                equal(_digest(output/name, policy.MAX_AUDIT_BYTES if name == policy.AUDIT else policy.MAX_NPZ_BYTES, storage_check), summary["artifacts_sha256"][name], "numeric_artifact_changed_before_publication")
            context.unchanged(storage_check)
            _raw_unchanged(raw_states)
            storage_check()
            os.replace(staging/policy.SUMMARY, output/policy.SUMMARY)
            installed[output/policy.SUMMARY] = file_state(output/policy.SUMMARY)
            descriptor = os.open(output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return summary, 0 if complete else 3
    except BaseException:
        if owned_output:
            for path, state in installed.items():
                if bounded._same_file(path, state):
                    path.unlink()
            if not list(output.iterdir()):
                output.rmdir()
        raise


def run_export(arguments):
    context = load_inputs(arguments)
    output, scratch, start_resources = _preflight(arguments, context)
    rows, candidates, raw_states = [], [], []
    for index, (identity, declaration, inventory, decode, old) in enumerate(zip(context.registration["recordings"],
            context.specification["recordings"], context.inventories, context.decodes, context.readiness["recordings"]), 1):
        row = _row(identity, declaration)
        observations = Observations();observations.phase("raw_hash")
        sink, observer = None, None
        path = Path(identity["canonical_path_private"])
        try:
            _resources(scratch, initial=True)
            LOGGER.info("Verifying raw bytes %d/%d for numeric export", index, len(context.inventories))
            with path.open("rb") as stream:
                before = file_state(stream=stream)
                raw_states.append((path, before))
                policy.require(before[2] == identity["size_bytes"] and sha256_stream(stream) == identity["raw_sha256"], "numeric_registered_raw_hash_or_size_changed")
                policy.require(file_state(stream=stream) == before and bounded._same_file(path, before), "numeric_raw_changed_during_hash")
                _resources(scratch)
                observations.phase("fresh_summary")
                fresh = read_inventory(stream, before[2])
                equal(fresh, inventory["inventory"], "numeric_preserved_inventory_mismatch")
                deadline = time.monotonic()+bounded.PROCESSING_SECONDS
                _resources(scratch)
                observations.phase("descriptor_binding")
                with Workspace(scratch, lambda: _resources(scratch), observations, deadline) as workspace:
                    sink = ScientificSink(workspace)
                    observer = NumericObserver(sink)
                    LOGGER.info("Exporting selected development streams %d/%d with preserved readiness equality", index, len(context.inventories))
                    row["stream_integrity"] = decoder.check_decoding(stream, before[2], fresh, sorted(bounded.TOPIC_LIMITS), scratch,
                        workspace.checkpoint, scientific_sink=observer, processing_deadline=deadline, index_connection=workspace.index)
                    equal(row["stream_integrity"], decode["decode_check"], "numeric_preserved_decode_mismatch")
                    observations.phase("scientific_finalize")
                    row["readiness"], row["condition_availability"], row["recorded_input_causality_checked"] = sink.finalize()
                    policy.require(sink.failure_code is None, sink.failure_code or "numeric_scientific_failure")
                    row["binding_observations"] = sink.binding_observations
                    for name in ("stream_integrity", "binding_observations", "readiness", "condition_availability", "recorded_input_causality_checked"):
                        equal(row[name], old[name], "numeric_preserved_readiness_mismatch")
                    row["readiness_matches_preserved"] = True
                    result = collect_candidates(sink, observer, row["readiness"], row["recorded_input_causality_checked"], identity["recording_id"], len(candidates))
                    policy.require(len(candidates)+len(result) <= policy.MAX_EDP, "numeric_actual_aggregate_edp_limit")
                    row.update(candidate_start=len(candidates), candidate_stop=len(candidates)+len(result),
                        residual_failure_counts=policy.failures(result, "residual_failure_code"), support=policy.build_numeric_archive(result)[1])
                    candidates.extend(result)
                    result = None
                policy.require(file_state(stream=stream) == before and bounded._same_file(path, before), "numeric_raw_changed_during_export")
        except Exception as error:
            _invalidate(row, scientific_failure(error), getattr(error, "reader_failure_context", None))
        if sink is not None:
            row["binding_observations"] = sink.binding_observations
        if observer is not None:
            row["observer_failure_counts"] = dict(sorted(observer.failures.items()))
        row["execution_observations"] = observations.summary()
        rows.append(row)
    try:
        context.unchanged()
        _raw_unchanged(raw_states)
    except Exception as error:
        for row in rows:
            _invalidate(row, scientific_failure(error))
    publication_deadline = time.monotonic()+policy.PUBLICATION_SECONDS
    if any(row["status"] != "complete" for row in rows):
        candidates.clear()
    try:
        return _publish(output, scratch, context, rows, candidates, start_resources, raw_states, publication_deadline)
    except Exception as error:
        # Owned incomplete files were cleaned by _publish. Never touch an unrelated output.
        for row in rows:
            _invalidate(row, scientific_failure(error))
        candidates.clear()
        summary = _summary(context, rows, [], start_resources, False)
        if not output.exists() and not output.is_symlink():
            output.mkdir(exist_ok=False)
            temporary = output/".numeric-inconclusive"
            try:
                _write_json(temporary, summary, policy.MAX_SUMMARY_BYTES, lambda: _checkpoint(publication_deadline))
                os.replace(temporary, output/policy.SUMMARY)
            except BaseException as marker_error:
                temporary.unlink(missing_ok=True)
                if not list(output.iterdir()):
                    output.rmdir()
                if not isinstance(marker_error, Exception):
                    raise
                LOGGER.error("numeric_inconclusive_marker_unavailable; no completed dataset")
        else:
            LOGGER.error("numeric_output_changed_or_appeared; preserved unrelated destination")
        return summary, 3


def run_validation(arguments):
    from ..io.numeric_archive import validate_archive
    deadline = time.monotonic()+policy.PUBLICATION_SECONDS
    checkpoint = lambda: _checkpoint(deadline)
    receipt = _new_output(arguments.validation_receipt)
    directory = arguments.export_directory.expanduser().absolute()
    policy.require(not receipt.is_symlink() and not receipt.resolve().is_relative_to(directory), "numeric_receipt_outside_export_required")
    context = load_inputs(arguments, checkpoint)
    policy.require(not receipt.resolve().is_relative_to(context.registration_directory), "numeric_receipt_overlaps_registration")
    for identity in context.registration["recordings"]:
        policy.require(receipt.resolve() != Path(identity["canonical_path_private"]), "numeric_receipt_overlaps_raw")
    for path in context.states:
        policy.require(receipt.resolve() != path.resolve(), "numeric_receipt_overlaps_input")
    summary, arrays = validate_archive(directory, arguments.expected_summary_sha256, context, checkpoint=checkpoint)
    result = {"contract_revision": policy.VALIDATION_REVISION, "purpose": "validate_development_numeric_archive_without_raw_or_model_admission",
        "status": "complete", "summary_sha256": arguments.expected_summary_sha256, "artifact_sha256": summary["artifacts_sha256"],
        "registration_sha256": context.registration_hash, "source_specification_sha256": context.registration["source_specification_sha256"],
        **context.hashes, **_runtime(include_compression=True), "geometric_profile_count": len(arrays["residuals_m"]),
        "conditioned_profile_count": len(arrays["conditions"]), "raw_opened": False, "model_admission_authorized": False,
        "raw_cache_deletion_authorized": False}
    checkpoint()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".numeric-validation-", dir=receipt.parent, delete=False) as stream:
            temporary = Path(stream.name)
        temporary.unlink()
        _write_json(temporary, result, policy.MAX_SUMMARY_BYTES, checkpoint)
        checkpoint()
        context.unchanged(checkpoint)
        policy.require(not directory.is_symlink() and {p.name for p in directory.iterdir()} == {policy.SUMMARY, policy.AUDIT, policy.ARCHIVE})
        for name, maximum, expected in ((policy.SUMMARY, policy.MAX_SUMMARY_BYTES, arguments.expected_summary_sha256),
                (policy.AUDIT, policy.MAX_AUDIT_BYTES, summary["artifacts_sha256"][policy.AUDIT]),
                (policy.ARCHIVE, policy.MAX_NPZ_BYTES, summary["artifacts_sha256"][policy.ARCHIVE])):
            equal(_digest(directory/name, maximum, checkpoint), expected, "numeric_artifact_changed_before_receipt")
        # Hard-link installation refuses an output that appeared during validation.
        os.link(temporary, receipt)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    LOGGER.info("Numeric archive validated without raw access or model admission")
    return result, 0
