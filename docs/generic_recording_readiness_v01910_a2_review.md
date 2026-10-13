# PR #34 a2 contract amendment and review handoff

Date: 2026-10-13. **Historical a2 proposal:** its review at `8d5c19e`
accepted B2–B5 and EDP generation, but returned NO-GO for R1 consumer bindings.
[a3 supersedes this proposal](generic_recording_readiness_v01910_a3_review.md);
focused R1/runbook delta GO and a3 CI remain pending.
No scientific implementation or private execution is added.

Claude reviewed a1 at `88b889af642837d00c477edbadea7b3dbbc4a4c9`, tree
`5bc290a127ed67142c9b722f3c200af242a493b4`, and returned **NO-GO with five
documentation blockers**. The attached independent review remains immutable.
The [a2 draft](generic_recording_readiness_v01910_draft.md) supersedes a1;
these are proposed resolutions, not a claimed reviewer GO.

| Finding | a2 resolution |
|---|---|
| B1 scientific binding | Classify every selected channel/schema before payload science; retain structural v1 and exact root-file-descriptor v2 allowlist; mixed unsupported E/R nulls whole-recording readiness, retaining reconciled container evidence. Explicitly differs from old row-level zero accounting. |
| B2 odometry poison | Complete geometry can publish with exit 0, but explicit `unavailable_odometry` and false recorded-input causality flags. Global unavailable label rejects all condition candidates; zero support is not measured zero yield. |
| B3 exclusive cascade | Coverage/projection precedes anchor; exact static-code partitions and matcher denominators reconcile. First emitted condition cause is primary except explicit global odometry unavailability; overlapping inherited diagnostics stay separate. |
| B4 scratch | Require exactly 18.5 GiB initially, 10 GiB during processing; freeze two disposable journal-free DBs with MEMORY temp storage and the existing 4 GiB address-space cap. Unexpected disk sidecars stop and count toward the total. |
| B5 lineage | Type-preserving exact fresh inventory/decode equality is fatal exit 2/no report on mismatch. Late raw/metadata/predecessor-byte mutation invalidates with exit 3 and detection-order first-cause handling. |

O1–O3 and O5–O10 are addressed: log-time causality only; existing bounded
in-memory scalar matcher reused; detection-order invalidations; private clock
endpoints; safe phase timings/checkpoint RSS and one shared deadline; exact
storage order; advertised selection/caps before hashing; odometry wording;
current-status preamble restored. For O4, retain existing collapsed qualifier
codes so the paired-failure partition remains exact; do not introduce sub-codes
that change that equality. For O11, supply the **delivered README.md** as an
attachment alongside the PR during delta review; the correction bundle includes
that README, its checksum manifest and the application-guard validation.

## CI identity independently verified

GitHub Actions [run 38399401770](https://github.com/SirBxss/MPR/actions/runs/38399401770)
is successful for reviewed head `88b889a`. Python 3.10 job `115302831520` and
Python 3.12 job `115302831804` each ran 650 tests with two existing skips
(648 passes). Both logs checked out temporary merge
`4a1f3330b65fb210c5a25bca5dd94995d3b1b530`, whose parents are `12ddee6` and
`88b889a`; its tree equals the reviewed head tree above. This resolves the
reviewer's API-access uncertainty, **not the five contract blockers**.
It does not certify CI for the new amendment head.

## Owner and next-agent steps

Apply the numbered correction patch to exact head `88b889a` in the **same
PR #34 branch**, run its README checks and push normally. Supply the PR link,
amendment draft/record, original review and delivered README for focused
B1–B5 delta review. Require new-head Python 3.10/3.12 CI and contract GO before
merge or implementation. Keep actual review/CI/merge identities distinct in
future status updates; do not retrospectively mark a1 accepted.

No successful private registration/inventory/decode is repeated by this patch.
No registered raw path, immutable artifact, historical contract/adapter,
scientific population/feature/sequence arithmetic, model or raw-retirement
state changes. The next scientific implementation remains the bounded counts-
only consumer after contract GO, not the old whole-summary readiness route.
