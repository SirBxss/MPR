# Batch02 registration reconciliation and pairing maintenance

Date: 2026-09-19. Status: summary registration, canonical timestamp-pairing
maintenance and epoch interpretation received focused `GO`, zero blockers.
No batch02 payload, geometry, eligibility, residual or model result is known.

## Accepted review and PR checkpoint

The user supplied `MPR_batch02_registration_pairing_review.md`, SHA-256
`6108be4a8ff4c8da9e82c221b409eac6f0f134b8e117878ccc745eb9dec9b03a`.
It reviews pushed head `ed981793fbcf458a032db4fc0bfb038c39f55585`, tree
`19d57ee15cbde04314341fc551303de8832e92bd`, against base
`1403927b8b0a0155cea19c6daba841160254c8c1`. These identities were independently
checked here by Git fetch. [PR #21](https://github.com/SirBxss/MPR/pull/21)
is open, unmerged and mergeable at this checkpoint.
[CI run 35467755430](https://github.com/SirBxss/MPR/actions/runs/35467755430)
completed successfully: Python 3.10 job `105963099376` and Python 3.12 job
`105963099475`, including MCAP extras, compilation and the tests. GitHub's
proposed/test merge SHA is not evidence that the user has merged the PR.

The reviewer independently reproduced 440 tests run (438 passes, two opt-in
skips) and reports approximately 47,800 differential pairing cases with no
differences. This review accepts the implementation and bounded interpretation,
not session independence, whole-drive memory safety, new payload execution,
sensor residual adoption or automatic merge. The PR is ready for the user's
merge; missing owner declarations are a later data-intake gate.

The formerly local `ddaceee60b2b9c4a63ed656a1d982ed858f3da9c` is now available
on the remote with the expected tree `1145540895cd910748036293cda4c3d77d4833a1`.
The original registration's claims of execution and a clean worktree remain
self-reported. No raw-file content hash has been independently checked here.

Both returned manifest files, including the `v002` filename, equal the draft
hash below. `docs/independent_outing_batch02_session_context.md` now gives the
focused provider questions and one summary-time/RAM collection command.
It replaces no prior result and does not repeat the full registration pass.

### Nonblocking review items and qualifications

- O1: the exact 58-test module command is given in Synthetic verification.
- O2: the historical common-ADP-clock statement is a producer-source premise,
  not recording-verified clock commensurability. The unchanged 50 ms numeric
  comparison establishes physical proximity only conditional on compatible
  clock scales/origins. This is now explicit in the epoch evidence and dated
  predeclaration addendum; no offsets are inferred or applied.
- O3: the existing manifest parser accepts any nonempty independence prose,
  including a placeholder. The new owner instructions explicitly require
  real evidence, not just parser acceptance. The frozen parser is unchanged;
  a lexical placeholder guard would not verify the truth of a declaration.
- O4: the separate v0.18 sensor matcher is still quadratic and batch01-pinned.
  A future whole-drive sensor audit requires its own scoped preparation.
- O5: 21 visible `Read` entries in the source transcript omit the path
  entirely; the epoch evidence now states this attribution limit directly.

Two review explanations must not be promoted into stronger project claims.
The optimized public matcher is also called by pairing, projection-alignment
and alignment workflows, not solely by v0.17 intake; the separate v0.18
matcher is unchanged. Also, MPR recomputing geometric span does not prove
that an unverified private producer defect could never affect any upstream
input. No such defect or causal explanation has been established here.

## Historical received evidence and verification limits

The user supplied `mpr_batch02_registration_review.zip` and explicitly reports
not opening a PR or doing further work beyond the supplied arrival procedure.
The ZIP contains exactly the private manifest and `batch02_registration.json`.
The registration names executed commit
`ddaceee60b2b9c4a63ed656a1d982ed858f3da9c` and reports an empty tracked-worktree
status. GitHub has no open PR and no pushed batch02 branch at this check;
the existing source-acquisition branch remains at `ca6b154`, main at
`1403927`. Thus the execution identity is reported by the file, not verified
against a remotely available commit/tree. The expected arrival-patch tree is
`1145540895cd910748036293cda4c3d77d4833a1`; reconcile it when the user pushes.

| Received artifact | SHA-256 of bytes independently hashed here |
|---|---|
| Registration ZIP | `5e6b4e284281f63b7dfe3daa27f76980f2eb5baebfcddd1488c7b8da27124783` |
| Private manifest | `c5f1f524864d28f9c88bd725f307eb3303a287823ee40f9cff23b4b5cdb711e1` |
| Registration JSON | `c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f` |

The manifest bytes exactly equal the delivered unfilled draft. File coverage
matches all four report basenames exactly, without duplicate basenames or
duplicate reported content hashes. All four summaries are reported readable;
the per-file byte sizes sum to 43,742,434,459 bytes. The raw files themselves
are unavailable here. Their reported SHA-256 values were checked for internal
consistency, not independently recomputed; transfer integrity, complete-body
readability and exact Protobuf descriptor compatibility are not established.
Private basenames, raw hashes and manifest contents remain outside Git.

## What the summaries advertise

Candidate numbers below are the arrival directory labels, not scientific
outing IDs or confirmed independent sessions.

| Candidate file | Bytes | Messages in each of the five path/marking topics | Odometry messages |
|---|---:|---:|---:|
| 01 | 8,381,930,717 | 10,798 | 32,724 |
| 02 | 1,409,205,136 | 1,780 | 5,396 |
| 03 | 8,036,964,995 | 10,597 | 32,116 |
| 04 | 25,914,333,611 | 34,081 | 103,282 |
| Total | 43,742,434,459 | 57,256 per topic | 173,518 |

The five equally counted topics in every file are:

- `/adp/estimated_drive_paths`: `Adp.Perception.EstimatedDrivePaths`;
- `/adp/road_lane_map_based`: `Adp.Perception.Road`;
- `/adp/lane_topology_sensor_based`: `Adp.Perception.Road`;
- `/adp/lane_topology_map_based`: `Adp.Perception.Road`; and
- `/adp/lane_markings_sensor_based`:
  `Adp.Perception.LaneMarkingsSensorBasedOutput`.

`/adp/odometry` advertises `Adp.OdometryState`. All six topics report Protobuf
schema/message encoding. `/em/road/ego_lane_path` is not advertised in any of
the four summaries. This does not block the canonical EDP/RLMB investigation:
EM fusion is not its reference. Equal topic counts do not establish paired
timestamps, geometry correspondence, common epoch or common physical frame.
Summary presence does not establish EDP topology source, sensor boundary
extent, H100 coverage, valid anchors, causal-input availability, duration or
independent estimation error. No count is an eligible-frame count. Even the
1,780-message file's duration cannot be inferred without an actual time range.

## Manifest and machine information still needed

The four-entry draft has null acquisition times, placeholder independence
descriptions and false attestations. The real parser rejects it at
`acquisition_batch_closed must be literally true`, as intended for a draft.
These unchanged placeholders are **not findings** that the user inspected
outcomes or that the files are from the same session. They simply do not yet
make the declarations required for an intake.

Preserve the supplied ZIP. Complete a new private manifest copy with real
timezone-aware acquisition starts and session evidence, grouping files by
actual physical session. Set attestations only when true; unknowns remain
explicit and block a formal cohort intake rather than being guessed.
Both prior-lock fields remain null because there is no successful lock.
The user must also provide `free -h` from the execution machine; no RAM report
was in this ZIP. Available session build/configuration/frame records are
useful, but a repeat of the broad BMW source inquiry is not required.

Four confirmed and technically eligible new outings would still fall below
the unchanged seven-outing lock threshold. Preserve outcome blindness and
do not assign development/final roles based on this registration.

## Evidence-supported executable change

At 34,081 valid timestamps on each side, the old v0.17-used matcher evaluates
`2 * 34,081 * 34,081 = 2,323,029,122` distances. That is arithmetic from the
algorithm and advertised counts, not an observed raw-data execution. It
justifies removing the all-pairs search before a whole-recording intake.

The maintenance change is confined to
`domain/pairing.py::_unique_nearest_positions`, used by the canonical public
`mutual_nearest_timestamp_pairs` function. It sorts target timestamps while
retaining original indices and multiplicity, then uses integer binary search
to inspect the immediate neighbors. Equal-distance ties and duplicate nearest
timestamps remain ambiguous. Both directional searches, mutuality, signed
delta, post-selection inclusive gate, unmatched/missing/ambiguity reporting
and output ordering are preserved. No geometry validity enters matching.
Time is O((N+M) log(N+M)) including sorting and result ordering; auxiliary
storage remains O(N+M). No float conversion or fixed-width timestamp cast is
introduced. Existing caller input conversion and gate validation are unchanged.

This is a computational correction, not a new scientific pairing rule.
Package/output versions, import-graph boundaries, schemas, thresholds, H100,
feature definitions and stored artifacts remain unchanged. The separate
batch01-pinned v0.18 sensor matcher is intentionally untouched; optimizing the
canonical intake does not generalize or reopen that closed audit.

The intake still retains complete per-file decoded EDP and reconstructed
estimate/reference geometry. This patch does not establish bounded memory
for a whole MCAP. Topic counts plus machine RAM inform the next assessment;
exact descriptor and geometry support require the later bounded, applicable
data-use step. Do not invoke the full intake from this result alone.

## Synthetic verification

Six new tests compare **all fields** of the public audit against an independent
exhaustive-distance oracle: 6,400 small stream/gate combinations, 300 seeded
unsorted cases, one-nanosecond distinctions at epochs beyond signed int64,
duplicate and equal-distance ambiguity, inclusive gate behavior and original
positions. A 34,081-message synthetic case checks complete pairing, and an
operation-count test rejects a return to Cartesian-product distance work
without relying on wall-clock thresholds. Existing intake and pairing tests
remain part of the regression check.

Local illustrative timings on Python 3.12.14 (one run each, synthetic integer
timestamps, reversed second stream for the before/after cases):

| Messages per stream | Previous matcher, seconds | Optimized matcher, seconds | Complete audit equality |
|---|---:|---:|---|
| 500 | 0.0534 | 0.00136 | exact |
| 2,000 | 0.8762 | 0.00564 | exact |
| 4,000 | 4.5258 | 0.01211 | exact |

A separate ordered 34,081-message synthetic pair matched all messages in
approximately 0.213 seconds. A separate `tracemalloc` run peaked at 20,589,272
bytes of traced allocation, with timestamp inputs already allocated. This is
neither total process RSS nor decoder/geometry memory, and timings are not a
CI acceptance threshold. The quadratic 34,081-message baseline was not run.

The focused pairing/intake suite has 58 passing tests, using exactly:

```bash
PYTHONPATH=src python -m unittest \
  tests.domain.test_timestamp_pairing_scalability \
  tests.domain.test_pairing_audit \
  tests.io.test_independent_outing_intake \
  tests.workflows.test_independent_outing_intake_cli
```

The complete suite
and compilation are recorded in `docs/current_status.md`. No real MCAP
diagnostic was rerun or new geometry output compared; the before/after
comparison above concerns synthetic pairing results only.

## Historical pre-review handoff and branch handling

Continue the user's local `docs/v0.19-batch02-arrival` branch. Apply the new
patch there, run the checks and push it. Open one PR to `main`; its ancestry
already includes the source-decision and pending epoch-correction commits.
Do not open a second PR from the older source-acquisition branch. Keep both
branches until the combined PR has review and CI acceptance and is merged.
Then remove only branches confirmed merged; never force-delete an unmerged
branch. No external push, PR, merge or deletion has been performed here.

The delivered review prompt covers the pending interpretation correction,
this registration reconciliation and the narrow matcher maintenance. A GO
does not attest session independence, approve a new sensor target, establish
whole-drive memory safety or authorize a batch01 rerun. After review and
truthful manifest/RAM evidence, select the smallest resource-safe next data
step under the existing outcome-blind gates.
