"""Native spatial projection/resampling without motion compensation.

The numerical path is retained from the accepted v0.5.0 implementation at
commit ``8a6c1d8``.  It is intentionally separate from the optional v0.5.1
odometry sensitivity workflow.
"""

from __future__ import annotations

import argparse
import logging
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ..domain.alignment import (
    SpatialAlignmentResult,
    compare_spatially_aligned_paths,
    project_point_to_path,
)
from ..domain.batch_pairing import HORIZON_60_M, HORIZON_100_M
from ..domain.geometry_validation import GeometryValidationError
from ..domain.pairing import (
    DiagnosticPathDisagreement,
    EgoRelativePath,
    compare_ego_relative_paths,
    mutual_nearest_timestamp_pairs,
)
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.projection_alignment import plot_alignment_comparison
from .pairing import DEFAULT_MAP_TOPIC, _decode_paths

LOGGER = logging.getLogger(__name__)


def _validate_arguments(arguments: argparse.Namespace) -> None:
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


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(
            f"output directory is not empty: {path}; use a new validation directory"
        )
    path.mkdir(parents=True, exist_ok=True)


def _covers(path: EgoRelativePath, stations: Sequence[float]) -> bool:
    return (
        float(stations[0]) >= float(path.stations_m[0]) - 1e-9
        and float(stations[-1]) <= float(path.stations_m[-1]) + 1e-9
    )


def _median_or_none(values: Sequence[float]) -> float | None:
    return None if not values else float(np.median(np.asarray(values, dtype=np.float64)))


def _rms_or_none(disagreement: DiagnosticPathDisagreement | None) -> float | None:
    return None if disagreement is None else disagreement.lateral_rms_m


def _aligned_result_or_none(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
    stations: Sequence[float],
) -> SpatialAlignmentResult | None:
    try:
        return compare_spatially_aligned_paths(
            estimate,
            reference,
            stations_m=stations,
        )
    except GeometryValidationError as error:
        if error.code in {
            "reference_alignment_estimate_coverage_incomplete",
            "reference_alignment_reference_coverage_incomplete",
        }:
            return None
        raise


def _native_result_or_none(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
    stations: Sequence[float],
) -> DiagnosticPathDisagreement | None:
    if not _covers(estimate, stations) or not _covers(reference, stations):
        return None
    return compare_ego_relative_paths(
        estimate,
        reference,
        stations_m=stations,
    )


def _station_rows(
    *,
    pair_index: int,
    aligned: SpatialAlignmentResult,
    native: DiagnosticPathDisagreement | None,
    reference: EgoRelativePath,
    h60_eligible: bool,
    h100_eligible: bool,
) -> list[dict[str, Any]]:
    native_by_station: dict[float, tuple[float, float, float]] = {}
    native_reference_points: dict[float, tuple[float, float]] = {}
    if native is not None:
        reference_x = np.interp(native.stations_m, reference.stations_m, reference.x_m)
        reference_y = np.interp(native.stations_m, reference.stations_m, reference.y_m)
        for index, station in enumerate(native.stations_m):
            key = float(station)
            native_by_station[key] = (
                float(native.lateral_m[index]),
                float(native.along_track_m[index]),
                float(native.heading_rad[index]),
            )
            native_reference_points[key] = (
                float(reference_x[index]),
                float(reference_y[index]),
            )

    rows: list[dict[str, Any]] = []
    for index, station_value in enumerate(aligned.stations_m):
        station = float(station_value)
        native_values = native_by_station.get(station)
        native_point = native_reference_points.get(station)
        aligned_lateral = float(aligned.disagreement.lateral_m[index])
        rows.append(
            {
                "pair_index": pair_index,
                "station_m": station,
                "estimate_x_m": float(aligned.estimate_points_m[index, 0]),
                "estimate_y_m": float(aligned.estimate_points_m[index, 1]),
                "native_reference_x_m": (
                    None if native_point is None else native_point[0]
                ),
                "native_reference_y_m": (
                    None if native_point is None else native_point[1]
                ),
                "aligned_reference_x_m": float(aligned.reference_points_m[index, 0]),
                "aligned_reference_y_m": float(aligned.reference_points_m[index, 1]),
                "native_lateral_m": (
                    None if native_values is None else native_values[0]
                ),
                "aligned_lateral_m": aligned_lateral,
                "aligned_minus_native_lateral_m": (
                    None
                    if native_values is None
                    else aligned_lateral - native_values[0]
                ),
                "native_along_track_m": (
                    None if native_values is None else native_values[1]
                ),
                "aligned_along_track_m": float(
                    aligned.disagreement.along_track_m[index]
                ),
                "native_heading_delta_rad": (
                    None if native_values is None else native_values[2]
                ),
                "aligned_heading_delta_rad": float(
                    aligned.disagreement.heading_rad[index]
                ),
                "h60_aligned_eligible": h60_eligible,
                "h100_aligned_eligible": h100_eligible,
            }
        )
    return rows


PAIR_FIELDS = (
    "pair_index",
    "estimate_message_index",
    "map_message_index",
    "estimate_source_time_ns_private",
    "map_source_time_ns_private",
    "source_delta_ms",
    "absolute_source_delta_ms",
    "pair_state",
    "failure_code",
    "estimate_geometry_state",
    "estimate_geometry_failure_code",
    "map_geometry_state",
    "map_geometry_failure_code",
    "reference_anchor_station_m",
    "reference_anchor_x_m",
    "reference_anchor_y_m",
    "estimate_anchor_x_m",
    "estimate_anchor_y_m",
    "anchor_distance_m",
    "anchor_heading_delta_rad",
    "alignment_projection_segment_index",
    "alignment_projection_segment_fraction",
    "aligned_reference_backward_coverage_m",
    "aligned_reference_forward_coverage_m",
    "h60_aligned_eligible",
    "h100_aligned_eligible",
    "h60_native_comparison_available",
    "h100_native_comparison_available",
    "native_h60_lateral_rms_m",
    "aligned_h60_lateral_rms_m",
    "aligned_minus_native_h60_lateral_rms_m",
    "native_h100_lateral_rms_m",
    "aligned_h100_lateral_rms_m",
    "aligned_minus_native_h100_lateral_rms_m",
)

STATION_FIELDS = (
    "pair_index",
    "station_m",
    "estimate_x_m",
    "estimate_y_m",
    "native_reference_x_m",
    "native_reference_y_m",
    "aligned_reference_x_m",
    "aligned_reference_y_m",
    "native_lateral_m",
    "aligned_lateral_m",
    "aligned_minus_native_lateral_m",
    "native_along_track_m",
    "aligned_along_track_m",
    "native_heading_delta_rad",
    "aligned_heading_delta_rad",
    "h60_aligned_eligible",
    "h100_aligned_eligible",
)


def run_alignment_audit(arguments: argparse.Namespace) -> dict[str, Any]:
    """Validate Leon's projection/resampling rule on one complete recording."""

    _validate_arguments(arguments)
    _ensure_empty_output(arguments.output_directory)
    estimates, references, decode_failures, counts = _decode_paths(
        arguments.mcap,
        estimate_topic=arguments.estimate_topic,
        map_topic=arguments.map_topic,
        max_step_m=arguments.max_step_m,
        stations_m=HORIZON_100_M,
        map_max_segments=arguments.map_max_segments,
        map_max_junction_gap_m=arguments.map_max_junction_gap_m,
        map_max_junction_heading_rad=math.radians(
            arguments.map_max_junction_heading_deg
        ),
    )
    maximum_delta_ns = (
        None
        if arguments.maximum_pair_delta_ms is None
        else int(round(arguments.maximum_pair_delta_ms * 1e6))
    )
    timestamp_audit = mutual_nearest_timestamp_pairs(
        [item.source_time_ns for item in estimates],
        [item.source_time_ns for item in references],
        maximum_delta_ns=maximum_delta_ns,
    )

    pair_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    alignment_failures: Counter[str] = Counter()
    source_deltas_ms: list[float] = []
    anchor_stations_m: list[float] = []
    anchor_distances_m: list[float] = []
    anchor_heading_deltas_rad: list[float] = []
    native_h60_rms: list[float] = []
    aligned_h60_rms: list[float] = []
    h60_rms_changes: list[float] = []
    native_h100_rms: list[float] = []
    aligned_h100_rms: list[float] = []
    h100_rms_changes: list[float] = []

    for pair_index, timestamp_pair in enumerate(timestamp_audit.pairs):
        estimate = estimates[timestamp_pair.first_position]
        reference = references[timestamp_pair.second_position]
        delta_ms = timestamp_pair.delta_ns / 1e6
        source_deltas_ms.append(abs(delta_ms))
        row: dict[str, Any] = {
            "pair_index": pair_index,
            "estimate_message_index": estimate.message_index,
            "map_message_index": reference.message_index,
            "estimate_source_time_ns_private": estimate.source_time_ns,
            "map_source_time_ns_private": reference.source_time_ns,
            "source_delta_ms": delta_ms,
            "absolute_source_delta_ms": abs(delta_ms),
            "pair_state": None,
            "failure_code": None,
            "estimate_geometry_state": estimate.geometry_state,
            "estimate_geometry_failure_code": estimate.failure_code,
            "map_geometry_state": reference.geometry_state,
            "map_geometry_failure_code": reference.failure_code,
            "reference_anchor_station_m": None,
            "reference_anchor_x_m": None,
            "reference_anchor_y_m": None,
            "estimate_anchor_x_m": None,
            "estimate_anchor_y_m": None,
            "anchor_distance_m": None,
            "anchor_heading_delta_rad": None,
            "alignment_projection_segment_index": None,
            "alignment_projection_segment_fraction": None,
            "aligned_reference_backward_coverage_m": None,
            "aligned_reference_forward_coverage_m": None,
            "h60_aligned_eligible": False,
            "h100_aligned_eligible": False,
            "h60_native_comparison_available": False,
            "h100_native_comparison_available": False,
            "native_h60_lateral_rms_m": None,
            "aligned_h60_lateral_rms_m": None,
            "aligned_minus_native_h60_lateral_rms_m": None,
            "native_h100_lateral_rms_m": None,
            "aligned_h100_lateral_rms_m": None,
            "aligned_minus_native_h100_lateral_rms_m": None,
        }
        if not estimate.geometry_ready or not reference.geometry_ready:
            row["pair_state"] = "geometry_not_ready"
            row["failure_code"] = (
                estimate.failure_code
                if not estimate.geometry_ready
                else reference.failure_code
            )
            pair_rows.append(row)
            continue

        assert estimate.path is not None
        assert reference.path is not None
        try:
            projection = project_point_to_path(
                estimate.path.origin_footpoint_m,
                reference.path,
            )
            aligned_h60 = _aligned_result_or_none(
                estimate.path,
                reference.path,
                HORIZON_60_M,
            )
            aligned_h100 = _aligned_result_or_none(
                estimate.path,
                reference.path,
                HORIZON_100_M,
            )
            native_h60 = _native_result_or_none(
                estimate.path,
                reference.path,
                HORIZON_60_M,
            )
            native_h100 = _native_result_or_none(
                estimate.path,
                reference.path,
                HORIZON_100_M,
            )
        except GeometryValidationError as error:
            row["pair_state"] = "alignment_not_ready"
            row["failure_code"] = error.code
            alignment_failures[error.code] += 1
            pair_rows.append(row)
            continue

        anchor_heading_delta = float(
            (estimate.path.origin_heading_rad - projection.heading_rad + np.pi)
            % (2.0 * np.pi)
            - np.pi
        )
        aligned_backward_coverage = float(
            projection.station_m - reference.path.stations_m[0]
        )
        aligned_forward_coverage = float(
            reference.path.stations_m[-1] - projection.station_m
        )
        h60_eligible = aligned_h60 is not None
        h100_eligible = aligned_h100 is not None
        row.update(
            {
                "pair_state": (
                    "aligned_h100_ready"
                    if h100_eligible
                    else "aligned_h60_ready"
                    if h60_eligible
                    else "alignment_coverage_incomplete"
                ),
                "failure_code": (
                    None
                    if h60_eligible
                    else "reference_alignment_h60_coverage_incomplete"
                ),
                "reference_anchor_station_m": projection.station_m,
                "reference_anchor_x_m": float(projection.point_m[0]),
                "reference_anchor_y_m": float(projection.point_m[1]),
                "estimate_anchor_x_m": float(estimate.path.origin_footpoint_m[0]),
                "estimate_anchor_y_m": float(estimate.path.origin_footpoint_m[1]),
                "anchor_distance_m": projection.distance_m,
                "anchor_heading_delta_rad": anchor_heading_delta,
                "alignment_projection_segment_index": projection.segment_index,
                "alignment_projection_segment_fraction": projection.segment_fraction,
                "aligned_reference_backward_coverage_m": aligned_backward_coverage,
                "aligned_reference_forward_coverage_m": aligned_forward_coverage,
                "h60_aligned_eligible": h60_eligible,
                "h100_aligned_eligible": h100_eligible,
                "h60_native_comparison_available": native_h60 is not None,
                "h100_native_comparison_available": native_h100 is not None,
                "native_h60_lateral_rms_m": _rms_or_none(native_h60),
                "aligned_h60_lateral_rms_m": (
                    None if aligned_h60 is None else aligned_h60.disagreement.lateral_rms_m
                ),
                "native_h100_lateral_rms_m": _rms_or_none(native_h100),
                "aligned_h100_lateral_rms_m": (
                    None
                    if aligned_h100 is None
                    else aligned_h100.disagreement.lateral_rms_m
                ),
            }
        )
        if aligned_h60 is not None and native_h60 is not None:
            change = aligned_h60.disagreement.lateral_rms_m - native_h60.lateral_rms_m
            row["aligned_minus_native_h60_lateral_rms_m"] = change
            native_h60_rms.append(native_h60.lateral_rms_m)
            aligned_h60_rms.append(aligned_h60.disagreement.lateral_rms_m)
            h60_rms_changes.append(change)
        if aligned_h100 is not None and native_h100 is not None:
            change = aligned_h100.disagreement.lateral_rms_m - native_h100.lateral_rms_m
            row["aligned_minus_native_h100_lateral_rms_m"] = change
            native_h100_rms.append(native_h100.lateral_rms_m)
            aligned_h100_rms.append(aligned_h100.disagreement.lateral_rms_m)
            h100_rms_changes.append(change)

        anchor_stations_m.append(projection.station_m)
        anchor_distances_m.append(projection.distance_m)
        anchor_heading_deltas_rad.append(abs(anchor_heading_delta))
        station_result = aligned_h100 if aligned_h100 is not None else aligned_h60
        if station_result is not None:
            native_station_result = (
                native_h100 if native_h100 is not None else native_h60
            )
            station_rows.extend(
                _station_rows(
                    pair_index=pair_index,
                    aligned=station_result,
                    native=native_station_result,
                    reference=reference.path,
                    h60_eligible=h60_eligible,
                    h100_eligible=h100_eligible,
                )
            )
        pair_rows.append(row)

    output = arguments.output_directory
    write_csv_rows(output / "alignment_pair_audit.csv", PAIR_FIELDS, pair_rows)
    write_csv_rows(
        output / "alignment_station_comparison.csv",
        STATION_FIELDS,
        station_rows,
    )
    plot_alignment_comparison(
        output / "alignment_comparison.png",
        pair_rows=pair_rows,
        station_rows=station_rows,
    )
    h60_count = sum(bool(row["h60_aligned_eligible"]) for row in pair_rows)
    h100_count = sum(bool(row["h100_aligned_eligible"]) for row in pair_rows)
    summary = {
        "version": "0.5.2",
        "purpose": "projection_based_reference_alignment_validation",
        "mcap_filename_private": arguments.mcap.name,
        "estimate_topic": arguments.estimate_topic,
        "map_topic": arguments.map_topic,
        **counts,
        "complete_stream_mutual_nearest_pair_count": len(timestamp_audit.pairs),
        "timestamp_gate_rejected_pair_count": len(timestamp_audit.rejected_by_gate),
        "h60_aligned_complete_pair_count": h60_count,
        "h100_aligned_complete_pair_count": h100_count,
        "h100_is_subset_of_h60": all(
            not row["h100_aligned_eligible"] or row["h60_aligned_eligible"]
            for row in pair_rows
        ),
        "canonical_horizons_m": [60, 100],
        "canonical_station_grid_m": list(HORIZON_100_M),
        "alignment_method": (
            "project EDP station-zero footpoint onto the paired RLMB path; "
            "define the projected RLMB station as aligned zero; sample RLMB at "
            "equal forward arc-length offsets"
        ),
        "alignment_assumption": (
            "EDP geometry close to station zero is sufficiently close to RLMB "
            "for the nearest projection to identify longitudinal correspondence"
        ),
        "anchor_quality_threshold_applied": False,
        "median_absolute_source_delta_ms": _median_or_none(source_deltas_ms),
        "median_reference_anchor_station_m": _median_or_none(anchor_stations_m),
        "median_anchor_distance_m": _median_or_none(anchor_distances_m),
        "median_absolute_anchor_heading_delta_rad": _median_or_none(
            anchor_heading_deltas_rad
        ),
        "median_native_h60_pair_lateral_rms_m": _median_or_none(native_h60_rms),
        "median_aligned_h60_pair_lateral_rms_m": _median_or_none(aligned_h60_rms),
        "median_aligned_minus_native_h60_pair_lateral_rms_m": _median_or_none(
            h60_rms_changes
        ),
        "median_native_h100_pair_lateral_rms_m": _median_or_none(native_h100_rms),
        "median_aligned_h100_pair_lateral_rms_m": _median_or_none(aligned_h100_rms),
        "median_aligned_minus_native_h100_pair_lateral_rms_m": _median_or_none(
            h100_rms_changes
        ),
        "decode_failures": dict(sorted(decode_failures.items())),
        "alignment_failures": dict(sorted(alignment_failures.items())),
        "timestamp_pairing_basis": (
            "unique mutual-nearest source timestamps on complete recording-local "
            "topic streams before geometry filtering"
        ),
        "source_delta_used_numerically_for_alignment": False,
        "alignment_semantics": "v0.5.0_native_spatial_projection",
        "spatial_reference_alignment_applied": True,
        "explicit_ego_pose_motion_compensation_applied": False,
        "accepted_for_modeling": True,
        "reference_signal_role": "best_available_pseudo_ground_truth",
        "aligned_difference_is_absolute_physical_ground_truth_error": False,
        "generated_final_residual_dataset": False,
        "trained_statistical_model": False,
        "next_decision": (
            "Run this validation on all manifest recordings; review anchor shifts, "
            "projection distances, coverage, and native-versus-aligned changes "
            "before freezing residual eligibility and training the Gaussian model."
        ),
        "confidentiality": (
            "Outputs contain BMW-derived timestamps and measurements and must remain private."
        ),
    }
    write_strict_json(output / "alignment_summary.json", summary)
    return summary


__all__ = [
    "DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC",
    "DEFAULT_MAP_TOPIC",
    "PAIR_FIELDS",
    "STATION_FIELDS",
    "run_alignment_audit",
]
