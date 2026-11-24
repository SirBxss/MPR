# Recorded reference-following geometry check

The next paper experiment asks how much development data a residual law needs
to select planner weights that perform comparably to empirical resampling.
The accepted spatial and short temporal forecast comparisons and the bounded
local recovery tuning result are the development evidence for that question.
The geometry check in this patch prepares one prerequisite for a prospective
reference-following task with changing nominal curvature.

## One-frame geometry check

`lane_residuals.domain.recorded_replay_geometry.check_recorded_replay_geometry`
takes the original estimate and reference geometry, the archived residual
and anchor evidence for their row, and an explicitly observed rear-axle pose
in the same physical frame. The caller is responsible for the exact
recording, pair, message and epoch binding and for validating frame semantics.

1. Reproduce H100 using the original alignment, left-normal sign and one
   metre anchor limit. Compare all 21 residuals, the reference anchor station,
   and the anchor distance with the archive, using an absolute 1e-9 m
   numerical reconciliation tolerance and zero relative tolerance.
2. Project the recorded rear axle onto the reference with the existing
   ambiguity check. Treat endpoint projections as unsupported because
   a clipped endpoint can hide insufficient longitudinal coverage.
3. Return the nominal coordinates at the original residual stations and
   their signed station positions relative to the vehicle's reference
   footpoint. Use the reference heading at that projection to compute
   initial lateral and wrapped heading errors.

For original station s, the station relative to the vehicle is
s + a - u, where a is the residual anchor station on the reference and u is
the vehicle's reference projection station. When the two origins differ,
relabeling the original profile as starting at the vehicle would shift the
disturbance along the path. The geometry check retains the shift explicitly.
Downstream replay must verify that every planner lookahead lies within
supported stations. The projected state is relative to the fusion reference.

The original development archive has residual profiles, anchor scalars and
exact row identities. It lacks the aligned nominal coordinates and an observed
initial vehicle state. The scalar speed feature cannot supply position, yaw
or prior command. A nominal reference-following runner remains a separate
implementation stage.

## Recorded input feasibility follow-up

The `lane_residuals.cli.recorded_replay_inputs` module now exposes two
operations. `describe` reads one prospectively specified original matched
development row from the sealed experiment and prints a private evidence form.
It does not open the MCAP. The form identifies the raw bytes, original matched
row and geometry profile, both raw message positions, pair index, source
epochs, and the estimator's recorded input time.

`verify` requires a completed and digest-pinned form. It reads the registered
MCAP once for byte identity and reuses the original bounded indexed decoder,
scientific sink and geometry converter. The checker reconciles the preserved
inventory and stream integrity, canonical pair and clock bindings, and the
estimate descriptor. It uses an exact-epoch, conflict-free rear-axle odometry
sample logged by the estimate log time. The private evidence form binds the
availability field and its full-availability enum symbol to the archived
odometry schema digest. The replay receipt records whether original wire
evidence supports the kept sample. The recorded-clock criterion establishes
log ordering only.

The exact kept sample must contain one explicit full-availability enum value.
The reader inspects original bytes in the indexed pass. A scalar without
presence can decode an absent field to the same enum value as availability.
Replay treats omission as ambiguous until applicable producer evidence
establishes its meaning. Reduced availability, unavailable or unknown values
and repeated qualifier tags cannot pass this feasibility check. Identical pose
duplicates retain the earliest log and publish time as before. Tied
representatives must agree on the availability check. Earlier archive speed
extraction continues using its established input contract.

The owner evidence must identify both coordinate frames, the basis for the
physical frame and pose declarations, and the path frame origin and yaw in
odometry coordinates at the estimate source epoch. The original EDP and RLMB
paths must already share that physical frame at that epoch for this stage.
The reported pose uses the existing rigid transform. The routine neither
guesses a transform from topic names nor accepts arrays supplied in place of
raw odometry. Keep the populated form, frame evidence and receipt private.

The receipt supplies nominal points, station offsets and initial geometric
state for this frame if every check passes. The original sequence bounds are
retained as identifiers. The receipt does not establish that the sequence is
replayable. A valid one-frame receipt, an unsupported pose or projection, and
an inconclusive input or source check lead to different next decisions.
Only a successful recorded check warrants extending this input path.
Previous curvature command and full lookahead support are separate planner
inputs. Require a recorded command or predeclare a common simulator
initialization policy before a rollout.

Archive-parity validation is specific to the old geometry mapping. A motion
compensation or time-base change that fails parity defines a new versioned
target and requires its own review. A successfully reconciled frame is a
geometry finding. It leaves closed-loop motion, previous-command evidence,
holdout roles and scientific acceptance of the new task to later stages.

After recorded feasibility is established, use a common nominal task and
planner grid for an outing-level calibration-budget comparison. Preserve
intact sequences in the empirical baseline, select weights on development
information, and evaluate the frozen choices using held recorded outcomes.
Reserve the prospective recordings until physical identity, overlap,
reference quality and role assignment are checked. A second perception
pipeline version is a separate requirement for an update-transfer claim.

## Verification and scope

The geometry tests cover station origins, signed state, archived alignment
and endpoint clipping. The input tests exercise a real synthetic protobuf
MCAP through the original numeric producer and indexed replay. They also
check wrong row, wrong epoch, changed bytes, missing or unusable odometry and
output protection. Replay-specific coverage includes explicit and omitted
default-valued qualifiers, non-available and unknown values, ambiguous wire
tags and duplicate pose receipt ordering. The BMW-side recorded check is
pending.
