# Generic development recording intake and readiness

Date: 2026-10-01. Contract:
`v0.19.6-generic-recording-readiness-2026-10-01-a1`.
Base: merged PR #27, commit `d03f7769c05ee751224aec3870b740c13a575edc`,
tree `0e12d76a7bba6a232d00b4668c967abd196e45e0`.
Status: local implementation and synthetic/MCAP-fixture tests; focused review
of the exact pushed head and Python 3.10/3.12 CI precede the new private audit.
No new private MCAP has been inspected by this implementation agent.

## Why this phase

The owner now has AWS download access and reports a roughly 30 GB MCAP
created by merging 180 input chunks. The Download Helper screenshot shows
MCAP export and merging enabled, an export/source identifier and a selected
3,584-second range. Its displayed `06/10/2026` date and timezone are ambiguous.
The screenshot does not prove the on-disk file name, byte identity, actual
message coverage, index completeness, chunk sizes, schemas, physical-session
identity, source independence or feature availability. The identifier's
physical-session semantics have not been established. Treat one merged file
as **one technical recording**, not 180 independent drives.

The current architecture already supplies reviewed EDP/RLMB geometry, indexed
storage-order reading, disk-backed odometry, strict causal-input checks and
sequence arithmetic. The batch02 orchestration and archive reader deliberately
pin four files and published hashes. They must remain pinned. This phase adds
a separate reusable consumer for explicitly declared new local files.

The first pilot is development-only. Its goal is to identify technical
support before preparing a new residual archive. It is not an alternative
v0.17 final-data lock or a model experiment. Inspecting this pilot must not
retroactively turn it into an untouched final-validation outing.

## Declarations and identity

`python -m lane_residuals.cli.recording_ingestion` has three subcommands:

| Command | Action | Output |
|---|---|---|
| `prepare` | Resolve one real local path and create a development declaration; unknown source evidence stays null | One new private JSON specification |
| `register` | Validate 1–64 explicitly listed recordings, hash each raw file and preserve exact specification bytes; no MCAP payload decoding | New directory with `source_specification.json` and `registration.json` |
| `audit` | Verify registered bytes and indexed structure, then inspect existing geometry, inputs and recording-local support | New directory with `recording_readiness.json` only |

There is no recursive directory scan, AWS API integration, automatic retry,
payload export, model adapter or deletion command. Absolute source paths avoid
duplicating the 30 GB file. A recommended cache location is
`data/raw/new_independent_outings/batch03/pilot_001/`; an already downloaded file
elsewhere can be registered in place. Preparation checks the actual file;
the runbook never assumes that its name is `output.mcap`.

The strict specification version is `mpr_recording_ingestion_v1`. It has exactly
`schema_version`, `batch_id`, `purpose: development_only`, and `recordings`.
Each recording has exactly `recording_id`, `local_path_private` and `source`.
Identifiers match `[a-z][a-z0-9_-]{0,47}`. Paths are normalized absolute Linux
MCAP paths without `..`. Duplicate identifiers, resolved paths and raw SHA-256
identities within a batch fail. Registration is not a global cross-batch
duplicate registry; final-data admission will require cross-batch source and
physical-session reconciliation.

Each source object contains exactly these fields, text or null except the
positive integer/null merged-input count:

```text
source_locator_private, source_recording_id_private,
physical_session_id_private, physical_session_evidence_private,
acquisition_start_utc_private, acquisition_end_utc_private,
export_settings_private, merged_input_mcap_count,
redownload_evidence_private
```

Physical-session identity and evidence must both be supplied or both null.
An export UUID alone is not evidence of a physical outing. Acquisition
endpoints must both be supplied or both null; supplied values need explicit
UTC offsets and increasing times. Do not convert the ambiguous screenshot date
to UTC. Preserve the original displayed labels and unknown timezone in the
export-settings text if useful. A declared session is evidence to review,
never an automatically verified identity or an independent-outing count.
Registration keeps exact private evidence; the returned readiness report
exports only declaration-presence flags and the claimed input-chunk count.

Input JSON rejects duplicate keys and non-finite values. The two-file
registration directory is immutable and has an exact file set. Audit validates
specification byte SHA-256, revision, purpose, recording order/coverage, canonical
paths, raw sizes and SHA-256 identities. Its report records both input hashes.
These are operator-supplied new inputs, not an externally authenticated source
registry; hash verification does not independently authenticate declarations.

## Preserved scientific arithmetic

Decode only EDP `/adp/estimated_drive_paths`, RLMB
`/adp/road_lane_map_based`, and the existing odometry topic. Keep the existing
EDP schema-v1/v2 rules, reference converter and failure diagnostics. No EM,
LTSB or lane-topology-map substitution occurs. RLMB remains a pseudo-reference;
map provenance does not prove physical ground truth or independence.

Use complete original timestamp streams with the existing unique, mutual
nearest matcher, including duplicate/tie/missing-time accounting. The canonical
rule still has **no maximum source-time delta gate**. Report numeric offsets;
do not infer equal physical ages, shift clocks or motion-compensate. A large
offset can require a separately reviewed follow-up before residual extraction.

Reuse H100 coverage at `0,5,...,100 m`, projection of the EDP ego footpoint
onto RLMB, and the <=1 m anchor condition without extrapolation. EDP spline
`s=0` is not assumed to be the vehicle/rear-axle origin. Account for every
topology label; assess complete conditions only on available/no-error
SENSOR_TOPOLOGY anchored candidates. LANE_MAP candidates remain visible in
counts and are not promoted into an independent sensor estimate population.

Reuse the six EDP/vehicle features in their existing order. Retain the fixed
50 ms speed definition and <=50 ms pose-interpolation gaps. Reject any used
odometry source state after the EDP source epoch or logged after the EDP log
epoch, with positive required log times. Identical pose duplicates coalesce
to the earliest log/publish representative; conflicting timestamps remain
unusable. Invalid/changed odometry schema poisons condition availability under
the existing fail-closed rule. No held speed, shift, imputation or future input
is introduced. Recorded clocks do not prove physical online availability.

Geometry and complete-condition support are **readiness candidates**, not
exported residual profiles. The scanner computes feature values transiently,
then exports only counts/failure codes and support summaries. It never calls
`aligned_residual`, builds an NPZ archive or serializes numeric feature values.
The old batch02 residual wrapper retains its mandatory exact preserved-count
and diagnostic parity gate, result shape and successful output semantics.

Sequence support reuses recording-local original estimate/pair indices and
strictly positive source gaps <=200 ms. Missing pairs/features or reordered
messages split sequences. Never stitch files even when a source declaration
places them in one physical session. Full estimate/reference source-clock and
selected-topic log-clock summaries report backward steps, adjacent repeats and
missing source times in storage order. Do not silently sort merged output to
manufacture continuous support.

## Execution limits and completeness

Audit hashes and decodes a recording through the **same open descriptor**;
it does not reopen the verified path for MCAP reads. Check regular-file
size/device/inode/mtime/ctime during hashing, after inspection and across the
batch before publication. Replacement or mutation invalidates its observations.
Registration also checks file state during hashing and before publication.

The indexed preflight retains advertised channel counts, schema identities,
descriptor SHA-256s, chunk sizes and exact decimal log endpoints. This index
evidence is distinct from verified decoded counts. No scan fallback is allowed.
The existing index consistency/chunk rules and actual decoded-count equality
remain mandatory. An interrupted stream never publishes prefix geometry or
input counts as completed evidence.

| Resource | Limit |
|---|---|
| EDP and RLMB messages | 100,000 per topic |
| Odometry messages | 1,000,000 for this new consumer only |
| Advertised compressed/uncompressed chunk and record size | 128 MiB |
| Temporary SQLite spool | 8 GiB, 4 MiB page cache, mmap disabled |
| Process address space | <=4 GiB, applied before heavy CLI imports |
| Available Linux memory | >=6 GiB at start and again before each decode |
| Free local scratch disk | >=10 GiB at start and again before each decode |

The new odometry budget handles an hour at 100 Hz; the historical batch02
budget stays 300,000. This is a declared engineering limit, not a selection,
causality or scientific-threshold change. Anything exceeding a resource limit
is **inconclusive**, not zero geometry. Preserve that report; do not crop,
downsample, remerge, silently raise a cap or retry under different rules.
Hashing costs one full read at registration and another at audit. Processing
is sequential; the raw file is neither copied nor held in RAM. Abrupt external
termination can leave a private temporary spool and no completion report.

## Result and stopping rule

A successful command exit is 0; a completed inconclusive report returns 3;
usage/input/dependency failures return 2 and do not publish a completed report.
Output directories/specification paths must be absent. Preserve failed outputs
and use a reviewed new directory for any subsequent run.

Read the result in this order: execution complete; indexed/decoded topic and
schema evidence; whole-file topology and conversion failures; canonical numeric
pairing and H100 anchor counts; causal failure codes; contiguous input support
and clock-order breaks. Zero complete inputs does not disprove geometric
residual feasibility. Positive geometry does not establish independent truth,
causal physical clocks, an eligible outing or sufficient temporal-model data.

After the first new pilot is reviewed, prepare the smallest evidence-supported
follow-up: either diagnose a schema/index/resource/clock obstacle, or add a
separate generic development archive extractor that requires exact readiness
count/diagnostic parity and exports the existing signed 21-station target.
An archive validator and matched-row physical-outing comparison protocol must
precede real AR/AIOHMM/flow fitting. Both flows remain synthetic-only.

Raw-cache deletion is **not authorized by this stage**, even with declared
redownload evidence. The future lifecycle needs verified durable numeric
archives, lineage and extraction/support audits, original source object/merge
evidence and an actually tested retrieval route. A new merged export need not
be byte-identical to the old one; preserve original object identities and merge
settings, not just an untested assertion that AWS access exists. Before final
claims, lock evidence-backed physical outings prospectively and protect final
drives from development inspection. The current seven-outing gate is unchanged.
