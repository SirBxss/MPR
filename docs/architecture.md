# Project architecture

MPR v0.4.5 is organized as a small diagnostic research application. The
categorization is mechanical: scientific arithmetic and observable output
contracts remain those of the accepted v0.4.5 baseline.

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
└── archive/             preserved historical runs
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
  pairing, EDP reconstruction, RLMB chaining, fixed cohorts, and reference
  diagnostics.
- `io` owns MCAP message decoding and reusable CSV/strict-JSON serialization.
- `visualization` renders diagnostic figures from already prepared data.
- `modeling` contains the Gaussian utility and is distinct from the current
  diagnostic pipeline; v0.4.5 does not train a model.
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
They are not trained models and are not ground-truth residuals. Modeling
utilities are reusable but inactive in v0.4.5. Legacy/withdrawn code is retained
only for reproducibility and compatibility.

One deliberate follow-up remains: `domain.geometry_validation` currently uses
the legacy polyline-projection primitive to preserve byte-for-byte scientific
behavior. Moving that arithmetic into a neutral domain geometry utility should
only be attempted with dedicated numerical characterization tests.
