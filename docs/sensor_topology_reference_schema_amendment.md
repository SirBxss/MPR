# v0.18.1 sensor-topology reference-schema correction

Status (2026-09-17): narrow correction accepted by focused corrective `GO`.
Its one authorized private rerun is reconciled and has real-output `GO` with
zero blockers. Batch01 is closed negative under unchanged structural rules;
see `docs/sensor_topology_batch01_v0181_result.md`. No further run is authorized.

Contract revision:
`v0.18.1-review-candidate-2026-09-17-reference-uint64-a1`.

## Why a correction is required

Claude returned implementation `GO` for v0.18.0 commit
`6a717827363529773a24f8fba2094cf5e75565b0`, tree
`530b73ff51243b8bfd27c3ffa47ef29e17649235`. The one authorized private run
then completed against the preserved 86-file batch01 lineage.

The privacy-safe schema inventory established that both fixed topics use one
message-owned `Adp.Perception.Road` file descriptor. Its
`RoadLaneSegment.id_` field 1 has Protobuf kind `uint64` (descriptor kind 4).
The v0.18.0 reference validator and its synthetic fixture instead required
`int64` (kind 3). Consequently, all decoded RLMB messages were retained as
`required_structure_drift` and the recording failure code incorrectly reported
`reference_stream_decode_failed`, even though reference decoding and source
timestamps succeeded.

This is a fixture and binding defect, not evidence that the reference stream
failed. The failed v0.18.0 output remains immutable diagnostic evidence and is
not an accepted complete two-sided audit.

## Exact correction

The v0.18.1 correction is limited to:

1. require singular `uint64` for `RoadLaneSegment.id_` field 1 in the RLMB
   descriptor validator;
2. use a `uint64` segment ID in the synthetic descriptor fixture and test that
   an `int64` variant fails closed;
3. report readable descriptor drift as
   `reference_required_structure_drift`, while reserving
   `reference_stream_decode_failed` for an actual decoding failure;
4. extend the frozen CLI dependency test through the runtime MCAP decoder
   import; and
5. identify corrected outputs as version `0.18.1` and the revision above.

The descriptor SHA-256 remains inventory evidence rather than an allow-list.
No basename, recording, message value, or observed outcome is special-cased.

## Rules that do not change

The estimate and reference topics, preserved v0.17.1 lineage, three output
filenames, privacy boundary, 50 ms source-time gate, strict CAMERA provenance,
unique ego binding, successor traversal, 16-segment limit, 1 m junction gap,
30 degree junction heading, 1--10 m median width band, and 100 m sensor span
remain unchanged.

The first real run also observed zero sensor chains reaching 100 m. That result
does not justify changing the horizon, reconstruction rule, or any threshold.
The v0.18.1 rerun corrects only the reference descriptor binding. If the
sensor-side 100 m count remains zero, the closed batch is negative for H100
structural feasibility regardless of reference readiness.

The audit still performs no cross-topic coordinate comparison, alignment,
anchor calculation, residual construction, condition extraction, sequence
construction, model fitting, planner execution, or figure generation. A
positive synchronized count would authorize only a separately predeclared
physical-frame and alignment audit.

## Review and rerun order

The following sequence is complete; it records the authorization history and
is not a fresh run instruction.

1. Verify the exact pushed corrective HEAD and tree.
2. Reproduce the focused and complete synthetic test suites.
3. Review this amendment and the corrective diff against the approved a3
   contract and v0.18.0 implementation review.
4. Only a focused corrective `GO` authorizes one rerun against the same raw
   bytes, manifest, and preserved v0.17.1 intake, into a new v0.18.1 output
   directory.
5. Preserve both the v0.18.0 and v0.18.1 three-file outputs for reconciliation.

Reviewer requests are supplied outside the repository. They are not project
documentation and must not be committed under `docs/`.
