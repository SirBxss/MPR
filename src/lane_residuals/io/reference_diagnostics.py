"""Static classifications only; never serialize exception text or payloads."""

from __future__ import annotations

from ..domain.geometry_validation import GeometryValidationError
from .mcap import RoadMessageError, _road_failure_code


REFERENCE_STAGES = frozenset({
    "schema", "road_fields", "polyline_coordinates", "polyline_optional_values",
    "arc_length_pool", "boundary_fields", "boundary_coordinates", "ego_metadata",
    "segment_reconstruction", "road_metadata", "frame_validation", "ordered_ego_path",
})
GEOMETRY_FAILURES = frozenset({
    "ego_origin_projection_ambiguous", "map_ego_drive_path_not_unique",
    "map_successor_junction_tangent_unavailable", "pairing_array_count_mismatch",
    "pairing_arrays_invalid", "pairing_geometry_degenerate", "pairing_origin_distance_invalid",
    "pairing_origin_invalid", "pairing_origin_outside_domain", "pairing_points_invalid",
    "pairing_points_non_finite", "pairing_station_coverage_incomplete", "pairing_stations_not_increasing",
})


def _reason(error: BaseException | None) -> str:
    if error is None:
        return "none"
    if isinstance(error, RoadMessageError):
        message = str(error)
        known = {
            "lane segment list is empty": "lane_segments_empty",
            "vertex pool contains unreadable coordinates": "vertex_pool_unreadable_coordinates",
            "distributed value has invalid status flags": "distributed_flags_invalid",
            "distributed value mean is marked invalid": "distributed_mean_invalid",
            "MCAP timestamps must be nonnegative": "mcap_timestamp_negative",
            "source_time_ns must be nonnegative": "source_timestamp_negative",
        }
        if message in known:
            return known[message]
        if message.startswith("message is missing required field ("):
            return "required_field_missing"
        # This existing classifier returns only fixed literal codes.
        return _road_failure_code(message)
    if isinstance(error, GeometryValidationError):
        # Known pairing codes are static; unknown attributes are never emitted.
        return error.code if isinstance(error.code, str) and error.code in GEOMETRY_FAILURES else "geometry_validation_error"
    if isinstance(error, TypeError):
        return "type_error"
    if isinstance(error, OverflowError):
        return "overflow_error"
    if isinstance(error, ValueError):
        return "value_error"
    return "other_error"


def reference_failure_detail(error: BaseException, stage: str) -> str:
    """The caller supplies a static conversion stage; causes are one level deep."""
    stage = stage if stage in REFERENCE_STAGES else "unclassified_stage"
    return f"{stage}:{_reason(error)}:{_reason(error.__cause__)}"
