# Registered MCAP inventory and generic pipeline continuation

Date: 2026-10-08. Revision:
`v0.19.8-registered-mcap-inventory-2026-10-08-a1`.
Base: merged PR #30, `c8a757229c87d040d913ccdeed96364fd1d5e0bc`, tree
`badf8da510ea6632f20d50402ac3e20e033a6fae`. This is an engineering continuation
of intake, independent of the reference/target study. It does not execute or
freeze the separate native-reference audit proposal.

## Exact stopping point

PR #28 added reusable `prepare`, `register`, and `audit`. PR #29 corrected
payload retention and enabled stored selected-chunk CRC checks for readiness.
PR #30's final `1e1fe43` received Claude GO/zero blockers; dated Codex checks
verified Actions run [37290291636](https://github.com/SirBxss/MPR/actions/runs/37290291636),
Python 3.10/3.12, each 579 run/577 pass/two skips. GitHub confirms PR #30
merged on 2026-10-05 at 13:45:39 UTC as `c8a7572`; main has that exact tree.

One batch03 technical recording remains 29,961,313,204 bytes, registered as
`batch03_aws_pilot001/pilot_001`. Its original audit was inconclusive ZstdError.
The subsequent attempt stopped at initial RAM preflight, exit 2, before
hashing/decoding/output: 4.5 GiB available <6 GiB, with 53 GiB disk passing.
There is no completed successor, decoded geometry finding, residual archive
or independent-session admission. Preserve the registration and old report.
The new inventory cannot resolve a Zstandard payload failure by itself.

A separate one-off metadata script returned 506 channels and 448 schemas.
It directly read schema/channel groups, skipping the large chunk-index group,
metadata-index group and header library field; it did not rehash raw bytes or
verify summary CRC. Rather than make every future batch depend on that script,
this implementation supplies a reusable, registered-file inventory stage.

## Implemented workflow and completeness boundary

| Stage | Reusable implementation | What completion proves |
|---|---|---|
| Prepare/register | Existing v0.19.6, explicit 1–64 files, immutable private specification/registration | Technical byte identities and preserved declarations |
| Inventory | New `recording_ingestion inventory`, every summary topic/schema | Bounded summary census on freshly verified registered bytes |
| Readiness | Existing EDP/RLMB/odometry `audit` with unchanged SENSOR input support rules | Technical support under its declared scientific contract, if decoding completes |
| Generic numeric export | Not yet implemented; old batch02 exporter remains pinned | Needs completed diagnostics, target/population decision and exact parity |
| Archive/model evaluation | Existing pinned archive validation and synthetic flows | No new-data fit or old/new comparison follows from an inventory |
| Raw-cache retirement | Not implemented or authorized | Needs verified durable archives, provenance and a tested retrieval route |

The input side is reusable. Arbitrary MCAPs are not automatically semantic
inputs to a lane residual model. Unknown encodings/topics can be inventoried;
new payload schemas still require a compatible adapter. Missing optional MCAP
summary data produces an explicit inconclusive result with no scan fallback.
This is not a claim that every valid MCAP must contain a summary or that an
inconclusive recording is unusable.

## Input and execution policy

Reuse the existing exact two-file registration, validated by `_registration`.
No re-registration, basename assumption, recursive discovery, AWS connection,
new physical-session inference, prior-readiness acceptance amendment or retry.
The inventory has no `--preserved-readiness-report` flag: it asks a different
question and never supersedes a readiness report. Source declarations remain
private and only their existing presence flags are exported.

Check existing absent output, registration/source hashes and file sizes.
Use the same Linux >=6 GiB available-memory / >=10 GiB free-scratch guards and
<=4 GiB process address-space cap as intake. Scratch must be an existing
directory; inventory creates no SQLite spool. Before each summary, recheck
resources. Hash each complete raw file once through one open descriptor,
then use that same descriptor for Header/DataEnd marker/Summary/Footer reads.
Check file descriptor/path state during verification, after inspection, and
across the batch before publication; recheck both registration files last.
The full SHA read touches compressed raw bytes without parsing/decompression.

The summary reader uses only Python's standard library. It does not invoke
MCAP/Protobuf decoders, read message/chunk contents or file-level metadata and
attachment values. It inspects the immediate DataEnd marker but does not
validate its data-section CRC. Schema descriptor bytes are hashed, not parsed
or exported. Header library is represented by presence and a hash only.
Channel metadata values and metadata-index names are discarded. Public
summaries contain topic/schema names/encodings, not raw source paths,
coordinates, source locators, acquisition epochs or producer metadata values.
Recording log endpoints are exact decimal values, never labelled acquisition UTC.

| Engineering ceiling | Value |
|---|---:|
| One metadata record content | 128 MiB, checked before allocation |
| Summary plus summary-offset sections | 1 GiB |
| Records in either summary section | 2,000,000 |
| Cumulative parsed UTF-8 text, including repeated compression labels | 16 MiB |
| Summary processing per recording, including CRC and parsing | 300 monotonic seconds |
| CRC read block | 1 MiB |

These are transparent engineering limits, not scientific selection gates.
The 300 seconds excludes the preceding full raw SHA pass and is checked
between bounded reads/records; it is not a hard wall-clock limit on stalled
filesystem reads. Memory retention is one capped record plus bounded
schema/channel text/maps and scalar aggregates. No whole chunk-index list
is retained. The summary-group total can exceed the per-record limit.
Unknown compression strings are counted as `other`; no codec is selected.
Oversize advertised message chunks are reported, not decompressed/rejected
as a metadata failure. Readiness retains its own old chunk/message ceilings.

Nonzero stored summary CRC is checked over exactly the [MCAP specification](https://mcap.dev/spec)'s
Summary/Summary Offset/footer-prefix bytes. CRC 0 remains `unavailable`.
CRC verifies recorded summary bytes, not payload correctness or authenticity.
Header/footer extents, immediate DataEnd marker, grouped opcodes, offset
coverage, per-record bounds, UTF-8/map boundaries, IDs/schema references,
indexed channel references, individual chunk/auxiliary extents and available
statistics/count arithmetic are checked. Optional absent statistics/count maps
remain null; a nonempty advertised count map reconciles to its advertised total.
Multiple channels/schema versions on one topic remain separate; schema ID 0
on a channel means no schema. MCAP-compatible record extension tails and
standard-writer empty summary-offset groups are supported.

This is not a full file-format validator. It does not verify chunk-index
ordering/global uniqueness, actual Chunk/Message Index bytes, omitted summary
records against the data section, data/attachment/chunk CRCs, decoded counts,
file-level producer metadata or deployment identity. Duplicate summary schema
or channel IDs, even if repeated identically, are conservatively inconclusive
for this consumer. Unsupported summary opcodes fail closed. Preserve the
result and review an explicit compatibility amendment rather than silently
raising limits or declaring zero geometry.

## Output and scientific interpretation

Only `recording_inventory.json` is written in a fresh directory. Exit 0 means
all bounded inventories completed and identities remained unchanged. Exit 3
means a completed inconclusive report exists; affected inventories are null,
never prefix counts. Completed other files remain separately visible. Exit 2
means input/preflight failure with no completed report. Initial RAM failure
is exit 2 before hashing; a post-hash resource stop is exit 3 with null inventory.
No retry, cropping or replacement of old outputs occurs.

`complete` is inventory completion, not geometry/readiness/producer evidence.
Message counts/chunk sizes are advertised, not decoded; missing counts are
null. Topic presence does not prove valid geometry, timestamp age, common
frames, H100 support, a defensible reference or independent drives. Both
flow modes remain synthetic-only. EDP/RLMB residual arithmetic, topology
filtering, six features, no-extrapolation rule and old archives are unchanged.

Read `generic_recording_inventory_runbook_v0198.md` for full apply/test/PR,
Claude review and one post-merge pilot-inventory command. Old runbook step 6
remains deferred. Review the inventory before choosing a decoder follow-up;
if successful, compare advertised channels/schemas/counts to the preserved
metadata reports. A separate native-structure contract must still be frozen
and reviewed before its implementation/private execution. Numerical export
and training require their own evidence-backed target and population.
