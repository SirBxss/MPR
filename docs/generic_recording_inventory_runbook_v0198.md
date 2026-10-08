# Complete v0.19.8 generic inventory instructions

Date: 2026-10-08. Bundle: `mpr_v0198_generic_recording_inventory.zip`.
Read `generic_recording_inventory_v0198.md` and the post-merge evidence
checkpoint. PR #30 is already merged. This is a **new feature PR**, with one
numbered patch based on main `c8a757229c87d040d913ccdeed96364fd1d5e0bc`.

## 1. What to do now

Apply the patch, run tests, push the new branch, open the PR, obtain Claude
GO/zero blockers and passing exact-head Python 3.10/3.12 CI, then merge.
After merge run **only the inventory in section 5**, once, on the existing
registration. Do not repeat preparation/registration for the old pilot or
run old step 6. Inventory reads metadata after verifying raw bytes; it does
not decompress the 30 GB recording or prove usable residual pairs.

The pipeline currently has reusable prepare/register/inventory/readiness.
The readiness adapter still checks the historical EDP/RLMB/odometry target.
Generic numeric export/training/raw retirement are not completed by this
patch. Keeping these distinctions prevents metadata success from silently
changing the research target or treating missing decoding as zero pairs.

## 2. Apply from the actual repository and test

Save the exact ZIP basename in `$HOME/Downloads/MPR` or `$HOME/Downloads`.
The block explicitly enters the repository, verifies project/top-level/clean
state and exact patch base, verifies bundle hashes and post-apply tree, and
creates the feature branch. It does not depend on the initial terminal path.
Run each fenced block separately, without adding backslashes to every line.

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_name="mpr_v0198_generic_recording_inventory"
  mpr_zip="$mpr_downloads/$mpr_name.zip"
  if ! test -r "$mpr_zip"; then mpr_zip="$HOME/Downloads/$mpr_name.zip"; fi
  if ! test -r "$mpr_zip"; then
    echo 'Stop: save mpr_v0198_generic_recording_inventory.zip in Downloads/MPR or Downloads.' >&2
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
  git switch main
  git pull --ff-only origin main
  if test "$(git rev-parse HEAD)" != c8a757229c87d040d913ccdeed96364fd1d5e0bc; then
    echo 'Stop: main differs from the reviewed patch base; return git log -5.' >&2
    exit 1
  fi
  git switch -c feature/v0.19.8-generic-recording-inventory
  git apply --check "$mpr_patch"
  git am "$mpr_patch"
  test "$(git rev-parse 'HEAD^{tree}')" = "$(cat "$mpr_bundle/EXPECTED_TREE")"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  python -m compileall -q src tests
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
    python -m unittest discover -s tests -t .
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest tests.io.test_recording_inventory tests.workflows.test_recording_inventory
  git diff --check c8a757229c87d040d913ccdeed96364fd1d5e0bc HEAD
  test -z "$(git status --porcelain)"
  git log -2 --oneline
)
```

Expected with MCAP extras: **606 run, 604 pass, two existing opt-in skips**;
**27 new inventory tests pass**. Stop on test/application/tree failure. Do
not reset, skip a failed test, apply twice or push a branch that was never
created. Return the failing output and `git status --short` if needed.
Internal bundle hashes check consistency; the delivered ZIP hash and exact
base/tree check provide independent comparison points, not source authentication.

## 3. Push and open the new PR

After section 2 succeeds:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  test "$(git branch --show-current)" = feature/v0.19.8-generic-recording-inventory
  test -z "$(git status --porcelain)"
  git push -u origin feature/v0.19.8-generic-recording-inventory
  git rev-parse HEAD
)
```

Base: `main`. PR title:

`feat: add bounded registered MCAP inventory before payload decoding`

PR description:

```text
New recordings currently enter the fixed EDP/RLMB readiness adapter directly;
complete topic/schema inspection depended on a one-off private metadata script.
Add a reusable inventory subcommand on immutable recording registrations.
It verifies each raw file once, reads summary metadata through the same
open descriptor, streams chunk-index aggregates, and validates nonzero
summary CRCs without decoding message payloads or retaining the whole index.

Unknown encodings remain inventory evidence. Missing advertised counts are
null; resource/CRC/parser/file/registration failures discard affected prefix
inventories. Header/channel/file metadata values remain private/uninspected.
The old readiness adapter, residual arithmetic, SENSOR filtering, six features,
pinned archives and models are unchanged. This does not establish a new
reference or complete generic numeric export, training or raw retirement.

Validation: compileall; full suite 606 run/604 pass/two existing skips; 27 new
inventory tests, standard MCAP writer parity, CLI subprocess/no-decoder tests,
resource/checksum/drift/unknown-count checks, bounded-index benchmark, patch
apply/tree and README shell/guard checks. No private payload execution.
Focused Claude GO and exact-head Python 3.10/3.12 CI precede merge and one
post-merge metadata-only inventory on the registered pilot.
```

Use the actual passing local counts if they differ and investigate skips.
Do not add registration/specification, MCAPs, private paths or result ZIPs to
Git. PR #30 needs no reopening; retain its merged history. This branch is ready
to push/open after local checks; merge only after section 4 succeeds.

## 4. Self-contained Claude review prompt

```text
Review the new SirBxss/MPR PR for feature/v0.19.8-generic-recording-inventory
against main c8a757229c87d040d913ccdeed96364fd1d5e0bc. Inspect the current exact
PR head, run tests, and return GO/NO-GO, blocker count and nonblocking findings.
Read AGENTS.md/current_status, generic_recording_inventory_v0198.md,
its runbook, output_contracts and reference_evidence_checkpoint_20261008.md.

Scope is target-independent registered-file metadata inventory. It is not
the unfrozen native-reference audit, old readiness retry or numeric extraction.
Check MCAP specification fidelity: bounded record/string/map lengths, footer/
DataEnd marker/summary extents, exact nonzero summary CRC range, unavailable
CRC zero, grouped records, optional/empty offset groups, extension tails,
schema-zero channels, multiple channel/schema versions, unavailable versus
zero counts, advertised statistics reconciliation and unknown encodings.
Check no whole chunk-index list, no message/metadata-value/attachment decoding,
process/memory/disk/summary/text/time budgets and explicit unsupported cases.
Check no private payload/producer values in outputs or exception text in logs.

Verify one raw SHA read and reuse of its open descriptor; immutable input
hashes/path state and before-publication checks, drift invalidation, fresh
outputs including dangling symlinks, incomplete null inventories, 0/3/2 exits,
post-hash resource failure and independent per-file results without outing roles.
Check lazy CLI routing and unchanged original readiness/default scientific
behavior/import boundaries. Run full/focused tests and real-writer parity.
Exercise README commands with a synthetic repository/home; check exact base,
post-apply tree, expected branch, path with spaces, hash guards and report ZIP.
Safety guards must survive PYTHONOPTIMIZE=1/2 and -O/-OO; do not use assertions
as executable recovery guards. Do not run private data, merge, publish or push.

Report exact head/tree, Python/dependency versions, tests/skips, CI access and
any claimed verification limit. Inventory completion must never be described
as usable residual pairs, independent ground truth, acquisition UTC or safe
raw deletion. No reference replacement, target/topology/feature change, real
fit, old step 6 or native-audit execution is included. The next owner action
is one post-merge inventory only if review and exact-head CI pass.
```

Send the review and PR link here. If NO-GO, correct the specific finding on
this same branch and obtain new-head review/CI. If GO/zero blockers and both
CI jobs pass at that reviewed head, merge using GitHub. Do not close the branch
before merge; deleting the remote branch after merge is optional.

## 5. One metadata-only inventory after merge

This uses the **existing registered path**, so the file's basename/location
needs no substitution. Do not move/rename/rewrite it after registration.
All guards preserve the old original three files and report. The old
readiness-successor/step-6 command is not executed. Scratch here is a new
inventory-specific directory; it need not reuse old readiness scratch.

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
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest tests.io.test_recording_inventory tests.workflows.test_recording_inventory
  printf '%s  %s\n' \
    041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44 \
    outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json \
    c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1 \
    outputs/registrations/recording_ingestion_v0196_batch03_pilot001/source_specification.json \
    55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7 \
    outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json \
    | sha256sum -c -
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import json
from pathlib import Path
from lane_residuals.io.recording_inventory import INVENTORY_REVISION

def require(condition, message):
    if not condition:
        raise SystemExit('Stop: ' + message)

require(INVENTORY_REVISION == 'v0.19.8-registered-mcap-inventory-2026-10-08-a1', 'inventory revision mismatch')
path = Path('outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json')
registration = json.loads(path.read_bytes())
require(registration.get('batch_id') == 'batch03_aws_pilot001', 'unexpected batch identity')
rows = registration.get('recordings')
require(isinstance(rows, list) and len(rows) == 1, 'expected one technical recording')
row = rows[0]
require(row.get('recording_id') == 'pilot_001', 'unexpected recording identity')
require(row.get('raw_sha256') == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78', 'raw declaration changed')
require(row.get('size_bytes') == 29961313204, 'registered size changed')
name = row.get('canonical_path_private')
require(isinstance(name, str) and bool(name), 'registered path missing')
raw = Path(name)
require(raw.is_file() and raw.stat().st_size == row['size_bytes'], 'registered raw path or size changed')
with raw.open('rb') as stream:
    require(bool(stream.read(1)), 'raw file unreadable')
output = Path('outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001')
scratch = Path('outputs/scratch/recording_inventory_v0198_batch03_pilot001')
require(not output.exists() and not output.is_symlink(), 'inventory output already exists')
require(not scratch.exists() and not scratch.is_symlink(), 'inventory scratch already exists; preserve it')
print('Existing pilot identity/path checked; inventory will freshly rehash raw bytes once.')
PY
  mkdir -p outputs/scratch/recording_inventory_v0198_batch03_pilot001
  free -h
  df -h outputs/scratch/recording_inventory_v0198_batch03_pilot001
  set +e
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion inventory \
    --registration-directory outputs/registrations/recording_ingestion_v0196_batch03_pilot001 \
    --scratch-directory outputs/scratch/recording_inventory_v0198_batch03_pilot001 \
    --output-directory outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001 \
    --log-level INFO
  mpr_exit=$?
  set -e
  printf 'Inventory exit code: %s\n' "$mpr_exit"
  case "$mpr_exit" in
    0|3) test -f outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001/recording_inventory.json ;;
    *) echo 'Stop: no completed inventory; return terminal output. Do not retry or lower limits.' >&2; exit "$mpr_exit" ;;
  esac
  printf '%s  %s\n' \
    041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44 \
    outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json \
    c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1 \
    outputs/registrations/recording_ingestion_v0196_batch03_pilot001/source_specification.json \
    55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7 \
    outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json \
    | sha256sum -c -
)
```

Exit 3 is a completed inconclusive report: continue only to section 6 to send
it for review. It is not zero pairs and does not authorize another scan.
Exit 2 has no completed report; stop and send terminal output. Empty scratch
may remain. A second failed RAM preflight is still only a resource finding.
If all three old hashes pass, those preserved files were not replaced.

## 6. Package the new report for review

This packages just the new metadata report and a sanitized receipt. It does
not include raw bytes, registration, private specification or old report.
It accepts complete or inconclusive inventory status and checks the expected
revision/lineage/flags before creating the receipt/ZIP. Existing receipt or ZIP
is preserved and causes a stop. No existing file is overwritten.

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

def require(condition, message):
    if not condition:
        raise SystemExit('Stop: ' + message)

folder = Path('outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001')
source = folder / 'recording_inventory.json'
require(source.is_file(), 'no completed inventory report')
raw = source.read_bytes()
report = json.loads(raw)
require(report.get('contract_revision') == 'v0.19.8-registered-mcap-inventory-2026-10-08-a1', 'report revision mismatch')
require(report.get('purpose') == 'development_only_recording_inventory', 'unexpected report purpose')
require(report.get('status') in ('complete', 'inconclusive'), 'unexpected completion status')
require(report.get('batch_id') == 'batch03_aws_pilot001', 'batch changed')
require(report.get('registration_sha256') == '041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44', 'registration lineage changed')
require(report.get('source_specification_sha256') == 'c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1', 'source lineage changed')
require(report.get('technical_recording_count') == 1 and report.get('independent_outing_count') is None, 'recording/session count changed')
rows = report.get('recordings')
require(isinstance(rows, list) and len(rows) == 1, 'expected one recording result')
row = rows[0]
require(row.get('recording_id') == 'pilot_001' and row.get('size_bytes') == 29961313204, 'pilot identity changed')
require(row.get('raw_sha256') == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78', 'raw identity changed')
require(row.get('status') == report['status'], 'per-file completion status mismatch')
if report['status'] == 'complete':
    require(row.get('failure_code') is None and isinstance(row.get('inventory'), dict), 'completed inventory missing')
else:
    require(isinstance(row.get('failure_code'), str) and bool(row['failure_code']) and row.get('inventory') is None, 'inconclusive prefix or failure state')
for key in ('message_payloads_decoded', 'geometry_readiness_assessed', 'residual_profiles_constructed',
            'numeric_conditions_exported', 'reference_independence_proven', 'model_fitted',
            'roles_assigned', 'raw_cache_deletion_authorized'):
    require(report.get(key) is False, 'unexpected scientific action flag')
receipt = folder / 'inventory_run_receipt.json'
zip_path = Path.home() / 'Downloads' / 'MPR' / 'recording_inventory_v0198_batch03_pilot001_results.zip'
require(not receipt.exists() and not receipt.is_symlink(), 'receipt already exists')
require(not zip_path.exists() and not zip_path.is_symlink(), 'result ZIP already exists')
require(source.read_bytes() == raw, 'report changed during packaging')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
receipt_value = {'git_commit': commit, 'report_sha256': hashlib.sha256(raw).hexdigest(),
                 'inventory_status': report['status'], 'purpose': report['purpose']}
with receipt.open('x') as stream:
    json.dump(receipt_value, stream, indent=2, sort_keys=True)
    stream.write('\n')
zip_path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('recording_inventory.json', raw)
    archive.write(receipt, arcname=receipt.name)
print('Commit:', commit)
print('Result ZIP:', zip_path)
print('ZIP SHA-256:', hashlib.sha256(zip_path.read_bytes()).hexdigest())
PY
)
```

Send this ZIP and the section-5 terminal output here. Read it in this order:
execution status/failure; raw/small-file lineage; summary CRC coverage;
all-topic/schema inventory; advertised counts and chunk limits; uninspected
metadata flags. Reconcile old 506/448 inventory and selected-topic counts if
this full inventory completes. Never compare an inconclusive null with zero.

## 7. Future recordings and remaining work

For a new existing local MCAP, use these templates only when the new batch is
ready for development inspection. Change the one absolute file path and both
new identifiers; choose fresh paths for its specification/registration/output.
Do not use the old pilot IDs or overwrite any prior batch. Add actual private
physical-session ID **with evidence** before registration if known; otherwise
leave null. Never infer acquisition times or independent drives from filenames,
export UUIDs or the number of merged chunks. Preparation does not know the
number of input chunks unless you supply that truthful optional argument.

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  mpr_file='/absolute/path/to/the/new/actual/file.mcap'
  test -r "$mpr_file"
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion prepare \
    --mcap-file "$mpr_file" --batch-id future_batch_001 --recording-id recording_001 \
    --output-specification config/private/future_batch_001.private.json
)
```

Review truthful provenance in that private specification, then:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion register \
    --specification config/private/future_batch_001.private.json \
    --output-directory outputs/registrations/future_batch_001
  test ! -e outputs/scratch/future_batch_001_inventory
  test ! -L outputs/scratch/future_batch_001_inventory
  mkdir -p outputs/scratch/future_batch_001_inventory
  set +e
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion inventory \
    --registration-directory outputs/registrations/future_batch_001 \
    --scratch-directory outputs/scratch/future_batch_001_inventory \
    --output-directory outputs/diagnostics/data/future_batch_001_inventory
  mpr_exit=$?
  set -e
  printf 'Inventory exit code: %s\n' "$mpr_exit"
  case "$mpr_exit" in
    0|3) test -f outputs/diagnostics/data/future_batch_001_inventory/recording_inventory.json ;;
    *) echo 'Stop and return terminal output; no completed inventory.' >&2; exit "$mpr_exit" ;;
  esac
)
```

For several explicitly listed files, review one strict specification containing
1–64 records; registrations are not a global cross-batch duplicate registry.
A declared physical session remains evidence to verify, not automatic role
assignment. Preserve original AWS object/export/merge information privately.
No AWS API or generic Data Portal query is implemented here.

Then review inventory and select a compatible decoder/readiness contract.
Complete decoding must precede target-dependent extraction. The unresolved
native reference proposal remains a separate reviewed step; all-topology EDP,
RLMB output-to-input disagreement and temporal stability are different research
targets. Generic archive export must preserve diagnostic parity and immutable
lineage. Validate archives and physical-session evaluation/causal sequences
before Gaussian/AR/AIOHMM/conditional and unconditional flow fitting. Raw-cache
retirement follows only verified durable outputs and a tested retrieval route.
Do not download another huge batch to evade the unresolved pilot failure.
