"""Counts-only exclusive attribution for the accepted v0.19.10 consumer."""

from collections import Counter
from .recording_ingestion import RecordingIngestionError
from .recording_readiness_bindings import LATE_ESTIMATE_BINDINGS

# Static codes from the pinned converters, not exception text or a prefix fallback.
PINNED_DATA_CODES = frozenset((
    'anchor_sampling_ambiguous',
    'anchor_zero_outside_domain',
    'chord_exceeds_arc_length',
    'comparator_array_count_mismatch',
    'comparator_arrays_not_vectors',
    'comparator_differential_geometry_missing',
    'comparator_ego_segment_not_unique',
    'comparator_non_finite',
    'comparator_not_direct_drive_path',
    'comparator_qualifier_unreadable',
    'comparator_reported_unavailable',
    'comparator_schema_or_encoding_mismatch',
    'comparator_stations_not_increasing',
    'comparator_zero_outside_domain',
    'curvature_change_unavailable',
    'ego_origin_projection_ambiguous',
    'estimate_condition_horizon_incomplete',
    'estimate_confidence_empty',
    'estimate_confidence_field_unavailable',
    'estimate_confidence_h100_coverage_incomplete',
    'estimate_confidence_non_finite',
    'estimate_confidence_non_numeric',
    'estimate_confidence_out_of_range',
    'estimate_descriptor_missing',
    'estimate_drive_paths_unavailable',
    'estimate_keep_lane_not_unique',
    'estimate_native_station_mapping_unavailable',
    'estimate_role_schema_unavailable',
    'estimate_role_unavailable',
    'estimate_schema_or_encoding_mismatch',
    'generated_geometry_non_finite',
    'heading_discretization_not_converged',
    'index_anchor_not_explicit',
    'index_anchor_not_integer',
    'index_anchor_out_of_range',
    'index_anchor_unavailable',
    'initial_parameters_unavailable',
    'initial_parameters_unreadable',
    'interval_count_mismatch',
    'map_ego_drive_path_not_unique',
    'map_successor_junction_tangent_unavailable',
    'maximum_output_points_exceeded',
    'model_parameters_absent',
    'non_finite_curvature_change',
    'non_finite_initial_parameters',
    'non_finite_segment_starts',
    'non_increasing_segment_starts',
    'odometry_insufficient_samples',
    'odometry_interpolation_gap_exceeds_limit',
    'odometry_log_lag_exceeds_limit',
    'odometry_log_times_not_monotonic',
    'odometry_no_sample_at_or_before_estimate_log',
    'odometry_reference_time_outside_coverage',
    'odometry_speed_history_outside_coverage',
    'odometry_timestamps_not_strictly_increasing',
    'pairing_array_count_mismatch',
    'pairing_arrays_invalid',
    'pairing_geometry_degenerate',
    'pairing_origin_distance_invalid',
    'pairing_origin_invalid',
    'pairing_origin_outside_domain',
    'pairing_points_invalid',
    'pairing_points_non_finite',
    'pairing_station_coverage_incomplete',
    'pairing_stations_not_increasing',
    'position_discretization_not_converged',
    'quadrature_not_converged',
    'reference_alignment_projection_ambiguous',
    'sampled_arc_length_not_converged',
    'sampled_length_exceeds_support',
    'sampling_crosses_unknown_interval',
    'segment_starts_too_short',
    'segment_starts_unavailable',
    'speed_interpolation_gap_too_wide',
    'speed_stream_empty',
    'speed_timestamp_outside_coverage',
    'speed_timestamps_not_strictly_increasing',
))
QUALIFIERS = frozenset(("estimate_not_attempted_estimator_unavailable", "estimate_model_structure_invalid", "estimate_model_flag_not_true"))
ESTIMATE_DATA = {"estimate_"+v for v in PINNED_DATA_CODES} | {"estimate_TypeError", "estimate_ValueError", "estimate_geometry_not_ready", "estimate_source_timestamp_missing"}
REFERENCE_DATA = {"map_"+v for v in PINNED_DATA_CODES} | {"map_RoadMessageError", "map_TypeError", "map_ValueError", "map_geometry_not_ready"}
H100_DATA = {"h100_"+v for v in PINNED_DATA_CODES} | {"h100_TypeError", "h100_ValueError", "h100_geometry_not_ready", "h100_estimate_coverage_incomplete", "h100_reference_coverage_incomplete"}
CONDITION_DATA = {"estimate_features_"+v for v in PINNED_DATA_CODES} | PINNED_DATA_CODES | {
    "estimate_features_TypeError", "estimate_features_ValueError", "estimate_features_AttributeError",
    "estimate_features_estimate_inputs_non_finite", "odometry_stream_empty", "odometry_stream_invalid_or_schema_changed",
    "speed_uses_future_source_sample", "speed_log_time_unavailable", "speed_input_logged_after_estimate", "ValueError", "TypeError"}


def _invalid():
    raise RecordingIngestionError("scientific_attrition_unclassified_failure")


def exclusive_attrition(counts, rows, odometry_available):
    """Partition first failures; inherited overlapping diagnostics stay separate."""
    buckets = {name: Counter() for name in ("source_time", "unique_pair", "estimate_qualifier", "estimate_geometry", "reference_geometry", "common_h100", "anchor", "sensor_admission", "complete_conditions")}
    pairing = counts["timestamp_pairing_counts"]
    missing = pairing["missing_time_first_positions"]
    unmatched = pairing["unmatched_first_positions"]-missing
    buckets["source_time"]["estimate_source_timestamp_missing"] = missing
    buckets["unique_pair"]["no_unique_mutual_nearest_pair"] = unmatched
    for code, count in counts["pair_failure_counts"].items():
        if code in LATE_ESTIMATE_BINDINGS or code == "map_schema_or_encoding_mismatch":
            _invalid()
        if code in QUALIFIERS:
            stage = "estimate_qualifier"
        elif code in ESTIMATE_DATA:
            stage = "estimate_geometry"
        elif code in REFERENCE_DATA:
            stage = "reference_geometry"
        elif code in H100_DATA:
            stage = "common_h100"
        elif code == "anchor_distance_exceeds_1m_or_invalid":
            stage = "anchor"
        else:
            _invalid()
        buckets[stage][code] += count
    anchored, sensor = counts["anchored_h100_pair_count"], counts["sensor_anchored_h100_pair_count"]
    if len(rows) != sensor:
        _invalid()
    buckets["sensor_admission"]["not_sensor_topology"] = anchored-sensor
    for row in rows:
        failures = row["condition_failure_codes"]
        if any(code not in CONDITION_DATA for code in failures):
            _invalid()
        if not odometry_available:
            global_codes = [v for v in failures if v in ("odometry_stream_empty", "odometry_stream_invalid_or_schema_changed")]
            if not global_codes:
                _invalid()
            buckets["complete_conditions"][global_codes[0]] += 1
        elif failures:
            buckets["complete_conditions"][failures[0]] += 1
        elif row["conditions"] is None:
            _invalid()
    stages=[];remaining=counts["estimate_message_count"]
    for name, failures in buckets.items():
        if any(type(v) is not int or v < 0 for v in failures.values()):
            _invalid()
        failures = {k:v for k,v in sorted(failures.items()) if v}
        rejected=sum(failures.values());previous=remaining;remaining-=rejected
        if remaining < 0:
            _invalid()
        expected={"unique_pair":pairing["pairs"], "common_h100":counts["h100_pair_count"], "anchor":anchored, "sensor_admission":sensor}.get(name)
        if expected is not None and remaining != expected:
            _invalid()
        stages.append({"stage":name,"input_count":previous,"rejected_count":rejected,"remaining_count":remaining,"failure_code_counts":failures})
    complete=sum(row["conditions"] is not None for row in rows) if odometry_available else 0
    if remaining != complete:
        _invalid()
    return {"decoded_estimate_message_count":counts["estimate_message_count"],"stages":stages,"complete_condition_frame_count":complete}
