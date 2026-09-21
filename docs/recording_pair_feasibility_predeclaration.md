# Batch02 recording-level EDP/RLMB geometry feasibility

Date: 2026-09-20. Revision:
`v0.19.0-batch02-recording-pair-feasibility-2026-09-20-a1`.
Status at declaration: proposed scope and synthetic-tested implementation,
awaiting focused independent review; no batch02 geometry result had been
inspected. On 2026-09-21 implementation/scope GO and Python 3.10/3.12 CI were
verified, and the one authorized real pilot completed. See
`docs/recording_pair_feasibility_batch02_result.md` for the subsequent evidence.
The rules below preserve the original declaration, not a request to rerun.
The existing package version remains 0.18.1; this is a
separate diagnostic contract, not a change to the v0.17 cohort lock.

## Trigger and scientific scope

The user reports that original session identity, acquisition-clock and export
provenance answers cannot be recovered. Keep them unavailable; do not keep
asking for them, infer attestations from plausible calendar dates, or invent a
manifest that passes v0.17. The four files cannot currently be admitted as
confirmed independent final-validation outings under that unchanged protocol.
This is not evidence that their geometry is unusable or that they are all one
session. No training/development/final role is assigned by this decision.

The returned container-context report advertises complete statistics for all
four files, with disjoint numerical log ranges. Under a conditional Unix-epoch
interpretation they fall on four different dates. Their intervals are about
18, 3, 18 and 57 minutes, not measured eligible-sequence durations. The reported
Linux host had 31 GiB RAM, 2.3 GiB available and 2 GiB swap entirely used.
Whole-file geometry retention in the old intake is therefore an avoidable
resource risk, although no actual out-of-memory failure has been observed.

The separate question now is: **do these exact recordings contain EDP/RLMB
paths that pass the existing H100 geometric coverage and anchor checks when
paired by the canonical numeric timestamp rule?** This is a recording-level
feasibility diagnostic. It does not create an independent-outing audit, change
the estimate/reference definition or evaluate residual quality. Positive
counts support only a later scoped investigation; zero counts do not prove
that no alternative topic/target could work.

The first check uses EDP and RLMB because their converter/projection semantics
already exist. It does not cancel the LTSB investigation. LTSB remains a
separate prospective target with unresolved frame, epoch and correspondence
requirements. Neither EM fusion nor lane-topology-map geometry is substituted
for RLMB. No additional BMW source answer is needed to run this limited check
after its implementation review.

## Frozen inputs and allowed observations

Consume the exact existing administrative artifacts:

| Input | SHA-256 |
|---|---|
| `batch02_registration.json` | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |
| `batch02_container_context.json` | `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad` |

Use only `data/raw/new_independent_outings/batch02`, with exactly the four
registered paths and byte hashes. No v0.17 acquisition manifest is accepted
by this CLI. Their absence does not become a successful declaration: the
output fixes physical-session provenance to unavailable, independent outing
count to null, and role/lock flags to false. Old manifests and outputs remain
immutable. Any future independent-data admission requires the original
protocol's actual evidence, not reinterpretation of this diagnostic.

Validate strict JSON bytes, exact coverage, sizes and current raw hashes
before output creation or payload inspection. This payload-stage hash check
is necessary because the time/RAM follow-up inherited old hashes and checked
only sizes; do not rerun or overwrite the administrative registration.
Detect file state changes during hashing and geometry processing. Preserve
all failures and positive/negative completed results.

Decode only `/adp/estimated_drive_paths` and `/adp/road_lane_map_based` with
Protobuf support. Reuse the existing v0.17.1 EDP descriptor/validity handling
and canonical RLMB converter. No new schema relaxation or v0.18 descriptor
binding is introduced. Per-message reconstruction failures remain records
with their original source timestamp, so geometry never prefilters pairing.
No odometry, conditions, confidence distributions, residuals, coordinates,
planner quantities or model results are exported. Path geometry exists only
in working memory and a temporary local SQLite spool, removed on normal
completion or handled failure; abrupt process termination may leave that
temporary private directory and is not a completed scientific output.

## Geometry and timestamp rules

`io.independent_outing_intake.iter_geometry_records` is a mechanical extraction
of the old conversion loop. The existing intake still collects its original
lists and retains its original complete-stream failure behavior. No v0.17
output, eligibility threshold, feature calculation or boundary rule changes.

For this new consumer, process selected messages in MCAP storage order to
avoid a cross-chunk log-time merge queue. Indices are internal per-topic
storage-order positions, not exported scientific IDs. Preserve every source
timestamp (including missing values) in compact Python streams, and preserve
complete path arrays losslessly on disk. Do not window, downsample, resample,
truncate or split/repack the original files. Pair only after successful
completion and count reconciliation of both streams.

Use the canonical `domain.pairing.mutual_nearest_timestamp_pairs` with its
unchanged unique-nearest, duplicate/tie, mutuality and missing-time semantics.
**The current canonical v0.17 intake passes no maximum-delta gate.** This
consumer does the same, explicitly reporting `pairing_maximum_delta_ns: null`.
Do not confuse that rule with the separate v0.18 sensor audit's 50 ms gate.
Numeric pairs alone establish neither close physical time nor common epoch;
no time shift, motion compensation or independent-reference claim is made.
The new count outputs are invariant to reordering the same per-topic records;
this does not establish ordering/sequence eligibility for a later intake.

Use the existing `_h100_geometry` exactly: project the estimate's ego-origin
footpoint onto the ordered RLMB path, check common station support at
`0, 5, ..., 100 m`, and forbid extrapolation. Do not assume native spline
station zero is the rear axle. Keep the existing projection ambiguity and
coverage tolerances. Check the existing finite anchor-distance limit of 1 m.

Report three nested counts:

1. `h100_pair_count`: paired reconstructed paths with complete projected H100
   coverage under the existing helper;
2. `anchored_h100_pair_count`: those pairs also satisfying the 1 m anchor; and
3. `sensor_anchored_h100_pair_count`: those also carrying an available/no-error
   EDP estimator state and the existing SENSOR_TOPOLOGY enum identity.

Also report all-estimate topology/descriptor counts, anchored-pair topology
counts, conversion/pair failure counts, stream message counts and the sizes
of all eight existing timestamp-audit fields. A conversion failure may appear
in both conversion and pair failure summaries; these are separate views and
must not be summed as disjoint exclusions. None of these is a v0.17 eligible
frame/outing count: causal-input availability, complete-outing all-SENSOR
conditions, source-time ordering, sequence-duration support and provenance
are not established by this workflow. No anchor distance or residual value
is included in the report. No outcome-driven threshold choice is allowed.

## Resource and completeness rules

Require a readable indexed summary, statistics and channel counts; no fallback
full-body scan when indexes are missing. Reject execution when any indexed
chunk advertises compressed-record or uncompressed size above 128 MiB, or
either selected topic advertises/produces more than 100,000 messages. Verify
decoded selected-topic totals against the summary before reporting counts.
These are execution limits, not geometry filters: do not skip oversized
chunks, analyze a prefix as the whole file, or label a limit as zero support.

Keep a 4 MiB SQLite page cache, no mmap, disk temporary storage and an 8 GiB
database page limit. Retained geometry is independent of recording length;
timestamp arrays/audits remain O(N+M) and are bounded by the message cap.
MCAP summaries, one decompressed chunk and one decoded/reconstructed record
still consume memory. Advertised chunk-size checks do not prove actual sizes
for a corrupt file, nor bound arbitrary decoder expansion. The binding Linux
CLI therefore enforces a 4 GiB process address-space allocation cap before
importing the workflow/decoder modules, preserves any stricter existing cap,
and restores the prior soft limit on return. The runbook sets numerical-library
thread counts to one to avoid unnecessary virtual-memory reservations. Require at
least 6 GiB freshly available RAM and 10 GiB free local scratch disk. These
operational choices are conservative pilot limits, not empirical whole-drive
memory measurements. Do not change swap/kernel settings or kill other users'
processes. Free your own unneeded applications before running.

The process limit may terminate a process without a report. An absent or
partial report is incomplete execution, never a negative result. A handled
resource/decode/disk failure returns an inconclusive per-file result with
`counts: null`; no positive or negative prefix counts are retained. Other
completed files remain visible, but the batch status is inconclusive if any
file is incomplete. Resolve a technical limit with a separately recorded
versioned retry; never automatically loosen a scientific gate.

## Artifact and review boundary

Create a fresh versioned output directory containing exactly
`recording_pair_feasibility.json`. Its schema is documented in
`docs/output_contracts.md`. Runtime source fingerprint and library versions
identify the actual executed code. Exit 0 means all four inspections completed
(even if all candidate counts are zero); exit 3 means at least one inspection
is inconclusive; exit 2 is a preflight/usage failure. No exit code grants a
cohort lock or authorizes residual extraction/model fitting.

Obtain focused independent review of this complete scope, the shared-loop
extraction, resource strategy, tests and command on the exact pushed branch.
`AGENTS.md` requires implementation GO before private geometry inspection;
the completed PR #21 review did not cover this new diagnostic. Only after GO
and normal Python 3.10/3.12 CI should the user perform the single batch02 run.
No additional session-history request is a prerequisite. Reconcile that
result before choosing subsequent schema, pairing, feature or sensor work.
