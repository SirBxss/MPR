# Batch02 context result and unavailable session provenance

Date: 2026-09-20. The original uploaded JSON is immutable and remains outside
Git. SHA-256: `b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad`.

## Verified repository and artifact state

PR #21 is merged at `7834defaf3e3e10b3af908f2b869c96dfa8fae12`, tree
`537c5930034132967fe5c05d198ed63c71af778e`. Its final head was
`d8f368c3454037449aa99e2e8d8819216b07d7f9`. Git fetch and the GitHub PR metadata
agree. CI run `35503298582` passed at that head on Python 3.10 and 3.12
(jobs `106058756794` and `106058756959`). This verifies the accepted source,
not a new private geometry run. The reported execution commit matches the
merge; clean tracked status, Python 3.12.3 and MCAP 1.4.0 are self-reported.

All four relative paths, reported raw hashes and byte sizes reconcile with
the preserved registration SHA-256
`c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f`.
Every raw end-minus-start equals its reported interval, and integer arithmetic
reproduces every conditional Unix-to-UTC display at nanosecond precision.
The raw MCAPs are not available here; their bytes were not independently hashed.
The context collector itself did not rehash them or decode any payload.

| Candidate directory | All-topic log-time interval, seconds |
|---|---:|
| 01 | 1079.935174608 |
| 02 | 178.084178125 |
| 03 | 1059.884897126 |
| 04 | 3408.308427676 |

The numerical ranges are disjoint and the conditional calendar dates differ.
Exact timestamp values and calendar displays remain in the private report.
Neither observation identifies original physical sessions or proves the
clock/epoch and acquisition meaning. The intervals concern all-topic container
log times, not the v0.17 usable-sequence duration. No file is assigned an
acquisition date, outing identity or development/final role from this table.

The execution host reported 31 GiB total RAM, 29 GiB used, 503 MiB free,
2.3 GiB available, and 2 GiB swap entirely used. This is a snapshot, not a
current memory measurement or evidence of a failed MCAP run. It supports
removing retained whole-recording geometry before a payload pilot and
checking current available memory immediately before execution.

## Owner decision and next work

The user says the session/acquisition/export answers cannot be obtained.
Record the gaps as unavailable; stop the repeated provider questions and do
not request another partially completed manifest. The existing v0.17 manifest
parser and seven-outing lock remain unchanged. These files are not currently
admissible as confirmed independent final-validation outings, but they are
not thereby proven unusable, mutually dependent or one physical session.

Proceed with the separately scoped recording-level geometry feasibility in
`docs/recording_pair_feasibility_predeclaration.md`. It reuses EDP/RLMB
conversion and H100 projection, preserves complete timestamp pairing and
holds paths in a private temporary disk spool. Only counts/failure states
leave the computation. The new CLI assigns no roles, calculates no residuals
or causal feature values, and cannot create an outing lock. The old full
intake remains unavailable with the draft manifest; this command does not
turn a technical result into eligibility under that protocol.

The memory change bounds retained geometry independently of file length,
while complete timestamp/audit metadata remains linear and capped. Decoder
and chunk memory still matter, so the runbook includes advertised chunk/message
limits, fresh host-memory/disk checks and a hard per-process address-space
limit. An incomplete run is inconclusive, not zero geometry support.

## Verification of the proposed implementation

Fifteen new tests cover lossless geometry round trips at anchor boundaries,
complete-stream pairing before geometry filtering, duplicates/missing times,
order-invariant counts, independent topology/anchor classification, bounded
live geometry/message references, summary/index resource limits, actual MCAP
storage-order/topic filtering, partial-stream cleanup, exact artifact/raw-file
lineage, low-memory refusal, process-cap/restoration behavior, existing-output
refusal and mutation handling.
The existing intake tests remain regression coverage for the shared conversion
loop extraction. No real batch02 payload has been read here.

Compilation passed. With MCAP extras installed, the full suite ran 455 tests
in 56.750 seconds: 453 passed, with the same two expected opt-in skips. The
52-test focused command passed in 1.686 seconds:

```bash
PYTHONPATH=src python -m unittest \
  tests.io.test_recording_pair_feasibility \
  tests.workflows.test_recording_pair_feasibility_cli \
  tests.io.test_independent_outing_intake \
  tests.workflows.test_independent_outing_intake_cli
```

A synthetic retained-memory comparison used 409 vertices per path and a
64 KiB dummy EDP payload. The same generator fed either retained lists or
the new disk-backed count consumer:

| Synthetic pairs | Retained-list traced peak, bytes | Disk-backed consumer traced peak, bytes |
|---:|---:|---:|
| 100 | 10,816,458 | 359,846 |
| 1,000 | 107,494,416 | 954,559 |

The disk consumer recovered all synthetic sensor/anchor/H100 candidates.
These are Python traced allocations, not total RSS or a measured MCAP memory
bound. The list arm models only the old retention lifetime; it is not a full
old-intake execution, and the disk arm additionally performs pairing/projection.
Dummy payload size is a fixture choice, not an observed BMW message size.
No timing speedup is claimed: lower retained memory trades for disk I/O.

The implementation and prospective scope require focused review on the exact
pushed branch before the first payload pilot. This is the new review required
by `AGENTS.md`, not a reopening of PR #21 or a request for unavailable metadata.
