# Matched real flow development protocol

5 November 2026. A2 prospective correction of the unmerged candidate. Independent source, scientific
protocol and private helper review, actual source CI, owner merge and separate
owner adoption are pending. Synthetic tests are engineering evidence only.
No BMW model has been fitted by this implementation session.

## Purpose and scientific scope

Complete the first matched comparison on the original complete feature dataset.
Reuse all four accepted matched baselines without fitting them again. Compare
an unconditional flow against a full conditional flow on exactly the same outer
folds and validation rows. This is a broader model comparison: the conditional
model adds current conditions and previous residual history together. Their
contrast cannot isolate speed, other features or memory separately.

The original speed definition and short sequences remain unchanged.
Results are conditional on the matched complete population selected by the
existing timing rules; representativeness of all driving is not established.
Planner integration requires a compatible online speed definition, which has
not been validated. The baseline AIOHMM adapter has one state and represents
no latent regime switching model. The new
protocol requires explicit scientific acceptance of the restricted short support
scope and a supervisor visible decision about the proposed model substitution.
It does not assert that the previous longer temporal support gate has passed.
The cached speed investigation supplies no adopted replacement feature, revised
population or proof of physical online feature availability. New recordings
remain prospective intake outside this experiment.

Targets retain the original estimate minus RLMB sign, ego coordinates, metre
units, 21 stations from 0 through 100 metres in 5 metre increments, complete
profile mask, source clocks and reset boundaries. The native accepted experiment
is the authority for all target definitions and qualification. RLMB is a fusion
based pseudo reference. Neither physical ground truth nor perception error
alone is established. Final outings remain reserved and unexposed.

The exact six inputs, in order, are speed_mps,
estimated_mean_abs_curvature_per_m, estimated_curvature_delta_per_m,
confidence_near_mean, confidence_middle_mean and confidence_far_mean.
No lane width, lane position, observed online target or additional input is added.

## Inputs, outputs and architecture

The closed request pins the native original one state experiment and its accepted
result ZIP. The new reader verifies its source tuple, manifests, nested original
baseline bytes, exact models, original fold transforms, scores and support. It
recursively uses unchanged native validators back to the original export.
The reader performs no raw MCAP operation and never repeats prior fits or draws.

Each mode is a separate MatchedFlow type, never a relabeled synthetic fit.
Only the prototype's pure bridge and gradient arithmetic is reused. Conditions
and residuals use the exact saved conditional Gaussian training fold means and
scales in both modes. No transform is fitted. The unconditional field sees 21
latent coordinates and bridge time. The conditional field additionally sees six
current features, 21 previous residual coordinates and a reset indicator.
Both use one 64 unit tanh layer and a linear 21 coordinate output.

The bridge parameter is probability transport time, not driving time. Temporal
dependence comes from the previous residual and the original reset boundaries.
Source clocks are retained, but elapsed driving time is not a new input. This
model does not establish a continuous physical time error law or validate
irregular sampling outside the original retained sequence contract.

Training minimizes mean squared straight bridge velocity error with independent
standard normal noise and uniform bridge time. The previous observed target
belongs to the same retained training sequence only. At sampling, the previous
residual comes exclusively from that draw's generated history. Every original
reset sets standardized history to zero and activates its separate reset flag.
Training uses observed history while inference uses generated history, so
exposure bias and accumulated sampling error remain model limitations. Neither
short support nor a numerical screen validates long planner rollouts.
Sampling accepts conditions and offsets, with no observed target argument.
No history crosses a recording, sequence, outing or outer fold.

The final fixed configuration is 100 epochs, batch size 256, Adam learning rate
0.003, beta values 0.9 and 0.999, and epsilon 1e-8. All training rows participate
once per epoch. Each epoch resamples bridge noise and time and permutes rows.
Training seed is 20261104 plus the fixed fold index. Independent initialization,
noise, time and permutation streams keep bridge inputs paired across modes.
No architecture search, inner fit, early selection, restart, clipping, held out
selection or automatic retry is implemented. Fixed epochs do not establish
optimizer convergence. The fixed configuration is a deliberate bounded first
comparison, not a claim that computation prevents training only selection. A
worse result cannot refute the flow family and a better result supports only
this configuration on this exposed development population. Loss history is a training objective, never a likelihood.

A diagnostic checkpoint is preserved after epoch 1 and each tenth epoch. These
are immutable diagnostic model states, not resumable optimizer checkpoints.
The completed final model and fit report are saved and reloaded before solver
calibration and held out scoring. Every failure stops all later fits.

## Numerical calibration and bounded work

Each successful fit is timed. Its fixed 600 second limit is checked within
mini batches. The first authorized fit supplies the training only timing check;
there is no extra timing fit. A timeout preserves the existing claim and any
completed checkpoints. It does not permit a fresh request with a different name.

Select shortest, middle and longest retained sequence per training outing,
using length then original index for ties. At most 18 sequences enter solver
calibration. No validation observations or training target values select this
subset. With 32 indexed draws and seed 20261105, compare Heun 32, 64 and 128
steps with common noise. Both refinement reports are retained. Use exactly 128
steps only if the final 64 to 128 refinement passes every declared criterion:

| Diagnostic | Maximum accepted change |
| :--- | ---: |
| Paired path RMSE in training standard deviation units | 0.025 |
| Largest paired coordinate change in those units | 0.15 |
| Largest pointwise mean change in those units | 0.025 |
| Largest pointwise standard deviation change in those units | 0.025 |
| Largest 5, 50 or 95 percent quantile change in those units | 0.05 |
| Fraction of row and threshold pairs with probability change greater than 2/32 | 0.02 |
| Largest pooled profile tail probability change | 0.01 |

Tail thresholds are 0.5, 1 and 2 metres. Pointwise probability resolution is
1/32. A pair exceeds the threshold only for a change strictly greater than
2/32. At most 2 percent of all row and threshold pairs may exceed it; the
denominator is three thresholds times the number of calibration rows. The
pooled criterion still screens the aggregate. The maximum pointwise change,
exceedance count, denominator and counts by threshold remain descriptive output.
This fraction tolerance addresses the brittleness of a single maximum over
many pairs. It is not a statistical familywise error or false discovery
correction and makes no independence or significance claim. These are prospective numerical
engineering tolerances for independent review, not empirically validated error
bounds. They were exercised only on synthetic fields before real fitting.
Heun evaluates velocity twice per step: at the current latent state and at
its Euler predictor, with the next transport time. The update averages those
velocities. Current driving conditions, generated past and reset flag are
fixed across both stages. There are at most 256 velocity evaluations per
active sample for the admitted 128 steps, four times the original Euler 64
budget. The indexed base noise, frame order and generated history law are
unchanged. The sampler keeps Euler as its direct API default; the reviewed
workflow explicitly requests Heun and saves that solver identity.

The screen cannot prove global solver convergence, precise tail probabilities
or validity outside the selected training support. A failed screen saves the
state and report and stops scoring and subsequent fits. Do not relax criteria
after seeing real data outcomes.

Each sampling call has a 180 second limit. Model fitting admits at most 20000
rows, 10000 sequences and length 100; a sampling allocation admits at most
16000000 scalar output values. Indexed noise fixes draw and original row before
batching. There is no padding or dropped row in the flat adapter. Sampling is
bounded in batches of at most 4096. The private runner adds a whole operation
time limit and preserves termination evidence, including a failed false draft
installation after successful preparation. It returns the prepared marker,
request and any partial draft in its execution ZIP. Existing or uncertain flow
claims from an older protocol revision block automatic continuation. CPU time
has a margin above the wall limit for parent controlled interruption. These ceilings are not completion
time forecasts or a reason to expand the admitted data.

## Matched evaluation and saved evidence

Use the original 128 draws and seed 20261022 plus fold index. Flow modes have
common indexed base noise; no common indexed noise relationship with the legacy
AR sampler is claimed. Evaluate physical metre residual samples on all unchanged
held out rows and resets with the existing matched evaluator. Primary metrics
are normalized sequence energy score and lag one correlation error. Retain
profile energy score, marginal CRPS, sample mean RMSE, intervals, sharpness,
profile tail Brier scores, per station diagnostics and valid support counts.

Flow physical NLL is JSON null with an explicit unavailable status. There is no
verified divergence integral, Jacobian density or normalized likelihood in this
implementation. Never substitute training MSE or a Gaussian approximation for
flow NLL. Existing baseline likelihoods remain available in the comparison.

Report score differences between independent halves of the 128 draws as
Monte Carlo sensitivity. These are descriptive differences from one run,
not confidence intervals, independent model validation or a selection rule.
Primary aggregation gives each outing equal weight. Missing lag values retain
assessed and unassessed outing counts and are never filled with zero. Paired
primary deltas compare each flow with all four original baselines. There is no
automatic winner, significance claim or planner improvement claim.

The complete successful return contains saved models, diagnostic checkpoints,
fit reports, calibration reports, fold scores, Monte Carlo diagnostics, common
comparison JSON and a Matplotlib PNG. Plot dots are outings and diamonds are
equal outing means. It also preserves authorization, immutable claim, original
one state result ZIP, request, experiment marker, output hashes and ZIP manifest.
The original result includes the earlier baseline chain unchanged. Failures
preserve partial evidence and stop the entire operation.

## Admission and next decisions

Preparation seals the protocol and writes no fitted model. A separate false
authorization draft requires all six literal Boolean attestations to become
true through an explicit owner decision. They cover this two flow development
fit, independent review and CI, restricted short scope acceptance, supervisor
visible substitution acceptance, final reservation and failed attempt retention.
A prior AR authorization, integer 1, string true or partial adoption is rejected
before any new fit claim. Software cannot itself verify the external scientific
or supervisor decisions; the owner must attest truthfully.

The immutable semantic attempt key includes the original Gaussian experiment,
accepted one state result and complete fixed flow protocol, excluding output
paths. Renaming outputs cannot retry a started design. Inputs and clean source
are checked before each fit and after the operation. Failed states, logs, claims,
receipts, partial ZIPs and unknown progress are evidence, never cleanup targets.
Independent review, actual new source CI and merge must precede owner adoption.

Four baseline configurations are complete; two flow configurations remain.
On the retained seven folds this is fourteen outer fits, with no extra selection
fits. Completion of those fits still requires saved state and score review,
model freeze, separately admitted final evaluation, planner interface validation
and downstream comparison. Additional long drives need a separate versioned
intake, split and feature decision before they can enter any final training.
The planner interface will need current conditions, reset flags, generated
history and the original frame, sign and station contract. Better statistical
scores alone establish no planner benefit.

## A2 prospective review correction

Independent review accepted the cached v0.19.26 diagnostic and found one blocker
in the first flow solver screen. Synthetic experiments at realistic fold scale
showed that the old pointwise maximum tail rule and the 64 step solver could
stop the entire operation at its first fit. No BMW flow had been fitted. This
revision changes the numerical protocol prospectively, keeps the other six
limits and all training settings fixed, and adds a realistic scale synthetic
regression for both modes and Gaussian and Student t innovations.

An initial prospective Euler 128 sweep still showed pooled tail failures in
some synthetic stress cases. The final candidate uses Heun on the same fixed
ladder to reduce discretization error, retaining that initial negative evidence.
The synthetic experiment makes no real data acceptance or global solver claim.

The request and authorization revisions now identify a2. Their old prepared
experiment pin and any old adopted authorization are invalid for this revision.
The source, runtime, helper and request pins are reissued in the private packet.
The owner must apply the delta to the current PR, obtain focused independent
review and new actual head CI, then merge before any owner preparation or fit.
The main agent accepts the restricted short support first comparison under
these explicit limitations. Owner adoption and the supervisor visible model
substitution decision remain separate. No longer support, speed replacement,
new population, final evaluation or planner admission follows from this fix.
