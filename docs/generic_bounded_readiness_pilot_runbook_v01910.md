# Post-merge bounded readiness pilot: v0.19.10

Date: 2026-10-15. PR #35 is merged at `4cf0af3`, exact accepted a2 tree
`f435f2bf8e26d1e3dc114bb50b10b7ff4cc83501`. Independent GO and both exact-
head CI logs are verified (703 tests/two existing skips per Python 3.10/3.12).
This is the post-merge counts-only successor, not the old deferred audit.
No private scientific result exists in the agent environment yet.

## Owner execution

A source-specific launcher is delivered privately, outside Git. Its pinned
registration/specification/inventory/decode hashes are taken from the owner's
preserved successful evidence. It selects and fast-forwards main, verifies the
exact merge/tree and refuses dirty/unexpected source. It checks JSON identity,
raw path/size and dependencies without hashing raw itself; the merged command
owns the single fresh raw hash, summary, selected decode and scientific work.
It neither reinstalls dependencies nor reruns registration/inventory/decode.

The actual entry point is:

```bash
python -m lane_residuals.cli.recording_ingestion bounded-readiness \
  --registration-directory "$MPR_REGISTRATION_DIR" \
  --preserved-inventory-report "$MPR_INVENTORY_REPORT" \
  --preserved-decode-report "$MPR_DECODE_REPORT" \
  --scratch-directory "$MPR_LOCAL_SCRATCH" \
  --output-directory "$MPR_FRESH_OUTPUT_DIR" \
  --topic /adp/estimated_drive_paths \
  --topic /adp/road_lane_map_based \
  --topic /adp/odometry
```

The variable names above are descriptive inputs, not additional discovery or
fallback behavior. Use the privately pinned launcher for the authorized pilot.
It requires the existing project virtual environment and standard Bash/Python
facilities, uses one BLAS/OpenMP thread, reserves fresh mode-700 scratch beneath
`/var/tmp`, checks 6 GiB MemAvailable and 18.5 GiB initial free scratch, and
retains the implementation's 10 GiB runtime floor/4 GiB process cap/deadline.
Scratch must be outside sync/backup activity; the unexpected-file guard stays.

The launcher reserves one private attempt directory under `outputs/run_receipts/`
and refuses existing output/attempt/result paths. This prevents accidental
repeat or overwrite. An exit-2 or interrupted attempt is retained for review;
no automatic retry or raw cleanup is performed. Before-attempt preflight stops
print a reason; no raw hash has run in those stops.

## Evidence returned

The private result ZIP contains the exact bounded JSON when published, a run
receipt, preflight/resource metadata, log, launcher copy, preserved predecessor
JSON snapshots and `SHA256SUMS`. It contains no raw MCAP. The receipt records
actual command exit code, source identity, timestamps, input immutability,
report digest/lineage and scratch path. Keep these private rather than pushing
source paths/identities to Git. Return the ZIP; on a preflight stop return the
terminal message. Preserve raw paths and every prior result.

A complete report remains counts-only. Exit 0 can include measured zero
geometry/conditions, or complete geometry with unavailable odometry; do not
infer complete-feature availability from exit code alone. Exit 3 is incomplete
or unsupported science/execution, with null observations rather than zero.
Exit 2 has no completed bounded report; receipts/logs still matter. The command
continues to enforce full-stream pairing before filtering and fixed geometry,
source admission, confidence/speed causality and sequence rules.

## Validation and limits

The private launcher was executed against real synthetic ZSTD MCAPs through
the exact merged CLI, without mocking decoding, geometry, resources or git.
Complete exit 0 and unsupported-binding exit 3 were packaged; result manifests,
input/raw immutability, branch selection from a feature branch, paths containing
spaces, repeat/overwrite rejection, dirty-work preservation and wrong-predecessor
rejection passed. Only synthetic identity constants and a dedicated test-home
variable differed from the owner launcher. The first fixture attempt stopped
because its symlinked test virtual environment was unignored; the test-only
exclude was corrected. No production launcher change or private run resulted.

The real private inventory/decode bytes also passed the merged metadata-only
predecessor parser using their reconciled identity fields and matching unknown
source declarations. This did not read the unavailable registration file or raw
MCAP and does not prove actual private descriptor compatibility. Existing exact-
source suite/CI evidence is sufficient; no new full suite/benchmark was rerun.
Two-point staging evidence does not establish realistic private deadline adequacy.

## Next data work

Review the returned per-version bindings; topology, pairing, H100/anchor/SENSOR
attrition; odometry availability; complete six-feature rows; sequence lengths,
transitions and phase timings. Distinguish unsupported/unknown from measured
zero, and geometry-only yield from the complete-condition subset.

If the evidence is complete, implement generic numeric export and strict archive
validation with the existing target/features and lineage. Then process additional
outcome-blind samples from evidenced separate physical sessions incrementally,
freeze the matched cohort/splits under the existing protocol and satisfy the
relevant model/data gates before real fitting. Keep flow modes synthetic-only
until their real-training gates are met. Do not use GB, file/job counts or the
SENSOR enum alone as proof of useful independent model data or physical truth.
A private catalogue and tested retrieval/archive gates precede raw retirement.
