"""Candidate-level transition diagnostics for EstimatedDrivePaths.

This module deliberately does not define a lane-estimation residual.  It keeps
all EDP candidates, evaluates both unresolved ``curvature_change`` hypotheses,
and distinguishes ordinary consecutive updates from spline-window rollovers.
Rollover continuity is evaluated at shifted native stations; no physical
cross-signal correspondence is inferred from this internal representation test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from .geometry_validation import (
    GeometryValidationError,
    SplineCurve,
    SplineParameters,
    generate_spline_curve,
)

FloatArray = NDArray[np.float64]
DEFAULT_EDP_TRANSITION_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))
EDP_SPLINE_HYPOTHESES = ("curvature_rate", "curvature_delta")
DEFAULT_ROLLOVER_BOUNDARY_ATOL_M = 1e-6
DEFAULT_ROLLOVER_MIN_MATCHED_BOUNDARIES = 3
DEFAULT_ROLLOVER_MIN_MATCHED_SPAN_M = 50.0


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
    common_station_count: int | None
    maximum_common_station_m: float | None
    station_zero_position_jump_m: float | None
    endpoint_position_jump_m: float | None
    sampled_position_rms_m: float | None
    rigid_normalized_shape_rms_m: float | None
    station_correspondence_status: str = "not_assessed"
    station_correspondence_failure_code: str | None = None
    rollover_detected: bool = False
    dropped_interval_count: int | None = None
    station_shift_m: float | None = None
    matched_boundary_count: int = 0
    matched_station_span_m: float = 0.0
    matched_curvature_change_count: int = 0
    curvature_change_suffix_rms_raw: float | None = None
    same_station_metrics_valid: bool = False
    shift_aware_metric_status: str = "not_applicable"
    shift_aware_station_count: int | None = None
    shift_aware_maximum_current_station_m: float | None = None
    shift_aware_shape_rms_m: float | None = None
    shift_aware_shape_endpoint_m: float | None = None
    shift_aware_shape_max_m: float | None = None
    rate_curvature_at_shift_delta_per_m: float | None = None


@dataclass(frozen=True)
class StationCorrespondence:
    """Fail-closed suffix-to-prefix correspondence between spline windows."""

    status: str
    failure_code: str | None
    rollover_detected: bool
    dropped_interval_count: int | None
    station_shift_m: float | None
    matched_boundary_count: int
    matched_station_span_m: float


@dataclass(frozen=True)
class _ShiftAwareMetrics:
    station_count: int
    maximum_current_station_m: float
    shape_rms_m: float
    shape_endpoint_m: float
    shape_max_m: float
    rate_curvature_at_shift_delta_per_m: float | None


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


def detect_station_correspondence(
    previous: SplineParameters,
    current: SplineParameters,
    *,
    boundary_atol_m: float = DEFAULT_ROLLOVER_BOUNDARY_ATOL_M,
    minimum_matched_boundaries: int = DEFAULT_ROLLOVER_MIN_MATCHED_BOUNDARIES,
    minimum_matched_span_m: float = DEFAULT_ROLLOVER_MIN_MATCHED_SPAN_M,
) -> StationCorrespondence:
    """Detect a unique ordered suffix-to-prefix station-window rebase.

    The detector uses only the spline boundary sequence.  It does not use a
    curve-jump threshold, interval-count change, or the unresolved curvature
    semantics.  Every previous suffix is translated to the current first
    boundary and its longest matching current prefix is measured.  Ties and
    short overlaps fail closed.
    """

    if not math.isfinite(boundary_atol_m) or boundary_atol_m < 0.0:
        raise ValueError("boundary_atol_m must be finite and nonnegative")
    if minimum_matched_boundaries < 2:
        raise ValueError("minimum_matched_boundaries must be at least two")
    if not math.isfinite(minimum_matched_span_m) or minimum_matched_span_m <= 0.0:
        raise ValueError("minimum_matched_span_m must be finite and positive")

    previous_boundaries = previous.segment_starts
    current_boundaries = current.segment_starts
    candidates: list[tuple[float, int, int]] = []
    for dropped_count in range(len(previous_boundaries) - 1):
        translated = (
            previous_boundaries[dropped_count:]
            - previous_boundaries[dropped_count]
            + current_boundaries[0]
        )
        maximum_count = min(len(translated), len(current_boundaries))
        matched_count = 0
        for index in range(maximum_count):
            if math.isclose(
                float(translated[index]),
                float(current_boundaries[index]),
                rel_tol=0.0,
                abs_tol=boundary_atol_m,
            ):
                matched_count += 1
            else:
                break
        matched_span = (
            0.0
            if matched_count < 2
            else float(current_boundaries[matched_count - 1] - current_boundaries[0])
        )
        candidates.append((matched_span, matched_count, dropped_count))

    best_span = max(item[0] for item in candidates)
    span_winners = [
        item
        for item in candidates
        if math.isclose(item[0], best_span, rel_tol=0.0, abs_tol=boundary_atol_m)
    ]
    best_count = max(item[1] for item in span_winners)
    winners = [item for item in span_winners if item[1] == best_count]
    if len(winners) != 1:
        return StationCorrespondence(
            status="unassessed",
            failure_code="rollover_boundary_alignment_ambiguous",
            rollover_detected=False,
            dropped_interval_count=None,
            station_shift_m=None,
            matched_boundary_count=best_count,
            matched_station_span_m=best_span,
        )

    _, matched_count, dropped_count = winners[0]
    if (
        matched_count < minimum_matched_boundaries
        or best_span < minimum_matched_span_m
    ):
        return StationCorrespondence(
            status="unassessed",
            failure_code="rollover_boundary_overlap_insufficient",
            rollover_detected=False,
            dropped_interval_count=None,
            station_shift_m=None,
            matched_boundary_count=matched_count,
            matched_station_span_m=best_span,
        )

    shift_m = float(
        previous_boundaries[dropped_count] - current_boundaries[0]
    )
    if dropped_count == 0:
        return StationCorrespondence(
            status="same_station_window",
            failure_code=None,
            rollover_detected=False,
            dropped_interval_count=0,
            station_shift_m=0.0,
            matched_boundary_count=matched_count,
            matched_station_span_m=best_span,
        )
    if shift_m <= boundary_atol_m:
        return StationCorrespondence(
            status="unassessed",
            failure_code="rollover_station_shift_not_positive",
            rollover_detected=False,
            dropped_interval_count=None,
            station_shift_m=None,
            matched_boundary_count=matched_count,
            matched_station_span_m=best_span,
        )
    return StationCorrespondence(
        status="rollover_detected",
        failure_code=None,
        rollover_detected=True,
        dropped_interval_count=dropped_count,
        station_shift_m=shift_m,
        matched_boundary_count=matched_count,
        matched_station_span_m=best_span,
    )


def _same_station_metrics(
    previous_geometry: CandidateGeometry,
    current_geometry: CandidateGeometry,
) -> tuple[int, float, float | None, float, float, float]:
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
    distances = np.linalg.norm(current_points - previous_points, axis=1)
    zero_positions = np.flatnonzero(np.isclose(common_stations, 0.0, atol=1e-12))
    station_zero_jump = (
        None
        if not len(zero_positions)
        else float(distances[int(zero_positions[0])])
    )
    return (
        len(common_stations),
        float(common_stations[-1]),
        station_zero_jump,
        float(distances[-1]),
        float(np.sqrt(np.mean(np.square(distances)))),
        _rigid_normalized_shape_rms(
            previous_points,
            current_points,
            float(previous_geometry.heading_rad[previous_indices[0]]),
            float(current_geometry.heading_rad[current_indices[0]]),
        ),
    )


def _shift_aware_metrics(
    previous: CandidateSnapshot,
    current: CandidateSnapshot,
    *,
    hypothesis: str,
    station_shift_m: float,
    max_step_m: float,
) -> _ShiftAwareMetrics:
    """Compare ``previous(q + shift)`` with ``current(q)`` without extrapolation."""

    assert previous.parameters is not None
    assert current.parameters is not None
    current_geometry = current.geometry(hypothesis)
    if current_geometry is None:
        raise GeometryValidationError(
            "edp_rollover_geometry_unavailable",
            "requested rollover hypothesis is unavailable",
        )
    requested = current_geometry.stations_m
    lower = max(
        float(current.parameters.segment_starts[0]),
        float(previous.parameters.segment_starts[0] - station_shift_m),
    )
    upper = min(
        float(current.parameters.segment_starts[-1]),
        float(previous.parameters.segment_starts[-1] - station_shift_m),
    )
    q = requested[(requested >= lower - 1e-9) & (requested <= upper + 1e-9)]
    if len(q) < 2:
        raise GeometryValidationError(
            "edp_rollover_common_coverage_insufficient",
            "rollover comparison has fewer than two requested stations in common",
        )

    previous_stations = q + station_shift_m
    previous_curve = generate_spline_curve(
        previous.parameters,
        meaning=hypothesis,
        anchor_policy="anchor_zero",
        max_step_m=max_step_m,
        extra_stations=tuple(float(value) for value in previous_stations),
    )
    current_curve = generate_spline_curve(
        current.parameters,
        meaning=hypothesis,
        anchor_policy="anchor_zero",
        max_step_m=max_step_m,
        extra_stations=tuple(float(value) for value in q),
    )
    previous_points = np.column_stack(
        (
            np.interp(previous_stations, previous_curve.s, previous_curve.x),
            np.interp(previous_stations, previous_curve.s, previous_curve.y),
        )
    )
    current_points = np.column_stack(
        (
            np.interp(q, current_curve.s, current_curve.x),
            np.interp(q, current_curve.s, current_curve.y),
        )
    )
    previous_heading = np.interp(
        previous_stations,
        previous_curve.s,
        np.unwrap(previous_curve.heading),
    )
    current_heading = np.interp(
        q,
        current_curve.s,
        np.unwrap(current_curve.heading),
    )
    angle = _wrap_angle(float(previous_heading[0] - current_heading[0]))
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle))),
        dtype=np.float64,
    )
    aligned_current = (
        (current_points - current_points[0]) @ rotation.T + previous_points[0]
    )
    distances = np.linalg.norm(aligned_current - previous_points, axis=1)

    rate_delta = None
    try:
        previous_rate = generate_spline_curve(
            previous.parameters,
            meaning="curvature_rate",
            anchor_policy="anchor_zero",
            max_step_m=max_step_m,
            extra_stations=(float(previous_stations[0]),),
        )
        current_rate = generate_spline_curve(
            current.parameters,
            meaning="curvature_rate",
            anchor_policy="anchor_zero",
            max_step_m=max_step_m,
            extra_stations=(float(q[0]),),
        )
        rate_delta = float(
            np.interp(previous_stations[0], previous_rate.s, previous_rate.curvature)
            - np.interp(q[0], current_rate.s, current_rate.curvature)
        )
    except GeometryValidationError:
        pass

    return _ShiftAwareMetrics(
        station_count=len(q),
        maximum_current_station_m=float(q[-1]),
        shape_rms_m=float(np.sqrt(np.mean(np.square(distances)))),
        shape_endpoint_m=float(distances[-1]),
        shape_max_m=float(np.max(distances)),
        rate_curvature_at_shift_delta_per_m=rate_delta,
    )


def compare_selected_candidates(
    previous: CandidateSnapshot,
    current: CandidateSnapshot,
    *,
    hypothesis: str,
    max_step_m: float = 0.25,
) -> SelectedTransition:
    """Compare consecutive selected candidates without assigning residual semantics."""

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

    previous_parameters = previous.parameters
    current_parameters = current.parameters
    source_delta_ms = (
        None
        if previous.source_time_ns is None or current.source_time_ns is None
        else (current.source_time_ns - previous.source_time_ns) / 1e6
    )
    topology_source_changed = previous.topology_source != current.topology_source
    lane_topology_ids_changed = previous.lane_topology_ids != current.lane_topology_ids
    correspondence = detect_station_correspondence(
        previous_parameters,
        current_parameters,
    )
    if source_delta_ms is None or source_delta_ms <= 0.0:
        correspondence = StationCorrespondence(
            status="unassessed",
            failure_code="edp_transition_source_time_invalid",
            rollover_detected=False,
            dropped_interval_count=None,
            station_shift_m=None,
            matched_boundary_count=correspondence.matched_boundary_count,
            matched_station_span_m=correspondence.matched_station_span_m,
        )
    elif (
        topology_source_changed
        or lane_topology_ids_changed
        or previous.role_symbol != current.role_symbol
    ):
        correspondence = StationCorrespondence(
            status="unassessed",
            failure_code="edp_transition_candidate_identity_changed",
            rollover_detected=False,
            dropped_interval_count=None,
            station_shift_m=None,
            matched_boundary_count=correspondence.matched_boundary_count,
            matched_station_span_m=correspondence.matched_station_span_m,
        )

    common_station_count: int | None = None
    maximum_common_station_m: float | None = None
    station_zero_jump: float | None = None
    endpoint_jump: float | None = None
    sampled_rms: float | None = None
    rigid_same_station_rms: float | None = None
    same_station_metrics_valid = False
    shift_status = "not_applicable"
    shift_metrics: _ShiftAwareMetrics | None = None
    if correspondence.status == "same_station_window":
        (
            common_station_count,
            maximum_common_station_m,
            station_zero_jump,
            endpoint_jump,
            sampled_rms,
            rigid_same_station_rms,
        ) = _same_station_metrics(previous_geometry, current_geometry)
        same_station_metrics_valid = True
    elif correspondence.rollover_detected:
        assert correspondence.station_shift_m is not None
        try:
            shift_metrics = _shift_aware_metrics(
                previous,
                current,
                hypothesis=hypothesis,
                station_shift_m=correspondence.station_shift_m,
                max_step_m=max_step_m,
            )
        except GeometryValidationError as error:
            shift_status = error.code
        else:
            shift_status = "ready"

    matched_curvature_count = 0
    curvature_suffix_rms = None
    if correspondence.dropped_interval_count is not None:
        dropped = correspondence.dropped_interval_count
        matched_curvature_count = min(
            max(correspondence.matched_boundary_count - 1, 0),
            len(previous_parameters.curvature_change) - dropped,
            len(current_parameters.curvature_change),
        )
        if matched_curvature_count > 0:
            difference = (
                previous_parameters.curvature_change[
                    dropped : dropped + matched_curvature_count
                ]
                - current_parameters.curvature_change[:matched_curvature_count]
            )
            curvature_suffix_rms = float(np.sqrt(np.mean(np.square(difference))))

    return SelectedTransition(
        previous_message_index=previous.message_index,
        current_message_index=current.message_index,
        previous_path_index=previous.path_index,
        current_path_index=current.path_index,
        hypothesis=hypothesis,
        source_delta_ms=source_delta_ms,
        topology_source_changed=topology_source_changed,
        lane_topology_ids_changed=lane_topology_ids_changed,
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
        common_station_count=common_station_count,
        maximum_common_station_m=maximum_common_station_m,
        station_zero_position_jump_m=station_zero_jump,
        endpoint_position_jump_m=endpoint_jump,
        sampled_position_rms_m=sampled_rms,
        rigid_normalized_shape_rms_m=rigid_same_station_rms,
        station_correspondence_status=correspondence.status,
        station_correspondence_failure_code=correspondence.failure_code,
        rollover_detected=correspondence.rollover_detected,
        dropped_interval_count=correspondence.dropped_interval_count,
        station_shift_m=correspondence.station_shift_m,
        matched_boundary_count=correspondence.matched_boundary_count,
        matched_station_span_m=correspondence.matched_station_span_m,
        matched_curvature_change_count=matched_curvature_count,
        curvature_change_suffix_rms_raw=curvature_suffix_rms,
        same_station_metrics_valid=same_station_metrics_valid,
        shift_aware_metric_status=shift_status,
        shift_aware_station_count=(
            None if shift_metrics is None else shift_metrics.station_count
        ),
        shift_aware_maximum_current_station_m=(
            None
            if shift_metrics is None
            else shift_metrics.maximum_current_station_m
        ),
        shift_aware_shape_rms_m=(
            None if shift_metrics is None else shift_metrics.shape_rms_m
        ),
        shift_aware_shape_endpoint_m=(
            None if shift_metrics is None else shift_metrics.shape_endpoint_m
        ),
        shift_aware_shape_max_m=(
            None if shift_metrics is None else shift_metrics.shape_max_m
        ),
        rate_curvature_at_shift_delta_per_m=(
            None
            if shift_metrics is None
            else shift_metrics.rate_curvature_at_shift_delta_per_m
        ),
    )


def selected_candidate_transitions(
    candidates: Sequence[CandidateSnapshot],
    *,
    max_step_m: float = 0.25,
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
                        max_step_m=max_step_m,
                    )
                )
            except GeometryValidationError:
                continue
    return tuple(transitions)


def rank_transition_centers(
    transitions: Sequence[SelectedTransition],
    *,
    hypothesis: str = "curvature_rate",
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
        (
            item
            for item in transitions
            if item.hypothesis == hypothesis
            and item.sampled_position_rms_m is not None
        ),
        key=lambda item: (
            -float(item.sampled_position_rms_m),
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
