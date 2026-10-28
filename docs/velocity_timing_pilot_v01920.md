# v0.19.20 bounded direct-velocity timing pilot

Current status: the independently approved a2 operation completed after actual
reviewed-head CI and owner merge. Its first exit-zero return is accepted by
raw-free receipt/source/input and complete analysis replay. Read the
[completion/next boundary](velocity_timing_result_20261026.md). The completed
design must not be rerun. This document preserves the original approved policy;
the post-hoc strict-prior-log hypothesis has not amended that policy or adopted
a feature/dataset. Observed VehicleVelocity timestamps differ from the interface
comment; retain that distinction and do not rewrite payloads to fit the comment.
All pending-operation/apply text below is historical preparation provenance.

Historical status: a2 implementation candidate after independent review. A1 exact-head CI
passed, but the local exclusion predicate and combined-mask legend needed
correction. A2 requires focused source/private-packet GO and new-head CI. No BMW
payload pilot or new fit has run. Read `velocity_timing_a2_review_20261026.md`.
The v0.19.19 summary return is technically verified; its source/review/CI/merge
prerequisite closure was not established. Preserve it and record that deviation.
Never rerun it to create a different operational history. The new source gate
fixes the missing enforcement prospectively, before any new raw access.

## Scientific scope

Inspect one development recording and one fixed 12-second log-time interval in
its earliest geometry run that spans at least 12 seconds in both source and log
time. The run must have consecutive estimate/pair indices, increasing source
time with gaps at most 200 ms, monotonic log time and available residual geometry.
Original geometry exclusions break runs. Selection uses cached geometry only,
never direct-speed values, old speed validity or model scores. The first short
geometry segment is not long enough; choosing a sustained segment prevents an
otherwise uninformative pilot. Decode the interval plus one second on each side.

Use both `/adp/velocity_vehicle_longitudinal` and `/adp/vehicle_velocity` in one
indexed selected-chunk pass. Reuse the immutable numeric export, audit and old
speed values. Do not decode EDP/RLMB/odometry again or construct new residuals.
Do not expose final outings, change role assignments, transform/fit a model,
export new training X/Y arrays, adopt a speed definition or sweep all outings.

### Established descriptor evidence

The scalar longitudinal root has value, generic qualifier and timestamp fields.
Its generic valid qualifier is 1; its timestamp description is interface
creation in nanoseconds. Topic-specific units, sign, reference point and deployed
clock/measurement-age semantics still need evidence. Existing consumer policy
alone cannot establish them. The generic message also represents other quantities.

VehicleVelocity contains a qualified nested value, a distinct outer qualifier
and standstill status. Its interface describes absolute COG speed with lateral
and longitudinal components; it warns that the nested timestamp lacks platform
information and is always zero. Verify actual decoded values rather than turn
that annotation into an observed all-zero result. This topic is a comparison
signal, not an adopted replacement. No log/publish/sibling timestamp substitution
is allowed. Do not mix the inner/outer/odometry qualifier enums.

Ordinary proto3 scalar defaults do not identify missing wire fields. Preserve
decoded zero timestamps and non-default decoded-field names without claiming wire
presence. Zero speed can be standstill. Nested message presence is checked with
HasField. Neither absence nor a scalar default may be interpreted conveniently
to improve coverage.

### Exploratory recorded-clock screen

For each original candidate frame, choose the latest decoded update whose log
time is at or before the cached EDP log time. A tie between multiple updates at
that latest log time is ambiguous and fails the screen; physical storage order
does not resolve availability order. Never search backward for a valid sample
after the latest update fails. Require its inner generic qualifier 1, finite
native value, positive source timestamp no later than EDP source time, and source
age at most **100 ms**. Require positive publish time no later than EDP publish
time. Keep all comparisons in integer nanoseconds, including values above 2^53.
Report log ties to EDP explicitly.

The fixed 100 ms threshold is an exploratory engineering screen covering a few
nominal update cycles, not an adopted physical freshness bound or an optimized
hyperparameter. No threshold sweep or offset fitting is included. Source/log/
publish clock comparability and physical input availability remain unproven.
The term `recorded_clock_screen_met` must not be relabelled causal eligibility.
Outer VehicleVelocity qualifier acceptance is not adopted by this screen.

Hypothetical local complete masks additionally require `residual_available` and
no `condition_failure_codes` entry beginning `estimate_features_`. In this frozen
producer those are exactly the non-speed feature failures; all other entries
come from the speed path, including `odometry_*` and bare exception class names.
The frame CSV retains the original codes and both constituent mask flags. Its
plot legend names local hypothetical completeness, never just the clock screen.
Original excluded rows, message/pair discontinuities,
nonpositive source increments and increments above 200 ms break sequences. Counts,
transitions and maximum spans are restricted to the selected local interval;
do not infer a cohort-wide dataset gain or longer-history model validation.

Numeric agreement pairs are limited to originally complete frames. Candidate
native units and old m/s values are not assumed equivalent; RMSE/offset are
exploratory numerical observations, not calibrated physical errors. Aggregate
names use `old_value` rather than an implied common m/s unit; equivalence is
explicitly false. EDP log ties are counted per frame and aggregated per topic.
No learned
scale, lag, imputation, clipping or feature transformation is introduced.

## Bounded implementation and integrity

After source-gate and regular-file checks, the workflow opens one nonblocking,
no-follow regular raw descriptor. It first reads summary/index/schema metadata
to prove the actual fixed-window budget, without hashing or decoding messages.
Only an affordable plan can reserve the durable hash/payload claim. The same
descriptor remains open across the registered SHA-256 verification and consumption
of the prepared plan; metadata is not reread. No payload is decoded before full
current identity verification.
Check size/type and stable device/inode/size/mtime/ctime throughout. Unlike the
summary-only predecessor, current raw identity is verified before decoding.
Only this one existing registered recording is hashed, once; this is a new
payload identity check, not a repeated residual export or summary operation.

| Resource | Fixed maximum |
|---|---:|
| Registered raw file | 2 GiB |
| Full-file SHA phase | 120 cooperative seconds |
| Summary/index/descriptor read bytes | 128 MiB |
| Selected chunk-record read bytes | 128 MiB |
| Cumulative expanded chunk bytes | 512 MiB |
| One chunk (record or expansion) | 4 MiB |
| Selected chunks / decoded selected messages | 2,048 / 50,000 |
| Disposable disk index | 32 MiB |
| Decode/analysis-read phase | 120 cooperative seconds |
| Child address space / parent payload timeout | 4 GiB / 300 seconds |
| Initial available memory / scratch space | 1 GiB / 256 MiB |

The 2 GiB raw verification pass is separate from the two 128 MiB phase budgets.
The metadata and decoder phases share the 120-second processing allowance;
the hash time has its own allowance. Actual indexed window costs and the selected
whole-recording advertised message upper bound must pass **before the claim,
full hashing or any message decompression**. A global summary total cannot prove
the local index budget; it is checked against the live exact inventory indexes.
Reject
missing/ambiguous topics, unsupported compression, changed summaries/descriptors,
overlapping index ranges, dishonest headers, CRC failures and exceeded actual
message limits. Reuse unchanged reviewed reader primitives and their bounded
zstd/lz4 decompression. No scan fallback or automatic wider interval is present.
All expanded bytes in touched chunks count, including unselected topics. Decode
only selected messages; never queue decoded messages from the full recording.

## Enforced source/review gate

The `seal` subcommand is metadata-only. The owner must supply an actual independent
GO review note and explicitly attest its conclusion. Its hash and path are
recorded; software cannot independently interpret or authenticate a review's
scientific conclusion. The gate verifies live read-only GitHub evidence: clean
local main equals local origin/main and live remote main; exact runtime
fingerprint; a matching merged PR; equality of its reviewed-head and current
merged trees; the latest exact-head tests workflow succeeded; all three required
Python 3.10/current, Python 3.12/current and frozen-reader jobs succeeded.
Network/rate-limit/unavailable evidence fails closed before raw inspection.
There is no offline bypass or self-supplied successful CI JSON.
The private runner pins the full expected reviewed tree, not just Python bytes;
even a later documentation-only merge invalidates this packet. It records that
expected tree in the parent receipt. Review attestation is still not authentication
of an independent reviewer. Its source-gate `--preflight-only` path (seal/check)
opens no raw file and can surface API connectivity/rate limits in advance.

`run` revalidates the note hash and live evidence before raw path access. Changes
to source/CI invalidate the gate. The final report records commit/tree, reviewed
head, PR, run/job identities, request and gate pins, and review-note digest. The
workflow checks runtime/current commit again before declaring completion.

A durable exclusive canonical design claim under
`outputs/private/velocity_timing_attempts/` precedes full hashing and payload
decoding. Its key uses revision, outing/recording/raw/size/cohort/inventory
identities, numeric-summary pin, integer window and fixed padding/age settings.
Formatting, input path aliases and output names are excluded. Reformatting JSON
cannot create another claimed design. File and directory ancestry are fsynced.
Existing claims reject before reading recording summary/index bytes. This is per-project
protection, not a global ledger across fresh clones; ordinary process discipline
still forbids a second clone as a retry. Claimed failure is inconclusive; return
all evidence. Gate failure and unaffordable metadata plans consume no claim.
The parent still preserves failed child packets; do not delete or rename them
to force a retry, widen budgets, or change clocks.

Progress snapshots use atomic replacement and fsync. Initial hash/decode progress
is unknown (`null`), not a claim that nothing happened. The hash and decoded
completion boundaries are persisted explicitly. SIGINT/SIGTERM produce an
incomplete report; SIGTERM is converted to a child exception. SIGKILL cannot run
finally, so a last `started` snapshot remains noninterpretable but honest about
unknown progress. Python subprocess timeout kills the POSIX child with SIGKILL;
the parent still records timeout/incomplete and packages available evidence.

## Outputs, tests and next decision

Private outputs: report, velocity-update CSV, per-frame screen CSV and two
Matplotlib PNGs for native-value traces and local hypothetical sequence support.
The parent packet also preserves pinned inputs, source gate, review note, child
logs, terminal code and partial failure/timeout evidence. Scientific interpretation
requires checking report status; an incomplete attempt is never a successful
coverage result. Never publish private descriptors, rows or measurements in Git.

Synthetic tests cover real MCAP NONE/zstd/lz4 chunks, invalid-latest barriers,
zero/future clocks, ambiguous ties, integer precision, old exclusions/resets,
full raw digest and drift, plan/actual resource stops, CRC failure, live-gate
failures, immutable attempts, interruption and Python rendering. Network tests
are mocked explicitly; positive native decoding is synthetic. Actual exact-head
three-job CI and independent source/protocol/launcher GO remain required.

After the real return, first establish timestamps/qualifiers/availability
plausibility and inspect the fixed local comparison. Producer semantics and
physical freshness still need justification before any adoption. If the pilot
is promising, make a separate common-population decision; otherwise stop this
side investigation. Existing Gaussian/AR results remain fixed. Flow protocol/
software work can proceed, while real fitting retains the existing scientific
temporal-support and supervisor-visible model-substitution gates.

## Historical a1 local validation checkpoint

Python 3.12.14 current and frozen-reader environments each pass the 88 focused
checks (33 new, 55 predecessor-reader checks), with no skips. A native synthetic
CLI child completes under its actual 4 GiB address ceiling and writes both PNGs;
its source/CI gate is explicitly mocked. Seven private parent publication checks
pass with child/network delegation explicitly stubbed. Plot layouts were visually
inspected. Public API response shape/job names were checked against the existing
accepted PR; that is compatibility evidence, not new-head CI or operation GO.
Compileall and whitespace checks pass. The full suite and Python 3.10 were not
run locally for this isolated addition; actual reviewed-head three-job CI remains
pending. No BMW raw endpoint or model/transform fitting was invoked.
