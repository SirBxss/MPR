"""Geometry primitives for an estimate-versus-map pairing audit.

The functions in this module deliberately stop before creating thesis labels.
They put two already-decoded paths on ego-relative arc-length stations, expose
their origin and heading offsets, and compute an explicitly diagnostic
disagreement along the map-path normal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry_validation import GeometryValidationError, SplineCurve
from .mcap_io import RoadFrame, RoadSegment

FloatArray = NDArray[np.float64]
DEFAULT_PAIRING_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))


def _wrap_angle(value: float | FloatArray) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    return (array + np.pi) % (2.0 * np.pi) - np.pi


def _finite_points(points: ArrayLike) -> FloatArray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2:
        raise GeometryValidationError(
            "pairing_points_invalid",
            "pairing geometry must have shape (n>=2, 2)",
        )
    if not np.all(np.isfinite(array)):
        raise GeometryValidationError(
            "pairing_points_non_finite",
            "pairing geometry must contain only finite coordinates",
        )
    increments = np.linalg.norm(np.diff(array, axis=0), axis=1)
    keep = np.concatenate(([True], increments > 1e-7))
    array = array[keep]
    if len(array) < 2:
        raise GeometryValidationError(
            "pairing_geometry_degenerate",
            "pairing geometry collapses to fewer than two unique points",
        )
    return array


@dataclass(frozen=True)
class _OriginProjection:
    station_m: float
    point_m: FloatArray = field(repr=False)
    distance_m: float
    heading_rad: float


def _project_origin(
    points: FloatArray,
    stations_m: FloatArray,
    *,
    ambiguity_distance_tolerance_m: float,
    ambiguity_station_separation_m: float,
) -> _OriginProjection:
    starts = points[:-1]
    vectors = points[1:] - starts
    lengths = np.linalg.norm(vectors, axis=1)
    squared_lengths = np.square(lengths)
    fractions = np.einsum("ij,ij->i", -starts, vectors) / squared_lengths
    fractions = np.clip(fractions, 0.0, 1.0)
    projections = starts + fractions[:, None] * vectors
    squared_distances = np.einsum("ij,ij->i", projections, projections)
    best = int(np.argmin(squared_distances))
    minimum_distance = float(math.sqrt(float(squared_distances[best])))
    projected_stations = stations_m[:-1] + fractions * lengths

    close = np.flatnonzero(
        np.sqrt(squared_distances)
        <= minimum_distance + ambiguity_distance_tolerance_m
    )
    if len(close) > 1:
        spread = float(np.ptp(projected_stations[close]))
        if spread > ambiguity_station_separation_m:
            raise GeometryValidationError(
                "ego_origin_projection_ambiguous",
                "the ego origin is equally close to separated parts of the path",
            )

    return _OriginProjection(
        station_m=float(projected_stations[best]),
        point_m=np.asarray(projections[best], dtype=np.float64),
        distance_m=minimum_distance,
        heading_rad=float(math.atan2(vectors[best, 1], vectors[best, 0])),
    )


@dataclass(frozen=True)
class EgoRelativePath:
    """One ordered path with station zero at the ego-origin footpoint."""

    source: str
    stations_m: FloatArray = field(repr=False)
    x_m: FloatArray = field(repr=False)
    y_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)
    origin_footpoint_m: FloatArray = field(repr=False)
    origin_distance_m: float
    origin_heading_rad: float
    reversed_to_positive_x: bool

    def __post_init__(self) -> None:
        stations = np.asarray(self.stations_m, dtype=np.float64)
        x = np.asarray(self.x_m, dtype=np.float64)
        y = np.asarray(self.y_m, dtype=np.float64)
        heading = np.asarray(self.heading_rad, dtype=np.float64)
        origin = np.asarray(self.origin_footpoint_m, dtype=np.float64)
        if len(stations) < 2 or len({len(stations), len(x), len(y), len(heading)}) != 1:
            raise GeometryValidationError(
                "pairing_array_count_mismatch",
                "ego-relative path arrays must have equal length of at least two",
            )
        if not all(
            array.ndim == 1 and np.all(np.isfinite(array))
            for array in (stations, x, y, heading)
        ):
            raise GeometryValidationError(
                "pairing_arrays_invalid",
                "ego-relative path arrays must be finite vectors",
            )
        if origin.shape != (2,) or not np.all(np.isfinite(origin)):
            raise GeometryValidationError(
                "pairing_origin_invalid",
                "origin footpoint must be a finite two-vector",
            )
        if not np.all(np.diff(stations) > 0.0):
            raise GeometryValidationError(
                "pairing_stations_not_increasing",
                "ego-relative path stations must be strictly increasing",
            )
        if not stations[0] - 1e-9 <= 0.0 <= stations[-1] + 1e-9:
            raise GeometryValidationError(
                "pairing_origin_outside_domain",
                "ego-relative path domain must contain station zero",
            )
        if not math.isfinite(self.origin_distance_m) or self.origin_distance_m < 0.0:
            raise GeometryValidationError(
                "pairing_origin_distance_invalid",
                "origin distance must be finite and nonnegative",
            )
        for name, array in (
            ("stations_m", stations),
            ("x_m", x),
            ("y_m", y),
            ("heading_rad", heading),
            ("origin_footpoint_m", origin),
        ):
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def points(self) -> FloatArray:
        return np.column_stack((self.x_m, self.y_m))

    @property
    def forward_coverage_m(self) -> float:
        return float(self.stations_m[-1])

    @property
    def backward_coverage_m(self) -> float:
        return float(-self.stations_m[0])


def ego_relative_path_from_points(
    points: ArrayLike,
    *,
    source: str,
    orient_toward_positive_x: bool = True,
    ambiguity_distance_tolerance_m: float = 1e-3,
    ambiguity_station_separation_m: float = 1.0,
) -> EgoRelativePath:
    """Project ``(0, 0)`` onto a path and make that footpoint station zero.

    Vertex order is reversed only when the tangent at the ego footpoint points
    toward negative x.  The reversal is always exposed in the returned audit
    object; it is never a hidden geometry correction.
    """

    if ambiguity_distance_tolerance_m < 0.0 or not math.isfinite(
        ambiguity_distance_tolerance_m
    ):
        raise ValueError("ambiguity distance tolerance must be finite and nonnegative")
    if ambiguity_station_separation_m <= 0.0 or not math.isfinite(
        ambiguity_station_separation_m
    ):
        raise ValueError("ambiguity station separation must be finite and positive")

    geometry = _finite_points(points)
    reversed_to_positive_x = False
    for _ in range(2):
        increments = np.linalg.norm(np.diff(geometry, axis=0), axis=1)
        stations = np.concatenate(([0.0], np.cumsum(increments)))
        projection = _project_origin(
            geometry,
            stations,
            ambiguity_distance_tolerance_m=ambiguity_distance_tolerance_m,
            ambiguity_station_separation_m=ambiguity_station_separation_m,
        )
        if orient_toward_positive_x and math.cos(projection.heading_rad) < 0.0:
            geometry = geometry[::-1].copy()
            reversed_to_positive_x = not reversed_to_positive_x
            continue
        break

    relative_stations = stations - projection.station_m
    dx = np.gradient(geometry[:, 0], stations, edge_order=1)
    dy = np.gradient(geometry[:, 1], stations, edge_order=1)
    headings = np.unwrap(np.arctan2(dy, dx))
    origin_heading = float(
        np.interp(projection.station_m, stations, headings)
    )
    return EgoRelativePath(
        source=source,
        stations_m=relative_stations,
        x_m=geometry[:, 0],
        y_m=geometry[:, 1],
        heading_rad=headings,
        origin_footpoint_m=projection.point_m,
        origin_distance_m=projection.distance_m,
        origin_heading_rad=origin_heading,
        reversed_to_positive_x=reversed_to_positive_x,
    )


def ego_relative_path_from_spline(curve: SplineCurve) -> EgoRelativePath:
    """Create an ego-relative audit path from a reconstructed estimate spline."""

    return ego_relative_path_from_points(curve.points, source="estimated_keep_lane")


def select_unique_ego_drive_path(frame: RoadFrame) -> RoadSegment:
    """Select one metadata-confirmed RLMB ego-lane drive path, fail closed."""

    candidates = [
        segment
        for segment in frame.segments
        if segment.is_ego is True and segment.geometry_source == "drive_path"
    ]
    if len(candidates) != 1:
        raise GeometryValidationError(
            "map_ego_drive_path_not_unique",
            "RLMB must expose exactly one metadata-confirmed ego drive path",
        )
    return candidates[0]


@dataclass(frozen=True)
class OrderedEgoLane:
    """Audited RLMB ego-lane path assembled from explicit successor indices."""

    path: EgoRelativePath = field(repr=False)
    segment_indices: tuple[int, ...]
    segment_ids: tuple[int, ...]
    junction_gaps_m: tuple[float, ...]
    junction_heading_deltas_rad: tuple[float, ...]
    reciprocal_predecessor_links: tuple[bool, ...]
    required_forward_m: float
    required_forward_coverage_reached: bool
    termination_reason: str

    @property
    def segment_count(self) -> int:
        return len(self.segment_indices)

    @property
    def max_junction_gap_m(self) -> float | None:
        return None if not self.junction_gaps_m else max(self.junction_gaps_m)

    @property
    def max_junction_heading_delta_rad(self) -> float | None:
        return (
            None
            if not self.junction_heading_deltas_rad
            else max(self.junction_heading_deltas_rad)
        )


def _junction_heading_delta(first: RoadSegment, second: RoadSegment) -> float:
    first_vectors = np.diff(first.points, axis=0)
    second_vectors = np.diff(second.points, axis=0)
    first_valid = np.flatnonzero(np.linalg.norm(first_vectors, axis=1) > 1e-7)
    second_valid = np.flatnonzero(np.linalg.norm(second_vectors, axis=1) > 1e-7)
    if not len(first_valid) or not len(second_valid):
        raise GeometryValidationError(
            "map_successor_junction_tangent_unavailable",
            "RLMB successor junction has no finite nondegenerate endpoint tangent",
        )
    first_vector = first_vectors[first_valid[-1]]
    second_vector = second_vectors[second_valid[0]]
    first_heading = math.atan2(first_vector[1], first_vector[0])
    second_heading = math.atan2(second_vector[1], second_vector[0])
    return abs(float(_wrap_angle(second_heading - first_heading)))


def ordered_ego_lane_from_road_frame(
    frame: RoadFrame,
    *,
    required_forward_m: float = 100.0,
    max_segments: int = 16,
    max_junction_gap_m: float = 1.0,
    max_junction_heading_delta_rad: float = math.radians(30.0),
) -> OrderedEgoLane:
    """Follow one explicit RLMB successor chain without guessing at branches.

    The metadata-confirmed ego segment is the only allowed starting point.  A
    successor is appended only when the current segment exposes exactly one
    successor index and the corresponding reconstructed drive path passes the
    declared position and heading continuity limits.  Ambiguous or malformed
    topology returns the valid prefix with an explicit termination reason.
    """

    if not math.isfinite(required_forward_m) or required_forward_m < 0.0:
        raise ValueError("required_forward_m must be finite and nonnegative")
    if isinstance(max_segments, bool) or max_segments < 1:
        raise ValueError("max_segments must be a positive integer")
    if not math.isfinite(max_junction_gap_m) or max_junction_gap_m < 0.0:
        raise ValueError("max_junction_gap_m must be finite and nonnegative")
    if (
        not math.isfinite(max_junction_heading_delta_rad)
        or max_junction_heading_delta_rad < 0.0
        or max_junction_heading_delta_rad > math.pi
    ):
        raise ValueError(
            "max_junction_heading_delta_rad must be finite and within [0, pi]"
        )

    start = select_unique_ego_drive_path(frame)
    by_index = {
        segment.source_index: segment
        for segment in frame.segments
        if segment.source_index is not None
        and segment.geometry_source == "drive_path"
    }
    points = start.points.copy()
    chain = [start]
    gaps: list[float] = []
    heading_deltas: list[float] = []
    reciprocal_links: list[bool] = []
    visited = (
        set()
        if start.source_index is None
        else {int(start.source_index)}
    )

    def result(reason: str) -> OrderedEgoLane:
        path = ego_relative_path_from_points(
            points,
            source="road_lane_map_based_ordered_ego_lane",
        )
        return OrderedEgoLane(
            path=path,
            segment_indices=tuple(
                -1 if segment.source_index is None else segment.source_index
                for segment in chain
            ),
            segment_ids=tuple(segment.segment_id for segment in chain),
            junction_gaps_m=tuple(gaps),
            junction_heading_deltas_rad=tuple(heading_deltas),
            reciprocal_predecessor_links=tuple(reciprocal_links),
            required_forward_m=float(required_forward_m),
            required_forward_coverage_reached=(
                path.forward_coverage_m + 1e-9 >= required_forward_m
            ),
            termination_reason=reason,
        )

    while True:
        current_path = ego_relative_path_from_points(
            points,
            source="road_lane_map_based_ordered_ego_lane",
        )
        if current_path.forward_coverage_m + 1e-9 >= required_forward_m:
            return result("required_forward_coverage_reached")
        if len(chain) >= max_segments:
            return result("maximum_segment_count_reached")

        current = chain[-1]
        if current.source_index is None:
            return result("topology_source_index_unavailable")
        if not current.successor_indices:
            return result("terminal_segment_no_successor")
        if len(current.successor_indices) != 1:
            return result("successor_branch_ambiguous")

        successor_index = current.successor_indices[0]
        if successor_index in visited:
            return result("successor_cycle_detected")
        successor = by_index.get(successor_index)
        if successor is None:
            original_count = (
                len(frame.segment_extractions)
                if frame.segment_extractions
                else max(by_index, default=-1) + 1
            )
            return result(
                "successor_index_out_of_range"
                if successor_index >= original_count
                else "successor_geometry_unavailable"
            )

        gap = float(np.linalg.norm(current.points[-1] - successor.points[0]))
        if gap > max_junction_gap_m + 1e-12:
            return result("successor_junction_gap_exceeds_limit")
        try:
            heading_delta = _junction_heading_delta(current, successor)
        except GeometryValidationError:
            return result("successor_junction_tangent_unavailable")
        if heading_delta > max_junction_heading_delta_rad + 1e-12:
            return result("successor_junction_heading_exceeds_limit")

        successor_points = successor.points
        if gap <= 1e-7:
            successor_points = successor_points[1:]
        points = np.vstack((points, successor_points))
        gaps.append(gap)
        heading_deltas.append(heading_delta)
        reciprocal_links.append(current.source_index in successor.predecessor_indices)
        chain.append(successor)
        visited.add(successor_index)


def ego_relative_path_from_road_frame(
    frame: RoadFrame,
    *,
    required_forward_m: float = 100.0,
    max_segments: int = 16,
    max_junction_gap_m: float = 1.0,
    max_junction_heading_delta_rad: float = math.radians(30.0),
) -> EgoRelativePath:
    """Create an ego-relative path from an audited RLMB successor chain."""

    return ordered_ego_lane_from_road_frame(
        frame,
        required_forward_m=required_forward_m,
        max_segments=max_segments,
        max_junction_gap_m=max_junction_gap_m,
        max_junction_heading_delta_rad=max_junction_heading_delta_rad,
    ).path


def sample_ego_relative_path(
    path: EgoRelativePath,
    stations_m: Sequence[float] = DEFAULT_PAIRING_STATIONS_M,
) -> EgoRelativePath:
    """Sample fixed ego-relative stations without extrapolation."""

    stations = np.asarray(stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or len(stations) < 2
        or not np.all(np.isfinite(stations))
        or not np.all(np.diff(stations) > 0.0)
    ):
        raise ValueError("stations must be a finite, strictly increasing vector")
    if (
        stations[0] < path.stations_m[0] - 1e-9
        or stations[-1] > path.stations_m[-1] + 1e-9
    ):
        raise GeometryValidationError(
            "pairing_station_coverage_incomplete",
            f"{path.source} does not cover every requested ego-relative station",
        )
    return EgoRelativePath(
        source=path.source,
        stations_m=stations,
        x_m=np.interp(stations, path.stations_m, path.x_m),
        y_m=np.interp(stations, path.stations_m, path.y_m),
        heading_rad=np.interp(stations, path.stations_m, np.unwrap(path.heading_rad)),
        origin_footpoint_m=path.origin_footpoint_m,
        origin_distance_m=path.origin_distance_m,
        origin_heading_rad=path.origin_heading_rad,
        reversed_to_positive_x=path.reversed_to_positive_x,
    )


@dataclass(frozen=True)
class DiagnosticPathDisagreement:
    """Uncompensated diagnostic discrepancy; never a final thesis label."""

    stations_m: FloatArray = field(repr=False)
    lateral_m: FloatArray = field(repr=False)
    along_track_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)

    @property
    def lateral_rms_m(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.lateral_m))))

    @property
    def lateral_max_abs_m(self) -> float:
        return float(np.max(np.abs(self.lateral_m)))


@dataclass(frozen=True)
class TimestampPair:
    """One mutual-nearest association between two complete timestamp streams."""

    first_position: int
    second_position: int
    delta_ns: int


@dataclass(frozen=True)
class MutualNearestTimestampAudit:
    """Fail-closed result of pairing two complete timestamp streams.

    Positions refer to the original input sequences. Messages without source
    timestamps, equal-distance ties, non-mutual nearest candidates, and pairs
    rejected by an explicit gate remain visible instead of being discarded.
    """

    pairs: tuple[TimestampPair, ...]
    rejected_by_gate: tuple[TimestampPair, ...]
    unmatched_first_positions: tuple[int, ...]
    unmatched_second_positions: tuple[int, ...]
    missing_time_first_positions: tuple[int, ...]
    missing_time_second_positions: tuple[int, ...]
    ambiguous_first_positions: tuple[int, ...]
    ambiguous_second_positions: tuple[int, ...]


def compare_ego_relative_paths(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
    *,
    stations_m: Sequence[float] = DEFAULT_PAIRING_STATIONS_M,
) -> DiagnosticPathDisagreement:
    """Compare equal ego-relative stations along the reference-path normal."""

    estimate_sampled = sample_ego_relative_path(estimate, stations_m)
    reference_sampled = sample_ego_relative_path(reference, stations_m)
    difference = estimate_sampled.points - reference_sampled.points
    tangent = np.column_stack(
        (
            np.cos(reference_sampled.heading_rad),
            np.sin(reference_sampled.heading_rad),
        )
    )
    normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    return DiagnosticPathDisagreement(
        stations_m=reference_sampled.stations_m,
        lateral_m=np.einsum("ij,ij->i", normal, difference),
        along_track_m=np.einsum("ij,ij->i", tangent, difference),
        heading_rad=_wrap_angle(
            estimate_sampled.heading_rad - reference_sampled.heading_rad
        ),
    )


def origin_alignment_metrics(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
) -> dict[str, float]:
    """Return raw common-frame indicators before any alignment is applied."""

    separation = estimate.origin_footpoint_m - reference.origin_footpoint_m
    return {
        "estimate_origin_distance_m": estimate.origin_distance_m,
        "reference_origin_distance_m": reference.origin_distance_m,
        "footpoint_separation_m": float(np.linalg.norm(separation)),
        "footpoint_dx_m": float(separation[0]),
        "footpoint_dy_m": float(separation[1]),
        "origin_heading_delta_rad": float(
            _wrap_angle(estimate.origin_heading_rad - reference.origin_heading_rad)
        ),
    }


def _unique_nearest_positions(
    source: Sequence[tuple[int, int]],
    target: Sequence[tuple[int, int]],
) -> tuple[dict[int, int], set[int]]:
    """Map each source position to one uniquely nearest target position."""

    nearest: dict[int, int] = {}
    ambiguous: set[int] = set()
    for source_position, source_time_ns in source:
        distances = [
            (abs(source_time_ns - target_time_ns), target_position)
            for target_position, target_time_ns in target
        ]
        if not distances:
            continue
        minimum_distance = min(distance for distance, _ in distances)
        candidates = [
            target_position
            for distance, target_position in distances
            if distance == minimum_distance
        ]
        if len(candidates) != 1:
            ambiguous.add(source_position)
            continue
        nearest[source_position] = candidates[0]
    return nearest, ambiguous


def mutual_nearest_timestamp_pairs(
    first_times_ns: Sequence[int | None],
    second_times_ns: Sequence[int | None],
    *,
    maximum_delta_ns: int | None = None,
) -> MutualNearestTimestampAudit:
    """Pair complete streams by unique mutual-nearest source timestamps.

    Geometry validity is intentionally absent from this function. An optional
    gate is applied only after mutual-nearest candidates are identified, so a
    rejected distant candidate cannot consume either message.
    """

    if maximum_delta_ns is not None:
        if isinstance(maximum_delta_ns, bool) or maximum_delta_ns < 0:
            raise ValueError("maximum_delta_ns must be nonnegative or None")
        maximum_delta_ns = int(maximum_delta_ns)

    first_valid = [
        (position, int(value))
        for position, value in enumerate(first_times_ns)
        if value is not None
    ]
    second_valid = [
        (position, int(value))
        for position, value in enumerate(second_times_ns)
        if value is not None
    ]
    missing_first = tuple(
        position for position, value in enumerate(first_times_ns) if value is None
    )
    missing_second = tuple(
        position for position, value in enumerate(second_times_ns) if value is None
    )

    first_to_second, ambiguous_first = _unique_nearest_positions(
        first_valid,
        second_valid,
    )
    second_to_first, ambiguous_second = _unique_nearest_positions(
        second_valid,
        first_valid,
    )
    first_time_by_position = dict(first_valid)
    second_time_by_position = dict(second_valid)

    accepted: list[TimestampPair] = []
    rejected: list[TimestampPair] = []
    for first_position, second_position in first_to_second.items():
        if second_to_first.get(second_position) != first_position:
            continue
        pair = TimestampPair(
            first_position=first_position,
            second_position=second_position,
            delta_ns=(
                first_time_by_position[first_position]
                - second_time_by_position[second_position]
            ),
        )
        if maximum_delta_ns is not None and abs(pair.delta_ns) > maximum_delta_ns:
            rejected.append(pair)
        else:
            accepted.append(pair)

    def ordering(pair: TimestampPair) -> tuple[int, int, int]:
        return (
            first_time_by_position[pair.first_position],
            pair.first_position,
            pair.second_position,
        )

    accepted.sort(key=ordering)
    rejected.sort(key=ordering)
    paired_first = {pair.first_position for pair in accepted}
    paired_second = {pair.second_position for pair in accepted}
    return MutualNearestTimestampAudit(
        pairs=tuple(accepted),
        rejected_by_gate=tuple(rejected),
        unmatched_first_positions=tuple(
            position
            for position in range(len(first_times_ns))
            if position not in paired_first
        ),
        unmatched_second_positions=tuple(
            position
            for position in range(len(second_times_ns))
            if position not in paired_second
        ),
        missing_time_first_positions=missing_first,
        missing_time_second_positions=missing_second,
        ambiguous_first_positions=tuple(sorted(ambiguous_first)),
        ambiguous_second_positions=tuple(sorted(ambiguous_second)),
    )


def nearest_monotone_pairs_unbounded(
    first_times_ns: Sequence[int],
    second_times_ns: Sequence[int],
) -> tuple[tuple[int, int, int], ...]:
    """Pair nearest timestamps monotonically without pretending a valid tolerance.

    The returned signed delta is ``first_time - second_time``.  Scientific
    acceptance must be decided separately from this diagnostic association.
    """

    first = sorted((int(value), index) for index, value in enumerate(first_times_ns))
    second = sorted((int(value), index) for index, value in enumerate(second_times_ns))
    if not first or not second:
        return ()
    result: list[tuple[int, int, int]] = []
    last_second_position = -1
    for time_a, index_a in first:
        candidates = [
            (abs(time_a - time_b), position, index_b, time_b)
            for position, (time_b, index_b) in enumerate(second)
            if position > last_second_position
        ]
        if not candidates:
            break
        minimum = min(item[0] for item in candidates)
        nearest = [item for item in candidates if item[0] == minimum]
        if len(nearest) != 1:
            continue
        _, position, index_b, time_b = nearest[0]
        result.append((index_a, index_b, time_a - time_b))
        last_second_position = position
    return tuple(result)


def evenly_spaced_indices(size: int, maximum_count: int) -> tuple[int, ...]:
    """Select deterministic, approximately even indices including both ends."""

    if size < 0:
        raise ValueError("size must be nonnegative")
    if maximum_count < 1:
        raise ValueError("maximum_count must be positive")
    if size <= maximum_count:
        return tuple(range(size))
    raw = np.linspace(0, size - 1, maximum_count)
    return tuple(int(value) for value in np.rint(raw))
