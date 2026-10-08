# Batch03 pilot001: completed registered-file inventory

Date: 2026-10-08. This reconciles the returned metadata-only inventory after
PR #31. The private MCAP is unavailable in this environment; raw verification
and resource observations are reported by the owner's execution, cross-checked
against the merged implementation and preserved evidence.

## Decision and exact lineage

Accept the returned artifact as **complete registered-file summary inventory**,
not decoded readiness or a residual dataset. There is no discrepancy with the
older metadata evidence. Do not repeat this inventory or registration.

PR #31 merged as `05e0c71f93f8133204f6b5577f5ca69662f647fc`, tree
`b44bbc4f18fc68a5a7f0ec8875f9a4f5b3feab7e`. The reviewed head was
`296e16146fe214d29af22133f5b5499abb36354c`; Claude returned GO/zero blockers.
Codex separately checked Actions run
[37749442988](https://github.com/SirBxss/MPR/actions/runs/37749442988): Python
3.12 job `113218780001` and Python 3.10 job `113218780274` both passed,
each 606 run/604 pass/two existing optional skips. The jobs checked out
GitHub's temporary merge `63bdfba` of that exact head into `c8a7572`;
they did not check out the feature head directly. The actual merge has the
same tree as the delivered and reviewed patch.

| Artifact / identity | SHA-256 or value |
|---|---|
| Returned result ZIP | `462126c2dc8ea0ae84e583176493b7236d3bc840bf2901ba21696d703fec10ba` |
| Exact `recording_inventory.json` bytes | `53932550e4fe2233c2bac33c0778b9549e9ab5bee83822dca225b98d4df41784` |
| Raw MCAP, 29,961,313,204 bytes | `a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78` |
| Preserved registration | `041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44` |
| Preserved source specification | `c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1` |
| Preserved original readiness JSON | `55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7` |
| Runtime Python-source fingerprint | `4819865d7305b5775693c2c12d6d4d51f16c0fece07f395d2cd9cb3017908401` |
| Contract | `v0.19.8-registered-mcap-inventory-2026-10-08-a1` |
| Technical identity | `batch03_aws_pilot001 / pilot_001` |

The ZIP contains exactly `recording_inventory.json` and
`inventory_run_receipt.json`. Its receipt names the actual merge commit and
its report hash matches the exact enclosed bytes. The returned source
fingerprint independently matches all merged package Python files. The
registration/specification/raw identity matches the original readiness report;
the owner's terminal reports all three small-file hashes passing before and
after execution, exit 0. No raw verification was repeated here.

The run reports Python 3.12.3, MCAP 1.4.0, mcap-protobuf-support 0.5.4,
Protobuf 7.35.1 and NumPy 2.5.1. Starting MemAvailable was 8,815,075,328 bytes
and scratch-free space 55,576,772,608 bytes, above the unchanged 6 GiB/10 GiB
floors; the process address-space limit remained 4 GiB. This new resource
success does not determine the cause of the old ZstdError.

## What the report actually establishes

| Advertised summary observation | Value |
|---|---:|
| Channels / distinct topics | 506 / 506 |
| Schemas | 448 |
| Total messages | 186,441,684 |
| `/log` messages | 160,423,668 |
| Non-`/log` messages, by subtraction | 26,018,016 |
| Chunk indexes | 116,243 |
| Summary plus summary-offset bytes | 237,099,566 |
| Chunk-index group bytes | 223,985,601 |
| Largest compressed chunk payload | 964,816 bytes |
| Largest complete chunk record | 964,869 bytes |
| Largest uncompressed chunk | 2,109,683 bytes |
| Compression categories | All indexed chunks advertise Zstandard |
| Nonzero summary CRC | Validated |
| Metadata indexes / attachments | 12 / 0 |

The summary log-endpoint difference is 3,603.358964128 seconds, approximately
60.06 minutes. This is an **advertised log-time span**, not verified acquisition
UTC, continuous driving time or a physical-session declaration. The MCAP is
one technical recording; the claimed 180 merged inputs are not 180 outings.
`independent_outing_count` remains null, and the physical-session/source-locator/
redownload-evidence flags remain false in this preserved registration.

All channels and schemas advertise Protobuf. Each topic has one channel here;
future files may have several. All 506 channel-metadata maps are empty.
Header-library presence/hash does not establish the recorded producer build.
The 12 file-level metadata records were not inspected. Exact log endpoints
and the header-library hash exist in the reviewer ZIP; do not reproduce those
values in public result documentation or post the ZIP publicly by default.

| Selected recorded topic | Advertised messages | Recorded schema root |
|---|---:|---|
| `/adp/estimated_drive_paths` | 36,032 | `Adp.Perception.EstimatedDrivePaths` |
| `/adp/road_lane_map_based` | 36,032 | `Adp.Perception.Road` |
| `/adp/odometry` | 109,191 | `Adp.OdometryState` |
| `/adp/position_on_map_pose_estimate` | 36,032 | `Adp.Localization.PositionOnMap.PoseEstimateFrame` |
| `/adp/foresight_lane_data_opb` | 3,602 | `Adp.Map.ForesightLaneData` |
| `/adp/foresight_projection_enu_coord_frame` | 3,602 | `Adp.Map.EnuCoordFrame` |
| Each of foresight MPP best-lanes / lanes-on-links / links | 36,032 | Previously inspected corresponding MPP root |
| `/adp/lane_topology_sensor_based` | 36,032 | `Adp.Perception.Road` |
| `/adp/lane_topology_map_based` | 36,032 | `Adp.Perception.Road` |

The three existing EDP/RLMB/odometry streams advertise 181,255 messages in
total. These are not residual rows. Equal EDP/RLMB counts do not prove pairing,
valid paths, a common origin, compatible geometry epochs or H100 support.
Pose/foresight/topic presence likewise proves no better independent reference.
Other recorded topics, including RT3000/GNSS streams, are availability leads;
their names alone establish neither lane truth nor independent calibrated pose.

## Reconciliation and withheld conclusions

The older `provenance_metadata.json` hash is
`20c8a25803d317f4452ae1bb6bd95c815757434d73ee8bc58163b8c7f53fcc5f`.
All 506 channel IDs/topic/encoding/schema associations and all 448 schema
IDs/root names/encodings/descriptor sizes/hashes match this new inventory.
The older `recorded_metadata.json` hash is
`8b797a3efc5866fc067cdd596610d4cc7ac3f6621e8bcea6d623fbafcb505c9a`.
All 38 selected channel/schema/count rows and all 38 descriptor hashes match.
Summing the new advertised channel counts gives the advertised total exactly.
No mismatch was found. Schema IDs are local identities, not generic bindings.

This new run adds fresh registered-byte verification, nonzero summary CRC
validation and bounded full chunk-index aggregation to the older one-off
metadata evidence. The old report's compressed/uncompressed maximum combined
the two; the new result distinguishes them. No earlier report is rewritten.

No message chunk was decompressed by this workflow. Selected chunk CRCs,
payload well-formedness, global index order/uniqueness and data-section CRC
are not established. The original ZstdError remains unresolved. The complete
inventory and its small advertised chunks do not prove that native decoding,
schema conversion, geometry alignment or residual extraction will complete.
All scientific-action flags remain false.

Local result-closure verification: strict JSON/ZIP member CRCs, exact member
set, receipt/report hash and source-fingerprint checks pass; source compilation
and whitespace checks pass. The unchanged full suite ran 606 tests in 66.540 s,
604 pass/two existing optional skips. No new test or executable source change
was introduced for this documentation reconciliation.

## Next implementation: selected-stream decodability before geometry

Keep the immediate task in generic input infrastructure. The smallest useful
next stage is a **target-independent selected-stream decoding check**, starting
with the recorded EDP/RLMB/odometry topics. It answers whether the indexed
selected chunks decompress, their available nonzero CRCs validate, embedded
schemas resolve, selected payloads decode and observed counts reconcile with
the inventory. It performs no residual arithmetic or topology acceptance;
decoding EDP messages does not adopt an all-topology scientific population.

The new command/output contract is not yet implemented or frozen. Before
private execution, specify predecessor lineage, explicit topic selection,
per-topic and total message budgets, time/record/chunk/index-memory limits,
CRC checked/unavailable counters, per-schema counts and fail-closed publication.
Retain one fresh raw hash/open descriptor, immutable input checks, new output
paths, the existing resource policy and no automatic retry. Partial failures
must not publish prefix counts as full-recording observations.

Inspect retained **index** memory as well as payload memory before selecting
the adapter. `IndexedStorageReader` fixes the FIFO payload queue but still
inherits `SeekingReader.get_summary()`, which materializes all chunk indexes
and their channel-offset dictionaries. The successful v0.19.8 inventory
avoids that materialization; its success is not a memory bound for the old
decoder. This is a verified code property, not a new reproduction of the
private error. Use a synthetic index-shape check and the smallest justified
bounded-reader change if needed; do not raise the process cap or speculate
that the raw file is corrupt.

Synthetic verification and focused implementation GO/normal CI must precede
one new private decoding check. Preserve the successful inventory and both
old readiness outcomes. Do not instruct the owner to execute the old deferred
readiness step 6 simply because memory now passes. The separate native-reference
proposal still needs its own contract review; no reference construction,
covariance correction, target adoption, generic numeric export, real fit or
raw retirement follows from this result.

## PR #31 nonblocking review follow-up

Carry forward N1 (reviewer ZIP log endpoints/library hash), N2 (unsupported
partial-summary codes must not automatically be called corruption), N4
(additional direct malformed-summary regressions), N5 (import-surface cleanup),
N6 (resource floors), N7 (reviewed empty-scratch recovery), N8 (first failure
context), N9 (explicit tree-mismatch stop) and N10 (transient string-map memory).
These did not block PR #31 and none is evidence of a defect in this result.
Do not lower floors, delete recovery directories or refactor imports merely
to clear nonblocking findings.

Clarify N3 rather than change the parser: the current primary
[MCAP specification](https://mcap.dev/spec#records) explicitly exempts Message,
DataEnd and Footer from record extension. Fixed DataEnd/Footer lengths are
consistent with that specification; the review's suggested future DataEnd
extension is not a currently supported MCAP compatibility requirement.
