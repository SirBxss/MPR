# v0.19.13 private evidence registry and generic dataset reader

This implementation closes the registry/reader slice in
`generic_archive_integration_next_20261018.md`. It reuses the accepted numeric
validator; it changes no geometry, topology admission, feature arithmetic,
clock guard, sequence rule, historical archive consumer or model. Code review
and exact-head CI precede owner merge and operational use of this new CLI.

## Evidence, storage and replay

`lane_residuals.cli.artifact_registry import` creates a **new** snapshot beneath
the project's Git-ignored `data/catalog/private/`. The parent snapshot, if any,
requires its external `registry.json` digest. Updates copy every previous event
and content-addressed evidence object, so an adopted authorization survives even
when its source file, old raw cache or previous snapshot is later offline.
Previous snapshots are never rewritten. Re-importing the same evidence adds no
duplicate event or raw identity. The manifest and all input files are bounded,
strict-JSON/hash checked and checked again before the final commit marker.
Project writers use an exclusive lock. A cold rebuild is rejected when an
existing registry is present, and an update's pinned parent must retain the
event history of every existing project snapshot. Selecting an older parent
cannot silently discard a later development reservation.

Each snapshot has exactly `registry.json` and `objects/`. Original metadata,
adopted authorizations, report bytes, archive arrays and validation receipts are
stored by SHA-256. Index rows are a rebuildable cache: verification replays the
pinned evidence and rejects an edited row even when that edited index is given
a new external digest. Archive replay invokes the strict standalone validator
implementation, not a relaxed NPZ reader. Original validation receipts must
also match the same summary, artifacts, predecessor/auth pins and populations.
This validation establishes artifact correctness; it does not recompute raw
geometry or prove that arbitrary source assertions are physically true.

Registration-only inventory/decode/readiness reports are retained as pinned
source reports with batch/registration/specification lineage and complete or
inconclusive status. They do not become independently re-executed science or
outing admission. An incomplete/inconclusive native report remains visible.

All JSON files under the project's `config/private/` are checked for adopted
authorization content, including renamed files and failed/unrun exports.
Unrelated configuration is watched for drift but is not copied into the
snapshot. External adopted records can be supplied explicitly with their pins.
All-false drafts confer no reservation; partial/non-Boolean attestations stop
the import for reconciliation. The importer never changes an attestation or
creates accepted consent. Archive-consumed adopted records are retained even
when they are outside the current project directory.

Raw identity is the exact byte digest, not a path, basename, RAAS ID, registry
row or archive. Source locators, recording aliases and declared physical-session
links remain distinct. Repeated raw identity cannot create extra units. Source
specification declarations of a physical session carry conservative possible
links; they never prove independence. Confirmed links, unresolved links,
conflicting links and their immutable evidence remain explicit. Existing
uncertainty/conflicts are retained by this slice; resolving them for a later
cohort requires reviewed adjudication rather than deleting old events.

Reservations and observed complete publication are separate states. Either
excludes linked outings from future final selection. Potential/unresolved links
conservatively carry exclusion while preserving uncertainty. Conflicting session
claims block selected dataset views. Nothing in this release assigns a role,
admits an independent outing, grants final-candidate status or authorizes a fit.
The later cohort/split consumer must still implement the reviewed admission and
reservation-aware lock; this registry does not replace that work.

Optional `--observe-cache` performs `lstat` only, reporting absent, unavailable
or present-unverified state and preserving prior observations. The default
never resolves/stats/opens raw paths. Original retrieval/source declarations
remain in the evidence, with exact-byte retrieval explicitly unverified.
There is no raw move, re-registration, deletion or cache-eviction operation.
Empty folders cannot substitute for the pinned recording/locator evidence.

## Dataset interface and producer compatibility

`io.generic_dataset.load_generic_archive` calls `read_pinned_summary`, the
producer-bound metadata loader and the strict `validate_archive`. It accepts
the independently reviewed numeric producer fingerprint `45f1f96…` and the
installed consumer's own exact runtime release. An arbitrary producer digest
in an input summary is rejected. Existing v0.19.12 readiness is validated against
its pinned producer, so a new integration release does not force successful
readiness to be rerun or its digest changed.

`io.artifact_registry.load_registry_dataset` additionally verifies a complete
snapshot, requires an explicit unique archive selection, rejects repeated raw
identity across selected archives and blocks session/exposure contradictions.
It returns a tuple of separate `GenericArchiveDataset` objects; no file boundary
is stitched. The archive view exposes:

| Interface | Meaning |
|---|---|
| `geometry_residuals_m` | All validated finite H100 vectors |
| `matched_residuals_m` | Exactly `residuals_m[conditioned_profile_indices]` |
| `conditions` | Six complete features in the unchanged order |
| `arrays` | Read-only arrays with original indices, recording IDs, integer clock strings and both offset arrays |
| `matched_sequences()` | Matched residual/feature slices and original profile indices, with one reset per accepted sequence |
| `require_model_admission()` | Always raises: this release is engineering-only |

All array masks, order and reset boundaries stay fixed. Immutable support
metadata is exposed separately. Unconditional/conditional comparisons must
later use the same matched subset. Training-fold-only transforms, free-running
generated histories, independent-outing support and all existing fit gates still
apply. No model consumer is rewired, no training transform is fitted and both
flow modes remain synthetic-only.

The CLI applies a 4 GiB process address-space cap and restores its caller's cap.
Metadata objects are bounded to 256 MiB, total objects/observed input to 1 GiB,
retained array memory to 512 MiB, events to 10,000 and validation to 300 s.
These are new metadata-consumer limits; accepted raw-decoder/science limits are
unchanged. The new marker is written last with exclusive file creation and
fsync. A failed publication without its marker is not a completed snapshot.

## Import schema and commands

Manifest revision: `v0.19.13-private-registry-import-2026-10-18`. The closed root
has `contract_revision`, `registrations`, `archives`, `relationships` and
`additional_authorizations`; the last four are lists, including empty lists.

- A registration has `registration_directory`, `expected_registration_sha256`
  and `reports`. Each optional report has `role` (`inventory`, `decode` or
  `readiness`), `path` and `expected_sha256`.
- An archive uses the existing numeric validator's registration/inventory/decode/
  readiness/authorization/export paths and the three original expected pins,
  plus `validation_receipt` and `expected_validation_receipt_sha256`. Exact
  accepted keys are `ARCHIVE_INPUT_FIELDS` in `io/artifact_registry.py`.
- A relationship has `left`, `right`, `status` and `evidence`. Nodes are typed
  `raw:<sha256>` or `session:<opaque-id>`; status is `confirmed`, `unresolved`
  or `conflicting`. At least one evidence file is required; each has `path`
  and `expected_sha256`. A RAAS locator is never a session-node type.
- An additional authorization has `path` and `expected_sha256`.

Keep the manifest private. For example, after code acceptance/merge:

```bash
.venv/bin/python -m lane_residuals.cli.artifact_registry import \
  --project-root "$PWD" \
  --manifest config/private/registry_import_v01913.private.json \
  --output-directory data/catalog/private/recording_registry_v01913_001

.venv/bin/python -m lane_residuals.cli.artifact_registry verify \
  --registry-directory data/catalog/private/recording_registry_v01913_001 \
  --expected-registry-sha256 ORIGINAL_DIGEST_PRINTED_BY_IMPORT
```

An update adds `--previous-directory` and `--expected-previous-sha256` and uses
a different output directory. Never edit the old snapshot or repin a changed
cached row to clear an exclusion. Printed digests and original result ZIPs must
be retained outside the derived index.

## Collection screening and next scientific work

The owner explicitly requests counts-only assessment of every remaining
downloaded recording. A private fixed-input controller uses a frozen copy of
the already accepted backend, so screening may run while this new code is in
review. It preserves completed attempts, duplicates and inconclusive outcomes,
supports recovery without repeating completed stages, and exports no residual
or numeric feature value. It does not opt in the remaining collection, change
the final pool or run on new files added after its pinned discovery.

Returned numeric brackets show source-relative speed exclusions even where
log/publication timestamps tie. Such ties do not prove physical availability.
Review the prediction epoch and any prospective past-only feature definition
before bulk numeric processing; do not silently relax the current guard, shift
clocks or join around missing features. Confidence-width/producer assumptions,
physical-session evidence, the reviewed cohort/split lock and the model/flow
scope gates remain. Consolidate implementation/results in this code PR; no
additional documentation-only round or old successful raw pilot is required.

## Local verification checkpoint

Python 3.12.14: compileall passes; 26 focused registry/reader tests pass; full
814 run /812 passed /two unchanged expected skips. The independently executed
read-only returned-archive acceptance confirms producer compatibility, exact
matched rows/resets, immutable original inputs, no raw stat/open, unresolved
session linkage and no role/fit/retirement. Private measurements and identities
remain outside Git. Native synthetic controller verification covers complete,
inconclusive, duplicate, interrupted, recovered and concurrent cases on the
unchanged accepted backend. Exact pushed-head 3.10/3.12 CI is still required.
