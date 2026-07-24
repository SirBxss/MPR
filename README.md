# Minimal Path-Residual Model (MPR)

MPR is a deliberately small project for understanding path discrepancies
before transferring the workflow to the larger LEEM thesis implementation.

Version 0.3 adds the missing real-data bridge:

```text
MCAP
→ embedded Protobuf decoding
→ synchronized map/sensor road frames
→ ego-segment selection
→ shared reference-station assignment
→ 11-dimensional residual vectors
→ descriptive multivariate Gaussian fit
```

The Gaussian and residual definitions from Version 0.2 remain unchanged.

## Scientific interpretation

The initial configured comparison is:

```text
surrogate reference: /adp/road_lane_map_based
estimate:            /adp/lane_topology_sensor_based
schema:              Adp.Perception.Road
```

This output must be described as:

> sensor-based versus map-based lane-path discrepancy

The map-based topic has not been established as ground truth. Consequently,
Version 0.3 does not support a claim about absolute sensor error or sensor
accuracy. BMW signal documentation or supervisor confirmation is required
before changing that interpretation.

The two paths must also be expressed in the same local coordinate frame.
Processing is intentionally blocked until the operator explicitly confirms
that assumption with `--assume-same-frame`.

## Residual definition

For a reference path and an estimated path at shared reference station `s`,

```text
p_ref(s) = [x_ref(s), y_ref(s)]
p_est(s) = [x_est(s), y_est(s)].
```

The reference left unit normal is

```text
n_ref(s) = [-t_y(s), t_x(s)],
```

and the signed lateral discrepancy is

```text
e(s) = n_ref(s)^T [p_est(s) - p_ref(s)].
```

Positive values lie to the left of the reference path with respect to
increasing `s`.

The real-data pipeline uses:

```text
s = [0, 5, 10, ..., 50] m
```

so one accepted road-frame pair produces one vector in `R^11`.

## How correspondence is established

The two MCAP topics do not automatically provide identical point stations.
Version 0.3 therefore performs these steps before calculating a residual:

1. Select the ego-lane segment using message metadata when available.
2. Otherwise select the valid segment nearest the ego origin. Coverage is only
   a tie-breaker, so a longer adjacent lane does not replace the likely ego lane.
3. Recompute geometric arc length along the map-based segment.
4. Define `s=0` by projecting the local ego origin `(0, 0)` onto that segment.
5. Project every sensor-based vertex onto the reference polyline.
6. Assign each sensor vertex the corresponding projected reference station.
7. Reject non-monotonic, truncated, distant, or otherwise invalid path pairs.
8. Interpolate both paths at the explicit evaluation stations.

This preprocessing establishes the shared-`s` assumption required by the
existing `Path2D` and `residual_vector` implementation.

## Installation

Create or activate the project virtual environment and run:

```bash
python -m pip install -e ".[mcap]"
```

The `mcap` extra installs:

- `mcap`;
- `mcap-protobuf-support`;
- `protobuf`.

The core synthetic geometry and Gaussian tests do not require these optional
packages.

## First MCAP run

Start with one recording and at most 100 accepted frame pairs:

```powershell
mpr-mcap `
  ".\data\mcap_data\2025-05-27_13-48-41_2025-05-27_13-49-01_MCAP_000054.mcap" `
  --assume-same-frame `
  --max-samples 100 `
  --output-directory ".\outputs\mcap_v03"
```

Equivalent module command:

```powershell
python -m lane_residuals.cli `
  ".\data\mcap_data\your_recording.mcap" `
  --assume-same-frame
```

Do not add `--assume-same-frame` merely to bypass the guard. First confirm from
the signal documentation or a trusted visualization that both topics use the
same origin, axes, handedness, and units.

## Generated local outputs

The command writes:

| File | Purpose |
|---|---|
| `residual_dataset.npz` | Stations, residual matrix, timestamps, sync deltas |
| `records.csv` | Row-level provenance and preprocessing diagnostics |
| `summary.json` | Acceptance/rejection audit, means, standard deviations |
| `mcap_diagnostics.png` | Path overlay, residuals, timing, rejections |
| `gaussian_model.npz` | Descriptive fitted mean and covariance |
| `gaussian_diagnostics.png` | Marginal interval and spatial correlation |
| `gaussian_summary.json` | Fit settings and in-sample NLL |

The Gaussian fit is descriptive and in-sample. Its reported NLL is not a
generalization result. A valid train/test comparison requires recording-session
groups and is deliberately postponed until geometry is validated.

All raw MCAP and derived outputs are ignored by Git. They may contain
BMW-confidential information and must not be pushed to the public repository.

## Rejection audit

The pipeline records stable rejection reasons, including:

- insufficient reference or estimate coverage;
- non-monotonic estimate-to-reference projection;
- excessive projection distance;
- implausibly large residual;
- invalid or degenerate path geometry;
- missing usable lane segments.

Rejections are evidence about the data and assumptions. They must be inspected,
not silently discarded.

## Gaussian baseline

For `N` accepted path pairs with `H=11` stations, the matrix is:

```text
E = [e_1^T; ...; e_N^T] in R^(N x H).
```

The unconditional model assumes:

```text
e_i ~ N(mu, Sigma), independently across accepted path-pair rows.
```

Maximum-likelihood estimates are:

```text
mu_hat    = (1 / N) sum_i e_i
Sigma_hat = (1 / N) sum_i (e_i - mu_hat)(e_i - mu_hat)^T + lambda I.
```

The covariance captures dependence between look-ahead stations within one
residual path. It does not model temporal dependence between consecutive
frames.

## Tests

After installation:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- residual sign and geometry;
- Gaussian fitting, likelihood, and correlated sampling;
- dynamic road-message extraction;
- timestamp and metadata preservation;
- one-to-one synchronization;
- ego-segment selection;
- polyline projection and shared station assignment;
- rejection reporting and saved dataset structure.

## Package layout

```text
src/lane_residuals/residuals.py      Path2D and signed residual definition
src/lane_residuals/gaussian.py       Unconditional Gaussian model
src/lane_residuals/mcap_io.py        Streaming Protobuf MCAP road decoder
src/lane_residuals/preprocessing.py  Sync, selection, projection, dataset audit
src/lane_residuals/plotting.py       Geometry, extraction, Gaussian diagnostics
src/lane_residuals/cli.py            mpr-mcap command
tests/                               Focused regression tests
```

## Required validation before all ten files

For the first 100 accepted pairs:

1. Inspect several map/sensor path overlays.
2. Confirm left/right sign convention.
3. Check that `s=0` is at the ego position.
4. Inspect timestamp differences.
5. Review all rejection categories and rates.
6. Check mean, spread, and spatial correlation for obvious geometric failures.
7. Confirm the semantic role and coordinate frame of both topics.

Only then process all ten MCAP chunks. The chunks belong to two contiguous
recording sessions, so individual chunks must not be randomly split between
training and testing.
