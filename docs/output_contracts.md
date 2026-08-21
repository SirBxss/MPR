# v0.4.5 output contracts

These contracts describe diagnostics, not training labels. EDP–RLMB
disagreement is not ground-truth lane-estimation error, and RLMB is a
pseudo-reference candidate rather than physical ground truth.

## v0.12.1 expanded-corpus inventory outputs

The inventory command writes exactly:

```text
mcap_inventory.csv
topic_compatibility.csv
recording_continuity.csv
proposed_session_groups.json
corpus_inventory_summary.json
corpus_inventory_diagnostics.png
```

CSV headers and order are fixed:

```text
mcap_inventory.csv:
recording_id,drive_id,relative_path_private,mcap_basename_private,file_size_bytes,sha256,drive_map_covered,readable,empty,duplicate_of_recording_id,usable,chronological_index_within_drive,filename_start_hint_private,filename_end_hint_private,filename_duration_ms,mcap_identifier_hint,internal_start_log_time_ns_private,internal_end_log_time_ns_private,internal_duration_ms,first_estimate_source_time_ns_private,last_estimate_source_time_ns_private,estimate_source_duration_ms,estimate_source_timestamp_count,estimate_missing_source_timestamp_count,estimate_source_timestamps_strictly_increasing,required_topics_schemas_compatible,filename_internal_time_disagreement,filename_order_disagrees_with_internal_order,failure_codes,exclusion_codes

topic_compatibility.csv:
recording_id,drive_id,mcap_basename_private,topic_role,topic,present,message_count,expected_schema_name,schema_names,schema_encodings,message_encodings,schema_compatible,failure_codes

recording_continuity.csv:
drive_id,left_recording_id,right_recording_id,left_mcap_basename_private,right_mcap_basename_private,internal_log_gap_ms,relevant_source_gap_ms,filename_gap_ms,filename_internal_gap_disagreement,identifier_delta,identifier_discontinuity,same_drive_label,internal_log_times_compatible,relevant_source_timestamps_strictly_increasing,source_gap_within_200_ms,required_topics_schemas_compatible,overlap_detected,timestamp_reset_detected,pair_index_boundary_state,stitchable,rejection_codes
```

Discovery is recursive and case-insensitive for the `.mcap` suffix.
`recording_id` is a deterministic opaque identifier; `drive_id` is derived
only by replacing the exact private-map label with a sorted opaque identifier.
Duplicate JSON keys, duplicate discovered basenames, missing basenames, and
extra map entries are retained in the summary. A partial map never gains an
inferred assignment.

Required roles are estimate (`/adp/estimated_drive_paths`), map
(`/adp/road_lane_map_based`), and odometry (`/adp/odometry`) with their accepted
Protobuf schemas. Each topic row reports presence, summary message count, and
the exact sorted schema/encoding signature. A file is unusable when it is
unmapped, unreadable, empty, byte-duplicate, lacks complete strictly increasing
estimate source timestamps, or fails a required topic/schema check. SHA-256 is
computed from file bytes. `duplicate_count` counts later redundant copies in
deterministic basename/path order; no copy disappears from the inventory.

Within each explicit drive, files are sorted by first relevant estimate source
time, then internal MCAP start time, with filename/path only as deterministic
tie-breakers. Filename start/end times and the numeric MCAP identifier are
diagnostic hints only. Duration or adjacent-gap disagreement over one second is
flagged. Identifier discontinuity is reported but is not a stitch gate.

Every row in `recording_continuity.csv` represents two adjacent files within
one mapped drive. An edge is stitchable only if both files are usable, the
explicit drive label matches, the next internal MCAP start is greater than or
equal to the previous internal end, relevant estimate source time increases
strictly, the positive relevant source gap is at most 200 ms, and required
topic/schema signatures match. Equal internal endpoints are valid touching
boundaries; only a negative internal gap is an overlap. Missing evidence,
overlaps, resets, excessive gaps, and schema differences reject the edge.
Recording-local pair-index reset is explicitly allowed and is not used as a
gate.

`proposed_session_groups.json` lists connected blocks formed only by
stitchable edges, every file exclusion, and all drive-map coverage failures. It
states that the private map was not modified and no frame stitching occurred.
`corpus_inventory_summary.json` distinguishes MCAP file count, provisional
continuous-block count, physical drive count, total internal duration, usable
internal duration, stitchable and rejected mapped-drive boundaries, redundant
duplicate count, unreadable/empty counts, and required-topic/schema failure
counts. Status is `incomplete` when exact coverage or any file-usability gate
fails; the command then returns 3 after writing the reports.

All six files are deterministic for unchanged inputs and contain private
metadata. They must remain outside version control. A complete audit points to
the v0.5.2 native projection-alignment phase. Any later sequence-contract work
may group verified contiguous frames only while preserving every frame's
original `recording_id`; it must not change the native target or introduce
delta-t compensation as model input.

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

## v0.5.2 accepted native projection-alignment batch

The workflow processes every MCAP independently and writes the historical
four-file native projection set under each
`recordings/recording_###/` directory. The batch root writes exactly:

```text
recording_alignment_summary.csv
alignment_pair_audit.csv
alignment_station_comparison.csv
alignment_batch_comparison.png
alignment_batch_summary.json
batch_manifest.json
batch_output_provenance.json
```

Both summary and manifest use:

```text
version: 0.5.2
purpose: exact_manifest_projection_based_reference_alignment_validation
alignment_semantics: v0.5.0_native_spatial_projection
explicit_ego_pose_motion_compensation_applied: false
source_delta_used_numerically_for_alignment: false
accepted_for_modeling: true
```

The expected file count is an explicit arbitrary positive integer. The exact
private basename map must cover every resolved file once, including duplicate
JSON-key detection. Recording and opaque drive IDs are deterministic. Pairing
is complete-stream, recording-local mutual-nearest source time with no default
timestamp gate. Source delta is diagnostic evidence only and never moves a
path. No odometry is decoded or applied.

Native alignment projects the EDP station-zero footpoint onto the paired RLMB
path and samples equal forward arc-length offsets from that projection. RLMB is
the best available pseudo-reference. H100 must remain a subset of H60. Every
model-eligible H100 pair must have exactly the finite canonical 21 rows at
`0, 5, ..., 100 m`; available-case rows are not model-eligible. Pairing never
crosses MCAP boundaries, and this workflow performs no residual export,
feature extraction, sequence stitching, or model training.

`source_files_sha256` in the summary and manifest hashes the exact private map,
`corpus_inventory_summary.json`, `recording_continuity.csv`, and
`proposed_session_groups.json`. `batch_output_provenance.json` repeats those
source hashes and hashes the other six generated batch-root outputs, including
the finalized summary and manifest.

Downstream native-alignment validation accepts the historical v0.5.0
`ten_mcap_projection_based_reference_alignment_validation` contract and this
v0.5.2 contract. It continues to reject every v0.5.1 motion-compensated output.

## v0.12.2 EDP topology-semantics and alignment-quality audit

The read-only audit writes:

```text
topology_message_audit.csv
topology_recording_summary.csv
topology_session_summary.csv
topology_transition_audit.csv
alignment_quality_outliers.csv
topology_semantics_summary.json
topology_alignment_quality_diagnostics.png
topology_audit_manifest.json
topology_audit_provenance.json
lineage/expanded_corpus_inventory_v0121/*
```

The message CSV contains one row per EDP message and reports raw-wire enum
presence/value, descriptor numeric value and readable name, estimator and
selected-path state, existing geometry/failure evidence, source delta, anchors,
residual RMS, and unchanged H60/H100 eligibility. Recording and session CSVs
contain deterministic distributions and fixed source-delta quantiles.

The transition CSV retains every adjacent within-MCAP edge and every accepted
within-session MCAP-boundary edge. The outlier CSV lists every currently
H60-eligible pair with anchor distance strictly greater than 1.0 m. That value
is an audit listing threshold, not an eligibility rule, and is not selected
from Gaussian or AIOHMM performance.

Semantic classification uses embedded protobuf enum descriptors, raw-wire
equality, and existing validation code—not timing. SENSOR_TOPOLOGY and
LANE_MAP remain distinct enum categories, while `independence_from_rlmb` is
explicitly `unknown`; the audit does not claim statistical or upstream
independence. Unproven fusion status and upstream sharing with RLMB also remain
`unknown`. `audit_build_blockers` controls audit completeness, and downstream
modeling constraints are reported separately. Failure and exclusion-reason
counts are non-mutually-exclusive, so one message may contribute to multiple
reasons. All six exact v0.12.1 inventory
outputs are copied byte-for-byte under `lineage/` and hashed. The private map
is hashed but not copied or added to Git.

## v0.13.0 quality-gated expanded sequential dataset

The command writes:

```text
expanded_profile_dataset.npz
profile_eligibility_audit.csv
sequence_manifest.csv
sequence_summary_by_drive.csv
cross_mcap_stitching_audit.csv
exclusion_reason_summary.csv
expanded_sequence_contract.json
train_only_standardization_metadata.json
expanded_sequence_diagnostics.png
expanded_sequence_manifest.json
expanded_sequence_provenance.json
```

`expanded_profile_dataset.npz` is a deterministic, pickle-free archive with
fixed ZIP metadata. It contains physical-unit `residuals_m [N,21]`, conditions
`[N,6]`, canonical stations, timestamps, original recording/drive/MCAP IDs,
quality-gated sequence IDs, pair/message indices, and eligibility fields.

Eligibility requires SENSOR_TOPOLOGY, existing H100 eligibility, exactly the
finite `0,5,...,100 m` residual vector, anchor distance `<= 1.0 m`, valid
estimator/estimate/map states, and finite v0.9 six-feature values. The 1.0 m
limit is a pre-model geometry rule. No heading threshold is applied.

Sequences split on drive/topology changes, any ineligible observation, anchor
gate failure, non-monotonic time, gaps above the declared cadence, or an
unaccepted MCAP boundary. Cross-MCAP stitching additionally requires accepted
v0.12.1 continuity and eligible immediate endpoint profiles. The original
recording ID remains attached to every stitched frame. The stitching audit
retains both endpoint exclusion codes as well as the boundary rejection code.

The standardization JSON is deliberately unfitted: future transforms must be
fit on training drives only after a separately reviewed split assignment.
The manifest selects no split or hyperparameters. Provenance hashes every
generated artifact, all accepted alignment/topology inputs, and the inherited
per-MCAP SHA-256 map from the v0.12.1 inventory.

## v0.5.1 optional reference-alignment sensitivity

The optional motion-alignment command writes exactly:

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

The v0.6.0 command accepts a complete historical v0.5.0 or current v0.5.2
native projection-alignment batch. It rejects v0.5.1 motion compensation.
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

## v0.9.0 common sequential dataset outputs

The command accepts only a complete v0.8.0 frozen conditional cohort with the
exact BMW condition schema v1 and canonical H100 residual grid. It writes
exactly:

```text
sequential_dataset.npz
sequence_summary.csv
sequence_frame_index.csv
drive_fold_manifest.json
drive_fold_standardizers.json
sequence_dataset_diagnostics.png
sequential_dataset_summary.json
```

`sequential_dataset.npz` is raw physical-unit data. Its main arrays are
`conditions[B,T,6]`, `residuals_m[B,T,21]`, `valid_mask[B,T,21]`, and
`lengths[B]`. It also stores sequence, recording, drive, pair, message, and
private source-time provenance. Padding is zero for numeric model arrays,
false for the validity mask, and `-1` for temporal indices. Active v0.9.0 H100
frames always contain all 21 stations.

`sequence_summary.csv` records each gap decision and sequence duration.
`sequence_frame_index.csv` maps every tensor position back to its immutable
recording/pair key. No frame may be lost, duplicated, reordered within a
recording, or joined across an MCAP boundary.

`drive_fold_manifest.json` is leave-one-physical-drive-out development
evidence. `drive_fold_standardizers.json` contains one transform per fold,
fitted only on that fold's training drives. Conditions and each residual
station have separate mean/scale values. The raw NPZ is never silently
standardized.

The diagnostic PNG reports sequence support, retained intervals, and raw
lag-one residual correlation. It is descriptive and fits no model. The summary
marks the current corpus as development-only, reports that no untouched final
test is present, and requires additional independent drives before final model
selection. All outputs are private BMW-derived artifacts and remain outside
version control.

## v0.10.0 sequence-contract Gaussian outputs

The command accepts only the exact seven-file v0.9.0 output set. It verifies
every recorded source hash, recomputes each training-drive standardizer, and
reconciles every fold sequence before fitting. It writes exactly:

```text
gaussian_sequence_evaluation.csv
gaussian_sequence_station_evaluation.csv
gaussian_sequence_frame_evaluation.csv
gaussian_sequence_fold_models.json
gaussian_sequence_model.json
gaussian_sequence_diagnostics.png
gaussian_sequence_summary.json
```

The evaluation CSV has one row per held-out physical drive and one recomputed
overall cross-validated row. It records standardized and Jacobian-adjusted
physical joint NLL, squared Mahalanobis distance, sample-mean RMSE, multivariate
energy score, marginal 95% coverage, and observed/generated lag-one dependence.
Overall metrics are recomputed from all out-of-fold frames and samples.

The station CSV reports sample-mean RMSE/bias, coverage, observed lag-one
correlation, and the generated median and 5th/95th percentile correlations.
The frame CSV maps likelihood, Mahalanobis, RMSE, and energy evidence back to
the immutable sequence/recording/drive/pair provenance.

`gaussian_sequence_fold_models.json` stores each held-out fold fit and its
training provenance. `gaussian_sequence_model.json` combines an all-development
training standardizer with the descriptive post-evaluation model. It is
explicitly not an untouched final model.

Sampling uses the recorded count and seed. Gaussian samples preserve spatial
covariance across H100 stations but are conditionally independent between
frames, so temporal dependency order is exactly zero. The energy score and
lag-one metrics form the common sample-based evaluation contract for AIOHMM
and RC-GAN. All seven outputs are private BMW-derived artifacts and remain
outside version control.

## v0.11.0 sequence-contract AIOHMM outputs

The command accepts the same exact seven-file v0.9.0 directory as v0.10.0. It
reuses the strict hash, fold-membership, and training-standardizer verifier and
writes exactly:

```text
aiohmm_sequence_evaluation.csv
aiohmm_sequence_station_evaluation.csv
aiohmm_sequence_frame_evaluation.csv
aiohmm_sequence_state_evaluation.csv
aiohmm_sequence_restart_evaluation.csv
aiohmm_sequence_fold_models.json
aiohmm_sequence_model.json
aiohmm_sequence_diagnostics.png
aiohmm_sequence_summary.json
```

`aiohmm_sequence_evaluation.csv` retains the v0.10.0 common sample-mean RMSE,
energy score, marginal coverage, and observed/generated lag-one metrics. It
adds teacher-forced standardized/physical joint NLL, posterior entropy and
occupancy, condition-dependent transition variation, expected dwell estimates,
and AR coefficient bounds. The overall row is recomputed from all out-of-fold
frames and samples. AIOHMM NLL is secondary and is not a common RC-GAN metric.

`aiohmm_sequence_station_evaluation.csv` uses the exact v0.10.0 station sample
metrics and adds the fold-model median AR coefficient at each station.
`aiohmm_sequence_frame_evaluation.csv` maps filtering likelihood increments,
sample metrics, posterior maximum state/probability, and posterior entropy back
to immutable sequence, recording, drive, and pair provenance.

`aiohmm_sequence_state_evaluation.csv` reports test-posterior and descriptive
all-data state occupancy, initial probabilities, zero-condition intercept-profile
RMS, AR range, covariance eigenvalue floor, self-transition behavior, expected
dwell, and transition-row entropy. State indices are deterministic canonical
diagnostic labels. They are exchangeable latent labels and must not be described
as physical road or driving regimes without separate evidence.

`aiohmm_sequence_restart_evaluation.csv` contains every deterministic restart,
including its seed, completion/convergence status, warnings, occupancy, AR
bound, training joint likelihood, selection flag, and canonicalized transition
and occupancy differences from the selected restart. Restarts share one fixed
architecture and are selected only by training joint likelihood. Held-out drives
do not select restarts, state count, transforms, or hyperparameters.

`aiohmm_sequence_fold_models.json` stores the selected fit for every physical-
drive fold. `aiohmm_sequence_model.json` combines an all-development-data
standardizer with the descriptive post-evaluation model; it is not an untouched
final model. Density evaluation conditions on the observed preceding residual,
whereas sampling recursively uses the preceding generated residual. The summary
records this teacher-forced/free-running distinction, the fixed exploratory
state count, training-only marginal sequence-reset prior, emission-parameter
pooling, covariance pooling/shrinkage, all seeds, output hashes, and the
two-drive development-only limitation. All nine outputs are private BMW-derived
artifacts and remain outside version control.
