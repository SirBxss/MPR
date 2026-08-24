# Thesis modeling plan

MPR is the canonical thesis implementation. LEEM is retained only as a source
of implementation ideas and historical evidence; its model code and results
are not the thesis execution path.

## Fixed scientific rules

- The target is the 21-dimensional signed H100 pseudo-residual at
  `0, 5, ..., 100 m`.
- The three planned families are conditional Gaussian, AIOHMM, and RC-GAN.
- All families consume the same conditions, targets, masks, lengths, sequence
  provenance, physical-drive folds, and evaluation rows.
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
| v0.14 | Clean-drive evaluation protocol and Gaussian re-baseline | Implemented; four leave-one-clean-drive-out folds, equal-drive and pooled metrics, and separate mixed-fragment transfer checks |
| v0.15 | Two-state AIOHMM on the v0.14 protocol | Implemented; temporal dependence improves strongly, but marginal calibration and full generative acceptance do not pass |
| v0.15.1 | One-state conditional AR ablation | Next minimal diagnostic; determine whether the latent switch adds value beyond autoregression without changing data, features, or folds |
| v0.16 | RC-GAN | Begins only after the AIOHMM/AR review and when the independent-drive/data-volume gate supports a defensible adversarial experiment |
| final | Locked comparison and thesis figures | Hyperparameters frozen before evaluating untouched physical drives |

The v0.10 Gaussian is the temporal null model: it uses sequence-shaped inputs
and the common evaluator, but it does not invent temporal dependence. This
separates gains caused by sequence modeling from gains caused by a different
cohort, split, transform, or metric implementation.

The expanded v0.15 result is not a general AIOHMM victory. Macro lag-one error
falls from 0.888345 to 0.018276, but frame energy and coverage are worse and
normalized complete-sequence energy is effectively tied. One selected fold fit
also reaches the occupancy-constrained optimization boundary. The next model
change is therefore a one-state conditional AR ablation, not feature expansion
or RC-GAN tuning. Additional clean physical drives remain necessary before an
untouched final comparison.

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
drives. Primary modeling uses only the four clean sensor-topology drives:
4,084 frames and 16 sequences. The other four drives contribute 518
mixed-source fragments and are supplementary only. This is adequate for
leakage-safe leave-one-drive-out development and a serious Gaussian/AIOHMM
comparison, but it still cannot provide both robust tuning and untouched final
test drives.

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
