# Generic pipeline: completed stages and precise continuation

Date: 2026-10-09. Read `recording_decode_check_batch03_v0199_result.md` first.
This is a continuation plan and acquisition/storage estimate, not a frozen
new executable contract, changed population rule or private-run command.

## What is reusable today

| Stage | Implemented scope | Pilot evidence / remaining limit |
|---|---|---|
| Prepare/register (v0.19.6) | Explicit new-file source declarations, immutable raw identities and registration | Existing pilot registered once; no session identity invented |
| Inventory (v0.19.8) | Fresh raw verification, bounded all-summary topics/schemas/counts/index aggregates and available summary CRC | Pilot complete; counts here are advertised metadata |
| Decode check (v0.19.9) | Explicit selected indexed Protobuf streams, disk-backed scalar indexes, bounded chunks/codecs, selected CRCs and count reconciliation | Pilot complete: 181,255 decoded messages; payloads discarded |
| Semantic/geometry readiness | Existing generic v0.19.6 audit and pinned batch02 scientific consumers exist | Old large-file readiness failed; reviewed disk-index decoder is not yet connected to a new generic scientific consumer |
| Numeric archive | Pinned batch02 extraction/strict read-only archive validator exist | No generic exporter for arbitrary registrations yet |
| Model execution | Classic within-outing comparisons; both flow modes synthetically verified | No new-pilot real fit or matched old/new comparison |
| Raw retirement/retrieval | Evidence fields and gates documented | No tested generic retirement mechanism; pilot retrieval evidence absent |

A new MCAP does not require starting the whole research project again.
Declare/register it under its own batch/recording identity, inventory it and
explicitly decode the desired streams through the supported generic stages.
Follow their existing contracts/runbooks with new versioned registration,
inventory, scratch and output paths; never reuse pilot001 paths for new data.
Choose one file per independently documented session where practical, but file
count does not itself prove independent drives. Record the source session/export
identifier, truthful time evidence and retrieval locator privately before
examining outcomes. New evidence about an existing registration needs a reviewed
successor/amendment, not overwriting its bytes or guessing missing facts.

This is not an assurance that **every** MCAP automatically yields residuals.
Selected decode requires a conforming indexed MCAP with usable summary counts,
embedded Protobuf descriptors and supported single-frame NONE/ZSTD/LZ4 chunks
within the reviewed budgets. It fails closed on unsupported formats, descriptor
or dependency drift, absent topics/counts, corrupt inspected chunks and limits.
Some valid MCAPs need a separately reviewed compatibility amendment. New required
BMW scientific field/frame/source semantics likewise require binding evidence;
ordinary compatible files can reuse the same adapter without a new investigation.
The long-term interface is generic containers plus explicit validated scientific
adapters, not topic-name guessing or silent relaxation.

## What counts as an H100 profile and residual

One accepted estimate/reference pair yields **one 21-dimensional profile** at
`0, 5, ..., 100 m`. Its 21 stations are components of the same profile, not
21 independent samples. A message containing some path points, an advertised
range endpoint or an ego lane ID is not sufficient.

The next consumer must distinguish these denominators and rejection reasons:

1. Decoded EDP/RLMB/odometry messages and every actual schema version.
2. Accepted message qualifiers, estimate/error/path selection and explicit
   topology provenance; unknown source stays unknown.
3. Estimate native forward support and unambiguous finite reference geometry.
4. Full timestamp-stream pairing under an explicit existing/reviewed epoch
   rule, followed by spatial anchoring and common H100 coverage.
5. Geometric H100 candidates by topology, separately from the unchanged old
   SENSOR acceptance gate and any prospective all-topology amendment.
6. Complete prediction-time six-feature support and gap-aware contiguous
   sequences, without bridging missing/rejected rows or resets.

EDP `s=0` is not automatically the ego/rear-axle origin. Retain the reviewed
near-vehicle projection and common longitudinal-station construction, finite
geometry checks, ambiguity/anchor handling and no extrapolation. Treat source,
log/publish and actual geometry epochs as different evidence. Close timestamps
do not by themselves establish a common physical frame or measurement age.
Use odometry compensation only under its separately justified frame/epoch rule;
do not introduce an arbitrary shift to increase yield.

When construction is justified, the historical signed target is EDP minus the
aligned RLMB pseudo-reference, projected on the reference left normal. It is
map-relative path disagreement. RLMB is not physical lane ground truth, and
shared map/pose inputs can suppress common-mode error in both paths. A model
of this disagreement cannot automatically answer absolute lane-error risk.
Changing to all-topology EDP must explicitly state that target/claim limitation,
retain source labels/strata and receive a population amendment before export or
fit. It does not make a pose covariance a path correction or a fused reference
independent. Pose/foresight work remains the separate draft proposal.

## Next implementation order

**Immediate next artifact:** freeze a narrow generic EDP/RLMB/odometry
semantic/geometry-readiness consumer contract for focused review. Reuse the
reviewed disk-index reader and existing scientific conversion/alignment/causal
arithmetic; extend the current architecture rather than replacing it. Specify
descriptor compatibility, all-message pairing versus post-filtering, topology
reporting versus admission, frames/origins/epochs, maximum gap, counts,
time/index/chunk/database bounds, lineage and complete/null publication.
Counts of native or geometric all-source support may be reported without
adopting all-source training; keep that distinction explicit. The source
evidence already present in the repository should be reused, not re-requested.

After focused contract GO, implement/test/review/CI, then one new counts-only
private run with fresh paths. No new run is authorized by this result-closure
patch. Preserve successful decode evidence and do not route the large file
through the old whole-summary reader simply because the memory floor passed.
Any new execution must freshly verify its raw identity once; accepting this
decode report is not permission to skip identity checks in a later phase.
Reuse one verified open stream for the new consumer's stages; avoid redundant
full-file hashes and O(N*M) pairing or whole-message/geometry retention.

Review that output, then prepare generic numeric archive export: exact 21-
station profiles, geometric versus complete-condition subsets, timestamps,
source/schema/session provenance, per-frame rejection/sequence identity,
schema-v1 conditions, archive hashes and a strict read-only validator. Metadata
and numeric arrays must retain identical accepted-row provenance. Keep the
unconditional geometry population available, but compare conditional and
unconditional models on the same complete-feature rows for a fair comparison.
Do not manufacture past speed availability or silently redefine the fixed
50 ms speed arithmetic to repair the previously observed causal attrition.

After defensible target/population and independent-session splits are locked,
predeclare real classic/flow execution and new-only versus legacy-plus-new
training arms with identical untouched evaluation outings, rows, feature
definitions and scoring. Old SENSOR and prospective all-source datasets are
not automatically interchangeable. Report source/condition distribution shifts
and stratify or match populations before attributing a difference to new data.
Fit transforms/tuning on development only. Use uncertainty calibration, proper
sample scores and temporal/spatial behavior as well as mean RMSE; equal RMSE
does not establish equal uncertainty quality. Flow training loss is not a
Gaussian-comparable log likelihood, and flow likelihood is not implemented.
Keep sequence reset/free-running semantics for AR/AIOHMM/conditional flow.

Before retiring raw bytes, verify durable archives/receipts/hash lineage,
review their completeness and demonstrate retrieval of the exact original
registered bytes. Keep original MCAPs until that stage exists and passes.
No automatic deletion is implemented; scratch database cleanup is different
from raw-file retirement. Do not promise a download/process/delete cycle yet.

## How much data to collect

The project's reviewed v0.17 plan is **8--12 eligible independently documented
physical outings in total, including the one legacy development outing**;
its acquisition minimum is seven eligible new outings. In that window its
deterministic split reserves two or three new final-test outings. The old
technical rules include at least 120 s and 500 eligible H100 frames per outing
and SENSOR-only/mixed-source exclusion. These are engineering gates, not a
power calculation or a sufficient flow-training sample size. An all-topology
amendment must address that exclusion explicitly while preserving honest
independent-session validation. Do not state that any 8--12 new MCAPs pass it.

The independent unit for a final claim is the held-out physical outing, not
each MCAP, row, station, transition or the number of kilometers. Thousands
of nearby cycles are correlated. The general group-validation principle is
described in the primary [scikit-learn cross-validation documentation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data):
training and validation must use disjoint groups to assess unseen groups.
Two or three final outings still provide limited generalization evidence;
never report the whole development corpus as the final independent sample size.

A **nonbinding collection budget**, pending actual yield, is 30--60 minutes
per separate session across the 8--12-outing planning window: 4--12 recorded
hours. At an illustrative average moving speed of 50 km/h this would be
200--600 km **if those hours were driving**. Neither number is a dataset gate,
an inference about this pilot, measured distance or an evidence-based minimum.
Seek different sessions/roads/curvature/confidence regimes rather than extending
one homogeneous recording, without selecting on residual/model outcomes.

At the pilot's approximate storage density, 29.96 decimal GB per 60.06-minute
advertised log span, that budget could be roughly **120--360 GB cumulatively
processed** with comparable exports. Compression, topic mix and stopped time
make this a weak storage estimate, not a mileage conversion. The log span is
not acquisition duration or proof of continuous motion. This is cumulative
raw traffic, not a recommendation to store it all locally at once. Topic-scoped
future exports may be smaller if all required streams and export provenance
are retained; do not rewrite the already registered file.

Choose the eventual data quantity using observed geometric/causal yield,
sequence duration and development-only group learning curves/calibration
stability under a reviewed evaluation plan. Do not choose it by repeatedly
checking untouched test results. Primary [scikit-learn learning-curve documentation](https://scikit-learn.org/stable/modules/learning_curve.html#learning-curve)
explains the training-size diagnostic; applying it by whole development
outings is the proposed MPR-specific extension, not an implemented experiment.
This pilot's 36,032 EDP cycles do not yet reveal any valid-profile fraction.
No scientifically defensible fixed GB/km/profile sufficiency can be asserted
before that yield and target are known.

Numeric storage should be much smaller than raw: 21 residuals plus six
conditions in float64 require `27 * 8 = 216` bytes per complete row, so 100,000
rows need 21.6 decimal MB for those values alone. Masks, timestamps, sequence/
source/schema/session provenance and integrity artifacts add overhead. This
is arithmetic for a future archive, not an exported dataset or permission
to delete raw bytes now.
