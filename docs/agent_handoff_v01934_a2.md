# Start here: v0.19.34 a2 handoff

Read [a2 protocol](planner_parameter_selection_v01934_a2.md), README's newest
header and [completion roadmap](thesis_paper_plan_v01934.md). A1 PR 58 is open,
not merged. Its exact-head CI passed, but independent review blocked its
scientific design before new BMW parameter outcomes. A1 must not be run. The
six original matched models remain fitted; accepted spatial and short temporal
development replications remain valid. Private results stay outside public Git.

A2 is a source delta on the same PR head. It revises the controller family,
nominal tasks/normalization, feasibility and diagnostics; it preserves frozen
model/data lineage and samplers. It adds a genuine synthetic decision fixture
and an owner training-metadata stage that can stop before real model draws or
held scoring. Read every stop rule; a non-informative result is not model failure.

Architecture:

* domain/planner_parameter_selection.py: fixed protocol, native Riccati maps,
  total/nominal/law rollout decomposition, increment and total exceedances,
  outing-mean nominal gate and passive-control probes, choice/held summaries.
* domain/planner_parameter_design.py: metadata-only nominal summaries, exact
  synthetic Gaussian risk, quadratic maps, variable-length block flip bounds,
  fixed-seed 64/32 decision fixture and per-fold readiness/stop classification.
* workflows/planner_parameter_selection.py: unchanged full native ancestry,
  preflight mode, all-fold design barrier before any real sampling, design-only
  output, fail-closed non-informative result, all choices before held replay,
  preserved exclusive outputs and drift/hash checks.
* io/planner_parameter_selection.py is unchanged. Both flow solver pins and all
  six frozen configurations remain native. No archive-only fallback is allowed.
* Tests cover native command/rollout parity, exact quadratic covariance traces,
  variable-length operator bounds, decomposition even with biased residuals,
  unsaturated zero-law tails, outing mean versus single-context veto, practical
  tie/magnitude rules, deterministic sensitivity, design stop and freeze barriers.

Private packet contains the delta, reissued manifest/helper, validation evidence,
review checklist, Python synthetic figure and exact owner commands. No real
model fitting/draws, real metadata design results or held outcomes have been
produced during implementation. The prior workspace was pruned; source and
private packets were recovered from Git/retained files. Private owner native
preflight remains mandatory. Do not recreate missing registry objects or weaken
checks to claim a pass. Synthetic tests are not an owner experiment.

Owner sequence: apply a2 on the same branch; compile/tests and synthetic helper;
push to PR 58; focused Claude source/protocol/private helper-manifest review;
new actual-head three-job CI; owner merge; clean tree/runtime check; native
preflight; design-only return. If design-ready under the reviewed protocol,
the full study repeats the design barrier before sampling. If not ready,
return its ZIP and stop with no real draw or held exposure. Review before any
new redesign. Outputs are fresh siblings of the packet, never inside prior
manifests or source. Preserve failed and historical attempts.

On a completed study, verify full archive and source/manifest pins, every
readiness condition, context/gate arrays, choices and freeze hashes, all
quadratic decompositions, increment versus total indicators, held nominal
violations and primary/secondary contrasts. Produce plots using Python. Do not
claim safety, physical replay, universal family superiority or significance.
The zero-law contrast includes noise awareness; structural model comparisons
are secondary. Training selection is in sample followed by outer validation,
not independent inner cross validation. Shared seeds/folds limit independence.

Four work packages remain, with the first two bundled: answerable planner
selection; robustness/claim audit; independent final validation/data quality and
role freeze; thesis/paper synthesis, with writing in parallel. Nine additional
reported recordings stay prospective. Reference quality and independent groups
must be established before assigning any training/final role. Target funnels
remain separate. Update README, AGENTS, current status, modeling plan and newest
handoff after each implementation/review/accepted return.
