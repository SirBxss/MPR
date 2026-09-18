# v0.18.1 batch01 sensor-topology audit result

Date: 2026-09-17. Status: artifact reconciliation and focused independent
real-output review passed (`GO`, zero blockers). Batch01 is closed negative
under the frozen 100 m structural rules. Preserve both outputs; no further
run is authorized. The user merged PR #20 at `1403927` after applying the
closure; see `docs/current_status.md` for the exact merge and CI identities.

## Scope and implementation identity

This is the approved narrow correction to the v0.18.0 structural audit:
singular `uint64` replaces the incorrect `int64` binding for RLMB segment ID,
and readable reference descriptor drift has its own failure code. All sensor
rules, topics, horizons, timing limits and output boundaries are unchanged.

Claude's corrective `GO` covered pushed implementation HEAD
`bc50ee656351beca14ab1f0ae57613fc3b86e81c`, tree
`3c78a31fbbce0161abd049abf7768289b90aa0d8`. Python 3.10 and 3.12 CI passed
with the configured MCAP extras. The user subsequently supplied the real
v0.18.1 output and reported applying the documentation-only review handoff.
The artifacts record version and contract revision, not a Git commit or
runtime-environment fingerprint; artifact reconciliation alone cannot prove
the exact executed checkout. The handoff patch changes no executable code.

The estimate-side topic is `/adp/lane_topology_sensor_based` (LTSB). The
reference-side topic remains `/adp/road_lane_map_based` (RLMB). The new
candidate target has not been adopted. This is not a residual export.

## Reconciled before/after counts

The table distinguishes recording, message and one-to-one pair counts. The
two streams are audited independently before the source-time pairing filter.

| Quantity | Preserved v0.18.0 | Corrected v0.18.1 |
|---|---:|---:|
| MCAP recordings | 86 | 86 |
| Decoded sensor messages | 17,163 | 17,163 |
| Decoded reference messages | 17,163 | 17,163 |
| Explicit ego candidates | 16,737 | 16,737 |
| Camera-boundary structures | 4,078 | 4,078 |
| Valid camera-only chains | 4,039 | 4,039 |
| Sensor chains reaching 100 m observed span | 0 | 0 |
| Independently H100-ready reference messages | 0 (descriptor defect) | 9,235 |
| Mutual-nearest source-time pairs within 50 ms | 0 (descriptor defect) | 17,087 |
| Synchronized dual 100 m structural candidates | 0 | 0 |

The reference descriptor changed from `required_structure_drift` to
`structure_conformant`. Sensor descriptor support remains conformant. The
message-owned descriptor digest, root name, encodings, full field inventory
and message count are otherwise identical in both inventories:
`55bb7100cf187ec60d4aa5eaeebcca56793b042f55398c940d9330fae615a364`.

There is no remaining `reference_stream_decode_failed`,
`reference_required_structure_drift`, or `source_time_pair_unavailable`
recording failure in v0.18.1. The recorded technical status remains
`no_synchronized_100m_candidates`; target adoption remains false.

## Reconciliation performed

A read-only Python standard-library comparison, without importing the MPR
implementation, checked:

- the exact three-file set, duplicate-free finite JSON, exact JSON keys and
  CSV header, 86 unique basename-ordered rows, and sibling file hashes;
- equality of the recorded manifest hash, preserved v0.17.1 lock hash, the complete
  86-entry recorded raw-basename/hash map, and per-file byte sizes;
- equality of the raw-map aggregate digest and all fixed topics, thresholds,
  chain limits, claim limits and authorization fields;
- every summary count and recording-failure count against the CSV rows,
  strict timestamp flags, descriptor-message counts and prerequisite-count
  bounds; and
- unchanged sensor-side counts and failure-code sets in **every** recording,
  unchanged sensor failure totals, and the expected reference support change.

Only three CSV columns change: `reference_h100_ready_count`,
`source_time_pair_count`, and `failure_codes`. Only six summary fields change:
`version`, `contract_revision`, those two counts, `recording_failure_counts`,
and `output_sha256`. The inventory changes only version, revision and the
reference support status. These satisfy corrective-review follow-ups H1 and
H4. No additional statistic, horizon sweep or geometry diagnostic was run.

The implementer's workspace also held the separately supplied private
manifest file: hashing its bytes reproduced the recorded manifest digest.
The independent reviewer did not have that file and checked only its recorded
hash across artifacts. This distinction resolves review item O1 without
attributing the implementer's byte-level check to the reviewer.

The intake and audit use different input roots: their private relative paths
are respectively `candidate_session_2025-08-21/<basename>` and `<basename>`.
That path column is root-relative, not a cross-workflow identity invariant.
Lineage is reconciled through the complete basename/SHA-256 map and all 86
recorded file sizes, not through equality of those relative paths (O3).

The raw MCAPs are unavailable in this workspace. Their recorded hashes were
reconciled with the preserved intake; their bytes were not independently
rehashed, and messages were not re-decoded. The supplied audit reports its
own lineage check as passed. This verification establishes artifact integrity
and report consistency, not independent reproduction of raw geometry.

## Remaining failure codes

These counts are numbers of recordings with at least one occurrence. They
are nonexclusive and must not be interpreted as message attrition counts.
The two reference readiness codes are newly visible after the descriptor
gate was corrected; v0.18.0 never reached those checks. Their appearance does
not establish newly occurring reference defects (O2).

| Recording failure code | Recordings |
|---|---:|
| `reference_ego_drive_path_not_unique` | 41 |
| `reference_successor_chain_invalid` | 48 |
| `sensor_camera_boundary_geometry_invalid` | 57 |
| `sensor_camera_boundary_range_invalid` | 51 |
| `sensor_camera_boundary_width_implausible` | 36 |
| `sensor_camera_chain_100m_span_unavailable` | 48 |
| `sensor_camera_chain_junction_invalid` | 9 |
| `sensor_ego_segment_not_unique` | 10 |

## Exact artifact lineage

The received v0.18.1 ZIP SHA-256 is:

```text
4e280bf5af9c6fe1f5b0be35746c24b1dfde32fbf254e271e91b22d498644f86
```

Its files rehash to:

```text
sensor_topology_recordings.csv
49c388e7d191a47ab5960d12f6228778f13eb9c67da05754d223889e9f100a0a

sensor_topology_schema_inventory.json
381228a60d7b24706eb0d4c3ede7c3b7a5279afd0bbbfea6b7f5f77c29d4bab0

sensor_topology_feasibility_summary.json
3de7fc8b3ccf275c167e038952257b921eeec5bfc39b6367bcd62718e171902d
```

The unchanged manifest, preserved intake lock and raw-map digest are:

```text
manifest
8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d

preserved v0.17.1 intake lock
b4c66ab0657119c87517facf9001d3f675847483d3d2ad96193f944067963616

86-entry raw-basename/SHA-256 map
1aaabfcaabd33ea31591643781ab7ef459cbf16774aeec73fe3e592ce928daae
```

The original v0.18.0 ZIP remains unchanged at
`c7f9aad2a38b6b370e827ebd5ef5cf36b26aab54cfdd16179f02a7e570018b7a`.
Raw files, manifests, audit outputs and review reports remain outside Git.

## Independent acceptance and review qualifications

`MPR_v0.18.1_batch01_real_output_review.md` returned **GO with zero blockers**
on documentation HEAD `77b1d8e34dca2e8a7e10d3457ce3b50ea7fd2e88`, tree
`7f535d84f7e76ce8eaf9de24a6a776f279d648b9`. Its SHA-256 is
`1caa9e1c520a6ba836041f12d679027fdb13a0da4529b5ad60a9f466856d01f8`.
The review independently reconciles the supplied outputs and accepts the
bounded interpretation; it does not reproduce raw geometry. GitHub Actions
run [35215993924](https://github.com/SirBxss/MPR/actions/runs/35215993924)
passes both Python 3.10 and 3.12 jobs, including MCAP-extra installation,
compilation and unit tests. The reviewed documentation tree has identical
`src/`, `tests/` and `pyproject.toml` objects to approved implementation
`bc50ee6`.

Preserve the review unchanged, with these interpretation qualifications:

- Positive sensor-chain, reference-ready and time-pair counts within one
  recording do not by themselves prove that the qualifying messages were
  paired. The review's recording-level cross-tabulation cannot establish its
  stronger claim that every other precondition is satisfied jointly. Zero
  sensor 100 m spans is sufficient to force zero synchronized candidates;
  it does not prove that span is the only failing gate for each pair.
- Identical repository trees establish unchanged committed code, not which
  checkout or uncommitted state produced the private output. The review's
  code-identity discussion must retain its own artifact-only execution limit.
- Zero spans do not locate chains relative to the numerical boundary. The
  review's illustrative `99.999999999 m` span is within the implemented
  `1e-9 m` comparison slack, so it is not an example of a necessarily rejected
  span. The absence of exported lengths still prevents any near-boundary claim.

These qualifications do not change any count or the accepted negative result.
Optional H2 is addressed by the dated retrospective numerical clarification
in `docs/sensor_topology_feasibility_predeclaration.md`; no executable rule
or output revision changes. O4 is addressed in the current status and README.

## Interpretation and next gate

Update on 2026-09-18: the later BMW source transcript requires an epoch
interpretation correction, recorded in
`docs/bmw_sensor_topology_epoch_evidence.md` and pending its own focused
review. Treat the 17,087 time pairs as numeric embedded-header proximity;
the recorded producer mode, geometry epoch and measurement-age relationship
remain unknown. No count, hash, original review or output is changed.

The binding defect is corrected: reference readiness and timing are now
evaluated. Under the unchanged strict camera-only reconstruction, this one
closed batch still supplies no synchronized 100 m structural candidates
because no sensor chain reaches the required observed span. Timestamp
pairing alone does not make a residual pair, and reference readiness counts
must not be interpreted as paired sensor/reference H100 counts.

The audit does not reveal individual sensor lengths, maximum extent, how
close chains are to 100 m, or which shorter horizon would be defensible. It
does not establish that the topic is generally unusable or identify a unique
physical reason for the sensor result. Frame equivalence remains unverified;
LTSB topology is map-influenced and RLMB is not physical ground truth. The
86 files are one physical outing, not 86 independent validation units.

The documentation closure and user's merge are complete. The next step is
the interpretation review and recording/frame evidence request in
`docs/bmw_sensor_topology_epoch_evidence.md`. The original implementation
and real-output reviews are complete; the later epoch clarification is a
separate review scope. Do not rerun, change thresholds, adopt
a shorter horizon, construct residuals, refit models or execute a planner to
turn this result positive. Any subsequent acquisition change or alternative
target/horizon requires its own prospective decision and applicable review.
This result does not alter the historical EDP models or establish planner
benefit. The next research step is a prospective acquisition/configuration or
target decision using producer evidence; these artifacts cannot choose a
shorter horizon. New scientific execution requires its applicable contract
and review. Merging the accepted audit does not authorize that execution.
