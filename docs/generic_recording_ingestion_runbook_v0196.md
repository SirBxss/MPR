# MPR v0.19.6 — apply, review and inspect the new merged recording

This runbook is also the patch ZIP's `README.md`. Follow the sections in order.
The code is based on merged PR #27, main
`d03f7769c05ee751224aec3870b740c13a575edc`. No new private result is included.
The project package version remains 0.18.1; v0.19.6 names this separate contract.

## 1. What this implements

The reusable workflow is:

1. **Prepare** a private specification using your actual downloaded file path.
2. **Register** its size/SHA-256 and preserve source declarations.
3. **Audit** indexed MCAP structure, existing EDP/RLMB H100 geometry, strict
   causal feature availability and recording-local sequence support.
4. Return the small JSON report for reconciliation and the next implementation.

It supports 1–64 explicitly listed files; `prepare` makes the first one-file
specification. It reuses the reviewed schema, geometry, timestamp pairing,
50 ms speed and <=200 ms sequence rules. It does not export residual vectors,
fit models, assign outing roles, call AWS or delete raw files. Those later stages
need the new readiness evidence and separate reviewed contracts.

One file merged from 180 chunks counts as **one technical recording**. Do not
count 180 outings. The screenshot's export identifier does not by itself prove
a physical drive, and its `06/10/2026` label has ambiguous date/clock semantics.
Unknown evidence stays null. This pilot is explicitly development-only.

Read `docs/generic_recording_ingestion_v0196.md` for the full scientific and
resource contract. Old batch01/batch02 outputs and commands stay frozen.

## 2. Apply the patch in the actual repository

Download `mpr_v0196_generic_recording_ingestion.zip` into **`~/Downloads/MPR`**.
That directory stores downloads; your Git repository is
**`~/PycharmProjects/MPR`**. Do not run `git am` or `pip install -e` inside the
download directory. Do not apply an older unmerged patch from another task.

Run this complete block in a terminal. It stops on a wrong path, dirty worktree,
unexpected base, extraction failure, patch failure or failed tests. If a guard
stops, preserve the error and stop there; do not delete/reset your worktree.

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_bundle="$mpr_downloads/mpr_v0196_generic_recording_ingestion"

  cd "$mpr_repo"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -n "$(git status --porcelain)"; then
    echo 'Stop: preserve or commit your existing changes before applying.' >&2
    exit 1
  fi
  git switch main
  git pull --ff-only origin main
  if test "$(git rev-parse HEAD)" != d03f7769c05ee751224aec3870b740c13a575edc; then
    echo 'Stop: main differs from the reviewed patch base; return git log -5.' >&2
    exit 1
  fi

  test -f "$mpr_downloads/mpr_v0196_generic_recording_ingestion.zip"
  test ! -e "$mpr_bundle"
  unzip "$mpr_downloads/mpr_v0196_generic_recording_ingestion.zip" -d "$mpr_downloads"
  test -f "$mpr_bundle/README.md"
  git switch -c feature/v0.19.6-generic-recording-ingestion
  git am "$mpr_bundle"/0001-*.patch

  if test -f .venv/bin/activate; then
    . .venv/bin/activate
  fi
  python -c 'import sys; print(sys.executable); print(sys.version)'
  python -m pip install -e '.[test,mcap]'
  python -m compileall -q src tests
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
    python -m unittest discover -s tests -t .
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest \
    tests.domain.test_recording_ingestion \
    tests.io.test_recording_ingestion \
    tests.workflows.test_recording_ingestion
  git diff --check
  git status --short
  git log -2 --oneline
)
```

Use your configured project interpreter if it lives somewhere other than
`.venv`; activate it before the block. The printed executable identifies what
actually ran. Do not continue after package/test errors. The baseline before
this patch is 526 tests. The patch adds 33 meaningful tests: expected **559 run,
557 pass, two existing opt-in skips** with MCAP extras; all **33** new focused
tests pass. Missing MCAP extras cause additional skips and do not exercise the
real compressed-Protobuf reader tests. Keep MCAP extras installed before review
and before the private audit.

The shell expands `0001-*.patch` after the directory is quoted. Do not escape
the `*`, prepend a backslash to `~`, or join separate commands with trailing
backslashes. A backslash here is used only to continue one `env` command.

## 3. Push and open a new PR

After the tests pass:

```bash
cd "$HOME/PycharmProjects/MPR"
git status --short
git rev-parse HEAD
git push -u origin feature/v0.19.6-generic-recording-ingestion
```

Open a PR against `main`. PR #27 is already merged; use a **new PR**.

**Title:** `feat: add generic development MCAP registration and readiness`

**Description:**

```text
The reviewed batch02 workflows are pinned to four recordings and cannot accept
the newly downloaded merged MCAP. Add a separate development-only
prepare/register/audit workflow for explicitly declared local recordings.
Preserve exact source declarations and raw identities, validate indexed MCAP
structure, and report existing EDP/RLMB H100 geometry, strict six-input
availability and original-storage-order sequence support.

Reuse the reviewed converters, ungated mutual-nearest pairing, H100 grid and
1 m anchor, 50 ms causal-speed checks and 200 ms sequence breaks. Hashing and
decoding share an open file descriptor; changed/incomplete streams publish
inconclusive observations rather than prefix counts. The new odometry resource
budget is 1,000,000; historical batch02 remains 300,000. No numeric residual or
condition export, AWS API, file stitching, outing roles, model fit or deletion.

Validation: compilation, full suite (559 run / 557 pass / 2 existing opt-in
skips with MCAP extras), 33 focused new tests and git diff --check. Includes real
compressed Protobuf MCAP and isolated CLI integration, old geometry/diagnostic
parity, causal rejection, missing/reordered clocks, metadata/raw tampering,
summary/decode completeness and resource/prepublication failure checks.

No private new-recording result exists yet. Exact-head independent scope/code
GO and Python 3.10/3.12 CI precede its one development pilot audit. Published
batch01/batch02 artifacts and synthetic-only flow gates remain unchanged.
```

Replace the validation counts if your actual run differs and explain why.
Require both GitHub CI jobs to pass on the current PR head. Do not merge on an
older head's GO after applying review corrections.

## 4. Give Claude this independent review prompt

Claude is the independent reviewer. This Work session has not run Claude; no
review GO for this new patch is being claimed. Provide the new PR URL and
current `git rev-parse HEAD`, then paste:

```text
Review MPR's new v0.19.6 generic development recording intake/readiness PR at
the exact current pushed head, against main d03f7769c05ee751224aec3870b740c13a575edc.
First read AGENTS.md, docs/current_status.md,
docs/generic_recording_ingestion_v0196.md,
docs/generic_recording_ingestion_runbook_v0196.md, docs/output_contracts.md,
and the reviewed v0.19.2 extraction contract. No private MCAP result exists yet.

Give GO/NO-GO with numbered blockers, exact head/tree, executed test counts,
dependency/CI verification limits and a concise scope decision. Do not declare
the new MCAP usable or authorize fitting from synthetic tests.

Check in particular:
1. Generic input declarations are development-only and keep unknown physical
   session/UTC/retrieval evidence null. 180 merged chunks/export UUID/file counts
   must never become independent outings or training/final roles.
2. Existing EDP schema-v1/v2 bindings, RLMB conversion, H100/anchor rules,
   complete ungated mutual-nearest pairing, signed-target definition, six-input
   arithmetic and recorded-source/log causality remain intact. RLMB stays a
   pseudo-reference; no independence or physical-clock proof is claimed.
3. The shared no-residual scanner cannot bypass the old residual wrapper's
   mandatory exact preserved-count/diagnostic gate. Successful batch02 outputs,
   pinned consumers and frozen import behavior remain unchanged.
4. Original storage indices and gaps determine support. No geometry-prefiltered
   pairing, future-speed fallback, imputation, silent sorting or file stitching.
5. Registration preserves exact source bytes and stable raw identities; same
   descriptor is used for raw hashing and decode. Check replacement/mutation,
   metadata drift, raw duplicate handling and final publication checks.
6. Indexed summary/chunk/topic limits and decoded count reconciliation remain
   fail-closed. New 1,000,000 odometry cap is resource-only; old 300,000 remains.
   Incomplete/resource-limited data produce null counts, not a negative finding.
   No coordinate/numeric-feature/residual payload is written in the report.
7. CLI limit restoration, static error codes, fresh outputs, spool cleanup,
   actual compressed-MCAP tests and the README's absolute directory guards.
8. No models, AWS interface invention, final-data promotion or automatic deletion.

Run compileall, the complete suite with MCAP extras and the 33 focused new tests.
Inspect regressions for old extraction/geometry behavior. Verify Python 3.10/3.12
CI on the same pushed head if available; otherwise explicitly mark unverified.
The proposed private execution is one readiness-only development pilot after
GO/CI. Return a Markdown review; do not modify code or execute private data.
```

Return Claude's review and the PR link here. If review and CI pass on the final
head, merge the PR, then run the private steps below from updated main. If a
blocker requires code changes, keep the PR open for correction and delta review.

## 5. Prepare the new file and its private declaration

**After exact-head implementation/scope GO and CI**, update the actual repo:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test -z "$(git status --porcelain)"
  git switch main
  git pull --ff-only origin main
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  python -m lane_residuals.cli.recording_ingestion --help
)
```

Recommended cache directory:

```bash
cd "$HOME/PycharmProjects/MPR"
mkdir -p data/raw/new_independent_outings/batch03/pilot_001
```

If convenient, move your **existing** MCAP into this directory with your file
manager. Do not copy 30 GB unnecessarily, merge it again, move it into batch02,
or rename/rewrite it after registration. You can register its existing absolute
download path instead. The workflow never assumes its basename.

In the next block, replace `/absolute/path/to/your/actual/file.mcap` with the
existing MCAP's full path. This is the only required path substitution. It
checks readability before producing anything. Preparation records your stated
180 input chunks and the reported export settings. The source/export identifier
starts as null; add the actual identifier privately if you have it. No identifier
is automatically recorded as a physical-session ID.

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  mpr_input='/absolute/path/to/your/actual/file.mcap'
  test -f "$mpr_input"
  test -r "$mpr_input"
  mkdir -p config/private
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion prepare \
    --mcap-file "$mpr_input" \
    --batch-id batch03_aws_pilot001 \
    --recording-id pilot_001 \
    --merged-input-mcap-count 180 \
    --export-settings 'Download Helper: MCAP; merge enabled; selected relative range 0 to 3584 seconds; date format and timezone unverified; owner reports 180 merged input MCAPs.' \
    --output-specification config/private/recording_ingestion_v0196_batch03_pilot001.private.json
)
```

If the screenshot refers to a different download, omit/change the optional
`--export-settings` argument before running. The source identifier can be
supplied with `--source-recording-id` or by editing the draft's
`source_recording_id_private`; keep it in private configuration. The code and
tracked runbook contain no private screenshot-specific identifier.

Open the generated JSON in PyCharm **before registering**. You may add an
actual persistent source locator/export manifest and confirmed source/session
evidence if already available. Otherwise leave null. Keep credentials and
expiring signed URLs out of the declaration. A physical-session ID needs
evidence that explicitly identifies a physical drive; a generic export UUID
is insufficient. Do not guess UTC endpoints. Any later metadata correction
needs a new preserved declaration/registration; do not edit registered files.

PyCharm Codex can run these local commands, check paths and capture outputs.
It does not need to redesign the extractor or implement a second pipeline.

## 6. Register bytes, then run the one readiness audit

Both destination directories below must be absent. Hashing the 30 GB file
takes a full read at registration and another at audit; initial verification
can take minutes. This is intentional identity checking, not loading it into
RAM. Keep the laptop powered and avoid changing the file during processing.

Register:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  test -f config/private/recording_ingestion_v0196_batch03_pilot001.private.json
  test ! -e outputs/registrations/recording_ingestion_v0196_batch03_pilot001
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion register \
    --specification config/private/recording_ingestion_v0196_batch03_pilot001.private.json \
    --output-directory outputs/registrations/recording_ingestion_v0196_batch03_pilot001 \
    --log-level INFO
)
```

This produces exactly the registration JSON and preserved source-specification
JSON. It does not decode geometry. Do not edit either file or add a note/log
inside this two-file directory.

Create scratch and check resources:

```bash
cd "$HOME/PycharmProjects/MPR"
mkdir -p outputs/work/recording_ingestion_v0196
free -h
df -h outputs/work/recording_ingestion_v0196
```

The audit needs >=6 GiB `MemAvailable`, >=10 GiB free local scratch and supports
a <=4 GiB process address space, 8 GiB spool, 128 MiB chunks, <=100,000 EDP/RLMB
messages each and <=1,000,000 odometry messages. Close memory-heavy processes
if needed. Do not raise caps or cut data to make a run succeed.

Run once into the new directory:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  test ! -e outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion audit \
    --registration-directory outputs/registrations/recording_ingestion_v0196_batch03_pilot001 \
    --scratch-directory outputs/work/recording_ingestion_v0196 \
    --output-directory outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001 \
    --log-level INFO
)
```

Exit **0** means a complete technical audit, not model readiness. Exit **3**
means an inconclusive report was preserved; return it without retrying. Exit
**2** means an input/resource/dependency failure prevented a completed report.
Return the terminal error. Never overwrite/remove a failed result to rerun.

If there is no indexed summary, or a giant uncompressed chunk exceeds the cap,
that is a reader/export execution obstacle rather than proof of unusable lane
geometry. Return the evidence; the next correction/re-export must be explicit.
The command does not silently scan all topics or crop a recording.

## 7. Return the small output ZIP

Run this even if the audit returned 3, provided its report exists:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json
  mkdir -p "$HOME/Downloads/MPR"
  mpr_return="$HOME/Downloads/MPR/recording_ingestion_v0196_batch03_pilot001_results.zip"
  test ! -e "$mpr_return"
  zip -j "$mpr_return" \
    outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json
  git rev-parse HEAD
  sha256sum "$mpr_return"
)
```

Send that ZIP, the new PR link and the printed code SHA here. No 30 GB upload,
private source specification, AWS credentials or temporary geometry spool is
needed. Keep registration/source evidence, raw MCAP and the report locally.
The returned report omits local paths, literal source locators/session IDs,
coordinates, confidence/speed values and residual profiles.

## 8. How we decide the next implementation

- **Incomplete execution:** inspect index/count/cap/decode/file-change evidence;
  correct the demonstrated obstacle without declaring a negative geometry result.
- **Complete with zero SENSOR H100 geometry:** inspect topology, reference and
  coverage/anchor failures. Do not shorten H100 or pool map-labeled EDP rows.
- **Geometry but missing strict inputs:** inspect exact causal failure codes and
  clock/schema evidence. Geometric residuals can still exist; temporal fitting
  requires sufficient contiguous complete inputs. No future-speed fallback.
- **Geometry and useful complete sequences:** implement the generic development
  residual archive with exact readiness parity, identity mapping and validation.
  Then review a matched-row old/new data comparison and physical-outing split
  protocol. Real flow fitting is not part of this readiness PR.

Future batches can use these same commands with new specifications and output
IDs when they meet the fixed supported schema/resource contract. Schema or
clock changes still need targeted investigation; a generic pipeline cannot
prove an arbitrary new topic equivalent or independent. The final protocol
needs prospectively evidence-backed physical outings, cross-batch duplicate
and overlap checks, enough longer complete sequences, and protected final drives.

**Keep the raw file for now.** Safe cache deletion comes after verified durable
residual/condition archives, audit/provenance records and a tested original-source
retrieval route. Re-running a merge may change raw bytes even when the recording
content is similar. AWS access alone does not verify exact reconstruction.
This version intentionally leaves `raw_cache_deletion_authorized: false`.

Do not close/delete the new branch while its review is pending. PR #27's branch
may be removed after confirming it is merged, if you want; no cleanup is needed
for this implementation. Merge the new PR only after final-head GO and both CI
jobs pass. Any result-driven code correction belongs in the open PR with delta
review, or in a separate reviewed follow-up after merge.
