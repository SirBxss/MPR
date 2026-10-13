# Bounded generic scientific readiness: review draft

Date: 2026-10-13. Status: **DRAFT FOR FOCUSED CONTRACT REVIEW**.
Proposed revision: `v0.19.10-bounded-recording-readiness-2026-10-13-a1`.
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
recorded log/publish-time causality checks. Never substitute future samples,
reference geometry, residuals or reference quality as prediction inputs.
Recorded-time eligibility is not proof of physical input availability.

## Inputs, identity and descriptor compatibility

Require one valid immutable v0.19.6 registration, its exact source specification,
the complete v0.19.8 inventory and complete v0.19.9 decode report. All batch,
recording order, raw SHA/size, registration/specification/inventory digests,
selected topics and advertised channel/schema versions must reconcile.
Predecessors are strict JSON with duplicate/nonfinite values rejected and
a 64 MiB byte cap per report. Preserve their bytes; do not amend in place.
Historical runtime versions remain recorded evidence rather than a requirement
that the new runtime equal the old runtime.

Select exactly `/adp/estimated_drive_paths`, `/adp/road_lane_map_based` and
`/adp/odometry`. Every actual selected channel/schema version is validated.
Embedded Protobuf decoding proves serialization compatibility only. Bind
scientific fields by the existing reviewed descriptor rules, including field
numbers/types/presence, enum meanings, coordinate validity and reference
segment-ID compatibility. Root type names or a previously observed hash alone
do not prove scientific compatibility. A compatible descriptor variation may
reuse existing binding; new unsupported semantics require a reviewed amendment.

Freshly hash each registered raw file once, from an already opened descriptor,
and verify size and descriptor/path state before and after hashing. Use that
same verified descriptor for bounded fresh summary parsing and selected decoding.
Neither a predecessor hash nor successful decoding substitutes for this check.
Recheck raw descriptor/path state and all metadata/predecessor bytes before
publication, including earlier files in a multi-recording batch. On identity
mutation, invalidate affected observations rather than publishing stale counts.

## Reader and scientific consumer ownership

`io.recording_decode_check` remains the bounded container owner. Add a narrowly
defined optional scientific sink only after contract review: payloads reach
the sink after decompression, CRC and Protobuf checks. The default decoder
result, historical wrappers, CLI behavior and output bytes remain unchanged.
`io.recording_ingestion` and existing domain converters own scientific binding
and disk-backed scalar/geometry/odometry staging; workflows own evidence,
resources, complete/null publication and static safe failure labels.

Never fall back to `SeekingReader.get_summary()` or the old whole-summary
readiness route. No retained collection of decoded message objects, full
MCAP payloads or unbounded geometry arrays. Keep only budgeted descriptors,
one bounded chunk/message, bounded scalar aggregates and temporary databases.
Use a stable disk-backed timestamp/order index for matching; avoid an O(N*M)
scan. The existing timestamp arithmetic is the oracle for synthetic parity.

## Pairing, attrition and sequences

Compute mutual-nearest unique pairing from the full valid original EDP/RLMB
source timestamp streams before geometry, qualifier or topology filtering.
Reuse existing integer timestamp handling, missing/duplicate behavior and tie
breaking. Pairing has **no maximum time-delta gate**; do not borrow the 50 ms
speed interval or sensor-lane structural audit's separate matching threshold.
Report source/log chronology in original storage order without repairing resets.
Source, log, publish and physical geometry epochs are distinct evidence.

In addition to inherited diagnostics, publish an exclusive EDP-row rejection
cascade in this fixed order:

| Stage | Predicate required to survive |
|---|---|
| `source_time` | Valid estimate source timestamp |
| `unique_pair` | Unique mutual-nearest counterpart from the full streams |
| `estimate_qualifier` | Existing reviewed ego/error/selection qualifiers |
| `estimate_geometry` | Existing finite estimate geometry and native support |
| `reference_geometry` | Existing unambiguous finite reference reconstruction |
| `anchor` | Existing reviewed spatial alignment and at-most-1-m anchor |
| `common_h100` | Full common 21-station support without extrapolation |
| `sensor_admission` | Existing SENSOR-only admission rule |
| `complete_conditions` | All six current/past, recorded-time-valid inputs |

Each stage rejects a row only once, at its first failing stage. This is a
reporting cascade, not permission to change pairing or scientific evaluation
order. Independently report all-source native/geometric support by the exact
observed topology label. Unknown/other labels remain explicit. Historical
diagnostics may contain overlapping counts; do not present those as additive
exclusive attrition. No pooled batch population or independent-outing count
is inferred from technical recordings.

Maintain separate sequence summaries for SENSOR H100 geometry candidates and
their complete-condition subset. Reuse `domain.exploratory_residuals.sequence_layout`
and `domain.recording_ingestion.summarize_support`: recording boundaries,
original estimate/pair-index gaps, nonpositive source-time steps, resets and
gaps over 200 ms break sequences. Do not bridge rejected/missing rows or
recordings, and do not discard singleton frames from frame denominators.
Report frame/sequence/transition counts, maximum frame count/duration,
length histogram and start-reason counts using the existing exact shapes.
These are candidate support counts, not constructed residual-vector counts
or v0.17 eligible physical outings.

## Fixed engineering budgets

Inherit all v0.19.8 summary and v0.19.9 container ceilings. No CLI override,
automatic retry, truncation presented as complete, or cap relaxation.

| Budget | Fixed value |
|---|---:|
| Summary bytes / one record / parsed text | 1 GiB / 128 MiB / 16 MiB |
| Records per summary section / summary timer | 2,000,000 / 300 cooperative s |
| Scientific EDP / RLMB / odometry messages | 100,000 / 100,000 / 1,000,000 |
| Container messages per topic / per recording | 1,000,000 / 2,000,000 |
| Selected channels / schema versions / descriptors | 256 / 64 / 16 MiB total |
| Selected chunk record / decoded chunk / Zstd window | 128 MiB each |
| Cumulative selected payload processed | 8 GiB |
| Index database / scientific databases combined | 512 MiB / 8 GiB |
| Total temporary database allocation | At most 8.5 GiB |
| SQLite page cache | 8 MiB per database connection |
| Process address space / minimum MemAvailable | At most 4 GiB / at least 6 GiB |
| Minimum free scratch at each checkpoint | 10 GiB |
| Scientific processing per recording | 1,800 cooperative s |

Scientific processing includes index staging, decoding, binding, matching,
geometry, feature checks and sequence aggregation. Its timer excludes raw
hashing and the separately timed fresh summary. Checks occur before each phase,
every 1,024 staged indexes/scientific rows, every 128 selected chunks, and before
publication, including each phase's first checkpoint. Cooperative timers are
not hard deadlines for a stalled native call. Check scientific topic budgets
against advertised counts before payload processing and against actual counts
during processing. Budget excess yields inconclusive observations, not zero.

Enforce database growth including SQLite journal/WAL sidecars, or disable
unbounded sidecars through a justified bounded configuration. The 10 GiB floor
must remain free while databases grow: merely starting with 10 GiB is not
enough to sustain their maximum allocation. Up to roughly 18.5 GiB initially
free could be needed for the full temporary budget plus that floor; this is
engineering headroom, not a revised scientific rule. Clean only owned temporary
files in `finally`; raw/source/report artifacts are never cleanup targets.

## Proposed output and publication states

Write one strict JSON artifact `bounded_recording_readiness.json`, atomically
as the completion marker in a new output directory. Maximum encoded size is
64 MiB. The exact top-level keys are:

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

`purpose` is `development_only_bounded_recording_readiness`. Revision is the
proposed a1 above. `reader_implementation` remains
`v0.19.9-disk-index-selected-chunks-a1`; `scientific_adapter_revision` is the a1
revision. Selected topics are the lexically sorted three-topic list above;
selected CRC validation is true. Independent-outing count is null. All listed
role/lock/fit/export/physical-proof/reference-proof/deletion booleans are false.
The all-recordings recorded-input causality flag is true only when all scientific
checks completed; it may be true with zero complete-feature candidates and
does not mean every inspected input was eligible. Runtime/resource shapes are
inherited from v0.19.9; execution limits contain every fixed ceiling above with
explicit byte/message/second units. Count integers are nonnegative, not booleans;
hash fields are lowercase 64-hex strings. No additional keys are accepted.

Each recording has exactly:

```text
recording_id, raw_sha256, size_bytes, source_declaration_status,
status, failure_code, invalidation_codes, reader_failure_context,
stream_integrity, readiness
```

Identity/source-declaration fields inherit registration/v0.19.9 shapes.
`stream_integrity` is the exact v0.19.9 `decode_check` object or null, retaining
per-channel/schema advertised-versus-decoded counts and exact selected CRC
coverage. `reader_failure_context` is the existing safe v0.19.9 context or null;
never export exception text, raw paths, coordinates, literal source IDs or a
positive decoded prefix as completed observations. Invalidation labels are
static and sorted. A recording has status `complete` or `inconclusive`.

Complete `readiness` has exactly these keys:

```text
counts, diagnostics, odometry, source_clock_order, log_clock_order,
sensor_geometry_support, complete_condition_support,
condition_failure_counts, exclusive_attrition
```

The first eight values inherit the exact existing readiness/domain shapes and
meanings at merged PR #33 (`12ddee6a4c855ed522378fa9742aef993a4bcb5f`), documented
in [output contracts](output_contracts.md#v0196-generic-development-recording-readiness).
Source clocks retain original storage-order estimate/reference statistics;
log clocks cover all three selected topics, matching existing shapes.
support histograms and condition/static failure maps remain sorted.
`exclusive_attrition` has exactly `decoded_estimate_message_count`, `stages`,
`complete_condition_frame_count`. `stages` is a nine-element array in the
fixed cascade order; each entry has exactly `stage`, `input_count`,
`rejected_count`, `remaining_count`, `failure_code_counts`. Each rejection map
uses static scientific labels and sums to `rejected_count`; input minus rejected
equals remaining. The next input equals the previous remaining. First input
equals decoded EDP count; last remaining equals complete-condition frame count.
Sensor-admission input equals all-source anchored H100 candidates; its remaining
equals SENSOR geometry frame count. Counts must reconcile with inherited
diagnostics and both support summaries; overlapping diagnostics remain separate.

Unsupported EDP/RLMB scientific binding, incomplete streams, resource limits or
scientific execution errors make `readiness` null. A completely reconciled
stream may retain `stream_integrity` if only subsequent scientific processing
fails. Interrupted decoding makes both null. Raw/registration/predecessor
identity invalidation nulls both. Never publish completed-prefix readiness.
The first cause remains visible; invalidation adds separate evidence without
masking it. Completed other recordings may remain in an inconclusive batch,
but no pooled counts or consumable partial numeric archive is created.

Preserve the existing odometry failure semantics: a fully decoded odometry
stream with an unsupported scientific binding or poisoned geometry can leave
completed estimate/reference geometry observable while condition availability
is reported as unavailable through the existing odometry/condition shapes.
This is not a completed zero-residual finding, nor permission to invent speed.
Container corruption or an incomplete odometry stream still invalidates the
whole scientific readiness result.

Batch status is complete only if all recording scientific processing and
identity/publication checks completed. Exit 0 means complete, including genuine
zero support; exit 3 means a preserved inconclusive report; exit 2 is preflight,
input/dependency failure without a report. A partial/interrupted write is not a
completion marker. No report is a numeric archive, fit, split or deletion gate.

## Required implementation evidence after contract GO

Test synthetic parity with existing descriptor bindings, timestamp ties/missing
clocks/uint64 extremes, pairing before filtering, lane-map/unknown provenance,
anchor rejection, no extrapolation, H100 support and exact six-feature behavior.
Demonstrate exclusive cascade reconciliation, genuine-zero complete publication,
odometry-poison geometry retention, unsupported E/R binding and interrupted
stream nulling, record/pair gap/reset and singleton sequence behavior.

Test same-descriptor and metadata mutation handling, no repeated hashing or
whole-summary fallback, nonzero/zero CRC coverage, actual-versus-advertised
limits, timer/database/sidecar floors, temp cleanup and first-cause retention.
Exercise a large synthetic index under constrained memory and compare old
wrappers/default decoder outputs to unchanged baselines. Keep old tests passing.
Use Python 3.10/3.12 CI and exact pushed-head implementation review.

After contract GO, implement/test/review/CI and merge; then provide a separately
specified one-file private counts-only command with fresh paths. Preserve old
successful reports. Numeric export/strict validator, target/population/session
admission, matched real model execution and verified raw retirement remain
separate later consumers. The proposed catalogue is not implemented here.
