# Prospective planner parameter selection a2

## Decision and retained scope

A1 is superseded before real model draws or held parameter scoring. Review
found a narrow effective grid and a nominal transient dominating its objective.
These are scientific design concerns despite passing implementation tests.
A2 takes the bounded Option A correction: construct a recoverability versus
disturbance-response trade-off and screen whether the question is answerable.
Do not require a particular learned law to win. No real model, feature, split,
archive, clock, original support or accepted flow solver is changed.

The target remains a signed lane/path discrepancy against a fusion-based
pseudo-reference. That reference is not independent physical ground truth.
This study does not remove shared-source bias or establish reference-map
quality; both remain limitations and final-validation design requirements.

Primary question: does a one-state AR law used for training-only parameter
selection reduce observed held local recovery loss relative to zero-law
selection? Zero versus AR includes noise awareness; it does not isolate
learned temporal structure. Named secondary contrasts are AR minus empirical,
conditional Gaussian, stationary AR and fixed reference planner; report all six
frozen learned configurations. Earlier matched permutation evidence remains
a separate temporal attribution experiment. This is a descriptive development
study, not independent final evidence, physical replay or vehicle safety.

The same affine state [lateral error m, heading error rad, previous curvature
correction 1/m] and signed 21-station profiles are used. Nominal curvature
feedforward is assumed cancelled. Conditions and errors are exogenous and not
updated after simulated vehicle motion. Global geometry, true observed initial
state and perception feedback are unavailable. Prediction dt is 0.1 s and
horizon 25; physical local state and jerk use original source intervals.

## Revised candidate family, tasks and objective

The reference configuration has curvature weight 16384 and curvature-rate
weight 4096. The nine curvature weights are 1024, 2048, 4096, 8192, 16384, 32768,
65536, 131072, 262144; the rate weight is fixed 4096. Other native settings stay
fixed. The reference is index 4. This single interpretable axis replaces the
ineffective 3x3 a1 family. Native units differ between lateral and curvature
terms; weight magnitude alone is not a physical actuator limit. A synthetic
sweep brackets the zero-law optimum; the largest permitted weight does not
win nominally on that declared suite. The old aggressive reference is not a
newly advantaged primary baseline. Keep the well-damped fixed reference and
the zero-law-selected setting as distinct controls.

Initial states are (+/-0.03 m, 0, 0) and (0,+/-0.0015 rad, 0). These small local
perturbations are engineering test states, not measured offsets. For each
sequence/task define dimensionless components:

* T = mean observed states t=1..L-1 of (e_t/0.03 m)^2+(psi_t/0.003 rad)^2.
* A = mean observed commands t=0..L-1 of (v_t^2 u_t/3 m/s^2)^2.
* J = mean command transitions t=1..L-1 of (((a_t-a_(t-1))/dt_(t-1))/5 m/s^3)^2.
* Loss = T+A+J, independent of internal controller weights.

The last observed command is scored without inventing its unobserved next
state. Equal weights and normalizations are prospective engineering choices,
not BMW requirements or certified comfort/safety limits. Tracking normalization
changes with the smaller tasks so tracking remains meaningful. Task reduction
alone would not fix the original grid; both are revised. Acceleration and jerk
refer only to incremental correction. The native solver is unconstrained;
the 3 and 5 values are diagnostic thresholds, not enforced actuators.

## Response decomposition and diagnostics

Linearity gives a nominal task response plus a zero-initial-state error-induced
response. For symmetric +/- tasks, cross terms cancel in the task average:
E_task Loss(total) = E_task Loss(nominal)+Loss(law increment).
The identity holds separately for T,A,J and biased error laws. It does not hold
for each task or for threshold indicators. Check it numerically for each
response; persist all three component arrays, with explicit ordering, per
candidate/arm/prefix/context. Held tables preserve the same decomposition.

Primary exceedance fields use the zero-initial-state error-induced response:
peak future absolute lateral error>1 m, acceleration>3 m/s^2 and jerk>5 m/s^3.
Total-response exceedances are retained under explicit total_ names. They must
not be confused with increment indicators or with physical safety constraints.
An expected quadratic loss chiefly uses first and second moments; a flow win
here would not establish non-Gaussian tail value.

## Shared nominal requirement

For each training outing, average nominal T equally over its 12 selected whole
sequences and four tasks. A candidate passes the context criterion if this
outing mean is at most (1+g) times the best nominal tracking outing mean among
the nine candidates, plus absolute 1e-12. Require this for each of the six
training outings. Primary g=20%; sensitivities 10% and 40%. Report exclusions
and binding outings, and worst individual context/task ratios separately.
One slow context no longer imposes an automatic every-context veto. The
fixed reference need not belong to every feasible set; its comparator status
is reported. If it lies outside, its signed oracle gap need not be nonnegative.

Additionally each nominal probe/task must have mean T at most 65% of its own
passive zero-control mean T: at least 35% tracking reduction on this declared
suite. Probes use speeds 10, 20, 30 m/s and 26 frames at 0.1 s, corresponding to
2.5 s of nominal recovery. This is an absolute engineering comparison to an
unresponsive control, not the a1 overshooting default. All nine revised
candidates pass the frozen probes. These probes never extend a learned error
law beyond its observed sequence support. Synthetic engineering checks require
all probe candidates' peak nominal acceleration<=3 and jerk<=5. The owner's
metadata check separately requires the reference configuration to remain in
that envelope on every selected training context. This is a design readiness
condition; held nominal violations remain visible without reselection.

## Data, samplers and freeze ordering

Reuse whole original temporal-eligible sequences with L>=3, original feature
semantics, clocks and resets. The a1 L>=3 support and metadata-only spread of
12 sequences per training outing remain unchanged. Select floor(linspace) in
source order, no residual magnitude choice, no speed floor added, no cropping
or bridging. Each outer fold has six training outings. The empirical pool is
all original complete training rows, independently resampled by frame. Held
outcomes use every supported held sequence. Equal weighting is tasks/draws,
then sequences per outing, then outings. Seven overlapping folds are not
independent fitted experiments; training contexts are in sample for the laws.

Restore both Gaussians, both AR models and both flows from the accepted native
ancestry. Keep Heun 128 for both flows. No refit. Use 64 draws, seed 193401, with
first 32 sensitivity. The same seed is deliberately reused across folds;
common random numbers do not create independent replicates. Reuse exact draws
across every candidate/task/gate. The horizon covers only 2.5*v metres, so far
stations have zero control gain at low speed; interpret model comparisons
accordingly. All choices in every fold must be written and hashed before any
held residual response is scored. Report deterministic tie tolerance 1e-10,
default first among feasible ties, then candidate index.

## Synthetic fixture before owner outcomes

The engineering fixture checks 108 native first-command comparisons, nominal
probe recovery, acceleration/jerk envelope and decision sensitivity. Its fixed
Gaussian family has spatial exponential covariance length 30 m, frame AR
rho in {0, 0.9}, marginal sigma in {0.005, 0.02, 0.10} m, speeds 10, 20, 30 and 8
frames with dt 0.1. Expected risks are exact trace(M*C) plus nominal loss.
Eight repeats of 64 draws use seed 193402+repeat; first 32 reuse the same draws.
Report exact choices, 64/32 choices, change frequency versus zero and prefix
agreement. Require an interior zero-law choice and at least two scenarios
changing it in at least 75% of repeats. This finite engineering sensitivity
screen is not a BMW result, a general power guarantee or evidence of a
particular trained model's superiority. The prototype design exploration is
retained privately; no real residual/model outcomes informed it.

## Owner metadata design stage and stop rule

There are three distinct modes before a full study:

1. Native preflight verifies source, ancestry, accepted returns, metadata and
   budgets without new solving, sampling or output creation.
2. Synthetic-only engineering runs the fixture with no BMW inputs.
3. Design-only performs nominal calculations using the training contexts'
   speeds, lengths and intervals; no learned-model draws or held response scores.
   Native loaders still read accepted archives/states for integrity. The
   diagnostic function itself receives only speeds and sequence metadata.

For each fold and gate, report the feasible set, zero-law choice, nominal gaps,
binding outings, nominal component/peak census, exact synthetic moment choices
and law-free flip bounds. Build zero-state quadratic maps M per sequence using
native affine gains. Whole contexts of different lengths have separate
coordinates: for weights w_k, use blockdiag(w_k*(M_zk-M_ck)). The maximum
eigenvalue is max_k w_k*lambda_max(M_zk-M_ck). If positive, nominal gap divided
by it bounds the total second moment needed to change the choice; divide by
all 21*sum(L_k) coordinates and take the square root for a global RMS bound.
This optimally aligned energy bound does not assert a plausible law or equal
energy allocation. Null means no positive eigenvalue, never JSON infinity.

Diagnose readiness before any real sampling. Every fold needs at least two
primary feasible candidates, nonempty sensitivity sets, at least one change
of the primary zero choice under the declared exact synthetic covariance
family, a flip bound within 0.30 m global RMS, and reference nominal context
peaks within 3 and 5. If any fold fails, preserve a complete
complete_parameter_selection_design_not_informative result and stop. No model
draws, held scores or choices are produced. This is not a negative finding
about learned models. Design-only always stops after this stage even when
ready. Full mode recomputes the same stage before sampling. A quadratic map
budget caps sequences at 32 frames, above this frozen population's support;
an over-budget sequence fails closed rather than being truncated or dropped.

## Held comparison and next decision

After all choices are frozen, score the nine candidates using observed held
residuals and report components, increment/total exceedances and each outing.
Primary is AR-selected minus zero-selected loss. Require at least 1% relative
macro loss reduction and at least four outing contrasts below-1e-10 for the
predeclared descriptive practical rule. Report all magnitudes, ties, prefix
and gate results. No significance claim is implied. A recommendation also
requires no primary held outing to violate the same 20%-over-grid-best nominal
tracking mean and no selected nominal context to exceed 3 or 5. Choices never
change based on held diagnostics. The retrospective oracle is a diagnostic
minimum over training-feasible candidates only, never a selector.

A passing development flag does not adopt parameters or authorize deployment.
Null or harmful results are valid. If the bounded design stage cannot support
an informative question, preserve that decision-specific sensitivity limit
and agree a bounded next action instead of repeatedly searching for a win.
Independent final validation, recording reference quality/roles and writing
remain separate. No new recording is admitted. Review source, protocol and
private helper/manifest, obtain new actual-head CI and owner merge, then run
owner preflight/design-only. The old a1 helper is superseded for execution.
