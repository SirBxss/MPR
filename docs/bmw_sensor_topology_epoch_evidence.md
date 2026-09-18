# LTSB upstream processing and timestamp evidence update

Date: 2026-09-18. Status: implementer assessment of the received source trace;
focused independent review of this interpretation correction is pending.
No executable change, private rerun or new target is proposed.

## Identity and evidence strength

The private input is `copilot_session_22.txt`, SHA-256
`f9f16bec168197ee489ced8f4f4d7f29e48f202834e5acbc9e21aed716f11565`.
Preserve the complete transcript unchanged outside Git. Its inline report is
headed `MPR_post_v0181_source_acquisition_evidence.md`; that heading does not
denote a separately supplied file with a separately verified hash.

Copilot reports BMW HEAD `465073bc593195eee0e4eada0a1389943e006a2b`, branch
`master`, and a clean worktree at the initial check. MPR cannot independently
inspect that private repository. Treat the findings as **Copilot-reported
source/configuration evidence at the named checkout**, not verified facts
about the software used for the August 2025 recording.

The transcript improves the earlier missing-HEAD limitation, but its claim
that all reads used immutable HEAD blobs is stronger than its visible
commands. Many reads use editor searches, `sed`, ordinary `git grep` or
Python file reads from the worktree. The initial clean-state report helps,
but no final clean-state check or full raw source output is supplied. The
report abbreviates several new paths and supplies shortened blob IDs for
the original entry points, not a complete immutable evidence package for
the newly traced LMSB files. Do not upgrade this into independent source
reproduction. This limitation does not require repeating the broad inquiry
before withdrawing an unsupported unconditional timestamp claim.

The user's pushed MPR branch was verified at
`3f894efce9af19f781003b30ea742ad9c0bb6226`, tree
`9457ad603ffc898bdcb1c985e1b1cdc69ef5bbe5`. It matches the delivered
source/acquisition decision record and has no executable delta from merged
`main` at `1403927`. No open PR was found at this checkpoint.

## Material findings and bounded interpretation

| Reported finding | What MPR can conclude | What remains unknown |
|---|---|---|
| LTSB copies `LaneMarkingsSensorBasedOutput.timestamp` | The upstream LMSB mode matters; LTSB is not unconditionally timestamped at raw camera measurement time | The mode and effective timestamp semantics used in batch01 |
| LMSB tracking mode (`lmsb_camera_pipethrough_enabled = 0`) predicts geometry and assigns an odometry timestamp | Camera-derived geometry can already be processed and ego-motion propagated before LTSB copies it | Whether this mode was deployed in the recording and the exact historical implementation |
| Pipethrough mode copies camera coordinates/header time; timestamp rewriting is also reported | Even the camera-header branch does not establish an untouched measurement time without checking override behavior | Override enablement, sign, placement in the call chain and recording applicability |
| A cutoff uses `max(cutoff_min_distance, v_lon * cutoff_time_distance)` on vertex x; reported settings are 61 m and 2500 ms with cutoff enabled | A concrete producer mechanism could truncate geometry; it is a hypothesis for the closed batch | Active settings, per-message application and its effect on the accepted span counts |
| Per-boundary clipping and local arc-length zeroing are reported | Equal normalized fractions need not be common physical cross-sections when supports differ | Actual mismatch or systematic bias in batch01; an appropriate physical correspondence rule |
| Map inputs affect geometry selection and `segment_length_`; odometry can affect propagated coordinates | CAMERA tags do not imply raw, map-independent or unpropagated measurements | Statistical dependence of estimate/reference errors and the deployed processing mode |
| LTSB origin/axes remain undocumented; RLMB rear-axle origin is reported | Physical alignment remains blocked | A justified transform, including rotation, translation and epoch handling |

The core timestamp trace points to
`domains/perception/road_sensor_based/lane_markings_sensor_based/lane_markings_sensor_based.cpp`
(reported branch at 509--524, prediction/output at 636--645), its sibling
`pipethrough_converter.cpp`, and
`domains/perception/road_sensor_based/lane_topology_sensor_based/lane_topology_sensor_based.cpp`
(reported assignment at 1097). These are source-report citations, not source
files available in this MPR checkout.

The reported default/checked-in values come from
`domains/perception/road_sensor_based/lane_markings_sensor_based/parameters/lane_markings_sensor_based_parameters.json`
and, where stated, `verification/configuration/creta_parameters/creta_perf_parameters.json`:

| Parameter | Value reported in inspected files | Recording value |
|---|---|---|
| `lmsb_camera_pipethrough_enabled` | 0 | unknown |
| `lmsb_cutoff_boundaries_enabled` | 1 | unknown |
| `lmsb_cutoff_min_distance` | 61.0 m | unknown |
| `lmsb_cutoff_time_distance` | 2500 ms | unknown |
| `lmsb_camera_timestamp_override_enabled` | 1 | unknown |
| `lmsb_camera_timestamp_override_offset_to_odometry_timestamp` | 80 ms; sign/application not established here | unknown |
| `lmsb_camera_extrapolation_threshold` | 25.0 m | unknown |
| `lmsb_lane_marking_tracker_max_prediction_cycles` | 6 cycles | unknown |

The transcript's phrase "resolved override" establishes at most a reported
value in a checked-in file. It does not establish the recording's effective
parameter resolution or that the cited set was deployed. No parameter from
this table is added to MPR configuration or used to shift timestamps.

## Qualifications to the transcript

- `40 m/s = 144 km/h` is the algebraic speed at which the reported cutoff
  position reaches x = 100 m when the formula is active. It is **not** a
  necessary speed for 100 m accumulated geometric span. Curvature, geometry
  behind x = 0 and later processing distinguish these quantities. It is not
  an acquisition recommendation, a speed observation or a proven cause of
  the batch01 failure. The report's claimed explanation of span variability
  is likewise unverified; the artifacts export no numeric spans.
- The pipethrough copy and limited negative transform search cannot establish
  that the complete upstream path never transforms geometry. The same
  report describes odometry propagation in another branch. Nor do vertex
  count limits alone establish a distance limit or observed pool exhaustion.
- Unequal supports permit correspondence error; they do not prove that all
  normalized-fraction midpoints are wrong or statistically biased. Retain
  the accepted recipe as a structural diagnostic, not a residual target.
- Unknown frame origin does not prove a nonzero constant residual offset.
  Rotation, translation and epoch mismatch remain unresolved; their effect
  need not be constant along a curved path.
- Missing per-vertex measurement time limits reconstruction of original
  measurements. It does not by itself make rigid motion compensation of
  geometry at a known output epoch impossible. A cycle count reported on
  LMSB is not established as available on recorded LTSB. Decide which
  processed estimate is the target before defining age/compensation rules.
- Existing MPR already explicitly rejects LTSB/RLMB independence claims.
  There is no independence claim to newly withdraw. The new report strengthens
  the processing/dependency caveat and corrects the unconditional time claim.
- The suggested private `CalculateArcLengthBehindEgo` indexing defect is
  unverified. The MPR sensor audit recomputes length from coordinates and
  does not consume that producer-derived quantity. It is not evidence for
  a new MPR patch or for the cause of zero spans.

## Effect on the completed audit

The implementation extracts field 5 and pairs strict streams numerically
with the reviewed mutual-nearest algorithm and 50 ms threshold. It does not
read an LMSB mode, subtract 80 ms, reverse propagation or use sensor
`segment_length_` as measured span. The source report establishes no new
decoder or arithmetic defect in that implementation.

Preserve the 17,087 count as **numeric embedded-header timestamp pairs**.
It does not establish equal measurement age, a known common physical epoch,
independent observations or motion-aligned geometry. The old blanket
"camera lane-marking validity time" and physical "nearby validity times"
interpretations are withdrawn pending recording-applicable evidence.
The original prospective assumption and this later correction must remain
distinguishable; see the dated addendum in the predeclaration.

The 4,039 valid chains, zero 100 m spans, 9,235 reference-ready messages and
zero synchronized structural candidates are unchanged. The sensor-side
zero is sufficient for that structural negative independently of the epoch
interpretation. No sample is recovered, discarded or relabelled by this
documentation correction. Original output names, hashes, machine fields and
review reports remain immutable; `camera-derived` must not be read as raw
camera-only processing. Existing review GOs cover their original trees, not
automatic acceptance of this later semantic correction.

## Next evidence and implementation gate

The next request is narrower than another general source trace:

1. Recover an authoritative link from the one recorded physical session to
   its actual software build, effective parameter set and overrides, using
   already available recording sidecars/session metadata or the data owner's
   build/configuration record. A filename, date, matching descriptor or
   current source default is insufficient. Include the parameters above,
   actual units, provenance and unknown entries rather than filling defaults.
2. Obtain the applicable camera-output frame/calibration specification and
   processing-mode epoch convention. Prefer an existing specification or
   responsible producer's evidence over another broad keyword search.
   This remains a separate gap even if the recording configuration is found.

These read-only evidence requests may proceed while the documentation
correction is reviewed. They do not authorize MCAP payload inspection,
metadata extraction code, a private replay, a horizon sweep or acquisition.
If the historical identity cannot be recovered, record it as unknown and
keep batch01 closed; do not make future progress depend indefinitely on it.
A future pilot can instead bind its own build/configuration and semantics
prospectively, under a new reviewed scope, without explaining this batch.

Once recording-applicable or prospectively applicable evidence is supplied,
select the smallest supported change using
`docs/sensor_topology_source_acquisition_decision.md`. A processed lane
estimate is not inherently an invalid modeling target, but its definition,
reference dependencies, physical station construction and validation scope
must be explicit before implementing residual extraction.
