# v0.19.5 synthetic flow reproducibility contract

## Starting evidence

PR #26 merged as `6d00ab84ee0bc7b35e1a9f811888e656a81e5b8b`.
The final branch head `b24d4119ca393f2c675c3c2b6888c4dc130c3124`
passed GitHub Actions run `36581621320` on Python 3.10 and 3.12; the user
reports focused corrective review GO. The resulting code has trainable unconditional
and conditional NumPy velocity fields, exclusively for synthetic engineering.
It has no accepted independent-outing cohort or real-data fit.

## This bounded implementation

The two existing modes retain the same straight-path objective, target,
station/feature dimensions, standardized start flag, generated-history
sampler and Euler solver. This version changes two *engineering* details:

1. `SyntheticFlowModel` validates mode, finite model arrays, strictly
   positive fitted scales, the 22/50 input widths, hidden/output shapes and
   finite nonnegative loss history on construction. It copies each array
   before making it read-only. Directly constructed malformed fields fail
   before velocity evaluation or sampling.
2. `fit_synthetic_flow` uses independent child random streams from the
   declared seed for parameter initialization, bridge noise, bridge time,
   and minibatch permutations. Conditional and unconditional training on
   the *same supplied training rows* now use identical bridge draws and
   row orders at the same seed even though their parameter dimensions differ.
   They still have different field inputs, parameter initialization and
   learning trajectories. This is a common-random-number control, not a
   fairness or superiority result. Sampling already uses the same indexed
   normal draw for the same grid and seed.

Synthetic regression tests capture the actual per-epoch noise/time supplied
to the bridge and verify exact equality across modes with different hidden
widths. They check malformed direct construction and separation from
source arrays. They also train both modes on a small synthetic fixture and
compare physical free-running outputs with Euler steps 4, 8, 16 and 32 using
the same indexed noise. The successive RMS step differences decrease for
both fields. This demonstrates local numerical convergence on that synthetic
fixture only. Solver choice for a later real cohort needs a separate
training/validation-only calibration over relevant distributional, tail and
temporal metrics; this test does not certify 32 steps generally.
The minibatch velocity objective and gradients are one pure helper used in
training. A separate synthetic test compares representative analytic
gradients with central finite differences for both 22- and 50-input fields.

Changing the random-stream implementation changes synthetic model weights
and loss traces relative to v0.19.4, even at the same integer seed. There
are no accepted fitted flow artifacts or real results to migrate. v0.19.4
source and review evidence remain historical.

## Scientific gate and next decision

The real data prove only the previously accepted 376 geometric and 134
six-feature EDP/RLMB pseudo-residual rows in batch02, with unknown physical
outing relationships and short condition-complete sequences. No new MCAP
read, split, model fit, score, likelihood, reference independence or
online previous-residual availability is established here.

The next **scientific** step is acquisition of independently identified
outings with longer contiguous causal-feature support, or a reviewed
alternative reference/clock/feature contract if the existing one remains
unavailable. Before fitting a real flow, decide the supervisor-visible
RC-GAN substitution; predeclare physical-outing splits and identical
training/evaluation rows for all baselines, online inputs, training-only
normalization/selection and learned-field solver calibration. The proposed
unconditional-vs-full-conditional contrast combines feature conditioning
and temporal history; attribution requires a separately predeclared
feature-only/history-only ablation. A normalized NLL remains unavailable
without a verified divergence integral. No current batch02 result meets
those gates.

The full conditional generator can simulate from a declared sequence reset
using its own generated previous residual without observing RLMB online.
Whether such a reset/history is meaningful for the intended current-frame
question, and whether conditioning on any *observed* past residual is
operationally possible, must be resolved in the future protocol. The
synthetic sampler does not establish either claim.
