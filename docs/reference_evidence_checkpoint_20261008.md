# Post-merge evidence checkpoint and pipeline direction

Date: 2026-10-08. Sanitized handoff; no private payload execution.

PR #30 is merged as `c8a757229c87d040d913ccdeed96364fd1d5e0bc` (2026-10-05
13:45:39 UTC), final reviewed head `1e1fe43195f5107f1e2abbbef06b0f5c6f20d713`,
tree `badf8da510ea6632f20d50402ac3e20e033a6fae`. Claude final GO has zero
blockers. The dated 2026-10-05 Codex check independently verified final-head
Actions [37290291636](https://github.com/SirBxss/MPR/actions/runs/37290291636):
Python 3.10/3.12 each 579 run/577 pass/two skips. This supersedes the older
pre-push merge-state text; old files/results remain dated historical evidence.

## Returned evidence and limits

| Artifact | SHA-256 |
|---|---|
| MPR_PR30_final_head_review_1e1fe43.md | a55a15a3589f6cacb0c8bdfe9110abd7227a2cf309a7c4f2c3b6c8500a5f70dd |
| codex_8.txt | de6669f05da5b1590ec0ccb17d4ce5728e2991908addc50e13c40bf606e2a8ba |
| provenance_metadata.json | 20c8a25803d317f4452ae1bb6bd95c815757434d73ee8bc58163b8c7f53fcc5f |
| copilot_session_24.txt | ba2555aa021752b821626544bf50f77b2030807fff5b7a6f59037f750b8c8cd0 |

The metadata JSON has 506 unique channels and 448 unique schemas; all channel
references, encodings/hashes/sizes and all 38 prior selected rows reconcile.
These are report checks, not independent raw-byte/payload observations.
Its source execution read schema/channel groups only, with no fresh raw SHA,
summary CRC, header-library or file-level metadata inspection. Empty channel
metadata keys do not prove no producer identity exists in file-level metadata.
The 804-byte metadata-index group remained uninspected. Name searches found
no `/sim/` topic in this inventory; broad debug/config name hits do not establish
useful diagnostics, calibration or absence of all possible ground truth.

Actually reported candidate streams include EDP debug, position-on-map space
morphing grid, HPL internal state, feature activation, lane position and MPP
links. These names do not prove payload validity, exact consumed producer
state, independent accuracy or compatibility of new nested bindings.

The reported BMW checkout is now fully identified:
`master@465073bc593195eee0e4eada0a1389943e006a2b`, clean tracked state. This
closes the earlier checkout-identity gap, not the recording-deployment gap.
Its source was inspected externally by Copilot, not independently opened here.
Keep three levels distinct: returned recorded metadata, externally reported
source behavior, and hypotheses about the actual recording.

The source follow-up strengthens these boundaries:

- Published pose status/covariance and available diagnostics do not uniquely
  identify HPL versus fallback writer mode. Missing internal conditions need
  instrumentation in the traced checkout, not guesses from matrix sparsity.
- HPL covariance is additive on ENU rotation-vector components. Published
  mean can have camera-bias adjustment without matching covariance adjustment;
  index 35 is not generally Euler-yaw variance. Covariance is no signed error
  correction or calibrated lane-reference error distribution.
- Foresight IndexRange last is inclusive in the traced implementation; one
  vertex/empty/overflow flags differ. Actual protobuf presence/default semantics
  must be inspected; centreline orientation is not proved by boundary comments.
- RLMB copies foresight lane IDs; EDP ID namespaces depend on topology source.
  Several localization candidates can become ego lanes. Do not choose a
  reference by closeness to EDP or infer correspondence from KEEP_LANE alone.
- MPP has no source header time, held content can be restamped, correlation
  counters need not advance with every lane change, and ENU IDs can repeat.
  Timestamp equality/IDs do not prove geometry epoch or exact consumed input.
- RLMB already converts map geometry using localization and can apply morphing;
  rebuilding the same map plus pose is not demonstrated to improve it.
- LANE_MAP EDP can be downstream of RLMB. Its residual is output-to-input
  disagreement, not independent perception error; pooling mostly map-backed
  rows can obscure the smaller SENSOR population. The old 95.1% share was
  conditional on valid anchored map-reference support, not drive-wide.
- ASTAS source checks concern simulated ego pose, not captured real lane/path
  ground truth. Independent INS/ego pose or future driven odometry also does
  not automatically supply the same intended lane-centre/path quantity.

## Current owner direction and completed review items

On 2026-10-08 the owner requests returning to generic data-pipeline work.
Jonas's previous-cycle odometry proposal was evaluated as temporal stability,
with possible invisible stable bias/shared odometry error; it is not adopted
as a residual target or implementation. Do not silently mix it with old labels.

The next delivered implementation is a metadata-only generic inventory, not
the unfrozen native-reference proposal. It supports repeatable input triage
without adopting a reference, changing EDP filtering or performing model fits.
Michael's KPI/Data Portal session-selection discussion is a separate data-
acquisition lead; query values, segment semantics and target selection are
unverified and are not built into this pipeline automatically.

The final Claude nonblocking follow-ups are handled here or explicitly retained:
merge/head/CI attribution is dated above; old step-4 prompt is marked as revised
after its original execution; metadata-index presence is distinct from actual
metadata inspection; all-topology claims remain source-stratified; the bundle
checks exact base and post-apply tree as well as hashes. Native semantic-hash,
PSD-tolerance, adapter/time budget and private execution questions remain
unfrozen. No further historical review rerun or metadata-name search is needed.

The pilot ZstdError and decoded feasibility are unresolved. Its initial RAM
stop produced no report. Preserve registration/specification/readiness and old
metadata bytes. No auto retry, re-registration, raw deletion, session roles,
reference replacement, covariance propagation or real training follows.
