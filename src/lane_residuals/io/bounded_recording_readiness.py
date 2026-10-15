"""Incremental scientific sink for the reviewed disk-index container reader."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from types import SimpleNamespace

from ..domain.independent_outing_intake import EXPECTED_TOPOLOGY_SOURCE
from ..domain.recording_ingestion import ClockOrderSummary, RecordingIngestionError, summarize_support
from ..domain.recording_readiness import exclusive_attrition
from ..domain.recording_readiness_bindings import LATE_ESTIMATE_BINDINGS, classify
from .exploratory_residuals import _OdometryStore, _estimate_features, _finish_conditions, _time_key
from .independent_outing_intake import _DecodedEstimate, iter_geometry_records
from .recording_pair_feasibility import GeometryStaging
from ..domain.recording_pair_diagnostics import PairDiagnostics
from .recording_readiness_resources import scientific_failure

TOPIC_ROLES = {"/adp/estimated_drive_paths":"estimate", "/adp/road_lane_map_based":"reference", "/adp/odometry":"odometry"}
TOPIC_LIMITS = {topic:1_000_000 if role=="odometry" else 100_000 for topic,role in TOPIC_ROLES.items()}
REVISION = "v0.19.11-bounded-recording-readiness-2026-10-15-a1"


class _BoundedOdometryStore(_OdometryStore):
    descriptor_unavailable = False

    def speed(self, time, log_time):
        if self.descriptor_unavailable:
            code = "odometry_stream_empty" if self.message_count == 0 else "odometry_stream_invalid_or_schema_changed"
            return None, {}, (code,)
        return super().speed(time, log_time)


class ScientificSink:
    def __init__(self, workspace):
        self.workspace, self.db = workspace, workspace.science
        self.failure_code = None
        self.binding_observations = None
        self._bindings, self._schemas, self._descriptors = {}, {}, {}
        self._actual = Counter()
        self._source = {role:ClockOrderSummary() for role in ("estimate", "reference")}
        self._logs = {topic:ClockOrderSummary() for topic in TOPIC_ROLES}
        self._diagnostics = PairDiagnostics()
        self.geometry = GeometryStaging(self.db, self._diagnostics)
        self.odometry = _BoundedOdometryStore(self.db, message_limit=TOPIC_LIMITS["/adp/odometry"])
        self.db.execute("CREATE TABLE geometry (role TEXT, position INTEGER, metadata TEXT, path BLOB, PRIMARY KEY(role,position))")
        self.db.execute("CREATE TABLE estimate_inputs (position INTEGER PRIMARY KEY, time TEXT, log TEXT, publish TEXT, features TEXT, failure TEXT)")

    def configure(self, selected):
        self._selected = selected

    def register_schema(self, schema, empty_message):
        self._schemas[schema.id] = schema
        self._descriptors[schema.id] = empty_message.DESCRIPTOR
        for key, channel in self._selected.items():
            if channel["schema_id"] != schema.id:
                continue
            role = TOPIC_ROLES[channel["topic"]]
            digest, cause = classify(empty_message, role, schema.name, channel["message_encoding"])
            self._bindings[key] = {"topic":channel["topic"], "role":role, "channel_id":key, "schema_id":schema.id,
                "message_file_descriptor_sha256":digest, "binding_status":"supported" if cause is None else "unsupported", "binding_failure_code":cause}
        self.workspace.checkpoint()

    def bindings_complete(self):
        if set(self._bindings) != set(self._selected):
            raise RecordingIngestionError("readiness_binding_observation_incomplete")
        self.binding_observations = sorted(self._bindings.values(), key=lambda r:(r["topic"],r["channel_id"]))
        self.odometry.descriptor_unavailable = any(r["role"]=="odometry" and r["binding_status"]=="unsupported" for r in self.binding_observations)
        for role in ("estimate", "reference"):
            if any(r["role"]==role and r["binding_status"]=="unsupported" for r in self.binding_observations):
                self.failure_code = "scientific_binding_unsupported_"+role+"_descriptor"
                break
        self.workspace.observations.phase("selected_decode")
        self.workspace.checkpoint()

    def _unsupported(self, binding, cause):
        binding.update(binding_status="unsupported", binding_failure_code=cause)
        if binding["role"] in ("estimate", "reference"):
            self.failure_code = "scientific_binding_unsupported_"+binding["role"]+"_descriptor"
        else:
            self.odometry.descriptor_unavailable = True

    def consume(self, channel_id, log_time, publish_time, decoded):
        channel_values = self._selected[channel_id]
        topic = channel_values["topic"]
        self._actual[topic] += 1
        if self._actual[topic] > TOPIC_LIMITS[topic]:
            raise RecordingIngestionError("scientific_actual_topic_limit")
        if (sum(self._actual.values())-1) % 1024 == 0:
            self.workspace.checkpoint()
        if self.failure_code is not None:
            return
        try:
            self._consume(channel_id, log_time, publish_time, decoded)
        except Exception as error:
            # Science cannot masquerade as measured zero. Continue container
            # verification without further scientific writes when possible.
            self.failure_code = scientific_failure(error)

    def _consume(self, channel_id, log_time, publish_time, decoded):
        channel_values = self._selected[channel_id]
        binding = self._bindings[channel_id]
        role, topic = binding["role"], binding["topic"]
        schema = self._schemas[binding["schema_id"]]
        channel = SimpleNamespace(topic=topic, message_encoding=channel_values["message_encoding"])
        message = SimpleNamespace(log_time=log_time, publish_time=publish_time)
        self._logs[topic].add(log_time)
        if getattr(decoded, "DESCRIPTOR", None) is not self._descriptors[schema.id]:
            digest, cause = classify(decoded, role, schema.name, channel.message_encoding)
            if cause is not None or digest != binding["message_file_descriptor_sha256"]:
                self._unsupported(binding, cause or role+"_descriptor_fields_unsupported")
                if role != "odometry":
                    return
        if role == "odometry":
            if binding["binding_status"] == "unsupported":
                import hashlib
                identity = f"{schema.name}|{channel.message_encoding}|sha256:{hashlib.sha256(schema.data).hexdigest()}"
                self.odometry.message_count += 1
                self.odometry.schemas[identity] += 1
                cause = "odometry_schema_or_encoding_mismatch" if binding["binding_failure_code"] == "odometry_schema_or_encoding_mismatch" else "odometry_invalid_message"
                self.odometry.failures[cause] += 1
            else:
                self.odometry.add(schema, channel, message, decoded)
            return
        position = len(self.geometry.times[role])
        record = next(iter_geometry_records(((schema,channel,message,decoded),), collect_reference_diagnostics=True))
        record = replace(record, message_index=position)
        if isinstance(record, _DecodedEstimate) and record.frame is not None:
            record = replace(record, frame=replace(record.frame, message_index=position))
        if role == "estimate" and record.failure_code in LATE_ESTIMATE_BINDINGS:
            cause = record.failure_code if record.failure_code == "estimate_schema_or_encoding_mismatch" else record.failure_code[len("estimate_"):]
            self._unsupported(binding, cause)
            return
        self._source[role].add(record.source_time_ns)
        if isinstance(record, _DecodedEstimate):
            frame = record.frame
            if record.path is not None and frame is not None and frame.estimator_state == "available_no_error" and frame.topology_source == EXPECTED_TOPOLOGY_SOURCE:
                features, failure = _estimate_features(record)
                if failure in ("estimate_confidence_field_unavailable", "estimate_drive_paths_unavailable", "estimate_role_schema_unavailable"):
                    self._unsupported(binding, "estimate_descriptor_fields_unsupported")
                    return
                self.db.execute("INSERT INTO estimate_inputs VALUES (?,?,?,?,?,?)", (position, _time_key(record.source_time_ns), _time_key(frame.log_time_ns), _time_key(frame.publish_time_ns), json.dumps(features,allow_nan=False), failure))
        self.geometry.add(record)

    def finalize(self):
        self.workspace.checkpoint()
        if self.failure_code is not None:
            return None, "not_assessed", False
        candidates=[]
        counts=self.geometry.finish(on_sensor_pair=lambda index,pair:candidates.append((index,pair)), checkpoint=self.workspace.checkpoint)
        result=_finish_conditions(self.db,self.odometry,counts,self._diagnostics.summary(),candidates,checkpoint=self.workspace.checkpoint)
        rows=result["candidates"]
        odometry=result["odometry"]
        available=odometry["message_count"]>0 and not odometry["failure_counts"] and len(odometry["schema_counts"])==1 and not any(r["role"]=="odometry" and r["binding_status"]=="unsupported" for r in self.binding_observations)
        if not available:
            for row in rows:
                row["conditions"]=None
        readiness={"counts":counts,"diagnostics":result["diagnostics"],"odometry":odometry,
            "source_clock_order":{k:v.summary() for k,v in self._source.items()},"log_clock_order":{k:v.summary() for k,v in self._logs.items()},
            "sensor_geometry_support":summarize_support(rows),"complete_condition_support":summarize_support([r for r in rows if r["conditions"] is not None]),
            "condition_failure_counts":dict(sorted(Counter(code for r in rows for code in r["condition_failure_codes"]).items())),
            "exclusive_attrition":exclusive_attrition(counts,rows,available)}
        self.workspace.checkpoint()
        return readiness, "available_for_checks" if available else "unavailable_odometry", available
