# Spatial planner replication v0.19.31

The first recorded spatial pilot passed archive and lineage acceptance.
Its evidence concerns the distribution of incremental responses in the
fixed affine reference planner on one development recording. The extension
asks whether its model comparisons replicate over the other six original
development outings. The sealed design was set after the pilot outcome
and before any spatial scores on those six outings.

## Frozen inputs and forecast arms

Replay the original sealed development experiment and its registered
archive ancestry. For each of the seven leave one outing out folds,
verify the held archive, the frozen Gaussian and flow states, and the
training and validation partitions against the private run manifest.
Read the accepted prepared scenarios and aggregate pilot report for the
first fold. Construct the six other scenario sets using the same original
matched row policy. Each outing in this design is one recording.
Keep the complete feature rows and sequence boundaries. Record geometry,
complete feature, original speed eligible and common support counts
separately for every fold.

Reuse the v0.19.30 single snapshot scorer, planner, grid, arm definitions
and sampling seed. Use the zero disturbance, training only empirical,
diagonal Gaussian, full covariance Gaussian and unconditional flow arms.
The flow forecasts single profile marginals. Reuse the sampled profiles
across speed settings. The 128 draw prefix is a descriptive draw
sensitivity check. There is no tuning or fitting of a new model.

## Prespecified summaries

The primary endpoint is CRPS in metres for peak absolute planned lateral
change at original speed. Average eligible rows within each outing, then
give each outing equal weight. Report the seven outing macro mean and
the six outing macro mean excluding the already observed pilot. Report
paired differences against full Gaussian per outing and as equal outing
means. Keep empirical and zero disturbance comparators in the table.

The first curvature change, interval coverage and width, 0.3 m
exceedance and Brier score remain secondary. The common support
sensitivity uses the same speed offsets as the pilot. Each macro
sensitivity requires nonempty common support in every outing in that
group. Quantiles in the macro summaries are means of within outing
quantiles. They are distinct from quantiles of a pooled sample.
Time block intervals describe variability within a recording. The
development folds share training data and support descriptive
cross outing comparisons.

An incomplete primary fold blocks publication of the complete
replication result. Require matching pilot scores before proceeding to
any of the other six outings. Compare counts and structures exactly.
Compare floating point score values with relative tolerance 1e-9 and
absolute tolerance 1e-12. These tolerances apply only to pilot replay
parity. Each fold is checkpointed with aggregate results and lineage.
The final ZIP is published only after all seven folds complete and the
inputs are rechecked.

## Interpretation

The original residual is sensor EDP relative to the RLMB fusion reference.
The study compares distributions of planned responses under one fixed
simulator and development population. Independent reference accuracy,
temporal propagation, absolute safety and the benefit of choosing
planner parameters based on the residual models require separate
evidence. Preserve the independent reservations and prospective drives.
