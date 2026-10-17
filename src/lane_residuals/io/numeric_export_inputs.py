"""Strict metadata-only lineage and deliberate development reservation inputs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from ..domain import numeric_export as policy
from ..domain.recording_ingestion import CONTRACT_REVISION, parse_specification, source_declaration_status
from ..domain.recording_readiness import CONDITION_DATA, QUALIFIERS, ESTIMATE_DATA, REFERENCE_DATA, H100_DATA
from .bounded_recording_readiness import REVISION as READINESS_REVISION, TOPIC_LIMITS, TOPIC_ROLES
from .recording_ingestion import file_state
from ..workflows import bounded_recording_readiness as bounded
from ..workflows.recording_ingestion import REGISTRATION_NAME, SPECIFICATION_NAME, _runtime

require, keys = policy.require, policy.keys
READINESS_FIELDS = frozenset({"contract_revision", "purpose", "batch_id", "status", "registration_sha256", "source_specification_sha256",
    "preserved_inventory_report_sha256", "preserved_decode_report_sha256", "reader_implementation", "scientific_adapter_revision",
    "selected_topics", "selected_chunk_crc_validation_enabled", "technical_recording_count", "independent_outing_count", "roles_assigned",
    "cohort_lock_created", "model_fitted", "residual_profiles_constructed", "numeric_conditions_exported",
    "recorded_input_causality_checked_for_all_recordings", "physical_input_availability_proven", "reference_independence_proven",
    "raw_cache_deletion_authorized", "runtime_versions", "runtime_source_sha256", "execution_limits", "resources_at_start",
    "recordings", "interpretation"})
INHERITED_FIELDS = frozenset({"recording_id", "raw_sha256", "size_bytes", "source_declaration_status", "status", "failure_code",
    "invalidation_codes", "reader_failure_context", "binding_observations", "stream_integrity", "readiness",
    "condition_availability", "recorded_input_causality_checked", "execution_observations"})
SCIENCE_FIELDS = frozenset({"counts", "diagnostics", "odometry", "source_clock_order", "log_clock_order",
    "sensor_geometry_support", "complete_condition_support", "condition_failure_counts", "exclusive_attrition"})
COUNT_FIELDS = frozenset({"estimate_message_count", "reference_message_count", "timestamp_pairing_counts", "pairing_maximum_delta_ns",
    "estimate_topology_counts", "estimate_descriptor_counts", "conversion_failure_counts", "pair_failure_counts",
    "anchored_h100_topology_counts", "h100_pair_count", "anchored_h100_pair_count", "sensor_anchored_h100_pair_count"})
PAIRING_FIELDS = frozenset({"pairs", "rejected_by_gate", "unmatched_first_positions", "unmatched_second_positions",
    "missing_time_first_positions", "missing_time_second_positions", "ambiguous_first_positions", "ambiguous_second_positions"})
ODOMETRY_FIELDS = frozenset({"message_count", "distinct_valid_timestamp_count", "duplicate_timestamp_group_count", "duplicate_message_count",
    "conflicting_timestamp_group_count", "discarded_conflicting_message_count", "maximum_timestamp_multiplicity", "schema_counts", "failure_counts"})
SUPPORT_FIELDS = frozenset({"frame_count", "sequence_count", "transition_count", "maximum_frame_count", "maximum_duration_ns",
    "sequence_length_histogram", "sequence_start_reason_counts"})
STAGES = ("source_time", "unique_pair", "estimate_qualifier", "estimate_geometry", "reference_geometry", "common_h100",
    "anchor", "sensor_admission", "complete_conditions")


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def equal(left, right, code="numeric_predecessor_mismatch"):
    require(canonical(left) == canonical(right), code)


def read_bytes(path, maximum, checkpoint=lambda: None):
    """Bound allocation before opening a regular nonsymlink metadata file."""
    path = Path(path).expanduser().absolute()
    require(not path.is_symlink(), "numeric_regular_nonsymlink_file_required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        before = file_state(stream=stream)
        require(before[2] <= maximum, "numeric_input_size_limit")
        chunks = []
        remaining = before[2]
        while remaining:
            checkpoint()
            block = stream.read(min(1024**2, remaining))
            require(bool(block), "numeric_input_changed")
            chunks.append(block)
            remaining -= len(block)
        require(not stream.read(1) and not path.is_symlink() and file_state(stream=stream) == before and file_state(path) == before,
            "numeric_input_changed")
    checkpoint()
    return b"".join(chunks), before


def read_json(path, maximum=policy.MAX_SUMMARY_BYTES, checkpoint=lambda: None):
    raw, state = read_bytes(path, maximum, checkpoint)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "numeric_duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        require(False, "numeric_nonfinite_json")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    canonical(value)
    return value, hashlib.sha256(raw).hexdigest(), state


def execution_observations(value):
    keys(value, {"elapsed_seconds", "peak_resident_memory_bytes"})
    keys(value["elapsed_seconds"], {"raw_hash", "fresh_summary", "descriptor_binding", "selected_decode", "scientific_finalize"})
    for elapsed in value["elapsed_seconds"].values():
        if elapsed is not None:
            require(policy.finite(elapsed) >= 0)
    if value["peak_resident_memory_bytes"] is not None:
        policy.integer(value["peak_resident_memory_bytes"])


def readiness_support(value):
    keys(value, SUPPORT_FIELDS)
    for name in SUPPORT_FIELDS - {"sequence_length_histogram", "sequence_start_reason_counts"}:
        policy.integer(value[name])
    policy.histogram(value["sequence_length_histogram"])
    for length in value["sequence_length_histogram"]:
        require(str(int(length)) == length and 0 < int(length) <= policy.MAX_EDP)
    policy.histogram(value["sequence_start_reason_counts"], {"recording_start", "recording_boundary", "estimate_index_gap",
        "pair_index_gap", "timestamp_non_monotonic", "temporal_gap_exceeds_200ms"})
    histogram = value["sequence_length_histogram"]
    require(value["frame_count"] == sum(int(k)*v for k, v in histogram.items()))
    require(value["sequence_count"] == sum(histogram.values()))
    require(value["transition_count"] == value["frame_count"]-value["sequence_count"])
    require(value["maximum_frame_count"] == max(map(int, histogram), default=0))


def _clock(value, count, *, signed=False):
    keys(value, {"message_count", "missing_timestamp_count", "backward_step_count", "repeated_adjacent_timestamp_count",
        "minimum_timestamp_ns_decimal", "maximum_timestamp_ns_decimal"})
    equal(value["message_count"], count)
    for key in ("message_count", "missing_timestamp_count", "backward_step_count", "repeated_adjacent_timestamp_count"):
        policy.integer(value[key])
        require(value[key] <= count)
    lo, hi = value["minimum_timestamp_ns_decimal"], value["maximum_timestamp_ns_decimal"]
    if count == value["missing_timestamp_count"]:
        require(lo is None and hi is None)
    else:
        require(policy.decimal(lo, signed=signed) <= policy.decimal(hi, signed=signed))


def scientific_shape(value, totals):
    """Check closed inherited shapes before the later full fresh-science oracle."""
    keys(value, SCIENCE_FIELDS)
    counts = value["counts"]
    keys(counts, COUNT_FIELDS)
    for name in ("estimate_message_count", "reference_message_count", "h100_pair_count", "anchored_h100_pair_count", "sensor_anchored_h100_pair_count"):
        policy.integer(counts[name])
    equal(counts["estimate_message_count"], totals["/adp/estimated_drive_paths"])
    equal(counts["reference_message_count"], totals["/adp/road_lane_map_based"])
    keys(counts["timestamp_pairing_counts"], PAIRING_FIELDS)
    for count in counts["timestamp_pairing_counts"].values():
        policy.integer(count)
    require(counts["pairing_maximum_delta_ns"] is None)
    for name in ("estimate_topology_counts", "estimate_descriptor_counts", "conversion_failure_counts", "pair_failure_counts", "anchored_h100_topology_counts"):
        policy.histogram(counts[name])
    for root in counts["estimate_descriptor_counts"]:
        policy.digest(root)
    require(sum(counts["estimate_topology_counts"].values()) == counts["estimate_message_count"])
    require(0 <= counts["sensor_anchored_h100_pair_count"] <= counts["anchored_h100_pair_count"] <= counts["h100_pair_count"] <= counts["timestamp_pairing_counts"]["pairs"])
    odometry = value["odometry"]
    keys(odometry, ODOMETRY_FIELDS)
    for name in ODOMETRY_FIELDS - {"schema_counts", "failure_counts"}:
        policy.integer(odometry[name])
    equal(odometry["message_count"], totals["/adp/odometry"])
    policy.histogram(odometry["schema_counts"])
    policy.histogram(odometry["failure_counts"])
    keys(value["source_clock_order"], {"estimate", "reference"})
    for role in ("estimate", "reference"):
        _clock(value["source_clock_order"][role], counts[f"{role}_message_count"], signed=True)
    keys(value["log_clock_order"], TOPIC_LIMITS)
    for topic in TOPIC_LIMITS:
        _clock(value["log_clock_order"][topic], totals[topic])
    for name in ("sensor_geometry_support", "complete_condition_support"):
        readiness_support(value[name])
    equal(value["sensor_geometry_support"]["frame_count"], counts["sensor_anchored_h100_pair_count"])
    require(value["complete_condition_support"]["frame_count"] <= value["sensor_geometry_support"]["frame_count"])
    policy.histogram(value["condition_failure_counts"], CONDITION_DATA)
    details = value["diagnostics"]
    keys(details, {"reference_failure_detail_counts", "reference_segment_failure_counts", "pair_outcomes_by_estimate_topology", "timestamp_delta_summaries"})
    for name in ("reference_failure_detail_counts", "reference_segment_failure_counts"):
        policy.histogram(details[name])
    require(type(details["pair_outcomes_by_estimate_topology"]) is dict)
    for group in details["pair_outcomes_by_estimate_topology"].values():
        keys(group, {"pair_count", "available_estimator_pair_count", "outcome_counts", "reference_failure_counts", "reference_failure_counts_with_available_estimator"})
        policy.integer(group["pair_count"])
        policy.integer(group["available_estimator_pair_count"])
        for name in ("outcome_counts", "reference_failure_counts", "reference_failure_counts_with_available_estimator"):
            policy.histogram(group[name])
        require(sum(group["outcome_counts"].values()) == group["pair_count"] >= group["available_estimator_pair_count"])
    keys(details["timestamp_delta_summaries"], {"all_numeric_pairs", "anchored_h100_pairs", "sensor_anchored_h100_pairs"})
    for group in details["timestamp_delta_summaries"].values():
        keys(group, {"count", "negative_count", "zero_count", "positive_count", "signed_reference_minus_estimate_ns", "absolute_ns"})
        for name in ("count", "negative_count", "zero_count", "positive_count"):
            policy.integer(group[name])
        require(group["count"] == sum(group[k] for k in ("negative_count", "zero_count", "positive_count")))
        for name in ("signed_reference_minus_estimate_ns", "absolute_ns"):
            quantiles = group[name]
            keys(quantiles, {"min", "max", "p50", "p95", "p99"})
            if group["count"] == 0:
                require(all(v is None for v in quantiles.values()))
            else:
                require(all(type(v) is int and -(2**64-1) <= v < 2**64 for v in quantiles.values()))
    attrition = value["exclusive_attrition"]
    keys(attrition, {"decoded_estimate_message_count", "stages", "complete_condition_frame_count"})
    equal(attrition["decoded_estimate_message_count"], counts["estimate_message_count"])
    equal(attrition["complete_condition_frame_count"], value["complete_condition_support"]["frame_count"])
    require(type(attrition["stages"]) is list and len(attrition["stages"]) == len(STAGES))
    remaining = counts["estimate_message_count"]
    for name, stage in zip(STAGES, attrition["stages"]):
        keys(stage, {"stage", "input_count", "rejected_count", "remaining_count", "failure_code_counts"})
        equal(stage["stage"], name)
        for field in ("input_count", "rejected_count", "remaining_count"):
            policy.integer(stage[field])
        require(stage["input_count"] == remaining == stage["rejected_count"]+stage["remaining_count"])
        allowed = {"source_time": {"estimate_source_timestamp_missing"}, "unique_pair": {"no_unique_mutual_nearest_pair"},
            "estimate_qualifier": QUALIFIERS, "estimate_geometry": ESTIMATE_DATA, "reference_geometry": REFERENCE_DATA,
            "common_h100": H100_DATA, "anchor": {"anchor_distance_exceeds_1m_or_invalid"},
            "sensor_admission": {"not_sensor_topology"}, "complete_conditions": CONDITION_DATA}[name]
        policy.histogram(stage["failure_code_counts"], allowed)
        require(sum(stage["failure_code_counts"].values()) == stage["rejected_count"])
        remaining = stage["remaining_count"]
        expected = {"unique_pair": counts["timestamp_pairing_counts"]["pairs"], "common_h100": counts["h100_pair_count"],
            "anchor": counts["anchored_h100_pair_count"], "sensor_admission": counts["sensor_anchored_h100_pair_count"]}.get(name)
        if expected is not None:
            equal(remaining, expected)
    equal(remaining, attrition["complete_condition_frame_count"])


def _registration(directory, checkpoint=lambda: None):
    """Read declarations without resolving, statting or opening any raw path."""
    directory = Path(directory).expanduser().resolve(strict=True)
    require(directory.is_dir() and {p.name for p in directory.iterdir()} == {REGISTRATION_NAME, SPECIFICATION_NAME})
    spec, spec_hash, _ = read_json(directory/SPECIFICATION_NAME, checkpoint=checkpoint)
    parse_specification(spec)
    registration, registration_hash, _ = read_json(directory/REGISTRATION_NAME, checkpoint=checkpoint)
    keys(registration, {"contract_revision", "purpose", "batch_id", "source_specification_sha256", "recordings", "runtime_versions", "runtime_source_sha256"})
    equal({k: registration[k] for k in ("contract_revision", "purpose", "batch_id", "source_specification_sha256")},
        {"contract_revision": CONTRACT_REVISION, "purpose": "development_only", "batch_id": spec["batch_id"], "source_specification_sha256": spec_hash})
    policy.digest(registration["runtime_source_sha256"])
    keys(registration["runtime_versions"], {"python", "mcap", "mcap-protobuf-support", "protobuf", "numpy"})
    require(all(v is None or type(v) is str and bool(v) for v in registration["runtime_versions"].values()))
    require(type(registration["runtime_versions"]["python"]) is str and bool(registration["runtime_versions"]["python"]))
    rows = registration["recordings"]
    require(type(rows) is list and len(rows) == len(spec["recordings"]))
    hashes, paths = set(), set()
    for row, declaration in zip(rows, spec["recordings"]):
        keys(row, {"recording_id", "canonical_path_private", "raw_sha256", "size_bytes"})
        equal(row["recording_id"], declaration["recording_id"])
        policy.digest(row["raw_sha256"])
        policy.integer(row["size_bytes"])
        require(row["size_bytes"] > 0)
        path = row["canonical_path_private"]
        require(type(path) is str and PurePosixPath(path).is_absolute() and str(PurePosixPath(path)) == path and ".." not in PurePosixPath(path).parts)
        require(path not in paths and row["raw_sha256"] not in hashes)
        paths.add(path)
        hashes.add(row["raw_sha256"])
    return spec, registration, registration_hash


@dataclass
class Inputs:
    specification: dict
    registration: dict
    registration_hash: str
    inventories: list
    decodes: list
    readiness: dict
    hashes: dict
    states: dict
    runtime: dict
    registration_directory: Path

    def unchanged(self, checkpoint=lambda: None):
        try:
            for path, (expected, maximum, before) in self.states.items():
                raw, state = read_bytes(path, maximum, checkpoint)
                require(state == before and hashlib.sha256(raw).hexdigest() == expected, "numeric_inputs_changed_before_publication")
            directory = self.registration_directory
            require({p.name for p in directory.iterdir()} == {REGISTRATION_NAME, SPECIFICATION_NAME}, "numeric_inputs_changed_before_publication")
        except OSError:
            require(False, "numeric_inputs_changed_before_publication")


def load_inputs(arguments, checkpoint=lambda: None):
    """All metadata and authorization validation precedes raw access or output."""
    spec, registration, reg_hash = _registration(arguments.registration_directory, checkpoint)
    topics = bounded.decoder.selected_topics(arguments.topic)
    equal(topics, sorted(TOPIC_LIMITS), "numeric_explicit_three_topics_required")
    paths = {"preserved_inventory_report_sha256": Path(arguments.preserved_inventory_report).expanduser().absolute(),
        "preserved_decode_report_sha256": Path(arguments.preserved_decode_report).expanduser().absolute(),
        "preserved_readiness_report_sha256": Path(arguments.preserved_readiness_report).expanduser().absolute(),
        "exposure_authorization_sha256": Path(arguments.exposure_authorization).expanduser().absolute()}
    directory = Path(arguments.registration_directory).expanduser().resolve(strict=True)
    raw_paths = {Path(r["canonical_path_private"]) for r in registration["recordings"]}
    raw_paths.update(Path(r["local_path_private"]) for r in spec["recordings"])
    require(not any(Path(os.path.abspath(path)) in raw_paths for path in paths.values()), "numeric_metadata_path_is_registered_raw")
    require(not paths["exposure_authorization_sha256"].resolve().is_relative_to(directory), "numeric_authorization_outside_registration_required")
    # Validate all file kinds/strict JSON before the reused predecessor parser.
    values, hashes, states = {}, {}, {}
    for key, path in paths.items():
        maximum = policy.AUTHORIZATION_BYTES if key == "exposure_authorization_sha256" else policy.MAX_SUMMARY_BYTES
        values[key], hashes[key], before = read_json(path, maximum, checkpoint)
        states[path] = (hashes[key], maximum, before)
    for name, expected in ((REGISTRATION_NAME, reg_hash), (SPECIFICATION_NAME, registration["source_specification_sha256"])):
        _, checked, before = read_json(directory/name, checkpoint=checkpoint)
        equal(checked, expected)
        states[directory/name] = (expected, policy.MAX_SUMMARY_BYTES, before)
    policy.digest(arguments.expected_readiness_sha256)
    policy.digest(arguments.expected_exposure_authorization_sha256)
    equal(hashes["preserved_readiness_report_sha256"], arguments.expected_readiness_sha256, "numeric_readiness_digest_mismatch")
    equal(hashes["exposure_authorization_sha256"], arguments.expected_exposure_authorization_sha256, "numeric_authorization_digest_mismatch")
    inventories, decodes, inv_hash, decode_hash = bounded._predecessors(arguments, registration, reg_hash, spec, topics)
    checkpoint()
    equal(inv_hash, hashes["preserved_inventory_report_sha256"])
    equal(decode_hash, hashes["preserved_decode_report_sha256"])
    require(sum(bounded._advertised_selection(r["inventory"], topics)[2]["/adp/estimated_drive_paths"] for r in inventories) <= policy.MAX_EDP,
        "numeric_aggregate_edp_limit")
    ready = values["preserved_readiness_report_sha256"]
    keys(ready, READINESS_FIELDS)
    expected = {"contract_revision": READINESS_REVISION, "purpose": "development_only_bounded_recording_readiness",
        "status": "complete", "batch_id": registration["batch_id"], "registration_sha256": reg_hash,
        "source_specification_sha256": registration["source_specification_sha256"], "preserved_inventory_report_sha256": inv_hash,
        "preserved_decode_report_sha256": decode_hash, "reader_implementation": bounded.decoder.READER_IMPLEMENTATION,
        "scientific_adapter_revision": READINESS_REVISION, "selected_topics": topics, "selected_chunk_crc_validation_enabled": True,
        "technical_recording_count": len(registration["recordings"]), "independent_outing_count": None}
    for key in ("roles_assigned", "cohort_lock_created", "model_fitted", "residual_profiles_constructed", "numeric_conditions_exported",
            "physical_input_availability_proven", "reference_independence_proven", "raw_cache_deletion_authorized"):
        expected[key] = False
    equal({key: ready[key] for key in expected}, expected)
    limits = bounded._limits()
    bounded._evidence_metadata(ready, {k: v for k, v in limits.items() if k != "process_address_space_soft_limit_bytes"})
    require(ready["resources_at_start"]["mem_available_bytes"] >= limits["minimum_mem_available_bytes"])
    require(ready["resources_at_start"]["scratch_free_bytes"] >= limits["minimum_initial_scratch_free_bytes"])
    runtime = _runtime(include_compression=True)
    require(ready["runtime_source_sha256"] in (policy.ACCEPTED_READINESS_SOURCE, runtime["runtime_source_sha256"]), "numeric_readiness_source_not_accepted")
    require(type(ready["recordings"]) is list and len(ready["recordings"]) == len(registration["recordings"]))
    for row, identity, declaration, inventory, decode in zip(ready["recordings"], registration["recordings"], spec["recordings"], inventories, decodes):
        keys(row, INHERITED_FIELDS)
        equal({k: row[k] for k in ("recording_id", "raw_sha256", "size_bytes")}, {k: identity[k] for k in ("recording_id", "raw_sha256", "size_bytes")})
        equal(row["source_declaration_status"], source_declaration_status(declaration["source"]))
        equal((row["status"], row["failure_code"], row["invalidation_codes"], row["reader_failure_context"]), ("complete", None, [], None))
        equal(row["stream_integrity"], decode["decode_check"])
        _, channels, totals = bounded._advertised_selection(inventory["inventory"], topics)
        bindings = row["binding_observations"]
        require(type(bindings) is list and len(bindings) == len(channels))
        equal([(r["topic"], r["channel_id"]) for r in bindings], sorted((r["topic"], i) for i, r in channels.items()))
        for binding in bindings:
            keys(binding, {"topic", "role", "channel_id", "schema_id", "message_file_descriptor_sha256", "binding_status", "binding_failure_code"})
            channel = channels[binding["channel_id"]]
            equal({k: binding[k] for k in ("topic", "schema_id")}, {k: channel[k] for k in ("topic", "schema_id")})
            policy.integer(binding["channel_id"])
            policy.integer(binding["schema_id"])
            equal(binding["role"], TOPIC_ROLES[binding["topic"]])
            policy.digest(binding["message_file_descriptor_sha256"])
            if binding["role"] != "odometry" or binding["binding_status"] == "supported":
                equal((binding["binding_status"], binding["binding_failure_code"]), ("supported", None))
            else:
                require(binding["binding_status"] == "unsupported" and binding["binding_failure_code"] in {
                    "odometry_schema_or_encoding_mismatch", "odometry_descriptor_fields_unsupported"})
        scientific_shape(row["readiness"], totals)
        odometry = row["readiness"]["odometry"]
        available = odometry["message_count"] > 0 and not odometry["failure_counts"] and len(odometry["schema_counts"]) == 1 and not any(b["role"] == "odometry" and b["binding_status"] != "supported" for b in bindings)
        equal(row["recorded_input_causality_checked"], available)
        equal(row["condition_availability"], "available_for_checks" if available else "unavailable_odometry")
        if not available:
            equal(row["readiness"]["complete_condition_support"]["frame_count"], 0)
        execution_observations(row["execution_observations"])
    equal(ready["recorded_input_causality_checked_for_all_recordings"], all(r["recorded_input_causality_checked"] for r in ready["recordings"]))
    authorization = values["exposure_authorization_sha256"]
    keys(authorization, policy.AUTHORIZATION_FIELDS)
    equal({k: authorization[k] for k in ("contract_revision", "purpose", "batch_id", "registration_sha256", "source_specification_sha256", "preserved_readiness_report_sha256")},
        {"contract_revision": policy.AUTHORIZATION_REVISION, "purpose": policy.AUTHORIZATION_PURPOSE, "batch_id": registration["batch_id"],
         "registration_sha256": reg_hash, "source_specification_sha256": registration["source_specification_sha256"], "preserved_readiness_report_sha256": hashes["preserved_readiness_report_sha256"]})
    raw_hashes = authorization["authorized_raw_sha256"]
    require(type(raw_hashes) is list and len(raw_hashes) > 0)
    for value in raw_hashes:
        policy.digest(value)
    equal(raw_hashes, sorted({r["raw_sha256"] for r in registration["recordings"]}))
    keys(authorization["attestations"], policy.ATTESTATIONS)
    require(all(v is True for v in authorization["attestations"].values()), "numeric_deliberate_authorization_required")
    context = Inputs(spec, registration, reg_hash, inventories, decodes, ready, hashes, states, runtime, directory)
    context.unchanged(checkpoint)
    return context
