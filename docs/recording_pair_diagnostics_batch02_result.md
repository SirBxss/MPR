# Batch02 reference failures and pair timing: completed real diagnostic

Date: 2026-09-22. Contract:
`v0.19.1-batch02-reference-timing-2026-09-22-a1`.
This reconciles the returned report against the preserved pilot and reviewed
source. It is not a private-MCAP rerun or an independent review of the real
output. The implementation review preceded this result.

## Identity, review and execution

PR #22 is now merged at `dddbcc9ff27a63d7f613416186c9802e15256d90`,
tree `9a60f7623fa02e56f00827683dec4e78b4428e18`.
PR #23 is open, unmerged and mergeable at checked head
`83da0f16f47162979bb1dcf7c7bfea51386a5930`, tree
`d9f74f8a5692d14d158f5acf2b77d38783db9804`. This is the same source tree as
the delivered local author commit `8cdc2ce`; the different commit ID is expected
after applying a format patch. Git fetch and GitHub metadata agree.

Claude's supplied implementation/scope review returned **GO, zero blockers**.
GitHub Actions run `35712459648` passed on Python 3.10 and 3.12, including the
MCAP-extra installation, compilation and unit-test steps. The workflow installs
`.[mcap,test]`. No PR comments or additional review submissions were returned
by the GitHub timeline at this check. Job metadata was checked, not individual
test logs; local verification is recorded below.

| Artifact | SHA-256 |
|---|---|
| Returned result ZIP | `562fb8d780c72ebd7118d3b75e467ee70c35d01947fa5c60c40a465be934c57a` |
| `recording_pair_diagnostics.json` | `fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb` |
| Supplied implementation/scope review | `d4c48609292c32e9736ad25afb118917f17e96bdaeef62b4a3bf3c3d8de2e210` |
| Preserved feasibility report | `89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec` |
| Registration | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |
| Container context | `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad` |
| Runtime source | `2f09d5a192d23e28833df06a4d3920768384d186d3fba334765b5620eda5267b` |

The ZIP contains exactly the diagnostic JSON. All artifact hashes above were
recomputed from the available bytes; the runtime digest was recomputed over
the 176 package-relative Python sources and matches the reviewed tree.
All four path/size/raw-hash identities and **every original nested count** match
the preserved pilot, independently of the report's equality flags. Every file
and the batch are complete, with null execution failures and successful
reported raw-hash verification. The raw MCAP bytes are unavailable here, so
their hashes, decoded geometry and real resource use were not reproduced.

The report records Python 3.12.3, MCAP 1.4.0, mcap-protobuf-support 0.5.4,
protobuf 7.35.1 and numpy 2.5.1. Its flags still say no causal-input check,
residuals, roles or cohort lock. Independent-outing count is null and session
provenance remains unavailable. Do not request those unavailable facts again.

## Reconciled real observations

The complete original ladder is unchanged: 57,256 messages per topic,
55,077 numeric pairs, 7,775 H100 pairs, 7,743 also passing the 1 m anchor,
and 376 available/no-error SENSOR_TOPOLOGY EDP candidates. The remaining
7,367 anchored candidates have LANE_MAP topology.

| Recording | Anchored H100 pairs | SENSOR subset | Empty reference lane lists | Ego-drive-path selection failures | Maximum absolute delta across all numeric pairs |
|---|---:|---:|---:|---:|---:|
| 01 | 3,113 | 10 | 480 | 615 | 39.218540 ms |
| 02 | 703 | 0 | 107 | 108 | 31.364799 ms |
| 03 | 2,165 | 40 | 1,858 | 1,086 | 49.752942 ms |
| 04 | 1,762 | 326 | 27,124 | 128 | 51.354187 ms |
| Total | 7,743 | 376 | 29,569 | 1,937 | 51.354187 ms maximum |

Failure columns count all reference messages, including unmatched messages;
they are not additional mutually exclusive matched-pair outcomes.

**The generic reference error is resolved.** Every one of the 29,569 original
`map_RoadMessageError` conversions is now classified as
`road_fields:lane_segments_empty:none`. The current schema access returns an
empty lane-segment list; the converter rejects it before parsing coordinate
pools. No polyline/boundary coordinate failure is observed, and every reported
segment-failure dictionary is empty. The latter is conditional on conversion
reaching segment reconstruction, not proof that every skipped pool is valid.
There is no evidence for recovering these messages by relaxing vertex-pool
validation. Upstream reasons for the empty lists remain unknown: this report
cannot distinguish map coverage, configuration, production or export causes.

The other 1,937 rejected references have
`ordered_ego_path:map_ego_drive_path_not_unique:none`. This means no uniquely
usable drive-path ego geometry under the current rule; it does not distinguish
zero qualifying paths from multiple paths. No correction to that rule follows.

Every matched empty-reference failure occurs in the SENSOR_TOPOLOGY stratum.
For sensor estimates with an available estimator, 22,072 matched pairs have an
empty reference. This is the dominant observed support limitation. The full
first-outcome partition of the 31,311 sensor-stratum pairs is:

| First pair outcome | Count |
|---|---:|
| Empty reference (`map_RoadMessageError`) | 22,072 |
| Estimator unavailable | 5,395 |
| Estimate H100 coverage incomplete | 2,447 |
| Reference H100 coverage incomplete | 831 |
| Reference ego-drive-path selection failure | 189 |
| Anchor exceeds limit or is invalid | 1 |
| Anchored H100 ready | 376 |

These counts do not establish an upstream causal dependency or independence.

**All 7,743 anchored pairs, including all 376 sensor candidates, have exact
numeric source-time delta zero.** The sensor subset is empty in recording 02,
whose corresponding quantiles correctly remain null. There is no observed
numeric offset to correct in the retained candidates. The broad pair set's
51.354187 ms maximum does not describe a retained H100 candidate. No time shift
or new acceptance threshold is justified by these results.

Equal source timestamps do not prove equal physical measurement age, equal
frame semantics or independent information. The source epochs may have been
aligned upstream. The report contains no per-pair cross-tab proving that all
nonzero deltas coincide with empty references, even though their marginal
counts coincide per recording. Do not turn that equality into an event-level
claim or compute pooled percentiles from per-file percentiles.

## What is resolved and what remains

The previous opaque-error/timing blocker is resolved. No converter correction
or repeated generic timing audit is indicated. The remaining technical work is
to check prediction-time inputs and contiguous support, then materialize the
candidate vectors. The report contains counts, not residual values, features
or sequence lengths. Its 376 candidates remain an upper bound on retained
sensor-topology frames under the current rules.

The target remains `/adp/estimated_drive_paths` minus spatially aligned
`/adp/road_lane_map_based`, projected onto the reference left unit normal at
`0, 5, ..., 100 m`. These are pseudo-residuals, not errors against independent
ground truth. Preserve ego-footpoint projection, common longitudinal stations,
the 1 m anchor, no extrapolation and recording-local geometry. Source-time
equality does not justify replacing spatial alignment with index comparison.
The EDP topology enum is not direct LTSB geometry or proof of independence.
Direct LTSB remains on hold under the owner's chosen priority.

## Next implementation: one bounded exploratory extraction phase

Prepare a separate prospective contract and implementation from merged PR #23.
The concrete goal is to deliver the first residual/condition/sequence artifact,
not another generic reference/timing report. Its internal order should be:

1. Validate both immutable batch02 reports and their exact raw lineage; reuse
   the complete-stream pairing and disk/resource protections. Reproduce the
   376-candidate set before applying any additional readiness checks.
2. Check the existing six conditions on those candidates: speed, two EDP
   curvature summaries and three EDP confidence summaries. Preserve feature
   definitions and expose missing/non-finite inputs separately. Inspect actual
   odometry bracket and availability times: the existing speed helper
   interpolates poses at the estimate epoch and 50 ms earlier, which alone
   does not establish causal input availability. In particular, a future upper
   bracket must not silently count as a causal feature. Any necessary change
   to feature semantics needs an explicit reviewed decision, not an incidental
   rewrite or imputation. Do not change frozen historical artifacts.
3. Determine recording-local contiguous runs using the existing 200 ms maximum
   gap and eligibility/discontinuity rules. Report lengths, durations and
   usable adjacent transitions. Never bridge excluded frames or the four
   files, whose shared-session relationships are unproven.
4. After those checks, compute finite signed 21-station vectors for retained
   rows using the existing native projection/resampling arithmetic. Export
   physical-unit residuals, the six conditions, row/sequence provenance and
   explicit exclusions into a new versioned directory. Retain unavailable
   input/sequence evidence even if no complete training rows survive.

Combining these ordered stages in one separately reviewed implementation can
avoid repeated full-drive scans. This is a proposed next scope, **not an
implemented command or authorization from the completed diagnostic's GO**.
Define its artifact and failure contracts and verify synthetic alignment/sign,
causality, discontinuity, lineage and bounded-memory behavior before private
execution. No raw rescan is needed merely to close the current result.

The 7,367 LANE_MAP candidates remain accounted for but excluded from the
sensor-topology extraction. Admitting them to increase training volume would
change the scientific population and require a separate research decision.
Filtering mixed files cannot make their outings all-SENSOR under v0.17.

**When residuals and training become possible:** the proposed extraction is
the next phase intended to produce actual vectors; its retained count may be
below 376. Assess that artifact before any separately declared training run.
A small exploratory Gaussian baseline may be possible if feature completeness,
sample support and an explicit development-only evaluation design permit it.
Temporal AR/AIOHMM fitting additionally needs usable contiguous sequences;
376 scattered snapshots do not demonstrate that support. Do not promise
model training merely because an MCAP is large or a vector can be computed.

The frozen independent-outing protocol still has no successful lock: unknown
session provenance, mixed topology and fewer than 500 candidates in the entire
batch do not satisfy its per-outing all-SENSOR, 500-frame, 120-second conditions
or the seven-new-outing requirement. These are formal protocol gates, not a
universal numerical minimum for fitting any Gaussian. Unknown provenance need
not stop explicitly exploratory extraction, but technical recording splits
must not be presented as independent-journey validation. More suitable data
remain necessary for the intended final thesis comparison.

## Review follow-ups and closure

The five review items are nonblocking. O1 suggests future regression coverage
for the default lazy import graph; O2 concerns the legacy default mode's rare
broken-install output-directory path, not this completed diagnostic. O3 proposes
a defensive dictionary lookup where current guards agree; no observed defect
requires it, and silently swallowing a missing invariant is not adopted here.
O4 is harmless quantile-key ordering under the sorted JSON writer. O5 is
confirmed by exact count parity: estimator availability removes no already
anchored sensor candidate, while the stratified failure view explains attrition
earlier in the pipeline. No runtime patch or private rerun is needed for closure.

This documentation-only closure is based on the actual pushed PR #23 head.
Apply it to that existing branch, let CI pass at the updated head, then merge
the existing PR. No duplicate PR, external mutation or branch deletion was
performed here. The new extraction belongs in its own later implementation PR;
normal review and CI precede its private run.

Closure verification: compilation and `git diff --check` pass. With MCAP extras
installed, the full local suite ran 477 tests in 206.884 s: 475 passed and the
two expected opt-ins skipped (`MPR_WHEEL_PATH` and
`MPR_RUN_PRIVATE_ALIGNMENT_PARITY`). Both MCAP-gated tests ran. No source,
test, configuration or dependency file changed; the runtime digest is unchanged.
The report reconciliation separately checks full legacy-count equality,
identity hashes, outcome partitions, timing-set sizes/sign partitions, empty
quantiles and zero offsets for every anchored candidate.
