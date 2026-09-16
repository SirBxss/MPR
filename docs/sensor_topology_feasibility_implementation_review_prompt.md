# MPR v0.18.0 sensor-topology implementation review request

Please perform a focused independent implementation review of the MPR v0.18.0
sensor-topology structural-feasibility audit.

Repository:
`https://github.com/SirBxss/MPR`

Pull request:
`https://github.com/SirBxss/MPR/pull/20`

Implementation branch:
`protocol/v0.18.0-sensor-topology-feasibility`

Exact pushed implementation HEAD:
`[PASTE git rev-parse HEAD]`

Exact pushed implementation tree:
`[PASTE git rev-parse HEAD^{tree}]`

Reviewed contract HEAD:
`75a1f9ff38885636dacafbd17144736420a7e17f`

Reviewed contract tree:
`ad6d9a664ac7ec38cea4c06f2197d02ae4942f4c`

The attached `MPR_v0.18.0_sensor_topology_contract_review.md` is the focused
contract review of that exact contract tree. It returned `GO` for
synthetic-only implementation. Its SHA-256 is:
`09b0351f448cd60025bd6e662bb5e7c392d38ab2af5332d3765f7b0a30b75c67`.

Do not run or request private MCAP data, the private acquisition manifest, or
real v0.17/v0.18 outputs. Do not inspect numeric candidate payloads. Review
only the pushed code, synthetic tests, documentation, and PR diff. Please first
verify the exact implementation HEAD and tree.

## Required review surface

Contract and evidence:

- `docs/sensor_topology_feasibility_predeclaration.md`
- `docs/bmw_sensor_topology_source_evidence.md`
- `docs/independent_outing_batch01_v0171_result.md`
- `docs/output_contracts.md`
- `docs/architecture.md`
- `docs/commands.md`
- `docs/current_status.md`
- `docs/sensor_topology_feasibility_implementation_notes.md`

Implementation:

- `src/lane_residuals/domain/sensor_topology_feasibility.py`
- `src/lane_residuals/io/sensor_topology_feasibility.py`
- `src/lane_residuals/workflows/sensor_topology_feasibility.py`
- `src/lane_residuals/cli/sensor_topology_feasibility.py`
- `src/lane_residuals/__init__.py`
- `src/lane_residuals/cli/__init__.py`
- `src/lane_residuals/io/mcap.py`
- `pyproject.toml`

Tests:

- `tests/domain/test_sensor_topology_feasibility.py`
- `tests/io/test_sensor_topology_feasibility.py`
- `tests/workflows/test_sensor_topology_feasibility_cli.py`
- `tests/workflows/test_independent_outing_intake_cli.py`

## Points to verify independently

1. The workflow validates the exact preserved v0.17.1 four-file audit and its
   complete nested lineage before creating output. Missing, extra, changed, or
   structurally drifted dependencies fail closed.
2. The audit is restricted to the exact closed batch01 raw basename/SHA-256
   map and unchanged private manifest. It does not inspect the legacy 67-file
   modeling lineage.
3. Descriptor identity comes only from
   `sha256(message.DESCRIPTOR.file.serialized_pb)`. A readable but unsupported
   descriptor retains its identity and recursive privacy-safe field inventory;
   only an unavailable descriptor receives a null identity.
4. Topic, schema name, schema encoding, message encoding, root identity,
   required field numbers, labels, scalar/message/enum kinds, referenced type
   names, and required enum values are checked structurally and fail closed.
   Multiple independently conformant descriptor generations remain separate
   inventory entries rather than creating a fingerprint allow-list.
5. Sensor-message acceptance requires the exact SENSOR_TOPOLOGY enum, exactly
   one valid non-Boolean integral ego index, the exact unwritten-range
   sentinels, nonempty in-bounds camera ranges, CAMERA boundary provenance,
   valid wrapper means and flags, valid vertex and arc slices, the reviewed
   width band, and no fallback to an LTSB direct path or EDP geometry.
6. Reconstruction preserves stored boundary order, fails on orientation ties,
   uses only the reviewed duplicate/gap rules, creates a consumer-derived
   midpoint, and traverses only a unique explicit successor chain with the
   reviewed cycle, segment-limit, gap, heading, empty-termination, and
   orientation-invariant 100 m rules.
7. `/adp/road_lane_map_based` H100 readiness is evaluated independently using
   the accepted RLMB rules. The implementation exposes no RLMB coordinate and
   does not weaken those rules.
8. The only cross-topic operation is recording-local mutual-nearest pairing of
   valid source timestamps with the prospectively fixed inclusive 50 ms gate.
   `source_time_pair_count` is counted before either geometry gate, and
   deterministic ties cannot cross recordings.
9. No sensor coordinate is projected onto, compared with, anchored to, or
   transformed into an RLMB coordinate. The workflow creates no residual,
   station sample, condition, sequence, model, planner input, or figure.
10. The exact fixed vocabulary of 32 exported failure codes is enforced.
    Unknown codes, malformed hashes, invalid counts, or inconsistent count
    ordering cannot reach an output artifact.
11. The producer writes exactly three reviewed files with the exact CSV/JSON
    schemas and fixed claim limits. It writes no timestamps, coordinates, raw
    numeric payloads, or derived geometry values, is byte-deterministic under
    the declared inputs, and never overwrites an existing target.
12. Complete positive audits exit `0`, complete zero-candidate audits exit `3`,
    and usage, input, lineage, decoding, and output failures exit `2` without a
    partial target directory.
13. The direct and transitive import graph excludes residual, condition,
    sequence, modeling, sampling, planner, evaluation, visualization, and
    `legacy.preprocessing` modules while preserving the historical package API
    and explicitly re-freezing the narrower v0.17 intake import graph.
14. Synthetic tests cover exact thresholds and adversarial Boolean, range,
    wrapper, arc, width, orientation, branch, cycle, limit, descriptor-drift,
    timestamp, lineage-tampering, determinism, no-overwrite, and import-graph
    cases without reading private data.
15. Documentation preserves the accepted negative v0.17.1 result and states
    the scientific limit accurately: even a positive synchronized count is
    not an H100 residual pair and authorizes only physical-frame resolution
    followed by a separately reviewed alignment-audit contract.

Please reproduce, if possible:

```bash
python -m compileall -q src tests

env PYTHONPATH=src \
  MPLBACKEND=Agg \
  MPLCONFIGDIR=/tmp/mpr-matplotlib \
  python -m unittest \
    tests.domain.test_sensor_topology_feasibility \
    tests.io.test_sensor_topology_feasibility \
    tests.workflows.test_sensor_topology_feasibility_cli

env PYTHONPATH=src \
  MPLBACKEND=Agg \
  MPLCONFIGDIR=/tmp/mpr-matplotlib \
  python -m unittest discover -s tests -t .

git diff --check 75a1f9ff38885636dacafbd17144736420a7e17f..HEAD
```

The expected local result is 28 focused v0.18.0 tests passing and 432 full
tests run: 430 passing and two expected optional-dependency skips.

## Verdict

Return exactly one primary verdict:

- `GO`: the exact implementation faithfully implements the reviewed contract
  and authorizes only one private closed-batch01 structural/co-availability
  audit using a new empty output directory.
- `AMEND`: identify every blocking issue with exact file, symbol or section,
  evidence, consequence, and smallest defensible correction.
- `NO-GO`: only for a fundamental contract or scientific-validity failure.

Separate blockers from optional hardening and do not treat style preferences
as blockers. A `GO` does not authorize merging, target adoption, residual
construction, historical EDP model reuse, model fitting, planner execution,
figures, or scientific claims. The private three-file output must still be
independently reconciled and reviewed before any later decision.
