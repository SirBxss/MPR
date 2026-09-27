# v0.19.3: archive admission and conditional flow foundation

## Observations and boundary

PR #24 is merged on main at `95745ea` (2026-09-25). The one completed,
published v0.19.2 batch02 extraction provides 376 finite geometric
EDP-minus-RLMB pseudo-residuals, 134 complete six-feature rows, 26 complete
condition sequences and 108 adjacent transitions, with a 10-frame longest
complete sequence. The four technical recordings have unknown physical-session
relationships; 116 of 134 complete rows come from recording 04. No new MCAP
run, outing lock, training set or independent test drive follows from these
observations. The target remains 21 signed H100 stations; RLMB independence
and physical ground-truth status are unproven.

The reader in `io.exploratory_archive.load_exploratory_archive` checks the
published summary's *pinned* SHA-256, the nested artifact hashes, fixed
extraction lineage, exact NPZ keys/dtypes/shapes/grid/feature order, audit
identity including exact decimal uint64 timestamps, condition-to-profile
indices, file-local sequence breaks and reported support. It returns
recording-local arrays, not a drive-grouped model dataset. Its optional
`expected_summary_sha256` is for explicit review of a differently published
fixture; the default admits only the independently reconciled batch02 bytes.
Each file is read into the bytes used for both hashing and parsing, so a
replacement during validation cannot substitute unverified values. Residual
and condition *values* have no second copy in the audit: they are protected
only by the hash chain to the pinned summary. Semantic checks cover identities,
structure and temporal support, not an independent numeric reconstruction.
`python -m lane_residuals.cli.exploratory_archive DIRECTORY` validates the
three unzipped files read-only and prints aggregate counts. It cannot redo
raw geometry, recover a physical session, establish source independence,
verify raw MCAP hashes locally or prove an input was physically online.

## Two proposed comparisons are separate questions

| Question | Current evidence | Prerequisite for a performance claim |
|---|---|---|
| Refit old families on the pooled development set | The old 4,602 frames and the new 134 complete rows have different provenance and availability gates; the new data have no accepted drive identities. | Define a reviewed common cohort, folds, training-only transforms, conditions and scoring rows. Preserve an untouched physical outing and avoid pooling any data from its session. Do not reopen the frozen within-outing model selection. |
| Fit old families on new rows alone | One technical recording supplies 87% of complete rows; the longest observed feature-complete sequence is ~0.9 s. | A *descriptive* Gaussian comparison may be planned separately on the identical complete subset with uncertainty and explicit no-generalization limits. AR/AIOHMM or flow performance comparisons need longer contiguous and independently identified outings. |

RMSE alone is inadequate for a probabilistic residual generator. On exactly
the same evaluation rows, report station-wise error of a declared point
summary *plus* proper sample-based distribution and calibration metrics,
tail/coverage behavior, lag-one/sequence structure and uncertainty across
physical outings. Do not interpret a nearly tied RMSE as proof of equivalent
uncertainty quality. Pooled-training and new-only fits cannot be compared on
their own training rows; a future new-data generalization comparison needs
the same *held-out physical drives*, not technical-file folds mislabelled as
independent drives. The old cohort and batch02 also have different selection
mechanisms, so a score shift alone cannot identify a causal dataset effect.

## Conditional flow candidate, with its testable math

The original thesis plan named RC-GAN as its third family. We propose
conditional straight-path flow matching as its replacement, subject to an
explicit supervisor-visible scope decision before any real fit. Its velocity
regression avoids adversarial optimization while serving the same goal of
sample-based residual uncertainty; neither approach promises better RMSE.
The `docs/model_comparison.md` gate against fitting a new family on the
current one-outing corpus applies **unchanged** to flow matching. Synthetic
bridge/sampler arithmetic does not constitute a fitted thesis model. A
continuous-normalizing-flow likelihood would require a separately implemented
and verified divergence integral; this prototype supplies none. Following the
straight-line/rectified-flow objective of
[Liu et al. (2022)](https://arxiv.org/abs/2209.03003), draw independent
standard-normal noise `z0`, a training residual `y` and `tau ~ U[0,1]`, then
form `z_tau = (1-tau) z0 + tau y`, target velocity `y-z0`. A future network
could minimize mean squared error between its field
`v_theta(z_tau, tau, x_t, y_(t-1))` and this target, using training-only
standardization fitted strictly within each accepted fold. Its first-frame
previous residual is zero. This contract conditions only on the six existing
prediction-time features and the **observed previous residual during
training**; future work must declare whether the previous residual is
available for online use. At inference, each sequence starts with zero
state, draws fresh noise at each frame, integrates `dz/dtau = v_theta`, and
passes back the **generated** previous residual. No future/current reference
is an input. The temporal direction follows the autoregressive factorization
studied in [ElGazzar and van Gerven, *Probabilistic Forecasting via Autoregressive Flow Matching* (2025)](https://arxiv.org/abs/2503.10375),
though no architecture or trained field has been adopted here.

`domain.flow_matching` implements the bridge, exact velocity target, simple
fixed-step Euler solver and padded free-running sampler with synthetic tests.
The arbitrary user-provided callable is **not a trained network**. An ODE
sampler with this loss supplies samples, but it does not automatically supply
tractable log probability; likelihood-based metrics would require a separately
verified density computation. Choice of capacity, solver steps, noise scaling,
normalization and optimization must be predeclared and checked on real
independently grouped training data. Before any fit, specify whether the
initial zero means zero metres or zero standardized units, add an explicit
sequence-start indicator (zero can also be a real residual), and map
`conditioned_residuals_m` using `conditioned_sequence_offsets` rather than
geometric offsets. A conditioned sequence resets even if a geometric-only
predecessor exists. Predeclare a solver-step convergence check on the
*evaluation metrics*, with any solver selection confined to training/validation
data; a few Euler steps can bias dispersion. Label any call with an observed
previous residual as teacher-forced, never as free-running simulation. No
hyperparameter sweep or real-data fit is part of this patch.

| Category | Statement |
|---|---|
| Data shows | Finite pseudo-residuals and 134 condition-ready rows with short file-local support; the loader checks pinned bytes and audit structure. |
| Current code assumes | A straight independent Gaussian noise/data coupling and one preceding residual for the candidate's synthetic mathematical contract; source clock and recorded availability semantics are unchanged. |
| Hypothesis | A learned conditional velocity field might represent wider and time-dependent uncertainty than Gaussian baselines when sufficiently many independently identified sequences exist. |

## Next bounded experiment decision

First obtain prospectively identified physical outings with SENSOR EDP/RLMB
H100 pairs and long contiguous *causal* condition support, or formally review
a different reference and availability contract if those cannot be obtained.
Then predeclare a cohort/split and same-row baselines before implementing a
trainable field (optional deep-learning dependency), save/load and common
sample evaluator. On batch02 alone, at most a separately approved descriptive
common-row Gaussian check is feasible. The 232 future-source odometry cases
remain excluded from the six-feature population; no imputation, clock shift
or new speed definition is authorized by the flow proposal.
