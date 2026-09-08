# v0.17.1 batch01 amended intake result

Status: accepted negative technical audit. The reviewed schema-v2 adapter
worked as declared, the standalone verifier passed, and Claude's focused real-
output review returned `GO`. This is not a successful cohort lock and does not
authorize model fitting, sampling, planner execution, final-outing evaluation,
gate relaxation, or an independent-generalization claim.

Date: 2026-09-08.

## Scope and lineage

Batch01 contains 86 consecutive MCAP chunks from one separately declared
physical outing. They remain one independent unit. The v0.17.1 run reused the
exact prospective manifest and raw bytes from the preserved v0.17.0 audit,
supplied that failed audit through
`--amended-from-failed-intake-directory`, supplied no prior successful lock,
and wrote to a new output directory.

The implementation review covered pushed commit
`ad8f72eb349d6f5ef5660043fff1d29a7cc12071`, tree
`1210048ae2d42ae7519044b53f0ea11574d3cd5d`, and returned `GO`. Its report
SHA-256 is:

```text
7cb78f59eb77eca0da85e81a9961096ccbd57adddd547f70404e13fa6a7928e7
```

The prospective manifest SHA-256 is:

```text
8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d
```

The amended output hashes are:

```text
independent_outing_recordings.csv
7dcf94f335f12c5adc0f7d8b198935daaf90d092bf9fc620babb6f340847cba5

independent_outings.csv
100b9e15f3b7a5e6d57eb4fdfa9e68b285e2f0546c40cd8a2705a6b000674847

independent_outing_lock.json
b4c66ab0657119c87517facf9001d3f675847483d3d2ad96193f944067963616

independent_outing_intake_summary.json
fcdbc4958b2838846c8aed6c44689830c3c6197780769e6386df4f7577f02ea6
```

The delivered four-file ZIP SHA-256 is
`d1ab5221280c7676eabdf09f8d118fbfca8ef27005d5a2ba5c940080390157ab`.
The standalone-verifier JSON SHA-256 is
`09de0c3186030c12aa26accd85382ae4942d0e6890ae8e1f74d1371b9bb2e623`.

The new lock and summary contain the same non-null
`schema_compatibility_amendment.amended_from_failed_audit` object. Its manifest
hash and all four recomputed output hashes equal the preserved v0.17.0 audit.
The old and new 86-entry raw-basename/SHA-256 maps are identical, and the
content-only outing fingerprint remains
`bb8d97f8e3f7becb5cf0b442498f5a20bfa6e2addd582daead5ecc3bfd4d7774`.

## Verification boundary

The standard-library verifier reports:

```text
contract_revision: v0.17.1-reviewed-2026-09-07-schema-v2-a1
schema_compatibility_amendment_id: v0.17.1-edp-schema-v2-2026-09-07
raw_mcap_count: 86
verification_status: passed
verification_scope: lineage_identity_split_and_report_reconciliation_only
technical_evidence_redecoded: false
files_written: 0
```

The verifier independently rehashed the real raw corpus, manifest, preserved
audit, and amended outputs and reconciled identity, split, roles, schemas, and
reports. It deliberately did not decode MCAP technical evidence. Consequently,
lineage is independently verified, while the technical counts below come from
the single reviewed producer run. The delivered record did not include the
terminal transcript; intake exit `3` and verifier exit `0` follow from their
stored statuses but are not separately evidenced by a terminal artifact.

Claude's final real-output review independently reconciled the delivered
artifacts and returned `GO`. Its report SHA-256 is:

```text
a33506179c1719207cb3b89b7744dc4ea1e82f07269941e9656874c93ce28c4e
```

## Technical result

The schema-v2 adapter removed the blanket descriptor-binding blocker without
changing identity, timing, raw usability, topic counts, boundaries, or frozen
eligibility rules:

| Quantity | Result |
|---|---:|
| raw-usable recordings | 86 / 86 |
| summed usable duration | 1707.738856448 s |
| decoded estimate messages | 17,163 |
| H100 geometry-ready paths | 5,289 |
| SENSOR_TOPOLOGY candidates | 0 |
| LANE_MAP candidates | 5,289 |
| unknown/other candidates | 0 |
| eligible H100 frames | 0 |
| eligible sequences | 0 |
| technically eligible new outings | 0 / 1 |
| required technically eligible new outings | 7 |

Exactly four recording-CSV columns changed relative to v0.17.0:
`failure_codes`, `h100_geometry_ready_count`,
`lane_map_topology_candidate_count`, and `topology_gate_candidate_count`.
Thirty-three recordings produced no H100-ready path; among the other 53, the
per-recording ready count ranges from 4 to 201 with median 85.

The producer's non-mutually-exclusive recording failure counts are:

| Failure code | Count |
|---|---:|
| `topology_source_not_sensor_topology` | 83 |
| `causal_inputs_estimate_condition_horizon_incomplete` | 67 |
| `h100_estimate_coverage_incomplete` | 63 |
| `causal_inputs_odometry_interpolation_gap_exceeds_limit` | 55 |
| `h100_reference_coverage_incomplete` | 47 |
| `map_map_ego_drive_path_not_unique` | 39 |
| `causal_inputs_boundary_context_endpoint_ineligible` | 36 |
| `causal_inputs_not_ready` | 4 |
| `estimate_not_attempted_estimator_unavailable` | 4 |
| `anchor_distance_exceeds_1m_or_invalid` | 3 |
| `filename_internal_duration_disagreement` | 2 |
| `map_RoadMessageError` | 2 |
| `reference_pair_unavailable` | 2 |

The outing-level failure codes are
`mixed_or_unknown_topology_source`, `eligible_frame_count_below_500`, and
`eligible_sequence_integrity_failed`. The last two follow from zero eligible
frames and are not independent causes.

## Interpretation and claim boundary

The adapter succeeded: all 17,163 estimate messages were decoded under the one
observed, exactly pinned schema-v2 descriptor, and 5,289 paths reached H100
geometry readiness. The candidate set is entirely LANE_MAP and therefore fails
the prospectively frozen SENSOR_TOPOLOGY primary-cohort rule.

This does not mean the complete outing contains no SENSOR messages. The prior
privacy-safe audit observed 787 SENSOR messages across three SENSOR-only and
two mixed recordings, but none of those messages produced an H100-ready
candidate. The accurate conclusion is therefore:

> The candidate set is entirely LANE_MAP. The outing's SENSOR_TOPOLOGY
> messages produced no H100-ready geometry and contributed no candidates.

Topology is sufficient to force zero eligible frames, but this audit does not
show that topology is the only obstacle or that the outing would otherwise
have passed the 500-frame gate. The additional H100/map-pairing, coverage,
anchor, and causal-input failures remain descriptive evidence. Neither those
gates nor the topology gate may be relaxed after observing this result.

The final status remains `insufficient_independent_outings`, split assignment
is unauthorized, all cohort roles/ranks/scores are null, and no final-outing
embargo is activated. This is an accepted negative technical audit, not a
successful lock.

## Next authorized action

Preserve the manifest, raw bytes, v0.17.0 audit, v0.17.1 audit, verifier result,
and both review reports unchanged. Acquire further genuinely independent
physical outings prospectively, using a new manifest and a new output directory
for each reviewed intake. The primary cohort still needs at least seven
technically eligible new outings; batch01 contributes zero.

Where operationally possible, future acquisition should use the same
SENSOR_TOPOLOGY domain as the accepted development lineage. If the available
production configuration emits only LANE_MAP, that is a domain-change blocker:
it requires a separate prospective scientific contract rather than relabeling
LANE_MAP as SENSOR, relaxing a gate, or repurposing batch01 after inspection.
