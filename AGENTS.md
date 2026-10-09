# MPR agent instructions

These instructions apply to the complete repository. MPR is the canonical
implementation for the thesis; LEEM is historical reference material only.

## Start every task here

1. Read `docs/current_status.md` for the exact stopping point and next task.
2. Read the relevant contract before changing code:
   - `docs/modeling_plan.md` for scientific gates and phase decisions;
   - `docs/output_contracts.md` for exact artifact schemas;
   - `docs/architecture.md` for ownership boundaries;
   - `docs/commands.md` for supported entry points;
   - `docs/generic_recording_ingestion_v0196.md` and its runbook before
     registering or auditing newly downloaded arbitrary MCAPs;
   - `docs/bmw_edp_schema_evidence.md` before changing any estimated-drive-
     path schema binding; and
   - `docs/independent_outing_schema_v2_amendment.md` for the reviewed v0.17.1
     compatibility boundary; and
   - `docs/independent_outing_batch01_v0171_result.md` for the accepted real
     amended audit, its exact lineage, interpretation, and remaining data gate;
     and
   - `docs/sensor_topology_feasibility_predeclaration.md` and
     `docs/bmw_sensor_topology_source_evidence.md` before any work that reads
     `/adp/lane_topology_sensor_based` as a candidate estimate source; and
   - `docs/bmw_sensor_topology_epoch_evidence.md` for the later correction to
     unconditional camera-time/raw-geometry interpretations.
3. Inspect `git status --short`, the current branch, and recent commits.
4. Preserve unrelated user changes and previously reviewed artifacts.

## Current checkpoint: 2026-10-08

The v0.19.9 selected-stream decode check is implemented locally on merged
PR #31 (`05e0c71`). Read `docs/generic_recording_decode_check_v0199.md` and
its complete runbook. Disk-backed scalar index ordering avoids the old full
summary retention; embedded Protobuf decoding/count reconciliation and
selected nonzero chunk CRC coverage run without a scientific adapter. A valid
116,243-chunk synthetic fixture completes under 256 MiB process address space;
this does not diagnose the original private ZstdError. Implementation GO and
Python 3.10/3.12 CI precede one new post-merge EDP/RLMB/odometry decode check.
No private decoding result exists here. Preserve old registration/reports;
no re-registration, old deferred step 6, geometry, reference/target/topology
adoption, export, real fit, role assignment or raw deletion follows yet.

## Historical checkpoint: 2026-10-08 accepted inventory result

PR #31 is now merged as `05e0c71f93f8133204f6b5577f5ca69662f647fc`, tree
`b44bbc4f18fc68a5a7f0ec8875f9a4f5b3feab7e`. Reviewed head `296e161` has Claude
GO/zero blockers and successful Python 3.10/3.12 CI (606 run/two existing
skips, temporary merge of that exact head). The owner completed one pilot
inventory, exit 0: fresh raw verification, validated nonzero summary CRC,
506 channels/topics, 448 schemas and exact reconciliation with prior metadata.
Read `docs/recording_inventory_batch03_v0198_result.md`. No payload decoded;
ZstdError/native support/residual eligibility remain unresolved.

Next is a specified, bounded selected-stream decoding check for generic input
infrastructure, before geometry. It is not yet implemented/frozen. Include
index-memory behavior, selected CRC coverage and full-count versus incomplete
publication tests; implementation GO/CI precedes a new private run. Do not
repeat registration/inventory or treat this result as authorization to run
old deferred step 6. Native-reference proposal/target adoption/numeric export/
real fits/outing roles/raw retirement remain separate evidence-backed steps.

## Historical checkpoint: 2026-10-08 inventory implementation prepared

PR #30 is merged as `c8a757229c87d040d913ccdeed96364fd1d5e0bc`, tree
`badf8da510ea6632f20d50402ac3e20e033a6fae`; reviewed final head `1e1fe43`
has Claude GO/zero blockers and independently verified exact-head CI.
Read `docs/reference_evidence_checkpoint_20261008.md` for all returned
Oct-05 evidence and its distinctions between recording/source/hypothesis.

The owner resumes generic pipeline work. The new registered-file inventory
is metadata only, with raw verification and bounded summary parsing; it
neither implements nor freezes the native-reference proposal. Read
`docs/generic_recording_inventory_v0198.md` and its complete runbook before
running `recording_ingestion inventory`. Exact-head implementation GO and
Python 3.10/3.12 CI precede one new private inventory in a fresh directory.
No new private result exists here. Old step 6 remains deferred, the pilot
ZstdError unresolved, decoded support unknown. Preserve all old identities.
Generic numeric export, reference/target/population adoption, real fits,
outing roles and raw deletion remain separate evidence-backed steps.

## Historical checkpoint: 2026-10-04

PR #30 is open at `cf2ae298835f154e3e597e746408dfd47e24238a`, tree
`ae8565dedaa2ccf0a8ba65c312eabebba3ed010c`. Claude GO has zero blockers;
Actions run `37211254466` passes Python 3.10/3.12, each 579 tests/two skips,
independently verified. A documentation-only evidence closure is prepared for
the same PR; new-head delta GO/CI precede merge. Read
`docs/reference_evidence_reconciliation_20261004.md` and the complete
`docs/reference_evidence_followup_runbook_20261004.md`.

The pilot's metadata report exposes 38 selected schema versions, including
35 foresight topics and EDP/RLMB/pose/lane/ENU/MPP structures. Counts are
advertised; no payload was decoded, fresh raw SHA or summary CRC verified.
Source dossier `master@465073bc` is externally reported evidence, not a full
immutable checkout identity or deployed recording build. It reports shared
map/pose/camera dependencies, covariance basis changing with writer mode,
and stamps that need not equal geometry epochs. Rebuilding foresight+pose
does not establish a better independent reference. SENSOR can include map
road-layer support; its enum alone does not establish independence.

Old runbook step 6 remains deferred; ZstdError and decoded feasibility are
unresolved. Next is the focused source/provenance follow-up and reviewed
native-structure audit proposal in
`docs/reference_native_structure_audit_proposal_20261004.md`. This is not a
frozen contract, implementation or private-run authorization. Missing producer
identity/mode can remain unknown for native counts; it blocks physical
transformation/propagation/accuracy claims. Distinguish map-relative agreement
from physical lane/path error and choose the target explicitly before export.
No reference adoption, mode guessing, covariance propagation/correction,
all-topology extraction, feature amendment, model fit, outing roles or deletion.

## Historical checkpoint: 2026-10-03

PR #29 merged as `fc6d5ff72c5812d43367897cc92416fd870e2686`; final head
`fe97561a3cfe6c727b16c56d661c21d551ae7aa6` has passing Python 3.10/3.12 CI
in run `37002940067`. Owner reports Claude delta GO. The post-merge 56 focused
tests passed. The private successor then stopped at initial memory preflight:
4.5 GiB MemAvailable < 6 GiB, exit 2, before raw hashing/decoding/output.
No new report or data finding exists. Read
`docs/recording_ingestion_batch03_v0197_preflight_stop.md`; the scratch directory
can remain empty from the shell preparation. Do not repeat registration,
automatically retry or lower caps. The original ZstdError is unresolved.

Owner's road-team discussion motivates a **prospective all-topology EDP and
reference study**. Map preference reportedly makes SENSOR-only EDP scarce;
the quoted ~90% is verbal context, not a new-file statistic. Investigate
`/adp/position_on_map_pose_estimate` (reported 6 x 6 covariance),
`/adp/foresight_lane_data_opb` and actually recorded foresight topics before
choosing a reference. Exact recorded schemas, producer dependencies, frames,
origins, covariance convention, lane binding and epochs are not established.
Read `docs/reference_redesign_investigation_20261003.md` and its complete
runbook. Next acquire BMW source/metadata evidence, then design a separately
reviewed bounded structural adapter. The old readiness successor is deferred.

This is a documentation/evidence phase, not a filter removal or adopted target.
Existing SENSOR-only outputs/contracts, six features, H100/sign, no-extrapolation
and final-data gates remain unchanged. Do not use covariance as a mean correction,
call shared-map disagreement ground-truth error, fuse correlated paths as
independent, select a reference by closeness to EDP, apply a pose transform twice,
or fit a model. Topology remains observable provenance in the proposed study.
The earlier checkpoints below are historical.

## Historical checkpoint: 2026-10-02

PR #29 is open at reviewed head `33f9542ffa835ded9d45c562528862506c1e91af`,
tree `7682cd3c5df0ae339d98d5a58fcbd6bcf0c89926`. Claude GO has zero blockers;
Actions run `36997429154` passes Python 3.10/3.12 (576 tests, two opt-in skips),
verified separately from the review. Before the single private successor,
adopt R1: readiness validates nonzero stored chunk CRCs; historical batch02
defaults stay false. Read `docs/bounded_storage_reader_crc_review_v0197.md`
and its dedicated runbook. The same-PR delta runs 579 tests (577 pass, two
existing skips), with 56 focused passes. It needs delta GO and CI at the new
pushed head before merge/private execution. CRC 0 means unavailable, not full
integrity proof; no raw bytes, registration, geometry, causality, resource
limit or output path changes. The earlier checkpoint below is historical.

PR #28 is merged at `8d55edf5f4c2ae7d30ce2533f702138319d63270`; its exact
reviewed head `ef7efb9` received GO and Python 3.10/3.12 CI. The one authorized
batch03 pilot001 audit returned inconclusive `ZstdError`, with readable index
evidence but null decoded observations. Read
`docs/recording_ingestion_batch03_v0196_result.md` and
`docs/bounded_storage_reader_v0197.md` before further work. The old assumption
that SeekingReader's FIFO storage iterator bounds raw-payload retention is
disproved. Its confirmed queue defect does not prove the private failure was
memory rather than a bad compressed frame. Preserve the registered file and
failed report; do not remerge, re-register, raise caps, change geometry or
declare zero pairs. The narrow v0.19.7 chunkwise reader and safe context are
implemented locally; 576 tests run, 574 pass, two existing opt-ins skip, with
53 focused passes. Exact-head corrective GO and normal CI must precede the
single predecessor-gated successor in a fresh directory. No private successor
has run here, and no generic archive/model/deletion/final-data gate is opened.
The earlier v0.19.6 preparation/review instructions below are historical.

Update `docs/current_status.md` whenever a phase is implemented, reviewed,
merged, or materially reinterpreted. It is the hand-off record for future
agents and new chats.

## Working relationship

- ChatGPT/Codex is the primary implementation agent. Claude is an independent
  reviewer, not the primary implementer.
- Stay focused and precise. Prefer the smallest defensible experiment or code
  change; do not expand the model family or architecture without evidence.
- Do not ask Leon for detailed implementation progress. Ask the user only when
  a scientific decision or unavailable BMW interface blocks correct work.
- The BMW codebase is unavailable here. Never invent its APIs, types, paths,
  planner entry points, or metric interfaces. BMW details are required only
  for an explicit BMW integration or transfer-validation task; they do not
  block the MPR-owned reference-planner sensitivity experiment. When BMW
  integration is required, give the user a focused Copilot prompt and wait for
  exact symbols and signatures.

## Scientific invariants

- The target is the 21-dimensional signed H100 pseudo-residual at
  `0, 5, ..., 100 m`.
- Residual means EDP estimate minus the spatially aligned RLMB
  pseudo-reference, projected onto the pseudo-reference left unit normal.
  Positive is left with respect to increasing station.
- The prospective v0.18 sensor-topology target is not adopted. The BMW trace
  establishes camera-derived boundary geometry inside a map-influenced
  topology graph but does not establish physical frame equivalence with RLMB.
  After focused review, its first phase may inventory strict camera-chain
  structure, orientation-invariant 100 m span, independent RLMB H100 readiness,
  and source-time co-availability only. It may not compare cross-topic
  coordinates, calculate an anchor or residual, or reinterpret an EDP result.
  The frozen a3 review candidate is supported by three private source traces.
  The third resolves every cited tracked path and rechecks the findings from
  immutable `HEAD` blobs; its failure to record the literal BMW commit SHA is
  a source-trace reproducibility limit, not a blocker for the fail-closed MPR
  structural audit. No further BMW-source answer is required for this phase.
  The frozen contract received focused `GO`, and the synthetic-only structural
  audit is implemented. Do not inspect private MCAPs before the exact pushed
  implementation receives focused implementation `GO`.
  Historical EDP models and sensor-lane residuals must never be pooled or
  relabelled as one target.
- RLMB is a pseudo-reference, not physical ground truth.
- BMW condition schema v1 is fixed in this exact order:
  `speed_mps`, `estimated_mean_abs_curvature_per_m`,
  `estimated_curvature_delta_per_m`, `confidence_near_mean`,
  `confidence_middle_mean`, `confidence_far_mean`.
- Prediction-time inputs may use only current or causal past estimator/vehicle
  state. Never use residuals, future values, RLMB outputs, or
  pseudo-reference-derived quality as features.
- Fit standardizers inside training folds only. Held-out groups must not affect
  fitting, early stopping, restarts, transforms, or hyperparameters.
- Current primary evidence is four technical recording groups from one
  same-day outing. It does not estimate independent-journey generalization.
- Never infer independent-outing count from MCAP count, filename numbering,
  directory count, continuous-block count, or technical recording-group count.
  Only the prospectively recorded physical-session declarations determine the
  outing unit. Read `docs/current_status.md` for the dated raw-data chronology.
- The frozen v0.15.4 planner-development model is K=1 with AR ceiling 0.99.
  This is a structural release of the binding 0.98 constraint, not a held-out
  performance selection. The failed v0.15.3 strict gate and reviewed 0.98
  reporting reference must remain visible.
- Generate residuals free-running over complete sequences: generated history
  feeds the next step and state resets exactly once per declared sequence.
  Independent frame sampling is invalid.
- Do not claim final model selection or planner benefit without the required
  independent data or completed planner experiment.
- RC-GAN is not pursued on the current one-outing corpus.
- The independently reviewed v0.16.2 audit is the final diagnostic on the
  current generated ensembles. Do not add an A4 arm, refit, seed sweep,
  planner-parameter sweep, or further post-hoc current-outing statistic.
- The next primary scientific evidence requires additional independent clean
  outings under a reviewed, locked final-data protocol. BMW-planner transfer is
  optional and separate; it requires confirmed interfaces and a new reviewed
  predeclaration and does not replace independent-outing validation.

## Implementation and artifact rules

- Prior version outputs are immutable inputs. New workflows validate exact
  file sets, schemas, and SHA-256 lineage before creating output.
- Write into a new empty versioned output directory. Fail before output on
  missing, extra, drifted, or tampered dependencies.
- Keep deterministic seeds and record them in summaries.
- Keep domain arithmetic, orchestration, I/O, visualization, and CLI adapters
  in their existing package layers.
- Generated `outputs/`, raw MCAPs, private configuration, and fitted model
  artifacts stay outside version control unless the user explicitly directs
  otherwise. Commit code, tests, contracts, and documentation.
- Do not silently change a reviewed scientific rule to make a gate pass.
  Preserve the failed result and declare any separate engineering decision.

## Verification and delivery

The v0.19.9 selected-stream decoder raises the baseline to 650 run, 648
passing and the same two opt-in skips. Its 44 focused tests pass with
MCAP 1.4/1.5; run these before the new post-merge private check. Local Python
3.12 validation does not substitute for pushed-head Python 3.10/3.12 CI.

Run at minimum:

```bash
python -m compileall -q src tests

env PYTHONPATH=src \
  MPLBACKEND=Agg \
  MPLCONFIGDIR=/tmp/mpr-matplotlib \
  python -m unittest discover -s tests -t .
```

At v0.15.4 the expected baseline is 315 passing tests with two expected
optional-dependency skips. Treat a changed count as something to explain.
The corrected v0.16 reference-planner implementation raises this to 324 passing tests
with the same two expected skips. The reviewed v0.16.1 Gaussian-transfer
implementation raises this to 329 passing tests with the same two skips. The
v0.16.2 spatial-structure audit raises this to 339 passing tests with the same
two skips.
The v0.17.0 independent-outing intake raises this to 381 passing tests with the
same two skips.
The v0.17 data-arrival verifier and runbook raise this to 384 passing tests with
the same two skips. They add no model or current-data diagnostic. The first
real v0.17.0 audit is preserved but is not a successful cohort lock; read
`docs/current_status.md` before any v0.17.1 work.
The v0.17.1 schema-v2 compatibility implementation raises this to 402 passing
tests with the same two skips. Its implementation and real batch01 audit both
received focused independent `GO`. Batch01 contributes zero eligible outings;
do not rerun it or relax topology, H100/map-pairing, anchor, or causal-input
gates. Further evidence requires new prospectively declared physical outings.
The reporting-only output-driven model comparison raises this to 404 passing
tests with the same two skips. It does not authorize a model fit, a new metric,
or final model selection.
The v0.18.0 structural-feasibility implementation raises the suite to 432 tests
run: 430 pass and two expected optional-dependency tests skip. Contract and
implementation review returned `GO`, authorizing one private batch01 run. That
run exposed an exact RLMB descriptor binding defect (`RoadLaneSegment.id_` is
`uint64`, not `int64`) while independently observing zero sensor chains reaching
100 m. Preserve the v0.18.0 output unchanged. The narrow v0.18.1 correction must
receive focused corrective review before a rerun into a new directory. It does
not authorize threshold changes, target adoption, residual creation, model
reuse, a model fit, a planner run, or a figure.
The narrow v0.18.1 correction and takeover regression raise the suite to 434
tests run: 432 pass and the same two expected skips. Its 30 focused tests
include the observed `uint64` reference descriptor, fail-closed `int64` drift,
and a short sensor chain that remains ineligible despite valid reference
geometry and timestamp pairing.

The v0.18.1 corrective implementation and corrected real batch01 output have
now both received focused `GO` with zero blockers; Python 3.10/3.12 CI passes.
The accepted result remains zero sensor 100 m spans and zero synchronized
candidates, despite 9,235 reference-ready messages and 17,087 time pairs.
Read `docs/sensor_topology_batch01_v0181_result.md` and the first section of
`docs/current_status.md` for exact identities, verification limits and the
documentation closure. The earlier review-before-rerun instructions above
record gates already completed, not permission for a further run. The closed
batch stays negative; no horizon/rule change, residual construction or new
scientific execution is authorized. PR #20 is now merged. The source inquiry
in `docs/sensor_topology_source_acquisition_decision.md` has returned. The
next step is focused review of the epoch interpretation correction and the
recording/frame evidence request in `docs/bmw_sensor_topology_epoch_evidence.md`.
Do not treat current-source defaults as recording settings, x cutoff as
geometric span, or source-time pairing as equal physical measurement age.
This does not reopen closed decoder questions or authorize a private run.
Select the next executable change only after applicable evidence identifies it.
The 2026-09-19 arrival of four large MCAPs changes the immediate priority:
follow `docs/independent_outing_batch02_arrival.md` for isolated file registration,
truthful private session declarations and the existing summary-only reader.
The epoch correction is already pushed at `ca6b154`; do not apply it twice.
This administrative inventory does not decode payloads or assign roles.
Assess whole-file geometry retention and O(N*M) pairing before a full-drive
run; do not use the batch01-pinned v0.18 command for new files. Four files do
not prove four outings and four eligible outings cannot meet the seven-outing
gate. Keep old outputs immutable and use the batch02 root, not its parent.

The batch02 registration, epoch interpretation and canonical pairing
maintenance received focused `GO`, zero blockers, at PR #21 head `ed981793`,
tree `19d57ee15cbde04314341fc551303de8832e92bd`; Python 3.10/3.12 CI passes.
The PR is merge-ready, still unmerged at the 2026-09-19 check. The reported
registration commit is now pushed with the expected tree. Read
`docs/independent_outing_batch02_registration_result.md` for exact identities
and evidence limits. The suite remains 440 run, 438 passing and two skips.
This changes no scientific pairing rule or separate v0.18 sensor matcher.

Both returned manifests, including `v002`, remain the same unfilled draft.
Follow `docs/independent_outing_batch02_session_context.md` for one summary-only
container time-range/RAM follow-up and truthful provider/session declarations.
No raw-file rehash, payload inspection or manifest auto-completion is part of
that command. MCAP log time need not use the Unix epoch; any UTC display is
conditional, and no file count proves separate physical sessions. Missing
declarations do not block merging the accepted maintenance PR or synthetic
engineering work. Whole-file geometry retention still needs resource
assessment before intake; the separate sensor matcher remains quadratic.
Do not rerun registration, infer eligibility from summary counts, or execute
private geometry from this maintenance alone. Closed batch01 stays closed.

The 2026-09-20 checkpoint supersedes the owner-evidence requests above:
PR #21 is merged at `7834def`, final-head Python 3.10/3.12 CI passed, and the
time/RAM JSON is reconciled. The owner cannot recover the session/acquisition/
export evidence. Keep it unavailable and stop requesting a completed batch02
v0.17 manifest. This blocks its independent-outing admission, not all technical
work. No session identity or training/final role may be inferred from dates.

The new recording-level EDP/RLMB pilot and shared streaming converter are
prepared for review; read `docs/recording_pair_feasibility_predeclaration.md`
and `docs/independent_outing_batch02_context_result.md`. After focused GO and
normal CI, its separate CLI may inspect only the exact registered batch02
files, with disk-backed geometry, complete timestamp streams, fresh RAM/disk
checks and the documented process limit. No v0.17 lock, causal-feature check,
residual, new sensor target or model follows. Resource/stream failures are
inconclusive with null counts, not negative geometry. Do not run the old
full-file intake with fabricated declarations or reopen closed batch01.
The fifteen new tests raise the suite to 455 run: 453 pass and the same two
opt-in tests skip. The 52-test focused selection is documented explicitly.

The 2026-09-21 checkpoint supersedes the pilot-preparation instructions above:
PR #22 received implementation/scope GO with zero blockers and passed Python
3.10/3.12 CI at `0661796`; the authorized pilot completed on all four files.
Read `docs/recording_pair_feasibility_batch02_result.md` and the current-status
header. The result contains 7,743 anchored H100 candidates, of which 376 carry
the sensor-topology EDP label; no residual, causal-feature check, role or lock
was produced. Do not rerun this completed pilot or promote geometry counts to
eligible outings. The next narrow diagnostic must distinguish RLMB conversion
reasons and numeric timestamp offsets before residual readiness is assessed.
No threshold change or target adoption follows from these observed counts.
PR #22 remains open and merge-ready; this result closure belongs in that PR.

The 2026-09-22 checkpoint implements that next diagnostic behind the explicit
`--preserved-feasibility-report` flag on the existing CLI. Read
`docs/recording_pair_diagnostics_predeclaration.md` before using it. Its failure
classification and integer timing summaries are observational; all old counts
must match the exact preserved pilot or the recording is inconclusive. The
new output is `recording_pair_diagnostics.json`. EDP/RLMB is prioritized and
direct LTSB work is on hold. This does not settle independence or adopt a target.
The suite now runs 477 tests: 475 pass and two expected opt-ins skip; 74 focused
tests pass. The default v0.17 import graph and legacy count behavior are intact.
PR #22 still needs its previously delivered documentation closure and merge;
put the new implementation in a separate PR after that merge. Its exact pushed
head needs focused implementation/scope GO and normal CI before the one new
private run. No new output is available yet and no residual/model follows.

The later 2026-09-22 result checkpoint supersedes those preparation gates:
PR #22 is merged at `dddbcc9`. PR #23 at `83da0f1`, tree `d9f74f8`, received
implementation/scope GO with zero blockers and passing Python 3.10/3.12 CI.
Its one real diagnostic completed with exact equality of every original count.
Read `docs/recording_pair_diagnostics_batch02_result.md` and the current-status
header. All 29,569 generic reference errors are empty lane lists; all 7,743
anchored H100 pairs, including 376 sensor candidates, have source-time delta
zero. No parser correction or time shift is supported; no residual exists yet.
Do not repeat this diagnostic. Its documentation closure belongs in PR #23.
Next prepare separately reviewed exploratory extraction: check six causal
inputs and file-local contiguous support before exporting retained 21-station
pseudo-residuals, conditions and provenance. Keep geometry/topology rules and
resource limits; examine actual odometry input causality, do not bridge files,
invent session identity or count LANE_MAP rows as sensor data. More suitable
independent data are still required for the final cohort. No new private
command or model fit is authorized by the completed diagnostic's GO.

The 2026-09-24 checkpoint supersedes the PR #23 closure instructions above:
PR #23 is merged at `49ca002`, tree `ee8392a`; CI run `35984264643` passed
Python 3.10/3.12 at final head `f32f27d`. The separately scoped v0.19.2 extractor
is implemented; read `docs/exploratory_residuals_predeclaration.md` and its output
contract. It preserves every original count and diagnostic, exports geometric
pseudo-residuals separately from the complete-feature subset, and never bridges
files or excluded frames. The prospective availability check retains the fixed
50 ms speed arithmetic but rejects used odometry states after the estimate epoch
or logged after the estimate. This implies exact current-epoch pose support;
recorded-clock checks do not prove physical availability. A strict subset may
be empty without disproving geometric residual feasibility. These new decisions
need focused review of the exact pushed implementation plus normal CI before
one private run. No real v0.19.2 result, model fit or outing lock exists yet.
Do not rerun the old pilot/diagnostic or request unavailable session metadata.
Verification now runs 503 tests: 501 pass and the two existing opt-ins skip;
100 focused tests pass, including 26 new tests and real MCAP odometry reading.

The 2026-09-25 result checkpoint supersedes the review-before-run instructions
above: PR #24 at `42bedf6` (tree `74ad92c`) received focused implementation
GO with zero blockers. Python 3.10/3.12 GitHub Actions run `36108508093` passed
503 tests with the two expected opt-in skips. The authorized batch02 v0.19.2
extraction is complete: 376 finite SENSOR EDP/RLMB pseudo-residuals, 134
complete-condition rows, 26 condition sequences/108 transitions and a 10-frame
maximum. The 242 missing conditions consist of 232 future-source speed brackets
and 10 interpolation-gap failures; no new causal-speed definition was adopted.
Read `docs/exploratory_residuals_batch02_v0192_result.md` for hashes, complete
reconciliation and limitations. **Do not rerun** the old pilot, timing diagnostic
or this extraction. Keep its outputs immutable. Its documentation-only closure
belongs on existing PR #24; pass CI at that new head before merging. No model fit,
outings/roles/lock, target change, AR/AIOHMM run or final-data validation is
authorized by these results. The next consumer needs an exact archive validator
and separately reviewed scope; prioritize prospectively identified independent
data with longer feature-ready sequences. Owner cannot recover batch02 session
provenance; do not request it again.

The later 2026-09-25 checkpoint supersedes the PR #24 merge instruction:
PR #24 is merged as `95745ea`. Branch
`feature/v0.19.3-archive-and-flow-foundation` adds a pinned, read-only
v0.19.2 output validator and synthetic straight-path conditional flow math;
read `docs/flow_matching_foundation_v0193.md` and the new header of
`docs/current_status.md`. This is not a cohort, new reference, trained flow,
model comparison, log-density implementation or permission to rerun MCAPs.
For future model fits, predeclare matched rows and physical outing splits,
with substantially longer feature-ready sequences before temporal claims.

The 2026-09-27 PR #25 correction was re-reviewed and merged as `7a98804`;
its Python 3.10/3.12 CI passed at final head `ccac468`. PR #26 adds
synthetic-only unconditional and six-feature autoregressive conditional
trainable flow fields; it merged as `6d00ab8` after focused review and
final-head Python 3.10/3.12 CI at `b24d411`. Read the first section of
`docs/current_status.md` for the current v0.19.5 synthetic hardening scope.
Neither mode may be fitted on batch02 by this work. The proposed RC-GAN-to-flow substitution
needs a supervisor-visible decision before a real fit; the independent-outing
and long-condition-support gate for another model family remains unchanged.

The 2026-09-30 checkpoint supersedes the v0.19.5 preparation wording:
PR #27 received synthetic-scope GO at `08cdfdf`, tree `2bc747a`, and both
Python 3.10/3.12 jobs passed in run `36692825235`. It is still unmerged.
The supplied PR #26 delta and PR #27 reviews carry forward finding C1:
`std == 0` misses exactly constant decimal columns. The narrow local
correction detects exact input equality, pins the constant mean and uses
scale one, preserving varying-column statistics without an epsilon floor.
Three regression tests raise the suite to 526 run; this local environment
passes 509 with 17 dependency/opt-in skips and all 17 focused flow tests.
Apply in the existing PR #27, then require focused delta GO and final-head
CI before merge. Do not create a new PR, reopen private diagnostics or fit
on batch02 on this correction's authority. Read the current-status header
for review identities, numerical before/after evidence and the data gate.

The 2026-10-01 checkpoint supersedes the PR #27 pre-merge instructions above:
it merged as `d03f776`, corrected final head `8273741`; delta GO and Python
3.10/3.12 CI run `36709679003` passed. Do not reapply that correction.
The separate v0.19.6 generic recording intake/readiness branch is prepared
for implementation review. Its commands declare development-only sources,
register raw hashes and audit indexed geometry, strict causal inputs and
recording-local sequence support. It accepts new declared files and preserves
the batch02 pins/defaults. Read `docs/generic_recording_ingestion_v0196.md`
before use. The new merged 180-chunk file is one technical recording, not
180 outings. Do not infer session identity or UTC dates from its screenshot.
Require exact-head GO and CI before its new private payload audit. No numeric
residual/condition export, fitting, outing admission or raw-cache deletion is
authorized by this readiness scope; prepare that follow-up only from reviewed
new evidence. Old completed private diagnostics must not be repeated.

Do not push, merge, open a pull request, or modify external systems unless the
user asks. Deliver repository changes as a ZIP patch batch containing a
`README.md` and numbered `git format-patch` files. The user's download location
is `~/Downloads/MPR`; always include `unzip <bundle>.zip` before `git am` in the
instructions. The actual repository directory is `~/PycharmProjects/MPR`.

## Code review rules

Flag any change that:

- changes the H100 grid, residual sign, feature order, or free-running contract;
- introduces held-out leakage or selects hyperparameters from held-out metrics;
- treats technical groups as independent journeys;
- hides a failed gate or upgrades development evidence into a final claim;
- changes a prior artifact instead of adding a versioned consumer;
- invents an unavailable BMW interface or reports planner benefit without an
  executed, predeclared planner evaluation.
