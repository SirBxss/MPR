# PR #30: recorded schemas and BMW source evidence

Date: 2026-10-04. This closes the first evidence request in the 2026-10-03
reference investigation. It is a documentation-only interpretation, not an
adopted reference, decoder, target amendment, payload audit or training result.
The complete next-action instructions are in
`reference_evidence_followup_runbook_20261004.md`.

## 1. Decision and exact stopping point

**Keep old runbook step 6 deferred.** The old readiness successor answers
SENSOR-only EDP/RLMB support, not the new pose/foresight semantic questions.
No successor payload run occurred in this evidence task. The original
ZstdError is unresolved; the later initial memory stop still has no report.

The pilot has recorded schema structures for EDP, RLMB, position-on-map pose,
ENU frames, lane geometry and MPP lane association. This is enough to specify
a bounded **native-structure** audit. It is not proof of valid geometry,
usable H100 pairs, covariance dimensions in messages or synchronized epochs.

The supplied BMW source trace reports that RLMB, map-preferred EDP,
localization and foresight share map/pose inputs and camera-related gates.
Rebuilding foresight with the same pose does not establish an independent or
more accurate lane reference. Do not adopt that replacement, average it with
RLMB as an independent observation, or use the pose covariance as a signed
correction. The recording's deployed behavior remains unverified.

Two research questions must remain distinct:

- **Operational map-relative disagreement:** all-topology EDP versus a
  declared map-and-pose-derived pseudo-reference, with topology-stratified
  reporting and explicit dependence limitations. This can be a defensible
  development target after its construction/population contract is reviewed.
- **Error relative to the physical lane/path:** requires independently
  justified reference observations or a validated joint-error model. The four
  topics alone do not supply that evidence. Independently accurate ego pose
  alone also does not establish accurate lane geometry or intended-path truth.

The owner's original goal is the second question. Do not quietly substitute
the first in the thesis or paper. Record an explicit scope decision before
new numeric extraction. No stronger scientific claim follows from more files.

## 2. Supplied evidence and independent checks

The owner supplied four files, completed old steps 1--5, left step 6 pending
and opened PR #30. Private attachments are not copied into the public repo.
Their exact SHA-256 identities are:

| File | SHA-256 |
|---|---|
| `MPR_PR30_docs_preflight_reference_review_cf2ae29.md` | `98009554e96d9a4baf1f6b05935aeb764678c4d138cb10646d202b676ac867cf` |
| `codex_7.txt` | `3fd9fc93ac1d4e719321819e94f8812cd5b8684546ddf0cd787420d7b4c31c79` |
| `recorded_metadata.json` | `8b797a3efc5866fc067cdd596610d4cc7ac3f6621e8bcea6d623fbafcb505c9a` |
| `copilot_session_23.txt` | `cd2c585c49ba679f948e1d89c962c324297b8a6a2110260952c2945076359dcc` |

PR #30 is open and unmerged at reviewed head
`cf2ae298835f154e3e597e746408dfd47e24238a`, tree
`ae8565dedaa2ccf0a8ba65c312eabebba3ed010c`, base
`fc6d5ff72c5812d43367897cc92416fd870e2686`. Claude gives **GO, zero blockers**
for its ten-file documentation-only diff. GitHub's synthetic merge SHA is not
evidence of an actual merge.

This session independently checked Actions run `37211254466` at that head:
Python 3.10 job `111462756848` and Python 3.12 job `111462756661` passed
installation, compilation and tests. Each reports **579 run, 577 pass,
two existing skips**, MCAP 1.5.0; test times 50.917 / 96.299 seconds.
This closes Claude's stated CI-verification limit for the original head.
A new documentation delta needs review/CI at its new pushed head.

The metadata JSON was read locally in full. All 38 descriptor entries were
checked for inventory/hash/size agreement, root-field equality, reported
message/field/enum counts, unique field names/numbers, reachable message graph
closure and resolved message/enum references. No external type references are
reported. Footer extent/group arithmetic is consistent. These are independent
checks of the returned report, not an independent read of the private MCAP.

The source dossier identifies only **`master@465073bc`**, dated 2026-08-05,
not a full immutable SHA, clean/dirty state or recording software build.
Its source-tagged claims and internal citations are **reported source evidence**:
the BMW checkout is unavailable here. The dossier's documented-intent,
inference and recording-unknown tags must not be promoted to facts proved by
the payload or independently rechecked private source. It reports writing a
short `/memories/repo/` note; no BMW source modification is reported. The
follow-up explicitly prohibits writing even such a note.

## 3. Pilot metadata: what the report actually establishes

Identity is one registered technical recording, `batch03_aws_pilot001` /
`pilot_001`, size **29,961,313,204 bytes**. The owner's stated 180 merged input
chunks do not become 180 physical drives or independent sessions.

| Preserved declaration | SHA-256 |
|---|---|
| Registration | `041f97ec85191b6770d73030256d5cd29b42b9fb53654565767aa23dfbe29f44` |
| Source specification | `c26e5a5556f574090ae8f8a498b60603d06070fea4816cd6633ba29a52a330e1` |
| Old inconclusive readiness JSON | `55ec8bde1ae22f54f05443ac1816bd85d508c9e605d69d7e712489c47f23d2a7` |
| Registered raw declaration | `a2fee0ef9d1150b72fba3e6a91bd3530ebb54e7e26902fdd9edad49ee2239d78` |

The local task checked the three small-file hashes and raw size/readability;
it did **not** freshly hash the 30 GB file. Resources were 12,509,716,480
bytes MemAvailable and 55,971,049,472 bytes scratch free. The task reports a
4 GiB hard/soft address-space cap, 128 MiB record ceiling and 300 s timeout.
The parser source itself was not supplied, so those execution claims are
supported by its transcript/report, not independently instrumented here.

The fixed 37-byte footer gives a 237,099,566-byte total summary extent,
including the 130-byte summary-offset table. Direct offset-group reads cover
13,073,909 bytes schemas, 34,007 channels and 5,115 statistics. The task skips
223,985,601 bytes chunk index and 804 bytes metadata index. Maximum reported
record-content lengths are 199,552 / 90 / 5,106 bytes respectively.
This is an observed bounded selection, not a new general whole-summary cap.

Overall summary: 506 channels, 448 schemas, one statistics record and
186,441,684 advertised messages across all topics. The report exports only
38 requested channel/schema rows, one per topic: three non-foresight primary
topics plus **35 foresight topics**, including the fourth primary topic.
The transcript's earlier progress line says 34 foresight channels; its final
result and JSON agree on 35. Use the JSON's validated inventory.

| Topic | Channel / schema | Root | Advertised count |
|---|---:|---|---:|
| `/adp/estimated_drive_paths` | 268 / 234 | `Adp.Perception.EstimatedDrivePaths` | 36,032 |
| `/adp/road_lane_map_based` | 405 / 195 | `Adp.Perception.Road` | 36,032 |
| `/adp/position_on_map_pose_estimate` | 389 / 341 | `Adp.Localization.PositionOnMap.PoseEstimateFrame` | 36,032 |
| `/adp/foresight_lane_data_opb` | 461 / 404 | `Adp.Map.ForesightLaneData` | 3,602 |
| `/adp/foresight_projection_enu_coord_frame` | 476 / 419 | `Adp.Map.EnuCoordFrame` | 3,602 |
| `/adp/foresight_most_probable_path_best_lanes` | 274 / 238 | `Adp.Map.BestLanesMostProbablePath` | 36,032 |
| `/adp/foresight_most_probable_path_lanes_on_links` | 275 / 239 | `Adp.Map.LanesOnLinksMostProbablePath` | 36,032 |

The primary descriptor byte-blob hashes, in table order for the first four:

- EDP: `be938af63816f7d1eee22d804d84b11d615d4644135aba389d25ee7bda323e26`.
- RLMB: `26d8f11e27ff997615c438eb407fec4b6e26dd5b459ac20ba941ede5e9c6abf3`.
- Pose: `b3c8838ea16fad6121412f1cb87647cbf40185c861756a896126c2eff231dbb7`.
- Lane data: `d8cfa22a8b3c70b82ea7c8faa89c05b72738776bf7a719a9baefd288b81a833c`.

Nonzero summary CRC is advertised but **not recomputed**; descriptor byte
blobs are omitted. Advertised counts are not decoded-valid counts, H100
support, covariance support, sustained rates, duration or physical sync.
Equal EDP/RLMB/pose counts prove none of these. Payload readability and the
old ZstdError remain unresolved. The report's `v0.19.8` is an ad hoc evidence
label, not an implemented/released MPR CLI or changed package version.

The 35 foresight topics cover behavior data, HPL map, landmarks, lane data,
map-matched route, four MPP topics, thirteen nearby-attribute topics, ENU,
two road-link frames and ten route topics. Full names/types/hashes remain
in the private JSON. Map-matched route advertises only **one** message; do
not assume navigation-route availability. The three MPP association streams
advertise 36,032 each; MPP visualization advertises 109,191. No claim about
its usable contents follows. This selected report is not a complete 506-topic
inventory of possible build/configuration/ground-truth/morphing topics.

## 4. Recorded structures versus current source claims

| Recorded descriptor evidence | Reported source interpretation | Remaining limit |
|---|---|---|
| EDP root fields 1--6; topology enum UNKNOWN=0, CROC=1, ODOMETRY=2, LANE_MAP=3, SENSOR=4; `DrivePath.error` NO_ERROR=7 and KEEP_LANE role=1 | MapPreferred mode and camera validation choose map paths; source may move graph geometry with odometry | No per-message topology distribution, physical epoch or deployed calibration |
| `DrivePath` has 1--7, 9--11, no field 8; clothoid has `x_0`, `y_0`, `theta_0`, `segment_starts`, `index_0` | Field 8 reportedly removed 2025-11-28; native origin is first segment start | Structural compatibility is not producer-version identification; never assume native s=0 is ego |
| RLMB segment id is uint64; signed range `start/size`; x/y/heading/curvature wrappers exist | Map centreline converted by rear-axle position and yaw; x/y mean written, stddev/heading/curvature reportedly unset | Presence and actual finite values need payload inspection; unset stddev is not zero uncertainty |
| Pose fields 1--8 include ENU id, pose, repeated-double covariance, sensor input and reset status | Mean rear-axle pose; yaw degrees CCW from East; covariance writer differs from proto comments | A repeated field does not prove 36 values, row-major layout, basis, calibration or mode |
| Pose `reset_status` field 8 present | Field reportedly added 2026-03-17 | Not an acquisition-date/build lower bound: replay/export/schema embedding can differ |
| Lane data has projection id, ENU point pools, lane ids, centreline IndexRange, connectivity, boundaries and map-version counter | Map lane geometry in projection ENU; offsets relative to lane/link features, not a global ego horizon | Pool validity, IndexRange endpoint convention, lane selection/direction/length and frame history unproved |
| ENU id uint32, origin, repeated rotation/translation-from-previous | Frame id reportedly hashes origin; lane proto's monotonic-id comment conflicts with implementation | Compare identity by equality only after binding is verified; no ordering or automatic transform-chain inference |
| MPP best lanes has ids/ranges, qualifiers/status, map counter, but no root timestamp; lanes-on-links also lacks root timestamp | MPP lane association rather than independent sensed geometry | Correlation-id semantics, validity intervals, reset/replay behavior and causal availability need tracing |

`Adp.Map.IndexRange` is `first`, `last`, `is_valid`, `has_value`, all optional;
it is not RLMB's signed `start/size`. `ProjectionId.id` is uint32 and
`LaneId.id` uint64. Respect nested presence/validity flags; do not silently
interpret absent optional scalars as valid zero. The report does not include
custom proto-option maxima or an independently compiled descriptor bundle.

## 5. Dependency, geometry and epoch findings

These are **reported source findings** from dossier sections 2--9, not direct
recording facts. Source/config history and actual deployment remain important.

- Map-preferred EDP receives LTMB derived from RLMB; the branch is reportedly
  gated by camera/map agreement, horizon and scenario validation. SENSOR can
  reportedly include a usable map road layer visible only in debug. A SENSOR
  enum alone therefore does not prove independent sensor geometry.
- RLMB and localization reportedly share the HD lane map/provider; map
  projection/ROI, MPP and localization have feedback dependencies. RLMB may
  apply a sensor-derived space-morphing grid. It is not established that raw
  foresight reconstruction is an improvement over RLMB; it could discard that
  correction. Actual morphing flags/grid and calibration are unknown.
- RLMB reportedly re-expresses pose in the lane-data ENU frame using retained
  origin history, then uses a 2-D translation and yaw. EDP and RLMB are already
  ego-relative in that implementation. Applying pose again is a double
  transform. Full 6-DoF conversion would be a changed method, not automatic
  equivalence to this 2-D producer.
- Multiple drivable localization candidates can reportedly be marked ego
  lanes while their probabilities are ignored. MPP denotes likely/intended
  route association, not independently verified actual ego lane. Do not pick
  the closest lane to EDP or invent tie-breaking/branch interpolation.
- RLMB stamps current processing clock; LTMB copies it; LANE_MAP EDP copies
  LTMB's stamp. EDP graph geometry can have a later odometry compensation
  epoch. Lane/behavior data can be restamped every publish while held content
  is unchanged. ENU publication stamps need not denote measurement time.
- Pose reportedly predicts a delayed filter state forward to latest odometry
  time. The reported 200 ms is a producer setting, **not** an authorized fixed
  offset correction. Recorder log/publish times reportedly both use receive
  time in one writer; the actual recording's writer/clock is unknown.
- Historical changes include RLMB input handling in May 2026 and selection
  changes in July 2026. Current source defaults/calibration snapshot cannot
  establish this pilot's software, map release, replay or configuration.

Future auditing must distinguish event/header stamps, receive stamps,
content changes and geometry validity epochs. Equal stamps can result from
copying, not physical alignment. Causal lane/frame association requires held
content/history with no use of future frame records. Source-only evidence
does not certify that rule can be satisfied by this recording.

## 6. Covariance: narrower use than initially hypothesized

The dossier traces a writer instead of relying on the proto comment:

- HPL output reportedly copies 36 row-major entries in East/North/Up and
  three **rotation-vector** state components, position units m and rotation
  units rad. This conflicts with the interface's vehicle-aligned/Euler intent.
- GNSS fallback reportedly instead fills along-track variance at index 0,
  cross-track variance at 7 and heading variance at 35, others zero. Zero
  entries are not proof of perfectly known remaining degrees of freedom.
  Unavailable qualifier reportedly clears the array rather than zero-filling.
- Published mean yaw can receive a camera heading-bias correction while
  covariance reportedly does not. Validity during convergence and possible
  mean/covariance mode mismatches also need investigation.
- The trace finds KPI error checks against ASTAS ground truth but no NEES/NIS
  consistency test in its search. This is a search result, not proof that
  calibration evidence cannot exist elsewhere. Map error and cross-covariance
  are not supplied by the located writer/interface.

Do not universally interpret index 7 as vehicle lateral variance or index 35
as exact Euler-yaw variance, rotate a global matrix using a proto comment, or
assume status/sensor/reset fields uniquely identify the writer branch. A
verified mode discriminator is still needed; unknown mode stays unknown.
The rotation-vector-to-pose perturbation Jacobian and covariance about the
actually published mean also remain unresolved. Mean yaw degrees and angular
covariance radian units must never be combined without explicit conversion.

Native inspection may count array lengths, qualifier/status combinations,
missing/nonfinite entries and raw numerical matrix properties. Even a finite,
symmetric PSD 36-array is not proof of a calibrated reference uncertainty.
Pose covariance cannot encode discrete wrong-lane choices or all reference
errors. Shared EDP/reference map/pose errors can cancel; subtracting this
matrix from empirical residual covariance does not identify estimator error.
Propagation remains deferred. The earlier illustrative straight-path math
is not a BMW observation model. Anchor/coverage selection can also change
under perturbation and is not captured by a local Jacobian.

## 7. Claude findings and their disposition

- **N1:** document both resource-check outcomes: initial exit 2/no report;
  post-hash resource failure exit 3/inconclusive report with null observations.
  Neither proves bad data. Preserve any later report and review a fresh path
  before another attempt; the old predecessor gate accepts only ZstdError.
- **N2:** replace recovery `assert` gates with explicit checks, including
  identity, scratch type/emptiness, dangling symlinks and resources, so
  `PYTHONOPTIMIZE` cannot bypass them. Improve regular-file error wording.
- **N3:** reviewer reports prior PR #29 delta-review SHA
  `207ec2537c92112d2639957494650b873dbbd8e22fbf072a0841cc040737b07b`.
  Those review bytes were not supplied here; this is reviewer-reported identity.
  PR #29 CI was independently checked separately.
- **N4:** 95.1% LANE_MAP in old anchored candidates is selected conditional on
  usable map-based RLMB. It is not the map-use rate of the drive. Require
  source-stratified counts/attrition, including unpaired/rejected frames, in
  a future all-topology study.
- **N5/N6:** document perturbation-dependent anchor/H100 censoring and require
  prediction-time availability for any new feature. Existing reference-side
  RLMB exclusion and the frozen six-feature schema remain unchanged.
- **N7:** old metadata inspection already read a summary under the 4 GiB cap;
  this new task adds exact group-size evidence and a smaller direct read.
- **N8:** original branch-creation ordering is historical; the new delivery
  verifies its bundle before updating the already open PR branch.

## 8. Next work and unchanged gates

Close this evidence in **the same PR #30**, get delta GO and new-head CI, then
merge. No new PR is needed for the documentation closure. The follow-up
source prompt is self-contained for BMW Copilot and can run in parallel with
a local metadata-only provenance search; neither depends on old step 6.

Next implementation: a reviewed, bounded native-field structural audit,
using the existing identity/CRC/storage reader architecture, exact schema
binding and fresh versioned outputs. Its draft scope is in
`reference_native_structure_audit_proposal_20261004.md`. It can measure native
availability even when deployed source or covariance meaning is unknown;
those unknowns block physical transformations/propagation and stronger claims,
not honest counting. Do not repeatedly ask for evidence that cannot be found.

Before all-topology residual export choose the target/reference, establish
geometric epochs/frames and an EDP-independent lane-selection rule, and
version the construction and population. Validate complete conditions and
causal sequences before fitting. Both flow modes remain synthetic-only.
Old/new comparison separates data, target and model changes; use common
evaluation rows where appropriate, train-only transforms and physical-session
held-out groups. More downloads should be selected for confirmed topic/build/
session/reference support, not volume. No raw deletion or final-data role is
opened by this evidence. Preserve historical SENSOR outputs unchanged.
