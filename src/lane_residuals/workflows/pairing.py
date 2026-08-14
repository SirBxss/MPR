"""Command-line audit for pairing EDP with road-lane-map-based geometry."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ..domain.geometry_validation import (
    GeometryValidationError,
    estimated_frame_from_message,
    generate_spline_curve,
)
from ..io.mcap import (
    McapDependencyError,
    RoadMessageError,
    iter_decoded_mcap_messages,
    road_frame_from_message,
    source_time_ns_from_message,
)
from ..domain.pairing import (
    DEFAULT_PAIRING_STATIONS_M,
    DiagnosticPathDisagreement,
    EgoRelativePath,
    OrderedEgoLane,
    compare_ego_relative_paths,
    ego_relative_path_from_spline,
    evenly_spaced_indices,
    mutual_nearest_timestamp_pairs,
    ordered_ego_lane_from_road_frame,
    origin_alignment_metrics,
    sample_ego_relative_path,
)
from ..domain.path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)
from ..visualization.pairing import (
    PairPlot as _PairPlot,
    plot_lateral_zoom as _plot_lateral_zoom,
    plot_pairs as _plot_pairs,
    plot_station_profiles as _plot_station_profiles,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_MAP_TOPIC = "/adp/road_lane_map_based"
DEFAULT_MAP_SCHEMA = "Adp.Perception.Road"


@dataclass(frozen=True)
class _TimedPath:
    message_index: int
    source_time_ns: int | None
    log_time_ns: int
    publish_time_ns: int
    geometry_state: str
    failure_code: str | None = None
    path: EgoRelativePath | None = field(default=None, repr=False)
    ordered_map_lane: OrderedEgoLane | None = field(default=None, repr=False)

    @property
    def geometry_ready(self) -> bool:
        return self.geometry_state == "geometry_ready" and self.path is not None


def _validate_arguments(arguments: argparse.Namespace) -> tuple[float, ...]:
    if arguments.max_pairs < 1:
        raise ValueError("max-pairs must be positive")
    if arguments.max_step_m <= 0.0 or not math.isfinite(arguments.max_step_m):
        raise ValueError("max-step-m must be finite and positive")
    if arguments.map_max_segments < 1:
        raise ValueError("map-max-segments must be positive")
    if (
        arguments.map_max_junction_gap_m < 0.0
        or not math.isfinite(arguments.map_max_junction_gap_m)
    ):
        raise ValueError("map-max-junction-gap-m must be finite and nonnegative")
    if (
        arguments.map_max_junction_heading_deg < 0.0
        or arguments.map_max_junction_heading_deg > 180.0
        or not math.isfinite(arguments.map_max_junction_heading_deg)
    ):
        raise ValueError(
            "map-max-junction-heading-deg must be finite and within [0, 180]"
        )
    if arguments.maximum_pair_delta_ms is not None and (
        arguments.maximum_pair_delta_ms < 0.0
        or not math.isfinite(arguments.maximum_pair_delta_ms)
    ):
        raise ValueError("maximum-pair-delta-ms must be finite and nonnegative")
    stations = np.asarray(arguments.stations_m, dtype=np.float64)
    if (
        stations.ndim != 1
        or len(stations) < 2
        or not np.all(np.isfinite(stations))
        or stations[0] < 0.0
        or not np.all(np.diff(stations) > 0.0)
    ):
        raise ValueError(
            "stations-m must be finite, nonnegative, and strictly increasing"
        )
    return tuple(float(value) for value in stations)


def _decode_paths(
    path: Path,
    *,
    estimate_topic: str,
    map_topic: str,
    max_step_m: float,
    stations_m: Sequence[float],
    map_max_segments: int = 16,
    map_max_junction_gap_m: float = 1.0,
    map_max_junction_heading_rad: float = math.radians(30.0),
) -> tuple[list[_TimedPath], list[_TimedPath], Counter[str], dict[str, int]]:
    """Decode every topic message before any temporal association is attempted."""

    estimates: list[_TimedPath] = []
    references: list[_TimedPath] = []
    failures: Counter[str] = Counter()
    counts = {"estimate_messages": 0, "map_messages": 0}
    iterator = iter_decoded_mcap_messages(
        path,
        topics=(estimate_topic, map_topic),
        include_ros1=False,
    )
    for schema, channel, message, decoded in iterator:
        topic = str(getattr(channel, "topic", ""))
        schema_name = str(getattr(schema, "name", ""))
        encoding = str(getattr(channel, "message_encoding", "")).lower()
        log_time_ns = int(getattr(message, "log_time", 0))
        publish_time_ns = int(getattr(message, "publish_time", 0))
        source_time_ns = source_time_ns_from_message(decoded)
        if topic == estimate_topic:
            message_index = counts["estimate_messages"]
            counts["estimate_messages"] += 1
            estimate_path: EgoRelativePath | None = None
            failure_code: str | None = None
            if (
                schema_name != DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA
                or encoding != "protobuf"
            ):
                failure_code = "estimate__schema_or_encoding_mismatch"
            else:
                try:
                    frame = estimated_frame_from_message(
                        decoded,
                        message_index=message_index,
                        log_time_ns=log_time_ns,
                        publish_time_ns=publish_time_ns,
                    )
                    source_time_ns = frame.source_time_ns
                    if not frame.candidate_ready or frame.candidate is None:
                        failure_code = f"estimate__{frame.conversion_state}"
                    else:
                        curve = generate_spline_curve(
                            frame.candidate,
                            meaning="curvature_rate",
                            anchor_policy="anchor_zero",
                            max_step_m=max_step_m,
                            extra_stations=stations_m,
                        )
                        estimate_path = ego_relative_path_from_spline(curve)
                except GeometryValidationError as error:
                    failure_code = f"estimate__{error.code}"
            if failure_code is not None:
                failures[failure_code] += 1
            estimates.append(
                _TimedPath(
                    message_index=message_index,
                    source_time_ns=source_time_ns,
                    log_time_ns=log_time_ns,
                    publish_time_ns=publish_time_ns,
                    geometry_state=(
                        "geometry_ready"
                        if estimate_path is not None
                        else "geometry_not_ready"
                    ),
                    failure_code=failure_code,
                    path=estimate_path,
                )
            )
        elif topic == map_topic:
            message_index = counts["map_messages"]
            counts["map_messages"] += 1
            reference_path: EgoRelativePath | None = None
            ordered_map_lane: OrderedEgoLane | None = None
            failure_code = None
            if schema_name != DEFAULT_MAP_SCHEMA or encoding != "protobuf":
                failure_code = "map__schema_or_encoding_mismatch"
            else:
                try:
                    frame = road_frame_from_message(
                        decoded,
                        topic=topic,
                        schema_name=schema_name,
                        log_time_ns=log_time_ns,
                        publish_time_ns=publish_time_ns,
                        sequence=message_index,
                    )
                    source_time_ns = frame.source_time_ns
                    ordered_map_lane = ordered_ego_lane_from_road_frame(
                        frame,
                        required_forward_m=max(stations_m),
                        max_segments=map_max_segments,
                        max_junction_gap_m=map_max_junction_gap_m,
                        max_junction_heading_delta_rad=(
                            map_max_junction_heading_rad
                        ),
                    )
                    reference_path = ordered_map_lane.path
                except (GeometryValidationError, RoadMessageError) as error:
                    failure_code = (
                        f"map__{getattr(error, 'code', 'road_message_invalid')}"
                    )
            if failure_code is not None:
                failures[failure_code] += 1
            references.append(
                _TimedPath(
                    message_index=message_index,
                    source_time_ns=source_time_ns,
                    log_time_ns=log_time_ns,
                    publish_time_ns=publish_time_ns,
                    geometry_state=(
                        "geometry_ready"
                        if reference_path is not None
                        else "geometry_not_ready"
                    ),
                    failure_code=failure_code,
                    path=reference_path,
                    ordered_map_lane=ordered_map_lane,
                )
            )
    return estimates, references, failures, counts


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _median_or_none(values: Sequence[float]) -> float | None:
    return None if not values else float(np.median(np.asarray(values, dtype=np.float64)))


def run_pairing_audit(
    arguments: argparse.Namespace,
    *,
    stations_m: Sequence[float],
) -> dict[str, Any]:
    estimates, references, failures, counts = _decode_paths(
        arguments.mcap,
        estimate_topic=arguments.estimate_topic,
        map_topic=arguments.map_topic,
        max_step_m=arguments.max_step_m,
        stations_m=stations_m,
        map_max_segments=getattr(arguments, "map_max_segments", 16),
        map_max_junction_gap_m=getattr(
            arguments,
            "map_max_junction_gap_m",
            1.0,
        ),
        map_max_junction_heading_rad=math.radians(
            getattr(arguments, "map_max_junction_heading_deg", 30.0)
        ),
    )
    maximum_delta_ns = (
        None
        if arguments.maximum_pair_delta_ms is None
        else int(round(arguments.maximum_pair_delta_ms * 1_000_000.0))
    )
    timestamp_audit = mutual_nearest_timestamp_pairs(
        [item.source_time_ns for item in estimates],
        [item.source_time_ns for item in references],
        maximum_delta_ns=maximum_delta_ns,
    )

    accepted_by_estimate = {
        pair.first_position: pair for pair in timestamp_audit.pairs
    }
    accepted_by_map = {
        pair.second_position: pair for pair in timestamp_audit.pairs
    }
    rejected_by_estimate = {
        pair.first_position: pair for pair in timestamp_audit.rejected_by_gate
    }
    rejected_by_map = {
        pair.second_position: pair for pair in timestamp_audit.rejected_by_gate
    }

    def inventory_row(
        *,
        role: str,
        position: int,
        record: _TimedPath,
    ) -> dict[str, Any]:
        if role == "estimate":
            accepted = accepted_by_estimate.get(position)
            rejected = rejected_by_estimate.get(position)
            ambiguous = position in timestamp_audit.ambiguous_first_positions
            missing_time = position in timestamp_audit.missing_time_first_positions
            counterpart = (
                references[accepted.second_position]
                if accepted is not None
                else references[rejected.second_position]
                if rejected is not None
                else None
            )
            delta_ns = (
                accepted.delta_ns
                if accepted is not None
                else rejected.delta_ns
                if rejected is not None
                else None
            )
        else:
            accepted = accepted_by_map.get(position)
            rejected = rejected_by_map.get(position)
            ambiguous = position in timestamp_audit.ambiguous_second_positions
            missing_time = position in timestamp_audit.missing_time_second_positions
            counterpart = (
                estimates[accepted.first_position]
                if accepted is not None
                else estimates[rejected.first_position]
                if rejected is not None
                else None
            )
            delta_ns = (
                -accepted.delta_ns
                if accepted is not None
                else -rejected.delta_ns
                if rejected is not None
                else None
            )

        ordered_lane = record.ordered_map_lane
        if accepted is not None:
            temporal_state = "paired_unique_mutual_nearest"
        elif rejected is not None:
            temporal_state = "unmatched_timestamp_gate"
        elif missing_time:
            temporal_state = "unmatched_source_time_missing"
        elif ambiguous:
            temporal_state = "unmatched_nearest_tie"
        else:
            temporal_state = "unmatched_non_mutual_nearest"
        return {
            "topic_role": role,
            "message_index": record.message_index,
            "source_time_ns_private": record.source_time_ns,
            "log_time_ns_private": record.log_time_ns,
            "publish_time_ns_private": record.publish_time_ns,
            "geometry_state": record.geometry_state,
            "geometry_failure_code": record.failure_code,
            "temporal_state": temporal_state,
            "counterpart_message_index": (
                None if counterpart is None else counterpart.message_index
            ),
            "counterpart_delta_ms": (
                None if delta_ns is None else delta_ns / 1e6
            ),
            "map_chain_segment_count": (
                None if ordered_lane is None else ordered_lane.segment_count
            ),
            "map_chain_segment_indices": (
                None
                if ordered_lane is None
                else ";".join(str(value) for value in ordered_lane.segment_indices)
            ),
            "map_chain_segment_ids": (
                None
                if ordered_lane is None
                else ";".join(str(value) for value in ordered_lane.segment_ids)
            ),
            "map_chain_termination_reason": (
                None if ordered_lane is None else ordered_lane.termination_reason
            ),
            "map_chain_required_coverage_reached": (
                None
                if ordered_lane is None
                else ordered_lane.required_forward_coverage_reached
            ),
            "map_chain_max_junction_gap_m": (
                None if ordered_lane is None else ordered_lane.max_junction_gap_m
            ),
            "map_chain_max_junction_heading_delta_rad": (
                None
                if ordered_lane is None
                else ordered_lane.max_junction_heading_delta_rad
            ),
            "map_chain_all_links_reciprocal": (
                None
                if ordered_lane is None or not ordered_lane.reciprocal_predecessor_links
                else all(ordered_lane.reciprocal_predecessor_links)
            ),
        }

    inventory_rows = [
        inventory_row(role="estimate", position=position, record=record)
        for position, record in enumerate(estimates)
    ] + [
        inventory_row(role="map", position=position, record=record)
        for position, record in enumerate(references)
    ]
    chain_rows = []
    for record in references:
        lane = record.ordered_map_lane
        chain_rows.append(
            {
                "map_message_index": record.message_index,
                "map_source_time_ns_private": record.source_time_ns,
                "geometry_state": record.geometry_state,
                "geometry_failure_code": record.failure_code,
                "segment_count": None if lane is None else lane.segment_count,
                "segment_indices": (
                    None
                    if lane is None
                    else ";".join(str(value) for value in lane.segment_indices)
                ),
                "segment_ids": (
                    None
                    if lane is None
                    else ";".join(str(value) for value in lane.segment_ids)
                ),
                "termination_reason": (
                    None if lane is None else lane.termination_reason
                ),
                "required_forward_m": (
                    None if lane is None else lane.required_forward_m
                ),
                "required_forward_coverage_reached": (
                    None
                    if lane is None
                    else lane.required_forward_coverage_reached
                ),
                "actual_forward_coverage_m": (
                    None if lane is None else lane.path.forward_coverage_m
                ),
                "actual_backward_coverage_m": (
                    None if lane is None else lane.path.backward_coverage_m
                ),
                "junction_gaps_m": (
                    None
                    if lane is None
                    else ";".join(f"{value:.9g}" for value in lane.junction_gaps_m)
                ),
                "junction_heading_deltas_rad": (
                    None
                    if lane is None
                    else ";".join(
                        f"{value:.9g}"
                        for value in lane.junction_heading_deltas_rad
                    )
                ),
                "reciprocal_predecessor_links": (
                    None
                    if lane is None
                    else ";".join(
                        "true" if value else "false"
                        for value in lane.reciprocal_predecessor_links
                    )
                ),
            }
        )
    pair_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    plot_candidates: list[_PairPlot] = []
    pair_deltas: list[float] = []
    footpoint_separations: list[float] = []
    heading_deltas: list[float] = []
    lateral_rms_values: list[float] = []
    primary_lateral_rms_values: list[float] = []
    far_lateral_rms_values: list[float] = []
    primary_stations = tuple(value for value in stations_m if value <= 60.0 + 1e-9)
    if len(primary_stations) < 2:
        primary_stations = tuple(stations_m)
    far_stations = tuple(value for value in stations_m if value > 60.0 + 1e-9)
    full_ready_pair_count = 0
    primary_ready_pair_count = 0
    for pair_index, timestamp_pair in enumerate(timestamp_audit.pairs):
        estimate = estimates[timestamp_pair.first_position]
        reference = references[timestamp_pair.second_position]
        delta_ms = timestamp_pair.delta_ns / 1e6
        alignment = {
            "estimate_origin_distance_m": None,
            "reference_origin_distance_m": None,
            "footpoint_separation_m": None,
            "footpoint_dx_m": None,
            "footpoint_dy_m": None,
            "origin_heading_delta_rad": None,
        }
        pair_state: str
        failure_code: str | None
        disagreement: DiagnosticPathDisagreement | None = None
        available_disagreement: DiagnosticPathDisagreement | None = None
        primary_disagreement: DiagnosticPathDisagreement | None = None
        far_lateral_rms_m: float | None = None
        available_stations: tuple[float, ...] = ()
        if not estimate.geometry_ready and not reference.geometry_ready:
            pair_state = "both_geometries_not_ready"
            failure_code = "both_geometries_not_ready"
        elif not estimate.geometry_ready:
            pair_state = "estimate_geometry_not_ready"
            failure_code = estimate.failure_code
        elif not reference.geometry_ready:
            pair_state = "map_geometry_not_ready"
            failure_code = reference.failure_code
        else:
            assert estimate.path is not None
            assert reference.path is not None
            alignment = origin_alignment_metrics(estimate.path, reference.path)
            common_lower = max(
                float(estimate.path.stations_m[0]),
                float(reference.path.stations_m[0]),
            )
            common_upper = min(
                estimate.path.forward_coverage_m,
                reference.path.forward_coverage_m,
            )
            available_stations = tuple(
                value
                for value in stations_m
                if common_lower - 1e-9 <= value <= common_upper + 1e-9
            )
            try:
                if len(available_stations) >= 2:
                    available_disagreement = compare_ego_relative_paths(
                        estimate.path,
                        reference.path,
                        stations_m=available_stations,
                    )
                if all(value in available_stations for value in primary_stations):
                    primary_disagreement = compare_ego_relative_paths(
                        estimate.path,
                        reference.path,
                        stations_m=primary_stations,
                    )
                if len(available_stations) == len(stations_m):
                    disagreement = available_disagreement
                if (
                    available_disagreement is not None
                    and len(far_stations) >= 2
                    and all(value in available_stations for value in far_stations)
                ):
                    far_mask = available_disagreement.stations_m > 60.0 + 1e-9
                    far_lateral_rms_m = float(
                        np.sqrt(
                            np.mean(
                                np.square(
                                    available_disagreement.lateral_m[far_mask]
                                )
                            )
                        )
                    )
            except GeometryValidationError as error:
                pair_state = "geometry_not_ready"
                failure_code = error.code
            else:
                if disagreement is not None:
                    pair_state = "diagnostic_ready_uncompensated"
                    failure_code = None
                    full_ready_pair_count += 1
                elif primary_disagreement is not None:
                    pair_state = "diagnostic_primary_ready_uncompensated"
                    failure_code = "pairing_full_horizon_coverage_incomplete"
                else:
                    pair_state = "geometry_not_ready"
                    failure_code = "pairing_primary_horizon_coverage_incomplete"
                if primary_disagreement is not None:
                    primary_ready_pair_count += 1
        row = {
            "pair_index": pair_index,
            "estimate_message_index": estimate.message_index,
            "map_message_index": reference.message_index,
            "estimate_source_time_ns_private": estimate.source_time_ns,
            "map_source_time_ns_private": reference.source_time_ns,
            "source_delta_ms": delta_ms,
            "absolute_source_delta_ms": abs(delta_ms),
            "timestamp_gate_ms": arguments.maximum_pair_delta_ms,
            "timestamp_gate_passed": (
                None if arguments.maximum_pair_delta_ms is None else True
            ),
            "pair_state": pair_state,
            "failure_code": failure_code,
            "estimate_geometry_state": estimate.geometry_state,
            "estimate_geometry_failure_code": estimate.failure_code,
            "map_geometry_state": reference.geometry_state,
            "map_geometry_failure_code": reference.failure_code,
            "estimate_backward_coverage_m": (
                None if estimate.path is None else estimate.path.backward_coverage_m
            ),
            "estimate_forward_coverage_m": (
                None if estimate.path is None else estimate.path.forward_coverage_m
            ),
            "reference_backward_coverage_m": (
                None if reference.path is None else reference.path.backward_coverage_m
            ),
            "reference_forward_coverage_m": (
                None if reference.path is None else reference.path.forward_coverage_m
            ),
            "estimate_reversed_to_positive_x": (
                None
                if estimate.path is None
                else estimate.path.reversed_to_positive_x
            ),
            "reference_reversed_to_positive_x": (
                None
                if reference.path is None
                else reference.path.reversed_to_positive_x
            ),
            **alignment,
            "diagnostic_lateral_rms_m": (
                None if disagreement is None else disagreement.lateral_rms_m
            ),
            "diagnostic_lateral_max_abs_m": (
                None if disagreement is None else disagreement.lateral_max_abs_m
            ),
            "diagnostic_primary_horizon_max_m": max(primary_stations),
            "diagnostic_primary_lateral_rms_m": (
                None
                if primary_disagreement is None
                else primary_disagreement.lateral_rms_m
            ),
            "diagnostic_far_lateral_rms_m": (
                far_lateral_rms_m
            ),
            "diagnostic_common_max_station_m": (
                None if not available_stations else max(available_stations)
            ),
            "diagnostic_available_lateral_rms_m": (
                None
                if available_disagreement is None
                else available_disagreement.lateral_rms_m
            ),
            "reference_chain_segment_count": (
                None
                if reference.ordered_map_lane is None
                else reference.ordered_map_lane.segment_count
            ),
            "reference_chain_segment_indices": (
                None
                if reference.ordered_map_lane is None
                else ";".join(
                    str(value)
                    for value in reference.ordered_map_lane.segment_indices
                )
            ),
            "reference_chain_segment_ids": (
                None
                if reference.ordered_map_lane is None
                else ";".join(
                    str(value) for value in reference.ordered_map_lane.segment_ids
                )
            ),
            "reference_chain_termination_reason": (
                None
                if reference.ordered_map_lane is None
                else reference.ordered_map_lane.termination_reason
            ),
            "reference_chain_required_coverage_reached": (
                None
                if reference.ordered_map_lane is None
                else reference.ordered_map_lane.required_forward_coverage_reached
            ),
            "reference_chain_max_junction_gap_m": (
                None
                if reference.ordered_map_lane is None
                else reference.ordered_map_lane.max_junction_gap_m
            ),
            "reference_chain_max_junction_heading_delta_rad": (
                None
                if reference.ordered_map_lane is None
                else reference.ordered_map_lane.max_junction_heading_delta_rad
            ),
        }
        pair_rows.append(row)
        pair_deltas.append(abs(delta_ms))
        if disagreement is not None:
            footpoint_separations.append(float(alignment["footpoint_separation_m"]))
            heading_deltas.append(abs(float(alignment["origin_heading_delta_rad"])))
            lateral_rms_values.append(disagreement.lateral_rms_m)
        if primary_disagreement is not None:
            primary_lateral_rms_values.append(primary_disagreement.lateral_rms_m)
        if far_lateral_rms_m is not None:
            far_lateral_rms_values.append(far_lateral_rms_m)
        if available_disagreement is not None:
            assert estimate.path is not None
            assert reference.path is not None
            estimate_sampled = sample_ego_relative_path(
                estimate.path,
                available_stations,
            )
            reference_sampled = sample_ego_relative_path(
                reference.path,
                available_stations,
            )
            for station_index, station in enumerate(
                available_disagreement.stations_m
            ):
                station_rows.append(
                    {
                        "pair_index": pair_index,
                        "station_m": float(station),
                        "estimate_x_m": float(estimate_sampled.x_m[station_index]),
                        "estimate_y_m": float(estimate_sampled.y_m[station_index]),
                        "reference_x_m": float(reference_sampled.x_m[station_index]),
                        "reference_y_m": float(reference_sampled.y_m[station_index]),
                        "diagnostic_lateral_m": float(
                            available_disagreement.lateral_m[station_index]
                        ),
                        "diagnostic_along_track_m": float(
                            available_disagreement.along_track_m[station_index]
                        ),
                        "diagnostic_heading_rad": float(
                            available_disagreement.heading_rad[station_index]
                        ),
                        "full_requested_horizon_available": disagreement is not None,
                        "primary_horizon_available": primary_disagreement is not None,
                    }
                )
        if primary_disagreement is not None:
            assert estimate.path is not None
            assert reference.path is not None
            plot_candidates.append(
                _PairPlot(
                    title=(
                        f"E{estimate.message_index} / M{reference.message_index}; "
                        f"Δt={delta_ms:.2f} ms"
                    ),
                    estimate=estimate.path,
                    reference=reference.path,
                    stations_m=(
                        tuple(stations_m)
                        if disagreement is not None
                        else tuple(primary_stations)
                    ),
                )
            )

    plots = [
        plot_candidates[index]
        for index in evenly_spaced_indices(
            len(plot_candidates),
            arguments.max_pairs,
        )
    ]

    output = arguments.output_directory
    _write_csv(
        output / "message_inventory.csv",
        (
            "topic_role",
            "message_index",
            "source_time_ns_private",
            "log_time_ns_private",
            "publish_time_ns_private",
            "geometry_state",
            "geometry_failure_code",
            "temporal_state",
            "counterpart_message_index",
            "counterpart_delta_ms",
            "map_chain_segment_count",
            "map_chain_segment_indices",
            "map_chain_segment_ids",
            "map_chain_termination_reason",
            "map_chain_required_coverage_reached",
            "map_chain_max_junction_gap_m",
            "map_chain_max_junction_heading_delta_rad",
            "map_chain_all_links_reciprocal",
        ),
        inventory_rows,
    )
    _write_csv(
        output / "rlmb_chain_audit.csv",
        (
            "map_message_index",
            "map_source_time_ns_private",
            "geometry_state",
            "geometry_failure_code",
            "segment_count",
            "segment_indices",
            "segment_ids",
            "termination_reason",
            "required_forward_m",
            "required_forward_coverage_reached",
            "actual_forward_coverage_m",
            "actual_backward_coverage_m",
            "junction_gaps_m",
            "junction_heading_deltas_rad",
            "reciprocal_predecessor_links",
        ),
        chain_rows,
    )
    pair_fields = (
        "pair_index",
        "estimate_message_index",
        "map_message_index",
        "estimate_source_time_ns_private",
        "map_source_time_ns_private",
        "source_delta_ms",
        "absolute_source_delta_ms",
        "timestamp_gate_ms",
        "timestamp_gate_passed",
        "pair_state",
        "failure_code",
        "estimate_geometry_state",
        "estimate_geometry_failure_code",
        "map_geometry_state",
        "map_geometry_failure_code",
        "estimate_backward_coverage_m",
        "estimate_forward_coverage_m",
        "reference_backward_coverage_m",
        "reference_forward_coverage_m",
        "estimate_reversed_to_positive_x",
        "reference_reversed_to_positive_x",
        "estimate_origin_distance_m",
        "reference_origin_distance_m",
        "footpoint_separation_m",
        "footpoint_dx_m",
        "footpoint_dy_m",
        "origin_heading_delta_rad",
        "diagnostic_lateral_rms_m",
        "diagnostic_lateral_max_abs_m",
        "diagnostic_primary_horizon_max_m",
        "diagnostic_primary_lateral_rms_m",
        "diagnostic_far_lateral_rms_m",
        "diagnostic_common_max_station_m",
        "diagnostic_available_lateral_rms_m",
        "reference_chain_segment_count",
        "reference_chain_segment_indices",
        "reference_chain_segment_ids",
        "reference_chain_termination_reason",
        "reference_chain_required_coverage_reached",
        "reference_chain_max_junction_gap_m",
        "reference_chain_max_junction_heading_delta_rad",
    )
    _write_csv(output / "pairing_audit.csv", pair_fields, pair_rows)
    _write_csv(
        output / "diagnostic_disagreement.csv",
        (
            "pair_index",
            "station_m",
            "estimate_x_m",
            "estimate_y_m",
            "reference_x_m",
            "reference_y_m",
            "diagnostic_lateral_m",
            "diagnostic_along_track_m",
            "diagnostic_heading_rad",
            "full_requested_horizon_available",
            "primary_horizon_available",
        ),
        station_rows,
    )
    _plot_pairs(output / "pairing_overlays.png", plots)
    _plot_lateral_zoom(output / "pairing_lateral_zoom.png", plots)
    _plot_station_profiles(output / "diagnostic_station_profiles.png", station_rows)
    ordered_lanes = [
        item.ordered_map_lane
        for item in references
        if item.ordered_map_lane is not None
    ]
    chain_terminations = Counter(
        item.termination_reason for item in ordered_lanes
    )
    summary = {
        "version": "0.4.5",
        "purpose": "estimated_path_vs_map_path_pairing_audit",
        "mcap_filename": arguments.mcap.name,
        "estimate_topic": arguments.estimate_topic,
        "map_topic": arguments.map_topic,
        **counts,
        "ready_estimate_geometry_count": sum(
            record.geometry_ready for record in estimates
        ),
        "ready_map_geometry_count": sum(
            record.geometry_ready for record in references
        ),
        "complete_stream_mutual_nearest_pair_count": len(timestamp_audit.pairs),
        "timestamp_gate_rejected_pair_count": len(
            timestamp_audit.rejected_by_gate
        ),
        "unmatched_estimate_message_count": len(
            timestamp_audit.unmatched_first_positions
        ),
        "unmatched_map_message_count": len(
            timestamp_audit.unmatched_second_positions
        ),
        "missing_estimate_source_time_count": len(
            timestamp_audit.missing_time_first_positions
        ),
        "missing_map_source_time_count": len(
            timestamp_audit.missing_time_second_positions
        ),
        "ambiguous_estimate_nearest_time_count": len(
            timestamp_audit.ambiguous_first_positions
        ),
        "ambiguous_map_nearest_time_count": len(
            timestamp_audit.ambiguous_second_positions
        ),
        "inspected_pair_count": len(pair_rows),
        "plotted_pair_count": len(plots),
        "diagnostic_ready_pair_count": full_ready_pair_count,
        "primary_horizon_ready_pair_count": primary_ready_pair_count,
        "primary_horizon_max_m": max(primary_stations),
        "far_horizon_min_m": (
            None if not far_stations else min(far_stations)
        ),
        "rlmb_ordered_lane_count": len(ordered_lanes),
        "rlmb_multi_segment_lane_count": sum(
            item.segment_count > 1 for item in ordered_lanes
        ),
        "rlmb_required_coverage_reached_count": sum(
            item.required_forward_coverage_reached for item in ordered_lanes
        ),
        "rlmb_chain_termination_counts": dict(sorted(chain_terminations.items())),
        "rlmb_chain_rule": (
            "start at exactly one metadata-confirmed ego drive path; follow only "
            "a unique explicit successor index; validate endpoint gap and tangent "
            "continuity; stop before branches or malformed topology"
        ),
        "rlmb_max_segments": getattr(arguments, "map_max_segments", 16),
        "rlmb_max_junction_gap_m": getattr(
            arguments,
            "map_max_junction_gap_m",
            1.0,
        ),
        "rlmb_max_junction_heading_deg": getattr(
            arguments,
            "map_max_junction_heading_deg",
            30.0,
        ),
        "extraction_failures": dict(sorted(failures.items())),
        "stations_m": list(stations_m),
        "timestamp_pairing_basis": (
            "unique mutual-nearest source timestamps on complete topic streams; "
            "geometry validity is applied only after temporal pairing"
        ),
        "pairing_before_geometry_filtering": True,
        "all_messages_retained_in_inventory": True,
        "estimate_spline_semantics": (
            "curvature_rate is the provisional reconstruction selected from "
            "spline-rollover invariance; official interface semantics remain "
            "unconfirmed"
        ),
        "estimate_spline_reconstruction": "curvature_rate",
        "curvature_change_semantics_confirmed": False,
        "timestamp_gate_ms": arguments.maximum_pair_delta_ms,
        "timestamp_gate_predeclared": arguments.maximum_pair_delta_ms is not None,
        "median_absolute_source_delta_ms": _median_or_none(pair_deltas),
        "median_footpoint_separation_m": _median_or_none(footpoint_separations),
        "median_absolute_origin_heading_delta_rad": _median_or_none(heading_deltas),
        "median_diagnostic_lateral_rms_m": _median_or_none(lateral_rms_values),
        "median_primary_horizon_lateral_rms_m": _median_or_none(
            primary_lateral_rms_values
        ),
        "median_far_horizon_lateral_rms_m": _median_or_none(
            far_lateral_rms_values
        ),
        "coordinate_frame_equivalence_confirmed": False,
        "timestamp_motion_compensation_applied": False,
        "map_signal_role": "pseudo_reference_candidate",
        "diagnostic_disagreement_is_lane_estimation_error": False,
        "generated_final_residual_dataset": False,
        "next_decision": (
            "Aggregate all predeclared recordings with fixed complete H60 and "
            "H100 cohorts before defining any provisional modelling dataset."
        ),
        "confidentiality": "Outputs contain BMW-derived measurements and must remain private.",
    }
    _write_json(output / "pairing_summary.json", summary)
    return summary
