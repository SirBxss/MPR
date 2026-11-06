# Agent handoff for the spatial planner benchmark

6 November 2026. The matched development model comparison after PR 51 is
complete. Private results and exact pins are in the owner analysis handoff.
The accepted original speed definition and short support are still in use.
Older prospective status entries below the current headers are historical.

v0.19.28 adds the synthetic spatial planner benchmark described in
docs/spatial_planner_v01928.md. Its first decision API remains compatible with
the earlier temporal planner studies. The optional horizon trace and affine
response are verified against the same solver. The CLI has no recorded data
input. It uses native synthetic Gaussian and flow states, fixed seeds,
Heun 128, and a separate synthetic replay set. Preserve legacy planner runs,
the matched model artifacts and all reserved outings.

The next recorded experiment needs a predeclared matched replay protocol and
a row identity join for validated nominal geometry, initial state and speed.
Freeze outcomes and scenario selection before opening planner results.
First compare nominal, recorded replay, empirical resampling, Gaussian
controls and unconditional flow under a fixed planner. Analyse per outing.
Keep temporal models, parameter tuning and uncertainty-aware target funnels
as distinct experimental questions. No direct speed adoption or long temporal
claim follows from the synthetic benchmark.

The newly downloaded recordings remain prospective. Keep the existing
locations and declare only the intended IDs. Separate geometry-only continuity
from complete-condition continuity. Protect independent test groups before
model or planner tuning. Keep private paths, data and result details out of
the repository. Update README, AGENTS, current status, modeling plan and the
dated handoff with the next implementation and outcome.
