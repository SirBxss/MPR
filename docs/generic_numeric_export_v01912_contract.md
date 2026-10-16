# Proposed v0.19.12 generic development numeric export and validation

Date: 2026-10-16. Contract revision:
`v0.19.12-generic-development-numeric-export-2026-10-16-a1`.
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

Implementation must provide a fixed, explicitly named numeric policy internally;
it must not merely enable the bounded-only Boolean in an unrelated consumer.
Keep historical default rejection and all historical workflows/lock/verifier/
archive pins, output contracts and default import behavior intact. Unknown roots
remain unsupported, including zero-message selected versions. No root list,
threshold, feature order or policy override is accepted from CLI/config/env.

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

Let P be the pre-residual geometry count and Q its complete-feature count,
both reproduced exactly from readiness. Let N be successfully constructed finite
residuals and C their complete-feature subset. Require `N <= P`, `C <= Q`, and
report the exact post-construction exclusion/failure partition. A coded expected
numeric geometry failure retains its audit row and excludes that vector; an
unexpected error, incomplete stream or resource failure makes the batch
inconclusive. Do not silently drop rows or promise that readiness counts are
already numeric vectors. A valid complete empty archive is permitted.

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
`scientific_policy_revision` equals this contract revision. The only complete
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
`candidate_start`, `candidate_stop`, `residual_failure_counts`, `support`.
The inherited fields have the exact v0.19.11 shapes; comparison is mandatory,
not a trusted Boolean alone. Half-open candidate ranges partition all audit
rows in registration order. `support` uses the existing v0.19.2 seven-field
shape in [output contracts](output_contracts.md#v0192-batch02-exploratory-residuals)
but is independently rebuilt for this population. Per-file sequence row ranges
are file-local; aggregate ranges index the full corresponding population.

The audit object has exactly `contract_revision`, `rows`. Each row contains:

```text
recording_id, candidate_index, pair_index, estimate_message_index,
reference_message_index, estimate_source_time_ns_decimal_private,
reference_source_time_ns_decimal_private, estimate_log_time_ns_decimal_private,
estimate_publish_time_ns_decimal_private,
signed_reference_minus_estimate_ns_decimal,
condition_failure_codes, speed_bracket_evidence, residual_failure_code,
anchor_distance_m, reference_anchor_station_m,
residual_available, conditions_available
```

Clock fields are canonical base-10 strings, unsigned uint64 for source/log/
publish evidence and signed exact difference for reference-minus-estimate.
Never convert through float, datetime or a JavaScript number. Source clock
semantics are not inferred as UTC. Speed evidence is either an empty object or
the six existing bracket/max-log/max-publish keys from v0.19.2, renamed with
`_ns_decimal_private`, each with exact uint64 text. Preserve available evidence
even on causal rejection. Both anchor fields are finite on residual success,
otherwise null. `conditions_available` describes the independent feature check;
only residual-success AND condition-success rows enter the conditioned arrays.
Vectors/features are not duplicated in the audit JSON.

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
  mappings, contradictory availability/failure/evidence, unaccounted residual
  loss or per-file/aggregate support/partition disagreement;
- offsets or sequence metadata that differ from an independent reconstruction
  of the original identities/source gaps for each exported population; a
  hashed summary's sequence declarations are not sufficient on their own.

Use `allow_pickle=False` only after ZIP/NPY size and member prechecks; bound
allocation before loading. Verify complete-row source/log causality from audit
brackets and require t/t−50 ms enclosure and <=50 ms bracket spans; do not
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
Revision is `v0.19.12-generic-numeric-validation-2026-10-16-a1`, purpose is
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
Output staging and final destination must use the checked local scratch
filesystem; account for live temporary plus published bytes within the extra
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
   Default historical consumers still reject the second root.

Normal exact-head Python 3.10/3.12 CI and focused numeric-consumer policy/code
review precede merge and one new versioned private export on retained raw.
Neither proposal/contract acceptance nor that future export enables real-flow
training. Next establish reviewed generic physical-session/cohort/split lineage,
process development drives incrementally, freeze matched roles/rows and satisfy
the unchanged support/model gates. Keep old data until durable archives and
tested exact-byte retrieval justify a separately authorized retirement.
