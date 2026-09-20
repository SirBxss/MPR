# BMW standalone sensor-topology source evidence

Last updated: 2026-09-19. The three original BMW traces below remain the
2026-09-15 evidence. A fourth received trace materially qualifies upstream
processing and timestamp semantics; see
`docs/bmw_sensor_topology_epoch_evidence.md` for its hash, named BMW HEAD,
evidence limits and completed focused interpretation review (`GO`, PR #21).

This document tracks the evidence needed to evaluate
`/adp/lane_topology_sensor_based` as a possible estimate-side source for a new
MPR residual target. It separates user-reported guidance, accepted MPR
evidence, BMW-source evidence, and inference. It is not permission to decode a
private target, calculate a residual, or reuse an old model.

The completed structural audit followed
`docs/sensor_topology_feasibility_predeclaration.md`. Its corrected negative
result is accepted and merged through PR #20. The next inquiry is scoped in
`docs/sensor_topology_source_acquisition_decision.md`; it addresses previously
unresolved extent, frame/epoch and provenance, without reopening the closed
decoder questions or permitting a new private run. That inquiry has now
returned; the next gaps are recording-specific build/configuration and an
applicable physical-frame/epoch specification.

## Evidence provenance

The data owner requested three read-only investigations through Copilot in the
BMW checkout. The returned transcripts are private and remain outside Git.
Their SHA-256 values, in evidence order, are:

```text
initial trace         57319e59c54ac270d1885c4039d1bac952798f9f7eb293466aec6e6e53b4e3f7
interface follow-up   315304f3567b5394f9fb15347c3ce63e3fde55dd4ac1960b4fd77744569468d2
path/HEAD-blob audit  f5fa27166e824f9276f267ce1b0d449189a5fb5e3e9c3fe3c9a5d3bebc285fb7
```

The third trace resolved all 23 cited files to complete tracked
repository-relative paths and verified their existence at `HEAD`. It then
rechecked every positive technical claim using immutable `HEAD:<path>` blobs
through `git show`, `git cat-file`, or `git grep ... HEAD --`; working-tree
contents therefore could not affect those reads. The checkout-identity command
was skipped, so the literal BMW commit SHA, top-level path, and clean-status
result were not captured.

The unidentified commit prevents a third party from reproducing the private
source search at one named BMW revision. It does not make the MPR audit depend
on guessed generated code: the proposed decoder inventories and validates the
descriptors stored in each MCAP and fails closed on structural drift. The
source evidence is therefore sufficient to freeze a focused MPR contract
review candidate, with the missing BMW commit recorded as a reproducibility
limitation rather than an implementation blocker. Facts below remain
classified as **Copilot-confirmed BMW-source evidence**, not as facts
independently verified by MPR. No further BMW-source answer is required for the
structural/co-availability audit. Explicitly unresolved physical-frame
semantics remain visible and continue to prohibit cross-topic geometry and
residual calculations.

### Canonical tracked source paths

The third trace verified these complete paths at its unidentified `HEAD`:

1. `interfaces/topics/topic_definitions.bzl`
2. `activities/road_sensor_based/lane_topology_sensor_based/lane_topology_sensor_based_activity.cpp`
3. `activities/road_sensor_based/lane_topology_sensor_based/lane_topology_sensor_based_activity.json`
4. `domains/perception/road_sensor_based/lane_topology_sensor_based/lane_topology_sensor_based.cpp`
5. `domains/perception/road_sensor_based/lane_topology_sensor_based/topology_updater/topology_updater.cpp`
6. `domains/perception/road_sensor_based/lane_topology_sensor_based/topology_updater/utils/topology_updater_utils.cpp`
7. `domains/perception/road_sensor_based/lane_topology_sensor_based/topology_updater/lane_marking_assigner.cpp`
8. `domains/perception/road_sensor_based/lane_topology_sensor_based/parameters/lane_topology_sensor_based_parameters.json`
9. `interfaces/perception/road/road.proto`
10. `interfaces/perception/road/road_lane_segment.proto`
11. `interfaces/perception/road/range.proto`
12. `interfaces/perception/road/range.h`
13. `interfaces/perception/road/road_lane_boundary.proto`
14. `interfaces/perception/road/boundary_properties.proto`
15. `interfaces/perception/shared/polyline_vertex.proto`
16. `interfaces/perception/shared/normal_distributed_value_float.proto`
17. `interfaces/perception/shared/normal_value.h`
18. `interfaces/perception/front_camera_lane_boundaries_and_road_edges/lane_boundary_common.proto`
19. `domains/perception/road_sensor_based/lane_topology_sensor_based/data_types/sw_design_data_types.md`
20. `interfaces/parameters/vehicle_geometry_parameters.json`
21. `generic_platform/verification/nautilus/configuration/configs/config.bzl`
22. `activities/road/lane_topology_map_based/README.md`
23. `interfaces/perception/lane_markings_sensor_based/lane_markings_sensor_based_output.proto`

## User-reported guidance and observations

- On 2026-09-14, the data owner reported that Leon recommended switching the
  estimate input from `/adp/estimated_drive_paths` to
  `/adp/lane_topology_sensor_based` and described the standalone topic as the
  preferable source for this study.
- Earlier Lichtblick inspection by the data owner showed
  `/adp/lane_topology_sensor_based` in the new 86-file recording and displayed
  `Adp.Perception.Road` as its message type.
- These observations motivate the audit. They do not establish the deployed
  producer build, recorded descriptor identity, frame origin, ego-lane
  geometry, or map independence.

## Accepted MPR evidence that remains unchanged

The accepted v0.17.1 batch01 audit concerns EDP, not the standalone sensor
topic. It established:

| Quantity | Accepted result |
|---|---:|
| closed MCAP chunks | 86 |
| physical outings represented | 1 |
| decoded EDP messages | 17,163 |
| EDP H100 geometry-ready candidates | 5,289 |
| EDP H100 SENSOR_TOPOLOGY candidates | 0 |
| EDP H100 LANE_MAP candidates | 5,289 |
| eligible v0.17 frames/outings | 0 / 0 |

The earlier complete EDP message audit observed 787 SENSOR_TOPOLOGY EDP
messages, but none became an H100-ready EDP candidate. This does not determine
how many standalone sensor-topology messages or structural candidates exist.
At the time of these source traces, no standalone-topic descriptor hash,
message count, ego-lane count, boundary-reconstruction count or 100 m span
count had been accepted. The later v0.18.1 result establishes 4,039 strict
camera-only chains and zero reaching 100 m, with 9,235 reference-ready
messages and 17,087 source-time pairs. Its exact evidence and limitations
are in `docs/sensor_topology_batch01_v0181_result.md`; none of those counts
establishes a physical sensor-range limit.

## MPR implementation evidence

MPR already contains historical support for Road-like topology messages:

- `src/lane_residuals/io/mcap.py::road_frame_from_message` can reconstruct a
  segment from a direct `drive_path_range` or paired lane boundaries.
- Its historical boundary helper tries `camera_based`, then `map_based`, then
  `artificial`. That permissive fallback is forbidden for the candidate
  sensor-topic audit.
- Its historical ego selector accepts several aliases and can permit a
  nearest-origin fallback. Neither behavior establishes the reviewed binding
  for this topic.
- Current RLMB handling requires a metadata-confirmed direct ego path and
  follows only an unambiguous, continuity-checked successor chain to H100.

These are historical reusable implementation ideas, not producer evidence.
The now-merged canonical structural audit is implemented separately in the
`domain`, `io`, `workflows` and `cli` `sensor_topology_feasibility` modules.

## Copilot-confirmed BMW-source evidence

### Producer and interface

Copilot identified the topic key `lane_topology_sensor_based` at
`topic_definitions.bzl:551`, the producer activity
`LaneTopologySensorBasedActivity`, and the core entry point
`LaneTopologySensorBased::RunOnce(Road&, LaneSegmentsToMapLinkIdsMapping&)` in
`lane_topology_sensor_based.cpp:619`. It reported
`lane_topology_sensor_based_activity.json` as the wiring configuration and
`lane_topology_sensor_based_parameters.json` as the parameter file. The
activity publishes the sensor topology and the lane-segment-to-map-link
mapping topics.

The root message is `adp::perception::Road`, the same current interface type
reported for RLMB. Copilot reported current `road.proto` version `1.2.0` and
the following relevant `Road` fields:

| Field | Number |
|---|---:|
| `topology_source_` | 4 |
| `time_stamp_` | 5 |
| `ego_lane_segment_indices_` | 6 |
| `lane_segments_` | 7 |
| `lane_boundary_pool_` | 9 |
| `polyline_vertex_pool_` | 10 |
| `polyline_arc_length_pool_` | 11 |
| `boundary_vertex_pool_` | 12 |
| `boundary_arc_length_pool_` | 13 |

The follow-up pinned `time_stamp_` as a singular proto3 `sint64` in
nanoseconds with `use_adp_time_point = true`; it has no presence bit and an
unset value decodes as zero. It pinned `ego_lane_segment_indices_` as repeated
`sint64`, `lane_segments_` as repeated `Adp.Perception.RoadLaneSegment`,
`lane_boundary_pool_` as repeated `Adp.Perception.RoadLaneBoundary`,
`boundary_vertex_pool_` as repeated `Adp.PolylineVertex`, and
`boundary_arc_length_pool_` as repeated `float`.

For `RoadLaneSegment` version `1.0.0`, the relevant fields are
`successor_lane_segment_indices_ = 6`, `predecessor_lane_segment_indices_ = 7`,
`segment_length_ = 8`, `drive_path_range_ = 11`,
`left_lane_boundary_ranges_ = 12`, and
`right_lane_boundary_ranges_ = 13`. `Range` is a `(start, size)` pair, not a
`(start, end)` pair. `BoundaryRanges` has `map_based = 1`, `camera_based = 2`,
and `artificial = 3`. `RoadLaneBoundary.geometry_ = 1` indexes the boundary
vertex and arc-length pools and `RoadLaneBoundary.source_ = 4` records
boundary provenance. The reported boundary-source enum is `INVALID = 0`,
`CAMERA = 1`, `MAP = 2`, and `ARTIFICIAL = 3`.

`Adp.PolylineVertex.x` and `.y` are singular
`Adp.Common.NormalDistributedValueF` messages at field numbers 1 and 2. That
wrapper contains singular `float mean = 1`, singular `float std_dev = 2`, and
singular `uint32 invalid_flags = 3`. The traced safe mean predicate is
`(invalid_flags & 0x01) == 0 && mean < FLT_MAX`; `0x01` marks an invalid mean
and `0xFF` means signal unfilled. A zero flag alone is insufficient proof that
the producer populated a default-constructed wrapper. The structural audit
must therefore combine the predicate with finite, nondegenerate geometry
checks and must not export wrapper values.

Successor, predecessor, and lateral-neighbour values are message-local indices
into `Road.lane_segments_`; segment boundary ranges index
`Road.lane_boundary_pool_`; and each boundary's geometry range then indexes
the boundary vertex pool. An unset `Range` uses an int64-max start sentinel and
size zero. The official range predicate also permits `(start = 0, size = 0)`
as a valid null object against an empty pool, so `size == 0` alone cannot
establish that a range is unwritten. `range.proto` and
`road_lane_segment.proto` were reported stable since 2025-06-13, before both
relevant recording generations. The exact serialized invalid lane-segment
index and ordering of multiple predecessor/successor indices were not
established.

### Ego-lane binding

`Road.ego_lane_segment_indices_` is the explicit binding. Copilot traced
`TopologyUpdaterImpl::AddIndicesToEgoLaneSegmentIndices` in
`topology_updater.cpp:353-361`: it appends valid
`ego_left`, `ego_straight`, and `ego_right` indices in that order while
skipping invalid slots.

This vector is therefore a set of lateral/branch alternatives at a split, not
a longitudinal path. Because invalid entries are omitted, an output consumer
cannot reliably recover which named slot produced a remaining position. A
message with exactly one in-range entry has one unambiguous ego candidate. A
message with zero entries has no binding; a message with more than one remains
branch-ambiguous and must not be resolved by vector order or geometry
proximity.

### Geometry representation and provenance

Copilot found no `drive_path_range` writer in the complete LTSB source tree.
The only writer in the broader `road_sensor_based` domain belongs to a
different drive-path-odometry component. For LTSB, the traced writers populate
only the `camera_based` left/right boundary sub-ranges. No LTSB writer for the
`map_based` or `artificial` sub-ranges was found.

Therefore the topic publishes no producer-defined ego-lane centreline. A
consumer can at most derive a diagnostic midpoint from paired camera
boundaries. A non-default direct path or a populated non-camera boundary range
in recorded data would be producer/schema drift relative to this trace; it is
not a fallback geometry arm.

The boundary vertex coordinates are measured in metres, heading in radians,
and curvature in inverse metres. The current proto and traced producer do not
state the coordinate-frame origin, x/y axis directions, or vehicle reference
point. A nearby software-design phrase says "vehicle coordinates", while
vehicle-parameter files distinguish CATIA and vehicle coordinate systems with
a non-zero translation. Copilot correctly treated rear-axle centring as
unproven.

The traces located two calls to `TopologyUpdaterUtils::AddLaneBoundary` in
`lane_marking_assigner.cpp` (lines 559 and 650 at the audited `HEAD`).
`AddLaneBoundary` remains the sole function that appends entries to the LTSB
boundary pool, and every emitted boundary is assigned
`LaneBoundarySource::kCamera`. They also located LTSB writes
of `Road.topology_source_ = RoadTopologySource::kSensorTopology` (numeric value
4). These findings justify fail-closed CAMERA boundary provenance and
whole-message SENSOR_TOPOLOGY checks in the prospective structural audit.

Camera boundary ranges are contiguous and append-ordered. On the boundary path
`AppendLaneBoundaryWithGeometry` to `FillBoundaryGeometry`, vertices are copied
verbatim from the camera input without sorting, reversal, or frame conversion;
corresponding arc lengths are generated in the same order,
starting at zero and nondecreasing across consecutive vertices. Direction
relative to vehicle travel remains unproven. The audit may validate stored
order and arc-length consistency and may use orientation-invariant geometric
span, but it may not infer forward direction or frame equivalence. The fourth
trace clarifies that this copy is from LMSB output, which can already be
tracked and odometry-propagated. It is not evidence of an untouched raw
camera pipeline.

One frame-transform token exists elsewhere in the LTSB tree, in
`domains/perception/road_sensor_based/lane_topology_sensor_based/preprocessors/split_preprocessors/bifurcation_detection/bifurcation_state_classifier.cpp`,
for an odometry-pose delta used by internal bifurcation-state tracking. It is
not on the boundary-geometry path and does not establish or modify the
published boundary frame.

### Topology is map-influenced

The activity directly subscribes to camera lane markings and semantic lane
types, odometry, road-scenario detection, HD-map link data, most-probable-path
links, and position-on-map lane/road outputs. Copilot traced use of
`map::MapLinkAccessor`, functions with `FromMap` in their names, and
map-split/detection parameters. It did not find a direct
`RoadLaneMapBasedTopic` subscription.

LTSB can create empty split/successor segments carrying length but no boundary
geometry, and it has distance-based holding/caching parameters. The only
robust per-segment evidence that usable geometry is camera-derived is the
camera boundary range together with each referenced boundary's source enum.
There is no traced scalar that proves an otherwise empty or held segment is
purely sensor-derived. The follow-up did locate the concrete whole-message
assignment `topology_source_ = kSensorTopology`; this identifies the producer
output but does not remove the map influence in its topology construction.

The defensible description is therefore: **camera-derived boundary geometry
inside a map-influenced topology graph**. The topic name must not be used to
claim complete independence from the map pseudo-reference.

### Time and extent

Copilot traced the output timestamp assignment to
`lane_topology_sensor_based.cpp:1097`:

```text
Road.time_stamp_ := LaneMarkingsSensorBasedOutput.timestamp
```

The original trace interpreted this value unconditionally as camera
lane-marking measurement/validity time. That interpretation is superseded
by the 2026-09-18 evidence correction: Copilot reports a tracking branch with
odometry-epoch output and a pipethrough branch with camera-header time, plus
configuration-dependent camera-timestamp rewriting. The applicable mode
and settings for batch01 remain unknown. No fixed timestamp adjustment is
justified. Because the proto3 scalar has no
presence bit, the audit can test only that the decoded timestamp is a positive
non-Boolean integer, not that it was explicitly serialized. No nominal LTSB
publication rate or guaranteed forward range was found. Full forward geometry
may require following successor indices, while empty map-informed successor
segments can terminate camera geometry.

RLMB uses a pose-estimate validity timestamp and documents its ego reference
as the rear-axle centre. The existing audit measures proximity of numeric
embedded header timestamps. Their common physical epoch and measurement-age
interpretation is not established for this recording. Physical frame-origin
equivalence is not established. Consequently no cross-topic point projection,
anchor distance, SE(2) compensation, or signed residual is authorized by this
source trace.

### Recording-generation history

Copilot reported a `road.proto` change on 2025-08-21 that renamed the field-18
message type from `SampledEstimatedDrivePaths` to
`SampledEstimatedDrivePath` without changing the field number or wire layout.
It also reported that message identifier `16452` and the drive-policy source
option were added on 2025-11-04, after the candidate recording date.
`road_lane_segment.proto` and `range.proto` were reported unchanged since
2025-06-13.

This supports structure-aware dynamic descriptor handling and prohibits
current-generated-code identity from being assumed for historical MCAPs. It
does not establish which exact producer commit created either recording
generation or whether producer behavior changed.

## Evidence questions and disposition

| Question | Disposition after source trace | Contract consequence |
|---|---|---|
| producer and configuration | technical symbols and all 23 complete paths verified from internally consistent HEAD blobs; commit SHA not captured | accept for MPR contract review while recording the named-revision reproducibility limit |
| root proto and field topology | nested decoder structure answered for the unidentified checkout | validate recorded descriptors by message-owned structure |
| coordinate frame/origin/axes | unresolved except units | prohibit cross-topic geometry alignment and residual math |
| ego binding | answered | require exactly one in-range ego index; reject zero or multiple |
| centreline representation | answered negatively | direct path is drift; camera midpoint is diagnostic only |
| ranges and graph indices | substantially answered | use `(start, size)` and message-local indices; never guess branches |
| fallback geometry | camera boundary writers only; every emitted boundary is assigned CAMERA; empty/map-informed topology exists | require sensor whole-message source, camera ranges, and CAMERA boundaries; reject drift |
| map/RLMB dependence | direct map/map-matching inputs; no direct RLMB topic | state map-influenced topology; do not claim independence |
| timestamp and rate | scalar/units and LTSB copy assignment answered; upstream epoch is configuration-dependent in the fourth trace; deployed mode and rate unresolved | positive strict numeric header timestamps only; no common-age or cadence claim |
| forward guarantee | unresolved; successor traversal may be required | audit explicit unique camera-only chains and observed span only |
| RLMB frame/epoch equivalence | physical origin and recording-applicable epoch relationship unresolved | no physical synchronization, anchor test or H100 residual-pair claim |
| generation differences | interface history partial; producer history unresolved | inventory exact recorded descriptors; no cross-generation assumption |

## Current conclusion

The trace is useful and changes the original a0 proposal materially. It
supports a narrower audit of descriptor identity, strict camera-boundary
reconstruction, unique successor connectivity, observed 100 m geometric span,
RLMB readiness, and source-time synchronization. It does **not** support the
original cross-topic anchor-distance test or the phrase "H100 structural
pair", because those require frame-origin equivalence.

A positive synchronized 100 m count would mean only that both inputs appear
structurally available in messages with numerically nearby header timestamps.
It would not establish physical synchronization. Before any residual is
calculated, BMW evidence or a separately reviewed empirical frame-calibration
contract must establish the coordinate transform, timestamp handling, and the
scientific acceptability of map-influenced topology selection.

## Evidence sufficiency and remaining limitation

Together, the three traces are sufficient to reject a0, define the nested
dynamic decoder and fail-closed producer checks, and freeze the a3 MPR contract
for focused independent review. The third trace supplied all complete paths
and rechecked the technical findings against one internally consistent set of
`HEAD` blobs. Its failure to name that HEAD is retained as an evidence
reproducibility limitation; it is not a reason to request further BMW work or
to block an MPR implementation after contract `GO`.

The technical questions about nested declarations, mean validity, CAMERA
source assignment, whole-message sensor-topology assignment, stored ordering,
unset-range semantics, timestamp type, and the boundary-path transform
negative are closed for this structural audit. Vertex direction, physical
frame/origin, publication cadence, and guaranteed forward extent remain
unresolved by design. Those semantic limits do not block the
structural/co-availability audit because it claims none of them, but they do
block any cross-topic alignment, H100 residual, target adoption, or reuse of
the historical EDP models.
