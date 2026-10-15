# PR #34 a3: consumer-required binding correction

Date: 2026-10-13. Status: **DRAFT; focused R1 delta GO pending**.
No scientific implementation or private execution is added.

Claude reviewed a2 at `8d5c19e05b037a25f94e1a99e55ee9a5afd6cb9a`, tree
`40315385eb39d20366d78d5778ae3bab51bde30c`, and returned NO-GO only for R1.
B2–B5, the EDP generation rule and the prior optional resolutions were accepted.
Their publication, cascade, resource and lineage choices remain fixed. The
[a3 draft](generic_recording_readiness_v01910_draft.md) supersedes a2 only at
the additional consumer-binding boundary; it is not yet accepted.

## R1 decisions

- Require a complete descriptor path for source time in both EDP and RLMB.
  Preserve the pinned aliases, presence/ordering and value-dependent fallback;
  declared selectable nested paths must be complete and compatibly typed.
- EDP additionally requires the declared topology enum and SENSOR symbol.
  This consumer gate is separate from unchanged structural-v1/exact-file-hash-v2
  generation classification; its new cause is
  `estimate_descriptor_fields_unsupported`.
- RLMB requires repeated lane segments, integer IDs, an explicit ego-designation
  route and complete **direct drive-path** vertices/range bindings. Paired
  boundaries cannot substitute because the pinned unique ego path and successor
  chain require `geometry_source == "drive_path"`.
- Keep successor indices optional: a single direct ego segment can already
  cover H100. A short segment without a successor retains the existing terminal/
  coverage failure; no chain or extrapolation is invented.
- Validate any declared optional pool/range entry that the converter can read,
  including x/y/distributed means and integer start/size. Another complete path
  cannot hide malformed declarations. Optional undeclared metadata stays optional.
- RLMB generic conversion labels remain data **after** a complete descriptor
  precheck; the old converter cannot infer late binding from those labels.
  EDP distinguishable binding failures retain their specific cause and the
  fixed unsupported-estimate recording code. Whole-recording null/exit-3 policy
  and reconciled container evidence remain the accepted a2 rules.

The draft adds prospective R1 structural/data fixtures and a maximum-budget
MEMORY-temp staging benchmark to required **post-GO implementation evidence**.
No new binder or private scan is implemented to obtain contract GO. Existing
converter probes explain the issue; they are not the new consumer.

## Public application instructions close O11

[The canonical runbook](generic_recording_readiness_contract_runbook_v01910.md)
is now in this PR. Its complete tested application/push commands are also the
delivered `README.md`; Claude can review them directly from Git without a
separate attachment. The bundle contains its snapshot `EXPECTED_TREE.txt`,
exact parent, numbered patch and checksum manifest. Snapshot-specific metadata
is outside the runbook so its own tree/patch hash is not circular.
Application checks manifest, exact reviewed parent, corrected tree, clean state,
Markdown-only diff and unchanged scientific/config/historical-contract paths.
The same-PR branch is selected automatically; no reset or force push is used.

## Codex-verified a2 CI

[Actions run 38409957807](https://github.com/SirBxss/MPR/actions/runs/38409957807)
passed for reviewed a2 head `8d5c19e`. Python 3.10 job `115339336541` and Python
3.12 job `115339337152` each ran 650 tests, 648 passes/two existing skips.
Codex inspected both logs: they checked out temporary merge
`9f6e5acf7337a1f1dd5346994f2531e128e6e9ef`, parents `12ddee6` + `8d5c19e`,
with the same a2 tree above. This resolves the reviewer's API-access uncertainty;
it does not override R1 NO-GO or certify the forthcoming a3 head.

N1 uses Codex-verified wording. N2 makes unexpected scratch-file exit 3 explicit.
N3 adds prospective maximum-budget memory evidence. N4 preserves reference time
pre-extraction on geometry failure. These do not reopen the accepted a2 choices.

## Owner and next-agent action

Apply the correction to exact a2 head `8d5c19e` in the same PR #34 branch,
test and push normally. Provide Claude this PR, the original a2 review, a3
draft/record and public runbook for R1/runbook-only delta review. Provide the
new-head CI link and actual checked-out merge identity separately. Do not mark
the draft frozen or merge/start implementation before focused GO and CI.
Preserve all prior results and registered raw paths; no scans, migration,
deletion, numeric export, real fit or outing lock follows from this correction.
