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

Start with one prospectively declared original development recording and its
archived rows. Reuse the staged geometry converter and source-clock
definitions on that raw identity. Verify the archive's recording, pair,
estimate and reference message identities and clock values before applying the
geometry check. Establish rear-axle localization and the reference-frame
transform at the evaluated epoch. Record the source of the previous
curvature command, or predeclare a common initialization policy as a
simulator condition and assess it separately. Use the original eligibility
and reset boundaries, and record counts of identity, pose, coverage and
geometry failures before inspecting planner outcomes.

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

The tests cover different residual and vehicle origins, the signed lateral
and heading conventions, invalid profile shape, archived alignment mismatch,
and projection clipping. This patch exercises the new check on synthetic
geometry. The existing development archives, fitted laws and audited tuning
results are immutable evidence.
