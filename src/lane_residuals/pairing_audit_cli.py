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

from .geometry_validation import (
    GeometryValidationError,
    estimated_frame_from_message,
    generate_spline_curve,
)
from .mcap_io import (
    McapDependencyError,
    RoadMessageError,
    iter_decoded_mcap_messages,
    road_frame_from_message,
    source_time_ns_from_message,
)
from .pairing_audit import (
    DEFAULT_PAIRING_STATIONS_M,
    DiagnosticPathDisagreement,
    EgoRelativePath,
    compare_ego_relative_paths,
    ego_relative_path_from_road_frame,
    ego_relative_path_from_spline,
    evenly_spaced_indices,
    mutual_nearest_timestamp_pairs,
    origin_alignment_metrics,
    sample_ego_relative_path,
)
from .path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
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

    @property
    def geometry_ready(self) -> bool:
        return self.geometry_state == "geometry_ready" and self.path is not None


@dataclass(frozen=True)
class _PairPlot:
    title: str
    estimate: EgoRelativePath = field(repr=False)
    reference: EgoRelativePath = field(repr=False)
    stations_m: tuple[float, ...]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit temporal and geometric pairing between EstimatedDrivePaths and "
            "road_lane_map_based without exporting thesis residual labels."
        )
    )
    parser.add_argument("mcap", type=Path, help="one MCAP file to inspect")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/pairing_audit"),
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=20,
        help="maximum number of evenly distributed diagnostic-ready pairs to plot",
    )
    parser.add_argument(
        "--maximum-pair-delta-ms",
        type=float,
        default=None,
        help=(
            "optional predeclared timestamp gate; omitted by default because no "
            "production synchronization tolerance has been proven"
        ),
    )
    parser.add_argument(
        "--stations-m",
        nargs="+",
        type=float,
        default=list(DEFAULT_PAIRING_STATIONS_M),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument(
        "--estimate-topic",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    )
    parser.add_argument("--map-topic", default=DEFAULT_MAP_TOPIC)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def _validate_arguments(arguments: argparse.Namespace) -> tuple[float, ...]:
    if arguments.max_pairs < 1:
        raise ValueError("max-pairs must be positive")
    if arguments.max_step_m <= 0.0 or not math.isfinite(arguments.max_step_m):
        raise ValueError("max-step-m must be finite and positive")
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
                            meaning="curvature_delta",
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
                    reference_path = ego_relative_path_from_road_frame(frame)
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


def _plot_pairs(path: Path, plots: Sequence[_PairPlot]) -> None:
    if not plots:
        path.unlink(missing_ok=True)
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = min(4, len(plots))
    rows = int(math.ceil(len(plots) / columns))
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(4.7 * columns, 3.9 * rows),
        squeeze=False,
    )
    for axis, item in zip(axes.flat, plots):
        for geometry, label, color in (
            (item.reference, "RLMB pseudo-reference candidate", "tab:blue"),
            (item.estimate, "Estimated KEEP_LANE", "tab:orange"),
        ):
            visible = (
                (geometry.stations_m >= -10.0)
                & (geometry.stations_m <= max(item.stations_m) + 5.0)
            )
            axis.plot(
                geometry.x_m[visible],
                geometry.y_m[visible],
                color=color,
                linewidth=1.5,
                label=label,
            )
            sampled = sample_ego_relative_path(geometry, item.stations_m)
            axis.scatter(sampled.x_m, sampled.y_m, color=color, s=8)
            axis.scatter(
                geometry.origin_footpoint_m[0],
                geometry.origin_footpoint_m[1],
                color=color,
                marker="x",
                s=35,
            )
        axis.scatter(0.0, 0.0, color="black", marker="+", s=45, label="(0,0)")
        axis.set_title(item.title, fontsize=9)
        axis.set_xlabel("x [m]")
        axis.set_ylabel("y [m]")
        axis.grid(True, alpha=0.25)
        axis.set_aspect("equal", adjustable="datalim")
    for axis in axes.flat[len(plots) :]:
        axis.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, fontsize=9)
    figure.suptitle(
        "EDP–RLMB raw-frame pairing audit (diagnostic only; no motion compensation)",
        fontsize=12,
        y=0.997,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.975))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=170)
    plt.close(figure)


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
        }

    inventory_rows = [
        inventory_row(role="estimate", position=position, record=record)
        for position, record in enumerate(estimates)
    ] + [
        inventory_row(role="map", position=position, record=record)
        for position, record in enumerate(references)
    ]
    pair_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    plot_candidates: list[_PairPlot] = []
    pair_deltas: list[float] = []
    footpoint_separations: list[float] = []
    heading_deltas: list[float] = []
    lateral_rms_values: list[float] = []
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
            pair_state = "diagnostic_ready_uncompensated"
            failure_code = None
            try:
                disagreement = compare_ego_relative_paths(
                    estimate.path,
                    reference.path,
                    stations_m=stations_m,
                )
            except GeometryValidationError as error:
                pair_state = "geometry_not_ready"
                failure_code = error.code
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
        }
        pair_rows.append(row)
        pair_deltas.append(abs(delta_ms))
        if disagreement is not None:
            assert estimate.path is not None
            assert reference.path is not None
            footpoint_separations.append(float(alignment["footpoint_separation_m"]))
            heading_deltas.append(abs(float(alignment["origin_heading_delta_rad"])))
            lateral_rms_values.append(disagreement.lateral_rms_m)
            estimate_sampled = sample_ego_relative_path(estimate.path, stations_m)
            reference_sampled = sample_ego_relative_path(reference.path, stations_m)
            for station_index, station in enumerate(disagreement.stations_m):
                station_rows.append(
                    {
                        "pair_index": pair_index,
                        "station_m": float(station),
                        "estimate_x_m": float(estimate_sampled.x_m[station_index]),
                        "estimate_y_m": float(estimate_sampled.y_m[station_index]),
                        "reference_x_m": float(reference_sampled.x_m[station_index]),
                        "reference_y_m": float(reference_sampled.y_m[station_index]),
                        "diagnostic_lateral_m": float(
                            disagreement.lateral_m[station_index]
                        ),
                        "diagnostic_along_track_m": float(
                            disagreement.along_track_m[station_index]
                        ),
                        "diagnostic_heading_rad": float(
                            disagreement.heading_rad[station_index]
                        ),
                    }
                )
            plot_candidates.append(
                _PairPlot(
                    title=(
                        f"E{estimate.message_index} / M{reference.message_index}; "
                        f"Δt={delta_ms:.2f} ms"
                    ),
                    estimate=estimate.path,
                    reference=reference.path,
                    stations_m=tuple(stations_m),
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
        ),
        inventory_rows,
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
        ),
        station_rows,
    )
    _plot_pairs(output / "pairing_overlays.png", plots)
    summary = {
        "version": "0.4.1",
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
        "diagnostic_ready_pair_count": len(plot_candidates),
        "extraction_failures": dict(sorted(failures.items())),
        "stations_m": list(stations_m),
        "timestamp_pairing_basis": (
            "unique mutual-nearest source timestamps on complete topic streams; "
            "geometry validity is applied only after temporal pairing"
        ),
        "pairing_before_geometry_filtering": True,
        "all_messages_retained_in_inventory": True,
        "estimate_spline_semantics": (
            "curvature_delta is a provisional reconstruction hypothesis; its "
            "interface semantics remain unresolved"
        ),
        "timestamp_gate_ms": arguments.maximum_pair_delta_ms,
        "timestamp_gate_predeclared": arguments.maximum_pair_delta_ms is not None,
        "median_absolute_source_delta_ms": _median_or_none(pair_deltas),
        "median_footpoint_separation_m": _median_or_none(footpoint_separations),
        "median_absolute_origin_heading_delta_rad": _median_or_none(heading_deltas),
        "median_diagnostic_lateral_rms_m": _median_or_none(lateral_rms_values),
        "coordinate_frame_equivalence_confirmed": False,
        "timestamp_motion_compensation_applied": False,
        "map_signal_role": "pseudo_reference_candidate",
        "diagnostic_disagreement_is_lane_estimation_error": False,
        "generated_final_residual_dataset": False,
        "next_decision": (
            "Rerun the two audited MCAPs and verify that invalid geometry prefixes "
            "remain index-aligned instead of shifting temporal pairs. Then inspect "
            "the remaining EDP spline and RLMB path-shape hypotheses."
        ),
        "confidentiality": "Outputs contain BMW-derived measurements and must remain private.",
    }
    _write_json(output / "pairing_summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        stations_m = _validate_arguments(arguments)
        if not arguments.mcap.is_file():
            raise FileNotFoundError(f"MCAP file not found: {arguments.mcap}")
        summary = run_pairing_audit(arguments, stations_m=stations_m)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "inspected %d pairs; %d have complete diagnostic station coverage",
        summary["inspected_pair_count"],
        summary["diagnostic_ready_pair_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return 0 if summary["inspected_pair_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
