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

## v0.5.1 reference-alignment validation

The new alignment command writes exactly:

```text
alignment_pair_audit.csv
alignment_station_comparison.csv
alignment_comparison.png
alignment_summary.json
```

`alignment_pair_audit.csv` retains every recording-local mutual-nearest pair,
including geometry/motion/projection failures and the signed published
source-time delta. It also records the proxied EDP geometry epoch, odometry log
lag, RLMB interpolation span, geometry-epoch delta, rear-axle SE(2) transform,
the RLMB anchor station selected by projecting EDP station zero, anchor distance
and heading, aligned coverage, and fixed H60/H100 eligibility. Native and
aligned per-pair RMS values are reported only when the corresponding complete
horizon is available.

`alignment_station_comparison.csv` contains the EDP point, native RLMB point,
aligned RLMB point, and native/aligned lateral, along-track, and heading
differences on the canonical `0, 5, ..., 100 m` grid. No extrapolation or
available-case horizon aggregation is permitted.

The output remains validation evidence. `alignment_summary.json` explicitly
records that the published source-time delta is not used as a speed multiplier,
RLMB pose-validity time and planar odometry are used for explicit motion
compensation, the EDP geometry epoch is an audited proxy rather than an exact
published timestamp, RLMB is the best available pseudo-ground truth, and no
final residual dataset or statistical model has been created.

The batch alignment command preserves the four-file set under each
`recordings/recording_###/` directory and adds:

```text
batch_manifest.json
recording_alignment_summary.csv
alignment_pair_audit.csv
alignment_station_comparison.csv
alignment_batch_comparison.png
alignment_batch_summary.json
```

The aggregate CSVs prefix every row with opaque `recording_id` and `drive_id`.
Drive grouping comes only from the exact private basename manifest. Aggregate
alignment metrics are recomputed from pair rows, and H100 eligibility is
required to remain a subset of H60.

## v0.6.0 canonical residual and Gaussian outputs

The v0.6.0 command accepts only a complete v0.5.0 projection-alignment batch.
It writes exactly:

```text
residual_vectors.csv
residual_dataset_summary.json
gaussian_evaluation.csv
gaussian_station_evaluation.csv
gaussian_model.json
gaussian_diagnostics.png
gaussian_summary.json
```

`residual_vectors.csv` contains one row per H100 pair. Its provenance columns
are followed by `residual_000m_m`, `residual_005m_m`, ..., `residual_100m_m`.
Every row has all 21 finite values. Every station therefore has the same pair
count, and no available-case row can enter the model.

```text
residual_vectors.csv:
recording_id,drive_id,pair_index,estimate_message_index,map_message_index,estimate_source_time_ns_private,map_source_time_ns_private,source_delta_ms,residual_000m_m,...,residual_100m_m

gaussian_evaluation.csv:
scope,held_out_drive_id,training_drive_ids,training_vector_count,test_vector_count,dimension,regularization_m2,mean_joint_negative_log_likelihood,mean_squared_mahalanobis,mean_squared_mahalanobis_per_dimension,pooled_mean_prediction_rmse_m,mean_station_mean_prediction_rmse_m,marginal_95_coverage,training_covariance_condition_number

gaussian_station_evaluation.csv:
scope,held_out_drive_id,station_m,test_vector_count,mean_prediction_rmse_m,mean_prediction_bias_m,marginal_95_coverage
```

`residual_dataset_summary.json` reconciles the vector count by drive,
recording, and station. It also records SHA-256 hashes of the four accepted
source files so the private dataset can be reproduced without embedding an
absolute local path.

`gaussian_evaluation.csv` contains one row for each held-out physical drive and
one recomputed overall cross-validated row. It reports joint negative
log-likelihood, squared Mahalanobis calibration, mean-prediction RMSE, pooled
marginal 95% coverage, and training covariance condition number.
`gaussian_station_evaluation.csv` provides held-out and overall RMSE, bias, and
marginal coverage at each canonical station.

`gaussian_model.json` is strict JSON and records the 21-element mean in metres,
the 21×21 covariance in square metres, marginal standard deviations, training
count, drive IDs, fixed regularization, and intended-use limitations. It is the
final descriptive fit on all accepted vectors; it is fitted only after
leave-one-drive-out evaluation. All seven files contain or derive from private
BMW measurements and must remain outside version control.

## v0.6.1 Gaussian adequacy outputs

The v0.6.1 command accepts only a complete and internally reconciled v0.6.0
Gaussian output directory. It writes exactly:

```text
gaussian_vector_diagnostics.csv
gaussian_marginal_diagnostics.csv
gaussian_multivariate_diagnostics.csv
gaussian_marginal_diagnostics.png
gaussian_multivariate_diagnostics.png
gaussian_adequacy_summary.json
```

CSV headers and column order are fixed:

```text
gaussian_vector_diagnostics.csv:
recording_id,drive_id,pair_index,squared_mahalanobis,squared_mahalanobis_per_dimension,chi_square_cdf,chi_square_upper_tail_probability,joint_negative_log_likelihood,above_chi_square_p95,above_chi_square_p99

gaussian_marginal_diagnostics.csv:
scope_type,scope_id,station_m,vector_count,standardized_mean,standardized_std,skewness,excess_kurtosis,normal_qq_correlation,empirical_p01,empirical_p05,empirical_p50,empirical_p95,empirical_p99,coverage_50,coverage_80,coverage_90,coverage_95,coverage_99,lower_tail_exceedance_95,upper_tail_exceedance_95

gaussian_multivariate_diagnostics.csv:
scope_type,scope_id,vector_count,dimension,mean_joint_negative_log_likelihood,mean_squared_mahalanobis,mean_squared_mahalanobis_per_dimension,chi_square_pit_mean,chi_square_pit_ks_distance,chi_square_qq_correlation,chi_square_expected_p50,empirical_mahalanobis_p50,chi_square_expected_p90,empirical_mahalanobis_p90,above_chi_square_p90_rate,chi_square_expected_p95,empirical_mahalanobis_p95,above_chi_square_p95_rate,chi_square_expected_p99,empirical_mahalanobis_p99,above_chi_square_p99_rate
```

Every diagnostic is calculated from predictions made by a Gaussian trained on
the other physical drive. The marginal CSV contains one row per drive/station
and one recomputed overall row per station. The multivariate CSV contains one
row per drive and one recomputed overall row. Per-vector chi-square reference
probabilities use 21 degrees of freedom.

`gaussian_adequacy_summary.json` records hashes of the four consumed v0.6.0
files, the canonical grid, pooled and per-drive coverage, worst station-wise
shape diagnostics, Mahalanobis calibration, and scientific limitations. No
formal iid normality p-value or post-hoc acceptance gate is reported because
the sequential pair rows are correlated and no threshold was predeclared.
All six files contain or derive from private BMW measurements and must remain
outside version control.

## v0.7.2 conditional-feature audit outputs

The v0.7.2 command accepts the raw MCAP set only when its basenames exactly
match the accepted v0.5.0 manifest hashed by the v0.6.0 residual dataset. It
also requires an explicit `--speed-source`; it never changes speed sources
automatically. It writes exactly:

```text
conditional_features.csv
conditional_feature_recording_summary.csv
conditional_feature_audit.png
conditional_feature_summary.json
```

CSV headers and column order are fixed:

```text
conditional_features.csv:
recording_id,drive_id,pair_index,estimate_message_index,estimate_source_time_ns_private,feature_state,failure_codes,speed_source,speed_is_signed,speed_mps,speed_evaluation_method,speed_displacement_m,speed_displacement_interval_ms,speed_previous_target_timestamp_ns_private,speed_current_target_timestamp_ns_private,speed_previous_lower_timestamp_ns_private,speed_previous_upper_timestamp_ns_private,speed_current_lower_timestamp_ns_private,speed_current_upper_timestamp_ns_private,speed_previous_interpolation_span_ms,speed_current_interpolation_span_ms,estimated_mean_abs_curvature_per_m,estimated_curvature_delta_per_m,confidence_near_mean,confidence_middle_mean,confidence_far_mean,confidence_minimum,confidence_floor_fraction,confidence_lateral_jump_detected,confidence_bucket_count,confidence_native_start_station_m,confidence_native_end_station_m

conditional_feature_recording_summary.csv:
recording_id,drive_id,mcap_filename_private,status,residual_vector_count,feature_ready_count,feature_ready_fraction,estimate_message_count,speed_source,speed_is_signed,speed_message_count,valid_speed_sample_count,usable_speed_sample_count,speed_distinct_timestamp_count,speed_duplicate_timestamp_group_count,speed_duplicate_message_count,speed_coalesced_duplicate_message_count,speed_conflicting_timestamp_group_count,speed_discarded_conflicting_message_count,maximum_speed_timestamp_multiplicity,median_speed_previous_interpolation_span_ms,median_speed_current_interpolation_span_ms,maximum_speed_previous_interpolation_span_ms,maximum_speed_current_interpolation_span_ms,failure_counts
```

`conditional_features.csv` contains one row for every canonical v0.6.0
residual vector, including rows whose features are unavailable. An EDP message
is resolved only by its exact recording-local message index, and its source
timestamp must reconcile with residual provenance. Valid signed longitudinal
speed is evaluated at that timestamp by exact match or recording-local linear
interpolation only when `direct_longitudinal_signal` is explicitly selected.

When `odometry_50ms_displacement` is selected, rear-axle position is evaluated
at the EDP source epoch and exactly 50 ms earlier. Each pose is independently
interpolated with the explicitly configured maximum bracket (50 ms in the
accepted gap-50 audit), and Euclidean displacement is divided by 0.05 s. The
result is unsigned, so reverse-motion direction is not
observable. Both interpolation brackets and endpoint targets are retained in
the per-vector evidence. Extrapolation and cross-recording interpolation are
forbidden in either mode.

Before odometry interpolation, messages are grouped by their state timestamp.
A duplicate group is coalesced only when every `x_position`, `y_position`, and
`yaw_angle` value is exactly equal. The earliest MCAP chronology item is kept
only as an identical representative. A group containing any pose conflict is
discarded in full; no first/latest-message rule is used. Per-recording and
aggregate summaries expose distinct timestamps, duplicate groups and messages,
coalesced duplicates, conflicting groups, discarded messages, and maximum
timestamp multiplicity.

Curvature uses the validated provisional curvature-rate spline interpretation.
Confidence belongs to the selected KEEP_LANE candidate and remains piecewise
constant in its native 5 m spline buckets. Ego-relative bin centres from
0–100 m are mapped back to native station before lookup. Empty vectors,
out-of-range values, and incomplete native coverage remain explicit failures;
confidence is never padded with zero.

The six intended model fields are `speed_mps`,
`estimated_mean_abs_curvature_per_m`, `estimated_curvature_delta_per_m`, and
the near/middle/far confidence means. Drive ID is retained only for held-out
grouping. `conditional_feature_summary.json` records availability and failure
counts, hashes, temporal rules, feature definitions, and that no conditional
model or reduced cohort has been created. Exit code `0` means complete feature
coverage; exit code `3` means the audit was written but is incomplete. All four
files contain or derive from private BMW measurements and must remain outside
version control.

## v0.8.0 conditional Gaussian outputs

The v0.8.0 command accepts only the reviewed v0.7.2 odometry gap-50 audit and
the exact v0.6.0 Gaussian directory named by that audit's SHA-256 hashes. It
writes exactly:

```text
conditional_cohort.csv
conditional_cohort_exclusions.csv
conditional_cohort_summary.json
conditional_gaussian_evaluation.csv
conditional_gaussian_station_evaluation.csv
conditional_gaussian_vector_evaluation.csv
conditional_gaussian_model.json
conditional_gaussian_comparison.png
conditional_gaussian_summary.json
```

`conditional_cohort.csv` retains the canonical residual provenance, all 21
H100 residuals, and the six finite conditional features. The row set is chosen
only by `feature_state == ready`; residual values are not used for selection.
`conditional_cohort_exclusions.csv` retains the exact key and failure code for
each omitted boundary row. Only pair-zero
`speed__odometry_reference_time_outside_coverage` exclusions are accepted.

`conditional_gaussian_evaluation.csv` contains conditional and unconditional
rows for every held-out physical drive plus one recomputed overall row for
each model. Both models are trained and tested on identical rows. The six
features are standardized using training-fold statistics only. The comparator
is refitted on the reduced cohort rather than copied from the 1,777-vector
v0.6.0 evaluation.

`conditional_gaussian_station_evaluation.csv` reports station RMSE, bias, and
marginal 95% coverage for both models. Per-vector held-out NLL, Mahalanobis
distance, and mean-prediction RMSE are recorded in
`conditional_gaussian_vector_evaluation.csv`. Overall and station metrics are
recomputed from these held-out vector predictions, never averaged from
per-recording summaries.

`conditional_gaussian_model.json` is the final descriptive all-cohort fit. It
stores training feature means/scales, a 21-vector intercept, a 6×21 matrix of
standardized-feature coefficients, and one 21×21 condition-invariant
covariance. The summary reports conditional-minus-unconditional held-out
metrics and explicit improvement booleans; it does not claim improvement when
the deltas are unfavorable. All outputs are private BMW-derived artifacts and
must remain outside version control.
