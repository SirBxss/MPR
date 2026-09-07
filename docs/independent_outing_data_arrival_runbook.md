# v0.17 initial data-arrival runbook

Use this runbook only for the first prospectively declared v0.17 acquisition
batch. It operationalizes the reviewed intake contract; it does not authorize
residual inspection, model fitting, sampling, planner execution, or final
evaluation. If any new-outing outcome has already been inspected, stop and
record that outing as development-only before continuing.

Checkpoint note (2026-09-07): the first 86-file batch has completed this
v0.17.0 procedure and its failed-availability output is immutable. Do not repeat
that run or overwrite it. The encountered BMW EDP schema transition is recorded
in `docs/bmw_edp_schema_evidence.md`. The exact v0.17.1 compatibility contract
in `docs/independent_outing_schema_v2_amendment.md` received focused contract
`GO`, and its bounded implementation is complete. Do not execute that
implementation on candidate data until its separate focused implementation
review returns `GO` and CI passes.

## 1. Preserve the prospective boundary

Collect genuinely separate physical outings, not merely separate MCAP chunks.
Target more than the minimum when practical: the lock requires at least 7
technically eligible new outings, every eligible outing needs at least 120.0
seconds of summed non-overlapping usable duration and at least 500 eligible
H100 frames, and a failed outing cannot be replaced after inspecting its
outcomes. Several MCAP chunks may represent one outing, but they must remain
one declared independent unit.

Before looking at residuals, conditions, model scores, planner values, or
figures, place the closed batch under one dedicated root such as:

```text
data/raw/new_independent_outings/
```

Keep that new-outing root separate from the accepted legacy root. A common
parent is already sufficient for a clean layout; do not flatten old and new
MCAPs into one directory or move the accepted legacy bytes merely to simplify
a command. Use one stable subdirectory per declared physical outing beneath
the recursive new-outing root, for example:

```text
data/raw/
├── mcap/                                  # accepted legacy lineage
└── new_independent_outings/               # one recursive v0.17 input root
    └── candidate_session_YYYY-MM-DD/      # all chunks from one outing
```

Later consumers must join accepted legacy and new data through their manifests,
content hashes, and cohort lock rather than by treating one flat directory as
a scientific cohort. Directory layout, filename numbering, and MCAP count do
not define independent outings.

The intake discovers `.mcap` files recursively. Every basename must be unique,
including across subdirectories. Confirm the working revision and inspect only
the file inventory:

```bash
cd ~/PycharmProjects/MPR

git switch main
git pull --ff-only
git status --short
git rev-parse HEAD

find "data/raw/new_independent_outings" \
  -type f -iname '*.mcap' -printf '%f\n' | LC_ALL=C sort

find "data/raw/new_independent_outings" \
  -type f -iname '*.mcap' -printf '%f\n' | LC_ALL=C sort | uniq -d
```

The second `find` pipeline must print nothing. Do not rename, edit, copy into,
or remove files after the manifest is closed. If a raw byte changes, the lock
lineage changes.

## 2. Create the private initial manifest

Copy the reviewed example into the ignored private-config directory:

```bash
mkdir -p config/private

cp config/examples/independent_outings_v017.private.example.json \
  config/private/independent_outings_v017.private.json
```

Edit only the private copy. Replace every placeholder and list every discovered
MCAP basename exactly once. Group chunks by their true physical session. Use a
timezone-aware acquisition time and record the actual operational basis for
the separate-session declaration. For the initial lock, both
`prior_successful_lock_sha256` and `superseding_contract_amendment_id` must be
`null`. The batch/prospective and per-outing attestation fields must remain
literally `true` only when their statements are true.

Validate the JSON and record its exact byte hash without printing outcome data:

```bash
python -m json.tool \
  config/private/independent_outings_v017.private.json >/dev/null

sha256sum config/private/independent_outings_v017.private.json
```

Do not modify the manifest after this point. A correction requires a new
manifest, a new versioned output directory, and preservation of the failed or
superseded evidence under the reviewed contract.

## 3. Execute the initial intake exactly once

The output target must not already exist. The initial command deliberately has
no `--prior-successful-lock` argument.

<!-- first-lock-command:start -->
```bash
cd ~/PycharmProjects/MPR

PYTHONPATH=src python -m lane_residuals.cli.independent_outing_intake \
  "data/raw/new_independent_outings" \
  --acquisition-manifest \
  "config/private/independent_outings_v017.private.json" \
  --output-directory \
  "outputs/diagnostics/data/independent_outing_intake_v017"

intake_status=$?
echo "intake exit status: ${intake_status}"
```
<!-- first-lock-command:end -->

Interpret the result before doing anything else:

- Exit status `0`: the availability gate passed, roles were locked, and the
  final-outing embargo is active. Continue to independent reconciliation below.
- Exit status `3`: all four audit files were written, but fewer than seven new
  outings were eligible, so no role was assigned. Preserve the complete output
  unchanged. Acquire more outcome-blind data under a new manifest and new
  versioned output; do not inspect outcomes or overwrite this audit.
- Exit status `2`: a usage, manifest, exact-coverage, lineage, dependency, or
  output-target check failed before a valid output was created. Correct only
  the clerical or technical cause while remaining outcome-blind. If an output
  directory exists unexpectedly, stop and retain it for investigation.
- Any other exit status: treat it as an internal failure. Stop, preserve the
  terminal log and inputs, and request code review.

## 4. Independently reconcile the bundle

A valid intake directory contains exactly these files:

```text
independent_outing_recordings.csv
independent_outings.csv
independent_outing_lock.json
independent_outing_intake_summary.json
```

Run the standalone verifier. It imports no `lane_residuals` code, does not
decode MCAP messages, reads only embargo-permitted hashes, identities, roles,
fixed counts and failure codes, and writes no file:

```bash
cd ~/PycharmProjects/MPR

python scripts/inspection/verify_v017_intake_bundle.py \
  "data/raw/new_independent_outings" \
  --acquisition-manifest \
  "config/private/independent_outings_v017.private.json" \
  --intake-output-directory \
  "outputs/diagnostics/data/independent_outing_intake_v017"
```

Continue only when it exits `0` and prints both:

```text
"verification_status": "passed"
"files_written": 0
```

It independently rehashes the manifest, every recursively discovered raw
MCAP, and the three self-hashable outputs. It recomputes outing fingerprints,
opaque IDs, the availability gate, split scores, ranks, roles, CSV aggregates,
attestations, and the embargo state. Any mismatch exits `2`; do not edit an
output to make it pass.

For a final file-set and hash record, run:

```bash
find "outputs/diagnostics/data/independent_outing_intake_v017" \
  -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort

sha256sum \
  outputs/diagnostics/data/independent_outing_intake_v017/*
```

## 5. Send the review evidence without opening outcomes

Package the manifest and four intake outputs only. Do not include raw MCAPs,
residuals, condition arrays, model artifacts, planner artifacts, or figures:

```bash
cd ~/PycharmProjects/MPR

zip -j \
  ~/Downloads/MPR/independent_outing_intake_v017_review.zip \
  config/private/independent_outings_v017.private.json \
  outputs/diagnostics/data/independent_outing_intake_v017/independent_outing_recordings.csv \
  outputs/diagnostics/data/independent_outing_intake_v017/independent_outings.csv \
  outputs/diagnostics/data/independent_outing_intake_v017/independent_outing_lock.json \
  outputs/diagnostics/data/independent_outing_intake_v017/independent_outing_intake_summary.json

git rev-parse HEAD
```

Send Codex the ZIP, the complete intake and verifier terminal output, and the
reported Git commit. Codex must reconcile the initial lock first. After that
check passes, send the same evidence and code revision to Claude for an
independent lock review. Do not open any final-test numeric evidence while
either review is pending.

The private manifest, raw data, and generated intake outputs stay outside Git.
Do not push them and do not open a PR for them. A successful, independently
accepted lock is recorded only by adding the exact accepted
`independent_outing_lock.json` SHA-256 to `docs/current_status.md` in a later
documentation commit.

## 6. Re-execute batch01 under v0.17.1 only after implementation GO

This section applies only to the already closed 86-file batch01. It does not
replace or retroactively edit Sections 1–5. The prospective manifest bytes,
raw MCAP bytes, and original v0.17.0 four-file output must remain unchanged.
Do not set `superseding_contract_amendment_id` and do not supply
`--prior-successful-lock`: the original audit failed before producing a
successful lock.

Only after the exact implementation commit receives focused independent `GO`
and both CI jobs pass, run into a new empty output directory while supplying
the preserved v0.17.0 failed audit:

```bash
cd ~/PycharmProjects/MPR

PYTHONPATH=src python -m lane_residuals.cli.independent_outing_intake \
  "data/raw/new_independent_outings" \
  --acquisition-manifest \
  "config/private/independent_outings_v017.private.json" \
  --amended-from-failed-intake-directory \
  "outputs/diagnostics/data/independent_outing_intake_v017" \
  --output-directory \
  "outputs/locks/independent_outing_intake_v0171_batch01"

intake_status=$?
echo "intake exit status: ${intake_status}"
```

The expected exit status is `3`, not `0`: the unchanged manifest declares only
one physical outing, so it cannot meet the seven-new-outing lock threshold.
All four amended output files must nevertheless exist, status must be
`insufficient_independent_outings`, and no cohort role may be assigned.

Reconcile the amended output with the independent standard-library verifier,
passing the same preserved failed-audit directory:

```bash
python scripts/inspection/verify_v017_intake_bundle.py \
  "data/raw/new_independent_outings" \
  --acquisition-manifest \
  "config/private/independent_outings_v017.private.json" \
  --amended-from-failed-intake-directory \
  "outputs/diagnostics/data/independent_outing_intake_v017" \
  --intake-output-directory \
  "outputs/locks/independent_outing_intake_v0171_batch01" \
  2>&1 | tee \
  ~/Downloads/MPR/independent_outing_intake_v0171_batch01_verifier.json

verifier_status=${PIPESTATUS[0]}
echo "verifier exit status: ${verifier_status}"
```

The verifier must exit `0` and report `verification_status: passed`,
`contract_revision: v0.17.1-reviewed-2026-09-07-schema-v2-a1`,
`schema_compatibility_amendment_id: v0.17.1-edp-schema-v2-2026-09-07`, and
`files_written: 0`. It independently rehashes the prior four files, current
manifest, and raw corpus. For batch01, review must reject the amended result if
`schema_compatibility_amendment.amended_from_failed_audit` is null, even if all
other checks pass.

Package only the four amended outputs and the saved complete verifier output
for review. Do not include raw MCAPs or any outcome values:

```bash
cd ~/PycharmProjects/MPR

zip -j \
  ~/Downloads/MPR/independent_outing_intake_v0171_batch01_review.zip \
  outputs/locks/independent_outing_intake_v0171_batch01/independent_outing_recordings.csv \
  outputs/locks/independent_outing_intake_v0171_batch01/independent_outings.csv \
  outputs/locks/independent_outing_intake_v0171_batch01/independent_outing_lock.json \
  outputs/locks/independent_outing_intake_v0171_batch01/independent_outing_intake_summary.json \
  ~/Downloads/MPR/independent_outing_intake_v0171_batch01_verifier.json

git rev-parse HEAD
```

Send Codex that ZIP, the complete intake and verifier terminal output, and the
exact Git commit. Codex must reconcile it first; then send the same evidence to
Claude for the independent real-output review.

## 7. Stop after the accepted lock

Even a reviewed exit-`0` lock authorizes only the next predeclaration. It does
not authorize a final model comparison. Codex must draft the exact training,
development, untouched-final, metric, aggregation, uncertainty, and decision
contract; Claude must review it; only then may a separate implementation begin.
