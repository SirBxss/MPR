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


def ego_relative_path_from_road_frame(frame: RoadFrame) -> EgoRelativePath:
    """Create an ego-relative audit path from one strict RLMB road frame."""

    segment = select_unique_ego_drive_path(frame)
    return ego_relative_path_from_points(
        segment.points,
        source="road_lane_map_based_ego_lane",
    )


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
