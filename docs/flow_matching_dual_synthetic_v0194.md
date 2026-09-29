# v0.19.4 synthetic dual flow prototype

## Decision and scope

PR #25 merged on main as `7a98804`, with its exact archive reader and
synthetic straight-path arithmetic. This next **engineering-only** branch
implements both requested variants on caller-provided synthetic arrays:

| Variant | Velocity inputs | Temporal behavior |
|---|---|---|
| Unconditional | Current 21-dimensional latent and bridge time | Independent per-frame draws on identical evaluation rows; a temporal null |
| Conditional | Same latent/time, six current causal conditions, preceding residual and explicit start flag | Teacher-forced observed previous residual during synthetic training; generated previous residual during free-running sampling |

Both use a small one-hidden-layer tanh NumPy field trained by Adam on the same
straight-path objective, with independent normal base noise and newly sampled
uniform bridge time at each epoch. No optional ML dependency or real-data
entry point is added. The shared target and sign remain EDP-minus-RLMB H100
**pseudo-residuals**, but this version learns only from synthetic values. The
proposed RC-GAN-to-flow thesis scope change still needs a supervisor-visible
decision before a real fit.

`fit_synthetic_flow(y, x, offsets, mode=...)` accepts *training rows only*, in
the order of the **conditioned** sequence offsets. Both modes fit per-station
residual means/scales from exactly those rows; the conditional mode also fits
its six feature means/scales there. Neither fits to held-out rows. The
standardized target and independent base noise live in one coordinate system.
At starts, the standardized previous residual is zero and a separate start
indicator is one, so this sentinel cannot be confused with an ordinary
observed zero. At later frames the previous physical residual is standardized
using the training parameters. The unconditional mode ignores conditions and
past residual by construction. The conditional mode uses the six-feature
schema only; it does not read RLMB or future observations as current inputs.
Every nonconstant training column retains its own fitted standard deviation,
even when its physical-unit variation is small (for example curvature).
Exactly constant columns use scale one and standardized value zero. Both fit
and sampling require a nonnegative integer seed; fit defaults to zero.

Sampling returns physical residuals in `[draw, sequence, padded-frame, 21]`,
with exactly zero padding. A fixed random seed defines normal noise for the
entire requested grid; both modes can use the same seed and rows. Each sample
and sequence resets history once. The conditional sampler integrates the
learned velocity in standardized coordinates by the existing Euler solver,
inverse transforms the new residual, then feeds *that sample* back. The
observed predecessor appears only in the synthetic training objective.

Focused synthetic tests check loss decrease and determinism, conditional
feature sensitivity versus the unconditional null, conditioned-offset start
behavior, physical inverse transforms, analytic free-running feedback and
reset, explicit start features, padded zeros, invalid inputs and Euler
step-halving against a known time-dependent field. There is no trained
model file, archive training command, likelihood, reported RMSE or physical
outing interpretation. Euler convergence on a learned field remains an
empirical check for any later reviewed cohort; this exact analytic test alone
does not establish it.

## Evidence / assumptions / next gate

- **Published data:** batch02 has 376 geometric profiles and only 134 complete
  six-feature rows, with 26 short condition sequences and 108 transitions.
  Physical outing identities and physical input age remain unproved. RLMB is a
  pseudo-reference, not ground truth.
- **Prototype assumptions:** independent Gaussian noise/data coupling,
  per-station training-only standardization, a tanh field, and one-step
  generated residual memory. These are testable modeling choices, not facts
  established by MCAP.
- **Next gate:** acquire independently identified outings with sufficiently
  long contiguous causal-feature support and a reviewed reference/clock
  contract; then predeclare the cohort, physical-drive splits, same-row
  baselines, proper distributional and temporal metrics, training-only
  hyperparameter/early-stopping rules, solver convergence checks, online
  availability of previous residual for the intended use, and a supervisor
  scope decision. Implement a real-data adapter and model persistence only
  after those gates. Do not fit either model on batch02 merely because this
  synthetic implementation exists.
