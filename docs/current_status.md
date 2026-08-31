# Current project status

Last updated: 2026-08-31. This is the first file a new agent should read after
`AGENTS.md`. Update it whenever implementation, review, merge state, or the
critical path changes.

## Current checkpoint

- Repository version: v0.16.2 spatial-structure audit complete, independently
  reproduced, approved, and merged. v0.16.1 real A3 sampling and planner
  transfer are also complete, independently reproduced, approved, and merged.
  The corrected v0.16
  implementation and real planner run remain complete and approved. The first
  pre-fix v0.16 planner output remains rejected; its v0.15.4 residual samples
  were valid and were reused.
- The v0.15.4 development freeze was merged at commit `38ddac5` through PR #6,
  `MPR v0.15.4: freeze development residual model`.
- The post-merge hand-off was merged through PR #7 at commit `22a2334`.
- Python 3.10 compatibility was merged through PR #8 at commit `e833e5a`;
  Python 3.10 and 3.12 CI both pass.
- The complete v0.16 planner work was merged through PR #9 at commit
  `e6f6307`; its post-merge GitHub Actions run passes.
- The complete v0.16.1 Gaussian transfer was merged through PR #10 at commit
  `0f46758`; its post-merge Python 3.10 and 3.12 GitHub Actions jobs pass.
- The complete v0.16.2 spatial-structure audit was merged through PR #11 at
  commit `99feb14`; its post-merge Python 3.10 and 3.12 GitHub Actions jobs
  pass.
- Current maintenance branch: `maintenance/v0.16.2-final-handoff`.
- Merged-main baseline verification: 339 tests pass with two expected skips.
- v0.16.2 focused verification: 339 tests pass with two expected skips. The
  tests cover population arithmetic, exact output schemas, lineage tampering,
  extra inputs, nonzero padding, non-overwrite behavior, and CLI exit codes.
- Corrected v0.16 implementation verification: 324 tests pass with two
  expected skips. A non-constant-profile direct quadratic solve verifies the
  first curvature command and optimized horizon objective.
- v0.16.1 synthetic implementation verification: 329 tests pass with two
  expected skips. The complete synthetic v0.13.1 through v0.16.1 chain covers
  deterministic A3 sampling and transfer, exact standardizer mismatch, accepted
  v0.16 hash mismatch, and sampling-summary tamper failures.
- Real v0.16.1 verification: A3 sampling passed the independent pre-planner
  gate; Codex and Claude each re-executed all 1,920 A3 sequence runs and
  522,624 active planner frames. Both reproduced every primary interval and
  the predeclared `full support` decision. Claude returned final `GO` with one
  mandatory non-gating length-dependence reporting qualifier, now encoded in
  the summary contract and documentation.
- Real private freeze run: complete and independently approved.
- The residual-modeling programme is frozen for planner development. Do not
  reopen model-family, state-count, convergence, or AR-ceiling searches on the
  current corpus without new evidence.
- The first v0.16.2 review returned `AMEND`. The corrected contract received a
  focused independent `GO` before implementation. The implementation reproduces
  the reviewer's previously disclosed fixed statistics on the accepted
  artifacts. Claude's final review independently regenerated both ensembles,
  reconciled every output, and returned `GO`; the phase is accepted and closed.

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
- For the same planner and cohort, the v0.14 unconditional Gaussian is much
  rougher than the frozen AR and has lower deviation under the predeclared
  equal-sequence macro. The deviation half is length-dependent and must never
  be reported without the exact cohort qualifier recorded below.
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

## Completed v0.16.1 Gaussian planner transfer

v0.16.1 is a separately labelled A3 extension, not an amendment to the
completed v0.16 result. It uses the immutable v0.14 unconditional-Gaussian
all-clean descriptive fit, runs only A3 through the accepted planner, and
compares it with immutable accepted A1/A2 metrics. A3 changes marginal
distribution, cross-station covariance, and temporal structure, so only the
v0.16 A2-minus-A1 comparison supports a causal temporal-order interpretation.

The real run uses 128 independent A3 draws, 15 sequences, 4,083 active frames,
Gaussian seed `20260828`, bootstrap seed `20260829`, and 20,000 independent
two-sample bootstrap replicates. The three sequences shorter than 20 frames are
excluded only from the primary p95 macros. All four intervals lie strictly in
their predeclared directions:

| Metric | A2 | A3 | A3 minus A2 | Independent-draw interval | k/N |
|---|---:|---:|---:|---:|---:|
| p95 absolute curvature rate | 0.168162 | 1.938071 | +1.769909 | [1.760356, 1.779786] | 12/12 |
| p95 absolute lateral jerk | 68.9550 | 791.1659 | +722.2110 | [719.136, 725.308] | 12/12 |
| mean absolute lateral error | 0.0699641 m | 0.0586593 m | -0.0113049 m | [-0.0128263, -0.0097855] | 10/15 |
| integrated absolute lateral error | 1.496831 m s | 1.418571 m s | -0.078260 m s | [-0.103351, -0.053499] | 10/15 |

The predeclared rule therefore returns smoothness pass, deviation pass, and
`overall_decision = full support`. This decision is retained exactly; the
post-result cohort diagnostic is not promoted into a new gate.

The deviation half is length-dependent. Mean absolute error is 16.2% lower
under the equal-sequence macro and 5.4% lower in the pooled-frame summary, but
both deviation metrics reverse on the same 5 of 15 sequences. Those sequences
contain 2,365 of 4,083 active frames (57.9%) and rank 1st, 2nd, 6th, 7th, and
8th by active-frame length. Thus all five are among the eight longest, both
longest sequences reverse, and every sequence with at most 174 frames agrees.
The final-review draft said "five of the six longest"; an exact rank audit
corrected that wording to the ranks above. Smoothness agrees in the
hypothesised direction on all 12 eligible sequences and every reported
aggregation.

The result may be stated only as a planner-observable model trade for this
fixed reference planner and one outing. It does not establish that A3-minus-A2
is caused only by temporal structure, that either model is generally better,
planner benefit, comfort, safety, BMW behavior, production readiness, physical
ground truth, final model selection, or generalization. The intervals quantify
Monte Carlo draw uncertainty with the cohort fixed, not dataset, journey, or
model-fitting uncertainty.

Reviewed real-artifact lineage:

```text
unconditional_gaussian_residual_samples.npz
458a255f76334b281889df48bf8f549bd7b1f2fd124579b958b41d5353a8c81f

unconditional_gaussian_residual_samples_summary.json
8b17a16be7d6f76b5a3d69f3b03f82e28f8105a4a60f4fe9df6aac60e806f0f2

gaussian_transfer_frame_metrics.npz
270480551b7fc0cb8c097fee6ff875b3e847f958e9928e5b053a78795671fe2f

gaussian_transfer_sequence_metrics.csv
1f10578ced9d05bab8472cecc0e6c346f2907b9c368a7da572ff23a723bcc1bf

gaussian_planner_transfer_summary.json (with mandatory qualifier)
2dcda2dc24da9148a64ab742a815592e874e07e8f7fb007822d2f85f04cec2fa
```

Codex reproduced the delivered frame archive bit for bit. Claude regenerated
the A3 and accepted A2 ensembles independently, re-executed the planner, and
matched all decisions to machine precision. Generated samples and planner
outputs remain outside Git. BMW transfer validation remains optional and
separate. The final untouched-drive phase is still blocked by the absence of
independent outings; v0.16.1 does not satisfy that data gate.

The seed-repetition suggestion remains deferred. Repeated sampling seeds would
quantify Monte Carlo sensitivity; they would not create independent-drive or
dataset uncertainty.

## Completed v0.16.2 spatial-structure audit

The completed bounded phase is a read-only descriptive audit of contemporaneous
cross-station covariance and correlation in the accepted A2 and A3 residual
ensembles. It addresses the specific open interpretation issue from the final
v0.16.1 review: the A3 deviation result is length-dependent, while A3 differs
from A2 in both station-wise scale and cross-station coherence.

The audit consumes only the complete immutable A2 and A3 sample directories.
It does not refit or resample a model, execute the planner, change the accepted
v0.16/v0.16.1 decisions, or create an A4 arm. Pooled-frame and equal-sequence
summaries are both mandatory. No interval, hypothesis test, or pass/fail gate
is permitted because the result is post-hoc and generated-ensemble descriptive
evidence.

The exact approved contract is in
`docs/spatial_structure_audit_predeclaration.md`. The first Claude review found
useful interpretation risks but proposed a scalar effective-sample-size formula
that is not valid for the audit's covariance/correlation estimands and described
the sequence-wise difference as more uniform than the exact accepted artifacts
support. The amended contract instead records unequal temporal dependence
without inventing an effective sample size, treats reset/length effects as
confounded rather than irrelevant, limits `k/15` to direction consistency,
closes the statistic list, and strengthens the causal wording.

Claude computed the complete fixed statistic list on independently regenerated
ensembles during that review. This must remain disclosed: the later accepted-
artifact run is a lineage-controlled reproducibility execution, not a first
look. The focused re-review returned `GO`, and both optional wording suggestions
were adopted. The workflow implementation reproduces the disclosed pooled
off-diagonal correlations (`0.3830158618` A2 and `0.5335912782` A3), adjacent
correlations (`0.7030729727` and `0.9689050398`), 182/210 positive pair
differences, and positive off-diagonal/adjacent differences in all 15 sequences.
Claude's final read-only review regenerated A2 and A3 independently, reproduced
all 42,378 matrix values within a maximum absolute difference of `1.55e-15`,
reconciled every CSV and hash, confirmed 339 passing tests with two skips, and
returned `GO`. The result and implementation were merged through PR #11.

Accepted v0.16.2 artifact hashes:

```text
spatial_structure_matrices.npz
cf4eac162018dd65be26b89b472dbc6fe65aab3aacedd46c22b82583d4ab951f

spatial_structure_by_station_pair.csv
773573ba00c18648259f7e055afde40d8c0e72a574b4298821ed75ad5524527f

spatial_structure_by_separation.csv
38fb5c157ca9b8424a64e7eeee4bc31d482ec12e5e0f5b916c9e27ca29433ca3

spatial_structure_by_sequence.csv
2f4e40ffd5e5ec70ddf262269315a278f0cb1a19ab4f87b0ea90255bc8cee842

spatial_structure_audit_summary.json
e11b9a90bba4aba2af07eacb2ca1bae50231e1c0b5fa90509edca7742531479e
```

For the thesis write-up, the 90, 95, and 100 m separation rows contain only
three, two, and one station pairs, so their near-zero tail signs are not a
structural finding. The A2 adjacent correlation also differs more between
pooled and equal-sequence weighting (`0.7031` versus `0.7203`) than the
off-diagonal statistic does; this is consistent with the predeclared
finite-horizon mixture and is why both weightings must remain visible. The
adjacent A2/A3 contrast is the clearest single summary, but it must be reported
beside the separation profile.

This is the stopping point for current-data generated-ensemble diagnostics.
No A4 arm, refit, seed sweep, planner-parameter sweep, or additional post-hoc
statistic is authorized. The primary next evidence requires independent clean
outings under a separately reviewed, locked final-data protocol. Optional BMW-
planner transfer remains separate, requires confirmed interfaces and a new
predeclaration, and cannot replace independent-outing validation.

## Reading map

- `docs/modeling_plan.md`: phase gates, evidence, and data-acquisition limits.
- `docs/output_contracts.md`: exact output files and schemas.
- `docs/aiohmm.md`: model equations, evaluation, and limitations.
- `docs/architecture.md`: package ownership and dependency boundaries.
- `docs/commands.md`: complete CLI surface.
- `README.md`: chronological project overview and usage.
