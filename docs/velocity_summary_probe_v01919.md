# Velocity feasibility: bounded first checkpoint

This is a read-only development diagnostic. It preserves all accepted training,
features, row masks, resets and final-outing restrictions. No message payload is
read, no replacement speed is adopted and no temporal recovery is established.

## Why this checkpoint

The accepted complete-feature sequences support only short-window temporal
comparison. Existing diagnostic evidence implicates the strict interpolated
odometry speed availability check. Direct velocity topics are candidates, but
their names and equal advertised counts do not establish valid speed, source
clocks, units, reference points or prediction-time availability. Repeating the
residual exporter cannot answer those missing semantic questions.

The new `python -m lane_residuals.cli.velocity_summary_probe` command extracts
exact Protobuf FileDescriptorSet bytes and readable message/field/enum
declarations for both direct velocity topics and odometry. It also calculates
advertised selected-chunk I/O for each topic, their two-topic union and all three.
Shared chunks are counted once in unions. Chunks lacking channel indexes are
included conservatively. No sequential-scan fallback or decompression exists.

## Limits and evidence boundary

- One reviewed development recording, selected for small footprint before
  inspecting candidate speed values or model outcomes. No seven-file sweep.
- Maximum 128 MiB cumulative raw reads, 100,000 chunk indexes and a cooperative
  60-second deadline. The private launcher supplies a 90-second parent timeout
  and 4 GiB process address-space ceiling. Time limits include summary parsing;
  they are resource bounds, not a promised BMW runtime.
- A section firewall allows only Header, immediate DataEnd marker, Summary and
  Footer. Neither message chunks nor metadata/attachment bodies can be read.
- Request, accepted cohort snapshot and inventory are SHA-bound. The selected
  outing must be development and contain the registered raw digest; other roles
  fail before raw path inspection. This consumer trusts the externally reviewed
  original snapshot pin: it does **not** recompute the cohort registry or create
  a new admission decision. The private preparation checks the original snapshot
  against already accepted evidence. Arbitrary self-pinned requests are outside
  the reviewed operational scope.
- The fresh inventory must exactly equal the accepted inventory. Descriptor
  bytes must match its schema hashes. The file size/type and stable open-file
  identity/mtime/ctime are checked. To avoid another full raw-file pass, the
  current full raw hash is **not** verified. Its old digest is provenance only;
  matching summary evidence cannot certify current message bytes. A future
  payload operation needs its own identity verification and review.
- Budget, parsing and changed-input failures are inconclusive. Once output
  creation starts, an incomplete receipt is retained. No existing output is
  overwritten. Private declarations and descriptors must never be committed.

## Decision after the first return

Inspect actual fields and enum declarations, then establish producer evidence
for the velocity quantity, signedness, units, vehicle frame/reference point,
qualifier meanings, missing-field handling, source clock and relevant input-read
deadline. A schema may contain hints; it cannot prove those semantics.

If the candidate is meaningful and a small selected read is affordable, implement
one bounded payload pilot using explicit mappings. Compare source-time and
recorded-availability ages, valid update gaps, causally eligible frame coverage,
sequence lengths/transitions and agreement with the old speed on their common
valid support. Use integer clocks, latest-past selection with a justified finite
age bound and an invalid-latest-update barrier. Do not skip invalid updates to
find a convenient older valid sample, mix topics silently, bridge excluded frames
or relax causality because log/publish timestamps tie. Separate the source-epoch
estimand from a later planner input-read estimand. A finite latest-past age must
not be optimized against held-out outcomes or picked solely to maximize coverage.

Stop after this checkpoint if semantic evidence or affordable I/O is missing.
Do not turn it into another raw-data engineering project. If a payload pilot is
promising, extend only that diagnostic to the other development outings before
adopting a new versioned common dataset. A changed feature/population would need
matched refits across model families; preserve the accepted comparison intact.

## Training position and critical path

The two Gaussian configurations, scalar stationary AR and station-wise one-state
AR have completed the matched development comparison. Both flow implementations
remain synthetic-only on this population. The planned next model work is a
matched unconditional-flow and conditional-autoregressive-flow protocol/adapter,
reviewed fixed training/selection scope, fitting and independent evaluation,
followed by consolidation of the common comparison. This is two configurations,
not a reliable fraction of remaining effort. The two-state switching model is a
separately justified extension, not an implicit extra required training job.

Flow protocol/software work can proceed without waiting for a speed decision.
Real-data flow fitting must still satisfy the existing scope, supervisor-visible
model-substitution decision and temporal-support gates; this diagnostic does not
waive them. Explicitly decide whether results on the accepted short-window
population are sufficient for the intended claim before expensive flow fits.
Any longer-history experiment needs a justified common population. Final held-out
evaluation and planner assessment are subsequent phases, not unfinished baseline
training. No timing promise or percentage-complete estimate follows from four
finished configurations. Avoid duplicate real fits until the population decision.

## Review and operation

Deliver numbered patches and the private pinned launcher separately. Independent
source/protocol/launcher review, actual reviewed-head three-job CI and owner merge
precede the first operational summary read. The user has authorized preparing
this bounded investigation; no new four-statement model authorization is needed
for a summary-only diagnostic. Review requirements are repository workflow, not
permission to expand the scope or fit models.

Validation uses deliberately unreadable synthetic message chunks to test the
section firewall, exact schema declarations, final-role rejection, resource
limits, shared-chunk accounting, changed-input detection and incomplete receipts.
Synthetic tests establish engineering behavior, not deployed signal semantics.
