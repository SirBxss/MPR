# Minimal Path-Residual Model (MPR)

MPR is the private data-validation bridge for the LEEM thesis. Version 0.3.8
does **not** create a residual training dataset. It audits estimator
availability across all recording files and tests two explicitly labelled
mathematical interpretations of the direct estimated drive path.

## v0.3.8 decision boundary

The validated production evidence is:

- `/adp/estimated_drive_paths` contains exactly one keep-lane path per audited
  message;
- 99 of 251 messages in the first fully audited recording were strict
  `KEEP_LANE + NO_ERROR` geometry candidates;
- 152 messages kept structurally valid spline arrays but explicitly reported
  `HIGH_CHI_2_FOR_MINIMAL_DISTANCE`;
- the observed sequence was 4 valid, 152 error-state, then 95 valid messages.

The 152 messages are therefore an estimator regime, not random malformed rows.
Removing them and training only on the 99 candidates would estimate geometry
conditional on availability and would introduce strong temporal selection
bias.

Version 0.3.8 keeps four stages separate:

```text
estimator state
→ converter state
→ synchronization state
→ comparator state and diagnostic metrics
```

A failure at one stage is never relabelled as a failure at another stage.
An adjacent path is never substituted for an unavailable keep-lane path.

## Explicit spline hypotheses

Let the production `segment_starts` values be treated, under a named
hypothesis, as strictly increasing boundaries

```text
b[0] < ... < b[m]
```

with interval lengths `L[i] = b[i+1] - b[i]` and production values
`q[i] = curvature_change[i]`.

Both hypotheses integrate

```text
dx/ds     = cos(theta)
dy/ds     = sin(theta)
dtheta/ds = kappa
```

but differ in curvature semantics:

| Hypothesis | Interval curvature rate |
|---|---|
| `curvature_rate__anchor_zero` | `dkappa/ds = q[i]` |
| `curvature_delta__anchor_zero` | `dkappa/ds = q[i] / L[i]` |

The initial `(x_0, y_0, theta_0, curvature_0)` state is assumed to be located
at `s=0`, which must lie inside the spline domain. This is a diagnostic
assumption, not confirmed BMW semantics.

`index_0` was not explicitly serialized in the audited production paths. Its
observed accessor value is an implicit Protobuf zero default. The index-anchor
hypothesis is therefore disabled by default and can operate only when the field
is explicitly present.

Position integration uses exact straight/circular branches and adaptive
8/16-point Gauss-Legendre quadrature for linearly changing curvature. Each
curve is checked by halving the sampling step, with default convergence limits
of 1 mm in position and `1e-4` rad in heading. Variable interval counts are
supported; 3–7 intervals are observations, not hard-coded limits.

Passing these checks means only:

> mathematically consistent under the named hypothesis

It does not confirm field meaning, coordinate frame, units, sign convention,
timestamp latency, or signal independence.

## Comparator—not ground truth

The diagnostic comparator is:

```text
/em/road/ego_lane_path    road_msgs/Road (ROS1)
```

Version 0.3.8 decodes its embedded ROS1 schema without requiring a ROS
installation. It accepts only exactly one metadata-confirmed ego segment with a
direct `drive_path_range_`. It rejects boundary-derived centrelines, invalid
coordinate means, missing heading/curvature, non-increasing native stations,
and a station domain that does not contain zero.

The two curves are compared at the comparator's exact native stations without
rigid alignment, station shifting, scaling, reflection, or fitted transforms.
Diagnostics include lateral, along-track, heading, curvature, endpoint,
coverage, projection-monotonicity, Chamfer, Hausdorff, curvature-extreme, and
self-intersection measures.

`/em/road/ego_lane_path` may share upstream lineage with the estimated path. It
is therefore called a comparator, not ground truth. Geometric agreement can
validate serialization or converter mathematics but cannot establish absolute
sensor error.

## Installation

```powershell
python -m pip install -e ".[mcap]"
python -m unittest discover -s tests -v
```

The MCAP extra installs Protobuf and ROS1 decoder support. The ROS1 decoder uses
the embedded `ros1msg` definition; a local ROS environment is not required.

## Run the complete ten-file audit

First create a local session map outside the public repository. It must map
every MCAP basename to the real contiguous recording session:

```json
{
  "first_chunk.mcap": "session_a",
  "second_chunk.mcap": "session_a",
  "third_chunk.mcap": "session_b"
}
```

The labels are replaced by opaque `session_###` identifiers in outputs.

Then run:

```powershell
python -m lane_residuals.geometry_validation_cli `
  ".\data\mcap_data" `
  --expected-file-count 10 `
  --session-map ".\config\mcap_sessions.private.json" `
  --comparison-max-delta-ms 20 `
  --sync-sensitivity-ms 5 10 20 50 `
  --max-step-m 0.25 `
  --minimum-common-coverage-m 20 `
  --output-directory ".\outputs\mcap_v038"
```

This first command performs the complete availability, schema, conversion,
duplicate/gap, and synchronization audit but does not compare raw coordinates.

Add `--assume-same-frame` only after confirming that both topics use the same
origin, axes, handedness, units, and timestamp semantics:

```powershell
python -m lane_residuals.geometry_validation_cli `
  ".\data\mcap_data" `
  --expected-file-count 10 `
  --session-map ".\config\mcap_sessions.private.json" `
  --assume-same-frame `
  --output-directory ".\outputs\mcap_v038"
```

The command exits with code 3 after saving outputs when the corpus is
scientifically incomplete, for example when a file failed, the count is not
ten, a scan was sampled, sessions are unassigned, a required topic is absent,
or schema fingerprints differ.

## Outputs

| File | Purpose |
|---|---|
| `corpus_manifest.json` | Ten-file completeness, opaque recording/session IDs, schema cohorts and scan state |
| `frame_states.csv` | One row for every decoded estimate message before filtering |
| `availability_summary.json` | State rates, contiguous runs, transitions and selection-bias warning |
| `duplicate_gap_audit.csv` | Cross-chunk duplicate timestamps, conflicts and session gaps |
| `synchronization_audit.csv` | Matched, ambiguous, unmatched and timestamp-missing estimate rows |
| `hypothesis_metrics.csv` | Per-frame diagnostic metrics or stable generation/comparison failure codes |
| `semantic_validation_summary.json` | Hypothesis assumptions, scientific gates and non-training declarations |
| `validation_overlays/` | Deterministically stratified confidential geometry overlays when comparison is enabled |

Tables and JSON exclude filenames, absolute timestamps, topology IDs,
confidences, raw spline values, coordinates and geometry arrays. Overlay images
contain confidential geometry and must remain local.

Duplicate chunk-boundary frames retain provenance in `frame_states.csv` but are
counted once in corpus-level availability totals and excluded from the
hypothesis decision.

## Hypothesis decision

The default result is `hypothesis_unresolved`. A hypothesis can be labelled
only `geometrically_preferred`, never semantically confirmed, and only when:

- real session grouping is supplied;
- at least two sessions contribute;
- each contributes at least 20 paired frames;
- the hypothesis has lower lateral RMS in at least 80% of paired frames in
  each session;
- its session median RMS is at most half the alternative's;
- its heading and coverage diagnostics are not materially worse;
- a deterministic block-bootstrap interval excludes zero;
- predeclared absolute lateral and heading tolerances were supplied.

Absolute tolerances are intentionally not guessed by the package. Without
authoritative requirements, the result remains unresolved even if one
hypothesis has a lower average discrepancy.

## Prohibited real-data outputs

Version 0.3.8 does not write:

- `residual_dataset.npz` from the direct-path workflow;
- `gaussian_model.npz`;
- likelihood or calibration results;
- train/test splits;
- planner-performance claims.

`--fit-gaussian` is unconditionally blocked in the older real-MCAP command.
The standalone Gaussian implementation and synthetic tests remain available
for learning and later use after the geometry, availability mechanism and
reference semantics are validated.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The regression suite covers Protobuf 4–7 wrappers, joint role/error evidence,
adjacent-lane non-substitution, the 251-message structured availability regime,
variable-length splines, straight/circular/linear-curvature cases, backward and
interior-anchor integration, rigid-transform equivariance, numerical
convergence, strict ROS1 comparator extraction, invalid distributed-value
means, timestamp ties, the greedy-matcher counterexample, privacy-safe output,
and unconditional real-data Gaussian blocking.

## Confidentiality

MCAP files, private session maps, output CSV/JSON files and figures may expose
BMW signals or geometry. Keep them outside the public repository unless BMW
explicitly approves publication. The public code should describe only generic
validation logic and synthetic tests.
