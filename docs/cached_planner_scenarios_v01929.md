# v0.19.29 cached spatial scenario preparation

8 November 2026. PR 52 is merged and its owner synthetic report reproduced
exactly. Its actual reviewed head passed all three CI jobs. The next
bounded step freezes the original pilot identities and motion inputs from
the validated development caches.

## Scientific definition

The study quantity is the change in the existing affine planner between
a profile perturbed reference and an otherwise identical nominal plan.
For fixed speed, timestep and weights, the planned states and inputs have
the form A times the initial state plus B times the residual profile.
Subtracting the nominal plan cancels the common initial state term.
The incremental trajectory can therefore be computed with zero initial
increment while retaining the effect of the measured spatial residual.
The regression test checks this cancellation against direct solves from
two distinct nonzero initial states.

This clarifies the scenario join requested after PR 52. A native absolute
trajectory replay needs the nominal coordinates and the observed initial
vehicle state. That information is absent from the numeric archive.
The current incremental sensitivity question uses the original validated
left normal projection and its frame identity instead. It neither
reconstructs the coordinates from the residual nor assumes that the
actual vehicle was centred in the lane. This is a deliberate prospective
choice for the first recorded spatial experiment.

The recorded original speed supplies the planner's kinematic context.
The prediction timestep is fixed at 0.1 seconds with the existing 25 step
configuration. It is a declared prediction grid rather than an estimate
of the observed source cadence. A future temporal experiment must use
separately verified consecutive inputs and its declared update cadence.

## Original input and deterministic selection

Load the original sealed development experiment through the existing
native validator. Replay the complete locked registry ancestry, final
embargo checks, exact original row manifest, archive and receipt pins.
Use the lexicographically first original development outing as the pilot.
It is fixed by identity before planner outcome inspection. Retain every
original complete feature row in its original order. Each row records
the archive identity, raw identity, original profile index, candidate
index, pair index, both message indices and both decimal source epochs.
Use decimal strings for source times so large integer clocks retain all
digits.

The six feature rows and residual profiles share the exact original
conditioned profile index mapping. Keep original sequence offsets even
though this spatial stage treats snapshots separately. Exclude a row
from the later spatial evaluation only when its original speed is below
the existing planner minimum or its speed times prediction horizon
exceeds 100 m. Record all original rows, both failure counts and the
Boolean eligibility mask. A zero eligible result is a valid completed
preparation with pilot_scenarios_ready false.

The original residual definition is sensor EDP minus the RLMB fusion
proxy. The native original archive and row identity replay supply the
geometry association. Reference independence and physical online input
availability remain qualified. Planner effects concern this stated
incremental simulator and this selected population.

## Outputs and operational scope

The new output directory contains scenario_rows.private.json,
scenario_arrays.npz and scenario_manifest.private.json. The NPZ preserves
all original matched profiles and indices, source speeds, eligibility,
station grid and reset offsets. The manifest binds the original
experiment, cohort and registry identities, selected held out fold,
protocol, consumer source and output file hashes. A sibling result ZIP
packages these files with SHA256SUMS.

Preparation reads cached JSON and NPZ inputs. It performs no raw endpoint
access, model fit, model sampling, planner scoring, speed replacement,
population amendment, new recording intake or final evaluation. It does
not publish planner outcomes. Failure preserves written files and
attempts to package the partial evidence. Existing destinations are
refused. Runtime and original inputs are checked again before the
completion manifest is written.

The private owner helper pins the reviewed source tree and runtime and
the accepted original experiment. Use it after source review, CI and
merge. Return the new ZIP for acceptance. In the subsequent recorded
pilot, use the manifest and matched fold to choose the frozen model
states. Declare sample counts, seeds, metrics, draw sensitivity and
per outing aggregation before computing outcomes.

## Continuation

The next consumer will compare nominal, recorded incremental replay,
empirical resampling, diagonal and full covariance Gaussian and
unconditional flow for the prepared eligible rows. A full covariance
Gaussian remains a primary comparator. The causal contrast of the
diagonal control concerns spatial covariance. A claim about higher
moments requires an appropriate moments matched control. Fixed
engineering threshold choices precede that evaluation.

Additional downloaded drives remain a prospective independent
evaluation pool. Preserve existing final reservations. Inventory and
readiness must first establish identity, technical compatibility,
geometry continuity and complete input continuity under distinct
denominators. Their storage names or duration alone cannot establish
those properties. Target funnels remain a separate possible extension.
