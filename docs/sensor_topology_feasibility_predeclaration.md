# v0.18.0 sensor-topology 100 m structural-feasibility predeclaration

Status: frozen prospective contract dated 2026-09-15. Focused independent
contract and implementation reviews returned `GO`, and the one authorized
private v0.18.0 run is preserved. That run exposed an exact RLMB descriptor
binding defect. The narrow v0.18.1 correction in
`docs/sensor_topology_reference_schema_amendment.md` subsequently received
corrective `GO`; its one authorized rerun and real-output review are complete
with a negative batch01 result. See `docs/sensor_topology_batch01_v0181_result.md`.
No further run is authorized. This predeclaration otherwise remains the
unchanged a3 scientific boundary. The original a0
draft was written after the accepted negative v0.17.1 batch01 EDP audit and
before MPR decoded or summarized any standalone sensor-topology message from
that closed batch. Three subsequent read-only Copilot traces of the BMW source
changed and then bounded the contract before implementation or private
execution. The third trace resolved all cited tracked paths and rechecked the
technical claims from immutable `HEAD:<path>` blobs. It did not capture the
literal BMW HEAD SHA; that named-revision reproducibility limit is recorded in
the evidence document but no longer blocks the completed contract review.

Prospective contract revision:
`v0.18.0-review-candidate-2026-09-15-sensor-topology-feasibility-a3`.

This phase asks whether `/adp/lane_topology_sensor_based` contains strict,
camera-boundary-derived geometry with at least 100 m of observed contiguous
span at source times that can be paired with independently ready RLMB
pseudo-reference messages. It is a privacy-safe technical audit, not a silent
replacement of `/adp/estimated_drive_paths`, not an H100 residual-pair build,
and not a model experiment.

## Why a3 freezes the amended design

The initial BMW-source trace established four facts that invalidated material
parts of the a0 design:

1. LTSB does not write `drive_path_range`; it publishes no producer-defined
   ego-lane centreline. A midpoint derived from paired camera boundaries is a
   consumer diagnostic only.
2. `ego_lane_segment_indices` contains lateral/branch alternatives, not a
   longitudinal path. Only a single in-range entry is unambiguous.
3. Forward geometry can require successor traversal; some map-informed
   successor segments deliberately carry length but no boundary geometry.
4. The sensor and RLMB physical frame origins are not documented as equal.
   Cross-topic projection, anchor distance, motion compensation, and residual
   sign therefore cannot be evaluated safely.

The trace also showed that LTSB directly consumes HD-map, most-probable-path,
and map-matching inputs. The accurate phrase is **camera-derived boundary
geometry inside a map-influenced topology graph**, not "map-independent sensor
topology".

Accordingly, a1 removed the direct-path arm, added strict camera-only successor
traversal, and replaced the cross-frame H100 structural-pair count with a
source-time-synchronized dual-availability count. No a0 output may be
generated or interpreted.

The second trace then pinned the nested numeric wrapper, mean-validity rule,
CAMERA boundary and SENSOR_TOPOLOGY write sites, stored boundary/vertex order,
arc-length construction, timestamp scalar semantics, and the exact unwritten
range sentinel. It corrected two unsafe a1 assumptions: `size == 0` alone does
not prove `drive_path_range` is unwritten, and a clear mean-invalid bit alone
does not reject the `FLT_MAX` sentinel. The intermediate a2 draft incorporated
those corrections.

The third trace then resolved all 23 cited source files to complete tracked
paths, verified their existence at one `HEAD`, and rechecked each positive
claim from that `HEAD`'s immutable blobs. It corrected one wording detail:
`AddLaneBoundary` has two calls but remains the sole boundary-pool constructor,
and it scoped the no-transform finding specifically to the published boundary
path. The trace did not name the commit behind `HEAD`. Because the MPR audit
uses message-owned descriptors, validates the exact required structure, and
fails closed on drift, that omission limits reproduction of the private
source trace but does not require another BMW query. This a3 revision freezes
the design for focused independent contract review.

## Scientific separation from historical work

The reviewed v0.17.1 adapter decoded all 17,163 EDP messages in the 86-file
batch01 outing and restored 5,289 H100-ready EDP candidates. Every candidate
was `ROAD_TOPOLOGY_SOURCE_LANE_MAP`; none was
`ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY`. The frozen v0.17 gate retained zero
eligible frames and assigned no cohort role. Those four output files remain
immutable negative evidence.

Leon's recommendation to investigate `/adp/lane_topology_sensor_based` is
recorded as user-reported domain guidance. It does not convert the standalone
topic into EDP or validate a new residual target.

Changing the estimate signal would change the modeled quantity:

```text
historical target := EDP keep-lane path minus aligned RLMB pseudo-reference

possible future target := consumer-derived camera-boundary midpoint
                          minus aligned RLMB pseudo-reference
```

The historical EDP models and metrics remain valid only for their accepted EDP
target. They cannot be relabelled, pooled with, applied to, or compared as if
they were fitted to the possible future target. Target adoption, residual
construction, and refitting require a separate reviewed contract and enough
independent outings.

## Evidence classes

Interpretation keeps these classes separate:

1. **Accepted MPR evidence**: immutable v0.17.1 lineage and counts.
2. **MPR-observed structural evidence**: topic/schema/descriptors, counts,
   reconstruction states, span states, and timestamp-pairing states from the
   future audit.
3. **Copilot-confirmed BMW-source evidence**: read-only findings summarized in
   the evidence document; MPR cannot reproduce the unidentified private
   checkout at one named commit.
4. **User-reported domain guidance**: Leon's recommendation.
5. **Inference**: any interpretation not established by the first four.

The third Copilot transcript recorded complete tracked repository-relative
paths and rechecked the claims against immutable `HEAD` blobs, but it did not
record the BMW commit SHA. The traces also did not establish the LTSB frame
origin/axes, nominal publication rate, guaranteed forward extent, vertex
direction relative to travel, or producer behavior across recording
generations. Those gaps remain visible. The whole-message
`topology_source = SENSOR_TOPOLOGY` assignment is source-traced. The missing
commit name is an evidence reproducibility limit; the unresolved physical
semantics remain binding scientific limits.

## Primary question and fixed non-questions

The only primary question is:

> In the closed 86-file batch01 outing, how often does the standalone LTSB
> message contain a strict camera-only, unambiguous ego-lane topology chain
> with at least 100 m of observed contiguous midpoint span, and how often can
> such a message be source-time-paired with an independently H100-ready RLMB
> message?

The audit may report only counts and fixed failure states needed to answer that
question. It must not:

- call the synchronized count an H100 residual pair or usable model pair;
- project any LTSB point onto RLMB or compare their coordinates;
- calculate an anchor distance, transform, signed/unsigned residual, or H100
  station value for LTSB;
- export coordinates, widths, distances, headings, timestamps, or numeric
  message payloads;
- calculate or summarize model conditions;
- construct sequences, assign an outing role, or amend the v0.17 cohort lock;
- fit, sample, rank, or evaluate a model;
- execute a planner or produce a figure;
- inspect `/adp/lane_topology_map_based` as an alternative;
- fall back to EDP, map-based, artificial, or direct-path LTSB geometry;
- use vector order or nearest-origin distance to resolve an ego-lane branch;
- tune a threshold after seeing the private result; or
- claim map independence, ground truth, target validity, safety, planner
  benefit, or generalization.

The reference remains `/adp/road_lane_map_based`. RLMB is a pseudo-reference,
not ground truth. It is decoded only to audit its independent H100 readiness
and source-time co-availability; its geometry is not combined with LTSB in
v0.18.0.

## Exact private lineage

The first and only authorized real execution consumes the same closed batch01
lineage as the accepted v0.17.1 audit:

- the recursive root containing the same 86 MCAP byte streams;
- the exact `independent_outings_v017_batch01.private.json` manifest bytes;
  and
- the complete preserved v0.17.1 four-file intake directory.

Before decoding either road topic, the workflow must validate:

- exactly the four expected v0.17.1 files and no extra file;
- the exact reviewed v0.17.1 contract revision
  `v0.17.1-reviewed-2026-09-07-schema-v2-a1` and negative status;
- null roles/ranks/scores and unauthorized split assignment;
- the accepted manifest SHA-256;
- all four recomputed output hashes and sibling reconciliation;
- exact recursive manifest coverage of the supplied MCAP root;
- the same unique 86-entry basename/SHA-256 map; and
- the same content-only outing fingerprint.

Any mismatch is a usage/lineage error before the new output directory is
created. No raw MCAP, manifest, v0.17.0 output, or v0.17.1 output is changed or
copied. The accepted 67-file legacy lineage is out of scope; auditing it could
enable a new development target and requires a separate reviewed decision.

## Fixed topics and descriptor handling

The workflow reads exactly:

```text
estimate topic   /adp/lane_topology_sensor_based
reference topic  /adp/road_lane_map_based
MCAP schema name Adp.Perception.Road
message encoding protobuf
```

Topic absence, schema-name drift, non-Protobuf encoding, decoding failure, and
descriptor generations are retained explicitly. No other topic repairs a
failure.

For every decoded message, descriptor identity is derived only from:

```text
sha256(message.DESCRIPTOR.file.serialized_pb)
```

It is never derived from an MCAP schema-record hash, caller label, filename,
or audit-provided fingerprint. The root descriptor must have simple name
`Road`, and its package compared ASCII-case-insensitively must be
`adp.perception`. Structural support is decided by required field numbers,
labels, and scalar/message/enum kinds, not by current generated-code identity
or the unrelated field-18 type name.

At minimum, the sensor descriptor must expose the source-traced structure:

- `Road`: singular enum field 4; singular `sint64` field 5; repeated `sint64`
  field 6; repeated `RoadLaneSegment` field 7; repeated `RoadLaneBoundary`
  field 9; repeated `Adp.PolylineVertex` field 12; and repeated `float` field
  13;
- `RoadLaneSegment`: repeated `int64` successor field 6; singular `Range`
  drive-path field 11; and singular `BoundaryRanges` left/right fields 12/13;
- `BoundaryRanges`: singular `Range` map/camera/artificial fields 1/2/3;
- `Range`: singular `int64` start field 1 and size field 2;
- `RoadLaneBoundary`: singular `Range` geometry field 1 and singular enum
  source field 4;
- `Adp.PolylineVertex`: singular `Adp.Common.NormalDistributedValueF` x/y
  fields 1/2; and
- `Adp.Common.NormalDistributedValueF`: singular `float` mean field 1,
  singular `float` standard-deviation field 2, and singular `uint32`
  invalid-flags field 3.

Required-field type, number, label, referenced-type, or enum-value drift is
unsupported even when decoding succeeds. Extra unrelated fields are
inventoried but do not fail this structural audit. Multiple recorded descriptor
generations may be audited only when each independently satisfies the same
required structure; they remain separate inventory entries.

The decoded whole-message topology source must be the source-traced
`SENSOR_TOPOLOGY` numeric enum value 4. Any other, missing-as-default, Boolean,
or non-integral value fails closed; topic name alone is not provenance.

The recursive schema inventory records field numbers, names, labels,
scalar/message/enum types, referenced full names, oneof membership, and the
serialized file-descriptor SHA-256. It records no option value containing a
local path and no message payload value. Inventory does not create a general
allow-list or establish semantic compatibility for residual construction.

## Strict ego binding and camera-only segment geometry

For one sensor message, `ego_lane_segment_indices` is valid only when:

- the field is explicitly present as the source-traced repeated signed index;
- it contains exactly one value;
- the value is a non-Boolean integer; and
- it is in range for that message's `lane_segments` array.

Zero or multiple entries are not resolved. Index order, lane ID, lateral
neighbours, geometry proximity, and nearest-origin selection are forbidden
substitutes.

Every segment admitted to the sensor chain must meet all of these rules:

1. `drive_path_range` is unwritten only when its decoded values are exactly
   `(start = 9223372036854775807, size = 0)`. `size == 0` alone is insufficient:
   `(start = 0, size = 0)` can be a valid null range. Any other value is
   producer drift and is never consumed.
2. Left and right `map_based` and `artificial` boundary ranges have the exact
   unwritten sentinel `(start = 9223372036854775807, size = 0)`; `size == 0`
   alone is not accepted.
3. Left and right `camera_based` ranges are integral `(start, size)` pairs,
   nonnegative, nonempty, in bounds for `lane_boundary_pool`, and resolve to at
   least one boundary per side.
4. Every referenced boundary reports CAMERA provenance, has an integral,
   nonnegative, nonempty geometry `(start, size)` range that is in bounds for
   both `boundary_vertex_pool` and `boundary_arc_length_pool`, and resolves to
   at least two valid x/y mean points and the same number of arc-length values.
5. Each x/y wrapper has a non-Boolean integral `invalid_flags` value in
   `[0, 255]`, has bit `0x01` clear, and has a finite mean strictly less than
   `3.4028234663852886e38` (`FLT_MAX`). A clear invalid bit or zero flags alone
   is not sufficient.
6. The corresponding arc-length slice is finite, starts at exactly `0.0`, is
   nondecreasing in stored vertex order, and ends above `0.0`.

An invalid or non-camera range invalidates that segment. Empty map-informed
segments are counted as chain termination, not converted from `segment_length`
and not filled from another source.

## Diagnostic midpoint and successor-chain rules

For each strict segment, reconstruct left and right polylines separately:

- take boundaries and vertices in their source-traced message-local stored
  order; do not interpret that order as forward travel direction;
- orient each next boundary by the endpoint choice with the smaller Euclidean
  gap to the accumulated polyline;
- if the two endpoint gaps are exactly equal, fail as ambiguous;
- remove only a junction point whose endpoint gap is at most `1e-6 m`, matching
  the existing characterized MPR boundary concatenation tolerance;
- reject a non-finite point, fewer than two distinct points, zero total arc
  length, or an inter-boundary gap greater than `1.0 m`;
- orient the complete right side to minimize paired start/end separation from
  the left side, failing an exact tie; and
- parameterize each side by its own arc length normalized to `[0, 1]`, linearly
  interpolate both on `max(left_count, right_count)` equally spaced normalized
  positions, and take their Cartesian midpoint.

The median paired boundary separation must be finite and within `[1.0, 10.0]
m`, the existing fixed MPR plausibility boundary. Only pass/failure counts are
exported. The midpoint is not described as the producer centreline.

Starting at the unique ego segment, the camera chain:

- visits at most 16 segments, including the initial segment;
- follows only one explicit, non-Boolean, in-range successor index;
- stops normally when no successor exists;
- fails on multiple successors before reaching the 100 m span, an invalid
  successor, a repeated segment, or the 16-segment limit;
- requires every visited segment to pass the camera-only rules above;
- orients a successor midpoint by the endpoint connection with the smaller
  gap, failing an exact tie;
- requires the chosen junction gap to be at most `1.0 m`; and
- requires the absolute junction heading change to be at most `30 degrees`.

After removing only a junction duplicate within `1e-6 m`, observed chain span
is the sum of Euclidean distances along the concatenated diagnostic midpoint. A
message has `camera_chain_100m_span` when that span is at least `100.0 m`. This
is orientation-invariant observed length. It is not forward H100 coverage from
the ego origin, because the LTSB origin and axes remain unverified.

If 100 m is reached before a later branch or invalid segment, the message
passes the span state without inspecting unnecessary downstream topology. No
numeric span, gap, heading, or width is serialized.

## Reference readiness and source-time pairing

RLMB handling remains the accepted current implementation:

- exactly one metadata-confirmed ego segment with direct drive-path geometry;
- only a unique explicit successor chain;
- no guessed branch, missing successor, cycle, or unavailable segment;
- at most 16 segments;
- junction gap at most `1.0 m`;
- junction heading change at most `30 degrees`; and
- coverage of the canonical reference stations `0, 5, ..., 100 m` without
  extrapolation.

This produces a per-reference-message Boolean `reference_h100_ready` only.
No RLMB coordinate is compared with a sensor coordinate.

Sensor and reference messages are paired by embedded source timestamp using
the existing deterministic mutual-nearest algorithm with maximum absolute
delta `50 ms`. The algorithm is inherited; the `50 ms` gate is a new,
prospectively fixed v0.18.0 structural-audit constant. The v0.17 intake did not
apply an estimate/reference delta gate, and historical comparison commands
used a different `20 ms` default. The original a3 rationale described LTSB
time as camera lane-marking validity time and RLMB time as pose validity
time on the ADP clock. The dated 2026-09-18 addendum below withdraws the
unconditional LTSB epoch interpretation; the numerical pairing rule stays
unchanged. Neither physical synchronization nor equal measurement age follows.

Log/publish time cannot repair an invalid source timestamp. The singular
proto3 timestamp scalar has no presence bit, so "present" is not observable.
Its decoded value must instead be a positive non-Boolean integer on every
decoded message and values must be strictly increasing within topic and
recording. Zero is invalid because it is also the decoded default. A stream
that fails has zero paired candidates; no subset is selected or reordered.
Pairing is recording-local and never crosses an MCAP boundary.

A `synchronized_100m_candidate` is one mutual-nearest pair for which the
sensor message passes `camera_chain_100m_span` and the reference message passes
`reference_h100_ready`. Under the dated interpretation correction below, it
means only dual structural availability at nearby numeric header timestamps.
It does not evaluate physical synchronization, alignment, anchor distance,
station correspondence, or residual readiness.

## Counting and failure vocabulary

All sensor/reference counts are message-level. Each message contributes at
most one count to each named state. `camera_boundary_segment_structure_count`
counts messages whose unique initial ego segment passes the camera-only
segment rule. `camera_only_successor_chain_count` counts messages whose strict
chain either reaches 100 m or terminates normally with zero successors after
at least one valid segment. `camera_chain_100m_span_count` is its at-least-100
m subset. `source_time_pair_count` counts every unique mutual-nearest pair that
passes the inclusive `50 ms` gate, before geometry filtering. Each such pair
contributes at most one
`synchronized_100m_candidate`. Corpus totals are exact sums of the 86
per-recording rows.

A recordings-row failure code is the union of codes reached by any relevant
message, chain attempt, reference attempt, or pairing state in that recording;
it may coexist with a positive count from another message. The detailed codes
therefore diagnose attrition and are not mutually exclusive success statuses.

The per-recording `failure_codes` field is a sorted unique subset of:

```text
sensor_topic_missing
reference_topic_missing
sensor_schema_or_encoding_mismatch
reference_schema_or_encoding_mismatch
sensor_descriptor_unavailable
reference_descriptor_unavailable
sensor_required_structure_drift
sensor_topology_source_invalid
sensor_stream_decode_failed
reference_stream_decode_failed
sensor_source_timestamp_invalid
reference_source_timestamp_invalid
sensor_source_timestamps_not_strict
reference_source_timestamps_not_strict
sensor_ego_metadata_missing
sensor_ego_metadata_invalid
sensor_ego_segment_not_unique
sensor_unexpected_direct_path
sensor_non_camera_boundary_present
sensor_camera_boundary_range_invalid
sensor_camera_boundary_provenance_invalid
sensor_camera_boundary_geometry_invalid
sensor_camera_boundary_width_implausible
sensor_camera_chain_ambiguous
sensor_camera_chain_cycle
sensor_camera_chain_limit_exceeded
sensor_camera_chain_junction_invalid
sensor_camera_chain_100m_span_unavailable
reference_ego_drive_path_not_unique
reference_successor_chain_invalid
reference_h100_coverage_incomplete
source_time_pair_unavailable
```

An internal detail must map to these exported codes. New exported codes require
a reviewed contract amendment. Invalid mean wrappers or arc-length slices map
to `sensor_camera_boundary_geometry_invalid`; a non-sensor whole-message enum
maps to `sensor_topology_source_invalid`. Codes are
non-mutually-exclusive.

The v0.18.1 corrective amendment adds exactly one exported code,
`reference_required_structure_drift`, so a readable-but-drifted RLMB descriptor
is not mislabeled as `reference_stream_decode_failed`. That addition is not
active for a private rerun until the corrective amendment receives focused
review `GO`.

## Fixed command and exact outputs

The implemented public surface is:

```bash
python -m lane_residuals.cli.sensor_topology_feasibility \
  NEW_MCAP_ROOT \
  --acquisition-manifest PRIVATE_ACQUISITION_MANIFEST.json \
  --preserved-intake-directory PRESERVED_V0171_OUTPUT_DIRECTORY \
  --output-directory NEW_EMPTY_OUTPUT_DIRECTORY \
  [--log-level INFO]
```

Topic names and thresholds are constants. `--log-level` accepts only `DEBUG`,
`INFO`, `WARNING`, or `ERROR` and affects console verbosity only.

After valid lineage input, the command writes exactly three private files:

```text
sensor_topology_recordings.csv
sensor_topology_schema_inventory.json
sensor_topology_feasibility_summary.json
```

### Recordings CSV

One deterministic basename-ordered row per MCAP has exactly:

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
sensor_source_timestamp_valid_count
reference_source_timestamp_valid_count
sensor_source_timestamps_strict
reference_source_timestamps_strict
explicit_ego_candidate_count
camera_boundary_segment_structure_count
camera_only_successor_chain_count
camera_chain_100m_span_count
reference_h100_ready_count
source_time_pair_count
synchronized_100m_candidate_count
failure_codes
```

Sets are semicolon-delimited, sorted, and deduplicated. Booleans are lowercase
`true`/`false`; counts and byte sizes are nonnegative decimal integers. No
timestamp or geometry-derived numeric value appears.
`*_source_timestamp_valid_count` counts decoded positive non-Boolean source
timestamp values; it does not claim proto3 field presence.

### Schema inventory

`sensor_topology_schema_inventory.json` contains exactly:

```text
version
contract_revision
purpose
descriptor_identity_rule
topics
```

Fixed values are `version = "0.18.0"`, the a3 revision,
`purpose = "sensor_topology_schema_inventory"`, and
`descriptor_identity_rule =
"sha256(message.DESCRIPTOR.file.serialized_pb)"`.

`topics` is sorted by topic and descriptor SHA-256. Each item contains exactly:

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

The arrays are sorted and unique. `field_inventory` is a recursively
full-name-sorted array whose entries contain exactly `full_name`, `number`,
`label`, `kind`, `referenced_full_name`, and `oneof_name`. Recursion stops on
an already visited message full name and records the reference without
expanding again. `descriptor_file_sha256` is null when unavailable; null sorts
after hashes. `audit_support_status` is one of `structure_conformant`,
`required_structure_drift`, `decode_failed`, or `descriptor_unavailable`.
It is not residual-target compatibility.

### Feasibility summary

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
minimum_sensor_chain_span_m
maximum_source_delta_ms
sensor_chain_limits
reference_chain_limits
sensor_descriptor_file_sha256s
reference_descriptor_file_sha256s
sensor_message_count
reference_message_count
sensor_decoded_count
reference_decoded_count
explicit_ego_candidate_count
camera_boundary_segment_structure_count
camera_only_successor_chain_count
camera_chain_100m_span_count
reference_h100_ready_count
source_time_pair_count
synchronized_100m_candidate_count
recording_failure_counts
output_sha256
technical_feasibility_status
producer_provenance_status
scientific_target_adoption_authorized
claim_limits
next_authorized_action
```

Fixed values and objects are:

```text
version                                  "0.18.0"
contract_revision                        "v0.18.0-review-candidate-2026-09-15-sensor-topology-feasibility-a3"
purpose                                  "sensor_topology_100m_structural_feasibility"
lineage_status                           "passed"
topics.estimate                          "/adp/lane_topology_sensor_based"
topics.reference                         "/adp/road_lane_map_based"
minimum_sensor_chain_span_m              100.0
maximum_source_delta_ms                  50.0
sensor_chain_limits.max_segments         16
sensor_chain_limits.maximum_junction_gap_m       1.0
sensor_chain_limits.maximum_junction_heading_deg 30.0
sensor_chain_limits.minimum_median_width_m        1.0
sensor_chain_limits.maximum_median_width_m        10.0
reference_chain_limits.max_segments                     16
reference_chain_limits.maximum_junction_gap_m           1.0
reference_chain_limits.maximum_junction_heading_deg     30.0
producer_provenance_status               "source_traced_frame_contract_unresolved"
scientific_target_adoption_authorized    false
```

`preserved_intake_lock_sha256` is the recomputed hash of the exact v0.17.1
lock. `raw_basename_sha256_map_sha256` hashes the v0.17.1 map sorted by basename
and encoded one entry at a time as:

```text
basename_utf8 || NUL || lowercase_file_sha256_ascii || LF
```

Every basename/hash is first reconciled with the manifest and raw bytes.
`output_sha256` has exactly the recordings CSV and schema-inventory JSON keys
in that order. The summary cannot hash itself. `recording_failure_counts`
contains only observed codes in lexical order with positive integer counts.

`claim_limits` is exactly:

```text
structural_feasibility_only
rlmb_is_pseudo_reference_not_ground_truth
ltsb_boundary_geometry_is_camera_derived_but_topology_is_map_influenced
ltsb_centreline_is_consumer_derived_not_producer_defined
physical_frame_equivalence_not_established
no_cross_topic_geometry_alignment_or_h100_residual_pair
no_residual_condition_sequence_model_planner_or_figure
no_cohort_role_or_independent_outing_generalization
```

When `synchronized_100m_candidate_count > 0`,
`technical_feasibility_status = "synchronized_100m_candidates_observed"` and
`next_authorized_action =
"resolve_physical_frame_contract_and_predeclare_alignment_audit"`. Otherwise
the status is `"no_synchronized_100m_candidates"` and the next action is
`"retain_negative_audit_and_review_schema_or_acquisition_configuration"`.
Neither status adopts the target.

Strict JSON forbids duplicate keys, NaN, and infinity and uses deterministic
formatting. Lineage/schema/usage errors exit `2` before output. A complete
zero-candidate audit exits `3`; a complete positive audit exits `0`. Both
complete states write all three files. Existing or nonempty output directories
are never overwritten.

## Privacy, determinism, and ownership

All outputs, raw MCAPs, and private manifests remain outside Git. Outputs may
contain private basenames, relative paths, file hashes, descriptor identities,
and aggregate counts. They contain no absolute path, run timestamp, raw numeric
payload, coordinate, timestamp value, span, width, gap, heading, projection,
residual, condition, sequence, model, planner, or figure value.

For identical code, contract, manifest bytes, raw bytes, preserved v0.17.1
files, and relative layout, all three byte streams are identical. A different
mount root changes nothing. A different relative layout may change only the
private relative-path column, the recordings CSV hash, and its summary hash.

The implementation follows repository ownership:

- `domain.sensor_topology_feasibility`: descriptor-independent structural
  states, strict camera midpoint/chain arithmetic, and fixed thresholds;
- `io.sensor_topology_feasibility`: descriptor inspection, dynamic field-number
  access, decoding adapters, and strict serialization;
- `workflows.sensor_topology_feasibility`: v0.17.1 lineage validation,
  recording-local orchestration, aggregation, non-overwrite, and hashes; and
- `cli.sensor_topology_feasibility`: arguments, logging, and exit mapping.

The workflow may reuse neutral primitives only after tests freeze their exact
behavior. It must not import `legacy.preprocessing`, a residual builder,
condition module, sequence builder, model, sampler, planner, evaluation, or
visualization module. Historical code is evidence, not the new owner.

## Synthetic implementation acceptance

The synthetic implementation tests must prove at least:

- exact preserved-v0.17.1 file/schema/hash/raw-map reconciliation before
  output creation;
- manifest coverage and rejection of missing, extra, duplicate, changed, or
  path-qualified entries;
- message-owned descriptor hashing and deterministic recursive inventory;
- exact topic/schema/encoding filtering and required field-number/type/label
  validation across conformant descriptor generations;
- strict single ego index and rejection of Boolean, missing, multiple,
  out-of-range, vector-order, or nearest-origin selection;
- rejection of a populated direct path, non-camera ranges, non-CAMERA boundary
  provenance, invalid `(start, size)` pairs, bad two-level pool indirection,
  non-finite/degenerate vertices, ambiguous orientation, gaps, the `1e-6 m`
  duplicate-junction boundary, and exact width boundaries;
- unique successor traversal, zero-successor stop, branch/cycle/limit rules,
  empty map-informed segment termination, exact gap/heading boundaries, and
  orientation-invariant 100 m span;
- unchanged RLMB H100 readiness without exposing or combining coordinates;
- source-time-only mutual-nearest pairing, deterministic ties, missing or
  non-strict times, exact `50 ms`, and recording-local isolation;
- no call to a cross-topic projection, anchor, transform, odometry
  compensation, residual, or station-sampling primitive;
- exact three-file schemas, hashes, deterministic bytes, non-overwrite, exit
  codes `0`/`3`/`2`, and absence of prohibited values; and
- no direct/transitive import of residual, conditions, sequences, modeling,
  sampling, planner, evaluation, or visualization.

The complete Python 3.10 and 3.12 suite must pass. The focused v0.18.0
implementation-review requirement was satisfied before its one private run;
the corrective amendment requires a fresh focused review before any rerun.

## Binding review and execution order

1. Commit and push the original prospective documentation on the dedicated
   branch.
2. Preserve the first private Copilot transcript and amend the repository
   evidence and contract from a0 to a1.
3. Preserve the interface follow-up and incorporate its technical corrections
   as intermediate a2 without reading private MCAPs.
4. Preserve the path/HEAD-blob audit, record its complete paths, corrections,
   and unidentified-commit limitation, and freeze this a3 review candidate.
   No further BMW-source response is required for this audit.
5. Push this exact documentation commit and obtain Claude's focused contract
   review. `AMEND` returns to the contract; only `GO` continues.
6. Implement the audit without reading private MCAPs and verify entirely on
   synthetic fixtures.
7. Push the exact implementation and obtain focused implementation `GO`.
8. Run once on the closed batch01 into a new empty versioned directory.
9. Independently reconcile the three files and review the real result.
10. If no synchronized candidate exists, stop and retain the negative result.
   If candidates exist, first resolve the physical frame contract, then write
   and review a separate alignment-audit contract. Residual construction is a
   later decision still requiring target adoption.

No v0.18.0 `GO` alone authorizes merging. Merge requires the applicable
contract, implementation, and real-output reviews, passing CI, and the user's
explicit decision.

## Claim boundary

v0.18.0 may state only whether the closed batch contains source-time-paired
messages with strict camera-only LTSB midpoint span of at least 100 m and an
independently H100-ready RLMB pseudo-reference. A positive result does not
prove frame equivalence, alignment, residual readiness, map independence,
physical truth, v0.17 outing eligibility, comparability with EDP, or expected
model performance. A zero result does not invalidate the topic outside this
recording, producer build, or configuration.

## Retrospective numerical clarification, 2026-09-17 (H2)

This dated addendum records comparisons already present in the reviewed
v0.18.0 implementation and unchanged by v0.18.1. It was added after the real
output review, not prospectively declared with a3. It changes no code,
scientific threshold, contract-revision identifier or preserved output.

For the sensor successor-chain audit in
`src/lane_residuals/domain/sensor_topology_feasibility.py`:

| Check | Existing floating-point comparison | Slack units |
|---|---|---|
| Accumulated observed span | `span + 1e-9 >= 100.0` | metres |
| Successor junction gap | reject if `gap > 1.0 + 1e-12` | metres |
| Successor heading change | reject if `heading_delta > math.radians(30.0) + 1e-12` | radians |

These are fixed implementation slacks for inclusive comparisons, not
data-tuned tolerances or measurement uncertainty. The heading slack is in
radians, not degrees. They do not change the separately specified boundary
reconstruction or junction-duplicate rules. Numeric sensor spans are absent
from the artifacts, so neither their proximity to these boundaries nor the
effect of removing the slack can be inferred from the zero count. No rerun
or sensitivity calculation is authorized by documenting these comparisons.

## Retrospective epoch clarification, 2026-09-18

This is an interpretation correction proposed after the completed audit;
focused independent review is pending. It is not a new prospective rule.
`docs/bmw_sensor_topology_epoch_evidence.md` records the supplied transcript,
its SHA-256, reported BMW HEAD and evidence limits. The new source report
describes configuration-dependent LMSB processing: a tracking/odometry-epoch
branch, a camera-header pipethrough branch and possible timestamp rewriting.
It does not establish which branch/settings generated batch01.

Withdraw the original unconditional camera-measurement-time assumption.
Keep the same positive/strict scalar checks, recording-local mutual-nearest
algorithm, 50 ms comparison and all geometric rules. The 17,087 accepted
time pairs mean numeric header proximity only; no common physical epoch,
equal age or valid compensation follows. The independent zero sensor-span
gate still forces zero synchronized structural candidates.

No output, machine field, contract-revision identifier, threshold or code is
changed, and no rerun is authorized. Existing GOs and frozen outputs remain
historical evidence; they do not pre-approve this later clarification.
