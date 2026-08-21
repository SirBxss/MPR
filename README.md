# Minimal Path-Residual Model (MPR) v0.13.1

MPR is the canonical implementation repository for the thesis. LEEM may be
consulted as historical implementation evidence, but new data contracts,
models, evaluation logic, and thesis results belong here.

Version 0.12.1 completes the read-only expanded-corpus inventory before any
cross-MCAP sequence work. It recursively hashes and inspects every MCAP,
requires exact basename coverage from the private physical-drive map, audits
required topics and schemas, compares filename hints with internal timing, and
proposes only fail-closed continuous blocks. It does not edit the drive map,
join frames, tune a model, change the accepted v0.5 native-alignment target, or
add delta-t compensation as a model input. The accepted 67-file audit contains
eight verified continuous blocks, but no sequence is stitched in this change.

Version 0.5.2 restores the accepted v0.5.0 native spatial projection and
resampling as a reproducible exact-manifest workflow. Source-time delta is
retained only as diagnostic evidence; no odometry motion compensation or
numeric delta-time path movement is applied. The historical v0.5.0 ten-file
contract remains readable, while v0.5.1 remains an optional sensitivity audit
and is not accepted for model inputs.

Version 0.12.2 adds a read-only, complete-corpus EDP topology-semantics and
alignment-quality audit. It preserves the SENSOR_TOPOLOGY gate and does not
change eligibility, stitch MCAPs, export residuals/features, or train models.

Version 0.13.0 builds the expanded physical-unit sensor-topology profile and
sequential dataset. Model-profile eligibility requires accepted H100 native
alignment, the exact 21-station grid, valid estimator/map/estimate geometry,
finite six-feature values, and anchor distance at most 1.0 m. The geometric
gate is fixed before modeling; no heading gate, split selection, hyperparameter
choice, or model training is performed.

Version 0.13.1 preserves v0.13.0 as the fail-closed parity baseline and permits
only the frozen unsigned 50 ms odometry-displacement speed to use the accepted
immediately preceding MCAP. Same-drive continuity, odometry topic/schema,
strict timestamp order, interpolation tolerance, and no-extrapolation checks
must all pass. EDP paths, residuals, and the other five conditions remain
recording-local. No split, standardizer fit, hyperparameter choice, or model
training is performed.

Version 0.11.0 implements the second thesis model family: an autoregressive
input-output hidden Markov model (AIOHMM). It keeps the exact v0.9.0 sequences,
six-feature schema, physical-drive folds, training-only transforms, sampling
seeds, and v0.10.0 metrics. The fixed exploratory default has three latent
states, condition-dependent transitions, station-wise AR(1) emissions, and
training-pooled emission parameters plus pooled/shrunk state-specific
21-dimensional covariances. A state-independent training-only conditional
Gaussian marginal supplies the reset distribution at each sequence start.
Multiple deterministic
restarts are selected by training likelihood only; held-out drives do not select
the state count, restart, transform, or any hyperparameter. State occupancy,
transition behavior, dwell estimates, AR coefficients, convergence, and restart
stability are explicit outputs. State labels are diagnostics, not physical
driving classes.

Version 0.10.0 implements the conditional Gaussian under the shared sequence
interface. It is deliberately a temporal null: active frames are fitted with a
linear conditional mean and spatial 21-dimensional covariance, but emissions
remain conditionally independent across time. The workflow evaluates exact
leave-one-physical-drive-out v0.9.0 folds and adds sample-based energy score,
marginal coverage, and lag-one correlation diagnostics that can also be used
for AIOHMM and RC-GAN.

Version 0.9.0 introduces the shared sequence contract required by all three
thesis model families: conditional Gaussian, AIOHMM, and RC-GAN. It converts
the frozen v0.8.0 H100 cohort into recording-local contiguous sequences,
splitting at missing pair indices or source-time gaps. It writes padded
`[sequence, time, feature]` conditions, padded
`[sequence, time, station]` residuals, explicit masks and lengths, exact
provenance, leave-one-physical-drive-out folds, and standardizers fitted on
training drives only. It does not train or select a new model.

Version 0.8.0 freezes the reviewed complete-feature cohort and performs the
first conditional-model comparison. It fits a six-feature linear conditional
mean with one fixed 21-dimensional Gaussian covariance and compares it with an
unconditional Gaussian refitted on the identical rows and identical
leave-one-physical-drive-out folds. Feature standardization is fitted inside
each training fold. The final all-row conditional model is fitted only after
evaluation, and the outputs report a negative result without promoting the
conditional model when held-out likelihood or RMSE does not improve.

Version 0.7.2 handles repeated odometry state timestamps without making an
arbitrary message-order choice. Duplicate groups are coalesced only when every
rear-axle pose is exactly identical. A group with conflicting position or yaw
is entirely discarded, and all duplicate, conflict, discard, and multiplicity
counts are retained in the audit outputs.

Version 0.7.1 keeps the fail-closed prediction-time feature audit and requires
an explicit speed contract. The original signed longitudinal signal remains
available as one mode. A second mode derives unsigned rear-axle speed from
odometry displacement between independently interpolated poses at the EDP
source epoch and exactly 50 ms earlier. Neither mode extrapolates or crosses an
MCAP boundary, and the output preserves the interpolation evidence.

Version 0.7.0 introduced the feature audit before any conditional model is
fitted. It matches each canonical residual vector to its original
recording-local EDP message, derives H100 curvature from the selected estimate,
and maps native 5 m KEEP_LANE confidence buckets to ego-relative bins without
padding or extrapolation.

Version 0.6.1 adds a fail-closed adequacy diagnostic for the v0.6.0
unconditional Gaussian. It recomputes every prediction by leaving out the
complete physical drive, then examines marginal coverage, tail shape, normal
Q–Q behavior, and multivariate Mahalanobis calibration. It does not treat the
1,777 sequential pairs as independent samples and does not apply a post-hoc
pass/fail threshold.

Version 0.6.0 freezes the accepted v0.5.0 complete H100 cohort as a canonical
21-dimensional residual-vector dataset and adds the first current statistical
baseline: one unconditional multivariate Gaussian. Evaluation holds out each
physical drive in turn; the final descriptive model is fitted on all vectors
only after the two held-out folds are evaluated.

Version 0.4.5 adds a corpus-level diagnostic over the validated v0.4.4
single-recording pipeline. It processes each MCAP independently, preserves
complete-stream timestamp pairing, and aggregates fixed complete cohorts at
0--60 m and 0--100 m. Per-drive and overall statistics are recomputed from the
underlying pair/station rows; recording medians are never averaged together.

Version 0.5.1 remains a separate optional RLMB motion-alignment sensitivity
audit. Its exploratory ten-recording run is not a prerequisite for v0.6.0:
the approximately 23.5 ms median source-time mismatch is retained as a
documented modelling limitation instead of blocking residual export.

The v0.4.4 geometry behavior remains unchanged. It extends the RLMB
pseudo-reference from the metadata-confirmed ego
segment by following only unique, explicit `successor_lane_segment_indices`.
Every junction must pass declared endpoint-gap and tangent-continuity limits.
The builder stops before branches, cycles, missing geometry, or discontinuous
junctions; it never chooses a nearby lane by distance.

The pairing audit now reports a primary 0–60 m diagnostic separately from the
full 0–100 m horizon. A pair may therefore remain useful for the conservative
near-horizon analysis even when the far horizon is unavailable. This does not
permit extrapolation and does not promote RLMB to physical ground truth.

The pairing and reference diagnostics now use `curvature_rate` as the
provisional reconstruction because this interpretation preserves retained
geometry across the observed rollovers. This is empirical evidence, not
official confirmation of the production field semantics. The transition audit
continues to export both `curvature_rate` and `curvature_delta` results.

The command still reconstructs the estimated `KEEP_LANE` spline and the
metadata-confirmed ego path from `/adp/road_lane_map_based`, places station zero
at each curve's ego-origin footpoint, and creates raw overlay diagnostics.

It does not promote the map signal to physical ground truth and does not export
a model-training residual dataset. The earlier implementation that treated
`ego_lane_path` as provisional ground truth remains withdrawn.

The thesis scope is fixed:

> **How wrong is the lane estimate likely to be under this situation?**

The target remains the signed lateral lane-estimation error along the normal of
a validated lane-reference path. The realised human-driven trajectory is not
substituted for the lane reference.

## Signal roles

| Object | v0.4.5 role |
|---|---|
| Estimated drive path | Lane estimate being evaluated |
| Same-estimator debug path | Spline-semantic oracle only |
| Direct map-lane geometry | Primary pseudo-reference candidate |
| Stable pose + `distance_to_centerline` | Independent reconstruction candidate |
| Future vehicle positions | Diagnostic realised trajectory only |
| Fused ego-lane path | Operational comparator only |
| Planar odometry | RLMB-to-EDP ego-frame compensation and audit evidence |
| GNSS, 6-DoF odometry, transforms | Additional pose/frame validation support |

No single MCAP topic is assumed to be physical ground truth. The v0.6.0 vectors
are EDP disagreement against the best available RLMB pseudo-reference; they
must not be described as independent physical ground-truth errors.

## EDP candidate-transition audit

Run this diagnostic on the second MCAP first, because its corrected pairing
audit showed clear EDP geometry regimes:

```bash
python -m lane_residuals.edp_transition_audit_cli \
  "data/raw/mcap/one_recording.mcap" \
  --output-directory "outputs/diagnostics/validation/edp_transition_audit"
```

The default run automatically detects all rollovers in the output tables and
plots up to four evenly distributed rollover windows. Detection does not use a
curve-jump threshold or interval-count change. It requires a unique longest
ordered match between a rebased previous boundary suffix and the current
boundary prefix, with at least three matched boundaries spanning at least 50 m.
Ties and insufficient overlap remain explicitly unassessed.

To reproduce the windows identified in the second audited MCAP, specify their
EDP message indices explicitly:

```bash
python -m lane_residuals.edp_transition_audit_cli \
  "data/raw/mcap/one_recording.mcap" \
  --transition-centers 92 113 133 153 172 190 208 227 247 \
  --transition-window-radius 3 \
  --output-directory "outputs/diagnostics/validation/edp_transition_audit_explicit"
```

The command writes:

| File | Purpose |
|---|---|
| `edp_message_inventory.csv` | Every EDP message and its exact KEEP_LANE selection state |
| `edp_candidate_inventory.csv` | Every candidate, literal metadata, confidence values, topology IDs, and raw spline parameters |
| `edp_candidate_geometry.csv` | Every reconstructable candidate sampled under both spline hypotheses |
| `edp_selected_transitions.csv` | Rollover status, station shift, boundary evidence, valid same-station metrics, and shift-aware metrics for both hypotheses |
| `edp_transition_windows.png` | All candidate curves around each ranked or explicit transition center |
| `edp_transition_metrics.png` | Transition metrics across the complete recording under both hypotheses |
| `edp_transition_summary.json` | Counts, ranked centers, assumptions, and the next scientific decision |

`path_index` is message-local and is never presented as a stable identity.
`lane_topology_ids` are exported literally as the only confirmed identity-like
metadata. The lane-role enum is exported literally; no separate
driving-intention field is claimed. All outputs contain BMW-derived raw values
and must remain private.

At a detected rollover, these fields are intentionally empty because equal
numeric native stations no longer denote the retained path portion:

- `station_zero_position_jump_m`
- `endpoint_position_jump_m`
- `sampled_position_rms_m`
- `rigid_normalized_shape_rms_m`

Use `station_shift_m` and `shift_aware_shape_rms_m` for the internal rollover
continuity diagnostic. Rigid normalization removes translation and heading
between the two EDP representations; therefore this metric is not a physical
lane-estimation error.

## One-file EDP–RLMB pairing audit

Start with one representative MCAP and plot at most 20 evenly distributed
diagnostic-ready pairs:

```powershell
python -m lane_residuals.pairing_audit_cli `
  ".\data\raw\mcap\one_recording.mcap" `
  --max-pairs 20 `
  --output-directory ".\outputs\diagnostics\validation\pairing_audit"
```

No timestamp validity threshold is applied by default because no production
synchronization tolerance has been proven. If a tolerance is later justified
before viewing the confirmatory result, pass it explicitly:

```powershell
--maximum-pair-delta-ms <predeclared_value>
```

The command writes:

| File | Purpose |
|---|---|
| `message_inventory.csv` | Every EDP/RLMB message, timestamp state, geometry state, failure code, and temporal association |
| `rlmb_chain_audit.csv` | Exact RLMB segment indices/IDs, junction checks, forward coverage, and fail-closed stop reason per map message |
| `pairing_overlays.png` | Raw EDP/RLMB overlays, ego origin, footpoints, and 0–100 m stations |
| `pairing_lateral_zoom.png` | Per-pair signed lateral disagreement with the primary 0–60 m region highlighted |
| `diagnostic_station_profiles.png` | Station-wise median, 5–95% band, RMS, and available pair count |
| `pairing_audit.csv` | Every accepted mutual-nearest temporal pair, including pairs whose geometry is invalid |
| `diagnostic_disagreement.csv` | Available reference-normal disagreement at 5 m stations, with primary/full-horizon availability flags; explicitly not thesis labels |
| `pairing_summary.json` | Counts, extraction failures, aggregate offsets, and scientific limitations |

`--max-pairs` limits only the number of overlay panels. It does not truncate
`message_inventory.csv`, `pairing_audit.csv`, or the diagnostic station rows.
Equal-distance timestamp ties and one-sided nearest candidates remain unmatched.
When `--maximum-pair-delta-ms` is supplied, candidates outside that predeclared
gate also remain unmatched and are reported in the inventory.

The audit uses geometric arc length independently for each curve. It projects
`(0,0)` onto both curves and evaluates station `d` at
`s_ego_footpoint + d`; native spline or map station origins are never assumed
to coincide. A reversed vertex order is normalized toward positive vehicle x
and recorded explicitly. No rigid alignment or timestamp motion compensation
is applied, because either would hide the frame mismatch this audit is intended
to reveal. EDP geometry uses the provisional `curvature_rate` reconstruction;
the summary records that its official interface meaning remains unconfirmed.

RLMB chaining is topology-first. It starts from exactly one
metadata-confirmed ego drive path and follows a successor only when the current
segment has exactly one explicit successor. The default safety limits are 16
segments, a 1.0 m endpoint gap, and a 30 degree tangent discontinuity. They can
be changed explicitly with `--map-max-segments`,
`--map-max-junction-gap-m`, and `--map-max-junction-heading-deg`; any change
must be reported with the experiment.

## Expanded-corpus continuity audit

Before extending the recording-local v0.9 sequence contract, update the
ignored private map so every recursively discovered MCAP basename occurs
exactly once. Several consecutive chunks may intentionally share a label when
the label denotes one physical session. Labels must come from external session
knowledge; filenames, wall-clock hints, and `MCAP_######` identifiers are never
used to assign a drive.

```bash
python -m lane_residuals.cli.corpus_inventory \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --output-directory \
  "outputs/diagnostics/data/expanded_corpus_inventory_v0121"
```

The command writes six private outputs: `mcap_inventory.csv`,
`topic_compatibility.csv`, `recording_continuity.csv`,
`proposed_session_groups.json`, `corpus_inventory_summary.json`, and
`corpus_inventory_diagnostics.png`. Exit code 3 means the reports were written
but exact coverage or file usability failed. An edge is a stitch candidate
only when both files have the same explicit drive label, the next internal
MCAP start is at or after the previous internal end, relevant source time
increases strictly, the estimate-source gap is positive and no larger than
200 ms, and all required topic/schema signatures agree. Equal internal
endpoints are valid touching boundaries. Overlaps,
resets, missing evidence, unreadable/empty/duplicate files, and topic/schema
failures remain explicit exclusions. Filename timing and identifier jumps such
as `000307 -> 000398` are diagnostic flags, not identity evidence or automatic
continuity rejections.

This audit does not implement cross-MCAP sequence stitching. Its accepted next
step is the v0.5.2 native projection-alignment phase below. Any later sequence
contract must consume only reviewed stitchable edges, retain every frame's
original `recording_id`, preserve the native-alignment target, and avoid
delta-t compensation as a model feature.

## Ten-MCAP fixed-cohort batch diagnostic

Create a private grouping map whose keys exactly match the ten MCAP basenames.
Files from the same physical recording session must use the same label. The
accepted v0.4.5 batch used `mcap_sessions.private.json` through the historical
`--drive-map` flag; labels are still replaced with opaque `drive_###`
identifiers in aggregate outputs. The three-entry
`mcap_drives.private.example.json` is only a format example and is not suitable
for this corpus.

```bash
cp config/examples/mcap_sessions.private.example.json \
  config/private/mcap_sessions.private.json
```

Run the corpus audit from a new, empty output directory:

```bash
python -m lane_residuals.batch_pairing_audit_cli \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --expected-file-count 10 \
  --max-pairs-per-recording 6 \
  --output-directory "outputs/diagnostics/validation/pairing_batch_v045"
```

Do not pass a timestamp gate or an outcome-tail threshold on the first
exploratory corpus run. If a physically justified threshold is later declared
before a confirmatory run, use `--primary-tail-threshold-m` and/or
`--full-tail-threshold-m`. When these are omitted, outcome-tail flags remain
empty instead of being defined circularly from the same observed distribution.

The batch command writes every existing one-file audit under
`recordings/recording_###/` plus:

| File | Purpose |
|---|---|
| `batch_manifest.json` | Exact corpus resolution, opaque drive assignment, per-recording status, failures, and completeness blockers |
| `recording_summary.csv` | One row per requested recording, including failed recordings and denominator-labelled H60/H100 metrics |
| `scope_horizon_metrics.csv` | Recording-, drive-, and corpus-level fixed-cohort metrics for H60 and H100 |
| `scope_station_metrics.csv` | Fixed-cohort station mean, RMS, median, 5th/95th percentiles, and constant pair denominator |
| `rlmb_chain_summary.json` | Coverage, multi-segment use, termination reasons, reciprocity, junction gaps, and junction headings by scope |
| `temporal_tail_events.csv` | Every temporal pair with relative time, H60/H100 eligibility and optional predeclared outcome-tail flags |
| `fixed_cohort_station_profiles.png` | Overall H60/H100 profiles without distance-dependent cohort shrinkage |
| `recording_horizon_summary.png` | Recording-level median per-pair RMS comparison |
| `temporal_diagnostic_events.png` | Drive-relative H60/H100 RMS timelines |
| `batch_summary.json` | Corpus reconciliation, overlap checks, pooled descriptive metrics, limitations, and next decision |

Canonical H60 always means the 13 stations `0, 5, ..., 60 m`; H100 always
means the 21 stations `0, 5, ..., 100 m`. A pair enters a horizon only when all
of its stations are available, so every station in that horizon has the same
pair count. H100 is always a subset of H60.

Timestamp pairing never crosses MCAP boundaries. Drive grouping comes only
from the exact private map, never from filenames or observed outcomes. Source
time overlap between chunks is reported as an incompleteness blocker rather
than silently deduplicated. Exit code `0` means a complete diagnostic run,
`3` means the outputs were written but the corpus is incomplete, and `2` means
invalid configuration or a global execution error.

These remain BMW-derived pseudo-residual diagnostics. They are not independent
samples, physical ground-truth lane errors, or a model-training dataset.

## Accepted native projection-alignment validation

v0.5.2 restores the accepted v0.5.0 spatial target over an arbitrary positive
exact manifest. Each MCAP is decoded and paired independently using complete-
stream mutual-nearest source timestamps. No timestamp gate is applied by
default. The signed source delta is reported but never used to translate,
rotate, extrapolate, or otherwise move either path.

EDP station zero is projected onto the native paired RLMB path. That projected
RLMB station becomes aligned zero, and both paths are sampled at equal forward
arc-length offsets. RLMB remains the best available pseudo-reference rather
than physical ground truth. H100 eligibility is a subset of H60, and only
complete 21-station H100 rows are model-eligible.

```bash
python -m lane_residuals.cli.projection_alignment_batch \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --corpus-inventory-directory \
  "outputs/diagnostics/data/expanded_corpus_inventory_v0121" \
  --expected-file-count 67 \
  --output-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v052_expanded"
```

The workflow hashes the exact private map, the accepted corpus summary,
continuity edges, proposed session groups, and all generated batch-level
outputs. It performs no cross-MCAP pairing, residual export, feature
extraction, sequence construction, or model training.

## EDP topology semantics and alignment-quality audit

```bash
python -m lane_residuals.cli.topology_semantics_audit \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --corpus-inventory-directory \
  "outputs/diagnostics/data/expanded_corpus_inventory_v0121" \
  --alignment-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v052_expanded" \
  --expected-file-count 67 \
  --output-directory \
  "outputs/diagnostics/validation/topology_semantics_alignment_quality_v0122"
```

Every EDP message retains its raw-wire enum value, embedded-descriptor enum
name, estimator/selection state, and v0.5.2 pair evidence. Within-MCAP and
within-session boundary transitions are explicit. Current H60-eligible anchor
distances above 1.0 m are listed without changing eligibility. Byte-identical
copies of all six accepted v0.12.1 inventory outputs are packaged under the
audit's `lineage/` directory and covered by SHA-256 provenance.

## Quality-gated expanded sequential dataset

```bash
python -m lane_residuals.cli.expanded_sequence_dataset \
  "data/raw/mcap" \
  --alignment-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v052_expanded" \
  --topology-audit-directory \
  "outputs/diagnostics/validation/topology_semantics_alignment_quality_v0122" \
  --expected-file-count 67 \
  --output-directory \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0130"
```

The workflow retains tensors `[N,21]` and `[N,6]`, original timestamps and
recording/drive/MCAP identity, and a quality-gated physical-session sequence
identifier. An accepted MCAP boundary is stitched only when both immediate
endpoints are eligible sensor-topology profiles and the timestamp gap is
strictly positive and at most 200 ms. Lane-map or ineligible intervals always
split sequences. Standardization metadata remains unfitted and explicitly
requires future training-drive-only fitting after split assignments are chosen.

The v0.13.0 output remains immutable reproducibility evidence. Build v0.13.1
with that directory as an explicit byte-parity baseline:

```bash
python -m lane_residuals.cli.expanded_sequence_dataset_v0131 \
  "data/raw/mcap" \
  --alignment-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v052_expanded" \
  --topology-audit-directory \
  "outputs/diagnostics/validation/topology_semantics_alignment_quality_v0122" \
  --v0130-directory \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0130" \
  --expected-file-count 67 \
  --output-directory \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131"
```

Every boundary-derived speed records both contributing private MCAP basenames
and the exact odometry timestamps. A parity audit requires every pre-existing
v0.13.0 residual and six-feature row to remain byte-identical.

## Optional odometry-compensated reference-alignment validation

v0.5.1 implements an optional common-time geometry sensitivity. RLMB is transformed from its
pose-validity ego frame into the EDP geometry-frame proxy using
`/adp/odometry`. EDP station zero is then projected onto the transformed RLMB
path. That projected station becomes aligned zero, and RLMB is sampled at the
same forward offsets `0, 5, ..., 100 m` as EDP.

The EDP topic does not publish its actual odometry geometry epoch. The offline
proxy is therefore the last odometry message recorded at or before the EDP
MCAP log time. Every pair reports the selected odometry timestamp, log-time
lag, RLMB interpolation span, SE(2) transform, and geometry-epoch delta. The
proxy is fail-closed when its lag or interpolation bracket exceeds the declared
limits.

Run one MCAP into a new validation directory:

```bash
python -m lane_residuals.cli.alignment \
  "data/raw/mcap/one_recording.mcap" \
  --output-directory \
  "outputs/diagnostics/validation/reference_alignment_recording_001"
```

The command writes `alignment_pair_audit.csv`,
`alignment_station_comparison.csv`, `alignment_comparison.png`, and
`alignment_summary.json`. It compares native and aligned residuals while
retaining the signed timestamp delta and constant H60/H100 eligibility.

This is explicit rear-axle SE(2) motion compensation followed by spatial
projection/resampling. It remains an offline approximation because the exact
DPE geometry epoch is not published. The v0.5.1 corpus result is an optional
sensitivity analysis and is explicitly rejected as v0.6.0 model input.

For the actual corpus, run the exact manifest batch command rather than a shell
loop:

```bash
python -m lane_residuals.cli.alignment_batch \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --expected-file-count 10 \
  --output-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v051"
```

Do not use the unused three-entry drive-map example and do not add a timestamp
gate for the first exploratory alignment run.

## Canonical residual export and Gaussian baseline

Run v0.6.0 from either the historical accepted v0.5.0 batch or a complete
v0.5.2 native projection-alignment batch. The workflow refuses v0.5.1 motion
outputs, incomplete batches, non-exact drive
grouping, H100 pairs outside H60, duplicate or missing stations, non-finite
values, and any station-wise available-case cohort.

```bash
python -m lane_residuals.cli.gaussian_baseline \
  "outputs/diagnostics/validation/reference_alignment_batch_v050" \
  --output-directory "outputs/models/gaussian_baseline_v060"
```

The default diagonal covariance regularization is `1e-6 m²`. The command
writes the exact wide vectors, dataset reconciliation, leave-one-drive-out
evaluation at fold and station level, the final all-data Gaussian parameters,
and one diagnostic plot. Drive labels come only from the accepted batch
manifest; filenames are never used to infer groups.

The pair rows are sequentially correlated, so 1,777 vectors do not represent
1,777 independent experiments. With only two physical drives, held-out results
are a first between-session check rather than a population-level estimate.

## Gaussian adequacy diagnostics

Run v0.6.1 from a complete, unchanged v0.6.0 Gaussian output directory:

```bash
python -m lane_residuals.cli.gaussian_diagnostics \
  "outputs/models/gaussian_baseline_v060" \
  --output-directory \
  "outputs/diagnostics/modeling/gaussian_adequacy_v061"
```

The command validates the exact canonical H100 vector contract, refits the
stored all-data model to verify its mean and covariance, and reconciles the
reported v0.6.0 cross-validation metrics. It then writes per-vector
Mahalanobis evidence, per-drive and overall station diagnostics, multivariate
chi-square calibration summaries, two plots, and a strict JSON summary.

The output is diagnostic evidence, not a second model fit. Conventional iid
normality p-values are intentionally omitted because adjacent residual vectors
are sequentially correlated. Model-family selection should be based on the
tail and between-drive evidence together with predeclared requirements.

## Conditional-feature availability audit

Run v0.7.2 against the same accepted alignment manifest and raw ten-MCAP
corpus that produced the v0.6.0 residual vectors:

```bash
python -m lane_residuals.cli.conditional_features \
  "data/raw/mcap" \
  --alignment-batch-directory \
  "outputs/diagnostics/validation/reference_alignment_batch_v050" \
  --gaussian-baseline-directory \
  "outputs/models/gaussian_baseline_v060" \
  --speed-source odometry_50ms_displacement \
  --maximum-odometry-interpolation-gap-ms 50 \
  --output-directory \
  "outputs/diagnostics/modeling/conditional_feature_audit_v072_gap50"
```

The odometry mode computes Euclidean rear-axle displacement over the fixed
preceding 50 ms and is therefore unsigned: reverse-motion direction is not
observable from this feature. Both endpoint poses use recording-local linear
interpolation with a predeclared maximum bracket of 50 ms for the accepted
gap-50 audit. The exact accepted manifest maps opaque recording IDs to private
MCAP basenames; filenames and drive identity are not model features. Repeated
state timestamps are accepted
only under exact pose equality; conflicting groups are removed before
interpolation and remain visible in the summaries.

The intended first conditional feature vector is explicitly sourced speed,
EDP mean absolute curvature, EDP H100 curvature change, and near/middle/far
KEEP_LANE confidence. Lane width is excluded because the confirmed recorded
Road value is a fused minimum over a complete segment rather than an
ego-position measurement.

Exit code `0` means every canonical residual vector has all six features. Exit
code `3` means valid audit outputs were written but at least one vector is not
feature-ready. The command never selects a smaller training cohort and does
not fit the conditional Gaussian; cohort freezing and model comparison happen
only after this availability result is reviewed.

## Conditional Gaussian same-cohort comparison

Run v0.8.0 from the unchanged v0.6.0 Gaussian directory and its corresponding
reviewed v0.7.2 gap-50 feature audit:

```bash
python -m lane_residuals.cli.conditional_gaussian \
  "outputs/models/gaussian_baseline_v060" \
  "outputs/diagnostics/modeling/conditional_feature_audit_v072_gap50" \
  --output-directory "outputs/models/conditional_gaussian_v080"
```

The command verifies SHA-256 linkage to all four v0.6.0 source files, matches
every feature row to its exact recording/pair residual key, and admits only
finite complete features. The accepted audit produces 1,770 vectors: 971 from
`drive_001`, 799 from `drive_002`, and seven explicit pair-zero exclusions
caused only by recording-local odometry coverage at MCAP boundaries. No speed
extrapolation or cross-MCAP interpolation is introduced.

Both models use the same fixed covariance regularization (`1e-6 m²` by
default) and the same test vectors. The output includes fold, station, and
per-vector metrics, the frozen cohort and exclusions, an all-row descriptive
conditional model, and a comparison plot. With the reviewed data, the linear
conditional mean is slightly worse overall than the same-cohort unconditional
model on both held-out joint NLL and pooled mean-prediction RMSE; this is a
valid model-comparison result, not a training failure.

## Common sequential dataset

Build the v0.9.0 sequence contract from the complete v0.8.0 output:

```bash
python -m lane_residuals.cli.sequence_dataset \
  "outputs/models/conditional_gaussian_v080" \
  --output-directory "outputs/datasets/sequential_dataset_v090"
```

The default 200 ms continuity limit is deliberately above the observed normal
frame spacing but below the observed multi-second holes. A recording is also
split whenever pair indices are not consecutive. A sequence never crosses an
MCAP recording boundary, and physical-drive membership comes only from the
frozen cohort's exact manifest provenance.

On the reviewed 1,770-frame development cohort, the command produces 13
contiguous sequences across 10 recordings and two physical drives. Their total
within-sequence duration is approximately 140.58 s. This is sufficient for
pipeline implementation and preliminary temporal baselines, but not for a
final AIOHMM/RC-GAN comparison or an untouched thesis test. Additional
independent physical drives are required before final model selection.

The v0.8.0 conditional Gaussian is therefore a completed baseline experiment,
not the finalized Gaussian thesis model. The next comparison must first make
the Gaussian consume the same sequence folds and evaluation contract as the
temporal models. Feature expansion should then be tested as a predeclared
ablation using prediction-time EDP/vehicle signals only; residual or
pseudo-reference outcomes must never be used as input features.

The staged implementation, feature gates, and additional-data trigger are
specified in [`docs/modeling_plan.md`](docs/modeling_plan.md).

## Sequence-contract Gaussian temporal null

Run v0.10.0 from the complete unchanged v0.9.0 sequence directory:

```bash
python -m lane_residuals.cli.sequence_gaussian \
  "outputs/datasets/sequential_dataset_v090" \
  --output-directory "outputs/models/gaussian_sequence_v0100"
```

The model is fitted independently in each physical-drive fold using that
fold's stored training-only transform. It supports the common `fit`, `sample`,
`log_probability`, `save`, and `load` lifecycle. The final all-development-data
fit is written only after held-out evaluation and is explicitly descriptive,
not an untouched final model.

With 128 samples and seed `20260819`, the reviewed cohort gives a held-out
sample-mean RMSE of approximately 0.36445 m, energy score of 1.02288 m, and
sample-based marginal 95% coverage of 0.88612. Most importantly, median
observed lag-one correlation is 0.96554 while the generated temporal-null
median is only 0.09118. This large declared temporal mismatch is the direct
motivation for the next AIOHMM phase.

## Autoregressive input-output HMM

Run v0.11.0 from the same complete unchanged v0.9.0 sequence directory:

```bash
python -m lane_residuals.cli.sequence_aiohmm \
  "outputs/datasets/sequential_dataset_v090" \
  --output-directory "outputs/models/aiohmm_sequence_v0110"
```

The default command performs three deterministic restarts for each fixed
three-state fold model and the descriptive all-development-data model. It may
take materially longer than the Gaussian because every generalized-EM
iteration runs sequence-level forward-backward inference and updates full
21-dimensional spatial covariances. Use the defaults for the reviewed run; the
reduced iteration/restart settings in tests are smoke checks only.

The AIOHMM density is teacher-forced: the likelihood at frame `t` conditions
on the observed residual at `t-1`. Generated sequences are free-running and
condition on the model's previously generated profile. This distinction is
reported because likelihood can improve while long-horizon generative RMSE,
energy score, or calibration does not. The common sample metrics—not AIOHMM
NLL alone—decide whether the temporal model earns its added complexity.

See [AIOHMM design and evaluation](docs/aiohmm.md) for the equations,
generalized-EM estimator, restart policy, diagnostics, and interpretation
limits.

## What the command does

The audit:

1. scans all ten MCAP chunks using the private two-session map;
2. inventories every MCAP topic from channel metadata, then catalogs decoded
   fields, schemas, rates, timestamps, and coverage for the configured
   reference-relevant topics;
3. revalidates production spline parameters against the debug topic;
4. extracts strict metadata-confirmed ego geometry from the map-lane topic;
5. decodes pose and current centreline distance from explicit private field mappings;
6. reconstructs hindsight lane-centre points as

   ```text
   p_center_world(t) = p_vehicle_world(t) - d_center(t) * n_left(t)
   ```

7. transforms future reconstructed points into the estimate frame at `t0`;
8. rejects incomplete 0–100 m windows, source-time ambiguity, long gaps, lane
   changes, estimator failures, and unconfirmed conventions;
9. compares direct map geometry, pose-plus-offset reconstruction, realised
   trajectory, fused comparator, and the lane estimate without exporting labels;
10. applies a predeclared reference-selection gate.

Vehicle yaw is currently a documented fallback for lane heading in the
pose-plus-offset reconstruction. It is not silently presented as exact lane
orientation.

## Install and test

```powershell
python -m pip install -e ".[mcap]"
python -m unittest discover -s tests -t . -v
```

The categorized source tree, command matrix, and frozen output contracts are
documented in [architecture](docs/architecture.md),
[commands](docs/commands.md), and [output contracts](docs/output_contracts.md).

## Prepare the private signal configuration

```powershell
New-Item -ItemType Directory -Force ".\config\private"
Copy-Item ".\config\examples\reference_signals.private.example.json" `
  ".\config\private\reference_signals.private.json"
```

The template contains the known candidate topics and conservative field-path
aliases. Its following convention values intentionally remain `false` until
verified from schema evidence or a responsible signal owner:

- `pose_is_stable_world_or_map_frame`
- `pose_reference_point_confirmed`
- `candidate_paths_share_estimate_frame`

If pose fields do not resolve, the first run still writes
`decoded_field_catalog.json`; use its exact paths to update the private config.
Do not add a guessed path merely to make the gate pass.

## First ten-file discovery run

Do not specify a candidate-agreement threshold on the first exploratory run:

```powershell
python -m lane_residuals.reference_audit_cli `
  ".\data\raw\mcap" `
  --expected-file-count 10 `
  --session-map ".\config\private\mcap_sessions.private.json" `
  --signal-config ".\config\private\reference_signals.private.json" `
  --comparison-max-delta-ms 20 `
  --pose-lsa-max-delta-ms 50 `
  --output-directory ".\outputs\diagnostics\validation\mcap_v039_reference_audit"
```

Exit code `3` is expected while the reference is unresolved; the diagnostic
outputs are still written. Exit code `2` means invalid configuration or command
arguments. Exit code `0` means the pseudo-reference gate passed, but final
residual export remains disabled until the next reviewed version.

The agreement tolerance for a later confirmatory run must be justified from a
planner requirement, measurement uncertainty budget, or supervisor-approved
criterion **before** examining the confirmatory data. It can then be supplied as:

```powershell
--max-candidate-median-abs-m <predeclared_value>
```

## Outputs

| File | Purpose |
|---|---|
| `reference_source_inventory.json` | Topic roles, rates, schemas, corpus coverage |
| `decoded_field_catalog.json` | Exact nested decoded field paths and sampled ranges |
| `pose_source_audit.csv` | Pose rate, continuity, jumps, confirmation state |
| `lsa_centerline_audit.csv` | Direct and boundary-derived current lateral offsets |
| `debug_semantic_audit.csv` | Production/debug role, error, and spline correspondence |
| `duplicate_conflict_audit.csv` | Cross-chunk identical duplicates and conflicts |
| `reference_frame_eligibility.csv` | Denominator-preserving eligibility per estimate frame |
| `candidate_reference_metrics.csv` | Diagnostic candidate-to-candidate and estimate discrepancies |
| `reference_validation_summary.json` | Fail-closed scientific decision and blockers |

That historical reference-audit summary always records:

- thesis scope unchanged;
- driven trajectory is not lane ground truth;
- fused ego-lane path is not lane ground truth;
- no final residual dataset was generated;
- no Gaussian, AIOHMM, or RC-GAN was fitted.

## Reference-promotion gate

The direct map-lane candidate is supported only if all gates pass:

- complete ten-file, two-session scan;
- no conflicting cross-chunk duplicates;
- estimate/debug status and spline semantics pass;
- direct map geometry is available with full station coverage;
- pose-plus-centreline reconstruction is available with full coverage;
- both candidates are cross-validated in at least two sessions;
- pose frame, pose reference point, centreline sign, and relevant frame
  conventions are confirmed;
- their median lateral disagreement passes a predeclared tolerance.

If only the future driven trajectory is available, v0.4.5 leaves the lane
reference unresolved. It does not change the thesis into drive-path prediction.

## Reference-audit scientific boundary

That earlier diagnostic stage answers only:

> Which MCAP-derived reference candidate is defensible enough to define lane-estimation error?

Version 0.6.0 now creates the fixed 21-dimensional pseudo-residual vector at
`0, 5, ..., 100 m` from the separately accepted v0.5.0 alignment batch. It
does not retroactively change the outputs or claims of this reference audit.
Planner-level experiments remain a later stage.

## Confidentiality

MCAP files, private configs, decoded field names, output tables, measurements,
and geometry remain BMW-confidential. Keep them outside the public repository
unless publication is explicitly approved. The `.gitignore` excludes common
private inputs and generated artifacts.
