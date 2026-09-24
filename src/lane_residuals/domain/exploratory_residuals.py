"""Recording-local exploratory vectors; no outing identities or fitted model."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .alignment import compare_spatially_aligned_paths
from .conditional_features import derive_unsigned_odometry_speed
from .geometry_validation import GeometryValidationError
from .independent_outing_intake import MAXIMUM_ANCHOR_DISTANCE_M, MAXIMUM_SEQUENCE_GAP_NS, ODOMETRY_INTERPOLATION_GAP_NS
from .motion import OdometrySample
from .pairing import EgoRelativePath
from .residual_dataset import CANONICAL_MODEL_STATIONS_M
from .sequence_dataset import BMW_CONDITION_FEATURE_NAMES


def aligned_residual(estimate: EgoRelativePath, reference: EgoRelativePath) -> tuple[list[float], float, float]:
    """Reuse native projection, sign and no-extrapolation arithmetic exactly."""
    aligned = compare_spatially_aligned_paths(estimate, reference, stations_m=CANONICAL_MODEL_STATIONS_M)
    if aligned.anchor_distance_m > MAXIMUM_ANCHOR_DISTANCE_M:
        raise GeometryValidationError("anchor_distance_exceeds_1m_or_invalid", "anchor exceeds limit")
    values = aligned.disagreement.lateral_m
    if values.shape != (21,) or not np.all(np.isfinite(values)):
        raise GeometryValidationError("residual_non_finite", "finite H100 vector required")
    return values.tolist(), aligned.anchor_distance_m, aligned.reference_anchor_station_m


def checked_speed(samples: Sequence[OdometrySample], source_time_ns: int,
                  estimate_log_time_ns: int) -> tuple[float | None, dict[str, Any], tuple[str, ...]]:
    """Apply unchanged 50 ms speed arithmetic, then explicit recorded-clock checks.

    The lookup caller supplies exactly the bracketing samples from the complete
    duplicate-audited stream. There is no fallback, time shift or extrapolation.
    Log-time ordering is a recording-availability proxy, not a physical latency
    or clock-synchronization claim.
    """
    speed = derive_unsigned_odometry_speed(samples, source_time_ns,
        maximum_bracket_gap_ns=ODOMETRY_INTERPOLATION_GAP_NS)
    by_time = {sample.timestamp_ns: sample for sample in samples}
    times = sorted({speed.previous_pose.lower_timestamp_ns, speed.previous_pose.upper_timestamp_ns,
                    speed.current_pose.lower_timestamp_ns, speed.current_pose.upper_timestamp_ns})
    used = [by_time[t] for t in times]
    evidence = {
        "previous_lower_timestamp_ns_private": speed.previous_pose.lower_timestamp_ns,
        "previous_upper_timestamp_ns_private": speed.previous_pose.upper_timestamp_ns,
        "current_lower_timestamp_ns_private": speed.current_pose.lower_timestamp_ns,
        "current_upper_timestamp_ns_private": speed.current_pose.upper_timestamp_ns,
        "maximum_input_log_time_ns_private": max(s.log_time_ns for s in used),
        "maximum_input_publish_time_ns_private": max(s.publish_time_ns for s in used),
    }
    failures = []
    if max(times) > source_time_ns:
        failures.append("speed_uses_future_source_sample")
    if estimate_log_time_ns <= 0 or any(s.log_time_ns <= 0 for s in used):
        failures.append("speed_log_time_unavailable")
    elif any(s.log_time_ns > estimate_log_time_ns for s in used):
        failures.append("speed_input_logged_after_estimate")
    return (None if failures else speed.value_mps), evidence, tuple(failures)


def sequence_layout(rows: Sequence[Mapping[str, Any]]) -> tuple[list[int], list[dict[str, Any]]]:
    """Never bridge a file, skipped estimate/pair, or nonpositive/>200 ms gap.

    Estimate indices retain storage-order provenance. Reordered records may
    conservatively split support; no session continuity is inferred or repaired.
    """
    if not rows:
        return [0], []
    starts = [0]
    reasons = [["recording_start"]]
    for i in range(1, len(rows)):
        previous, current = rows[i - 1], rows[i]
        breaks = []
        if current["recording_id"] != previous["recording_id"]:
            breaks.append("recording_boundary")
        else:
            if current["estimate_message_index"] != previous["estimate_message_index"] + 1:
                breaks.append("estimate_index_gap")
            if current["pair_index"] != previous["pair_index"] + 1:
                breaks.append("pair_index_gap")
            gap = current["estimate_source_time_ns_private"] - previous["estimate_source_time_ns_private"]
            if gap <= 0:
                breaks.append("timestamp_non_monotonic")
            elif gap > MAXIMUM_SEQUENCE_GAP_NS:
                breaks.append("temporal_gap_exceeds_200ms")
        if breaks:
            starts.append(i)
            reasons.append(breaks)
    offsets = starts + [len(rows)]
    sequences = [{"sequence_index": i, "recording_id": rows[lo]["recording_id"],
        "start_row": lo, "stop_row": hi, "frame_count": hi - lo, "transition_count": hi - lo - 1,
        "duration_ns": rows[hi - 1]["estimate_source_time_ns_private"] - rows[lo]["estimate_source_time_ns_private"],
        "start_reasons": reasons[i]} for i, (lo, hi) in enumerate(zip(offsets, offsets[1:]))]
    return offsets, sequences


def build_archive(candidates: Sequence[Mapping[str, Any]]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Separate geometric vectors from the complete, recorded-causal subset.

    Missing features are never represented by imputed values in model arrays.
    Decimal-string timestamps preserve uint64 precision without object arrays.
    """
    profiles = [r for r in candidates if r["residuals_m"] is not None]
    for row in profiles:
        for key in ("estimate_source_time_ns_private", "reference_source_time_ns_private"):
            if type(row[key]) is not int or not 0 <= row[key] < 2**64:
                raise ValueError("profile timestamps must be uint64 integers")
        if not isinstance(row["recording_id"], str) or not 0 < len(row["recording_id"]) <= 16:
            raise ValueError("recording identifier cannot be empty or truncated")
    conditioned_indices = [i for i, r in enumerate(profiles) if r["conditions"] is not None]
    conditioned = [profiles[i] for i in conditioned_indices]
    offsets, sequences = sequence_layout(profiles)
    condition_offsets, condition_sequences = sequence_layout(conditioned)
    arrays = {
        "stations_m": np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64),
        "condition_names": np.asarray(BMW_CONDITION_FEATURE_NAMES, dtype="U48"),
        "residuals_m": np.asarray([r["residuals_m"] for r in profiles], dtype=np.float64).reshape(-1, 21),
        "recording_id": np.asarray([r["recording_id"] for r in profiles], dtype="U16"),
        "candidate_index": np.asarray([r["candidate_index"] for r in profiles], dtype=np.int64),
        "pair_index": np.asarray([r["pair_index"] for r in profiles], dtype=np.int64),
        "estimate_message_index": np.asarray([r["estimate_message_index"] for r in profiles], dtype=np.int64),
        "reference_message_index": np.asarray([r["reference_message_index"] for r in profiles], dtype=np.int64),
        "estimate_source_time_ns_decimal": np.asarray([str(r["estimate_source_time_ns_private"]) for r in profiles], dtype="U20"),
        "reference_source_time_ns_decimal": np.asarray([str(r["reference_source_time_ns_private"]) for r in profiles], dtype="U20"),
        "geometry_sequence_offsets": np.asarray(offsets, dtype=np.int64),
        "conditioned_profile_indices": np.asarray(conditioned_indices, dtype=np.int64),
        "conditions": np.asarray([r["conditions"] for r in conditioned], dtype=np.float64).reshape(-1, 6),
        "conditioned_sequence_offsets": np.asarray(condition_offsets, dtype=np.int64),
    }
    if not np.all(np.isfinite(arrays["residuals_m"])) or not np.all(np.isfinite(arrays["conditions"])):
        raise ValueError("exported model arrays must be finite")
    support = {"geometric_profile_count": len(profiles), "conditioned_profile_count": len(conditioned),
        "geometry_sequences": sequences, "conditioned_sequences": condition_sequences,
        "geometry_transition_count": sum(r["transition_count"] for r in sequences),
        "conditioned_transition_count": sum(r["transition_count"] for r in condition_sequences)}
    return arrays, support
