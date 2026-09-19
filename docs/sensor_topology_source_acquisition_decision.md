# Post-v0.18.1 source and acquisition decision

2026-09-19 priority update: four new large MCAPs have arrived according to the
user. Follow `docs/independent_outing_batch02_arrival.md` for administrative
registration and existing summary-only inspection first. The epoch correction
is already on the remote branch at `ca6b154` and still awaits focused review.
Recover available metadata for these new sessions; missing historical batch01
build records do not block their registration. The scientific decision table
below remains applicable before any new geometry/residual construction.

Started: 2026-09-17. Updated: 2026-09-18. Status: the source inquiry has
returned; a timestamp/provenance interpretation correction is prepared for
focused review. No new scientific target, acquisition configuration,
diagnostic or executable implementation is selected.
This is the planning step toward a possible v0.19 phase, not a v0.19 release
or an executable audit predeclaration. MPR remains version 0.18.1.

Current disposition: `docs/bmw_sensor_topology_epoch_evidence.md` preserves
the received transcript identity and assesses the new findings. The next
evidence request concerns the recording's actual build/configuration and
an applicable physical-frame/epoch specification. Do not repeat the broad
inquiry below. The reported cutoff is a current-source hypothesis for
batch01; it is neither an observed span nor a chosen new horizon.

## Starting point

PR #20 merged at `1403927b8b0a0155cea19c6daba841160254c8c1`, tree
`440f3bfc1a19fd9e74ef563c43c410da073cb7e3`. The final branch head was
`5b2034e6d704c5d23410b46e9cfd6e095859f5e2`, with the same tree. Its
[CI run 35222402624](https://github.com/SirBxss/MPR/actions/runs/35222402624)
passed Python 3.10 and 3.12 compilation and unit tests with MCAP extras.
This is verified pre-merge CI, not a claim about a separate main-push run.

The accepted one-outing batch01 result is immutable: 4,039 valid camera-only
chains, zero sensor chains reaching the required 100 m observed span, 9,235
independently ready reference messages, 17,087 source-time pairs and zero
synchronized candidates. The reference binding defect is fixed. See
`docs/sensor_topology_batch01_v0181_result.md` for exact lineage and review.

The remaining question is not answered by another execution of that audit:
**what source or acquisition evidence supports the next defensible geometry
construction, and which implementation, if any, follows from it?**

## Evidence, assumptions and hypotheses

| Item | Evidence currently available | What is not established |
|---|---|---|
| Sensor geometry | CAMERA-tagged boundary geometry in a map-influenced LTSB graph; no producer-defined direct path was found in the traced LTSB code | Map independence, unbiased boundary geometry or a planning path |
| 100 m span | No strict chain passes in this batch under the reviewed recipe | A maximum physical sensor range, typical lengths, distance from the threshold or a viable shorter horizon |
| Chain termination | MPR stops on normal termination or an empty map-influenced successor and rejects ambiguous/invalid chains | Which producer/configuration mechanism explains this batch's short chains; the outputs do not separate those terminal causes |
| Midpoint | MPR orients each side and pairs equal fractions of its own arc length in `midpoint_from_boundaries` | That unequal boundary extents share a longitudinal origin or that equal fractions represent common physical cross-sections |
| Source time | Numeric header proximity is observed; the fourth trace reports tracking/odometry-epoch and pipethrough/header-time branches plus possible timestamp rewriting | The recorded mode/epoch, equal measurement age or aligned geometry |
| Frame | LTSB units are known; RLMB documents rear-axle reference; no common LTSB origin/axes were established | A physical transform, axis convention, vehicle reference point or valid motion-compensation recipe |
| Producer/configuration | Three earlier traces and a fourth at reported BMW HEAD `465073b`; the latter reports concrete cutoff and processing parameters | The deployed batch01 build/configuration or an acquisition mode capable of the intended geometry |

Possible clipping, unequal boundary support, held geometry and reconstruction
conservatism are **hypotheses**, not findings from the output counts. There is
no newly established implementation defect. The normalized-midpoint recipe
remains valid as the definition of the completed structural diagnostic; its
suitability for a future physical residual needs separate justification.

## Completed inquiry scope (preserved for context)

The BMW checkout is unavailable to the MPR implementation agent. Follow
`AGENTS.md`: provide a focused Copilot request for exact private symbols and
evidence, then use the returned source trace to choose the implementation.
The request was a separate handoff file outside Git. It asked three questions:

1. **Extent and acquisition:** trace the camera-boundary input through
   clipping/filtering, segment partitioning and holding to the existing LTSB
   output writer. Identify any actual limits, parameter defaults and active
   overrides, their units and domain (vehicle-forward distance, arc length,
   map distance, point count or another quantity). Distinguish a documented
   capability from a guarantee. Establish the known relationship, if any,
   between the inspected source/configuration and batch01 or a future
   acquisition. A current default is not proof of a recorded setting.
2. **Geometry semantics:** follow the upstream camera geometry writer to
   its physical origin, axes, direction, per-boundary longitudinal definition
   and validity epoch. Determine whether clipping can give the two sides
   unequal support, and whether producer evidence supplies a common station
   convention or correspondence rule. Trace held/cached geometry and any
   ego-motion propagation. Compare these explicit semantics with RLMB;
   record exact transform direction and prerequisites only if established.
3. **Provenance:** separate map effects on coordinate values, topology/ego
   selection, holding/propagation and shared pose/calibration inputs. Check
   the RLMB side of those dependencies as well. Lack of a direct RLMB
   subscription does not establish independent error. Identify which
   comparisons could remain a defensible pseudo-residual and which claims
   the evidence cannot support.

Reuse the complete paths in `docs/bmw_sensor_topology_source_evidence.md`.
Do not repeat the closed decoder, CAMERA enum, range-sentinel or ego-index
questions unless new source evidence contradicts their previous answers.
The missing historical BMW SHA is not retroactively made a v0.18 blocker.
Record the new inquiry's exact HEAD and immutable file/blob identities;
leave recording-build correspondence explicitly unknown when unavailable.

This inquiry reads source, checked-in configuration and already available
build metadata only. It does not open MCAP payloads, compute lengths or
statistics, alter configuration, replay recordings or run an acquisition.
It requires no additional MPR executable and no additional review just to
collect the read-only evidence. Return a concise private report with
claim, complete path/symbol, evidence revision, configuration scope and
unresolved consequence for each answer. Unresolved answers are acceptable.

## Decision after the evidence returns

| Supported finding | Next bounded action | What stays blocked |
|---|---|---|
| Source evidence contradicts an interpretation without establishing an executable defect (current disposition) | Correct and review the epoch/provenance claims; recover recording/frame evidence without changing the accepted counts | Inferring a causal diagnosis, hard-coding current defaults or rerunning the audit |
| A concrete decoder or reconstruction mismatch with applicable producer semantics | Demonstrate it with a minimal synthetic fixture; propose a narrow versioned corrective contract and review before changing an accepted rule or rerunning private data | Silent changes to v0.18.1 or treating a changed recipe as the same result |
| A documented acquisition mode can supply the desired camera support | Plan a prospective pilot with recorded build/configuration and separate physical-session identity; define technical acceptance before seeing its output | Assuming 100 m observed span guarantees forward H100 from an ego anchor or a final-data cohort |
| Confirmed producer limits make the intended H100 target unsuitable | Present an explicit target/source decision, with scientific rationale independent of selecting a passing horizon on batch01 | Automatically choosing 50/60/80 m, extending with map geometry, extrapolating or reusing EDP models |
| The extent question remains unknown | State the missing fact. Consider a separately scoped descriptive engineering diagnostic only if needed, with reviewed questions, output fields and data-use limits fixed first | Ad hoc span histograms, threshold sweeps or reopening the closed batch under the old authorization |
| Frame, epoch or boundary correspondence remains unresolved | Keep any future work at structural feasibility; request only the specific missing evidence or propose a separately reviewed calibration study | Cross-topic projection, motion compensation, alignment and residual construction |
| Shared dependencies prevent the intended interpretation | State the bounded pseudo-reference interpretation or propose a different target/reference in a separate decision | Calling map output independent ground truth or substituting `/adp/lane_topology_map_based` merely by name |

Source evidence alone cannot assign final-data roles or validate a geometry
algorithm on real messages. It determines the next question and synthetic
fixtures. A changed target needs its own station/origin, signed-residual,
reference, causal-feature, sequence and validation contracts before fitting.
Historical EDP results and the new sensor-lane target remain separate.

## Completion and handoff

The implementation agent should, in order:

1. Preserve and hash the returned private source report, without committing
   it or full private source excerpts. Record only the needed evidence
   summary, exact identities, contradictions and remaining unknowns in MPR.
2. Compare the answers with the existing code and all three earlier traces;
   distinguish recording-applicable facts from current-source-only facts.
3. Select the smallest supported next change using the table above. Write
   a concrete prospective contract when the scientific rule or data use
   changes; obtain the applicable focused review before implementation/run.
4. Implement in the existing domain/I/O/workflow/CLI layers only when needed,
   add meaningful synthetic tests, and follow the established implementation
   review and new-directory execution sequence for any private audit.

Do not add a speculative evidence validator, new CLI, configurable horizon,
model or alignment adapter merely to create code during this evidence gap.
No final-model evaluator is unblocked: v0.17 still has zero eligible new
outings, and the historical model/planner freeze remains in force.
