# Thesis modeling plan

MPR is the canonical thesis implementation. LEEM is retained only as a source
of implementation ideas and historical evidence; its model code and results
are not the thesis execution path.

## Fixed scientific rules

- The target is the 21-dimensional signed H100 pseudo-residual at
  `0, 5, ..., 100 m`.
- The three planned families are conditional Gaussian, AIOHMM, and RC-GAN.
- All families consume the same conditions, targets, masks, lengths, sequence
  provenance, recording-group folds, and evaluation rows.
- A model never sees a held-out drive while fitting parameters,
  standardization, early stopping, or hyperparameters.
- A sequence never crosses an MCAP recording boundary or a detected pair/time
  gap.
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
| v0.15.2 | Two-state convergence audit | Implemented; exact private-corpus run must determine whether the v0.15.0 stopping rule confounded the latent-switching comparison |
| v0.15.3 | One-state AR-boundary sensitivity | Begins only after v0.15.2; vary only the predeclared AR ceiling and test the recorded coverage prediction |
| v0.16 | RC-GAN | Begins only after the AIOHMM/AR audits and when the independent-drive/data-volume gate supports a defensible adversarial experiment |
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
comparison, broad feature search, or RC-GAN work.

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

Before final model selection or a strong RC-GAN claim, obtain more independent
clean physical drives. A practical acquisition target remains 8--12 clean
drives, with at least two locked as an untouched final test; this is an
engineering planning target, not a substitute for a formal sample-size
analysis. Prefer individual continuous recordings of 2--5 minutes or longer
over many 20-second chunks.
Retain exact basename-to-session/drive manifests and cover variation in speed,
curvature, confidence, road type, and operating conditions without selecting
recordings based on observed residual size.

If only chunked recordings are available, do not join them into one sequence
unless a separate continuity contract proves monotonic source time, no overlap,
an acceptable boundary gap, identical signal semantics, and one physical
session. Until then, every MCAP remains a sequence boundary.
