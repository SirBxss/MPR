# Independent evaluation of PR #38 implementation review

Date: 2026-10-17. Reviewed owner head `76aa06c7e1626fb7d2f27f35b5286ed155919c9a`,
parent main `acf8c0f3f8257ba24ef43e713df28ca2c2184bb1`, head tree
`6dbf979f6a6485f939c0703b1ba1ed142450ccd8`. The review is substantively correct:
retain NO-GO for a1 until B-1 and M-1 are corrected and the delta reviewed.
This is one corrective commit for the existing PR, not a new contract round.

## Findings and correction

| Finding | Independent assessment and a2 behavior |
|---|---|
| B-1: validator tied to its own release | Confirmed by a failing real synthetic archive regression on a1. Validation first reads a bounded strict, exact-shape/revision, caller-hash-pinned complete summary. Its producer fingerprint, rather than the validator's source, is the second permitted readiness source. Accepted old v0.19.11 readiness stays permitted. The exporter still accepts only old readiness or its own release. There is no CLI/config/environment allowlist. |
| M-1: aliased export parent permits a temporary receipt inside the archive | Confirmed on a1 by trapping temporary-file creation. Containment now uses the canonical export directory and receipt parent before any temporary. The original archive path is retained for direct-symlink rejection; blindly resolving it for all I/O would weaken that existing check. An external receipt through a symlinked ancestor remains supported. |
| O-1: FIFO metadata hangs before regular-file check | Adopted: nonblocking, no-follow, close-on-exec open where supported, followed by the existing descriptor regular-file/state/size checks. A writer-free FIFO subprocess regression has a deadline. This is not a proof against every adversarial filesystem race in inherited parsers. |
| O-2: source can change during execution | Adopted: every late input check also recomputes the process's own source fingerprint, with deadline checkpoints. The initial validator fingerprint may differ from the producer; a change during that validation may not. Late source changes prevent complete publication/receipt installation. |
| O-3: new parent entries need durability | Adopted: sync the output directory and its parent after final marker installation, and the receipt parent after exclusive hard-link installation. Receipt sync failure removes only the unchanged owned receipt. The null-marker path also attempts directory/parent sync. |
| O-4: identify accepted readiness-source case | Documented below without adding a field to the frozen schema. |
| O-5: delivery cache files | New bundles exclude cache directories and bytecode recursively. Old delivered ZIPs stay immutable. Manifest/file-set/CRC checks cover the actual replacement delivery. |
| O-6: stronger numerical fixtures | Added real MCAP rotation/translation with both residual signs and fixed six-feature values, and two supported descriptor versions with two messages apiece. These are regression coverage, not newly discovered scientific defects. |

The source cases are derived in this order: if
`preserved_readiness_runtime_source_sha256` is the fixed accepted `069e109…`,
the case is **accepted v0.19.11**; otherwise it must equal the pinned summary's
`runtime_source_sha256`, the **same export release** case. The validation receipt's
own fingerprint records which implementation checked the archive. A third source
or nonlegacy producer/readiness mismatch remains invalid, even with coherent
predecessor/authorization hash updates. An unpinned/malformed summary is rejected
before it can influence the input loader. The full validator then rechecks the
summary and all existing lineage, policy, audit, NPZ, support and late identities.

A raw-free validator cannot independently reconstruct geometric vectors from
metadata. Coherently replacing vector/feature values and re-pinning every
identity creates a different archive; external consumers must preserve the
original export-time summary digest. This is an explicit trust boundary, not
a reason to claim physical accuracy or raw recomputation. RLMB is a pseudo-reference.
Confidence width and same-major compatibility remain explicit assumptions.

## Original-head CI independently verified

Authenticated full logs from run `39052189376` were fetched, closing the review's
log-access limitation. Both jobs checked out merge
`79ea2c8a24cb6d01ac1d6c35e934f2bd1249ca31`, parents main `acf8c0f` and owner
head `76aa06c`, with the reviewed tree above.

| Job | Python | Exact logged result |
|---|---|---|
| `117452850633` | 3.10.22 | 775 run, 773 passed, two skips, 113.562 s |
| `117452850487` | 3.12.15 | 775 run, 773 passed, two skips, 118.787 s |

This verifies a1, not a2. Focused delta GO, new-head Python 3.10/3.12 CI, then
owner merge are still needed for the numeric correction. No remote write was made.

## Discovery and immediate critical path

The private metadata-only discovery has 33 distinct source IDs/paths: 32 present
unverified files totaling 54,417,501,986 bytes (54.42 GB / 50.68 GiB), one absent.
The present set includes the completed old pilot. None has a discovery raw hash,
verified physical-session link, numeric authorization or model role. Absence is
not evidence of corruption, deletion history or a failed download. Do not infer
33 drives or new-data yield. Keep exact source IDs and paths in private evidence.

Choose the smallest present newer file, excluding the old completed pilot, by
outcome-blind processing cost: 486,691,631 bytes. A private one-attempt launcher
uses already accepted main `acf8c0f` and source `069e109…` to prepare/register,
inventory, decode and run bounded readiness for this file. It can run while
PR #38 receives its delta review. It preserves null unknown session/acquisition/
merged-count evidence, receipts, stage exit codes, immutable predecessors and
raw state; it never generates numeric authorization. It stops at the first
failed stage, refuses an existing attempt/registration, and packages available
evidence without retry or raw deletion. Each existing stage owns its normal
fresh raw verification; this is not a claim of one hash across the whole chain.

Private launcher validation executes actual unmodified accepted CLI/readers,
Protobuf/ZSTD, SQLite science, Git and resource checks on synthetic files.
Complete and unsupported-binding outcomes, wrong-size/repeat guards, paths
containing spaces, raw/predecessor immutability and ZIP/manifest checks pass.
Only fixture Home and expected size differ from the fixed owner configuration.
No private raw or actual newer-data outcome is available in this environment.

The next milestones are (1) accepted numeric correction, (2) newer counts and
one owner-authorized export plus pinned standalone validation, (3) durable
reservation/exposure/session-aware catalog, matched cohort/splits and generic
model archive consumer, then (4) approved real fitting/evaluation under existing
gates. Incremental acquisition and tested raw retirement follow compact validated
outputs; their full automation need not delay the first residuals. Decide how much
to download from complete-feature support, contiguous sequences and evidenced
outings, not GB. Do not rerun old successes or erase old data now.

## Local a2 validation

Python 3.12.14 with the installed MCAP stack: compileall passes; **70 focused
numeric tests pass** (22.870 s); full required suite **788 run, 786 passed,
two unchanged opt-in skips** (158.191 s). Thirteen new regressions explain the
increase from 775. The two a1 B-1/M-1 reproduction failures were retained before
fixing code. Diff/file-link checks pass, and the five scientific-file hashes and
complete seven-use/four-definition admission surface pass their existing pins.
These are synthetic local checks, not new-head hosted CI or a private data result.
