# Minimal Path-Residual Model (MPR) v0.4.0

Version 0.4.0 adds a focused **EDP–RLMB pairing audit** to the fail-closed
lane-reference candidate workflow from v0.3.9. It reconstructs the estimated
`KEEP_LANE` spline and the metadata-confirmed ego path from
`/adp/road_lane_map_based`, pairs their source timestamps, places station zero
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

| Object | v0.4.0 role |
|---|---|
| Estimated drive path | Lane estimate being evaluated |
| Same-estimator debug path | Spline-semantic oracle only |
| Direct map-lane geometry | Primary pseudo-reference candidate |
| Stable pose + `distance_to_centerline` | Independent reconstruction candidate |
| Future vehicle positions | Diagnostic realised trajectory only |
| Fused ego-lane path | Operational comparator only |
| GNSS, odometry, transforms | Pose/frame validation support |

No single MCAP topic is assumed to be physical ground truth. A final residual
dataset is forbidden in this version.

## One-file EDP–RLMB pairing audit

Start with one representative MCAP and inspect 20 evenly distributed usable
pairs:

```powershell
python -m lane_residuals.pairing_audit_cli `
  ".\data\mcap_data\one_recording.mcap" `
  --max-pairs 20 `
  --output-directory ".\outputs\pairing_audit"
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
| `pairing_overlays.png` | Raw EDP/RLMB overlays, ego origin, footpoints, and 0–100 m stations |
| `pairing_audit.csv` | Timestamp deltas, coverage, path direction, origin offsets, and pair status |
| `diagnostic_disagreement.csv` | Reference-normal disagreement at 5 m stations, explicitly not thesis labels |
| `pairing_summary.json` | Counts, extraction failures, aggregate offsets, and scientific limitations |

The audit uses geometric arc length independently for each curve. It projects
`(0,0)` onto both curves and evaluates station `d` at
`s_ego_footpoint + d`; native spline or map station origins are never assumed
to coincide. A reversed vertex order is normalized toward positive vehicle x
and recorded explicitly. No rigid alignment or timestamp motion compensation
is applied, because either would hide the frame mismatch this audit is intended
to reveal.

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

   under the explicitly recorded positive-left convention;
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
python -m unittest discover -s tests -v
```

## Prepare the private signal configuration

```powershell
New-Item -ItemType Directory -Force ".\config"
Copy-Item ".\examples\reference_signals.private.example.json" `
  ".\config\reference_signals.private.json"
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
  ".\data\mcap_data" `
  --expected-file-count 10 `
  --session-map ".\config\mcap_sessions.private.json" `
  --signal-config ".\config\reference_signals.private.json" `
  --comparison-max-delta-ms 20 `
  --pose-lsa-max-delta-ms 50 `
  --output-directory ".\outputs\mcap_v039_reference_audit"
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

If only the future driven trajectory is available, v0.4.0 leaves the lane
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
