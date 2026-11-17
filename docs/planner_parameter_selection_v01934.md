# Prospective development planner parameter selection, v0.19.34

## Question and scope

Does selecting the correction effort and correction rate weights using a
frozen learned error law reduce observed local recovery loss on an outer held
outing relative to selection with zero disturbance? The predeclared primary
law is the one state AR model. All six original trained configurations remain
comparators, together with empirical sampling and the fixed default planner.
This is a prospective development study after accepting the spatial and
temporal replications. It is not an independent final test or a physical
vehicle replay. No BMW parameter outcomes were inspected to choose this grid,
loss or support. Metadata and accepted saved states can be checked beforehand.

The original affine lateral planner is retained. Its state is local incremental
lateral error e in m, heading error psi in rad and previous curvature correction
u_previous in 1/m. The residual profile supplies the same signed 21 station
offsets in m as the accepted planner adapter. Controls correct local deviations
around nominal motion, assuming nominal curvature feedforward is cancelled.
Original coordinates, lane geometry, observed initial state and perception
feedback from changed vehicle motion are unavailable. Residuals are exogenous.
Consequently this tests the response of a transparent local recovery simulator,
not route completion, collision avoidance, full comfort, or vehicle safety.

## Fixed tasks, candidates and support

Each sequence starts independently with each of these four synthetic states:
(e, psi, u_previous) = (0.3, 0, 0), (-0.3, 0, 0),
(0, 0.015, 0), (0, -0.015, 0). These are engineering perturbations, not
measured vehicle states. All laws face the same tasks. Resets are original
sequence boundaries, never selected by residual magnitude.

Nine candidates form the Cartesian product of curvature weight scales
{0.25, 1, 4} and curvature rate weight scales {0.25, 1, 4} applied to the fixed
ReferencePlannerConfig. Other weights and the 25 step prediction horizon are
unchanged. Prediction dt is 0.1 s. Default index 4 has both scales 1.
Each source frame recomputes a control with its recorded speed and residual
profile. Local state propagates with the original source interval, using the
existing Euler transition, not the planner's prediction dt. No final state is
invented after the last observed command.

Use whole original temporal eligible sequences, additionally requiring at least
three frames so a recovery action has an observed lateral consequence. The
prior temporal study also included two frame sequences; this study therefore
has a prospectively different, explicitly reported population. Original support
requires valid recorded intervals, speed at least 0.1 m/s and complete 100 m
station support for the fixed spatial prediction. Speeds, integer nanosecond
clocks, sequence boundaries, feature definitions and original archive pins are
unchanged. No cropping, bridging, speed correction or new drive admission.

For each outer held outing, use exactly 12 eligible original sequences from
each of its six training outings. Take floor(linspace(0, N-1, 12)) in source
order after the metadata eligibility filter, requiring N >= 12. Keep whole
sequences and their clocks. The manifest seals every selected index before
sampling. All supported held sequences are scored. This bounded training
context quadrature controls workload; it is not a claim of exhaustive scenario
coverage. Conditions come from training outings only. The empirical pool uses
all original complete residual rows of those training outings, independently
resampled per frame; it does not imply temporal dependence.

## Frozen laws and computation

Selectors use zero disturbance, empirical profiles, unconditional Gaussian,
conditional Gaussian, stationary scalar AR, one state AR, unconditional flow
and conditional flow. A ninth evaluation method retains the default planner
without selection. Both AR models retain their generated history and original
sequence resets. Both flow modes use their accepted Heun solver at 128 steps
and the frozen Gaussian transform, never a cheaper replacement sampler.

Use 64 draws per stochastic arm and seed 193401 for each fold. Save shape,
seed and canonical little endian float64 draw hashes. Reuse these exact draws
across candidates, tasks and sensitivities. The first 32 draws form the
Monte Carlo sensitivity. Do not generate different draws for a different
candidate. The exact affine control map is computed by propagating all 21
station linear terms through the native Riccati recursion. Synthetic tests
compare it and complete source clock rollouts with direct native solves.

Training contexts are in sample for the frozen laws fitted on their six
training outings. This is training only risk selection followed by outer
outing validation, not an inner cross validation claim. Seven outer folds
share training data and are not seven independent fitted experiments.
No real model is refitted and no final reserved recording is opened.

## Evaluation loss and nominal requirement

For source frames t=0,...,L-1, let a_t = v_t squared times u_t denote
incremental lateral acceleration and j_t = (a_t-a_(t-1))/dt_(t-1) for t>=1.
For each draw and task define dimensionless components:

* T = mean over t=1,...,L-1 of [(e_t/0.3 m)^2 + (psi_t/0.03 rad)^2].
* A = mean over t=0,...,L-1 of (a_t/3 m/s^2)^2.
* J = mean over t=1,...,L-1 of (j_t/5 m/s^3)^2.
* Loss = T + A + J with fixed equal normalized weights.

This evaluation loss is independent of the candidate's internal cost weights.
It scores the final observed command without inventing its future state.
Speed changes enter a_t and j_t; jerk describes the incremental correction,
not total vehicle jerk. Report components separately so a scalar gain cannot
hide poor tracking. Equal averaging is over draws and tasks, then sequences
within training outing, then the six training outings. Held comparisons use
equal sequences per outing, then equal weight over the seven outings.
Never treat frames or Monte Carlo draws as independent experimental units.

All selectors share a nominal feasible set, established without sampled
residuals. For every training sequence/task, nominal T must be at most 1.10
times default T plus absolute 1e-12. Also require this on three deterministic
zero disturbance recovery probes at 10, 20 and 30 m/s, each with 26 frames
and dt 0.1 s. These probes check 2.5 s nominal recovery, including rejection
of an unresponsive controller. They do not extrapolate a learned error law
beyond its observed support. A synthetic native parity and negative control
screen runs before real model sampling.

Select the feasible candidate with lowest predicted loss. Ties within absolute
1e-12 prefer the default, then the smallest index. A shared nominal requirement
prevents a candidate from winning solely by refusing to recover local errors.
The default is always feasible. Prespecified nominal requirement sensitivities
are 5%, 10% (primary), and 20%, combined with 64 and 32 draws. These six
settings reuse the same generated and held candidate grids, with no refit or
additional sampling. They are sensitivity analyses, not six primary tests.

## Freeze, held scoring and interpretation

Write all seven selection files and their hashes before any held response
scoring. The sampler and selector interfaces never receive held residuals.
After this barrier, evaluate all nine fixed candidates using observed held
residual sequences and the same four synthetic initial states. Do not change
a selected candidate based on a held nominal failure or cost.

The primary contrast is held loss of the one state AR selected candidate
minus held loss of the zero disturbance selected candidate. The descriptive
risk rule requires a negative equal outing mean and at least four negative
outing contrasts. Report ties, each outing and the full range. A development
recommendation additionally requires the primary AR choices to pass the same
10% nominal tracking bound on every held sequence/task. Report all failures.
Neither a passing flag nor lower forecasting error authorizes adopting
parameters. Small improvements need a practical magnitude assessment.

Secondary comparisons include default, empirical and all six learned laws;
tracking, acceleration, jerk, candidate choices; per sequence draw/task
fractions with peak future absolute lateral error >1 m, peak absolute
incremental acceleration >3 m/s^2 and jerk >5 m/s^3; and regret against a
retrospective held minimum restricted to training feasible candidates. That
oracle uses held outcomes and is a diagnostic lower bound, never a selector.
Threshold exceedances are engineering diagnostics, not safety constraints.

A linear simulator with an expected quadratic loss chiefly tests first and
second moments across time and space. A flow beating a Gaussian here does not
establish non-Gaussian tail usefulness. This experiment lacks a new matched
AR permutation selector ablation, so it cannot attribute any selection gain
solely to temporal coupling. The earlier replication separately addresses
that ablation. Identical choices, zero gains or harmful choices are valid
negative findings. Do not enlarge the grid or change the loss after the run
to manufacture a positive result. Any followup needs a separate prospective
protocol and must remain labelled development.

## Evidence handling and execution

Native development_flow.load_experiment validates the complete original
registry, numeric exports, Gaussian and AR ancestry before restoring the
accepted flow return. Verify all saved states, transforms, completion receipts,
fit claims and accepted solver calibration pins. Verify the accepted temporal
replication and each original row clock/support census. No archive only
fallback is allowed if native lineage fails. Preflight performs these checks
without new sampling, control solving or output creation.

The private helper pins the complete Git tree, runtime source and sealed
manifest, denies MCAP opens and network sockets, and runs with single numerical
threads. Source and inputs are checked between folds. Write exclusive outputs;
preserve partial work and failures. A published ZIP has an internal file hash
census. Defaults put output beside the packet, not inside prior evidence.
Review source, protocol, private manifest and helper, obtain CI on the actual
head and owner merge, then run owner preflight and the bounded study once.
Return its ZIP privately. Keep BMW counts, identifiers, input digests, paths,
comparative findings, tables and plots outside public Git. Source tests use
synthetic fixtures only. Follow the private packet for exact commands.
