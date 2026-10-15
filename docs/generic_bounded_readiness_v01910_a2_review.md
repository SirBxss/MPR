# PR #35 a2: independent evaluation and narrow correction

Date: 2026-10-15. Claude reviewed head
`b11459adea73452f02b10f5acba8cf6f99f4473e`, tree
`16acf58fa565650c6a2ee1a3fd5bcec4ef9e28b0`, parent/main
`0f2950e2b76b823fabea0b67309b268afe205806`. Codex independently verified
these GitHub identities; PR #35 is open/unmerged. The original supplied review
is preserved unchanged in the delivery ZIP, SHA-256 `cbd0223bb29b78f870ffb1757f0a256e897667ddcdfcfc393d9d70b7c52e3359`.

## Decision and reproduction

Claude's NO-GO is justified. The pinned `project_point_to_path` can reject an
ambiguous projection with `reference_alignment_projection_ambiguous`.
`_h100_geometry` prefixes it as `h100_reference_alignment_projection_ambiguous`.
The new exclusive classifier omitted that existing label, throwing
`scientific_attrition_unclassified_failure` and nulling the recording's science.
An expected pair rejection must instead be counted in `common_h100`.

Codex reproduced this using unchanged geometry and a reference fold with two
arms equally close to an EDP footpoint. A real synthetic Protobuf/MCAP fixture
has one ambiguous pair and one normal pair. Before the fix, the sink raises the
unclassified-label error and the actual workflow publishes exit 3. After the
fix, the workflow publishes a complete exit-0 report, one common-H100 rejection
and one complete-condition frame, with unchanged full-stream integrity evidence.
Actual private trigger frequency is unknown; no private raw was accessed.

## Changes and optional suggestions

| Review item | Evaluation and action |
|---|---|
| B-1 | Add precisely the existing projection code to the static pin. Preserve protected arithmetic and classify the resulting H100 label at the existing common-H100 stage. |
| O-1 | Add an AST regression over the full pinned geometry/pairing/alignment/condition/motion and condition-I/O modules. Every literal coded exception must be pinned or explicitly accounted for. Four exact residual-only sites have written exclusions; the existing nonfinite-feature literal has its explicit condition entry. This is a conservative module sweep, not a complete automatic call-graph proof. Production classification remains static; unknown labels still null science. |
| O-2 | The canonical runbook now applies this delta on the existing PR branch. A clean branch exactly at the reviewed base is an apply path, including after `git am --abort`; a completed identical correction is repeat-safe. Differing work stops and is preserved. |
| O-3 | Confirmed with weak references: the last payload and path remained alive at matching entry. Clear the loop reference after ingestion. The strengthened inherited test checks release before matching, not only after return. Empty input remains supported. |
| O-4 | Valid benchmark limitation. Existing maximum-budget evidence uses two-point staged paths and excludes conversion/decoding. It proves neither realistic finalisation cost nor private deadline adequacy. No new performance claim is made by this classifier correction; a more representative stress profile remains follow-up work. |
| O-5 | Use local scratch outside synchronisation/backup activity for the private pilot. Preserve the unexpected-file guard and resource floors. Prior sidecar creator remains unproven. |
| O-6 | Directory fsync is a reasonable durability enhancement, outside this narrow correction. Atomic publication remains unchanged; crash/power-loss durability is not established. |
| O-7 | The map identity label remains unreachable after the all-version precheck. No contract cause or unreachable failure policy is changed in this delta. |
| O-8 | Actual private descriptors are unavailable here. Do not infer conformance from fixtures. Preserve per-version binding observations in the one future pilot; descriptor-only checks can use privately available preserved bytes. |

## Exact-head CI independently checked

[Run 38725711604](https://github.com/SirBxss/MPR/actions/runs/38725711604)
passed at the original head. Codex read both authenticated job logs:

| Job | Runtime | Exact log result |
|---|---|---|
| [116390925161](https://github.com/SirBxss/MPR/actions/runs/38725711604/job/116390925161) | Python 3.10.22 | 700 run, 698 pass/two skips, 84.488 s |
| [116390925521](https://github.com/SirBxss/MPR/actions/runs/38725711604/job/116390925521) | Python 3.12.15 | 700 run, 698 pass/two skips, 53.818 s |

Both logs check out `14c7e3e0c035b9deb7a52a4de84a9f81bba64073`.
GitHub's Git object confirms parents `0f2950e` + `b11459a` and tree
`16acf58fa565650c6a2ee1a3fd5bcec4ef9e28b0`, identical to the reviewed head.
This resolves the reviewer's CI-access limit. It does not cover a2.

## Local verification and next checkpoint

New regression tests were first run against the old implementation and failed
for B-1 and O-3. The correction adds three test methods (703 total; two existing
opt-in skips). The delivery's `VALIDATION.json` pins the final committed-source
suite and distinguishes actual tests from intercepted shell-command simulations.
It also records actual ZIP/manifest/patch/README checks, which Claude could not
perform because the original ZIP was absent from that review session.

Apply/test/push this numbered correction using the
[canonical same-PR runbook](generic_bounded_readiness_runbook_v01910.md).
Focused a2 GO and exact new-head Python 3.10/3.12 CI precede merge and the one
new counts-only pilot. Do not reapply PR #34 or the initial implementation.
The unchanged data-completion plan is: measured pilot yield, generic numeric
export/strict archive validation, then evidenced independent sessions/splits
and existing gates before real training. No private yield, new dataset,
physical ground-truth claim, raw deletion or fit is established here.
