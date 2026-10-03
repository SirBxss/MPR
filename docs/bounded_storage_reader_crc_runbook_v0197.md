# MPR PR #29 — apply the CRC delta, then review, merge and audit

**2026-10-03 update:** PR #29 is merged at `fc6d5ff`. Do not reapply this delta.
The successor stopped at initial RAM preflight (exit 2, no new report), before
decoding; the shell may have left empty scratch. Source/reference evidence is
now prioritized. Use `reference_redesign_runbook_20261003.md` for the current
read-only checks, prospective study and deferred recovery; the old section 5
requires absent scratch and is not a recovery command for that empty directory.
These original sections are preserved as the dated implementation runbook.

Date: 2026-10-02. This is the new delta ZIP's complete `README.md`.
It applies **on your existing branch**, at exact reviewed head
`33f9542ffa835ded9d45c562528862506c1e91af`. Do not reapply the original
v0.19.7 ZIP, create another branch/PR, or run the private audit yet.

## 1. Review decision and correction

Claude gave GO with zero blockers at `33f9542`. I separately verified
Python 3.10/3.12 CI run `36997429154`: both logs contain 576 tests and two
existing skips, with MCAP extras installed. Your terminal counts agree.

R1 is a nonblocking priority-1 recommendation. We adopt it before the
one-shot audit: a stored chunk checksum can catch compressed corruption
that still produces valid Protobuf and changed confidence values. Readiness
now checks nonzero stored CRCs; historical batch02 defaults stay unchanged.
One compressed-bit synthetic mutation was complete with six sensor/condition
frames at the reviewed code and is inconclusive CRCValidationError with null
counts after this correction. Healthy readiness is unchanged.

CRC 0 means unavailable under MCAP. This is selected-chunk verification
where stored, not complete file/source integrity or proof of independent
reference information. The private native ZstdError cause remains unresolved.
No raw rewrite, re-registration, geometry/causality/resource rule change,
residual archive, training or deletion is introduced.

Read `docs/bounded_storage_reader_crc_review_v0197.md`. Original GO/CI is
verified, but this new delta needs new-head delta GO/CI before merge/audit.
That is the existing exact-head project review gate, not a claim that Claude
blocked the original PR. The private 30 GB file is unavailable here.

## 2. Apply and test on the existing feature branch

Download **`mpr_v0197_pr29_crc_delta.zip`** into **`~/Downloads/MPR`**.
Your Git repository is **`~/PycharmProjects/MPR`**. Run this whole block:

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_bundle="$mpr_downloads/mpr_v0197_pr29_crc_delta"
  cd "$mpr_repo"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -n "$(git status --porcelain)"; then
    echo 'Stop: preserve or commit your current changes before applying.' >&2
    exit 1
  fi
  git switch feature/v0.19.7-bounded-storage-reader
  git pull --ff-only origin feature/v0.19.7-bounded-storage-reader
  if test "$(git rev-parse HEAD)" != 33f9542ffa835ded9d45c562528862506c1e91af; then
    echo 'Stop: feature branch differs from the reviewed delta base. Return git log -5.' >&2
    exit 1
  fi
  if test ! -d "$mpr_bundle"; then
    test ! -e "$mpr_bundle"
    test -r "$mpr_downloads/mpr_v0197_pr29_crc_delta.zip"
    unzip -n "$mpr_downloads/mpr_v0197_pr29_crc_delta.zip" -d "$mpr_downloads"
  fi
  test -f "$mpr_bundle/README.md"
  test -f "$mpr_bundle/SHA256SUMS"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  set -- "$mpr_bundle"/0001-*.patch
  test "$#" -eq 1
  test -f "$1"
  git am "$1"

  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -c 'import sys; print(sys.executable); print(sys.version)'
  python -m pip install -e '.[test,mcap]'
  python -m compileall -q src tests
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
    python -m unittest discover -s tests -t .
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest \
    tests.io.test_indexed_storage_reader \
    tests.io.test_recording_ingestion \
    tests.io.test_recording_pair_feasibility \
    tests.workflows.test_recording_ingestion
  git diff --check
  test -z "$(git status --porcelain)"
  git log -3 --oneline
)
```

Expected with MCAP extras: **579 run, 577 pass, two existing opt-in skips**;
**56 focused pass**. The delta adds three tests to your 576-test suite.
Extra dependency skips mean the actual-container tests did not execute.
Use your configured interpreter if it is outside `.venv`; activate it first.
Keep individual commands on separate lines; a trailing backslash continues
only the shown `env` command. Do not escape the patch wildcard or `~`.

If anything stops, return the error plus `git status --short`, branch and
`git log -5 --oneline`. Do not reset, apply twice or continue after failures.

## 3. Push to the same PR #29

After tests pass:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git branch --show-current)" = feature/v0.19.7-bounded-storage-reader
  test -z "$(git status --porcelain)"
  git rev-parse HEAD
  git push origin feature/v0.19.7-bounded-storage-reader
)
```

PR #29 updates automatically. Keep its title:
**`fix: bound indexed MCAP storage-order payload retention`**.
Append this paragraph to its description, using your actual test counts:

```text
Address review R1 before the single private successor: only generic readiness
opts into nonzero stored chunk CRC validation; historical batch02 defaults
remain false. Add an enabled-policy flag without claiming complete CRC
coverage or source integrity. A one-bit ZSTD confidence mutation still decodes
at the reviewed code but now produces inconclusive CRCValidationError, chunk
context and null observations. Healthy readiness is unchanged and zero CRCs
remain unavailable under MCAP. No raw registration or scientific/resource
rules change. Validation: 579 tests (577 pass, 2 existing opt-in skips), 56
focused passes, compileall and whitespace checks. The prior head 33f9542 had
GO and passing Python 3.10/3.12 CI; the new head requires delta GO/CI before
merge. Post-merge instructions now repeat focused tests in the owner's runtime.
```

No new PR or branch cleanup is needed. Keep the local feature branch through
the source comparison after merge. Do not merge on the older head's GO/CI.

## 4. Claude delta review, then merge

Give Claude PR #29 and the new `git rev-parse HEAD`, then paste:

```text
Review only the R1 CRC delta in MPR PR #29 at its exact new pushed head,
against the previously reviewed 33f9542ffa835ded9d45c562528862506c1e91af.
Your original verdict was GO with zero blockers. Its Python 3.10/3.12 CI
was independently verified as passing in run 36997429154 (576 tests, 2 skips).
Do not reopen the confirmed FIFO/geometry questions without new evidence.

Read AGENTS.md/current_status, bounded_storage_reader_crc_review_v0197.md,
its complete runbook and output_contracts. Verify:
1. _iter_messages has validate_crcs=False by default; only readiness opts
   into True. Batch02 callers, archive/model/domain code and all geometry,
   pairing, feature, causality, sequence and resource rules are unchanged.
2. Nonzero stored chunk CRCs are checked before selected messages are yielded.
   A later valid-Protobuf compressed confidence mutation becomes inconclusive
   CRCValidationError with chunk context and every decoded field null; no
   prefix counts, exception text or private path leak, and spool is removed.
3. Healthy scientific output is identical. CRC 0 remains unavailable per MCAP,
   and no whole-file, CRC-coverage, source-authenticity or reference-independence
   claim is made. The new top-level flag records enabled policy only.
4. The existing predecessor hashes/index equality, registration, raw bytes,
   output/scratch paths and no-automatic-retry gate stay intact.
5. The same-PR delta instructions and post-merge 56-test environment check
   are correct. No raw deletion, private execution, exporter or fit is added.

Run compileall, the full suite with MCAP extras (579 tests, two existing
opt-in skips) and the 56 focused tests in the runbook. Verify Python 3.10/3.12
CI at the exact new head, or explicitly mark unverified. Return GO/NO-GO,
numbered blockers, exact head/tree and test/verification limits. Do not edit
code or execute private data. Scope is one unchanged registered pilot successor
after final-head delta GO/CI and merge; its private ZstdError cause remains
unresolved until the new report is reconciled.
```

Return the delta review and current PR head here. After delta GO and both
CI jobs pass at that head, **merge PR #29**. Then run sections 5–6 below once.
No prior step-5 attempt is required, and no extra preparation/registration.

## 5. After final-head GO/CI and merge: one successor

These commands are for **after** corrective review/CI and merge, not now.
Keep the local corrective branch until the source-tree comparison succeeds.
There is no path substitution and no new registration. The existing registration
contains the authoritative raw path (the moved pilot file remains there).

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  test -z "$(git status --porcelain)"
  mpr_reviewed_head="$(git rev-parse feature/v0.19.7-bounded-storage-reader)"
  git switch main
  git pull --ff-only origin main
  if ! git diff --quiet "$mpr_reviewed_head" HEAD -- src tests pyproject.toml; then
    echo 'Stop: main source/tests differ from the reviewed corrective branch.' >&2
    exit 1
  fi
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  python -m lane_residuals.cli.recording_ingestion audit --help
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest \
    tests.io.test_indexed_storage_reader \
    tests.io.test_recording_ingestion \
    tests.io.test_recording_pair_feasibility \
    tests.workflows.test_recording_ingestion
  git rev-parse HEAD

  mpr_registration="outputs/registrations/recording_ingestion_v0196_batch03_pilot001"
  mpr_previous="outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json"
  mpr_successor="outputs/diagnostics/data/recording_ingestion_v0197_batch03_pilot001"
  mpr_scratch="outputs/work/recording_ingestion_v0197"
  test -r "$mpr_registration/registration.json"
  test -r "$mpr_registration/source_specification.json"
  test -r "$mpr_previous"
  test ! -e "$mpr_successor"
  test ! -e "$mpr_scratch"
  printf '%s  %s\n' \
    041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44 \
    "$mpr_registration/registration.json" \
    c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1 \
    "$mpr_registration/source_specification.json" \
    55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7 \
    "$mpr_previous" | sha256sum -c -

  python - "$mpr_registration/registration.json" <<'PY'
from pathlib import Path
import json, sys
registration = json.loads(Path(sys.argv[1]).read_text())
assert registration['batch_id'] == 'batch03_aws_pilot001'
assert len(registration['recordings']) == 1
row = registration['recordings'][0]
assert row['recording_id'] == 'pilot_001'
assert row['raw_sha256'] == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78'
assert row['size_bytes'] == 29961313204
path = Path(row['canonical_path_private'])
assert path.is_file() and path.stat().st_size == row['size_bytes']
with path.open('rb') as stream:
    assert stream.read(1)
print('Preserved pilot identity and registered path verified; audit will rehash raw bytes once.')
PY

  free -h
  df -h .
  mkdir -p "$mpr_scratch"
  mpr_audit_status=0
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion audit \
      --registration-directory "$mpr_registration" \
      --preserved-readiness-report "$mpr_previous" \
      --scratch-directory "$mpr_scratch" \
      --output-directory "$mpr_successor" \
      --log-level INFO || mpr_audit_status=$?
  printf 'Successor audit exit code: %s\n' "$mpr_audit_status"
  case "$mpr_audit_status" in
    0|3) test -r "$mpr_successor/recording_readiness.json" ;;
    *) echo 'Stop: no completed successor report; return terminal output.' >&2; exit "$mpr_audit_status" ;;
  esac
)
```

The `printf` above writes three checksum pairs, not a command separator.
No raw-file `sha256sum` is added; audit already rehashes its registered bytes
through the same descriptor used for decoding. Leave raw bytes/path and both
preserved registration files unchanged. Hashing 30 GB takes a full read;
processing interleaved selected chunks can take considerably longer than the
small fixture tests. There is no measured private runtime estimate here.
Do not stop merely because logging is sparse. The CLI checks >=6 GiB memory
and >=10 GiB scratch; your last readings passed, but fresh load/free space can
change. Resource failures remain inconclusive, never permission to raise caps.

## 6. Package the report and return it

After section 5 produced a completed report (exit 0 or 3), run:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  mpr_result_dir="outputs/diagnostics/data/recording_ingestion_v0197_batch03_pilot001"
  mpr_result_zip="$HOME/Downloads/MPR/recording_ingestion_v0197_batch03_pilot001_results.zip"
  test -r "$mpr_result_dir/recording_readiness.json"
  test ! -e "$mpr_result_zip"
  test -d "$HOME/Downloads/MPR"
  (cd "$mpr_result_dir" && zip "$mpr_result_zip" recording_readiness.json)
  git rev-parse HEAD
  sha256sum "$mpr_result_zip"
  printf 'Result ZIP: %s\n' "$mpr_result_zip"
)
```

Send the ZIP, PR link, Claude review, final code SHA, ZIP SHA and terminal
output. Keep exact clock endpoints/private declarations internal to your
authorized research workflow; the JSON is not a public PR attachment.

| Result | Interpretation and next step |
|---|---|
| Exit 0, nonzero geometry and complete-condition sequence support | Review timing, topology, clock order and durations; then design separate generic extraction with exact readiness parity and archive validation |
| Exit 0, zero geometry or zero complete conditions | Completed negative/subset finding; diagnose documented failure populations without changing gates |
| Exit 3, ZSTD memory/window code | New decoder/resource evidence; inspect progress/memory snapshot before a separate engineering decision |
| Exit 3, corrupt/incomplete frame or generic decompression code | Inspect selected failing offset/phase and source-integrity evidence; generic category alone does not prove corruption |
| Exit 3, index/predecessor/raw drift | Preserve evidence; resolve exact lineage/integrity discrepancy before any further run |
| Exit 3, CRCValidationError | A stored selected-chunk checksum mismatched; decoded observations remain null. Review the offset/context before any further run |
| Exit 2 or external kill/no completed report | Return terminal output; no complete data result and no automatic rerun |

Do not automatically rerun, re-download, overwrite the old result or delete
raw files. We get new residuals only after a completed, reviewed readiness
result supports a separately reviewed numeric exporter. Real flow training
and old/new comparisons then require validated archives, sufficient causal
sequences and a physical-session split protocol. This pilot does not become
an untouched final-validation outing merely because it passes technically.

With the CRC delta, expected post-merge focused count is **56**. A completed
successor checks nonzero stored CRCs on chunks read for selected topics.
CRC 0 is unavailable; skipped chunks and full file/source integrity remain
outside this check. The policy flag does not claim complete CRC coverage.
An external kill may leave a private `mpr-ingestion-*` temporary spool under
scratch. Preserve terminal evidence and return it; nothing is deleted
automatically. Manual cleanup/retry planning must be scoped to that spool,
never the raw MCAP, registration or failed readiness output.
