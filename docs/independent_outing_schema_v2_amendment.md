# v0.17.1 estimated-drive-path schema-v2 compatibility amendment

Status: complete. The contract, bounded implementation, and real amended
batch01 output each received focused independent `GO`. Batch01 is an accepted
negative technical audit with no role assignment, not a successful cohort
lock. Its exact result is recorded in
`docs/independent_outing_batch01_v0171_result.md`.

Date: 2026-09-07.

Amendment ID: `v0.17.1-edp-schema-v2-2026-09-07`.

This document proposes one narrow amendment to the reviewed v0.17.0
independent-outing intake contract. It changes only how an estimated-drive-path
message proves that its model parameters are available under the existing
legacy rule and one exact BMW schema-v2 descriptor. It does not change the
scientific unit, prospective manifest, topology policy, geometry thresholds,
causal-input rules, duration or frame gates, deterministic split, embargo, or
claim limits. It makes one additive, exactly specified lineage change to the
two JSON outputs; the four filenames, CSV schemas, and every existing JSON key
remain unchanged.

The evidence and BMW-source trace are recorded in
`docs/bmw_edp_schema_evidence.md`. No residual, condition value, model score,
planner value, or figure was used to formulate this amendment.

## Trigger and necessity

The first closed v0.17 batch was processed under the reviewed v0.17.0 code.
All 86 files were raw-usable, but every file failed geometry conversion because
the decoder required legacy Boolean field 8,
`model_parameters_optional_flag`. A privacy-safe descriptor audit showed that
all 86 files use one exact candidate schema fingerprint, retain the required
path and nested geometry bindings, and omit only that legacy Boolean. A BMW
source trace reports that schema version 2 made `model_parameters` required and
deliberately removed the optional wrapper, its validity-field binding, and the
Boolean while retaining `DrivePath.error`.

Treating every absent field-8 descriptor as compatible would be too broad.
Continuing to require field 8 for the exact reviewed v2 descriptor would reject
available geometry for a reason that no longer exists in that schema. The
amendment therefore preserves the reviewed structural legacy rule and adds
only one exact, evidence-backed v2 descriptor. Other flag-absent schemas remain
fail-closed.

## Exact supported generations

Candidate v2 is selected by SHA-256 of the message's own serialized Protobuf
file descriptor. The generation-validity check must recompute this value from
the decoded message itself:

```python
hashlib.sha256(message.DESCRIPTOR.file.serialized_pb).hexdigest()
```

This is the exact descriptor-only method used by
`domain/path_source_probe._schema_fingerprint` and by the evidence probe that
produced the pinned candidate value. The generation decision must not read
`EstimatedFrameAudit.schema_fingerprint`, because that value enters through a
caller-supplied parameter. It must not use
`domain/geometry_validation._schema_fingerprint`, because that helper hashes
the MCAP schema record's `FileDescriptorSet` whenever `schema.data` is present
and only falls back to the message file descriptor otherwise. Those are
different identities on a real MCAP even though simplified fixtures can make
them appear equal. An MCAP schema-record hash, caller label, cached audit
field, or supplied constant is never generation evidence.

The v0.17.0 legacy rule is preserved structurally so the amendment does not
impose a new fingerprint restriction on already supported v1 descriptors:

| Generation | Descriptor rule | Field-8 rule |
|---|---|---|
| legacy v1 | Preserve the reviewed v0.17.0 structural binding; `f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f` is the observed reference, not a newly exhaustive allow-list | `model_parameters_optional_flag` must be Boolean field 8, be explicitly present, and equal true |
| candidate v2 | `dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4` | field 8 must be absent; no Boolean substitute is invented |

Any other descriptor without the valid legacy Boolean is unsupported and
remains `schema_bindings_incomplete` or a new explicit unsupported-generation
failure. It cannot be accepted merely because its field names resemble the
listed v2 generation. A future flag-absent BMW schema requires a new evidence
record and reviewed amendment.

The exact candidate-v2 fingerprint commits the following observed field
numbers, types, and cardinality. The implementation must still resolve every
field it consumes and fail if a required binding is unavailable:

```text
EstimatedDrivePaths.drive_paths       field 4, repeated DrivePath message
DrivePath.error                       field 1, optional DrivePathError enum
DrivePath.role                        field 2, optional LaneRole enum
DrivePath.model_parameters            field 3, optional ClothoidSplineMinimalParameters message
DrivePath.drive_path_confidences      field 7, repeated double
model_parameters.x_0                  field 1, optional double
model_parameters.y_0                  field 2, optional double
model_parameters.theta_0              field 3, optional double
model_parameters.curvature_0          field 4, optional double
model_parameters.segment_starts       field 5, repeated double
model_parameters.curvature_change     field 6, repeated double
model_parameters.index_0              field 7, optional int64
```

The generation decision must use the hash computed from the message's own file
descriptor inside the validity check. Any candidate-v2 field-number, type, or
cardinality drift changes that hash and fails closed. The schema binding set is
generation-dependent at descriptor resolution: legacy requires the Boolean
field-8 binding, whereas the one exact v2 descriptor requires its absence. A
later relaxation of only the flag-value check would not implement this
amendment because descriptor binding is evaluated first. The legacy path
continues the v0.17.0 binding and flag semantics rather than acquiring a new
descriptor-fingerprint restriction.

## Fixed per-path validity rule

MPR continues to select exactly one `LANE_ROLE_KEEP_LANE` path. Zero or
multiple keep-lane paths remain failures. For the selected path, both
generations require:

1. `error` is known and exactly
   `DRIVE_PATH_ERROR_NO_ERROR`; checking only that it is not UNINITIALIZED is
   forbidden;
2. `model_parameters` yields a message value under the existing v0.17.0
   presence rule; candidate v2 additionally requires explicit presence through
   `ListFields()` or a successful `HasField()` check, so implicit defaults,
   descriptor-only inference, and an allocated-but-absent submessage do not
   satisfy candidate-v2 presence;
3. `x_0`, `y_0`, `theta_0`, and `curvature_0` are available and finite;
4. `segment_starts` has at least two finite, strictly increasing values;
5. `curvature_change` is finite and has exactly
   `len(segment_starts) - 1` values;
6. `index_0` is available, is a non-Boolean integer, and satisfies
   `0 <= index_0 < len(segment_starts)`; explicit Protobuf scalar presence is
   not required because the reviewed int64 binding has an effective default of
   zero; and
7. all existing spline conversion and H100 geometry checks pass unchanged.

Legacy v1 additionally requires field 8 to be explicitly present and literally
true. Candidate v2 additionally requires field 8 to be absent from its exact
descriptor. Model-parameter presence alone never overrides an error value or a
failed structural check.

No fallback path role, default spline, numeric imputation, cross-message carry,
or reinterpretation of fields 10 or 11 is permitted.

## Rules that do not change

The amendment does not alter any of the following reviewed v0.17 rules:

- one physical outing is the independent unit; 86 MCAP chunks remain one
  outing;
- raw files, original v0.17.0 output, and prospective manifest bytes are
  immutable;
- every technical audit remains outcome-blind and exports no raw numeric
  payload values, residuals, feature distributions, model evidence, or planner
  evidence;
- `ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY` remains mandatory over every EDP
  message in the exact otherwise accepted topology-candidate set;
- any LANE_MAP, unknown, or ambiguous source in that set makes the whole outing
  mixed-source and ineligible for the primary cohort;
- the anchor-distance, H100, map, estimator, six causal-input availability,
  odometry, continuity, 120-second, 500-frame, and sequence-integrity rules are
  unchanged;
- at least seven eligible new physical outings are still required before split
  assignment;
- no role is assigned when fewer than seven new outings are eligible;
- split hashing, ranking, final-count arithmetic, final embargo, and claim
  limits remain unchanged;
- the four output filenames, every existing summary/lock key and CSV column,
  exit-code semantics, strict-JSON and no-overwrite discipline, and byte-
  determinism remain unchanged; the summary and lock gain only the additive
  `schema_compatibility_amendment` object specified below; and
- the amendment cannot authorize a model fit, final comparison, planner run,
  schema-v2 feature search, or independent-generalization claim.

The observed majority of LANE_MAP messages is not a reason to relax the
topology gate. The amended run may therefore remain technically ineligible even
after geometry conversion is restored; that would be a correct result.

## Implementation boundary after review

If focused independent review returns `GO`, v0.17.1 may change only:

1. schema-generation classification and path-model validity in the shared
   descriptor/path audit;
2. the geometry converter's use of that reviewed validity result;
3. explicit failure/status reporting needed to distinguish supported legacy,
   supported v2, and unsupported descriptors;
4. intake summary/lock contract revision strings, the exact additive lineage
   object below, and validation of an optional prior failed-audit directory;
5. tests, output-contract documentation, command/runbook documentation, and
   the project hand-off required to freeze the behavior.

Before any real v0.17.1 execution, `docs/output_contracts.md`, exact-schema
tests, and `scripts/inspection/verify_v017_intake_bundle.py` must be updated
together. The workflow and standalone verifier must independently enforce the
same additive lineage contract; updating only the producer is forbidden.

The implementation must not special-case basenames, paths, candidate payload
values, or the observed topology distribution. Synthetic tests must cover:

- a structurally supported legacy descriptor plus Boolean field 8 true passes
  the availability component without a new fingerprint restriction;
- legacy flag false, absent, default-only, or non-Boolean evidence fails;
- exact candidate-v2 fingerprint plus explicit model presence and NO_ERROR
  passes the availability component without field 8;
- a supplied wrong, unrelated, or `None` audit fingerprint and inconsistent
  `schema.data` do not change the generation decision, which uses only the
  decoded message's own file descriptor;
- a fixture whose caller claims the pinned candidate identity while its own
  descriptor contains field 8 with a false or default-only legacy flag fails;
  this deliberately impossible honest-descriptor combination is a regression
  test against trusting caller-supplied generation identity, while the same
  descriptor with an explicitly true Boolean still follows the preserved
  legacy rule;
- v2 parameters present with any non-NO_ERROR enum fails;
- absent parameters, non-finite scalars, short/non-increasing segment starts,
  non-finite changes, count mismatch, missing/non-integer `index_0` (including
  a value that `int()` cannot consume, while rejecting `bool` explicitly), and
  an out-of-range `index_0` fail for both generations;
- an unknown fingerprint with v2-like fields fails;
- candidate-v2 field-number, type, or cardinality drift changes the internally
  computed fingerprint and fails;
- mixed SENSOR_TOPOLOGY/LANE_MAP remains outing-ineligible;
- all-SENSOR synthetic v1 and v2 inputs produce the same downstream geometry
  and eligibility for semantically identical messages;
- outputs remain deterministic, exact-schema, no-overwrite, and free of
  embargoed values; and
- the complete Python 3.10/3.12 suite and independent lock verifier pass.

No real candidate payload may be used to tune a threshold or weaken a test.

## Real-batch execution after implementation review

The preserved v0.17.0 output is never overwritten. After implementation has
its own focused independent `GO` and CI passes:

1. reuse the exact closed-batch manifest bytes with SHA-256
   `8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d`;
2. do not set `superseding_contract_amendment_id`, because that manifest field
   is paired with a prior *successful* lock and the v0.17.0 batch did not
   produce one;
3. execute into a new empty versioned output directory such as
   `outputs/locks/independent_outing_intake_v0171_batch01`;
4. supply the preserved v0.17.0 four-file output directory through the new
   `--amended-from-failed-intake-directory` argument;
5. expect exit status 3, `insufficient_independent_outings`, and no role
   assignment: the unchanged manifest declares one outing, so eligibility is
   at most one and can never meet the seven-new-outing lock threshold;
6. retain all four amended outputs after that expected exit status;
7. run the updated standalone verifier against the raw MCAPs, unchanged
   manifest, preserved v0.17.0 output, and amended outputs; and
8. package the four output files and verifier result for independent review
   before treating the technical counts as accepted evidence.

The amended contract revision is exactly
`v0.17.1-reviewed-2026-09-07-schema-v2-a1`. Both
`independent_outing_lock.json` and
`independent_outing_intake_summary.json` gain exactly one top-level key,
`schema_compatibility_amendment`, with this exact nested schema:

```json
{
  "amendment_id": "v0.17.1-edp-schema-v2-2026-09-07",
  "descriptor_identity_source": "sha256(message.DESCRIPTOR.file.serialized_pb)",
  "allowed_flag_absent_estimate_file_descriptor_sha256": "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4",
  "legacy_estimate_file_descriptor_reference_sha256": "f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f",
  "legacy_validity_rule": {
    "descriptor_rule": "structural_v0.17.0_binding_no_exhaustive_descriptor_allowlist",
    "field_name": "model_parameters_optional_flag",
    "field_number": 8,
    "protobuf_type": "bool",
    "explicit_presence_required": true,
    "required_value": true
  },
  "observed_estimate_file_descriptor_sha256": [
    "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
  ],
  "amended_from_failed_audit": null
}
```

The names deliberately distinguish estimated-path descriptor identities from
`outing_fingerprint_sha256` and `split_score_sha256`. The observed list is
sorted lexicographically, contains only hashes recomputed from decoded message
file descriptors, and is empty only when no estimate message is decoded.

`amended_from_failed_audit` is `null` when the new optional command argument is
absent. When the argument is supplied, it is an object with exactly these keys:

```json
{
  "contract_revision": "v0.17.0-reviewed-2026-09-03-layout-c1",
  "manifest_sha256": "8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d",
  "output_sha256": {
    "independent_outing_recordings.csv": "0f4d0f4e285c676abcadb00b94ee259384867a04330d93fbd6284f7d4d3dabb4",
    "independent_outings.csv": "51c8b42f6c7d31b7af1e8817cf295fee999c06897d5ea12ab3d368002cf41c9e",
    "independent_outing_lock.json": "9ee7565bd800c11773e17917838efdd5ddc3440c6803aa3a8a65631c8a778e60",
    "independent_outing_intake_summary.json": "81f9511575bae84036df98557fa8e63e19db2223e75b0c2cac3cc8d48b96fc0a"
  }
}
```

This object is derived from the supplied directory rather than hard-coded to
batch01. Before writing any output, the workflow must require exactly the four
v0.17.0 filenames, validate their exact original schemas, recompute all four
byte hashes, reconcile the old summary's sibling-output hash map, require
`insufficient_independent_outings` with no assigned roles, reconcile the old
manifest hash with the current manifest bytes, and reconcile the old recording
basename/SHA-256 map with the current raw corpus. Any mismatch is a pre-write
error. For batch01, the recomputed values must also equal the four independently
pinned hashes shown above. The argument is optional for a genuinely new
manifest with no prior failed audit, but is mandatory for the batch01 re-run
specified here.
It is distinct from `--prior-successful-lock`, which remains forbidden for
batch01. The standalone verifier receives the same preserved directory,
recomputes this reconciliation independently, and requires the nested objects
in the new lock and summary to be exactly equal.

No other output key or CSV column changes. The reviewed implementation commit
is recorded in `docs/current_status.md`, not discovered dynamically at runtime.
This creates an explicit, machine-checkable audit trail without misusing the
prior-successful-lock mechanism or making output depend on Git availability.
No unlisted key is permitted in either additive nested object.

## Review gate

Before any implementation, the reviewer must verify:

- the BMW-source evidence supports separate v1/v2 presence semantics;
- exact descriptor pinning is sufficient and not broader than the evidence,
  and the generation decision is recomputed from the message file descriptor
  rather than either audit/schema-record fingerprint surface;
- `error == DRIVE_PATH_ERROR_NO_ERROR` remains mandatory;
- `index_0` and every other existing structural, topology, causal-input,
  duration, sequence, split, embargo, and claim rule remain mandatory;
- the proposed output lineage is enough to reconcile the failed v0.17.0 audit
  with the future v0.17.1 run, and the exact additive object plus failed-audit
  directory interface are neither under- nor over-specified;
- the batch01 exit-3/no-role expectation follows from the unchanged seven-
  outing threshold; and
- no candidate outcome or post-hoc threshold informed the amendment.

The contract `GO` authorized only the implementation boundary above. The
implementation and real batch01 output subsequently received their separate
focused `GO` decisions. The v0.17.0 and v0.17.1 outputs are both immutable
lineage evidence. No review authorizes a gate relaxation, another batch01 run,
model fit, sampling, planner execution, final-outing inspection, or scientific
generalization.
