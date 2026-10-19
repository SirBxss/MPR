# Next implementation: generic artifact registry and dataset reader

This is a concrete implementation plan following the successful newer numeric
pilot, not an implemented release, new frozen scientific contract or permission
to fit. It belongs with the next code PR; do not add another documentation-only
round before beginning this work. Existing reviewed contracts and gates govern.

## Deliver one useful vertical slice

Add a private, versioned metadata registry that imports existing immutable
registration/inventory/decode/readiness, adopted authorizations, complete-export
pins and standalone validation receipts. Record exact byte identities and source
releases, attempt states, raw cache presence and explicit unknowns. Import must
not decode raw, rerun predecessors, compute a new cohort role, move a cache file
or write into an old archive. Do not treat an editable index as stronger evidence
than its pinned artifacts; rebuilding the index must preserve exclusion records.

Track source/download artifact IDs as locators separately from evidenced physical
sessions. Represent aliases/links and evidence explicitly, including contradictory
or unresolved links. Import authorization/reservation even for failed or unrun
exports; actual publication/exposure remains a separate state. Propagate both
development exclusions through every evidenced link before a final candidate
draw; unknown links remain unresolved, not proof of independence. Prevent duplicate
raw identities or alias changes from creating extra independent units or restoring
final eligibility. Keep private identities and numeric results outside Git.

Add a read-only generic dataset adapter that invokes the strict standalone archive
validator with explicit metadata/auth/summary pins, then exposes the two populations
and their exact candidate/recording/sequence provenance. It must not weaken the
batch02-pinned historical consumer. Expose `residuals_m` separately from the matched
`residuals_m[conditioned_profile_indices]` / `conditions` pair. Preserve original
integer clocks and all sequence reset boundaries; never join around missing
features or across files. Fail before dataset publication on missing/drifted pins,
invalid mappings, unsupported releases or exposure/session contradictions.

This slice may publish a private engineering intake/support report, not a fitted
model, a cohort lock or final role assignments. Wire the existing role/fit gates
before any real model consumer can call it. Plan matched unconditional/conditional
comparisons on identical complete-feature rows; geometry-only exploratory support
must not silently change the comparison population. Standardizers are fit within
training folds only. Free-running generated histories reset at every declared
sequence and remain recording-local unless a separately reviewed continuity rule
explicitly accepts a boundary.

## Directory and retention model

Use a private `data/` index plus immutable versioned artifact directories, with raw
cache storage configured separately. Stable logical recording IDs and an explicit
RAAS/download locator remain even after eventual cache eviction. Avoid depending
on an empty raw directory as the provenance record: the registry stores the raw
digest, size, exact retrieval recipe/evidence, original locator and cache state.
Existing `outputs/registrations` and `outputs/diagnostics` remain valid immutable
locations referenced by the registry; do not migrate them just to obtain neatness.
Confirm private paths are ignored by Git before writing. Never auto-rename,
overwrite, re-register or delete this pilot's files.

Keep retirement as a later explicit operation: durable archive copies and
validation evidence, persistent reservation/session registry, and a tested
exact-byte retrieval path are required. A new download or re-merge that changes
the raw digest creates a new identity, not a restored old registration. A future
acquisition controller can process one bounded file at a time, preserve compact
artifacts and retire a recoverable raw cache; that controller is not this slice.

## Next private data selection

Use already downloaded files first. Select a small prospective development group
using source/session evidence and processing cost/duration before numeric outcomes.
Counts-only screening reports all fixed attrition, complete-feature support and
sequence lengths. New files need their own truthful predecessors; completed pilots
do not. Preserve unreserved/unexposed candidate outings for the eventual locked
final split and do not bulk authorize all downloads. Large disagreements are not
a quality exclusion. No yield or disk-capacity forecast should assume this short
pilot represents all drives.

The existing exporter accepts readiness from the reviewed historical release or
its own exact source release. Before issuing another launcher, explicitly test
the producer/consumer release pairing. A documentation or integration commit
changes the full-tree launcher preflight even if runtime source is unchanged;
a source change can also change runtime compatibility. Use an immutable accepted
release for each run or implement a reviewed versioned compatibility policy.
Do not discover incompatibility after processing a long raw file and do not solve
it by rerunning a successful readiness report or weakening its pin.

## Focused acceptance checks

Use synthetic fixtures for the new registry/reader and the existing returned
archive for read-only acceptance. Cover duplicate imports, hash drift, source/
session ID confusion, unresolved/conflicting session links, failed/unrun adopted
authorizations, exposure propagation through aliases and final-candidate exclusion.
Verify raw-free loading, exact conditioned-row mapping, deterministic sequence
boundaries, matched populations, no model admission/role assignment, immutable
inputs and historical-consumer rejection of unsupported archives. Required full
checks and exact pushed-head CI still apply. Deliver tested numbered patches and
README; the owner applies, pushes, requests review and merges.
