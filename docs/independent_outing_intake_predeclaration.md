# v0.17 independent-outing intake and cohort-lock predeclaration

Status: amended draft dated 2026-09-03. The original draft was written before
any additional-outing MCAP, derived residual, condition vector, or model result
was available to the MPR implementation agent. Claude reviewed pushed commit
`189f948a71ca895fd5a4d8ff8275a2757b998c53` and returned `AMEND`. The originally
named local patch-source commit `77d33d662882b48e2e8b6360cfc01f63f4e20bee`
has the same repository tree, `86945dfef7c3156aff7f892c2713ca23897946a4`, so
the review covered the intended content. This amendment resolves the review's
three substantive findings and adopts its useful split-hardening suggestions.
A focused independent re-review is required before workflow implementation.
Every result will be retained regardless of whether the availability gate
passes.

This is an intake and cohort-lock phase, not the final model comparison. It
creates the immutable provenance and outcome-blind development/final split
needed by a later, separately predeclared evaluation. It does not fit, select,
sample, or evaluate a model and does not execute a planner.

## Purpose and scientific unit

The purpose is to determine whether the newly acquired corpus contains enough
technically eligible, genuinely separate physical outings to support an
untouched final evaluation, and to lock which new outings have the
`development` and `final_test` roles without using residual or model outcomes.

The independent unit is one physical outing, not an MCAP, recording group,
continuous sequence, or frame. One outing is one declared vehicle data-
collection session. Several chunked MCAPs may belong to that outing, but they
remain one independent unit even if no pair of chunks is stitchable. Technical
groups from one session never become independent outings merely because they
have different filenames, source topologies, or recording IDs.

Physical-outing identity cannot be inferred reliably from MCAP filenames. The
data owner must declare it prospectively in the private acquisition manifest.
The workflow verifies exact file coverage and internal consistency but reports
that outing independence is provenance-declared rather than statistically
proven.

The accepted same-day corpus remains exactly one legacy development outing. It
may be used later for training under a separately reviewed evaluation contract,
but it is not part of the newly acquired corpus, cannot receive a final-test
role, and never counts as more than one independent outing.

## Prospective private acquisition manifest

Before any additional-outing residual magnitude, condition distribution,
planner output, or model metric is inspected, the data owner creates one strict
JSON object with these top-level fields:

```text
version                          "0.17"
purpose                          "prospective_independent_outing_intake"
acquisition_batch_closed         true
created_before_outcome_inspection true
legacy_development_outing_count  1
prior_successful_lock_sha256      null or lowercase 64-character SHA-256
superseding_contract_amendment_id null or nonempty string
outings                          nonempty array
```

For the first successful lock, `prior_successful_lock_sha256` and
`superseding_contract_amendment_id` are both `null`. A permitted superseding
run sets both fields: the hash identifies the exact previous
`independent_outing_lock.json`, and the amendment identifier names the dated,
independently reviewed contract amendment that records what changed and why.
One null and one non-null field is invalid.

Every item in `outings` contains exactly:

```text
private_outing_label             unique nonempty string
acquisition_start_utc            timezone-aware ISO-8601 string
separate_physical_session        true
independence_basis_private       nonempty string
mcap_basenames_private           nonempty array of unique .mcap basenames
```

`independence_basis_private` records the operational evidence used by the data
owner, such as a separately initiated vehicle/data-collection session. It is
not interpreted as a model feature or as proof of probabilistic independence.
Road type, speed, curvature, confidence, residual magnitude, and expected model
performance are forbidden manifest fields and cannot affect outing identity or
split assignment.

The manifest covers only newly acquired MCAPs. Every case-insensitive `.mcap`
file discovered recursively below the supplied new-data root must appear
exactly once by basename, and the manifest may contain no missing, extra,
duplicate, non-file, or path-qualified entry. Discovered basenames must
themselves be unique. The workflow hashes the exact manifest bytes and every
MCAP byte stream with SHA-256. A malformed manifest, required attestation field
that is not literally `true`, open acquisition batch, coverage mismatch,
duplicate basename, or file that cannot be opened and hashed is a usage error
and produces no output directory. A hashable file whose MCAP container cannot
be decoded is instead a fixed technical failure retained in the audit.

`acquisition_batch_closed`, `created_before_outcome_inspection`,
`separate_physical_session`, `independence_basis_private`, and a null
`prior_successful_lock_sha256` are data-owner declarations. The workflow checks
their required type, value, and internal consistency; it cannot verify that the
declarations are truthful or that an undeclared prior lock does not exist. The
lock and summary record them as `declared_not_independently_verified`.
Outcome-blindness therefore rests on these prospective declarations, the
immutable artifact record, and the final-outing embargo, not on an impossible
machine verification.

Changing an outing label, membership, timestamp, declaration, basename, or raw
file byte after a successful lock changes lineage and invalidates the complete
lock. It is never treated as an in-place correction.

The first successful v0.17 lock is binding. Its reviewed
`independent_outing_lock.json` SHA-256 must be added to
`docs/current_status.md`, creating the project-level accepted-lock record. A
successful re-execution with identical manifest bytes, raw bytes, reviewed
code version, and contract is a reproduction of the same logical lock, not a
second lock; it must produce identical four-file bytes, lock hash, roles, and
opaque IDs. A different successful lock over any overlapping raw file content
is a contract violation unless it is a declared superseding run under a dated,
independently reviewed amendment. Such a run must supply the exact prior lock
to the CLI; the workflow verifies its declared hash, successful status,
raw-file hash map, and at least one overlapping raw file SHA-256 before writing
output. It records the prior lock hash and overlap count in both new JSON files.
A disjoint later corpus is a separate study/version and cannot silently replace
the accepted v0.17 final cohort.

The workflow cannot discover an omitted prior lock outside its inputs. A null
prior-lock declaration is therefore recorded as an attestation, while the
accepted hash in `docs/current_status.md` and independent review provide the
durable external check. A failed `E < 7` audit assigns no roles and is not a
successful lock; the existing versioned retry path remains available while all
failed outputs are retained.

## Fixed outcome-blind technical eligibility

Technical intake may inspect only file bytes, container metadata, topic/schema
identity and counts, source timestamps, topology enum identity, fixed geometry-
eligibility states, and counts/durations derived from those states. It must not
export or expose signed residual vectors, residual magnitudes or summaries,
condition values or distributions, planner quantities, likelihoods, generated
samples, or model metrics. The six feature values may be computed in memory
only to apply their already reviewed availability/finite-value gates; no value
or aggregate leaves that eligibility calculation.

File-level raw usability reuses the reviewed v0.12.1 rules:

- the file is nonempty, readable, and not a later byte-duplicate;
- estimate, map, and odometry topics are present under their accepted schemas
  and encodings;
- estimate source timestamps are present and strictly increasing; and
- exact manifest coverage is retained without an inferred assignment.

An unusable file remains in the audit with every failure code. It contributes
no usable duration or eligible frame, but it does not silently remove the
outing or any other recording from provenance.

Frame eligibility reuses the frozen v0.13.1 rules without exposing numeric
targets or features: SENSOR_TOPOLOGY, complete finite H100 geometry on exactly
`0, 5, ..., 100 m`, anchor distance at most `1.0 m`, accepted estimator,
estimate, and map states, and availability of all six schema-v1 causal
features. The preceding-MCAP odometry exception remains limited to the exact
reviewed 50 ms speed bracket. No residual-value, heading, confidence-magnitude,
or model-performance threshold may be added.

A new outing is technically eligible only when all of these fixed conditions
hold:

1. it has at least one raw-usable recording;
2. raw-usable recording intervals are globally monotonic and non-overlapping
   in internal source time within the declared outing, and the sum of their
   non-overlapping estimate-source durations is at least `120.0 s`;
3. every EDP message with otherwise accepted estimator/estimate geometry and
   paired H100 reference geometry is classified SENSOR_TOPOLOGY; any LANE_MAP,
   unknown, or ambiguous classification in that candidate set makes the whole
   outing mixed-source and ineligible for the primary cohort;
4. it contains at least `500` v0.13.1-eligible H100 frames after the fixed
   frame rules; and
5. every eligible frame is retained exactly once in a nonempty gap-aware
   sequence; an unaccepted MCAP boundary splits the sequence rather than being
   crossed or deleting a frame.

The 120 s and 500-frame requirements are prospective engineering support
gates, not a formal power calculation and not evidence that frames are
independent. An outing failing either remains fully reported as ineligible.
No replacement recording or partial outing may be chosen after seeing a
residual value.

Cross-MCAP continuity is assessed with the existing 200 ms source-gap and
schema/timestamp rules. Accepted continuity may join sequences while retaining
every original recording ID. Rejected boundaries split sequences; they do not
turn one declared outing into multiple independent units.

## Availability gate and deterministic split

Let `E` be the number of technically eligible new outings. The legacy corpus
contributes one development outing, so the total independent-outing count is
`E + 1`.

The acquisition gate passes only when `E >= 7`, giving at least eight total
outings including the legacy development outing. The 8--12 target in
`docs/modeling_plan.md` does not state whether the legacy outing counts toward
it; this contract explicitly adopts the inclusive reading. Because every
final-test outing must come from new data, that choice affects the development
pool but does not reduce the new untouched final set. If more than 11 new
outings are eligible, none is discarded to force an upper limit. The target
remains an engineering planning rule rather than a formal sample-size analysis.

Within the 8--12 total-outing planning window, the formula below assigns two
untouched final outings when `E` is 7--9 (8--10 total) and three when `E` is
10--11 (11--12 total). The evidential weight of a later final claim rests on
those two or three independent final outings, not on all 8--12 outings. The
total primarily governs development support and must never be reported as the
sample size of the untouched evidence.

If `E < 7`, the workflow writes a complete `insufficient_independent_outings`
audit, assigns no cohort role, and authorizes neither residual inspection nor a
final comparison. More data may be added only through a new manifest and a new
versioned output while the failed batch remains immutable. If outcomes from an
outing have already been inspected, that outing is permanently
development-only and cannot enter a later final-test candidate set.

When the gate passes, each eligible new outing receives an immutable
content-only fingerprint. Sort the lowercase 64-character SHA-256 values of
all its declared MCAP byte streams as ASCII bytes, retaining repeated entries,
and encode each value as:

```text
lowercase_file_sha256_ascii || LF
```

Define `outing_fingerprint_sha256` as SHA-256 over the concatenated encodings.
Every declared outing fingerprint must be unique; identical fingerprints are a
lineage error rather than an extra tie-break opportunity. Define the split
score as SHA-256 over:

```text
"MPR-v0.17-final-split-v1" || NUL || outing_fingerprint_sha256_ascii
```

The number of final outings is fixed as:

```text
max(2, ceil((E + 1) / 5))
```

The workflow must assert `2 <= final_count < E` before assigning a role. The
inequality follows from `E >= 7`, but it remains an explicit defensive
invariant so a future arithmetic change cannot consume all new development
outings.

Eligible new outings are sorted by split-score bytes, then fingerprint bytes
as an explicit collision tie-breaker. The first `final_count` receive
`final_test`; every remaining eligible new outing receives `development`.
Ineligible outings receive `excluded`. Opaque `outing_###` identifiers are
assigned independently in ascending fingerprint order. Input discovery order,
JSON array order, local path, basename, private label spelling, and acquisition
time do not alter this split. A cosmetic rename changes manifest/provenance
lineage and therefore requires reconciliation, but it cannot reroll the
content-only fingerprint or split assignment.

This deterministic hash assignment is intentionally not stratified using
speed, curvature, confidence, road type, H100 residuals, or model results. With
few outings it may produce an imbalanced final set; that imbalance is retained
and reported rather than repaired after inspection.

## Final-outing embargo

After a successful lock, development-outing data may be processed to implement
and verify the later evaluation pipeline. Final-test outing content remains
embargoed. Before the separate final-comparison contract is independently
approved and its implementation passes synthetic and development-only tests,
only the following final-outing evidence may be read:

- immutable file and manifest hashes;
- opaque outing/recording identity and cohort role;
- raw usability, fixed eligibility, duration, frame, and sequence counts; and
- fixed exclusion or boundary codes.

No final-outing residual coordinate or summary, feature value or distribution,
model prediction, likelihood, sample, metric, plot, or planner result may be
opened or logged. The intake implementation must not import a modeling,
sampling, planner, evaluation, or visualization module.

After lock, a final outing is never replaced because its eventual H100
residuals or model metrics are inconvenient. A raw-byte or lineage mismatch
invalidates evaluation. A later technical failure is reported as a failed or
incomplete final evaluation under the separately reviewed rule; it does not
trigger silent reassignment.

## Fixed v0.17 outputs

The future command has exactly this public surface; the support thresholds and
split rule are constants rather than command-line choices:

```bash
python -m lane_residuals.cli.independent_outing_intake \
  NEW_MCAP_ROOT \
  --acquisition-manifest PRIVATE_ACQUISITION_MANIFEST.json \
  --output-directory NEW_EMPTY_OUTPUT_DIRECTORY \
  [--prior-successful-lock PRIOR_INDEPENDENT_OUTING_LOCK.json] \
  [--log-level INFO]
```

`--prior-successful-lock` is absent for an initial run. It is mandatory exactly
when the manifest declares a prior successful lock, forbidden otherwise, and
must identify that exact strict-JSON lock artifact. Supplying it does not by
itself authorize supersession; the paired non-null amendment identifier remains
mandatory and is recorded as a data-owner declaration.

`--log-level` accepts `DEBUG`, `INFO`, `WARNING`, or `ERROR`, defaults to
`INFO`, and changes console verbosity only.

The future command writes exactly four private files to a new empty versioned
directory:

```text
independent_outing_recordings.csv
independent_outings.csv
independent_outing_lock.json
independent_outing_intake_summary.json
```

`independent_outing_recordings.csv` contains one row per discovered MCAP in
deterministic basename order: opaque and private outing identity, private
basename and relative path, byte size and SHA-256, raw-usability fields,
source-time bounds and duration, fixed topic/schema evidence, fixed topology
and H100-eligibility counts, original recording identity, and all failure or
boundary codes.

`independent_outings.csv` contains one row per declared outing in opaque-ID
order: file and usable-recording counts, summed usable duration, topology and
eligible-frame/sequence counts, every eligibility check, eligibility status,
fingerprint, split score and rank when authorized, and cohort role.

`independent_outing_lock.json` records the exact source and manifest hashes,
canonicalized private-to-opaque mapping, raw file hash map, eligibility rules,
all outing fingerprints, the fixed salt and split arithmetic, locked roles,
legacy development count, attestation limits, prior-lock declaration and
verification evidence, and explicit final-outing embargo. Strict JSON forbids
NaN and infinity.

`independent_outing_intake_summary.json` records file/outing counts, duration
and support counts, non-mutually-exclusive failure counts, availability-gate
status, role counts, attestation status, prior-lock hash and overlap count when
applicable, output hashes, claim limits, and the next authorized action. It
contains no residual, condition, model, or planner value.

After syntactically valid exact-coverage input, the workflow always writes all
four audit files. It exits `3` when `E < 7` and no roles are assigned. It exits
`0` when `E >= 7` and the deterministic lock is complete; transparently
reported ineligible extra recordings or outings do not invalidate that lock.
Usage, manifest-schema, exact-coverage, hashing, lineage, or output-directory
errors exit `2` before creating output. Existing or nonempty output directories
are never overwritten. Raw MCAPs are never copied.

All four outputs and the private acquisition manifest remain outside version
control. Only code, tests, contracts, and non-private documentation are
committed. All four files are byte-deterministic for the same manifest bytes,
raw bytes, reviewed code version, and contract. They contain no absolute local
path, wall-clock run timestamp, or environment-dependent ordering.

## Implementation acceptance before real data

Implementation starts only after focused independent `GO` on this amended
contract. Synthetic tests must prove:

- strict manifest schema, prospective attestations, and exact recursive MCAP
  coverage;
- paired null/non-null prior-lock fields, optional CLI-input coupling, exact
  prior-lock hash/status/raw-map validation, and overlap counting;
- duplicate basename/content and raw-usability behavior;
- fixed eligibility arithmetic at the 120 s, 500-frame, and seven-new-outing
  boundaries;
- content-only split invariance to discovery, path, basename, private-label,
  acquisition-time, and JSON-array order;
- exact fingerprint, salt, final-count, rank, opaque-ID, and role assignment;
- `2 <= final_count < E` and unique declared-outing fingerprints;
- explicit decoupling of fingerprint-ordered opaque IDs from split-score-
  ordered roles, including a fixture in which those two orders differ;
- no role assignment when the availability gate fails;
- immutable output, strict schema, hash lineage, no extra files, and no
  overwrite;
- byte-identical four-file reproduction for identical inputs, with no absolute
  path, run timestamp, or environment-dependent ordering;
- absence of residual, condition, model, planner, and figure fields from every
  output; and
- CLI exit statuses `0`, `2`, and `3`.

The complete Python 3.10/3.12 test suite must pass. The implementation review
must also confirm that the workflow has no modeling or planner dependency.
Synthetic success does not authorize final-outing decoding beyond the intake
allowlist.

## Next phase after a successful real lock

After the real four-file lock is independently reconciled, a separate final-
comparison predeclaration must fix, before any embargoed value is read:

- the exact legacy and new development training inputs;
- frozen model families, condition schema, hyperparameters, standardizers,
  fitting and convergence rules;
- final-test sequence construction and failure handling;
- sample counts and seeds;
- outing-macro primary metrics, intervals or descriptive rules, and decision
  classification; and
- exact claim limits and reporting of every final outing.

That later contract must be reviewed before evaluator implementation and before
any final-outing residual, feature, model, or plot is inspected. Development
results cannot change the hash-locked final membership.

## Interpretation and stop rules

v0.17 may state only that the acquisition batch did or did not meet the fixed
outcome-blind availability gate and which immutable opaque outings were locked
to each role. It cannot state model quality, final model selection,
independent-journey generalization, planner benefit, BMW-planner behavior,
safety, comfort, production readiness, or physical ground-truth accuracy.

The phase does not authorize RC-GAN, schema-v2 feature search, a new AR ceiling,
another current-outing diagnostic, BMW-planner transfer, or final evaluation.
Any change to the manifest schema, eligibility gates, fingerprint/split rule,
embargo, or outputs after independent review requires a dated amendment and
focused re-review before use.
