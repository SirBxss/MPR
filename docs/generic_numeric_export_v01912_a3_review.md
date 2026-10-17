# Independent evaluation of PR #37 a2 review and a3 correction

Date: 2026-10-17. Reviewed owner head `cc5acdbe07c7923ff4dbf52b93cfaaff031e72ea`,
tree `a1f4c0ce61ff4da790a2980caa7e9b9e2b6f0e3a`, parent `4c99b7b`.
Main remains `7e4a06b`. The review is substantially sound, but its suggested
wording should not be copied without the qualifications below. This a3 is
documentation only on existing PR #37; no production exporter is implemented.

## Findings assessed independently

| Review item | Assessment |
|---|---|
| R-1: source `purpose` is not an export opt-in | Supported. `parse_specification` rejects every other purpose, `prepare` generates that value and registration enforces it. The same label is therefore present before any deliberate decision to export numeric outcomes. It cannot discriminate counts-only screening from numeric exposure. This is a missing prospective control, not evidence that any final data has already leaked. |
| C-3: literal-True scanning is incomplete | Supported. The current source has seven keyword uses and four default-False keyword-only definitions. A computed-value call bypasses a literal-True-only scan. Pin the complete surface and all five affected source files; forbid dynamic opt-ins. These are regression guards, not a formal guarantee against every dynamic Python construction. |
| C-4: observer alignment/containment | Supported with qualification. Use the sink's pre-delegation position and verify one append and exact source time; select the unique KEEP_LANE path, not index zero. Contain ordinary observation failures, but do not swallow resource, storage, deadline or real sink/reader failures. |
| B-1/B-3/C-1/C-2 closure | Supported at the contract/feasibility level. Unchanged-sink composition is feasible, the confidence assumption remains explicit and unconfirmed, the support schema is exact and the residual-code surface is closed. Production implementation conformance remains to be tested. |
| a2 CI log gap | Closed by authenticated log retrieval, rather than inferred from job duration. Both jobs ran the full expected suite on the actual a2 test merge/tree. |
| PR metadata | The live API shows four commits and a nonempty description. The review properly flagged its page as potentially stale; there is no remaining empty-description defect at this check. |

## Qualifications to the review's proposed fix

**Authorization is not proof of execution.** A separate owner-supplied file is a
reasonable explicit input, but its existence proves a recorded decision, not
that outcomes were actually generated or seen. A3 makes signing/supplying it an
explicit permanent development reservation, distinct from complete-export
exposure. Both are excluded from future final selection by a declared
conservative policy; neither proves session independence or admits an outing.
SHA-256 pins file bytes, not human identity. There is no implicit bypass for the
old pilot, and no change to the old two-file registration schema.

**Do not apply "never raises" literally.** The observer shares the disposable
science SQLite workspace. A tiny in-memory counterexample (no MCAP or project
database involved) shows why storage errors cannot be treated like absent
metadata: forcing `SQLITE_FULL` rolled back a pending scientific row with a
memory journal; under journal OFF the subsequent read failed with
`SQLITE_CORRUPT` in this environment. The actual bounded workspace uses journal
OFF and explicit page/resource caps. SQLite's own
[journal-mode documentation](https://www.sqlite.org/pragma.html#pragma_journal_mode)
also describes the missing rollback/atomicity guarantees with OFF.
This is a failure-mode demonstration, not
evidence of corruption in any recorded data or project output.

A3 contains ordinary extraction/selection/alignment errors in observer state,
but routes SQLite/transaction, memory, deadline and other resource failures
through the existing invalidation/termination path. Exceptions from the real
sink/reader are not observer failures and are never intercepted as such. A
candidate with unavailable metadata invalidates export; an ordinary missing
observation on a noncandidate cannot change scientific selection. All observer
work counts toward the same resource/deadline budgets.

**Static tests do not establish semantic implementation correctness.** Full
keyword/definition scanning closes the concrete computed-flag gap. Byte-pinning
the five shared files also prevents changes to their defaults/forwarding.
Runtime admission/default tests and code review are still required; the private
synthetic feasibility harness is not the production exporter or validator.

## Exact a3 input boundary

The [revised contract](generic_numeric_export_v01912_contract.md) defines one
mandatory separate exposure-authorization file with its own revision, eight
exact top-level fields and four literal-true attestations. It pins batch,
registration, source specification, preserved readiness and the exact sorted
raw-hash set; a supplied expected authorization hash pins its bytes. It lives
outside the immutable two-file registration directory. Missing/malformed/
partial/extra/drifted authorization stops before raw hashing or output creation.
Late drift invalidates publication. Summary, standalone validation and receipt
bind the same digest. No valid authorization is automatically derived from the
universal pipeline label. A draft helper cannot auto-accept the attestations.

The future session/split consumer must distinguish permanent reservation from
actual numeric publication, propagate both exclusions to physical-session links
and aliases, and exclude them before final selection. Failed/unrun authorization
is not silently revoked. This is separate from any train/validation role lock.
The additional input is metadata only; it requires no new raw-data diagnostic.

The observer contract pins all seven keyword uses/four definitions/five source
files and adds exact position/time checks, unique KEEP_LANE observation,
ordinary failure counts, candidate-versus-noncandidate handling and resource/
storage failure propagation. These clarify implementation; they change no H100,
reference, feature, speed, pairing or sequence rule.

## a2 CI independently verified

Authenticated decoded logs for
[run 39018949854](https://github.com/SirBxss/MPR/actions/runs/39018949854)
both check out `c60a33702e455af7b3dcb38f945acac466ddd797`, parents main
`7e4a06b` plus reviewed `cc5acdb`, tree `a1f4c0c…` equal to the a2 head.

| Job | Python | Run / passed / skips | Test seconds |
|---|---|---|---:|
| `117356710898` | 3.10.22 | 718 / 716 / 2 | 56.278 |
| `117356710760` | 3.12.15 | 718 / 716 / 2 | 78.510 |

The shorter job did not omit tests. These logs cover a2, not the new a3 commit.
Focused a3 review and new-head CI remain pending. No new private command,
message, push, merge, model fit or deletion was performed by the agent.

## Next action and scope

Apply one fifth documentation commit on the same PR using the updated
[runbook](generic_numeric_export_contract_runbook_v01912.md). Review R-1/C-3/C-4
closure, particularly the two qualifications above. The next production change
implements exporter and standalone validator together; code review/CI/merge
precedes an explicitly authorized versioned export. The retained pilot is an
engineering option, not a mandatory source-quality hurdle before newer data.
A qualified newer development recording may be selected once its own preserved
readiness and authorization are available. Reserve untouched final candidates.
Do not extrapolate old-pilot support to the newer manually screened collection.
Validated archives, reviewed session/split/model integration and their existing
gates still precede real fits. Keep existing data until durable validation and
tested retrieval justify retirement.
