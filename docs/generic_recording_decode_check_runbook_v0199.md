# MPR v0.19.9 — complete selected-stream decoding instructions

## Accepted pilot execution: 2026-10-09

PR #32 is merged as `85cd9d6`. The owner's Step 5 completed with exit 0;
the Step 6 ZIP was returned and reconciled. Read
`recording_decode_check_batch03_v0199_result.md` and
`generic_pipeline_continuation_20261009.md` for the current stopping point.
The application/PR/pilot commands below record an already completed workflow.
Do not rerun them for pilot001, reuse its output/scratch paths, or use a repeat
decode check as the next geometry command. No new private command is authorized
by the documentation-only result closure.

This bundle continues **merged PR #31** at
`05e0c71f93f8133204f6b5577f5ca69662f647fc`.
The pilot's inventory is complete; payload decoding remains unknown.
Two patches include the accepted inventory result closure and the new generic
`decode-check`. Existing scientific readers/rules/archives/models are unchanged.

Repository: **`$HOME/PycharmProjects/MPR`**.
Downloads: **`$HOME/Downloads/MPR`**.
ZIP: **`mpr_v0199_selected_stream_decode_check.zip`**.
New branch: **`feature/v0.19.9-selected-stream-decode-check`**.
The existing private registration supplies the raw MCAP path. **No raw path
substitution, move, copy, rename, remerge or re-registration is needed.**

Follow sections 1–4 now. Section 5 is for **after GO, passing CI and merge**;
section 6 sends the new report back for review. Old deferred step 6 stays
deferred: this is a new decoding-only command, not the old geometry audit.
Do not download/delete more raw data as a workaround for an unresolved stop.

## 1. Save the ZIP and prepare

Save the delivered ZIP directly inside `$HOME/Downloads/MPR`. Do not run
commands in Downloads/MPR as though it were the repository. Keep your normal
MPR virtual environment; the commands activate `.venv` if it exists. If your
environment is elsewhere, activate that existing environment first.
Preserve any unrelated uncommitted changes before applying. No command resets
or overwrites existing patches, result directories or private identities.

## 2. Extract, apply both patches and test

Paste this **entire block**. Stop on any error; do not continue to push a branch
that was never created. The two patches apply sequentially to their reviewed
base; do not apply just the second patch or apply either twice.

```bash
(
  set -eu
  mpr_repo="$HOME/PycharmProjects/MPR"
  mpr_downloads="$HOME/Downloads/MPR"
  mpr_bundle="$mpr_downloads/mpr_v0199_selected_stream_decode_check"
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
  if test "$(git rev-parse HEAD)" != 05e0c71f93f8133204f6b5577f5ca69662f647fc; then
    echo 'Stop: main differs from the reviewed base; return git log -5.' >&2
    exit 1
  fi
  test -r "$mpr_downloads/mpr_v0199_selected_stream_decode_check.zip"
  test ! -e "$mpr_bundle"
  test ! -L "$mpr_bundle"
  unzip "$mpr_downloads/mpr_v0199_selected_stream_decode_check.zip" -d "$mpr_downloads"
  (cd "$mpr_bundle" && sha256sum -c SHA256SUMS)
  test "$(find "$mpr_bundle" -maxdepth 1 -name '000*.patch' -type f | wc -l)" -eq 2
  git switch -c feature/v0.19.9-selected-stream-decode-check
  for mpr_patch in "$mpr_bundle"/000*.patch; do
    test -f "$mpr_patch"
    git apply --check "$mpr_patch"
    git am "$mpr_patch"
  done
  test "$(git rev-parse 'HEAD^{tree}')" = "$(cat "$mpr_bundle/EXPECTED_TREE")"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  python -m pip install -e '.[test,mcap]'
  python -m compileall -q src tests
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpr-matplotlib \
    python -m unittest discover -s tests -t .
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m unittest tests.io.test_recording_decode_check tests.workflows.test_recording_decode_check
  git diff --check 05e0c71f93f8133204f6b5577f5ca69662f647fc HEAD
  test -z "$(git status --porcelain)"
  git log -3 --oneline
)
```

Expected with MCAP extras: **650 run, 648 pass, two unchanged opt-in skips**;
**44 focused tests pass**. Unavailable MCAP extras must not be mistaken for
successful decoder validation. Stop on failure, missing new tests or additional
skips. Return failing output and `git status --short`; do not reset or skip tests.
Internal hashes/tree verify bundle consistency, not source authentication.

## 3. Push the new branch and open its PR

After all section-2 checks pass:

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  test "$(git branch --show-current)" = feature/v0.19.9-selected-stream-decode-check
  test -z "$(git status --porcelain)"
  git push -u origin feature/v0.19.9-selected-stream-decode-check
  git rev-parse HEAD
)
```

Open a new PR against **main**. PR #31 stays merged; no reopening is needed.
Title:

`feat: check registered MCAP stream decoding with disk-backed indexes`

Description:

```text
The registered pilot's metadata inventory completed, but the old chunkwise
reader still retains every ChunkIndex and its channel-offset map through
SeekingReader.get_summary(). Add a separate generic decode-check command
that stages scalar index ordering in temporary SQLite, decodes explicit
selected embedded Protobuf streams, validates available selected-chunk CRCs,
and reconciles actual per-channel counts to the preserved complete inventory.

Each raw file is freshly verified once through the same descriptor. Initial
dependency drift stops before payload/output; incomplete decoding publishes
null full-stream results with safe execution progress and first-cause retention.
The accepted v0.19.8 inventory result is documented in the first patch.
No scientific adapter, target/topology/feature change, residual export, real fit,
outing assignment, raw deletion or retry of old deferred step 6 is included.

Validation: compileall; full suite 650 run/648 pass/two unchanged opt-in skips;
44 focused tests, NONE/ZSTD/LZ4 writer and existing-reader value/order parity,
CRC/count/cap/cleanup/lineage/drift tests, actual optimized CLI runs and runbook
guard/application checks. A valid synthetic 116,243-chunk/185-channel-index
fixture completes under 256 MiB RLIMIT_AS; old summary loading hits MemoryError.
No private payload run. Implementation GO and exact-head Python 3.10/3.12 CI
precede merge and one new EDP/RLMB/odometry decoding-only check on the pilot.
```

Do not commit raw MCAPs, registration/specification, private report ZIPs or
source locators. This change is ready to commit/push/open after section 2.
Delete the remote development branch only after merge, if desired.

## 4. Focused Claude review, CI and merge

This is a **Claude review prompt for the MPR repository**, not a BMW Copilot
prompt. No new BMW codebase answer is required for generic byte decoding.

```text
Review the new SirBxss/MPR PR on feature/v0.19.9-selected-stream-decode-check
against main 05e0c71f93f8133204f6b5577f5ca69662f647fc. Return GO/NO-GO,
blocker count, exact current head/tree, versions, tests/skips and limits of
verification. Read AGENTS/current_status, generic_recording_decode_check_v0199,
its runbook/output contract and the accepted v0.19.8 inventory result.

This is a separate target-independent decoding stage, not the native-reference
proposal or old geometry/readiness retry. Verify no SeekingReader summary or
whole ChunkIndex/map retention; temporary SQLite scalar ordering/size/cache/
cleanup, unsorted listings, uint64 clocks, duplicate offsets and overlapping
Chunk+MessageIndex ranges. Inspect selected channel/schema versions, explicit
unique topic selection, absent/count-unknown versus true zero, embedded root
decoding, proto2 required fields, actual advertised count reconciliation,
unselected invalid wire data and no decoded-message retention/geometry call.

Check bounded NONE/ZSTD/LZ4 decompression, Zstd frame window/known/unknown size,
LZ4 max output/eof/trailing handling, actual header/index match, selected stored
CRC nonzero validation before payload, CRC zero unavailable and precise
unselected/DataEnd/MessageIndex integrity limitations. Confirm all advertised
and actual caps, cooperative deadlines/resource checks and unsupported cases.
No full-file authenticity or universal MCAP support claim is allowed.

Check strict bounded predecessor JSON/top-row sets/core lineage and fresh
type-preserving inventory equality; one raw hash/same descriptor, initial
drift no report, execution/batch/path/predecessor/registration drift invalidation,
first-cause retention, full-stream nulls rather than prefix counts, safe scalar
context without native exception text, fresh output including symlink guards,
0/3/2 exits, lazy CLI routing/cap restoration and unchanged scientific readers.
Run full/focused tests and value/order parity. Reproduce the synthetic memory
benchmark if practical; it is not private pilot throughput/cause attribution.

Exercise complete README apply and report guards using a synthetic repo/home
with spaces. Guards must work under PYTHONOPTIMIZE=1/2 and -O/-OO, without
assertions as safety checks. Verify exact base, both sequential patches, expected
tree/branch and preserved small-file hashes. Do not run private data, push,
merge or send messages. No independent ground truth, all-topology adoption,
residuals, training, physical-outing roles or safe deletion follows here.
The next owner action after GO, both CI jobs and merge is one new decoding-only
check; its real report must be reviewed before further geometry work.
```

Send the PR link and review here. A NO-GO requires a specific correction on
this same branch, followed by review/CI at its new head. **Merge after GO with
zero blockers and both Python 3.10/3.12 CI jobs passing at that reviewed head.**
If a CI run uses a temporary merge, verify it contains that exact head/base;
do not mistake a different checkout for reviewed-head evidence.

## 5. One new decoding check after merge

Use only after section 4. This keeps the original registration/specification,
failed readiness report and successful inventory bytes unchanged. It uses a
fresh decoding scratch/output directory and the raw path already registered.
>=6 GiB MemAvailable and >=10 GiB free scratch are required, with <=4 GiB
process address space. Close unnecessary memory-heavy applications first;
do not lower limits or automatically retry if preflight fails.

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
    python -m unittest tests.io.test_recording_decode_check tests.workflows.test_recording_decode_check
  mpr_verify_preserved() {
    printf '%s  %s\n' \
      041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44 \
      outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json \
      c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1 \
      outputs/registrations/recording_ingestion_v0196_batch03_pilot001/source_specification.json \
      55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7 \
      outputs/diagnostics/data/recording_ingestion_v0196_batch03_pilot001/recording_readiness.json \
      53932550e4fe2233c2bac33c0778b9549e9ab5bee83822dca225b98d4df41784 \
      outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001/recording_inventory.json \
      | sha256sum -c -
  }
  mpr_verify_preserved
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import json
from pathlib import Path
from lane_residuals.io.recording_decode_check import DECODE_REVISION, READER_IMPLEMENTATION

def require(condition, message):
    if not condition:
        raise SystemExit('Stop: ' + message)

require(DECODE_REVISION == 'v0.19.9-selected-stream-decode-check-2026-10-08-a1', 'decoder revision mismatch')
require(READER_IMPLEMENTATION == 'v0.19.9-disk-index-selected-chunks-a1', 'reader mismatch')
registration = json.loads(Path('outputs/registrations/recording_ingestion_v0196_batch03_pilot001/registration.json').read_bytes())
require(registration.get('batch_id') == 'batch03_aws_pilot001', 'batch changed')
rows = registration.get('recordings')
require(isinstance(rows, list) and len(rows) == 1, 'expected one technical recording')
row = rows[0]
require(row.get('recording_id') == 'pilot_001', 'recording changed')
require(row.get('raw_sha256') == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78', 'raw declaration changed')
require(type(row.get('size_bytes')) is int and row['size_bytes'] == 29961313204, 'registered size changed')
name = row.get('canonical_path_private')
require(isinstance(name, str) and bool(name), 'registered path missing')
raw = Path(name)
require(raw.is_file() and raw.stat().st_size == row['size_bytes'], 'raw path/size changed')
with raw.open('rb') as stream:
    require(bool(stream.read(1)), 'raw file unreadable')
output = Path('outputs/diagnostics/data/recording_decode_check_v0199_batch03_pilot001')
scratch = Path('outputs/scratch/recording_decode_check_v0199_batch03_pilot001')
require(not output.exists() and not output.is_symlink(), 'decode output already exists; preserve it')
require(not scratch.exists() and not scratch.is_symlink(), 'decode scratch already exists; preserve it')
print('Existing pilot identity/path checked; decode check will freshly rehash raw bytes once.')
PY
  mkdir -p outputs/scratch/recording_decode_check_v0199_batch03_pilot001
  free -h
  df -h outputs/scratch/recording_decode_check_v0199_batch03_pilot001
  set +e
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    python -m lane_residuals.cli.recording_ingestion decode-check \
    --registration-directory outputs/registrations/recording_ingestion_v0196_batch03_pilot001 \
    --scratch-directory outputs/scratch/recording_decode_check_v0199_batch03_pilot001 \
    --preserved-inventory-report outputs/diagnostics/data/recording_inventory_v0198_batch03_pilot001/recording_inventory.json \
    --topic /adp/estimated_drive_paths \
    --topic /adp/road_lane_map_based \
    --topic /adp/odometry \
    --output-directory outputs/diagnostics/data/recording_decode_check_v0199_batch03_pilot001 \
    --log-level INFO
  mpr_exit=$?
  set -e
  printf 'Decode check exit code: %s\n' "$mpr_exit"
  case "$mpr_exit" in
    0|3) test -f outputs/diagnostics/data/recording_decode_check_v0199_batch03_pilot001/recording_decode_check.json ;;
    *) echo 'Stop: no completed decode check; return terminal output. Do not retry or lower limits.' >&2; exit "$mpr_exit" ;;
  esac
  mpr_verify_preserved
)
```

The three topics advertise **181,255 messages total**. Complete decoding
reconciles this, but not a residual count or H100 eligibility. EDP messages
are decoded regardless of topology solely to test byte/schema support; this
does not adopt an all-topology scientific population. Exit 3 has a completed
inconclusive report: proceed only to section 6. Exit 2 has no completed report;
stop and return terminal output, preserving scratch and all old outputs.

## 6. Package only the new report and sanitized receipt

This checks exact pilot lineage, stage flags and complete/null state, then
creates a new receipt and ZIP without overwriting existing files. It includes
no raw bytes, private registration/specification, timestamps or payload values.

```bash
(
  set -eu
  cd "$HOME/PycharmProjects/MPR"
  test -f pyproject.toml
  test "$(git rev-parse --show-toplevel)" = "$(pwd -P)"
  if test -f .venv/bin/activate; then . .venv/bin/activate; fi
  env PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python - <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

def require(condition, message):
    if not condition:
        raise SystemExit('Stop: ' + message)

folder = Path('outputs/diagnostics/data/recording_decode_check_v0199_batch03_pilot001')
source = folder / 'recording_decode_check.json'
require(source.is_file(), 'no completed decode report')
raw = source.read_bytes()
report = json.loads(raw)
require(report.get('contract_revision') == 'v0.19.9-selected-stream-decode-check-2026-10-08-a1', 'report revision mismatch')
require(report.get('reader_implementation') == 'v0.19.9-disk-index-selected-chunks-a1', 'reader mismatch')
require(report.get('purpose') == 'development_only_recording_decode_check', 'unexpected purpose')
require(report.get('status') in ('complete', 'inconclusive'), 'unexpected completion status')
require(report.get('batch_id') == 'batch03_aws_pilot001', 'batch changed')
require(report.get('registration_sha256') == '041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44', 'registration lineage changed')
require(report.get('source_specification_sha256') == 'c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1', 'source lineage changed')
require(report.get('preserved_inventory_report_sha256') == '53932550e4fe2233c2bac33c0778b9549e9ab5bee83822dca225b98d4df41784', 'inventory lineage changed')
topics = sorted(['/adp/estimated_drive_paths', '/adp/road_lane_map_based', '/adp/odometry'])
require(report.get('selected_topics') == topics, 'selected streams changed')
require(type(report.get('technical_recording_count')) is int and report['technical_recording_count'] == 1 and report.get('independent_outing_count') is None, 'recording/session count changed')
for key in ('selected_payload_decoding_enabled', 'selected_chunk_crc_validation_enabled'):
    require(report.get(key) is True, 'decode/CRC policy changed')
for key in ('geometry_readiness_assessed', 'residual_profiles_constructed', 'numeric_conditions_exported',
            'reference_independence_proven', 'model_fitted', 'roles_assigned', 'raw_cache_deletion_authorized'):
    require(report.get(key) is False, 'unexpected scientific action flag')
rows = report.get('recordings')
require(isinstance(rows, list) and len(rows) == 1, 'expected one result')
row = rows[0]
require(row.get('recording_id') == 'pilot_001' and type(row.get('size_bytes')) is int and row['size_bytes'] == 29961313204, 'pilot identity changed')
require(row.get('raw_sha256') == 'a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78', 'raw identity changed')
require(row.get('status') == report['status'], 'per-file status mismatch')
if report['status'] == 'complete':
    check = row.get('decode_check')
    require(row.get('failure_code') is None and row.get('reader_failure_context') is None and row.get('invalidation_codes') == [] and isinstance(check, dict), 'completed decoding missing')
    require(check.get('decoded_selected_message_count') == 181255, 'complete selected count mismatch')
    counts = {r['topic']: r['decoded_message_count'] for r in check['topics']}
    require(counts == {'/adp/estimated_drive_paths': 36032, '/adp/road_lane_map_based': 36032, '/adp/odometry': 109191}, 'topic counts mismatch')
    require(all(r['decoded_message_count'] == r['advertised_message_count'] for r in check['channel_versions']), 'channel counts mismatch')
    crc = check['selected_chunk_crc']
    require(crc['checked_nonzero_count'] + crc['unavailable_zero_count'] == check['completed_selected_chunk_count'] == check['selected_indexed_chunk_count'], 'CRC/chunk coverage mismatch')
else:
    require(isinstance(row.get('failure_code'), str) and bool(row['failure_code']) and row.get('decode_check') is None, 'inconclusive prefix or failure state')
receipt = folder / 'decode_run_receipt.json'
zip_path = Path.home() / 'Downloads' / 'MPR' / 'recording_decode_check_v0199_batch03_pilot001_results.zip'
require(not receipt.exists() and not receipt.is_symlink(), 'receipt already exists; preserve it')
require(not zip_path.exists() and not zip_path.is_symlink(), 'result ZIP already exists; preserve it')
require(source.read_bytes() == raw, 'report changed during packaging')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
value = {'git_commit': commit, 'report_sha256': hashlib.sha256(raw).hexdigest(),
         'decode_status': report['status'], 'purpose': report['purpose']}
with receipt.open('x') as stream:
    json.dump(value, stream, indent=2, sort_keys=True)
    stream.write('\n')
zip_path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('recording_decode_check.json', raw)
    archive.write(receipt, arcname=receipt.name)
print('Commit:', commit)
print('Result ZIP:', zip_path)
print('ZIP SHA-256:', hashlib.sha256(zip_path.read_bytes()).hexdigest())
PY
)
```

Send this ZIP and section-5 terminal output here. Read status/cause first,
then immutable lineage, summary/selected-chunk CRC coverage, schema-version
counts and advertised/decoded reconciliation. Failure progress is not a
complete count or zero residual finding. A complete check still creates no
residuals and does not resolve reference independence or actual session identity.

## 7. Next stages and future recordings

For a new batch, generic prepare/register/inventory already accept explicitly
declared files; see v0.19.8 runbook section 7. Preserve truthful AWS session/
object/export information privately and leave unavailable evidence null.
After reviewing a complete inventory, decode compatible explicit Protobuf
topics using this new command, with fresh batch-specific scratch/output and
that inventory path. Other encodings require a separate compatible adapter.
Arbitrary MCAP metadata support is not automatic lane-model semantics.

The sequence from here is: review the pilot decode result; settle/review native
structure and the research reference/population target; implement compatible
bounded geometry/residual/causal-feature extraction with diagnostic parity;
validate immutable numeric archives and evidence-backed session/sequence splits;
then run the declared classical/conditional/unconditional flow experiments
and old/new comparison. Map/pose/foresight do not automatically supply truth.
No generic numeric exporter or safe raw-cache retirement is implemented yet.
Raw retirement needs durable verified outputs and a tested retrieval route.
