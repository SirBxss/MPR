# Supported commands

All seven v0.4.5 console aliases and their historical `python -m` forms remain
supported. v0.5.1 adds categorized motion-alignment validation, v0.6.0 adds
the canonical residual/Gaussian workflow, v0.6.1 adds held-out Gaussian
adequacy diagnostics, and v0.7.0 adds a prediction-time feature-availability
audit. v0.7.1 adds an explicit odometry-displacement speed source, and v0.7.2
adds fail-closed duplicate-timestamp handling with explicit evidence. v0.8.0
adds the frozen-cohort, same-fold conditional Gaussian comparison. v0.9.0 adds
the common gap-aware sequential dataset and training-drive-only transforms for
the three thesis model families. v0.10.0 adds the conditional Gaussian
temporal-null adapter and common generative metrics. v0.11.0 adds the fixed
development AIOHMM with input-dependent transitions, autoregressive emissions,
and training-only deterministic restart selection. Existing
historical command defaults and flags are unchanged; the conditional-feature
command requires `--speed-source`. Use `--help` for the complete option set.

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
| `mpr-audit-conditional-features` | `python -m lane_residuals.cli.conditional_features` | v0.7.2 exact-manifest speed, EDP-curvature, and KEEP_LANE-confidence availability audit with duplicate-timestamp evidence; no model fit | Raw MCAP corpus, accepted v0.5.0 alignment batch, complete v0.6.0 Gaussian directory, and explicit `--speed-source` | All-vector feature CSV, recording summary, availability plot, and strict JSON summary |
| `mpr-train-conditional-gaussian` | `python -m lane_residuals.cli.conditional_gaussian` | v0.8.0 frozen complete-feature cohort and same-fold conditional/unconditional Gaussian comparison | Complete unchanged v0.6.0 Gaussian directory and its reviewed v0.7.2 gap-50 feature-audit directory | Frozen cohort/exclusions, fold/station/vector comparison CSVs, final conditional model, plot, and strict JSON summaries |
| `mpr-build-sequential-dataset` | `python -m lane_residuals.cli.sequence_dataset` | v0.9.0 gap-aware sequence construction; no model fit or selection | Complete unchanged v0.8.0 conditional Gaussian directory | Raw physical-unit sequence tensor, sequence/frame provenance, drive folds, training-only standardizers, plot, and strict JSON summary |
| `mpr-train-sequence-gaussian` | `python -m lane_residuals.cli.sequence_gaussian` | v0.10.0 conditional Gaussian temporal null under the common sequence/evaluation interface | Complete unchanged v0.9.0 sequential dataset directory | Fold/frame/station metrics, fold and descriptive models, temporal diagnostic plot, and strict JSON summary |
| `mpr-train-sequence-aiohmm` | `python -m lane_residuals.cli.sequence_aiohmm` | v0.11.0 fixed-state AIOHMM; development-only and no held-out state-count/hyperparameter selection | Complete unchanged v0.9.0 sequential dataset directory | Common fold/frame/station metrics, state/restart diagnostics, fold and descriptive models, plot, and strict JSON summary |

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
outputs/datasets/<new-dataset-run-name>/
```

Existing implemented default paths remain unchanged. Exit code `0` means the
command's diagnostic success condition was met, `2` means an input/dependency
or command error, and commands with a scientific completeness gate may return
`3` after writing valid diagnostic outputs.
