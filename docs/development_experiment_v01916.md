# Matched development experiment and Gaussian fit protocol, v0.19.16

Date: 2026-10-22. Candidate above merged PR #41 (`6ed17f2`, reviewed owner
head `ad692e3`, tree `e81a8fab`). Its fixed development export operation returned
successfully and passed independent raw-free checksum, source, lineage, numeric,
row/reset and descendant replay. The original cohort and every publication stay
binding. Private counts, clocks, identities and marker pins remain private.

## Bounded first real experiment

This implementation adds a new admission path for a fixed Gaussian pair on the
complete-feature subset of **all locked new development outings**. It changes
neither old readers' false model-admission flags nor any historical training CLI.
It does not import legacy rows automatically. Legacy evidence remains separate
until an explicit common-target/cohort protocol justifies combining it.

The same residual vectors and reset boundaries are used by both models. The
unconditional Gaussian ignores features. The conditional Gaussian uses an
intercept and the frozen six features with a full, condition-independent spatial
covariance. Its mean is training-standardized minimum-norm OLS. Full-rank means
equal ordinary OLS; exact constant and collinear features do not require deleting
held-out rows or inventing feature variation. The design rank is saved. All
normalization uses training rows only. Exact constant columns retain their exact
value as mean and scale one; every varying column retains its own positive scale.
Covariance is the MLE of training errors plus `1e-6 I` in residual-standardized
coordinates. No mean ridge, tuning grid, early stopping or adaptive repair is used.
Historical Gaussian implementations and artifacts are unchanged.

Each locked development outing is held out once. Other development outings form
that fold's training set; the final outings never enter a fold. These are
development cross-validation results, including any later model/protocol choices;
they are not untouched final evidence. All frames and singleton sequences remain.
Recording/estimate/pair/source-time gaps and original conditioned offsets remain
resets. Neither an interval-span gate nor a large frame count proves independent
observations or long temporal support. Identity quality remains owner-declared.

The fixed sampling design uses 128 draws, paired indexed normal noise for both
models, and seed `20261022 + fold_index`. Both Gaussian models are temporal
nulls. Their lag score uses only retained adjacent pairs. Fewer than two pairs,
or constant station series, produces explicitly unavailable lag support rather
than a zero-error claim. Per-fold scores include physical joint NLL (with the
normalization Jacobian), frame and normalized sequence energy, marginal CRPS,
sample-mean RMSE, station bias/RMSE, 50/80/95 percent marginal intervals, and Brier
scores for max-absolute-profile exceedances of 0.5/1/2 m. Tail thresholds are
fixed diagnostics, not inferred physical safety thresholds. Primary scalar
aggregation weights outings equally. Secondary pooled scores use frame weights,
sequence weights for sequence energy, and squared-error pooling for RMSE.
No frame-IID confidence interval or automatic winner is reported.

## Preparation and immutable replay

`io.development_experiment` accepts an externally pinned, closed-schema request:

```text
contract_revision, cohort_directory, expected_cohort_sha256,
original_registry_directory, expected_original_registry_sha256,
descendants, archive_sha256, export_receipt, expected_export_receipt_sha256,
experiment_directory, training_directory, authorization, result_zip
```

Revision is `v0.19.16-matched-development-experiment-2026-10-22-a1`.
Descendants are the complete explicit ordered list of `directory, sha256`.
The successful export receipt must match the externally pinned original cohort,
original/latest registries, chain and archive selection. Digest-bound copies may
be replayed offline; receipt locator strings do not redirect the reader to raw.
Every registry and original cohort strictly replays, including identity/final
embargo rejection before descendant arrays. Cached records/roles are not trusted.
Project history and adopted numeric consent must be present in the pinned chain.
All development raws must be covered exactly once; final, excluded, outside,
duplicate-raw, duplicate-component and partial-session selections are refused.
The first adapter requires one archive per complete outing.

Preparation fits nothing. It writes exactly `request.json`, `row_manifest.json`,
then completion marker `experiment.json`. The row manifest records exact archive
row mappings, recording/message/pair indices, decimal source clocks and offsets.
The marker pins its bytes, request, original lock, latest registry, protocol,
support and complete outing folds. Replay reconstructs everything; repinning
edited folds, rows or protocol cannot promote them. Source and inputs are checked
before completion. Outputs must be new, ignored private locations, separated from
inputs and immutable or markerless partial containers. Every original stays in
place. The protocol, not a CLI override, fixes training and result destinations.

## Fit authorization and lifecycle

Both preparation and training require the selected project imports, clean source,
expected Git tree and runtime. Training additionally needs a pinned authorization
with the exact experiment marker digest, purpose
`fixed_gaussian_pair_development_cross_validation_only`, revision
`v0.19.16-development-gaussian-fit-2026-10-22-a1`, and four literal true flags:

```text
explicit_development_gaussian_fit
independent_protocol_review_and_ci_accepted
final_outings_remain_unexposed
fixed_protocol_and_preserve_failed_attempts
```

Issued drafts contain false flags. Owner adoption occurs only after independent
source/protocol/helper GO, exact reviewed-head Python 3.10/3.12 and frozen-reader
CI, and owner merge. No code sets those flags true for the owner. This is the
separately reviewed Gaussian real-fit protocol; neither engineering readiness nor
an old training CLI grants it. The original adapters continue to deny admission.

The shared registry writer lock covers the entire operation. Immutable inputs,
file sets, project history, consent and runtime are checked before every fit and
after scoring. A new attempt preserves model states before scoring, exact fold
membership, seeds, scores and hashes. Persisted states are reloaded before use.
Caught failure/interrupt preserves partial models and returns a receipt and
SHA/CRC-checked private ZIP; later folds stop. An existing attempt or result is
never overwritten or retried. A preflight failure creates no training attempt.
A hard kill or packaging failure requires preserved local evidence and a separate
recovery review. Terminal success is
`complete_development_gaussian_cross_validation`, exit 0 and integrity true.

## Flow matching and subsequent gates

`io.synthetic_flow_model` adds bounded JSON, external SHA pins, exclusive writes,
strict synthetic-only scope and validated learned-array reconstruction. It uses
no pickle and grants no real-data fit. Tests exercise both modes and reproduce
seeded Euler samples after save/load. `modeling.synthetic_flow_sampling` batches
velocity evaluation across draws/sequences while retaining indexed noise,
generated history, starts and zero padding. Batch-size-one samples are bitwise
equal to the original sampler; larger batches are checked within numerical
tolerance because matrix reductions may differ. Velocity-call counts are reduced
without reducing Euler steps. The existing flow objective, start state,
reference sampler and training streams remain unchanged. This is an efficiency
change, not evidence of improved predictive distributions or solver convergence
on the real cohort.

AR/AIOHMM, real flow, final evaluation and planner experiments are not activated
by this Gaussian protocol. They need explicit scientific scope and an appropriate
temporal-support contract. The observed short complete-feature histories must
not be bridged. Flow still needs the supervisor-visible scope decision, real
model adapter/persistence protocol, fixed training/validation settings and solver
convergence checks on evaluation metrics. A flow training objective is not NLL.

Keep RLMB's pseudo-reference qualification, shared-dependency uncertainty, exact
speed causality, unconfirmed 5 m confidence width and producer compatibility
assumption visible. A past-only speed construction, if supported by producer
semantics, would require a separately reviewed version and comparable cohort.
New downloads require separate prospective intake; they cannot silently replace
excluded outings or reroll final roles after development exposure.


## Local validation checkpoint

Compileall and full suites pass on Python 3.10.22/current MCAP 1.6.0,
Python 3.12.14/current MCAP 1.6.0 and Python 3.12.14/frozen-reader MCAP 1.4.0:
923 tests, 921 passing and two unchanged expected skips each. The 34 added tests
cover actual synthetic preparation, fitting/state replay/scoring, wrong consent,
lineage/fold tampering, drift/interrupts, output preservation, density units,
exact constants, sample-score/reset behavior and synthetic flow persistence and
batch/reference parity. Twelve original scientific/numeric/flow files are
byte-identical. Offline private replay reconstructs matched development blocks
and folds with guards against owner raw endpoints and model/transform fitting.
Twelve disposable Git/helper checks cover patch application, source/import pins,
false drafts and preservation; positive helper CLI delegation is explicitly
stubbed on fabricated synthetic identities. Actual data orchestration/fits are
native synthetic tests. Local evidence is private. Review, pushed-head CI and
owner merge/adoption remain required before operational use.
