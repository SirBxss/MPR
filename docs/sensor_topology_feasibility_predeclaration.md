# v0.18.0 sensor-topology H100 feasibility predeclaration

Status: prospective draft dated 2026-09-14. This document was written after
the accepted negative v0.17.1 batch01 EDP audit and before MPR decoded or
summarized any standalone sensor-topology descriptor, geometry, H100-pair
count, residual, condition, model, or planner result from that closed batch.
The data owner's earlier Lichtblick topic/type observation is recorded
separately as user-reported evidence. This contract requires focused
independent review before implementation or private execution.

Prospective contract revision:
`v0.18.0-prospective-2026-09-14-sensor-topology-feasibility-a0`.

This phase asks whether `/adp/lane_topology_sensor_based` can provide the
estimate-side geometry for a future residual target. It is a privacy-safe
technical feasibility audit, not a silent replacement of
`/adp/estimated_drive_paths`, not a residual-dataset build, and not a model
experiment.

## Why this is a separate phase

The reviewed v0.17.1 adapter decoded all 17,163 EDP messages in the 86-file
batch01 outing and restored 5,289 H100-ready EDP candidates. Every such
candidate was `ROAD_TOPOLOGY_SOURCE_LANE_MAP`; none was
`ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY`. The frozen v0.17 primary gate therefore
retained zero eligible frames and assigned no cohort role. That result and its
four output files remain immutable negative evidence.

Leon subsequently advised the data owner that the standalone
`/adp/lane_topology_sensor_based` topic is the preferable estimate source.
This is recorded as user-reported domain guidance, not as independently
verified producer provenance. The guidance is scientifically plausible
because it avoids the EDP producer's per-cycle map-preferred source selection,
but the topic name alone does not prove coordinate semantics, ego-lane
identity, H100 coverage, or independence from map inputs.

Changing the estimate signal changes the modeled quantity:

```text
historical target := EDP keep-lane path minus aligned RLMB pseudo-reference

candidate target  := sensor-derived ego-lane centreline
                     minus aligned RLMB pseudo-reference
```

The historical EDP models and metrics remain valid only for their accepted EDP
target. They cannot be relabelled, pooled with, applied to, or compared as if
they were fitted to the candidate sensor-lane target. A later target adoption
and any refitting require a separate reviewed contract and sufficient
independent outings.

## Evidence classes and unresolved producer questions

The audit and its interpretation keep these evidence classes separate:

1. **Accepted MPR evidence**: immutable v0.17.1 lineage and counts.
2. **MPR-observed structural evidence**: MCAP topic/schema/descriptors,
   message counts, field presence, reconstruction states, coverage states, and
   timestamp-pairing states produced by the future audit.
3. **BMW-source evidence**: exact producer and interface semantics returned by
   a read-only investigation of the unavailable BMW repository.
4. **User-reported domain guidance**: Leon's recommendation to prefer the
   standalone sensor-topology topic.
5. **Inference**: any interpretation not established by one of the first four
   classes.

Before a sensor-topology residual target can be adopted, BMW-source evidence
must establish:

- the exact Protobuf file, message, version, and producer for
  `/adp/lane_topology_sensor_based`;
- the coordinate frame and reference point of every geometry pool;
- source-timestamp meaning and publication rate;
- the exact metadata that identifies the current ego-lane segment;
- whether `drive_path_range`, paired camera boundaries, or another binding is
  the intended ego-lane centreline representation;
- the meaning and indexing of predecessor/successor links and boundary ranges;
- whether the topic can contain map-derived, fused, artificial, or fallback
  geometry despite its name;
- whether the producer consumes lane-map or RLMB inputs directly or
  indirectly; and
- any guaranteed or configured forward range.

Missing BMW-source evidence does not prevent the structural audit from
reporting what is present in the closed MCAPs. It does prevent that evidence
from being called an independent sensor estimate or used to calculate a
residual.

## Primary question and fixed non-questions

The only primary question is:

> In the already closed 86-file batch01 outing, how much structurally
> reconstructible standalone sensor-lane geometry can be synchronized with
> the unchanged RLMB pseudo-reference and cover the canonical 0--100 m
> horizon under strict, predeclared rules?

The audit may report counts and failure states needed to answer that question.
It must not:

- calculate or export a signed or unsigned residual;
- inspect residual magnitude, distribution, station profile, or plot;
- calculate, export, or summarize any of the six model conditions;
- construct sequences, assign an outing role, or amend the v0.17 cohort lock;
- fit, sample, rank, or evaluate a model;
- execute a planner;
- inspect `/adp/lane_topology_map_based` as an alternative reference;
- fall back to EDP, fusion, map-based, or artificial estimate geometry;
- tune geometry, pairing, coverage, or plausibility thresholds from the real
  result; or
- claim independence, physical ground truth, model validity, planner benefit,
  safety, or generalization.

The exact reference remains `/adp/road_lane_map_based`. RLMB remains a
pseudo-reference, not ground truth. Holding the reference fixed isolates the
effect of changing only the estimate-side source.

## Exact private input lineage

The first and only authorized real execution consumes the same closed batch01
lineage as the accepted v0.17.1 audit:

- the recursive root containing the same 86 MCAP byte streams;
- the exact prospective
  `independent_outings_v017_batch01.private.json` manifest bytes; and
- the complete preserved v0.17.1 four-file intake directory.

Before decoding either road topic, the future workflow must validate:

- exactly the four expected v0.17.1 files and no extra file;
- the reviewed v0.17.1 contract revision and negative status;
- null roles/ranks/scores and unauthorized split assignment;
- the accepted manifest SHA-256;
- all four recomputed v0.17.1 output hashes and their sibling reconciliation;
- exact recursive manifest coverage of the supplied MCAP root;
- the same unique 86-entry basename/SHA-256 map; and
- the same content-only outing fingerprint.

Any mismatch is a usage/lineage error and must occur before the new output
directory is created. No raw MCAP, manifest, v0.17.0 output, or v0.17.1 output
may be changed or copied.

The audit does not inspect the accepted 67-file legacy lineage. A later legacy
sensor-topology audit is a separate decision because it could enable a new
development dataset and therefore requires its own reviewed scope.

## Fixed topics, schemas, and descriptor identity

The future workflow reads exactly:

```text
estimate topic   /adp/lane_topology_sensor_based
reference topic  /adp/road_lane_map_based
message encoding protobuf
expected root message name Adp.Perception.Road
```

Topic absence, schema-name drift, non-Protobuf encoding, decoding failure, and
multiple descriptor generations are reported explicitly and never repaired by
another topic.

For every decoded message, descriptor identity is derived only from:

```text
sha256(message.DESCRIPTOR.file.serialized_pb)
```

It must not be derived from an MCAP schema-record hash, caller-provided label,
filename, or an audit-provided fingerprint. The audit may inventory previously
unseen descriptors and their non-numeric field structure. Discovery does not
create an allow-list or establish semantic compatibility. No descriptor may be
hard-coded after observing batch01 without a dated amendment and focused
review.

The schema inventory records field numbers, names, labels, scalar/message/enum
types, referenced full names, oneof membership, and serialized file-descriptor
SHA-256. It records no option value that contains a local path and no numeric
message payload.

## Structural geometry classes

Every sensor-topic message and every original lane segment is retained in
counts even when reconstruction fails. A message may contribute to multiple
diagnostic structure counts, but each count's definition is fixed.

An **explicit ego candidate** requires exactly one segment to be identified by
an explicit message- or segment-level ego/host/current-lane binding. The future
implementation must enumerate the exact descriptor-owned binding used. Broad
name guessing and nearest-origin lane selection are prohibited for candidate
readiness. Missing, false, conflicting, multiple, out-of-range, or
structurally ambiguous metadata receives a distinct failure state.

Two estimate geometry classes are audited separately:

1. **Direct-path structure**: the unique explicit ego segment exposes a valid
   `drive_path_range` with at least two finite points.
2. **Camera-boundary structure**: the unique explicit ego segment exposes
   valid left and right `camera_based` lane-boundary ranges; every referenced
   pool range is integral, nonnegative, in range, nonempty, and resolves to at
   least two finite points per side.

For the sensor estimate, `map_based` and `artificial` boundary ranges are never
fallbacks. Direct-path and camera-boundary counts remain separate because the
BMW-source meaning of the direct path is not yet established. If both are
present, neither silently overrides the other in the report.

Camera-boundary midpoint reconstruction, when structurally possible, reuses
one fixed diagnostic algorithm:

- concatenate each side's ordered boundary polylines, orienting the next
  polyline by the nearest endpoint and removing only a duplicate junction;
- orient the right side to minimize paired start/end separation;
- parameterize each side by its own geometric arc length normalized to
  `[0, 1]`;
- linearly interpolate both sides on
  `max(left_point_count, right_point_count)` equally spaced normalized
  stations; and
- take the Cartesian midpoint of the two interpolated sides.

The midpoint is diagnostic geometry, not a validated physical centreline.
Median reconstructed width must be finite and within `[1.0, 10.0] m`, matching
the existing legacy parser's fixed plausibility boundary. The report records
only pass/failure counts, never a width value or distribution.

Direct paths and reconstructed midpoints are converted separately to an
ego-relative station axis by the existing projection/orientation primitive.
Neither class may borrow points from an adjacent segment or follow successor
links in v0.18.0. This intentionally distinguishes single-segment availability
from a future, source-validated topology-chain design.

## Reference, synchronization, and H100 states

RLMB handling is unchanged from the accepted current pipeline:

- require exactly one metadata-confirmed ego segment with direct drive-path
  geometry;
- follow only a unique explicit successor chain;
- never guess at a branch, missing successor, cycle, or unavailable segment;
- allow at most 16 segments;
- require each junction gap to be at most `1.0 m`;
- require each junction heading change to be at most `30 degrees`; and
- retain every termination/failure reason.

Sensor and reference messages are paired by embedded source timestamp only,
using the existing deterministic mutual-nearest rule with maximum absolute
delta `50 ms`. Log/publish time is diagnostic identity only and cannot rescue
a missing source timestamp. Every source timestamp must be integral; duplicate
or non-monotonic per-topic source time is reported and cannot be silently
reordered into readiness.

Pairing is recording-local in v0.18.0. No sensor or reference geometry crosses
an MCAP boundary, even when adjacent files belong to the same physical outing.
This keeps every per-recording H100 count independently reconcilable and avoids
introducing a continuity rule into a feasibility audit.

For each of the two estimate geometry classes, an **H100 structural pair**
requires all of the following:

1. the strict estimate structure for that class;
2. an accepted RLMB ordered ego-lane path;
3. a mutual-nearest source-time pair within `50 ms`;
4. projection of the estimate origin footpoint onto RLMB at finite distance no
   greater than `1.0 m`;
5. estimate coverage of every canonical station `0, 5, ..., 100 m` without
   extrapolation; and
6. RLMB coverage from the aligned anchor through `+100 m` without
   extrapolation.

No residual is needed to evaluate these Boolean states. Direct-path and
camera-boundary H100 counts remain separate and are called **structural**, not
usable model pairs. Producer provenance, target semantics, causal features,
sequence integrity, outing support, and independent-outing count remain
unevaluated.

All non-H100 counts are message-level. `explicit_ego_candidate_count` counts
sensor messages with exactly one structurally identified ego segment.
`direct_path_structure_count` and `camera_boundary_structure_count` count
sensor messages for which that same unique segment passes the respective
structure rule. Each mutual-nearest sensor/reference message pair contributes
at most one direct-path H100 pair and at most one camera-boundary H100 pair.
The corpus summary is the integer sum of the 86 per-recording rows. A recording
with a missing timestamp or a non-strict sensor or reference source-time stream
has zero H100 structural pairs; no valid-looking subset is selected from it.

The per-recording `failure_codes` field is a sorted unique subset of this
closed v0.18.0 vocabulary:

```text
sensor_topic_missing
reference_topic_missing
sensor_schema_or_encoding_mismatch
reference_schema_or_encoding_mismatch
sensor_descriptor_unavailable
reference_descriptor_unavailable
sensor_stream_decode_failed
reference_stream_decode_failed
sensor_source_timestamp_missing
reference_source_timestamp_missing
sensor_source_timestamps_not_strict
reference_source_timestamps_not_strict
sensor_ego_binding_unreviewed
sensor_ego_metadata_missing
sensor_ego_metadata_invalid
sensor_ego_segment_not_unique
sensor_direct_path_range_invalid
sensor_direct_path_geometry_invalid
sensor_camera_boundary_range_invalid
sensor_camera_boundary_geometry_invalid
sensor_camera_boundary_width_implausible
reference_ego_drive_path_not_unique
reference_successor_chain_invalid
reference_h100_coverage_incomplete
source_time_pair_unavailable
anchor_invalid_or_exceeds_1m
sensor_direct_path_h100_coverage_incomplete
sensor_camera_boundary_h100_coverage_incomplete
```

An implementation may retain a more detailed internal exception, but it must
map it to exactly one of these stable exported codes. A new exported code is a
contract amendment. Multiple codes may apply to one recording, so failure
counts are explicitly non-mutually-exclusive.

## Fixed command and outputs

The proposed implementation has exactly this public surface:

```bash
python -m lane_residuals.cli.sensor_topology_feasibility \
  NEW_MCAP_ROOT \
  --acquisition-manifest PRIVATE_ACQUISITION_MANIFEST.json \
  --preserved-intake-directory PRESERVED_V0171_OUTPUT_DIRECTORY \
  --output-directory NEW_EMPTY_OUTPUT_DIRECTORY \
  [--log-level INFO]
```

All thresholds and topic names are constants, not command-line choices.
`--log-level` accepts only `DEBUG`, `INFO`, `WARNING`, or `ERROR` and changes
console verbosity only.

After valid lineage input, the command writes exactly three private files:

```text
sensor_topology_recordings.csv
sensor_topology_schema_inventory.json
sensor_topology_feasibility_summary.json
```

`sensor_topology_recordings.csv` contains one deterministic basename-ordered
row per MCAP with exactly these columns:

```text
relative_path_private
basename_private
file_size_bytes
file_sha256
sensor_topic_present
reference_topic_present
sensor_message_count
reference_message_count
sensor_decoded_count
reference_decoded_count
sensor_descriptor_file_sha256s
reference_descriptor_file_sha256s
sensor_source_timestamp_present_count
reference_source_timestamp_present_count
sensor_source_timestamps_strict
reference_source_timestamps_strict
explicit_ego_candidate_count
direct_path_structure_count
camera_boundary_structure_count
direct_path_h100_structural_pair_count
camera_boundary_h100_structural_pair_count
failure_codes
```

Descriptor sets and failure-code sets are semicolon-delimited, sorted, and
deduplicated. Boolean values serialize as lowercase `true`/`false`. Counts and
byte sizes are nonnegative decimal integers. No timestamp, coordinate,
boundary width, station value, projection distance, or residual appears.

`sensor_topology_schema_inventory.json` contains exactly:

```text
version
contract_revision
purpose
descriptor_identity_rule
topics
```

Its fixed values are `version = "0.18.0"`, the contract revision above,
`purpose = "sensor_topology_schema_inventory"`, and
`descriptor_identity_rule =
"sha256(message.DESCRIPTOR.file.serialized_pb)"`.

`topics` is an array sorted by topic and then descriptor SHA-256. Each item
contains exactly:

```text
topic
message_count
mcap_schema_names
mcap_schema_encodings
message_encodings
descriptor_file_sha256
root_message_full_name
field_inventory
audit_support_status
```

The schema/encoding arrays are sorted and unique. `field_inventory` is a
recursively full-name-sorted array whose entries contain exactly `full_name`,
`number`, `label`, `kind`, `referenced_full_name`, and `oneof_name`.
`full_name` is the Protobuf field full name; `number` is a positive integer;
`label` is `optional`, `required`, or `repeated`; `kind` is the canonical
Protobuf scalar, enum, or message type name; and the two final values are
strings or JSON null. Recursion stops on an already visited message full name
and records that reference without expanding it again.
`descriptor_file_sha256` is JSON null when descriptor bytes are unavailable,
and null identities sort after hashes. `audit_support_status` is one of
`structure_observed`, `decode_failed`, or `descriptor_unavailable`. It is not a
semantic compatibility decision.

`sensor_topology_feasibility_summary.json` contains exactly:

```text
version
contract_revision
purpose
lineage_status
preserved_intake_contract_revision
preserved_intake_lock_sha256
manifest_sha256
raw_mcap_count
raw_basename_sha256_map_sha256
topics
station_grid_m
maximum_source_delta_ms
maximum_anchor_distance_m
reference_chain_limits
sensor_descriptor_file_sha256s
reference_descriptor_file_sha256s
sensor_message_count
reference_message_count
sensor_decoded_count
reference_decoded_count
explicit_ego_candidate_count
direct_path_structure_count
camera_boundary_structure_count
direct_path_h100_structural_pair_count
camera_boundary_h100_structural_pair_count
recording_failure_counts
output_sha256
technical_feasibility_status
producer_provenance_status
scientific_target_adoption_authorized
claim_limits
next_authorized_action
```

Its fixed scalar and object values are:

```text
version                         "0.18.0"
contract_revision               "v0.18.0-prospective-2026-09-14-sensor-topology-feasibility-a0"
purpose                         "sensor_topology_h100_structural_feasibility"
lineage_status                  "passed"
topics.estimate                 "/adp/lane_topology_sensor_based"
topics.reference                "/adp/road_lane_map_based"
station_grid_m                  [0.0, 5.0, ..., 100.0]
maximum_source_delta_ms         50.0
maximum_anchor_distance_m       1.0
reference_chain_limits.max_segments                     16
reference_chain_limits.maximum_junction_gap_m           1.0
reference_chain_limits.maximum_junction_heading_deg     30.0
producer_provenance_status      "requires_reviewed_bmw_source_evidence"
scientific_target_adoption_authorized false
```

`preserved_intake_lock_sha256` is the recomputed hash of the exact v0.17.1
`independent_outing_lock.json`. `raw_basename_sha256_map_sha256` is SHA-256
over the v0.17.1 raw map sorted by basename as UTF-8 and encoded one entry at a
time as:

```text
basename_utf8 || NUL || lowercase_file_sha256_ascii || LF
```

Every basename and file hash is first reconciled with the manifest and raw
bytes. `output_sha256` has exactly the keys
`sensor_topology_recordings.csv` and
`sensor_topology_schema_inventory.json` in that order. `recording_failure_counts`
has every observed failure code as a key in lexical order and positive integer
counts only; absent codes are omitted.

`claim_limits` is exactly this ordered string array:

```text
structural_feasibility_only
rlmb_is_pseudo_reference_not_ground_truth
producer_independence_not_established
sensor_centreline_semantics_not_adopted
no_residual_or_condition_values_computed_or_exported
no_cohort_role_or_model_evaluation
no_independent_outing_generalization
```

When a structural H100 count is positive, `next_authorized_action` is
`obtain_reviewed_bmw_source_evidence_and_predeclare_target_adoption`; when
both counts are zero it is
`retain_negative_audit_and_review_sensor_schema_or_acquisition_configuration`.

`output_sha256` contains exactly the SHA-256 values of the recordings CSV and
schema-inventory JSON; the summary cannot hash itself. Strict JSON forbids
duplicate keys, NaN, and infinity and uses deterministic formatting.
`technical_feasibility_status` is `structural_h100_candidates_observed` when
either structural H100 count is positive and `no_structural_h100_candidates`
otherwise. `producer_provenance_status` remains
`requires_reviewed_bmw_source_evidence`. Consequently
`scientific_target_adoption_authorized` is always `false` in v0.18.0.

Lineage/schema/usage errors exit `2` before output. A complete zero-candidate
audit exits `3`; a complete positive structural audit exits `0`. Both complete
statuses write all three files and are retained. Existing or nonempty output
directories are never overwritten.

## Privacy, determinism, and implementation boundaries

All three outputs, raw MCAPs, and the private acquisition manifest remain
outside Git. The outputs may contain private basenames, relative paths, file
hashes, schema identities, and aggregate technical counts. They contain no
absolute path, run timestamp, raw payload value, geometry coordinate, residual,
condition, sequence, model, planner, or figure value.

For identical code, contract, manifest bytes, raw bytes, preserved v0.17.1
files, and relative layout, all three output byte streams must be identical.
Changing only the root mount path changes nothing. Changing relative layout
may change only `relative_path_private`, the recordings CSV hash, and the
summary field that records that hash.

The planned implementation follows repository ownership:

- `domain.sensor_topology_feasibility` owns structural state definitions and
  fixed geometry readiness arithmetic;
- `io.sensor_topology_feasibility` owns descriptor inventory and strict
  serialization;
- `workflows.sensor_topology_feasibility` owns v0.17.1 lineage validation,
  decoding orchestration, aggregation, non-overwrite, and output hashes; and
- `cli.sensor_topology_feasibility` owns arguments, logging, and exit mapping.

The workflow may reuse neutral current primitives only after tests prove their
exact behavior. It must not import `legacy.preprocessing`, any residual-dataset
builder, conditional-feature module, model, sampler, planner, evaluation, or
visualization module. Legacy code is implementation evidence, not the new
scientific owner.

## Implementation acceptance before private execution

After focused contract `GO`, synthetic tests must prove at least:

- exact preserved-v0.17.1 file/schema/hash/raw-map reconciliation before
  output creation;
- exact manifest coverage and rejection of missing, extra, duplicate, changed,
  or path-qualified MCAP entries;
- message-owned descriptor hashing and deterministic recursive field inventory;
- exact topic/schema/encoding filtering with no topic fallback;
- per-message and per-segment failure retention;
- strict explicit ego selection and rejection of nearest-origin fallback;
- separation of direct-path and camera-boundary structure;
- prohibition of map/artificial sensor-boundary fallback;
- pool-range type/bounds/cardinality failures, non-finite points, degenerate
  boundaries, reversed side orientation, duplicate junctions, and the fixed
  width boundary;
- unchanged strict RLMB ego selection and successor-chain boundaries;
- source-time-only mutual-nearest pairing, tie behavior, missing/duplicate/
  non-monotonic times, and the exact `50 ms` boundary;
- exact `0, 5, ..., 100 m` coverage without extrapolation and the exact
  `1.0 m` anchor boundary;
- independent direct-path and camera-boundary H100 counts;
- exact three-file schemas, hashes, deterministic bytes, no overwrite, and
  absence of prohibited payload/target/model fields;
- complete zero/positive audit exit codes `3`/`0` and pre-output error code
  `2`; and
- no direct or transitive import of residual construction, conditions,
  sequences, modeling, sampling, planner, evaluation, or visualization.

The complete Python 3.10 and 3.12 suite must pass. A focused implementation
review is required before the real command is run.

## Review and execution order

The order is binding:

1. Commit and push this prospective documentation on a dedicated branch.
2. Obtain the BMW-source trace listed above and preserve it as a private raw
   transcript plus a concise evidence-classified repository document.
3. Obtain Claude's focused review of the exact amended contract commit and
   tree. `AMEND` returns to step 1; only `GO` continues.
4. Implement the audit without touching private MCAPs and verify it entirely
   on synthetic fixtures.
5. Push the exact implementation and obtain focused implementation `GO`.
6. Run once on the closed batch01 into a new empty versioned output directory.
7. Independently reconcile the three output files and review the real result.
8. If no structural H100 candidate exists, stop and retain the negative
   result. If candidates exist, write and review a separate target-adoption
   contract using the descriptor and BMW-source evidence before calculating
   any residual.

No v0.18.0 `GO` authorizes merging by itself. Merge occurs only after the
applicable contract, implementation, and—if executed before merge—real-output
reviews have returned `GO`, CI passes, and the user explicitly chooses to
merge.

## Claim boundary

v0.18.0 may state only whether the closed batch contains structural standalone
sensor-lane H100 candidates synchronized to the unchanged RLMB
pseudo-reference under this contract. A positive result does not prove that
the topic is map-independent, that its midpoint is the producer-intended lane
centre, that the future residual is physically correct, that the outing meets
v0.17 eligibility, that old and new targets are comparable, or that any model
will improve. A zero result does not invalidate the topic outside this
recording/configuration.
