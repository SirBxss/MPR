"""Candidate-level transition diagnostics for EstimatedDrivePaths.

This module deliberately does not define a lane-estimation residual.  It keeps
all EDP candidates, evaluates both unresolved ``curvature_change`` hypotheses,
and compares consecutive selected KEEP_LANE curves only to expose abrupt
changes in the estimate signal itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from .geometry_validation import GeometryValidationError, SplineCurve, SplineParameters

FloatArray = NDArray[np.float64]
DEFAULT_EDP_TRANSITION_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))
EDP_SPLINE_HYPOTHESES = ("curvature_rate", "curvature_delta")


def _wrap_angle(value: float) -> float:
    return float((value + math.pi) % (2.0 * math.pi) - math.pi)


@dataclass(frozen=True)
class CandidateGeometry:
    """One EDP candidate sampled under one explicit spline hypothesis."""

    message_index: int
    path_index: int
    hypothesis: str
    stations_m: FloatArray = field(repr=False)
    x_m: FloatArray = field(repr=False)
    y_m: FloatArray = field(repr=False)
    heading_rad: FloatArray = field(repr=False)
    curvature_per_m: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        arrays = tuple(
            np.asarray(value, dtype=np.float64)
            for value in (
                self.stations_m,
                self.x_m,
                self.y_m,
                self.heading_rad,
                self.curvature_per_m,
            )
        )
        if any(array.ndim != 1 for array in arrays):
            raise GeometryValidationError(
                "edp_candidate_geometry_not_vector",
                "candidate geometry arrays must be one-dimensional",
            )
        if not arrays[0].size or len({len(array) for array in arrays}) != 1:
            raise GeometryValidationError(
                "edp_candidate_geometry_count_mismatch",
                "candidate geometry arrays must have one equal nonzero length",
            )
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise GeometryValidationError(
                "edp_candidate_geometry_non_finite",
                "candidate geometry arrays must be finite",
            )
        if not np.all(np.diff(arrays[0]) > 0.0):
            raise GeometryValidationError(
                "edp_candidate_stations_not_increasing",
                "candidate geometry stations must be strictly increasing",
            )
        for name, array in zip(
            (
                "stations_m",
                "x_m",
                "y_m",
                "heading_rad",
                "curvature_per_m",
            ),
            arrays,
        ):
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    @property
    def points(self) -> FloatArray:
        return np.column_stack((self.x_m, self.y_m))


@dataclass(frozen=True)
class CandidateSnapshot:
    """All extracted evidence for one candidate in one EDP message."""

    message_index: int
    source_time_ns: int | None
    path_index: int
    topology_source: str
    role_symbol: str
    error_symbol: str
    selected_unique_keep_lane: bool
    selected_for_pairing_audit: bool
    candidate_status: str
    failure_codes: tuple[str, ...]
    model_flag_value: bool | None
    lane_topology_ids: tuple[int, ...]
    confidences: tuple[float, ...]
    parameters: SplineParameters | None = field(default=None, repr=False)
    geometries: tuple[CandidateGeometry, ...] = field(default=(), repr=False)

    def geometry(self, hypothesis: str) -> CandidateGeometry | None:
        matches = [item for item in self.geometries if item.hypothesis == hypothesis]
        if len(matches) > 1:
            raise GeometryValidationError(
                "edp_candidate_hypothesis_ambiguous",
                "a candidate exposes duplicate geometry for one hypothesis",
            )
        return matches[0] if matches else None


@dataclass(frozen=True)
class SelectedTransition:
    """Diagnostic change between two consecutive selected EDP candidates."""

    previous_message_index: int
    current_message_index: int
    previous_path_index: int
    current_path_index: int
    hypothesis: str
    source_delta_ms: float | None
    topology_source_changed: bool
    lane_topology_ids_changed: bool
    selected_path_index_changed: bool
    interval_count_changed: bool
    x_0_delta_m: float
    y_0_delta_m: float
    theta_0_delta_rad: float
    curvature_0_delta_per_m: float
    confidence_mean_delta: float | None
    common_station_count: int
    maximum_common_station_m: float
    station_zero_position_jump_m: float | None
    endpoint_position_jump_m: float
    sampled_position_rms_m: float
    rigid_normalized_shape_rms_m: float


def sample_candidate_curve(
    curve: SplineCurve,
    *,
    message_index: int,
    path_index: int,
    stations_m: Sequence[float] = DEFAULT_EDP_TRANSITION_STATIONS_M,
) -> CandidateGeometry:
    """Sample a provisional curve only where its native station domain exists."""

    stations = np.asarray(stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or not len(stations)
        or not np.all(np.isfinite(stations))
        or not np.all(np.diff(stations) > 0.0)
    ):
        raise ValueError("stations must be a finite, strictly increasing vector")
    tolerance = 1e-9
    retained = stations[
        (stations >= float(curve.s[0]) - tolerance)
        & (stations <= float(curve.s[-1]) + tolerance)
    ]
    if not len(retained):
        raise GeometryValidationError(
            "edp_candidate_no_requested_station_coverage",
            "candidate curve does not cover any requested transition station",
        )
    return CandidateGeometry(
        message_index=message_index,
        path_index=path_index,
        hypothesis=curve.curvature_meaning,
        stations_m=retained,
        x_m=np.interp(retained, curve.s, curve.x),
        y_m=np.interp(retained, curve.s, curve.y),
        heading_rad=np.interp(retained, curve.s, np.unwrap(curve.heading)),
        curvature_per_m=np.interp(retained, curve.s, curve.curvature),
    )


def _mean_or_none(values: Sequence[float]) -> float | None:
    return None if not values else float(np.mean(np.asarray(values, dtype=np.float64)))


def _rigid_normalized_shape_rms(
    previous_points: FloatArray,
    current_points: FloatArray,
    previous_heading: float,
    current_heading: float,
) -> float:
    angle = _wrap_angle(previous_heading - current_heading)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    rotation = np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)
    aligned = (current_points - current_points[0]) @ rotation.T + previous_points[0]
    return float(np.sqrt(np.mean(np.sum(np.square(aligned - previous_points), axis=1))))


def compare_selected_candidates(
    previous: CandidateSnapshot,
    current: CandidateSnapshot,
    *,
    hypothesis: str,
) -> SelectedTransition:
    """Compare consecutive selected candidates without assigning error semantics."""

    if not previous.selected_for_pairing_audit or not current.selected_for_pairing_audit:
        raise GeometryValidationError(
            "edp_transition_candidate_not_selected",
            "transition comparison requires two pairing-audit-selected candidates",
        )
    if current.message_index != previous.message_index + 1:
        raise GeometryValidationError(
            "edp_transition_messages_not_consecutive",
            "selected transition comparison requires consecutive message indices",
        )
    if previous.parameters is None or current.parameters is None:
        raise GeometryValidationError(
            "edp_transition_parameters_unavailable",
            "selected transition comparison requires both raw parameter sets",
        )
    previous_geometry = previous.geometry(hypothesis)
    current_geometry = current.geometry(hypothesis)
    if previous_geometry is None or current_geometry is None:
        raise GeometryValidationError(
            "edp_transition_geometry_unavailable",
            "selected transition comparison requires the requested hypothesis",
        )

    common_stations = np.intersect1d(
        previous_geometry.stations_m,
        current_geometry.stations_m,
    )
    if not len(common_stations):
        raise GeometryValidationError(
            "edp_transition_no_common_station",
            "consecutive candidates have no common requested station",
        )
    previous_indices = np.searchsorted(previous_geometry.stations_m, common_stations)
    current_indices = np.searchsorted(current_geometry.stations_m, common_stations)
    previous_points = previous_geometry.points[previous_indices]
    current_points = current_geometry.points[current_indices]
    differences = current_points - previous_points
    distances = np.linalg.norm(differences, axis=1)
    station_zero_jump = None
    zero_positions = np.flatnonzero(np.isclose(common_stations, 0.0, atol=1e-12))
    if len(zero_positions):
        station_zero_jump = float(distances[int(zero_positions[0])])

    previous_parameters = previous.parameters
    current_parameters = current.parameters
    source_delta_ms = (
        None
        if previous.source_time_ns is None or current.source_time_ns is None
        else (current.source_time_ns - previous.source_time_ns) / 1e6
    )
    return SelectedTransition(
        previous_message_index=previous.message_index,
        current_message_index=current.message_index,
        previous_path_index=previous.path_index,
        current_path_index=current.path_index,
        hypothesis=hypothesis,
        source_delta_ms=source_delta_ms,
        topology_source_changed=(previous.topology_source != current.topology_source),
        lane_topology_ids_changed=(
            previous.lane_topology_ids != current.lane_topology_ids
        ),
        selected_path_index_changed=(previous.path_index != current.path_index),
        interval_count_changed=(
            previous_parameters.interval_count != current_parameters.interval_count
        ),
        x_0_delta_m=float(current_parameters.x_0 - previous_parameters.x_0),
        y_0_delta_m=float(current_parameters.y_0 - previous_parameters.y_0),
        theta_0_delta_rad=_wrap_angle(
            current_parameters.theta_0 - previous_parameters.theta_0
        ),
        curvature_0_delta_per_m=float(
            current_parameters.curvature_0 - previous_parameters.curvature_0
        ),
        confidence_mean_delta=(
            None
            if _mean_or_none(previous.confidences) is None
            or _mean_or_none(current.confidences) is None
            else float(
                _mean_or_none(current.confidences)
                - _mean_or_none(previous.confidences)
            )
        ),
        common_station_count=len(common_stations),
        maximum_common_station_m=float(common_stations[-1]),
        station_zero_position_jump_m=station_zero_jump,
        endpoint_position_jump_m=float(distances[-1]),
        sampled_position_rms_m=float(np.sqrt(np.mean(np.square(distances)))),
        rigid_normalized_shape_rms_m=_rigid_normalized_shape_rms(
            previous_points,
            current_points,
            float(previous_geometry.heading_rad[previous_indices[0]]),
            float(current_geometry.heading_rad[current_indices[0]]),
        ),
    )


def selected_candidate_transitions(
    candidates: Sequence[CandidateSnapshot],
) -> tuple[SelectedTransition, ...]:
    """Return both-hypothesis comparisons for consecutive ready messages."""

    selected = sorted(
        (item for item in candidates if item.selected_for_pairing_audit),
        key=lambda item: item.message_index,
    )
    transitions: list[SelectedTransition] = []
    for previous, current in zip(selected, selected[1:]):
        if current.message_index != previous.message_index + 1:
            continue
        for hypothesis in EDP_SPLINE_HYPOTHESES:
            try:
                transitions.append(
                    compare_selected_candidates(
                        previous,
                        current,
                        hypothesis=hypothesis,
                    )
                )
            except GeometryValidationError:
                continue
    return tuple(transitions)


def rank_transition_centers(
    transitions: Sequence[SelectedTransition],
    *,
    hypothesis: str = "curvature_delta",
    maximum_centers: int = 4,
    minimum_separation_messages: int = 7,
) -> tuple[int, ...]:
    """Rank large curve changes without declaring an arbitrary event threshold."""

    if hypothesis not in EDP_SPLINE_HYPOTHESES:
        raise ValueError(f"unknown spline hypothesis: {hypothesis}")
    if maximum_centers < 1:
        raise ValueError("maximum_centers must be positive")
    if minimum_separation_messages < 1:
        raise ValueError("minimum_separation_messages must be positive")
    ordered = sorted(
        (item for item in transitions if item.hypothesis == hypothesis),
        key=lambda item: (
            -item.sampled_position_rms_m,
            item.current_message_index,
        ),
    )
    selected: list[int] = []
    for item in ordered:
        center = item.current_message_index
        if any(abs(center - other) < minimum_separation_messages for other in selected):
            continue
        selected.append(center)
        if len(selected) == maximum_centers:
            break
    return tuple(sorted(selected))
