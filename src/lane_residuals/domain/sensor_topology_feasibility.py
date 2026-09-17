"""Pure structural geometry rules for the v0.18.1 feasibility audit.

This module never aligns the two topics and never constructs a residual.  It
accepts already decoded, message-local geometry, returns Boolean audit states,
and keeps all numeric geometry out of serialized outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

MINIMUM_CHAIN_SPAN_M = 100.0
MAXIMUM_CHAIN_SEGMENTS = 16
MAXIMUM_JUNCTION_GAP_M = 1.0
MAXIMUM_JUNCTION_HEADING_DEG = 30.0
MINIMUM_MEDIAN_WIDTH_M = 1.0
MAXIMUM_MEDIAN_WIDTH_M = 10.0
JUNCTION_DUPLICATE_TOLERANCE_M = 1e-6
MAXIMUM_SOURCE_DELTA_NS = 50_000_000


class SensorTopologyAuditError(ValueError):
    """Fail-closed structural failure carrying one contract code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class SensorSegment:
    """One decoded segment, before successor traversal."""

    midpoint: FloatArray | None = field(repr=False)
    successor_indices: tuple[object, ...]
    failure_code: str | None = None
    empty_map_influenced_termination: bool = False

    def __post_init__(self) -> None:
        if self.midpoint is not None:
            points = _finite_points(self.midpoint)
            points.setflags(write=False)
            object.__setattr__(self, "midpoint", points)
        if self.failure_code is not None and self.midpoint is not None:
            raise ValueError("a failed segment cannot contain a midpoint")
        if self.empty_map_influenced_termination and self.midpoint is not None:
            raise ValueError("an empty termination cannot contain a midpoint")


@dataclass(frozen=True)
class SensorChainAudit:
    """Message-level states exported only as counts by the workflow."""

    explicit_ego_candidate: bool
    initial_segment_structure: bool
    camera_only_successor_chain: bool
    camera_chain_100m_span: bool
    failure_codes: tuple[str, ...]


@dataclass(frozen=True)
class TimestampPair:
    first_position: int
    second_position: int
    delta_ns: int


@dataclass(frozen=True)
class MutualNearestTimestampAudit:
    pairs: tuple[TimestampPair, ...]
    rejected_by_gate: tuple[TimestampPair, ...]
    ambiguous_first_positions: tuple[int, ...]
    ambiguous_second_positions: tuple[int, ...]


def strict_integer(value: object, *, name: str) -> int:
    """Return an integer while rejecting Booleans and numeric coercion."""

    if isinstance(value, bool) or not isinstance(value, Integral):
        raise SensorTopologyAuditError(
            "sensor_ego_metadata_invalid",
            f"{name} must be a non-Boolean integer",
        )
    return int(value)


def _finite_points(points: ArrayLike) -> FloatArray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "geometry must have shape (n>=2, 2)",
        )
    if not np.all(np.isfinite(array)):
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "geometry must contain only finite points",
        )
    increments = np.linalg.norm(np.diff(array, axis=0), axis=1)
    if len(np.unique(array, axis=0)) < 2 or float(np.sum(increments)) <= 0.0:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_geometry_invalid",
            "geometry collapses to fewer than two distinct points",
        )
    return array


def concatenate_boundaries(boundaries: Sequence[ArrayLike]) -> FloatArray:
    """Concatenate stored boundary polylines using the frozen endpoint rule."""

    if not boundaries:
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_range_invalid",
            "a side must reference at least one camera boundary",
        )
    result = _finite_points(boundaries[0]).copy()
    for raw in boundaries[1:]:
        candidate = _finite_points(raw)
        gap_to_start = float(np.linalg.norm(result[-1] - candidate[0]))
        gap_to_end = float(np.linalg.norm(result[-1] - candidate[-1]))
        if gap_to_start == gap_to_end:
            raise SensorTopologyAuditError(
                "sensor_camera_chain_ambiguous",
                "boundary orientation has an exact endpoint tie",
            )
        if gap_to_end < gap_to_start:
            candidate = candidate[::-1]
            gap = gap_to_end
        else:
            gap = gap_to_start
        if gap > MAXIMUM_JUNCTION_GAP_M:
            raise SensorTopologyAuditError(
                "sensor_camera_boundary_geometry_invalid",
                "inter-boundary gap exceeds 1 m",
            )
        if gap <= JUNCTION_DUPLICATE_TOLERANCE_M:
            candidate = candidate[1:]
        if len(candidate):
            result = np.vstack((result, candidate))
    return _finite_points(result)


def midpoint_from_boundaries(left: ArrayLike, right: ArrayLike) -> FloatArray:
    """Build the consumer diagnostic midpoint using normalized side stations."""

    left_points = _finite_points(left)
    right_points = _finite_points(right)
    same_cost = float(
        np.linalg.norm(left_points[0] - right_points[0])
        + np.linalg.norm(left_points[-1] - right_points[-1])
    )
    reversed_cost = float(
        np.linalg.norm(left_points[0] - right_points[-1])
        + np.linalg.norm(left_points[-1] - right_points[0])
    )
    if same_cost == reversed_cost:
        raise SensorTopologyAuditError(
            "sensor_camera_chain_ambiguous",
            "complete right-side orientation has an exact tie",
        )
    if reversed_cost < same_cost:
        right_points = right_points[::-1]

    def normalized(points: FloatArray) -> FloatArray:
        station = np.concatenate(
            ([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
        )
        if station[-1] <= 0.0:
            raise SensorTopologyAuditError(
                "sensor_camera_boundary_geometry_invalid",
                "boundary side has zero total length",
            )
        return station / station[-1]

    left_station = normalized(left_points)
    right_station = normalized(right_points)
    sample = np.linspace(0.0, 1.0, max(len(left_points), len(right_points)))
    left_sampled = np.column_stack(
        [np.interp(sample, left_station, left_points[:, axis]) for axis in (0, 1)]
    )
    right_sampled = np.column_stack(
        [np.interp(sample, right_station, right_points[:, axis]) for axis in (0, 1)]
    )
    widths = np.linalg.norm(left_sampled - right_sampled, axis=1)
    median_width = float(np.median(widths))
    if (
        not math.isfinite(median_width)
        or median_width < MINIMUM_MEDIAN_WIDTH_M
        or median_width > MAXIMUM_MEDIAN_WIDTH_M
    ):
        raise SensorTopologyAuditError(
            "sensor_camera_boundary_width_implausible",
            "median paired-boundary width is outside [1, 10] m",
        )
    return _finite_points(0.5 * (left_sampled + right_sampled))


def _heading(points: FloatArray, *, at_end: bool) -> float:
    vectors = np.diff(points, axis=0)
    indices = range(len(vectors) - 1, -1, -1) if at_end else range(len(vectors))
    for index in indices:
        vector = vectors[index]
        if float(np.linalg.norm(vector)) > JUNCTION_DUPLICATE_TOLERANCE_M:
            return math.atan2(float(vector[1]), float(vector[0]))
    raise SensorTopologyAuditError(
        "sensor_camera_chain_junction_invalid",
        "junction tangent is unavailable",
    )


def _heading_delta(first: FloatArray, second: FloatArray) -> float:
    delta = _heading(second, at_end=False) - _heading(first, at_end=True)
    return abs((delta + math.pi) % (2.0 * math.pi) - math.pi)


def audit_sensor_chain(
    ego_indices: Sequence[object],
    segments: Sequence[SensorSegment],
) -> SensorChainAudit:
    """Audit one LTSB message without selecting or aligning another topic."""

    if not ego_indices:
        return SensorChainAudit(False, False, False, False, ("sensor_ego_metadata_missing",))
    if len(ego_indices) != 1:
        return SensorChainAudit(False, False, False, False, ("sensor_ego_segment_not_unique",))
    try:
        ego = strict_integer(ego_indices[0], name="ego_lane_segment_indices[0]")
    except SensorTopologyAuditError as error:
        return SensorChainAudit(False, False, False, False, (error.code,))
    if ego < 0 or ego >= len(segments):
        return SensorChainAudit(False, False, False, False, ("sensor_ego_metadata_invalid",))

    initial = segments[ego]
    if initial.midpoint is None:
        code = initial.failure_code or "sensor_camera_boundary_geometry_invalid"
        return SensorChainAudit(True, False, False, False, (code,))

    points = initial.midpoint.copy()
    current_index = ego
    visited = {ego}
    visited_count = 1
    while True:
        span = float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
        if span + 1e-9 >= MINIMUM_CHAIN_SPAN_M:
            return SensorChainAudit(True, True, True, True, ())

        current = segments[current_index]
        successors = current.successor_indices
        if not successors:
            return SensorChainAudit(True, True, True, False, ("sensor_camera_chain_100m_span_unavailable",))
        if len(successors) != 1:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_junction_invalid",))
        if visited_count >= MAXIMUM_CHAIN_SEGMENTS:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_limit_exceeded",))
        try:
            successor_index = strict_integer(successors[0], name="successor index")
        except SensorTopologyAuditError:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_junction_invalid",))
        if successor_index < 0 or successor_index >= len(segments):
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_junction_invalid",))
        if successor_index in visited:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_cycle",))
        successor = segments[successor_index]
        if successor.empty_map_influenced_termination:
            return SensorChainAudit(True, True, True, False, ("sensor_camera_chain_100m_span_unavailable",))
        if successor.midpoint is None:
            return SensorChainAudit(
                True,
                True,
                False,
                False,
                (successor.failure_code or "sensor_camera_boundary_geometry_invalid",),
            )

        candidate = successor.midpoint
        gap_to_start = float(np.linalg.norm(points[-1] - candidate[0]))
        gap_to_end = float(np.linalg.norm(points[-1] - candidate[-1]))
        if gap_to_start == gap_to_end:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_ambiguous",))
        if gap_to_end < gap_to_start:
            candidate = candidate[::-1]
            gap = gap_to_end
        else:
            gap = gap_to_start
        if gap > MAXIMUM_JUNCTION_GAP_M + 1e-12:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_junction_invalid",))
        try:
            heading_delta = _heading_delta(points, candidate)
        except SensorTopologyAuditError as error:
            return SensorChainAudit(True, True, False, False, (error.code,))
        if heading_delta > math.radians(MAXIMUM_JUNCTION_HEADING_DEG) + 1e-12:
            return SensorChainAudit(True, True, False, False, ("sensor_camera_chain_junction_invalid",))
        if gap <= JUNCTION_DUPLICATE_TOLERANCE_M:
            candidate = candidate[1:]
        if len(candidate):
            points = np.vstack((points, candidate))
        visited.add(successor_index)
        visited_count += 1
        current_index = successor_index


def mutual_nearest_timestamp_pairs(
    first_times_ns: Sequence[int],
    second_times_ns: Sequence[int],
    *,
    maximum_delta_ns: int = MAXIMUM_SOURCE_DELTA_NS,
) -> MutualNearestTimestampAudit:
    """Pair complete strict streams by unique mutual-nearest source time."""

    if (
        isinstance(maximum_delta_ns, bool)
        or not isinstance(maximum_delta_ns, Integral)
        or maximum_delta_ns < 0
    ):
        raise ValueError("maximum_delta_ns must be a nonnegative integer")

    def nearest(source: Sequence[int], target: Sequence[int]) -> tuple[dict[int, int], set[int]]:
        result: dict[int, int] = {}
        ambiguous: set[int] = set()
        for source_position, source_time in enumerate(source):
            distances = [abs(source_time - target_time) for target_time in target]
            if not distances:
                continue
            minimum = min(distances)
            candidates = [i for i, distance in enumerate(distances) if distance == minimum]
            if len(candidates) == 1:
                result[source_position] = candidates[0]
            else:
                ambiguous.add(source_position)
        return result, ambiguous

    first_to_second, ambiguous_first = nearest(first_times_ns, second_times_ns)
    second_to_first, ambiguous_second = nearest(second_times_ns, first_times_ns)
    accepted: list[TimestampPair] = []
    rejected: list[TimestampPair] = []
    for first_position, second_position in first_to_second.items():
        if second_to_first.get(second_position) != first_position:
            continue
        pair = TimestampPair(
            first_position,
            second_position,
            first_times_ns[first_position] - second_times_ns[second_position],
        )
        (accepted if abs(pair.delta_ns) <= maximum_delta_ns else rejected).append(pair)
    key = lambda pair: (first_times_ns[pair.first_position], pair.first_position, pair.second_position)
    return MutualNearestTimestampAudit(
        tuple(sorted(accepted, key=key)),
        tuple(sorted(rejected, key=key)),
        tuple(sorted(ambiguous_first)),
        tuple(sorted(ambiguous_second)),
    )
