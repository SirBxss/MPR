"""Bind one original development row to its archive and indexed MCAP."""

from __future__ import annotations

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


def _qualifier_failure(decoded, payload: bytes, binding: dict) -> str | None:
    """Require one explicit Available tag in the original top-level wire fields."""
    from google.protobuf.empty_pb2 import Empty
    from google.protobuf.unknown_fields import UnknownFieldSet

    field = decoded.DESCRIPTOR.fields_by_name.get(binding["field"])
    if field is None or field.enum_type is None or _field_is_repeated(field):
        return "replay_odometry_qualifier_descriptor_unsupported"
    available = field.enum_type.values_by_name.get(binding["available_symbol"])
    if available is None or sum(value.number == available.number for value in field.enum_type.values) != 1:
        return "replay_odometry_qualifier_descriptor_unsupported"

    # Empty has no declared fields, so the runtime preserves the original
    # occurrences, including explicit zero, wrong wire types and duplicates.
    wire = Empty.FromString(payload)
    occurrences = (item for item in UnknownFieldSet(wire) if item.field_number == field.number)
    first = next(occurrences, None)
    if first is None:
        return "replay_odometry_qualifier_implicit"
    if first.wire_type != 0 or next(occurrences, None) is not None:
        return "replay_odometry_qualifier_wire_ambiguous"
    if first.data != available.number % (1 << 64) or getattr(decoded, field.name) != available.number:
        return "replay_odometry_qualifier_not_available"
    return None


class _ExactOdometryQualifier:
    """Observe availability for the same representative used by the pose store."""

    def __init__(self, source_time: int, binding: dict):
        self.source_time = source_time
        self.binding = binding
        self.clocks: tuple[int, int] | None = None
        self.failure: str | None = None

    def observe(self, topic: str, log: int, publish: int, decoded, payload: bytes) -> None:
        if topic != DEFAULT_ODOMETRY_TOPIC:
            return
        try:
            source_time = _timestamp_ns(decoded)
        except (ValueError, TypeError, OverflowError):
            # The scientific sink already records invalid odometry messages.
            return
        clocks = (log, publish)
        if source_time != self.source_time or (self.clocks is not None and clocks > self.clocks):
            return
        failure = _qualifier_failure(decoded, payload, self.binding)
        if clocks == self.clocks and failure != self.failure:
            self.failure = "replay_odometry_qualifier_clock_tie"
        else:
            self.clocks, self.failure = clocks, failure

    def require_available(self, log: int, publish: int) -> None:
        if self.clocks != (log, publish):
            raise GeometryValidationError("replay_odometry_qualifier_sample_mismatch",
                                          "qualifier must bind to the selected pose")
        if self.failure is not None:
            raise GeometryValidationError(self.failure, "exact rear-axle pose requires explicit availability")


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

    odometry = db.execute(
        "SELECT log, publish, x, y, yaw, multiplicity, conflict FROM odometry WHERE time=?",
        (_time_key(estimate_time),),
    ).fetchone()
    if odometry is None:
        raise GeometryValidationError("replay_odometry_exact_epoch_missing", "exact rear-axle epoch required")
    log, publish, x, y, yaw, multiplicity, conflict = odometry
    if conflict or int(log) > estimate_log:
        raise GeometryValidationError("replay_odometry_conflict_or_late", "conflicting or late rear-axle evidence")
    if sink.odometry.descriptor_unavailable or sink.odometry.failures or len(sink.odometry.schemas) != 1:
        raise GeometryValidationError("replay_odometry_stream_unsupported", "original odometry binding required")
    qualifier.require_available(int(log), int(publish))
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
    }


def recover_frame(
    frame: ReplayFrame, path_frame_in_odometry: Pose2D, scratch: Path, resource_check, *,
    qualifier_binding: dict,
) -> tuple[RecordedReplayGeometry, dict]:
    """Verify bytes and replay the original indexed conversion on one open file."""
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
        deadline = time.monotonic() + PROCESSING_SECONDS
        with Workspace(scratch, resource_check, Observations(), deadline) as workspace:
            sink = ScientificSink(workspace)
            qualifier = _ExactOdometryQualifier(int(frame.identity["estimate_source_time_ns"]), qualifier_binding)
            integrity = decoder.check_decoding(
                stream, before[2], inventory, sorted(TOPIC_LIMITS), scratch, workspace.checkpoint,
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
                require(file_state(stream=stream) == before and file_state(path) == before,
                        "replay_raw_changed")
