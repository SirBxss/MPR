# v0.19.22 paired source-tie diagnostic

## Decision and scope, 28 October 2026

PR #46 is merged with the approved implementation tree. This implementation
carries its deferred [review closure](velocity_history_review_20261028.md) in
the same patch batch. No separate documentation-only PR is needed.

New private source evidence does not establish the deployed speed producer or
recording-applicable quantity and clock semantics. Preserve that evidence
outside Git. Current-source descriptions, recorded numeric fields and actual
consumer availability remain distinct. The earlier
[sensor timestamp qualification](bmw_sensor_topology_epoch_evidence.md) also
remains applicable; do not repeat a broad inquiry that it already addressed or
treat its mode defaults as recording settings.

The smallest useful code step is to make the material source-equality
sensitivity explicit and repeatable in the diagnostic layer. It changes no
accepted selector, feature, schema, dataset, model or admission gate. Independent
review and actual new-head CI remain pending. The measured cached replay and
source assessment are delivered privately. They are post hoc on the same old
window, not prospective or independent validation.

## Fixed paired rule

`domain.velocity_source_ties` calls the unchanged v0.19.21 primary exactly once:
select the latest update with log time strictly less than EDP log time, then
validate the selected update without fallback, allowing source equality and
the unchanged exploratory 100 ms age bound. Preserve the entire primary
analysis, original failure codes, source/publish inversions, and selected-update
identity. Zero speed is a valid value. VehicleVelocity is a consistency
comparison, not independent truth or an interchangeable speed definition.

The secondary uses that **same selected update** and additionally requires
positive integer source age: selected source time strictly less than EDP source
time. An equality failure never triggers an older update search, interpolation,
offset, clock substitution or new threshold. Keep all primary quality/publish
screens, geometry, non-speed exclusions and original recording/message/pair/
source-gap resets. Report both conventions regardless of which looks better.

For each topic report both supports, chosen ties (including ties on already
failing rows), ties among primary-complete rows, primary-only/secondary-only
counts, and gains/losses against the original geometry-qualified complete mask.
The secondary must be a subset of the primary. Keep the prior v0.19.20
latest-log-at-or-before result and original complete support separately.

Observe integer source/log/publish ranges, zero/negative counts, seconds
components, adjacent equal/decreasing counts, and positive timestamps below
five numeric seconds. These are neither UTC dates nor clock calibration,
resolution, producer identification, sample latency or consumer availability.
The legacy field name `publish_ns` describes an MCAP header value; it does not
establish time of publication by the topic producer. No rule uses the new clock
observations to select or admit data.

Per-message EDP topology/event qualifier payloads are not present in the cached
audit. The original accepted geometry population is SENSOR-only by the frozen
producer contract; that is different from newly observing those payload fields.
Do not infer a mode-specific timestamp path or degraded-state interpretation
for individual cached frames. No map-based population is admitted here.

## I/O and artifacts

The new CLI is `python -m lane_residuals.cli.velocity_source_ties`, with only
`--result-zip`, `--result-sha256`, `--output`. It reuses the unchanged bounded
v0.19.21 loader, including exact ZIP members, byte/expansion limits, SHA/CRC,
six-file cache materialization, development-role/lineage validation and complete
original analysis/frame replay. An archived raw path is provenance only and
is never opened, statted, hashed or decoded. This consumer has no raw-operation
or feature-adoption option and is not a new-window decoder.

Before creating output, validate the input and refuse an existing directory or
symlink. Successful output has exactly five files:

- `report.private.json`, status `complete_cached_source_tie_audit`;
- `paired_frames.private.csv`, primary and secondary fields on each same sample;
- `support_comparison.private.csv`, original/prior-pilot/primary/secondary support;
- `source_tie_comparison.png` and `.pdf`, generated with Matplotlib.

After an output-stage failure preserve an incomplete report with failure class.
Cached analysis is repeatable into fresh directories; it never reopens the
completed raw attempt. Reports keep false adoption, dataset modification,
model fitting, producer identification, clock comparability, physical
availability, generalization and cohort-recovery claims. No training arrays,
standardizers or model states are written. All outputs remain private.

## Next scientific step and training state

Resolve only the remaining quantity/clock applicability questions from available
read-only source evidence; keep unavailable historical identity unknown. No
mandatory metadata-recovery loop is introduced. If strong physical availability
cannot be established, the main agent must explicitly decide whether a
qualified offline recorded-clock feature is justified by the available value
and clock evidence. A physically causal deployment claim needs stronger proof.
Neither acceptance is automatically granted by this diagnostic.

Only a separately reviewed, outcome-independent bounded development-window
protocol may assess generalization. It must predeclare both tie conventions,
population/window selection, success criteria and interpretation. Do not widen
the completed pilot or sweep the cohort. Other geometry/feature/reset barriers
can still limit runs. A later adopted speed/schema/population change requires
a versioned common comparison and appropriate affected fits while preserving
the accepted original experiment.

Four matched development configurations (two Gaussians and two AR controls)
are complete. Both flows still need first matched real-data fits and evaluation,
under the existing temporal-support/model-substitution/review gates. Their
software/protocol preparation can continue in parallel with the evidence work.
Then come frozen model comparison, separately authorized final evaluation and
planner assessment. Final outings remain unexposed. Model counts are not an
estimate of remaining effort. No real model is fitted by this implementation.
