# Batch03 pilot001: v0.19.7 memory preflight stop

Date: 2026-10-03. Evidence is the owner's pasted terminal output, reconciled
against the merged source. There is no new readiness JSON to reconcile.

## Implementation and execution identity

- PR #29 is merged as `fc6d5ff72c5812d43367897cc92416fd870e2686`.
- Final feature head: `fe97561a3cfe6c727b16c56d661c21d551ae7aa6`.
- Merge and final feature trees: `fea8e02b7bfd4f05a038de2d3efe192bc852eed7`,
  identical to the delivered readiness CRC correction.
- Owner reports Claude delta GO; that delta review file was not supplied in
  this turn. Do not describe it as independently reread here.
- Actions run `37002940067` was independently checked: Python 3.10/3.12 jobs
  `110824560020` / `110824559813` succeeded at the final feature head, including
  package/MCAP installation, compilation and unit tests.
- Both CI logs report 579 tests with two existing opt-in skips, MCAP 1.5.0;
  Python 3.12 took 96.151 s, Python 3.10 took 94.964 s.
- Owner's post-merge focused suite: 56 tests, all passed, 4.850 seconds.
- The registration, source-specification and old v0.19.6 readiness hashes all
  passed the runbook's checks. Preserved pilot identity/path/size checks passed.

## Observed host state and outcome

| Observation | Reported value | Existing requirement |
|---|---:|---:|
| Total physical RAM | 31 GiB | Not the admission quantity |
| Available RAM | 4.5 GiB | At least 6 GiB |
| Free RAM | 489 MiB | Not the admission quantity |
| Swap free | 1.1 MiB of 2 GiB | Does not count as available RAM |
| Disk free on repository filesystem | 53 GiB | At least 10 GiB free scratch |
| CLI error | `available_memory_below_6gib` | Fail before data processing |
| Exit status | 2 | No completed audit |

The memory requirement is exactly `6 * 1024**3` bytes, obtained from Linux
`/proc/meminfo:MemAvailable`, not rounded `free -h` text. The disk snapshot
is comfortably above the scratch threshold on this filesystem. This attempt
stopped on memory. A different scratch filesystem would need its own check.

In `workflows.recording_ingestion.run_readiness`, the initial `_resources`
check occurs after registration/predecessor validation but before raw hashing,
indexed metadata inspection, decoder iteration, geometry spooling and report
publication. `_new_output` checks absence without creating the output.
An additional synthetic reproduction at 4.5 GiB RAM/53 GiB disk confirms
that raw hashing, index inspection and readiness decoding are not called,
output stays absent and an already prepared empty scratch stays empty.
The CLI catches the preflight exception and returns 2. The preceding shell
block creates the scratch directory, so it can leave an **empty** scratch
directory even though no data was processed. Neither private directory state
nor private host memory can be independently inspected from this workspace.

This is a host-resource stop, not a new MCAP corruption result, zero-pair
finding, decoder regression or failed geometry test. It does not resolve the
original v0.19.6 `ZstdError`. There are no new decoded observations to label
zero or null in a report: **no new report exists from this invocation**.

## Disposition

The owner stopped correctly. Keep the original failed report, registration
and raw MCAP unchanged. The engineering investigation is documented; private
data feasibility remains unresolved. The successor is deferred while the
prospective reference-source study is prioritized. No automatic retry, new
registration, threshold reduction, cache purge, swap reset or raw deletion.

Use the read-only state/memory block in
`reference_redesign_runbook_20261003.md`. Save work and close unused
memory-heavy applications, then measure again; an 8--10 GiB available margin
is helpful operationally, not a new scientific or admission threshold.
Linux's available-memory estimate already considers reclaimable cache; do not
add `buff/cache` to it or treat deleting disk files as freeing active RAM.
Kernel reference: <https://docs.kernel.org/filesystems/proc.html>, `MemAvailable`.

If the old readiness question is deliberately resumed later, an empty
scratch directory may be reused without deleting it, provided the successor
output is still absent and no process is using that scratch. A nonempty
scratch directory or any successor output requires inspection first. The
complete deferred-recovery instructions are in the new runbook. A preflight
stop before raw processing is not a completed decoded successor. Once actual
processing produces a report or fails later, reconcile that evidence before
any additional run.

The prospective all-topology EDP/reference study is separate; read
`reference_redesign_investigation_20261003.md`. Existing SENSOR-only extraction
and admission rules remain unchanged in code and preserved outputs.
