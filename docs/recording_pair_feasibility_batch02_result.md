# Batch02 recording-pair feasibility: completed real pilot

Date: 2026-09-21. Contract:
`v0.19.0-batch02-recording-pair-feasibility-2026-09-20-a1`.
This is reconciliation of the returned private report, not a raw-data rerun
or an independent review of the real output.

## Implementation identity and execution

PR #22 is open, unmerged and mergeable at checked head
`0661796eb1dcf3b8f68ab8eac1d5d7f621cbba17`, tree
`ba42ddd448cb61804b00b7eba48c0acd2c7d7138`, against main `7834def`.
Claude's supplied implementation/scope review returned **GO, zero blockers**;
its SHA-256 is
`d37fff4a2628066537f93317e8dde2639a5e0952907e70ad46cd033cb0880b85`.
GitHub Actions run `35578240792` passed Python 3.10 and 3.12; both jobs include
the package/MCAP-reader installation, compilation and full unit suite. The
workflow installs `.[mcap,test]`, covering the dependency concern in review O3.
No PR comment or additional review finding was returned by the GitHub timeline
at this check. The independent GO covers implementation and the one pilot;
it must not be described as an independent review of these new real counts.

The returned `recording_pair_feasibility.json` has SHA-256
`89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec`.
Its registration and context hashes match the frozen contract:

| Input | SHA-256 |
|---|---|
| Registration | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |
| Container context | `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad` |
| Runtime source | `f121352befc008965d2ee770b76b01be7101d5bba76000963185249bb951df0d` |

All four relative paths, sizes and recorded raw-file hashes also reconcile
against both supplied administrative artifacts, whose bytes were rehashed.
The runtime-source digest was independently recomputed from the reviewed tree
using the documented package-relative file map and matches exactly. Reported
versions are Python 3.12.3, MCAP 1.4.0, mcap-protobuf-support 0.5.4, protobuf
7.35.1 and numpy 2.5.1. All four recording inspections and the batch are
`complete`, with no per-file execution failure. The report records successful
raw-hash verification. Raw MCAPs are unavailable to this reconciliation, so
their byte hashes and geometry have not been independently recomputed here.

The owner's execution snapshot shows 14 GiB available RAM and 80 GiB free
disk. This satisfies the 6 GiB/10 GiB pilot guards; the earlier 2.3 GiB RAM
snapshot in review O1 is historical. Completion demonstrates that this run
finished under its configured limits, not measured peak RSS or general safety
for arbitrary full-drive MCAPs. No timing/RSS benchmark was returned.

## Reconciled counts

Numbers below identify recordings, not confirmed independent physical drives.

| Recording | Messages per topic | Numeric pairs | H100 coverage | H100 plus 1 m anchor | SENSOR_TOPOLOGY subset | LANE_MAP subset |
|---|---:|---:|---:|---:|---:|---:|
| 01 | 10,798 | 10,798 | 3,124 | 3,113 | 10 | 3,103 |
| 02 | 1,780 | 1,780 | 703 | 703 | 0 | 703 |
| 03 | 10,597 | 10,556 | 2,165 | 2,165 | 40 | 2,125 |
| 04 | 34,081 | 31,943 | 1,783 | 1,762 | 326 | 1,436 |
| Total | 57,256 | 55,077 | 7,775 | 7,743 | 376 | 7,367 |

The 376 candidates are **EDP** estimates whose topology enum is
`ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY`, with available/no-error estimator state.
They are not direct lane-topology-sensor-based paths. The estimate/reference
topics are `/adp/estimated_drive_paths` and `/adp/road_lane_map_based` (RLMB).
Neither EM fusion nor lane-topology-map geometry was substituted.

All 57,256 EDP records have the supported v2 descriptor fingerprint
`dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4`.
There are 2,179 unmatched records on each side (0, 0, 41, 2,138 by file),
and zero missing-time, ambiguous or gate-rejected positions. Zero gate
rejections is expected: `pairing_maximum_delta_ns` is null in every file.
This report gives neither individual time offsets nor their distribution;
it cannot establish close synchronization or equal physical measurement age.

Matched-pair failures reconcile exactly with the 7,743 anchored candidates:

| First reported pair failure | Count |
|---|---:|
| `map_RoadMessageError` | 22,072 |
| `h100_estimate_coverage_incomplete` | 12,599 |
| `estimate_not_attempted_estimator_unavailable` | 5,445 |
| `h100_reference_coverage_incomplete` | 5,261 |
| `map_map_ego_drive_path_not_unique` | 1,925 |
| `anchor_distance_exceeds_1m_or_invalid` | 32 |

The 47,334 failures plus 7,743 anchored candidates equal 55,077 numeric pairs.
These are first-failure categories, not independent causal attribution.
Conversion failures also cover unmatched records and can be hidden in the pair
view by an earlier estimate failure; the two views must never be added.
Unlike v0.17's all-estimate frame audit, this consumer records unmatched
estimates in timestamp counts only, not as `reference_pair_unavailable` pairs.
Per-file message, topology, descriptor, nested-count and failure partitions
were checked mechanically and all reconcile.

## What follows scientifically

This is positive geometric feasibility: the files are not a blanket H100
geometry failure. The existing projection checks the estimate's ego-origin
footpoint against RLMB, supports the 21 stations from 0 to 100 m without
extrapolation, and bounds the anchor distance. It does not equate native
spline station zero with the rear axle.

The 376 sensor-topology candidates are an upper bound on retained frames
under these converters and gates, before causal inputs, timing interpretation
and sequence checks. Residuals have not been computed. All 7,367 LANE_MAP
candidates must remain visible: filtering them away cannot turn these files
into an all-SENSOR outing under the frozen v0.17 gate. The 376 total is also
below even one outing's 500-frame minimum. It is not a statistical sample-size
justification for training an AR/HMM model; continuous eligible durations are
unknown. All four files contain non-sensor H100 candidates.

Session/acquisition/export provenance remains unavailable. No outing count,
role or cohort lock is assigned. Do not ask for the unavailable facts again.
Even a later defensible exploratory extraction would measure EDP-minus-RLMB
pseudo-residuals, not physical ground-truth error. This result establishes no
new independence or physical-frame/epoch guarantee for RLMB or sensor topology.

## Exact next implementation decision

First expose the specific reference-conversion failure reasons and the numeric
time-offset distribution, without changing acceptance rules. In recording 04,
27,124 of 34,081 RLMB messages fail with `map_RoadMessageError`; all files total
29,569 such conversion failures. The current iterator drops the reason because
`RoadMessageError` has no `.code`, retaining only its class name. This is an
observability limitation, not proof that the converter or the data is wrong.

The road converter can reject an empty lane list or invalid coordinates in a
whole vertex pool before selecting the ego path, among other reasons. A bad
unused pool entry is therefore a code-path hypothesis worth distinguishing
from missing ego geometry; the returned JSON does not establish either cause.
Do not skip invalid entries, relax validity/schema/coverage rules, shorten H100,
add extrapolation, shift timestamps or select a delta threshold to obtain samples.

A narrow versioned follow-up should preserve complete-stream pairing and all
old counts, add static reason/stage counts (no raw exception payload), and
report signed/absolute pair deltas separately for all pairs and the retained
sensor candidates. Account for topology in the failure summaries so map errors
are not automatically attributed to potentially useful sensor estimates.
Declare and test this extension before another private run, using the existing
disk/resource protections and immutable pilot report as lineage. This document
does not itself implement or execute that extension.

Once that result establishes what can be reconstructed and how it is paired,
assess causal feature availability and contiguous support before a separately
scoped exploratory residual extraction. A low count alone is not a reason to
replace the target with LTSB/LTM; that investigation retains its own unresolved
frame, epoch and correspondence requirements. No new model or planner run follows.

## Review follow-ups and delivery

O1's old RAM issue is resolved by the new snapshot and completed execution.
O3 is addressed by the checked CI dependency-install steps. O4 is clarified
above and in the output contract; O6 is clarified in the Linux command runbook.
O2 (a broken decoder install can leave an empty output directory) remains an
optional engineering follow-up; it did not occur in this complete result.
O5's fixed `raw_hashes_verified` field remains truthful through the existing
pre-report hash guard; changing its schema is unnecessary for this closure.

The result closure changes documentation only. PR #22's reviewed implementation
is merge-ready on the checked evidence. Apply this closure to the existing PR,
let CI pass on the new head, then the owner may merge it. Do not open a duplicate
PR or delete the branch before merging. No external push, merge, comment or
branch deletion was performed by this reconciliation.

Closure verification: compilation and `git diff --check` pass. With MCAP extras
installed locally, the full suite ran 455 tests in 62.559 s: 453 passed and the
two expected opt-ins skipped (`MPR_WHEEL_PATH`,
`MPR_RUN_PRIVATE_ALIGNMENT_PARITY`). The real indexed-MCAP reader test ran and
passed. No source/test file or runtime fingerprint changes in this closure.
