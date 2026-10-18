"""Scalar observation around unchanged science, followed by staged-only export."""

from __future__ import annotations

from collections import Counter
import hashlib
import math

from ..domain.exploratory_residuals import aligned_residual
from ..domain.geometry_validation import GeometryValidationError
from ..domain import numeric_export as policy
from ..domain.path_source_probe import _effective_enum_symbol, _effective_field_value, _joint_audit_bindings, _repeated_values
from ..domain.recording_ingestion import RecordingIngestionError, summarize_support
from .exploratory_residuals import _finish_conditions, _time_key
from .mcap import source_time_ns_from_message
from .numeric_export_inputs import equal
from .recording_pair_feasibility import _count_staged_geometry, _unpack_path


def _metadata(decoded):
    """Observe bound scalars only; no classification, feature validation or path conversion."""
    source = source_time_ns_from_message(decoded)
    if source is not None and source < 0:
        source = None
    if source is None:
        raise ValueError("source missing")
    bindings = _joint_audit_bindings(decoded.DESCRIPTOR)
    paths = _repeated_values(decoded, bindings.drive_paths)
    selected = [path for path in paths or () if _effective_enum_symbol(path, bindings.role)[0] == "LANE_ROLE_KEEP_LANE"]
    if len(selected) != 1:
        raise ValueError("unique selected path missing")
    path = selected[0]
    model, _, _ = _effective_field_value(path, bindings.model_parameters)
    starts = _repeated_values(model, bindings.segment_starts)
    end = float(starts[-1])
    if not math.isfinite(end):
        raise ValueError("native end unavailable")
    return source, hashlib.sha256(decoded.DESCRIPTOR.file.serialized_pb).hexdigest(), len(path.drive_path_confidences), end


class NumericObserver:
    """No replacement/subclassing of ScientificSink; preserve real delegation errors."""
    def __init__(self, inner):
        self.inner = inner
        self.failures = Counter()
        self.actual_edp = 0
        inner.db.execute("CREATE TABLE numeric_observations (position INTEGER PRIMARY KEY, root TEXT, confidence_count INTEGER, native_end REAL)")

    def configure(self, selected):
        self.inner.configure(selected)
        self.selected = selected

    def register_schema(self, *arguments):
        self.inner.register_schema(*arguments)

    def bindings_complete(self):
        self.inner.bindings_complete()

    def consume(self, channel_id, log_time, publish_time, decoded):
        if self.selected[channel_id]["topic"] != "/adp/estimated_drive_paths":
            self.inner.consume(channel_id, log_time, publish_time, decoded)
            return
        self.actual_edp += 1
        policy.require(self.actual_edp <= policy.MAX_EDP, "numeric_actual_edp_limit")
        position = len(self.inner.geometry.times["estimate"])
        failure, values = None, None
        # Only pure scalar extraction is inside this narrow containment boundary.
        try:
            values = _metadata(decoded)
        except RecordingIngestionError:
            raise
        except (AttributeError, TypeError, ValueError, IndexError, KeyError, OverflowError):
            failure = "numeric_observer_metadata_unavailable"
        # The original object and arguments are delegated once, outside the catch.
        self.inner.consume(channel_id, log_time, publish_time, decoded)
        times = self.inner.geometry.times["estimate"]
        if len(times) != position+1 or values is not None and times[position] != values[0]:
            failure = failure or "numeric_observer_alignment_mismatch"
        if failure:
            self.failures[failure] += 1
        else:
            # Writes/resource errors propagate even for a noncandidate message.
            self.inner.db.execute("INSERT INTO numeric_observations VALUES (?,?,?,?)", (position, *values[1:]))


def collect_candidates(sink, observer, readiness, available, recording_id, start):
    """Reproduce pre-residual populations before checked numeric construction."""
    workspace, db, staging = sink.workspace, sink.db, sink.geometry
    workspace.checkpoint()
    pairs = []
    maximum = readiness["counts"]["sensor_anchored_h100_pair_count"]
    def pair(index, value):
        policy.require(len(pairs) < maximum, "numeric_preserved_candidate_count_exceeded")
        pairs.append((index, value))
    counts = _count_staged_geometry(db, staging.times, staging.topology_counts, staging.conversion_failures,
        staging.descriptor_counts, None, on_sensor_pair=pair, checkpoint=workspace.checkpoint)
    equal(counts, readiness["counts"], "numeric_staged_readiness_mismatch")
    result = _finish_conditions(db, sink.odometry, counts, readiness["diagnostics"], pairs,
        compute_residuals=False, checkpoint=workspace.checkpoint)
    rows = result["candidates"]
    if not available:
        for row in rows:
            row["conditions"] = None
    equal(result["odometry"], readiness["odometry"], "numeric_staged_readiness_mismatch")
    equal(summarize_support(rows), readiness["sensor_geometry_support"], "numeric_staged_readiness_mismatch")
    equal(summarize_support([r for r in rows if r["conditions"] is not None]), readiness["complete_condition_support"], "numeric_staged_readiness_mismatch")
    equal(dict(sorted(Counter(c for r in rows for c in r["condition_failure_codes"]).items())), readiness["condition_failure_counts"], "numeric_staged_readiness_mismatch")
    equal(sink._diagnostics.summary(), readiness["diagnostics"], "numeric_staged_readiness_mismatch")
    # No residual is evaluated until all staged parity checks above pass.
    for i, row in enumerate(rows):
        workspace.checkpoint()
        row.update(recording_id=recording_id, candidate_index=start+i)
        metadata = db.execute("SELECT root,confidence_count,native_end FROM numeric_observations WHERE position=?", (row["estimate_message_index"],)).fetchone()
        policy.require(metadata is not None, "numeric_candidate_observation_missing")
        row.update(estimate_file_descriptor_sha256=metadata[0], confidence_vector_length=metadata[1], estimate_native_station_end_m=metadata[2])
        evidence = row["speed_bracket_evidence"]
        if evidence:
            times = {evidence[key] for key in ("previous_lower_timestamp_ns_private", "previous_upper_timestamp_ns_private",
                "current_lower_timestamp_ns_private", "current_upper_timestamp_ns_private")}
            logs = [db.execute("SELECT log FROM odometry WHERE time=? AND conflict=0", (_time_key(t),)).fetchone() for t in times]
            policy.require(all(item is not None for item in logs), "numeric_odometry_evidence_missing")
            evidence["minimum_input_log_time_ns_private"] = min(int(item[0]) for item in logs)
        def path(role, position):
            return _unpack_path(db.execute("SELECT path FROM geometry WHERE role=? AND position=?", (role, position)).fetchone()[0])
        try:
            values, distance, station = aligned_residual(path("estimate", row["estimate_message_index"]), path("reference", row["reference_message_index"]))
            row.update(residuals_m=values, anchor_distance_m=distance, reference_anchor_station_m=station)
        except GeometryValidationError as error:
            if error.code != "residual_non_finite":
                raise
            row["residual_failure_code"] = error.code
        workspace.checkpoint()
    return rows
