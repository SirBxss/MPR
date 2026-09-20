# Batch02: four large-file arrivals

Completion checkpoint: the user has returned the registration ZIP. See
`docs/independent_outing_batch02_registration_result.md` for the reconciled
counts, incomplete owner declarations and next engineering step. Preserve
the report and do not repeat this command. The procedure below is retained
as the executed administrative recipe, not a new payload-run authorization.
PR #21 has since received `GO` and passing CI. Follow
`docs/independent_outing_batch02_session_context.md` for the new summary-time
and RAM follow-up, not this old registration command.

Date: 2026-09-19. Status: administrative registration and container-topic
inventory only; no batch02 payload, geometry, eligibility or model result has
been inspected here. The user reports four new drives, each in one MCAP.
The screenshot shows approximately 8.4, 1.4, 8.0 and 25.9 GB (43.7 GB total).
Those rounded display values are not verified file sizes or drive identities.
Private basenames and the owner-completed manifest remain outside Git.

## Priority and the previous patch

Prioritize these arrivals. Git fetch confirms that the timestamp correction
already exists on `origin/docs/v0.19-source-acquisition-decision` at
`ca6b154320c7cff7e77adb42cf7c3586e6dc88eb`, tree
`927cd0e4ff5f76b9bde2104e205fe247f6127424`. It matches the previously delivered
correction even though the user reports not applying the last patch. Do not
apply that patch again. This checkpoint establishes repository content, not
which actions the user performed locally. No open PR was found at this check.
The material epoch interpretation still awaits focused independent review.

The old batch01 negative stays closed. Recovering its historical software
build is not a prerequisite for registering new arrivals. Obtain available
session/build/configuration records for these new files instead; record
unknowns without filling them from current-source defaults.

This procedure uses the existing `inspect_mcap_topics` summary reader. It
adds no reader, CLI, scientific gate, target or release. The allowed first
look is file names/sizes/hashes and summary-advertised presence, message counts,
schema names and encodings for the seven explicitly listed topics below.
It does not iterate message records, decode payloads, inspect topology enums,
construct geometry, or assign development/final roles. Topic presence and a
schema name are not proof of decoder compatibility or usable residual pairs.

## 1. Place the files without altering their bytes

From the project root:

```bash
cd ~/PycharmProjects/MPR
mkdir -p data/raw/new_independent_outings/batch02/candidate_drive_01
mkdir -p data/raw/new_independent_outings/batch02/candidate_drive_02
mkdir -p data/raw/new_independent_outings/batch02/candidate_drive_03
mkdir -p data/raw/new_independent_outings/batch02/candidate_drive_04
mkdir -p config/private
mkdir -p ~/Downloads/MPR
df -h data/raw/new_independent_outings/batch02
free -h
```

Place one original MCAP in each candidate directory, preserving its basename.
The delivered private instructions map the screenshot's files to these four
directories. These are storage labels, not a declaration of independence.
Keep the original download/source copy until transfer integrity is confirmed;
copying all four needs roughly another 44 GB on the destination filesystem.
Do not split/repack the originals merely because they are large: that changes
file hashes and potentially recording boundaries used by the frozen intake.

Use **only** `data/raw/new_independent_outings/batch02` as this batch's root.
The parent now also contains the closed 86-file batch; old commands pointing
at that parent no longer describe the old exact file set. Preserve its
manifest, files and all old output directories unchanged.

## 2. Record real session provenance privately

Use the delivered four-entry private draft, saved as
`config/private/independent_outings_v017_batch02.private.json`. The draft has
false attestations and unset acquisition times deliberately. It is not a
runnable v0.17 manifest until the owner completes it truthfully.

For each actual physical session, record its timezone-aware acquisition start,
the operational evidence that it was a separately initiated session and all
its exact MCAP basenames. Merge entries if files came from the same session.
Four files, four folders or four UUIDs do not prove four independent outings.
Do not substitute today's date, a filesystem modification time or a guessed
date from a filename. If identity/time is unknown, return the draft with that
gap; container inventory below does not require a false attestation.

Set the closed-batch and before-outcome-inspection attestations to true only
when true. Keep both prior-lock/supersession fields null: no successful cohort
lock exists. If outcomes have already been inspected, disclose that before
any final-cohort decision; do not attest otherwise. The summary-only inventory
below is outcome-blind. Preserve completed manifest bytes before any later
eligibility execution; corrections need a new manifest/versioned output.

In a separate private note, record any already available software build,
effective producer parameters, frame/epoch specification and their evidence
source. Unknown is acceptable. In particular, do not assume the previously
reported 61 m/2.5 s cutoff, tracking mode or 80 ms override applies here.
Missing historical batch01 metadata need not delay this registration.

## 3. Register bytes and inspect only existing summary metadata

Use the project's existing environment. First verify imports:

```bash
PYTHONPATH=src python -c 'from lane_residuals.io.mcap import inspect_mcap_topics; import mcap'
```

If the MCAP dependency is absent, install the project's declared extra in
that environment with `python -m pip install -e '.[mcap]'`. Do not use the
general `scripts/inspection/inspect_mcap.py` or `open_mcap.py`: those iterate
messages and the former exports payload samples by default.

Run this command once after file transfers have finished. Hashing reads all
approximately 44 GB sequentially in 1 MiB blocks; summary inspection uses the
existing reader without message decoding. It can take several minutes. A
fresh output directory is required; retain any incomplete directory and use
a new numbered directory if a technical retry is needed.

```bash
PYTHONPATH=src python - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

from lane_residuals.io.mcap import inspect_mcap_topics

root = Path('data/raw/new_independent_outings/batch02')
files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() == '.mcap')
if len(files) != 4 or len({p.name for p in files}) != 4:
    raise SystemExit('Expected exactly four MCAPs with unique basenames in batch02; check placement.')
topics = (
    '/adp/estimated_drive_paths',
    '/adp/road_lane_map_based',
    '/adp/lane_topology_sensor_based',
    '/adp/lane_topology_map_based',
    '/adp/lane_markings_sensor_based',
    '/adp/odometry',
    '/em/road/ego_lane_path',
)
output = Path('outputs/diagnostics/data/batch02_registration_v001')
output.mkdir(parents=True, exist_ok=False)
rows = []
for index, path in enumerate(files, 1):
    print(f'[{index}/4] Hashing and reading summary: {path.name}', flush=True)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    row = {
        'relative_path': path.relative_to(root).as_posix(),
        'basename': path.name,
        'size_bytes': before.st_size,
        'sha256': digest.hexdigest(),
    }
    try:
        records = inspect_mcap_topics(path, topics=topics)
        row['summary_read_status'] = 'readable'
        row['topics'] = [{
            'topic': item.topic,
            'present': item.present,
            'message_count_reported_or_zero_if_unavailable': item.message_count,
            'schema_names': list(item.schema_names),
            'schema_encodings': list(item.schema_encodings),
            'message_encodings': list(item.message_encodings),
        } for item in records]
    except Exception as error:
        row['summary_read_status'] = 'failed'
        row['summary_error_type'] = type(error).__name__
        row['topics'] = None
        print(f'  Summary unavailable: {type(error).__name__}; no payload fallback.', flush=True)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SystemExit(f'File changed during registration: {path.name}; preserve output and investigate.')
    rows.append(row)
report = {
    'purpose': 'batch02_administrative_registration_and_summary_only_inventory',
    'mpr_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'tracked_worktree_status': subprocess.check_output(
        ['git', 'status', '--short', '--untracked-files=no'], text=True).strip(),
    'mcap_file_count': len(rows),
    'total_size_bytes': sum(row['size_bytes'] for row in rows),
    'interpretation': 'Summary advertisements only; zero counts may mean unavailable statistics. No payload validation, physical epoch, eligibility or independence is established.',
    'files': rows,
}
with (output / 'batch02_registration.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(f'Wrote {output / "batch02_registration.json"}', flush=True)
PY
```

This is an administrative report, not one of the four v0.17 lock outputs or
the three v0.18 feasibility outputs. The SHA-256 identifies the local bytes;
it does not verify transfer against the source unless source checksums match.
Compare supplied provider/source checksums when available. A readable summary
does not verify the complete MCAP body. Missing/broken summary is inconclusive,
not an empty topic or an unusable drive; do not fall back to a payload scan.
The existing helper substitutes zero when summary counts are unavailable;
the explicit report field and interpretation preserve that limitation.
The two decoder-support flags returned by the helper are intentionally omitted:
they check names/encodings, not exact descriptor compatibility.

## 4. Return this bounded evidence

Send `batch02_registration.json`, the owner-completed manifest (or clearly
incomplete draft), any available private provenance note and the terminal
output of `free -h`. These are small private artifacts; do not send the MCAPs
or commit their identities/configuration to Git. Include all four files,
including failed summaries. Preserve this first report unchanged.

## 5. Choose the next executable step from that evidence

The large-file concern is demonstrated in current code, not measured on these
recordings: `io/independent_outing_intake.py::_decode_geometry_streams` retains
all decoded EDPs plus reconstructed estimate/reference geometry for one file.
`domain/pairing.py::_unique_nearest_positions` compares every source timestamp
with every target timestamp, in both directions: O(N*M) work. The separate
v0.18 matcher also has O(N*M) work. Large camera payloads could dominate file
bytes while these topic counts remain modest; file size alone proves neither
out-of-memory nor acceptable execution. There is no giant-file benchmark yet.

After registration, inspect the relevant topic counts and schema names, then
choose the smallest necessary change. If needed, make timestamp matching
scalable while preserving exact tie, duplicate, missing-time, mutual-nearest
and gate semantics, with synthetic equivalence tests. Address retained
geometry separately; a faster matcher alone does not establish bounded memory.
Use synthetic long streams for resource checks before a whole-drive run.
Do not split originals or relax gates to bypass the problem.

Keep the canonical EDP/RLMB H100 target if its existing evidence/gates apply.
If EDP provenance again fails, record that result before considering a
separately scoped sensor-topology diagnostic. The v0.18 CLI is pinned to
closed batch01; never pass these new files with its old manifest/intake.
Presence of EM or map-based topology does not adopt them as a reference.
LTSB residual construction still needs applicable frame/epoch and physical
station correspondence; map-based geometry remains a pseudo-reference.

The v0.17 lock needs at least seven eligible new physical outings. Even if all
four prove independent and technically eligible, four alone cannot create a
successful lock. They can supply useful outcome-blind technical evidence;
keep future final candidates untouched and collect at least three additional
eligible outings if these four qualify. A later cumulative closed manifest
must be decided prospectively, preserving every earlier failed audit. Do not
change the seven-outing rule or declare these four development-only merely
because the first stage is technical. No residual/model/feature inspection or
final split is part of this arrival procedure.
