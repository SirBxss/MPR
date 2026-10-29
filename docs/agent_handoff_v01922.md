# Agent handoff — v0.19.22 paired source-tie audit

Date: 28 October 2026. Start with AGENTS, README, current status and
[the fixed diagnostic contract](velocity_source_ties_v01922.md).

PR #46 is merged at `3a48cced905a4dc12dd02fe548e2ae0238cf5e73`, retaining
reviewed tree `b69141494fb08bae174f2532619d501222de7753`. Its independent
source/protocol/private-helper GO and all three actual reviewed-head CI jobs
are accepted. The deferred review-closure documentation is carried into this
implementation. Do not apply the old closure patch separately on top.

New private source evidence is assessed outside Git. It does not identify the
deployed producer or establish recording-applicable units/sign/reference,
timestamp or clock/consumer semantics. The old sensor processing/timestamp
trace already exists; see [its qualification](bmw_sensor_topology_epoch_evidence.md).
Do not infer recording mode from current defaults or repeatedly request
unrecoverable historical metadata. Retain source fact, reported evidence and
inference as distinct categories. Keep all new private transcripts, source
locations/snippets/commit identities and measurements outside public Git.

Four new modules implement a paired audit: unchanged primary selection once,
strict-source secondary on that same sample, clock observations, workflow,
Python plots and CLI. The existing history loader/selector and all other
previous Python files remain byte-identical. No new raw reads, training arrays,
feature/schema/dataset modifications or fits occur. Numeric MCAP header publish
time is not promoted to producer publication time. Existing output is refused;
failures preserve an incomplete diagnostic report after creation.

Fourteen new tests cover equality/no reselection, one-nanosecond and age bounds,
integer precision, invalid/latest/no-history barriers, zero speed, original
losses, geometry/other-feature/reset barriers, clock observation limits, exact
primary parity, native CLI figures and failure/input preservation. Complete
local validation is recorded in the private packet. Actual new-head CI and
independent review of this candidate remain pending; old CI does not cover it.

The cached replay remains post hoc on the same previously exposed window. It
does not close generalization, speed adoption or physical availability. The
next evidence request is focused on the unresolved production/value/clock path,
not another broad schema/geometry trace. Resolve its result as main agent;
accept unknowns without inventing a deployment mapping. A separate prospectively
reviewed bounded development protocol follows only a defensible interpretation.
Predeclare both tie conventions and all success criteria before new windows.

Both Gaussians and both AR controls remain accepted. Both flows remain
synthetic-only and need first real matched training/evaluation under existing
gates. Preserve original experiments, all attempts, reset/fold/reference/sign/
grid/feature contracts and final embargo. Do not launch blanket refits. A later
versioned changed-population experiment must compare models on common inputs.
Flow software/protocol preparation can continue alongside this evidence work.

Deliver numbered format-patch ZIP with README and unzip-before-apply commands
for `~/PycharmProjects/MPR` and `~/Downloads/MPR`. No external push, PR creation
or merge without user instruction. Update README, AGENTS, status and this handoff
after implementation, review and results. No owner raw/cached replay is required
merely to reproduce the diagnostic already supplied in the private packet.
