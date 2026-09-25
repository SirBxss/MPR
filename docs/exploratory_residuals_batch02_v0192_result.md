# Batch02 v0.19.2 exploratory residual result: reconciled

Date: 2026-09-25. Contract:
`v0.19.2-batch02-exploratory-residuals-2026-09-24-a1`.
This is an independent reconciliation of the supplied ZIP against the immutable
registration/context, v0.19.0 pilot, v0.19.1 diagnostic and reviewed source. It
is **not** an MCAP rescan, independent physical ground-truth validation, outing
admission or model experiment. Keep the three returned output files immutable;
do not repeat the completed private extraction.

## Implementation identity and review boundary

PR #24 is open and mergeable at pushed head
`42bedf6e70b3ce23937f3d1d55a85e7fd3456f46`, tree
`74ad92ca1866c091555060d241a86c55e05da013`, based on merged PR #23 at
`49ca0022104d96b0e4595dde0a48e69ca899406c`. The local author's commit
`8020275` has the exact same tree. Claude's supplied focused implementation and
scope review (SHA-256 `9038a47bfc0a8c947e837731452da5d7ea049a0fc408239a58dd0bbd93839941`)
records **GO, zero blockers** on that pushed head. Its reviewer could not
independently verify GitHub CI. We checked GitHub's run `36108508093` on that
head: **Python 3.10 and 3.12 succeeded**, each installing MCAP/test extras,
compiling and running 503 tests with two expected opt-in skips. GitHub shows no
PR discussion comments at this check. The review concerned implementation and
scope, not the later real output; the output reconciliation below is ours.

| Input/output | SHA-256 |
|---|---|
| Submitted result ZIP | `fd280febbc8691ff5a8aec699fd7eb3ea7ac866d17712d71c3117d7064c77aac` |
| `exploratory_residual_summary.json` | `64bee5e5970c173aebff3ac1ee265b4be171d81c1e8292a202b48a696319a678` |
| `candidate_audit.json` | `0ad7b085df8dfc8f2f8629b46fc3549013dd689c3d40791f8cc9bca0ddc35bd7` |
| `exploratory_residuals.npz` | `9f9abaa8a45bb75980ad200a1f1763277ffa2478d825a0f3709e4376be2b8a7a` |
| Preserved registration | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |
| Container context | `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad` |
| Preserved v0.19.0 pilot | `89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec` |
| Preserved v0.19.1 diagnostic | `fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb` |
| Runtime source digest | `96a0df813a1a815fdae963e68ceca1563dd1a89653201453164bf12962c82d6c` |

All hashes above were recomputed from the available bytes; the runtime digest
was recomputed from the local tree's Python source files. The ZIP has exactly
the three expected files and the summary's hashes equal the other two bytes.
The report says all four raw hashes were freshly verified on the execution
machine. **The raw MCAPs are unavailable here**, so we cannot independently
repeat that check, decode or assess source independence and physical frame/age
agreement. The report records Python 3.12.3, MCAP 1.4.0, numpy 2.5.1, protobuf
7.35.1 and mcap-protobuf-support 0.5.4 for the private run.

The registered paths, byte sizes and saved raw SHA-256 identities match across
registration, context and all three reports. Every complete recording's full
nested original count object matches the v0.19.0 and v0.19.1 reports, with both
reported parity flags true. Both old artifact bytes and lineage checks are
preserved. The prior diagnostic's detailed timing/failure observations are
unchanged by the output; the new run reports their successful comparison, not
those details in its JSON. Each of the four records has `status=complete`, null
failure, valid odometry schema and zero invalid/duplicate/conflicting odometry
messages. The four odometry counts are 32,724 / 5,396 / 32,116 / 103,282,
total **173,518**. The summary has no role, cohort lock, model or fitted
standardizer; independent-outing count remains null and physical input
availability unproven.

## Observed residual and condition populations

| Recording | SENSOR H100/anchor candidates | Finite 21-station residuals | Complete six-feature rows | Complete-feature sequences |
|---|---:|---:|---:|---:|
| 01 | 10 | 10 | 1 | 1 |
| 02 | 0 | 0 | 0 | 0 |
| 03 | 40 | 40 | 17 | 2 |
| 04 | 326 | 326 | 116 | 23 |
| Total | **376** | **376** | **134** | **26** |

All 376 geometric vectors are finite and have shape `(21,)`; there are **zero
residual-construction failures**. Exact sensor candidate totals match every
preserved count (10/0/40/326). All 376 estimate/reference source-time
*differences are numerically zero*. All projection anchor distances are finite
and <= 1 m (median 0.0551 m; maximum 0.8787 m). No LANE_MAP row was added.
These are EDP-minus-RLMB **pseudo-residuals**, not errors relative to independent
physical ground truth. Source-time equality does not establish equal physical
measurement age, coordinate-frame equivalence or estimator/reference
independence.

Exactly **242** candidates have geometric vectors but lack the complete six
conditions: **232** use an odometry state with source time after the estimate's
source epoch under the unchanged 50 ms speed interpolation; **10** fail its
50 ms interpolation-gap limit. The two failure categories are disjoint in this
output. The audit retains bracket evidence for all future-source cases, and
those brackets independently check as future relative to the estimate source
time. No late-log, missing confidence, invalid odometry, duplicate conflict or
reference-dependent feature failure is reported. Rejected rows are still in
the geometric archive; none is zero-filled as a condition row. Future-source
failure means the standard recorded bracket was not causal under this recorded
clock check. It does not prove that no differently defined causal speed could
exist. Do not alter the speed definition or shift the clocks to increase the
count without a separately reviewed methodological decision. For these 232 rows,
the future bracket leads the estimate source time by approximately **9.44 to
30.41 ms** (median 19.92 ms), while the *maximum* contributing odometry MCAP
log time equals the estimate's MCAP log time in every such row; the corresponding
maximum publish times also equal. These numeric fields are in the returned
audit, so no extra scan is needed to observe the discrepancy. Identical recorded
log/publish timestamps do **not** establish that a state whose own source epoch
is later was available at prediction time. They motivate a separately grounded
clock/producer-semantics question before considering any alternate speed
construction; they do not justify recategorizing the 232 rows today.

The archive has the exact 14 documented keys, the correct fixed feature/station
order, non-object dtypes and finite condition values. All 376 candidate indices,
recording IDs, pair/estimate/reference indices and exact uint64 decimal
source timestamps match the audit row by row. The 134 strictly increasing
`conditioned_profile_indices` point **only** to rows whose six conditions are
available; consumers must use this mapping to select matching target vectors.
The empirical selection is material: the median absolute residual at 100 m is
about 0.6805 m over all geometric rows and 0.6249 m over the conditioned
subset. These descriptive values do not establish a causal difference or a
performance result. Any later unconditional-versus-conditional comparison
must use a common declared sample set, preferably the 134 conditioned rows.

At station 0, the median absolute pseudo-residual is about **0.0551 m**. At
100 m, the median is about **0.6805 m**, 95th percentile about **1.9735 m**,
maximum **4.0811 m**. The maximum across any station/row is **4.2514 m**.
All these values are finite; the larger far-horizon disagreements call for
cautious interpretation as pseudo-reference divergence, not an unplanned
outlier threshold or evidence of physical lane-estimation error. This summary
cannot identify which raw geometry, map provenance or physical frame produced
a particular large value.

## Actual temporal support and next decision

The geometric vectors form **19** file-local sequences, **357** valid adjacent
transitions; two runs reach **113 frames / ~11.2 seconds**. The complete-feature
subset forms **26** file-local sequences and **108** adjacent transitions.
Its **longest runs are 10 frames / ~0.9 seconds**. Sequence offsets, every
reported start reason, frame count, transition count and duration were
independently recomputed from audit identities, original estimate/pair indices
and <=200 ms strictly positive source-time gaps, with file boundaries enforced.
No file is stitched to another. The 1 / 17 / 116 complete-feature rows across
recordings 01 / 03 / 04 are dominated by recording 04; recording 02 has none.

**Decision:** accept this as the first real finite residual/condition/sequence
artifact under the current EDP/RLMB pseudo-target. This phase is complete.
The conditional sequence support is short and uneven; an AR/AIOHMM comparison
on it would not provide a defensible new temporal-model conclusion. A tiny
exploratory Gaussian calculation may be technically possible, but no model,
standardizer, held-out fold, performance number or thesis claim is authorized
by this result. Before any baseline, separately predeclare its descriptive
purpose, exact common subset, minimum support, split limitations and validator;
then review it. A historical training CLI cannot consume this new NPZ.
The priority for a thesis comparison remains more *prospectively identified*
independent SENSOR-capable outings with sufficient reference/condition and
contiguous support. The owner cannot recover the batch02 session/acquisition/
export history; do not ask again or infer outings from the four files. All 376
candidates combined remain below the frozen 500-frame per-outing admission
condition, with unknown physical identities and mixed topology. The seven-new-
outing gate is also unmet. Direct LTSB remains on hold. No old model, planner,
reference converter or topology threshold needs a change on these findings.

## Review observations and handoff

Claude's six observations are nonblocking. O1 found alternate **labels** for
speed failures when both paths would reject speed; the availability and
numeric speeds agreed in its differential. Here 10 rows carry the
`odometry_interpolation_gap_exceeds_limit` code. No label correction or second
private run is warranted by this output. O2 asks that the reproducible 100-test
module selection be preserved in `docs/current_status.md`. O3 motivates the
common-subset comparison rule above. O4 clarifies that a future-source bracket
is not proof that all conceivable speed definitions fail, and that an odometry
decode interruption would be inconclusive rather than a geometry failure;
all four real streams completed. O5 suggests only small hardening with no
observed defect. O6 calls for an exact validator **before any new archive
consumer**; defer it to a separately scoped reviewed training/analysis phase.
No change to reviewed v0.19.2 source code, feature arithmetic, gates, tests or
old outputs is required to close this result.

Documentation-closure verification: `python -m compileall -q src tests`,
`git diff --check` and the full local suite pass with MCAP extras installed:
**503 run, 501 pass, two expected opt-in skips** (`MPR_WHEEL_PATH` and
`MPR_RUN_PRIVATE_ALIGNMENT_PARITY`). The result reconciliation additionally
checks prior report bytes, all four registered identities and old nested counts,
all archive hashes/keys/dtypes/identities/condition mappings, and both sequence
layouts independently. These checks consume returned artifacts, not raw MCAPs.
Only documentation is changed by this closure; the reviewed implementation's
runtime-source SHA-256 remains unchanged.

This documentation-only closure belongs in the **existing open PR #24**.
Apply it on the branch at reviewed `42bedf6`, let Python 3.10/3.12 CI pass
again at the new documentation head, then merge PR #24. Preserve the closed
v0.19.2 output. A later scoped implementation, if justified, gets a separate
branch/PR/review. No external push, PR update, merge or second private
execution was performed here. All numeric conclusions are limited to the
returned artifacts and separately reconciled lineage, not independent raw
recording replay.
