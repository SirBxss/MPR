# Current project status

Last updated: 2026-08-26. This is the first file a new agent should read after
`AGENTS.md`. Update it whenever implementation, review, merge state, or the
critical path changes.

## Current checkpoint

- Repository version: v0.15.4 development-model freeze and sampler.
- Base on `main`: commit `94bf365`, the merged v0.15.3 AR-boundary audit.
- Working branch: `modeling/v0.15.4-development-model-freeze`.
- Integration state at this checkpoint: the three v0.15.4 implementation,
  test, and documentation patches are applied locally; push/PR/merge still
  need to be recorded here after they occur.
- User verification: 315 tests pass with two expected skips.
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

Do not implement the BMW adapter from guesses. First obtain exact BMW-codebase
symbols and signatures through the user's connected Copilot for:

1. the planner reference-path type and reviewed operation for applying signed
   lateral offsets along its path-normal convention;
2. the planner invocation/runner and the outputs available for evaluation;
3. the source and temporal construction of all six schema-v1 conditions at
   each planner timestep;
4. scenario/reset boundaries and stable scenario identifiers;
5. the baseline planner metrics and accepted comparison harness.

Then predeclare the smallest useful planner experiment before inspecting its
results. At minimum compare the unchanged reference-path baseline with sampled
residual perturbations using identical scenarios and planner settings. Record
sampling seeds, sequence resets, failures, and paired scenario-level metrics.
Do not claim improvement merely because the planner remains feasible.

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
