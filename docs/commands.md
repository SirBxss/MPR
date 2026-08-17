# Supported commands

All seven v0.4.5 console aliases and their historical `python -m` forms remain
supported. v0.5.1 adds categorized motion-alignment validation, v0.6.0 adds
the canonical residual/Gaussian workflow, and v0.6.1 adds held-out Gaussian
adequacy diagnostics. Existing defaults and flags are unchanged; use `--help`
for the complete option set.

| Console alias | Python module form | Purpose and status | Required inputs | Generated outputs |
|---|---|---|---|---|
| `mpr-mcap` | `python -m lane_residuals.cli` | Legacy v0.3.x association/model command, retained for compatibility | One MCAP and its historical options | Legacy association audit, plots, optional dataset/model summaries |
| `mpr-probe-path-source` | `python -m lane_residuals.path_probe_cli` | Privacy-safe structural probe; diagnostic only | One MCAP | `estimated_drive_paths_joint_audit.json` at the selected `--output` path |
| `mpr-validate-path-geometry` | `python -m lane_residuals.geometry_validation_cli` | Corpus geometry and spline-hypothesis validation; no residual labels or model | MCAP files/directories; optional session map | Geometry CSV audits, JSON summaries, and diagnostic overlays |
| `mpr-audit-reference-candidates` | `python -m lane_residuals.reference_audit_cli` | Fail-closed reference-candidate discovery; no final residual export | MCAP corpus, exact session map, private signal config | Reference inventory/catalog, CSV audits, and validation summary |
| `mpr-audit-path-pairing` | `python -m lane_residuals.pairing_audit_cli` | One-recording EDP–RLMB pseudo-reference disagreement audit | One MCAP | Pair/message/chain/station CSVs, plots, and `pairing_summary.json` |
| `mpr-audit-edp-transitions` | `python -m lane_residuals.edp_transition_audit_cli` | Candidate and rollover diagnostics under both reconstruction hypotheses | One MCAP | EDP inventories, geometry/transition CSVs, plots, and summary JSON |
| `mpr-audit-path-pairing-batch` | `python -m lane_residuals.batch_pairing_audit_cli` | v0.4.5 ten-recording fixed-cohort aggregation | MCAP files/directories and exact `--drive-map` | Per-recording pairing outputs plus corpus CSVs, JSONs, and plots |
| `mpr-audit-reference-alignment` | `python -m lane_residuals.cli.alignment` | v0.5.1 odometry SE(2) compensation plus projection/resampling; no model training | One MCAP containing EDP, RLMB, and planar odometry | Alignment pair/station CSVs, comparison plot, and summary JSON |
| `mpr-audit-reference-alignment-batch` | `python -m lane_residuals.cli.alignment_batch` | v0.5.1 exact-manifest motion-alignment validation; no model training | MCAP files/directories and exact `--drive-map` | Per-recording alignment outputs plus aggregate CSVs, plot, manifest, and summary |
| `mpr-train-gaussian-baseline` | `python -m lane_residuals.cli.gaussian_baseline` | v0.6.0 canonical H100 export, leave-one-drive-out evaluation, and final Gaussian fit | Accepted complete v0.5.0 alignment-batch directory | Residual vectors, dataset/model summaries, fold/station evaluation CSVs, and diagnostics plot |
| `mpr-diagnose-gaussian-baseline` | `python -m lane_residuals.cli.gaussian_diagnostics` | v0.6.1 leave-one-drive-out marginal, tail, Q–Q, and Mahalanobis adequacy diagnostic | Complete unchanged v0.6.0 Gaussian output directory | Per-vector, marginal, and multivariate CSVs; two plots; strict JSON summary |

For the accepted ten-MCAP corpus, the historical `--drive-map` flag must point
to `config/private/mcap_sessions.private.json`. That session map is the
canonical grouping manifest for the two physical recording sessions. The
separate three-entry private drive-map copy is unused and must not be used,
merged, or inferred for this corpus.

The current local input/output layout is opt-in through command arguments:

```text
data/raw/mcap/
config/private/mcap_sessions.private.json
config/private/reference_signals.private.json
outputs/diagnostics/validation/<new-run-name>/
outputs/models/<new-model-run-name>/
```

Existing implemented default paths remain unchanged. Exit code `0` means the
command's diagnostic success condition was met, `2` means an input/dependency
or command error, and commands with a scientific completeness gate may return
`3` after writing valid diagnostic outputs.
