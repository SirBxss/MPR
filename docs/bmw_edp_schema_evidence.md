# BMW estimated-drive-path schema evidence

Last updated: 2026-09-07.

This document preserves the evidence needed to understand the estimated-drive-
path schema transition encountered during the first real v0.17 intake. It is a
technical hand-off, not an authorization to change an eligibility rule. The
binding scientific contract remains
`docs/independent_outing_intake_predeclaration.md`; the proposed narrow change
is isolated in `docs/independent_outing_schema_v2_amendment.md` and requires
focused independent review before implementation.

## Evidence classes and trust boundary

Three evidence classes must remain distinct:

1. **MPR-observed evidence** was decoded from the MCAP-embedded Protobuf
   descriptors and messages by privacy-safe MPR probes. Codex inspected these
   reports directly.
2. **BMW-source evidence** was returned by GitHub Copilot after a user-directed,
   read-only investigation of the unavailable BMW repository. Codex could
   reconcile it with the observed descriptors but could not independently open
   the cited BMW files.
3. **Inference** is useful interpretation that was not stated in an accessible
   design record or commit message. It must not be promoted to source fact.

The raw Copilot transcript, raw MCAPs, private manifest, and generated intake
outputs remain outside Git. This document records the non-numeric schema facts,
source locations, hashes, and conclusions required for continuity.

## First real intake result

The closed batch contains 86 consecutive MCAP chunks from one separately
started physical outing. All 86 files were raw-readable and raw-usable under
the v0.17.0 container/topic checks. They provide 1,707.738856448 seconds of
summed non-overlapping estimate-source duration. The exact prospective manifest
has SHA-256:

```text
8025ce2a73fc28b1457e0b15c4c870b5d54f80c6913c64a5ea2d4e9877e4c41d
```

The original v0.17.0 run correctly failed closed because the current decoder
requires the legacy `model_parameters_optional_flag`, which is absent from all
86 candidate descriptors. It wrote and retained an
`insufficient_independent_outings` audit with zero eligible frames and no role
assignment. The independent read-only verifier passed at merged commit
`fc46ce533ba6555224d0264e91e7ef7483ace9dc`.

The preserved original output hashes are:

| Artifact | SHA-256 |
|---|---|
| `independent_outing_recordings.csv` | `0f4d0f4e285c676abcadb00b94ee259384867a04330d93fbd6284f7d4d3dabb4` |
| `independent_outings.csv` | `51c8b42f6c7d31b7af1e8817cf295fee999c06897d5ea12ab3d368002cf41c9e` |
| `independent_outing_lock.json` | `9ee7565bd800c11773e17917838efdd5ddc3440c6803aa3a8a65631c8a778e60` |
| `independent_outing_intake_summary.json` | `81f9511575bae84036df98557fa8e63e19db2223e75b0c2cac3cc8d48b96fc0a` |

The ZIP containing those four files has SHA-256
`8389b4559fc445333509ea297750680d5e767f47e8a7de3293510fe13cc3d918`.
It is evidence of a failed availability gate, not an accepted cohort lock.

## MPR descriptor and message evidence

The paired schema probe sampled 200 messages from the legacy corpus and 200
from the candidate corpus without exporting raw numeric payload values. The
complete candidate audit then inspected all 17,163 estimated-drive-path
messages in all 86 files.

| Property | Legacy generation | Candidate generation |
|---|---|---|
| File-descriptor SHA-256 | `f6ae6e61378ea6d3a07d6d7128b232db55d1e00e49c4fd9cd3708c4acea6992f` | `dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4` |
| `drive_paths` | field 4, repeated `Adp.Perception.DrivePath` | unchanged |
| `DrivePath.error` | field 1, enum | unchanged; additional enum values exist |
| `DrivePath.role` | field 2, enum | unchanged |
| `DrivePath.model_parameters` | field 3, message | unchanged and observed through `ListFields()` |
| `model_parameters_optional_flag` | field 8, Boolean; observed true on sampled legacy paths | absent from the descriptor |
| `drive_path_confidences` | field 7, repeated numeric | unchanged |
| `considered_objects_range` | absent | field 10, message |
| `raw_lane_topology_ids` | absent | field 11, repeated integer |

The nested model-parameter bindings retain their field numbers, types, and
cardinality across both observed generations:

| Field | Number | Required MPR use |
|---|---:|---|
| `x_0` | 1 | finite initial position |
| `y_0` | 2 | finite initial position |
| `theta_0` | 3 | finite initial heading |
| `curvature_0` | 4 | finite initial curvature |
| `segment_starts` | 5 | repeated, finite, strictly increasing, length at least 2 |
| `curvature_change` | 6 | repeated, finite, length one less than `segment_starts` |
| `index_0` | 7 | required non-Boolean integer anchor; must satisfy `0 <= index_0 < len(segment_starts)`; not a substitute validity flag |

The complete candidate audit found:

| Measure | Count |
|---|---:|
| MCAP files | 86 |
| decoded estimate messages | 17,163 |
| keep-lane/no-error paths | 17,119 |
| paths passing the probe's pre-conversion structural subset | 17,119 |
| paths truncated by the audit | 0 |
| legacy-rule joint candidates | 0 |

All 86 files have the same candidate schema fingerprint. All 86 fail the
legacy binding check only on `model_parameters_optional_flag`. The probe's
`model_structure_valid` subset checks finite initial parameters, segment
starts, and curvature-change values and lengths; it does not execute the
converter's mandatory `index_0` integer and range checks or H100 conversion.
The candidate descriptor does bind `index_0` as optional int64 field 7, but
the effective value still requires converter validation. Thus the zero
candidate count under the legacy rule is not evidence that model geometry is
unavailable, and the 17,119 subset count is not evidence that every path has
already passed the complete converter.

The complete audit also records, without relaxing the gate:

| `topology_source` | Messages |
|---|---:|
| `ROAD_TOPOLOGY_SOURCE_LANE_MAP` | 16,376 |
| `ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY` | 787 |

Eighty-one files contain only LANE_MAP messages, three only SENSOR_TOPOLOGY,
and two contain both. These are message-level observations, not yet the final
v0.17 topology-candidate counts after H100 pairing and all fixed frame gates.
The reviewed primary-cohort rule remains all-SENSOR over the exact candidate
set; the schema transition does not justify weakening it.

Evidence artifact hashes:

| Evidence | SHA-256 |
|---|---|
| paired schema-probe ZIP | `ca22dd4e0b26f2a93b7d99077ff4ce4219ed73b27053216d78714d9557b8532b` |
| candidate probe JSON | `96b4bfa81ce1aeb1f88e13384b668480a048ebcaff9284fb165d945fc167ccaa` |
| legacy probe JSON | `4f0751b5c832b33187af60e308204459b2605823822625b58032a112b2158cc5` |
| complete 86-file summary text | `24a41fc7d18b97537dacff9d4cd317d927a6bb52142bcf417e92d616d838b65c` |
| Copilot read-only session text | `6f3e4cafd2ccdc0b408751bb64e24e071c53c2c0922137411444b767f2f0c25b` |

## BMW-source trace reported by Copilot

The following facts were reported as confirmed from the BMW repository. Exact
line numbers are approximate because the repository is unavailable here; the
symbol and repository-relative path are the durable locator. The inspected
local mirror has rewritten/squashed history and reports the same change under
multiple IDs, so the commit IDs below are trace clues rather than stable
upstream citations.

### Schema transition

- `interfaces/perception/road/estimated_drive_paths.proto`, message
  `Adp.Perception.DrivePath`, is reported at schema version 2.2.0.
- The forward change appears in commit `ee7c462d7532` dated 2026-06-17, with
  rebased duplicates `a85c7fab5982`, `6561773a25cc`, and `c51c9f6b824f`.
- That change atomically moved major version 1 to 2, removed
  `use_amp_optional = true`, removed the
  `validity_field_name = "model_parameters_optional_flag"` binding, removed
  Boolean field 8, and changed the `model_parameters` description to say it is
  required.
- The legacy flag was reportedly introduced by commit `f56560ec2957` dated
  2025-12-08.
- `interfaces/README.md`, around lines 53--74, classifies field removal and a
  semantic-meaning change as major compatibility breaks.
- Field number 8 is not protected by either `reserved 8;` or a reserved field
  name. Nothing currently reuses it, but this is a latent wire-compatibility
  risk in the BMW interface rather than an MPR reason to accept future schemas.

### Producer validity semantics

- `domains/perception/road/drive_paths_estimation/graph_optimization/graph.cpp`,
  `Graph::GetEstimates()` around lines 1374--1395, reportedly assigns
  `drive_path.error` from the graph-node state and then populates
  `drive_path.model_parameters` unconditionally for every emitted node.
- `domains/perception/road/drive_paths_estimation/drive_paths_estimation.cpp`,
  `DrivePathsEstimation::FillOutput()` around line 655, reportedly serializes
  every estimate without filtering it by `error`.
- Consequently, schema-v2 model-parameter presence means available, not
  semantically valid. The only success state is exact equality to
  `DRIVE_PATH_ERROR_NO_ERROR = 7`; every other `DrivePathError` value is a
  failure state.
- `domains/perception/road/drive_paths_estimation/graph_optimization/
  graph_elements_factory.cpp`, `CreateClothoidSplineEstimationParameters()`
  around lines 29--35, reportedly requires at least two segment starts.

The source evidence therefore supports this generation-specific consumer rule:

```text
legacy v1 usable path := model_parameters explicitly present
                         AND model_parameters_optional_flag == true
                         AND error == DRIVE_PATH_ERROR_NO_ERROR
                         AND fixed structure/numeric checks pass

candidate v2 usable path := model_parameters explicitly present
                            AND error == DRIVE_PATH_ERROR_NO_ERROR
                            AND fixed structure/numeric checks pass
```

Absence of the legacy Boolean is not, by itself, sufficient to classify an
arbitrary future schema as v2. MPR must additionally require the exact reviewed
descriptor generation.

### Topology-source semantics

- `interfaces/perception/road/road_topology_source.proto` defines UNKNOWN,
  CROC, ODOMETRY, LANE_MAP, and SENSOR_TOPOLOGY. LANE_MAP denotes lane-map
  topology; SENSOR_TOPOLOGY denotes topology obtained from sensors.
- `domains/perception/road/drive_paths_estimation/scenario_classification.cpp`,
  `ScenarioClassification::Step()` and `DetermineMapGeometry()`, reportedly
  recomputes the source each cycle. In map-preferred mode it can switch with
  map availability and usable map horizon, so a source transition within one
  physical outing is legitimate producer behavior.
- `DrivePathsEstimation::FillOutput()` writes the selected source to each
  message. The field is therefore per-message evidence, not a fixed outing
  declaration.
- `lane_topology_ids` and `raw_lane_topology_ids` are reportedly populated only
  on the LANE_MAP branch.
- Copilot reported a component default of map-preferred mode and a
  `product2_init_values.json` override to sensor mode. The exact deployed
  configuration for the 2025-08-21 recording was not established.

These facts explain why both source values may legitimately appear, but they
do not alter MPR's prospectively fixed SENSOR_TOPOLOGY primary-cohort rule.

## Confirmed conclusions and unresolved points

Supported conclusions:

- the candidate files carry one consistent, newer EDP schema generation;
- removal of the Boolean accompanied an explicit required-field semantic and
  major-version change;
- v2 path validity still requires exact `error == NO_ERROR` and must not be
  inferred from parameter presence alone;
- the existing nested geometry fields and fixed structural checks remain
  applicable; and
- a narrow, exact-generation adapter can restore the intended technical audit
  without inspecting residual, feature, model, or planner outcomes.

Not established:

- no unsquashed design rationale or ADR for the schema change was found;
- whether field 8 was left unreserved deliberately or accidentally is unknown;
- the complete downstream-consumer population was not audited;
- the exact deployed topology-mode configuration is unknown; and
- accepting schema v2 does not establish that this outing passes topology,
  H100 pairing, six-input availability, frame-count, or sequence gates.

## Required continuation

1. Obtain focused independent review of
   `docs/independent_outing_schema_v2_amendment.md` at an exact Git commit.
2. Do not change decoder or eligibility code unless that review returns `GO`.
3. If approved, implement only the exact-generation validity adapter, tests,
   output lineage updates, and runbook command required by the amendment.
4. Re-run the same closed batch from the unchanged manifest bytes into a new
   empty v0.17.1 output directory. Never overwrite the v0.17.0 audit.
5. Independently verify and review the amended real audit before interpreting
   technical eligibility or acquiring outcome evidence.
