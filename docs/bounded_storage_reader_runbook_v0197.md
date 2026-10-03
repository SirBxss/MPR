# MPR v0.19.7 — correct the reader, review, then inspect the same pilot

Date: 2026-10-02. This is also the patch ZIP's complete `README.md`.
Base main: **`8d55edf5f4c2ae7d30ce2533f702138319d63270`**, merged PR #28.
The package version stays 0.18.1; v0.19.7 identifies this engineering amendment.

**Post-review update:** the original patch is applied and PR #29 is open at
`33f9542`, with GO and passing Python 3.10/3.12 CI. R1's small readiness CRC
delta is prepared before the audit; use `bounded_storage_reader_crc_runbook_v0197.md`
to apply it to the same PR. Sections 2–4 below record the completed original
delivery, not commands to repeat. The private successor still needs final-head
delta GO/CI and merge.

## 1. Decision and current evidence

The first audit failed with **`ZstdError`**, exit 3. It did not find zero pairs:
decoded geometry, input and sequence fields are all **null**. The readable
index advertises 36,032 EDP, 36,032 RLMB and 109,191 odometry messages, with
2,109,683-byte maximum advertised chunks. Existing resource gates passed.

The old storage-order reader retains selected payloads across all selected
chunks before yielding. This confirmed engineering defect is corrected by
one-chunk iteration. The private failure may still involve an invalid or
incomplete compressed frame; the old report cannot distinguish it from a
native resource failure. A valid synthetic 512 MiB-payload fixture fails at
zero yields with the baseline under a 256 MiB cap and completes 128 with
the correction under the same cap. This is not a private-file rerun.

Keep the original MCAP, registration and failed output unchanged. Do not
repeat prepare/register, merge chunks again, raise limits, change topics,
sort clocks or delete any raw/output file. PR #28 is already merged; this
correction belongs in a **new PR**. No training or residual export follows yet.

Read `docs/recording_ingestion_batch03_v0196_result.md` and
`docs/bounded_storage_reader_v0197.md`. The existing project instruction in
`AGENTS.md` requires exact-head implementation review before private MCAP
inspection; the current checkpoint states: "Exact-head corrective GO and
normal CI must precede the single predecessor-gated successor in a fresh
directory." Therefore apply/test/push/review comes before the private command.
The implementation agent has not run Claude or accessed the private raw file.

## 2. Apply and test in the actual repository

Download **`mpr_v0197_bounded_storage_reader.zip`** to **`~/Downloads/MPR`**.
Your repository is **`~/PycharmProjects/MPR`**. The download directory is not
a Git repository. If your file manager already extracted the named bundle,
the block validates and reuses it; otherwise it extracts the ZIP once.

Run this entire block. Do not add trailing backslashes between independent
commands, escape the wildcard, or continue after a failed guard.

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_bundle="$mpr_downloads/mpr_v0197_bounded_storage_reader"

  cd "$mpr_repo"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -n "$(git status --porcelain)"; then
    echo 'Stop: preserve or commit your current changes before applying.' >&2
    exit 1
  fi
  git switch main
  git pull --ff-only origin main
  if test "$(git rev-parse HEAD)" != 8d55edf5f4c2ae7d30ce2533f702138319d63270; then
    echo 'Stop: main differs from the patch base. Return git log -5.' >&2
    exit 1
  fi
  if git show-ref --verify --quiet refs/heads/feature/v0.19.7-bounded-storage-reader; then
    echo 'Stop: the corrective branch already exists. Preserve git status and git log -5.' >&2
    exit 1
  fi

  if test ! -d "$mpr_bundle"; then
    test ! -e "$mpr_bundle"
    test -r "$mpr_downloads/mpr_v0197_bounded_storage_reader.zip"
    unzip -n "$mpr_downloads/mpr_v0197_bounded_storage_reader.zip" -d "$mpr_downloads"
  fi
  test -f "$mpr_bundle/README.md"
  test -f "$mpr_bundle/SHA256SUMS"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  set -- "$mpr_bundle"/0001-*.patch
  test "$#" -eq 1
  test -f "$1"
  git switch -c feature/v0.19.7-bounded-storage-reader
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
  git log -2 --oneline
)
```

Expected with MCAP extras: **576 run, 574 pass, two existing opt-in skips**;
**53 focused pass**. There are 17 new tests. Extra dependency skips mean the
actual compressed-reader tests did not run; resolve installation first.
The memory regression uses synthetic temporary files, never your raw data.
Use your configured interpreter if it is outside `.venv`; activate it before
the block. The printed executable identifies the interpreter actually used.

If a command stops, return its output, `git status --short`, current branch
and `git log -5 --oneline` from the actual repository. Do not reset, delete
branches, apply the patch twice or push a branch that was not created.

## 3. Push and open a new PR

After all tests pass:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git branch --show-current)" = feature/v0.19.7-bounded-storage-reader
  test -z "$(git status --porcelain)"
  git rev-parse HEAD
  git push -u origin feature/v0.19.7-bounded-storage-reader
)
```

Open a **new PR against `main`**. Do not reopen PR #28 or close/delete its
branch as a prerequisite. Optional cleanup of already merged branches can
wait; retain this corrective local branch through the post-merge source check.

**Title:** `fix: bound indexed MCAP storage-order payload retention`

**Description:**

```text
The first registered batch03 readiness audit stopped with ZstdError and null
decoded observations. Upstream SeekingReader's FIFO storage-order iterator
expands all selected chunks and retains their raw payloads before its first
yield; log_time_order=False does not provide bounded reading.

Replace that iterator with physical-offset, one-chunk traversal using the
existing summary and Protobuf decoder interfaces. Validate index/header/frame
and inner-record bounds; keep unchanged topic/chunk/process/spool limits and
actual decoded-count reconciliation. Add fixed ZSTD failure categories and
payload-free chunk/progress/memory context. A failed prefix remains null.

Add an explicit single-recording preserved-readiness gate for the same old
ZstdError raw/registration/specification lineage, exact fresh index metadata
and predecessor-byte checks. Reuse the original registration. Audit adds the
reader identity and compression-library versions. No geometry, schema binding,
H100/anchor, time pairing, causality, six-input or sequence rule changes.
No residual archive, fit, role, AWS operation or raw deletion is introduced.

Validation: compileall; full suite with MCAP extras (576 run, 574 pass, two
existing opt-in skips); 53 focused passes; whitespace check. Seventeen new
tests cover real NONE/ZSTD/LZ4, unknown frame size, physical order, corrupt
prefix invalidation, bounds, failure privacy, predecessor/index drift and an
actual 512 MiB-under-256 MiB subprocess. The exact baseline fails at zero
yields; the correction yields all 128. Six actual compressed synthetic fixtures
have byte-identical scientific readiness/extraction outputs. Focused import-
path tests also pass on MCAP 1.5.0; embedded workers use installed 1.4.0.

The private ZstdError's allocation-versus-frame cause is still unresolved.
Exact-head independent corrective GO and Python 3.10/3.12 CI must precede one
fresh predecessor-gated pilot successor after merge. Published outputs remain
immutable and both flow modes remain synthetic-only.
```

Use actual validation counts if yours differ and explain skips/failures.
Do not merge before independent GO and both CI jobs at the **current head**.

## 4. Claude corrective review prompt

Provide the new PR URL and `git rev-parse HEAD`, then paste:

```text
Review MPR v0.19.7 at the exact current pushed PR head, against merged main
8d55edf5f4c2ae7d30ce2533f702138319d63270. Read AGENTS.md, current_status,
recording_ingestion_batch03_v0196_result.md, bounded_storage_reader_v0197.md,
the full v0.19.7 runbook and output_contracts.md. The original private report
is inconclusive ZstdError; decoded counts/support are null, not zero.

Give GO/NO-GO with numbered blockers, exact head/tree, actual test/dependency
counts and CI verification limits. Do not modify code or execute private data.
Check upstream MCAP 1.4.0/1.5.0 FIFO behavior independently, not just comments.

Check especially:
1. One selected chunk is retained at a time; no hidden upstream message queue,
   list materialization or NonSeekingReader scan fallback. Test first-yield
   decompression and actual 512 MiB payload under a 256 MiB AS cap.
2. Physical byte-offset/inner-record order preserves timestamps, schema,
   channels, sequence and payload bytes. Reversed summary indexes must not
   sort log/source clocks or manufacture sequence continuity.
3. Outer/inner bounds, index/header/frame sizes, selected channel/schema
   identity, all existing resource limits and decoded-count reconciliation
   remain fail-closed. Valid unknown ZSTD frame content size still works.
   Verify NONE/ZSTD/LZ4 and that unrequested invalid Protobuf is ignored.
4. Chunk failure context contains static scalar container/progress/memory
   observations only. No native exception text, paths, payloads or timestamps.
   A corrupt later frame discards all prefix readiness and removes the spool.
5. The optional predecessor flag accepts only the exact one-recording old
   ZstdError lineage with null observations, verifies fresh index equality
   before decoding and exact predecessor bytes before publication. Existing
   two-file registration and raw identity stay immutable; no re-registration.
6. No scientific arithmetic/gate changes: EDP/RLMB pseudo-reference, supported
   bindings, H100, origin projection, 1 m anchor/no extrapolation, complete
   mutual-nearest pairing without a delta gate, strict 50 ms causal speed,
   six inputs, file-local <=200 ms breaks, old batch02 parity/archive pins.
7. Default frozen intake imports remain optional; only the shared new storage
   decoder changes. No numeric archive, fit, role, deletion, AWS or EM/LTSB.
8. Runbook paths, base/clean/extraction/test guards, successor hash checks and
   exit handling are executable. No automatic retry or overwritten output.
9. The confirmed queue bug is distinguished from the unresolved cause of the
   private native ZstdError. Synthetic completion is not usable-pair proof.

Run compileall and the full suite with MCAP extras: expected 576 tests with
two opt-in skips. Run the 53-test focused selection in the runbook. Verify
Python 3.10/3.12 CI at the same pushed head, or label it unverified.
The proposed execution is one readiness-only successor on the same registered
pilot, after final-head GO/CI and merge. Return the Markdown review.
```

Return the review, new PR URL and test output here. If corrections change the
head, repeat delta review/CI at that head. The original PR #28 GO does not
approve this new implementation.

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
