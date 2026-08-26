# Supported commands

All historical console aliases and their `python -m` forms remain supported.
v0.5.2 restores corpus-independent native projection alignment;
v0.13.0 preserves the fail-closed expanded sequential checkpoint, and v0.13.1
adds accepted-boundary context only for its frozen odometry speed feature;
v0.14.0 adds the leakage-safe clean-drive evaluation contract and Gaussian
re-baseline while keeping mixed-source fragments supplementary; v0.15.0 adds
the exact-contract two-state expanded AIOHMM evaluation and corrected
occupancy-safe generalized EM; v0.15.1 adds the exact one-state conditional-AR
ablation against both frozen baselines without changing the evaluation;
v0.15.2 re-fits only the two-state model with the fixed absolute per-frame EM
stopping rule and compares it with both reviewed autoregressive artifacts;
v0.15.3 varies only the one-state AR ceiling over the fixed predeclared grid
and consolidates both Gaussian and both reviewed autoregressive references;
v0.15.4 freezes the structurally nonbinding 0.99 development model without
refitting and exports physical free-running residual sequences for planner use;
v0.12.2 adds a read-only complete-corpus topology/quality audit;
v0.5.1 remains categorized motion-alignment sensitivity validation. v0.6.0 adds
the canonical residual/Gaussian workflow, v0.6.1 adds held-out Gaussian
adequacy diagnostics, and v0.7.0 adds a prediction-time feature-availability
audit. v0.7.1 adds an explicit odometry-displacement speed source, and v0.7.2
adds fail-closed duplicate-timestamp handling with explicit evidence. v0.8.0
adds the frozen-cohort, same-fold conditional Gaussian comparison. v0.9.0 adds
the common gap-aware sequential dataset and training-drive-only transforms for
the three thesis model families. v0.10.0 adds the conditional Gaussian
temporal-null adapter and common generative metrics. v0.11.0 adds the fixed
development AIOHMM with input-dependent transitions, autoregressive emissions,
and training-only deterministic restart selection. v0.12.1 completes the
expanded-corpus continuity/session audit; it does not stitch sequences or fit
any model. Existing
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
| `mpr-audit-native-projection-alignment-batch` | `python -m lane_residuals.cli.projection_alignment_batch` | v0.5.2 accepted exact-manifest native projection/resampling; no motion compensation or model training | MCAP files/directories, exact `--drive-map`, accepted corpus inventory, and positive expected count | Per-recording native alignment outputs, aggregate CSVs/plot, manifests, summary, and SHA-256 provenance |
| `mpr-audit-topology-semantics` | `python -m lane_residuals.cli.topology_semantics_audit` | v0.12.2 read-only EDP enum/transition and alignment-quality audit; eligibility unchanged | Exact MCAP corpus, private map, complete v0.12.1 inventory, and complete v0.5.2 alignment batch | Message/recording/session/transition/outlier CSVs, plot, summary, manifest, provenance, and packaged inventory lineage |
| `mpr-build-expanded-sequential-dataset` | `python -m lane_residuals.cli.expanded_sequence_dataset` | v0.13.0 quality-gated sensor-topology H100 profiles and physical-session sequences; no split or model selection | Exact raw MCAP corpus, complete v0.5.2 alignment, and corrected complete v0.12.2 topology audit | Deterministic profile archive, sequence/eligibility/stitch/exclusion audits, drive summary, plot, contract, manifest, and provenance |
| `mpr-build-expanded-sequential-dataset-v0131` | `python -m lane_residuals.cli.expanded_sequence_dataset_v0131` | v0.13.1 accepted-boundary context for the unchanged 50 ms odometry speed only; v0.13.0 tensor parity enforced | v0.13.0 output plus its exact raw/alignment/corrected-topology lineage | Expanded deterministic archive, boundary-context/parity/stitch audits, summaries, plot, contract, manifest, and provenance |
| `mpr-evaluate-expanded-gaussian` | `python -m lane_residuals.cli.expanded_gaussian` | v0.14.0 unconditional/conditional Gaussian re-baseline on four leave-one-clean-recording-group-out folds within one outing; no random frame split or hyperparameter search | Complete unchanged v0.13.1 expanded sequence directory | Frozen evaluation contract, fold/station/frame metrics, fold and descriptive models, comparison plot, and strict summary |
| `mpr-evaluate-expanded-aiohmm` | `python -m lane_residuals.cli.expanded_aiohmm` | v0.15.0 fixed two-state AIOHMM on the exact v0.14.0 clean-drive protocol; no held-out tuning | Complete unchanged v0.13.1 directory and its exact v0.14.0 Gaussian result directory | Fold/station/frame/state/restart metrics, fold and descriptive models, diagnostic plot, and strict comparison summary |
| `mpr-evaluate-expanded-ar-ablation` | `python -m lane_residuals.cli.expanded_ar_ablation` | v0.15.1 fixed one-state conditional AR; isolates autoregression from latent switching with no evaluation drift | Complete unchanged v0.13.1 directory plus its exact v0.14.0 Gaussian and reviewed v0.15.0 AIOHMM result directories | One-state fold/station/frame/restart evidence, paired three-model diagnostics, models, and strict Gaussian/AIOHMM comparison summary |
| `mpr-audit-expanded-aiohmm-convergence` | `python -m lane_residuals.cli.expanded_aiohmm_convergence` | v0.15.2 fixed two-state convergence audit; only the EM stopping scale and threshold differ from v0.15.0 | Complete unchanged v0.13.1 directory plus its exact v0.14.0 Gaussian, reviewed v0.15.0 AIOHMM, and reviewed v0.15.1 one-state AR directories | Corrected two-state fold/station/frame/state/restart evidence, old/new convergence comparison, diagnostic plot, models, and strict two-reference summary |
| `mpr-audit-expanded-ar-boundary` | `python -m lane_residuals.cli.expanded_ar_boundary` | v0.15.3 fixed one-state AR-ceiling sensitivity; only 0.98, 0.99, 0.995, and 0.999 are evaluated | Complete unchanged v0.13.1 directory plus exact v0.14.0, reviewed v0.15.0, v0.15.1, and v0.15.2 result directories | Three candidate subdirectories, consolidated seven-row model table, paired fold/station tables, boundary/calibration plot, and strict lineage summary |
| `mpr-freeze-development-residual-model` | `python -m lane_residuals.cli.development_model_freeze` | v0.15.4 fixed 0.99 development-model freeze; no refit, performance selection, or final-model claim | Complete reviewed v0.15.1 and v0.15.3 directories | Self-contained physical-unit sampler bundle and strict freeze summary |
| `mpr-sample-development-residuals` | `python -m lane_residuals.cli.development_residual_sampling` | v0.15.4 deterministic free-running H100 residual generation; no path modification or planner execution | Frozen v0.15.4 model JSON and exact condition-sequence NPZ | Physical residual-sample NPZ and strict sampling summary |
| `mpr-audit-reference-alignment` | `python -m lane_residuals.cli.alignment` | v0.5.1 odometry SE(2) compensation plus projection/resampling; no model training | One MCAP containing EDP, RLMB, and planar odometry | Alignment pair/station CSVs, comparison plot, and summary JSON |
| `mpr-audit-reference-alignment-batch` | `python -m lane_residuals.cli.alignment_batch` | v0.5.1 exact-manifest motion-alignment validation; no model training | MCAP files/directories and exact `--drive-map` | Per-recording alignment outputs plus aggregate CSVs, plot, manifest, and summary |
| `mpr-train-gaussian-baseline` | `python -m lane_residuals.cli.gaussian_baseline` | v0.6.0 canonical H100 export, leave-one-drive-out evaluation, and final Gaussian fit | Historical complete v0.5.0 or current complete v0.5.2 native alignment batch | Residual vectors, dataset/model summaries, fold/station evaluation CSVs, and diagnostics plot |
| `mpr-diagnose-gaussian-baseline` | `python -m lane_residuals.cli.gaussian_diagnostics` | v0.6.1 leave-one-drive-out marginal, tail, Q–Q, and Mahalanobis adequacy diagnostic | Complete unchanged v0.6.0 Gaussian output directory | Per-vector, marginal, and multivariate CSVs; two plots; strict JSON summary |
| `mpr-audit-conditional-features` | `python -m lane_residuals.cli.conditional_features` | v0.7.2 exact-manifest speed, EDP-curvature, and KEEP_LANE-confidence availability audit with duplicate-timestamp evidence; no model fit | Raw MCAP corpus, accepted v0.5.0 alignment batch, complete v0.6.0 Gaussian directory, and explicit `--speed-source` | All-vector feature CSV, recording summary, availability plot, and strict JSON summary |
| `mpr-train-conditional-gaussian` | `python -m lane_residuals.cli.conditional_gaussian` | v0.8.0 frozen complete-feature cohort and same-fold conditional/unconditional Gaussian comparison | Complete unchanged v0.6.0 Gaussian directory and its reviewed v0.7.2 gap-50 feature-audit directory | Frozen cohort/exclusions, fold/station/vector comparison CSVs, final conditional model, plot, and strict JSON summaries |
| `mpr-build-sequential-dataset` | `python -m lane_residuals.cli.sequence_dataset` | v0.9.0 gap-aware sequence construction; no model fit or selection | Complete unchanged v0.8.0 conditional Gaussian directory | Raw physical-unit sequence tensor, sequence/frame provenance, drive folds, training-only standardizers, plot, and strict JSON summary |
| `mpr-train-sequence-gaussian` | `python -m lane_residuals.cli.sequence_gaussian` | v0.10.0 conditional Gaussian temporal null under the common sequence/evaluation interface | Complete unchanged v0.9.0 sequential dataset directory | Fold/frame/station metrics, fold and descriptive models, temporal diagnostic plot, and strict JSON summary |
| `mpr-train-sequence-aiohmm` | `python -m lane_residuals.cli.sequence_aiohmm` | v0.11.0 fixed-state AIOHMM; development-only and no held-out state-count/hyperparameter selection | Complete unchanged v0.9.0 sequential dataset directory | Common fold/frame/station metrics, state/restart diagnostics, fold and descriptive models, plot, and strict JSON summary |
| `mpr-audit-corpus-inventory` | `python -m lane_residuals.cli.corpus_inventory` | v0.12.1 read-only, fail-closed expanded-corpus continuity/session audit | Recursive MCAP root and exact private basename-to-drive map | File/topic/edge CSVs, proposed groups, strict summary, and diagnostic plot |

Run the expanded-corpus audit with a new empty output directory:

```bash
python -m lane_residuals.cli.corpus_inventory \
  "data/raw/mcap" \
  --drive-map "config/private/mcap_sessions.private.json" \
  --output-directory \
  "outputs/diagnostics/data/expanded_corpus_inventory_v0121"
```

The fixed stitch-candidate source-gap gate is 200 ms. Exact basename coverage
is mandatory, including duplicate-key detection in the JSON map. If coverage
or file usability is incomplete, all six reports are still written and the
command returns 3. The command never infers drive identity, changes the private
map, or performs cross-MCAP sequence stitching.

Run the accepted native projection batch with an explicit positive expected
count. The corpus inventory is provenance and a fail-closed prerequisite:

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

`--maximum-pair-delta-ms` defaults to no gate. The source delta remains in the
audit rows but is never used numerically for alignment. MCAPs are processed
independently; no pair crosses a recording boundary.

Run the read-only topology-semantics and alignment-quality audit:

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

The 1.0 m anchor-distance listing is diagnostic only. It does not change the
accepted topology gate or H60/H100 eligibility.

Build the v0.13.0 pre-model dataset:

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

The cadence tolerance defaults to 200 ms. The established v0.9 condition
schema uses unsigned 50 ms odometry-displacement speed with a 50 ms maximum
recording-local interpolation span. No cross-MCAP feature interpolation,
train/validation/test assignment, standardizer fit, or model training occurs.

Build v0.13.1 without modifying the v0.13.0 directory:

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

Only a right-boundary profile whose prior-file odometry context passes every
declared gate can be restored. The boundary audit retains topic/schema,
timestamp, bracket, extrapolation, contributing-MCAP, and rejection evidence.

Run the v0.14.0 Gaussian re-baseline from a new empty output directory:

```bash
python -m lane_residuals.cli.expanded_gaussian \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --output-directory "outputs/models/expanded_gaussian_v0140"
```

Primary evaluation is leave-one-clean-recording-group-out over groups 001--004.
The groups are separated portions of one longer same-day outing, so this is not
independent-journey validation. Every fold fits its standardizer on the other
three clean groups only. Drives
005--008 are mixed-source fragments and are never used for fitting or primary
model comparison; a model trained on all clean drives evaluates them only as a
supplementary transfer check. The fixed unconditional and six-feature linear
conditional Gaussians use common Monte Carlo seeds and identical rows. No
random frame split, held-out hyperparameter search, or final-model claim is
made.

Run the v0.15.0 AIOHMM from a new empty output directory:

```bash
python -m lane_residuals.cli.expanded_aiohmm \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --output-directory "outputs/models/expanded_aiohmm_v0150"
```

The command validates every v0.14 output hash and requires its source lineage,
fold transforms, sample count, and seed to match v0.13.1 exactly. The two-state
configuration is fixed; mixed fragments remain supplementary. Exit code `0`
means the workflow completed, not that every scientific acceptance check
passed. Read `result_classification` and `development_acceptance_checks` in the
summary before promoting the model.

Run the v0.15.1 one-state AR ablation from a new empty output directory:

```bash
python -m lane_residuals.cli.expanded_ar_ablation \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --output-directory "outputs/models/one_state_ar_v0151"
```

The command permits exactly two architecture changes from v0.15: one state
instead of two and therefore no effective input-dependent transition. Every
other fitted-model hyperparameter, restart count, fold, training-only
standardizer, sampling seed, sample count, and metric must match. It reports
one-state-minus-Gaussian deltas to measure the AR contribution and symmetric
one-state/two-state deltas to measure the incremental value of latent
switching. A negative delta is better. The four technical groups still
represent one outing, so paired group results remain within-outing development
evidence only.

Run the v0.15.2 two-state convergence audit from a new empty output directory:

```bash
python -m lane_residuals.cli.expanded_aiohmm_convergence \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --output-directory "outputs/models/two_state_convergence_v0152"
```

The convergence rule is fixed to absolute standardized log-probability
improvement per training frame with a `1e-3` threshold. The CLI rejects a
different tolerance, AR bound, state count, restart count, or any other drift
from the reviewed v0.15.0 configuration. It validates all three upstream
directories and their hashes before creating output. The summary compares the
corrected two-state model with both the original two-state and one-state fits;
it does not perform model selection or the later AR-boundary sweep.

Run the v0.15.3 one-state AR-boundary sensitivity from a new empty output
directory:

```bash
python -m lane_residuals.cli.expanded_ar_boundary \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  --gaussian-directory "outputs/models/expanded_gaussian_v0140" \
  --aiohmm-directory "outputs/models/expanded_aiohmm_v0150_reviewed" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --two-state-convergence-directory \
  "outputs/models/two_state_convergence_v0152" \
  --output-directory "outputs/models/one_state_ar_boundary_v0153"
```

The CLI requires the unchanged 0.98 v0.15.1 configuration and rejects any
user-supplied baseline drift before creating output. It reuses that reviewed
artifact as the 0.98 row, then fits only the fixed 0.99, 0.995, and 0.999
candidates. Every candidate changes only
`maximum_absolute_autoregression`. The consolidated table includes the
unconditional Gaussian, conditional Gaussian, corrected two-state AIOHMM,
and all four one-state ceilings. A successful command means the audit was
completed, not that a higher ceiling or final thesis model was accepted.

Freeze the reviewed development model into a new empty directory:

```bash
python -m lane_residuals.cli.development_model_freeze \
  "outputs/models/one_state_ar_boundary_v0153" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --output-directory "outputs/models/development_residual_model_v0154"
```

The selected cap is fixed in code at 0.99. The command verifies every source
hash, the failed strict performance decision, the identical higher-cap model
payloads, and the absence of 0.99 boundary contact before writing two files.
It never offers a CLI hyperparameter-selection flag.

Generate residual sequences from a physical condition archive:

```bash
python -m lane_residuals.cli.development_residual_sampling \
  "outputs/models/development_residual_model_v0154/development_residual_model.json" \
  "outputs/planner/planner_condition_sequences.npz" \
  --sample-count 128 \
  --seed 20260826 \
  --output-directory "outputs/planner/residual_samples_v0154"
```

The input NPZ must contain exactly `conditions`, `lengths`, `sequence_ids`,
and `feature_names`. Conditions use physical units and shape `[B,T,6]`; padded
frames are zero. The exporter writes signed residuals in metres with shape
`[samples,B,T,21]` and keeps padded frames zero.

Build the fixed primary v0.16 scenario and v0.15.4 condition archives:

```bash
python -m lane_residuals.cli.reference_planner_scenarios \
  "outputs/datasets/expanded_sensor_sequence_dataset_v0131" \
  "outputs/diagnostics/validation/reference_alignment_batch_v052" \
  --output-directory "outputs/planner/reference_planner_scenarios_v016"
```

Pass its `planner_condition_sequences.npz` to the v0.15.4 sampler with at
least 20 draws, then run:

```bash
python -m lane_residuals.cli.reference_planner_sensitivity \
  "outputs/planner/residual_samples_v0154" \
  "outputs/planner/reference_planner_scenarios_v016/reference_planner_scenarios.npz" \
  --shuffle-seed 20260827 \
  --output-directory "outputs/planner/reference_planner_sensitivity_v016"
```

The fixed equations and claim limits are in
`docs/reference_planner_predeclaration.md`.

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
