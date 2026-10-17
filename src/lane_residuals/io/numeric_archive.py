"""Independent raw-free validation of the generic development numeric archive."""

from __future__ import annotations

import ast
import binascii
from collections import Counter
import hashlib
import io
import math
from pathlib import Path
import struct
import zipfile
import zlib

import numpy as np

from ..domain import numeric_export as policy
from ..domain.recording_readiness import CONDITION_DATA, exclusive_attrition
from ..domain.recording_ingestion import summarize_support
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from .numeric_export_inputs import equal, execution_observations, read_bytes, read_json
from .recording_decode_check import READER_IMPLEMENTATION
from .bounded_recording_readiness import REVISION as READINESS_REVISION

require, keys = policy.require, policy.keys


def reconstruct_sequences(rows):
    """Separate validator implementation; do not call exporter sequence_layout."""
    offsets, sequences = [0], []
    if not rows:
        return offsets, sequences
    starts = [(0, ["recording_start"])]
    for index in range(1, len(rows)):
        previous, current = rows[index-1:index+1]
        reasons = []
        if previous["recording_id"] != current["recording_id"]:
            reasons = ["recording_boundary"]
        else:
            if current["estimate_message_index"]-previous["estimate_message_index"] != 1:
                reasons.append("estimate_index_gap")
            if current["pair_index"]-previous["pair_index"] != 1:
                reasons.append("pair_index_gap")
            delta = current["estimate_source_time_ns_private"]-previous["estimate_source_time_ns_private"]
            if delta <= 0:
                reasons.append("timestamp_non_monotonic")
            elif delta > 200_000_000:
                reasons.append("temporal_gap_exceeds_200ms")
        if reasons:
            starts.append((index, reasons))
    offsets = [start for start, _ in starts]+[len(rows)]
    for index, ((start, reasons), stop) in enumerate(zip(starts, offsets[1:])):
        sequences.append({"sequence_index": index, "recording_id": rows[start]["recording_id"], "start_row": start,
            "stop_row": stop, "frame_count": stop-start, "transition_count": stop-start-1,
            "duration_ns": rows[stop-1]["estimate_source_time_ns_private"]-rows[start]["estimate_source_time_ns_private"],
            "start_reasons": reasons})
    return offsets, sequences


def independent_support(rows):
    profiles = [r for r in rows if r["residual_available"]]
    conditioned = [r for r in profiles if r["conditions_available"]]
    _, geometry = reconstruct_sequences(profiles)
    _, conditions = reconstruct_sequences(conditioned)
    return {"geometric_profile_count": len(profiles), "conditioned_profile_count": len(conditioned),
        "geometry_sequences": geometry, "conditioned_sequences": conditions,
        "geometry_transition_count": sum(r["transition_count"] for r in geometry),
        "conditioned_transition_count": sum(r["transition_count"] for r in conditions)}


def _speed(row):
    codes = row["condition_failure_codes"]
    evidence = row["speed_bracket_evidence"]
    causal = {"speed_uses_future_source_sample", "speed_log_time_unavailable", "speed_input_logged_after_estimate"}
    if not evidence:
        require(not causal.intersection(codes))
        require(any(code in CONDITION_DATA and not code.startswith("estimate_features_") for code in codes))
        return
    keys(evidence, policy.SPEED_FIELDS)
    ev = {k: policy.decimal(v) for k, v in evidence.items()}
    t = row["estimate_source_time_ns_private"]
    require(t >= 50_000_000)
    brackets = []
    for name, target in (("previous", t-50_000_000), ("current", t)):
        lo, hi = (ev[f"{name}_{bound}_timestamp_ns_decimal_private"] for bound in ("lower", "upper"))
        require(lo <= target <= hi and hi-lo <= 50_000_000)
        brackets += [lo, hi]
    minimum = ev["minimum_input_log_time_ns_decimal_private"]
    maximum = ev["maximum_input_log_time_ns_decimal_private"]
    require(minimum <= maximum)
    expected = set()
    if max(brackets) > t:
        expected.add("speed_uses_future_source_sample")
    if row["estimate_log_time_ns_private"] <= 0 or minimum <= 0:
        expected.add("speed_log_time_unavailable")
    elif maximum > row["estimate_log_time_ns_private"]:
        expected.add("speed_input_logged_after_estimate")
    require(causal.intersection(codes) == expected)
    require(all(code.startswith("estimate_features_") or code in causal for code in codes))


def validate_audit(rows, summary, context, checkpoint):
    require(type(rows) is list and len(rows) <= policy.MAX_EDP)
    require(len(rows) == summary["pre_residual_candidate_count"])
    require(type(summary["recordings"]) is list and len(summary["recordings"]) == len(context.registration["recordings"]))
    normalized, cursor = [], 0
    for record, identity, old in zip(summary["recordings"], context.registration["recordings"], context.readiness["recordings"]):
        checkpoint()
        keys(record, policy.RECORDING_FIELDS)
        for key in ("recording_id", "raw_sha256", "size_bytes", "source_declaration_status", "binding_observations",
                "stream_integrity", "readiness", "condition_availability", "recorded_input_causality_checked"):
            equal(record[key], old[key])
        equal((record["status"], record["failure_code"], record["invalidation_codes"], record["reader_failure_context"], record["readiness_matches_preserved"]),
            ("complete", None, [], None, True))
        equal(record["outcome_exposure"], policy.EXPOSURE)
        execution_observations(record["execution_observations"])
        policy.histogram(record["observer_failure_counts"], policy.OBSERVER_CODES)
        require(sum(record["observer_failure_counts"].values()) <= old["readiness"]["counts"]["estimate_message_count"])
        count = old["readiness"]["counts"]["sensor_anchored_h100_pair_count"]
        equal((record["candidate_start"], record["candidate_stop"]), (cursor, cursor+count))
        roots = {b["message_file_descriptor_sha256"] for b in record["binding_observations"] if b["role"] == "estimate" and b["binding_status"] == "supported"}
        current_rows, pairs, estimates, references = [], set(), set(), set()
        previous_pair = -1
        for row in rows[cursor:cursor+count]:
            checkpoint()
            keys(row, policy.AUDIT_FIELDS)
            value = dict(row)
            equal(row["recording_id"], identity["recording_id"])
            equal(row["candidate_index"], len(normalized))
            for field in ("candidate_index", "pair_index", "estimate_message_index", "reference_message_index", "confidence_vector_length"):
                policy.integer(row[field])
            require(previous_pair < row["pair_index"] < old["readiness"]["counts"]["timestamp_pairing_counts"]["pairs"])
            previous_pair = row["pair_index"]
            require(row["estimate_message_index"] < old["readiness"]["counts"]["estimate_message_count"])
            require(row["reference_message_index"] < old["readiness"]["counts"]["reference_message_count"])
            require(row["pair_index"] not in pairs and row["estimate_message_index"] not in estimates and row["reference_message_index"] not in references)
            pairs.add(row["pair_index"]);estimates.add(row["estimate_message_index"]);references.add(row["reference_message_index"])
            for name in ("estimate_source_time", "reference_source_time", "estimate_log_time", "estimate_publish_time"):
                value[f"{name}_ns_private"] = policy.decimal(row[f"{name}_ns_decimal_private"])
            equal(policy.decimal(row["signed_reference_minus_estimate_ns_decimal"], signed=True), value["reference_source_time_ns_private"]-value["estimate_source_time_ns_private"])
            codes = row["condition_failure_codes"]
            require(type(codes) is list and all(type(c) is str and c in CONDITION_DATA for c in codes) and len(codes) == len(set(codes)))
            require(type(row["conditions_available"]) is bool and row["conditions_available"] == (not codes))
            require(type(row["residual_available"]) is bool and row["residual_available"] == (row["residual_failure_code"] is None))
            require(row["residual_failure_code"] in (None, "residual_non_finite"))
            require(policy.digest(row["estimate_file_descriptor_sha256"]) in roots)
            policy.finite(row["estimate_native_station_end_m"])
            if row["residual_available"]:
                require(0 <= policy.finite(row["anchor_distance_m"]) <= 1.)
                policy.finite(row["reference_anchor_station_m"])
            else:
                require(row["anchor_distance_m"] is None and row["reference_anchor_station_m"] is None)
            require(type(row["speed_bracket_evidence"]) is dict)
            _speed(value)
            # Conditions are a placeholder only for inherited counts, never a numeric feature.
            value["conditions"] = [] if row["conditions_available"] else None
            current_rows.append(value);normalized.append(value)
        cursor += count
        equal(dict(sorted(Counter(c for r in current_rows for c in r["condition_failure_codes"]).items())), old["readiness"]["condition_failure_counts"])
        equal(policy.failures(current_rows, "residual_failure_code"), record["residual_failure_counts"])
        equal(independent_support(current_rows), record["support"])
        equal(summarize_support(current_rows), old["readiness"]["sensor_geometry_support"])
        equal(summarize_support([r for r in current_rows if r["conditions_available"]]), old["readiness"]["complete_condition_support"])
        equal(exclusive_attrition(old["readiness"]["counts"], current_rows, old["recorded_input_causality_checked"]), old["readiness"]["exclusive_attrition"])
    require(cursor == len(rows))
    equal(sum(r["conditions_available"] for r in normalized), summary["pre_residual_complete_condition_count"])
    equal(policy.failures(normalized, "condition_failure_codes"), summary["condition_failure_counts"])
    equal(policy.failures(normalized, "residual_failure_code"), summary["residual_failure_counts"])
    equal(independent_support(normalized), summary["support"])
    return normalized


def _npz(raw, rows, checkpoint):
    profiles = [r for r in rows if r["residual_available"]]
    conditioned = [r for r in profiles if r["conditions_available"]]
    n, m = len(profiles), len(conditioned)
    shapes = {key: (n,) for key in ("recording_id", "candidate_index", "pair_index", "estimate_message_index", "reference_message_index",
        "estimate_source_time_ns_decimal", "reference_source_time_ns_decimal")}
    shapes.update(stations_m=(21,), condition_names=(6,), residuals_m=(n, 21), conditions=(m, 6), conditioned_profile_indices=(m,))
    # Require an ordinary empty-comment ZIP ending at EOCD, without trailing bytes.
    require(len(raw) >= 22 and raw[-22:-18] == b"PK\x05\x06" and raw[-2:] == b"\0\0", "numeric_npz_trailing_data")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) == len(policy.ARRAY_DTYPES) and {info.filename for info in infos} == {k+".npy" for k in policy.ARRAY_DTYPES})
        require(sum(info.file_size for info in infos) <= policy.MAX_NPZ_BYTES, "numeric_npz_uncompressed_size_limit")
        _zip_storage(raw, archive, infos, checkpoint)
        for info in infos:
            checkpoint()
            name = info.filename[:-4]
            require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
            with archive.open(info) as member:
                require(member.read(6) == b"\x93NUMPY")
                version = member.read(2)
                require(version in (b"\x01\0", b"\x02\0"))
                width = 2 if version[0] == 1 else 4
                size_raw = member.read(width)
                require(len(size_raw) == width)
                header_size = int.from_bytes(size_raw, "little")
                require(0 < header_size <= 16_384, "numeric_npy_header_limit")
                header_raw = member.read(header_size)
                require(len(header_raw) == header_size)
                header = ast.literal_eval(header_raw.decode("latin1"))
                keys(header, {"descr", "fortran_order", "shape"})
                require(header["descr"] == policy.ARRAY_DTYPES[name] and header["fortran_order"] is False)
                shape = header["shape"]
                require(type(shape) is tuple and all(type(v) is int and 0 <= v <= policy.MAX_EDP+1 for v in shape))
                if name in shapes:
                    equal(shape, shapes[name])
                else:
                    require(len(shape) == 1 and 1 <= shape[0] <= (n if name.startswith("geometry") else m)+1)
                require(info.file_size == 8+width+header_size+math.prod(shape)*np.dtype(header["descr"]).itemsize)
    checkpoint()
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = {}
        for name in policy.ARRAY_DTYPES:
            checkpoint()
            array = archive[name]
            require(array.dtype == np.dtype(policy.ARRAY_DTYPES[name]) and array.flags.c_contiguous)
            arrays[name] = array
    equal(arrays["stations_m"].tolist(), list(CANONICAL_MODEL_STATIONS_M))
    equal(arrays["condition_names"].tolist(), list(BMW_CONDITION_FEATURE_NAMES))
    require(np.isfinite(arrays["residuals_m"]).all() and np.isfinite(arrays["conditions"]).all())
    for i, row in enumerate(profiles):
        if i % 1024 == 0:
            checkpoint()
        for name in ("recording_id", "candidate_index", "pair_index", "estimate_message_index", "reference_message_index"):
            require(arrays[name][i] == row[name])
        for side in ("estimate", "reference"):
            require(str(arrays[f"{side}_source_time_ns_decimal"][i]) == str(row[f"{side}_source_time_ns_private"]))
    require(np.array_equal(arrays["conditioned_profile_indices"], [i for i, r in enumerate(profiles) if r["conditions_available"]]))
    for prefix, population in (("geometry", profiles), ("conditioned", conditioned)):
        offsets, _ = reconstruct_sequences(population)
        require(np.array_equal(arrays[f"{prefix}_sequence_offsets"], offsets))
    for array in arrays.values():
        array.setflags(write=False)
    return arrays


def _zip_storage(raw, archive, infos, checkpoint):
    """Reject unlisted bytes and overlong compressed streams without large inflation."""
    expected_offset = 0
    for info in sorted(infos, key=lambda item: item.header_offset):
        checkpoint()
        require(info.header_offset == expected_offset and raw[expected_offset:expected_offset+4] == b"PK\x03\x04")
        header = struct.unpack_from("<4s5H3I2H", raw, expected_offset)
        _, _, flags, method, _, _, crc, compressed_size, size, name_length, extra_length = header
        require(flags == info.flag_bits and method == info.compress_type and not flags & 1)
        require(method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
        begin = expected_offset+30+name_length+extra_length
        require(raw[expected_offset+30:expected_offset+30+name_length] == info.filename.encode("ascii"))
        end = begin+info.compress_size
        require(begin <= end <= len(raw))
        if not flags & 8:
            require(crc == info.CRC and compressed_size in (info.compress_size, 0xffffffff) and size in (info.file_size, 0xffffffff))
        produced, checksum = 0, 0
        inflater = zlib.decompressobj(-15) if method == zipfile.ZIP_DEFLATED else None
        for offset in range(begin, end, 64*1024):
            block = raw[offset:min(offset+64*1024, end)]
            if inflater is None:
                produced += len(block);checksum = binascii.crc32(block, checksum)
                require(produced <= info.file_size)
            else:
                while block:
                    checkpoint()
                    inflated = inflater.decompress(block, min(1024**2, info.file_size-produced+1))
                    produced += len(inflated);checksum = binascii.crc32(inflated, checksum)
                    require(produced <= info.file_size and not inflater.unused_data, "numeric_npz_overlong_stream")
                    block = inflater.unconsumed_tail
        if inflater is not None:
            require(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail)
        require(produced == info.file_size and checksum & 0xffffffff == info.CRC)
        expected_offset = end
        if flags & 8:
            if raw[expected_offset:expected_offset+4] == b"PK\x07\x08":
                expected_offset += 4
            if compressed_size == 0xffffffff or size == 0xffffffff:
                descriptor = struct.unpack_from("<IQQ", raw, expected_offset)
                expected_offset += 20
            else:
                descriptor = struct.unpack_from("<III", raw, expected_offset)
                expected_offset += 12
            require(descriptor == (info.CRC, info.compress_size, info.file_size))
    require(expected_offset == archive.start_dir)
    central_bytes = sum(46+len(info.filename.encode("ascii"))+len(info.extra)+len(info.comment) for info in infos)
    require(archive.start_dir+central_bytes == len(raw)-22)


def validate_archive(directory, expected_summary_sha256, context, *, checkpoint=lambda: None):
    """Open metadata/NPZ only; context is validated without raw-path access."""
    directory = Path(directory).expanduser().absolute()
    require(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()} == {policy.SUMMARY, policy.AUDIT, policy.ARCHIVE})
    policy.digest(expected_summary_sha256)
    summary, summary_hash, _ = read_json(directory/policy.SUMMARY, checkpoint=checkpoint)
    equal(summary_hash, expected_summary_sha256, "numeric_summary_digest_mismatch")
    keys(summary, policy.SUMMARY_FIELDS)
    expected = {"contract_revision": policy.REVISION, "scientific_policy_revision": policy.REVISION, "purpose": policy.PURPOSE,
        "status": "complete", "failure_code": None, "batch_id": context.registration["batch_id"],
        "registration_sha256": context.registration_hash, "source_specification_sha256": context.registration["source_specification_sha256"],
        **context.hashes, "preserved_readiness_contract_revision": READINESS_REVISION,
        "preserved_readiness_runtime_source_sha256": context.readiness["runtime_source_sha256"], "reader_implementation": READER_IMPLEMENTATION,
        "estimate_admission_policy": policy.admission_policy(), "confidence_bucket_semantics": policy.CONFIDENCE_SEMANTICS,
        "outcome_exposure_policy": policy.EXPOSURE_POLICY, "schema_semantics_deployed_producer_retraced": False,
        "technical_recording_count": len(context.registration["recordings"]), "independent_outing_count": None,
        "recorded_input_causality_checked_for_all_recordings": context.readiness["recorded_input_causality_checked_for_all_recordings"],
        "residuals_exported": True, "numeric_conditions_exported": True}
    for name in ("roles_assigned", "cohort_lock_created", "model_fitted", "standardizers_fitted", "physical_input_availability_proven",
            "reference_independence_proven", "raw_cache_deletion_authorized"):
        expected[name] = False
    equal({k: summary[k] for k in expected}, expected)
    from ..workflows.numeric_export import limits, SEMANTICS_BASIS
    equal(summary["schema_semantics_basis"], SEMANTICS_BASIS)
    from ..workflows.bounded_recording_readiness import _evidence_metadata
    _evidence_metadata(summary, {k: v for k, v in limits().items() if k != "process_address_space_soft_limit_bytes"})
    require(summary["resources_at_start"]["mem_available_bytes"] >= limits()["minimum_mem_available_bytes"])
    require(summary["resources_at_start"]["scratch_free_bytes"] >= limits()["minimum_initial_scratch_free_bytes"])
    require(type(summary["interpretation"]) is str and bool(summary["interpretation"]))
    policy.integer(summary["pre_residual_candidate_count"], policy.MAX_EDP)
    policy.integer(summary["pre_residual_complete_condition_count"], policy.MAX_EDP)
    keys(summary["artifacts_sha256"], {policy.AUDIT, policy.ARCHIVE})
    audit, audit_hash, _ = read_json(directory/policy.AUDIT, policy.MAX_AUDIT_BYTES, checkpoint)
    raw, archive_state = read_bytes(directory/policy.ARCHIVE, policy.MAX_NPZ_BYTES, checkpoint)
    equal(summary["artifacts_sha256"], {policy.AUDIT: audit_hash, policy.ARCHIVE: hashlib.sha256(raw).hexdigest()})
    keys(audit, {"contract_revision", "rows"})
    equal(audit["contract_revision"], policy.REVISION)
    rows = validate_audit(audit["rows"], summary, context, checkpoint)
    try:
        arrays = _npz(raw, rows, checkpoint)
    except (zipfile.BadZipFile, SyntaxError, UnicodeError, EOFError, OverflowError, struct.error, zlib.error):
        require(False, "numeric_npz_invalid")
    checkpoint()
    context.unchanged(checkpoint)
    # Validation is not permission to mutate inputs between checking and publication.
    for name, maximum, expected_hash in ((policy.SUMMARY, policy.MAX_SUMMARY_BYTES, summary_hash),
            (policy.AUDIT, policy.MAX_AUDIT_BYTES, audit_hash), (policy.ARCHIVE, policy.MAX_NPZ_BYTES, summary["artifacts_sha256"][policy.ARCHIVE])):
        checked, _ = read_bytes(directory/name, maximum, checkpoint)
        equal(hashlib.sha256(checked).hexdigest(), expected_hash, "numeric_artifact_changed_during_validation")
    require(not directory.is_symlink() and {p.name for p in directory.iterdir()} == {policy.SUMMARY, policy.AUDIT, policy.ARCHIVE})
    return summary, arrays
