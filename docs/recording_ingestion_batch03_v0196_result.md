# Batch03 pilot001: preserved inconclusive readiness

Date: 2026-10-02. This reconciles the owner's first v0.19.6 readiness report;
the private 30 GB raw file is unavailable to this implementation environment.

## Exact lineage

PR #28 is merged at `8d55edf5f4c2ae7d30ce2533f702138319d63270`, tree
`979a446fef8c7bb0df6cb2f12f0701a6f935f260`. The independently reviewed head
was `ef7efb9fe31f764123b77fa41dc4b64f79dbe35d`: Claude GO, zero blockers.
GitHub Actions run `36872777200` passed Python 3.10/3.12, each with 559 tests
and two existing opt-in skips. This closes the pre-run gates in the older
status/runbook; it does not supply GO for the subsequent reader correction.

The returned ZIP contains only `recording_readiness.json`. Its SHA matches
the owner's terminal; the reported source fingerprint matches the merged
package Python files. A stale application or incorrect working directory is
not supported by this evidence.

| Identity | SHA-256 |
|---|---|
| Returned ZIP | `264549408a82ab73f21cf0560d1fe40283eeb62d38ff745bd57eecae37e9d68b` |
| Exact readiness JSON bytes | `55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7` |
| Raw MCAP, 29,961,313,204 bytes | `a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78` |
| Preserved registration | `041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44` |
| Preserved source specification | `c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1` |
| Old runtime source fingerprint | `dfb826fb4a6865c4f784a2d747b0df5c42c999ca8ab082eb3eddf6dc56752b41` |

## What is actually observed

The report is **inconclusive**, exit 3, with failure class **`ZstdError`**.
All decoded geometry, timing, odometry, clock, condition and support fields
are null. They are not zero. No residual archive, role, model or deletion
authorization was produced. Raw SHA equality verifies registered identity,
not integrity against an original authenticated AWS object.

The indexed summary was readable and passed the declared budgets:

| Indexed observation | Advertised value |
|---|---|
| `/adp/estimated_drive_paths` | 36,032 messages; `Adp.Perception.EstimatedDrivePaths`, Protobuf |
| `/adp/road_lane_map_based` | 36,032 messages; `Adp.Perception.Road`, Protobuf |
| `/adp/odometry` | 109,191 messages; `Adp.OdometryState`, Protobuf |
| All topics | 186,441,684 messages |
| Chunk indexes | 116,243 |
| Largest advertised compressed/uncompressed chunk | 2,109,683 bytes |
| Indexed log-time span | Approximately 3,603.359 seconds |

Advertised message/schema presence does not prove supported decoded bindings,
usable geometry, synchronization, causal inputs or residual pairs. Index
descriptor hashes cover the entire `FileDescriptorSet`; they are not the
binding hashes used by the geometry converters. The exact log endpoints stay
in the preserved report; do not reinterpret them as verified UTC acquisition
times or physical-session evidence.

The start readings were 7,936,512,000 MemAvailable bytes and 15,631,355,904
scratch-free bytes, above the unchanged 6 GiB/10 GiB preflight floors.
The CLI still imposed a 4 GiB address-space limit. Reported dependencies were
Python 3.12.3, MCAP 1.4.0, mcap-protobuf-support 0.5.4, Protobuf 7.35.1 and
NumPy 2.5.1. The old report did not record the Zstandard version or native
error category, failing chunk/progress or process-memory snapshot.

## Confirmed bug, unresolved private-file cause

MCAP 1.4.0's seeking reader queues every matching chunk index first. With
`log_time_order=False`, its FIFO expansion appends selected messages behind
the remaining indexes. It therefore retains selected raw message payloads
from every matching chunk before yielding the first message. The same
algorithm is present in the inspected 1.5.0 wheel. The earlier MPR assumption
that this flag alone made reading bounded was wrong; inspecting geometry
object liveness could not detect the upstream raw-payload queue.

A valid synthetic ZSTD MCAP with 128 four-MiB values (512 MiB total) and a
45,046-byte file reproduces the defect under an isolated 256 MiB AS limit:
the exact merged reader raises `MemoryError`, yielding zero messages; the
chunkwise correction completes all 128 under the same limit. This establishes
an implementation defect. It does **not** establish that the private native
`ZstdError` was allocation failure rather than invalid/incomplete compressed
data or another decoder issue. The preserved report lacks that distinction.

Preserve the raw file, registration and failed report. Read
[`bounded_storage_reader_v0197.md`](bounded_storage_reader_v0197.md) for the
narrow correction and separately reviewed, predecessor-gated successor.
Do not raise limits, change topics/horizon, sort timestamps, remerge,
re-register, download a replacement or delete the cache on this evidence.
No negative geometry conclusion and no training decision follows yet.
