# Minimal Lane-Residual Model

This is a clean, deliberately small implementation for understanding the
lane-estimation residual before adding contextual inputs or complex models.
It is separate from the larger LEEM experiment repository.

## Scope of this first version

Included:

- one ground-truth path and one estimated path per sample;
- a shared longitudinal reference coordinate, `s`, for both paths;
- interpolation to explicitly selected evaluation stations;
- signed lateral residuals measured along the ground-truth left normal;
- conversion of several independent path pairs into a residual matrix;
- one visual demonstration and focused unit tests.

Not included yet:

- Gaussian fitting;
- condition variables such as weather, speed, curvature, or sensor status;
- temporal or sequence modelling;
- automatic geometric path matching;
- planner integration.

Keeping these items out is intentional. The residual definition and the path
alignment assumption should be verified first.

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
```

The demonstration writes `outputs/residual_demo.png` and prints the residual
vector.

## Package layout

```text
src/lane_residuals/residuals.py  path validation and residual calculation
src/lane_residuals/plotting.py   path/residual visualisation
examples/run_demo.py             deterministic synthetic example
tests/                            definition and sign-convention tests
```

## Next checkpoint

Before fitting any probability distribution, replace or supplement the demo
with a few representative real path pairs and answer:

1. Are the two paths already expressed in the same coordinate system?
2. Does the data provide a common reference station or another correspondence?
3. Is the left-positive sign convention correct for the project?
4. Which station range is available reliably across samples?
5. Are any path pairs invalid, truncated, or geometrically ambiguous?

Only after those checks should independent residual vectors be collected as
rows of a matrix and used to fit the first unconditional Gaussian model.
