# Minimal Path-Residual Model (MPR) v0.5.1

Version 0.4.5 adds a corpus-level diagnostic over the validated v0.4.4
single-recording pipeline. It processes each MCAP independently, preserves
complete-stream timestamp pairing, and aggregates fixed complete cohorts at
0--60 m and 0--100 m. Per-drive and overall statistics are recomputed from the
underlying pair/station rows; recording medians are never averaged together.

Version 0.5.1 extends the separate RLMB alignment audit with explicit rear-axle
odometry compensation. It does not modify the accepted v0.4.5 diagnostic files
and does not yet train a model.

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

No single MCAP topic is assumed to be physical ground truth. A final residual
dataset is forbidden in this version.

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

## Odometry-compensated reference-alignment validation

v0.5.1 implements the common-time geometry step required before the spatial
correspondence proposed for residual extraction. RLMB is transformed from its
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
DPE geometry epoch is not published. The result must be reviewed across the
exact ten-recording manifest before H100 vectors are promoted to the
Gaussian-training dataset.

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

The summary always records:

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

## Scientific boundary

This version answers only:

> Which MCAP-derived reference candidate is defensible enough to define lane-estimation error?

The following version may create the fixed 21-dimensional residual vector at
`0, 5, ..., 100 m` only after this answer is supported. Model fitting and
planner-level experiments remain separate later stages.

## Confidentiality

MCAP files, private configs, decoded field names, output tables, measurements,
and geometry remain BMW-confidential. Keep them outside the public repository
unless publication is explicitly approved. The `.gitignore` excludes common
private inputs and generated artifacts.
