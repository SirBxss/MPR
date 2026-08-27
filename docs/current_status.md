# Current project status

Last updated: 2026-08-27. This is the first file a new agent should read after
`AGENTS.md`. Update it whenever implementation, review, merge state, or the
critical path changes.

## Current checkpoint

- Repository version: corrected v0.16.0 implementation and real planner run
  complete. Claude independently approved the corrected code and result with
  nonblocking reporting comments. The first pre-fix planner output remains
  rejected; its v0.15.4 residual samples were valid and were reused.
- Integration state: merged to `main` at commit `38ddac5` through PR #6,
  `MPR v0.15.4: freeze development residual model`.
- The post-merge hand-off was merged through PR #7 at commit `22a2334`.
- Python 3.10 compatibility was merged through PR #8 at commit `e833e5a`;
  Python 3.10 and 3.12 CI both pass.
- Current implementation branch: `planner/v0.16-reference-sensitivity`,
  reviewed remotely at commit `1244c48` before this completion update.
- Merged-main baseline verification: 315 tests pass with two expected skips.
- Corrected v0.16 implementation verification: 324 tests pass with two
  expected skips. A non-constant-profile direct quadratic solve verifies the
  first curvature command and optimized horizon objective.
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
- For the fixed v0.16 reference planner and current within-outing cohort,
  temporal ordering changes planner behavior even when each sequence/draw
  retains exactly the same multiset of H100 residual profiles. This is a
  sensitivity result, not planner benefit or a production-planner result.
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

## Completed v0.16 planner sensitivity

The primary experiment uses an MPR-owned deterministic reference planner, not
BMW planner integration. This keeps the result reproducible and isolates
temporal ordering from unavailable production configuration. BMW integration
remains an optional later transfer-validation step and must still use exact,
Copilot-confirmed symbols.

Existing accepted artifacts are sufficient for the primary experiment:

- `alignment_station_comparison.csv` provides aligned RLMB pseudo-reference
  coordinates on H100 through `aligned_reference_x_m` and
  `aligned_reference_y_m`;
- the v0.13.1 sequence archive provides exact recording, pair, message,
  timestamp, condition, and sequence identity;
- v0.15.4 provides free-running signed residual draws on the same H100 grid.

The contract and its dated amendment record are in
`docs/reference_planner_predeclaration.md`. The earlier snapshot-only plan was
rejected because it cannot identify temporal-order effects. The implementation
propagates a linearized lateral/heading error state around recorded motion; it
does not stitch ego-relative paths globally.

The executed arms are A0 zero, A1 within-sequence time-shuffled frozen AR, and
A2 frozen AR. A2 minus A1 is primary. The corrected run uses 128 paired draws,
15 eligible sequences, 4,083 active frames, residual seed `20260826`, and
shuffle seed `20260827`. One clean singleton was excluded before sampling and
recorded without inspecting residual values or planner outcomes.

Primary A2-minus-A1 results are macro means over the 15 sequences. The quoted
interval is the predeclared 2.5/97.5 percentile spread across paired Monte
Carlo draws, not a confidence interval for the dataset or mean:

| Metric | Mean difference | Paired-draw interval | Verdict |
|---|---:|---:|---|
| integrated absolute lateral error | +0.176956 m s | [0.122456, 0.235142] | effect |
| maximum absolute lateral error | +0.012402 m | [0.006209, 0.017037] | effect |
| constraint-violation fraction | -0.093137 | [-0.131466, -0.058316] | effect |
| fraction beyond 0.3 m | +0.000198 | [0.000000, 0.002551] | indeterminate; descriptive |
| final absolute lateral error | +0.004085 m | [-0.023638, 0.029294] | indeterminate |

The effect is a trade, not a benefit claim. Relative to A1, A2 has 13.4%
greater integrated absolute lateral error and 8.5% greater maximum absolute
lateral error, while producing fewer fixed-envelope violations. Post-hoc
descriptive summaries from the retained frame metrics make the mechanism more
legible: macro p95 absolute curvature rate is `0.9330` for A1 versus `0.2096`
for A2, macro p95 absolute lateral jerk is `409.60` versus `76.01 m/s^3`, and
macro mean absolute lateral error is `0.06440` versus `0.06996 m`. These
descriptive quantities were not predeclared decision gates.

The violation envelopes are not enforced constraints or safety limits. A0 has
zero planner correction and zero lateral error, yet its equal-sequence macro
violation fraction is `0.259355`. On a pooled-frame basis, nominal-path lateral
acceleration trips at `0.061964`, nominal-path jerk trips at `0.403380`, and
any envelope trips at `0.409013`. This is an exogenous recorded-reference and
envelope-calibration floor, not planner behavior. A1's extreme derivative
values are likewise a statistical-null/protocol artifact of shuffling the
reference every source frame without an actuator or enforced rate limit;
absolute comfort or safety interpretations are invalid.

Reviewed corrected-artifact lineage:

```text
reference_planner_scenarios.npz
615f6c7d5ef6b6b9c0770c65b58bb23c573a838579aa4fdf3f25c141a15c0591

sampled_residual_sequences.npz
5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa

reference_planner_frame_metrics.npz
9d2b6a724a648839756597d40497cf6a2fc9b55a4422230fcddb317fe26a2a9f

reference_planner_sequence_metrics.csv
3f9ea8db4e4e2817c450dd82ebe8a52042a12e6aa76fbb0d4b7b31da4d96a1df

reference_planner_sensitivity_summary.json
38a04f655f9c9f6ec0e89d817534e8e289e0571787c229fa630d37406bcc8154
```

Codex inspected the uploaded raw NPZ and CSV, recomputed the summary exactly,
and reproduced selected A1/A2 trajectories bit for bit from the corrected code.
Claude independently regenerated the pipeline under Python 3.11.15 and NumPy
2.4.4. Its sample NPZ was not byte-identical (`c8f3e648...` rather than
`5f54e56f...`), so the two runs are not interchangeable lineage artifacts and
the exact byte-level cause remains unisolated. The shuffle count, A0 macro
result, and all primary contrasts nevertheless agree at the precision reported
in the final review. This is numerical reproduction across environments, not
byte identity; the hashes above remain the authoritative accepted lineage.

## Next actions

Merge the reviewed v0.16 branch after this completion documentation is applied,
the full suite passes, and Python 3.10/3.12 CI is green. Generated scenario,
sample, and planner-output artifacts remain outside Git.

Claude's suggested unconditional-Gaussian A3 arm is scientifically useful but
is not required for the accepted primary result. It changes both marginal and
temporal structure, so it must not be added post hoc to this experiment. If
pursued, define it as a separate v0.16.1 extension, predeclare its hypothesis,
metric, direction, and reporting rule before implementation or execution, and
report it regardless of outcome. BMW transfer validation remains optional and
separate.

The seed-repetition suggestion remains deferred. Repeated sampling seeds would
quantify Monte Carlo sensitivity; they would not create independent-drive or
dataset uncertainty.

## Reading map

- `docs/modeling_plan.md`: phase gates, evidence, and data-acquisition limits.
- `docs/output_contracts.md`: exact output files and schemas.
- `docs/aiohmm.md`: model equations, evaluation, and limitations.
- `docs/architecture.md`: package ownership and dependency boundaries.
- `docs/commands.md`: complete CLI surface.
- `README.md`: chronological project overview and usage.
