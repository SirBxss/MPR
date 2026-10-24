# Matched stationary AR memory control, v0.19.17

Date: 2026-10-23. This candidate follows merged PR #42 (`0712352`, reviewed
owner head `9d42975`, tree `a87bfb33`). Its owner-authorized Gaussian development
operation completed and its returned evidence passed independent raw-free
archive/source/authorization/lineage, exact row/reset and saved-state/score replay.
Private counts, identities, hashes, scores and plots stay in the private review
packet. The first Gaussian result is immutable; do not rerun or replace it.

## Question and bounded scientific choice

The next question is whether short-window temporal persistence improves generated
sequence distributions when the single-frame distribution is held fixed. This
is a deliberately small new control, not a reproduction of the historical
station-wise conditional AR/AIOHMM. That implementation also changes regression,
reset priors and covariance regularization, so its old scores cannot isolate
memory or be pooled into the current matched table.

For each original whole-outing fold, reuse its already fitted conditional
Gaussian state, including mean function, training transforms and spatial
covariance. Let `e_t = standardized_y_t - mean(x_t)` and `Sigma = L L^T` be that
frozen state. At every original reset:

```text
e_0 ~ Normal(0, Sigma)
e_t = phi * e_(t-1) + sqrt(1-phi^2) * L * epsilon_t
y_t = inverse_training_transform(mean(x_t) + e_t)
epsilon_t ~ independent Normal(0, I)
```

One shared scalar phi is fitted using only retained adjacent pairs in the fold's
training outings. No transition crosses a sequence or recording boundary.
The fixed bound is `abs(phi) <= 0.99`, inherited prospectively from the earlier
development ceiling, not selected by any current AR validation result. It is
per retained frame at the admitted source cadence, not a per-second parameter.
Binding at the cap is reported; it does not permit increasing the cap.

The reset covariance and innovation scaling imply the exact same Gaussian
marginal at every frame for any supplied feature trajectory. At phi zero, both
sampling and density reproduce the accepted conditional Gaussian bitwise. All
singletons remain and are exact Gaussian resets. No bridge, interpolation,
downsampling or new feature/reference semantics are introduced.

## One-dimensional fitting and interpretation

Whiten training deviations with the frozen spatial Cholesky factor. Over valid
pairs, define `xx = sum(previous^2)`, `yy = sum(current^2)`,
`xy = sum(previous*current)` and `df = 21 * transition_count`.
The transition negative log-likelihood, up to constants, is

```text
0.5 * [df * log(1-phi^2)
       + (yy - 2*phi*xy + phi^2*xx)/(1-phi^2)]
```

Its derivative numerator is
`df*phi^3 - xy*phi^2 + (xx+yy-df)*phi - xy`. Evaluate all real stationary roots
inside the bound, both endpoints and zero, then choose the minimum objective.
The sufficient statistics, valid training pair count, chosen coefficient and
cap-binding flag are persisted. No mean, covariance or standardizer is refitted.
No hyperparameter, restart, validation selection or early stopping is added.

The primary descriptive evidence is paired held-out-outing differences in
normalized sequence energy and retained-pair lag-correlation error, with all
signs and the equal-outing macro reported. No automatic winner, p-value,
frame-IID confidence interval or model-selection gate follows. This is a
result-informed development extension; the prior development scores are exposed.

Frame energy, marginal CRPS, intervals and tail events remain in the common
score table, but finite Monte Carlo differences cannot be claimed as marginal
improvement because the frame distributions are identical by construction.
Analytic marginal mean RMSE and single-frame NLL are inherited exactly. A
separate physical observed-history chain NLL is reported; it evaluates the joint
sequence factorization using observed past pseudo-residuals offline. Free-running
sampling uses only generated past deviations and current features, never true
held-out residual history. Observed pseudo-residuals requiring RLMB are not
automatically available ADAS prediction-time inputs.

These data support only the originally retained short histories. Do not infer
long-horizon, planner, independent physical-ground-truth or final-test results.
RLMB/common-dependency, owner-declared identity, strict causal speed, confidence
width and producer-interface qualifications remain. A scalar stationary process
does not establish that real error dynamics are stationary or one-dimensional.

## Evidence, preparation and authorization

`io.development_temporal` has a closed externally pinned request containing:

```text
contract_revision, original_experiment_directory,
expected_original_experiment_sha256, gaussian_result_zip,
expected_gaussian_result_sha256, experiment_directory,
training_directory, authorization, result_zip
```

It strictly replays the original v0.19.16 experiment and all prior registry
descendants. The old Gaussian return is bounded to 64 MiB and 128 ZIP members,
with exact names, CRCs, SHA entries, authorization, states, folds, seeds,
training/validation support and aggregate replay. The producer tuple must be
the reviewed merged PR #42 tuple; same-release source is not self-authorizing.
No final, legacy, excluded or alternative rows can enter through this adapter.

Preparation fits nothing and writes only `request.json`, then completion marker
`experiment.json`. The marker binds the old experiment, Gaussian return, exact
rows/folds, fixed protocol and private scope. Cached changes are reconstructed
and refused, including repinned protocol/row/fold edits. The engineering flags
remain false. A separate authorization purpose
`fixed_stationary_ar_control_development_only` requires four literal true flags:

```text
explicit_development_stationary_ar_fit
independent_protocol_review_and_ci_accepted
final_outings_remain_unexposed
fixed_protocol_and_preserve_failed_attempts
```

The old Gaussian authorization grants no AR fit. Source/protocol/helper review,
exact-head Python 3.10/3.12/frozen-reader CI, owner merge and explicit owner
adoption precede any real phi fit. The private packet supplies the owner commands
and exact pins. Accepted Gaussian evidence may be copied byte-identically into a
new ignored import location without moving, overwriting or re-registering it.

## Attempt lifecycle and immutable outputs

The new consumer shares the existing registry writer lock and checks source,
imports, tree, runtime, input bytes and file sets before fitting and at postflight.
Output paths are private, new and separate from all protected inputs. Ancestor
checks include request, authorization and row-manifest partial markers. The
result ZIP's parent must exist before an attempt begins; prior partial ZIPs stop.

Before output creation or fitting, an exclusive durable claim is appended under
`outputs/fit_ledgers/private/matched_temporal_v01917`. Its key binds the original
experiment, accepted Gaussian return and full protocol, excluding request/output
locator names. A renamed request cannot repeat the same design invisibly. Claims
are never rewritten or deleted; terminal outcome is in the linked receipt and
result ZIP. Claims themselves are watched for drift. A failure creating the
attempt directory after a claim still leaves a trace and needs recovery review.

Writable started attempts preserve authorization, claim, the original Gaussian
ZIP and partial model/score files. Caught fit failures and one interrupt stop
later folds and package evidence. Model states are persisted and reloaded before
scoring. Common comparison tables reuse the old baseline scores unchanged.
The receipt also records each primary metric's paired outing values and AR-minus-
baseline differences, their equal-outing mean, and improved/worsened/tied counts.
Missing lag support is explicitly unassessed and excluded from that metric's mean;
it is never replaced by zero. These are descriptive comparisons, not significance
tests or evidence of long-horizon performance.

Packaging uses a separate `.zip.partial`, verifies it and publishes the final
name by an exclusive atomic link. Ordinary pre-publication packaging failure
retains the partial and finalizes only this new attempt's unpublished local
receipt as failure; no accepted artifact is overwritten. A hard kill, another
interrupt during cleanup, or a durability error after publication can still
leave incomplete finalization evidence. Preserve terminal output and all claims,
receipts and ZIPs; do not retry. The private parent helper waits for the CLI on
Ctrl-C instead of killing its cleanup. Source hashes do not attest every ignored
interpreter hook; keep the existing trusted environment and its stated boundary.

## Subsequent model comparisons

No historical AR/AIOHMM, real flow, final evaluation or planner operation is
activated by this narrow gate. Later comparisons need identical rows, folds,
input/history declarations, physical sample metrics and fold-local selection.
Flow training loss is not Gaussian NLL; solver/density claims need their own
checks. All attempted fits and seeds must remain visible. Add the public-safe
accepted-return checkpoint with this functional PR; private numeric evidence
stays in the private packet. No additional raw scan is required for this control.
