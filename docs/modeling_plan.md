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
| v0.11 | AIOHMM on condition schema v1 | State-count exploration remains development-only; state occupancy and transition stability are reported |
| v0.12 | Predeclared prediction-time feature ablations | A feature schema changes only when availability, leakage, and held-out-drive improvement gates pass |
| v0.13 | RC-GAN | Begins only after the independent-drive/data-volume gate; distributional and temporal metrics use identical held-out rows |
| final | Locked comparison and thesis figures | Hyperparameters frozen before evaluating untouched physical drives |

The v0.10 Gaussian is the temporal null model: it uses sequence-shaped inputs
and the common evaluator, but it does not invent temporal dependence. This
separates gains caused by sequence modeling from gains caused by a different
cohort, split, transform, or metric implementation.

## Feature policy

The six v0.8 features remain BMW condition schema v1 for the architecture
comparison. Candidate schema-v2 features should be audited before fitting:

- prediction-time longitudinal acceleration or recent speed slope;
- prediction-time yaw rate, lateral acceleration, or steering state when a
  confirmed source and timestamp contract exist;
- near/middle/far curvature rather than only whole-H100 summaries;
- confidence minimum, spread, and recent change in addition to bucket means;
- short causal histories of the above features, never future values.

Each candidate first receives an all-frame availability audit. Ablations use
the same frozen target cohort and physical-drive splits. Searching many
features on the present two drives is exploratory only and cannot finalize the
thesis schema.

## Additional-data gate

The present development set has 1,770 frames, 13 contiguous sequences, about
140.58 s of within-sequence duration, and only two physical drives. It is
adequate for contract development and preliminary Gaussian/AIOHMM execution,
but it cannot provide separate train, validation, and untouched test drives.

Before final model selection or an RC-GAN claim, collect more independent
physical drives. A practical acquisition target is 8--12 drives, with at least
two drives locked as an untouched final test; this is an engineering planning
target, not a substitute for a formal sample-size analysis. Prefer individual
continuous recordings of 2--5 minutes or longer over many 20-second chunks.
Retain exact basename-to-session/drive manifests and cover variation in speed,
curvature, confidence, road type, and operating conditions without selecting
recordings based on observed residual size.

If only chunked recordings are available, do not join them into one sequence
unless a separate continuity contract proves monotonic source time, no overlap,
an acceptable boundary gap, identical signal semantics, and one physical
session. Until then, every MCAP remains a sequence boundary.
