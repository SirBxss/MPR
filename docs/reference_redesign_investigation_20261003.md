# Prospective all-topology EDP and reference investigation

**2026-10-04 evidence update:** the first source/recorded-schema inquiry has
returned; read `reference_evidence_reconciliation_20261004.md`. Reported source
dependence and mode-dependent covariance narrow the feasible interpretation.
This original proposal is not an adopted reference or covariance model.

Date: 2026-10-03. Status: evidence-acquisition and methodological discussion,
**not an adopted new residual target, reference, extractor or feature schema**.
MPR remains the canonical thesis implementation. This record supersedes the
old critical-path instruction to pursue only more SENSOR-labelled EDP for the
next development study; it does not amend historical contracts or outputs.

## 1. New owner/road-team information

The owner reports that the road team explained EDP's map preference: when
usable map information is available, its selected topology generally switches
to LANE_MAP; map availability is around 90% in their experience. Consequently,
trying to obtain a large SENSOR-only EDP population is unlikely to be an
efficient primary acquisition strategy. This is a dated, attributed verbal
report. The exact producer revision, configuration, physical sessions and
percentage in the new pilot have not been verified. It is not a measured
90% MCAP statistic or a universal guarantee about every deployed EDP version.

The owner's proposed direction is to consider EDP across topology sources,
then investigate improving/replacing RLMB using:

- `/adp/position_on_map_pose_estimate`, reportedly including a 6 x 6 covariance;
- `/adp/foresight_lane_data_opb`, reportedly containing useful information;
- other `/adp/foresight` topics once their exact recorded names are inventoried.

The owner explicitly says these reference ideas are **not fixed**. Record the
decision as prioritizing an all-topology/reference feasibility study, not as
accepting an unverified reference or blindly exporting every message. No BMW
source or recorded schema for these new topics is available to this agent.

## 2. What existing evidence already establishes

`bmw_edp_schema_evidence.md` records a previous read-only BMW source trace:
`ScenarioClassification::Step()` / `DetermineMapGeometry()` recompute the
source per cycle and can switch with map availability and usable horizon.
`DrivePathsEstimation::FillOutput()` publishes that source. Map-preferred
defaults and a sensor-mode product override were reported; the actual recorded
configuration was not established. This supports the mechanism behind the
road-team report without proving its numeric prevalence in the new file.

The completed batch02 pilot has the following **geometrically anchored H100**
population, before any all-topology condition/export validation:

| Population | Count | Interpretation |
|---|---:|---|
| All anchored EDP/RLMB H100 candidates | 7,743 | Previously counted by the geometry audit |
| SENSOR_TOPOLOGY candidates | 376 | 4.9% of those candidates |
| LANE_MAP candidates | 7,367 | 95.1% of those candidates |
| Exported historical SENSOR residual profiles | 376 | Reviewed v0.19.2 pseudo-target only |
| Historical complete six-feature rows | 134 | 26 short sequences, longest ten frames |

The 95.1% is conditional on the anchored-candidate population, not the fraction
of all EDP messages, map availability or physical drive duration. These old
geometry counts show the potential gain in coverage. They do not establish
7,743 training rows, longer causal sequences or a trustworthy new reference.
The new 30 GB batch03 pilot has no completed decoded readiness result.

The current new-data reference is **`/adp/road_lane_map_based` (RLMB)**. It is
distinct from the older `/em/road/ego_lane_path` fusion discussion and from
`/adp/lane_topology_map_based`. Avoid treating these names as synonyms.
RLMB remains a pseudo-reference, not physical ground truth. Existing LTSB
source traces also establish map influence in topology selection, so merely
switching to a topic with “sensor” in its name would not establish independence.

## 3. Present implementation versus proposed study

The existing streaming geometry audit already counts multiple EDP sources.
`io.recording_pair_feasibility._count_geometry` reports all anchored H100
geometry and separate SENSOR/LANE_MAP populations. The reviewed numeric
extractor/readiness support path is narrower: `io.exploratory_residuals._scan_stream`
retains estimator inputs only for `EXPECTED_TOPOLOGY_SOURCE`, and its
`on_sensor_pair` callback receives SENSOR-only candidates. Changing a single
filter would therefore be insufficient: candidate identity, condition support,
counts/parity, sequence breaks and archive target metadata would also change.

For the prospective study, topology is a provenance/regime variable rather
than the sole estimate admission rule. Keep exact descriptors, valid keep-lane
role/no-error state, finite geometry, common H100 support, unambiguous ego
binding, timestamps and causal-feature checks. “All points” means eligible
path profiles from the declared source population, not every vertex, error
message, UNKNOWN enum or unsupported schema. Inventory every source identity,
including UNKNOWN/unrecognized values, without silently labeling them SENSOR
or MAP; their numeric admission needs explicit semantic evidence.

Keep source-switch boundaries visible. Whether temporal sequences can span
them must be predeclared after producer semantics are understood; a change in
source is not an independently recorded physical drive. Existing 21-station
sign and no-extrapolation rules are retained unless a separately justified
target definition changes them. Historical archives/models must not be pooled
with a changed reference or population under their old target identifier.

No real fit, feature addition, final-outing admission or relaxed old gate is
implemented by this documentation. The new direction may lead to a separately
versioned development contract and, later, a supervisor-visible revision of
the final-data protocol. Inspected pilot data remain development evidence.

## 4. What the proposed topics might contribute

| Candidate | Owner-reported evidence | Plausible use, conditional on source/schema checks | Not established |
|---|---|---|---|
| Position-on-map pose estimate | 6 x 6 covariance | Pose/frame registration; quantify the localization contribution to reference uncertainty | Mean pose fields, matrix semantics, calibration, map error, independence, availability |
| Foresight lane data OPB | Useful information | Candidate lane geometry or constraints if actually encoded | OPB meaning, centreline/boundaries, ego lane vs planned route, horizon, frames, independent source |
| Other foresight topics | Topic family exists per owner | Route/link/lane association and auxiliary quality evidence | Exact names, recorded presence, usable geometry or ordering |
| Existing RLMB | Reviewed converter and observed EDP pairing | Baseline pseudo-reference for an outcome-blind comparison | Independent road truth or inferiority to a new candidate |

Covariance describes uncertainty around a specified estimate; it does not
supply a signed pose correction or a road centreline by itself. Even a pose
mean only registers map geometry into a vehicle frame. It cannot repair a
wrong map shape or lane association without another source of evidence.
An informative foresight attribute stream might help selection/quality while
containing no reconstructible path. More fields are not evidence of accuracy.

Before interpreting the 6 x 6 matrix, establish its field layout, parameter
ordering, units, coordinate basis, pose origin, rotation/error-state convention,
and whether it is covariance, information or a packed matrix. Inspect validity,
sentinel/zero semantics, conditioning, which uncertainty sources are excluded,
and whether it is a covariance conditional on an already chosen map lane.
Check finite entries, shape, symmetry and PSD with declared numerical
tolerances; do not silently repair a matrix or treat all-zero as perfect
localization. A common ROS pose message has a particular six-coordinate
ordering, but that is **not evidence of this BMW message's ordering**.

## 5. The dependence question must come before fusion

Trace the actual producer-to-consumer graph for EDP in each topology regime,
RLMB, position-on-map and foresight. Establish whether they share the same
HD-map geometry/version, localization/map match, route/MPP, camera tracking,
odometry or EDP output. Inspect caching, map overrides, feedback and prediction.
No such edges for the new topics are confirmed here.

If EDP and the candidate reference share map or localization errors, their
disagreement can be small while both are wrong relative to the road. For
vectors aligned to a common physical target, the error difference is

\[
d=e_E-e_R,\qquad
\operatorname{Cov}(d)=\Sigma_E+\Sigma_R-C_{ER}-C_{ER}^{\mathsf T}.
\]

This is a covariance identity, not an adopted BMW observation model. Shared
errors can cancel; reference noise can also inflate disagreement. Unknown
cross-covariance prevents isolating estimator error by subtracting a pose
covariance from empirical residual covariance. The pose matrix is only one
possible part of reference error, not the full \(\Sigma_R\).

Averaging two map-derived paths as if independent risks double-counting
information. Applying a position-on-map transform to RLMB that already uses
the same pose risks applying the correction twice. Selecting the reference
closest to EDP minimizes disagreement by construction and is not independent
validation. These are hypotheses to check with source evidence, not findings
that the new topics definitely share those dependencies.

If independence cannot be established, an explicitly scoped all-topology
**EDP-to-reference disagreement** study can still be useful. It must not claim
the distribution of EDP error relative to the physical lane. A stronger
accuracy claim needs a separately justified independent reference/measurement
or a validated joint-error model; covariance alone does not create either.

## 6. How pose uncertainty could affect H100

The general first-order propagation is \(\Sigma_y\approx J\Sigma_xJ^\mathsf T\),
using a Jacobian and covariance defined in consistent perturbation frames.
Solà, Deray and Atchuthan, *A micro Lie theory for state estimation in robotics*,
section II-H, equations 51--55, provides this general mathematical background:
<https://arxiv.org/abs/1812.01537>. This is not evidence for the BMW schema.

As an **illustrative straight, planar, fixed-correspondence approximation**,
let lateral registration perturbation be \(\delta b\) metres and small relative
heading perturbation be \(\delta\psi\) radians, with signs defined so that
\(\delta d(s)=\delta b+s\delta\psi\). Then

\[
\operatorname{Var}[\delta d(s)]
=P_{bb}+2sP_{b\psi}+s^2P_{\psi\psi},
\]

\[
\operatorname{Cov}[\delta d(s_i),\delta d(s_j)]
=P_{bb}+(s_i+s_j)P_{b\psi}+s_is_jP_{\psi\psi}.
\]

For illustration, 0.1 degree heading standard deviation alone gives about
0.175 m lateral standard deviation at 100 m. These are two correlated modes,
not 21 independent station noises. No numeric BMW covariance was inspected.
Relative-pose uncertainty can differ from absolute pose uncertainty; a shared
transformation of both paths can cancel in their disagreement.

For actual curved H100 profiles, derive the Jacobian of the **complete**
alignment/resampling operation: physical frame conversion, estimate ego
footpoint, reference projection/anchor station, station sampling and changing
reference normals. Retain common longitudinal support without extrapolation.
Small perturbations can change the nearest branch or lane identity, where a
single local Gaussian/Jacobian approximation becomes unsuitable. A 6 x 6
continuous pose covariance does not encode a multimodal lane-choice error.
Perturbations can also move candidates across the <= 1 m anchor and H100
coverage gates. That censoring/selection change is not captured by a local
Jacobian on the already accepted population; report gate stability separately.
Plan synthetic finite-difference and perturbation-draw checks on stable
correspondences before any private covariance propagation is implemented.

## 7. Evidence to acquire first

Use the complete read-only BMW source prompt in
`reference_redesign_runbook_20261003.md`. Its first deliverable is a technical
evidence dossier with:

1. Literal BMW checkout commit SHA/dirty state and producer version/config
   applicability; complete paths, symbols and line references for every claim.
2. Exact topic bindings and Protobuf roots/dependencies, field numbers/types,
   enums, covariance semantics, geometry representations, validity and limits.
3. Provenance graph and whether candidate information is already in RLMB/EDP.
4. Frames, origins, axes, units and native longitudinal definitions; route/ego
   lane binding, successor ambiguity, merge/split and lane-change behavior.
5. Measurement, validity, prediction, publish and recording epochs, age,
   transform direction, caching and config-dependent timestamp behavior.
6. Historical schema/producer changes relevant to the recording generation;
   current source alone cannot prove what produced a historical MCAP.
7. Available MCAP-embedded descriptor/topic evidence, obtained initially from
   summary metadata only where technically possible, with bounded resources.
   No fallback that scans the full file or retains all payloads automatically.

Technical source/schema metadata stay inside the authorized BMW research
workflow. Public repository docs contain the attributable conclusions and
evidence identities, not copied proprietary source, coordinates, exact
recording epochs, internal URLs or raw descriptors.

After the source dossier, separately design a bounded structural/quality audit
on the preserved development pilot. It must inventory actual message presence,
valid geometry, ambiguity, horizons, timestamp/age support, covariance validity
and candidate source regimes without computing residuals or choosing a winner
by closeness to EDP. If a source cannot provide geometry or common frame/epoch
support, document that limitation before considering fusion.

## 8. Decisions after evidence, not before

| Evidence outcome | Scientifically defensible next step |
|---|---|
| Covariance is interpretable but no new geometry exists | Quantify a reference-uncertainty component in a separately specified diagnostic; do not call it a better path |
| Foresight reproduces RLMB geometry/pose | Treat as a related representation or auxiliary quality stream; do not fuse as independent evidence |
| New geometry has supported frames/epochs and distinct useful information | Specify a candidate-reference construction and validate it against evidence external to EDP closeness |
| Useful reference is map/EDP-dependent | Retain a declared pseudo-reference/disagreement target with shared-error limitations and regime reporting |
| Independent reference evidence exists | Review an error-target contract, uncertainty budget and outcome-blind validation protocol |
| Frames, epochs, lane binding or covariance semantics remain unresolved | Acquire the specific missing evidence; do not invent transforms, thresholds or labels |

The next implementation should therefore be a small reviewed evidence adapter
or structural audit **after exact recorded schemas and producer semantics are
known**, not an immediate filter removal/fusion/model fit. A generic pipeline
can reuse declaration, identity hashing, bounded readers, spooling and artifact
validation; topic-specific semantic bindings and scientific target contracts
still require evidence. “Generic” cannot mean arbitrary MCAPs automatically
become defensible labels.

Once the new target/reference is accepted: version the exporter and condition
schema if needed, validate an immutable archive, predeclare matched old/new
comparisons and physical-session splits, then fit Gaussian/AR/AIOHMM and both
flow modes on comparable rows. Target changes confound a raw old-vs-new score
comparison; explicitly separate population, reference and model changes.
Pose covariance or topology as prediction features require a separate
causal-availability and feature-schema decision. The current six features
remain frozen; reference-derived quality is not automatically a model input.

The paper deadline reported by the owner is the end of October 2026. Prioritize
reference validity and a precise claim over speculative fusion or repeated
private scans. This document is the resumption point for later agents.
