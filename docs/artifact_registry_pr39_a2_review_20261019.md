# PR #39 a2 review evaluation

The reviewed owner head is `83fdd5491b8f1980dfc63f4664363923812ed5b6`,
tree `12791e0b053f409f094971f2089bc2e48a715ead`, with base main `734876b`.
Claude's NO-GO for that head is supported. Both blockers and the contradictory
declaration, constructible flag and output-traversal findings were independently
reproduced before correction. This delta belongs on the same PR, with no new
documentation prerequisite, private rerun or scientific-rule change.

| Finding | Evaluation and a2 action |
| --- | --- |
| B-1 shared source locator misses exclusion | Confirmed. Exact non-null source recording IDs and canonical-JSON locators group different raw digests; linear possible raw links carry both declaring specification pins. Reservations propagate in either direction and transitively, including through later confirmed sessions. No locator/session node or independence is inferred. |
| B-2 installed-own producer becomes a replay dead end | Confirmed. Adopted option (a): `REVIEWED_NUMERIC_PRODUCERS` is the explicit durable tuple, currently only reviewed `45f1f96…`. Installed-own archives are rejected before a snapshot exists. Synthetic fixtures explicitly patch the tuple; production never trusts its own fingerprint automatically. Reviewed-producer replay/update is tested across a simulated consumer release change. |
| S-1 contradictory source-declared sessions | Confirmed. Contradictions block the possible component and selected dataset, retaining both source assertions. |
| S-2 constructible admission flags | Confirmed. Both frozen dataset dataclasses use `field(default=False, init=False)`; construction/replacement cannot set the flag and admission methods still raise. |
| S-3 output path creates stray directories | Confirmed. Traversal and symlinked parents fail before any directory/lock side effect. |
| S-4 marker provenance/durability | Addressed. Sync object/output/parent directory entries before the marker, recheck the source immediately before it, retain creator fingerprint, then sync the marker/output/parent. Failed publication preserves prior snapshot bytes. |
| S-5 failed external attempts | Added optional pinned `numeric_attempt` registration reports. Inconclusive summaries require their adopted authorization event and matching identity/readiness pins; a missing external record fails before publication. Attempts retain reservation/attempt evidence and never imply complete publication or a dataset. Unlisted external files cannot be discovered automatically. |
| S-6 system-temp residual copies | Addressed. Replay uses private temporary directories adjacent to the snapshots. A killed process can leave them inside the private area; no automatic eviction is added. |
| S-7 raw path guard | Addressed for normalized and directory-resolved candidate paths, both canonical and specification raw paths, and case-insensitive raw extensions. All declared raw paths are collected before reports/archives are read. Raw endpoints are never resolved/statted by the guard. An unreported hardlink identity cannot be proved without raw metadata access; no stronger filesystem-isolation claim is made. |
| S-8 dataset session unknowns | Added immutable `session_state_by_raw`, including absent evidence, unresolved/conflicting state and both declared-ID views. Absence is never interpreted as independence. |
| S-9 unrelated strict JSON | Existing fail-closed policy retained and documented, with a regression for unrelated duplicate-key JSON. All lowercase `*.json` are parsed; other suffixes and external files need explicit pins. |
| S-10 capacity concern | Not a reproduced defect. Byte/memory/time caps remain fixed and are documented independently of outing-count requirements. The private acceptance measures actual object and array bytes; future bulk intake must check its actual size rather than assuming any seven archives fit. |

The graph, archive reader, snapshot I/O and their tests change; the five accepted
scientific source files, historical archive consumer, numeric artifact schema,
feature arithmetic/order, admission defaults, clock guard, raw-reader limits,
flow/model code and real-fit gates remain unchanged. A1 snapshot marker schema
was an unmerged candidate; a2 adds creator provenance and derived row fields.
No operational a1 snapshot is migrated or erased by this delta. If one was
created outside the reviewed workflow, preserve its digest and reconcile it;
do not cold-rebuild to discard history.

## CI and verification scope

Authenticated logs for original-head run `39232003310`, jobs `117991936743`
and `117991936261`, show Python 3.10/3.12 each **814 run, OK, skipped=2**.
Both check out merge `45e5b8084b3d6037beaf687f414582ca126b5ab8` with the
reviewed head tree. This resolves Claude Q-4's original CI-count uncertainty;
it is not evidence for the corrected head. Local correction checks and private
raw-free acceptance are retained in the delivered evidence. Focused a2 GO and
exact pushed-head matrix CI remain required before merge.

Local Python 3.12.14 with MCAP 1.5 passes compileall, **45 focused tests** and
the full **833 run, OK, skipped=2** suite. The increase is 19 regression tests
over a1. Unchanged-science byte/AST and historical-consumer regressions pass.
The new raw-free acceptance also imports the complete returned collection's
registration/report metadata alongside the existing accepted numeric archives.
Its actual object/input/array sizes remain below the unchanged limits; exact
private measurements stay in the handoff.

The original private returned-archive and native-controller evidence is included
in the corrected private handoff for independent inspection. New archive
acceptance replays the already published reviewed-producer archives, verifies
matched rows/resets and immutable inputs, and guards raw opens/stats. It does not
recompute private raw science, create consent or train a model. Native counts
controller code and accepted frozen producer are unchanged by the correction.

## Qualifications that remain explicit

Q-1 is correct: the integration release's exporter does not accept readiness
from an arbitrary older integration release. New exports from already successful
reviewed-producer readiness must run that compatible immutable producer. Do not
rerun readiness or edit its source pin to avoid compatibility checks. The durable
registry allowlist is an archive-consumer policy, not a relaxed exporter policy.

Q-2 is correct: history protection is scoped to the project private root and
contract. A different checkout, moved/deleted history or a new contract is not a
global reservation ledger. Retain external registry digests and require anchored
lineage in the later cohort consumer; never rebuild elsewhere to clear exposure.

Q-3 is correct: unresolved/absent session evidence may be inspected in an
engineering dataset view but grants no physical outing, final candidate, role
or model admission. The owner completed the fixed counts collection; keep all
complete/inconclusive evidence and plan only a reviewed failed-stage successor.
The source-clock/prediction-epoch question, confidence/producer assumptions,
physical-session evidence, cohort/split integration and existing flow/fit gates
remain separate. No bulk opt-in, raw move/deletion or private model run follows.
