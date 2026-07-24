"""Road-frame synchronization, lane-association audit, and residual extraction.

Version 0.3.2 treats the map-based road as a *surrogate reference*, not as
ground truth.  It preserves every lane candidate before selecting one, uses
embedded source timestamps by default, and reports geometric coverage at
multiple horizons before the residual model is interpreted.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike

from .mcap_io import RoadFrame, RoadSegment, load_road_frames
from .residuals import FloatArray, Path2D, residual_vector

DEFAULT_REFERENCE_TOPIC = "/adp/road_lane_map_based"
DEFAULT_ESTIMATE_TOPIC = "/adp/lane_topology_sensor_based"
DEFAULT_STATIONS = np.arange(0.0, 50.1, 5.0)
DEFAULT_AUDIT_HORIZONS = (20.0, 30.0, 40.0, 50.0)


class FrameRejection(ValueError):
    """A path-pair rejection with a stable machine-readable reason."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


@dataclass(frozen=True)
class ProjectionResult:
    """Polyline coordinates assigned to query points by nearest projection."""

    stations: FloatArray
    projected_points: FloatArray
    distances: FloatArray


@dataclass(frozen=True)
class SelectedRoadSegment:
    """A selected segment and the rule used to select it."""

    segment: RoadSegment
    method: Literal["metadata", "nearest_origin_fallback"]


@dataclass(frozen=True)
class SynchronizedRoadFramePair:
    """One one-to-one time match between reference and estimate frames."""

    reference: RoadFrame
    estimate: RoadFrame
    delta_ns: int

    @property
    def log_delta_ns(self) -> int:
        """Return estimate minus reference MCAP log time."""

        return self.estimate.log_time_ns - self.reference.log_time_ns

    @property
    def source_delta_ns(self) -> int | None:
        """Return estimate minus reference embedded source time when available."""

        if (
            self.reference.source_time_ns is None
            or self.estimate.source_time_ns is None
        ):
            return None
        return self.estimate.source_time_ns - self.reference.source_time_ns


@dataclass(frozen=True)
class SynchronizationResult:
    """One-to-one synchronization output and unmatched-frame counts."""

    pairs: tuple[SynchronizedRoadFramePair, ...]
    unmatched_reference: int
    unmatched_estimate: int
    time_basis: Literal["log", "source"]


@dataclass(frozen=True)
class ResidualRecord:
    """Provenance and preprocessing diagnostics for one residual row."""

    recording_id: str
    reference_log_time_ns: int
    estimate_log_time_ns: int
    reference_source_time_ns: int | None
    estimate_source_time_ns: int | None
    synchronization_delta_ms: float
    log_time_delta_ms: float
    source_time_delta_ms: float | None
    reference_segment_id: int
    estimate_segment_id: int
    reference_geometry_source: str
    estimate_geometry_source: str
    reference_selection: str
    estimate_selection: str
    estimate_points_retained_fraction: float
    maximum_projection_distance_m: float


@dataclass(frozen=True)
class CandidateSegmentRecord:
    """Geometry and selection evidence for one lane-segment candidate."""

    recording_id: str
    pair_index: int
    role: Literal["reference", "estimate"]
    log_time_ns: int
    source_time_ns: int | None
    segment_id: int
    selected: bool
    selection_method: str
    is_ego: bool | None
    geometry_source: str
    quality: object | None
    point_count: int
    origin_distance_m: float
    station_start_m: float
    station_end_m: float
    forward_coverage_m: float


@dataclass(frozen=True)
class PairAuditRecord:
    """Synchronization, association, coverage, and rejection evidence per pair."""

    recording_id: str
    pair_index: int
    synchronization_basis: str
    synchronization_delta_ms: float
    log_time_delta_ms: float
    source_time_delta_ms: float | None
    reference_segment_id: int | None
    estimate_segment_id: int | None
    reference_selection: str
    estimate_selection: str
    reference_forward_coverage_m: float | None
    estimate_forward_coverage_m: float | None
    common_forward_coverage_m: float | None
    estimate_points_retained_fraction: float | None
    maximum_projection_distance_m: float | None
    maximum_absolute_residual_m: float | None
    accepted: bool
    rejection_reason: str


@dataclass(frozen=True)
class LaneAssociationExample:
    """All candidates for one synchronized pair retained for labelled plotting."""

    pair_index: int
    reference_segments: tuple[RoadSegment, ...]
    estimate_segments: tuple[RoadSegment, ...]
    selected_reference_segment_id: int | None
    selected_estimate_segment_id: int | None
    source_time_delta_ms: float | None
    accepted: bool
    rejection_reason: str


@dataclass(frozen=True)
class PathPairExample:
    """A small in-memory sample retained only for diagnostic plotting."""

    reference: Path2D
    estimate: Path2D
    residual: FloatArray


@dataclass(frozen=True)
class ExtractionReport:
    """Counts needed to audit data acceptance and rejection."""

    reference_frames: int
    estimate_frames: int
    synchronized_pairs: int
    pairs_considered: int
    unconsidered_synchronized_pairs: int
    accepted_pairs: int
    unmatched_reference_frames: int
    unmatched_estimate_frames: int
    time_basis: str
    max_time_delta_ms: float
    rejection_counts: tuple[tuple[str, int], ...]

    @property
    def rejection_dict(self) -> dict[str, int]:
        return dict(self.rejection_counts)

    def to_dict(self) -> dict[str, object]:
        return {
            "reference_frames": self.reference_frames,
            "estimate_frames": self.estimate_frames,
            "synchronized_pairs": self.synchronized_pairs,
            "pairs_considered": self.pairs_considered,
            "unconsidered_synchronized_pairs": (
                self.unconsidered_synchronized_pairs
            ),
            "accepted_pairs": self.accepted_pairs,
            "unmatched_reference_frames": self.unmatched_reference_frames,
            "unmatched_estimate_frames": self.unmatched_estimate_frames,
            "time_basis": self.time_basis,
            "max_time_delta_ms": self.max_time_delta_ms,
            "rejection_counts": self.rejection_dict,
        }


@dataclass(frozen=True)
class ResidualDataset:
    """Residual matrix plus row-level provenance and extraction diagnostics."""

    stations: FloatArray
    residuals: FloatArray
    records: tuple[ResidualRecord, ...]
    examples: tuple[PathPairExample, ...]
    candidate_records: tuple[CandidateSegmentRecord, ...]
    pair_audit_records: tuple[PairAuditRecord, ...]
    association_examples: tuple[LaneAssociationExample, ...]
    audit_horizons_m: tuple[float, ...]
    report: ExtractionReport
    reference_topic: str
    estimate_topic: str

    def __post_init__(self) -> None:
        stations = np.asarray(self.stations, dtype=np.float64)
        residuals = np.asarray(self.residuals, dtype=np.float64)
        audit_horizons = np.asarray(self.audit_horizons_m, dtype=np.float64)
        if stations.ndim != 1 or len(stations) == 0:
            raise ValueError("stations must be a nonempty one-dimensional array")
        if residuals.ndim != 2 or residuals.shape[1] != len(stations):
            raise ValueError("residuals must have shape (N, H)")
        if residuals.shape[0] != len(self.records):
            raise ValueError("one ResidualRecord is required for every residual row")
        if not np.all(np.isfinite(stations)) or not np.all(np.isfinite(residuals)):
            raise ValueError("stations and residuals must contain only finite values")
        if (
            audit_horizons.ndim != 1
            or len(audit_horizons) == 0
            or not np.all(np.isfinite(audit_horizons))
            or np.any(audit_horizons <= 0.0)
            or np.any(np.diff(audit_horizons) <= 0.0)
        ):
            raise ValueError(
                "audit_horizons_m must be finite, positive, and strictly increasing"
            )
        object.__setattr__(self, "stations", stations)
        object.__setattr__(self, "residuals", residuals)
        object.__setattr__(
            self,
            "audit_horizons_m",
            tuple(float(value) for value in audit_horizons),
        )

    def horizon_coverage_counts(self) -> dict[float, int]:
        """Count geometrically usable synchronized pairs at each audit horizon."""

        return {
            horizon: sum(
                record.common_forward_coverage_m is not None
                and record.common_forward_coverage_m >= horizon - 1e-9
                for record in self.pair_audit_records
            )
            for horizon in self.audit_horizons_m
        }


def _polyline_geometry(points: ArrayLike) -> tuple[FloatArray, FloatArray]:
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2:
        raise ValueError("points must have shape (N, 2)")
    if len(coordinates) < 2 or not np.all(np.isfinite(coordinates)):
        raise ValueError("points must contain at least two finite coordinates")

    increments = np.hypot(
        np.diff(coordinates[:, 0]),
        np.diff(coordinates[:, 1]),
    )
    keep = np.concatenate(([True], increments > 1e-9))
    coordinates = coordinates[keep]
    if len(coordinates) < 2:
        raise ValueError("polyline collapses to fewer than two unique points")
    increments = np.hypot(
        np.diff(coordinates[:, 0]),
        np.diff(coordinates[:, 1]),
    )
    stations = np.concatenate(([0.0], np.cumsum(increments)))
    return coordinates, stations


def project_points_to_polyline(
    polyline: ArrayLike,
    query_points: ArrayLike,
) -> ProjectionResult:
    """Project query points onto the closest line segment of a polyline."""

    points, stations = _polyline_geometry(polyline)
    queries = np.asarray(query_points, dtype=np.float64)
    if queries.ndim == 1:
        queries = queries[None, :]
    if queries.ndim != 2 or queries.shape[1] != 2 or len(queries) == 0:
        raise ValueError("query_points must have shape (M, 2)")
    if not np.all(np.isfinite(queries)):
        raise ValueError("query_points must contain only finite values")

    starts = points[:-1]
    vectors = points[1:] - starts
    squared_lengths = np.einsum("ij,ij->i", vectors, vectors)
    lengths = np.sqrt(squared_lengths)

    projected_stations = np.empty(len(queries), dtype=np.float64)
    projected_points = np.empty_like(queries)
    distances = np.empty(len(queries), dtype=np.float64)
    for index, query in enumerate(queries):
        fractions = np.einsum("ij,ij->i", query - starts, vectors) / squared_lengths
        fractions = np.clip(fractions, 0.0, 1.0)
        candidates = starts + fractions[:, None] * vectors
        squared_distances = np.einsum(
            "ij,ij->i",
            candidates - query,
            candidates - query,
        )
        segment_index = int(np.argmin(squared_distances))
        fraction = fractions[segment_index]
        projected_stations[index] = (
            stations[segment_index] + fraction * lengths[segment_index]
        )
        projected_points[index] = candidates[segment_index]
        distances[index] = np.sqrt(squared_distances[segment_index])

    return ProjectionResult(
        stations=projected_stations,
        projected_points=projected_points,
        distances=distances,
    )


def reference_path_from_segment(segment: RoadSegment) -> Path2D:
    """Create a geometric reference path with ``s=0`` at the ego origin."""

    points, stations = _polyline_geometry(segment.points)
    origin_projection = project_points_to_polyline(points, [[0.0, 0.0]])
    origin_station = float(origin_projection.stations[0])

    # In the confirmed ego-local frame, +x is forward.  Normalize a reversed
    # vertex order so positive reference station also points forward.
    before = max(stations[0], origin_station - 1.0)
    after = min(stations[-1], origin_station + 1.0)
    if after > before:
        local_x_change = float(
            np.interp(after, stations, points[:, 0])
            - np.interp(before, stations, points[:, 0])
        )
        if local_x_change < 0.0:
            points = points[::-1]
            points, stations = _polyline_geometry(points)
            origin_projection = project_points_to_polyline(
                points,
                [[0.0, 0.0]],
            )
            origin_station = float(origin_projection.stations[0])

    stations = stations - origin_station
    return Path2D(s=stations, x=points[:, 0], y=points[:, 1])


def estimate_path_on_reference(
    estimate_segment: RoadSegment,
    reference_path: Path2D,
    *,
    minimum_retained_fraction: float = 0.8,
) -> tuple[Path2D, FloatArray, float]:
    """Assign estimate vertices the station of their reference projection."""

    if not 0.0 < minimum_retained_fraction <= 1.0:
        raise ValueError("minimum_retained_fraction must be in (0, 1]")

    projection = project_points_to_polyline(
        np.column_stack((reference_path.x, reference_path.y)),
        estimate_segment.points,
    )
    projected_stations = projection.stations + reference_path.s[0]
    x = estimate_segment.x.copy()
    y = estimate_segment.y.copy()
    distances = projection.distances.copy()

    differences = np.diff(projected_stations)
    nonzero = differences[np.abs(differences) > 1e-7]
    if len(nonzero) == 0:
        raise FrameRejection(
            "estimate_projection_degenerate",
            "estimate vertices project to one reference station",
        )
    if float(np.median(nonzero)) < 0.0:
        projected_stations = projected_stations[::-1]
        x = x[::-1]
        y = y[::-1]
        distances = distances[::-1]

    # Points outside the finite reference polyline clamp to an endpoint and
    # create a repeated leading/trailing station. Trim those out-of-domain tails
    # before measuring internal monotonicity.
    start = 0
    while (
        start + 1 < len(projected_stations)
        and projected_stations[start + 1] <= projected_stations[start] + 1e-7
    ):
        start += 1
    stop = len(projected_stations)
    while (
        stop - 2 >= start
        and projected_stations[stop - 1] <= projected_stations[stop - 2] + 1e-7
    ):
        stop -= 1
    projected_stations = projected_stations[start:stop]
    x = x[start:stop]
    y = y[start:stop]
    distances = distances[start:stop]
    if len(projected_stations) < 2:
        raise FrameRejection(
            "estimate_projection_degenerate",
            "estimate has fewer than two in-domain projected vertices",
        )

    keep_indices = [0]
    for index in range(1, len(projected_stations)):
        if projected_stations[index] > projected_stations[keep_indices[-1]] + 1e-7:
            keep_indices.append(index)
    retained_fraction = len(keep_indices) / len(projected_stations)
    if len(keep_indices) < 2 or retained_fraction < minimum_retained_fraction:
        raise FrameRejection(
            "estimate_projection_nonmonotonic",
            "estimate-to-reference projection is not sufficiently monotonic",
        )

    keep = np.asarray(keep_indices, dtype=np.int64)
    return (
        Path2D(
            s=projected_stations[keep],
            x=x[keep],
            y=y[keep],
        ),
        distances[keep],
        retained_fraction,
    )


def _selection_score(
    segment: RoadSegment,
    *,
    station_min: float,
    station_max: float,
) -> tuple[float, float, int]:
    path = reference_path_from_segment(segment)
    coverage_shortfall = max(0.0, path.s[0] - station_min) + max(
        0.0, station_max - path.s[-1]
    )
    origin_distance = float(
        project_points_to_polyline(segment.points, [[0.0, 0.0]]).distances[0]
    )
    # Never substitute a more distant adjacent lane merely because it is longer.
    # Origin distance identifies the likely ego lane; coverage is only a tie-breaker.
    return origin_distance, coverage_shortfall, -len(segment.x)


def select_ego_segment(
    frame: RoadFrame,
    *,
    stations: ArrayLike = DEFAULT_STATIONS,
) -> SelectedRoadSegment:
    """Select the ego segment from metadata, falling back to geometry."""

    station_array = np.asarray(stations, dtype=np.float64)
    if station_array.ndim != 1 or len(station_array) == 0:
        raise ValueError("stations must be a nonempty one-dimensional array")

    metadata_candidates = [segment for segment in frame.segments if segment.is_ego]
    candidates = metadata_candidates if metadata_candidates else list(frame.segments)
    scored: list[tuple[tuple[float, float, int], RoadSegment]] = []
    for segment in candidates:
        try:
            score = _selection_score(
                segment,
                station_min=float(station_array[0]),
                station_max=float(station_array[-1]),
            )
        except ValueError:
            continue
        scored.append((score, segment))
    if not scored:
        raise FrameRejection(
            "no_usable_segment",
            f'frame on topic "{frame.topic}" has no usable road segment',
        )
    scored.sort(key=lambda item: item[0])
    return SelectedRoadSegment(
        segment=scored[0][1],
        method="metadata" if metadata_candidates else "nearest_origin_fallback",
    )


def candidate_segment_records(
    frame: RoadFrame,
    *,
    recording_id: str,
    pair_index: int,
    role: Literal["reference", "estimate"],
    selected: SelectedRoadSegment | None,
) -> tuple[CandidateSegmentRecord, ...]:
    """Describe every segment in a frame without discarding adjacent lanes."""

    records: list[CandidateSegmentRecord] = []
    selected_id = None if selected is None else selected.segment.segment_id
    selection_method = "" if selected is None else selected.method
    for segment in frame.segments:
        try:
            path = reference_path_from_segment(segment)
            origin_distance = float(
                project_points_to_polyline(
                    segment.points,
                    [[0.0, 0.0]],
                ).distances[0]
            )
        except (ValueError, FloatingPointError):
            continue
        records.append(
            CandidateSegmentRecord(
                recording_id=recording_id,
                pair_index=pair_index,
                role=role,
                log_time_ns=frame.log_time_ns,
                source_time_ns=frame.source_time_ns,
                segment_id=segment.segment_id,
                selected=segment.segment_id == selected_id,
                selection_method=(
                    selection_method if segment.segment_id == selected_id else ""
                ),
                is_ego=segment.is_ego,
                geometry_source=segment.geometry_source,
                quality=segment.quality,
                point_count=len(segment.x),
                origin_distance_m=origin_distance,
                station_start_m=float(path.s[0]),
                station_end_m=float(path.s[-1]),
                forward_coverage_m=max(0.0, float(path.s[-1])),
            )
        )
    return tuple(records)


def _source_delta_ms(pair: SynchronizedRoadFramePair) -> float | None:
    delta_ns = pair.source_delta_ns
    return None if delta_ns is None else delta_ns / 1_000_000.0


def _frame_time_ns(
    frame: RoadFrame,
    basis: Literal["log", "source"],
) -> int | None:
    return frame.log_time_ns if basis == "log" else frame.source_time_ns


def synchronize_road_frames(
    reference_frames: Sequence[RoadFrame],
    estimate_frames: Sequence[RoadFrame],
    *,
    max_delta_ms: float = 50.0,
    time_basis: Literal["log", "source"] = "source",
) -> SynchronizationResult:
    """Greedily create ordered, one-to-one nearest timestamp matches."""

    if not np.isfinite(max_delta_ms) or max_delta_ms < 0.0:
        raise ValueError("max_delta_ms must be finite and nonnegative")
    if time_basis not in ("log", "source"):
        raise ValueError('time_basis must be "log" or "source"')

    reference = [
        frame
        for frame in reference_frames
        if _frame_time_ns(frame, time_basis) is not None
    ]
    estimate = [
        frame
        for frame in estimate_frames
        if _frame_time_ns(frame, time_basis) is not None
    ]
    reference.sort(key=lambda frame: int(_frame_time_ns(frame, time_basis)))
    estimate.sort(key=lambda frame: int(_frame_time_ns(frame, time_basis)))

    tolerance_ns = int(round(max_delta_ms * 1_000_000.0))
    pairs: list[SynchronizedRoadFramePair] = []
    unmatched_reference = len(reference_frames) - len(reference)
    unmatched_estimate = len(estimate_frames) - len(estimate)
    reference_index = 0
    estimate_index = 0

    while reference_index < len(reference) and estimate_index < len(estimate):
        reference_time = int(_frame_time_ns(reference[reference_index], time_basis))
        estimate_time = int(_frame_time_ns(estimate[estimate_index], time_basis))

        if estimate_time < reference_time - tolerance_ns:
            unmatched_estimate += 1
            estimate_index += 1
            continue
        if estimate_time > reference_time + tolerance_ns:
            unmatched_reference += 1
            reference_index += 1
            continue

        best_estimate_index = estimate_index
        if estimate_index + 1 < len(estimate):
            next_time = int(
                _frame_time_ns(estimate[estimate_index + 1], time_basis)
            )
            if (
                abs(next_time - reference_time)
                < abs(estimate_time - reference_time)
                and abs(next_time - reference_time) <= tolerance_ns
            ):
                unmatched_estimate += 1
                best_estimate_index = estimate_index + 1
                estimate_time = next_time

        pairs.append(
            SynchronizedRoadFramePair(
                reference=reference[reference_index],
                estimate=estimate[best_estimate_index],
                delta_ns=estimate_time - reference_time,
            )
        )
        reference_index += 1
        estimate_index = best_estimate_index + 1

    unmatched_reference += len(reference) - reference_index
    unmatched_estimate += len(estimate) - estimate_index
    return SynchronizationResult(
        pairs=tuple(pairs),
        unmatched_reference=unmatched_reference,
        unmatched_estimate=unmatched_estimate,
        time_basis=time_basis,
    )


def _check_path_coverage(
    path: Path2D,
    stations: FloatArray,
    *,
    role: str,
) -> None:
    if path.s[0] > stations[0] + 1e-9 or path.s[-1] < stations[-1] - 1e-9:
        raise FrameRejection(
            f"insufficient_{role}_coverage",
            f"{role} path range [{path.s[0]}, {path.s[-1]}] does not cover "
            f"[{stations[0]}, {stations[-1]}]",
        )


def build_residual_dataset(
    reference_frames: Sequence[RoadFrame],
    estimate_frames: Sequence[RoadFrame],
    *,
    recording_id: str,
    stations: ArrayLike = DEFAULT_STATIONS,
    reference_topic: str = DEFAULT_REFERENCE_TOPIC,
    estimate_topic: str = DEFAULT_ESTIMATE_TOPIC,
    max_delta_ms: float = 50.0,
    time_basis: Literal["log", "source"] = "source",
    max_samples: int | None = 100,
    max_projection_distance_m: float = 5.0,
    max_absolute_residual_m: float = 5.0,
    minimum_retained_fraction: float = 0.8,
    n_examples: int = 4,
    audit_horizons_m: Sequence[float] = DEFAULT_AUDIT_HORIZONS,
    n_association_examples: int = 6,
) -> ResidualDataset:
    """Convert synchronized road frames into residuals plus association evidence."""

    station_array = np.asarray(stations, dtype=np.float64)
    audit_horizons = np.asarray(audit_horizons_m, dtype=np.float64)
    if (
        station_array.ndim != 1
        or len(station_array) == 0
        or not np.all(np.isfinite(station_array))
        or np.any(np.diff(station_array) <= 0.0)
    ):
        raise ValueError("stations must be finite and strictly increasing")
    if (
        audit_horizons.ndim != 1
        or len(audit_horizons) == 0
        or not np.all(np.isfinite(audit_horizons))
        or np.any(audit_horizons <= 0.0)
        or np.any(np.diff(audit_horizons) <= 0.0)
    ):
        raise ValueError(
            "audit_horizons_m must be finite, positive, and strictly increasing"
        )
    if max_samples is not None and max_samples < 1:
        raise ValueError("max_samples must be at least one or None")
    if n_examples < 0 or n_association_examples < 0:
        raise ValueError("example counts must be nonnegative")
    if max_projection_distance_m <= 0.0 or max_absolute_residual_m <= 0.0:
        raise ValueError("distance and residual limits must be positive")

    synchronization = synchronize_road_frames(
        reference_frames,
        estimate_frames,
        max_delta_ms=max_delta_ms,
        time_basis=time_basis,
    )
    rejection_counts: Counter[str] = Counter()
    residual_rows: list[FloatArray] = []
    records: list[ResidualRecord] = []
    examples: list[PathPairExample] = []
    candidate_records: list[CandidateSegmentRecord] = []
    pair_audit_records: list[PairAuditRecord] = []
    accepted_association_examples: list[LaneAssociationExample] = []
    rejected_association_examples: list[LaneAssociationExample] = []
    considered = 0

    for pair_index, pair in enumerate(synchronization.pairs):
        if max_samples is not None and len(residual_rows) >= max_samples:
            break
        considered += 1
        selected_reference: SelectedRoadSegment | None = None
        selected_estimate: SelectedRoadSegment | None = None
        reference_path: Path2D | None = None
        estimate_path: Path2D | None = None
        projection_distances: FloatArray | None = None
        retained_fraction: float | None = None
        reference_forward_coverage: float | None = None
        estimate_forward_coverage: float | None = None
        common_forward_coverage: float | None = None
        maximum_projection_distance: float | None = None
        maximum_absolute_residual: float | None = None
        residual: FloatArray | None = None
        rejection_reason = ""

        try:
            selected_reference = select_ego_segment(
                pair.reference,
                stations=station_array,
            )
            selected_estimate = select_ego_segment(
                pair.estimate,
                stations=station_array,
            )
            reference_path = reference_path_from_segment(
                selected_reference.segment
            )
            estimate_path, projection_distances, retained_fraction = (
                estimate_path_on_reference(
                    selected_estimate.segment,
                    reference_path,
                    minimum_retained_fraction=minimum_retained_fraction,
                )
            )
            reference_forward_coverage = max(0.0, float(reference_path.s[-1]))
            estimate_forward_coverage = max(0.0, float(estimate_path.s[-1]))
            common_forward_coverage = min(
                reference_forward_coverage,
                estimate_forward_coverage,
            )

            available_stop = min(
                float(station_array[-1]),
                common_forward_coverage,
            )
            relevant = (estimate_path.s >= station_array[0] - 1e-9) & (
                estimate_path.s <= available_stop + 1e-9
            )
            if np.any(relevant):
                maximum_projection_distance = float(
                    np.max(projection_distances[relevant])
                )

            _check_path_coverage(
                reference_path,
                station_array,
                role="reference",
            )
            _check_path_coverage(
                estimate_path,
                station_array,
                role="estimate",
            )

            if maximum_projection_distance is None:
                raise FrameRejection(
                    "no_relevant_estimate_points",
                    "no estimate vertices project into the evaluation range",
                )
            if maximum_projection_distance > max_projection_distance_m:
                raise FrameRejection(
                    "projection_distance_too_large",
                    f"maximum projection distance {maximum_projection_distance:.3f} m "
                    f"exceeds {max_projection_distance_m:.3f} m",
                )

            residual = residual_vector(
                reference_path,
                estimate_path,
                station_array,
            )
            maximum_absolute_residual = float(np.max(np.abs(residual)))
            if maximum_absolute_residual > max_absolute_residual_m:
                raise FrameRejection(
                    "absolute_residual_too_large",
                    "residual magnitude exceeds the configured plausibility limit",
                )
        except FrameRejection as error:
            rejection_reason = error.reason
            rejection_counts[error.reason] += 1
        except (ValueError, FloatingPointError):
            rejection_reason = "invalid_geometry"
            rejection_counts["invalid_geometry"] += 1

        candidate_records.extend(
            candidate_segment_records(
                pair.reference,
                recording_id=recording_id,
                pair_index=pair_index,
                role="reference",
                selected=selected_reference,
            )
        )
        candidate_records.extend(
            candidate_segment_records(
                pair.estimate,
                recording_id=recording_id,
                pair_index=pair_index,
                role="estimate",
                selected=selected_estimate,
            )
        )

        accepted = rejection_reason == ""
        pair_audit_records.append(
            PairAuditRecord(
                recording_id=recording_id,
                pair_index=pair_index,
                synchronization_basis=time_basis,
                synchronization_delta_ms=pair.delta_ns / 1_000_000.0,
                log_time_delta_ms=pair.log_delta_ns / 1_000_000.0,
                source_time_delta_ms=_source_delta_ms(pair),
                reference_segment_id=(
                    None
                    if selected_reference is None
                    else selected_reference.segment.segment_id
                ),
                estimate_segment_id=(
                    None
                    if selected_estimate is None
                    else selected_estimate.segment.segment_id
                ),
                reference_selection=(
                    "" if selected_reference is None else selected_reference.method
                ),
                estimate_selection=(
                    "" if selected_estimate is None else selected_estimate.method
                ),
                reference_forward_coverage_m=reference_forward_coverage,
                estimate_forward_coverage_m=estimate_forward_coverage,
                common_forward_coverage_m=common_forward_coverage,
                estimate_points_retained_fraction=retained_fraction,
                maximum_projection_distance_m=maximum_projection_distance,
                maximum_absolute_residual_m=maximum_absolute_residual,
                accepted=accepted,
                rejection_reason=rejection_reason,
            )
        )

        association_example = LaneAssociationExample(
            pair_index=pair_index,
            reference_segments=pair.reference.segments,
            estimate_segments=pair.estimate.segments,
            selected_reference_segment_id=(
                None
                if selected_reference is None
                else selected_reference.segment.segment_id
            ),
            selected_estimate_segment_id=(
                None
                if selected_estimate is None
                else selected_estimate.segment.segment_id
            ),
            source_time_delta_ms=_source_delta_ms(pair),
            accepted=accepted,
            rejection_reason=rejection_reason,
        )
        association_target = (
            accepted_association_examples if accepted else rejected_association_examples
        )
        if len(association_target) < n_association_examples:
            association_target.append(association_example)

        if not accepted:
            continue

        assert (
            selected_reference is not None
            and selected_estimate is not None
            and reference_path is not None
            and estimate_path is not None
            and residual is not None
            and retained_fraction is not None
            and maximum_projection_distance is not None
        )
        residual_rows.append(residual)
        records.append(
            ResidualRecord(
                recording_id=recording_id,
                reference_log_time_ns=pair.reference.log_time_ns,
                estimate_log_time_ns=pair.estimate.log_time_ns,
                reference_source_time_ns=pair.reference.source_time_ns,
                estimate_source_time_ns=pair.estimate.source_time_ns,
                synchronization_delta_ms=pair.delta_ns / 1_000_000.0,
                log_time_delta_ms=pair.log_delta_ns / 1_000_000.0,
                source_time_delta_ms=_source_delta_ms(pair),
                reference_segment_id=selected_reference.segment.segment_id,
                estimate_segment_id=selected_estimate.segment.segment_id,
                reference_geometry_source=(
                    selected_reference.segment.geometry_source
                ),
                estimate_geometry_source=(
                    selected_estimate.segment.geometry_source
                ),
                reference_selection=selected_reference.method,
                estimate_selection=selected_estimate.method,
                estimate_points_retained_fraction=retained_fraction,
                maximum_projection_distance_m=maximum_projection_distance,
            )
        )
        if len(examples) < n_examples:
            examples.append(
                PathPairExample(
                    reference=reference_path,
                    estimate=estimate_path,
                    residual=residual.copy(),
                )
            )

    report = ExtractionReport(
        reference_frames=len(reference_frames),
        estimate_frames=len(estimate_frames),
        synchronized_pairs=len(synchronization.pairs),
        pairs_considered=considered,
        unconsidered_synchronized_pairs=len(synchronization.pairs) - considered,
        accepted_pairs=len(residual_rows),
        unmatched_reference_frames=synchronization.unmatched_reference,
        unmatched_estimate_frames=synchronization.unmatched_estimate,
        time_basis=time_basis,
        max_time_delta_ms=max_delta_ms,
        rejection_counts=tuple(sorted(rejection_counts.items())),
    )

    accepted_limit = (n_association_examples + 1) // 2
    rejected_limit = n_association_examples - accepted_limit
    association_examples = (
        accepted_association_examples[:accepted_limit]
        + rejected_association_examples[:rejected_limit]
    )
    if len(association_examples) < n_association_examples:
        unused_accepted = accepted_association_examples[accepted_limit:]
        unused_rejected = rejected_association_examples[rejected_limit:]
        association_examples.extend(
            (unused_accepted + unused_rejected)[
                : n_association_examples - len(association_examples)
            ]
        )

    return ResidualDataset(
        stations=station_array,
        residuals=(
            np.vstack(residual_rows)
            if residual_rows
            else np.empty((0, len(station_array)), dtype=np.float64)
        ),
        records=tuple(records),
        examples=tuple(examples),
        candidate_records=tuple(candidate_records),
        pair_audit_records=tuple(pair_audit_records),
        association_examples=tuple(association_examples),
        audit_horizons_m=tuple(float(value) for value in audit_horizons),
        report=report,
        reference_topic=reference_topic,
        estimate_topic=estimate_topic,
    )


def build_residual_dataset_from_mcap(
    path: str | Path,
    *,
    assume_same_frame: bool,
    reference_topic: str = DEFAULT_REFERENCE_TOPIC,
    estimate_topic: str = DEFAULT_ESTIMATE_TOPIC,
    stations: ArrayLike = DEFAULT_STATIONS,
    max_delta_ms: float = 50.0,
    time_basis: Literal["log", "source"] = "source",
    max_samples: int | None = 100,
    max_projection_distance_m: float = 5.0,
    max_absolute_residual_m: float = 5.0,
    audit_horizons_m: Sequence[float] = DEFAULT_AUDIT_HORIZONS,
    n_association_examples: int = 6,
) -> ResidualDataset:
    """Decode one MCAP and create residuals for two same-frame road topics."""

    if not assume_same_frame:
        raise ValueError(
            "same-frame use has not been confirmed; pass assume_same_frame=True "
            "only after verifying both road topics use the same coordinate frame"
        )
    source = Path(path)
    grouped = load_road_frames(
        source,
        topics=(reference_topic, estimate_topic),
    )
    if not grouped[reference_topic]:
        raise FrameRejection(
            "reference_topic_empty",
            f'no decodable messages found on "{reference_topic}"',
        )
    if not grouped[estimate_topic]:
        raise FrameRejection(
            "estimate_topic_empty",
            f'no decodable messages found on "{estimate_topic}"',
        )
    return build_residual_dataset(
        grouped[reference_topic],
        grouped[estimate_topic],
        recording_id=source.stem,
        stations=stations,
        reference_topic=reference_topic,
        estimate_topic=estimate_topic,
        max_delta_ms=max_delta_ms,
        time_basis=time_basis,
        max_samples=max_samples,
        max_projection_distance_m=max_projection_distance_m,
        max_absolute_residual_m=max_absolute_residual_m,
        audit_horizons_m=audit_horizons_m,
        n_association_examples=n_association_examples,
    )


def save_residual_dataset(
    dataset: ResidualDataset,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Save derived residuals, provenance, and an auditable JSON summary."""

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)

    residual_path = destination / "residual_dataset.npz"
    np.savez_compressed(
        residual_path,
        stations=dataset.stations,
        residuals=dataset.residuals,
        reference_log_time_ns=np.asarray(
            [record.reference_log_time_ns for record in dataset.records],
            dtype=np.int64,
        ),
        estimate_log_time_ns=np.asarray(
            [record.estimate_log_time_ns for record in dataset.records],
            dtype=np.int64,
        ),
        reference_source_time_ns=np.asarray(
            [
                -1
                if record.reference_source_time_ns is None
                else record.reference_source_time_ns
                for record in dataset.records
            ],
            dtype=np.int64,
        ),
        estimate_source_time_ns=np.asarray(
            [
                -1
                if record.estimate_source_time_ns is None
                else record.estimate_source_time_ns
                for record in dataset.records
            ],
            dtype=np.int64,
        ),
        synchronization_delta_ms=np.asarray(
            [record.synchronization_delta_ms for record in dataset.records],
            dtype=np.float64,
        ),
        log_time_delta_ms=np.asarray(
            [record.log_time_delta_ms for record in dataset.records],
            dtype=np.float64,
        ),
        source_time_delta_ms=np.asarray(
            [
                np.nan
                if record.source_time_delta_ms is None
                else record.source_time_delta_ms
                for record in dataset.records
            ],
            dtype=np.float64,
        ),
    )

    records_path = destination / "records.csv"
    field_names = list(ResidualRecord.__dataclass_fields__)
    with records_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names)
        writer.writeheader()
        for record in dataset.records:
            writer.writerow(
                {field_name: getattr(record, field_name) for field_name in field_names}
            )

    pair_audit_path = destination / "pair_audit.csv"
    pair_field_names = list(PairAuditRecord.__dataclass_fields__)
    with pair_audit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=pair_field_names)
        writer.writeheader()
        for record in dataset.pair_audit_records:
            writer.writerow(
                {
                    field_name: getattr(record, field_name)
                    for field_name in pair_field_names
                }
            )

    candidate_path = destination / "candidate_segments.csv"
    candidate_field_names = list(CandidateSegmentRecord.__dataclass_fields__)
    with candidate_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=candidate_field_names)
        writer.writeheader()
        for record in dataset.candidate_records:
            writer.writerow(
                {
                    field_name: getattr(record, field_name)
                    for field_name in candidate_field_names
                }
            )

    projection_distances = np.asarray(
        [record.maximum_projection_distance_m for record in dataset.records],
        dtype=np.float64,
    )
    reference_selection_counts = Counter(
        record.reference_selection for record in dataset.records
    )
    estimate_selection_counts = Counter(
        record.estimate_selection for record in dataset.records
    )
    reference_geometry_source_counts = Counter(
        record.reference_geometry_source for record in dataset.records
    )
    estimate_geometry_source_counts = Counter(
        record.estimate_geometry_source for record in dataset.records
    )
    all_reference_selection_counts = Counter(
        record.reference_selection
        for record in dataset.pair_audit_records
        if record.reference_selection
    )
    all_estimate_selection_counts = Counter(
        record.estimate_selection
        for record in dataset.pair_audit_records
        if record.estimate_selection
    )
    selected_segment_pairs = Counter(
        f"{record.reference_segment_id}->{record.estimate_segment_id}"
        for record in dataset.pair_audit_records
        if record.reference_segment_id is not None
        and record.estimate_segment_id is not None
    )

    def delta_summary(values: Sequence[float | None]) -> dict[str, float | int] | None:
        array = np.asarray(
            [value for value in values if value is not None],
            dtype=np.float64,
        )
        array = array[np.isfinite(array)]
        if len(array) == 0:
            return None
        return {
            "count": int(len(array)),
            "median_signed": float(np.median(array)),
            "median_absolute": float(np.median(np.abs(array))),
            "maximum_absolute": float(np.max(np.abs(array))),
        }

    horizon_counts = dataset.horizon_coverage_counts()
    horizon_denominator = len(dataset.pair_audit_records)
    horizon_summary = {
        f"{horizon:g}": {
            "geometric_pair_count": count,
            "fraction_of_considered_pairs": (
                count / horizon_denominator if horizon_denominator else 0.0
            ),
        }
        for horizon, count in horizon_counts.items()
    }
    mean_residual = (
        np.mean(dataset.residuals, axis=0).tolist()
        if len(dataset.residuals)
        else None
    )
    standard_deviation = (
        np.std(dataset.residuals, axis=0).tolist()
        if len(dataset.residuals)
        else None
    )
    summary = {
        "interpretation": (
            "sensor-based versus map-based lane-path discrepancy; "
            "map-based data is a surrogate reference, not confirmed ground truth"
        ),
        "reference_topic": dataset.reference_topic,
        "estimate_topic": dataset.estimate_topic,
        "stations_m": dataset.stations.tolist(),
        "matrix_shape": list(dataset.residuals.shape),
        "mean_residual_m": mean_residual,
        "standard_deviation_m": standard_deviation,
        "accepted_fraction_of_considered_pairs": (
            dataset.report.accepted_pairs / dataset.report.pairs_considered
            if dataset.report.pairs_considered
            else 0.0
        ),
        "synchronization": {
            "pairing_basis": dataset.report.time_basis,
            "basis_delta_ms": delta_summary(
                [
                    record.synchronization_delta_ms
                    for record in dataset.pair_audit_records
                ]
            ),
            "log_time_delta_ms": delta_summary(
                [record.log_time_delta_ms for record in dataset.pair_audit_records]
            ),
            "source_time_delta_ms": delta_summary(
                [
                    record.source_time_delta_ms
                    for record in dataset.pair_audit_records
                ]
            ),
        },
        "maximum_projection_distance_m": (
            {
                "median": float(np.median(projection_distances)),
                "maximum": float(np.max(projection_distances)),
            }
            if len(projection_distances)
            else None
        ),
        "reference_selection_counts": dict(reference_selection_counts),
        "estimate_selection_counts": dict(estimate_selection_counts),
        "all_pair_reference_selection_counts": dict(
            all_reference_selection_counts
        ),
        "all_pair_estimate_selection_counts": dict(all_estimate_selection_counts),
        "selected_segment_pair_counts": dict(selected_segment_pairs),
        "reference_geometry_source_counts": dict(
            reference_geometry_source_counts
        ),
        "estimate_geometry_source_counts": dict(
            estimate_geometry_source_counts
        ),
        "horizon_coverage": {
            "definition": (
                "selected reference and estimate paths geometrically cover the "
                "horizon; this is not a correctness or plausibility test"
            ),
            "considered_pairs": horizon_denominator,
            "horizons_m": horizon_summary,
        },
        "extraction_report": dataset.report.to_dict(),
    }
    summary_path = destination / "summary.json"
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")

    return {
        "residuals": residual_path,
        "records": records_path,
        "pair_audit": pair_audit_path,
        "candidate_segments": candidate_path,
        "summary": summary_path,
    }
