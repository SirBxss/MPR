# Agent handoff for v0.19.32

Start with this file and
[temporal_planner_pilot_v01932.md](temporal_planner_pilot_v01932.md).
The original six matched development configurations are fitted.
PR 55 is merged and the owner spatial replication is accepted.
The private evaluation package holds its measured results, Python plots
and per outing diagnostics. The source tree holds no private results.

The next candidate implements a single outing temporal engineering
pilot. It carries incremental planner state across exact recorded
sequence intervals and compares frozen AR forecasts with controls that
preserve each frame's spatial profile ensemble. Read the protocol for
the command score, lateral state eligibility, clock assumptions and
finite permutation limits. Keep the original data and model states.

Modules are domain/temporal_planner_pilot.py for support, affine maps,
state propagation and scores, io/temporal_planner_pilot.py for restoration
after native evidence replay, and workflows/temporal_planner_pilot.py
for the owner operation. The existing model samplers and evidence
validators are reused. Tests cover direct native affine cancellation,
exact clock differences, preservation of whole profiles, score
arithmetic, native model restoration, preflight and output protection.

The private packet contains the exact sealed manifest and owner helper.
Its preflight requires the original intact registry, original sealed
experiments and the accepted one state and spatial result archives.
The main agent reconstructed pilot support from the accepted scenario
cache and restored its real model states without scoring real inputs.
The agent's registry copy lacks required objects for full native replay.
Owner preflight is therefore part of acceptance.

Next review the code, protocol, sealed manifest and helper, verify CI at
the actual head and merge. Then run preflight followed by the single
owner pilot. Return the new ZIP privately. If execution fails, preserve
the terminal log and output before deciding whether to reissue a run.
The default output is outside the packet to avoid the manifest directory
guard that blocked the first replication preflight.

After result acceptance, decide whether the temporal coupling contrast
merits a prespecified outing replication. Independent final reservations
and prospective additional recordings retain their earlier roles.
A planner tuning study requires a separate objective, parameter space
and validation split. Target funnels remain a future extension.
