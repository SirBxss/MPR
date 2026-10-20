# v0.19.14 generic owner-declared outing cohort

Status: implementation and contract candidate for independent review. This is
the next slice above the merged v0.19.13 registry/reader, not permission to fit
a model. The owner now explicitly declares the registered folder/source IDs to
represent different physical drives. Their IDs are useful labels; exact byte
identity remains SHA-256. The declaration is retained as
`owner_declared_not_independently_verified`, with the actual statement/basis,
without inventing a provider session ID, acquisition UTC or source trace.

## Scientific and compatibility boundary

The target, SENSOR-only population, six feature names/order, H100 sign/grid,
fixed speed causality, confidence-width assumption, source-compatibility caveat,
numeric producer allowlist, historical consumers and real-fit/flow gates are
unchanged. The five frozen scientific files remain byte-identical. RLMB remains
a map-relative pseudo-reference. User-confirmed separate drives are an explicit
physical-membership declaration, not a claim of statistical independence or
machine verification.

Reuse the v0.17 pure eligibility function: at least one raw-usable file, at least
120 seconds of monotonic nonoverlapping estimate-source intervals, zero non-SENSOR
pre-anchor H100 candidates, at least 500 complete eligible frames and exact
sequence retention. The requirement is not one contiguous 120-second complete
sequence. All recording boundaries remain resets in this generic consumer.
Readiness describes eligibility states, not finite residual construction or a fit.

This separately versioned contract accepts a post-pilot owner declaration and
already-reviewed generic count reports. It does not falsely serialize the old
`created_before_outcome_inspection=true`, invent missing acquisition UTC, or use
the legacy basename-bound CLI. Permanent reservations/publication exclusions
protect any already exposed outcome and linked drive. The prospective raw pool
and exact report choices are explicit and hash-pinned, before new final outcomes.

## Private declaration and cohort manifest

Session declaration revision is
`v0.19.14-owner-session-declaration-2026-10-19-a1`. Exact fields:

```text
contract_revision, purpose, evidence_status, declaration_text_private,
independence_basis_private, outings
```

Purpose is `owner_declared_physical_session_membership`; evidence status is the
literal above. Each outing has exactly `session_id_private` (unique meaningful
text), `separate_physical_session` (literal true), `raw_sha256` (nonempty sorted
unique list of known registered raw hashes). One raw can appear only once. Several
technical files may belong to one declared outing. IDs are labels, never features.
The owner statement is evidence, not a signed human-identity authentication.

The cohort manifest has exactly:

```text
contract_revision, registry_sha256, session_declaration_sha256,
scope_raw_sha256, readiness_by_raw_sha256, legacy_development_outing_count,
prior_successful_lock_sha256
```

Revision is `v0.19.14-generic-owner-declared-cohort-2026-10-19-a1`. The scope is
nonempty, sorted and unique. The readiness map covers exactly that scope and pins
registry-held reports; no implicit latest-file selection is allowed. Selected
physical outings cannot be partially included. The legacy count is integer one.
No successful generic lock exists at this checkpoint; the prior field must be
null. This version rejects supersession rather than silently rerolling a lock.
An accepted earlier lock requires its own reviewed amendment and consumer.

Original registrations/specifications remain immutable. A reviewed operational
helper can append the owner declaration as pinned evidence for confirmed
raw-to-session *claims* in a new registry descendant. Confirmation means the
owner asserts the link, not that the software verified physical truth. Failed
readiness reports remain events when complete successor reports are appended.

## Readiness, identity and reservations

The consumer strictly replays the complete v0.19.11 report, exact registration,
inventory/decode lineage, stream oracle, schema bindings, scientific shapes,
clock/count/attrition/sequence evidence, fixed limits and recorded causality flags.
Only the frozen reviewed readiness/numeric producers are accepted. No numeric
consent is created to validate counts. Pre-anchor H100 candidate topology is
reconstructed from the two complete geometry outcomes and checked against the
total H100 count. Raw-usable files also require all topics, supported odometry
and complete strictly increasing estimate-source clocks.

Two graphs remain distinct: confirmed identity plus exact per-recording source
IDs detect contradictory claims; possible links additionally include locators,
source-declared sessions and every unresolved/conflicting relationship. Different
owner or source sessions inside an identity component block its whole possible
component. An unresolved link alone does not prove identity, but distinct or
unknown owner sessions in that possible component cannot be counted separately
or assigned across folds. Broad free-text locators are possible links only.
Component sizes are retained in the pure policy view; no folder/bucket becomes a
physical session merely by appearing in metadata.

Existing reservations/publications/conflicts are retained and propagated through
all possible links and declared session membership. A later owner label cannot
erase a previous exclusion. Existing v0.19.13 snapshot rows/replay semantics stay
unchanged; stronger identity checks live in the new consumer. The metadata path
guard additionally checks parent-resolved containment before endpoint lstat.
This is not a general filesystem sandbox or a hardlink-detection guarantee.

## Prospective final selection

At least seven technically eligible new outings plus the legacy development
outing are still required. Retain the v0.17 raw-content outing fingerprint,
split-score salt/rank and `max(2, ceil((E+1)/5))` final count. The explicit amendment
is to rank **only eligible unreserved/unexposed outings** for final selection.
Reserved eligible outings remain development. Insufficient total eligible
outings or insufficient untouched final candidates produces a complete support
audit with no roles. All ineligible outings remain reported, not replaced.

Labels, directory layout, manifest ordering, residual values, features and model
scores do not influence the draw. The first successful lock in the retained
project is binding. A separate checkout/omitted external history is not a global
reservation ledger: retain external expected digests, the accepted project lock
checkpoint and all private history. The same limitation applies to v0.19.13.

## Publication, replay and model interface

`python -m lane_residuals.cli.generic_cohort create` takes project-root,
registry-directory/expected-registry-sha256, session-declaration/expected-session-
declaration-sha256, cohort-manifest/expected-cohort-manifest-sha256 and a new
output-directory. Output is confined to Git-ignored `data/catalog/private/`.
`verify` takes cohort-directory/expected-cohort-sha256 and the original registry.
These commands are operational only after independent GO, CI and owner merge.

A complete new directory contains exactly `session_declaration.json`,
`cohort_manifest.json`, `cohort.json`. The final file is the completion marker,
with the returned external digest. It pins both original evidence files and the
registry, records creator source, declared evidence quality, support/failures,
content fingerprints, split policy, role/admission flags and all outing rows.
Verification recomputes those rows from original evidence; repinning edited
cached roles cannot make them valid. No residual/feature values are output.
Successful create exits 0; an insufficient support/final-pool audit exits 3;
invalid evidence exits 2. A missing final marker is not a completed cohort.

Registry/cohort writers share the same project lock. Inputs, source and registry
are rechecked before the exclusive durable final marker. Output traversal,
symlinked output parents and existing destinations are rejected. Metadata inputs
use strict file/hash checks and registered-raw alias guards. Previous snapshots are
never written. A partial publication is preserved for recovery. Replay needs a
private writable parent; a read-only backup should be copied without changing its
expected digest. Existing metadata/object/array/time caps are not relaxed; the
CLI inherits a 4 GiB address-space ceiling and restores its caller's prior limit.

`load_development_dataset` is a first **snapshot-bound engineering adapter**.
It replays the cohort and strict numeric archives, rejects out-of-scope/final/
excluded archives and duplicate possible components, and exposes original
read-only matched arrays and recording-local sequences. A fold selects complete
disjoint development sessions with exact selected-archive coverage. No scaling,
imputation, padding, history bridging or fitting occurs. Fit transformations only
inside training folds after the later real-fit protocol is authorized.

Both the generic reader and the new adapter retain nonconstructible false model
admission flags. Adding new development exports later requires a reviewed
descendant-registry model adapter; do not replace this frozen snapshot binding
or reroll roles. This slice does not wire old training CLIs or implement real
flow persistence, normalized flow likelihood, real-fit authorization, final
evaluation or raw retirement. The flow scope/history/solver and planner stages
remain separate reviewed work.

## Verification and operational delivery

Focused tests exercise fixed thresholds, label/order invariance, owner evidence,
same-source/confirmed/unresolved contradictions, exposure propagation, duplicate
raw/partial-outing rejection, native seven-outing count-only admission, immutable
publication/replay, source/input drift, prior history, failed publication, raw
alias guard ordering, exact matched blocks, disjoint whole-session folds and no
model grant. Returned-artifact acceptance uses copies and raw open/stat guards;
private measurements, session IDs, proposal roles and hashes stay outside Git.
The delivered owner README contains apply/review instructions separately from
any agent-only evidence. No owner MCAP scan or numeric consent follows this slice.

Local Python 3.12.14 / MCAP 1.5 verification passes compileall, 76 focused tests
and the full 864-test suite with 862 passes and the same two expected skips.
The strengthened alias-order regression additionally instruments both stat and
lstat on a non-MCAP-suffixed alias. Raw-free returned-artifact acceptance passes
on private copies, including successor recovery/session evidence, cohort replay
and exact matched inputs. These checks are candidate evidence, not independent
review, pushed-head Python 3.10/3.12 CI or an operational owner lock.

## 2026-10-20 PR #40 CI compatibility correction

The pushed owner head `681cbf9` has the delivered tree `b6fac873`. Both jobs in
run `39385094591`, tested merge `0da60c0`, compile but fail the 864-test suite
with eight failures, seven errors and two expected skips. CI installed MCAP
1.6.0. Its [reader API](https://mcap.dev/docs/python/_modules/mcap/reader)
resolves the new bounds and always forwards `starting_at`/`ending_before` to
`iter_messages`, including their None defaults. The indexed reader's older
signature caused the reproduced TypeError before decoding. Readiness assertions
then reported inconclusive results. This does not invalidate preserved returns.

The correction explicitly accepts `starting_at`, `starting_after`, `ending_at`
and `ending_before` as keyword-only arguments. None retains the exact old full
physical-file-order read. Every non-None time bound, old or new, is rejected by
the existing fixed error before summary or payload access; zero is a bound.
No filters, fallback scan, reordering, resource/CRC relaxation or broad ignored
keyword arguments are introduced. Two native regressions cover null-bound
message parity under NONE/ZSTD/LZ4 and rejection of all six bounds at zero,
negative and positive values. Existing inherited-decoder and corruption/memory
tests exercise the new upstream call path.

Local verification: compileall and the complete suite pass on Python 3.10.22
and 3.12.14 with MCAP 1.6.0/new decoder extras (866 run, 864 passed, two unchanged
skips each). The 104 focused reader/ingestion checks pass on the new set;
180 focused reader/ingestion/cohort/registry checks pass with MCAP 1.5.0 and
the earlier decoder extras. Both local full runs use the CI test command and
Matplotlib settings without adding BLAS-thread limits. The failed CI logs,
reproduction and environment inventories remain in the private delivery.

Keep this delta in PR #40, refresh private delivery source pins, and require
independent delta GO plus corrected-head Python 3.10/3.12 CI before owner merge.
The earlier local 1.5.0 results above remain historical. No accepted artifact,
producer allowlist, scientific source file, causal-feature definition, cohort
gate or model authorization changes. The metadata-only owner operation remains
pending until its existing review/CI/merge conditions are met.
