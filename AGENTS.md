# MPR agent instructions

These instructions apply to the complete repository. MPR is the canonical
implementation for the thesis; LEEM is historical reference material only.

## Start every task here

1. Read `docs/current_status.md` for the exact stopping point and next task.
2. Read the relevant contract before changing code:
   - `docs/modeling_plan.md` for scientific gates and phase decisions;
   - `docs/output_contracts.md` for exact artifact schemas;
   - `docs/architecture.md` for ownership boundaries;
   - `docs/commands.md` for supported entry points.
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
