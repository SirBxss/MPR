# PR #34 a4: independent a3 review evaluation and R1-C correction

Date: 2026-10-14. Status: **DRAFT; focused R1-C/runbook GO and a4 CI pending**.
No implementation or private execution is added. Earlier review records are
preserved as historical proposals, not retroactive approvals.

## Evaluation and decision

Claude reviewed a3 `1548382fe8c6b5dcc228441ac82ec16ed0e1fb2f`, tree
`32bd20b8c5f6acb88c4115c58091e9d55ef97fd1`, and returned NO-GO only for R1-C.
The principal finding is correct. `selected_keep_lane_confidences` raises
`estimate_confidence_field_unavailable` when the declaration is absent;
`_scan_stream` retains `estimate_features_` failure accounting. Three fixed
causal features require these confidence buckets, so missing binding makes
complete-feature support structurally unavailable rather than measured zero.

Geometry can still be valid. Whole-recording null/exit 3 is this contract's
already accepted unsupported-EDP policy, not a claim that confidence absence
destroys geometry. Preserving geometry with a new confidence-unavailable state
is a possible separate design; it would change the accepted availability enum.
This amendment uses the existing policy without reopening B2–B5 or generation.

The [draft](generic_recording_readiness_v01910_draft.md) now requires repeated
numeric `drive_path_confidences` on the path element. Missing or incompatible
declaration yields `estimate_descriptor_fields_unsupported`, recording cause
`scientific_binding_unsupported_estimate_descriptor`, readiness null,
`not_assessed`, false causality and exit 3; reconciled container evidence survives.
Empty/nonfinite/out-of-range values or insufficient bucket coverage on a bound
field remain existing feature failures. With other bindings/odometry supported,
they may produce complete, available-for-checks, measured zero feature support.
An incompatible declared type is a binding defect, not a nonnumeric data value.

Six synthetic real-Protobuf probes of the unchanged functions cover absent,
singular, empty, out-of-range, nonfinite and valid confidence fields. Each retains a geometric
SENSOR candidate; only the valid vector yields a complete-condition row.
Legacy-v1 classification remains unchanged. These explain the defect; they are
not tests of an implemented new binder. Prospective implementation fixtures
now require the null/zero distinction and valid control explicitly.

## Optional suggestions assessed

- O-R2 is clarified: `map_entry` fields do not satisfy repeated-message bindings.
  Add its structural fixture; iteration of maps yields keys, not path objects.
- O-RB1 compares ZIP and extracted manifests before trusting a reused directory.
  O-RB2 rechecks a matching correction after a fast-forward pull. O-RB3 uses an
  exact changed-path allowlist. O-RB4 documents manual `git am --abort` recovery.
  The [public runbook](generic_recording_readiness_contract_runbook_v01910.md)
  and delivered README remain byte-identical, with same-PR normal push only.
- O-R1 real-descriptor conformance belongs to post-GO implementation evidence.
  Prefer preserved descriptor bytes before requesting another private read.
  Compatibility with the actual private pilot is not verified here.
- O-R3's optional-field relaxation and O-R4's extra policy fixtures are not
  needed to correct R1-C. Keep the accepted a3 choices; do not broaden or narrow
  those bindings silently during implementation.

## Codex-verified exact a3 CI

[Run 38427830200](https://github.com/SirBxss/MPR/actions/runs/38427830200)
completed successfully. Codex inspected both job logs:

| Python | Job | Result |
|---|---|---|
| 3.10 | [115401787259](https://github.com/SirBxss/MPR/actions/runs/38427830200/job/115401787259) | 650 run; 648 pass; two existing skips |
| 3.12 | [115401786707](https://github.com/SirBxss/MPR/actions/runs/38427830200/job/115401786707) | 650 run; 648 pass; two existing skips |

Both checked out temporary merge `6a2dc0b74b28beadaffdbcdee0610778bbef3b53`.
GitHub's commit object confirms parents `12ddee6a4c855ed522378fa9742aef993a4bcb5f`
and reviewed a3 `1548382fe8c6b5dcc228441ac82ec16ed0e1fb2f`; its tree equals
the a3 tree above. Claude's inability to inspect CI is an evidence limit, not
a failing CI result. This verifies a3 only; a4 needs its own run after push.

## Owner and next agent

Use exact a3 as patch parent in the existing PR #34 branch. Apply/test/push with
the runbook, obtain focused R1-C/map clarification/runbook GO and new-head
Python 3.10/3.12 CI. No external mutation is performed by this delivery.
Only then merge the contract and implement/test/review/CI the bounded consumer.
Merge that implementation before issuing one fresh counts-only pilot command.
No completed scans are repeated by this amendment. Raw paths, registrations,
old reports and numeric archives remain unchanged; no collection download,
numeric export, real fit, outing-role lock or raw deletion follows.

Future numeric export/validation, private source/session catalogue, controller
and exact-byte retrieval/retirement are separate consumers. Use pilot yields
to size acquisition incrementally; job/interval counts do not prove physical
outings. RLMB remains a pseudo-reference and both flow modes synthetic-only.
