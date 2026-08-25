# MPR autoregressive input-output HMM

## Purpose and scientific boundary

The AIOHMM is the second of the three fixed MPR thesis model families:

1. conditional multivariate Gaussian;
2. autoregressive input-output hidden Markov model;
3. RC-GAN, after the independent-drive/data-volume gate.

Its purpose is narrow: test whether explicit temporal memory and a small latent
state can improve held-out generative realism over the Gaussian temporal null
while every data, split, transform, and metric decision remains unchanged.
It does not redefine the target, repair the pseudo-reference, search new
features, or authorize final model selection from the present four clean
recording groups. These groups are portions of one same-day outing, not four
independent journeys.

The current v0.15 input is the immutable v0.13.1 physical-unit tensor contract:

- six prediction-time condition features at each retained frame;
- 21 signed pseudo-residual stations at `0, 5, ..., 100 m`;
- 16 clean recording/gap-local sequences and 4,084 retained primary frames;
- 18 mixed-source sequences and 518 frames used only for supplementary transfer;
- exact lengths, masks, timestamps, and recording/drive/pair provenance;
- leave-one-recording-group-out folds and transforms fitted on training groups
  only; this estimates within-outing transfer, not journey-level generalization.

The model never joins recordings, crosses a detected gap, interpolates targets,
or assumes the observed 69--91 ms intervals are exactly constant. Every
retained frame is one discrete model step.

## Model

For latent state `z_t`, standardized condition vector `x_t`, and standardized
21-station residual vector `y_t`, transitions are

$$
p(z_t=j\mid z_{t-1}=i,x_t)
=\operatorname{softmax}_j\left(W_i[1,x_t]\right).
$$

The destination frame's current condition controls the transition into that
frame. For frames after the sequence start, emissions are

$$
y_t\mid z_t=k,x_t,y_{t-1}
\sim
\mathcal N\left(
B_k^T[1,x_t]+d_k\odot y_{t-1},\Sigma_k
\right).
$$

`B_k` contains a state-specific intercept and six condition coefficients at
every station. `d_k` is a station-wise diagonal AR(1) vector; no full 21 by 21
lag matrix is fitted. `Sigma_k` is a state-specific full spatial covariance.
Each state regression is shrunk toward one shared training-frame AR regression;
this prevents a low-occupancy state from acquiring an unsupported intercept or
persistence coefficient while leaving well-supported states data-driven.
Each covariance is pooled toward the occupancy-weighted shared covariance and
then shrunk toward its diagonal before an eigenvalue floor is applied. This
keeps within-frame spatial dependence while constraining a parameterization
that is large relative to two physical drives.

At the first frame, there is no valid preceding residual. A state-independent
conditional Gaussian marginal fitted on all training frames supplies the reset
distribution. A held-out fold has only 6--7 training sequence starts, so fitting
a separate 21-dimensional start covariance from start rows would be singular
and unstable. The marginal prior uses no held-out rows. This reset is
intentional: a sequence cannot inherit a residual from a different recording
or across a detected gap.

## Fixed development configuration

The CLI defaults are an exploratory architecture, not selected thesis
hyperparameters:

| Choice | Default | Reason |
|---|---:|---|
| latent states | 2 | parsimonious correction after the v0.11 three-state occupancy collapse |
| EM restarts | 3 | expose initialization sensitivity |
| maximum EM iterations | 30 | bounded generalized-EM run |
| AR absolute bound | 0.98 | constrain free-running instability |
| emission pooling penalty | 10.0 | shrink rare-state mean/AR parameters toward the shared AR regression |
| state covariance pooling | 0.50 | regularize state-specific full covariances |
| diagonal covariance shrinkage | 0.15 | stabilize spatial covariance estimates |
| minimum state occupancy | 0.05 | prevent a nominal second state from becoming a negligible component |
| Monte Carlo samples | 128 | identical frozen evaluator scale as v0.14 |

Changing the state count or other architecture values creates another
development experiment. The command does not compare configurations or select
one using held-out drives.

## Inference and generalized EM

`modeling.aiohmm_inference` performs log-domain forward-backward inference for
time-varying transition matrices. Unit tests compare its state and transition
posteriors with exact enumeration of every hidden-state path in a small HMM.
The filtering normalizer at each frame is retained; these increments sum exactly
to the sequence joint log-density and support provenance-preserving frame rows.

One deterministic generalized-EM restart performs:

1. RMS-quantile initialization with seeded perturbations;
2. forward-backward state and transition posteriors;
3. one shared AR regression followed by posterior-weighted state/station
   regressions pooled toward the shared coefficients;
4. posterior-weighted spatial covariance estimates, pooling, shrinkage, and
   positive-definite projection;
5. smoothed initial-state probability updates;
6. multinomial-logistic transition updates with deterministic Adam steps.

The reset frame of every sequence is excluded from step 3 and the
state-specific covariance part of step 4 because it is generated by the
separate reset distribution. This corrects the earlier mismatch in which a row
could influence parameters that did not define its likelihood. After every
M-step, v0.15 backtracks along a convex parameter update until training
likelihood is non-decreasing and the posterior occupancy floor is satisfied.

The transition update is numerical, covariance regularization changes the exact
maximum-likelihood M-step, and AR coefficients are clipped. The backtracking
gate therefore checks the actual raw likelihood rather than assuming the full
regularized update is monotone. If no feasible non-decreasing step exists, the
fit retains the best valid state and reports nonconvergence.

Hidden-state labels are exchangeable. After fitting, parameters are reordered
by ascending zero-condition emission-intercept profile RMS, then mean intercept
and median AR. This creates deterministic diagnostic labels for comparing
restarts. It does not turn a state index into a physical class.

## Restart and leakage policy

Every recording-group fold fits the same architecture with deterministic restart
seeds. The selected restart has the highest training joint log-density among
successful same-architecture restarts. The held-out drive is not used to choose:

- state count;
- restart;
- standardizer;
- convergence threshold;
- covariance regularization;
- transition settings;
- AR bound;
- sample seed.

The restart CSV records all failures, warnings, convergence states, occupancies,
AR bounds, and canonicalized transition/occupancy differences from the selected
restart. A descriptive all-development-data fit is run only after cross-
validated evaluation and is explicitly not an untouched final model.

## Observed-history density versus free-running generation

Likelihood evaluation uses the observed `y_(t-1)` when computing the emission
at frame `t`. The filtering increments sum to a proper joint sequence density
and answer whether the fitted observed-history conditional density explains the
held-out sequence.

Sampling draws `y_0` from the training-only marginal reset prior and recursively
uses the generated `y_(t-1)` afterward. This is free-running and answers whether
the model can generate realistic complete sequences without seeing target
residuals. A model can therefore achieve a strong observed-history
NLL and still accumulate bias, become under-dispersed, or produce poor energy
score in free-running mode. Both results must be reported.

## Evaluation

The primary cross-model evidence is frozen by v0.14:

- physical-unit sample-mean RMSE;
- multivariate 21-dimensional energy score;
- length-normalized energy score on the complete flattened sequence;
- marginal 95% coverage;
- observed/generated station-wise lag-one correlation and median absolute
  error.

Observed-history standardized and Jacobian-adjusted physical NLL are proper
density scores for the Gaussian/AIOHMM comparison. They remain separate from
the cross-family sample metrics because an RC-GAN need not provide a normalized
likelihood and because NLL does not measure free-running generation.

Model-specific diagnostics include:

- posterior state occupancy and entropy on every held-out drive;
- maximum posterior probability;
- mean and variable condition-dependent transition matrices;
- self-transition probability and geometric dwell estimate;
- station/state AR coefficient ranges and clipping;
- covariance minimum eigenvalues;
- EM likelihood history, best iteration, convergence, warnings, and restart
  stability.

The v0.15 expanded result reduces macro lag-one error from 0.888345 to 0.018276.
Its normalized complete-sequence energy is nearly tied (0.286286 versus
0.286028 m) and favors the AIOHMM on three of four technical groups, but frame
energy and marginal coverage are worse. All 15 completed fits touch both the
occupancy and maximum-AR boundaries, and one selected fit does not converge.
The predeclared sequence-energy check therefore remains false and the correct
classification remains temporal improvement without full generative
acceptance. The descriptive 3/4 split is underpowered and cannot establish
independent-journey generalization.

## Command

Install the current checkout and run the reviewed configuration:

```bash
python -m pip install -e ".[mcap]"
python -m lane_residuals.cli.expanded_aiohmm \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --output-directory "outputs/models/expanded_aiohmm_v0150"
```

The output directory must be absent or empty. The workflow fails before fitting
if any source filename, hash, fold member, frame count, v0.14 result, or stored
training-only transform differs from the accepted lineage.

## One-state AR ablation

v0.15.1 runs the same emission and evaluation code with `state_count=1`. This
is a conditional autoregressive Gaussian, not a latent-state model: posterior
occupancy and the 1-by-1 transition are deterministically one. It retains the
v0.15 reset distribution, station-wise AR coefficients, covariance treatment,
observed-history density, free-running generation, folds, standardizers,
restarts, seeds, sample count, and metrics.

```bash
python -m lane_residuals.cli.expanded_ar_ablation \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --output-directory "outputs/models/one_state_ar_v0151"
```

The command fails before fitting if either baseline is incomplete or changed,
or if any non-architectural v0.15 hyperparameter differs. One-state versus
conditional Gaussian measures the contribution of AR. Two-state versus
one-state measures the additional contribution of latent switching. Neither
comparison creates independent outings that are absent from the corpus.

## Two-state convergence audit

The reviewed v0.15.0 fit used relative change in total standardized
log-probability and one selected two-state fit did not converge. v0.15.2 closes
that optimization confound without combining it with an architecture or
boundary change. It uses
`absolute_log_probability_improvement_per_frame` with a fixed threshold of
`1e-3` standardized nats per training frame. The state count, occupancy floor,
AR ceiling, EM iteration limit, regularization, transition optimizer, restarts,
seeds, folds, transforms, sample count, and metrics remain those of v0.15.0.

```bash
python -m lane_residuals.cli.expanded_aiohmm_convergence \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --output-directory "outputs/models/two_state_convergence_v0152"
```

The workflow fails closed before fitting if either reviewed autoregressive
artifact has changed or any non-convergence setting drifts. It reports whether
all five selected fits converge, how many iterations were added, and how the
corrected two-state model changes every predeclared macro and paired-group
sample metric. A corrected fit must be compared with the one-state result
before making a latent-switching claim. This audit does not relax the 0.98 AR
ceiling; that sensitivity remains a separate next phase.

## One-state AR-boundary sensitivity

v0.15.3 keeps the reviewed one-state architecture and evaluates the fixed
maximum-absolute-AR grid `{0.98, 0.99, 0.995, 0.999}`. The 0.98 result is
loaded from v0.15.1 and hash-validated; only the three higher values are fit.
All other configuration values, folds, training-only standardizers, restarts,
sampling seeds, sample count, and metrics remain identical.

```bash
python -m lane_residuals.cli.expanded_ar_boundary \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --two-state-convergence-directory \
  "outputs/models/two_state_convergence_v0152" \
  --output-directory "outputs/models/one_state_ar_boundary_v0153"
```

The decision contract is deliberately conservative. Development support
requires fewer boundary-contact station-folds, improved macro coverage error,
non-worse energy/lag/RMSE checks, consistent fold directions, and no failed or
selected nonconverged fit. If more than one ceiling passes, the smallest is
reported. Because all folds remain portions of one outing, even that result is
not an unbiased final selection and must be confirmed on independent outings
before freezing the planner model.

## Limitations and next gate

- The effective primary support is one same-day outing divided into four clean
  technical groups, not four independent journeys or 4,084 independent frames.
- Leave-one-group-out evaluation measures within-outing transfer only.
- The two-state correction is fixed and cannot be finalized on these four
  drives.
- State-specific linear means and diagonal AR terms cannot express nonlinear
  condition effects or cross-station lag coupling.
- Gaussian state emissions approximate heavy tails only through a finite
  mixture.
- Dwell times are geometric/condition-dependent; there is no explicit duration
  model.
- RLMB remains a pseudo-reference, and the accepted target retains the
  documented approximately 23.5 ms timing mismatch as label noise.
- The frame interval is near 80 ms but not constant; the AIOHMM is a discrete-step,
  not continuous-time, model.

The current data are sufficient for implementation and exploratory Gaussian
versus AIOHMM comparison. They are not sufficient for final state-count tuning,
broad feature search, RC-GAN claims, or an untouched thesis test. The reviewed
one-state result favors autoregression without latent switching on the current
corpus, and the corrected two-state audit shows that this conclusion was not
caused by premature EM stopping. The separate AR-boundary audit remains
development evidence until it is confirmed on independent outings.
The acquisition gate remains 8--12 independent physical drives, with at least
two locked final test drives and preferably continuous 2--5 minute recordings.
