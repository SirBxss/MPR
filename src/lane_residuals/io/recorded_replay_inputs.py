"""Bind one original development row to its archive and indexed MCAP."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import time

import numpy as np

from ..domain.artifact_registry import require
from ..domain.geometry_validation import GeometryValidationError
from ..domain.motion import Pose2D, ego_frame_transform
from ..domain.pairing import EgoRelativePath, mutual_nearest_timestamp_pairs
from ..domain.path_source_probe import _field_is_repeated
from ..domain.recorded_replay_geometry import RecordedReplayGeometry, check_recorded_replay_geometry
from . import development_experiment as original, recording_decode_check as decoder
from .bounded_recording_readiness import ScientificSink, TOPIC_LIMITS
from .direct_speed_study import object_json
from .exploratory_residuals import _time_key
from .numeric_export_inputs import equal
from .numeric_residuals import NumericObserver
from .odometry import DEFAULT_ODOMETRY_TOPIC, _timestamp_ns
from .recording_ingestion import file_state, sha256_stream
from .recording_inventory import read_inventory
from .recording_pair_feasibility import _unpack_path
from .recording_readiness_resources import Observations, PROCESSING_SECONDS, Workspace

IDENTITY_FIELDS = (
    "recording_id", "candidate_index", "pair_index",
    "estimate_message_index", "reference_message_index",
)
QUALIFIER_BINDING_FIELDS = ("schema_data_sha256", "field", "available_symbol")


@dataclass(frozen=True)
class ReplayFrame:
    identity: dict
    audit: dict
    residual_m: np.ndarray
    original_speed_mps: float
    raw_path: Path
    size_bytes: int
    inventory: dict
    stream_integrity: dict
    sequence_start: int
    sequence_stop: int


def select_frame(inputs: original.ExperimentInputs, outing_id: str, matched_row: int) -> ReplayFrame:
    """Select by original row index before raw access or planner evaluation."""
    blocks = [block for block in inputs.blocks if block.outing_id == outing_id]
    require(len(blocks) == 1, "replay_original_development_outing_required")
    archive = blocks[0].archive
    arrays = archive.arrays
    indices = arrays["conditioned_profile_indices"]
    require(0 <= matched_row < len(indices), "replay_original_matched_row_required")
    profile = int(indices[matched_row])
    identity = {key: arrays[key][profile].item() for key in IDENTITY_FIELDS}
    recording = identity["recording_id"]
    raw = archive.raw_sha256_by_recording[recording]
    summary = object_json(inputs.context, archive.summary_sha256)
    audit = object_json(inputs.context, summary["artifacts_sha256"]["candidate_audit.json"])
    row = audit["rows"][identity["candidate_index"]]
    require(all(row[key] == identity[key] for key in IDENTITY_FIELDS)
            and row["residual_available"] is True and row["conditions_available"] is True,
            "replay_original_audit_row_mismatch")
    for role in ("estimate", "reference"):
        require(arrays[f"{role}_source_time_ns_decimal"][profile]
                == row[f"{role}_source_time_ns_decimal_private"], "replay_archive_clock_mismatch")
    record, = [item for item in inputs.context.metadata["records"] if item["raw_sha256"] == raw]
    paths = record["canonical_paths_private"]
    require(len(paths) == 1, "replay_unambiguous_registered_raw_path_required")
    size = record["size_bytes"]
    inventory = object_json(inputs.context, summary["preserved_inventory_report_sha256"])
    inventory_row, = [item for item in inventory["recordings"] if item["recording_id"] == recording]
    summary_row, = [item for item in summary["recordings"] if item["recording_id"] == recording]
    require(all(item["status"] == "complete" and item["raw_sha256"] == raw
                and item["size_bytes"] == size for item in (inventory_row, summary_row)),
            "replay_registered_recording_mismatch")
    offsets = arrays["conditioned_sequence_offsets"]
    sequence = int(np.searchsorted(offsets, matched_row, side="right") - 1)
    identity.update(
        outing_id=outing_id, matched_row=matched_row, geometry_profile_row=profile,
        archive_sha256=archive.summary_sha256, raw_sha256=raw,
        estimate_source_time_ns=row["estimate_source_time_ns_decimal_private"],
        reference_source_time_ns=row["reference_source_time_ns_decimal_private"],
        estimate_log_time_ns=row["estimate_log_time_ns_decimal_private"],
        estimate_publish_time_ns=row["estimate_publish_time_ns_decimal_private"],
    )
    return ReplayFrame(
        identity, row, arrays["residuals_m"][profile], float(arrays["conditions"][matched_row, 0]),
        Path(paths[0]), size,
        inventory_row["inventory"], summary_row["stream_integrity"],
        int(offsets[sequence]), int(offsets[sequence + 1]),
    )


def frame_evidence_template(frame: ReplayFrame) -> dict:
    return {
        "row": frame.identity,
        "path_frame_epoch_ns": frame.identity["estimate_source_time_ns"],
        "path_frame": None,
        "odometry_frame": None,
        "frame_and_pose_evidence_reference": None,
        "both_original_paths_verified_in_same_frame_at_epoch": False,
        "recorded_rear_axle_pose_valid_at_epoch": False,
        "odometry_qualifier": dict.fromkeys(QUALIFIER_BINDING_FIELDS),
        "path_frame_in_odometry": {"x_m": None, "y_m": None, "yaw_rad": None},
    }


def validate_frame_evidence(value: dict, frame: ReplayFrame) -> tuple[Pose2D, dict]:
    """Check the declared binding; physical frame semantics come from the owner."""
    require(type(value) is dict and set(value) == set(frame_evidence_template(frame)),
            "replay_frame_evidence_schema")
    equal(value["row"], frame.identity, "replay_frame_evidence_row_mismatch")
    require(value["path_frame_epoch_ns"] == frame.identity["estimate_source_time_ns"],
            "replay_frame_evidence_epoch_mismatch")
    for key in ("path_frame", "odometry_frame", "frame_and_pose_evidence_reference"):
        require(type(value[key]) is str and bool(value[key].strip()), "replay_frame_evidence_required")
    require(value["both_original_paths_verified_in_same_frame_at_epoch"] is True
            and value["recorded_rear_axle_pose_valid_at_epoch"] is True,
            "replay_frame_and_pose_confirmation_required")
    pose = value["path_frame_in_odometry"]
    require(type(pose) is dict and set(pose) == {"x_m", "y_m", "yaw_rad"} and
            all(type(v) in (int, float) for v in pose.values()), "replay_frame_origin_pose_required")
    qualifier = value["odometry_qualifier"]
    _validate_qualifier_binding(qualifier, frame)
    return Pose2D(**pose), qualifier


def _validate_qualifier_binding(qualifier: dict, frame: ReplayFrame) -> None:
    require(type(qualifier) is dict and set(qualifier) == set(QUALIFIER_BINDING_FIELDS)
            and all(type(item) is str and item.strip() for item in qualifier.values()),
            "replay_odometry_qualifier_binding_required")
    archived_schemas = {row["schema_data_sha256"] for row in frame.stream_integrity["channel_versions"]
                        if row["topic"] == DEFAULT_ODOMETRY_TOPIC}
    require(archived_schemas == {qualifier["schema_data_sha256"]},
            "replay_odometry_qualifier_binding_mismatch")


def _qualifier_wire(decoded, payload: bytes, binding: dict) -> tuple[str | None, int | None]:
    """Return the qualifier gate result and the raw varint of a single tag."""
    from google.protobuf.empty_pb2 import Empty
    from google.protobuf.unknown_fields import UnknownFieldSet

    field = decoded.DESCRIPTOR.fields_by_name.get(binding["field"])
    if field is None or field.enum_type is None or _field_is_repeated(field):
        return "replay_odometry_qualifier_descriptor_unsupported", None
    available = field.enum_type.values_by_name.get(binding["available_symbol"])
    if available is None or sum(value.number == available.number for value in field.enum_type.values) != 1:
        return "replay_odometry_qualifier_descriptor_unsupported", None

    # Empty has no declared fields, so the runtime preserves the original
    # occurrences, including explicit zero, wrong wire types and duplicates.
    wire = Empty.FromString(payload)
    occurrences = (item for item in UnknownFieldSet(wire) if item.field_number == field.number)
    first = next(occurrences, None)
    if first is None:
        return "replay_odometry_qualifier_implicit", None
    if first.wire_type != 0 or next(occurrences, None) is not None:
        return "replay_odometry_qualifier_wire_ambiguous", None
    if first.data != available.number % (1 << 64) or getattr(decoded, field.name) != available.number:
        return "replay_odometry_qualifier_not_available", first.data
    return None, first.data


class OdometryQualifierError(GeometryValidationError):
    def __init__(self, code: str, counts: dict):
        super().__init__(code, "exact rear-axle pose requires consistent explicit availability")
        self.counts = counts


class _ExactOdometryQualifier:
    """Observe availability for the same representative used by the pose store."""

    def __init__(self, source_time: int, binding: dict):
        self.source_time = source_time
        self.binding = binding
        self.clocks: tuple[int, int] | None = None
        self.failure: str | None = None
        self.outcomes: Counter[str] = Counter()

    def observe(self, topic: str, log: int, publish: int, decoded, payload: bytes) -> None:
        if topic != DEFAULT_ODOMETRY_TOPIC:
            return
        try:
            source_time = _timestamp_ns(decoded)
        except (ValueError, TypeError, OverflowError):
            # The scientific sink already records invalid odometry messages.
            return
        clocks = (log, publish)
        if source_time != self.source_time:
            return
        failure, _ = _qualifier_wire(decoded, payload, self.binding)
        self.record(clocks, failure)

    def record(self, clocks: tuple[int, int], failure: str | None) -> None:
        self.outcomes[failure or "explicit_available_wire_value"] += 1
        if clocks == self.clocks and failure != self.failure:
            self.failure = "replay_odometry_qualifier_clock_tie"
        elif self.clocks is None or clocks < self.clocks:
            self.clocks, self.failure = clocks, failure

    def summary(self) -> dict:
        return {
            "exact_epoch_message_count": sum(self.outcomes.values()),
            "qualifier_outcome_counts": dict(sorted(self.outcomes.items())),
        }

    def failure_code(self) -> str | None:
        if self.failure == "replay_odometry_qualifier_clock_tie":
            return self.failure
        if len(self.outcomes) > 1:
            return "replay_odometry_qualifier_duplicate_conflict"
        return self.failure

    def require_available(self, log: int, publish: int, multiplicity: int) -> None:
        if self.clocks != (log, publish) or sum(self.outcomes.values()) != multiplicity:
            raise OdometryQualifierError("replay_odometry_qualifier_sample_mismatch", self.summary())
        if (failure := self.failure_code()) is not None:
            raise OdometryQualifierError(failure, self.summary())


def reconcile_staged_frame(
    sink: ScientificSink, frame: ReplayFrame, path_frame_in_odometry: Pose2D,
    qualifier: _ExactOdometryQualifier,
) -> tuple[RecordedReplayGeometry, dict]:
    row, db = frame.identity, sink.db
    estimate, reference = row["estimate_message_index"], row["reference_message_index"]
    estimate_time = int(row["estimate_source_time_ns"])
    reference_time = int(row["reference_source_time_ns"])
    estimate_log = int(row["estimate_log_time_ns"])
    times = sink.geometry.times
    require(estimate < len(times["estimate"]) and reference < len(times["reference"])
            and times["estimate"][estimate] == estimate_time
            and times["reference"][reference] == reference_time, "replay_original_message_clock_mismatch")
    pairs = mutual_nearest_timestamp_pairs(times["estimate"], times["reference"]).pairs
    pair_index = row["pair_index"]
    require(pair_index < len(pairs)
            and (pairs[pair_index].first_position, pairs[pair_index].second_position) == (estimate, reference),
            "replay_original_pair_mismatch")
    estimate_input = db.execute(
        "SELECT time, log, publish FROM estimate_inputs WHERE position=?", (estimate,)
    ).fetchone()
    require(estimate_input is not None and tuple(map(int, estimate_input))
            == (estimate_time, estimate_log, int(row["estimate_publish_time_ns"])),
            "replay_original_estimate_input_mismatch")
    descriptor = db.execute("SELECT root FROM numeric_observations WHERE position=?", (estimate,)).fetchone()
    require(descriptor == (frame.audit["estimate_file_descriptor_sha256"],),
            "replay_original_estimate_descriptor_mismatch")
    def read_path(role: str, index: int) -> EgoRelativePath:
        stored = db.execute("SELECT path FROM geometry WHERE role=? AND position=?", (role, index)).fetchone()
        path = None if stored is None else _unpack_path(stored[0])
        require(path is not None, "replay_original_geometry_missing")
        return path

    if sink.odometry.descriptor_unavailable or sink.odometry.failures or len(sink.odometry.schemas) > 1:
        raise GeometryValidationError("replay_odometry_stream_unsupported", "original odometry binding required")
    odometry = db.execute(
        "SELECT log, publish, x, y, yaw, multiplicity, conflict FROM odometry WHERE time=?",
        (_time_key(estimate_time),),
    ).fetchone()
    if odometry is None:
        raise GeometryValidationError("replay_odometry_exact_epoch_missing", "exact rear-axle epoch required")
    log, publish, x, y, yaw, multiplicity, conflict = odometry
    if conflict or int(log) > estimate_log:
        raise GeometryValidationError("replay_odometry_conflict_or_late", "conflicting or late rear-axle evidence")
    qualifier.require_available(int(log), int(publish), multiplicity)
    transform = ego_frame_transform(Pose2D(x, y, yaw), path_frame_in_odometry)
    geometry = check_recorded_replay_geometry(
        read_path("estimate", estimate), read_path("reference", reference),
        ego_pose_in_path_frame=Pose2D(*transform.translation_target_m, transform.yaw_delta_rad),
        archived_residual_m=frame.residual_m,
        archived_anchor_station_m=frame.audit["reference_anchor_station_m"],
        archived_anchor_distance_m=frame.audit["anchor_distance_m"],
    )
    return geometry, {
        "source_time_ns": str(estimate_time), "log_time_ns": str(int(log)),
        "publish_time_ns": str(int(publish)), "identical_pose_message_count": multiplicity,
        "availability_evidence": "explicit_available_wire_value",
        **qualifier.summary(),
    }


@contextmanager
def _recording_for_frame(frame: ReplayFrame, qualifier_binding: dict):
    """Verify the pinned recording and keep one file descriptor for the scan."""
    _validate_qualifier_binding(qualifier_binding, frame)
    path = frame.raw_path
    require(path.is_absolute() and path.resolve() == path, "replay_registered_raw_path_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = file_state(stream=stream)
        require(before[2] == frame.size_bytes and sha256_stream(stream) == frame.identity["raw_sha256"],
                "replay_raw_size_or_digest_mismatch")
        require(file_state(stream=stream) == before and file_state(path) == before, "replay_raw_changed")
        inventory = read_inventory(stream, before[2])
        equal(inventory, frame.inventory, "replay_original_inventory_mismatch")
        try:
            yield stream, before[2], inventory
        finally:
            require(file_state(stream=stream) == before and file_state(path) == before, "replay_raw_changed")


def recover_frame(
    frame: ReplayFrame, path_frame_in_odometry: Pose2D, scratch: Path, resource_check, *,
    qualifier_binding: dict,
) -> tuple[RecordedReplayGeometry, dict]:
    """Verify bytes and replay the original indexed conversion on one open file."""
    with _recording_for_frame(frame, qualifier_binding) as (stream, size, inventory):
        deadline = time.monotonic() + PROCESSING_SECONDS
        with Workspace(scratch, resource_check, Observations(), deadline) as workspace:
            sink = ScientificSink(workspace)
            qualifier = _ExactOdometryQualifier(int(frame.identity["estimate_source_time_ns"]), qualifier_binding)
            integrity = decoder.check_decoding(
                stream, size, inventory, sorted(TOPIC_LIMITS), scratch, workspace.checkpoint,
                scientific_sink=NumericObserver(sink), processing_deadline=deadline,
                index_connection=workspace.index, payload_observer=qualifier.observe,
            )
            equal(integrity, frame.stream_integrity, "replay_original_stream_integrity_mismatch")
            require(sink.failure_code is None, sink.failure_code or "replay_scientific_decode_failed")
            workspace.checkpoint()
            try:
                return reconcile_staged_frame(sink, frame, path_frame_in_odometry, qualifier)
            finally:
                workspace.checkpoint()


def census_odometry_qualifier(frame: ReplayFrame, binding: dict, scratch: Path, resource_check) -> dict:
    """Count qualifier wire encodings without calculating or exposing geometry."""
    qualifier = _ExactOdometryQualifier(int(frame.identity["estimate_source_time_ns"]), binding)
    wires = Counter(dict.fromkeys(("omitted", "explicit_zero", "explicit_nonzero", "ambiguous"), 0))
    nonzero_values: Counter[str] = Counter()
    invalid_source_times = 0

    def observe(_topic, log, publish, decoded, payload):
        nonlocal invalid_source_times
        failure, value = _qualifier_wire(decoded, payload, binding)
        if failure == "replay_odometry_qualifier_descriptor_unsupported":
            raise GeometryValidationError(failure, "census requires the archived qualifier descriptor")
        if value is None:
            wires["omitted" if failure == "replay_odometry_qualifier_implicit" else "ambiguous"] += 1
        elif value == 0:
            wires["explicit_zero"] += 1
        else:
            wires["explicit_nonzero"] += 1
            # Signed, descriptor-declared values get individual bins. Unknown
            # wire numbers share a bin to keep the accumulator bounded.
            signed = value - (1 << 64) if value >= (1 << 63) else value
            enum = decoded.DESCRIPTOR.fields_by_name[binding["field"]].enum_type
            key = str(signed) if signed in enum.values_by_number else "unknown"
            nonzero_values[key] += 1
        try:
            source_time = _timestamp_ns(decoded)
        except (ValueError, TypeError, OverflowError):
            invalid_source_times += 1
        else:
            if source_time == qualifier.source_time:
                qualifier.record((log, publish), failure)

    with _recording_for_frame(frame, binding) as (stream, size, inventory):
        integrity = decoder.check_decoding(
            stream, size, inventory, (DEFAULT_ODOMETRY_TOPIC,), scratch, resource_check,
            payload_observer=observe,
        )
        for key in ("channel_versions", "topics"):
            expected = [item for item in frame.stream_integrity[key] if item["topic"] == DEFAULT_ODOMETRY_TOPIC]
            equal(integrity[key], expected, "replay_census_odometry_integrity_mismatch")
        count = integrity["decoded_selected_message_count"]
        require(sum(wires.values()) == count, "replay_census_message_count_mismatch")
        resource_check()
    return {
        "odometry_message_count": count,
        "wire_counts": dict(wires),
        "explicit_nonzero_value_counts": dict(sorted(nonzero_values.items())),
        "invalid_source_time_count": invalid_source_times,
        "selected_epoch": {
            **qualifier.summary(),
            "qualifier_failure_code": qualifier.failure_code() if qualifier.clocks is not None
            else "replay_odometry_exact_epoch_missing",
        },
    }
