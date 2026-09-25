"""Bounded batch02 extraction using the reviewed geometry and indexed reader."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any, Iterable

import numpy as np

from ..domain.conditional_features import (
    ConditionalFeatureError, ODOMETRY_SPEED_INTERVAL_NS,
    selected_keep_lane_confidences, summarize_estimate_conditions,
)
from ..domain.exploratory_residuals import aligned_residual, checked_speed, sequence_layout
from ..domain.geometry_validation import GeometryValidationError
from ..domain.independent_outing_intake import EXPECTED_TOPOLOGY_SOURCE
from ..domain.motion import OdometrySample, Pose2D
from ..domain.recording_pair_diagnostics import PairDiagnostics
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from .independent_outing_intake import _DecodedEstimate, iter_geometry_records
from .mcap import McapDependencyError
from .odometry import DEFAULT_ODOMETRY_SCHEMA, DEFAULT_ODOMETRY_TOPIC, _finite_number, _timestamp_ns
from .recording_pair_feasibility import (
    MAX_MESSAGES_PER_TOPIC, MAX_SPOOL_BYTES, TOPICS, RecordingReadError, ResourceLimitError,
    _count_geometry, _iter_messages, _unpack_path,
)

TOPIC_LIMITS = {**{topic: MAX_MESSAGES_PER_TOPIC for topic in TOPICS}, DEFAULT_ODOMETRY_TOPIC: 300_000}


def _time_key(value: int) -> str:
    # MCAP nanosecond chronology is uint64. Fixed-width decimal preserves exact
    # ordering in SQLite even beyond signed int64, without floating conversion.
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError("timestamp must be a uint64 integer")
    return f"{value:020d}"


def _failure(error: Exception) -> str:
    # Only internal coded validation exceptions or a static class name; never
    # raw exception messages, payload coordinates or decoder diagnostics.
    return str(error.code) if isinstance(error, (ConditionalFeatureError, GeometryValidationError)) else type(error).__name__


class _OdometryStore:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.message_count = 0
        self.failures: Counter[str] = Counter()
        self.schemas: Counter[str] = Counter()
        self.db.execute("CREATE TABLE odometry (time TEXT PRIMARY KEY, log TEXT, publish TEXT, x REAL, y REAL, yaw REAL, multiplicity INTEGER, conflict INTEGER)")
        self.db.execute("CREATE INDEX usable_odometry ON odometry(time) WHERE conflict=0")

    def add(self, schema, channel, message, decoded):
        self.message_count += 1
        if self.message_count > TOPIC_LIMITS[DEFAULT_ODOMETRY_TOPIC]:
            raise ResourceLimitError("decoded_topic_count_exceeds_resource_limit")
        identity = f"{schema.name}|{channel.message_encoding}|sha256:{hashlib.sha256(schema.data).hexdigest()}"
        self.schemas[identity] += 1
        if schema.name != DEFAULT_ODOMETRY_SCHEMA or channel.message_encoding.lower() != "protobuf":
            self.failures["odometry_schema_or_encoding_mismatch"] += 1
            return
        try:
            key = _time_key(_timestamp_ns(decoded))
            log, publish = _time_key(int(message.log_time)), _time_key(int(message.publish_time))
            pose = tuple(_finite_number(decoded, name) for name in ("x_position", "y_position", "yaw_angle"))
        except (ValueError, TypeError, OverflowError):
            self.failures["odometry_invalid_message"] += 1
            return
        old = self.db.execute("SELECT log,publish,x,y,yaw,multiplicity,conflict FROM odometry WHERE time=?", (key,)).fetchone()
        if old is None:
            self.db.execute("INSERT INTO odometry VALUES (?,?,?,?,?,?,1,0)", (key, log, publish, *pose))
        else:
            conflict = int(bool(old[6]) or tuple(old[2:5]) != pose)
            # Identical duplicates keep the earliest recorded representative,
            # matching the established duplicate policy. Conflicts stay unusable.
            first_log, first_publish = min((log, publish), (old[0], old[1]))
            self.db.execute("UPDATE odometry SET log=?,publish=?,multiplicity=?,conflict=? WHERE time=?",
                            (first_log, first_publish, old[5] + 1, conflict, key))

    def summary(self):
        rows = self.db.execute("SELECT COUNT(*), COALESCE(SUM(multiplicity>1),0), COALESCE(SUM(multiplicity-1),0), COALESCE(SUM(conflict),0), COALESCE(SUM(CASE WHEN conflict THEN multiplicity ELSE 0 END),0), COALESCE(MAX(multiplicity),0) FROM odometry").fetchone()
        return {"message_count": self.message_count, "distinct_valid_timestamp_count": rows[0],
            "duplicate_timestamp_group_count": rows[1], "duplicate_message_count": rows[2],
            "conflicting_timestamp_group_count": rows[3], "discarded_conflicting_message_count": rows[4],
            "maximum_timestamp_multiplicity": rows[5], "schema_counts": dict(sorted(self.schemas.items())),
            "failure_counts": dict(sorted(self.failures.items()))}

    def speed(self, time: int, log_time: int):
        if self.message_count == 0:
            return None, {}, ("odometry_stream_empty",)
        if self.failures or len(self.schemas) != 1:
            return None, {}, ("odometry_stream_invalid_or_schema_changed",)
        selected = {}
        try:
            if time < ODOMETRY_SPEED_INTERVAL_NS:
                raise ConditionalFeatureError("odometry_speed_history_outside_coverage", "history before zero")
            for target in (time - ODOMETRY_SPEED_INTERVAL_NS, time):
                for operator, direction in (("<=", "DESC"), (">=", "ASC")):
                    row = self.db.execute(f"SELECT time,log,publish,x,y,yaw FROM odometry WHERE conflict=0 AND time {operator} ? ORDER BY time {direction} LIMIT 1", (_time_key(target),)).fetchone()
                    if row is None:
                        raise GeometryValidationError("odometry_reference_time_outside_coverage", "bracket missing")
                    selected[int(row[0])] = OdometrySample(int(row[0]), int(row[1]), int(row[2]), Pose2D(*row[3:]))
            return checked_speed([selected[k] for k in sorted(selected)], time, log_time)
        except (ConditionalFeatureError, GeometryValidationError, ValueError, TypeError) as error:
            return None, {}, (_failure(error),)


def _estimate_features(record: _DecodedEstimate):
    try:
        values = summarize_estimate_conditions(record.curve, record.path, selected_keep_lane_confidences(record.decoded))
        vector = [float(getattr(values, name)) for name in BMW_CONDITION_FEATURE_NAMES[1:]]
        if not np.all(np.isfinite(vector)):
            raise ConditionalFeatureError("estimate_inputs_non_finite", "finite inputs required")
        return vector, None
    except (ConditionalFeatureError, GeometryValidationError, ValueError, TypeError, AttributeError) as error:
        return None, _failure(error)


def _extract_stream(messages: Iterable[Any], db: sqlite3.Connection, expected_counts, expected_diagnostics):
    odometry = _OdometryStore(db)
    db.execute("CREATE TABLE estimate_inputs (position INTEGER PRIMARY KEY, time TEXT, log TEXT, publish TEXT, features TEXT, failure TEXT)")

    def geometry_messages():
        for item in messages:
            if item[1].topic == DEFAULT_ODOMETRY_TOPIC:
                odometry.add(*item)
            else:
                yield item

    def observed_records():
        with closing(iter_geometry_records(geometry_messages(), collect_reference_diagnostics=True)) as records:
            for record in records:
                if isinstance(record, _DecodedEstimate):
                    frame = record.frame
                    if (record.path is not None and frame is not None and
                            frame.estimator_state == "available_no_error" and frame.topology_source == EXPECTED_TOPOLOGY_SOURCE):
                        features, failure = _estimate_features(record)
                        db.execute("INSERT INTO estimate_inputs VALUES (?,?,?,?,?,?)",
                            (record.message_index, _time_key(record.source_time_ns), _time_key(frame.log_time_ns),
                             _time_key(frame.publish_time_ns), json.dumps(features, allow_nan=False), failure))
                    del frame
                yield record
                del record

    candidates = []
    def on_sensor_pair(pair_index, pair):
        if len(candidates) >= expected_counts["sensor_anchored_h100_pair_count"]:
            raise RecordingReadError("preserved_candidate_count_exceeded")
        candidates.append((pair_index, pair))

    diagnostics = PairDiagnostics()
    with closing(observed_records()) as records:
        counts = _count_geometry(records, db, diagnostics, on_sensor_pair=on_sensor_pair)
    details = diagnostics.summary()
    if counts != expected_counts:
        raise RecordingReadError("preserved_counts_mismatch")
    if details != expected_diagnostics:
        raise RecordingReadError("preserved_diagnostics_mismatch")
    if len(candidates) != counts["sensor_anchored_h100_pair_count"]:
        raise RecordingReadError("candidate_identity_count_mismatch")
    # All original observations agree before any residual value is calculated.
    rows = []
    for pair_index, pair in candidates:
        row = db.execute("SELECT time,log,publish,features,failure FROM estimate_inputs WHERE position=?", (pair.first_position,)).fetchone()
        if row is None:
            raise RecordingReadError("candidate_input_identity_missing")
        time, log, publish = map(int, row[:3])
        features = json.loads(row[3])
        speed, evidence, speed_failures = odometry.speed(time, log)
        failures = ([] if row[4] is None else [f"estimate_features_{row[4]}"]) + list(speed_failures)
        conditions = [speed, *features] if not failures else None
        rows.append({"recording_id": "pending", "candidate_index": len(rows), "pair_index": pair_index,
            "estimate_message_index": pair.first_position, "reference_message_index": pair.second_position,
            "estimate_source_time_ns_private": time, "reference_source_time_ns_private": time - pair.delta_ns,
            "estimate_log_time_ns_private": log, "estimate_publish_time_ns_private": publish,
            "signed_reference_minus_estimate_ns": -pair.delta_ns,
            "condition_failure_codes": failures, "speed_bracket_evidence": evidence,
            "conditions": conditions, "residuals_m": None, "residual_failure_code": None,
            "anchor_distance_m": None, "reference_anchor_station_m": None})
    _, input_sequences = sequence_layout([r for r in rows if r["conditions"] is not None])
    for row in rows:
        def read_path(role, position):
            raw = db.execute("SELECT path FROM geometry WHERE role=? AND position=?", (role, position)).fetchone()[0]
            return _unpack_path(raw)
        try:
            values, distance, station = aligned_residual(read_path("estimate", row["estimate_message_index"]),
                                                       read_path("reference", row["reference_message_index"]))
            row.update(residuals_m=values, anchor_distance_m=distance, reference_anchor_station_m=station)
        except (GeometryValidationError, ValueError, TypeError) as error:
            row["residual_failure_code"] = _failure(error)
    return {"status": "complete", "failure_code": None, "legacy_counts_match_preserved": True,
        "diagnostics_match_preserved": True, "counts": counts, "odometry": odometry.summary(),
        "input_ready_sequence_count_before_residuals": len(input_sequences), "candidates": rows}


def inconclusive(code: str):
    return {"status": "inconclusive", "failure_code": code, "legacy_counts_match_preserved": None,
        "diagnostics_match_preserved": None, "counts": None, "odometry": None,
        "input_ready_sequence_count_before_residuals": None, "candidates": None}


def inspect_recording_residuals(path: Path, scratch: Path, expected_counts, expected_diagnostics):
    """Discard incomplete streams/changed observations and remove the private spool."""
    try:
        with TemporaryDirectory(prefix="mpr-residuals-", dir=scratch) as temporary:
            with closing(sqlite3.connect(str(Path(temporary) / "geometry.sqlite"))) as db:
                db.execute("PRAGMA page_size=4096")
                db.execute("PRAGMA cache_size=-4096")
                db.execute("PRAGMA mmap_size=0")
                db.execute("PRAGMA temp_store=FILE")
                db.execute(f"PRAGMA max_page_count={MAX_SPOOL_BYTES // 4096}")
                db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role, position))")
                with closing(_iter_messages(path, topic_limits=TOPIC_LIMITS)) as messages:
                    return _extract_stream(messages, db, expected_counts, expected_diagnostics)
    except McapDependencyError:
        raise
    except (ResourceLimitError, RecordingReadError) as error:
        return inconclusive(str(error))
    except MemoryError:
        return inconclusive("memory_limit")
    except Exception as error:
        return inconclusive(type(error).__name__)
