# BMW standalone sensor-topology source evidence

Last updated: 2026-09-14.

This document tracks the evidence needed to evaluate
`/adp/lane_topology_sensor_based` as a possible estimate-side source for a new
MPR residual target. It deliberately separates user-reported guidance,
observable MPR code, private-data observations, BMW-source evidence, and
inference. It is not permission to decode a target, calculate a residual, or
reuse an old model.

The binding prospective scope is
`docs/sensor_topology_feasibility_predeclaration.md`.

## User-reported guidance and observations

- On 2026-09-14, the data owner reported that Leon recommended switching the
  estimate input from `/adp/estimated_drive_paths` to
  `/adp/lane_topology_sensor_based` and described the standalone topic as the
  preferable source for this study.
- Earlier Lichtblick inspection by the data owner showed
  `/adp/lane_topology_sensor_based` in the new 86-file recording and displayed
  `Adp.Perception.Road` as its message type.
- These observations motivate a prospective audit. They do not establish the
  deployed producer configuration, exact descriptor identity, coordinate
  semantics, ego-lane binding, horizon, or upstream independence.

## Facts visible in the MPR repository

MPR already contains historical technical support for Road-like topology
messages:

- `src/lane_residuals/io/mcap.py::road_frame_from_message` can reconstruct a
  segment from a direct `drive_path_range` or from paired lane boundaries.
- Its historical paired-boundary helper tries `camera_based`, then
  `map_based`, then `artificial`. That permissive fallback is not acceptable
  for a future sensor-only estimate contract.
- It records explicit ego candidates from several possible message/segment
  names, but those names are compatibility heuristics rather than a reviewed
  binding for the new private descriptor.
- `src/lane_residuals/legacy/preprocessing.py` historically defaults to
  `/adp/lane_topology_sensor_based` against
  `/adp/road_lane_map_based` and computes diagnostic residuals only through
  50 m by default.
- The legacy selector permits a nearest-origin fallback when explicit ego
  metadata is absent unless configured otherwise.
- The current RLMB path code requires a unique metadata-confirmed direct ego
  path and follows only an unambiguous, continuity-checked successor chain to
  H100.

These facts reduce implementation uncertainty, but the legacy preprocessing
module is not a canonical v0.18 implementation. Its H50 default, broad schema
aliases, boundary-source fallback, and optional nearest-origin selection must
not be promoted silently.

## Accepted private-data evidence that remains unchanged

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
how many standalone sensor-topology messages or structural H100 pairs exist.

No standalone sensor-topic descriptor hash, message count, ego-lane count,
boundary-reconstruction count, or H100 structural-pair count has been accepted
or recorded in MPR.

## BMW-source evidence still required

The BMW repository is unavailable to MPR. A user-directed, read-only Copilot
investigation should answer the following without changing BMW code:

1. What component publishes `/adp/lane_topology_sensor_based`? Provide the
   exact repository-relative producer file, class/function, and configuration
   entry.
2. What exact `.proto` file and root message define the topic? Provide the
   interface version and relevant message/field numbers.
3. What coordinate frame and vehicle reference point do
   `polyline_vertex_pool`, `boundary_vertex_pool`, and any direct drive path
   use? State axis directions and units.
4. Which exact field identifies the current ego/host lane segment? Clarify
   whether it is an index, ID, flag, or implicit convention and how absence or
   ambiguity must be handled.
5. Which geometry is producer-intended as the sensor ego-lane centreline:
   `drive_path_range`, paired `camera_based` boundaries, or another field?
6. How are left/right boundary ranges and predecessor/successor indices
   encoded? State whether indices address the message-local pools.
7. Can the sensor topic contain `map_based`, `artificial`, fused, cached, or
   fallback geometry? If so, identify the per-message evidence that
   distinguishes it.
8. Does the producer consume lane-map, RLMB, navigation-map, fusion, or
   map-matching inputs directly or transitively? Provide the relevant source
   path and dataflow symbols.
9. What timestamp is written, at which processing stage, and at what nominal
   publication rate?
10. What forward-range guarantee or configuration applies, and can topology
    continue across lane-segment successor links beyond the first segment?
11. Is `/adp/road_lane_map_based` expressed in the same coordinate frame and
    epoch? If not, identify the required transform and its timestamp.
12. Are there interface-generation differences between the accepted legacy
    recordings and the 2025-08-21 batch? Provide commit/version evidence, not
    only a current-source answer.

The answer must distinguish confirmed source facts from inference, include
exact symbols and repository-relative paths, and state explicitly when a
question cannot be established from the available checkout.

## Current conclusion

Leon's recommendation makes the standalone topic the strongest candidate for
the next estimate source. The MPR repository contains useful parser and
geometry primitives, so a new audit should be smaller than a ground-up
integration. It is not a topic-string substitution: descriptor binding,
sensor-only geometry, explicit ego-lane identity, H100 construction, timing,
and producer independence all remain open.

The next safe action is contract review followed by a synthetic-only
implementation of the three-file structural feasibility audit. Real residual
construction remains prohibited even if that audit finds positive structural
H100 counts.
