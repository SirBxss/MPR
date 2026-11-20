# Agent handoff for v0.19.34

**Historical a1, superseded and not authorized for execution.** Read the
[a2 protocol](planner_parameter_selection_v01934_a2.md) and
[a2 handoff](agent_handoff_v01934_a2.md). The review blocked the a1 design;
its old helper must not be run. The text below preserves that design history.

Start here, then read [protocol](planner_parameter_selection_v01934.md) and
[roadmap](thesis_paper_plan_v01934.md). PR 57 is merged and its owner temporal
replication return is accepted. The original six matched configurations are
trained. Spatial and temporal development replications are complete. Private
acceptance evidence includes the source independent assessment, Python plots,
negative subgroup findings and prospective next experiment plan. Keep the
full evidence, not just the favourable headline. These are development
results; independent final validation and planner tuning benefit remain open.

This implementation adds prospective parameter selection for the existing
local affine planner. It uses all six frozen models plus zero disturbance,
empirical and fixed planner baselines. It selects only on training outing
contexts, freezes all fold choices, then assesses observed held sequences.
The parameter grid, recovery states, loss and shared nominal tracking
requirement are fixed. Monte Carlo and nominal requirement sensitivities are
bundled into the same bounded run. No real model draws or new parameter
outcomes have been computed during implementation. No parameters are adopted.

Architecture:

* domain/planner_parameter_selection.py declares the complete protocol,
  candidate grid, exact native affine control maps, recovery rollout metrics,
  training context selection, nominal probes, choice and held summaries.
* io/planner_parameter_selection.py replays native development flow ancestry
  once, verifies the accepted complete return and restores both Gaussians,
  both AR laws and both flows, including accepted solver calibration pins.
  It binds the accepted temporal checkpoint and original state ancestry.
* workflows/planner_parameter_selection.py preflights every original fold,
  verifies sealed metadata and native sampling budgets, runs a synthetic
  native parity/negative control screen, generates each arm once per fold,
  writes all choices, then evaluates held candidates and packages results.
* New synthetic tests cover direct native control and rollout parity, temporal
  clocks, task averaging, training only support, nominal feasibility, ties,
  prefix reuse, all six restored laws and samplers, no lineage fallback,
  preflight with no solving, freeze ordering, source drift, output protection,
  failed sampling/held scoring and changed choice detection.

The private packet contains the source patch, pinned manifest, runner, owner
commands, review checklist, preparation provenance and validation record.
Manifest preparation verifies accepted ZIP bytes and frozen states and derives
indices from accepted sequence metadata without new model draws or tuning
outcomes. It cannot replace full native owner preflight. The local cached
registry is incomplete; do not bypass a missing object error. Review the
private validation record for exact completed and unavailable checks.

Next action: independent review of source, protocol and exact private helper
and manifest; CI on the reviewed head; owner merge; owner preflight; one owner
study. The output must be a fresh sibling of the packet. Preserve failed
outputs and partial ZIPs. Return the full result ZIP and SHA256 privately.
Analyse all predeclared outcomes and create plots with Python. A completed
run can legitimately fail the descriptive rule. Do not change its scoring.

After accepting the return, decide whether the evidence supports a useful
parameter selection contribution or only a modelling/response contribution.
Freeze models, selector and data roles before any independent final exposure.
New long recordings still require provenance, reference quality, overlap and
condition checks. Their number alone does not establish independent evidence.
They must not be quietly pooled into training. Final candidate fitting and
independent evaluation, if needed, require a separate reviewed design.
Target funnels stay outside this thesis completion path unless the owner and
supervisors explicitly revise the scope.

Update README, AGENTS, current status, modeling plan and the newest handoff
after every implementation, review and accepted return. This header controls
next actions; earlier checkpoints are historical. Never publish private BMW
results or confuse synthetic tests with an owner experiment.
