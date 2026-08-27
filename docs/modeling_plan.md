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
| v0.16.1 | Unconditional-Gaussian planner transfer | Proposed and awaiting pre-run review; test the actual v0.14 Gaussian as a separate model-to-model extension without changing the causal v0.16 result |
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

An unconditional-Gaussian A3 arm is not part of the accepted v0.16 experiment.
It is proposed as v0.16.1 because the observed smoothness contrast makes a
planner-facing link to the actual v0.14 Gaussian scientifically useful. The
separate predeclaration fixes its model source, seeds, primary metrics,
independent-draw interval, directional hypotheses, and reporting rule before
implementation or execution. A3 changes both marginal and temporal structure,
so its likely relation to the A1 statistical null remains a hypothesis until
tested and cannot replace the causal A2-minus-A1 result.

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
