# Minimal Lane-Residual Model

This deliberately small project implements the first complete statistical
baseline for lane-estimation error. Version 0.1 converted aligned path pairs
into residual vectors. Version 0.2 fits one **unconditional multivariate
Gaussian** to those vectors.

The implementation is separate from the larger LEEM experiment repository so
that every assumption can be understood and tested before adding conditions,
latent regimes, neural networks, or planner integration.

## Version 0.2 scope

Included:

- one ground-truth path and one estimated path per sample;
- shared longitudinal reference coordinate `s` and explicit stations;
- signed lateral residuals along the ground-truth left normal;
- an `N x H` residual matrix;
- maximum-likelihood Gaussian mean and covariance fitting;
- explicit diagonal covariance regularization;
- joint log-density, mean test NLL, and correlated path sampling;
- residual and Gaussian diagnostic figures;
- twelve focused unit tests.

Still excluded:

- condition variables such as weather, speed, curvature, or sensor status;
- time dependence between consecutive path pairs;
- mixture distributions, HMMs, GANs, or other complex models;
- automatic geometric path matching;
- planner integration.

## Mathematical definition

For path-pair sample `i`, let the aligned ground-truth and estimated positions
at reference station `s` be

```text
p_gt_i(s)  = [x_gt_i(s),  y_gt_i(s)]
p_est_i(s) = [x_est_i(s), y_est_i(s)].
```

The ground-truth unit tangent and left unit normal are

```text
t_gt_i(s) = d p_gt_i(s) / ds / ||d p_gt_i(s) / ds||
n_gt_i(s) = [-t_y(s), t_x(s)].
```

The signed lateral residual is

```text
e_i(s) = n_gt_i(s)^T [p_est_i(s) - p_gt_i(s)].
```

Positive therefore means that the estimated path lies to the **left** of the
ground-truth path with respect to increasing `s`. The evaluation stations are
always passed explicitly; this project does not silently assume 21 stations.

For `N` independent path pairs evaluated at `H` common stations, the residual
vectors form

```text
E = [e_1^T; ...; e_N^T] in R^(N x H).
```

The unconditional model assumes

```text
e_i ~ N(mu, Sigma), independently for i = 1, ..., N.
```

The fitted maximum-likelihood parameters are

```text
mu_hat    = (1 / N) sum_i e_i
Sigma_hat = (1 / N) sum_i (e_i - mu_hat)(e_i - mu_hat)^T + lambda I.
```

The divisor is `N`, because this is the likelihood estimator, not the unbiased
sample-covariance estimator. `lambda` is an explicitly reported diagonal
regularization in squared residual units. It prevents numerical failure when
the empirical covariance is singular or nearly singular.

## Central data assumption

`s` is the shared ground-truth reference station assigned to the path points.
It is not recomputed independently for the estimated path. Consequently,
ground-truth and estimated positions with the same `s` are assumed to
correspond.

This assumption is suitable for the first experiment if the source data is
already aligned. If real data does not provide such correspondence, path
matching must become a separate preprocessing step and be validated before
statistical modelling.

## Install and run

From this directory:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/run_demo.py
python examples/run_gaussian_demo.py
```

The first demonstration writes `outputs/residual_demo.png`. The Gaussian
demonstration uses independent synthetic training and test matrices, writes
`outputs/gaussian_demo.png`, and prints the test negative log-likelihood.

## Package layout

```text
src/lane_residuals/residuals.py  path validation and residual calculation
src/lane_residuals/gaussian.py   unconditional Gaussian fit, NLL, and sampling
src/lane_residuals/plotting.py   geometry and Gaussian diagnostics
examples/run_demo.py             deterministic residual-geometry example
examples/run_gaussian_demo.py    controlled statistical example
tests/                            definition and sign-convention tests
```

## Interpretation limits

- The Gaussian is **unconditional**: every path pair shares the same mean and
  covariance regardless of driving conditions.
- The covariance represents dependence between stations within one residual
  path. Independence is assumed only between different rows/path pairs.
- NLL values are comparable only when models use the same residual definition,
  units, dimension, and evaluation stations.
- A continuous density can exceed one, so its log-density can be positive and
  the resulting NLL can be negative. Lower test NLL is still better when the
  comparison is otherwise valid.
- The plotted 95% interval is marginal at each station. It is not a 95%
  simultaneous coverage region for the entire residual path.
- Regularization affects likelihood and sampling and must therefore be selected
  without test-set leakage and reported in experiments.

## Next checkpoint after Version 0.2

Before interpreting this baseline on real data, replace or supplement the demo
with representative path pairs and answer:

1. Are the two paths already expressed in the same coordinate system?
2. Does the data provide a common reference station or another correspondence?
3. Is the left-positive sign convention correct for the project?
4. Which station range is available reliably across samples?
5. Are any path pairs invalid, truncated, or geometrically ambiguous?

Then create a drive/sequence-aware train-validation-test split, fit only on the
training rows, select regularization on validation data, and report test NLL
plus calibration and covariance diagnostics. The next model should be added
only after this baseline has been validated and its failures are identified.
