# v0.18.0/v0.18.1 sensor-topology implementation handoff

Status: v0.18.0 received focused implementation `GO` and its one authorized
private run is preserved. That run exposed one reference descriptor binding
defect. The narrow v0.18.1 correction has corrective `GO`, passing Python
3.10/3.12 CI, and an accepted real-output `GO` on the corrected private run.
Batch01 is closed negative; no further run is authorized. The exact result
and review identities are in `docs/sensor_topology_batch01_v0181_result.md`.

## Reviewed starting point

- branch: `protocol/v0.18.0-sensor-topology-feasibility`
- pushed contract-review HEAD:
  `75a1f9ff38885636dacafbd17144736420a7e17f`
- reviewed contract tree:
  `ad6d9a664ac7ec38cea4c06f2197d02ae4942f4c`
- local patch-source base:
  `857ada05b968e9fd5ebda555118b3b75738d258b`, with the same tree
- contract-review verdict: `GO`
- contract-review report SHA-256:
  `09b0351f448cd60025bd6e662bb5e7c392d38ab2af5332d3765f7b0a30b75c67`

The implementation did not read private MCAP data, the private acquisition
manifest, or either real v0.17 intake directory. All data-path behavior was
verified with synthetic Protobuf messages and temporary synthetic lineage
fixtures.

## Implemented boundary

`domain.sensor_topology_feasibility` owns only descriptor-independent geometry
and timing rules: strict camera-boundary concatenation, consumer-derived
midpoints, unique successor traversal, orientation-invariant 100 m span, and
the recording-local mutual-nearest 50 ms gate.

`io.sensor_topology_feasibility` owns the two fixed topics, message-owned file-
descriptor hashing, exact required Protobuf structure, recursive privacy-safe
field inventory, sensor-message reconstruction, independent RLMB H100
readiness, and per-recording counts. A readable but drifted descriptor retains
its hash and field inventory while failing support; only an unavailable
descriptor receives a null identity.

`workflows.sensor_topology_feasibility` validates the exact preserved v0.17.1
four-file lineage before decoding. It checks the historical top-level and
nested schemas, manifest/raw coverage, opaque IDs, outing fingerprints,
attestations, split state, embargo, schema-amendment lineage, and all sibling
hashes. It writes exactly three deterministic files transactionally and never
overwrites an existing target.

`cli.sensor_topology_feasibility` exposes the reviewed arguments and maps a
complete positive audit to exit `0`, a complete zero-candidate audit to exit
`3`, and input/lineage/command errors to exit `2`.

The package root and historical CLI facade now resolve compatibility exports
lazily. This preserves the historical public API while preventing the v0.18
adapter from transitively loading residual, model, plotting, planner, or legacy
preprocessing layers. The old v0.17 intake import graph and the new narrow
v0.18 graph are both frozen by subprocess tests.

## Contract hardening retained

- The 50 ms gate is explicitly a new, prospectively fixed v0.18 audit value;
  the mutual-nearest algorithm is inherited, but the value is not attributed
  to the v0.17 estimate/reference intake.
- `source_time_pair_count` is defined after the inclusive 50 ms source-time
  gate and before either geometry filter.
- The corrected exported failure vocabulary is a fixed set of 33 codes. The
  added code is only `reference_required_structure_drift`; it distinguishes a
  readable-but-drifted descriptor from an actual reference decode failure.
  Dataclass and workflow boundaries reject unknown codes, malformed hashes,
  invalid count ordering, and inconsistent synchronized counts.
- Structural drift cannot form a timestamp pair, even when Protobuf decoding
  itself succeeds. Required referenced types and the reviewed enum symbols and
  numeric values are checked exactly rather than by a substring heuristic.
- The reference side reproduces the accepted unique-chain, origin-projection,
  positive-x orientation, junction, segment-limit, and 100 m coverage gates
  without exposing or combining coordinates.
- No sensor coordinate is projected onto, compared with, or transformed into
  an RLMB coordinate.
- Inclusive floating-point comparisons use fixed implementation slack only for
  numerical stability: `1e-9 m` at the 100 m accumulated-span boundary and
  `1e-12 m` at the 1 m successor gap and `1e-12 radians` at the 30 degree
  successor heading boundary. These values are not data-tuned tolerances.
  The predeclaration's dated retrospective H2 addendum records the exact
  comparisons and distinguishes the date of that documentation from a3.
- Multiple successors map to `sensor_camera_chain_junction_invalid`;
  `sensor_camera_chain_ambiguous` is reserved for exact orientation ties.

## v0.18.1 corrective delta

The real v0.18.0 schema inventory showed that `RoadLaneSegment.id_` field 1 is
singular `uint64`. The synthetic fixture and reference validator had assumed
`int64`, so decoded RLMB messages were rejected before readiness evaluation.
v0.18.1 corrects that exact type, separates reference descriptor drift from a
true decode failure, and extends the import-graph test through the runtime MCAP
decoder. No sensor rule, threshold, topic, output filename, or scientific
authorization changes. The full boundary is recorded in
`docs/sensor_topology_reference_schema_amendment.md`.

## Synthetic verification

Focused tests cover:

- exact descriptor identity and recursive inventory;
- conformant descriptor generations and fail-closed field drift;
- topology-source, ego-index, range, sentinel, CAMERA provenance, wrapper,
  arc, width, orientation, gap, branch, cycle, limit, and span boundaries;
- reference H100 readiness and source-time pairing, including exact 50 ms and
  deterministic ties;
- exact preserved-lineage reconciliation before output creation;
- exact three-file schemas, deterministic bytes, non-overwrite, and exits;
- rejection of nested lineage tampering and unreviewed failure codes; and
- absence of every prohibited direct or transitive import.

Correction verification on 2026-09-17:

```text
python -m compileall -q src tests                         passed
git diff --check                                          passed
focused v0.18.1 tests                                     30 passed
full unittest suite                                       434 run
                                                            432 passed
                                                            2 expected skips
```

The takeover verification used Python 3.12.14, NumPy 2.3.5, and Protobuf
6.33.6. The extra test preserves the 100 m sensor-span gate after the corrected
reference descriptor permits readiness and timing checks. The two skips are
the opt-in wheel-content check (`MPR_WHEEL_PATH`) and private historical
alignment parity (`MPR_RUN_PRIVATE_ALIGNMENT_PARITY`). This local result does
not replace Python 3.10/3.12 CI with the MCAP extras installed.

The original v0.18.0 source at `6a71782` and corrected source were also run on
identical synthetic `uint64` messages. The reference is a straight 120 m path
and the two timestamps are identical. These are constructed fixtures, not BMW
measurements or a private rerun:

| Synthetic sensor span | Version | Sensor 100 m count | Reference ready | Time pairs | Synchronized candidates |
|---|---|---:|---:|---:|---:|
| 80 m | v0.18.0 | 0 | 0 | 0 | 0 |
| 80 m | v0.18.1 | 0 | 1 | 1 | 0 |
| 120 m | v0.18.0 | 1 | 0 | 0 | 0 |
| 120 m | v0.18.1 | 1 | 1 | 1 | 1 |

Thus the correction fixes premature reference rejection without changing
sensor availability. The original warning alone cannot distinguish these
cases. At synthetic verification time, the real reference-ready and
timestamp-pair counts were unknown and could not be inferred from these
fixtures. The later accepted real counts are 9,235 and 17,087 respectively,
with zero sensor spans and zero synchronized candidates; see the result
document for their artifact-only verification scope.

## Next-agent checklist

1. Read the accepted result and `docs/current_status.md`; implementation,
   corrective and real-output reviews are complete.
2. PR #20 and its documentation closure are merged at `1403927`. Resume on
   the source/acquisition decision branch recorded in `docs/current_status.md`;
   do not apply another patch to the completed PR.
3. Preserve both outputs and review reports unchanged outside Git. Do not
   rerun the closed batch or change a threshold to convert the negative.
4. Complete the source/configuration inquiry in
   `docs/sensor_topology_source_acquisition_decision.md`, then select the next
   supported implementation and its applicable contract/review. These outputs
   do not identify an alternative horizon or establish frame equivalence.

## Historical corrective checklist (completed)

This was the sequence before the accepted corrected real run; it does not
authorize another execution.

1. Confirm a clean worktree after applying the delivered patches.
2. Run the compile and full-suite commands in `AGENTS.md` on Python 3.10 and
   Python 3.12 CI.
3. Push the implementation branch and record both `git rev-parse HEAD` and
   `git rev-parse HEAD^{tree}`.
4. Request focused independent corrective review using a prompt supplied
   outside the repository; reviewer prompts are not committed project docs.
5. If the verdict is `AMEND`, change only the identified implementation or
   contract defect and repeat review.
6. Only a corrective `GO` authorizes one private closed-batch01 rerun using
   the documented command template and a new v0.18.1 output directory. Preserve
   the original v0.18.0 output unchanged.
7. A positive synchronized count authorizes only physical-frame resolution and
   a separate alignment-audit predeclaration. It does not authorize a residual,
   target adoption, historical EDP model reuse, fitting, planning, or figures.
