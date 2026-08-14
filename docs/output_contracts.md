# v0.4.5 output contracts

These contracts describe diagnostics, not training labels. EDP–RLMB
disagreement is not ground-truth lane-estimation error, and RLMB is a
pseudo-reference candidate rather than physical ground truth.

## Single-recording pairing audit

The exact filename set is:

```text
message_inventory.csv
rlmb_chain_audit.csv
pairing_audit.csv
diagnostic_disagreement.csv
pairing_overlays.png
pairing_lateral_zoom.png
diagnostic_station_profiles.png
pairing_summary.json
```

CSV headers and column order are fixed:

```text
message_inventory.csv:
topic_role,message_index,source_time_ns_private,log_time_ns_private,publish_time_ns_private,geometry_state,geometry_failure_code,temporal_state,counterpart_message_index,counterpart_delta_ms,map_chain_segment_count,map_chain_segment_indices,map_chain_segment_ids,map_chain_termination_reason,map_chain_required_coverage_reached,map_chain_max_junction_gap_m,map_chain_max_junction_heading_delta_rad,map_chain_all_links_reciprocal

rlmb_chain_audit.csv:
map_message_index,map_source_time_ns_private,geometry_state,geometry_failure_code,segment_count,segment_indices,segment_ids,termination_reason,required_forward_m,required_forward_coverage_reached,actual_forward_coverage_m,actual_backward_coverage_m,junction_gaps_m,junction_heading_deltas_rad,reciprocal_predecessor_links

pairing_audit.csv:
pair_index,estimate_message_index,map_message_index,estimate_source_time_ns_private,map_source_time_ns_private,source_delta_ms,absolute_source_delta_ms,timestamp_gate_ms,timestamp_gate_passed,pair_state,failure_code,estimate_geometry_state,estimate_geometry_failure_code,map_geometry_state,map_geometry_failure_code,estimate_backward_coverage_m,estimate_forward_coverage_m,reference_backward_coverage_m,reference_forward_coverage_m,estimate_reversed_to_positive_x,reference_reversed_to_positive_x,estimate_origin_distance_m,reference_origin_distance_m,footpoint_separation_m,footpoint_dx_m,footpoint_dy_m,origin_heading_delta_rad,diagnostic_lateral_rms_m,diagnostic_lateral_max_abs_m,diagnostic_primary_horizon_max_m,diagnostic_primary_lateral_rms_m,diagnostic_far_lateral_rms_m,diagnostic_common_max_station_m,diagnostic_available_lateral_rms_m,reference_chain_segment_count,reference_chain_segment_indices,reference_chain_segment_ids,reference_chain_termination_reason,reference_chain_required_coverage_reached,reference_chain_max_junction_gap_m,reference_chain_max_junction_heading_delta_rad

diagnostic_disagreement.csv:
pair_index,station_m,estimate_x_m,estimate_y_m,reference_x_m,reference_y_m,diagnostic_lateral_m,diagnostic_along_track_m,diagnostic_heading_rad,full_requested_horizon_available,primary_horizon_available
```

Suffixes define units: `_ns` nanoseconds, `_ms` milliseconds, `_s` seconds,
`_m` metres, `_rad` radians, and `_deg` degrees. Timestamp columns marked
`_private` and all decoded measurements are confidential.

`pairing_summary.json` has these stable top-level keys:

```text
all_messages_retained_in_inventory, ambiguous_estimate_nearest_time_count,
ambiguous_map_nearest_time_count, complete_stream_mutual_nearest_pair_count,
confidentiality, coordinate_frame_equivalence_confirmed,
curvature_change_semantics_confirmed,
diagnostic_disagreement_is_lane_estimation_error, diagnostic_ready_pair_count,
estimate_messages, estimate_spline_reconstruction, estimate_spline_semantics,
estimate_topic, extraction_failures, far_horizon_min_m,
generated_final_residual_dataset, inspected_pair_count, map_messages,
map_signal_role, map_topic, mcap_filename,
median_absolute_origin_heading_delta_rad, median_absolute_source_delta_ms,
median_diagnostic_lateral_rms_m, median_far_horizon_lateral_rms_m,
median_footpoint_separation_m, median_primary_horizon_lateral_rms_m,
missing_estimate_source_time_count, missing_map_source_time_count,
next_decision, pairing_before_geometry_filtering, plotted_pair_count,
primary_horizon_max_m, primary_horizon_ready_pair_count, purpose,
ready_estimate_geometry_count, ready_map_geometry_count, rlmb_chain_rule,
rlmb_chain_termination_counts, rlmb_max_junction_gap_m,
rlmb_max_junction_heading_deg, rlmb_max_segments,
rlmb_multi_segment_lane_count, rlmb_ordered_lane_count,
rlmb_required_coverage_reached_count, stations_m, timestamp_gate_ms,
timestamp_gate_predeclared, timestamp_gate_rejected_pair_count,
timestamp_motion_compensation_applied, timestamp_pairing_basis,
unmatched_estimate_message_count, unmatched_map_message_count, version
```

## Batch pairing audit

Each successful `recordings/recording_###/` directory contains the unchanged
single-recording set above. Batch-root filenames are:

```text
batch_manifest.json
recording_summary.csv
scope_horizon_metrics.csv
scope_station_metrics.csv
temporal_tail_events.csv
rlmb_chain_summary.json
fixed_cohort_station_profiles.png
recording_horizon_summary.png
temporal_diagnostic_events.png
batch_summary.json
```

Batch CSV headers and column order are fixed:

```text
recording_summary.csv:
recording_id,drive_id,mcap_filename_private,status,error_code,error_message,estimate_message_count,map_message_count,mutual_nearest_pair_count,unmatched_estimate_message_count,unmatched_map_message_count,median_absolute_source_delta_ms,rlmb_multi_segment_lane_count,h60_complete_cohort_pair_count,h60_pooled_lateral_rms_m,h60_median_pair_lateral_rms_m,h60_p95_pair_lateral_rms_m,h100_complete_cohort_pair_count,h100_pooled_lateral_rms_m,h100_median_pair_lateral_rms_m,h100_p95_pair_lateral_rms_m,h60_predeclared_outcome_tail_pair_count,h100_predeclared_outcome_tail_pair_count

scope_horizon_metrics.csv:
scope_type,scope_id,horizon_m,cohort_pair_count,station_count_per_pair,pooled_observation_count,contributing_recording_count,pooled_lateral_mean_m,pooled_lateral_rms_m,pooled_lateral_median_m,median_pair_lateral_rms_m,p95_pair_lateral_rms_m,maximum_absolute_lateral_m

scope_station_metrics.csv:
scope_type,scope_id,horizon_m,station_m,cohort_pair_count,lateral_mean_m,lateral_rms_m,lateral_median_m,lateral_p05_m,lateral_p95_m

temporal_tail_events.csv:
recording_id,drive_id,pair_index,estimate_message_index,map_message_index,recording_relative_source_time_s,drive_relative_source_time_s,seconds_from_recording_end,in_final_recording_time_window,recording_tail_window_s,h60_eligible,h100_eligible,h60_pair_lateral_rms_m,h100_pair_lateral_rms_m,h60_tail_threshold_m,h100_tail_threshold_m,h60_outcome_tail_flag,h100_outcome_tail_flag,tail_thresholds_predeclared
```

`batch_manifest.json` records version, purpose, expected/resolved counts,
completeness status, canonical horizons/grid, grouping provenance, blockers, and
per-recording status. `batch_summary.json` records reconciliation, grouping,
fixed-cohort metrics, overlap evidence, thresholds, scientific limitations, and
the next decision. `rlmb_chain_summary.json` contains recording-, drive-, and
overall scopes. JSON is strict (`NaN` and infinity are rejected).

H60 is the fixed set of pairs with complete values at `0, 5, ..., 60 m` (13
stations). H100 is the fixed set with complete values at `0, 5, ..., 100 m` (21
stations). H100 is a subset of H60. Membership is selected once per horizon,
so the pair denominator is constant at every station. Recording, drive, and
overall aggregates are recomputed from underlying pair/station rows.

Pairing uses complete-stream mutual-nearest source timestamps and retains the
signed delta. EDP reconstruction uses the validated provisional curvature-rate
interpretation. RLMB follows only explicit unique successors and stops
fail-closed. Lateral sign is defined by the pseudo-reference normal. Sampling
never extrapolates.

## Other diagnostic commands

The transition command retains `edp_message_inventory.csv`,
`edp_candidate_inventory.csv`, `edp_candidate_geometry.csv`,
`edp_selected_transitions.csv`, two PNG plots, and
`edp_transition_summary.json`. Geometry validation retains four CSV audits,
three JSON reports, and `validation_overlays/`. Reference validation retains
its source/catalog JSON files, six CSV audits, and
`reference_validation_summary.json`. These files contain private decoded field
names or BMW-derived measurements and must remain outside version control.
