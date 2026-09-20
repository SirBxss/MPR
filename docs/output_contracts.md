# v0.4.5 output contracts

These contracts describe diagnostics, not training labels. EDP–RLMB
disagreement is not ground-truth lane-estimation error, and RLMB is a
pseudo-reference candidate rather than physical ground truth.

## Proposed batch02 recording-pair feasibility output

The new `python -m lane_residuals.cli.recording_pair_feasibility` writes exactly
`recording_pair_feasibility.json`, after its separately required review GO.
It is not a v0.17 lock or a v0.18 sensor audit. The binding scope is in
`docs/recording_pair_feasibility_predeclaration.md`.

Top-level keys are exactly:

```text
contract_revision, purpose, status, registration_sha256,
container_context_sha256, runtime_versions, runtime_source_sha256,
raw_hashes_verified, physical_session_provenance, independent_outing_count,
roles_assigned, cohort_lock_created, causal_input_availability_checked,
residuals_computed, interpretation, recordings
```

Revision is `v0.19.0-batch02-recording-pair-feasibility-2026-09-20-a1`;
purpose is `recording_level_geometry_feasibility_without_session_provenance`.
Status is `complete` only when all four files complete; otherwise
`inconclusive`. `raw_hashes_verified` records successful pre-decode verification;
a subsequent file change makes that file inconclusive with null counts.
Physical-session provenance is `unavailable_owner_report_2026-09-20`,
independent outing count is null, and the four role/lock/causal-input/residual
flags are false. A zero-candidate complete inspection is not an execution
failure and says nothing about independent-outing count.

`runtime_versions` has `python`, `mcap`, `mcap-protobuf-support`, `protobuf`,
and `numpy`. The runtime-source fingerprint hashes the UTF-8 bytes of
`json.dumps(mapping, sort_keys=True)` using Python's default separators, where
mapping is every package-relative POSIX `.py` path to its file-byte SHA-256.
It fingerprints available runtime source without importing model modules.
Prior administrative report hashes identify exact immutable input bytes;
all raw hashes are freshly checked before payload processing.

Each recording has exactly `relative_path_private`, `raw_sha256`,
`size_bytes`, `status`, `failure_code`, `counts`. Inconclusive results have a
static failure code and null counts, never a partial-stream aggregate. Complete
results have null failure code and these exact count-object keys:

```text
estimate_message_count, reference_message_count, timestamp_pairing_counts,
pairing_maximum_delta_ns, estimate_topology_counts, estimate_descriptor_counts,
conversion_failure_counts, pair_failure_counts, anchored_h100_topology_counts,
h100_pair_count, anchored_h100_pair_count, sensor_anchored_h100_pair_count
```

`timestamp_pairing_counts` contains integer lengths for the eight canonical
audit fields: `pairs`, `rejected_by_gate`, `unmatched_first_positions`,
`unmatched_second_positions`, `missing_time_first_positions`,
`missing_time_second_positions`, `ambiguous_first_positions`, and
`ambiguous_second_positions`. No source timestamp arrays or message indices
are exported. The maximum-delta field is null, explicitly preserving the
canonical intake's ungated matching; it is not the sensor audit's 50 ms rule.
The remaining dictionary fields map enum names, descriptor hashes or failure
codes to integer counts. Their categories can overlap across dictionaries.

The three nested candidate counts are defined in the predeclaration. They
are geometry/anchor/topology feasibility only, not v0.17 eligible frames or
outings. No raw coordinates, anchor distances, confidence/condition values,
residuals, distribution statistics, model scores or role assignments appear.
Temporary working geometry is not part of the artifact.

Exit 0 means a complete four-file inspection, including a complete zero result.
Exit 3 means the JSON records at least one inconclusive file. Exit 2 means
preflight/command failure; absence of a complete JSON after interruption or
process termination never supports a negative scientific conclusion.

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

## v0.13.1 accepted-boundary odometry-context dataset

v0.13.1 leaves every v0.13.0 artifact untouched and writes a new directory:

```text
expanded_profile_dataset.npz
profile_eligibility_audit.csv
sequence_manifest.csv
sequence_summary_by_drive.csv
cross_mcap_stitching_audit.csv
boundary_odometry_context_audit.csv
exclusion_reason_summary.csv
v0130_parity_audit.json
expanded_sequence_contract.json
train_only_standardization_metadata.json
expanded_sequence_diagnostics.png
expanded_sequence_manifest.json
expanded_sequence_provenance.json
```

The only cross-MCAP calculation is the existing unsigned odometry displacement
between an EDP source epoch and exactly 50 ms earlier. The immediately previous
MCAP may supply odometry samples only across an accepted same-drive v0.12.1
edge, with identical expected topic/schema, strict cross-boundary odometry
timestamps, brackets no wider than the established 50 ms tolerance, and no
extrapolation. Both contributing private basenames and every interpolation
sample timestamp are retained in the boundary audit and archive evidence.

EDP paths, residuals, curvature, and confidence features are never interpolated
across files. SENSOR_TOPOLOGY/H100/geometry/finite-value eligibility, the 1.0 m
anchor gate, absence of a heading gate, and the six feature definitions are
unchanged. A restored endpoint is stitched only when it becomes fully eligible;
every rejected candidate retains all applicable rejection codes.

`v0130_parity_audit.json` compares canonical recording/pair keys and requires
the residual and six-feature bytes of every v0.13.0 profile to be unchanged.
Counts are observed outputs, not enforced reference constants. Exclusion-reason
counts are non-mutually-exclusive. Standardization remains unfitted and no
split, hyperparameter, or model is selected. Provenance hashes the corrected
v0.12.2 semantics, v0.13.0 baseline, live 67-MCAP corpus, and generated files.

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

## v0.14.0 expanded drive-grouped Gaussian outputs

The command accepts only the exact hash-reconciled v0.13.1 output directory.
It reconstructs padded sequences without losing per-frame recording or MCAP
provenance and writes exactly:

```text
drive_grouped_evaluation_contract.json
gaussian_grouped_evaluation.csv
gaussian_grouped_station_evaluation.csv
gaussian_grouped_frame_evaluation.csv
gaussian_grouped_models.json
gaussian_grouped_diagnostics.png
gaussian_grouped_summary.json
```

`drive_grouped_evaluation_contract.json` fixes four leave-one-clean-recording-
group-out folds over technical groups 001--004. The groups are separated
portions of one longer same-day outing and do not support journey-level
generalization claims. Each embedded standardizer is fitted only on the other
three clean groups. Random frame splits are forbidden. Drives
005--008 remain a separate mixed-source supplementary cohort and never
contribute to fitting or primary model comparison.

`gaussian_grouped_evaluation.csv` contains eight primary fold rows (four per
model), two pooled primary rows, and two supplementary transfer rows. The
unconditional and six-feature conditional Gaussian use identical frames,
folds, transforms, sample counts, and common random seeds. Sample-mean RMSE,
frame-wise energy score, length-normalized complete-sequence energy score,
marginal 95% coverage, and lag-one error are common cross-family metrics;
physical NLL and Mahalanobis distance are Gaussian diagnostics. The sequence
score flattens each active `[time, 21]` block and divides Euclidean distances by
`sqrt(sequence_length * 21)` before averaging.

The station CSV retains H100 spatial metrics, while the frame CSV maps every
out-of-fold or supplementary score back to exact sequence, recording, drive,
MCAP basename, pair index, message index, and private source timestamp.
`gaussian_grouped_models.json` stores every fold model plus one descriptive fit
on all clean development drives. That fit is not an untouched final model.

The summary reports both pooled-frame and equal-drive macro metrics. Conditional
minus unconditional macro deltas use a negative-is-better convention. No
hyperparameter search or final model selection is authorized. All outputs are
private BMW-derived artifacts and remain outside version control.

## v0.15.0 expanded clean-drive AIOHMM outputs

The command accepts only the exact hash-reconciled v0.13.1 directory and the
exact seven-file v0.14.0 Gaussian result directory. It revalidates source hashes,
clean-drive folds, training-only transforms, sample count, and seed, then writes:

```text
expanded_aiohmm_evaluation.csv
expanded_aiohmm_station_evaluation.csv
expanded_aiohmm_frame_evaluation.csv
expanded_aiohmm_state_evaluation.csv
expanded_aiohmm_restart_evaluation.csv
expanded_aiohmm_fold_models.json
expanded_aiohmm_model.json
expanded_aiohmm_diagnostics.png
expanded_aiohmm_summary.json
```

The evaluation CSV contains four clean held-out-group rows, one pooled clean
row, and one supplementary mixed-fragment transfer row. It reports the exact
v0.14 common metrics plus observed-history joint density, posterior-state, transition,
dwell, and AR diagnostics. The frame CSV preserves recording and private MCAP
provenance. The state and restart CSVs expose occupancy, convergence, and
deterministic training-likelihood restart selection.

The fixed state count is two. Reset frames use the separate training-only reset
distribution and are excluded from state-specific AR emission/covariance
updates. Generalized-EM M-steps are backtracked until raw training likelihood is
non-decreasing and the posterior occupancy floor is respected; otherwise the
fit stops and reports nonconvergence. The mixed cohort never enters fitting or
primary comparison.

`expanded_aiohmm_summary.json` records deltas against the conditional Gaussian,
paired group-level sequence-energy evidence, constraint-boundary activation,
the one-outing independence limitation, individual development checks, and a
result classification. Workflow success does not imply scientific acceptance.
The reviewed run is classified as
`temporal_dependence_improved_but_full_generative_acceptance_not_met`.

## v0.15.1 one-state conditional-AR ablation outputs

The command accepts only the exact hash-reconciled v0.13.1 directory, exact
v0.14.0 Gaussian directory, and complete reviewed v0.15.0 AIOHMM directory.
It verifies the same source lineage, four folds, fold-training transforms,
Monte Carlo protocol, restart count, and all non-architectural AIOHMM
hyperparameters before creating the output directory. It writes exactly:

```text
one_state_ar_evaluation.csv
one_state_ar_station_evaluation.csv
one_state_ar_frame_evaluation.csv
one_state_ar_state_evaluation.csv
one_state_ar_restart_evaluation.csv
one_state_ar_fold_models.json
one_state_ar_model.json
one_state_ar_diagnostics.png
one_state_ar_summary.json
```

The one component uses the unchanged v0.15 station-wise AR(1) emission,
training-only reset marginal, spatial covariance regularization, observed-
history likelihood, and free-running sampler. Its posterior occupancy and
transition probability are identically one by construction; they are retained
in the tabular contract for parity but are not interpreted as hidden-state
evidence. The focused plot therefore replaces occupancy/transition panels with
three-model macro and paired-group sequence-energy comparisons plus the fitted
AR coefficient profile.

`one_state_ar_summary.json` records one-state-minus-conditional-Gaussian deltas
to isolate the autoregressive contribution and symmetric one-state/two-state
deltas to isolate the latent-switching contribution. Every reported delta uses
the negative-is-better convention. It also records paired technical-group
sequence-energy counts, exact hashes of both baselines, and an explicit latent-
switching classification. These are within-one-outing development diagnostics;
they do not authorize journey-level generalization or final model selection.

## v0.15.2 two-state convergence-audit outputs

The command accepts only the exact hash-reconciled v0.13.1 directory and the
complete v0.14.0, v0.15.0, and v0.15.1 result directories. Before creating
output, it verifies their filename sets, SHA-256 hashes, source lineage, folds,
training-only transforms, Monte Carlo protocol, and model configurations. The
candidate must differ from v0.15.0 only in the fixed convergence criterion and
tolerance. It writes exactly:

```text
two_state_convergence_evaluation.csv
two_state_convergence_station_evaluation.csv
two_state_convergence_frame_evaluation.csv
two_state_convergence_state_evaluation.csv
two_state_convergence_restart_evaluation.csv
two_state_convergence_comparison.csv
two_state_convergence_fold_models.json
two_state_convergence_model.json
two_state_convergence_diagnostics.png
two_state_convergence_summary.json
```

The five common evaluation artifacts and two model artifacts retain the shared
autoregressive schema. The restart CSV additionally records the last raw
standardized log-probability improvement, its absolute per-training-frame
value, and the configured convergence measure. The comparison CSV contains one
selected row for each of four held-out-group fits plus the descriptive
all-clean fit, with old/new iteration counts, convergence states, training
joint log-probabilities, and the corrected final stopping measure.

`two_state_convergence_summary.json` records exact hashes of both frozen
autoregressive references, the two permitted configuration differences,
selected-fit convergence diagnostics, macro deltas against v0.15.0 and
v0.15.1, and paired-group win counts and deltas for all five sample-based
metrics. Its classification first states whether nonconvergence remains, then
whether the corrected two-state fit supplies any sample-metric support for
latent switching. Negative model deltas always mean better. The diagnostic
does not change the AR boundary, introduce a model family, authorize final
selection, or estimate independent-journey generalization.

## v0.15.3 one-state AR-boundary-sensitivity outputs

The command accepts only the exact hash-reconciled v0.13.1 dataset and the
complete v0.14.0, v0.15.0, reviewed v0.15.1, and reviewed v0.15.2 result
directories. All references and their transitive lineage are validated before
output is created. The CLI configuration must exactly reproduce v0.15.1 at
the 0.98 baseline. It then fits the fixed 0.99, 0.995, and 0.999 candidates,
changing only `maximum_absolute_autoregression`.

The top-level output is exactly:

```text
candidates/
  one_state_ar_cap_0_990/
  one_state_ar_cap_0_995/
  one_state_ar_cap_0_999/
ar_boundary_model_comparison.csv
ar_boundary_fold_comparison.csv
ar_boundary_station_comparison.csv
ar_boundary_sensitivity_diagnostics.png
ar_boundary_sensitivity_summary.json
```

Each candidate directory contains the shared nine-file one-state
evaluation/model contract. Its summary records the one permitted difference
from v0.15.1 and the exact v0.15.1 hashes. The reviewed 0.98 files are not
copied or regenerated.

`ar_boundary_model_comparison.csv` contains seven macro rows: unconditional
Gaussian, conditional Gaussian, corrected two-state AIOHMM, reviewed
one-state 0.98, and the three candidate ceilings. This is the consolidated
comparison required before paper reporting. `ar_boundary_fold_comparison.csv`
contains the same seven models on each of four technical groups.
`ar_boundary_station_comparison.csv` contains the four one-state ceilings on
all 21 H100 stations, including both reference-cap and candidate-cap binding
flags. The figure visualizes macro deltas, calibration, station profiles, and
remaining boundary contact.

The summary reports pairwise candidate deltas against all three frozen model
roles, paired group directions, the predeclared conservative checks, and the
smallest development-supported ceiling when one exists. The recorded pooled
coverage hypothesis of approximately 0.918 is diagnostic and is not an
acceptance or selection target. Command success means the sensitivity audit
completed; it never authorizes a final model, journey-level generalization, or
planner benefit.

## v0.15.4 development-model freeze and sampling outputs

The freeze command accepts only the complete reviewed v0.15.1 one-state
directory and v0.15.3 AR-boundary directory. It validates their exact file
sets, recursive hashes, candidate configurations, convergence states, and the
failed strict performance decision before creating output. The selected
ceiling is fixed at 0.99 in code; it cannot be chosen through the CLI.

The freeze output is exactly:

```text
development_residual_model.json
development_model_freeze_summary.json
```

`development_residual_model.json` contains the all-clean one-state model and
its physical-unit standardizer. It records the six condition features in
required order, the signed 21-station H100 residual contract, the free-running
sequence-reset sampling contract, hashes of every v0.15.1 and v0.15.3 source
file, and the scientific limitations. The file is authorized for development
planner experiments only. It does not authorize final model selection,
independent-journey generalization, or a planner-benefit claim.

`development_model_freeze_summary.json` records the fixed structural rationale:
0.99 is the smallest tested nonbinding ceiling above the identical interior
fit shared by 0.99, 0.995, and 0.999. It retains the reviewed 0.98 comparison,
the strict v0.15.3 failure, both variants' binding-station evidence, the frozen
model hash, and the next phase. This is not held-out performance selection.

The sampling command accepts that exact frozen model plus one NPZ containing
exactly:

```text
conditions       float array [B,T,6], physical units, zero padding
lengths          integer array [B]
sequence_ids     unique nonempty string array [B]
feature_names    exact BMW condition schema v1 string array [6]
```

It writes exactly:

```text
sampled_residual_sequences.npz
sampled_residual_sequences_summary.json
```

The sample NPZ contains `residual_samples_m` with shape `[S,B,T,21]`, plus
`lengths`, `stations_m`, `sequence_ids`, and `feature_names`. Active values are
signed residuals in metres and padded frames are exactly zero. Sampling is
free-running: each generated frame uses generated residual history, and model
state resets once at the start of each input sequence. The summary hashes both
inputs and the sample file and records the seed and sample count. This command
does not modify path geometry or execute a planner.

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

## v0.16.0 reference-planner sensitivity outputs

The scenario builder joins the accepted v0.13.1 profile archive to the v0.5.2
aggregate alignment stations by exact `(recording_id, pair_index)`, retaining
only `drive_001` through `drive_004`. It writes:

```text
reference_planner_scenarios.npz
planner_condition_sequences.npz
reference_planner_scenario_summary.json
```

The scenario NPZ contains physical `conditions[B,T,6]`, feature names,
`lengths[B]`, `nominal_paths_xy_m[B,T,21,2]`, `sequence_ids[B]`, H100 stations,
and source timestamps. Numeric padding is zero. The condition NPZ is the exact
four-array v0.15.4 sampler input. The summary hashes sources and outputs.
Sequences with fewer than two active frames are excluded before either archive
is written. The summary records their IDs and counts and states that the gate
does not use residual values or planner outcomes.

The sensitivity command consumes the scenario NPZ and complete hash-verified
v0.15.4 sample directory. It writes:

```text
reference_planner_frame_metrics.npz
reference_planner_sequence_metrics.csv
reference_planner_sensitivity_summary.json
```

Frame metrics have shape `[3,S,B,T,8]` in arm order `zero`,
`time_shuffled_ar`, `frozen_ar`. The CSV retains every arm/draw/sequence
accumulation metric. The summary records fixed parameters, hashes, shuffle
seed, and paired A2-minus-A1 Monte Carlo-draw intervals while denying BMW,
benefit, global-replay, safety, and journey-generalization claims.

## v0.16.1 unconditional-Gaussian planner-transfer outputs

The sampler consumes the complete exact v0.13.1 and v0.14 directories, the
frozen v0.15.4 development model, the complete accepted A2 sample directory,
and the accepted v0.16 scenario archive. It executes no planner and writes
exactly:

```text
unconditional_gaussian_residual_samples.npz
unconditional_gaussian_residual_samples_summary.json
```

The NPZ uses the v0.15.4 five-array sample schema and contains 128 independent-
frame draws from the stored v0.14 all-clean unconditional Gaussian in physical
metres. Spatial covariance is retained and padding is zero. The summary records
every input/output hash, exact v0.14/v0.15.4 standardizer equality, seed
`20260828`, and per-station A3/A2 means, population standard deviations, mean
differences, and standard-deviation ratios. Marginal diagnostics have no gate.

The transfer command consumes that complete two-file sample directory, the
same accepted scenario NPZ, and the complete immutable v0.16 sensitivity
directory. It runs only A3 and writes exactly:

```text
gaussian_transfer_frame_metrics.npz
gaussian_transfer_sequence_metrics.csv
gaussian_planner_transfer_summary.json
```

Frame metrics have shape `[S,B,T,8]` for `unconditional_gaussian` and retain
the v0.16 metric order. The CSV contains one A3 row per draw and sequence with
the four primary metrics plus secondary accumulation, objective, and envelope
metrics. The summary records exact accepted hashes and content invariants,
the >=20-frame primary p95 set, all-sequence p95 robustness macros, per-sequence
and pooled summaries, A3-minus-A2 `k/N` sign agreement, and an independent
two-sample 20,000-replicate bootstrap using seed `20260829`.

The summary also contains
`deviation_family_length_dependence_qualifier`. This single structured field
records, for both deviation metrics, the equal-sequence difference and relative
difference, reversing sequence IDs, active-frame share, length ranks, and the
smallest longest-sequence prefix containing every reversal. It separately
records the pooled-frame mean-deviation contrast and smoothness `k/N`. Its role
is mandatory post-result interpretation; `changes_predeclared_decision` is
always false. It prevents `full_planner_observable_trade_supported` from being
read without the reviewed cohort qualifier and does not create a new gate.

The full decision requires both smoothness intervals above zero and both
deviation intervals below zero. Smoothness-only and deviation-only outcomes are
named separately. A3-minus-A1 is descriptive. A3-minus-A2 does not isolate
temporal structure, and no output authorizes planner benefit, comfort, safety,
BMW behavior, production readiness, global replay, final model selection, or
journey-level generalization.

## v0.16.2 A2/A3 cross-station structure audit outputs

The audit consumes exactly the accepted v0.15.4 A2 and v0.16.1 A3 sample NPZ
and summary in their complete two-file directories. All four SHA-256 values,
both summary identities, the five-array NPZ schema, H100 stations, sequence
axes, BMW condition schema v1, active-frame finiteness, and exact zero padding
must pass before output is created. It writes exactly:

```text
spatial_structure_matrices.npz
spatial_structure_by_station_pair.csv
spatial_structure_by_separation.csv
spatial_structure_by_sequence.csv
spatial_structure_audit_summary.json
```

`spatial_structure_matrices.npz` has fixed arm order
`[frozen_ar, unconditional_gaussian]` and exactly these arrays:

```text
arm_names                                  string  [2]
stations_m                                 float64 [21]
sequence_ids                               string  [15]
lengths                                    int64   [15]
pooled_means_m                             float64 [2,21]
pooled_covariances_m2                      float64 [2,21,21]
pooled_correlations                        float64 [2,21,21]
pooled_covariance_difference_m2            float64 [21,21]
pooled_correlation_difference              float64 [21,21]
per_sequence_covariances_m2                float64 [2,15,21,21]
per_sequence_correlations                  float64 [2,15,21,21]
per_sequence_covariance_differences_m2     float64 [15,21,21]
per_sequence_correlation_differences       float64 [15,21,21]
```

Difference arrays are unconditional Gaussian minus frozen AR. Object arrays
and pickle are forbidden. Population covariance uses denominator `N`; padding
is excluded. Each station variance must be finite and positive and correlation
round-off is accepted only within absolute tolerance `1e-12`.

The station-pair CSV contains the 210 unordered pairs in lexicographic station
order with separation, both arms' covariance/correlation, and both differences.
The separation CSV contains the 20 fixed separations with pair counts and
unweighted means of those covariance/correlation values. The sequence CSV
contains the 15 sequences in stored order with active length, each arm's mean
off-diagonal and adjacent correlation, and the two differences.

The strict JSON summary records all input hashes, hashes of the four non-summary
outputs, array/CSV schemas, population formulas, counts, source seeds, pooled
and equal-sequence summaries, the pair tally beside the complete separation
profile, direction-only sequence tallies, unequal temporal dependence, the
reviewer's pre-implementation calculation disclosure, and every claim limit.
It reports no scalar effective sample size, p-value, interval, or decision gate.
The summary omits its own hash to avoid recursive content. Generated outputs
remain outside version control.

## v0.17.0/v0.17.1 independent-outing intake and cohort-lock outputs

The command consumes only the recursively discovered new-MCAP root, the exact
bytes of the prospective private acquisition manifest, and—only for a declared
supersession—the exact prior successful lock. The v0.17.1 amended interface can
also consume one preserved failed v0.17.0 four-file audit through
`--amended-from-failed-intake-directory`. It writes exactly four private files
to a directory that must not already exist:

```text
independent_outing_recordings.csv
independent_outings.csv
independent_outing_lock.json
independent_outing_intake_summary.json
```

The recording CSV has one row per discovered MCAP in deterministic basename
order and this exact header:

```text
recording_id,outing_id,private_outing_label,mcap_basename_private,relative_path_private,file_size_bytes,sha256,raw_readable,raw_empty,duplicate_of_recording_id,raw_usable,chronological_index_within_outing,internal_start_log_time_ns_private,internal_end_log_time_ns_private,first_estimate_source_time_ns_private,last_estimate_source_time_ns_private,estimate_source_duration_s,estimate_source_timestamp_count,estimate_missing_source_timestamp_count,estimate_source_timestamps_strictly_increasing,required_topic_schema_compatible,estimate_topic_present,estimate_topic_message_count,estimate_topic_schema_compatible,map_topic_present,map_topic_message_count,map_topic_schema_compatible,odometry_topic_present,odometry_topic_message_count,odometry_topic_schema_compatible,decoded_estimate_message_count,decoded_map_message_count,topology_gate_candidate_count,sensor_topology_candidate_count,lane_map_topology_candidate_count,unknown_or_other_topology_candidate_count,h100_geometry_ready_count,h100_eligible_frame_count,sequence_count_touching_recording,boundary_to_previous_stitchable,eligible_sequence_stitched_to_previous,failure_codes,boundary_codes
```

The outing CSV has one row per declared outing in opaque-ID order and this
exact header:

```text
outing_id,private_outing_label,acquisition_start_utc_private,separate_physical_session_declared,independence_basis_private,recording_count,raw_usable_recording_count,summed_usable_duration_s,usable_intervals_monotonic_nonoverlapping,topology_gate_candidate_count,non_sensor_topology_candidate_count,eligible_frame_count,sequence_count,retained_eligible_frame_count,has_raw_usable_recording,usable_duration_gate_passes,topology_gate_passes,eligible_frame_count_gate_passes,sequence_integrity_passes,technically_eligible,outing_fingerprint_sha256,split_score_sha256,split_rank,cohort_role,failure_codes
```

`independent_outing_lock.json` has these exact top-level fields:

```text
version
purpose
contract_revision
status
manifest
legacy_development_outing_count
raw_file_sha256_by_basename_private
private_to_opaque_outing_id
outings
eligibility_rules
availability_gate
split_contract
split_assignments_authorized
role_counts
attestations
prior_successful_lock
final_outing_embargo
schema_compatibility_amendment
```

The lock records manifest and raw hashes, content-only outing fingerprints,
opaque IDs, every eligibility result, the exact salt and final-count formula,
cohort roles when authorized, the one-outing legacy count, declaration limits,
prior-lock reconciliation, and the embargo allowlist. It contains no relative
or absolute path, environment value, or run timestamp, so its bytes and SHA-256
are independent of the mounted root layout. The raw-file map is keyed by unique
private basename and is reconciled exactly with each outing's nested hash map.
The last listed key exists only under the exact v0.17.1 contract revision;
preserved v0.17.0 artifacts retain their original schema and remain readable by
the standalone verifier.

`independent_outing_intake_summary.json` has these exact top-level fields:

```text
version
purpose
status
contract_revision
manifest_sha256
mcap_file_count
declared_new_outing_count
eligible_new_outing_count
ineligible_new_outing_count
legacy_development_outing_count
total_independent_outing_count_including_legacy
raw_usable_recording_count
summed_usable_duration_s
eligible_h100_frame_count
eligible_sequence_count
availability_gate
final_count
role_counts
failure_code_counts_non_mutually_exclusive
attestation_status
prior_successful_lock_sha256
prior_successful_lock_verified
overlapping_raw_sha256_count
output_sha256
summary_self_hash_recorded
claim_limits
next_authorized_action
schema_compatibility_amendment
```

The last listed key exists only under the exact v0.17.1 contract revision. In
both the lock and summary it has this exact schema and identical content:

```json
{
  "amendment_id": "v0.17.1-edp-schema-v2-2026-09-07",
  "descriptor_identity_source": "sha256(message.DESCRIPTOR.file.serialized_pb)",
  "allowed_flag_absent_estimate_file_descriptor_sha256": "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4",
  "legacy_estimate_file_descriptor_reference_sha256": "f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f",
  "legacy_validity_rule": {
    "descriptor_rule": "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist",
    "field_name": "model_parameters_optional_flag",
    "field_number": 8,
    "protobuf_type": "bool",
    "explicit_presence_required": true,
    "required_value": true
  },
  "observed_estimate_file_descriptor_sha256": [],
  "amended_from_failed_audit": null
}
```

The observed-descriptor list is sorted and unique. It contains only SHA-256
identities recomputed from decoded messages' own serialized file descriptors;
it is empty exactly when no estimate message was decoded. The optional
`amended_from_failed_audit` value is either null or an object with exactly:

```text
contract_revision
manifest_sha256
output_sha256
```

`output_sha256` contains exactly the four v0.17.0 output filenames and their
recomputed byte hashes. When the failed-audit argument is supplied, the
producer validates before writing that the directory contains exactly those
four files, both JSON files have their exact original v0.17.0 schemas and
contract revision, the old status is `insufficient_independent_outings`, no
role was assigned, the summary's three sibling hashes reconcile, its manifest
hash equals the current manifest bytes, and its recording basename/hash map
equals the current raw corpus. The standalone verifier receives the same
directory and reconstructs this lineage independently. A mismatch is an error;
the prior failed output is never edited or copied into the amended directory.

The v0.17.1 `contract_revision` is exactly
`v0.17.1-reviewed-2026-09-07-schema-v2-a1`. Its descriptor compatibility is
limited to the preserved structural legacy rule with explicit Boolean field 8
equal to true and the one pinned flag-absent v2 descriptor above. Both
generations additionally require the consumed `index_0` binding to be
non-repeated int64 field 7; its value must be a non-Boolean integer within the
supplied boundary range. It does not weaken any topology, geometry,
causal-input, duration, sequence, split, embargo, or claim rule.

`output_sha256` covers the two CSVs and lock; the summary deliberately records
no recursive self-hash. The summary may inherit the recording CSV's relative-
layout dependence. No file contains signed residual coordinates or summaries,
condition values or distributions, model or planner quantities, generated
samples, likelihoods, plots, or frame-level numeric features. Source-time
bounds, fixed technical counts, durations, topology identities, fixed failure
codes, and cohort identity are the only permitted intake evidence.

When at least seven new outings pass every fixed gate, status is `locked`, roles
are assigned, and the command returns `0`. Below seven, status is
`insufficient_independent_outings`, every split score/rank/role is null or empty,
all four files are still written, and the command returns `3`. Manifest,
coverage, hash, prior-lock, or output-target errors return `2` before creating
the output directory. Raw MCAPs, manifests, and all four outputs remain outside
version control. For identical manifest and raw bytes, code, contract, and
supplied failed-audit directory contents, the outputs are byte-deterministic;
changing the supplied failed-audit contents changes or invalidates the amended
lineage rather than being ignored.

## v0.18.0/v0.18.1 sensor-topology feasibility outputs

Status: the frozen a3 contract and v0.18.0 implementation received focused
review `GO`. The one authorized v0.18.0 run is preserved but exposed a precise
RLMB descriptor binding defect: `RoadLaneSegment.id_` is singular `uint64`, not
`int64`. v0.18.1 corrects only that binding, adds
`reference_required_structure_drift`, and identifies the corrected output with
version `0.18.1` and revision
`v0.18.1-review-candidate-2026-09-17-reference-uint64-a1`. The three filenames
and schemas below are otherwise unchanged. A private rerun remains unsupported
until focused corrective review returns `GO`. Binding definitions are in
`docs/sensor_topology_feasibility_predeclaration.md` and
`docs/sensor_topology_reference_schema_amendment.md`.

After exact reconciliation with the preserved v0.17.1 batch01 lineage, the
command writes exactly three private files to a new empty directory:

```text
sensor_topology_recordings.csv
sensor_topology_schema_inventory.json
sensor_topology_feasibility_summary.json
```

The recordings CSV has one deterministic basename-ordered row per MCAP and
this exact header:

```text
relative_path_private,basename_private,file_size_bytes,file_sha256,sensor_topic_present,reference_topic_present,sensor_message_count,reference_message_count,sensor_decoded_count,reference_decoded_count,sensor_descriptor_file_sha256s,reference_descriptor_file_sha256s,sensor_source_timestamp_valid_count,reference_source_timestamp_valid_count,sensor_source_timestamps_strict,reference_source_timestamps_strict,explicit_ego_candidate_count,camera_boundary_segment_structure_count,camera_only_successor_chain_count,camera_chain_100m_span_count,reference_h100_ready_count,source_time_pair_count,synchronized_100m_candidate_count,failure_codes
```

`sensor_topology_schema_inventory.json` has exactly these top-level fields:

```text
version
contract_revision
purpose
descriptor_identity_rule
topics
```

Each topic/descriptor item has exactly:

```text
topic
message_count
mcap_schema_names
mcap_schema_encodings
message_encodings
descriptor_file_sha256
root_message_full_name
field_inventory
audit_support_status
```

Every recursively inventoried field has exactly `full_name`, `number`,
`label`, `kind`, `referenced_full_name`, and `oneof_name`. Descriptor identity
comes only from `sha256(message.DESCRIPTOR.file.serialized_pb)`. Support is
limited to the required source-traced field-number/type/label structure;
inventorying a descriptor does not establish residual-target compatibility.

`sensor_topology_feasibility_summary.json` has exactly:

```text
version
contract_revision
purpose
lineage_status
preserved_intake_contract_revision
preserved_intake_lock_sha256
manifest_sha256
raw_mcap_count
raw_basename_sha256_map_sha256
topics
minimum_sensor_chain_span_m
maximum_source_delta_ms
sensor_chain_limits
reference_chain_limits
sensor_descriptor_file_sha256s
reference_descriptor_file_sha256s
sensor_message_count
reference_message_count
sensor_decoded_count
reference_decoded_count
explicit_ego_candidate_count
camera_boundary_segment_structure_count
camera_only_successor_chain_count
camera_chain_100m_span_count
reference_h100_ready_count
source_time_pair_count
synchronized_100m_candidate_count
recording_failure_counts
output_sha256
technical_feasibility_status
producer_provenance_status
scientific_target_adoption_authorized
claim_limits
next_authorized_action
```

The a3 audit requires the whole-message SENSOR_TOPOLOGY value, the exact
unwritten direct-path sentinel, valid nested mean wrappers, and stored-order
arc-length consistency. It accepts only paired camera boundaries with CAMERA
provenance, uses exactly one explicit ego index, and may traverse only a unique
strict successor chain. It reports orientation-invariant 100 m observed
midpoint span and source-time co-availability with independently H100-ready
RLMB. It does not compare LTSB and RLMB coordinates, test an anchor, or produce
an H100 residual-pair count because their physical frame origins are not
established as equal. `scientific_target_adoption_authorized` is always false. No output
contains an absolute path, run timestamp, raw numeric payload, coordinate,
timestamp value, width, span, junction value, projection, residual, condition,
sequence, model, planner, or figure value.

`source_time_pair_count` is the number of unique recording-local
mutual-nearest source-time pairs that pass the inclusive 50 ms gate before any
geometry filtering. The 50 ms value is a prospectively fixed v0.18 audit
constant, not an inherited v0.17 estimate/reference gate. Each accepted pair
can contribute at most one `synchronized_100m_candidate`.
