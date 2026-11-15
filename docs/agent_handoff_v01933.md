# Agent handoff for v0.19.33

Start with this file and
[temporal_planner_replication_v01933.md](temporal_planner_replication_v01933.md).
PR 56 is merged and its owner temporal pilot is accepted. The original six
matched development configurations are fitted. Spatial planner replication
is complete. Comparative temporal pilot findings and their interpretation
are in the accepted private assessment. Keep every baseline, including zero
disturbance, in the replication. Private evidence, results, plots and input
digests are retained outside public Git.

The current candidate implements the prospective temporal replication across
the original frozen development folds. It requires pilot parity before any
other outing is sampled and separates the six new outings from the pilot in
equal outing summaries. No refit, new feature, new recording or parameter
tuning is included. Exact rules and evidence limits are in the protocol.

Architecture:

* domain/temporal_planner_replication.py verifies score arithmetic, computes
  the fixed block and sequence length diagnostics, and aggregates outings.
* io/temporal_planner_replication.py reads the bounded pinned pilot and reuses
  complete native temporal lineage validation once before restoring all folds.
* workflows/temporal_planner_replication.py preflights every fold, scores the
  pilot and checks parity, then scores the remaining folds and packages results.
* The v0.19.32 scoring, affine maps, clock/support policy, native samplers and
  evidence readers are reused without modification. New tests cover unequal
  weighting, exact epoch binning, secondary missingness, state restoration,
  fail closed parity, native lineage errors, output protection and drift.

The private packet contains a sealed replication manifest, helper, prospective
assessment, reviewer checklist, validation record and exact owner commands.
Manifest preparation can verify accepted numeric archive bytes, original row
identities and saved model states without reading new temporal outcomes. A
complete native owner preflight still requires the intact registry and original
experiment folders. The local copy's missing registry objects are documented
in the private validation record; do not weaken that check to make it pass.

Review source, protocol and the exact private packet, verify CI on the actual
head, merge, then run preflight and the owner replication. The helper's output
defaults to a sibling of its packet. Preserve failed directories and partial
archives. Return the new ZIP and its SHA256 privately for result review and
Python plots. Preflight alone does not reproduce pilot scores.

After accepting the result, decide which model candidates support a separate
planner tuning experiment. Statistical forecast quality, temporal coupling
benefit and improved parameter selection are separate claims. Freeze the
tuning objective, candidate parameter space, baselines and validation split
before running it. Additional recordings need intake and role checks; final
reservations remain unexposed. Keep target funnels separate.

Update README, AGENTS, current status, modeling plan and the newest handoff
after every implementation, review and accepted return. Earlier checkpoints
remain historical evidence, with this header controlling the next action.
