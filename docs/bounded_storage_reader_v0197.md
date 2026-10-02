# v0.19.7: bounded indexed storage reader and one pilot successor

Date: 2026-10-02. Engineering amendment to the unchanged scientific contract
`v0.19.6-generic-recording-readiness-2026-10-01-a1`. Base main is merged PR #28,
`8d55edf5f4c2ae7d30ce2533f702138319d63270`.

Read [`recording_ingestion_batch03_v0196_result.md`](recording_ingestion_batch03_v0196_result.md)
first. The private result is inconclusive, not a zero-pair finding. This
correction is locally implemented/tested; exact-head independent GO and
Python 3.10/3.12 CI are pending before its one private execution.

## Reader correction

`io.indexed_storage_reader.IndexedStorageReader` subclasses the existing
optional MCAP seeking reader for its summary and Protobuf decoder interfaces.
The shared `decoder_types()` resolves it lazily, preserving the frozen
default intake import graph. The adapter replaces only message iteration:

1. Require indexed chunks, retain existing complete-statistics/message budgets,
   and process chunk indexes in **physical byte-offset order**.
2. Validate chunk ranges and selected channel identities; skip chunks indexed
   exclusively for unrequested topics. A chunk without channel indexes is
   decoded conservatively, never treated as empty.
3. Read one bounded chunk record through the verified open descriptor. Check
   opcode, exact record length, actual/indexed compression, compressed and
   uncompressed sizes, and chunk time bounds before decoding.
4. For ZSTD, reject a known frame content size inconsistent with the already
   capped MCAP size; valid unknown-content-size frames use the existing
   bounded `max_output_size` path. Decompress one chunk once.
5. Traverse bounded inner record lengths and yield only selected Message
   objects. Decode selected Protobuf payloads with the same DecoderFactory;
   unselected payloads are neither decoded nor queued. Release the current
   chunk before loading the next.

This bounds retained payloads by the current chunk/message, rather than the
total selected recording payload. Index structures and the existing bounded
spool/scalar collections still consume memory; this is not a guarantee that
every input fits 4 GiB. No sequential scan fallback, time filtering, reverse
reading or log-time sorting is supported by this adapter. Current callers
already request full storage order. A summary with out-of-order chunk indexes
is traversed by file offset, consistent with the intended physical-storage
definition; the old FIFO would have used summary listing order. Within a
chunk, original message order and all timestamp/sequence/schema fields stay
unchanged. No backward-clock repair is introduced.

NONE, ZSTD and LZ4 use the existing MCAP decompressors. CRC policy remains the
existing default (not newly required). Exact decoded-topic count reconciliation
still rejects interrupted or incomplete selected streams. The reader does
not certify every ignored topic/chunk or provenance of the original export.

Primary implementation evidence: installed MCAP 1.4.0 and downloaded 1.5.0
reader/queue sources, plus the public
[MCAP seeking reader](https://mcap.dev/docs/python/_modules/mcap/reader) and
[chunk decompressor](https://mcap.dev/docs/python/_modules/mcap/stream_reader).
Upgrading MCAP alone is not the tested correction.

## Failure observability and preserved-report gate

Readiness adds `reader_failure_context` per recording. It is null on success
and on failures outside the chunk iterator. Chunk failures retain only static
codes, physical byte offset, zero-based indexed chunk ordinal, fully processed
selected-chunk count, phase, compression category, native exception class and
optional Linux process virtual/resident byte snapshots. These execution
observations are **not** prefix sample/geometry evidence. All readiness counts
and support fields remain null after any incomplete stream. No exception text,
paths, coordinates, payload values or timestamp is added to this context.

Native ZstdError text is inspected internally only to choose fixed categories:
`zstd_decompression_memory_limit`, `zstd_decoder_window_limit`,
`zstd_dictionary_error`, `zstd_corrupt_or_incomplete_frame`, or
`zstd_decompression_failed`. These are library-reported error classifications,
not independent proof of original-file corruption. Frame/index disagreement
has a separate static code. Native text is never exported or logged.

The optional audit flag `--preserved-readiness-report` is intentionally narrow:
accept exactly one old inconclusive `ZstdError` recording, with null decoded
observations, no exports/roles/fit/deletion, exact registration/specification
lineage and the same raw identity. Before payload inspection, fresh indexed
metadata must exactly equal the preserved metadata. Pin exact predecessor
bytes in `preserved_readiness_report_sha256` and check them again before
publication. Tampering/drift invalidates observations. Generic first audits
omit the flag; no automatic retry or multi-recording amendment is added.

Registration/specification schemas and contract revision remain unchanged,
so the existing immutable two-file registration is reused. New readiness
reports identify `v0.19.7-indexed-storage-chunkwise-a1` and also record Zstandard
and LZ4 runtime versions; registration retains its original version-key set.
The old JSON bytes are never rewritten.

## Scientific invariants and execution scope

No geometry, schema binding, station grid, target sign, origin projection,
<=1 m anchor, no-extrapolation rule, complete-stream mutual-nearest pairing,
source-time-offset policy, strict 50 ms speed, six condition definitions,
<=200 ms sequence breaks or recorded-clock causality arithmetic changes.
EDP remains the estimate and RLMB a pseudo-reference. There is no EM/LTSB
substitution, numeric archive, training, file stitching, role, final-data
admission, AWS API or deletion. Both flow modes remain synthetic-only.
All resource limits, including 4 GiB AS, 128 MiB chunks, 8 GiB spool, per-topic
budgets and 6 GiB/10 GiB preflight floors stay fixed.

After exact-head corrective implementation/scope GO and normal CI, authorize
one successor on the **same registered batch03 pilot001 bytes**, into a new
v0.19.7 output directory, following
[`bounded_storage_reader_runbook_v0197.md`](bounded_storage_reader_runbook_v0197.md).
Do not repeat the original audit or prepare/register commands. If it completes,
review actual pair, timing, clock-order and complete-condition sequence support
before implementing generic numeric extraction. If still inconclusive, inspect
the new fixed error category/context; do not automatically retry, re-export,
change caps or declare unusable geometry. A corrupt-frame category warrants
targeted integrity/source evidence only after that result is reconciled.

## Verification and limits

The suite rises from 559 to **576 tests: 574 pass, two existing opt-in skips**
with MCAP extras. All **53 focused tests** pass. Seventeen new tests include
real NONE/ZSTD/LZ4 field/decoded-byte parity, first-yield chunk decompression
count, reversed summary indexes, backward clocks, inner/outer bounds, index/
schema identity, fixed failure privacy, later corruption invalidation/spool
cleanup, valid unknown ZSTD content size and predecessor drift gates.
The real 512 MiB-under-256 MiB isolated memory regression runs with MCAP 1.4.0.
The focused selection also passes with MCAP 1.5.0 selected through an isolated
wheel import path; embedded subprocess tests use the installed 1.4.0 runtime.
Local dependencies are Python 3.12.14, MCAP 1.4.0, protobuf-support 0.5.4,
Protobuf 7.36.2, NumPy 2.3.5, Zstandard 0.25.0 and LZ4 4.4.5. This does not
match all of the owner's versions, and is not a private-file rerun.

Six actual compressed synthetic MCAPs (complete, backward timestamps,
duplicate timestamps, sequence gap, missing confidence, missing odometry)
have byte-identical canonical readiness/scientific extraction output against
the exact merged baseline after removing only the new null context field.
The complete case retains two 21-station -0.5 m profiles and two conditions.
Reproducible scripts/logs accompany the patch ZIP. They use only temporary
synthetic files, establish regression/resource behavior and measure no real
pair count or scientific-model performance.
