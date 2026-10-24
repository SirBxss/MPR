# v0.19.18 matched one-state AR development protocol

Status: implementation candidate, 2026-10-24. PR #43 and its first scalar AR
return are accepted; this new consumer has not been independently reviewed,
merged or authorized for a real fit. Private publication terminal evidence
closes the earlier return's pending finalization check. Preserve the original
analysis and add its acceptance checkpoint; never rewrite the earlier report.

## Scope and scientific question

Use the existing one-state Gaussian AR/AIOHMM implementation on exactly the
accepted development rows, whole-outing leave-one-out folds and sequence offsets.
The station-wise autoregression can represent persistence beyond a scalar
memory control. Coefficients apply per retained frame, not per second; the law
does not explicitly condition on elapsed time. With one state there is no hidden-state switching. Its reset
law, conditional mean and innovation covariance also differ from the scalar
control: this is a broader model comparison, not a pure memory ablation.
No superiority, optimal configuration or planner benefit is presupposed.

The signed 21-station SENSOR_TOPOLOGY EDP/RLMB H100 pseudo-residual, feature order,
causal guards and all original exclusions are unchanged. RLMB is map-relative,
may share upstream dependencies and is not independent physical ground truth.
Folder IDs carry owner-declared separate-drive evidence, not independent
verification. Preserve the unconfirmed confidence-width/interface assumptions.

## Exact training and generation law

Use unchanged `AutoregressiveInputOutputHMM`, one state, full innovation
covariance and 21 station-wise diagonal AR coefficients bounded by 0.99.
Reuse each accepted conditional Gaussian fold's exact feature/residual means
and scales; never refit or use the legacy epsilon-floor standardizer.
Reset emissions use the unchanged legacy initialization fitted on all training
frames. No reset-only covariance fit is introduced.

The full literal configuration is frozen in `CONFIGURATION` and in each marker:
maximum/minimum EM iterations 30/5; relative-total-training-log-probability
tolerance 1e-4; regression ridge 1e-3; emission pooling 10; covariance pooling
0.5, diagonal shrinkage 0.15, minimum eigenvalue 1e-5; minimum effective
observations 10; AR ceiling 0.99; transition L2 1e-3, learning rate 0.03 and
Adam steps 30; initial smoothing 0.01; minimum state occupancy 0.01; seed
20260820; input-dependent transitions false. Transition machinery is ineffective
for one state. These explicit legacy defaults are not a reproduction of every
historical fitted artifact or evidence of tuned optimality.

Exactly one training-only fit per outer fold; no validation argument, restart,
held-out tuning or model-family sweep. Save every iteration log, best iteration,
convergence flag, warnings and cap count. Finite valid unconverged outputs remain
visible, marked for scientific review, without automatic fit acceptance or retry.

Pack every original sequence separately, retaining exact integer source clocks,
recording IDs, pair/message indices and padding masks. Preparation hashes this
adapter interface for both sides of every fold without fitting. Training replays
the same interface. Refuse more than 100000 padded frame positions or 2000000
sampled padded positions before legacy allocation; never truncate for memory.
Bounds apply to interface positions, not byte-level process RSS guarantees.

Generate 128 free-running trajectories per retained sequence, seed 20261022 plus
fold index. The legacy sampler consumes different random streams than the
accepted Gaussian/scalar consumers: common seeds do not establish common indexed
noise. Generation receives conditions/lengths only, never observed targets.
Resets remain original; no rejected frame or recording gap is bridged.

## Fair scores and interpretation

Reuse immutable scores/states from the accepted Gaussian pair and scalar AR;
fit no predecessor. Use the unchanged physical sample scorer and equal-outing
primary aggregation. Sequence energy and retained-pair lag error are descriptive
primary metrics with paired outing tables against all three predecessors.
Singletons carry no transition information. Missing temporal support remains
unassessed. Short retained windows do not establish long-horizon persistence.

For frame NLL, compute the exact generated-history Gaussian marginal recursion:
`m_t = B x_t + diag(a) m_(t-1)`,
`C_t = diag(a) C_(t-1) diag(a) + Q`, starting at the reset Gaussian.
Include the physical residual-scale Jacobian. Keep observed-history chain
NLL/frame separate and explicitly offline; it is not prediction-time observed
error input and is not interchangeable with frame marginal NLL.
Save analytic marginal-mean RMSE separately from sample-score means.
Sample Monte Carlo variation remains; no automatic winner or significance claim.

## Contracts, lifecycle and authorization

New modules are `modeling.matched_one_state_ar`, `io.development_one_state`,
`workflows.development_one_state` and `cli.development_one_state`.
A closed nine-field request pins the original scalar experiment and its accepted
ZIP, new experiment/training/auth/result locations and contract revision.
The reader verifies exact predecessor producer, CRC/SHA/file set, consent,
attempt claim, nested Gaussian bytes, saved states, rows, scores and paired
aggregates, then reuses original cohort/all-descendant replay. It does not fit
or recompute predecessor score Monte Carlo draws.

Preparation writes only `request.json` and `experiment.json`. The latter binds
old experiments, row manifest, archives, folds, adapter layouts and full protocol.
Existing engineering model-admission flags remain false. A distinct exact
authorization purpose `fixed_one_state_ar_development_only` requires all four
literal booleans:
`explicit_development_one_state_ar_fit`,
`independent_protocol_review_and_ci_accepted`,
`final_outings_remain_unexposed`,
`fixed_protocol_and_preserve_failed_attempts`.
Old Gaussian/scalar consent cannot authorize this fit.

Under the writer lock, recheck destinations/source/inputs and create an exclusive
fsynced semantic claim before fitting. Its design binds the original Gaussian
experiment, accepted scalar ZIP and full protocol, independently of output aliases.
Renaming paths cannot create a fresh ordinary attempt. New ancestors are fsynced.
Known raw input aliases are rejected lexically before endpoint metadata access.
No raw read, scan, export, acquisition or final-outing exposure is part of this stage.

Success is `complete_matched_one_state_ar_cross_validation`, exit 0, integrity
true and no failures. Training preserves adopted consent, claim, accepted scalar
ZIP, per-fold model/fit report and scores, and receipt. The private result ZIP
contains `experiment/`, `training/`, and `SHA256SUMS`.
A failed/interrupt attempt preserves available outputs and ledger, exit 2/130,
and cannot be retried by ordinary commands. Output-creation, receipt or packaging
failures emit separate immutable claim-adjacent failure events when storage permits.
Checked partial ZIP publication uses file/parent fsync and exclusive linking.
A post-publication fsync failure preserves the published ZIP and records failure
externally: even a complete embedded receipt cannot alone prove final publication.
Return terminal output and actual child exit status with the ZIP. No process can
guarantee receipt creation on total storage failure or SIGKILL/power loss.

## Review and continuation

Require independent source/protocol/private-helper GO, actual exact-head Python
3.10/current, Python 3.12/current and frozen-reader CI, and owner merge.
Then prepare without fitting and inspect its expected marker. Only after owner
adoption of the new four statements execute the sealed operation once.
Local tests are engineering verification, not a BMW scientific result.

Four major comparison stages remain at candidate delivery: (1) operate and review
this stronger AR baseline; (2) separately review matched unconditional and
conditional AR flow experiments and any justified training-only improvements;
(3) freeze comparison/selection and conduct authorized held-out evaluation;
(4) planner-level assessment. Stage counts are milestones, not guaranteed numbers
of PRs or commands. Both flows remain synthetic-only until their own real-fit gate.
Do not automatically fit two-state models or intake additional downloads.

