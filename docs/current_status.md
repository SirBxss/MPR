# Current project status

Last updated: 2026-08-26. This is the first file a new agent should read after
`AGENTS.md`. Update it whenever implementation, review, merge state, or the
critical path changes.

## Current checkpoint

- Repository version: v0.16.0 implementation under review; no real planner
  result has been run or interpreted yet.
- Integration state: merged to `main` at commit `38ddac5` through PR #6,
  `MPR v0.15.4: freeze development residual model`.
- The post-merge hand-off was merged through PR #7 at commit `22a2334`.
- Python 3.10 compatibility was merged through PR #8 at commit `e833e5a`;
  Python 3.10 and 3.12 CI both pass.
- Current implementation branch: `planner/v0.16-reference-sensitivity`.
- User verification: 315 tests pass with two expected skips.
- v0.16 implementation verification: 323 tests pass with two expected skips.
- Real private freeze run: complete and independently approved.
- The residual-modeling programme is frozen for planner development. Do not
  reopen model-family, state-count, convergence, or AR-ceiling searches on the
  current corpus without new evidence.

## Frozen development model

- Family: one-state conditional autoregressive Gaussian, with no latent-state
  switching or effective transition model.
- Configured AR ceiling: 0.99.
- Maximum fitted absolute AR coefficient: `0.9878812705276584`; the selected
  fit is interior and does not touch the 0.99 ceiling.
- Retained reporting reference: v0.15.1 at ceiling 0.98.
- Reference binding stations: `0, 5, 10, 15, 20, 25, 30 m`.
- Selected 0.99 binding stations: none.
- The 0.99, 0.995, and 0.999 all-clean fitted parameters are identical except
  for their configured ceiling.
- Selection basis: smallest tested nonbinding ceiling above the identical
  interior optimum. This is an engineering constraint release, not held-out
  performance selection.
- The strict v0.15.3 development gate remains failed.
- `final_model_selection_authorized=false`.
- `journey_level_generalization_estimated=false`.
- `planner_benefit_evaluated=false`.

Reviewed real-artifact hashes:

```text
development_residual_model.json
976259c05eb67e600b017a81bed77846a424b5687d51f4a04168431bfc7b6bd3

development_model_freeze_summary.json
7b00fda0e72c8ef8e94a07da755402407ea8d989f5c7dd3ee0837dfd85b8dba7
```

The freeze artifact records a 32-file v0.15.3 audit hash map, including
`ar_boundary_fold_comparison.csv`. Per-fold evidence remains in that immutable
v0.15.3 source artifact and does not need to be duplicated into the freeze.

## What is scientifically supported

- Autoregression captures the observed lag-one structure on the current
  within-outing corpus.
- The tested latent two-state switch does not earn its complexity over K=1.
- The convergence audit does not change that conclusion.
- The 0.98 AR cap binds near-field stations; releasing it produces an interior
  optimum, while marginal/calibration limitations remain.
- No completed model supports a claim of independent-journey generalization or
  planner-level benefit.
- RLMB remains a pseudo-reference with the documented source and timing
  limitations.

## Implemented v0.15.4 interfaces

Freeze command:

```bash
python -m lane_residuals.cli.development_model_freeze \
  "outputs/models/one_state_ar_boundary_v0153" \
  --one-state-ar-directory "outputs/models/one_state_ar_v0151" \
  --output-directory "outputs/models/development_residual_model_v0154"
```

Planner-facing sampler:

```bash
python -m lane_residuals.cli.development_residual_sampling \
  "outputs/models/development_residual_model_v0154/development_residual_model.json" \
  "outputs/planner/planner_condition_sequences.npz" \
  --sample-count 128 \
  --seed 20260826 \
  --output-directory "outputs/planner/residual_samples_v0154"
```

The sampler input NPZ contains exactly `conditions [B,T,6]` in physical units,
integer `lengths [B]`, unique nonempty `sequence_ids [B]`, and the exact
`feature_names [6]`. It exports signed physical residuals
`residual_samples_m [S,B,T,21]` with zero padding. It does not modify geometry
or execute a planner.

## Next critical phase: v0.16 planner sensitivity

The primary experiment is now an MPR-owned deterministic reference planner,
not a BMW-planner integration. This change keeps the first planner result
reproducible and isolates the effect of the residual sequence from unavailable
production configuration. BMW integration remains an optional later
transfer-validation step and must still use exact, Copilot-confirmed symbols.

Existing accepted artifacts are sufficient for the primary experiment:

- `alignment_station_comparison.csv` provides aligned RLMB pseudo-reference
  coordinates on H100 through `aligned_reference_x_m` and
  `aligned_reference_y_m`;
- the v0.13.1 sequence archive provides exact recording, pair, message,
  timestamp, condition, and sequence identity;
- v0.15.4 provides free-running signed residual draws on the same H100 grid.

The contract is fixed in `docs/reference_planner_predeclaration.md`. Claude's
time-shuffled null and accumulation metrics were accepted. The earlier
snapshot-only plan was rejected because it cannot identify temporal-order
effects. The implementation propagates a linearized lateral/heading error state
around recorded motion; it does not stitch ego-relative paths globally.

The arms are A0 zero, A1 within-sequence time-shuffled frozen AR, and A2 frozen
AR. A2 minus A1 is primary. A pure-NumPy tracking LQ controller avoids a solver
dependency and reports fixed envelope violations rather than enforcing them.
At least 20 paired Monte Carlo draws and per-sequence accumulation metrics are
required. Clean singleton sequences are excluded before sampling and recorded
in the scenario summary because they cannot support propagation or shuffling;
the rule does not inspect residual values or planner outcomes.

The seed-repetition suggestion from review is deferred to the reporting or
planner-evaluation phase. Repeated sampling seeds quantify Monte Carlo
sensitivity; they do not create independent-drive or dataset uncertainty.

## Reading map

- `docs/modeling_plan.md`: phase gates, evidence, and data-acquisition limits.
- `docs/output_contracts.md`: exact output files and schemas.
- `docs/aiohmm.md`: model equations, evaluation, and limitations.
- `docs/architecture.md`: package ownership and dependency boundaries.
- `docs/commands.md`: complete CLI surface.
- `README.md`: chronological project overview and usage.
