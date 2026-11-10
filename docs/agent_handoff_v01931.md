# Agent handoff for v0.19.31

PR 54 is merged and the owner recorded spatial pilot was accepted.
Preserve the accepted aggregate pilot and its original scenario and
model artifacts. The current candidate implements the frozen extension
in [spatial_planner_replication_v01931.md](spatial_planner_replication_v01931.md).
The private packet includes the sealed manifest and owner helper.
Source and exact manifest review and CI on the reviewed head precede
owner merge and scoring.

The preflight restores the original cached experiment, validates all
seven held archive and model bindings and computes support without
scoring. The owner run first requires numerical parity with the accepted
pilot. Then it scores the six previously unscored folds and publishes the
seven outing and six outing summaries separately. If a run stops,
preserve its terminal output and any partial evidence before deciding
whether to reissue it. Keep the reviewed manifest and its pins private.

The main agent restored the real saved models across every fold without
sampling and tested the synthetic end to end path. The local registry
copy lacks required objects for native preflight. The owner preflight
must use the original intact registry and sealed experiment. The six
replication outcomes await the owner run.

After accepting results, compare the empirical, nominal and learned
arms across individual outings and secondary metrics. Treat differences
as development evidence. A later temporal or planner tuning experiment
requires its own protocol and evidence gate.
