# Agent handoff for prospective solver correction

5 November 2026. Read the newest README, AGENTS, current status and modeling
plan headers, then docs/matched_flow_v01927.md. Earlier conflicting checkpoints
are historical. PR 51 is still the same implementation PR. Apply only the a2
delta on the original v0.19.27 tree. Do not reapply v0.19.26 or the first flow
patch and do not merge the old candidate as the basis for an operation.

Independent review accepted the v0.19.26 cached diagnostics and their numeric
parity. It accepted the restricted original short support comparison as a
scientific recommendation but found a blocker in the first flow solver screen.
The main agent agrees that the numerical correction must happen before any
BMW flow fit. The original actual PR head CI passed all required jobs. That
old run does not establish CI for this new correction.

A2 prospectively replaces the final 32 to 64 step Euler screen and fixed 64
step scoring with Heun 64 to 128 and fixed Heun 128 step scoring. It replaces the single
maximum pointwise tail gate with a fraction tolerance: at most 2 percent of
row and threshold pairs may change by strictly more than 2/32. It retains the
pooled tail limit and all other numerical limits, as well as maxima, counts
and denominators for interpretation. It is a numerical engineering tolerance,
not a formal statistical multiplicity correction or global solver error bound.
The larger synthetic regression exercises both modes with normal and Student t
innovations, short sequence distributions and station dependent scales. An
initial Euler 128 stress sweep still failed the unchanged pooled tail limit in
some synthetic cases; that evidence is retained. The more accurate Heun scheme
addresses this error without changing the numerical tolerances. Exact analytic
field tests assess integration order, stage context, resets and batching.

The sampler adds explicit Heun integration; calibration, the flow contract and
workflow select it consistently for screening and held out scoring. Heun uses
two velocity evaluations per step while holding each frame's conditions and
generated past fixed across both stages. Euler remains the direct API default.
Training math,
architecture, seeds, sample count, admitted original rows, transforms, folds,
reset boundaries, proper scores and unavailable NLL remain unchanged. The
request and authorization revisions identify a2; old prepared pins and adopted
authorizations cannot be used. Private source, runtime, request and helper pins
are reissued together. Independent focused delta review and new actual source
CI precede merge, owner adoption and one authorized operation.

The private runner now preserves successful child preparation evidence when
writing its false authorization fails. The event distinguishes child success
from launcher failure, reports the failed stage and retains markers and any
partial draft in its execution ZIP. It never adopts a draft. It also refuses
any older or uncertain flow attempt claim before prepare or train, preventing
a protocol rename from hiding an earlier real attempt. The CPU ceiling has a
margin above the wall limit, leaving parent interruption time. Preserve logs,
claims, markers, partial drafts, fitted states, receipts and every partial ZIP.
Do not retry an attempted design by changing output names or revision strings.

The main agent accepts the restricted development comparison with explicit
conditions: original matched complete population only; single profile and
retained short lag behaviour only; no long physical time or planner rollout
claim; no speed feature attribution or proven compatible online speed; seven
outing comparison units; fusion pseudo reference; fixed configuration rather
than optimal model family claims. A one state AR adapter does not constitute a
switching AIOHMM. The owner must attest truthfully and the supervisor visible
RC GAN to flow substitution decision remains separate and unprovided here.

Four baseline configurations remain complete. The two flow configurations
still await fourteen outer fold fits. There is no new raw operation, speed
adoption, population export, additional recording intake, baseline refit,
final exposure or planner evaluation. Owner reported additional long drives
remain prospective intake under the existing final reservations.

The private packet preserves the original review and packet, exact current
source snapshot, delta patch, reissued helper and request, synthetic benchmark,
local validation and explicit chat ready owner commands. Review source and
helper together. Future agents must distinguish original head CI, new candidate
CI, independent delta review, owner merge and real result acceptance. Update
continuity after each implementation and carry accepted review closure into
the next implementation without a separate documentation only CI cycle.
