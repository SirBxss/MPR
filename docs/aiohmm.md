# MPR v0.11 autoregressive input-output HMM

## Purpose and scientific boundary

The AIOHMM is the second of the three fixed MPR thesis model families:

1. conditional multivariate Gaussian;
2. autoregressive input-output hidden Markov model;
3. RC-GAN, after the independent-drive/data-volume gate.

Its purpose is narrow: test whether explicit temporal memory and a small latent
state can improve held-out generative realism over the v0.10 Gaussian temporal
null while every data, split, transform, and metric decision remains unchanged.
It does not redefine the target, repair the pseudo-reference, search new
features, or authorize final model selection from the present two drives.

The input is the immutable v0.9 physical-unit tensor contract:

- six prediction-time condition features at each retained frame;
- 21 signed pseudo-residual stations at `0, 5, ..., 100 m`;
- 13 recording-local/gap-local sequences and 1,770 retained frames in the
  reviewed development cohort;
- exact lengths, masks, timestamps, and recording/drive/pair provenance;
- leave-one-physical-drive-out folds and transforms fitted on training drives
  only.

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
| latent states | 3 | small fixed regime capacity without held-out state-count search |
| EM restarts | 3 | expose initialization sensitivity |
| maximum EM iterations | 30 | bounded generalized-EM run |
| AR absolute bound | 0.98 | constrain free-running instability |
| emission pooling penalty | 10.0 | shrink rare-state mean/AR parameters toward the shared AR regression |
| state covariance pooling | 0.50 | regularize state-specific full covariances |
| diagonal covariance shrinkage | 0.15 | stabilize spatial covariance estimates |
| minimum state occupancy | 0.01 | reject strongly collapsed fitted states |
| Monte Carlo samples | 128 | identical common evaluator scale as v0.10 |

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

The transition update is numerical, covariance regularization changes the exact
maximum-likelihood M-step, and AR coefficients are clipped. Therefore observed
training likelihood is not guaranteed to increase on every iteration. The code
retains the best valid observed training-likelihood state, records decreases,
reports nonconvergence, and stops before accepting a state below the configured
occupancy floor.

Hidden-state labels are exchangeable. After fitting, parameters are reordered
by ascending zero-condition emission-intercept profile RMS, then mean intercept
and median AR. This creates deterministic diagnostic labels for comparing
restarts. It does not turn a state index into a physical class.

## Restart and leakage policy

Every physical-drive fold fits the same architecture with deterministic restart
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

## Teacher-forced density versus free-running generation

Likelihood evaluation uses the observed `y_(t-1)` when computing the emission
at frame `t`. This is teacher forcing and answers whether the fitted conditional
density explains the observed next frame.

Sampling draws `y_0` from the training-only marginal reset prior and recursively
uses the generated `y_(t-1)` afterward. This is free-running and answers whether
the model can generate realistic complete sequences without seeing target
residuals. A model can therefore achieve a strong teacher-forced
NLL and still accumulate bias, become under-dispersed, or produce poor energy
score in free-running mode. Both results must be reported.

## Evaluation

The primary cross-model evidence is unchanged from v0.10:

- physical-unit sample-mean RMSE;
- multivariate 21-dimensional energy score;
- marginal 95% coverage;
- observed/generated station-wise lag-one correlation and median absolute
  error.

Teacher-forced standardized and Jacobian-adjusted physical NLL are secondary
AIOHMM diagnostics because an RC-GAN need not provide a normalized likelihood.

Model-specific diagnostics include:

- posterior state occupancy and entropy on every held-out drive;
- maximum posterior probability;
- mean and variable condition-dependent transition matrices;
- self-transition probability and geometric dwell estimate;
- station/state AR coefficient ranges and clipping;
- covariance minimum eigenvalues;
- EM likelihood history, best iteration, convergence, warnings, and restart
  stability.

An AIOHMM earns its place only if temporal and distributional/generative
metrics improve consistently across physical drives. A pooled lag-one win alone
does not justify the added model if energy score, calibration, or one held-out
drive deteriorates materially.

## Command

Install the current checkout and run the reviewed configuration:

```bash
python -m pip install -e ".[mcap]"
python -m lane_residuals.cli.sequence_aiohmm \
  "outputs/datasets/sequential_dataset_v090" \
  --output-directory "outputs/models/aiohmm_sequence_v0110"
```

The output directory must be absent or empty. The workflow fails before fitting
if any source filename, hash, fold member, frame count, or stored training-only
transform differs from v0.9.0.

## Limitations and next gate

- The effective independent support is two physical drives, not 1,770 frames.
- The three-state choice is exploratory and cannot be selected or finalized on
  these two drives.
- State-specific linear means and diagonal AR terms cannot express nonlinear
  condition effects or cross-station lag coupling.
- Gaussian state emissions approximate heavy tails only through a finite
  mixture.
- Dwell times are geometric/condition-dependent; there is no explicit duration
  model.
- RLMB remains a pseudo-reference, and the accepted target retains the
  documented approximately 23.5 ms timing mismatch as label noise.
- The frame interval is near 80 ms but not constant; v0.11 is a discrete-step,
  not continuous-time, model.

The current data are sufficient for implementation and exploratory Gaussian
versus AIOHMM comparison. They are not sufficient for final state-count tuning,
broad feature search, RC-GAN claims, or an untouched thesis test. The acquisition
gate remains 8--12 independent physical drives, with at least two locked final
test drives and preferably continuous 2--5 minute recordings.
