# Batch02 exploratory EDP/RLMB residual extraction

Date: 2026-09-24. Revision:
`v0.19.2-batch02-exploratory-residuals-2026-09-24-a1`.
Prepared after merged PR #23 (`49ca002`, tree `ee8392a`). This is a separate
exploratory extraction scope, not v0.17 outing admission or a model experiment.
Its exact pushed implementation requires focused review GO and normal CI before
one private run. No private extraction result is known at declaration time.

## Evidence and objective

The completed v0.19.1 diagnostic preserves every v0.19.0 count. Of 7,743
anchored H100 pairs, 376 have available SENSOR_TOPOLOGY EDP estimates, split
10/0/40/326 by recording. Every anchored pair has numeric source-time delta zero.
All 29,569 generic reference-conversion failures are empty lane-segment lists.
There is no observed coordinate-pool defect or retained numeric offset to repair.
Read `docs/recording_pair_diagnostics_batch02_result.md` for the evidence limits.

The next output should contain actual 21-station pseudo-residuals, fixed
conditions where available, and recording-local sequence support. No model fit,
new feature definition, topology relaxation, horizon change, new time gate,
time shift, motion compensation, threshold sweep or LTSB/LTM/EM adoption occurs.
RLMB remains a pseudo-reference, not independent physical ground truth.

## Exact inputs and preservation

Use exactly the four registered batch02 files and the original registration and
container-context bytes, plus both completed JSON reports. Required SHA-256:

| Input | SHA-256 |
|---|---|
| Registration | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |
| Container context | `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad` |
| v0.19.0 feasibility | `89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec` |
| v0.19.1 diagnostics | `fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb` |

Validate complete status, exact paths/sizes/hashes, source fingerprints, no-role
flags and full original counts across both reports before raw hashing/decoding.
Import actual decoder dependencies before any output. Rehash all four raw files
before payloads; check file state before/after each inspection and again across
all files before export. Never edit prior outputs or invent session declarations.

Reconstruct complete EDP/RLMB streams with the same converters and ungated
mutual-nearest matcher. Compare **every original count and every v0.19.1
per-recording diagnostic field** exactly before calculating residuals. Any
drift or incomplete execution is inconclusive; no dataset from a partial batch
is exported. A callback retains only pair indices and scalar identities for
sensor candidates; its capacity is the preserved per-recording candidate count.
No private coordinates/payloads are retained in a Python history.

## Residual and feature populations

The unchanged geometric population requires available/no-error EDP,
SENSOR_TOPOLOGY, full H100 coverage and at most 1 m projection-anchor distance.
Continue to account for LANE_MAP through preserved counts; do not export those
7,367 candidates as sensor profiles. Unknown source independence stays unknown.

Reuse `compare_spatially_aligned_paths` on the reconstructed native paths:
project the EDP station-zero ego footpoint onto RLMB; sample common forward
arc-length offsets `0,5,...,100 m`; compute estimate-minus-reference dotted with
RLMB's left unit normal. Positive means left. Do not assume spline s=0 is the
rear axle, compare by vertex index, extrapolate, or infer frame equivalence from
equal source timestamps. Export only finite 21-station vectors, with explicit
construction failures for any candidate that cannot produce one.

**Two populations are explicit.** Feature availability and prospective sequence
support are assessed before residual calculation. A geometric vector does not
mathematically require a vehicle-speed input, so retain that vector even if
conditions are unavailable. The archive separately identifies profiles with all
six finite conditions passing the new recorded-clock checks. This separation is
a prospective exploratory output decision; it neither changes old eligibility
artifacts nor promotes incomplete rows into a conditional training dataset.
No feature is imputed and no missing-feature row is represented by a numeric
zero condition vector. Only the complete subset has six-column condition rows.

EDP-only curvature/confidence summaries use the existing functions and schema-v1
order. They may be computed transiently while streaming available sensor EDP
records to avoid retaining decoded messages; only paired candidate data are
exported. No RLMB, residual, future estimate or recording identity is a feature.

## Explicit speed availability decision

The existing `derive_unsigned_odometry_speed` evaluates poses at the estimate
source epoch t and t-50 ms using interpolation brackets of at most 50 ms, then
divides displacement by 50 ms. That arithmetic can use a sample after t to
interpolate the current pose. Successful interpolation therefore does not prove
a causal feature. Preserve its numeric definition and add these **separate,
conservative extraction checks**, without rewriting historical artifacts:

1. Every contributing odometry state timestamp must be <= t. With unchanged
   non-extrapolating interpolation at t, this requires a sample exactly at t;
   the earlier t-50 ms endpoint may be interpolated from causal past samples.
2. The estimate and contributing odometry MCAP log timestamps must be positive,
   and every contributing log timestamp must be <= the estimate's log timestamp.
3. Report rejected future-state, late-log and missing-log inputs separately,
   preserving both pose brackets and maximum contributing log/publish times.
   Do not shift t, use nearest/held speed, widen a bracket or interpolate features
   across EDP frames to obtain additional complete rows.

These are checks under the recorded source/log clock conventions. MCAP log time
is an availability proxy; this does not prove common physical clock semantics,
real vehicle publication latency or online availability. Publish times are
retained as evidence, not assumed to share the source/log clock. The summary
explicitly leaves physical availability unproven. The strict subset may be
small or empty; geometric residuals remain visible in that case.

Odometry uses the established `Adp.OdometryState` scalar decoder rules. Store
poses and chronology in SQLite, with exact uint64 decimal time keys. Coalesce
only exactly pose-identical duplicate state timestamps, choosing the earliest
log/publish representative. Any conflicting timestamp group remains entirely
unusable, as in the existing duplicate policy. Record group/message counts.
No silent row repair. A decoded invalid odometry message, schema/encoding
mismatch or schema change makes speed unavailable for that recording; reference
and estimate geometry can still yield residuals. A reader/decode interruption
or resource/completeness failure makes the recording inconclusive instead.

## Sequence definition

Build separate layouts for geometric profiles and the complete-feature subset.
Both are recording-local. Require consecutive original estimate indices and
canonical pair indices, and strictly positive source-time gaps <=200 ms. A
skipped estimate, unmatched/excluded pair, missing condition (for the conditional
layout), residual construction failure, nonpositive gap or larger gap breaks
the corresponding sequence. Never bridge files. Storage indices are retained;
out-of-order storage can conservatively fragment support and is not repaired
by claiming unproven continuity. Sequence summaries expose length, duration,
adjacent-transition count and break reasons. Singletons remain with zero duration
and zero transitions. No padded or synthetic frames are inserted.

This reuses the established adjacency/gap protections without supplying the
physical-drive IDs required by historical sequence builders. Technical recording
IDs are not inferred physical outings and are never input features or roles.

## Bounded execution and output

Read only EDP, RLMB and `/adp/odometry` in indexed storage order in one pass.
Keep existing 100,000-message limits for each geometry topic, a fixed
300,000-message odometry cap, 128 MiB chunk/record cap, 8 GiB SQLite page cap,
4 MiB page cache, disk temporary storage and no mmap. Require 6 GiB available
RAM, 10 GiB free scratch and a 4 GiB process address-space limit applied before
heavy imports. Odometry caps are resource limits, not eligibility thresholds.
The context inventory contains 173,518 odometry messages across the four files;
no full decoded payload list or pose-history list is needed. At most four
bracketing poses are brought into Python per candidate. A temporary spool is
removed on normal completion and handled exceptions; SIGKILL may leave a spool.

The module-only CLI writes into a new absent directory. On complete execution:

- `exploratory_residuals.npz`: deterministic physical-unit profiles, precise
  identities/timestamps, separate complete conditions and sequence offsets;
- `candidate_audit.json`: one row per original sensor candidate, including
  missing-feature and geometry-failure evidence; and
- `exploratory_residual_summary.json`: lineage, versions, source fingerprint,
  per-recording observations, support counts and hashes of the other files.

On inconclusive execution, write only the summary with null aggregate support
and no archive/audit. A complete summary is written last and is the completion
marker; interrupted serialization without it is not a usable dataset. Preserve
that failed output and do not silently retry into it. Exact schemas are in
`docs/output_contracts.md`. All new outputs contain private recording evidence
and stay outside Git. There is no train/test split, standardization, model,
planner, figure, outing role or cohort lock. Exit codes remain 0 complete,
2 preflight/execution error and 3 inconclusive batch.

## Verification and next decision

Tests must establish analytic residual sign and displaced origins, no
extrapolation/anchor relaxation, exact old count/diagnostic parity, feature
parity where causal, explicit future/late/missing exclusions, duplicate conflict
handling, bounded storage and actual indexed Protobuf odometry reading. Cover
lineage/type/raw drift, incomplete streams, file mutation, deterministic output,
empty complete-feature populations, sequence gaps and all four file boundaries.
Old default readers/counts and frozen intake imports must still pass.

After focused review GO and CI, one private extraction run should produce the
first batch02 residual values. Reconcile its complete-feature count and sequence
support before specifying an exploratory Gaussian/AR training protocol. No fit
is authorized by extraction alone. More suitable independently declared outings
remain necessary for the frozen final-data protocol; the 376 upper bound and
unknown session history do not satisfy it. Do not re-request unavailable facts.


## Implementation verification checkpoint

The local implementation passes compilation and whitespace checks. With MCAP
extras installed, 503 tests run: 501 pass and only the wheel/private-parity
opt-ins skip. The focused selection has 100 passing tests (26 new). Actual
indexed Protobuf odometry reading is exercised on generated MCAP bytes.
The frozen merged-base comparison preserves complete counts/diagnostics and
all 24 synthetic record fingerprints, including native geometry-array bytes;
before/after JSON SHA-256 is
`5ce69b351de53c30d13339fe808f38c24245382987e29f58890c306a6cf86360`.
This is synthetic verification, not a rerun of private batch02. Expected source
fingerprint: `96a0df813a1a815fdae963e68ceca1563dd1a89653201453164bf12962c82d6c`.
Focused review and new-head CI are pending; no private v0.19.2 output exists.
