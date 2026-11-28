# Common support for repeated steering-rate budgets

The data-efficiency question is whether one-state AR can tune the
controller with fewer labelled outings than intact-sequence empirical
resampling. The earlier budget pilot used one nested subset of each size.
Repeating the comparison across outing compositions helps distinguish
label budget from the influence of a particular outing.

## Metadata check

- Recover the accepted PR #60 calibration partition and context bank. Bind
  the PR #60 preflight and PR #62 rate-design receipt by SHA-256. Replay both
  designs with exact parity. The six passing steering-rate indices are
  1 through 6, with weights from 2,048 to 65,536.
- Enumerate every subset of one, three and five of the five calibration
  outings in deterministic order. This gives 5, 10 and 1 subsets,
  respectively. Count eligible intact empirical donor windows on the
  original context bank for each subset. Use the original sequence resets
  and per-interval cadence tolerance.
- Keep the intersection of supported contexts across all subsets for
  both methods. With every singleton included, a shared context needs at
  least one donor window from each calibration outing. Record any context
  losses and per-outing coverage. Do not fill gaps with contexts picked
  after seeing labels. The check stops if a calibration outing loses all
  its contexts or any native metadata resource check fails.
- Recheck the six frozen rate weights on the resulting panel. Keep the
  original full-panel tracking anchor, passive probes and peak limits.
  A failed weight stops this design. Retain its diagnostics to inform
  any separate design review.

The private report seals the common panel and records support and nominal
diagnostics. It reads only the allowlisted calibration metadata members.
The support intersection can change the distribution of scoring contexts.
Coverage and the stopped cases should be reviewed before fixing a
selection protocol. The minimum of one context per outing is a structural
requirement for equal outing weighting. It is not a statistical adequacy
claim.

## Subsequent comparison

Fix the scoring bank, transforms, draw count and controller-choice rule
before reading calibration residuals. Fit each AR model within its
assigned whole-outing subset. Compare the two methods on identical
subset budgets and contexts. Treat the overlapping subsets as development
sensitivity analyses. New fit and audit authorization are separate from
the metadata receipt. Preserve the previously used inner-development
audit and the outer held partition.
