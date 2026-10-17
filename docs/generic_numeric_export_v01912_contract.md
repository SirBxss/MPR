# Proposed v0.19.12 generic development numeric export and validation

Date: 2026-10-17. Contract revision:
`v0.19.12-generic-development-numeric-export-2026-10-17-a2`.
Status: **documentation-only review candidate; no new CLI is implemented**.
Base is actual merged main `7e4a06b`, tree `c9600a0`. The
[completed pilot](new_development_readiness_result_20261016.md) motivates this
next consumer. Review this precise boundary before implementing its raw reader
and standalone validator together. This proposal does not authorize a private
run, real fit, outing admission, final-data inspection or raw-cache deletion.

## Target, population and schema policy

Export development-only, recording-local SENSOR EDP-minus-spatially-aligned-RLMB
pseudo-residuals. Preserve exactly 21 stations `0,5,...,100 m`, increasing-station
RLMB left-normal sign (positive left), origin projection, common forward H100
coverage, <=1 m anchor and no extrapolation. RLMB remains a map-relative
pseudo-reference. Equal recorded times do not establish physical frame or clock
equivalence. No LANE_MAP/all-topology pooling or sensor-lane target is introduced.

Reuse the existing ungated mutual-nearest timestamp matcher, every reviewed
per-version binding, qualifier, direct-reference-path rule and frozen six-feature
arithmetic. Features, in order, are `speed_mps`,
`estimated_mean_abs_curvature_per_m`, `estimated_curvature_delta_per_m`,
`confidence_near_mean`, `confidence_middle_mean`, `confidence_far_mean`.
No reference, residual, file/session identity or later estimate is a feature.
No standardization, fitting, imputation, padding, time repair or filtering by
residual magnitude/model outcome occurs.

Explicit prospective numeric-consumer policy: retain structural legacy-v1 and
the previously reviewed exact flag-absent-v2 root
`dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4`;
add the fixed v0.19.11 root
`604f854d430cf394693b4fe8944b8bbd12d10959e33935e716d65955a0b2ab9a`
**only inside this new numeric consumer**, subject to exactly the a2 generation,
required-model, declared NO_ERROR/KEEP_LANE/SENSOR and additional consumer checks.
Use [the a2 evidence and semantic argument](edp_descriptor_compatibility_v01911.md),
including interface 2.3's actual custom options and the explicit assumption that
the producer follows BMW's major-version semantic-compatibility policy. This
proposal does not claim a new deployed-producer trace or unconditional semantic
identity from a hash. Reassess that assumption before real fits.

The numeric workflow obtains all admission, late descriptor checks and geometry
conversion exclusively through composition around the **unchanged v0.19.11
`ScientificSink`**. Do not subclass/replace its scientific methods, mutate its
policy, add a call passing `allow_bounded_v01911_edp=True`, change a shared-helper
signature or edit `io/bounded_recording_readiness.py`. Its revision stays
`v0.19.11-bounded-recording-readiness-2026-10-16-a2`. The newly reviewed numeric
consumer policy authorizes this reuse; it does not generalize old bounded GO.

The exporter defines one frozen `NUMERIC_ESTIMATE_ADMISSION_POLICY_V01912`
constant and serializes it as `estimate_admission_policy`, with exactly:
`policy_id="v0.19.12-numeric-through-v0.19.11-sink-a2"`,
`mechanism="unchanged_v01911_scientific_sink"`, `structural_legacy_v1=true`,
`flag_absent_v2_root_file_sha256=[dbfcc…,604f…]` (the full hashes above, in that
order), and `historical_defaults_unchanged=true`. Conformance tests must show
that this description equals actual sink admission, including zero-message
versions. An AST check pins exactly the three existing literal-True keyword
call sites in `src/`, all inside that unchanged sink, and byte equality of
the sink source to the accepted release. Keep historical default rejection,
workflows/locks/verifier/archive pins, output contracts and default imports.
Unknown roots remain unsupported. No root list, threshold, feature order or
policy override is accepted from CLI/config/env. A change to this mechanism
or the shared scientific code requires a separate reviewed amendment.

### Confidence semantics: second explicit assumption

The actual interface 2.3 option describes confidence buckets using the external
implementation constant `detail::kConfidenceScoreBucketSize`; it does not state
a numeric width. MPR fixes that width at 5 m. This is an **unconfirmed assumption
separate from the same-major interface assumption**, applicable to every
admitted estimate root. Version compatibility and finite/plausible values do
not establish the constant's value. It affects coverage and all three confidence
features, including the earlier counts-only feature-readiness population.
Do not reinterpret or overwrite that completed predecessor.

Serialize `confidence_bucket_semantics` with exactly `assumed_bucket_size_m=5.0`,
`provenance_status="assumed_unconfirmed_implementation_constant"`,
`applies_to="all_admitted_estimate_roots"`, and
`basis="interface names detail::kConfidenceScoreBucketSize; numeric value not source-traced"`.
For every candidate retain the actual admitting EDP file-descriptor hash, the
selected KEEP_LANE confidence-vector length and its last native spline boundary
in metres. These are observations only: no new admission/filter or feature.
Length/end consistency can challenge an assumption; it cannot verify bucket
width, origin, padding or clamping. Attempt a producer-source trace before real
fits; until confirmed, retain this assumption and root provenance explicitly in
any later reviewed model/evaluation provenance. No real fit is authorized here.

### Outcome exposure and future final-test protection

Numeric export is outcome exposure. Per the accepted v0.17 rule, every recording
in a complete numeric export and **every physical outing it is later shown to
belong to** is permanently development-only, excluded from any later final-test
candidate draw. This conservative rule includes a complete empty numeric export.
The already retained pilot is declared development-only; no new declaration is
needed from the owner for that pilot. New exports require development-only
declaration in the immutable source specification **before** numeric work.
Never automatically declare/export the whole available pool. Prospective final
candidates may receive embargo-compatible counts-only readiness, not numeric
export or residual/feature inspection under this consumer.

The complete summary and validator must bind an exposure marker to every
registered raw hash. The future generic session/split consumer must ingest all
complete-export exposure records, propagate exclusions across physical-session
links and aliases, and reject any exposed outing as `final_test`, even if it
was regrouped or re-exported. It must prospectively define final selection from
the still-unexposed eligible pool; the old hash draw cannot simply be applied
to a mixed exposed/unexposed collection. An inconclusive export never proves
final eligibility; separately known inspection, including from a failed attempt,
still triggers the existing permanent-development rule. Preserve exposure
records after eventual raw retirement.

## Proposed entry points and exact prerequisites

The future exporter subcommand is `recording_ingestion export-residuals`, requiring
registration directory, preserved complete inventory/decode/readiness report
paths, an explicit `--expected-readiness-sha256`, existing local scratch, a new
output directory and exactly the three explicit EDP/RLMB/odometry topics. These
names are reserved by this draft and are not executable commands today.
The readiness predecessor must have the exact v0.19.11 a2 revision, complete
batch and per-recording status, exact registration/specification/inventory/
decode lineage, selection, bindings, limits and source-declaration observations.
Unsupported/null readiness is not exportable. Preserve original unavailable
session/acquisition declarations as unavailable.

Validate strict JSON (exact field sets/types, no duplicate keys/nonfinite values),
exact registration directory membership, every predecessor shape and digest,
reader/policy revisions, all raw IDs/sizes/hashes and flags before reserving an
output or hashing raw. Reuse bounded-readiness predecessor validation rather
than inventing permissive alternatives. Validate readiness's source fingerprint
against either the accepted v0.19.11 source fingerprint
`069e1095426bd82f675af093356e699868306d2fa297a8a27b7e058295d062b7`
or the running export release's exact fingerprint (for newly created readiness
on that same reviewed implementation). Record which case applies; no arbitrary
caller fingerprint allowlist. Report the exporter's own fingerprint separately.
An explicit expected hash is an identity guard, not an override of readiness
semantics. The already successful registration/inventory/decode are
immutable dependencies; do not rerun those commands as prerequisites.

For each recording, open one raw descriptor, freshly hash it once, verify its
registered bytes/state, reconstruct the exact summary and selected decoded-stream
oracle, and run the existing bounded scientific stages. Reuse the disk-index
reader and disposable scientific SQLite staging. Do not route large files through
the historical whole-summary payload reader or retain decoded messages/paths
in a Python history. Compare strict canonical JSON for these complete objects
against preserved readiness **before calculating any residual for that file**:

| Comparison | Required equality |
|---|---|
| Stream | Entire `stream_integrity`, reader/selection/CRC policy |
| Bindings | Entire ordered `binding_observations` |
| Science | `counts`, `diagnostics`, `odometry`, `source_clock_order`, `log_clock_order` |
| Population/support | `sensor_geometry_support`, `complete_condition_support`, `condition_failure_counts`, `exclusive_attrition` |
| Availability | `condition_availability`, `recorded_input_causality_checked` |

Fresh timings/resources/dependency versions and runtime source fingerprint are
new observations, not equality targets. Counts, descriptor identities, clocks,
duplicate handling, conditions and sequence support are equality targets.
Mismatch is inconclusive, not a new zero population or accepted replacement
readiness. Reconcile all raw states, registration and predecessor bytes again
at final publication, including files processed earlier in a batch. No usable
partial batch can be published if a later recording/identity check fails.

## Candidate populations, availability and sequences

The candidate audit has one row for every SENSOR anchored H100 pair before
numeric construction, including feature and residual failures. Reuse existing
`aligned_residual` and condition finalization arithmetic on staged geometry;
do not perform a second raw read for a separate feature diagnostic. Candidate
capacity is bounded by the validated preserved count and fixed aggregate cap.

Implement new I/O/orchestration outside the unchanged sink: a delegating
observer may store bounded, read-only scalar metadata alongside the existing
scientific tables, without retaining messages or changing any inherited value.
Call the real sink finalizer and reconcile preserved readiness first. While its
workspace is still open, a second **staged-SQLite-only** pass can use the existing
`_count_staged_geometry` with `diagnostics=None` and a scalar pair callback,
then `_finish_conditions(compute_residuals=False)`. Do not call `geometry.finish`
again with the original accumulating diagnostics. Require exact counts,
condition failures and both pre-residual support objects again, including the
existing unavailable-odometry behavior, before the new checked residual loop.
This repeats no raw hash/decoding, conversion or admission. All repeated staged
work remains within the original deadline, caps and checkpoints. Observer data
must not affect the frozen science or masquerade as a recovered feature.

Let P be the pre-residual geometry count and Q its complete-feature count,
both reproduced exactly from readiness. Let N be successfully constructed finite
residuals and C their complete-feature subset. Require `N <= P`, `C <= Q`, and
report the exact post-construction exclusion/failure partition. The **only**
allowed row-level residual failure is `residual_non_finite`; retain that audit
row and exclude its vector. The full coded surface of the reused numeric
alignment/residual functions is:

| Code | v0.19.12 handling after readiness equality |
|---|---|
| `residual_non_finite` | Explicit candidate failure; no vector |
| `anchor_distance_exceeds_1m_or_invalid` | Inconclusive batch: contradicts the already passed anchor check |
| `reference_alignment_projection_ambiguous` | Inconclusive batch: contradicts the same projection used in readiness |
| `reference_alignment_estimate_coverage_incomplete` | Inconclusive batch: contradicts H100 coverage |
| `reference_alignment_reference_coverage_incomplete` | Inconclusive batch: contradicts aligned reference H100 coverage |

The table is exhaustive for `aligned_residual` and the alignment functions it
calls at this release. Other coded errors, bare `ValueError`/`TypeError` (including
the historical finalizer's class-name strings), exceptions, incomplete streams
or resource failures make the batch inconclusive; do not turn them into row
exclusions. The validator rejects any other row code. Do not silently drop rows
or promise readiness counts are already numeric vectors. A valid complete empty
archive is permitted. Historical v0.19.2 failure handling remains unchanged.

Retain geometry-only vectors despite missing conditions. Store conditions only
for complete rows, using an explicit increasing index into residual rows.
`conditions[i]` aligns with `residuals_m[conditioned_profile_indices[i]]`.
No condition zeros/NaNs/masks masquerade as observed six-feature inputs.

The fixed speed definition uses displacement from t−50 ms to t with at most
50 ms pose brackets. Every contributing source timestamp must be <= t, and
every used log time and the estimate log time must be positive with used logs
<= estimate log time. Record previous/current lower/upper source brackets and
maximum used log/publish times for successful arithmetic even if causality
rejects it. Preserve future-source, late-log and missing-log failures separately.
Publish times are evidence, not a new gating clock. Keep physical input
availability explicitly unproven. Exact duplicate poses/conflicting times,
odometry schema poisoning and unavailable-speed behavior remain unchanged.

Use original canonical candidate/pair/message identities. Assign global
candidate indices in registration order, then canonical pair order; store
message/pair indices file-locally. Reconstruct sequences independently for the
exported geometry and complete-feature populations using the existing rules:
split on recording changes, nonconsecutive original estimate or pair indices,
nonpositive source-time gaps or gaps >200 ms. Residual/condition exclusion can
therefore create additional breaks. Never bridge files, filtered rows or missing
features, even when a common physical session is claimed. Reset generated
state once per sequence in any later approved model consumer.

## Artifact schemas

A complete new directory contains exactly `numeric_export.json`,
`candidate_audit.json`, `residuals.npz`. The strict JSON summary is the final
atomic completion marker and hashes the exact other two files. The summary is
not self-hashed; its separately retained receipt/expected hash pins its bytes.
No directory without a complete summary is a dataset. Publication failures
must never leave a complete marker or a mixture that validates as complete.

The summary has exactly these fields:

```text
contract_revision, purpose, status, failure_code, batch_id,
registration_sha256, source_specification_sha256,
preserved_inventory_report_sha256, preserved_decode_report_sha256,
preserved_readiness_report_sha256, preserved_readiness_contract_revision,
preserved_readiness_runtime_source_sha256, runtime_versions,
runtime_source_sha256, reader_implementation, scientific_policy_revision,
estimate_admission_policy, confidence_bucket_semantics, outcome_exposure_policy,
schema_semantics_basis, schema_semantics_deployed_producer_retraced,
resources_at_start, execution_limits, technical_recording_count,
independent_outing_count, roles_assigned, cohort_lock_created, model_fitted,
standardizers_fitted, residuals_exported, numeric_conditions_exported,
recorded_input_causality_checked_for_all_recordings,
physical_input_availability_proven, reference_independence_proven,
raw_cache_deletion_authorized, pre_residual_candidate_count,
pre_residual_complete_condition_count, condition_failure_counts,
residual_failure_counts, support, recordings, artifacts_sha256, interpretation
```

`purpose=development_only_recording_local_edp_rlmb_numeric_export`.
`scientific_policy_revision` equals this contract revision.
`outcome_exposure_policy="permanent_development_only_after_numeric_export_v01912_a2"`.
The two semantic/policy objects have the exact frozen shapes above. The only complete
artifact hash keys are `candidate_audit.json` and `residuals.npz`. Export flags
mean successful publication, including the empty case; inspect support counts
for actual yield. Independent outing count is null. Roles, lock, fitting,
standardizers, physical availability/reference independence and deletion flags
remain false. Recorded-causality-checked means checks completed, not every row
passed. No schema producer re-trace may be asserted solely from the old receipt.

Each recording has exactly `recording_id`, `raw_sha256`, `size_bytes`,
`source_declaration_status`, `status`, `failure_code`, `invalidation_codes`,
`reader_failure_context`, `binding_observations`, `stream_integrity`,
`readiness`, `condition_availability`, `recorded_input_causality_checked`,
`readiness_matches_preserved`, `execution_observations`,
`candidate_start`, `candidate_stop`, `residual_failure_counts`, `support`,
`outcome_exposure`.
The inherited fields have the exact v0.19.11 shapes; comparison is mandatory,
not a trusted Boolean alone. Half-open candidate ranges partition all audit
rows in registration order. For complete records, `outcome_exposure` contains
exactly `status="permanently_development_only"`, `final_test_eligible=false`,
`applies_to="recording_and_any_linked_physical_outing"`. Its enclosing recording
binds this marker to the exact registered raw hash. On an inconclusive batch it
is null for all records, because no complete numeric dataset is published;
that null never overrides separately known exposure. `support` has exactly the
following **six** fields: `geometric_profile_count`, `conditioned_profile_count`,
`geometry_sequences`, `conditioned_sequences`, `geometry_transition_count`,
`conditioned_transition_count`. Each sequence has the existing eight keys in
[output contracts](output_contracts.md#v0192-batch02-exploratory-residuals).
Readiness's seven-field `summarize_support` object is a different schema.
Both export support populations are independently rebuilt. Per-file sequence row ranges
are file-local; aggregate ranges index the full corresponding population.

The audit object has exactly `contract_revision`, `rows`. Each row contains:

```text
recording_id, candidate_index, pair_index, estimate_message_index,
reference_message_index, estimate_source_time_ns_decimal_private,
reference_source_time_ns_decimal_private, estimate_log_time_ns_decimal_private,
estimate_publish_time_ns_decimal_private,
signed_reference_minus_estimate_ns_decimal,
condition_failure_codes, speed_bracket_evidence, residual_failure_code,
estimate_file_descriptor_sha256, confidence_vector_length,
estimate_native_station_end_m,
anchor_distance_m, reference_anchor_station_m,
residual_available, conditions_available
```

Clock fields are canonical base-10 strings, unsigned uint64 for source/log/
publish evidence and signed exact difference for reference-minus-estimate.
Never convert through float, datetime or a JavaScript number. Source clock
semantics are not inferred as UTC. Speed evidence is either an empty object or
the six existing bracket/max-log/max-publish keys from v0.19.2, renamed with
`_ns_decimal_private`, plus `minimum_input_log_time_ns_decimal_private`, each
with exact uint64 text. Obtain the minimum log from the same duplicate-audited
odometry representatives identified by those four bracket timestamps while the
workspace is open. This seventh observational value does not change the sink,
speed arithmetic or readiness; maximum log alone cannot prove every used log
is positive. Preserve available evidence
even on causal rejection. Both anchor fields are finite on residual success,
otherwise null. `conditions_available` describes the independent feature check;
only residual-success AND condition-success rows enter the conditioned arrays.
`estimate_file_descriptor_sha256` is the lowercase 64-hex hash of that message's
own root `FileDescriptorProto` bytes, agreeing with its supported binding. It
is not the enclosing FileDescriptorSet hash. `confidence_vector_length` is the
nonnegative integer count on the uniquely selected KEEP_LANE path, including
zero for a present empty vector. `estimate_native_station_end_m` is the finite
last native `model_parameters.segment_starts` value on that path, read using
the existing bound schema fields, not an ego-relative station or inferred
length. Capture these scalars during delegation without a new conversion or
classification opt-in. A geometry candidate missing this observational identity
is a batch inconsistency, not a silently omitted audit row. They stay out of
the NPZ feature columns. Vectors/features are not duplicated in audit JSON.

The NPZ contains exactly the fourteen arrays in the v0.19.2 table in
[output contracts](output_contracts.md#v0192-batch02-exploratory-residuals),
with identical shapes, names and meanings, **except `recording_id` uses U48**
to preserve every valid generic registration identifier (maximum 48 ASCII
characters) without truncation. This is a separately versioned archive, not an
accepted input to the pinned old batch02 validator or any training CLI.
Use little-endian float64/int64/U48/U20 in the serialized NPY members, require
exact dtypes and C order, and reject object/structured/subarray alternatives.
`condition_names` remains U48. No ID remapping, casting or silent truncation.
Empty matrices retain shapes `(0,21)` and `(0,6)`; empty offsets are `[0]`.

## Standalone validation and bounded publication

The future separate metadata-only validator requires the export directory,
explicit expected summary SHA-256, registration and preserved inventory/decode/
readiness reports, and a new validation-receipt path outside the export.
It opens no raw MCAP and never mutates or repairs any input. Reject:

- missing/extra/symlink files, noncomplete/unknown revisions, bad expected or
  artifact hashes, predecessor/registration/raw-identity mismatch, incorrect claim
  flags, malformed JSON and duplicate ZIP/JSON members;
- missing/extra NPZ members, wrong dtype/order/shape, oversized headers/payloads,
  inconsistent NPY sizes, trailing bytes, nonfinite values, wrong stations or
  feature order, invalid IDs, lossy/noncanonical timestamps or integer types;
- out-of-range/duplicate/reordered candidate/profile indices, broken row
  mappings, contradictory availability/failure/evidence, unknown residual codes,
  missing/contradictory exposure markers, wrong admission/confidence-assumption
  objects, invalid root/vector-length/native-end observations, unaccounted residual
  loss or per-file/aggregate support/partition disagreement;
- offsets or sequence metadata that differ from an independent reconstruction
  of the original identities/source gaps for each exported population; a
  hashed summary's sequence declarations are not sufficient on their own.

Use `allow_pickle=False` only after ZIP/NPY size and member prechecks; bound
allocation before loading. Verify complete-row source/log causality from audit
brackets and require t/t−50 ms enclosure and <=50 ms bracket spans. Rejection
codes must agree symmetrically with available evidence: with nonempty bracket
evidence, future-source is present iff maximum bracket source time > t; missing-
log is present iff estimate log or minimum used log is nonpositive; otherwise late-log is
present iff maximum used log exceeds estimate log. Empty evidence must instead
have an established arithmetic/odometry-unavailable failure, not an invented
future/late code. Reconstruct sequences with a separate small implementation
or cross-check against independent hand-built oracles, not just a shared call
to the exporter's `sequence_layout`. Do not
infer speed magnitude or raw geometry correctness from scalar audit evidence.
No raw-free validator can independently recompute residual vectors or prove
physical semantics; exporter synthetic conformance, immutable lineage and
independent implementation review remain necessary.

On success, write only a new strict receipt with exactly `contract_revision`,
`purpose`, `status`, `summary_sha256`, `artifact_sha256`,
`registration_sha256`, `source_specification_sha256`,
`preserved_inventory_report_sha256`, `preserved_decode_report_sha256`,
`preserved_readiness_report_sha256`, `runtime_source_sha256`, `runtime_versions`,
`geometric_profile_count`, `conditioned_profile_count`, `raw_opened`,
`model_admission_authorized`, `raw_cache_deletion_authorized`.
Revision is `v0.19.12-generic-numeric-validation-2026-10-17-a2`, purpose is
`validate_development_numeric_archive_without_raw_or_model_admission`, status
is `complete`, and the final three Booleans are false. The receipt is hashable
evidence, not cohort/fit/retrieval authorization. Invalid input returns exit 2
without a success receipt; valid complete empty archives return exit 0.

Exporter input/preflight failures return exit 2 with no new output directory.
A supported complete batch, including zero yield, returns exit 0 with exactly
three artifacts. Post-preflight science/reader/resource/oracle/identity failure
returns exit 3 with **summary only**: null aggregate candidate/support/failure
counts, empty artifact hashes and false export flags. Complete per-file
observations may remain but are not a dataset. Unentered comparison/range/support
fields are null. Preserve first failure plus later distinct invalidation codes.
An interrupted writer without the final marker is unusable, never complete.

The existing per-topic caps, <=512 MiB index/<=8 GiB science/<=8.5 GiB combined
SQLite limits, PRAGMAs/cache/page/file checks, 4 GiB process limit, 6 GiB initial
available-memory requirement, >=10 GiB runtime scratch floor and 1,800-second
per-recording science deadline remain fixed. Numeric work for each file is
inside that same deadline and must have cooperative checkpoints; it is not an
unbounded phase after the timer. Hashing and <=300-second fresh summary remain
separate, as before. Add a separate <=300-second final serialization/publication
deadline and the same limit for standalone validation.

Reserve a further 1 GiB for all aggregate artifacts/staging before the first
raw hash: >=19.5 GiB initial free scratch, no relaxation of the runtime floor.
Cap the sum of advertised EDP messages across the registration at 100,000
(preflight exit 2 otherwise), audit JSON at 256 MiB, summary at 64 MiB, and NPZ
at 128 MiB in **both compressed and total uncompressed NPY size**. This bounds
aggregate candidate/vector retention even across 64 registered recordings.
Output staging and final destination must have the **same `st_dev`** as checked
scratch (check the existing parent before creation and the actual directory
after creation); the future runbook must choose a destination satisfying this.
Scratch under `/var/tmp` and reports under the repository need not share a
device, so verify rather than assume. Account for live temporary plus published bytes within the extra
1 GiB and reject path overlap with inputs/registration/raw. Check free space
during both scientific processing and serialization. No user cap override,
file-temporary SQLite fallback, hidden extra spool or rerun on exhaustion.

Validate staged summary/audit/NPZ with the standalone logic before installing
the completion marker. Record input/artifact states and hashes across validation
and late publication checks so validation cannot bless subsequently changed
bytes. Cleanup may remove only owned new temporary/output files; prior outputs
and raw are immutable. A failed batch never leaves a complete partial archive.

## Implementation acceptance and subsequent data work

Implement raw-to-archive and standalone validator in one focused follow-up,
not another counts-only scanner. Preserve the historical suite and prove:

1. Synthetic MCAP end-to-end equality with preserved v0.19.11 readiness,
   including empty/geometry-only/complete/mixed schema/unsupported odometry;
   exact-source fingerprint, one raw hash and late predecessor/raw mutation.
2. Positive-left/negative-right residuals on rotated/translated paths, fixed
   21 stations, no extrapolation or alternate branch/short-horizon admission;
   unchanged features and rejection of future-source/late-log speed.
3. Maximum-length IDs, uint64 clocks including >2**53 and near 2**64−1,
   interleaved storage/source order, missing-feature/residual gaps, separate
   recording boundaries and complete empty-array round trips.
4. Independently mutated hashes, fields/types, NPZ members/dtypes/shapes/headers,
   candidate mapping, condition subset, timestamps, causality, partitions and
   sequences all fail strict validation; coherent artifact rehash alone cannot
   bypass the pinned summary hash or independent lineage/support checks.
5. Bounded serialization/validation, cleanup, disk/deadline/process limits,
   atomic publication and batch failure after an earlier successful file.
   Default historical consumers still reject the second root. Pin unchanged
   sink bytes/revision and the three opt-in call sites; test observer and staged
   second-pass parity without double-counting diagnostics or another raw read.
6. Every complete export has the required per-raw exposure marker; unknown or
   forged markers fail validation. Root/confidence observables survive mixed
   supported versions, empty/invalid confidence values and failed conditions
   without changing readiness. Unknown residual codes and all four geometry
   parity-violation codes null the batch rather than silently reducing it.

Normal exact-head Python 3.10/3.12 CI and focused numeric-consumer policy/code
review precede merge and one new versioned private export on retained raw.
Neither proposal/contract acceptance nor that future export enables real-flow
training. Next establish reviewed generic physical-session/cohort/split lineage,
process development drives incrementally, freeze matched roles/rows and satisfy
the unchanged support/model gates. Keep old data until durable archives and
tested exact-byte retrieval justify a separately authorized retirement.

The owner reports newer, manually screened data beyond the earlier pilot.
That pilot is a retained compatibility/engineering case, not a collection-wide
quality estimate. After the export path is reviewed and merged, check a small
declared-development selection from the **newer** data; do not require improved
yield from the old pilot before doing so. Predeclare technical H100/reference/
causal-support screening criteria, retain rejection counts and state that later
claims apply to the screened population. Do not select by residual size/model
performance or consume all prospective final candidates during development.
The audit's future-lead and bracket-span evidence can test clock-phase hypotheses
on each new dataset, without another raw diagnostic or residual-based selection.
Any speed-definition change remains a prospective separate amendment; the old
pilot's regular windows do not establish such a change is needed on newer data.
