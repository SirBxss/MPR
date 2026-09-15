# BMW standalone sensor-topology source evidence

Last updated: 2026-09-15.

This document tracks the evidence needed to evaluate
`/adp/lane_topology_sensor_based` as a possible estimate-side source for a new
MPR residual target. It separates user-reported guidance, accepted MPR
evidence, BMW-source evidence, and inference. It is not permission to decode a
private target, calculate a residual, or reuse an old model.

The binding prospective scope is
`docs/sensor_topology_feasibility_predeclaration.md`.

## Evidence provenance

The data owner requested two read-only investigations through Copilot in the
BMW checkout. The returned transcripts are private and remain outside Git.
Their SHA-256 values, in evidence order, are:

```text
initial trace         57319e59c54ac270d1885c4039d1bac952798f9f7eb293466aec6e6e53b4e3f7
interface follow-up   315304f3567b5394f9fb15347c3ce63e3fde55dd4ac1960b4fd77744569468d2
```

Both traces reported source searches and excerpts, but neither recorded the
BMW checkout commit SHA. The follow-up also claimed to provide complete
repository-relative paths while listing only basenames such as `road.proto`
and `topology_updater_utils.cpp`. MPR cannot open that checkout and therefore
cannot independently reproduce or uniquely locate the searches. Facts below
are classified as
**Copilot-confirmed BMW-source evidence**, not as facts independently verified
by MPR. Missing checkout identity/path provenance and explicitly unresolved
physical-frame semantics remain visible rather than being inferred.

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
No standalone-topic descriptor hash, message count, ego-lane count,
boundary-reconstruction count, or 100 m span count has been accepted.

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

These are reusable implementation ideas, not producer evidence and not a
canonical v0.18 implementation.

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

The follow-up traced the sole LTSB boundary-pool constructor to
`TopologyUpdaterUtils::AddLaneBoundary` and reported that every emitted
boundary is assigned `LaneBoundarySource::kCamera`. It also located LTSB writes
of `Road.topology_source_ = RoadTopologySource::kSensorTopology` (numeric value
4). These findings justify fail-closed CAMERA boundary provenance and
whole-message SENSOR_TOPOLOGY checks in the prospective structural audit.

Camera boundary ranges are contiguous and append-ordered. Boundary vertices
are copied verbatim from the camera input without sorting, reversal, or frame
conversion; corresponding arc lengths are generated in the same order,
starting at zero and nondecreasing across consecutive vertices. Direction
relative to vehicle travel remains unproven. The audit may validate stored
order and arc-length consistency and may use orientation-invariant geometric
span, but it may not infer forward direction or frame equivalence.

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

The value is the camera lane-marking measurement/validity time in nanoseconds,
not an LTSB processing or publication time. Because the proto3 scalar has no
presence bit, the audit can test only that the decoded timestamp is a positive
non-Boolean integer, not that it was explicitly serialized. No nominal LTSB
publication rate or guaranteed forward range was found. Full forward geometry
may require following successor indices, while empty map-informed successor
segments can terminate camera geometry.

RLMB uses a pose-estimate validity timestamp and documents its ego reference
as the rear-axle centre. Both timestamps use the ADP clock and describe content
validity, so source-time proximity can be audited. Physical frame-origin
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
| producer and configuration | technical symbols substantially answered; checkout SHA and complete paths missing | retain as intermediate source evidence, not independently reproduced fact |
| root proto and field topology | nested decoder structure answered for the unidentified checkout | validate recorded descriptors by message-owned structure |
| coordinate frame/origin/axes | unresolved except units | prohibit cross-topic geometry alignment and residual math |
| ego binding | answered | require exactly one in-range ego index; reject zero or multiple |
| centreline representation | answered negatively | direct path is drift; camera midpoint is diagnostic only |
| ranges and graph indices | substantially answered | use `(start, size)` and message-local indices; never guess branches |
| fallback geometry | camera boundary writers only; every emitted boundary is assigned CAMERA; empty/map-informed topology exists | require sensor whole-message source, camera ranges, and CAMERA boundaries; reject drift |
| map/RLMB dependence | direct map/map-matching inputs; no direct RLMB topic | state map-influenced topology; do not claim independence |
| timestamp and rate | timestamp scalar/units/producer answered; no presence bit; rate unresolved | require positive decoded source time; source-time proximity only; no cadence claim |
| forward guarantee | unresolved; successor traversal may be required | audit explicit unique camera-only chains and observed span only |
| RLMB frame/epoch equivalence | time semantics compatible; physical origin unresolved | no anchor test or H100 residual-pair claim |
| generation differences | interface history partial; producer history unresolved | inventory exact recorded descriptors; no cross-generation assumption |

## Current conclusion

The trace is useful and changes the original a0 proposal materially. It
supports a narrower audit of descriptor identity, strict camera-boundary
reconstruction, unique successor connectivity, observed 100 m geometric span,
RLMB readiness, and source-time synchronization. It does **not** support the
original cross-topic anchor-distance test or the phrase "H100 structural
pair", because those require frame-origin equivalence.

A positive synchronized 100 m count would mean only that both inputs appear
structurally available at nearby validity times. Before any residual is
calculated, BMW evidence or a separately reviewed empirical frame-calibration
contract must establish the coordinate transform, timestamp handling, and the
scientific acceptability of map-influenced topology selection.

## Final provenance supplement required before contract review

Together, the two traces are sufficient to reject a0 and specify the nested
dynamic-decoder and fail-closed producer checks for an intermediate a2
contract. They are not sufficient to freeze a review candidate because the
second response omitted the requested checkout identity and supplied
basenames rather than complete repository-relative paths. One final, strictly
provenance-only BMW-source response must record:

1. the literal output of `git rev-parse HEAD`,
   `git rev-parse --show-toplevel`, and `git status --short` from the checkout
   used for source verification; the status must be empty, and the technical
   findings must be rechecked at that exact clean HEAD; and
2. the complete tracked repository-relative path for every cited producer,
   activity, topic-definition, parameter, proto, header, and design file,
   derived from that same checkout rather than inferred from basename search.

The technical questions about nested declarations, mean validity, CAMERA
source assignment, whole-message sensor-topology assignment, stored ordering,
unset-range semantics, timestamp type, and the negative frame finding are
closed for the intermediate contract. Vertex direction, physical frame/origin,
publication cadence, and guaranteed forward extent remain unresolved by
design; they do not block the structural/co-availability audit because it
claims none of those semantics.

This supplement is technical interface evidence only. It must not inspect an
MCAP, report payload values, or change BMW code.
