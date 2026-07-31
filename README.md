# Minimal Path-Residual Model (MPR)

MPR is a deliberately small project for understanding path discrepancies
before transferring the workflow to the larger LEEM thesis implementation.

Version 0.3.4 keeps the v0.3.3 fail-safe lane audit and adds an evidence-first
probe for the production estimated-drive-path Protobuf schema:

```text
MCAP
→ embedded Protobuf decoding
→ source-time synchronization of map/sensor road frames
→ drive-path extraction or paired-boundary centreline construction
→ all-original-segment inventory, including reconstruction failures
→ strict metadata-confirmed sensor ego-segment selection
→ 20/30/40/50 m two-sided geometric coverage analysis
→ decoded direct-path schema and field-presence audit
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
Version 0.3.4 does not support a claim about absolute sensor error or sensor
accuracy. BMW signal documentation or supervisor confirmation is required
before changing that interpretation.

The two paths must also be expressed in the same local coordinate frame.
Processing is intentionally blocked until the operator explicitly confirms
that assumption with `--assume-same-frame`.

The v0.3.2 audit showed that all 16 accepted pairs used explicitly non-ego
fallback sensor segments and produced an approximately one-lane-width
discrepancy. The metadata-confirmed sensor ego segments were short or failed
reconstruction. Those 16 vectors are invalid for modelling and must be
discarded.

Version 0.3.4 therefore rejects a frame as `ego_segment_unavailable` when ego
metadata points to geometry that cannot be reconstructed. It never substitutes
a surviving adjacent lane. When ego metadata is entirely absent, the estimate
is rejected as `ego_metadata_missing` by default.

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
Version 0.3.4 therefore performs these steps before calculating a residual:

1. Extract a provided drive path when its range is valid.
2. If a sensor-topology segment has no drive path, construct its centreline by
   resampling and averaging its paired left/right lane boundaries.
3. Pair frames by embedded source timestamp by default while also reporting
   the MCAP-log-time difference.
4. Inventory every original map and sensor segment, including failed
   reconstructions and their boundary/range failure reasons.
5. Select the ego-lane segment using message metadata.
6. Reject the sensor frame when the metadata-confirmed ego segment is
   unavailable, or when ego metadata is missing.
7. Recompute geometric arc length along the map-based segment.
8. Define `s=0` by projecting the local ego origin `(0, 0)` onto that segment.
9. Project every sensor-based vertex onto the reference polyline.
10. Assign each sensor vertex the corresponding projected reference station.
11. Count coverage independently at 20, 30, 40, and 50 m only when the common
    selected-path range satisfies both `s_min <= 0` and `s_max >= horizon`.
12. Reject non-monotonic, truncated, distant, or otherwise invalid path pairs.
13. Interpolate both paths at the explicit evaluation stations.

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

Start with one recording and audit at most 100 synchronized pairs:

```powershell
mpr-mcap `
  ".\data\mcap_data\2025-05-27_13-48-41_2025-05-27_13-49-01_MCAP_000054.mcap" `
  --assume-same-frame `
  --max-pairs 100 `
  --output-directory ".\outputs\mcap_v034"
```

Equivalent module command:

```powershell
python -m lane_residuals.cli `
  ".\data\mcap_data\your_recording.mcap" `
  --assume-same-frame `
  --time-basis source `
  --audit-horizons 20 30 40 50
```

Do not add `--assume-same-frame` merely to bypass the guard. First confirm from
the signal documentation or a trusted visualization that both topics use the
same origin, axes, handedness, and unit.

## Generated local outputs

The command writes:

| File | Purpose |
|---|---|
| `residual_dataset.npz` | Stations, residual matrix, timestamps, sync deltas |
| `records.csv` | Row-level provenance and preprocessing diagnostics |
| `pair_audit.csv` | Every considered pair, both time deltas, selected IDs, coverage, and rejection |
| `candidate_segments.csv` | Every map/sensor segment candidate and selection evidence |
| `summary.json` | Acceptance, timing, lane-selection, and horizon-coverage audit |
| `path_source_candidates.json` | Container metadata for direct ego/path topic candidates |
| `estimated_drive_paths_structure.json` | Separate descriptor/presence report from `mpr-probe-path-source` |
| `mcap_diagnostics.png` | Cropped path overlay, residuals, timing, rejections, horizons, selection methods |
| `lane_association_audit.png` | Labelled map/sensor candidate segments; `*` marks each selection |
| `gaussian_model.npz` | Optional descriptive fitted mean and covariance |
| `gaussian_diagnostics.png` | Optional marginal interval and spatial correlation |
| `gaussian_summary.json` | Optional fit settings and in-sample NLL |

The Gaussian fit is descriptive and in-sample. Its reported NLL is not a
generalization result. A valid train/test comparison requires recording-session
groups and is deliberately postponed until geometry is validated.

Version 0.3.4 does not fit the Gaussian by default. After the labelled lane
association is confirmed, add `--fit-gaussian` to generate the three Gaussian
outputs.

If no pair survives the configured 50 m checks, v0.3.4 still writes the pair,
candidate, timing, rejection, and horizon audits. This is intentional: failed
association or coverage must remain inspectable.

`--allow-estimate-fallback` is available only for diagnostic comparison when a
message contains no ego metadata. The CLI refuses to fit a Gaussian if accepted
rows include such fallback selection.

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
- unavailable explicitly identified ego segments;
- missing estimate ego metadata.

Rejections are evidence about the data and assumptions. They must be inspected,
not silently discarded.

Detailed reconstruction text remains in `candidate_segments.csv`, while
`summary.json` aggregates stable codes such as `implausible_lane_width`. This
prevents one summary key per measured boundary width.

`summary.json` also reports decoded, retained, and discarded message counts for
each road topic. This makes pre-synchronization losses, such as empty road
messages, explicit.

`horizon_coverage` in `summary.json` answers a narrower question: whether the
common path range begins at or before zero and reaches 20, 30, 40, or 50 m. It
does not establish that the selected lanes correspond or that their discrepancy
is plausible.

`records.csv` and `summary.json` explicitly report whether each selected path
came from a provided `drive_path` or was constructed from
`paired_boundaries`. The boundary-derived sensor centreline is a deterministic
preprocessing result, not a separately measured ground-truth path.

## Direct path-source candidates

Each run also inventories:

```text
/em/road/ego_lane_path       road_msgs/Road (ROS1)
/adp/estimated_drive_paths   Adp.Perception.EstimatedDrivePaths (Protobuf)
```

Their message counts and encodings are written to
`path_source_candidates.json`. The first still needs ROS1 message decoding.
Version 0.3.4 decodes the second only for structural inspection; it does not yet
convert it into `Path2D`.

Run the production Protobuf probe independently:

```powershell
python -m lane_residuals.path_probe_cli `
  ".\data\mcap_data\2025-05-27_13-48-41_2025-05-27_13-49-01_MCAP_000054.mcap" `
  --max-messages 20 `
  --output ".\outputs\mcap_v034\estimated_drive_paths_structure.json"
```

The report contains:

- nested production field paths and Protobuf types;
- enum symbols and observed enum names;
- oneof membership;
- field-presence counts;
- repeated-field length ranges;
- conservative candidates for keep-lane role, status/error, timestamp, initial
  pose/curvature, segment lengths, and curvature changes.

It exports no raw scalar numeric values or coordinates. The geometry converter
must only be implemented after these production fields are confirmed. The
similar ROS debug schema is useful context but is not accepted as proof that the
production Protobuf uses identical fields.

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
- source-time default pairing with separate source/log delta reporting;
- ego-segment selection;
- strict rejection of failed or missing estimate ego metadata;
- successful and failed original-segment audit records;
- two-sided 20/30/40/50 m coverage counts, including rejected pairs;
- container-level inventory of direct path-source candidates;
- descriptor-driven direct-path inspection without numeric payload export;
- bounded pair auditing even when zero residuals are accepted;
- stable reconstruction failure codes and message-load diagnostics;
- polyline projection and shared station assignment;
- rejection reporting and saved dataset structure.

## Package layout

```text
src/lane_residuals/residuals.py      Path2D and signed residual definition
src/lane_residuals/gaussian.py       Unconditional Gaussian model
src/lane_residuals/mcap_io.py        Streaming Protobuf MCAP road decoder
src/lane_residuals/path_source_probe.py  Direct-path schema/presence audit
src/lane_residuals/path_probe_cli.py     mpr-probe-path-source command
src/lane_residuals/preprocessing.py  Sync, selection, projection, dataset audit
src/lane_residuals/plotting.py       Geometry, extraction, Gaussian diagnostics
src/lane_residuals/cli.py            mpr-mcap command
tests/                               Focused regression tests
```

## Required validation before all ten files

For the first 100 synchronized pairs:

1. Inspect `lane_association_audit.png` and verify the labelled map/sensor IDs.
2. Verify that only metadata-confirmed ego sensor geometry can be accepted.
3. Inspect source-time and log-time differences separately.
4. Compare the 20, 30, 40, and 50 m geometric-coverage counts.
5. Confirm left/right sign convention and check that `s=0` is at the ego position.
6. Review all rejection categories and rates.
7. Confirm the semantic role and coordinate frame of both topics.
8. Only after association is validated, interpret the residual mean, spread,
   covariance, or Gaussian fit.

Before implementing `/adp/estimated_drive_paths` geometry, inspect
`estimated_drive_paths_structure.json` and confirm the keep-lane, validity,
timestamp, initial-pose/curvature, segment-length, and curvature-change paths.

Only then process all ten MCAP chunks. The chunks belong to two contiguous
recording sessions, so individual chunks must not be randomly split between
training and testing.
