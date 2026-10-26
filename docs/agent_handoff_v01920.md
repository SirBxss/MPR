# Agent handoff — v0.19.20 velocity timing candidate

Read this file after AGENTS.md and docs/current_status.md. Update this handoff,
the root README and current status after each implementation/result/review. Keep
dated historical records intact; add a superseding checkpoint rather than rewrite
the provenance of an old operation.

## Fixed scientific context

MPR models 21-station H100 SENSOR_TOPOLOGY EDP/RLMB pseudo-residual profiles on
0:5:100 m. RLMB is a map-relative pseudo-reference with possible shared upstream
dependencies, not independent physical ground truth. Preserve feature order,
geometry/sign, no-extrapolation, causal guards, outing roles, row/reset contracts
and unconfirmed confidence/interface assumptions. Two final outings remain
unexposed. Owner-declared physical identities are qualified evidence.

Four configurations have completed the accepted matched development comparison:
unconditional Gaussian, conditional Gaussian, scalar stationary AR and station-wise
one-state AR. The last has no hidden-state switching; the scalar control has a
different scientific purpose. Both flow modes exist as synthetic implementations
but still need reviewed matched real-data training/evaluation. Historical
multi-state results use another population and cannot be directly ranked here.
All measured counts, model scores and private pins are in private evidence.

The complete-feature sequences are too short for broad long-history claims.
The speed audit implicates current-endpoint odometry interpolation requiring
future source samples; geometry alone is much more continuous. Do not relax the
guard because output log/publish timestamps tie. Replacing speed or the admitted
population would require a versioned common dataset and matched refits; preserve
the accepted comparison rather than mix populations across families.

## Recent operation chain

- PR #44 a2 station-wise AR return and owner exit-zero publication are independently
  verified. Do not repeat baseline fits, tune AR caps from these results or rerun
  old numeric exports.
- v0.19.19 summary-only pilot returned successfully and its exact request, cache
  pins, descriptor bytes/declarations and receipts were verified. No payload,
  new model or feature was produced. Preserve that original return.
- Offline decoding of custom descriptor options found that VehicleVelocity
  describes COG absolute speed and warns its nested timestamp lacks platform
  support/is zero. This is interface evidence, not observed payload counts. The
  scalar longitudinal timestamp describes interface creation. The generic root
  alone does not establish topic-specific units/frame/measurement availability.
- The v0.19.19 launcher enforced runtime bytes but failed to enforce documented
  review/CI/merge prerequisites. Remote main still showed PR #44 during return
  evaluation, so closure was not established. Record the deviation; never rerun
  the summary to manufacture a compliant history.
- v0.19.20 implements the bounded payload/timing successor and prospectively
  enforces actual merged-source/exact-head-CI evidence plus owner-attested
  independent review GO before raw access. Source/protocol/launcher review,
  actual reviewed-head CI, owner merge and the BMW run are still pending.

## Current implementation and operating boundary

Read [the complete protocol](velocity_timing_pilot_v01920.md). New modules are
domain.velocity_timing, io.velocity_timing_pilot, io.velocity_review_gate,
workflows.velocity_timing_pilot, reporting.velocity_timing and the matching CLI.
Existing scientific/model/feature/export source remains unchanged.

The private packet binds one development recording, original cohort/inventory,
numeric export/audit and a geometry-selected sustained 12-second log window with
one-second margins. It contains every needed cached input; no large source ZIP
needs unpacking or manual descriptor mapping. It includes numbered source patches,
an apply helper for either the old main or already-applied v0.19.19 tree, and a
single owner runner after review/CI/merge. Patch application never reruns v0.19.19.

One full registered raw hash precedes selected indexed decoding of both direct
topics together. Resource caps, fixed request claims and failure ZIPs prevent
silent sweeps and renamed retries. Output is diagnostic CSV/JSON and Python
plots. A fixed 100 ms recorded-clock screen is exploratory; source-clock and
physical availability semantics remain unproven. Invalid latest updates are
barriers. Equal update log times remain ambiguous. Vehicle outer qualifier
acceptance, timestamp substitutions, new speed features and dataset admission
are not adopted. Local hypothetical spans cannot become cohort-wide claims.

## Next actions and training critical path

1. Review the complete public patch/protocol and private launcher/request. Keep
   private measurements, interface binaries and raw identities out of public Git.
2. Owner applies/pushes through normal PR workflow. No agent may push/open/merge
   without user instruction. Pass actual exact-head three-job CI, obtain focused
   independent GO and owner merge. The source gate rejects a feature branch or
   missing/changed CI before raw access.
3. Owner runs the one private launcher with the actual review note and GO
   attestation. Return result ZIP, SHA-256 and child exit code, including failure
   evidence. Do not rename/retry a started request or edit pins/limits.
4. Verify archive/source/gate/raw-identity/scope/clock facts and replay the small
   CSV analysis independently. Check plotted units and time axes. No conclusion
   follows from a normal exit alone.
5. Decide whether a small expansion is justified. Resolve longitudinal physical
   semantics before a causal feature adoption. If blocked or unpromising, stop
   the side investigation; continue matched flow protocol/software work.

Two flow configurations remain under the current development-training plan,
followed by independent verification and a consolidated fair comparison. Final
held-out evaluation and planner assessment are later phases. Do not infer effort
percentages or a guaranteed timeline from the count of finished configurations.
Do not launch expensive duplicate flow fits while the common-population decision
is unresolved or waive the existing scientific/model-substitution gates.

The owner's standard local repository and download paths and patch delivery
rules remain in AGENTS.md. Every future deliverable must include README apply,
validation, review/merge, operation and return instructions, plus explicit status
of what actually ran. Use Python for scientific plots, never image generation.
