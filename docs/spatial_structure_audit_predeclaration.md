# v0.16.2 A2/A3 cross-station structure audit predeclaration

Status: amended on 2026-08-31 after an independent `AMEND` review and awaiting
focused re-review, after the accepted v0.16.1 result and before implementation
or generation of a v0.16.2 output.

This is a post-hoc descriptive audit. Claude's final v0.16.1 review already
reported that the pooled mean off-diagonal station correlation was about
`0.383` for A2 and `0.534` for A3. Those values motivated this audit and are
not unseen confirmatory outcomes. Every result will be retained regardless of
direction.

After this statistic list was fixed, the independent reviewer computed the
complete audit on independently regenerated A2 and A3 ensembles while deciding
whether the phase was worth performing. The reviewer therefore knows the full
result before implementation. The accepted-artifact v0.16.2 run is a lineage-
controlled reproducibility execution rather than a first look, and its summary
must record this disclosure. No statistic was added or removed in response to
the reviewer's computed values.

## Scientific question

How do the accepted A2 frozen-AR and A3 unconditional-Gaussian generated
ensembles differ in their contemporaneous cross-station covariance and
correlation structure, and is the direction of the correlation difference
consistent across station separations and planning sequences?

The audit documents one input difference that the v0.16.1 record leaves
unquantified. The A3 sampler already reports station-wise mean and standard
deviation, but not the dependence between stations. The final planner review
found that the A3-minus-A2 deviation contrast is length-dependent and named a
near-field scale difference and a cross-station-coherence difference as two
plausible contributors. This audit measures the second of those. It narrows
what is undescribed; it does not close the causal question, which remains open.

This audit can quantify those two ensembles' spatial structure. It cannot
identify whether marginal scale or cross-station coherence caused the planner
result. A causal decomposition would require a separately predeclared new arm;
no such arm is authorized here.

## Fixed immutable inputs

The workflow consumes only the complete accepted A2 and A3 residual-sample
directories. It does not load raw data, refit either model, resample residuals,
or execute the planner.

Accepted A2 files:

```text
sampled_residual_sequences.npz
5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa

sampled_residual_sequences_summary.json
6038dde59c9db9b715ce4966c1b7f5d239133664856efd4cc4acf6e8e18acb4b
```

Accepted A3 files:

```text
unconditional_gaussian_residual_samples.npz
458a255f76334b281889df48bf8f549bd7b1f2fd124579b958b41d5353a8c81f

unconditional_gaussian_residual_samples_summary.json
8b17a16be7d6f76b5a3d69f3b03f82e28f8105a4a60f4fe9df6aac60e806f0f2
```

Each directory must contain exactly its NPZ and summary. The workflow fails
before creating its output directory if a filename, SHA-256 value, summary
identity, stored sample hash, or required authorization flag differs.

The two NPZ archives must have exactly these arrays:

```text
residual_samples_m  float64 [128, 15, 924, 21]
lengths             integer [15]
stations_m          float64 [21]
sequence_ids        string  [15]
feature_names       string  [6]
```

`lengths`, `stations_m`, `sequence_ids`, and `feature_names` must match
element-for-element across arms. The station grid must be exactly
`0, 5, ..., 100 m`; the feature order must be BMW condition schema v1. The
sample count is 128, the sequence count is 15, and the sum of active sequence
lengths is 4,083. Active residuals must be finite and all padded residuals
must be exactly zero.

The summaries must retain these scientific identities:

- A2 is the complete v0.15.4 free-running frozen-AR sample with seed
  `20260826`, generated history enabled, independent-frame sampling disabled,
  planner execution disabled, and final selection disabled.
- A3 is the complete v0.16.1 unconditional-Gaussian sample with seed
  `20260828`, temporal dependency order zero, independent active frames,
  preserved spatial covariance, planner execution disabled, and final
  selection disabled.
- Both arms use physical signed H100 residuals in metres and have exact
  v0.14/v0.15.4 residual-standardizer equality as already enforced by the A3
  sampler.

## Fixed calculations

Padding is excluded. For one arm, concatenate every active vector from all
128 draws and all 15 sequences into `X[N,21]`, where
`N = 128 * 4,083 = 522,624` generated frame profiles.

`N` is the exact profile count in each stored finite ensemble, not an
inferential sample size. A3 profiles are temporally independent by construction.
A2 profiles are serially dependent within each sequence and reset once at each
sequence boundary, so the two arms do not have equal estimation precision for
their underlying generators despite equal nominal profile counts. No scalar
effective sample size is reported: the common stationary scalar-AR formula for
a sample mean is not valid for these 21-dimensional covariance and correlation
statistics under condition-dependent means, cross-station dependence, resets,
and unequal sequence lengths. The reported moments remain exact descriptions
of the two stored generated ensembles.

For station `j`, calculate the population mean and covariance:

```text
mu[j] = mean_n X[n,j]
C[j,k] = mean_n ((X[n,j] - mu[j]) * (X[n,k] - mu[k]))
R[j,k] = C[j,k] / sqrt(C[j,j] * C[k,k])
```

All arithmetic uses float64. Every station variance must be finite and strictly
positive. The correlation diagonal is required to equal one within a fixed
absolute tolerance of `1e-12`; every correlation must be finite and within
`[-1-1e-12, 1+1e-12]` before clipping only round-off excursions to `[-1,1]`.

The same population calculation is repeated separately for each sequence by
pooling that sequence's 128 draws and active frames. No sequence is dropped;
even the three-frame sequence contributes 384 generated profiles.

An A2 per-sequence result describes that finite-horizon generated ensemble as
presented to the planner; it is not an estimate of one stationary spatial
parameter. A2 starts every sequence from its fitted marginal reset prior and
then evolves autoregressively under that sequence's conditions. Sequence length
therefore changes the mixture of reset, transient, and later free-running
profiles, while the condition histories also differ between sequences. Any
association between an A2 per-sequence correlation and sequence length is
structurally confounded by those factors. It may not be interpreted as physical
spatial heterogeneity across the outing or as a causal explanation of the
v0.16.1 length-dependent planner result. It is not declared irrelevant to that
planner result either, because the planner consumed the same finite-horizon
sequences. A3 has no temporal state or dynamic reset transient, but its
per-sequence values still describe finite Monte Carlo subsets. No per-sequence
effective sample size is claimed for either arm.

For each arm and for A3 minus A2, report:

1. the complete 21-by-21 covariance matrix;
2. the complete 21-by-21 correlation matrix;
3. the arithmetic mean correlation over the 210 unordered off-diagonal
   station pairs;
4. the arithmetic mean over the 20 adjacent-station correlations;
5. mean correlation at each station separation in
   `5, 10, ..., 100 m`, using every unordered pair at that separation;
6. the number and fraction of the 210 pairs for which A3 correlation exceeds
   A2 correlation; and
7. per-sequence mean off-diagonal and adjacent-station correlations, their
   A3-minus-A2 differences, and the descriptive `k/15` count with a positive
   difference.

The 210 station pairs are functions of one 21-by-21 correlation matrix per arm
and are strongly mutually dependent. The pair count is therefore one
descriptive tally, not 210 independent comparisons. It must always be reported
beside the complete separation profile and never as a standalone proportion.
Likewise, a positive per-sequence `k/15` count describes consistency of
direction only; it does not establish uniform effect magnitude or absence of a
relationship with sequence length.

The pooled result weights generated active frames equally. The per-sequence
macro is the arithmetic mean of the 15 per-sequence statistics and weights
sequences equally. Both are mandatory because the v0.16.1 deviation result is
length-dependent.

No p-value, confidence interval, bootstrap interval, equivalence margin, or
pass/fail threshold is computed. Treating the 522,624 generated profiles as
independent data would be pseudo-replication, while a Monte Carlo interval
would quantify only generator noise and could be narrowed by drawing more
samples. This audit is descriptive by design.

## Outputs

The command writes exactly five files to a new empty output directory:

```text
spatial_structure_matrices.npz
spatial_structure_by_station_pair.csv
spatial_structure_by_separation.csv
spatial_structure_by_sequence.csv
spatial_structure_audit_summary.json
```

`spatial_structure_matrices.npz` contains fixed arm order
`[frozen_ar, unconditional_gaussian]`, the station grid, sequence identities
and lengths, pooled means/covariances/correlations, and per-sequence covariance
and correlation matrices. Numeric arrays use float64; lengths use int64; names
use NumPy string dtypes; object arrays and pickle are forbidden.

`spatial_structure_by_station_pair.csv` contains one row for every unordered
station pair in lexicographic `(station_i, station_j)` order, including
separation, A2/A3 covariance and correlation, and A3-minus-A2 differences.

`spatial_structure_by_separation.csv` contains one row for each 5 m separation
and reports pair count plus A2, A3, and difference means for covariance and
correlation.

`spatial_structure_by_sequence.csv` contains one row per accepted sequence in
stored order and reports active-frame count, each arm's mean off-diagonal and
adjacent-station correlation, and both A3-minus-A2 differences.

`spatial_structure_audit_summary.json` records exact input and output hashes,
array schemas, counts, formula and weighting identities, pooled and equal-
sequence results, pair and sequence directional counts, the unequal temporal-
dependence structure of the arms, the reviewer's pre-implementation calculation
disclosure, the already known post-hoc status, and all claim limitations.
Strict JSON forbids NaN and infinity.

No figure is part of the scientific contract. Publication figures should be a
separate read-only reporting layer after this numeric artifact is independently
reviewed, so plot formatting cannot change or obscure the audited values.

## Interpretation limits

The audit may state only that, in these exact accepted generated ensembles,
A3 has higher, lower, or similar contemporaneous cross-station covariance or
correlation than A2 under the reported pooled and equal-sequence summaries.
It may describe how that difference varies with station separation and across
the 15 fixed sequences.

The separation profile may be described as generally decaying toward zero if
the complete values support that wording, but it may not be called strictly
monotonic unless every consecutive fixed separation value satisfies that exact
property. A positive difference in all 15 sequences may be called uniform in
direction only. No approximate-uniformity threshold for magnitude was fixed,
so the audit may not claim that the difference is constant across sequences or
does not vary with sequence length.

It may not state that:

- cross-station coherence caused the v0.16.1 deviation reversals;
- marginal scale and spatial coherence have been causally separated;
- A2 or A3 is the generally better residual model;
- any effect generalizes to another outing, dataset, planner, or vehicle;
- the MPR reference planner represents BMW planner behavior;
- planner benefit, comfort, safety, production readiness, or physical ground
  truth has been evaluated; or
- final model selection is authorized.

All intervals and model/planner conclusions from v0.16 and v0.16.1 remain
unchanged. The existing mandatory length-dependence qualifier remains attached
to the deviation result.

## Stop rule and next evidence gate

v0.16.2 is the final planned diagnostic using the current generated ensembles.
It authorizes no A4 arm, model refit, planner-parameter sweep, additional seed
sweep, or new current-outing selection exercise.

The statistic list in *Fixed calculations* is closed. Any additional cross-
station statistic computed on these ensembles, including a partial correlation,
eigenvalue spectrum, factor structure, or conditional-independence measure,
requires a new predeclaration reviewed before computation. It may not be added
to a v0.16.2 rerun after this output has been inspected.

After independent review of the real v0.16.2 output, the next substantive
scientific evidence requires either:

1. additional independent clean outings under a separately locked final-data
   protocol; or
2. an optional BMW-planner transfer study using exact confirmed production
   interfaces and a new predeclaration.

Neither is silently substituted by more Monte Carlo draws or more post-hoc
analysis of the present outing.
