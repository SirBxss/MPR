"""Spatial alignment of EDP paths to the best available RLMB reference.

The v0.4.5 diagnostic gives each path an ego-relative station coordinate by
projecting ``(0, 0)`` onto that path independently.  This module implements the
additional correspondence proposed for provisional residual extraction:

1. take the EstimatedDrivePaths station-zero footpoint;
2. project that point onto the paired RLMB path;
3. call the projected RLMB station zero for this comparison; and
4. sample both paths at equal forward arc-length offsets.

This is spatial reference alignment.  It is not explicit timestamp/SE(2)
motion compensation and must not be described as independent physical ground
truth recovery.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry_validation import GeometryValidationError
from .pairing import DiagnosticPathDisagreement, EgoRelativePath

FloatArray = NDArray[np.float64]


def _wrap_angle(value: ArrayLike | float) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    return (array + np.pi) % (2.0 * np.pi) - np.pi


def _requested_stations(stations_m: Sequence[float]) -> FloatArray:
    stations = np.asarray(stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or len(stations) < 2
        or not np.all(np.isfinite(stations))
        or stations[0] < 0.0
        or not np.all(np.diff(stations) > 0.0)
    ):
        raise ValueError(
            "stations must be finite, nonnegative, and strictly increasing"
        )
    return stations


@dataclass(frozen=True)
class PathPointProjection:
    """One fail-closed point-to-path projection in the path station domain."""

    station_m: float
    point_m: FloatArray = field(repr=False)
    distance_m: float
    heading_rad: float
    segment_index: int
    segment_fraction: float

    def __post_init__(self) -> None:
        point = np.asarray(self.point_m, dtype=np.float64)
        if point.shape != (2,) or not np.all(np.isfinite(point)):
            raise ValueError("projection point must be a finite two-vector")
        scalar_values = (
            self.station_m,
            self.distance_m,
            self.heading_rad,
            self.segment_fraction,
        )
        if not all(math.isfinite(value) for value in scalar_values):
            raise ValueError("projection values must be finite")
        if self.distance_m < 0.0:
            raise ValueError("projection distance must be nonnegative")
        if self.segment_index < 0:
            raise ValueError("projection segment index must be nonnegative")
        if not 0.0 <= self.segment_fraction <= 1.0:
            raise ValueError("projection segment fraction must be within [0, 1]")
        point.setflags(write=False)
        object.__setattr__(self, "point_m", point)


def project_point_to_path(
    point_m: ArrayLike,
    path: EgoRelativePath,
    *,
    ambiguity_distance_tolerance_m: float = 1e-3,
    ambiguity_station_separation_m: float = 1.0,
) -> PathPointProjection:
    """Project one point onto an ordered path without guessing at ambiguity."""

    point = np.asarray(point_m, dtype=np.float64)
    if point.shape != (2,) or not np.all(np.isfinite(point)):
        raise ValueError("point_m must be a finite two-vector")
    if (
        ambiguity_distance_tolerance_m < 0.0
        or not math.isfinite(ambiguity_distance_tolerance_m)
    ):
        raise ValueError(
            "ambiguity distance tolerance must be finite and nonnegative"
        )
    if (
        ambiguity_station_separation_m <= 0.0
        or not math.isfinite(ambiguity_station_separation_m)
    ):
        raise ValueError(
            "ambiguity station separation must be finite and positive"
        )

    points = path.points
    starts = points[:-1]
    vectors = points[1:] - starts
    lengths = np.linalg.norm(vectors, axis=1)
    squared_lengths = np.square(lengths)
    fractions = np.einsum("ij,ij->i", point - starts, vectors) / squared_lengths
    fractions = np.clip(fractions, 0.0, 1.0)
    projections = starts + fractions[:, None] * vectors
    differences = projections - point
    squared_distances = np.einsum("ij,ij->i", differences, differences)
    best = int(np.argmin(squared_distances))
    minimum_distance = float(math.sqrt(float(squared_distances[best])))
    projected_stations = path.stations_m[:-1] + fractions * lengths

    close = np.flatnonzero(
        np.sqrt(squared_distances)
        <= minimum_distance + ambiguity_distance_tolerance_m
    )
    if len(close) > 1:
        spread = float(np.ptp(projected_stations[close]))
        if spread > ambiguity_station_separation_m:
            raise GeometryValidationError(
                "reference_alignment_projection_ambiguous",
                "the EDP station-zero point is equally close to separated parts "
                "of the reference path",
            )

    return PathPointProjection(
        station_m=float(projected_stations[best]),
        point_m=projections[best],
        distance_m=minimum_distance,
        heading_rad=float(math.atan2(vectors[best, 1], vectors[best, 0])),
        segment_index=best,
        segment_fraction=float(fractions[best]),
    )


@dataclass(frozen=True)
class SpatialAlignmentResult:
    """Aligned samples and signed residuals for one temporal path pair."""

    stations_m: FloatArray = field(repr=False)
    estimate_points_m: FloatArray = field(repr=False)
    reference_points_m: FloatArray = field(repr=False)
    disagreement: DiagnosticPathDisagreement = field(repr=False)
    reference_projection: PathPointProjection = field(repr=False)
    estimate_anchor_point_m: FloatArray = field(repr=False)
    anchor_heading_delta_rad: float
    aligned_reference_backward_coverage_m: float
    aligned_reference_forward_coverage_m: float

    def __post_init__(self) -> None:
        stations = np.asarray(self.stations_m, dtype=np.float64)
        estimate_points = np.asarray(self.estimate_points_m, dtype=np.float64)
        reference_points = np.asarray(self.reference_points_m, dtype=np.float64)
        estimate_anchor = np.asarray(self.estimate_anchor_point_m, dtype=np.float64)
        expected_shape = (len(stations), 2)
        if stations.ndim != 1 or len(stations) < 2:
            raise ValueError("aligned stations must contain at least two values")
        if estimate_points.shape != expected_shape or reference_points.shape != expected_shape:
            raise ValueError("aligned point arrays must have shape (stations, 2)")
        if not all(
            np.all(np.isfinite(array))
            for array in (stations, estimate_points, reference_points)
        ):
            raise ValueError("aligned samples must be finite")
        if estimate_anchor.shape != (2,) or not np.all(np.isfinite(estimate_anchor)):
            raise ValueError("estimate anchor must be a finite two-vector")
        if not math.isfinite(self.anchor_heading_delta_rad):
            raise ValueError("anchor heading delta must be finite")
        if (
            not math.isfinite(self.aligned_reference_backward_coverage_m)
            or not math.isfinite(self.aligned_reference_forward_coverage_m)
            or self.aligned_reference_backward_coverage_m < 0.0
            or self.aligned_reference_forward_coverage_m < 0.0
        ):
            raise ValueError("aligned reference coverage must be finite and nonnegative")
        for name, array in (
            ("stations_m", stations),
            ("estimate_points_m", estimate_points),
            ("reference_points_m", reference_points),
            ("estimate_anchor_point_m", estimate_anchor),
        ):
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def reference_anchor_station_m(self) -> float:
        """RLMB native ego-relative station selected as aligned station zero."""

        return self.reference_projection.station_m

    @property
    def anchor_distance_m(self) -> float:
        """Distance from EDP station zero to its projected RLMB footpoint."""

        return self.reference_projection.distance_m


def compare_spatially_aligned_paths(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
    *,
    stations_m: Sequence[float],
    ambiguity_distance_tolerance_m: float = 1e-3,
    ambiguity_station_separation_m: float = 1.0,
) -> SpatialAlignmentResult:
    """Apply projection/resampling and calculate provisional lateral residuals.

    The estimate keeps its existing station coordinate.  The reference is
    sampled at ``projection.station_m + stations_m``.  Neither path is ever
    extrapolated.
    """

    stations = _requested_stations(stations_m)
    projection = project_point_to_path(
        estimate.origin_footpoint_m,
        reference,
        ambiguity_distance_tolerance_m=ambiguity_distance_tolerance_m,
        ambiguity_station_separation_m=ambiguity_station_separation_m,
    )
    reference_stations = projection.station_m + stations
    tolerance = 1e-9
    if (
        stations[0] < estimate.stations_m[0] - tolerance
        or stations[-1] > estimate.stations_m[-1] + tolerance
    ):
        raise GeometryValidationError(
            "reference_alignment_estimate_coverage_incomplete",
            "the EDP path does not cover every requested aligned station",
        )
    if (
        reference_stations[0] < reference.stations_m[0] - tolerance
        or reference_stations[-1] > reference.stations_m[-1] + tolerance
    ):
        raise GeometryValidationError(
            "reference_alignment_reference_coverage_incomplete",
            "the RLMB path does not cover every requested station after alignment",
        )

    estimate_x = np.interp(stations, estimate.stations_m, estimate.x_m)
    estimate_y = np.interp(stations, estimate.stations_m, estimate.y_m)
    estimate_heading = np.interp(
        stations,
        estimate.stations_m,
        np.unwrap(estimate.heading_rad),
    )
    reference_x = np.interp(reference_stations, reference.stations_m, reference.x_m)
    reference_y = np.interp(reference_stations, reference.stations_m, reference.y_m)
    reference_heading = np.interp(
        reference_stations,
        reference.stations_m,
        np.unwrap(reference.heading_rad),
    )
    estimate_points = np.column_stack((estimate_x, estimate_y))
    reference_points = np.column_stack((reference_x, reference_y))
    difference = estimate_points - reference_points
    tangent = np.column_stack((np.cos(reference_heading), np.sin(reference_heading)))
    normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    disagreement = DiagnosticPathDisagreement(
        stations_m=stations,
        lateral_m=np.einsum("ij,ij->i", normal, difference),
        along_track_m=np.einsum("ij,ij->i", tangent, difference),
        heading_rad=_wrap_angle(estimate_heading - reference_heading),
    )
    return SpatialAlignmentResult(
        stations_m=stations,
        estimate_points_m=estimate_points,
        reference_points_m=reference_points,
        disagreement=disagreement,
        reference_projection=projection,
        estimate_anchor_point_m=estimate.origin_footpoint_m,
        anchor_heading_delta_rad=float(
            _wrap_angle(estimate.origin_heading_rad - projection.heading_rad)
        ),
        aligned_reference_backward_coverage_m=float(
            projection.station_m - reference.stations_m[0]
        ),
        aligned_reference_forward_coverage_m=float(
            reference.stations_m[-1] - projection.station_m
        ),
    )
