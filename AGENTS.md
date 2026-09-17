# MPR agent instructions

These instructions apply to the complete repository. MPR is the canonical
implementation for the thesis; LEEM is historical reference material only.

## Start every task here

1. Read `docs/current_status.md` for the exact stopping point and next task.
2. Read the relevant contract before changing code:
   - `docs/modeling_plan.md` for scientific gates and phase decisions;
   - `docs/output_contracts.md` for exact artifact schemas;
   - `docs/architecture.md` for ownership boundaries;
   - `docs/commands.md` for supported entry points;
   - `docs/bmw_edp_schema_evidence.md` before changing any estimated-drive-
     path schema binding; and
   - `docs/independent_outing_schema_v2_amendment.md` for the reviewed v0.17.1
     compatibility boundary; and
   - `docs/independent_outing_batch01_v0171_result.md` for the accepted real
     amended audit, its exact lineage, interpretation, and remaining data gate;
     and
   - `docs/sensor_topology_feasibility_predeclaration.md` and
     `docs/bmw_sensor_topology_source_evidence.md` before any work that reads
     `/adp/lane_topology_sensor_based` as a candidate estimate source.
3. Inspect `git status --short`, the current branch, and recent commits.
4. Preserve unrelated user changes and previously reviewed artifacts.

Update `docs/current_status.md` whenever a phase is implemented, reviewed,
merged, or materially reinterpreted. It is the hand-off record for future
agents and new chats.

## Working relationship

- ChatGPT/Codex is the primary implementation agent. Claude is an independent
  reviewer, not the primary implementer.
- Stay focused and precise. Prefer the smallest defensible experiment or code
  change; do not expand the model family or architecture without evidence.
- Do not ask Leon for detailed implementation progress. Ask the user only when
  a scientific decision or unavailable BMW interface blocks correct work.
- The BMW codebase is unavailable here. Never invent its APIs, types, paths,
  planner entry points, or metric interfaces. BMW details are required only
  for an explicit BMW integration or transfer-validation task; they do not
  block the MPR-owned reference-planner sensitivity experiment. When BMW
  integration is required, give the user a focused Copilot prompt and wait for
  exact symbols and signatures.

## Scientific invariants

- The target is the 21-dimensional signed H100 pseudo-residual at
  `0, 5, ..., 100 m`.
- Residual means EDP estimate minus the spatially aligned RLMB
  pseudo-reference, projected onto the pseudo-reference left unit normal.
  Positive is left with respect to increasing station.
- The prospective v0.18 sensor-topology target is not adopted. The BMW trace
  establishes camera-derived boundary geometry inside a map-influenced
  topology graph but does not establish physical frame equivalence with RLMB.
  After focused review, its first phase may inventory strict camera-chain
  structure, orientation-invariant 100 m span, independent RLMB H100 readiness,
  and source-time co-availability only. It may not compare cross-topic
  coordinates, calculate an anchor or residual, or reinterpret an EDP result.
  The frozen a3 review candidate is supported by three private source traces.
  The third resolves every cited tracked path and rechecks the findings from
  immutable `HEAD` blobs; its failure to record the literal BMW commit SHA is
  a source-trace reproducibility limit, not a blocker for the fail-closed MPR
  structural audit. No further BMW-source answer is required for this phase.
  The frozen contract received focused `GO`, and the synthetic-only structural
  audit is implemented. Do not inspect private MCAPs before the exact pushed
  implementation receives focused implementation `GO`.
  Historical EDP models and sensor-lane residuals must never be pooled or
  relabelled as one target.
- RLMB is a pseudo-reference, not physical ground truth.
- BMW condition schema v1 is fixed in this exact order:
  `speed_mps`, `estimated_mean_abs_curvature_per_m`,
  `estimated_curvature_delta_per_m`, `confidence_near_mean`,
  `confidence_middle_mean`, `confidence_far_mean`.
- Prediction-time inputs may use only current or causal past estimator/vehicle
  state. Never use residuals, future values, RLMB outputs, or
  pseudo-reference-derived quality as features.
- Fit standardizers inside training folds only. Held-out groups must not affect
  fitting, early stopping, restarts, transforms, or hyperparameters.
- Current primary evidence is four technical recording groups from one
  same-day outing. It does not estimate independent-journey generalization.
- Never infer independent-outing count from MCAP count, filename numbering,
  directory count, continuous-block count, or technical recording-group count.
  Only the prospectively recorded physical-session declarations determine the
  outing unit. Read `docs/current_status.md` for the dated raw-data chronology.
- The frozen v0.15.4 planner-development model is K=1 with AR ceiling 0.99.
  This is a structural release of the binding 0.98 constraint, not a held-out
  performance selection. The failed v0.15.3 strict gate and reviewed 0.98
  reporting reference must remain visible.
- Generate residuals free-running over complete sequences: generated history
  feeds the next step and state resets exactly once per declared sequence.
  Independent frame sampling is invalid.
- Do not claim final model selection or planner benefit without the required
  independent data or completed planner experiment.
- RC-GAN is not pursued on the current one-outing corpus.
- The independently reviewed v0.16.2 audit is the final diagnostic on the
  current generated ensembles. Do not add an A4 arm, refit, seed sweep,
  planner-parameter sweep, or further post-hoc current-outing statistic.
- The next primary scientific evidence requires additional independent clean
  outings under a reviewed, locked final-data protocol. BMW-planner transfer is
  optional and separate; it requires confirmed interfaces and a new reviewed
  predeclaration and does not replace independent-outing validation.

## Implementation and artifact rules

- Prior version outputs are immutable inputs. New workflows validate exact
  file sets, schemas, and SHA-256 lineage before creating output.
- Write into a new empty versioned output directory. Fail before output on
  missing, extra, drifted, or tampered dependencies.
- Keep deterministic seeds and record them in summaries.
- Keep domain arithmetic, orchestration, I/O, visualization, and CLI adapters
  in their existing package layers.
- Generated `outputs/`, raw MCAPs, private configuration, and fitted model
  artifacts stay outside version control unless the user explicitly directs
  otherwise. Commit code, tests, contracts, and documentation.
- Do not silently change a reviewed scientific rule to make a gate pass.
  Preserve the failed result and declare any separate engineering decision.

## Verification and delivery

Run at minimum:

```bash
python -m compileall -q src tests

env PYTHONPATH=src \
  MPLBACKEND=Agg \
  MPLCONFIGDIR=/tmp/mpr-matplotlib \
  python -m unittest discover -s tests -t .
```

At v0.15.4 the expected baseline is 315 passing tests with two expected
optional-dependency skips. Treat a changed count as something to explain.
The corrected v0.16 reference-planner implementation raises this to 324 passing tests
with the same two expected skips. The reviewed v0.16.1 Gaussian-transfer
implementation raises this to 329 passing tests with the same two skips. The
v0.16.2 spatial-structure audit raises this to 339 passing tests with the same
two skips.
The v0.17.0 independent-outing intake raises this to 381 passing tests with the
same two skips.
The v0.17 data-arrival verifier and runbook raise this to 384 passing tests with
the same two skips. They add no model or current-data diagnostic. The first
real v0.17.0 audit is preserved but is not a successful cohort lock; read
`docs/current_status.md` before any v0.17.1 work.
The v0.17.1 schema-v2 compatibility implementation raises this to 402 passing
tests with the same two skips. Its implementation and real batch01 audit both
received focused independent `GO`. Batch01 contributes zero eligible outings;
do not rerun it or relax topology, H100/map-pairing, anchor, or causal-input
gates. Further evidence requires new prospectively declared physical outings.
The reporting-only output-driven model comparison raises this to 404 passing
tests with the same two skips. It does not authorize a model fit, a new metric,
or final model selection.
The v0.18.0 structural-feasibility implementation raises the suite to 432 tests
run: 430 pass and two expected optional-dependency tests skip. Contract and
implementation review returned `GO`, authorizing one private batch01 run. That
run exposed an exact RLMB descriptor binding defect (`RoadLaneSegment.id_` is
`uint64`, not `int64`) while independently observing zero sensor chains reaching
100 m. Preserve the v0.18.0 output unchanged. The narrow v0.18.1 correction must
receive focused corrective review before a rerun into a new directory. It does
not authorize threshold changes, target adoption, residual creation, model
reuse, a model fit, a planner run, or a figure.
The narrow v0.18.1 correction and takeover regression raise the suite to 434
tests run: 432 pass and the same two expected skips. Its 30 focused tests
include the observed `uint64` reference descriptor, fail-closed `int64` drift,
and a short sensor chain that remains ineligible despite valid reference
geometry and timestamp pairing.

The v0.18.1 corrective implementation and corrected real batch01 output have
now both received focused `GO` with zero blockers; Python 3.10/3.12 CI passes.
The accepted result remains zero sensor 100 m spans and zero synchronized
candidates, despite 9,235 reference-ready messages and 17,087 time pairs.
Read `docs/sensor_topology_batch01_v0181_result.md` and the first section of
`docs/current_status.md` for exact identities, verification limits and the
documentation closure. The earlier review-before-rerun instructions above
record gates already completed, not permission for a further run. The closed
batch stays negative; no horizon/rule change, residual construction or new
scientific execution is authorized. The user decides whether to merge PR #20.

Do not push, merge, open a pull request, or modify external systems unless the
user asks. Deliver repository changes as a ZIP patch batch containing a
`README.md` and numbered `git format-patch` files. The user's download location
is `~/Downloads/MPR`; always include `unzip <bundle>.zip` before `git am` in the
instructions.

## Code review rules

Flag any change that:

- changes the H100 grid, residual sign, feature order, or free-running contract;
- introduces held-out leakage or selects hyperparameters from held-out metrics;
- treats technical groups as independent journeys;
- hides a failed gate or upgrades development evidence into a final claim;
- changes a prior artifact instead of adding a versioned consumer;
- invents an unavailable BMW interface or reports planner benefit without an
  executed, predeclared planner evaluation.
