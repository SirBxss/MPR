# Supported commands

All historical console aliases and their `python -m` forms remain supported.
v0.5.2 restores corpus-independent native projection alignment;
v0.13.0 builds the pre-model quality-gated expanded sequential dataset;
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
