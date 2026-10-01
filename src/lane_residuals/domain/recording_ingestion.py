"""Development-only source declarations and recording-local support summaries."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import PurePosixPath
import re
from typing import Any

from .exploratory_residuals import sequence_layout

CONTRACT_REVISION = "v0.19.6-generic-recording-readiness-2026-10-01-a1"
SPECIFICATION_VERSION = "mpr_recording_ingestion_v1"
MAX_RECORDINGS = 64
SOURCE_FIELDS = frozenset({
    "source_locator_private", "source_recording_id_private", "physical_session_id_private",
    "physical_session_evidence_private", "acquisition_start_utc_private", "acquisition_end_utc_private",
    "export_settings_private", "merged_input_mcap_count", "redownload_evidence_private",
})
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


class RecordingIngestionError(ValueError):
    """An MPR-authored static code, safe for logs without private input values."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _keys(value: Any, expected: set | frozenset, code: str):
    if not isinstance(value, dict) or set(value) != expected:
        raise RecordingIngestionError(code)


def parse_specification(value: Any) -> dict[str, Any]:
    """Validate explicit metadata; never infer sessions or dates from file names."""
    _keys(value, {"schema_version", "batch_id", "purpose", "recordings"}, "invalid_specification_fields")
    if value["schema_version"] != SPECIFICATION_VERSION or value["purpose"] != "development_only":
        raise RecordingIngestionError("development_only_specification_required")
    if not isinstance(value["batch_id"], str) or not _IDENTIFIER.fullmatch(value["batch_id"]):
        raise RecordingIngestionError("invalid_batch_id")
    rows = value["recordings"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_RECORDINGS:
        raise RecordingIngestionError("invalid_recording_count")
    ids, paths = set(), set()
    for row in rows:
        _keys(row, {"recording_id", "local_path_private", "source"}, "invalid_recording_fields")
        identifier, name = row["recording_id"], row["local_path_private"]
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier) or identifier in ids:
            raise RecordingIngestionError("invalid_or_duplicate_recording_id")
        if not isinstance(name, str) or not name or "\x00" in name:
            raise RecordingIngestionError("invalid_local_path")
        path = PurePosixPath(name)
        if not path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".mcap" or str(path) != name or name in paths:
            raise RecordingIngestionError("absolute_distinct_mcap_paths_required")
        ids.add(identifier)
        paths.add(name)
        source = row["source"]
        _keys(source, SOURCE_FIELDS, "invalid_source_fields")
        for key in SOURCE_FIELDS - {"merged_input_mcap_count"}:
            item = source[key]
            if item is not None and (not isinstance(item, str) or not item.strip() or len(item) > 8192):
                raise RecordingIngestionError("source_values_must_be_text_or_null")
        count = source["merged_input_mcap_count"]
        if count is not None and (type(count) is not int or not 1 <= count <= 1_000_000):
            raise RecordingIngestionError("invalid_merged_input_count")
        if (source["physical_session_id_private"] is None) != (source["physical_session_evidence_private"] is None):
            raise RecordingIngestionError("session_identity_requires_evidence")
        start, end = source["acquisition_start_utc_private"], source["acquisition_end_utc_private"]
        if (start is None) != (end is None):
            raise RecordingIngestionError("acquisition_range_requires_both_endpoints")
        if start is not None:
            try:
                times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in (start, end)]
            except ValueError as error:
                raise RecordingIngestionError("explicit_utc_acquisition_range_required") from error
            if any(t.utcoffset() != timedelta(0) for t in times) or times[1] <= times[0]:
                raise RecordingIngestionError("explicit_utc_acquisition_range_required")
    return value


def source_declaration_status(source: dict[str, Any]) -> dict[str, Any]:
    """A declaration is retained as evidence to review, not a verified outing."""
    return {
        "source_locator_declared": source["source_locator_private"] is not None,
        "source_recording_id_declared": source["source_recording_id_private"] is not None,
        "physical_session_declared_with_evidence": source["physical_session_id_private"] is not None,
        "acquisition_utc_range_declared": source["acquisition_start_utc_private"] is not None,
        "export_settings_declared": source["export_settings_private"] is not None,
        "claimed_merged_input_mcap_count": source["merged_input_mcap_count"],
        "redownload_evidence_declared": source["redownload_evidence_private"] is not None,
        "physical_session_identity_verified": False,
    }


def summarize_support(rows) -> dict[str, Any]:
    _, sequences = sequence_layout(rows)
    return {
        "frame_count": len(rows), "sequence_count": len(sequences),
        "transition_count": sum(s["transition_count"] for s in sequences),
        "maximum_frame_count": max((s["frame_count"] for s in sequences), default=0),
        "maximum_duration_ns": max((s["duration_ns"] for s in sequences), default=0),
        "sequence_length_histogram": dict(sorted(Counter(str(s["frame_count"]) for s in sequences).items())),
        "sequence_start_reason_counts": dict(sorted(Counter(reason for s in sequences for reason in s["start_reasons"]).items())),
    }


class ClockOrderSummary:
    """Compact original-storage-order chronology; no sorting or epoch inference."""

    def __init__(self):
        self.count = self.missing = self.backwards = self.repeated = 0
        self.minimum = self.maximum = self.previous = None

    def add(self, time):
        self.count += 1
        if time is None:
            self.missing += 1
        else:
            self.minimum = time if self.minimum is None else min(self.minimum, time)
            self.maximum = time if self.maximum is None else max(self.maximum, time)
            if self.previous is not None:
                self.backwards += int(time < self.previous)
                self.repeated += int(time == self.previous)
        self.previous = time

    def summary(self):
        return {"message_count": self.count, "missing_timestamp_count": self.missing,
                "backward_step_count": self.backwards, "repeated_adjacent_timestamp_count": self.repeated,
                "minimum_timestamp_ns_decimal": None if self.minimum is None else str(self.minimum),
                "maximum_timestamp_ns_decimal": None if self.maximum is None else str(self.maximum)}
