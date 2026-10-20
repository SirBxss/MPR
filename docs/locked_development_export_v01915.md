# Locked development exports and descendant engineering data, v0.19.15

Date: 2026-10-20. Implementation candidate above merged PR #40 (`3b8496b`,
reviewed `f23d8b0`). The owner metadata operation and its first cohort lock are
independently accepted. Exact private identities, counts and pins stay outside
Git. This source change implements the conditions for the next concrete export
operation; it is not another documentation-only prerequisite or a model result.

## Scope and immutable inputs

Keep the original three-file cohort and its original registry externally pinned.
Later registries are additional snapshots, never replacements for that binding.
`io.locked_development.load_context` takes the original paths/digest and an
ordered explicit list of `RegistryCheckpoint(directory, sha256)` descendants.
Every snapshot strictly replays. Each child must name its immediately preceding
parent, preserve its ordered event prefix, and contain every prior object with
identical bytes. Omitted intermediates, cycles, wrong hashes, cached-index drift
and altered history fail. No source/raw endpoint is queried by default replay.
An early rejection pass rebuilds identity/exposure from pinned JSON objects
before any descendant numeric array is opened. It does not trust cached rows
and never replaces the full strict validator for an accepted descendant.

The complete original owner declaration, including out-of-scope pilots and old
possible links, determines membership. Later metadata may not change the
possible raw component of an admitted outing, introduce conflicting identity,
or make its session unresolved. Any later final reservation/publication or
linked exclusion invalidates final evidence and blocks development access.
The consumer never fixes contamination by reranking or reassigning roles.
Already excluded uncertainty is retained and never promoted.

The caller must retain the external accepted-lock checkpoint and all history.
Project-local scanning under the shared writer lock detects omitted local
registry history. It cannot discover hidden external snapshots or establish a
globally authenticated owner identity. Independent drive declarations remain
`owner_declared_not_independently_verified`.

## Review corrections

R-1: usable intervals from distinct files require strict separation (`stop <
next_start`). Touching source epochs fail, matching v0.17. Existing accepted
single-file locks replay unchanged. Any previously unsupported touching-file
lock fails closed rather than being silently grandfathered. Generic readiness
conservatively makes a file raw-unusable after any odometry failure; this is
stricter than the historical v0.17 usability definition. It does not add a long
contiguous complete-sequence duration gate or relax the support thresholds.

R-2: registry/cohort writers share an early output-separation guard. Outputs
cannot equal or nest inside explicit immutable inputs, any ancestor carrying
`registry.json`/`cohort.json` (even a malformed/partial marker), or an `objects`
directory. Ancestor overlap with explicit inputs also fails. Existing path,
symlink, traversal and ignored-private-location checks remain. Invalid nesting
fails before locks/directories are created; native tests verify parent bytes,
file sets and continued replay. Partial publications are preserved.

R-3: every target must belong to the original locked development population
before any attempt or new reservation exists. Final, excluded, out-of-scope,
duplicate-component, already-published and previously inconclusive numeric
targets fail. Reuse published archives; recovery requires a separately reviewed
plan rather than automatic retry. This first controller supports single-raw
registrations and distinct possible components only, so a whole-registration
export cannot smuggle an unrelated/final recording into a permitted target.

## Export controller

`python -m lane_residuals.cli.locked_development_export` requires project-root,
plan, expected-plan-sha256, expected-consumer-tree and expected-consumer-runtime.
The private issued helper additionally requires clean merged remote main with
the reviewed exact tree/runtime. A source candidate is not an operational grant.
Independent implementation/helper GO, exact-head CI and owner merge precede use.

Plan revision is `v0.19.15-locked-development-export-plan-2026-10-20-a1`.
It has exactly:

```text
contract_revision, cohort_directory, expected_cohort_sha256,
original_registry_directory, expected_original_registry_sha256, descendants,
frozen_release_directory, frozen_release_pin,
expected_frozen_release_pin_sha256, collection_lock_path,
targets, attempt_directory, result_zip
```

Each descendant has exactly `directory, sha256`; each target has exactly
`raw_sha256, authorization, expected_authorization_sha256, numeric_output,
reserved_registry, complete_registry`. Relative paths resolve under project-root;
absolute private paths are allowed. Destinations must be new, separated, and in
their existing private/derived/receipt locations. No predecessor path is moved.
The private plan fixes the finite target list and reuses the existing archive.

The controller materializes only original selected registry-held registration,
specification, inventory, decode and complete readiness bytes. An authorization
must already contain all four explicit owner attestations and match this exact
whole registration/readiness/raw. False drafts are never adopted by the code.
All project configuration consent is inspected before an attempt, because the
registry importer scans it: unselected new adopted consent is refused before it
could incidentally reserve a final/outsider. Existing recorded consent survives.

The frozen producer remains `45f1f96f…`. Its full issued release file set,
all file digests and runtime hash must match. Its Python/dependency inventory
must exactly equal Python 3.12.3, MCAP 1.4.0, protobuf-support 0.5.4, NumPy 2.5.1,
protobuf 7.35.1, lz4 4.4.5, zstandard 0.25.0 before an attempt and during execution.
These are recorded producer pins, not recommendations to upgrade/downgrade an
environment in place. No producer allowlist is broadened or self-accepted.

The shared project registry lock and original collection lock serialize work.
Native children inherit their descriptors. Source, consent, history, destination,
and resource preflights run before the attempt and again under lock. Operational
headroom remains 12 GiB available RAM and 18.5 GiB scratch free; the backend's
unchanged caps and <=4 GiB address-space limit apply separately. Numeric output
and scratch must share a filesystem. The controller does not scan MCAPs itself.

For each target, sequentially: preserve exact inputs; import a permanent
development reservation; recheck locked scope; call frozen export (fresh raw
hash/selected stream); call its strict raw-free validator; publish a new registry
descendant; replay against the original lock. Each complete publication is
distinct from prior authorization/reservation. No acquisition, counts-only
rerun, raw move/delete, speed reinterpretation, model fitting or final read occurs.

The receipt preserves exact plan bytes/digest, consumer commit/tree/runtime,
frozen release/version pins, original/cohort/current pins, stages/statuses, targets,
descendants, input-integrity result and false model/deletion grants. A caught
failure/interrupt stops subsequent targets and returns a ZIP with receipt,
commands/logs, original selected metadata, all completed/partial new outputs,
and exact SHA256SUMS plus CRC verification. Exit 0 means all selected exports,
validation/publication and matched engineering replay completed; 2 means failure;
130 means a captured interrupt. Preflight failures create no attempt/result.
If packaging itself fails, preserve local partial output and terminal evidence.
No attempt/output/result is overwritten, resumed, or silently retried.

## Descendant dataset and remaining scientific gates

`io.locked_development.load_development_dataset` takes the same original and
descendant pins plus explicit unique archive digests. It uses strict numeric
replay and rejects outside/final/excluded archives, repeated raw aliases within
or across archives, duplicate possible components and partial selected sessions.
It exposes original read-only matched residual/features, row mappings and reset
boundaries, bound to both the original cohort and chosen descendant. Whole-
session folds remain disjoint with exact selected-archive coverage. No scaler,
imputation, sequence bridging or fit occurs; model admission cannot be enabled.
The old v0.19.14 snapshot reader and old training CLIs remain untouched.

The engineering 7-outing/120-second/500-frame gate is not a power analysis or
model validation. Source duration is not contiguous complete-feature duration.
Retain fragmentation, exact clocks, the speed causality guard, unknown physical
availability semantics, 5 m confidence assumption and producer compatibility
caveat. RLMB is a map-relative pseudo-reference, not independent physical truth.
Keep the reservation-aware split amendment and exposure chronology visible.
Both flows remain synthetic-only. Real fitting still requires frozen matched
comparisons, folds, fold-local transforms and the separate real-fit/flow protocol.

Remaining nonblocking review observations include separate readiness/producer
allowlists before any widening, crash-truncated markers, persisted component
visibility, exclusion breakdowns and replay temporary placement. Old schemas
are not rewritten to resolve these reporting/lifecycle questions. CI now adds a
frozen-reader dependency job alongside current Python 3.10/3.12; its newer
Python patch release is compatibility evidence, not an exact owner-environment run.

## Local implementation verification

Compileall and full suites pass on Python 3.10.22/3.12.14 with current MCAP 1.6.0,
and Python 3.12.14 with MCAP 1.4.0 and the recorded reader dependencies: 889 run,
887 pass and two expected skips each. This adds 23 tests to PR #40; the final
suites include all 40 focused generic-policy/new-guard cases. Native synthetic
exports exercise reservation-before-read, standalone validation/publication,
matched rows/resets/folds and failure/interrupt/source-drift preservation.
Ten scientific/numeric files remain byte-identical to merged main.

Raw-free acceptance on private copies preserves the original lock and archive
bytes, identifies pending development targets and rejects final/excluded/already-
published targets without raw endpoint queries. Disposable Git checks exercise
actual patch application and remote-main refusal; positive owner-authorization
delegation is synthetic and stubbed, with native export orchestration tested
separately. These are implementation checks; independent review and actual
reviewed-head CI/owner merge remain pending before private operational use.
