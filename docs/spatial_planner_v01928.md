# v0.19.28 spatial reference planner benchmark

6 November 2026. This step implements the fixed planner spatial benchmark and
a synthetic command that exercises it through the native matched model
interfaces. The original matched Gaussian, AR and flow comparison is complete
on development data. The speed diagnostic is closed and its longer support
question remains unresolved. The spatial study uses one reference snapshot
per solve, independently of the duration of continuous perception updates.

## Input and output contract

An input profile has 21 signed lateral offsets in physical metres at
0, 5, ..., 100 m. Positive values point along the left normal of the reference.
The scenario fixes speed, timestep, initial lateral and heading errors, and
previous curvature correction. These values and the planner configuration are
shared across each arm. The planner solves its existing unconstrained lateral
tracking problem. The new trace API returns the first decision plus predicted
lateral error and curvature correction at each next step. The previous
first-step API uses the same solver and return type. The spatial adapter
rejects a lookahead beyond 100 m rather than extending the last station.

The spatial response map is built from the existing solve on zero disturbance
and the 21 unit station profiles. With fixed dynamics and an unconstrained
quadratic objective, subtracting the zero disturbance solution gives a linear
map for the planned lateral states and curvature. Verify this against direct
solves before using it for generated ensembles. Its columns do not describe
successive perception frames.

The benchmark reports signed first curvature change and maximum absolute
planned lateral change from the zero disturbance plan. It reports the mean
and the 95th percentile of the absolute outcomes and scalar sample CRPS
against the replay outcome for each metric. It uses the same number of draws
for each stochastic arm. The empirical CRPS treats those draws as a discrete
distribution. A replay target is an observed outcome under the same simulator,
not an independent measure of physical lane position or production behaviour.

The native model adapter accepts an unconditional matched Gaussian or
unconditional matched flow state. Flow sampling uses explicit Heun 128.
A conditional flow reset is a distinct distribution from a full temporal
rollout, so the single snapshot adapter refuses conditional states. The
benchmark does not infer the provenance of supplied arrays. A future recorded
consumer must reconcile the exact held out row, model state, scenario
geometry, speed and identity before invoking it.

## Synthetic experiment

The CLI creates its own training and replay fixtures with separate fixed
seeds, fits and restores synthetic model states, and compares nominal,
synthetic replay, empirical resampling, diagonal Gaussian, full covariance
Gaussian and unconditional flow. The diagonal and full Gaussian arms use the
same fitted mean and station variances. Two illustrative speeds make the
difference between spatial lookahead and continuous observation support
visible. The JSON retains the seed, configuration, sample counts, response
gains and all outcome summaries. The figure shows station sensitivity.

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg python3 -m lane_residuals.cli.spatial_planner_demo --output /path/to/new/synthetic_output
```

This command accepts only an output path. The generated data and comparisons
are synthetic engineering evidence. A different scenario or comparison with
real inputs needs a separately defined replay consumer and protocol.

## Recorded replay study to design next

Ask which spatial structures reproduce the fixed planner outcomes on the
same held out reference snapshots. Use original matched development folds
for the first recorded study and score per outing. Record inclusion,
unassessed scenarios, draw sensitivity and the dispersion of outing results.
The target is EDP disagreement relative to the RLMB fusion proxy. Use a
consistent local coordinate and station mapping, common planner settings and
an independently defined initial state. The matched numeric residual and model
archives alone do not establish a complete nominal geometry and state
contract for this study. Locate the corresponding validated geometry and
state data and verify the join before using recorded inputs.

For the first command, test the affine response and its covariance prediction
directly. For an affine output with a quadratic metric, the mean and
covariance determine expected quadratic cost. Tail metrics such as peak
planned deviation can still distinguish distribution shape. A Gaussian
matched to the flow moments on development draws is a useful control if the
claim concerns higher moments. Specify practical engineering effect
thresholds prospectively. Avoid interpreting output changes as realised
steering, safety or comfort outcomes.

Greiser et al. use noisy recorded references for planner parameter tuning.
Their replay and held out evaluation are design precedents. The existing
fixed planner answers the spatial question without requiring their exact
solver and tuning setup. Any replication or later transfer claim needs a
separate specification. Target funnels change the planning objective and
require a predictive belief calibrated for the relevant reference; they are a
separate possible research project.

## Prospective additional drive intake

Keep new recordings separate from accepted fits and reserved final outings.
Inventory owner declared IDs in place. Verify byte identity and related session
or route groups before treating two recordings as independent. Screen schema,
reference and estimate topology, timestamp support, geometry, and source
coverage without inspecting model performance or selecting on residuals.
Report continuity twice: geometry valid only and complete conditions at the
desired planner cadence. Preserve rejected and unassessed counts. Decide
development and independent test roles by group before outcome inspection.
An independent evaluation with a single deployable model needs a prospectively
specified model freeze using development data. Preserve original folds and
results if a separate version adds training data.
