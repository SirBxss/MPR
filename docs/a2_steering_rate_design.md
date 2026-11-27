# A2 steering-rate design check

## Question and scope

Does changing only the curvature-correction rate weight create a feasible,
practically distinct planner choice on the accepted a2 local-recovery task?
The prior budget pilot preferred the same correction-effort setting at the
feasible boundary across methods and budgets. Curvature-rate regularization
is a useful axis to test because it determines how strongly the controller
penalizes changes in correction between commands. Short residual sequences
can influence the resulting tracking and jerk costs.

The check uses the frozen PR 60 calibration contexts, with their original
speeds, intervals and resets. It keeps the fixed a2 reference curvature
weight of 16,384 and brackets the reference rate weight of 4,096 with
`[1024, 2048, 4096, 8192, 16384]`. The original planner, four signed
initial conditions, horizon, propagation, and dimensionless loss
`T + A + J` are reused. The stages that use labelled data remain outside
this check. Preserve the preceding tuning result and the earlier failed
synthetic screens.

## Nominal feasibility

Test zero disturbances before computing synthetic loss curves. For each
rate candidate, require the outing mean tracking to be no greater than
120% of the best tracking from the original nine curvature-weight settings
on that outing. This uses the same tracking anchor at every rate. On the
original 10, 20 and 30 m/s recovery probes, every task must achieve at
most 65% of passive tracking loss. Require nominal peak acceleration and
jerk at or below 3 m/s² and 5 m/s³ on every common context and recovery
probe. This last gate applies to every rate candidate. It is stricter
than the PR 60 archive check, which applied those training-context
limits to the fixed reference. These are simulator engineering limits.

The receipt contains gate failures, original limits, per-outing means,
probe ratios and peaks. A descriptive trade-off is present when one
feasible rate reduces mean normalized tracking loss by at least 2% and
the other lowers mean normalized jerk loss by at least 2%, each relative
to the other rate. This threshold borrows the prior pilot's descriptive
margin and has no inferential interpretation.

## Synthetic loss sensitivity

With at least two feasible rates, show expected loss on the shared
contexts under zero-mean covariance probes. Reuse the earlier exponential
spatial correlation length (30 m), frame AR coefficients (0 and 0.9) and
marginal RMS levels (0.005, 0.02 and 0.10 m). Use equal sequence weights
within outings and equal outing weights. These are predeclared probes.
For the exact affine rollout and quadratic loss, the expectation is
nominal loss plus the weighted sum of `sigma² trace(M C)`. Here `M`
is the sequence quadratic form and `C` is the unit-variance covariance.
The receipt gives the numerical minimizer, runner-up gap and all settings
within 2% of the minimum, including the a2 numerical tie tolerance.
The zero-disturbance diagnostic uses the same summaries.

Differences in synthetic choices are descriptive. A shared optimal
setting can still be harder for one method to identify from a small
calibration subset. Conversely, broadly flat loss or a choice fixed by a
constraint may make calibration-data efficiency practically unidentifiable
on this axis. A completed design receipt authorizes no subsequent stage.

## Evidence and next decision

The command verifies a clean reviewed source tree and runtime, the pinned
PR 60 preflight and archive-set identity, exact PR 60 context/donor and
role parity, and unchanged inputs at completion. It reads only the
approved calibration metadata members and hashes the calibration archive
containers for integrity. It writes a fresh private receipt. It does not
decode residual values, fit models, audit decisions, or open either held
numeric container.

Review the feasibility and loss curves together. If there is enough room
for materially different decisions, a separate budget protocol can freeze
whole-outing subsets, common contexts, per-budget model transforms, an
intact-sequence empirical baseline and a held controller-loss/regret
estimand before new outcome access. Require variation in finite-budget
decision or regret for a useful learning curve. Distinct population-law
optima are unnecessary. If the bracket is uninformative, preserve the
result alongside the original pilot and revisit the research claim before
changing the task. Physical recorded replay is a separate extension.
