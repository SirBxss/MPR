# v0.16.1 unconditional-Gaussian planner-transfer predeclaration

Status: independently reviewed and amended on 2026-08-27, after the accepted
v0.16 result and before any v0.16.1 implementation or real output. The four
primary metrics, the p95 level, and both hypothesis directions were selected
from post-hoc descriptive quantities measured on the accepted A1/A2 result and
recorded in `docs/current_status.md`. v0.16.1 is therefore a confirmatory test
of a v0.16-generated hypothesis, not an independent discovery. What makes it a
genuine test is that the A3 ensemble did not yet exist and was not inspected
when these choices were fixed. Its result must be reported regardless of
direction.

## Scientific question

Does the actual v0.14 all-clean unconditional Gaussian produce the same
directional planner trade as the v0.16 marginal-matched time-shuffled null when
each is compared with the frozen v0.15.4 autoregressive model?

This is a model-to-model transfer question. A3 differs from A2 in its marginal
distribution, including cross-station covariance, and its temporal structure,
so A3 minus A2 cannot identify a temporal effect by itself. The accepted
A2-minus-A1 comparison in v0.16 remains the only causal temporal-order result
because A1 and A2 contain the exact same H100 profiles in different orders.

## Fixed arms and immutable sources

- A1 `time_shuffled_ar`: the accepted v0.16 marginal-matched temporal null.
- A2 `frozen_ar`: the accepted free-running v0.15.4 AR arm.
- A3 `unconditional_gaussian`: independent-frame draws from the v0.14
  unconditional Gaussian's descriptive fit on all four clean development
  groups.

A0 is not rerun because it does not answer the transfer question. A1 and A2
are not rerun; their accepted frame and sequence metrics are immutable inputs.
The v0.14 model is not refitted, and no covariance, regularization,
standardizer, planner parameter, scenario, or model hyperparameter is changed.

The A3 source must be the `unconditional_gaussian` member of
`gaussian_grouped_models.json`, specifically its
`descriptive_all_clean_fit`. That payload is development-only and explicitly
not an untouched final model. The complete seven-file v0.14 directory must be
validated against the exact hash-reconciled v0.13.1 dataset, its four clean
groups, its stored folds, and all output hashes before sampling. The all-clean
fit is used because the frozen AR planner-development model is also an
all-clean descriptive fit; fold-specific Gaussian models would describe an
out-of-fold evaluation protocol rather than one planner-facing model.

The accepted v0.16 inputs are fixed to:

```text
reference_planner_scenarios.npz
615f6c7d5ef6b6b9c0770c65b58bb23c573a838579aa4fdf3f25c141a15c0591

sampled_residual_sequences.npz used by A1/A2
5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa

reference_planner_frame_metrics.npz
9d2b6a724a648839756597d40497cf6a2fc9b55a4422230fcddb317fe26a2a9f

reference_planner_sequence_metrics.csv
3f9ea8db4e4e2817c450dd82ebe8a52042a12e6aa76fbb0d4b7b31da4d96a1df

reference_planner_sensitivity_summary.json
38a04f655f9c9f6ec0e89d817534e8e289e0571787c229fa630d37406bcc8154
```

The workflow must fail before output if any file set, schema, identity,
parameter, count, or SHA-256 lineage differs.

The sampler must also load the exact frozen v0.15.4 development model used to
generate A1/A2:

```text
development_residual_model.json
976259c05eb67e600b017a81bed77846a424b5687d51f4a04168431bfc7b6bd3
```

It must verify that
`models.unconditional_gaussian.descriptive_all_clean_fit.standardizer` in
`gaussian_grouped_models.json` has `residual_mean_m`, `residual_scale_m`, and
`stations_m` exactly equal to the corresponding frozen v0.15.4 standardizer
arrays. Equality is element-for-element after each validated JSON payload is
converted to float64; tolerance-based acceptance is forbidden. The maximum
absolute discrepancy for each array is recorded and the sampler fails before
writing output if any discrepancy is nonzero.

The sampler will consume the complete v0.13.1 dataset directory, the complete
v0.14 Gaussian directory, the frozen v0.15.4 development-model JSON, the
complete accepted A2 residual-sample directory, and the accepted v0.16 scenario
NPZ. The transfer workflow will consume the resulting A3 sample directory, the
same scenario NPZ, and the complete accepted v0.16 sensitivity directory. This
keeps model validation, sampling, and planner comparison separate and gives
every produced file one unambiguous lineage.

## A3 sampling contract

The v0.14 model remains in its stored standardized residual space. Samples are
converted to physical metres using the exact all-clean v0.14 residual mean and
scale. Conditions are retained only to reproduce the accepted `[B,T]` shape,
sequence identities, and padding; the unconditional model does not consume
their values.

| Item | Fixed value |
|---|---:|
| sample count | 128 |
| Gaussian sampling seed | 20260828 |
| active sequences | 15 |
| active frames | 4,083 |
| stations | `0, 5, ..., 100 m` |
| residual unit | m |
| temporal dependency order | 0 |

Every active A3 frame is an independent draw from one 21-dimensional Gaussian.
Spatial cross-station covariance is preserved. Sequence boundaries do not
create state because A3 has no temporal state. Padding remains exactly zero.
The output must state that A3 uses neither common random numbers nor paired
residual profiles with A1/A2.

Before any planner execution, the A3 sampler summary must record, at every
station, the active-frame A3 mean and population standard deviation, the
corresponding accepted A2 mean and population standard deviation, the
A3-minus-A2 mean difference, and the A3/A2 standard-deviation ratio. These are
mandatory descriptive diagnostics and do not gate execution; no similarity
threshold is predeclared. A mean ratio is deliberately omitted because division
by an A2 mean near zero is unstable. The diagnostic exists so a marginal-
location or marginal-scale explanation of A3-minus-A2 can be assessed from the
record.

## Planner execution

Only A3 is newly executed. It uses the exact accepted scenario paths,
timestamps, speeds, sequence resets, propagation equations, first-frame
interval convention, 25-step Riccati solution, planner configuration, metric
definitions, and geometry validation from v0.16. The accepted A1/A2 frame
arrays and sequence rows are loaded read-only for comparison.

The run is invalid if any active planner metric is non-finite, padding is not
zero, sequence identity differs, a numerical solve fails, or the planner
configuration differs from the accepted v0.16 summary.

## Predeclared primary metrics

For each arm, draw, and sequence, compute:

1. p95 absolute curvature rate in `1/(m s)`;
2. p95 absolute lateral jerk in `m/s^3`;
3. mean absolute lateral error in `m`; and
4. time-integrated absolute lateral error in `m s`.

The p95 uses `numpy.quantile(values, 0.95, method="linear")`. A sequence
contributes to a primary p95 macro only if it has at least 20 active frames.
Sequences below this threshold are excluded from both p95 primary macros and
listed by ID and frame count in the summary. The p95 macros over all 15
sequences are mandatory robustness variants. This threshold is fixed before A3
is generated and is not derived from an A3 value. Mean and integrated absolute
lateral error continue to use all 15 sequences because neither is a quantile.

Each draw-level macro value is the arithmetic mean of its eligible sequence
values, so aggregation remains equal-sequence rather than pooled-frame.
Per-sequence and pooled-frame summaries are also mandatory. The two p95 metrics
avoid the saturation of the v0.16 any-envelope indicator; mean absolute lateral
error is the scale-free companion to the length-dependent integral.

Maximum lateral error, final lateral error, the 0.3 m exceedance fraction,
constraint-violation fraction, objective, and individual envelope trip rates
remain secondary descriptions. None may change the v0.16.1 decision.

## Comparison and Monte Carlo interval

The primary estimand is A3 minus A2 for each of the four primary metrics. A3
and A2 are independent Monte Carlo ensembles, not paired residual draws.
Therefore v0.16's paired-draw percentile rule is not reused.

For each metric, report the difference between the two 128-draw macro means
and an independent two-sample bootstrap interval:

| Item | Fixed value |
|---|---:|
| bootstrap replicates | 20,000 |
| bootstrap seed | 20260829 |
| interval | 2.5/97.5 percentiles |
| quantile method | linear |

For every replicate, sample 128 A3 draw indices with replacement and then 128
A2 draw indices with replacement from one `numpy.random.default_rng` stream;
subtract the resampled A2 mean from the resampled A3 mean. This interval
quantifies only Monte Carlo uncertainty in the two generated ensembles. It is
not a dataset confidence interval, a journey-level interval, or an uncertainty
estimate for model fitting.

For each primary metric, additionally report the number of eligible sequences
whose per-sequence A3-minus-A2 mean difference has the hypothesised sign, as
`k/N`. The p95 metrics use the >=20-frame eligible set; the deviation metrics
use all 15 sequences. This count is reported alongside every bootstrap interval
and is mandatory, but it is a cohort-consistency description rather than a
hypothesis test and does not change the pass/fail rule.

The following pre-run minimum-detectable-difference estimates come from the
accepted A1/A2 ensembles and use A1 as an approximate independent-frame proxy
for the still-unseen A3 variance. They are context, not guarantees or gates:

| Metric | Estimated absolute MDE | As percent of A2 level |
|---|---:|---:|
| p95 absolute curvature rate | 0.0130 `1/(m s)` | 6.2% |
| p95 absolute lateral jerk | 5.431 `m/s^3` | 7.1% |
| mean absolute lateral error | 0.00212 m | 3.0% |
| integrated absolute lateral error | 0.03405 `m s` | 2.3% |

A2 is immutable at 128 draws, so its variance imposes an irreducible precision
floor. Increasing only A3 to 512 draws would reduce the deviation-metric
intervals by at most about 30% while quadrupling A3 execution. This fixes 128
A3 draws as the proportionate choice. Independent A3 sampling also forfeits the
strong A1/A2 cross-draw correlation for deviation metrics; an indeterminate
deviation result therefore means the model-to-model difference is unresolved
under this unpaired design, not that the models are equivalent.

A3-minus-A1 levels and ratios are secondary and descriptive. A1 is the exact
AR-marginal temporal null, whereas A3 changes marginals and removes conditioning
as well as temporal dependence. No A3-minus-A1 difference has a single causal
interpretation.

## Directional hypotheses and decision rule

The v0.16 result motivates, but does not prove, the following fixed directions:

- H-smoothness: A3 has higher p95 absolute curvature rate and higher p95
  absolute lateral jerk than A2;
- H-deviation: A3 has lower mean absolute lateral error and lower integrated
  absolute lateral error than A2.

H-smoothness is supported only if both bootstrap intervals are strictly above
zero. H-deviation is supported only if both intervals are strictly below zero.
The full planner-observable trade is supported only if both hypothesis families
pass. H-smoothness is principally a manipulation check because A3 is temporally
independent; H-deviation is the informative transfer test. The two smoothness
metrics were strongly correlated in accepted A1/A2 draws, while the two
deviation metrics were only moderately correlated, so the conjunction is more
stringent for H-deviation.

If one family passes, report either `partial support: smoothness family only`
or `partial support: deviation family only`; the outcomes must not be collapsed
into one unnamed category. If neither passes or a direction reverses, report
that the proposed transfer is unsupported. An interval containing zero is
indeterminate. Every outcome is retained.

## Permitted interpretation

If the full rule passes, v0.16.1 may state that the actual v0.14 unconditional
Gaussian exhibits the same directional deviation-versus-smoothness trade as
the v0.16 time-shuffled null for this fixed reference planner and within this
one outing. Together with v0.16, this would make the temporal-model difference
planner-observable while keeping the causal temporal claim anchored to A2
minus A1.

It may additionally state that, for this fixed reference planner and within
this one outing, a model preferred on marginal and distributional metrics and a
model preferred on temporal metrics produce materially different planner-facing
behaviour, so distributional model ranking does not by itself determine
planner-facing behaviour. Both are in-sample all-clean descriptive fits; this
statement has no generalization, out-of-fold, or final-model-selection
implication.

The extension may not claim that A3-minus-A2 is caused only by temporal
structure, that the Gaussian is worse or the AR is better overall, planner
benefit, comfort, safety, BMW planner behavior, production readiness, physical
ground truth, global replay, final model selection, or independent-journey
generalization. Absolute A3/A1 derivative magnitudes remain artifacts of an
unconstrained reference planner without an actuator model and are meaningful
only as comparisons under the identical protocol.

## Output contract to implement after review

The Gaussian sampler will write exactly:

```text
unconditional_gaussian_residual_samples.npz
unconditional_gaussian_residual_samples_summary.json
```

The A3 planner-transfer workflow will write exactly:

```text
gaussian_transfer_frame_metrics.npz
gaussian_transfer_sequence_metrics.csv
gaussian_planner_transfer_summary.json
```

Both summaries must record complete input/output hashes, seeds, counts,
parameters, aggregation rules, hypotheses, decisions, and all prohibited-claim
flags. The sampler summary must include the standardizer-equality audit and A3
versus A2 marginal diagnostics. The transfer summary must include the short-
sequence exclusions, both p95 macro variants, and per-metric `k/N` directional
agreement. Alongside exact accepted hashes, it must record reproducibility
content invariants: array shapes and dtypes, `active_frame_count = 4083`,
`shuffled_frame_positions_changed = 520675`, and A0 macro constraint-violation
fraction `0.259355`. These invariants do not weaken the exact hash gate.
Generated samples and planner outputs remain outside Git.

Claude's independent pre-execution review returned `changes required`; all five
blocking corrections and the associated reporting clarifications were accepted
in this amendment. Implementation is authorized only after this amended
contract is committed. Real A3 execution remains forbidden until the
implementation passes its complete synthetic verification suite.
