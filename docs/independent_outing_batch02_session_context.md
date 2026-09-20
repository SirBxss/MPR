# Batch02: recording times, session declarations and machine capacity

Date: 2026-09-19. The code/interpretation review is complete: PR #21 received
focused `GO` with zero blockers and passing Python 3.10/3.12 CI. Missing
session facts do not block merging that PR. Review identities and limits are
in `independent_outing_batch02_registration_result.md`.

Both returned manifests, including the file named `v002`, are the same
unfilled draft. Preserve them and the completed registration. Do not repeat
the 43.7 GB registration/hash pass. This follow-up collects only container
time-range hints and the execution machine's RAM; it does not complete the
manifest or run a scientific intake.

## What to enter, and where to obtain it

| Manifest field | Required fact | Acceptable source |
|---|---|---|
| `acquisition_start_utc` | Actual acquisition-session start as a timezone-aware ISO-8601 time, preferably UTC with `Z` | Recording/session log or provider confirmation, including the clock and timezone |
| `separate_physical_session` | `true` only for an actually separate physical recording session | Owner/provider knowledge that this was separately initiated; file count or UUIDs do not establish it |
| `independence_basis_private` | Factual explanation identifying the session and the evidence used to distinguish it | Session ID/log reference, provider confirmation and its date; record whether the file is an original capture, trim, replay or export |
| `mcap_basenames_private` | All files belonging to that physical session | Provider's file-to-session mapping; group several files together when appropriate |

`acquisition_batch_closed` means the complete file set for this declared
acquisition batch is fixed, not that seven eligible outings exist.
`created_before_outcome_inspection` attests that the declaration precedes
inspection of scientific outcomes. The completed summary-only registration
and this administrative follow-up do not inspect those outcomes. Set each
flag only when true. Keep both prior-lock/supersession fields null because no
successful lock exists. Leave unresolved facts explicit in the draft; do not
turn an unknown into a positive attestation to satisfy the parser.

The existing parser validates structure and literal flags, not the truth of
the declarations. In particular, a nonempty `REPLACE with ...` description
can pass once other fields are filled. Replace that prose with evidence;
passing the parser alone does not establish physical-session independence,
and separate sessions do not prove probabilistically independent errors.
No frozen manifest acceptance rule is changed by this handoff.

The [MCAP specification](https://mcap.dev/spec) defines summary start/end as
the earliest/latest **message log times across the file**. Its timestamp
epoch is user-defined and need not be Unix time. Therefore neither an
apparently plausible UTC conversion nor disjoint file ranges proves the
physical acquisition date or a separate drive. A replay, trimmed interval
or merged export may require the original session log. These container
times are also distinct from the embedded ADP header times used for pairing.

Use a first log time as the session start only if its epoch/clock, original
acquisition meaning and coverage of the session start are confirmed. Never
substitute download time, filesystem modification time, today's date, or
an inferred timezone. Convert the confirmed local time with the timezone
and daylight-saving offset applicable on that acquisition date.

Ask the data provider, using the exact four basenames from the private report:
for each file, what is its original physical recording-session ID and actual
session start with timezone; are any files chunks, trims or replays of the
same capture; does it include the start of the session; and what epoch/clock
does MCAP `log_time` use? An existing session manifest/log is sufficient; no
new broad BMW source-code inquiry is required for these administrative facts.

Once confirmed, create a new private manifest version, for example
`config/private/independent_outings_v017_batch02_v003.private.json`. Keep the
provider reply/log privately alongside it rather than adding undeclared JSON
fields. Unknowns can be returned now; do not fabricate a completed manifest.

## One summary-only follow-up command

Run from `~/PycharmProjects/MPR` in the environment used for registration.
The delivered `COLLECT_BATCH02_CONTEXT.sh` contains this exact Python block.
It requires the existing `mcap` extra. It validates the received registration
hash and exact file coverage/sizes before creating a new output directory.
Raw file hashes are inherited from that report, **not recomputed**. This
cheap size check cannot detect same-size content changes since registration.

The permitted reads are the seekable MCAP header/footer/summary and `free -h`.
The exported fields are file identity/size, summary status, total message
count, raw minimum/maximum log times, their difference, conditional Unix-to-
UTC representations, software versions and RAM. There is no message iteration,
payload decoding, attachment/metadata-content extraction or scan fallback.
Missing summaries/statistics remain unknown. The all-topic log-time interval
is not the v0.17 usable-duration or eligible-frame criterion. No new scientific
CLI, output contract or cohort assignment is introduced.

```bash
python - <<'MPR_BATCH02_CONTEXT_PY'
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from mcap.reader import make_reader

registration_path = Path('outputs/diagnostics/data/batch02_registration_v001/batch02_registration.json')
expected_registration_sha256 = 'c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f'
registration_bytes = registration_path.read_bytes()
if hashlib.sha256(registration_bytes).hexdigest() != expected_registration_sha256:
    raise SystemExit('Registration identity changed; preserve it and reconcile before continuing.')
registration = json.loads(registration_bytes)
root = Path('data/raw/new_independent_outings/batch02').resolve(strict=True)
registered_files = registration['files']
if len(registered_files) != 4:
    raise SystemExit('Expected the four registered batch02 files.')
paths = []
for item in registered_files:
    relative = PurePosixPath(item['relative_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise SystemExit('Unsafe registered path; reconcile the registration.')
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise SystemExit('Registered file is not inside batch02.')
    if path.stat().st_size != item['size_bytes']:
        raise SystemExit('Registered size changed; preserve evidence and investigate.')
    paths.append(path)
found = [p.resolve() for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.mcap']
if len(set(paths)) != 4 or len(found) != 4 or set(found) != set(paths):
    raise SystemExit('Batch02 MCAP coverage changed; do not proceed.')
output = Path('outputs/diagnostics/data/batch02_container_context_v001')
output.mkdir(parents=True, exist_ok=False)

def if_unix_utc(value):
    # This is a conditional display, never a claim about this recording's epoch.
    if value == 0:
        return None
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    date = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return date.strftime('%Y-%m-%dT%H:%M:%S') + f'.{nanoseconds:09d}Z'

rows = []
for item, path in zip(registered_files, paths):
    print(f'Reading summary only: {item["relative_path"]}', flush=True)
    before = path.stat()
    row = {
        'relative_path': item['relative_path'],
        'size_bytes': before.st_size,
        'sha256_from_registration_not_rehashed': item['sha256'],
        'summary_status': None,
        'message_count_all_topics': None,
        'message_start_log_time_ns': None,
        'message_end_log_time_ns': None,
        'log_time_range_ns': None,
        'start_if_unix_epoch_utc': None,
        'end_if_unix_epoch_utc': None,
        'clock_epoch_and_acquisition_correspondence': 'unconfirmed',
    }
    try:
        with path.open('rb') as stream:
            summary = make_reader(stream).get_summary()
        if summary is None:
            row['summary_status'] = 'missing_summary'
        elif summary.statistics is None:
            row['summary_status'] = 'missing_statistics'
        else:
            stats = summary.statistics
            count, start, end = stats.message_count, stats.message_start_time, stats.message_end_time
            row.update(message_count_all_topics=count, message_start_log_time_ns=start,
                       message_end_log_time_ns=end)
            if count == 0:
                row['summary_status'] = 'no_messages_reported'
            elif end < start:
                row['summary_status'] = 'invalid_statistics_range'
            else:
                row['summary_status'] = 'statistics_readable'
                row.update(log_time_range_ns=end - start,
                           start_if_unix_epoch_utc=if_unix_utc(start),
                           end_if_unix_epoch_utc=if_unix_utc(end))
    except Exception as error:
        row['summary_status'] = 'summary_read_failed'
        row['error_type'] = type(error).__name__
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev) != (
            after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev):
        raise SystemExit('File changed during summary read; preserve output and investigate.')
    rows.append(row)

try:
    ram = {'status': 'collected', 'free_h': subprocess.check_output(
        ['free', '-h'], text=True, stderr=subprocess.DEVNULL)}
except (OSError, subprocess.CalledProcessError) as error:
    ram = {'status': 'unavailable', 'free_h': None, 'error_type': type(error).__name__}
report = {
    'purpose': 'batch02_administrative_container_time_hints_and_ram_v001',
    'registration_sha256': expected_registration_sha256,
    'mpr_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'tracked_worktree_status': subprocess.check_output(
        ['git', 'status', '--short', '--untracked-files=no'], text=True).strip(),
    'python_version': platform.python_version(),
    'mcap_version': version('mcap'),
    'raw_hashes_recomputed': False,
    'interpretation': 'Summary log times only. Epoch and physical acquisition correspondence unconfirmed; UTC strings are conditional on Unix epoch. File ranges do not establish session independence or usable duration. No payload inspected or manifest changed.',
    'execution_machine_ram': ram,
    'files': rows,
}
report_path = output / 'batch02_container_context.json'
with report_path.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(f'Wrote {report_path}', flush=True)
MPR_BATCH02_CONTEXT_PY
```

Return `outputs/diagnostics/data/batch02_container_context_v001/batch02_container_context.json`
and any provider/session evidence available. No raw MCAP upload is needed.
The command refuses an existing output directory; preserve a partial result
and resolve its cause before choosing a fresh numbered directory for a retry.

## Handoff verification

The exact embedded Python block was exercised against four synthetic MCAPs,
with message and decoded-message iteration forbidden and verified unused.
Checks cover one-nanosecond precision, missing summary/statistics, an empty
file, refusal to overwrite, registration identity drift, size changes, path
escape and extra-file coverage. The original registration stayed unchanged;
RAM was a test fixture, not evidence about the user's machine. No real batch02
file was available for this check. The delivered shell helper is extracted
verbatim from the block above.

Compilation passes. With MCAP extras installed, the unchanged full suite
ran 440 tests in 55.571 seconds: 438 passed and the same two opt-in tests
skipped. The explicitly named 58-test pairing/intake selection passed in
1.313 seconds. No runtime package, scientific contract or unit-test count
changes in this documentation/administrative handoff.

## Next implementation boundary

The next code assessment concerns per-file geometry retention in the existing
EDP/RLMB intake. Its canonical timestamp matcher is now scalable, but this
does not bound decoded/reconstructed geometry memory. Use the observed topic
counts and execution-machine capacity to choose a synthetic resource check
and the smallest necessary retention correction, preserving the full pairing
streams, tie semantics, eligibility gates and recording/sequence boundaries.
Any runtime change needs its own meaningful parity/resource tests and review
before the applicable private geometry run. These declarations need not hold
up merging the already accepted maintenance PR or synthetic engineering work.

Then perform an outcome-blind technical eligibility assessment under the
existing reviewed scope, with truthful session declarations. Topic presence
alone cannot answer whether EDP supplies SENSOR_TOPOLOGY H100 profiles and
valid RLMB pairing/anchors. Do not fit models, export residuals, substitute
EM fusion or adopt LTSB/RLMB residuals from these summaries. The separate
v0.18 sensor matcher remains quadratic and its CLI remains batch01-pinned;
the canonical optimization must not be represented as making that audit
ready for these four giant files.

Four eligible separate sessions would still be fewer than the seven required
for a final cohort lock. That does not prevent the scoped technical assessment.
If fewer than four physical sessions are confirmed, group them honestly; the
next acquisition requirement follows the eligible outing count, not file count.
