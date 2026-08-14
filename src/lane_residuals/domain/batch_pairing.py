"""Corpus aggregation for diagnostic EDP--RLMB pairing audits.

This module aggregates the diagnostic-only outputs produced by
``pairing_audit_cli``.  It deliberately uses complete, fixed station cohorts
for 0--60 m and 0--100 m.  It never creates training labels or fits a model.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from ..io.reports import write_csv_rows, write_strict_json


HORIZON_60_M = tuple(float(value) for value in range(0, 61, 5))
HORIZON_100_M = tuple(float(value) for value in range(0, 101, 5))
CANONICAL_STATIONS_M = HORIZON_100_M


class BatchAggregationError(ValueError):
    """Raised when single-recording outputs violate batch invariants."""


@dataclass(frozen=True)
class RecordingAuditData:
    """One single-recording diagnostic audit and its corpus assignment."""

    recording_id: str
    drive_id: str
    mcap_filename: str
    status: str
    output_directory: str
    summary: Mapping[str, Any] = field(default_factory=dict, repr=False)
    pair_rows: tuple[Mapping[str, str], ...] = field(default_factory=tuple, repr=False)
    station_rows: tuple[Mapping[str, str], ...] = field(default_factory=tuple, repr=False)
    chain_rows: tuple[Mapping[str, str], ...] = field(default_factory=tuple, repr=False)
    inventory_rows: tuple[Mapping[str, str], ...] = field(default_factory=tuple, repr=False)
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


def read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    """Read one audit CSV without guessing numeric types."""

    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def load_recording_audit(
    *,
    recording_id: str,
    drive_id: str,
    mcap_filename: str,
    output_directory: Path,
) -> RecordingAuditData:
    """Load the exact output set written by one successful pairing audit."""

    required = {
        "summary": output_directory / "pairing_summary.json",
        "pairs": output_directory / "pairing_audit.csv",
        "stations": output_directory / "diagnostic_disagreement.csv",
        "chains": output_directory / "rlmb_chain_audit.csv",
        "inventory": output_directory / "message_inventory.csv",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise BatchAggregationError(
            "recording audit is missing required outputs: " + ", ".join(missing)
        )
    with required["summary"].open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    if tuple(float(value) for value in summary.get("stations_m", ())) != CANONICAL_STATIONS_M:
        raise BatchAggregationError(
            "single-recording audit does not use the canonical 0:5:100 m grid"
        )
    return RecordingAuditData(
        recording_id=recording_id,
        drive_id=drive_id,
        mcap_filename=mcap_filename,
        status="succeeded",
        output_directory=str(output_directory),
        summary=summary,
        pair_rows=read_csv_rows(required["pairs"]),
        station_rows=read_csv_rows(required["stations"]),
        chain_rows=read_csv_rows(required["chains"]),
        inventory_rows=read_csv_rows(required["inventory"]),
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise BatchAggregationError("batch inputs must not contain NaN or infinity")
    return result


def _optional_int(value: Any) -> int | None:
    number = _optional_float(value)
    if number is None:
        return None
    integer = int(number)
    if float(integer) != number:
        raise BatchAggregationError(f"expected an integer value, received {value!r}")
    return integer


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise BatchAggregationError(f"expected a Boolean value, received {value!r}")


def _station_key(value: Any) -> float:
    station = _optional_float(value)
    if station is None:
        raise BatchAggregationError("station rows require a station value")
    for canonical in CANONICAL_STATIONS_M:
        if abs(station - canonical) <= 1e-8:
            return canonical
    raise BatchAggregationError(f"unexpected non-canonical station {station}")


def _pair_vectors(
    recording: RecordingAuditData,
) -> dict[int, dict[float, float]]:
    vectors: dict[int, dict[float, float]] = defaultdict(dict)
    for row in recording.station_rows:
        pair_index = _optional_int(row.get("pair_index"))
        lateral = _optional_float(row.get("diagnostic_lateral_m"))
        if pair_index is None or lateral is None:
            raise BatchAggregationError("diagnostic station row is missing pair or lateral value")
        station = _station_key(row.get("station_m"))
        if station in vectors[pair_index]:
            raise BatchAggregationError(
                f"duplicate station {station:g} for {recording.recording_id} pair {pair_index}"
            )
        vectors[pair_index][station] = lateral
    return dict(vectors)


def fixed_horizon_vectors(
    recording: RecordingAuditData,
) -> dict[int, dict[int, tuple[float, ...]]]:
    """Return complete H60/H100 vectors keyed by pair index.

    Eligibility is taken from the single-recording pair audit.  Missing station
    rows for an eligible pair are an invariant violation rather than an
    available-case fallback.
    """

    if not recording.succeeded:
        return {60: {}, 100: {}}
    station_vectors = _pair_vectors(recording)
    pair_rows: dict[int, Mapping[str, str]] = {}
    for row in recording.pair_rows:
        pair_index = _optional_int(row.get("pair_index"))
        if pair_index is None or pair_index in pair_rows:
            raise BatchAggregationError(
                f"invalid or duplicate pair index in {recording.recording_id}"
            )
        pair_rows[pair_index] = row

    result: dict[int, dict[int, tuple[float, ...]]] = {60: {}, 100: {}}
    for pair_index, row in pair_rows.items():
        eligible_60 = _optional_float(
            row.get("diagnostic_primary_lateral_rms_m")
        ) is not None
        eligible_100 = _optional_float(row.get("diagnostic_lateral_rms_m")) is not None
        if eligible_100 and not eligible_60:
            raise BatchAggregationError(
                f"H100 pair is not H60 eligible in {recording.recording_id}"
            )
        observed = station_vectors.get(pair_index, {})
        for horizon, eligible, stations in (
            (60, eligible_60, HORIZON_60_M),
            (100, eligible_100, HORIZON_100_M),
        ):
            if not eligible:
                continue
            missing = [station for station in stations if station not in observed]
            if missing:
                raise BatchAggregationError(
                    f"{recording.recording_id} pair {pair_index} is H{horizon} "
                    f"eligible but lacks stations {missing}"
                )
            result[horizon][pair_index] = tuple(observed[station] for station in stations)
    if not set(result[100]).issubset(result[60]):
        raise BatchAggregationError("H100 cohort must be a subset of H60")
    return result


def _percentile(values: np.ndarray, quantile: float) -> float:
    return float(np.percentile(values, quantile))


def _scope_members(
    recordings: Sequence[RecordingAuditData],
) -> dict[tuple[str, str], tuple[RecordingAuditData, ...]]:
    successful = tuple(recording for recording in recordings if recording.succeeded)
    scopes: dict[tuple[str, str], tuple[RecordingAuditData, ...]] = {}
    for recording in successful:
        scopes[("recording", recording.recording_id)] = (recording,)
    drive_ids = sorted({recording.drive_id for recording in successful})
    for drive_id in drive_ids:
        scopes[("drive", drive_id)] = tuple(
            recording for recording in successful if recording.drive_id == drive_id
        )
    scopes[("overall", "overall")] = successful
    return scopes


def aggregate_fixed_cohorts(
    recordings: Sequence[RecordingAuditData],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, int], dict[int, tuple[float, ...]]]]:
    """Aggregate fixed H60/H100 cohorts for recording, drive, and corpus scopes."""

    vectors_by_recording = {
        recording.recording_id: fixed_horizon_vectors(recording)
        for recording in recordings
        if recording.succeeded
    }
    station_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    pair_vectors_by_scope: dict[
        tuple[str, int], dict[int, tuple[float, ...]]
    ] = {}
    for (scope_type, scope_id), members in _scope_members(recordings).items():
        for horizon, stations in ((60, HORIZON_60_M), (100, HORIZON_100_M)):
            keyed_vectors: list[tuple[tuple[str, int], tuple[float, ...]]] = []
            for recording in members:
                for pair_index, vector in vectors_by_recording[recording.recording_id][horizon].items():
                    keyed_vectors.append(((recording.recording_id, pair_index), vector))
            matrix = (
                np.asarray([vector for _, vector in keyed_vectors], dtype=np.float64)
                if keyed_vectors
                else np.empty((0, len(stations)), dtype=np.float64)
            )
            if matrix.shape != (len(keyed_vectors), len(stations)):
                raise BatchAggregationError("fixed-cohort matrix has an invalid shape")
            pair_rms = (
                np.sqrt(np.mean(np.square(matrix), axis=1))
                if len(matrix)
                else np.asarray([], dtype=np.float64)
            )
            scope_key = f"{scope_type}:{scope_id}"
            pair_vectors_by_scope[(scope_key, horizon)] = {
                index: vector for index, (_, vector) in enumerate(keyed_vectors)
            }
            for station_index, station in enumerate(stations):
                values = matrix[:, station_index]
                station_rows.append(
                    {
                        "scope_type": scope_type,
                        "scope_id": scope_id,
                        "horizon_m": horizon,
                        "station_m": station,
                        "cohort_pair_count": len(values),
                        "lateral_mean_m": None if not len(values) else float(np.mean(values)),
                        "lateral_rms_m": None if not len(values) else float(np.sqrt(np.mean(np.square(values)))),
                        "lateral_median_m": None if not len(values) else float(np.median(values)),
                        "lateral_p05_m": None if not len(values) else _percentile(values, 5.0),
                        "lateral_p95_m": None if not len(values) else _percentile(values, 95.0),
                    }
                )
            observation_count = int(matrix.size)
            horizon_rows.append(
                {
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "horizon_m": horizon,
                    "cohort_pair_count": len(matrix),
                    "station_count_per_pair": len(stations),
                    "pooled_observation_count": observation_count,
                    "contributing_recording_count": len(
                        {recording_id for recording_id, _ in (key for key, _ in keyed_vectors)}
                    ),
                    "pooled_lateral_mean_m": None if not observation_count else float(np.mean(matrix)),
                    "pooled_lateral_rms_m": None if not observation_count else float(np.sqrt(np.mean(np.square(matrix)))),
                    "pooled_lateral_median_m": None if not observation_count else float(np.median(matrix)),
                    "median_pair_lateral_rms_m": None if not len(pair_rms) else float(np.median(pair_rms)),
                    "p95_pair_lateral_rms_m": None if not len(pair_rms) else _percentile(pair_rms, 95.0),
                    "maximum_absolute_lateral_m": None if not observation_count else float(np.max(np.abs(matrix))),
                }
            )
    return station_rows, horizon_rows, pair_vectors_by_scope


def _split_semicolon_floats(value: Any) -> tuple[float, ...]:
    if value is None or value == "":
        return ()
    result = tuple(float(item) for item in str(value).split(";") if item != "")
    if not all(math.isfinite(item) for item in result):
        raise BatchAggregationError("junction values must be finite")
    return result


def _split_semicolon_bools(value: Any) -> tuple[bool, ...]:
    if value is None or value == "":
        return ()
    return tuple(_optional_bool(item) is True for item in str(value).split(";") if item != "")


def _finite_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "median": None, "p95": None, "maximum": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(array),
        "median": float(np.median(array)),
        "p95": _percentile(array, 95.0),
        "maximum": float(np.max(array)),
    }


def aggregate_rlmb_chains(
    recordings: Sequence[RecordingAuditData],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Aggregate topology and junction evidence with explicit denominators."""

    output: dict[str, dict[str, dict[str, Any]]] = {
        "recording": {},
        "drive": {},
        "overall": {},
    }
    for (scope_type, scope_id), members in _scope_members(recordings).items():
        rows = [row for member in members for row in member.chain_rows]
        auditable = [row for row in rows if _optional_int(row.get("segment_count")) is not None]
        terminations = Counter(str(row.get("termination_reason", "")) for row in auditable)
        gaps = [value for row in auditable for value in _split_semicolon_floats(row.get("junction_gaps_m"))]
        headings = [abs(value) for row in auditable for value in _split_semicolon_floats(row.get("junction_heading_deltas_rad"))]
        reciprocal_values = [value for row in auditable for value in _split_semicolon_bools(row.get("reciprocal_predecessor_links"))]
        no_link_count = sum(
            not _split_semicolon_bools(row.get("reciprocal_predecessor_links"))
            for row in auditable
        )
        geometry_failures = len(rows) - len(auditable)
        if len(terminations) and sum(terminations.values()) != len(auditable):
            raise BatchAggregationError("RLMB termination denominators do not reconcile")
        payload = {
            "map_message_count": len(rows),
            "chain_auditable_count": len(auditable),
            "map_geometry_failure_count": geometry_failures,
            "coverage_0_60_m_count": sum(
                (_optional_float(row.get("actual_forward_coverage_m")) or -math.inf) >= 60.0 - 1e-9
                for row in auditable
            ),
            "coverage_0_100_m_count": sum(
                (_optional_float(row.get("actual_forward_coverage_m")) or -math.inf) >= 100.0 - 1e-9
                for row in auditable
            ),
            "multi_segment_count": sum(
                (_optional_int(row.get("segment_count")) or 0) > 1 for row in auditable
            ),
            "termination_counts": dict(sorted(terminations.items())),
            "junction_link_count": len(reciprocal_values),
            "reciprocal_link_count": sum(reciprocal_values),
            "nonreciprocal_link_count": len(reciprocal_values) - sum(reciprocal_values),
            "no_link_chain_count_not_applicable": no_link_count,
            "junction_gap_m": _finite_summary(gaps),
            "absolute_junction_heading_delta_rad": _finite_summary(headings),
        }
        if not (
            payload["coverage_0_100_m_count"]
            <= payload["coverage_0_60_m_count"]
            <= payload["chain_auditable_count"]
        ):
            raise BatchAggregationError("RLMB coverage denominators do not reconcile")
        output[scope_type][scope_id] = payload
    return output


def source_time_envelope(recording: RecordingAuditData) -> tuple[int, int] | None:
    """Return the complete estimate-stream source-time envelope."""

    values = [
        _optional_int(row.get("source_time_ns_private"))
        for row in recording.inventory_rows
        if row.get("topic_role") == "estimate"
    ]
    finite = [value for value in values if value is not None]
    if not finite:
        return None
    return min(finite), max(finite)


def detect_drive_overlaps(
    recordings: Sequence[RecordingAuditData],
) -> list[dict[str, Any]]:
    """Report source-time interval overlaps; never silently deduplicate chunks."""

    overlaps: list[dict[str, Any]] = []
    by_drive: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for recording in recordings:
        if not recording.succeeded:
            continue
        envelope = source_time_envelope(recording)
        if envelope is not None:
            by_drive[recording.drive_id].append((*envelope, recording.recording_id))
    for drive_id, intervals in sorted(by_drive.items()):
        ordered = sorted(intervals)
        for index, (start, end, recording_id) in enumerate(ordered):
            for other_start, other_end, other_id in ordered[index + 1 :]:
                if other_start > end:
                    break
                overlap_ns = min(end, other_end) - max(start, other_start)
                if overlap_ns >= 0:
                    overlaps.append(
                        {
                            "drive_id": drive_id,
                            "first_recording_id": recording_id,
                            "second_recording_id": other_id,
                            "overlap_duration_ms": overlap_ns / 1e6,
                            "boundary_timestamp_shared": overlap_ns == 0,
                        }
                    )
    return overlaps


def temporal_diagnostic_rows(
    recordings: Sequence[RecordingAuditData],
    *,
    recording_tail_window_s: float,
    primary_tail_threshold_m: float | None,
    full_tail_threshold_m: float | None,
) -> list[dict[str, Any]]:
    """Build pair timelines with optional predeclared outcome-tail flags."""

    if recording_tail_window_s < 0.0 or not math.isfinite(recording_tail_window_s):
        raise ValueError("recording tail window must be finite and nonnegative")
    for name, threshold in (
        ("primary", primary_tail_threshold_m),
        ("full", full_tail_threshold_m),
    ):
        if threshold is not None and (threshold <= 0.0 or not math.isfinite(threshold)):
            raise ValueError(f"{name} tail threshold must be finite and positive")

    successful = [recording for recording in recordings if recording.succeeded]
    vectors = {
        recording.recording_id: fixed_horizon_vectors(recording)
        for recording in successful
    }
    envelopes = {
        recording.recording_id: source_time_envelope(recording)
        for recording in successful
    }
    drive_origins: dict[str, int] = {}
    for recording in successful:
        envelope = envelopes[recording.recording_id]
        if envelope is not None:
            drive_origins[recording.drive_id] = min(
                drive_origins.get(recording.drive_id, envelope[0]), envelope[0]
            )

    rows: list[dict[str, Any]] = []
    for recording in successful:
        envelope = envelopes[recording.recording_id]
        for pair in recording.pair_rows:
            pair_index = _optional_int(pair.get("pair_index"))
            if pair_index is None:
                raise BatchAggregationError("temporal pair requires a pair index")
            time_ns = _optional_int(pair.get("estimate_source_time_ns_private"))
            vector_60 = vectors[recording.recording_id][60].get(pair_index)
            vector_100 = vectors[recording.recording_id][100].get(pair_index)
            rms_60 = None if vector_60 is None else float(np.sqrt(np.mean(np.square(vector_60))))
            rms_100 = None if vector_100 is None else float(np.sqrt(np.mean(np.square(vector_100))))
            recording_relative = (
                None if time_ns is None or envelope is None else (time_ns - envelope[0]) / 1e9
            )
            seconds_from_end = (
                None if time_ns is None or envelope is None else (envelope[1] - time_ns) / 1e9
            )
            drive_relative = (
                None
                if time_ns is None or recording.drive_id not in drive_origins
                else (time_ns - drive_origins[recording.drive_id]) / 1e9
            )
            rows.append(
                {
                    "recording_id": recording.recording_id,
                    "drive_id": recording.drive_id,
                    "pair_index": pair_index,
                    "estimate_message_index": _optional_int(pair.get("estimate_message_index")),
                    "map_message_index": _optional_int(pair.get("map_message_index")),
                    "recording_relative_source_time_s": recording_relative,
                    "drive_relative_source_time_s": drive_relative,
                    "seconds_from_recording_end": seconds_from_end,
                    "in_final_recording_time_window": (
                        None if seconds_from_end is None else seconds_from_end <= recording_tail_window_s + 1e-12
                    ),
                    "recording_tail_window_s": recording_tail_window_s,
                    "h60_eligible": vector_60 is not None,
                    "h100_eligible": vector_100 is not None,
                    "h60_pair_lateral_rms_m": rms_60,
                    "h100_pair_lateral_rms_m": rms_100,
                    "h60_tail_threshold_m": primary_tail_threshold_m,
                    "h100_tail_threshold_m": full_tail_threshold_m,
                    "h60_outcome_tail_flag": (
                        None
                        if primary_tail_threshold_m is None or rms_60 is None
                        else rms_60 >= primary_tail_threshold_m
                    ),
                    "h100_outcome_tail_flag": (
                        None
                        if full_tail_threshold_m is None or rms_100 is None
                        else rms_100 >= full_tail_threshold_m
                    ),
                    "tail_thresholds_predeclared": (
                        primary_tail_threshold_m is not None or full_tail_threshold_m is not None
                    ),
                }
            )
    return rows


def recording_summary_rows(
    recordings: Sequence[RecordingAuditData],
    horizon_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Create one denominator-labelled row for every requested recording."""

    horizons = {
        (str(row["scope_id"]), int(row["horizon_m"])): row
        for row in horizon_rows
        if row["scope_type"] == "recording"
    }
    temporal_by_recording: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in temporal_rows:
        temporal_by_recording[str(row["recording_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for recording in recordings:
        summary = recording.summary
        h60 = horizons.get((recording.recording_id, 60), {})
        h100 = horizons.get((recording.recording_id, 100), {})
        temporal = temporal_by_recording.get(recording.recording_id, [])
        rows.append(
            {
                "recording_id": recording.recording_id,
                "drive_id": recording.drive_id,
                "mcap_filename_private": recording.mcap_filename,
                "status": recording.status,
                "error_code": recording.error_code,
                "error_message": recording.error_message,
                "estimate_message_count": summary.get("estimate_messages"),
                "map_message_count": summary.get("map_messages"),
                "mutual_nearest_pair_count": summary.get("complete_stream_mutual_nearest_pair_count"),
                "unmatched_estimate_message_count": summary.get("unmatched_estimate_message_count"),
                "unmatched_map_message_count": summary.get("unmatched_map_message_count"),
                "median_absolute_source_delta_ms": summary.get("median_absolute_source_delta_ms"),
                "rlmb_multi_segment_lane_count": summary.get("rlmb_multi_segment_lane_count"),
                "h60_complete_cohort_pair_count": h60.get("cohort_pair_count", 0),
                "h60_pooled_lateral_rms_m": h60.get("pooled_lateral_rms_m"),
                "h60_median_pair_lateral_rms_m": h60.get("median_pair_lateral_rms_m"),
                "h60_p95_pair_lateral_rms_m": h60.get("p95_pair_lateral_rms_m"),
                "h100_complete_cohort_pair_count": h100.get("cohort_pair_count", 0),
                "h100_pooled_lateral_rms_m": h100.get("pooled_lateral_rms_m"),
                "h100_median_pair_lateral_rms_m": h100.get("median_pair_lateral_rms_m"),
                "h100_p95_pair_lateral_rms_m": h100.get("p95_pair_lateral_rms_m"),
                "h60_predeclared_outcome_tail_pair_count": sum(row.get("h60_outcome_tail_flag") is True for row in temporal),
                "h100_predeclared_outcome_tail_pair_count": sum(row.get("h100_outcome_tail_flag") is True for row in temporal),
            }
        )
    return rows

