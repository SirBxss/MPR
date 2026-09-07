# Thesis modeling plan

MPR is the canonical thesis implementation. LEEM is retained only as a source
of implementation ideas and historical evidence; its model code and results
are not the thesis execution path.

## Fixed scientific rules

- The target is the 21-dimensional signed H100 pseudo-residual at
  `0, 5, ..., 100 m`.
- The completed development comparison contains the Gaussian baselines and the
  reviewed conditional autoregressive models. RC-GAN is not pursued on the
  current one-outing corpus because the data-volume and complexity gates do
  not support it.
- All families consume the same conditions, targets, masks, lengths, sequence
  provenance, recording-group folds, and evaluation rows.
- A model never sees a held-out drive while fitting parameters,
  standardization, early stopping, or hyperparameters.
- A sequence crosses an MCAP recording boundary only under the reviewed
  v0.13.1 same-drive continuity contract. Path and residual geometry remain
  recording-local; only accepted preceding odometry supplies a missing 50 ms
  speed bracket. Detected pair/time gaps still split sequences.
- Prediction-time features may use the current or past estimate/vehicle state.
  They may not use a residual, future residual, RLMB result, or any
  pseudo-reference-derived quality measure.
- Added model or feature complexity must improve predeclared held-out metrics
  and remain stable across physical drives.

## Phases and gates

| Phase | Implementation | Completion gate |
|---|---|---|
| v0.8 | Six-feature conditional Gaussian baseline | Complete; negative held-out comparison retained as a valid result |
| v0.9 | Common gap-aware sequence dataset and training-drive-only transforms | Complete; real-cohort reconciliation and contract tests pass |
| v0.10 | Gaussian sequence-parity adapter and common evaluator | Complete; same folds/rows, sampling, likelihood, save/load, energy score, calibration, and deterministic seeds tested |
| v0.11 | AIOHMM on the original condition schema v1 cohort | Implemented as the first temporal prototype; retained for diagnosis, not final comparison |
| v0.12 | Expanded-corpus inventory, alignment, and topology semantics | Complete; fail-closed lineage and the RLMB-independence limitation are explicit |
| v0.13 | Quality-gated expanded sequence dataset | Complete; v0.13.1 contains 4,602 frames, 34 sequences, and accepted boundary-speed context |
| v0.14 | Clean-group evaluation protocol and Gaussian re-baseline | Implemented; four leave-one-clean-group-out folds within one same-day outing, equal-group and pooled metrics, and separate mixed-fragment transfer checks |
| v0.15 | Two-state AIOHMM on the v0.14 protocol | Implemented; temporal dependence improves strongly, but marginal calibration and full generative acceptance do not pass |
| v0.15.1 | One-state conditional AR ablation | Complete and reviewed; one-state wins all five macro sample metrics against the original two-state fit, while the AR ceiling remains active |
| v0.15.2 | Two-state convergence audit | Complete and reviewed; one fold gains one iteration, every macro delta is at most `4e-4`, and the one-state conclusion is unchanged |
| v0.15.3 | One-state AR-boundary sensitivity | Complete and reviewed; 0.99, 0.995, and 0.999 share the same interior fit, while none passes every strict performance gate |
| v0.15.4 | Development-model freeze and sampler | Implemented; freezes 0.99 for planner development as the smallest nonbinding structural ceiling, retains 0.98 and the failed strict gate, and exports physical free-running H100 samples |
| v0.16 | Reference-planner temporal-order sensitivity | Complete and independently reviewed; temporal ordering changes the fixed planner's accumulated deviation and command smoothness within the current outing |
| v0.16.1 | Unconditional-Gaussian planner transfer | Complete and independently reproduced; the predeclared full-support rule passes, with mandatory length-dependent qualification of the deviation family |
| v0.16.2 | A2/A3 cross-station structure audit | Complete, independently reproduced, approved, and merged; it describes spatial-structure differences without assigning planner causality or authorizing another current-outing diagnostic |
| v0.17 | Prospective independent-outing intake and cohort lock | v0.17.0 implementation and arrival verifier are independently approved and merged; the first 86-chunk real audit is preserved with no role assignment, and no successful cohort lock exists |
| v0.17.1 | Exact EDP schema-v2 compatibility | First contract review returned `AMEND`; the documentation-only correction is awaiting focused re-review before implementation |
| final | Locked comparison and thesis figures | Hyperparameters frozen before evaluating untouched physical drives |

The v0.10 Gaussian is the temporal null model: it uses sequence-shaped inputs
and the common evaluator, but it does not invent temporal dependence. This
separates gains caused by sequence modeling from gains caused by a different
cohort, split, transform, or metric implementation.

The expanded v0.15 result is not a general AIOHMM victory. Macro lag-one error
falls from 0.888345 to 0.018276, but frame energy and coverage are worse and
normalized complete-sequence energy is effectively tied. All completed fits
touch the occupancy and maximum-AR boundaries, and one selected fold fit does
not converge. The four technical groups are separated portions of one longer
same-day outing, so this is within-outing evidence only.

The reviewed v0.15.1 ablation changes only the state count to one and disables
the now-trivial transition. It beats the original two-state result on all five
macro sample-based metrics and on sequence energy in three of four groups;
both claims remain within-outing. All one-state fits reach the 0.98 AR ceiling,
while the v0.15.0 two-state reference retains a potentially premature stopping
confound. v0.15.2 therefore changes only that stopping contract to a fixed
absolute improvement of `1e-3` standardized nats per training frame. Once the
corrected two-state evidence is reviewed, v0.15.3 may vary only the AR ceiling.
Additional independent outings remain necessary before an untouched final
comparison, broad feature search, or any more complex model family.

v0.15.3 treats 0.98 as an immutable reviewed reference and fits only the three
higher ceilings. A higher ceiling receives development support only when it
reduces station-fold boundary contact, improves macro calibration, remains no
worse on the predeclared temporal and energy criteria, and has no failed or
selected nonconverged fit. Fold directions are reported even though the four
groups are not independent journeys. If several candidates pass, the smallest
is reported to avoid maximizing a noisy metric on the same outing. This is
conservative development guidance, not final hyperparameter selection.

v0.15.4 makes a separate engineering freeze after that scientific decision.
It does not reinterpret the strict gate as passed. The 0.99 candidate is used
because it is the smallest tested ceiling above the common interior optimum;
the larger ceilings add no fitted freedom. The bundled all-clean model remains
development-only, uses the same six features and H100 residual sign contract,
and must be sampled free-running over complete condition sequences. Planner
evaluation must report that 0.98 remains the reviewed performance reference.

v0.16 uses a deterministic MPR-owned reference planner. The primary comparison
is frozen AR order against an exact within-sequence time shuffle of the same
residual profiles. Snapshot-only evaluation cannot identify temporal-order
effects, so a linearized lateral/heading error state is propagated around the
recorded motion. Ego-relative paths are not stitched into a global trajectory,
and the experiment is not vehicle-state replay. The fixed contract is in
`docs/reference_planner_predeclaration.md`.

The experiment may report sensitivity in nominal-path deviation, heading,
curvature, curvature rate, lateral acceleration, jerk, objective value, and
numerical failures. It may not report planner benefit, closed-loop safety, BMW
planner behavior, or production readiness. A later BMW transfer-validation
experiment requires exact production interfaces and conventions but does not
block the primary v0.16 result.

The corrected 128-draw real run separates A2 frozen order from A1 shuffled
order on three of five predeclared headline metrics. A2 increases integrated
absolute lateral error by `0.176956 m s` and maximum absolute lateral error by
`0.012402 m`, while reducing the fixed-envelope violation fraction by
`0.093137`; all three paired-draw intervals exclude zero. Final absolute error
and the 0.3 m exceedance fraction are indeterminate under the unchanged
predeclared interval rule. The result shows that temporal correlation trades
accumulated deviation against command smoothness for this fixed within-outing
simulation. It does not establish planner benefit, comfort, safety, production
behavior, or journey-level generalization.

The v0.16.1 A3 arm remains separate from the accepted v0.16 experiment. Its
model source, seeds, primary metrics, short-sequence p95 rule, marginal
diagnostics, independent-draw interval, directional hypotheses,
cohort-consistency reporting, and claim limits were fixed before A3 existed.
The real run passes both predeclared families: A3 is much rougher than A2 and
has lower deviation under the equal-sequence macro. The deviation result is
length-dependent, however: the same five sequences reverse both deviation
metrics, contain 57.9% of active frames, and rank 1st, 2nd, 6th, 7th, and 8th
by length. The pooled-frame mean-deviation reduction is 5.4%, versus 16.2%
under equal sequence weighting. This non-gating qualifier must accompany the
full-support decision. Because A3 changes marginal distribution, cross-station
covariance, and temporal structure, it cannot replace the causal A2-minus-A1
result or authorize a general model ranking.

The approved v0.16.2 audit consumes the accepted A2 and A3 generated residual
ensembles read-only and quantifies contemporaneous cross-station covariance and
correlation. It is explicitly post-hoc: the approximate pooled correlation
levels were already reported in the independent v0.16.1 review. It reports
station-pair, separation, pooled-frame, and equal-sequence descriptions with no
interval or pass/fail gate. It cannot establish that spatial coherence caused
the length-dependent planner deviations or separate coherence from marginal
scale. Its reviewed contract is the final current-data generated-ensemble
diagnostic; no A4 arm or further model/planner sweep follows from it.

The focused re-review returned `GO` before implementation. The workflow now
hard-pins both complete source directories and writes only the predeclared
numeric matrices and tables. Its accepted-artifact implementation check
reproduced the reviewer's already disclosed statistic list. The final review
then independently regenerated both source ensembles, reconciled all five
files, and returned `GO`; the audit is complete and merged.

The v0.16.2 arm comparison uses the same nominal generated-profile count, but
that count is not an inferential sample size: A2 is serially dependent and
sequence-reset, whereas A3 is temporally independent. No scalar effective
sample size is authorized for the covariance/correlation estimands. Sequence-
wise A2 structure is a finite-horizon mixture of reset, transient, conditional,
and later free-running behavior, so a length association is confounded rather
than evidence of physical spatial heterogeneity or a causal planner mechanism.

No further implementation on the present generated ensembles is authorized.
The primary next phase requires additional independent clean outings and a
separately reviewed, locked final-data protocol before any final comparison.
An optional BMW-planner transfer remains a distinct production-relevance study
requiring confirmed interfaces and its own predeclaration; it cannot substitute
for independent-outing evidence.

v0.17 separates data intake from the later final comparison. Its amended
contract is `docs/independent_outing_intake_predeclaration.md`. It fixes
prospective physical-outing declarations, outcome-blind technical eligibility,
a minimum of seven eligible new outings in addition to the one legacy
development outing, deterministic content-hash-based final assignment,
first-successful-lock binding, and an embargo on final-outing residuals,
features, and model evidence. The contract explicitly adopts an inclusive
reading of the 8--12-outing target and states that only two or three outings
form the untouched test set within that planning window. The target remains an
engineering planning rule rather than a formal power calculation. No v0.17
workflow was permitted until focused independent review authorized it. The
focused re-review of the amended contract required one exact correction to the
layout-dependence wording and explicitly authorized implementation without
another wording review once that correction was committed. v0.17.0 now
implements only that reviewed intake boundary. Its focused implementation
review found one package-initializer dependency wording issue; the correction
received `GO`, and the implementation is merged. The private prospective
manifest was completed, its CEST filename times were reconciled to internal
UTC, and the first real intake was executed and independently reconciled. It
correctly assigned no role, both because only one new outing exists and because
the technical decoder failed closed on a newer BMW EDP descriptor that removed
the legacy model-parameter Boolean. Privacy-safe complete-message evidence and
a Copilot read-only BMW source trace support a narrow generation-aware adapter.
That evidence is recorded in `docs/bmw_edp_schema_evidence.md`; the exact
v0.17.1 amendment is drafted in
`docs/independent_outing_schema_v2_amendment.md`. Its first focused review
returned `AMEND` for descriptor-hash identity, additive output lineage, and
mandatory `index_0` wording; the corrected exact contract requires focused
re-review before code changes. The arrived set remains one physical
outing and can contribute at most one of seven required new outings. File or
chunk count must not be used as outing count.

A successful real v0.17 lock still does not authorize final evaluation. The
exact training corpus, frozen competitors, fitting rules, final-outing failure
handling, sample seeds, outing-macro metrics, decision rule, and claim limits
must be fixed in a second predeclaration and reviewed before embargoed final-
outing values are read.

## Feature policy

The six v0.8 features remain BMW condition schema v1 for the first expanded-data
architecture comparison. v0.14 explicitly measures whether they improve a
conditional Gaussian over the unconditional reference. Candidate schema-v2
features should be audited before fitting:

- prediction-time longitudinal acceleration or recent speed slope;
- prediction-time yaw rate, lateral acceleration, or steering state when a
  confirmed source and timestamp contract exist;
- near/middle/far curvature rather than only whole-H100 summaries;
- confidence minimum, spread, and recent change in addition to bucket means;
- short causal histories of the above features, never future values.

Each candidate first receives an all-frame availability audit. Ablations use
the same frozen target cohort and physical-drive splits. Broad feature search
on four clean development drives remains exploratory and cannot finalize the
thesis schema.

## Additional-data gate

The accepted v0.13.1 set has 4,602 frames and 34 sequences across eight mapped
technical groups. Primary modeling uses only four clean sensor-topology groups
from one same-day outing:
4,084 frames and 16 sequences. The other four drives contribute 518
mixed-source fragments and are supplementary only. This is adequate for
leakage-safe leave-one-group-out development and a serious within-outing
Gaussian/AIOHMM comparison, but it cannot estimate independent-journey
generalization or provide an untouched final test outing.

Before final model selection or any strong higher-complexity-model claim,
obtain more independent clean physical drives. A practical acquisition target
remains 8--12 clean drives, with at least two locked as an untouched final
test; this is an engineering planning target, not a substitute for a formal
sample-size analysis. Prefer individual continuous recordings of 2--5 minutes
or longer
over many 20-second chunks.
Retain exact basename-to-session/drive manifests and cover variation in speed,
curvature, confidence, road type, and operating conditions without selecting
recordings based on observed residual size.

Chunked recordings may be joined only when the reviewed continuity contract
proves monotonic source time, no overlap, an acceptable boundary gap, identical
signal semantics, eligible immediate endpoints, and one physical session. All
other MCAP boundaries remain sequence boundaries.
