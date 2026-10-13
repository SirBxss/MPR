# Batch03 pilot001: accepted selected-stream decode check

Date: 2026-10-09. This is a documentation-only reconciliation of the owner's
one completed v0.19.9 run. The private MCAP is unavailable here. Fresh raw
hashing, chunk inspection and resources are reported by that execution and
cross-checked against the exact merged source, preserved reports and receipt;
the agent did not repeat the private scan or independently recover raw bytes.

## Decision and repository lineage

Accept the report as **complete selected indexed-stream decoding**, exit 0.
There is no reason to rerun registration, inventory or decoding for this pilot.
This clears its generic decoding gate, not geometry or model-data eligibility.

PR [#32](https://github.com/SirBxss/MPR/pull/32) merged as
`85cd9d6fef920bd8f347c471c14f520835ef2b24`, tree
`1d6b997bb7ff26e10d3172cc47a4dad9293f1c48`. Claude's full supplied review,
`MPR_v0.19.9_PR32_selected_stream_decode_check_review_92120f7.md`, gives
GO/zero blockers for head `92120f7d08e0cb41446a67199227516ed1057537`, with
the same tree. The review is private evidence, not copied into the repository.

Codex independently read [Actions run 37795138166](https://github.com/SirBxss/MPR/actions/runs/37795138166)
and both actual job logs. Python 3.12 job `113372512080` ran 650 tests in
63.959 s; Python 3.10 job `113372512343` ran 650 in 79.620 s. Both passed
648 with the same two opt-in skips. Their checkout is GitHub temporary merge
`c39ad015037a8586acf6b062cb3a58d01641db2a`, parents `05e0c71`/`92120f7`,
with the same tree as the actual merge. This resolves the reviewer's CI-log
access limitation; it is not described as a direct feature-head checkout.

The owner's post-merge 44 focused tests passed in 4.409 s. All four preserved
small-file SHA guards passed before and after the run. The terminal says
fresh raw verification, disk-backed selected decoding and exit 0. The receipt
names the actual merge and binds the exact enclosed report bytes.

| Artifact / identity | SHA-256 or value |
|---|---|
| Returned result ZIP | `c34b1077531c4c79fac46629d49e91fcf65a8dcb964b3832a0d3f78a5ef4d296` |
| Exact `recording_decode_check.json` | `05026e239d7b9679719147529fd153bdde7244b584df3c9c22fac7301ebf3bb5` |
| Exact `decode_run_receipt.json` | `e1b91536d426675d5cac3a1f32600afbe0a0d44bef6a2325ac55730bd5d40466` |
| Preserved complete inventory | `53932550e4fe2233c2bac33c0778b9549e9ab5bee83822dca225b98d4df41784` |
| Preserved original readiness | `55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7` |
| Registration | `041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44` |
| Source specification | `c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1` |
| Raw MCAP, 29,961,313,204 bytes | `a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78` |
| Runtime Python-source fingerprint | `0cfbd7885fb3543190a5939951f268f6dfc8202a0ab68a806041e40c687878e8` |
| Contract | `v0.19.9-selected-stream-decode-check-2026-10-08-a1` |
| Reader | `v0.19.9-disk-index-selected-chunks-a1` |
| Technical identity | `batch03_aws_pilot001 / pilot_001` |

The ZIP contains exactly the two named JSON members. Member CRCs, strict JSON
without duplicate keys/nonfinite constants, exact report/row/count key sets,
receipt binding, dependency identities, source fingerprint and count arithmetic
pass local reconciliation. The selected channel bindings, counts and descriptor
hashes exactly match the preserved inventory. Raw size/hash and declaration
flags also match the original readiness. No private path, source identifier,
coordinate or exact epoch is reproduced in this public documentation.

## What the complete report proves

| Selected topic | Advertised = decoded messages | Recorded root | Channel / schema |
|---|---:|---|---|
| `/adp/estimated_drive_paths` | 36,032 | `Adp.Perception.EstimatedDrivePaths` | 268 / 234 |
| `/adp/road_lane_map_based` | 36,032 | `Adp.Perception.Road` | 405 / 195 |
| `/adp/odometry` | 109,191 | `Adp.OdometryState` | 100 / 92 |
| Total selected messages | 181,255 | Three embedded Protobuf roots | Three channel/schema versions |

These IDs are file-local audit identities, not bindings to reuse in new files.
Each selected topic has exactly one observed schema/channel version here.

| Selected-index execution observation | Value |
|---|---:|
| All indexed chunks | 116,243 |
| Selected indexed chunks = completed chunks | 103,409 |
| Skipped indexed chunks | 12,834 |
| Selected chunks with nonzero CRC checked successfully | 103,409 |
| Selected chunks with unavailable zero CRC | 0 |
| Selected chunks without channel indexes | 0 |
| Cumulative selected payload bytes processed | 4,329,760,104 |
| Nonzero summary CRC | Validated |
| Index ranges / unique offsets | Validated |
| Summary index listing already in physical order | True |
| Failure / first-failure context | Null / null |
| Later invalidation codes | None |

Processed payload bytes are cumulative, not simultaneously retained data,
an exported numeric dataset or a peak-memory measurement. The selected chunk
CRCs cover the chunks actually inspected, including their mixed uncompressed
contents, but only selected message payloads were decoded. The other 12,834
indexed chunks were skipped; their payload/header/CRC validity is not proved.
Message Index contents, DataEnd CRC, omitted/out-of-index messages, attachments
and metadata values are not independently exhaustively audited. Fresh SHA
checks identity, not authenticity. Do not call this whole-file certification.

The report records Python 3.12.3, MCAP 1.4.0, mcap-protobuf-support 0.5.4,
Protobuf 7.35.1, NumPy 2.5.1, Zstandard 0.25.0 and LZ4 4.4.5. Starting
MemAvailable was 7,797,071,872 bytes (about 7.26 GiB), scratch free
55,853,977,600 bytes (about 52.02 GiB). Both pass the unchanged 6 GiB/10 GiB
floors; address-space soft limit is 4 GiB. No elapsed scan time or peak RSS is
provided in the returned report; do not infer either from this snapshot.

## Interpretation and withheld conclusions

The same registered raw identity now completes selected indexed decoding
under the new bounded reader. The original readiness ZstdError no longer
blocks this consumer. This does not determine the historical error's cause
or prove that the old reader would now finish. The reviewer's old summary
reader completed at the production 4 GiB cap with about 2.04 GiB RSS; its
failure under a much smaller synthetic 256 MiB cap proves a retention
difference only. No claim that memory caused the private ZstdError is made.

The report does **not** inspect topology frequencies, qualifier/error states,
finite clothoids, unambiguous lane chains, H100 span, common path origins,
frames/geometry epochs, estimate-reference time matching, causal six-feature
availability or contiguous sequence support. It constructs no residuals.
The 36,032 EDP messages are the starting message denominator, not confirmed
eligible profiles. Equal EDP/RLMB counts do not imply valid one-to-one pairs.
H100 eligibility and feature support are unknown, not zero.

All seven scientific/deletion flags are false; independent-outing count is
null. This is one technical recording with a declared 180 merged input MCAPs,
not proof of one physical outing or 180 independent drives. Physical-session
evidence, acquisition UTC, source locator/recording identifier and redownload
evidence remain undeclared. Do not overwrite registration to invent those
facts. For future data record truthful evidence prospectively before outcomes.

EDP remains the estimate candidate. RLMB is a correlated map-relative
pseudo-reference, not physical ground truth. Decode success does not adopt
all-topology EDP, establish sensor independence or validate a pose/foresight
reference. The latter proposal remains draft; both flow modes remain
synthetic-only. Preserve all old SENSOR archives, six features, sign/H100 and
no-extrapolation rules. No real fit, cohort lock or raw deletion follows.

## Review follow-up and next owner action

Claude's eight findings are nonblocking: earlier metadata-only selected-topic
rejection; clearer bounded-reader failure labels; explicit codec dependency
floors/preflight; SQLite temporary-file policy; old-reader production-cap
evidence; visible README guard failures; shared-helper import separation; and
duplicate-channel metadata comparison coverage. Preserve them as future narrow
work, not a reason to repeat this completed run or refactor speculatively.
The focused tests precede any new scan and exercise codec compatibility;
this owner's actual codec versions and run completed. No finding is closed by
claiming a patch that was not implemented.

The next task is the contract in `generic_pipeline_continuation_20261009.md`:
bounded generic semantic/geometry readiness using the reviewed I/O and existing
scientific arithmetic, with explicit attrition denominators and no new target
adoption. Export, target/population amendment, matched-data training and raw
retirement follow their own reviewed evidence. Do not execute old deferred
readiness or repeat successful pilot commands. This result closure adds only
documentation; follow its delivered README for apply/test/PR, not a data run.

Local closure verification: strict artifact/receipt/predecessor/schema/source
reconciliation, source compilation and whitespace checks pass. The unchanged
full suite ran 650 tests in 71.095 s on Python 3.12.14/MCAP 1.5.0: 648 pass,
two unchanged opt-in skips. No executable source, test, configuration or output
contract is changed. The documentation head still needs owner-applied CI;
the passing PR #32 implementation CI is not relabelled as new-head CI.
