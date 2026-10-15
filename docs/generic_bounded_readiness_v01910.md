# v0.19.10 bounded scientific readiness implementation

Date: 2026-10-15. Status: **local implementation; exact pushed-head review and CI pending**.
The accepted contract is [a4](generic_recording_readiness_v01910_draft.md),
revision `v0.19.10-bounded-recording-readiness-2026-10-14-a4`. Its historical
draft header records its pre-review state. PR #34 is merged at
`0f2950e2b76b823fabea0b67309b268afe205806`, tree
`4100debbc422558b0a049a96aaa7a97f340d7064`. Claude GO covers head `5fc0318`;
Codex checked both a4 CI logs in [run 38697721107](https://github.com/SirBxss/MPR/actions/runs/38697721107):
Python 3.10/3.12 each 650 run, 648 pass/two skips, checkout merge `1546a96`
with the accepted tree. This is contract CI, not implementation CI.

## Command and purpose

The new subcommand is `python -m lane_residuals.cli.recording_ingestion bounded-readiness`.
It requires `--registration-directory`, `--preserved-inventory-report`,
`--preserved-decode-report`, `--scratch-directory`, `--output-directory` and
three explicit `--topic` arguments: `/adp/estimated_drive_paths`,
`/adp/road_lane_map_based`, `/adp/odometry`. Order does not matter; duplicates,
missing or additional topics are rejected. The legacy `audit`, `inventory` and
`decode-check` commands keep their contracts and defaults.

This is a development counts-only consumer. It writes one atomic completion
marker, `bounded_recording_readiness.json`, in a new directory. It constructs
no residual profiles or numeric archive, fits no model, assigns no outing or
split role and never deletes raw data. Its source/log clock endpoints and
descriptor observations are private evidence and must stay outside public Git.

## Implementation and preserved arithmetic

- `domain.recording_readiness_bindings` checks every selected schema/channel
  before payload science. EDP generation uses the existing structural legacy-v1
  and exact root-file-hash-v2 rule. Additional clock/topology/qualifier, numeric
  spline and confidence bindings follow a4. RLMB requires explicit ego direct
  geometry, complete nested entries and existing aliases. Maps cannot satisfy
  repeated-message bindings. Odometry bindings have their own availability rule.
- The disk-index `io.recording_decode_check` accepts an optional scientific sink,
  absolute deadline and caller-owned index connection. Default decoding paths,
  output shape, ordering and CRC behavior remain unchanged. The new sink sees
  each message only after decompression, chunk CRC and Protobuf checks.
- Shared incremental geometry staging and condition finalization are extracted
  from the existing I/O wrappers. The same converters, timestamp matcher, H100
  arithmetic, anchor gate, speed and feature functions and sequence summaries
  are reused. No scientific threshold or domain arithmetic is changed.
- Paths, inputs and odometry go to one disposable scientific SQLite database.
  Only the bounded timestamp/matcher/diagnostic scalars and candidate scalar/
  feature rows are retained in memory; decoded messages and chunk payloads are
  not retained across iterations.
- The new workflow owns strict predecessor checks, one raw hash per recording
  on the same descriptor used for fresh summary/decoding, exact fresh-oracle
  comparison, resource enforcement, late identity checks and atomic publication.

## Results and failure interpretation

Complete readiness contains the inherited `counts`, `diagnostics`, `odometry`,
`source_clock_order`, `log_clock_order`, `sensor_geometry_support`,
`complete_condition_support`, `condition_failure_counts`, plus `exclusive_attrition`.
The latter partitions nine first-failure stages: source time, unique pair,
estimate qualifier, estimate geometry, reference geometry, common H100, anchor,
SENSOR admission and complete conditions. Overlapping inherited diagnostics
remain separate. Unknown labels or inconsistent partitions null science.

| Situation | Publication and exit |
|---|---|
| Complete supported streams, including genuine zero yield | Complete readiness; available for checks/true; exit 0 |
| Empty/invalid/unsupported/multiple-identity odometry | Retained geometry; unavailable odometry/false; exit 0 when otherwise complete |
| Any unsupported EDP or RLMB version, including a zero-message version | Readiness null, not assessed/false; retain reconciled stream evidence; exit 3 |
| Bound confidence field with empty, NaN, out-of-range or insufficient-coverage values | Feature data rejection; can produce measured zero support |
| Missing or incompatible confidence declaration | Unsupported EDP consumer binding; null readiness/exit 3 |
| Container failure | Both stream/science null; safe reader progress context; exit 3 |
| Scientific failure after complete reconciled decoding | Stream retained, science null; exit 3 |
| Late identity mutation | Both stream/science and binding observations null; first cause and later distinct invalidations retained in detection order; exit 3 |
| Invalid inputs, preflight or fresh-oracle disagreement | No report directory, including earlier batch results; exit 2 |

An unsupported odometry descriptor poisons availability even if that version
has zero messages; it cannot disappear behind otherwise usable odometry.
Missing-time or geometrically invalid RLMB rows retain their pre-extracted
time for full-stream pairing. No delta threshold or timestamp repair is added.

## Fixed resource behavior

The accepted caps are unchanged: 100,000 EDP and 100,000 RLMB, 1,000,000 odometry,
4 GiB process address space, 6 GiB MemAvailable, 18.5 GiB initial scratch before
each raw hash and a 10 GiB runtime scratch floor. The one 1,800-second cooperative
deadline starts after fresh-summary equality and covers binding through final
aggregation. The 300-second summary timer and raw hashing are separate.

Exactly two files live in each owned temporary directory: index <=512 MiB and
science <=8 GiB, combined <=8.5 GiB. Every connection verifies `journal_mode=OFF`,
`synchronous=OFF`, `temp_store=MEMORY`, `mmap_size=0`, 4,096-byte pages and <=8 MiB
cache. Page limits and measured logical/allocated bytes are checked. Unexpected
entries stop the run; there is no file-temp fallback or resource-limit override.
Cleanup targets only the owned temporary directory.

`execution_observations` records nonoverlapping raw-hash, fresh-summary,
descriptor-binding, selected-decode and scientific-finalize elapsed times, with
null for unentered phases. Peak RSS is sampled at checkpoints, not a continuous
peak claim. The CLI installs/restores its process limit around execution.

## Verification evidence

The local Python 3.12.14 release suite runs **700 tests: 698 pass and two existing
skips**. Final delivery checks are recorded in the bundle
`VALIDATION.json`; remote Python 3.10/3.12 implementation CI remains pending.
Baseline/default-reader
parity, real synthetic Protobuf/MCAP compression/CRC fixtures, supported versus
unbound versus zero values, mixed/zero-message schema versions, odometry poison,
exclusive attribution, sequence breaks, resource limits, lineage/fresh-oracle
drift, batch invalidation and immutable outputs are exercised.

[The maximum-budget staging result](validation/recording_readiness_staging_v01910.json)
uses 1,000,000 odometry plus 100,000 EDP and 100,000 RLMB records, all candidate
input rows, real MEMORY-temp SQLite index/sort work, the unchanged scalar matcher
and actual geometry/feature finalization. It completes under 4 GiB, retaining
100,000 complete-condition frames and 99,999 transitions; sampled peak RSS is
224,976,896 bytes, database allocation 989,831,168 bytes, elapsed 207.279 seconds.
The fixture stages repeated valid synthetic paths; it does not benchmark
Protobuf conversion, compressed MCAP decoding or private-recording performance.

Two prior runs in the agent's synchronized workspace stopped on an unexpected
`.science.sqlite.*` temporary entry. The unchanged guard/algorithm completed on
isolated temporary storage. External workspace interference is plausible, but
the creator was not established. Preserve these failed observations in delivery
evidence; do not ignore arbitrary files or weaken the guard for a private run.

## Review and continuation

Use a new implementation PR based on merged PR #34. Exact pushed-head
implementation GO and Python 3.10/3.12 CI are required before its merge and the
one new private pilot. The actual private EDP/RLMB/odometry descriptors are not
available here. Use preserved descriptor bytes for conformance evidence where
available; otherwise retain that evidence limit explicitly. The gate itself
classifies all embedded descriptors before any scientific payload conversion.

After the pilot, use [the data-completion handoff](generic_pipeline_data_completion_20261015.md)
to interpret yield and choose incremental acquisition. Numeric export/strict
validation, source/session catalogue, orchestration and verified raw retirement
remain separate consumers. The current registered raw path and all successful
reports stay unchanged; flows remain synthetic-only.
