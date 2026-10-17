# PR #36 a2 acceptance and next pilot handoff

Checked: 2026-10-16. **GO, zero blockers; exact-source CI verified.**
PR #36 is still open/unmerged at the check. No further code correction or
documentation patch is required before the owner merges the accepted head.
This continuity record is reserved for the next implementation.

## Accepted identities

| Item | Identity |
|---|---|
| PR | [SirBxss/MPR #36](https://github.com/SirBxss/MPR/pull/36) |
| Reviewed/pushed head | `03a9d77cd8b3f3ffdb3c990ef902f4fdef4ff7e3` |
| Reviewed/pushed tree | `c9600a05e0436393099496689c19b6149dc0154f` |
| Exact parent | `132e2e5d4f003a1693ac255f75539869ac8ab0e5` |
| Main at check | `4cf0af37ffad05e34b632571ec271485d6de50c3` |
| CI test merge | `07a6a4cc71a50c9030cf774154d25b767b762e76` |
| Test-merge parents | Main `4cf0af3` plus reviewed head `03a9d77` |
| Test-merge tree | `c9600a05e0436393099496689c19b6149dc0154f`, equal to reviewed head |
| Delivered a2 ZIP SHA-256 | `a52177b433523732fd2a8c06821fefe20071ee68a7d7e5aea3ae7f23b1fb7b0c` |
| Claude GO review SHA-256 | `62db71bbf71eb85535dd53aaf65b911668d5e2f2446f84aa2404887e20548327` |

The local format-patch commit `95ae7a6` and owner git-am commit `03a9d77`
have the same parent and source tree. Their different commit IDs are expected.
The actual post-merge main commit must still be verified; the temporary CI
merge ID is not a future main-merge identity.

## Review evaluation and CI closure

Claude's a2 GO is supported. The reviewer received and checked the actual a2
ZIP, all 24 members/manifest, a1 delivered bytes, patch/application/base/tree,
original private result/descriptor evidence and the portable reproducer. Codex
also reconfirmed the a2 ZIP checksum/manifest and pushed tree.

B-1 is closed for counts-only readiness: actual extension-aware descriptor
evidence declares interface 2.3, required model parameters, no removed optional
or validity binding, unchanged consumed geometry fields/units, and nonzero
NO_ERROR/KEEP_LANE/SENSOR enum values. The argument retains one explicit
assumption: BMW followed its major-version policy. This is not an independently
retraced deployed producer or an exhaustive old/new descriptor diff.

B-2 is closed: only bounded readiness enables the second fixed root; shared
defaults remain original-pin/structural legacy. The real historical technical
inspector regression cannot admit the new root under old cohort-lock lineage.
Historical workflows/contracts/verifier/import graphs and scientific rules
remain unchanged. No raw recorded payload or private scientific successor was
run during this acceptance check.

The remaining CI-log prerequisite in Claude's review is now resolved. Codex
read the authenticated decoded logs and reconciled Git merge objects:

| Job | Python | Actual result | Suite time |
|---|---|---|---:|
| [116985950027](https://github.com/SirBxss/MPR/actions/runs/38904914991/job/116985950027) | 3.10.22 | 718 run, 716 passed, two skips | 88.882 s |
| [116985950529](https://github.com/SirBxss/MPR/actions/runs/38904914991/job/116985950529) | 3.12.15 | 718 run, 716 passed, two skips | 86.483 s |

Both jobs succeeded in [run 38904914991](https://github.com/SirBxss/MPR/actions/runs/38904914991)
and logged checkout of `07a6a4c` with the exact accepted tree. The earlier
local Python 3.12.14 run (718/716/2) and Claude's independent Python 3.11 run
are supplementary evidence. No further suite repetition or benchmark is
required for this unchanged accepted source.

## Owner action and next implementation

Merge the accepted PR #36 using GitHub's **Create a merge commit** option.
Then update local main and return its identity:

```bash
cd ~/PycharmProjects/MPR
git switch main
git pull --ff-only origin main
git status --short
git log -1 --format='%H%n%T%n%P'
```

The next agent verifies actual main's merge ancestry and accepted tree before
issuing one new v0.19.11 counts-only successor. Use the existing registration
and successful inventory/decode evidence, a fresh versioned output/receipt,
and local scratch. Retain the failed v0.19.10 report digest. Do not rerun or
overwrite that attempt or accepted predecessors. Registered raw paths remain
in place. Actual SENSOR/H100/condition/sequence yield is still unknown.

Measured readiness then informs generic numeric residual export and strict
archive validation, followed by incremental evidenced physical sessions,
cohort/split gates and model training. The generic exporter is a later reviewed
consumer: it does not implicitly inherit this bounded-only admission policy.
Use the existing pilot before deciding how much more data to download.

## Non-blocking follow-up carried forward

- At a later reviewed diagnostics/export stage, consider counts over admitted
  SENSOR H100 rows for event/extended qualifiers, cut-off distance, estimation
  age and distance since an external constraint. Report contradictions; do not
  silently introduce filters. These diagnostics do not delay this merge/pilot.
- Before real fits, attempt to obtain a 2.2-to-2.3 changelog/source trace. If
  unavailable, retain the version-policy assumption explicitly in evaluation
  provenance and research limitations. Do not promote it to a source fact.
- Keep the fixed six causal features unchanged; age/cut-off fields are not
  automatically added as inputs. SENSOR, 21-station signed targets, H100,
  reference interpretation and scientific/model gates remain fixed.
- Performance profiling, directory fsync and the historical raise inventory
  remain separate suggestions. No deadline-adequacy claim or raw retirement is
  authorized by acceptance of this compatibility patch.
