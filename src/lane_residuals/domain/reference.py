"""Reference-candidate discovery and reconstruction for real MCAP data.

This module keeps the LEEM target fixed: signed lateral *lane-estimation*
error.  It does not promote a realised vehicle trajectory to lane ground truth.
Instead, it provides the geometry and audit primitives needed to test whether
direct map-lane geometry or a pose-plus-centreline-offset reconstruction can be
used as a defensible pseudo-reference.

All functions are deterministic and fail closed.  No statistical model is fit
and no final residual dataset is written by this module.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .geometry_validation import GeometryValidationError, SplineCurve

FloatArray = NDArray[np.float64]

DEFAULT_REFERENCE_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))

THESIS_TARGET_QUESTION = (
    "How wrong is the lane estimate likely to be under this situation?"
)
THESIS_TARGET_VARIABLE = (
    "signed lateral lane-estimation error along the validated reference-path normal"
)


@dataclass(frozen=True)
class TimedMessage:
    """One decoded message with opaque corpus provenance."""

    recording_id: str
    session_id: str
    topic: str
    schema_name: str
    message_encoding: str
    message_index: int
    log_time_ns: int
    publish_time_ns: int
    source_time_ns: int | None
    decoded: Any = field(repr=False)
    schema_fingerprint: str | None = None
    payload_fingerprint: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PoseSample:
    """Planar vehicle pose in a stable world/map frame."""

    recording_id: str
    session_id: str
    message_index: int
    time_ns: int
    x_m: float
    y_m: float
    yaw_rad: float
    valid: bool = True

    def __post_init__(self) -> None:
        values = np.asarray((self.x_m, self.y_m, self.yaw_rad), dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise GeometryValidationError(
                "pose_non_finite", "pose x, y, and yaw must be finite"
            )
        if self.time_ns < 0:
            raise GeometryValidationError(
                "pose_time_invalid", "pose time must be nonnegative"
            )


@dataclass(frozen=True)
class LateralLaneSample:
    """Current vehicle-to-centreline offset and supporting lane signals."""

    recording_id: str
    session_id: str
    message_index: int
    time_ns: int
    distance_to_centerline_m: float
    distance_to_left_boundary_m: float | None = None
    distance_to_right_boundary_m: float | None = None
    lane_change_detected: bool = False
    road_ambiguity_detected: bool = False
    valid: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(self.distance_to_centerline_m):
            raise GeometryValidationError(
                "centerline_distance_non_finite",
                "distance_to_centerline must be finite",
            )
        for value in (
            self.distance_to_left_boundary_m,
            self.distance_to_right_boundary_m,
        ):
            if value is not None and not math.isfinite(value):
                raise GeometryValidationError(
                    "boundary_distance_non_finite",
                    "lane-boundary distances must be finite when present",
                )
        if self.time_ns < 0:
            raise GeometryValidationError(
                "centerline_time_invalid", "centreline time must be nonnegative"
            )

    @property
    def boundary_derived_offset_m(self) -> float | None:
        """Return the boundary-derived offset under the declared sign equation.

        This is deliberately an auxiliary consistency signal.  The exact
        ``back_axis`` reference-point semantics remain unconfirmed.
        """

        if (
            self.distance_to_left_boundary_m is None
            or self.distance_to_right_boundary_m is None
        ):
            return None
        return 0.5 * (
            self.distance_to_right_boundary_m
            - self.distance_to_left_boundary_m
        )


@dataclass(frozen=True)
class CenterlineWorldSample:
    """One reconstructed lane-centre sample in a stable world/map frame."""

    recording_id: str
    session_id: str
    time_ns: int
    x_m: float
    y_m: float
    heading_rad: float
    lane_change_detected: bool
    road_ambiguity_detected: bool
    provenance: str


@dataclass(frozen=True)
class CandidateGeometry:
    """One candidate lane-reference path in the estimate's local frame."""

    source: str
    s_m: FloatArray = field(repr=False)
    x_m: FloatArray = field(repr=False)
    y_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)
    curvature_per_m: FloatArray = field(repr=False)
    provenance: str

    def __post_init__(self) -> None:
        arrays = [
            np.asarray(value, dtype=np.float64)
            for value in (
                self.s_m,
                self.x_m,
                self.y_m,
                self.heading_rad,
                self.curvature_per_m,
            )
        ]
        if len(arrays[0]) < 2 or len({len(array) for array in arrays}) != 1:
            raise GeometryValidationError(
                "candidate_array_count_mismatch",
                "candidate arrays must have the same length of at least two",
            )
        if not all(array.ndim == 1 and np.all(np.isfinite(array)) for array in arrays):
            raise GeometryValidationError(
                "candidate_arrays_invalid", "candidate arrays must be finite vectors"
            )
        if not np.all(np.diff(arrays[0]) > 0.0):
            raise GeometryValidationError(
                "candidate_stations_not_increasing",
                "candidate stations must be strictly increasing",
            )
        for name, array in zip(
            ("s_m", "x_m", "y_m", "heading_rad", "curvature_per_m"),
            arrays,
        ):
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def points(self) -> FloatArray:
        return np.column_stack((self.x_m, self.y_m))


@dataclass(frozen=True)
class CandidateDiscrepancy:
    """Diagnostic discrepancy between an estimate and one candidate reference."""

    stations_m: FloatArray = field(repr=False)
    lateral_m: FloatArray = field(repr=False)
    along_track_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)
    curvature_per_m: FloatArray = field(repr=False)

    @property
    def lateral_rms_m(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.lateral_m))))

    @property
    def lateral_max_abs_m(self) -> float:
        return float(np.max(np.abs(self.lateral_m)))


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    )


def _protobuf_fields(value: Any) -> tuple[tuple[str, Any], ...] | None:
    descriptor = getattr(value, "DESCRIPTOR", None)
    fields = getattr(descriptor, "fields", None)
    if fields is None:
        return None
    result: list[tuple[str, Any]] = []
    for item in fields:
        name = str(getattr(item, "name", ""))
        if name:
            result.append((name, getattr(value, name)))
    return tuple(result)


def _object_fields(value: Any) -> tuple[tuple[str, Any], ...]:
    protobuf = _protobuf_fields(value)
    if protobuf is not None:
        return protobuf
    if isinstance(value, Mapping):
        return tuple((str(key), item) for key, item in value.items())
    names: list[str] = []
    slots = getattr(type(value), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    names.extend(str(name) for name in slots)
    if hasattr(value, "__dict__"):
        names.extend(str(name) for name in vars(value))
    result: list[tuple[str, Any]] = []
    for name in dict.fromkeys(names):
        if name.startswith("_") or not hasattr(value, name):
            continue
        item = getattr(value, name)
        if callable(item):
            continue
        result.append((name, item))
    return tuple(result)


def flatten_scalar_fields(
    value: Any,
    *,
    maximum_depth: int = 8,
    maximum_sequence_items: int = 64,
) -> dict[str, tuple[Any, ...]]:
    """Flatten decoded Protobuf/ROS/mapping objects into normalized paths.

    Repeated values use ``[]`` in the path.  Values are retained only for
    in-memory auditing; callers should summarize rather than serialize raw
    coordinates from confidential recordings.
    """

    if maximum_depth < 1 or maximum_sequence_items < 1:
        raise ValueError("flattening limits must be positive")
    flattened: dict[str, list[Any]] = defaultdict(list)
    seen: set[int] = set()

    def visit(item: Any, path: str, depth: int) -> None:
        if item is None or depth > maximum_depth:
            return
        if isinstance(item, (bool, int, float, str)):
            if path:
                flattened[path].append(item)
            return
        if isinstance(item, np.generic):
            if path:
                flattened[path].append(item.item())
            return
        if _is_sequence(item) or (
            hasattr(item, "__iter__")
            and not isinstance(item, Mapping)
            and not _object_fields(item)
        ):
            try:
                values = tuple(item)
            except TypeError:
                values = ()
            for child in values[:maximum_sequence_items]:
                visit(child, f"{path}[]" if path else "[]", depth + 1)
            return
        identity = id(item)
        if identity in seen:
            return
        seen.add(identity)
        for name, child in _object_fields(item):
            child_path = f"{path}.{name}" if path else name
            visit(child, child_path, depth + 1)
        seen.discard(identity)

    visit(value, "", 0)
    return {path: tuple(values) for path, values in sorted(flattened.items())}


def summarize_field_catalog(
    messages: Iterable[TimedMessage],
    *,
    maximum_messages_per_topic: int = 50,
) -> list[dict[str, Any]]:
    """Build a privacy-aware decoded-field catalogue for configured topics."""

    if maximum_messages_per_topic < 1:
        raise ValueError("maximum_messages_per_topic must be positive")
    counts_by_topic: dict[str, int] = defaultdict(int)
    values_by_key: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    messages_with_key: dict[tuple[str, str, str], set[tuple[str, int]]] = defaultdict(set)
    for message in messages:
        if counts_by_topic[message.topic] >= maximum_messages_per_topic:
            continue
        counts_by_topic[message.topic] += 1
        flattened = flatten_scalar_fields(message.decoded)
        for path, values in flattened.items():
            key = (message.topic, message.schema_name, path)
            values_by_key[key].extend(values)
            messages_with_key[key].add((message.recording_id, message.message_index))

    rows: list[dict[str, Any]] = []
    for (topic, schema_name, path), values in sorted(values_by_key.items()):
        numeric = [
            float(value)
            for value in values
            if isinstance(value, (int, float, np.number))
            and not isinstance(value, (bool, np.bool_))
            and math.isfinite(float(value))
        ]
        types = sorted({type(value).__name__ for value in values})
        rows.append(
            {
                "topic": topic,
                "schema_name": schema_name,
                "field_path": path,
                "value_types": types,
                "sampled_message_count": len(messages_with_key[(topic, schema_name, path)]),
                "sampled_value_count": len(values),
                "finite_numeric_count": len(numeric),
                "minimum": min(numeric) if numeric else None,
                "maximum": max(numeric) if numeric else None,
            }
        )
    return rows


def resolve_path(value: Any, path: str) -> Any:
    """Resolve one exact dot path without guessing semantics."""

    if not isinstance(path, str) or not path or "[]" in path:
        raise KeyError(path)
    current = value
    for name in path.split("."):
        if isinstance(current, Mapping):
            if name not in current:
                raise KeyError(path)
            current = current[name]
        elif hasattr(current, name):
            current = getattr(current, name)
        else:
            raise KeyError(path)
    return current


def resolve_first_path(value: Any, paths: Sequence[str]) -> tuple[str, Any]:
    """Resolve the first explicitly configured path and return its provenance."""

    for path in paths:
        try:
            return path, resolve_path(value, path)
        except KeyError:
            continue
    raise KeyError(",".join(paths))


def finite_scalar(value: Any, *, logical_name: str) -> float:
    """Convert a configured scalar or explicit value wrapper to float."""

    if not isinstance(value, (bool, int, float, np.number)) and hasattr(value, "value"):
        value = getattr(value, "value")
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.number)
    ):
        raise GeometryValidationError(
            "configured_field_not_numeric", f"{logical_name} is not numeric"
        )
    result = float(value)
    if not math.isfinite(result):
        raise GeometryValidationError(
            "configured_field_non_finite", f"{logical_name} is not finite"
        )
    return result


def boolean_scalar(value: Any, *, logical_name: str) -> bool:
    """Convert an explicitly configured boolean/integer flag."""

    if hasattr(value, "value") and not isinstance(value, (bool, int, np.integer)):
        value = getattr(value, "value")
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and int(value) in (0, 1):
        return bool(value)
    raise GeometryValidationError(
        "configured_flag_not_boolean", f"{logical_name} is not a boolean flag"
    )


def nearest_monotone_pairs(
    first_times_ns: Sequence[int],
    second_times_ns: Sequence[int],
    *,
    maximum_delta_ms: float,
) -> tuple[tuple[int, int, int], ...]:
    """Return deterministic, ambiguity-rejecting nearest monotone pairs."""

    if not math.isfinite(maximum_delta_ms) or maximum_delta_ms < 0.0:
        raise ValueError("maximum_delta_ms must be finite and nonnegative")
    tolerance_ns = int(round(maximum_delta_ms * 1_000_000.0))
    first = [(int(value), index) for index, value in enumerate(first_times_ns)]
    second = [(int(value), index) for index, value in enumerate(second_times_ns)]
    first.sort()
    second.sort()
    result: list[tuple[int, int, int]] = []
    used_second: set[int] = set()
    last_second_position = -1
    for time_a, index_a in first:
        candidates = [
            (abs(time_a - time_b), position, index_b, time_b)
            for position, (time_b, index_b) in enumerate(second)
            if position > last_second_position
            and index_b not in used_second
            and abs(time_a - time_b) <= tolerance_ns
        ]
        if not candidates:
            continue
        minimum = min(item[0] for item in candidates)
        nearest = [item for item in candidates if item[0] == minimum]
        if len(nearest) != 1:
            continue
        _, position, index_b, time_b = nearest[0]
        result.append((index_a, index_b, time_a - time_b))
        used_second.add(index_b)
        last_second_position = position
    return tuple(result)


def reconstruct_centerline_samples(
    poses: Sequence[PoseSample],
    lane_samples: Sequence[LateralLaneSample],
    *,
    maximum_delta_ms: float,
    positive_offset_is_lane_left: bool,
) -> tuple[CenterlineWorldSample, ...]:
    """Reconstruct current lane-centre points from pose and signed offset.

    With a positive-left convention, ``p_center = p_vehicle - d*n_left``.
    The pose yaw is used as a documented fallback for lane heading; candidate
    promotion must retain this limitation unless an independent lane heading is
    supplied later.
    """

    if not positive_offset_is_lane_left:
        raise GeometryValidationError(
            "centerline_sign_unconfirmed",
            "the current implementation requires a confirmed positive-left sign",
        )
    if not poses or not lane_samples:
        return ()
    pose_sessions = {item.session_id for item in poses}
    lane_sessions = {item.session_id for item in lane_samples}
    if len(pose_sessions) != 1 or pose_sessions != lane_sessions:
        raise GeometryValidationError(
            "reconstruction_session_mismatch",
            "pose and centreline samples must belong to one identical session",
        )
    pairs = nearest_monotone_pairs(
        [item.time_ns for item in poses],
        [item.time_ns for item in lane_samples],
        maximum_delta_ms=maximum_delta_ms,
    )
    result: list[CenterlineWorldSample] = []
    for pose_index, lane_index, _ in pairs:
        pose = poses[pose_index]
        lane = lane_samples[lane_index]
        if not pose.valid or not lane.valid:
            continue
        normal_left = np.asarray(
            (-math.sin(pose.yaw_rad), math.cos(pose.yaw_rad)), dtype=np.float64
        )
        vehicle = np.asarray((pose.x_m, pose.y_m), dtype=np.float64)
        center = vehicle - lane.distance_to_centerline_m * normal_left
        result.append(
            CenterlineWorldSample(
                recording_id=pose.recording_id,
                session_id=pose.session_id,
                time_ns=pose.time_ns,
                x_m=float(center[0]),
                y_m=float(center[1]),
                heading_rad=pose.yaw_rad,
                lane_change_detected=lane.lane_change_detected,
                road_ambiguity_detected=lane.road_ambiguity_detected,
                provenance="pose_plus_distance_to_centerline__vehicle_yaw_fallback",
            )
        )
    result.sort(key=lambda item: item.time_ns)
    return tuple(result)


def _derive_heading_and_curvature(points: FloatArray, s_m: FloatArray) -> tuple[FloatArray, FloatArray]:
    dx = np.gradient(points[:, 0], s_m, edge_order=1)
    dy = np.gradient(points[:, 1], s_m, edge_order=1)
    heading = np.unwrap(np.arctan2(dy, dx))
    curvature = np.gradient(heading, s_m, edge_order=1)
    return heading, curvature


def candidate_from_polyline(
    *,
    source: str,
    points: Sequence[Sequence[float]] | FloatArray,
    provenance: str,
    stations_m: Sequence[float] | None = None,
) -> CandidateGeometry:
    """Create a candidate geometry from an ordered local-frame polyline."""

    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2:
        raise GeometryValidationError(
            "candidate_points_invalid", "candidate points must have shape (n>=2, 2)"
        )
    if not np.all(np.isfinite(array)):
        raise GeometryValidationError(
            "candidate_points_non_finite", "candidate points must be finite"
        )
    if stations_m is None:
        increments = np.linalg.norm(np.diff(array, axis=0), axis=1)
        keep = np.concatenate(([True], increments > 1e-6))
        array = array[keep]
        if len(array) < 2:
            raise GeometryValidationError(
                "candidate_has_no_motion", "candidate polyline has no usable motion"
            )
        s = np.concatenate(
            ([0.0], np.cumsum(np.linalg.norm(np.diff(array, axis=0), axis=1)))
        )
    else:
        s = np.asarray(stations_m, dtype=np.float64)
        if s.ndim != 1 or len(s) != len(array):
            raise GeometryValidationError(
                "candidate_station_count_mismatch",
                "provided stations must match candidate point count",
            )
        keep = np.concatenate(([True], np.diff(s) > 1e-6))
        s, array = s[keep], array[keep]
    heading, curvature = _derive_heading_and_curvature(array, s)
    return CandidateGeometry(
        source=source,
        s_m=s,
        x_m=array[:, 0],
        y_m=array[:, 1],
        heading_rad=heading,
        curvature_per_m=curvature,
        provenance=provenance,
    )


def build_hindsight_candidate(
    centerline_samples: Sequence[CenterlineWorldSample],
    *,
    anchor_pose: PoseSample,
    maximum_inter_sample_gap_s: float = 0.25,
    minimum_future_distance_m: float = 100.0,
    maximum_stationary_duration_s: float = 2.0,
    stationary_step_threshold_m: float = 0.05,
) -> CandidateGeometry:
    """Build a future centreline candidate in the anchor pose's ego frame."""

    if maximum_inter_sample_gap_s <= 0.0 or not math.isfinite(maximum_inter_sample_gap_s):
        raise ValueError("maximum_inter_sample_gap_s must be finite and positive")
    if minimum_future_distance_m <= 0.0 or not math.isfinite(minimum_future_distance_m):
        raise ValueError("minimum_future_distance_m must be finite and positive")
    if maximum_stationary_duration_s <= 0.0 or not math.isfinite(maximum_stationary_duration_s):
        raise ValueError("maximum_stationary_duration_s must be finite and positive")
    if stationary_step_threshold_m < 0.0 or not math.isfinite(stationary_step_threshold_m):
        raise ValueError("stationary_step_threshold_m must be finite and nonnegative")
    future = [
        item
        for item in centerline_samples
        if item.session_id == anchor_pose.session_id and item.time_ns >= anchor_pose.time_ns
    ]
    if len(future) < 2:
        raise GeometryValidationError(
            "hindsight_future_samples_missing", "fewer than two future samples"
        )
    if any(item.lane_change_detected for item in future):
        first_change = next(
            index for index, item in enumerate(future) if item.lane_change_detected
        )
        future = future[:first_change]
    if len(future) < 2:
        raise GeometryValidationError(
            "hindsight_lane_change_window", "lane change invalidates the future window"
        )
    if any(item.road_ambiguity_detected for item in future):
        first_ambiguity = next(
            index for index, item in enumerate(future) if item.road_ambiguity_detected
        )
        future = future[:first_ambiguity]
    if len(future) < 2:
        raise GeometryValidationError(
            "hindsight_road_ambiguity_window",
            "intersection or road-branch ambiguity invalidates the future window",
        )
    gaps = np.diff(np.asarray([item.time_ns for item in future], dtype=np.int64)) / 1e9
    invalid = np.flatnonzero(gaps > maximum_inter_sample_gap_s)
    if len(invalid):
        future = future[: int(invalid[0]) + 1]
    world = np.asarray([(item.x_m, item.y_m) for item in future], dtype=np.float64)
    steps = np.linalg.norm(np.diff(world, axis=0), axis=1)
    stationary = steps <= stationary_step_threshold_m
    if np.any(stationary):
        start = None
        for index, current in enumerate(stationary):
            if current and start is None:
                start = index
            at_end = index == len(stationary) - 1
            if start is not None and (not current or at_end):
                end = index + 1 if current and at_end else index
                duration = (future[end].time_ns - future[start].time_ns) / 1e9
                if duration > maximum_stationary_duration_s:
                    raise GeometryValidationError(
                        "hindsight_prolonged_stop",
                        "a prolonged stationary interval invalidates the future window",
                    )
                start = None
    relative = world - np.asarray((anchor_pose.x_m, anchor_pose.y_m), dtype=np.float64)
    c, s = math.cos(anchor_pose.yaw_rad), math.sin(anchor_pose.yaw_rad)
    world_to_ego = np.asarray(((c, s), (-s, c)), dtype=np.float64)
    local = relative @ world_to_ego.T
    candidate = candidate_from_polyline(
        source="pose_plus_centerline_offset",
        points=local,
        provenance=future[0].provenance,
    )
    if candidate.s_m[-1] < minimum_future_distance_m:
        raise GeometryValidationError(
            "hindsight_coverage_incomplete",
            "future reconstructed centreline does not cover the required distance",
        )
    return candidate


def sample_candidate(
    candidate: CandidateGeometry,
    stations_m: Sequence[float] = DEFAULT_REFERENCE_STATIONS_M,
) -> CandidateGeometry:
    """Resample a candidate at fixed stations without extrapolation."""

    stations = np.asarray(stations_m, dtype=np.float64)
    if stations.ndim != 1 or len(stations) < 2 or not np.all(np.isfinite(stations)):
        raise ValueError("stations must be a finite vector with at least two entries")
    if not np.all(np.diff(stations) > 0.0):
        raise ValueError("stations must be strictly increasing")
    if stations[0] < candidate.s_m[0] - 1e-9 or stations[-1] > candidate.s_m[-1] + 1e-9:
        raise GeometryValidationError(
            "candidate_station_coverage_incomplete",
            "candidate does not cover all requested stations",
        )
    return CandidateGeometry(
        source=candidate.source,
        s_m=stations,
        x_m=np.interp(stations, candidate.s_m, candidate.x_m),
        y_m=np.interp(stations, candidate.s_m, candidate.y_m),
        heading_rad=np.interp(stations, candidate.s_m, np.unwrap(candidate.heading_rad)),
        curvature_per_m=np.interp(stations, candidate.s_m, candidate.curvature_per_m),
        provenance=candidate.provenance,
    )


def compare_estimate_to_candidate(
    estimate: SplineCurve,
    candidate: CandidateGeometry,
    *,
    stations_m: Sequence[float] = DEFAULT_REFERENCE_STATIONS_M,
) -> CandidateDiscrepancy:
    """Compute diagnostic estimate-minus-candidate discrepancies.

    These values are not final lane-estimation errors until the candidate has
    passed the reference-selection gate.
    """

    sampled = sample_candidate(candidate, stations_m)
    stations = sampled.s_m
    if stations[0] < estimate.s[0] - 1e-9 or stations[-1] > estimate.s[-1] + 1e-9:
        raise GeometryValidationError(
            "estimate_station_coverage_incomplete",
            "estimate does not cover all requested candidate stations",
        )
    estimate_x = np.interp(stations, estimate.s, estimate.x)
    estimate_y = np.interp(stations, estimate.s, estimate.y)
    estimate_heading = np.interp(stations, estimate.s, np.unwrap(estimate.heading))
    estimate_curvature = np.interp(stations, estimate.s, estimate.curvature)
    difference = np.column_stack(
        (estimate_x - sampled.x_m, estimate_y - sampled.y_m)
    )
    tangent = np.column_stack(
        (np.cos(sampled.heading_rad), np.sin(sampled.heading_rad))
    )
    normal = np.column_stack(
        (-np.sin(sampled.heading_rad), np.cos(sampled.heading_rad))
    )
    return CandidateDiscrepancy(
        stations_m=stations,
        lateral_m=np.einsum("ij,ij->i", normal, difference),
        along_track_m=np.einsum("ij,ij->i", tangent, difference),
        heading_rad=(estimate_heading - sampled.heading_rad + np.pi)
        % (2.0 * np.pi)
        - np.pi,
        curvature_per_m=estimate_curvature - sampled.curvature_per_m,
    )


def compare_reference_candidates(
    first: CandidateGeometry,
    second: CandidateGeometry,
    *,
    stations_m: Sequence[float] = DEFAULT_REFERENCE_STATIONS_M,
) -> dict[str, float]:
    """Compare two candidate references at fixed stations."""

    a = sample_candidate(first, stations_m)
    b = sample_candidate(second, stations_m)
    difference = np.column_stack((a.x_m - b.x_m, a.y_m - b.y_m))
    normal_b = np.column_stack((-np.sin(b.heading_rad), np.cos(b.heading_rad)))
    lateral = np.einsum("ij,ij->i", normal_b, difference)
    heading = (a.heading_rad - b.heading_rad + np.pi) % (2.0 * np.pi) - np.pi
    return {
        "lateral_rms_m": float(np.sqrt(np.mean(np.square(lateral)))),
        "lateral_median_abs_m": float(np.median(np.abs(lateral))),
        "lateral_max_abs_m": float(np.max(np.abs(lateral))),
        "heading_rms_rad": float(np.sqrt(np.mean(np.square(heading)))),
    }


def audit_pose_continuity(
    poses: Sequence[PoseSample],
    *,
    maximum_position_jump_m: float,
    maximum_yaw_jump_rad: float,
) -> dict[str, Any]:
    """Summarize continuity without silently declaring a pose source valid."""

    if maximum_position_jump_m <= 0.0 or maximum_yaw_jump_rad <= 0.0:
        raise ValueError("pose jump thresholds must be positive")
    ordered = sorted(poses, key=lambda item: item.time_ns)
    if len(ordered) < 2:
        return {
            "sample_count": len(ordered),
            "duration_s": 0.0,
            "median_rate_hz": None,
            "maximum_position_step_m": None,
            "maximum_yaw_step_rad": None,
            "position_jump_count": 0,
            "yaw_jump_count": 0,
        }
    times = np.asarray([item.time_ns for item in ordered], dtype=np.int64)
    points = np.asarray([(item.x_m, item.y_m) for item in ordered], dtype=np.float64)
    yaw = np.unwrap(np.asarray([item.yaw_rad for item in ordered], dtype=np.float64))
    delta_s = np.diff(times) / 1e9
    position_step = np.linalg.norm(np.diff(points, axis=0), axis=1)
    yaw_step = np.abs(np.diff(yaw))
    positive_delta = delta_s[delta_s > 0.0]
    return {
        "sample_count": len(ordered),
        "duration_s": float((times[-1] - times[0]) / 1e9),
        "median_rate_hz": (
            None if len(positive_delta) == 0 else float(1.0 / np.median(positive_delta))
        ),
        "maximum_position_step_m": float(np.max(position_step)),
        "maximum_yaw_step_rad": float(np.max(yaw_step)),
        "position_jump_count": int(np.sum(position_step > maximum_position_jump_m)),
        "yaw_jump_count": int(np.sum(yaw_step > maximum_yaw_jump_rad)),
    }


def reference_decision(
    *,
    complete_corpus: bool,
    estimator_semantics_valid: bool,
    direct_map_candidate_frames: int,
    reconstructed_candidate_frames: int,
    sessions_with_both_candidates: int,
    candidate_lateral_median_abs_m: float | None,
    maximum_allowed_candidate_median_abs_m: float | None,
    pose_frame_confirmed: bool,
    centerline_sign_confirmed: bool,
    pose_reference_point_confirmed: bool,
    candidate_frame_confirmed: bool,
) -> dict[str, Any]:
    """Apply the fail-closed pseudo-reference promotion gate."""

    blockers: list[str] = []
    if not complete_corpus:
        blockers.append("corpus_incomplete")
    if not estimator_semantics_valid:
        blockers.append("estimate_debug_semantics_not_validated")
    if direct_map_candidate_frames < 1:
        blockers.append("direct_map_candidate_unavailable")
    if reconstructed_candidate_frames < 1:
        blockers.append("pose_offset_candidate_unavailable")
    if sessions_with_both_candidates < 2:
        blockers.append("fewer_than_two_sessions_cross_validate_candidates")
    if not pose_frame_confirmed:
        blockers.append("stable_pose_frame_unconfirmed")
    if not centerline_sign_confirmed:
        blockers.append("centerline_sign_unconfirmed")
    if not pose_reference_point_confirmed:
        blockers.append("pose_reference_point_unconfirmed")
    if not candidate_frame_confirmed:
        blockers.append("map_lane_and_estimate_frame_unconfirmed")
    if maximum_allowed_candidate_median_abs_m is None:
        blockers.append("candidate_agreement_threshold_not_predeclared")
    elif candidate_lateral_median_abs_m is None:
        blockers.append("candidate_agreement_not_measured")
    elif candidate_lateral_median_abs_m > maximum_allowed_candidate_median_abs_m:
        blockers.append("candidate_agreement_threshold_failed")

    selected = None if blockers else "direct_map_lane_cross_validated_by_pose_offset"
    return {
        "status": "reference_unresolved" if blockers else "pseudo_reference_supported",
        "selected_reference": selected,
        "blockers": blockers,
        "driven_trajectory_is_ground_truth": False,
        "ego_lane_path_is_ground_truth": False,
        "final_residual_export_allowed": False,
        "model_fitting_allowed": False,
        "thesis_target_question": THESIS_TARGET_QUESTION,
        "thesis_target_variable": THESIS_TARGET_VARIABLE,
    }
