# Selected-stream decoding check on registered MCAPs

**2026-10-09 checkpoint:** this design is implemented and reviewed; PR #32
merged as `85cd9d6` and the one authorized pilot run completed, exit 0.
Read `recording_decode_check_batch03_v0199_result.md` for accepted real evidence
and `generic_pipeline_continuation_20261009.md` for the remaining pipeline.
The pre-run design/evidence below is historical; do not repeat its pilot run.

Date: 2026-10-08. Candidate revision:
`v0.19.9-selected-stream-decode-check-2026-10-08-a1`.
Base: merged PR #31, `05e0c71f93f8133204f6b5577f5ca69662f647fc`.
This extends generic input infrastructure. It does not implement the draft
native-reference audit or change any scientific population or target.

## Evidence and immediate problem

The accepted pilot inventory is complete on freshly verified registered
bytes, with nonzero summary CRC validated. It contains 116,243 chunk indexes,
506 channels and 448 schemas; EDP/RLMB advertise 36,032 messages each,
odometry 109,191. Its largest advertised uncompressed chunk is 2,109,683 bytes.
These counts are not decoded observations. Read
`recording_inventory_batch03_v0198_result.md` for immutable lineage.

The v0.19.7 storage iterator bounds queued message payloads but inherits
`SeekingReader.get_summary()`: every ChunkIndex and its channel-offset map
still resides in memory. The new inventory instead streams aggregates. The
new decoder stages scalar index records in temporary SQLite, orders them by
physical byte offset, and discards each channel-offset map after insertion.
This is a demonstrated retention difference, not proof of the cause of the
private original ZstdError. No private payload has been decoded here.

## Input and execution contract

`recording_ingestion decode-check` requires:

- The existing exact two-file registration directory, with its strict
  specification, registered raw identities and specification/registration hashes.
- One preserved, **complete** v0.19.8 `recording_inventory.json`. Duplicate
  JSON keys, nonfinite constants, extra/missing top-level or recording-row keys,
  wrong revision/purpose/lineage/row order, noninteger identity counts, or
  scientific flags are rejected. The read is capped at 64 MiB.
- An explicit list of 1–16 unique, exact absolute topic names, each <=1,024
  characters. No default topic discovery or automatic selection.
- Existing scratch and a new absent, nonsymlink output directory.

Initial registration/predecessor/resource/dependency failures stop with exit 2
and no new report. Each raw file is freshly hashed **once**, and its same open
descriptor supplies fresh summary inventory and selected chunks. Fresh
inventory must exactly match the preserved inventory, including JSON number
types and source-declaration status. A mismatch is dependency drift: exit 2
before payload decoding/new output. Historical runtime/interpretation fields
are retained predecessor evidence, not required to match the new runtime.
Descriptor bytes are never taken from a sidecar or inferred BMW type binding.

The fresh inventory rechecks summary extents/metadata/count arithmetic and
available summary CRC under its unchanged limits (1 GiB summary, 128 MiB
record, 16 MiB parsed text, 2 million records per section, 300 cooperative
seconds). Selected channels require available nonnegative advertised counts
and Protobuf message/schema encoding with a real embedded schema. Missing
topics/counts are explicit inconclusive failures, never invented zero counts.
Multiple channel/schema versions remain separate and file-local.

| Additional engineering ceiling | Value |
|---|---:|
| Messages per selected topic / all selected messages per recording | 1,000,000 / 2,000,000 |
| Selected channel / schema versions per recording | 256 / 64 |
| Cumulative selected schema descriptor bytes | 16 MiB |
| Selected Chunk record / actual uncompressed data / Zstd window | 128 MiB each |
| Temporary index database / SQLite page cache | 512 MiB / 8 MiB |
| Cumulative selected payload bytes processed, not retained | 8 GiB |
| Decoder processing per recording | 1,800 cooperative seconds |
| Process address space / minimum MemAvailable / free scratch | <=4 GiB / >=6 GiB / >=10 GiB |

The decoder timer excludes raw hashing and the preceding fresh inventory;
it is checked between bounded operations, not a hard deadline for stalled
I/O/native calls. Resource checks occur before each fresh inventory, every
1,024 staged indexes and every 128 selected chunks, including the first.
Budgets are engineering limits for this consumer, not evidence of zero
geometry. No user flag raises limits or enables fallback/retry.

Index offsets are globally unique and sorted on disk, with nonoverlap of
Chunk plus advertised Message Index ranges. An empty channel-offset map
requires conservative inspection of the chunk; otherwise only chunks with
a selected channel are read. Selected records/actual headers must match the
index's identity, length, compression, size and unsigned time bounds. Times
are checked privately as uint64 values and never sorted or exported here.
No whole ChunkIndex list/map-of-maps or decoded message collection is kept.
SQLite is closed and its temporary directory removed on success or failure.

NONE, ZSTD and LZ4 chunks are supported. Zstd window and known frame content
size are checked before one-frame decompression; unknown-size output is capped.
LZ4 output is capped with `LZ4FrameDecompressor.max_length` and its end-of-frame
checked. Trailing/concatenated compressed frames are conservatively unsupported
by this consumer. This does not declare every such recording globally invalid.
See the primary [Zstandard API](https://python-zstandard.readthedocs.io/en/latest/decompressor.html)
and [LZ4 API](https://python-lz4.readthedocs.io/en/stable/lz4.frame.html).

For every inspected chunk, a nonzero uncompressed CRC is verified before
any selected payload is decoded; CRC zero is counted as **unavailable**.
Selected payloads decode against their embedded root through MCAP's
Protobuf DecoderFactory and must satisfy proto2 required-field initialization.
Instances are immediately discarded. Successful decoding does not establish
BMW scientific schema compatibility, qualifier validity, finite geometry,
frames, epochs, path origins, source independence, features or H100 support.

## Completeness and privacy

Exit 0 means every registered file completed its selected indexed streams,
per-channel decoded counts equal advertised counts, and identities remained
unchanged. Exit 3 means a completed inconclusive JSON exists: affected
`decode_check` is **null**, never successful-prefix counts. Other files retain
individual results, without pooling or assigning outings. Exit 2 means no
completed report. A missing dependency/topic/codec is not zero residual pairs.

Failure context contains fixed scalar execution observations only: phase,
zero-based physical indexed-chunk ordinal, chunk byte offset, completed selected
chunk count, decoded selected-message prefix count, processed payload bytes,
channel/schema IDs, supported compression label or `unsupported`, exception
class, and Linux process VmSize/VmRSS (nullable). It is **execution progress**,
not a complete population statistic. The first cause is preserved; later raw,
registration or predecessor identity invalidations are listed separately.
Native exception text, paths, payload bytes, coordinates and exact timestamps
are never logged/exported. Source declarations use existing presence flags only.

Raw descriptor/path state is checked during verification, after inspection
and across the batch before publication. Both registration files' exact set
and hashes and the preserved inventory bytes' hash are rechecked last. Drift
during execution nulls affected results; initial drift produces no report.
The output contains only `recording_decode_check.json`. There is no payload
archive, AWS API, producer metadata extraction, retrieval/deletion mechanism,
numeric residual/condition export or fit.

## Integrity boundary

Summary CRC and **inspected selected-chunk** CRCs are separate coverage.
Unselected indexed chunks with nonempty maps disjoint from selected channels
are skipped and their CRC/payload/header is not validated. Message Index
record contents, DataEnd CRC, metadata values, attachments, omitted chunks
or selected messages outside indexed chunks are not independently enumerated.
The consumer relies on a conforming indexed MCAP and available Statistics;
count reconciliation is additional evidence, not full-file authenticity or
exhaustive format certification. Selected duplicate Schema records compare
name/encoding/data/hash; selected duplicate Channel records compare binding,
topic/encoding and metadata **entry count**, not metadata keys/values.
See the [MCAP specification](https://mcap.dev/spec).

Unsupported summaries, unindexed streams, unsupported selected codecs/schemas
or limits cause an explicit inconclusive result; there is no streaming scan
fallback. Investigate the recorded cause before any narrowly reviewed amendment.

## Validation and direction

Synthetic tests cover NONE/ZSTD/LZ4 writer parity, decoded-value/order parity
with the existing chunk reader, multiple schemas, descending uint64 clocks,
CRC zero/mismatch, missing indexes/counts/topics, invalid selected/unselected
payloads, proto2 required fields, wrong advertised counts and actual headers,
duplicate/overlapping ranges, caps/deadlines/resources/cleanup, one raw hash,
same-descriptor use, predecessor/registration/path/batch drift, null publication,
first-cause retention, CLI routing/cap restoration, and actual -O/-OO CLI runs.

A valid synthetic disk fixture with 116,243 Zstd chunks and 185 channel entries
per ChunkIndex completed the new selected decoder under 256 MiB RLIMIT_AS:
116,243 decoded selected messages and nonzero chunk CRCs, 52.968 seconds,
36,440 KiB maximum RSS on Python 3.12.14/MCAP 1.5.0. The old summary reader
hit MemoryError under the same cap. Both reader children imported the same
modules before setting the cap; fixture generation occurred separately.
This is synthetic index-retention evidence, not private-file throughput or a
diagnosis of the original failure. Reproduction script/result accompany delivery.

Read `generic_recording_decode_check_runbook_v0199.md` for apply/test/PR/review
and **one new post-merge decoding check**, initially EDP/RLMB/odometry. Focused
implementation GO and Python 3.10/3.12 CI precede private execution. This does
not repeat registration/inventory as an owner task or execute old deferred
step 6; the command itself necessarily revalidates the inventory once.

Review the real report before geometry work. If complete, resume the separately
reviewed native-structure/reference/population decision and prepare compatible
bounded scientific extraction with explicit geometry/frame/epoch/causal rules.
If inconclusive, diagnose its exact phase and cause without automatic retries.
All-topology EDP being decoded here does not adopt an all-topology training
target. RLMB remains a correlated pseudo-reference, not ground truth.
Historical target/sign/H100/no-extrapolation/SENSOR/six-feature rules, archives
and models are untouched. Conditional and unconditional flow remain
synthetic-only. Raw retirement requires verified durable numeric outputs,
traceable session provenance and a tested retrieval route, still unimplemented.
