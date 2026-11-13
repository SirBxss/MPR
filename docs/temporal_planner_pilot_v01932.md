# Temporal planner pilot v0.19.32

The spatial replication completed on the frozen development folds. The
next question is whether temporal dependence improves prediction of a
planner's response across consecutive updates. This candidate evaluates
the lexicographically first original development outing as an engineering
pilot. It uses frozen states and the original retained sequences.

## Hypothesis and comparator design

The primary contrast is the one state AR forecast minus its framewise
permuted control for mean normalized sequence energy of incremental
commanded lateral acceleration. The score has units of metres per second
squared. A lower score means closer joint distributional agreement with
the recorded residual replay within this simulator.

Generate complete sequences from the saved models using only conditions
and original reset offsets. The generated past comes from the sampler.
Independently permute draw indices at every frame after a sequence start.
Move all 21 stations together. Each frame retains exactly the same
finite collection of spatial profiles. Dependence between frames is
altered without changing those framewise empirical distributions.
Finite permutations can retain some residual empirical dependence.

The arms are zero disturbance, empirical independent frame resampling
from the training outings, frozen full covariance conditional Gaussian,
stationary scalar AR, its permuted control, one state AR, and its
permuted control. The scalar AR offers a second temporal control whose
theoretical marginals equal the conditional Gaussian marginals.
Comparisons across fitted families can also reflect different fitted
marginals. The within model permutation contrasts isolate temporal
coupling of the same finite profile ensembles.

The pilot uses 128 draws with seed 193201 and permutation seed 193202.
The draw sensitivity uses the first 64 native draws and generates the
permutation control again within that prefix. All models and their
training transforms come from the original matching fold. No held
residual enters a sampler or an empirical training pool.

## State and clock definitions

Use the existing affine lateral planner and its 25 step prediction
horizon with fixed prediction step 0.1 s. Let the incremental state
contain lateral error in metres, heading error in radians and previous
curvature command in inverse metres. With speed v and prediction step
fixed, its first command has linear form

`delta_u_t = K(v_t) delta_x_t + G(v_t) r_t`.

The coefficients are obtained from the native planner by solving three
unit state and 21 unit profile inputs. At an observed update interval
h, propagate its native Euler dynamics with distance d = v h

`delta_e_next = delta_e + d delta_heading`

`delta_heading_next = delta_heading + d delta_u`

`delta_previous_command_next = delta_u`.

The nominal and perturbed plans have identical speed and common nominal
affine forcing. Their common state contribution cancels in the
difference at the initial update, and subtraction gives the incremental
recursion at every later update. An independent regression checks direct
native solves from two nonzero initial states with changing speeds,
irregular intervals and common affine forcing against this recursion.

This is an explicit local error state simulator assumption. Profiles
are exogenous recorded inputs, and the perturbed vehicle does not feed
back into perception. The numeric archive does not supply global nominal
coordinates or observed initial state. The experiment therefore evaluates
incremental simulator responses. Geometric frame reconstruction and
actual closed loop vehicle behavior need additional evidence.

Use exact integer differences between consecutive EDP source epochs for
the state update intervals. Convert the differences to seconds only
after subtraction. These epochs define the simulator's input cadence.
They do not establish actual online planner input availability.
The prediction grid and observed update intervals have distinct roles.
The AR coefficients remain those fitted per retained frame.

## Support and resets

Use all original complete rows for native model sampling so every model
keeps its original sequence history. Admit a whole sequence for scoring
only if it has at least two frames, every frame meets the original speed
and spatial lookahead rules, and every interval is within the existing
planner interval bounds. Exclude unsupported sequences as a whole.
Record every original sequence and its exclusion reason. Reset all
three incremental state components at each original sequence start.
The last recorded command is scored without inventing a final update
interval.

The primary command score applies to sequences with at least two frames.
With zero initial increment, the Euler model produces zero lateral
increment at both observed times of a two frame sequence. Accordingly,
the secondary peak lateral state score applies only to sequences with
at least three frames. Report its assessed count explicitly.

## Scores and interpretation

For a sequence of L commands, divide the energy score of the L dimensional
commanded acceleration vector by sqrt(L). Use the full pairwise mean
distance of the finite draw ensemble. Average equally across eligible
sequences. The signed primary contrast is one state AR minus its own
permuted control. Also report the analogous stationary AR contrast,
command marginal CRPS and peak incremental lateral state CRPS.
Report every per sequence score in the private return.

For each command, the reported acceleration increment is v squared
times the incremental curvature command. Absolute acceleration requires
the common nominal curvature. Scores concern the short observed support
of the retained sequences, conditional on the fixed models and common
motion inputs. The finite ensemble score and prefix check are
descriptive. A further outing replication must be specified before
looking at its temporal scores. A temporal model benefit in this pilot
still leaves planner parameter tuning and physical validation as
separate research questions.

## Operation and failure handling

The private manifest pins the accepted spatial replication, original
experiment, one state experiment and result, selected fold, saved model
states, scenario identities and support summary. The native temporal
evidence readers replay the existing registry and saved state lineage.
Preflight checks the complete support and native sampling budget with
no scoring or output writes.

Review source, protocol, exact manifest and helper, then verify CI on
the actual reviewed PR head and merge. The helper's default output is a
sibling of the packet, outside its manifest directory. This incorporates
the operational correction from the previous owner preflight.

The scoring run writes the reviewed manifest and sequence census,
samples the frozen laws once, records the main and prefix scores,
rechecks all inputs and source and publishes a checksum ZIP through a
temporary partial name. Existing destinations are rejected. Preserve
the directory, partial ZIP and terminal log on failure.
