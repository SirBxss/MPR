# PR #30 evidence closure and next actions

Date: 2026-10-04. This is the delivery ZIP's complete README. Read
`reference_evidence_reconciliation_20261004.md` for findings and evidence
limits. This delta is documentation only; it includes no new decoder or
private payload command.

## 1. Immediate answer

**Do not run step 6 of the 2026-10-03 README.** It remains deferred. Its
SENSOR-only support question does not answer the new reference questions.
The original PR #30 head has Claude GO and independently verified passing
Python 3.10/3.12 CI. The supplied evidence establishes recorded schemas and
reported producer dependence, not valid residual pairs or a better reference.

Apply this evidence closure to **the existing PR #30 branch**, not a new PR.
It adopts two nonblocking review improvements, records all four returned
artifacts and specifies the next native-structure audit as a proposal. No
historical result, source filter, feature schema, target or runtime changes.
Do not download more large batches or delete the registered pilot now.

## 2. Apply and test from the correct repository

Save `mpr_pr30_reference_evidence_20261004.zip` in `$HOME/Downloads/MPR` or
`$HOME/Downloads`. Keep its exact basename. This block finds either location;
it does not depend on the terminal's initial directory or an MCAP basename.
If already extracted, it verifies the existing bundle instead of overwriting
it. The branch must still be based at the reviewed PR head `cf2ae29`; a
different head stops for reconciliation, without resetting any work.

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_name="mpr_pr30_reference_evidence_20261004"
  mpr_zip="$mpr_downloads/$mpr_name.zip"
  if ! test -r "$mpr_zip"; then mpr_zip="$HOME/Downloads/$mpr_name.zip"; fi
  if ! test -r "$mpr_zip"; then
    echo 'Stop: save mpr_pr30_reference_evidence_20261004.zip in Downloads/MPR or Downloads.' >&2
    exit 1
  fi
  cd "$mpr_repo"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -n "$(git status --porcelain)"; then
    echo 'Stop: preserve or commit existing changes before applying.' >&2
    exit 1
  fi
  mkdir -p "$mpr_downloads"
  mpr_bundle="$mpr_downloads/$mpr_name"
  if test -L "$mpr_bundle"; then
    echo 'Stop: bundle directory is a symlink.' >&2
    exit 1
  fi
  if ! test -e "$mpr_bundle"; then unzip "$mpr_zip" -d "$mpr_downloads"; fi
  test -d "$mpr_bundle"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  set -- "$mpr_bundle"/0001-*.patch
  if test "$#" -ne 1 || ! test -f "$1"; then
    echo 'Stop: expected exactly one numbered patch.' >&2
    exit 1
  fi
  mpr_patch="$1"
  mpr_branch="docs/reference-redesign-2026-10-03"
  git fetch origin "$mpr_branch:refs/remotes/origin/$mpr_branch"
  if git show-ref --verify --quiet "refs/heads/$mpr_branch"; then
    git switch "$mpr_branch"
  else
    git switch --track -c "$mpr_branch" "origin/$mpr_branch"
  fi
  git pull --ff-only origin "$mpr_branch"
  if test "$(git rev-parse HEAD)" != cf2ae298835f154e3e597e746408dfd47e24238a; then
    echo 'Stop: PR branch differs from the reviewed delta base; return git log -5.' >&2
    exit 1
  fi
  git apply --check "$mpr_patch"
  git am "$mpr_patch"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  python -m compileall -q src tests
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
    python -m unittest discover -s tests -t .
  git diff --check cf2ae298835f154e3e597e746408dfd47e24238a HEAD
  git diff --exit-code fc6d5ff72c5812d43367897cc92416fd870e2686 HEAD -- src tests pyproject.toml config scripts .github
  test -z "$(git status --porcelain)"
  git log -2 --oneline
)
```

Expected suite: **579 run, 577 pass, two existing skips** with MCAP extras.
This verifies repository behavior; it does not inspect the private recording.
If `git am` fails, stop and return `git status --short` and the error. Do not
reset or run a second patch application. The previous directory error is
avoided by the explicit `cd`, top-level repository and project-file checks.

## 3. Push the existing PR; review the final head

After the apply/test block succeeds:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git branch --show-current)" = docs/reference-redesign-2026-10-03
  test -z "$(git status --porcelain)"
  git push origin docs/reference-redesign-2026-10-03
  git rev-parse HEAD
)
```

Keep **PR #30**. Suggested final title:

`docs: reconcile reference evidence and defer unsafe covariance interpretation`

Suggested description (replace the old description, retaining these facts):

```text
The pilot's v0.19.7 successor stopped on the initial 6 GiB memory preflight,
before hashing/decoding and without a report. This docs-only change records
that incident and reconciles the returned Claude review, metadata-only Codex
transcript/JSON and BMW source dossier. The selected summary exposes EDP,
RLMB, pose, foresight lane/ENU/MPP schemas; no payload validity or residual
result follows. The source trace reports shared map/pose dependencies and
mode-dependent covariance/timestamp semantics, so a better independent
reference is not adopted.

Recovery guards now use explicit checks that survive Python optimization;
the docs distinguish initial exit 2/no report from post-hash resource exit
3/inconclusive report. The old step 6 remains deferred. A native-structure
audit is proposed for separate focused contract/implementation review.
Source, tests, configuration, old artifacts, SENSOR filtering, six features
and model behavior are unchanged. Both flow modes remain synthetic-only.

Validation: compileall; 579 tests, 577 pass and two existing skips; shell
syntax and optimized recovery-guard fixtures; report graph/extent arithmetic;
patch apply/tree and unchanged implementation checks. The original cf2ae29
head had Claude GO and passing exact-head Python 3.10/3.12 CI; delta review
and CI must apply to the new final head before merge. No private payload ran.
```

Claude prompt, after pushing (Claude has the MPR checkout; this is not BMW
Copilot):

```text
Review the final pushed PR #30 head, including the documentation delta on
cf2ae298835f154e3e597e746408dfd47e24238a, against main fc6d5ff. Record exact
head/tree and return GO/NO-GO with numbered blockers. Do not edit, merge,
inspect private MCAP payloads or run the deferred old step 6.

Read AGENTS/current_status, reference_evidence_reconciliation_20261004.md,
reference_evidence_followup_runbook_20261004.md and the draft native-audit
proposal. Verify the old implementation/artifacts/contracts are unchanged.
Check N1/N2: initial resource exit 2/no report versus post-hash exit 3/report;
explicit recovery guards must fail closed under PYTHONOPTIMIZE for nonempty
or symlink/file scratch, existing/dangling output, identity/resource failures.

Check recorded-schema versus reported-source versus hypothesis separation.
Counts are advertised, covariance is repeated double with unproved per-message
length/mode, descriptors do not identify deployed software, summary CRC and
fresh raw SHA were not verified. The BMW source trace has only a short SHA
and cannot independently establish recording behavior. Rebuilding correlated
foresight+pose is not adopted as improved independent truth. SENSOR can include
a map road layer; near-equal stamps and counts do not prove physical sync.
No covariance-as-correction, mode guessing, double transform, closest-to-EDP
lane selection, feature leakage, residual or fit. Verify commands, bundle
base, existing branch/PR and privacy. The native audit is a proposal, not an
executable/private-run authorization. Verify new-head CI or mark it unverified.
```

**Merge when delta review has GO/zero unresolved blockers and both Python
3.10/3.12 jobs pass at the final pushed head.** The original GO was valid;
it does not review new text. Do not open another docs PR or close the working
branch beforehand. After merge, return the merge SHA and delta review.

## 4. Focused BMW follow-up: independent of step 6

This is a self-contained prompt for Copilot/Codex connected to the **BMW
checkout**. It needs no MPR/thesis context. Run in parallel with section 5
if convenient. A source-only answer cannot prove recording configuration.

```text
Continue the read-only source investigation of estimated drive paths,
map-based road lanes, position-on-map pose and foresight lane/ENU/MPP topics.
Do not modify files (including /memories/repo/ notes), run recordings, use
credentials, export raw proprietary code or guess absent interfaces. Report
full literal HEAD SHA and tracked dirty state. For each finding give exact
tracked path, symbol, lines and revision; mark source fact, interface intent,
inference or recording-unknown. Retain the distinction from deployed software.

Previous dossier reported master@465073bc, HPL covariance in ENU rotation-
vector state, GNSS fallback covariance in along/cross-track axes, camera yaw
bias without covariance adjustment, hashed ENU ids, held foresight restamping,
and EDP/RLMB sharing map+pose. Answer only the following unresolved items:

1. Can published PoseEstimateFrame status/sensor_input/reset_status uniquely
   distinguish the exact covariance-writing branch, including GNSS mean with
   HPL/empty covariance and convergence? Give a truth table from writer paths.
   If not, name the minimum actually published diagnostic required and its
   exact topic/root schema. Do not infer mode from covariance sparsity.
2. Establish global rotation-vector perturbation convention and the relation
   of its covariance to published yaw/bias-corrected mean. Do NOT implement a
   propagation or claim that entry 35 is exactly Euler-yaw variance.
3. Resolve foresight IndexRange.first/last endpoint inclusivity, validity/
   has_value flags, single-point/empty semantics and orientation/direction.
   Resolve LaneId-to-RLMB-id mapping, MPP correlation-id and map-counter
   lifetime/reset semantics, and how the ego lane is selected before using
   the path being evaluated. Identify genuinely ambiguous cases.
4. MPP roots have no timestamp. Which recorded inputs establish causal
   association with lane/ENU content, given restamping, origin changes,
   replay, and retained history? Do hashed ids ever repeat or get reused?
   Do not replace hash equality with numeric ordering or invent time offsets.
5. Locate ACTUAL recorded build/calibration/map-release/recorder provenance
   interfaces and names, plus space-morphing/debug diagnostics needed to
   establish deployed behavior. If these are not recorded, say unavailable;
   current defaults do not fill the gap. No broad further source survey.
6. The dossier mentions ASTAS ground truth in localization KPI tools. Resolve
   the exact producer/interface and what it measures: independent ego pose,
   surveyed lane geometry, or intended path? Can recording metadata identify
   it? Does it share map/localization inputs? Do not call independent ego pose
   alone lane ground truth. Also identify any existing validated lane-reference
   acquisition option; mark operational availability unknown.

Return a short evidence table, exact checkout identity and remaining unknowns.
Do not repeat the already established dependency trace or request inaccessible
recording dates/configuration as if they could be inferred from schema fields.
```

## 5. Metadata-only provenance follow-up: independent of section 4

Use Codex in PyCharm connected to **MPR and the registered local file**.
The completed recorded_metadata JSON stays immutable. The following task
reads metadata only; it does not repair ZstdError, run step 6 or decode new
topics. It is a local evidence task, not an MPR CLI.

```text
Read AGENTS/current_status and the 2026-10-04 evidence closure. Perform one
bounded metadata-only follow-up on batch03_aws_pilot001/pilot_001. Preserve
the old recorded_metadata.json byte-for-byte. Resolve the raw path only from
the pinned registration, never assume a basename or re-register/remerge it.
Recheck the three small-file lineage hashes, registered size/readability,
6 GiB MemAvailable/10 GiB disk and 4 GiB hard/soft process cap. No fresh raw
30 GB SHA, message iterator, chunk/data reads, payload decoding, decompression,
NonSeekingReader, fallback scan, credentials, archive, fit or deletion.

First locate and hash the existing report whose SHA is
8b797a3efc5866fc067cdd596610d4cc7ac3f6621e8bcea6d623fbafcb505c9a
at outputs/diagnostics/data/recorded_reference_metadata_v0198_batch03_pilot001/
recorded_metadata.json. If it is absent or changed, stop and report; do not
regenerate or overwrite it. Reuse its footer/group-size evidence after file
size/footer checks, not as fresh raw integrity proof. Read direct schema/channel
summary groups only, one bounded record at a time, <=128 MiB per record,
external 300 s timeout. Skip the 224 MB chunk-index group. If the available
API requires a whole summary/unbounded scan, stop and report the limitation.

Export a sanitized inventory of ALL 506 channels/root schemas, with channel/
schema IDs, encodings, descriptor hashes and bounded metadata key names.
Search that inventory for actual build/version/config/calibration/map-release/
recorder provenance, space-morphing grid, EDP/pose diagnostics and independently
measured GT/ASTAS streams; names are hints, not semantic proof. Include absent
from-summary versus not-inspected categories. Inventory all versions; never
guess names or infer ground truth from a name. If explicit summary metadata
contains producer identity, inspect only directly addressed bounded metadata
records after checking their extent/record limit; otherwise report unavailable.
Do not scan message payloads for provenance. Keep private identifiers/values,
paths, absolute epochs and descriptor bytes local; share only allowed keys,
availability, schema topology/hashes and interpretation limits.

Save one NEW report in the absent directory
outputs/diagnostics/data/recorded_reference_provenance_20261004_batch03_pilot001
(provenance_metadata.json). Do not touch a pre-existing directory or artifact.
Return the parser code/command used, limits, skipped groups, content hash and
tracked git status. Raw SHA and summary CRC remain unverified unless actually
verified by an explicitly bounded metadata-only method; label them honestly.
If a resource/parser/size/scope gate fails, stop and return the reason.
```

If acquisition/build/GT information cannot be found, keep it unknown. This
does not block a carefully scoped native availability audit. It does block
claiming physical covariance/frame/epoch semantics and accurate lane truth
without another evidence source. Do not spend successive rounds asking the
same unavailable question.

## 6. What happens after this closure

Return the focused source answer and provenance report. The native-audit
proposal can receive design feedback in parallel, but its unfrozen budgets
and publication schema do not yet permit executable-contract GO. Refine and
freeze those details, then obtain focused **contract** review before
implementation. The next implementation
reuses the bounded/CRC reader and inspects native fields, with synthetic tests
and exact-head implementation GO/CI before its private run. The deferred old
step 6 remains unnecessary unless its old question is deliberately resumed.

Then reconcile decoded availability. Choose and version the reference/target
and all-topology population, establish frame/epoch/lane selection, export
residuals/complete conditions/sequences, validate the archive, and only then
train both flow modes and compare classical models on matched new-data
evaluations. A changed reference must not be presented as a pure data effect.
Physical-session evidence is required for independent-drive validation.

With the end-of-October paper deadline, prioritize one defensible target and
evaluation over more speculative fusion or unlimited data. Independent lane
reference availability determines the accuracy claim; otherwise explicitly
scope the paper to map-relative path disagreement and its limitations. This
is a decision to make with the thesis supervisor, not an automatic target
change in this documentation patch.
