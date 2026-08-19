# Project architecture

MPR keeps the accepted diagnostics frozen, retains v0.5.1 as a separate
odometry-compensated sensitivity audit, and provides the v0.6.0 canonical
residual/Gaussian workflow, v0.6.1 Gaussian adequacy diagnostics, the v0.7.2
conditional-feature audit, and the v0.8.0 frozen-cohort conditional Gaussian
comparison. v0.9.0 establishes MPR as the canonical thesis implementation and
adds the common gap-aware sequence contract used by the conditional Gaussian,
AIOHMM, and RC-GAN. LEEM is reference-only. The categorization separates scientific
arithmetic, orchestration, I/O, plots, and command adapters.

```text
src/lane_residuals/
├── cli/                 parsers, logging setup, main(), and exit-code mapping
├── workflows/           end-to-end diagnostic orchestration
├── domain/              current scientific calculations and data structures
├── io/                  MCAP decoding and generic report serialization
├── visualization/       current diagnostic plotting
├── modeling/            Gaussian and future statistical-model utilities
├── legacy/              v0.3.x, withdrawn, and superseded implementations
├── __init__.py          compatibility exports
└── *_cli.py, *.py       tiny compatibility facades for public import/module paths
scripts/
├── inspection/          one-off, non-package inspection helpers
└── private_data_extraction/  local BMW-data extraction helpers
config/
├── examples/            tracked placeholder-only templates
└── private/             ignored local configuration
data/
├── raw/mcap/            ignored, byte-preserved source recordings
└── intermediate/        optional ignored intermediates
outputs/diagnostics/
├── frozen/              checksum-protected accepted baselines
├── validation/          new comparison runs
├── modeling/            model adequacy and calibration diagnostics
└── archive/             preserved historical runs
outputs/models/           ignored private model runs and residual vectors
outputs/datasets/         ignored private sequence datasets and split manifests
tests/
├── domain/              scientific invariants
├── workflows/           orchestration and output behavior
├── io/                  decoding and serialization
├── cli/                 command-adapter tests
├── modeling/            statistical utilities
├── legacy/              withdrawn/v0.3.x compatibility
└── compatibility/       v0.4.5 public and packaging contracts
```

Package responsibilities:

- `cli` parses arguments, configures logging, calls one workflow, and maps
  errors or results to the established exit codes.
- `workflows` coordinates decoding, domain calculations, plots, and report
  writing for a complete command.
- `domain` contains current deterministic scientific rules, including temporal
  pairing, EDP reconstruction, RLMB chaining, odometry interpolation, rear-axle
  SE(2) transforms, fixed cohorts, reference diagnostics, and the immutable
  H100 residual-vector contract.
- `io` owns MCAP message decoding and reusable CSV/strict-JSON serialization.
  Prediction-time vehicle speed is decoded here with its source timestamp and
  qualifier; interpolation remains a domain rule.
- `visualization` renders diagnostic figures from already prepared data.
- `modeling` contains the Gaussian distribution and likelihood/calibration
  primitives. The v0.6.0 workflow uses them only after the domain contract has
  accepted a complete exact-manifest H100 dataset. The v0.6.1 workflow
  recomputes aligned leave-one-drive-out predictions and compares their
  marginal and Mahalanobis behavior with Gaussian reference distributions.
  The v0.8.0 conditional model adds a fold-standardized linear mean while
  retaining one condition-invariant 21-dimensional covariance.
- `domain.sequence_dataset` splits frames at recording, missing-pair, and
  source-time gaps; owns padded conditions/residuals, masks, lengths, and
  train-drive-only standardization.
- `modeling.base` defines the shared fit, sample, log-probability, save, and
  load lifecycle. Model-specific code must not redefine the dataset or split.
- `domain.conditional_features` owns recording-local direct-speed
  interpolation, fixed-interval unsigned odometry-speed derivation, EDP
  native-to-ego station translation, fixed H100 curvature summaries, and exact
  confidence-bucket coverage rules.
- `legacy` preserves v0.3.x association/preprocessing, withdrawn provisional
  residual behavior, and its synthetic plotting without presenting it as the
  current scientific pipeline.

The intended dependency direction is:

```text
cli -> workflows -> domain / io / visualization
```

Domain modules must not import CLI or workflows. I/O modules must not import
CLI or workflows. A workflow must never import another CLI. Compatibility
facades may forward names but must not own implementation logic.

Current diagnostics quantify EDP–RLMB or candidate-to-candidate disagreement.
The accepted v0.5.0 projection output supplies the v0.6.0 model vectors; the
v0.5.1 odometry workflow remains optional because DPE does not publish its exact
geometry epoch. The model workflow accepts exactly `0, 5, ..., 100 m`, requires
one fixed H100 cohort, and evaluates by physical drive before fitting the final
all-data model. The adequacy workflow accepts only a reconciled v0.6.0 output,
never an available-case station profile. The feature workflow additionally
requires the exact accepted alignment manifest and raw MCAP basename set. It
retains one audit row per residual vector and fits no model. The v0.8.0
workflow consumes that immutable audit, selects complete rows without looking
at residual values, and evaluates conditional and unconditional models on
identical drive-held-out folds. Legacy/withdrawn
code is retained only for reproducibility and compatibility. The v0.9.0
workflow consumes the frozen v0.8.0 cohort, performs no model fitting, and
writes leave-one-physical-drive-out development folds. It explicitly does not
create an untouched final test from the present two-drive corpus.

One deliberate follow-up remains: `domain.geometry_validation` currently uses
the legacy polyline-projection primitive to preserve byte-for-byte scientific
behavior. Moving that arithmetic into a neutral domain geometry utility should
only be attempted with dedicated numerical characterization tests.
