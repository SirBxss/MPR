# Short temporal planner replication v0.19.33

This implements the prospective replication recorded in the private pilot
assessment before temporal outcomes from the other development outings were
examined. PR 56 is merged and its owner pilot is accepted. The private
assessment records comparative findings and the scientific interpretation.
Replication retains every baseline, including zero disturbance. Private
measurements, comparisons and pins belong in the sealed packet and accepted
result assessments.

## Question and fixed experiment

The hypothesis is that preserving the frozen one state AR's temporal coupling
improves its planner command sequence distribution relative to a control with
the identical finite spatial profile ensembles and permuted draw indices at
each later frame. The stationary scalar AR contrast is secondary. Other arm
comparisons also reflect fitted marginal distributions and their calibration.

Reuse the exact v0.19.32 affine planner, prediction step, recorded interval
propagation, original resets, terminal rule, seven arms, sample count, seeds
and prefix construction. See [pilot protocol](temporal_planner_pilot_v01932.md)
for the equations, coordinate conventions and simulator assumptions. None of
those rules is tuned from the accepted pilot. The pilot selection field in
the embedded scoring protocol identifies its inherited checkpoint; the outer
replication protocol specifies the full development fold set.

The target remains signed sensor EDP minus RLMB fusion pseudo residuals in
metres at the original 21 stations. Speed and conditions remain the original
accepted features. Restore the original conditional Gaussian, stationary AR
and one state AR states for every original development fold through the native
evidence validators. Build each empirical pool from that fold's training
outings in the original order. No validation residual enters a sampler.

Sample all original complete rows with their original offsets. Score only
whole original sequences admitted by the pilot rules. Preflight checks every
fold's row identities, clock intervals, support census, saved state pins,
training population and native padded sampling limit before any sampling.
An empty primary fold blocks the complete experiment. The secondary lateral
state score requires at least three frames, with its assessed count explicit.

## Parity and scoring

Reproduce the accepted pilot first. Its complete sequence census must match
exactly. Every stored main sequence score and aggregate must match, as must
every stored prefix aggregate. Score parity uses relative tolerance 1e-9 and
absolute tolerance 1e-12; counts and structural types remain exact. A parity
failure preserves that fold's evidence and blocks sampling the other folds.
Preflight verifies lineage and support without claiming numerical parity.

The primary metric is the full pairwise finite ensemble energy score of the
incremental commanded lateral acceleration sequence divided by sqrt(length).
Its units are m/s². Average sequences equally within an outing, then average
outings equally. Keep separate summaries for all original outings and those
beyond the pilot. Report all seven arms, including zero disturbance, plus
the same metrics at the prefix draw count. The prefix controls are rebuilt
inside the prefix as in the pilot. Retain main and prefix per sequence scores.

The primary descriptive replication rule requires both a negative equal
outing mean one state AR minus permuted energy on the six new outings and
negative individual differences on at least four of those six. Zero is a tie
and does not count as negative. Report per outing signs, mean, minimum and
maximum. This rule is a prospective development decision, without a declared
minimum practical improvement or a significance claim. The stationary AR rule
is secondary and does not replace a failed primary comparison.

## Descriptive diagnostics

Retain the pilot interpretation note's within outing block calculation.
Subtract the earliest start across all original sequences, including excluded
singletons, from each eligible sequence start using exact integer epochs.
Assign its intact sequence to the resulting 30 s source time bin. Sort
nonempty eligible bins and resample the same number of bins with replacement
1,000 times using NumPy default_rng seed 193002. Carry all sequences in each
selected bin, including repeated bins, and average the pooled sequences
equally. This preserves sequence weighting when bin sizes differ. Report
2.5 and 97.5 percentile bounds only with at least five nonempty bins.

Report negative, positive and tied sequence counts and contrast groups for
2, 3 to 5, 6 to 9 and at least 10 frames. The final group accommodates the
original cohort's longer sequences without modifying its support. Empty
groups have null estimates. The block interval is descriptive within an
outing conditional on frozen fitted states and finite draws. Overlapping
training folds and development reuse preclude an independent final test
interpretation. Do not pool those intervals into an independence claim.

For an outing with no secondary lateral support, retain its command results
and mark the affected macro lateral metric unavailable. List the missing
outings instead of changing their weight or substituting zero.

## Operation and scientific limits

The sealed manifest pins all accepted original experiments, state archives,
spatial replication, temporal pilot source, pilot manifest, and every fold's
support and model identities. Replay the complete native temporal evidence
once and restore all selected fold states from those validated archives.
No archive only fallback is allowed after native validation fails.

The private helper defaults to a fresh sibling of the packet directory.
Existing outputs, partial archives, aliases of inputs and locations inside
prior evidence are rejected. Preflight writes nothing and performs no model
sampling or planner scoring. The full run preserves each fold's main and
prefix scores, complete sequence census and diagnostics. It rechecks inputs
and the source after each fold and before aggregation. A checksummed ZIP is
published through an exclusive partial file, fsync and a nonoverwriting link.
Failures retain existing evidence and a stage report.

Independent source, protocol, manifest and helper review, CI on the reviewed
head and owner merge precede the owner run. Read the private packet README
for concrete commands and archive locations. Preserve earlier attempts.

This stage tests short recorded support in an exogenous affine incremental
simulator. It does not establish physical lane truth, perception feedback,
online feature availability, long rollouts or better planner tuning. Finite
ensemble bias need not cancel between dependent and permuted forecasts, and
the prefix check is a sensitivity diagnostic. After accepting the replication,
choose candidates for a separate planner parameter selection and validation
study with a fixed objective and honest holdout. Keep independent final
reservations and additional recordings in their existing prospective roles.
Target funnels remain a separate future extension.
