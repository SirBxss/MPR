# Batch02 reference-conversion and timestamp diagnostic

Date: 2026-09-22. Revision:
`v0.19.1-batch02-reference-timing-2026-09-22-a1`.
Prospective extension after the completed v0.19.0 pilot. Implementation and
scope require focused review and normal CI before the one new private run.

## Question and fixed scope

The returned pilot contains 376 sensor-topology EDP H100/anchor candidates,
but generic reference failures and unreported numeric time offsets prevent
assessing residual readiness. We will distinguish those failures and describe
the existing pairs' offsets. EDP/RLMB remains the priority; direct LTSB work
is on hold, with its earlier results and unresolved assumptions preserved.
No alternative topic, reconstructed target or model is adopted.

This extension observes the unchanged converters and complete-stream ungated
mutual-nearest matcher. No source-time shift, delta gate, extrapolation, H100
change, pool-entry skipping, schema relaxation or geometric repair is allowed.
Do not infer physical synchronization from close numeric timestamps, or assume
that a pool error proves the affected vertices are irrelevant to the ego path.
No residuals, features, odometry, sequences, model or planner are constructed.
Unknown acquisition/session provenance stays unknown; no role or lock follows.

## Inputs and execution boundary

Use the same exact four registered batch02 files and original registration/
container-context bytes specified by the v0.19.0 declaration. Additionally
require the exact preserved `recording_pair_feasibility.json`, SHA-256
`89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec`.
Validate its revision, complete status, no-role flags, original runtime-source
fingerprint, four identities and counts against the administrative inputs.
Reject any altered report before hashing raw files, decoding or creating output.
Never overwrite or update the original pilot or earlier batches.

The existing CLI selects this separately versioned mode only when passed
`--preserved-feasibility-report`. Without it, the original output contract and
conversion/pairing behavior remain unchanged. The new output directory must
be absent and receives exactly `recording_pair_diagnostics.json`.

Retain the indexed/storage-order reader, complete topic-count checks, 100,000
messages per topic, 128 MiB chunk limit, temporary disk-backed geometry,
8 GiB spool limit, 4 MiB SQLite cache, 4 GiB process address-space cap, and
fresh 6 GiB available RAM/10 GiB free scratch guards. Decoder imports are
checked before output creation in the new mode. Raw identities are freshly
hashed and file-state mutation checks are unchanged. Bounded scalar offset
lists add at most three lists with 100,000 entries each; no payload history
or extra geometry is retained.

## New observations

Reference exceptions receive a static stage/reason/cause classification.
Stages identify fields, polyline coordinates, optional polyline values,
arc-length pool, boundary fields/coordinates, ego metadata, segment
reconstruction, road metadata, frame validation and ordered ego-path selection.
Classification does not catch new exception types, recover geometry, or
replace the historical failure code. Unknown text maps to a fixed fallback;
raw exception strings, coordinates, field values and message IDs are not output.

The existing per-segment reconstruction failure codes are aggregated for road
frames whose conversion returned. These count failed segments, not rejected
reference messages or ego-only failures; they can occur in a reference that
ultimately succeeds. Whole-message failures do not supply partial segment counts.

For each estimate-topology stratum, report numeric pair count, available
estimator count, first-outcome counts, reference-failure detail counts and those
reference failures paired with an available estimator. The reference-failure
view includes failures masked by an earlier estimate failure in the legacy
first-outcome view. It attributes no sensor topology to an unmatched reference.

Report signed and absolute source-time deltas for three nested sets: all
numeric pairs, anchored H100 pairs, and sensor-topology anchored H100 pairs.
Signed delta is **reference source time minus estimate source time**, in ns.
Use Python integers throughout. Each set reports count, negative/zero/positive
counts and min/p50/p95/p99/max for signed and absolute deltas. Percentiles use
the nearest-rank definition: sorted value at `ceil(p * n / 100) - 1`.
An empty set has zero counts and null extrema/percentiles. No interpolation,
absolute timestamps, per-pair rows, acceptance bins or selected cutoff is added.

## Reconciliation and next decision

Every complete recording's entire original `counts` object must equal its
preserved pilot object, not merely the three headline counts. The new report
records that comparison. A mismatch or incomplete read produces an inconclusive
recording with null counts/diagnostics; a mismatch is explicitly labelled and
cannot be described as a successful extension. No partial-prefix summaries
survive a stream/resource/file-state failure. Other completed files remain
visible, but any inconclusive recording makes the batch inconclusive (exit 3).
Preflight failures exit 2; a complete count-preserving extension exits 0.

Synthetic tests must cover reason/stage separation, suppressed private text,
unchanged success/failure/path/timestamp behavior, duplicate/tie/missing-time
semantics, order invariance, signed integer precision, empty sets, all three
timing subsets, topology stratification, complete-count parity, lineage drift,
file mutation, decoder-import failure and interrupted-stream cleanup.

Reconcile the new real report before proposing a converter correction or
timing decision. Then assess causal inputs and contiguous support before any
separately scoped exploratory residual extraction. The old 376 count is a
geometric upper bound under its unchanged rules, not an eligible dataset.
There is no outcome-driven horizon or threshold change and no independent-
outing admission implied by this diagnostic.

## Implementation verification (2026-09-22)

The implementation is complete and ready for review, not yet independently
approved or privately executed. Compilation passes. With MCAP extras installed,
477 tests run: 475 pass and the two usual opt-ins skip. The full run completed
in 155.735 s; this is test runtime, not a whole-drive memory/time benchmark.
The focused selection has 74 passing tests:

```bash
PYTHONPATH=src python -m unittest \
  tests.domain.test_recording_pair_diagnostics \
  tests.io.test_recording_pair_diagnostics \
  tests.workflows.test_recording_pair_diagnostics_cli \
  tests.io.test_recording_pair_feasibility \
  tests.workflows.test_recording_pair_feasibility_cli \
  tests.io.test_independent_outing_intake \
  tests.workflows.test_independent_outing_intake_cli
```

Twenty-two new tests cover the declared risks, including real Protobuf/MCAP
decoding with good, empty and invalid-geometry references. The old real-MCAP
reader and frozen v0.17 module-graph tests also pass. No prior allowlist,
scientific threshold or domain geometry/model implementation was edited.

The delivered portable synthetic comparison was run against immutable PR #22
head `0661796` and the new diagnostic mode. All original counts, 24 records'
timestamps/failure states, scalar path fields and path-array bytes agree.
Both retain 12 numeric pairs, 4 H100 pairs, 3 anchored pairs and 2 sensor-anchored
pairs. The old three generic RoadMessageErrors split into one empty-lane-list,
one polyline-coordinate and one boundary-coordinate failure; two ego-selection
failures remain rejected. Injected deltas of -20/+7 ns are reproduced exactly.
These tiny offsets are synthetic fixtures, not predictions about batch02.

Expected package-source fingerprint (same algorithm as the original report):
`2f09d5a192d23e28833df06a4d3920768384d186d3fba334765b5620eda5267b`.
The package distribution version remains 0.18.1; the separately versioned
contract identifies this diagnostic. Actual private dependency versions will
be recorded by the runtime report, and count agreement is mandatory.
