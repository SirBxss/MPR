# v0.16 reference-planner predeclaration

This contract is fixed before inspecting real planner outputs. The experiment
measures sensitivity of one transparent reference planner. It does not emulate
the BMW planner, establish planner benefit, or support a safety claim.

## Primary question and arms

The primary question is whether the temporal ordering of lane-estimation
pseudo-residuals changes the behavior of the specified planner when the set of
21-dimensional residual frames is held exactly fixed within each sequence.

- A0 `zero`: zero residual, for the magnitude comparison.
- A1 `time_shuffled_ar`: each A2 draw is independently permuted in time within
  each declared sequence.
- A2 `frozen_ar`: free-running v0.15.4 residual draws in generated order.

The primary estimand is paired A2 minus A1. A1 preserves the exact multiset of
H100 profiles within every sequence and draw, including each profile's spatial
cross-station structure. It changes only temporal ordering and never crosses a
sequence boundary. A2 minus A0 is secondary. The unconditional Gaussian arm
is deferred because it changes both marginal and temporal structure.

A snapshot-only evaluation is rejected for the primary question: if every
frame begins from the same state, an aggregate of deterministic per-frame
outcomes depends only on the marginal set of frames, so A1 and A2 cannot be
distinguished in expectation.

## Simulation interpretation

The stored H100 paths are ego-relative snapshots of the recorded motion. They
do not provide transforms that stitch the simulated ego into one global frame.
The simulation therefore propagates only a linearized error state
`x = [d, psi_error, previous_curvature_correction]` around the recorded motion.
It is a receding-horizon error-state sensitivity simulation, not vehicle-state
replay or a global closed-loop reconstruction.

At each active source timestamp, the workflow reconstructs the signed residual
along the aligned RLMB path's left normals to validate the geometry contract.
The linearized Frenet planner consumes the mathematically equivalent signed
lateral-offset profile directly; it does not propagate perceived-path global
coordinates across ego-relative snapshots. It solves a finite-horizon tracking
problem using current speed, executes the first correction over the observed
interval, and carries the error state to the next frame. State resets once per
declared sequence. The residual is treated as an exogenous time-indexed process
whose dependence on the simulated state is not modeled.

## Planner equations and fixed parameters

```text
d_next          = d + v * dt * psi_error
psi_error_next  = psi_error + v * dt * u
u_previous_next = u
```

The 25-step affine LQ objective compares each predicted next state
`x_(k+1)` with the current H100 residual interpolated at
`v*dt, 2*v*dt, ...`, and includes heading error, curvature correction, and
correction-rate regularization. The last predicted-state tracking term receives
the fixed terminal multiplier. A pure-NumPy backward Riccati recursion solves
this exact objective and the stored objective metric is its optimized horizon
value. Constraints are not enforced; fixed envelopes are outcome metrics.

| Parameter | Fixed value |
|---|---:|
| horizon steps | 25 |
| lateral / heading weights | 8.0 / 3.0 |
| curvature / rate weights | 1.0 / 4.0 |
| terminal multiplier | 4.0 |
| maximum absolute curvature | 0.20 1/m |
| maximum absolute curvature rate | 0.25 1/(m s) |
| maximum absolute lateral acceleration | 3.0 m/s² |
| maximum absolute lateral jerk | 5.0 m/s³ |
| maximum absolute lateral deviation | 1.0 m |
| lateral excursion reporting threshold | 0.3 m |
| accepted source-time interval | 0.01–0.25 s |
| minimum numerical speed | 0.1 m/s |

These are fixed engineering sensitivity parameters, not fitted quantities,
production settings, or safety limits. They must not change after real outputs
are inspected.

## Cohort, metrics, and uncertainty

The primary cohort is fixed to clean groups `drive_001` through `drive_004`.
Frames join to aligned paths by exact `(recording_id, pair_index)`. Every
sequence has at least two frames and strictly increasing timestamps. Singleton
sequences are excluded before sampling because neither temporal propagation nor
within-sequence shuffling is defined for them. Their IDs and counts are retained
in the scenario summary; this eligibility rule does not inspect residual values
or planner outcomes.

At least 20 residual draws are required. Headline sequence metrics are
time-integrated absolute lateral error, maximum absolute lateral error,
fraction beyond 0.3 m, constraint-violation fraction, and final absolute
lateral error. Per-frame lateral and heading error, total curvature, curvature
rate, lateral acceleration, jerk, objective, and violation are retained.

Every headline A2-minus-A1 effect reports its mean and 2.5/97.5 percentiles
across paired Monte Carlo draws. This is not a dataset confidence interval and
does not estimate independent-journey uncertainty. Per-sequence rows are
mandatory. An interval including zero is reported as indeterminate for this
configuration, not automatically as evidence of no effect.
The 0.3 m threshold-exceedance fraction is a descriptive secondary metric and
cannot carry the temporal-order conclusion by itself.

The result may describe within-outing sensitivity of this fixed planner. It
may not claim planner benefit, BMW behavior, production readiness, safety,
physical ground truth, global replay, or journey-level generalization.

## Amendment record: 2026-08-27

This section was added after the first real planner output was inspected. That
first output is rejected because review found that the Riccati recursion
compared predicted state `x_(k+1)` with reference `r_k`. Commit `1244c48`
corrected the implementation and made three corresponding documentation
changes before the accepted run was produced:

1. the objective description now states the corrected `x_(k+1)` versus
   `r_(k+1)` indexing, terminal weighting, and optimized-objective meaning;
2. the geometry paragraph now distinguishes left-normal geometry validation
   from direct use of the equivalent signed Frenet offset; and
3. the 0.3 m threshold-exceedance fraction was labelled descriptive and unable
   to carry the temporal-order conclusion by itself.

No arm, cohort, source artifact, seed, numerical planner parameter, headline
metric, paired A2-minus-A1 estimand, interval rule, or claim limit changed. The
third clarification was nevertheless a post-output demotion of one headline
metric and is therefore declared explicitly. Under the original rule, the
accepted corrected run reports three separating metrics and two indeterminate
metrics: integrated absolute lateral error, maximum absolute lateral error,
and constraint-violation fraction separate; final absolute lateral error and
the 0.3 m exceedance fraction do not. Under the amended interpretation, the
0.3 m result remains reported with the same indeterminate verdict but is also
identified as descriptive. Its accepted arm means are only `0.000856` for A1
and `0.001054` for A2, so neither interpretation relies on it for the
temporal-order conclusion.

This completion update also records the existing first-frame convention. A
sequence's first frame has no preceding source interval, so it uses the first
observed within-sequence interval; equivalently, `dt[0] = dt[1]`. This documents
the executed implementation and does not change the accepted run.
