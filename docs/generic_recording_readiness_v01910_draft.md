# Bounded generic scientific readiness: review draft

Date: 2026-10-13. Status: **DRAFT FOR FOCUSED CONTRACT REVIEW**.
Proposed revision: `v0.19.10-bounded-recording-readiness-2026-10-13-a2`.
a2 addresses the five blockers in the independent review of PR #34 at
`88b889af642837d00c477edbadea7b3dbbc4a4c9`; a1 has NO-GO and is superseded.
Read [the amendment record](generic_recording_readiness_v01910_a2_review.md).
This documentation does not implement a command or authorize a private run.
Read [the continuation](generic_pipeline_continuation_20261009.md),
[the decoder contract](generic_recording_decode_check_v0199.md),
[existing readiness](generic_recording_ingestion_v0196.md) and
[the handoff](development_recording_decode_followup_20261013.md).

## Purpose and fixed scientific scope

Connect the reviewed v0.19.9 disk-index reader to the existing EDP/RLMB/
odometry scientific arithmetic. Count native geometry, common H100 support,
SENSOR admission, complete causal features and sequence support separately.
No numeric residual or condition arrays, payload coordinates or row tables
are exported. Zero support in a completed execution and unknown support in
an incomplete execution must remain different states.

The historical target remains the signed EDP-minus-aligned-RLMB projection
onto the reference left normal, at 21 stations `0, 5, ..., 100 m`.
RLMB remains a pseudo-reference; the target is map-relative path disagreement,
not measured physical lane error. Shared producer dependencies remain material.
Counts across topology labels do not adopt an all-topology training population.
The SENSOR enum does not prove map independence or a physical outing.

Preserve existing schema-bound qualifier/path selection, finite geometry,
orientation, near-vehicle footpoint, anchor distance at most 1 m, common
longitudinal stations and no extrapolation. Do not assume EDP `s=0` is the
rear-axle origin. No new frame transform, epoch compensation, covariance
correction, foresight reference or threshold is introduced.

The fixed six-feature order is `speed_mps`,
`estimated_mean_abs_curvature_per_m`, `estimated_curvature_delta_per_m`,
`confidence_near_mean`, `confidence_middle_mean`, `confidence_far_mean`.
Reuse existing 50 ms speed arithmetic, odometry interpolation limits and
recorded log-time causality checks. Publish times remain evidence only;
there is no publish-time admission gate. Never substitute future samples,
reference geometry, residuals or reference quality as prediction inputs.
Recorded-time eligibility is not proof of physical input availability.

## Inputs, identity and descriptor compatibility

Require one valid immutable v0.19.6 registration, its exact source specification,
the complete v0.19.8 inventory and complete v0.19.9 decode report. Batch,
recording order, raw SHA/size, registration/specification/inventory digests,
selected topics and advertised channel/schema versions must reconcile.
Predecessors are strict JSON: duplicate/nonfinite values rejected, 64 MiB
per report. Preserve their bytes. Historical package versions are evidence,
not a requirement that new version strings equal old ones.

Select exactly `/adp/estimated_drive_paths`, `/adp/road_lane_map_based` and
`/adp/odometry`. Before opening/hashing raw bytes, validate this selection,
all predecessor identities/counts, dependencies and advertised container and
scientific budgets against both preserved reports. Exceeding the EDP/RLMB/
odometry scientific caps is exit 2 with `scientific_advertised_topic_limit`;
inconsistent topic/count evidence is exit 2 with `readiness_predecessor_mismatch`.
No output directory/report is created by any exit-2 path, even in a batch.

Freshly hash each registered file once from an opened descriptor; check size
and descriptor/path state before/after hashing. Reuse the same verified
descriptor for fresh bounded summary and selected decoding. Before payload
processing, compare the complete fresh inventory object with the preserved
recording's v0.19.8 `inventory` using canonical strict-JSON equality that
preserves integer/Boolean distinctions. Difference is fatal exit 2, no report,
`readiness_preserved_inventory_mismatch`, matching the v0.19.9 drift policy.

Before any message payload enters a scientific converter, classify **every
selected channel/schema version**, using its embedded descriptor/type. A
zero-valued instance may expose the descriptor; it is not a synthetic payload
or evidence that message values are valid. Serialization and scientific
binding are separate decisions. Descriptor binding is independent of whether
any actual row passes ego/error/geometry qualifiers.

### Exact scientific binding policy (B1)

For EDP, preserve `estimate_descriptor_support` and the reviewed
[v0.17.1 amendment](independent_outing_schema_v2_amendment.md) verbatim:

- Legacy v1 uses the existing structural binding: Boolean, singular field 8
  `model_parameters_optional_flag` and singular int64 field 7 `index_0`, plus
  all existing generation-dependent required bindings. Actual flag presence/
  true value is a per-message qualifier, not a descriptor decision.
- Flag-absent candidate v2 requires the exact root message's **file descriptor**
  SHA-256 `dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4`,
  the flag's absence, int64 field 7 and the existing required bindings.
- Recompute that identity from `message.DESCRIPTOR.file.serialized_pb`, or
  the same descriptor on its resolved type before message processing. An MCAP
  `FileDescriptorSet` hash or caller-supplied audit hash is a different identity.
  A changed MCAP schema-record hash alone does not decide this generation.
- Any other flag-absent descriptor is unsupported. Do not replace the exact
  allowlist with structural similarity. A relaxation is a separate evidence
  record and reviewed amendment, not implementation discretion.

For RLMB, preserve the existing `Adp.Perception.Road`/Protobuf binding and the
structural alternatives consumed by `io.mcap.road_frame_from_message` and
`ordered_ego_lane_from_road_frame` at merged PR #33. Bind declared descriptor
paths before testing values: the first declared alias in each existing alias
tuple wins; underscore aliases and existing direct-path/boundary-midpoint
alternatives remain permitted. Required lane-segment/ID bindings and at least
one complete existing geometry-reconstruction descriptor path must resolve.
Optional metadata or an unused alternative need not exist; empty repeated
values, invalid flags/ranges and nonfinite coordinates on a bound path remain
data failures. Preserve current integer segment-ID handling, including int64/
uint64, without borrowing the separate sensor-lane adapter's constraints.
Do not accept a new alias or field conversion by root name alone.

For odometry, use the existing `Adp.OdometryState`/Protobuf identity, singular
integer `timestamp` and numeric `x_position`, `y_position`, `yaw_angle`
bindings consumed by `_OdometryStore`. A missing/incompatible declared field
is unsupported binding; a bound field with invalid values is message poison.
Either makes condition availability unavailable under B2; it does not suppress
otherwise complete EDP/RLMB geometry.

The following are **binding failures**, excluded from the row cascade:
`estimate_schema_or_encoding_mismatch`, `map_schema_or_encoding_mismatch`,
`estimate_descriptor_missing`, `unsupported_estimate_descriptor_generation`,
`candidate_v2_descriptor_contract_mismatch`,
`legacy_index_0_descriptor_contract_mismatch`, `schema_bindings_incomplete`,
and their `estimate_`-prefixed conversion forms. A reference descriptor that
cannot resolve the existing required paths is also binding-unsupported.
An unexpected late binding failure, despite descriptor precheck, nulls the
recording's readiness; it is never converted to a genuine-zero data result.

One unsupported EDP **or** RLMB version makes the whole recording scientifically
inconclusive: no supported-version subset, no complete-prefix counts. Record
`scientific_binding_unsupported_estimate_descriptor` or
`scientific_binding_unsupported_reference_descriptor`; if both apply, estimate
has precedence. Finish container verification without the scientific sink
so a complete, reconciled `stream_integrity` can be retained. Container failure
instead remains the execution first cause. This deliberately differs from the
old v0.19.6 per-message zero-support accounting; historical outputs are unchanged.
Per-version binding observations preserve the descriptor cause separately.

### Fresh decoding and late mutation (B5)

After all selected streams decode, require exact type-preserving canonical
JSON equality of the fresh `stream_integrity` with the preserved v0.19.9
recording's `decode_check`: all channel/schema/topic counts, CRC coverage,
chunk/index counts/order and processed payload bytes. It is an oracle for
identical bytes/topics, not merely a lineage label. Difference gives fatal
exit 2, no batch report, `readiness_preserved_decode_mismatch`; discard staged
scientific observations and owned scratch. Do not compare new runtime versions,
timings or the new scientific fields to predecessor fields.

Recheck raw descriptor/path state and exact registration/specification and
both predecessor bytes before publication, including earlier batch files.
Late mutation detected by these identity rechecks gives exit 3 and affected
recording invalidation, with both stream/scientific observations null. Use
static labels `file_changed_before_report_publish`,
`registration_changed_before_report_publish`,
`preserved_inventory_changed_before_report_publish`, and
`preserved_decode_changed_before_report_publish`. A raw change during processing
uses `file_changed_during_readiness`. Preserve the first cause and append later
distinct invalidations in **detection order**, matching v0.19.9. If fresh-value
comparison already caused exit 2, no later successor report is written.

## Reader and scientific consumer ownership

`io.recording_decode_check` remains the bounded container owner. Add a narrow
optional scientific sink after review: messages reach it after decompression,
CRC and Protobuf checks. Historical defaults/output shapes remain unchanged.
`io.recording_ingestion` and domain converters own scientific staging/arithmetic;
workflows own evidence, resources, safe failure labels and publication.
Never fall back to `SeekingReader.get_summary()` or old whole-summary readiness.

Reuse `mutual_nearest_timestamp_pairs` **verbatim**: its O(N log N) scalar
matching is bounded by 100,000 EDP and 100,000 RLMB records. Allowed in-memory
structures are these per-role integer/None timestamp lists and matcher indexes,
bounded `PairDiagnostics` scalar delta lists and at most 100,000 candidate
scalar/feature rows. Their aggregate memory remains subject to the 4 GiB process
cap; no assumption about a particular Python-object byte size replaces that cap.
No retained list of decoded messages, chunk payloads or path/geometry arrays.
Per-row geometry/odometry is disk-staged; only one bounded chunk/message and
budgeted descriptors/path conversion workspaces may be live at once.

Original storage order means **ascending indexed chunk byte offset, then stored
record order within each chunk**. Estimate/reference positions and clock
summaries use that order; the matcher preserves its existing timestamp-sorted
pair enumeration/ties. Neither chronology nor sequence gaps are repaired.

## Pairing, attrition and sequences

Compute mutual-nearest unique pairing on the full original EDP/RLMB timestamp
streams before message qualifiers, geometry or topology filtering. Reuse the
existing missing/duplicate/tie handling and integer timestamps. There is no
maximum delta gate. Neither the 50 ms speed interval nor a sensor-lane audit's
separate match threshold is a pairing limit. Source/log/publish/physical geometry
epochs remain different evidence. Clock summaries observe original storage order.

The exclusive cascade now follows `_count_geometry`/`_h100_geometry` evaluation
order. It is a partition of first failures, not a new scientific selection rule:

| Stage | Exact attribution |
|---|---|
| `source_time` | Matcher `missing_time_first_positions`; label `estimate_source_timestamp_missing` |
| `unique_pair` | Valid-time unmatched EDP positions; label `no_unique_mutual_nearest_pair` |
| `estimate_qualifier` | `estimate_not_attempted_estimator_unavailable`, `estimate_model_structure_invalid`, `estimate_model_flag_not_true` |
| `estimate_geometry` | Remaining existing `estimate_*` conversion/spline/curve/path data codes, plus `estimate_geometry_not_ready`; binding codes are excluded |
| `reference_geometry` | Existing `map_*` data/reconstruction codes, plus `map_geometry_not_ready`; binding codes are excluded |
| `common_h100` | Every existing `h100_*` failure, including footpoint projection and estimate/reference coverage failures |
| `anchor` | Exactly `anchor_distance_exceeds_1m_or_invalid`, tested only after H100 coverage passes |
| `sensor_admission` | Anchored H100 pairs failing existing SENSOR admission; label `not_sensor_topology` |
| `complete_conditions` | One primary condition failure per rejected candidate as defined below |

The prefixes above mean the static labels emitted by the **pinned existing
converters**, not arbitrary exception text or future labels. An unclassified
code/impossible state gives null readiness, `scientific_attrition_unclassified_failure`.
Do not silently place it into a catch-all data bucket. Rich estimator sub-state
labels remain in inherited diagnostics; this cascade keeps the existing collapsed
qualifier labels, so the requested partition is exact rather than relabelled.

First input is `counts.estimate_message_count`. Source-time rejected equals
`timestamp_pairing_counts.missing_time_first_positions`. Unique-pair rejected
equals `unmatched_first_positions - missing_time_first_positions`; its remaining
equals `timestamp_pairing_counts.pairs`. Use those count fields' existing names;
do not subtract ambiguous positions twice. No optional ambiguity split is added.

Stages `estimate_qualifier` through `anchor` partition the paired rows' existing
`counts.pair_failure_counts` by the table above, retaining each existing label.
They need not equal all-stream `conversion_failure_counts`, which also includes
unpaired rows. `common_h100` remaining equals `h100_pair_count`; `anchor`
remaining equals `anchored_h100_pair_count`. SENSOR input is the latter;
its remaining equals `sensor_anchored_h100_pair_count` and geometry support
frame count. All-source anchored topology counts remain independent diagnostics;
unknown/other sources stay explicit and are never admitted as SENSOR.

For available odometry, attribute the **first** code in `_scan_stream`'s existing
per-candidate emission order: optional `estimate_features_*` first, then the
existing `speed_failures` tuple. That tuple is either its one bracket/geometry
exception code, or `speed_uses_future_source_sample` followed by
`speed_log_time_unavailable`/`speed_input_logged_after_estimate` in `checked_speed`
order. Do not sort per-row codes before choosing the primary cause. The inherited
`condition_failure_counts` still counts **all** emitted codes and is non-exclusive.
With globally unavailable odometry, B2 instead assigns the global unavailable
label to every candidate in this last stage; inherited overlapping feature
failures remain visible separately. This explicit reporting priority prevents
odometry unavailability from masquerading as a measured zero-condition yield.

Maintain separate SENSOR H100 and complete-condition support summaries, using
`sequence_layout`/`summarize_support` unchanged. Recording boundaries, original
estimate/pair-index gaps, resets/nonpositive source steps and gaps over 200 ms
break sequences; missing/rejected rows are never bridged. Retain singletons in
frame/sequence denominators (zero transitions). Exact histogram/start-reason/
maximum duration shapes remain inherited. No physical outing or residual-vector
count follows from these candidate support summaries.

## Fixed engineering budgets

Inherit v0.19.8/v0.19.9 container ceilings, with no override/retry/fallback.
The following choices freeze B4, rather than leaving configuration alternatives:

| Budget | Fixed value |
|---|---:|
| Summary bytes / record bytes / parsed text | 1 GiB / 128 MiB / 16 MiB |
| Records per summary section / summary timer | 2,000,000 / 300 cooperative s |
| Scientific EDP / RLMB / odometry messages | 100,000 / 100,000 / 1,000,000 |
| Container messages per topic / recording | 1,000,000 / 2,000,000 |
| Selected channels / schemas / descriptor bytes | 256 / 64 / 16 MiB total |
| Selected chunk record / decoded chunk / Zstd window | 128 MiB each |
| Selected payload bytes processed | 8 GiB |
| Index database / one scientific database | 512 MiB / 8 GiB |
| Total database-file allocation | 8.5 GiB |
| SQLite page cache / process address space | 8 MiB per connection / 4 GiB |
| Minimum MemAvailable | 6 GiB |
| **Initial free scratch, before each raw hash** | **18.5 GiB = 19,864,223,744 bytes** |
| Free scratch floor during processing | 10 GiB |
| Combined processing after fresh summary | 1,800 cooperative s |

Initial scratch below 18.5 GiB gives `insufficient_initial_scratch_space`,
exit 2, before hashing or output creation. During processing, below 10 GiB
gives `scratch_free_below_runtime_floor`, exit 3 with inconclusive recording.
These are fixed preflight versus runtime policies, not approximate guidance.
Check memory/scratch before each phase, every 1,024 staged indexes/scientific
rows, every 128 selected chunks and before publication, including first checkpoints.
Actual message counts are checked during decoding despite the early advertised
checks. Runtime resource excess never means genuine zero support.

Use exactly two disposable database files in an owned recording scratch
directory: index at most 512 MiB, and all geometry/inputs/odometry staging in
one scientific DB at most 8 GiB. Every connection must set and verify
`journal_mode=OFF`, `synchronous=OFF`, `temp_store=MEMORY`, `mmap_size=0`,
4,096-byte page size and at most 8 MiB page cache. Bound main files with their
page limits and measured allocated bytes; enforce the combined 8.5 GiB ceiling.
No WAL or rollback journals and **no `temp_store=FILE`** are permitted in this
new consumer. SQLite sort/temp structures instead count toward the process
address-space cap; allocation failure gives inconclusive `memory_limit`.
If the runtime cannot honor these pragmas, fail dependency preflight before
hashing with `readiness_sqlite_configuration_unsupported`.

This is a deliberate engineering change from the historical scientific DB's
default rollback journal/FILE temp store; historical consumers remain unchanged.
Disposable DBs are never reused or resumed after failure/crash, so journal-free
crash recovery is not needed. Any unexpected on-disk sidecar/temp file is charged
to the same total allocation, stops processing with `readiness_unexpected_scratch_file`
and nulls readiness; do not ignore it or continue with a different configuration.
Cleanup deletes only files inside the owned temporary directory in `finally`.
Raw/source/report/catalogue paths are never cleanup targets.

The 300 s fresh-summary timer and unbounded raw-hash phase are separate. Start
one 1,800 s deadline immediately after fresh summary equality, before descriptor
binding. It covers binding, index staging, selected decoding/scientific sink,
matching, geometry, feature checks and sequence aggregation. The new reader
invocation shares this absolute deadline; it must not reset a second 1,800 s
timer. Its default standalone decoder deadline remains unchanged. Timeout is
inconclusive `readiness_processing_time_limit`; unfinished full-stream science
is null. Cooperative checks are not hard deadlines for stalled native calls.

`execution_limits` is the exact v0.19.9 key/value map (including its 1,800 s
decode limit), plus these exact fields; its decode deadline and the new processing
deadline are the same deadline in this consumer:

```json
{
  "maximum_summary_bytes": 1073741824,
  "maximum_summary_record_bytes": 134217728,
  "maximum_parsed_summary_text_bytes": 16777216,
  "maximum_summary_records_per_section": 2000000,
  "maximum_summary_seconds": 300,
  "maximum_scientific_messages_by_topic": {
    "/adp/estimated_drive_paths": 100000,
    "/adp/road_lane_map_based": 100000,
    "/adp/odometry": 1000000
  },
  "maximum_scientific_database_bytes": 8589934592,
  "maximum_combined_database_bytes": 9126805504,
  "sqlite_page_cache_bytes": 8388608,
  "minimum_initial_scratch_free_bytes": 19864223744,
  "maximum_processing_seconds_per_recording": 1800
}
```

## Proposed output and publication states

Atomically write one strict JSON `bounded_recording_readiness.json` in a new
output directory as the completion marker, at most 64 MiB. Top-level keys remain:

```text
contract_revision, purpose, batch_id, status,
registration_sha256, source_specification_sha256,
preserved_inventory_report_sha256, preserved_decode_report_sha256,
reader_implementation, scientific_adapter_revision, selected_topics,
selected_chunk_crc_validation_enabled, technical_recording_count,
independent_outing_count, roles_assigned, cohort_lock_created, model_fitted,
residual_profiles_constructed, numeric_conditions_exported,
recorded_input_causality_checked_for_all_recordings,
physical_input_availability_proven, reference_independence_proven,
raw_cache_deletion_authorized, runtime_versions, runtime_source_sha256,
execution_limits, resources_at_start, recordings, interpretation
```

Purpose is `development_only_bounded_recording_readiness`; contract and
scientific-adapter revisions are a2 above. Reader remains
`v0.19.9-disk-index-selected-chunks-a1`; selected topics are the sorted three
topics and CRC validation true. Independent-outing count is null. All role/
lock/fit/export/physical-proof/reference-proof/deletion booleans remain false.
Runtime/resource shapes inherit v0.19.9; limits are frozen above. Counts are
nonnegative integers, not booleans; hashes lowercase 64-hex; no extra keys.

Each recording has exactly:

```text
recording_id, raw_sha256, size_bytes, source_declaration_status,
status, failure_code, invalidation_codes, reader_failure_context,
binding_observations, stream_integrity, readiness,
condition_availability, recorded_input_causality_checked, execution_observations
```

Identity/source fields inherit registration/v0.19.9. `stream_integrity` is
exactly the old `decode_check` shape or null. `reader_failure_context` is the
existing safe v0.19.9 chunk context or null, not arbitrary exception text.
Static invalidation labels retain detection order and first-cause precedence.

`binding_observations` is null until all selected descriptors are classified;
otherwise an array sorted by `(topic, channel_id)`, one item per channel/schema
version with exactly `topic`, `role`, `channel_id`, `schema_id`,
`message_file_descriptor_sha256`, `binding_status`, `binding_failure_code`.
Role is `estimate`, `reference` or `odometry`; status `supported`/`unsupported`;
file-descriptor SHA is 64-hex or null if unavailable. Supported cause is null.
Unsupported EDP cause is its existing descriptor/schema code (unprefixed
generation codes); unsupported reference is `map_schema_or_encoding_mismatch`
or `reference_descriptor_fields_unsupported`; unsupported odometry is
`odometry_schema_or_encoding_mismatch` or `odometry_descriptor_fields_unsupported`.
This is descriptor evidence, not decoded-prefix science. Identity mutation
nulls it; container failure may retain it only on verified unchanged bytes.

Complete `readiness` has exactly:

```text
counts, diagnostics, odometry, source_clock_order, log_clock_order,
sensor_geometry_support, complete_condition_support,
condition_failure_counts, exclusive_attrition
```

The first eight values retain existing shapes/meanings at merged PR #33;
see [output contracts](output_contracts.md#v0196-generic-development-recording-readiness).
Source clocks cover estimate/reference, log clocks all three selected topics.
Their exact decimal endpoints and schema/source evidence are **private reviewer
evidence**, never public Git or meeting text. No numeric conditions/residuals,
coordinates, literal raw paths/session IDs or row tables are exported.

`exclusive_attrition` has exactly `decoded_estimate_message_count`, `stages`,
`complete_condition_frame_count`. Stages are the nine entries in the a2 table,
each with exactly `stage`, `input_count`, `rejected_count`, `remaining_count`,
`failure_code_counts`. Input minus rejected equals remaining; rejection-map
sum equals rejected; next input equals previous remaining. First input equals
decoded EDP count; last remaining equals complete-condition frame count.
All intermediate equalities and paired-failure partitions in B3 are mandatory.
Overlapping inherited condition/conversion diagnostics are not additive stages.

### Explicit odometry-unavailable state (B2)

For fully decoded, CRC-checked, count-reconciled streams, odometry is globally
unavailable if any selected odometry descriptor is unsupported, any message is
invalid/schema-or-encoding-mismatched, its `_OdometryStore.schema_counts` has
more than one identity, or the stream is empty. Identical duplicate timestamps
and audited conflicts are handled by the existing store: duplicates/conflicts
alone are not new whole-stream poison rules.

Publish recording `status: complete`, `failure_code: null`, complete stream
integrity and **retained geometry/readiness**. Set `condition_availability` to
`unavailable_odometry`, `recorded_input_causality_checked` to false. If all other
recordings complete, batch status is complete and exit code **0**, but its
all-recordings recorded-input causality flag is **false**. The exact availability
enum and false flag distinguish this from genuine zero-condition data.

Retain the existing odometry `failure_counts`/`schema_counts` and all inherited
non-exclusive condition failure counts. For unsupported descriptor binding,
count affected messages under existing `odometry_schema_or_encoding_mismatch`
if identity/encoding differs, otherwise `odometry_invalid_message`; binding
observations retain the specific descriptor cause. Multiple schema identities
can poison availability even with empty `failure_counts`. In the exclusive last
stage, attribute **every** SENSOR H100 row to
`odometry_stream_invalid_or_schema_changed` (or `odometry_stream_empty` for empty
stream), irrespective of overlapping estimate-feature failures. Therefore the
complete-condition support summary has zero frames/sequences/transitions, but
those zeros mean unavailable under this explicit state, not measured zero yield.
Even with no SENSOR H100 candidates, unavailable status remains explicit.

With fully processed usable odometry, set `condition_availability` to
`available_for_checks` and the per-recording causality flag true. Individual
bracket/estimate/log-time failures are then measured rejection counts and may
produce genuine zero complete-feature support. This flag says the recorded
source/log-time checks were performed, not that all rows passed or physical
availability was proven. Publish time never gates either population.

### Complete, inconclusive and fatal outcomes

| Outcome | Recording state / readiness | Availability / causality flag | Batch exit |
|---|---|---|---|
| Complete supported science, including measured zero | Complete; readiness retained | Available for checks / true | 0 if all complete |
| Complete E/R with globally unavailable odometry | Complete; geometry/readiness retained | Unavailable odometry / false | 0 if all complete |
| Unsupported EDP/RLMB version | Inconclusive; readiness null; reconciled stream retained | Not assessed / false | 3 |
| Incomplete selected stream | Inconclusive; stream and readiness null | Not assessed / false | 3 |
| Scientific failure after reconciled decoding | Inconclusive; readiness null; stream retained | Not assessed / false | 3 |
| Identity mutation at late recheck | Inconclusive; both null, binding observations null | Not assessed / false | 3 |
| Input/preflight/dependency or fresh-oracle mismatch | No report, including earlier batch rows | No published state | 2 |

`condition_availability` enum values are exactly `available_for_checks`,
`unavailable_odometry`, `not_assessed`; never null. The all-recordings causality
flag is the conjunction of complete state **and** per-recording flags, not
merely `batch.status == complete`. No incomplete science is represented by
positive prefix counts or by zero. A complete container observation can survive
a later scientific failure, but not an unfinished selected stream or identity
invalidation. Completed other recordings may remain in an inconclusive batch;
there is no pooled population or consumable partial archive.

`execution_observations` has exactly `elapsed_seconds` and
`peak_resident_memory_bytes`. Elapsed map keys are exactly `raw_hash`,
`fresh_summary`, `descriptor_binding`, `selected_decode`, `scientific_finalize`;
each is a finite nonnegative number or null if not entered/measured. Selected
decode includes its scientific sink work; finalize includes subsequent matching/
geometry/features/sequences, so stages do not overlap. RSS is nonnegative integer
bytes or null if unavailable and is sampled at the resource checkpoints, not
claimed as an exact continuous peak. Partial timing is execution evidence only.
No claim about private pilot processing duration or cap adequacy exists yet.

A partial/interrupted write is not a completion marker. No status opens a
numeric archive, fit, role assignment, reference proof or deletion gate.

## Required implementation evidence after contract GO

Test B1 per-version binding independently of message qualifiers: supported v1,
exact v2, new flag-absent descriptors, incomplete bindings, mixed supported/
unsupported E/R versions, MCAP-schema versus root-file hashes and late binding
failure. Test B2 poison/schema multiplicity even when there are zero candidates,
both condition-availability populations and their exact status/exit/flags.
Test B3's coverage-before-anchor double-failure cases and all endpoint/partition
equalities; first-emitted condition cause and global odometry override.
Test B4 initial 18.5-GiB versus runtime 10-GiB boundaries, disposable journal-free
MEMORY temp pragmas, unexpected sidecars, address-space exhaustion and cleanup.
Test B5 exact type-preserving fresh-summary/decode equality, mismatch exit 2
without output and late identity mutation/detection-order invalidations.

Test synthetic parity with existing descriptor bindings, timestamp ties/missing
clocks/uint64 extremes, pairing before filtering, lane-map/unknown provenance,
anchor rejection, no extrapolation, H100 support and exact six-feature behavior.
Demonstrate exclusive cascade reconciliation, genuine-zero complete publication,
odometry-poison geometry retention, unsupported E/R binding and interrupted
stream nulling, record/pair gap/reset and singleton sequence behavior.

Test same-descriptor and metadata mutation handling, no repeated hashing or
whole-summary fallback, nonzero/zero CRC coverage, actual-versus-advertised
limits, shared timer/database/sidecar floors, temp cleanup and first-cause retention.
Exercise a large synthetic index under constrained memory and compare old
wrappers/default decoder outputs to unchanged baselines. Keep old tests passing.
Use Python 3.10/3.12 CI and exact pushed-head implementation review.

After contract GO, implement/test/review/CI and merge; then provide a separately
specified one-file private counts-only command with fresh paths. Preserve old
successful reports. Numeric export/strict validator, target/population/session
admission, matched real model execution and verified raw retirement remain
separate later consumers. The proposed catalogue is not implemented here.
