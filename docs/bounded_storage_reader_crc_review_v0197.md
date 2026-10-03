# PR #29 review closure and readiness CRC amendment

Date: 2026-10-02. PR #29 is open at reviewed head
`33f9542ffa835ded9d45c562528862506c1e91af`, tree
`7682cd3c5df0ae339d98d5a58fcbd6bcf0c89926`, against main
`8d55edf5f4c2ae7d30ce2533f702138319d63270`.

## Accepted original review and separately verified CI

The supplied independent Claude review returns **GO, zero blockers**, for
the original engineering scope. Its exact file SHA-256 is
`2c7bb53023bd152cc9cb11345e580f8f614167786183553de95cf2b1a712e0f7`.
The reviewer independently verified the upstream FIFO defect, one-chunk
retention, message/decoded-byte parity on MCAP 1.4.0/1.5.0, scientific
output parity, optional imports, predecessor lineage and runbook guards.
The review's extra fixtures/RSS measurements are independent reviewer
evidence, not private-file measurements or this agent's local runs.

CI was unverified in the review. This session checked
[Actions run 36997429154](https://github.com/SirBxss/MPR/actions/runs/36997429154)
at that exact head. Python 3.10 job `110807249837` and Python 3.12 job
`110807249706` both passed dependency installation, compileall and tests.
Both logs have **576 run, OK (skipped=2)**, with MCAP 1.5.0 installed and
temporary test merge `860deb7` of the reviewed head into its unchanged base.
The owner's 576-test/53-focused runs agree. PR #29 remains unmerged.

## R1: adopted before the single private successor

R1 is priority 1, **nonblocking**. The reviewer allowed either checksum
validation or an explicit integrity limitation. We adopt validation before
the expensive single successor because a concrete valid-Protobuf corruption
was demonstrated; we do not pretend R1 was an external blocking verdict.

The reviewed default did not validate chunk CRCs. A single compressed bit
can silently change valid confidence values while preserving record headers,
message counts and usable geometry. Our own six-frame fixture gives complete
readiness with six sensor/condition frames at the reviewed source; the CRC
amendment gives **inconclusive CRCValidationError**, a chunk-decompression
context and all scientific observations null. Prefix evidence is discarded
and temporary geometry is cleaned up. This identifies an engineering
integrity limitation, not the private native ZstdError's unresolved cause.

Small implementation delta:

- `_iter_messages` adds keyword `validate_crcs=False` and forwards it to the
  existing indexed reader. Historical batch02 defaults are unchanged.
- Only `inspect_recording_readiness` opts into True. The existing MCAP
  decompressor checks stored nonzero uncompressed chunk CRCs before yield.
- The readiness report records `selected_chunk_crc_validation_enabled: true`
  as a policy flag. Registration/specification, raw bytes and previous JSON
  are unchanged. No CLI bypass or new private path is introduced.

[The MCAP specification](https://mcap.dev/spec#chunk-op0x06) defines zero
`uncompressed_crc` as unavailable. Such chunks remain valid and are not
rejected merely for absent checksums. CRC verification here covers chunks
read for selected topics (including all records within those chunks), not
skipped chunks, attachments, full data-section integrity or authenticity
against a trusted original AWS/export object. We do not measure CRC coverage
or claim complete file integrity. A raw SHA proves unchanged registered
bytes; it does not prove an authenticated original was undamaged.

Every geometry/schema/station/target/alignment/pairing/feature/causality/
sequence rule and resource limit is unchanged. No domain, model, archive,
batch02 workflow or dependency bound changes. No private raw execution,
numeric export, fit, outing role, final-data admission or deletion follows.

## Other recommendations and verification

N4 is adopted: run the **56** focused tests again after merge/dependency
installation before the private successor. N5 is documented: an external
kill may leave a private temporary spool; preserve evidence, and scope any
manual cleanup plan to that spool. No automatic cleanup/retry is added.
N6 is closed for the original head by this exact review/CI checkpoint.
N1–N3 are deferred: no speculative LZ4 refactor, stronger predecessor shape
gate or dependency-range change is part of this ZSTD-pilot CRC delta.
N7's different synthetic compressed file size reflects different fixture
contents/writers; neither fixture size identifies the private MCAP.

Local Python 3.12.14 with MCAP extras: **579 run, 577 pass, two existing
opt-in skips; 56 focused pass**. Three new actual-container tests cover the
silent compressed confidence mutation, unchanged healthy readiness and CRC
0 limitations. The focused import-path selection also passes with MCAP
1.5.0; embedded subprocess tests use installed 1.4.0. Compileall and whitespace
checks pass. The old GO/CI does not approve the new delta: push it to the
same PR #29, require exact-new-head delta GO and both CI jobs, then merge.

Read [`bounded_storage_reader_crc_runbook_v0197.md`](bounded_storage_reader_crc_runbook_v0197.md)
for the complete apply/test/push/Claude/merge/audit/result steps. The original
30 GB registered bytes and predecessor report remain unchanged. No private
successor has run in this environment.
