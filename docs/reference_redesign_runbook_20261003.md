# MPR: close the preflight incident and investigate the reference

Date: 2026-10-03. This is the delivery ZIP's complete README.
Patch scope is **documentation only** on merged main
`fc6d5ff72c5812d43367897cc92416fd870e2686`. No new topic decoder, topology
filter change, reference fusion, residual archive or fit is included.

## 1. What happened and what to do now

Your 56 focused tests passed. PR #29 is merged with the CRC correction.
Available RAM was 4.5 GiB, below the existing 6 GiB requirement; disk free
was 53 GiB, above 10 GiB. Exit 2 occurred **before raw hashing or payload
processing**, so there is no successor report to ZIP. The scratch directory
may exist empty because the shell created it before calling the CLI.

The original v0.19.6 ZstdError is still unresolved. Preserve its report,
registration and raw file. We defer its successor while acquiring evidence
for the new reference direction. Do not rerun the original registration or
silently remove the EDP source filter. The road-team report is recorded as
owner-reported evidence, not a verified producer configuration or new target.

Save your work and close unused large applications (for example Lichtblick
with an open recording, notebook kernels, extra IDEs or browser windows).
This is a suggestion, not a claim about which process consumes your memory.
Run this **read-only** block from any terminal. It does not run an audit:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test -f AGENTS.md
  free -h
  df -h .
  ps -u "$(id -u)" -o pid,comm,rss --sort=-rss | head -16
  python - <<'PY'
from pathlib import Path
import shutil
successor = Path('outputs/diagnostics/data/recording_ingestion_v0197_batch03_pilot001')
scratch = Path('outputs/work/recording_ingestion_v0197')
if successor.exists() or successor.is_symlink():
    raise SystemExit('Stop: successor output exists; inspect it before any further run.')
if scratch.is_symlink() or (scratch.exists() and not scratch.is_dir()):
    raise SystemExit('Stop: scratch is a symlink or not a directory.')
if scratch.exists() and next(scratch.iterdir(), None) is not None:
    raise SystemExit('Stop: scratch is nonempty; preserve and inspect it.')
print('Successor absent; scratch absent or empty. Nothing was deleted.')
memory = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
              if line.startswith('MemAvailable:'))
disk = shutil.disk_usage(scratch if scratch.exists() else Path('.')).free
print(f'Available memory: {memory/1024**3:.2f} GiB; disk free: {disk/1024**3:.2f} GiB')
if memory < 6*1024**3 or disk < 10*1024**3:
    raise SystemExit('Resource gate still fails. Close unused applications and measure again; no audit started.')
print('Resource snapshot passes; the audit remains deferred for the source study.')
PY
)
```

`rss` is KiB per process, useful for locating consumers, not a total physical
usage estimate; shared pages can be counted repeatedly. Do not add buff/cache
to MemAvailable, purge cache, reset swap, lower the gate or kill processes
blindly. Aim for some headroom above 6 GiB (8--10 GiB is convenient). Host
resources can change after this snapshot. No immediate audit is needed.

## 2. Apply the documentation handoff

Download `mpr_reference_redesign_20261003.zip` to **`~/Downloads/MPR`**.
Your repository is **`~/PycharmProjects/MPR`**, not the download directory.
Run the complete block:

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_bundle="$mpr_downloads/mpr_reference_redesign_20261003"
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
  if test "$(git rev-parse HEAD)" != fc6d5ff72c5812d43367897cc92416fd870e2686; then
    echo 'Stop: main differs from the reviewed patch base; return git log -5.' >&2
    exit 1
  fi
  git switch -c docs/reference-redesign-2026-10-03
  if test ! -d "$mpr_bundle"; then
    test ! -e "$mpr_bundle"
    test -r "$mpr_downloads/mpr_reference_redesign_20261003.zip"
    unzip -n "$mpr_downloads/mpr_reference_redesign_20261003.zip" -d "$mpr_downloads"
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
  git diff --check
  git diff --exit-code fc6d5ff72c5812d43367897cc92416fd870e2686 HEAD -- src tests pyproject.toml
  test -z "$(git status --porcelain)"
  git log -3 --oneline
)
```

Expected with MCAP extras: **579 tests run, 577 pass, two existing opt-in
skips**, unchanged. This documents the investigation, not a new implementation
revision. If a block stops, return the error, branch, status and `git log -5`;
do not reset, apply twice or continue past failures. No PR #29 patch is reapplied.

## 3. Push and open the documentation PR

After checks pass:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git branch --show-current)" = docs/reference-redesign-2026-10-03
  test -z "$(git status --porcelain)"
  git rev-parse HEAD
  git push -u origin docs/reference-redesign-2026-10-03
)
```

Open a **new documentation PR** to main. PR #29 is already merged; keep its
history intact. No old branch cleanup is required for these instructions.

Title:

```text
docs: record pilot memory stop and prospective EDP reference study
```

Description:

```text
Record PR #29's merged identity and the pilot successor's exit-2 memory
preflight stop: 4.5 GiB available versus the existing 6 GiB requirement,
before hashing/decoding and without a completed report. Preserve the old
ZstdError evidence and document empty-scratch recovery without a retry now.

Record the owner-reported map-preferred EDP behavior and prioritize a separate
all-topology/reference feasibility study using position-on-map pose covariance
and foresight candidates. Distinguish observed counts, source traces, verbal
information and unverified hypotheses. Specify schema/frame/time/provenance
questions, shared-error limits, mathematical illustrations and read-only BMW
source/recorded-metadata prompts. No filter, reference, target, feature, model,
resource, numeric output or raw-file change is implemented.

Validation: compileall and the unchanged full suite with MCAP extras
(579 run, 577 pass, 2 existing opt-in skips), whitespace and Bash syntax checks;
source/tests/dependency diff against fc6d5ff is empty.
```

Claude prompt for the documentation PR:

```text
Review this documentation-only MPR PR at its exact pushed head against
fc6d5ff72c5812d43367897cc92416fd870e2686. Read AGENTS/current_status, the
2026-10-03 preflight incident, reference investigation and complete runbook.
Verify src/tests/pyproject and prior artifacts are unchanged. Check the RAM
guard ordering against merged code, exit 2 versus no completed report, and
the scratch directory left by the old shell block. Recovery must accept only
absent/empty nonsymlink scratch, absent successor output and unchanged inputs;
it is deferred, with no immediate private run or gate reduction.

Check the evidence classes: verbal ~90% is not a new-file measurement;
7,743/376/7,367 are old anchored geometry counts, not ready training rows.
All-topology EDP is prospective, not a retroactive rewrite of SENSOR-only
results/admission. No topic name, 6x6 covariance or extra foresight fields prove
geometry, accuracy or independence. Check cross-covariance and illustrative
pose propagation, frame/epoch/anchor caveats, no covariance-derived correction
or feature leakage, and no unsupported claim of a new decoder or residual.

Check commands/paths/branch/base and privacy boundaries. Return GO/NO-GO,
numbered blockers and exact head/tree. Verify CI or mark it unverified. Do not
edit source, inspect private payloads or execute the deferred audit. Avoid
asking for unavailable old batch02 session evidence.
```

After documentation GO and CI pass, merge this new PR. The read-only evidence
gathering below can proceed while it is reviewed. It changes no MPR source.

## 4. Acquire the BMW source evidence

Use Codex in PyCharm or Copilot **with the BMW producer/interface checkout
available**, not only the MPR project. The MPR checkout alone does not contain
these BMW definitions. Paste the following as a read-only task:

```text
Perform a read-only source investigation for MPR's prospective estimate/reference
study. Do not modify code, use credentials, export raw source/recordings, run
private payload scans or infer interfaces from names. Record literal checkout
HEAD SHA and dirty state. Tie each claim to complete tracked path, symbol,
line range and exact revision; inspect Git history where behavior changed.
If the BMW checkout is unavailable, state that and stop the source phase.

Topics of interest:
/adp/estimated_drive_paths
/adp/road_lane_map_based
/adp/position_on_map_pose_estimate
/adp/foresight_lane_data_opb
Other actually declared /adp/foresight topics: discover exact names, do not guess.

The road team reportedly says EDP prefers map topology whenever a usable map
is available, about 90% in their experience. Verify selection/fallback/source
enum semantics, producer config and whether this applies to the recording
generation. Do not treat the percentage or current checkout as recording proof.

1. Resolve topic aliases/bindings to exact root schemas and transitive types.
   Record field numbers/types/cardinality/presence/enums and documented validity
   semantics, plus historical schema/producer revisions applicable to recordings.
2. Pose covariance: locate the writer, not just a proto comment. Establish
   matrix layout/order/units, covariance vs information, pose mean and origin,
   coordinate basis, rotation/error-state convention, frame-transform direction,
   conditioning, scale/tuning, excluded errors, invalid/zero/sentinel semantics,
   reset behavior, calibration evidence and any lane-choice ambiguity.
3. Foresight: establish OPB meaning from symbols/docs; actual centreline/boundary/
   polynomial/point geometry vs attributes; ego-lane versus route/MPP; graph
   connectivity/ranges; longitudinal coordinate/origin; horizon, interpolation,
   lane-change/merge/split and route ambiguity; valid/held/predicted states.
4. Trace producer dependencies and data uses for each topic: HD-map version,
   localization/map matching, route/MPP, odometry, cameras, EDP, caches/feedback.
   Does RLMB already use the same pose or foresight geometry? Does LANE_MAP EDP
   use the same map/pose? Which inputs are distinct observations, not copies?
   Identify covariance/cross-covariance interfaces if present; don't invent them.
5. Establish frames/origins/axes/units, including ego/rear axle and native s=0.
   Establish source/measurement/validity/prediction/publish epochs, ages, output
   update rate, timestamp rewriting, relevant configuration and availability.
   Identical header/log stamps are not physical synchronization evidence.
6. Identify exactly what these topics can/cannot support: frame registration,
   reference uncertainty, path reconstruction, route association or independent
   validation. State unknowns explicitly. Do not call map-based data ground truth
   or combine correlated streams as independent. Never choose a reference by
   closeness to EDP or apply a pose transform twice.

Return a concise technical dossier with an evidence table, dependency graph,
schema/coordinate/time/covariance facts and unresolved questions. Separate
source facts, documented intent, inferred behavior and unavailable recording
configuration. Keep proprietary code and internal URLs in the authorized BMW
workspace; provide only policy-approved summaries for external review.
```

Return the technical summary here through the authorized research workflow.
Do not send source archives, credentials or the 30 GB raw file.

## 5. Recorded schema metadata, then the next implementation

After resources are adequate, a separate **metadata-only** IDE task may establish
recorded topic presence/descriptor identities without the old payload audit:

```text
Read-only recorded-metadata task in the local MPR project. Do not modify source,
registration/raw bytes, create a new registration, decode payload messages,
construct paths/residuals or invoke any prior audit. First read AGENTS and the
2026-10-03 reference runbook. Resolve the single preserved pilot path from
outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json;
do not guess its basename. Verify the pinned registration/specification/old-report
hashes from the existing CRC runbook and registered size. Record this task's
metadata-only scope: it does not freshly verify the full 30 GB raw hash.

Use only seekable MCAP footer/summary metadata if available, with a capped
process and bounded record reads. Require fresh >=6 GiB MemAvailable and >=10 GiB
scratch free; retain the existing 4 GiB process cap and 128 MiB record-size bound.
The existing code does not declare a total-summary byte/count cap: read footer
offsets first and report summary extent without loading an unbounded region;
if a bounded metadata read cannot be justified, stop and return the extent for
a separately reviewed adapter. Do not invent an existing summary-size guard.
Do not use iterator fallbacks, iter_messages/iter_decoded_messages or
NonSeekingReader, and do not decompress data chunks. If there is no usable
summary, a limit is exceeded or the API cannot perform this task safely, stop
with the missing evidence rather than scanning the recording.

Inventory exact channels/schema names, encodings, descriptor SHA-256 identities,
and advertised message counts for EDP, RLMB, position_on_map_pose_estimate,
foresight_lane_data_opb and actually present /adp/foresight topics. Inspect the
embedded FileDescriptorSet only for message-owned field/type/enum topology and
covariance/geometry structure. Count each channel/schema version separately;
absence from the summary is not a decoded-absence or geometry-validity finding.
No raw field values, coordinates, epochs or full descriptor bytes in a public
report. Put any allowed local metadata report in a fresh versioned private
directory and report its content hash. Do not claim schema alone proves frame,
timestamp, covariance calibration or producer independence.
```

These are local evidence tasks, not a newly supported MPR CLI or authorization
to improvise a payload scan. Do not call the existing `path_probe` with new
topic names: it is EDP-specific and does not establish the new schemas.

Return source evidence and recorded schema summaries before numeric work.
Then we can implement the smallest bounded structural adapter, review it,
inspect actual valid geometry/time/covariance support, and decide the reference.
Only after that decision comes the versioned all-topology numeric exporter,
archive validation, predeclared old/new comparisons and real model training.
Keep untouched future physical sessions for final evaluation. No acquisition
of unlimited new bytes is needed before the reference evidence is understood.

## 6. Deferred recovery of the unchanged old readiness question

**Do not run this section now.** It is retained for continuity if the old
EDP/RLMB readiness question is deliberately resumed after the source study.
This measures the existing SENSOR support and counts other sources; it does
not implement the proposed reference or all-topology exporter. The code is
already merged/reviewed. A documented initial memory-only stop leaves no new
decoded result; this permits one deliberate processing attempt after resources
recover, not automatic repeated retries after payload failures/reports.

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test -f AGENTS.md
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  test -z "$(git status --porcelain)"
  git switch main
  git pull --ff-only origin main
  if ! git diff --quiet fc6d5ff72c5812d43367897cc92416fd870e2686 HEAD -- src tests pyproject.toml; then
    echo 'Stop: implementation differs from merged PR #29; review before the private run.' >&2
    exit 1
  fi
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
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
  printf '%s  %s\n' \
    041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44 \
    "$mpr_registration/registration.json" \
    c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1 \
    "$mpr_registration/source_specification.json" \
    55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7 \
    "$mpr_previous" | sha256sum -c -
  python - "$mpr_registration/registration.json" "$mpr_successor" "$mpr_scratch" <<'PY'
from pathlib import Path
import json, shutil, sys
registration = json.loads(Path(sys.argv[1]).read_text())
assert registration['batch_id'] == 'batch03_aws_pilot001'
assert len(registration['recordings']) == 1
row = registration['recordings'][0]
assert row['recording_id'] == 'pilot_001'
assert row['raw_sha256'] == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78'
assert row['size_bytes'] == 29961313204
raw = Path(row['canonical_path_private'])
assert raw.is_file() and raw.stat().st_size == row['size_bytes']
with raw.open('rb') as stream:
    assert stream.read(1)
output, scratch = map(Path, sys.argv[2:])
assert not output.exists() and not output.is_symlink(), 'successor output already exists'
assert not scratch.is_symlink(), 'scratch is a symlink'
if scratch.exists():
    assert scratch.is_dir() and next(scratch.iterdir(), None) is None, 'scratch is not empty'
else:
    scratch.mkdir(parents=True)
available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                 if line.startswith('MemAvailable:'))
assert available >= 6*1024**3, 'available memory below 6 GiB; no audit started'
assert shutil.disk_usage(scratch).free >= 10*1024**3, 'scratch free below 10 GiB'
print('Preserved identity and empty scratch checked; audit will rehash raw bytes once.')
PY
  free -h
  df -h "$mpr_scratch"
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
    *) echo 'Stop: no completed successor report; preserve and return terminal output.' >&2; exit "$mpr_audit_status" ;;
  esac
)
```

This reuses empty scratch; it deletes nothing and does not touch the old
report. Any later failure/report requires reconciliation. If a completed
report is produced, package it using section 6 of the existing
`bounded_storage_reader_crc_runbook_v0197.md`, and return its JSON ZIP, code
SHA, ZIP SHA and terminal output. Do not ZIP an absent output or describe exit
2 as a data finding. This section does not need the old feature branch to
remain locally available: it compares source against the verified merge.
