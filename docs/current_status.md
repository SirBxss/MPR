# Current project status

Last updated: 2026-09-22. This is the first file a new agent should read after
`AGENTS.md`. Update it whenever implementation, review, merge state, or the
critical path changes.

## Batch02 timing/reference result reconciled; prepare exploratory residual extraction

PR #22 is merged at `dddbcc9`, tree
`9a60f7623fa02e56f00827683dec4e78b4428e18`. PR #23 remains open and mergeable
at `83da0f16f47162979bb1dcf7c7bfea51386a5930`, tree
`d9f74f8a5692d14d158f5acf2b77d38783db9804`. Claude's implementation/scope
review returned **GO with zero blockers**. GitHub Actions run `35712459648`
passed Python 3.10/3.12, including the MCAP-reader installation and unit tests.
The authorized v0.19.1 private diagnostic is now complete; do not repeat it.

Read `docs/recording_pair_diagnostics_batch02_result.md` for exact artifact
hashes, arithmetic, review limitations and the next implementation scope.
The returned JSON SHA-256 is
`fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb`.
Its source fingerprint matches the reviewed code, all four files complete,
and every original nested count equals the preserved pilot. These checks were
recomputed from supplied artifacts; raw MCAP bytes are unavailable here.
The independent review covered implementation/scope, not the later real output.

All **29,569 generic reference-conversion failures are empty lane-segment
lists**, including 27,124 in recording 04. No coordinate-pool error is observed;
the empty-list check happens before coordinate validation. An additional 1,937
references fail unique ego-drive-path selection. No converter repair is
supported by this result; upstream reasons for empty geometry remain unknown.
All **7,743 anchored H100 pairs have exact source-time delta zero**, including
all **376 sensor-topology EDP candidates** (10/0/40/326 by recording).
The 7,367 LANE_MAP candidates remain excluded from the sensor population.
No time shift or new delta threshold is indicated. Equal source times establish
neither physical measurement age nor independent information.

The former error/timing blocker is resolved. Next prepare a bounded exploratory
EDP/RLMB extractor that first checks the six existing prediction-time features
and recording-local contiguous support, then exports finite 21-station
pseudo-residuals, conditions and sequence provenance for retained rows.
Reuse the disk-backed architecture, native projection, H100/no-extrapolation,
1 m anchor and existing sequence-gap rules. Inspect speed-input causality:
pose interpolation at the estimate epoch does not itself prove that its upper
bracket was available at prediction time. Preserve old feature semantics and
make any necessary new decision explicit before execution. Do not stitch the
four files, pool LANE_MAP frames or reopen LTSB simply to raise sample counts.

That next phase should produce the first actual residual vectors, subject to
readiness checks; **376 is an upper bound, not an exported training dataset**.
The current report has no residuals, features or sequence lengths. A later
exploratory baseline depends on retained support and a declared development
protocol; AR/AIOHMM also requires contiguous transitions. No automatic fit or
final validation follows. The frozen outing gates remain unmet, and the owner
cannot recover session/acquisition/export history. Do not request it again or
infer independent outings, training/final roles or an admission lock.

Compilation and whitespace checks pass; the full suite runs 477 tests, with
475 passing and two expected opt-in skips. Runtime/source/test files are unchanged.

This closure changes documentation only and belongs in existing PR #23.
Apply it, let CI pass at the updated head, then merge that PR. Prepare the
separate extraction contract/code from merged main; its focused review and CI
must precede its private run. There is no new extraction command yet and no
private rescan is needed now. Earlier review-before-diagnostic instructions
below are historical gates already completed, not requests to repeat them.

## Historical reference-failure/timing implementation preparation

The owner chose to prioritize EDP/RLMB and put direct LTSB investigation on hold.
This preserves the established path-residual target; it is not a claim that EDP
is independent ground truth or intrinsically superior. The completed pilot's
376 sensor-topology candidates remain the latest real geometric result.

The next step is implemented on `diagnostic/v0.19-reference-timing`, extending
the existing CLI with `--preserved-feasibility-report`. Read
`docs/recording_pair_diagnostics_predeclaration.md` (revision
`v0.19.1-batch02-reference-timing-2026-09-22-a1`) and the output contract.
It adds static reference-failure stages/reasons/causes, segment-rejection
counts, topology-stratified pair outcomes and signed/absolute source-time
offset summaries. The sign is reference minus estimate; exact integer
nearest-rank percentiles avoid float loss. No delta gate or time shift is added.

The exact preserved real pilot is required by SHA-256 before raw hashing or
payload inspection. Every original per-recording count must match it; drift
is inconclusive with null counts/diagnostics. The complete-stream matcher,
H100 projection, 1 m anchor, topology rules and resource limits are unchanged.
Without the new flag, the old output schema remains unchanged. The frozen
v0.17 import graph still passes. New-mode decoder imports are checked before
output creation, addressing the broken-install path noted in review O2.

Compilation passes; **477 tests run, 475 pass, two expected opt-ins skip**.
Twenty-two new tests bring the focused selection to 74 passing tests. Both
real-MCAP tests run with the optional dependencies installed. A separate
synthetic comparison against exact PR #22 head `0661796` preserves every
original count, all 24 record timestamps/failure states and path-array bytes.
The new details separate deliberately injected empty-road, polyline-pool,
boundary-pool and ego-path failures. This is synthetic evidence only.
Expected runtime-source SHA-256:
`2f09d5a192d23e28833df06a4d3920768384d186d3fba334765b5620eda5267b`.

GitHub still shows PR #22 open at `0661796` on this date; its previously
delivered result-closure patch has not been pushed. The new batch includes that
same documentation patch as 0001 for convenience; do not apply it twice.
Finish the closure and merge #22 after CI, then apply patch 0002 on a new
branch from that merged main. Open a separate implementation PR and obtain
focused Claude GO plus Python 3.10/3.12 CI before the one new private run.
This review-before-run boundary comes from AGENTS.md and the new declaration;
the old pilot's GO does not cover the extension. Implementation is complete
and reviewable; no external push/PR/merge or private execution was performed.

After GO, write only `recording_pair_diagnostics.json` into a fresh
`outputs/diagnostics/data/recording_pair_diagnostics_v0191_batch02` directory.
Reconcile failure causes, numeric deltas and original-count equality before
any converter correction, timing decision, feature/sequence audit or residual
extraction. No new real timing/failure breakdown is available here. Session
provenance stays unavailable; do not ask for it again or infer outing roles.

## Historical PR #22 pilot review and real-result reconciliation

PR #22 is open/unmerged and mergeable at `0661796`, tree
`ba42ddd448cb61804b00b7eba48c0acd2c7d7138`. Claude returned implementation/scope
**GO with zero blockers**; CI run `35578240792` passed Python 3.10/3.12 with
MCAP dependencies installed. The authorized one-run pilot is now complete.
The new host snapshot had 14 GiB available RAM and 80 GiB free disk, resolving
the earlier memory precondition. Do not repeat the completed pilot.

The returned report's source fingerprint matches the reviewed package exactly.
All four files completed: 57,256 messages per topic, 55,077 numeric pairs,
7,775 H100 pairs, 7,743 also passing the 1 m anchor. Of those, 7,367 are LANE_MAP
and 376 have an available/no-error EDP estimator with SENSOR_TOPOLOGY (10, 0,
40, 326 by recording). These are EDP/RLMB geometry candidates, not direct LTSB
pairs, eligible frames or computed residuals. Pairing remains ungated; no
numeric delta distribution or physical timing verification was produced.

Read `docs/recording_pair_feasibility_batch02_result.md` for exact identities,
arithmetic, failure counts and verification limits. The result has been
reconciled by the implementer; the supplied independent review concerned the
implementation/scope, not this real output. Raw MCAPs remain unavailable here.
Unknown session provenance remains unknown, with no role or outing admission.
Mixed topology and the 376-frame upper bound also prevent claiming the frozen
500-frame/all-SENSOR outing gates have passed. Do not request missing session
facts again or fit a model from these counts.

The next code task is a narrow diagnostic extension exposing static RLMB
conversion reasons/stages and pair time offsets while preserving the current
rules/counts. Recording 04 has 27,124 generic `map_RoadMessageError` conversions
out of 34,081 reference messages; that label cannot distinguish empty geometry
from a parser/pool problem. No cause or correction is yet proven. Assess causal
features and continuous support after that evidence, before exploratory residual
extraction. Do not change thresholds or adopt a different target to raise counts.

The reviewed implementation is ready for the owner's merge; this documentation
closure is intended for the existing PR #22, followed by normal CI at its new
head. No external mutation has been performed. Earlier preparation/run-request
instructions below are historical and do not authorize a repeated pilot.
Documentation-closure verification passes compilation and whitespace checks;
the full suite with MCAP extras runs 455 tests, 453 pass and the same two
opt-ins skip. Source/test files and the runtime fingerprint are unchanged.

## Historical PR #21 merge and recording-level pilot preparation

PR #21 is merged at `7834defaf3e3e10b3af908f2b869c96dfa8fae12`, tree
`537c5930034132967fe5c05d198ed63c71af778e`. GitHub and Git fetch agree, and
CI run `35503298582` passed Python 3.10/3.12 at the final PR head `d8f368c`.
The user returned `batch02_container_context.json`, SHA-256
`b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad`.
Its four identities, sizes, time differences and conditional UTC conversions
reconcile with the preserved registration. All summaries report statistics;
the intervals are approximately 18, 3, 18 and 57 minutes on disjoint numerical
log-time ranges. These are not verified acquisition dates, independent
sessions or eligible-sequence durations. Raw bytes remain unavailable here.

The owner says the requested session/acquisition/export history cannot be
obtained. **Stop asking for those facts or a completed batch02 v0.17 manifest.**
Keep the drafts and unknown provenance unchanged. The original independent-
outing lock remains blocked; do not infer either four independent outings or
one shared outing. No training/final role is assigned. Unknown identity does
not prevent a separately scoped technical recording diagnostic.

The host report had 2.3 GiB available of 31 GiB RAM and fully used 2 GiB swap.
The proposed `recording_pair_feasibility` CLI stores reconstructed geometry
temporarily on disk, keeps complete capped timestamp streams and reuses the
canonical EDP/RLMB converter and H100/anchor arithmetic. The shared conversion
loop is extracted without changing the old intake's list wrapper or gates.
The new output exposes counts/failure states only; no causal features,
residuals, model, sensor-target adoption, sequence stitching or cohort lock.
Resource/decode interruptions yield inconclusive results with null counts,
never a negative conclusion from a partial prefix. The canonical intake has
no timestamp-distance gate; this consumer preserves and labels that fact.
The separate v0.18 sensor matcher's 50 ms rule is not substituted.

Read `docs/independent_outing_batch02_context_result.md` and
`docs/recording_pair_feasibility_predeclaration.md` for identities, scope,
synthetic verification, memory limits and interpretation. The new code/scope
is prepared for focused independent review on a new branch from merged main.
After GO and Python 3.10/3.12 CI, free enough host memory, then run the one
fixed batch02 pilot under the documented process limit. No private geometry
run is yet authorized by its preparation, and no new outcome has been seen.
The old provider questions and fill-v003 instructions below are historical.

Compilation passes; 455 tests run, 453 pass and the same two opt-in tests
skip. Fifteen new tests exercise storage, completeness, pairing preservation,
lineage and resource boundaries. The 52 focused tests pass; their exact module
set and the synthetic memory comparison are in the context-result document.

## Historical PR #21 acceptance and session-context request

On 2026-09-19 the user supplied the focused Claude review
`MPR_batch02_registration_pairing_review.md`, SHA-256
`6108be4a8ff4c8da9e82c221b409eac6f0f134b8e117878ccc745eb9dec9b03a`:
**GO, zero blockers** for the epoch interpretation, administrative registration,
canonical pairing maintenance and handoff. GitHub PR #21 is open and unmerged
at the checked head `ed981793fbcf458a032db4fc0bfb038c39f55585`, tree
`19d57ee15cbde04314341fc551303de8832e92bd`, against main `1403927`.
CI run `35467755430` passed on both Python 3.10 and 3.12. This is merge-ready
code/documentation; missing session declarations do not block its merge.
No external push, merge or branch deletion has been performed here.

The earlier reported registration commit `ddaceee60b2b9c4a63ed656a1d982ed858f3da9c`
is now pushed and its tree matches `1145540895cd910748036293cda4c3d77d4833a1`.
This verifies the available source tree, not the file's self-reported execution
or the raw MCAP hashes. The independent reviewer reproduced 440 tests run,
438 passing and two expected skips. The five optional review items are
documented in `docs/independent_outing_batch02_registration_result.md`; no
further runtime correction or repeated review is needed for those items.

Both newly returned private manifests, including the `v002` copy, still have
the unfilled draft SHA-256 `c5f1f524864d28f9c88bd725f307eb3303a287823ee40f9cff23b4b5cdb711e1`.
No acquisition time, separate-session evidence or execution-machine RAM has
been supplied. These are missing facts, not negative scientific findings.
Follow `docs/independent_outing_batch02_session_context.md`: one additional
summary-only read collects raw container log-time ranges and machine RAM,
without rehashing all files, decoding payloads or editing the manifests.
MCAP timestamps have a user-defined epoch; any Unix-to-UTC display is only
conditional. Ask the provider for original session IDs, starts/timezones,
capture/export relationships and log-time clock convention. Preserve the
original registration and create a new manifest version when facts are known.

Next substantive implementation: assess per-file decoded/reconstructed
geometry memory in the canonical EDP/RLMB intake, then make only a necessary
semantics-preserving resource correction with synthetic checks. The optimized
canonical matcher does not make the separate quadratic, batch01-pinned v0.18
sensor audit ready for batch02. No batch02 payload, H100 eligibility, residual
or model result is known. Session declarations and resource assessment still
precede a formal intake; no seven-outing lock or LTSB target adoption follows
from this GO. Unknown old batch01 build metadata need not block new-session
administrative work. Keep the closed batch01 outputs unchanged.

## Historical registration reconciliation and maintenance preparation

The user returned `mpr_batch02_registration_review.zip`, SHA-256
`5e6b4e284281f63b7dfe3daa27f76980f2eb5baebfcddd1488c7b8da27124783`.
Its two files reconcile internally: four distinct reported raw hashes,
exact manifest/report basename coverage and 43,742,434,459 total bytes.
Each summary advertises EDP, RLMB, LTSB, map-based topology, LMSB and odometry.
The five path/marking topics each total 57,256 messages; odometry totals
173,518. EM ego-lane path is not advertised. These are summary counts,
not payload/geometry compatibility or H100 eligibility results. Raw hashes
were not independently recomputed here.

The private manifest exactly matches the unfilled draft: dates are null,
independence descriptions remain placeholders and attestations remain false.
Do not interpret these defaults as negative data findings or set them true
on the user's behalf. A formal intake needs truthful owner-completed session
declarations. The received ZIP contains no machine RAM or build/frame record.
The original ZIP/registration remain immutable; the user should complete a
new versioned private manifest copy and send `free -h`.

The registration reports commit
`ddaceee60b2b9c4a63ed656a1d982ed858f3da9c` and no tracked modifications.
GitHub still exposes only the source-acquisition branch at `ca6b154`, with
main at `1403927` and no open PR. The reported local execution commit/tree
cannot yet be verified remotely. The expected arrival tree is
`1145540895cd910748036293cda4c3d77d4833a1`.

The 34,081-message largest path stream justifies a narrowly scoped maintenance
change: `domain/pairing.py::_unique_nearest_positions` now uses sorted integer
timestamps and binary search instead of all-to-all distances. Original indices,
duplicate/tie ambiguity, both-direction mutuality, missing/unmatched states,
signed deltas, gate timing and output ordering are preserved. No scientific
threshold, schema, output or package version changes. The separate v0.18
sensor matcher and its closed-batch authorization remain untouched.

Compilation passes; the 58 focused tests pass; the full suite runs 440 tests,
438 pass and the same two opt-in tests skip. Six new tests establish complete
audit parity against an exhaustive oracle and guard against quadratic
distance work. A synthetic 34,081-message pair completes in approximately
0.213 seconds locally. This is not a whole-MCAP or geometry memory benchmark.
Exact evidence, timings, limits and handoff are in
`docs/independent_outing_batch02_registration_result.md`.

Next: apply the new patch on the user's existing local batch02 branch, push
and open one combined PR to main. Obtain focused review of the pending epoch
interpretation and this matcher maintenance, with normal CI. Keep the older
source branch until that PR is accepted and merged; no separate old-branch
PR is needed. No push/PR/merge/branch deletion has been performed here.
In parallel collect the missing manifest/RAM evidence. Whole-file geometry
retention still needs resource assessment before a full intake; this patch
alone is not permission for a private payload run. Do not rerun registration
or batch01, infer seven eligible outings from four files, or adopt a new
sensor residual target from topic names/counts.

## Historical four-file arrival preparation, 2026-09-19

The user reports four new drives, one large MCAP per drive. The screenshot
shows rounded sizes totaling approximately 43.7 GB, with a 25.9 GB largest
file. No raw bytes, topic counts, acquisition dates or physical-session
attestations for these files have been supplied here. They are four candidate
files, not yet four verified independent/eligible outings.

Git fetch on 2026-09-19 confirms the existing user branch
`docs/v0.19-source-acquisition-decision` at
`ca6b154320c7cff7e77adb42cf7c3586e6dc88eb`, tree
`927cd0e4ff5f76b9bde2104e205fe247f6127424`: the prior epoch correction is
already present despite the user's report that the last patch was not
applied. Do not deliver/apply that correction twice. `main` remains
`1403927`; no open PR was found. Focused interpretation review remains
pending; presence on the branch is not review acceptance.

Next: follow `docs/independent_outing_batch02_arrival.md`. Register the
original files under the dedicated `data/raw/new_independent_outings/batch02`
root, record truthful session provenance privately, and use the existing
summary-only topic reader plus streaming hashes. The accompanying private
draft does not pre-attest dates, independence or outcome blindness. Registration
can proceed with explicit provenance gaps; a valid intake manifest cannot.
No payload/geometry extraction or cohort assignment is part of this step.
The old batch's unavailable historical metadata does not block registration.

Source inspection identifies a concrete execution concern: the v0.17 intake
retains per-file decoded/reconstructed geometry and its mutual-nearest matcher
does O(N*M) timestamp work. The v0.18 matcher also does O(N*M) work. Counts
from the new summaries will inform the need for a narrow semantics-preserving
performance correction before full-drive execution. No memory/runtime failure
has been observed on these files. Do not split/repack them or reuse the
batch01-pinned v0.18 command. Old commands using the common parent root would
now include additional files and violate their exact-coverage requirement.

The unchanged final-cohort gate needs seven eligible new physical outings;
four alone cannot pass it. Keep the new candidates outcome-blind while
assessing technical availability. All batch01 negative results and pending
frame/epoch/correspondence questions remain visible. This handoff changes
priority and administrative instructions only; no runtime, tests, scientific
threshold, schema binding or model changes.

Handoff verification: compilation and all 434 tests completed (432 passes,
two expected opt-in skips) with MCAP extras installed. The documented command
also ran against four synthetic MCAPs with message/decoded-message iteration
disabled; known counts, missing statistics, missing summary, file hashes and
existing-output refusal behaved as documented. These are command checks,
not a benchmark or a real batch02 diagnostic. No new test cases were added
to the unchanged runtime suite.

## Historical source inquiry and epoch-correction preparation, 2026-09-18

The user pushed `docs/v0.19-source-acquisition-decision` at
`3f894efce9af19f781003b30ea742ad9c0bb6226`, tree
`9457ad603ffc898bdcb1c985e1b1cdc69ef5bbe5`; Git fetch confirms the delivered
tree. `main` remains the PR #20 merge `1403927`. No open PR was found at this
checkpoint, and the PR-event workflow query returns no run for the new branch
head. This is not a failed test: the configured workflow runs on PRs and
pushes to `main`. The unchanged executable baseline has 434 tests run,
432 passes and two opt-in skips.

Received `copilot_session_22.txt`, SHA-256
`f9f16bec168197ee489ced8f4f4d7f29e48f202834e5acbc9e21aed716f11565`.
Copilot reports BMW HEAD `465073bc593195eee0e4eada0a1389943e006a2b`, a clean
initial worktree and no link to the August 2025 recording build. The report
is preserved unchanged outside Git. The assessment and pending focused
interpretation review are in `docs/bmw_sensor_topology_epoch_evidence.md`.

The important correction is configuration-dependent upstream processing:
LMSB can track/propagate camera-derived geometry to an odometry timestamp;
pipethrough and timestamp-override behavior are separate possibilities.
Withdraw the unconditional camera-measurement-time interpretation. Retain
the 17,087 pairs only as numeric header-time proximity, with all audit
counts and preserved outputs unchanged. No new MPR decoder or arithmetic
defect is established. The code performs no 80 ms correction or inference
of the producer mode, and no such change is justified now.

The reported `max(61 m, speed * 2.5 s)` x-cutoff is a plausible mechanism,
not a batch01 diagnosis or a bound on accumulated sensor-chain length.
Checked-in parameters do not establish deployed values. Equal fractional
boundary stations can mismatch physical sections, but this is not proof of
observed statistical bias. Frame equivalence and error independence remain
unestablished. The new evidence note qualifies other source-report overreach
and the incomplete immutable-read evidence without demanding a repeat of
the entire source inquiry.

Next: apply/push the documentation correction to the same user branch,
open a focused PR and obtain review of the material epoch interpretation.
The supplied private review prompt names the exact expected tree. In
parallel, use the narrower recording/frame evidence request supplied outside
Git. Existing sidecars/build/configuration records and an applicable frame
specification are the required inputs; no new MCAP scan or payload run is
authorized. If historical provenance cannot be recovered, record unknown
and make any future pilot self-contained under its own prospective scope.
Do not block all future work indefinitely on finding batch01's build.

## Historical merge and source-inquiry preparation, 2026-09-17

On 2026-09-17 GitHub and a local fetch confirm PR #20 merged at
`1403927b8b0a0155cea19c6daba841160254c8c1`. Merged `main` and final branch
HEAD `5b2034e6d704c5d23410b46e9cfd6e095859f5e2` both have tree
`440f3bfc1a19fd9e74ef563c43c410da073cb7e3`, exactly the delivered closure.
Pre-merge [CI run 35222402624](https://github.com/SirBxss/MPR/actions/runs/35222402624)
passes Python 3.10 and 3.12, including MCAP-extra installation, compilation
and unit tests. A separate post-merge main-push run was not verified by the
available PR-event-filtered workflow query; the successful branch tree and
merged tree are identical. The implementation baseline remains 434 tests:
432 passes and two opt-in skips.

The user requested continuation. The next bounded action is documented in
`docs/sensor_topology_source_acquisition_decision.md`: a focused read-only
BMW producer/configuration inquiry into extent, frame/epoch/correspondence
and shared dependencies. A separate Copilot prompt is delivered outside Git.
No new BMW answer is available yet. The previous interface trace remains
sufficient for the completed v0.18 audit; these are the unresolved semantic
questions needed to choose future work, not a request to repeat that trace.

Working branch: `docs/v0.19-source-acquisition-decision`, based on merged
`main`. v0.19 is only a planning label; no version bump, new CLI, changed
horizon, target adoption, geometry diagnostic or private run is implemented
or authorized by this record. Preserve the closed batch. Return the source
report first, then choose and review the smallest supported implementation.
The missing BMW source/configuration evidence is the current blocker.

## Historical v0.18.1 real-output GO and accepted closed-batch negative

The user supplied the corrected batch01 audit and reported applying the
documentation-only review handoff. Artifact reconciliation passed against the
preserved v0.18.0 output, exact manifest and v0.17.1 intake. The reference
descriptor is now `structure_conformant`; 9,235 reference messages are
H100-ready and 17,087 source-time pairs pass the 50 ms gate. All sensor counts
and sensor failure-code sets are unchanged in every one of the 86 recordings:
16,737 ego candidates, 4,078 camera structures, 4,039 valid camera-only chains,
and zero chains reaching 100 m. Synchronized 100 m candidates remain zero.

The exact hashes, before/after comparison, failure counts, verification scope
and interpretation limits are in
`docs/sensor_topology_batch01_v0181_result.md`. Raw MCAP bytes were unavailable
here; recorded hashes and reports were reconciled, not raw geometry re-decoded.
No numeric span distribution or alternative horizon was inspected. The
corrective-review H1/H4 reconciliation checks pass.

Claude's `MPR_v0.18.1_batch01_real_output_review.md` returns **GO with zero
blockers** on pushed documentation HEAD
`77b1d8e34dca2e8a7e10d3457ce3b50ea7fd2e88`, tree
`7f535d84f7e76ce8eaf9de24a6a776f279d648b9`. The received review SHA-256 is
`1caa9e1c520a6ba836041f12d679027fdb13a0da4529b5ad60a9f466856d01f8`.
Git fetch and the GitHub API confirm that HEAD/tree, with PR #20 open and
unmerged and `main` at `b82908b`. Both documentation patches are therefore
visible remotely. This is the observed review checkpoint, not a claim that
later handoff commits are already pushed.

GitHub Actions run
[35215993924](https://github.com/SirBxss/MPR/actions/runs/35215993924)
passes both Python 3.10 and 3.12 jobs, including MCAP-extra installation,
compilation and unit tests. The `src/`, `tests/` and `pyproject.toml` objects
are identical to approved corrective implementation `bc50ee6`.

The closure clarifies optional O1--O4: distinguish the implementer's actual
manifest-byte hash from the reviewer's recorded-hash comparison; identify
reference failures as newly visible; explain root-relative private paths;
and supersede the old pending-review/unpushed status. H2 is now documented
as a dated retrospective account of existing numerical slack in the frozen
predeclaration, with units and exact comparisons. No rule changes.

The result document also qualifies three review statements: recording-level
marginal counts do not establish message-level joint eligibility; committed
tree identity does not prove the executed checkout; and the review's near-
boundary numerical example lies within the implementation's comparison
slack. These do not affect the accepted counts or verdict. Preserve the
received review and all prior artifacts unchanged outside Git.

At that checkpoint, the next action was the documentation closure and the
user's merge decision; both are now complete as recorded above. Contract,
implementation, corrective and real-output reviews are complete; no further review cycle or
private rerun is needed for this closure. No new PR is needed. The next
research step is a prospective acquisition/configuration or target decision
using producer evidence. The batch cannot justify selecting a shorter
horizon; residual construction also remains blocked by the unresolved frame
contract. Do not relax this batch's rules or start a new diagnostic/model run.

## Corrective implementation review and CI record

At the corrective-review checkpoint, the user had pushed the correction after
local tests passed. GitHub PR #20 then pointed to
`bc50ee656351beca14ab1f0ae57613fc3b86e81c`, tree
`3c78a31fbbce0161abd049abf7768289b90aa0d8`. Fetching that branch confirmed
both identities and that reviewed v0.18.0 commit `6a71782` is its ancestor.
PR #20 was open and unmerged; `main` was `b82908b`.

Claude's supplied `MPR_v0.18.1_reference_uint64_corrective_review.md` reviews
that exact HEAD/tree and returns **GO with zero blockers**. Preserve the
report outside Git; its SHA-256 is
`9b11742f9ff890a2cad3daef8cc20bf0714b2501c0ba432b7a2bec7653ac381c`.
The reviewer reproduced 30 focused tests and the 434-test full suite, with
432 passes and two opt-in skips, and mutation-tested both corrective changes.

GitHub Actions run
[35198056451](https://github.com/SirBxss/MPR/actions/runs/35198056451)
completed successfully for this pushed change. Both `unit-tests (3.10)` and
`unit-tests (3.12)` passed installation of the package and MCAP readers,
compilation, and unit tests. This resolves review item H3. This is CI evidence,
not a private-data execution.

That GO authorized one private v0.18.1 run against unchanged closed batch01
bytes, manifest and preserved v0.17.1 intake into a new directory. The user
has now supplied that run's output. Its reconciliation is recorded above;
the authorization is not permission for another run.

The required reconciliation checklist was:

- verify their own output hashes and identical manifest, raw-hash map and
  preserved-intake identity;
- require the sensor count ladder to remain `16737 / 4078 / 4039 / 0`, compare
  every corresponding per-recording sensor count, and require unchanged
  sensor-side failure-count entries (H1);
- expect the same reference descriptor to be `structure_conformant`, with
  the previous false decode-failure code absent; investigate any remaining
  descriptor/decode failure instead of interpreting it as missing geometry
  (H4);
- read the actual reference-ready and source-time-pair counts from the new
  output without predicting their values; and
- retain the expected zero synchronized count under unchanged sensor evidence
  and obtain focused real-output review before closing this phase or merging.

Three nonblocking review statements need precise qualification. The count
invariant is in `RecordingInspection.__post_init__`, not a
`FeasibilitySummary` class. The two skipped tests are opt-in wheel contents
and private historical alignment parity, not skips caused by missing MCAP
packages; the author's local environment also did not contain MCAP extras.
Finally, a zero count at 100 m does not establish that every chain was far
from the boundary: numeric spans were not exported. Preserve the report as
received rather than modifying it. H2 was optional at that checkpoint; the
closure above now records the existing floating-point slack in a dated
contract clarification, with no threshold or result change.

This GO authorizes no merge, new target, cross-topic alignment, residual,
model, planner run or figure. The user has reported applying the
documentation-only review record; it changes no executable code.

## Historical takeover verification, before the corrective push

The GitHub branch was fetched and PR #20 inspected. Remote `main` remains
`b82908bb4ed3770e338f8279dfc6dcdbb055b851`; the open PR remains at reviewed
v0.18.0 implementation `6a717827363529773a24f8fba2094cf5e75565b0`, tree
`530b73ff51243b8bfd27c3ffa47ef29e17649235`. No corrective review is recorded
there. The previous session had already completed the two local v0.18.1
correction commits, ending at `52a881a`, tree
`38ac50cf2720c925b1c9bee50617c3eccff804fb`. Applying those same patches to the
actual remote PR head reproduces that tree exactly. Do not reimplement the
correction or mistake merged `main` for the latest development state.

The takeover adds one synthetic regression: an 80 m strict camera chain and
an H100-ready `uint64` RLMB message at the same source time produce one time
pair but zero synchronized 100 m candidates. It changes no production code
or scientific threshold. The focused suite now has 30 tests; the full suite
ran 434 tests, with 432 passing and two expected opt-in skips,
under Python 3.12.14, NumPy 2.3.5, and Protobuf 6.33.6. Python 3.10 and the
complete MCAP dependency environment remain CI checks for the pushed tree.

The preserved v0.18.0 archive was reconciled read-only against its three file
hashes, all 86 recording rows, summary totals/failure counts, strict-time
flags, descriptor counts, exact manifest bytes, and preserved v0.17.1 lock and
raw-hash map. No raw MCAP bytes were available here; this is artifact
reconciliation, not raw re-decoding or a v0.18.1 private run. The ZIP hash
below corrects a transcription that omitted its final hexadecimal character;
no archive or output bytes were changed.

The source and saved artifacts are authoritative over the older conversation
description: the active reference is `/adp/road_lane_map_based`, not
`/em/road/ego_lane_path` or `/adp/lane_topology_map_based`. The retained sensor
counts mean 4,039 valid camera-only chains, **zero** reaching 100 m, not 4,039
H100 candidates. That is a result under the frozen reconstruction rules, not
proof that every possible use of the topic lacks geometry. The saved outputs
contain no numeric span distribution or raw geometry from which to infer a
different horizon or physical cause.

At that checkpoint, the next action was to apply the verified patch batch and push the existing
PR #20 branch, obtain focused corrective `GO` on its exact HEAD/tree, then
rerun once into a new v0.18.1 directory. No new PR is needed. Residual
construction remains blocked by the structural result and unresolved physical
frame contract; independent ground truth has not been established.

## Current checkpoint

- Merged repository version: v0.18.1 structural feasibility and accepted
  negative batch01 closure, through PR #20 at `1403927`. The current step is
  the source/acquisition evidence inquiry above. Earlier v0.17.1 EDP schema
  compatibility remains implemented,
  synthetically verified, independently approved, and exercised on the closed
  real batch01. Its v0.17.0 independent-outing intake base is independently
  approved and merged. Claude's earlier focused
  implementation review returned one `AMEND` concerning the legacy package
  initializer's transitive imports; the correction froze that graph and the
  focused re-review returned `GO`.
  A real v0.17.0 one-outing audit now exists, passed independent reconciliation,
  and assigned no role. No successful v0.17 cohort lock exists. The candidate
  descriptor is a newer BMW EDP generation that removed the legacy model-
  parameter Boolean. Complete privacy-safe evidence and a read-only BMW source
  trace support a narrow v0.17.1 amendment. Its first focused review returned
  `AMEND`; the corrected contract, implementation, and real amended audit then
  each received focused `GO`. The adapter restored H100 conversion, but the
  resulting candidate set is entirely LANE_MAP and contains zero eligible
  SENSOR_TOPOLOGY frames. No role was assigned and no successful cohort lock
  exists. v0.16.2 spatial-structure
  audit is complete, independently reproduced, approved, and merged. v0.16.1
  real A3 sampling and planner
  transfer are also complete, independently reproduced, approved, and merged.
  The corrected v0.16
  implementation and real planner run remain complete and approved. The first
  pre-fix v0.16 planner output remains rejected; its v0.15.4 residual samples
  were valid and were reused.
- Completed corrective phase: v0.18.1 standalone sensor-topology 100 m structural
  feasibility. Leon advised the data owner to prefer
  `/adp/lane_topology_sensor_based` over EDP for this study. The BMW source
  trace is now recorded and changed the original a0 proposal: LTSB publishes
  camera-derived boundaries rather than a centreline, its topology is
  map-influenced, and its physical frame origin is not established as equal to
  RLMB. The frozen a3 contract therefore permits only strict camera-chain span
  and source-time co-availability counts. Claude independently reviewed the
  exact pushed a3 tree and returned contract `GO`. Claude then reviewed exact
  v0.18.0 implementation HEAD `6a717827363529773a24f8fba2094cf5e75565b0`,
  tree `530b73ff51243b8bfd27c3ffa47ef29e17649235`, and returned implementation
  `GO`, authorizing one private run. That run reconciled the closed lineage and
  decoded both streams, but exposed one exact RLMB binding defect:
  `RoadLaneSegment.id_` is `uint64`, while the validator required `int64`.
  Independently, zero sensor chains reached 100 m. Preserve that v0.18.0 output
  unchanged. v0.18.1 corrects only the descriptor type and failure
  classification. The exact corrective HEAD and tree now have focused `GO`
  and passing Python 3.10/3.12 CI, as recorded above. The corrected real run is
  received, reconciled and accepted by focused real-output `GO` with zero
  blockers. This phase is closed negative for batch01; the documentation
  closure was applied and PR #20 is merged.
  No cross-topic projection, H100 residual-pair claim, threshold change or
  target adoption follows from the merge. Three private source traces now
  record the technical evidence and all 23 complete tracked paths; the third
  rechecked the claims against immutable `HEAD` blobs but did not capture the
  BMW commit SHA. That is retained as a source-trace reproducibility limit and
  does not require another BMW query. The candidate
  target is not adopted, and the historical EDP target/models remain
  unchanged.
- Merged branch and PR #20: `protocol/v0.18.0-sensor-topology-feasibility`.
  The exact pushed a3 contract-review identity is commit
  `75a1f9ff38885636dacafbd17144736420a7e17f`, tree
  `ad6d9a664ac7ec38cea4c06f2197d02ae4942f4c`. The local patch-source base
  `857ada05b968e9fd5ebda555118b3b75738d258b` has that same reviewed tree.
  The reviewed v0.18.0 implementation identity is commit
  `6a717827363529773a24f8fba2094cf5e75565b0`, tree
  `530b73ff51243b8bfd27c3ffa47ef29e17649235`. The accepted corrective HEAD is
  `bc50ee656351beca14ab1f0ae57613fc3b86e81c`, tree
  `3c78a31fbbce0161abd049abf7768289b90aa0d8`.
  The real-output review covers documentation HEAD
  `77b1d8e34dca2e8a7e10d3457ce3b50ea7fd2e88`, tree
  `7f535d84f7e76ce8eaf9de24a6a776f279d648b9`, with unchanged implementation.
- Claude's focused v0.18.0 contract review returned `GO`. The report SHA-256
  is `09b0351f448cd60025bd6e662bb5e7c392d38ab2af5332d3765f7b0a30b75c67`.
  Its optional hardening is reflected where applicable: the new 50 ms value is
  labelled prospectively fixed, source-time-pair counting is explicit, and
  implementation tests freeze lineage, descriptor generations, privacy, and
  the transitive import boundary.
- Claude's focused v0.18.0 implementation review returned `GO`; its report
  SHA-256 is
  `f530f7910f6090a845246ea6ac626d9ace92fc960688a3b8edeb139d66385088`.
  Its runtime-import hardening is included in v0.18.1. Reviewer prompts are
  external request artifacts and are not stored under `docs/`.
- The v0.15.4 development freeze was merged at commit `38ddac5` through PR #6,
  `MPR v0.15.4: freeze development residual model`.
- The post-merge hand-off was merged through PR #7 at commit `22a2334`.
- Python 3.10 compatibility was merged through PR #8 at commit `e833e5a`;
  Python 3.10 and 3.12 CI both pass.
- The complete v0.16 planner work was merged through PR #9 at commit
  `e6f6307`; its post-merge GitHub Actions run passes.
- The complete v0.16.1 Gaussian transfer was merged through PR #10 at commit
  `0f46758`; its post-merge Python 3.10 and 3.12 GitHub Actions jobs pass.
- The complete v0.16.2 spatial-structure audit was merged through PR #11 at
  commit `99feb14`; its post-merge Python 3.10 and 3.12 GitHub Actions jobs
  pass.
- The v0.16.2 final hand-off was merged through PR #12 at commit `1711b10`.
- The reviewed v0.17 protocol was merged through PR #13 at commit `4c700f9`.
- The independently approved v0.17.0 implementation was merged through PR #14
  at commit `6d3f34d`; the focused dependency-boundary correction is commit
  `2035f34` in that merge.
- The v0.17 data-arrival runbook and independent read-only initial-lock verifier
  were merged through PR #16 at commit `3765994`. They add no scientific
  analysis. No further scientific implementation is authorized before the
  real cohort lock.
- The raw-data chronology and first 86-file arrival checkpoint were merged
  through PR #17 at commit `fc46ce5`.
- The complete v0.17.1 EDP schema-compatibility implementation, tests, and
  accepted negative batch01 hand-off were merged through PR #18 at commit
  `00cfa1c`. Both Python 3.10 and 3.12 CI passed before merge. No successful
  independent-outing cohort lock was created.
- A reporting-only model-comparison view now reads the already accepted
  v0.15.3 macro and fold outputs directly and renders a four-metric meeting
  figure. It adds no model fit, current-data statistic, or selection decision.
- The reporting-only model comparison was merged through PR #19 at commit
  `b82908b`; merged `main` has tree `06530a7`. The documented baseline is 404
  passing tests with two expected skips.
- Claude's focused v0.17.1 contract re-review covered pushed commit `b51bee3`
  and exact tree `a846fe8`, returned `GO`, and authorized only the bounded
  compatibility implementation. Local patch-source commit `b51fb21` has the
  same reviewed tree. The report SHA-256 is
  `f35ca84085eef36590f5cc4af513a21c9e676be3c2273f853b3b1b1c72062ce1`.
- The bounded v0.17.1 implementation contains separate feature, test, and
  final hardening commits for the decoder, intake, additive failed-audit
  lineage, independent verifier, strict non-Boolean integer anchor handling,
  and synthetic contract coverage. Claude reviewed exact pushed commit
  `ad8f72e`, tree `1210048`, reproduced 402 tests with two expected skips, and
  returned implementation `GO`. The implementation-review report SHA-256 is
  `7cb78f59eb77eca0da85e81a9961096ccbd57adddd547f70404e13fa6a7928e7`.
  No patch-source SHA is treated as the review identity.
- The v0.17 prospective independent-outing intake and cohort-lock contract was
  drafted before new data were available. Claude reviewed pushed commit
  `189f948` and returned `AMEND`. The apparent review-SHA mismatch is resolved:
  local patch-source commit `77d33d6` and pushed `git am` commit `189f948` have
  the identical tree `86945df`. Claude's focused re-review of pushed commit
  `a41ec59` confirmed every original blocker and hardening point resolved and
  returned one new `AMEND`: four-file byte identity had incorrectly ignored
  the intentionally recorded relative-path column. The exact C1 correction is
  now applied, the binding lock hash is explicitly layout-independent, and the
  reviewer required no further wording review before implementation. The exact
  four-file workflow, CLI, schemas, and synthetic acceptance tests are now
  implemented. Claude then reviewed pushed implementation commit `31905c5`,
  returned one focused `AMEND` for the package-initializer dependency wording,
  and returned `GO` after the correction at `2035f34`. PR #14 is merged; the
  later real one-outing audit is recorded below.
- v0.17.0 implementation verification: 381 tests pass with two expected skips.
  The 42 new tests cover the strict manifest, exact recursive coverage,
  eligibility boundaries, content-only split, distinct ID/rank orders,
  deterministic/layout-independent artifacts, prior-lock supersession,
  embargoed-field absence, non-overwrite behavior, raw-inspector primitives,
  and CLI statuses 0/2/3.
- v0.17 data-arrival-readiness verification: 384 tests pass with two expected
  skips. The three added tests independently reconcile a complete synthetic
  first lock without writes, fail on manifest/raw/output drift, and freeze the
  runbook's initial-lock command, thresholds, outputs, and package-independence
  boundary.
- Historical v0.17.0 merged baseline verification: 384 tests pass with two
  expected skips.
- v0.17.1 implementation verification: 402 tests pass with two expected skips.
  The added tests cover exact message-owned descriptor identity, unrestricted
  structural legacy admission with explicit-true Boolean field 8, exact pinned
  flag-absent v2 admission, unsupported and drifted generation failure, all
  structural/index failures for both generations, equal downstream geometry
  and eligibility, exact additive JSON lineage, pre-write failed-audit
  reconciliation, deterministic output, and independent verifier coupling.
- v0.18.0 implementation verification: 432 tests run, 430 pass, and
  two expected optional-dependency tests skip. The 28 focused synthetic tests
  cover strict camera-boundary reconstruction, exact geometric boundaries,
  successor branches/cycles/limits, orientation-invariant span, message-owned
  descriptor identity, conformant generations, structural drift, fixed
  schema/encoding behavior, RLMB readiness, the 50 ms mutual-nearest rule,
  exact preserved-lineage validation, deterministic three-file output,
  non-overwrite, exit codes, and the transitive prohibited-import boundary.
  Compilation and `git diff --check` also passed before review. No private MCAP
  was read during implementation or review.
- v0.18.1 corrective verification, including the takeover regression: 434 tests
  run, 432 pass, and the same two expected opt-in checks skip (wheel contents
  and private historical alignment parity).
  All 30 focused tests pass, including
  acceptance of the observed singular `uint64` reference segment ID,
  fail-closed retention of an `int64` drifted descriptor, correct failure-code
  separation, preserved sensor-span rejection after successful reference/time
  pairing, and the runtime MCAP-decoder import graph. Compilation and
  `git diff --check` pass. The correction used only the privacy-safe three-file
  audit; no private MCAP or raw numeric payload was read.
- Real v0.18.0 batch01 structural audit: the unchanged manifest, 86 raw MCAPs,
  and preserved v0.17.1 intake reconciled. Both fixed topics had 17,163 decoded
  messages with valid strict source times. The sensor stream produced 16,737
  explicit-ego candidates, 4,078 camera-boundary structures, 4,039 valid
  camera-only chains, and zero chains reaching 100 m. Reference readiness was
  incorrectly zero because the reviewed validator required Protobuf `int64`
  for `RoadLaneSegment.id_`, while the retained message-owned descriptor shows
  singular `uint64`. The output therefore remains immutable defect evidence,
  not a complete two-sided feasibility result. v0.18.1 corrects only that exact
  binding and the misleading drift failure code. The sensor-side zero cannot
  be changed by this correction and must not trigger threshold tuning.
  The preserved v0.18.0 ZIP SHA-256 is
  `c7f9aad2a38b6b370e827ebd5ef5cf36b26aab54cfdd16179f02a7e570018b7a`;
  its recordings, schema-inventory, and summary file SHA-256 values are
  `b2b70f1e4222e9de2efd00ee49e71317aae2b486a3ae3af8d95ece63b5af0d06`,
  `cbe2ffb04dc5ad87fba472b194ab2a072f4eaa3fc2fd078fd60ed17929162793`,
  and `c59e27a4a77d21211fb77940c47c902d86ee868a75ab227271d39f0d47c183df`.
- First real v0.17.0 batch audit: all 86 MCAPs are raw-usable, summed usable
  duration is `1707.738856448 s`, the availability status is
  `insufficient_independent_outings`, no role is assigned, and the standalone
  verifier passes. The original output is immutable evidence, not a successful
  cohort lock.
- Real v0.17.1 amended batch01 audit: the same 86 raw files and manifest were
  reconciled to the preserved failed audit. The adapter decoded 17,163 estimate
  messages and produced 5,289 H100-ready candidates; all candidates are
  LANE_MAP, none is SENSOR_TOPOLOGY, and zero frames or sequences are eligible.
  The outing remains technically ineligible, contributes zero of seven
  required new outings, and has no role. The standard-library verifier passed
  over the real raw hashes with `files_written=0`; it independently verifies
  lineage/report reconciliation but does not re-decode technical counts.
  Claude's final real-output review returned `GO`. Exact hashes, failure counts,
  interpretation limits, and acquisition implications are in
  `docs/independent_outing_batch01_v0171_result.md`.
- v0.16.2 focused verification: 339 tests pass with two expected skips. The
  tests cover population arithmetic, exact output schemas, lineage tampering,
  extra inputs, nonzero padding, non-overwrite behavior, and CLI exit codes.
- Corrected v0.16 implementation verification: 324 tests pass with two
  expected skips. A non-constant-profile direct quadratic solve verifies the
  first curvature command and optimized horizon objective.
- v0.16.1 synthetic implementation verification: 329 tests pass with two
  expected skips. The complete synthetic v0.13.1 through v0.16.1 chain covers
  deterministic A3 sampling and transfer, exact standardizer mismatch, accepted
  v0.16 hash mismatch, and sampling-summary tamper failures.
- Real v0.16.1 verification: A3 sampling passed the independent pre-planner
  gate; Codex and Claude each re-executed all 1,920 A3 sequence runs and
  522,624 active planner frames. Both reproduced every primary interval and
  the predeclared `full support` decision. Claude returned final `GO` with one
  mandatory non-gating length-dependence reporting qualifier, now encoded in
  the summary contract and documentation.
- Real private freeze run: complete and independently approved.
- The residual-modeling programme is frozen for planner development. Do not
  reopen model-family, state-count, convergence, or AR-ceiling searches on the
  current corpus without new evidence.
- The first v0.16.2 review returned `AMEND`. The corrected contract received a
  focused independent `GO` before implementation. The implementation reproduces
  the reviewer's previously disclosed fixed statistics on the accepted
  artifacts. Claude's final review independently regenerated both ensembles,
  reconciled every output, and returned `GO`; the phase is accepted and closed.

## Raw-data chronology and 2026-09-07 intake checkpoint

The raw-data history has three distinct stages. Preserve this order and do not
retroactively replace a historical file count with a later one:

| Stage | MCAP files | Scientific unit and status |
|---|---:|---|
| Early fixed cohort | 10 | Historical corpus used by the early fixed-cohort workflows. Its ten-file documentation remains correct for those versions. |
| Accepted expanded legacy lineage | 67 | Later accepted legacy corpus. v0.17 treats its evidence as one legacy development outing, not 67 independent outings. |
| Newly arrived candidate set | 86 | One separately started, consecutively recorded physical outing. The first v0.17.0 technical audit is complete but failed closed before H100 eligibility because of an exact BMW EDP schema-generation mismatch. |

A fresh read-only reconciliation of the accepted expanded legacy root reported
exactly 67 accepted lineage entries and 67 files in the legacy directory. It
found no duplicate legacy basenames, no accepted file missing, no file outside
the accepted lineage, and zero accepted-file SHA-256 mismatches. The legacy
bytes and accepted lineage are therefore unchanged.

The recorded legacy reconciliation output is:

```text
accepted lineage count: 67
legacy directory count: 67
duplicate legacy basenames: []
accepted files missing: []
files outside accepted lineage: 0
first extra basenames: []
last extra basenames: []
accepted-file hash mismatches: 0
```

The separate candidate-root comparison reported 86 MCAPs, no duplicate
candidate basenames, no basename overlap with the 67-file legacy root, and zero
byte-identical overlap. The user confirmed that all 86 chunks belong to one
new physical drive that started separately from the legacy outing. Filename
wall-clock timestamps are CEST (UTC+02:00), corroborated by internal MCAP UTC
timestamps; the prospective manifest records the first internal time as
`2025-08-21T14:37:46+00:00`. No candidate residual, condition, model, planner,
or figure has been inspected.

The recorded legacy-versus-candidate comparison output is:

```text
legacy MCAP count: 67
candidate MCAP count: 86
duplicate candidate basenames: []
basename overlaps: []
byte-identical overlaps:
byte-identical overlap count: 0
```

The two roots contain 153 MCAP files in total, but 153 is not an inferential
sample size. Under the reviewed v0.17 contract, the accepted legacy evidence is
one development outing and the 86-file candidate can contribute at most one
new eligible outing after the technical gate. Even if it passes, at least six
additional eligible new physical outings are needed to reach the minimum of
seven. Keep the accepted legacy root in place and the new files under the
separate recursive `data/raw/new_independent_outings/` root, with one stable
subdirectory per physical outing. Later workflows must combine them through
their manifests, content hashes, and cohort lock, not by flattening raw files
into one directory.

## First real v0.17.0 audit and schema-v2 checkpoint

The exact private manifest was closed before outcome inspection and has
SHA-256:

```text
8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d
```

The v0.17.0 intake decoded 17,163 estimate and 17,163 map messages plus 52,012
odometry messages. All 86 recordings were raw-readable and raw-usable; their
usable intervals were monotonic and non-overlapping. The run wrote all four
required files, assigned no role, exposed no outcome value, and exited with the
expected insufficient-outings status. The standalone verifier passed at commit
`fc46ce533ba6555224d0264e91e7ef7483ace9dc`.

The immutable original output hashes are:

```text
independent_outing_recordings.csv
0f4d0f4e285c676abcadb00b94ee259384867a04330d93fbd6284f7d4d3dabb4

independent_outings.csv
51c8b42f6c7d31b7af1e8817cf295fee999c06897d5ea12ab3d368002cf41c9e

independent_outing_lock.json
9ee7565bd800c11773e17917838efdd5ddc3440c6803aa3a8a65631c8a778e60

independent_outing_intake_summary.json
81f9511575bae84036df98557fa8e63e19db2223e75b0c2cac3cc8d48b96fc0a
```

The initial run reported all 86 files as
`estimate_schema_bindings_incomplete`. A 200-message paired probe and complete
86-file privacy-safe audit isolated the cause: the candidate corpus has one
consistent serialized-descriptor fingerprint,
`dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4`,
which retains all used nested spline bindings but omits legacy Boolean field 8.
All 17,119 keep-lane/no-error paths in the complete audit pass the schema
probe's pre-conversion structural subset. That subset does not execute the
converter's mandatory `index_0` integer/range checks or H100 conversion, so it
must not be described as the complete converter gate. The candidate descriptor
does retain `index_0` as int64 field 7. The legacy descriptor reference is
`f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f`.

Copilot's read-only BMW source trace reports that the schema-v2 transition made
`model_parameters` required, removed the optional wrapper/validity binding and
Boolean field together with a major-version bump, but retained exact
`DrivePath.error == DRIVE_PATH_ERROR_NO_ERROR` as the semantic validity gate.
The trace and all evidence limitations are preserved in
`docs/bmw_edp_schema_evidence.md`.

The complete audit observed 16,376 LANE_MAP and 787 SENSOR_TOPOLOGY messages.
This does not change the predeclared all-SENSOR primary-cohort rule and is not
yet the exact post-H100 topology-candidate count. The schema adapter may restore
geometry conversion while the outing still correctly fails the topology gate.

`docs/independent_outing_schema_v2_amendment.md` defines a narrow v0.17.1
exact-generation adapter. Claude reviewed pushed commit `2d139251` (tree
`13aa4f35`) and returned `AMEND`: descriptor identity had to be separated from
the MCAP schema-record/caller audit hash, the additive output-lineage schema had
to be exact, and mandatory `index_0` validation had to be explicit. The amended
draft resolved those points, defines machine-checkable failed-audit lineage,
and records that batch01 must still exit 3 with no role assignment because it
declares only one outing. The first review report SHA-256 is
`fdbeff33bccda9f1eebb0e7fc62827af986448ff28d3fe5fd0e9a0c91b43ef20`.
Claude's focused re-review then returned `GO` on exact tree `a846fe8`. The
bounded implementation was applied at pushed commit `ad8f72e`, tree `1210048`.
Both CI jobs passed and Claude returned implementation `GO`. The real amended
run and standalone verification then completed under that exact code, and
Claude's final real-output review returned `GO`; its report SHA-256 is
`a33506179c1719207cb3b89b7744dc4ea1e82f07269941e9656874c93ce28c4e`.

The real result is an accepted negative technical audit. Of 17,163 decoded
estimate messages, 5,289 paths reached H100 geometry readiness. All 5,289
candidates are LANE_MAP; none is SENSOR_TOPOLOGY, so the frozen primary gate is
sufficient to force zero eligible frames. This does not prove topology was the
only obstacle: the outing's 787 SENSOR messages produced no H100-ready
candidate, and H100/map-pairing, coverage, anchor, and causal-input failures
must not be relaxed post hoc to recover them. The candidate set, not the whole
outing, is uniformly LANE_MAP. The exact audit record is
`docs/independent_outing_batch01_v0171_result.md`.

## Frozen development model

- Family: one-state conditional autoregressive Gaussian, with no latent-state
  switching or effective transition model.
- Configured AR ceiling: 0.99.
- Maximum fitted absolute AR coefficient: `0.9878812705276584`; the selected
  fit is interior and does not touch the 0.99 ceiling.
- Retained reporting reference: v0.15.1 at ceiling 0.98.
- Reference binding stations: `0, 5, 10, 15, 20, 25, 30 m`.
- Selected 0.99 binding stations: none.
- The 0.99, 0.995, and 0.999 all-clean fitted parameters are identical except
  for their configured ceiling.
- Selection basis: smallest tested nonbinding ceiling above the identical
  interior optimum. This is an engineering constraint release, not held-out
  performance selection.
- The strict v0.15.3 development gate remains failed.
- `final_model_selection_authorized=false`.
- `journey_level_generalization_estimated=false`.
- `planner_benefit_evaluated=false`.

Reviewed real-artifact hashes:

```text
development_residual_model.json
976259c05eb67e600b017a81bed77846a424b5687d51f4a04168431bfc7b6bd3

development_model_freeze_summary.json
7b00fda0e72c8ef8e94a07da755402407ea8d989f5c7dd3ee0837dfd85b8dba7
```

The freeze artifact records a 32-file v0.15.3 audit hash map, including
`ar_boundary_fold_comparison.csv`. Per-fold evidence remains in that immutable
v0.15.3 source artifact and does not need to be duplicated into the freeze.

## What is scientifically supported

- Autoregression captures the observed lag-one structure on the current
  within-outing corpus.
- The tested latent two-state switch does not earn its complexity over K=1.
- The convergence audit does not change that conclusion.
- The 0.98 AR cap binds near-field stations; releasing it produces an interior
  optimum, while marginal/calibration limitations remain.
- No completed model supports a claim of independent-journey generalization or
  planner-level benefit.
- For the fixed v0.16 reference planner and current within-outing cohort,
  temporal ordering changes planner behavior even when each sequence/draw
  retains exactly the same multiset of H100 residual profiles. This is a
  sensitivity result, not planner benefit or a production-planner result.
- For the same planner and cohort, the v0.14 unconditional Gaussian is much
  rougher than the frozen AR and has lower deviation under the predeclared
  equal-sequence macro. The deviation half is length-dependent and must never
  be reported without the exact cohort qualifier recorded below.
- RLMB remains a pseudo-reference with the documented source and timing
  limitations.

## Implemented v0.15.4 interfaces

Freeze command:

```bash
python -m lane_residuals.cli.development_model_freeze \
  "outputs/models/one_state_ar_boundary_v0153" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --output-directory "outputs/models/development_residual_model_v0154"
```

Planner-facing sampler:

```bash
python -m lane_residuals.cli.development_residual_sampling \
  "outputs/models/development_residual_model_v0154/development_residual_model.json" \
  "outputs/planner/planner_condition_sequences.npz" \
  --sample-count 128 \
  --seed 20260826 \
  --output-directory "outputs/planner/residual_samples_v0154"
```

The sampler input NPZ contains exactly `conditions [B,T,6]` in physical units,
integer `lengths [B]`, unique nonempty `sequence_ids [B]`, and the exact
`feature_names [6]`. It exports signed physical residuals
`residual_samples_m [S,B,T,21]` with zero padding. It does not modify geometry
or execute a planner.

## Completed v0.16 planner sensitivity

The primary experiment uses an MPR-owned deterministic reference planner, not
BMW planner integration. This keeps the result reproducible and isolates
temporal ordering from unavailable production configuration. BMW integration
remains an optional later transfer-validation step and must still use exact,
Copilot-confirmed symbols.

Existing accepted artifacts are sufficient for the primary experiment:

- `alignment_station_comparison.csv` provides aligned RLMB pseudo-reference
  coordinates on H100 through `aligned_reference_x_m` and
  `aligned_reference_y_m`;
- the v0.13.1 sequence archive provides exact recording, pair, message,
  timestamp, condition, and sequence identity;
- v0.15.4 provides free-running signed residual draws on the same H100 grid.

The contract and its dated amendment record are in
`docs/reference_planner_predeclaration.md`. The earlier snapshot-only plan was
rejected because it cannot identify temporal-order effects. The implementation
propagates a linearized lateral/heading error state around recorded motion; it
does not stitch ego-relative paths globally.

The executed arms are A0 zero, A1 within-sequence time-shuffled frozen AR, and
A2 frozen AR. A2 minus A1 is primary. The corrected run uses 128 paired draws,
15 eligible sequences, 4,083 active frames, residual seed `20260826`, and
shuffle seed `20260827`. One clean singleton was excluded before sampling and
recorded without inspecting residual values or planner outcomes.

Primary A2-minus-A1 results are macro means over the 15 sequences. The quoted
interval is the predeclared 2.5/97.5 percentile spread across paired Monte
Carlo draws, not a confidence interval for the dataset or mean:

| Metric | Mean difference | Paired-draw interval | Verdict |
|---|---:|---:|---|
| integrated absolute lateral error | +0.176956 m s | [0.122456, 0.235142] | effect |
| maximum absolute lateral error | +0.012402 m | [0.006209, 0.017037] | effect |
| constraint-violation fraction | -0.093137 | [-0.131466, -0.058316] | effect |
| fraction beyond 0.3 m | +0.000198 | [0.000000, 0.002551] | indeterminate; descriptive |
| final absolute lateral error | +0.004085 m | [-0.023638, 0.029294] | indeterminate |

The effect is a trade, not a benefit claim. Relative to A1, A2 has 13.4%
greater integrated absolute lateral error and 8.5% greater maximum absolute
lateral error, while producing fewer fixed-envelope violations. Post-hoc
descriptive summaries from the retained frame metrics make the mechanism more
legible: macro p95 absolute curvature rate is `0.9330` for A1 versus `0.2096`
for A2, macro p95 absolute lateral jerk is `409.60` versus `76.01 m/s^3`, and
macro mean absolute lateral error is `0.06440` versus `0.06996 m`. These
descriptive quantities were not predeclared decision gates.

The violation envelopes are not enforced constraints or safety limits. A0 has
zero planner correction and zero lateral error, yet its equal-sequence macro
violation fraction is `0.259355`. On a pooled-frame basis, nominal-path lateral
acceleration trips at `0.061964`, nominal-path jerk trips at `0.403380`, and
any envelope trips at `0.409013`. This is an exogenous recorded-reference and
envelope-calibration floor, not planner behavior. A1's extreme derivative
values are likewise a statistical-null/protocol artifact of shuffling the
reference every source frame without an actuator or enforced rate limit;
absolute comfort or safety interpretations are invalid.

Reviewed corrected-artifact lineage:

```text
reference_planner_scenarios.npz
615f6c7d5ef6b6b9c0770c65b58bb23c573a838579aa4fdf3f25c141a15c0591

sampled_residual_sequences.npz
5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa

reference_planner_frame_metrics.npz
9d2b6a724a648839756597d40497cf6a2fc9b55a4422230fcddb317fe26a2a9f

reference_planner_sequence_metrics.csv
3f9ea8db4e4e2817c450dd82ebe8a52042a12e6aa76fbb0d4b7b31da4d96a1df

reference_planner_sensitivity_summary.json
38a04f655f9c9f6ec0e89d817534e8e289e0571787c229fa630d37406bcc8154
```

Codex inspected the uploaded raw NPZ and CSV, recomputed the summary exactly,
and reproduced selected A1/A2 trajectories bit for bit from the corrected code.
Claude independently regenerated the pipeline under Python 3.11.15 and NumPy
2.4.4. Its sample NPZ was not byte-identical (`c8f3e648...` rather than
`5f54e56f...`), so the two runs are not interchangeable lineage artifacts and
the exact byte-level cause remains unisolated. The shuffle count, A0 macro
result, and all primary contrasts nevertheless agree at the precision reported
in the final review. This is numerical reproduction across environments, not
byte identity; the hashes above remain the authoritative accepted lineage.

## Completed v0.16.1 Gaussian planner transfer

v0.16.1 is a separately labelled A3 extension, not an amendment to the
completed v0.16 result. It uses the immutable v0.14 unconditional-Gaussian
all-clean descriptive fit, runs only A3 through the accepted planner, and
compares it with immutable accepted A1/A2 metrics. A3 changes marginal
distribution, cross-station covariance, and temporal structure, so only the
v0.16 A2-minus-A1 comparison supports a causal temporal-order interpretation.

The real run uses 128 independent A3 draws, 15 sequences, 4,083 active frames,
Gaussian seed `20260828`, bootstrap seed `20260829`, and 20,000 independent
two-sample bootstrap replicates. The three sequences shorter than 20 frames are
excluded only from the primary p95 macros. All four intervals lie strictly in
their predeclared directions:

| Metric | A2 | A3 | A3 minus A2 | Independent-draw interval | k/N |
|---|---:|---:|---:|---:|---:|
| p95 absolute curvature rate | 0.168162 | 1.938071 | +1.769909 | [1.760356, 1.779786] | 12/12 |
| p95 absolute lateral jerk | 68.9550 | 791.1659 | +722.2110 | [719.136, 725.308] | 12/12 |
| mean absolute lateral error | 0.0699641 m | 0.0586593 m | -0.0113049 m | [-0.0128263, -0.0097855] | 10/15 |
| integrated absolute lateral error | 1.496831 m s | 1.418571 m s | -0.078260 m s | [-0.103351, -0.053499] | 10/15 |

The predeclared rule therefore returns smoothness pass, deviation pass, and
`overall_decision = full support`. This decision is retained exactly; the
post-result cohort diagnostic is not promoted into a new gate.

The deviation half is length-dependent. Mean absolute error is 16.2% lower
under the equal-sequence macro and 5.4% lower in the pooled-frame summary, but
both deviation metrics reverse on the same 5 of 15 sequences. Those sequences
contain 2,365 of 4,083 active frames (57.9%) and rank 1st, 2nd, 6th, 7th, and
8th by active-frame length. Thus all five are among the eight longest, both
longest sequences reverse, and every sequence with at most 174 frames agrees.
The final-review draft said "five of the six longest"; an exact rank audit
corrected that wording to the ranks above. Smoothness agrees in the
hypothesised direction on all 12 eligible sequences and every reported
aggregation.

The result may be stated only as a planner-observable model trade for this
fixed reference planner and one outing. It does not establish that A3-minus-A2
is caused only by temporal structure, that either model is generally better,
planner benefit, comfort, safety, BMW behavior, production readiness, physical
ground truth, final model selection, or generalization. The intervals quantify
Monte Carlo draw uncertainty with the cohort fixed, not dataset, journey, or
model-fitting uncertainty.

Reviewed real-artifact lineage:

```text
unconditional_gaussian_residual_samples.npz
458a255f76334b281889df48bf8f549bd7b1f2fd124579b958b41d5353a8c81f

unconditional_gaussian_residual_samples_summary.json
8b17a16be7d6f76b5a3d69f3b03f82e28f8105a4a60f4fe9df6aac60e806f0f2

gaussian_transfer_frame_metrics.npz
270480551b7fc0cb8c097fee6ff875b3e847f958e9928e5b053a78795671fe2f

gaussian_transfer_sequence_metrics.csv
1f10578ced9d05bab8472cecc0e6c346f2907b9c368a7da572ff23a723bcc1bf

gaussian_planner_transfer_summary.json (with mandatory qualifier)
2dcda2dc24da9148a64ab742a815592e874e07e8f7fb007822d2f85f04cec2fa
```

Codex reproduced the delivered frame archive bit for bit. Claude regenerated
the A3 and accepted A2 ensembles independently, re-executed the planner, and
matched all decisions to machine precision. Generated samples and planner
outputs remain outside Git. BMW transfer validation remains optional and
separate. The final untouched-drive phase is still blocked by the absence of
independent outings; v0.16.1 does not satisfy that data gate.

The seed-repetition suggestion remains deferred. Repeated sampling seeds would
quantify Monte Carlo sensitivity; they would not create independent-drive or
dataset uncertainty.

## Completed v0.16.2 spatial-structure audit

The completed bounded phase is a read-only descriptive audit of contemporaneous
cross-station covariance and correlation in the accepted A2 and A3 residual
ensembles. It addresses the specific open interpretation issue from the final
v0.16.1 review: the A3 deviation result is length-dependent, while A3 differs
from A2 in both station-wise scale and cross-station coherence.

The audit consumes only the complete immutable A2 and A3 sample directories.
It does not refit or resample a model, execute the planner, change the accepted
v0.16/v0.16.1 decisions, or create an A4 arm. Pooled-frame and equal-sequence
summaries are both mandatory. No interval, hypothesis test, or pass/fail gate
is permitted because the result is post-hoc and generated-ensemble descriptive
evidence.

The exact approved contract is in
`docs/spatial_structure_audit_predeclaration.md`. The first Claude review found
useful interpretation risks but proposed a scalar effective-sample-size formula
that is not valid for the audit's covariance/correlation estimands and described
the sequence-wise difference as more uniform than the exact accepted artifacts
support. The amended contract instead records unequal temporal dependence
without inventing an effective sample size, treats reset/length effects as
confounded rather than irrelevant, limits `k/15` to direction consistency,
closes the statistic list, and strengthens the causal wording.

Claude computed the complete fixed statistic list on independently regenerated
ensembles during that review. This must remain disclosed: the later accepted-
artifact run is a lineage-controlled reproducibility execution, not a first
look. The focused re-review returned `GO`, and both optional wording suggestions
were adopted. The workflow implementation reproduces the disclosed pooled
off-diagonal correlations (`0.3830158618` A2 and `0.5335912782` A3), adjacent
correlations (`0.7030729727` and `0.9689050398`), 182/210 positive pair
differences, and positive off-diagonal/adjacent differences in all 15 sequences.
Claude's final read-only review regenerated A2 and A3 independently, reproduced
all 42,378 matrix values within a maximum absolute difference of `1.55e-15`,
reconciled every CSV and hash, confirmed 339 passing tests with two skips, and
returned `GO`. The result and implementation were merged through PR #11.

Accepted v0.16.2 artifact hashes:

```text
spatial_structure_matrices.npz
cf4eac162018dd65be26b89b472dbc6fe65aab3aacedd46c22b82583d4ab951f

spatial_structure_by_station_pair.csv
773573ba00c18648259f7e055afde40d8c0e72a574b4298821ed75ad5524527f

spatial_structure_by_separation.csv
38fb5c157ca9b8424a64e7eeee4bc31d482ec12e5e0f5b916c9e27ca29433ca3

spatial_structure_by_sequence.csv
2f4e40ffd5e5ec70ddf262269315a278f0cb1a19ab4f87b0ea90255bc8cee842

spatial_structure_audit_summary.json
e11b9a90bba4aba2af07eacb2ca1bae50231e1c0b5fa90509edca7742531479e
```

For the thesis write-up, the 90, 95, and 100 m separation rows contain only
three, two, and one station pairs, so their near-zero tail signs are not a
structural finding. The A2 adjacent correlation also differs more between
pooled and equal-sequence weighting (`0.7031` versus `0.7203`) than the
off-diagonal statistic does; this is consistent with the predeclared
finite-horizon mixture and is why both weightings must remain visible. The
adjacent A2/A3 contrast is the clearest single summary, but it must be reported
beside the separation profile.

This is the stopping point for current-data generated-ensemble diagnostics.
No A4 arm, refit, seed sweep, planner-parameter sweep, or additional post-hoc
statistic is authorized. The primary next evidence requires independent clean
outings under a separately reviewed, locked final-data protocol. Optional BMW-
planner transfer remains separate, requires confirmed interfaces and a new
predeclaration, and cannot replace independent-outing validation.

## Authorized v0.17 independent-outing intake

The amended prospective contract is
`docs/independent_outing_intake_predeclaration.md`. It was written before any
new-outing MCAP or derived value was available to the implementation agent.
The phase is deliberately limited to private raw-file provenance,
outcome-blind technical eligibility, deterministic cohort assignment, and a
final-outing embargo. It fits no model and computes no scientific comparison.

The fixed draft requires at least seven technically eligible new physical
outings in addition to the one legacy development outing. All untouched final
outings come from the new data. Split assignment is a deterministic salted
SHA-256 ranking of content-only outing fingerprints and cannot use filenames,
speed, curvature, confidence, residual, model, or planner results. The first
successful lock is binding and its reviewed hash must be recorded in this
file. Within the 8--12 total-outing planning window, only two or three new
outings form the untouched final set. The intake target is an engineering
planning gate, not a formal sample-size analysis.

Next actions are ordered:

1. preserve the 86 raw chunks, exact manifest, v0.17.0 and v0.17.1 outputs,
   schema probes, verifier result, and all review reports unchanged;
2. use `docs/model_comparison.md` and its reproducible output-driven plotting
   command for the meeting and mid-term presentation; it reports only already
   accepted evidence and does not reopen model selection;
3. preserve the v0.18.0 contract and implementation review `GO` reports and
   original three-file private output unchanged; no further BMW-source answer
   is required for this correction;
4. preserve the accepted v0.18.1 corrective review, passing CI identities and
   the now-reconciled corrected three-file output unchanged; do not rerun;
5. retain the accepted real-output `GO` and merged PR #20 closure; complete
   the source/acquisition inquiry in
   `docs/sensor_topology_source_acquisition_decision.md` before selecting
   further sensor-target implementation or acquisition changes;
6. continue acquiring separate outcome-blind physical outings through new
   manifests and versioned outputs until at least seven new outings are
   technically eligible; where operationally possible, acquire the same
   SENSOR_TOPOLOGY domain as the accepted development lineage;
7. if the available production configuration emits only LANE_MAP, treat that
   as a domain-change blocker requiring a new prospective scientific contract,
   not as permission to relax the current gates; and
8. only after a successful reconciled cohort lock, predeclare and review the
   separate final comparison before reading any embargoed final-outing outcome.

The intake implementation gates are satisfied and the first real audit is
preserved, but the required new-outing count has not. The scientific programme
remains intentionally data-blocked: do not draft evaluator code, fit another
model, or open any final-outing outcome before a successful prospective lock.
The narrow schema-v2 adapter and batch01 audit are independently approved, but
batch01 contributes zero eligible outings. The v0.18 correction creates no
exception by itself: no further current-batch diagnostic,
model-family experiment, gate change, model fit, sampler run, or planner run is
authorized until its applicable review gates pass. The existing final-model
programme remains data-blocked pending new prospectively declared physical
outings.

## v0.18.0/v0.18.1 sensor-topology feasibility

The proposed phase changes only the estimate-side signal under investigation:
`/adp/lane_topology_sensor_based` replaces EDP, while
`/adp/road_lane_map_based` remains the unchanged pseudo-reference. Because
this changes the modeled quantity from an EDP residual to a sensor-lane
residual, it is a new candidate target rather than a v0.17 eligibility repair.
No historical EDP artifact is overwritten or reclassified.

The three Copilot traces are preserved outside Git with SHA-256 values
`57319e59c54ac270d1885c4039d1bac952798f9f7eb293466aec6e6e53b4e3f7`,
`315304f3567b5394f9fb15347c3ce63e3fde55dd4ac1960b4fd77744569468d2`, and
`f5fa27166e824f9276f267ce1b0d449189a5fb5e3e9c3fe3c9a5d3bebc285fb7` and
summarized in the evidence document. They found that `drive_path_range` is not
written by LTSB, `ego_lane_segment_indices` represents branch alternatives,
full geometry may require successor traversal, and the producer directly
consumes map/map-matching inputs. They established the timestamp scalar and
LTSB copy assignment, CAMERA boundary provenance, SENSOR_TOPOLOGY whole-message
assignment, nested coordinate validity, and stored-order geometry. The third
trace resolved all 23 complete paths and rechecked the claims from immutable
`HEAD` blobs. It did not capture the literal BMW commit SHA, which limits exact
source-trace reproduction but does not block the descriptor-driven MPR audit.
The traces did not establish a common physical origin or axes with RLMB.
The fourth trace now qualifies the upstream epoch and processing mode; see
the current evidence note before interpreting source-time pairs physically.

The frozen a3 first stage remains limited to the closed 86-file batch01 and
three privacy-safe outputs. It may inventory descriptors; enforce exactly one
ego index; reconstruct only paired CAMERA-provenance boundaries; follow only a
unique camera-only successor chain; count orientation-invariant 100 m observed
span; audit RLMB H100 readiness independently; and count mutual-nearest
source-time co-availability within 50 ms. It may not compare coordinates,
calculate an anchor/transform/residual, export numeric payload values, build a
sequence, fit a model, run a planner, or produce a figure.

Claude reviewed the exact pushed a3 documentation and v0.18.0 implementation
identities and returned `GO` for both. The technical decoder and path questions
are closed; no further BMW-source answer is required. The one authorized run
then showed a narrower MPR defect: RLMB segment ID field 1 is `uint64`, not the
synthetic fixture's assumed `int64`. It also observed zero strict sensor chains
reaching 100 m. The v0.18.1 correction changes only that descriptor binding,
the associated structural-drift failure label, output version/revision, and the
runtime import-graph test. Focused corrective review returned `GO` for the
exact pushed HEAD and tree recorded above; both CI versions pass. The approved
private rerun is now received and reconciled: reference readiness is 9,235,
source-time pairing is 17,087, and synchronized candidates remain zero with
the sensor ladder unchanged. Focused real-output review returned `GO`, and
PR #20 is merged.
Even a positive synchronized count after correction
would authorize only resolution of the physical frame contract and a separate
alignment-audit predeclaration; it is not an H100 residual pair and does not
prove map independence or permit old EDP model reuse. With zero sensor chains
at 100 m, this closed batch cannot form synchronized H100 structural candidates
unless the predeclared scientific threshold is changed—which is not authorized.

## Reading map

- `docs/bmw_sensor_topology_epoch_evidence.md`: fourth source trace, material
  timestamp correction, evidence limits and recording/frame request.
- `docs/sensor_topology_source_acquisition_decision.md`: current source-only
  inquiry, evidence gaps, decision branches and next implementation gate.
- `docs/sensor_topology_batch01_v0181_result.md`: corrected real batch01
  output, exact lineage, before/after reconciliation and accepted review.
- `docs/modeling_plan.md`: phase gates, evidence, and data-acquisition limits.
- `docs/model_comparison.md`: concise accepted metric table, output-driven
  presentation figure, model comparison by property, and planner relevance.
- `docs/independent_outing_intake_predeclaration.md`: reviewed v0.17 prospective
  intake, deterministic split, and final-outing embargo.
- `docs/independent_outing_data_arrival_runbook.md`: exact initial manifest,
  intake, independent verification, packaging, and review sequence.
- `docs/bmw_edp_schema_evidence.md`: durable MPR descriptor observations and
  Copilot-reported BMW source trace for the EDP v1-to-v2 transition.
- `docs/independent_outing_schema_v2_amendment.md`: reviewed v0.17.1 exact-
  generation compatibility boundary and completed review gates.
- `docs/independent_outing_batch01_v0171_result.md`: accepted amended batch01
  lineage, technical result, interpretation limits, and next acquisition gate.
- `docs/sensor_topology_feasibility_predeclaration.md`: prospective v0.18.0
  batch01 structural audit, exact prohibitions, outputs, tests, and review
  order.
- `docs/sensor_topology_reference_schema_amendment.md`: exact v0.18.1 RLMB
  `uint64` descriptor correction, unchanged rules, and corrective review gate.
- `docs/bmw_sensor_topology_source_evidence.md`: classified Copilot BMW-source
  findings, exact private transcript hashes, remaining frame/producer gaps, and
  the consequences for the frozen a3 contract.
- `docs/sensor_topology_feasibility_implementation_notes.md`: exact reviewed
  starting identity, implemented module boundary, synthetic verification, and
  next-agent checklist for the v0.18.1 correction. Reviewer prompts are sent
  separately and are not project documentation.
- `docs/output_contracts.md`: exact output files and schemas.
- `docs/aiohmm.md`: model equations, evaluation, and limitations.
- `docs/architecture.md`: package ownership and dependency boundaries.
- `docs/commands.md`: complete CLI surface.
- `README.md`: chronological project overview and usage.
