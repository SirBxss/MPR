# Recorded spatial planner pilot v0.19.30

## Question and scope

How well do frozen models reproduce the distribution of incremental planner
responses to recorded residuals at the same cached speed? The primary
comparison is the CRPS of the peak absolute planned lateral change over the
prediction horizon, with the full covariance Gaussian as comparator. Lower
CRPS means closer probabilistic agreement with the recorded replay target
in this simulator. The pilot uses a single held out development recording
and row weighting within that recording.

The source residual is sensor EDP minus the RLMB fusion proxy in signed
metres at 21 stations from 0 to 100 m. All eligible complete feature rows
from the prepared fold enter the primary arm. The report gives geometry,
complete feature and planner eligible counts separately. The planner is
the existing unconstrained affine solver with the frozen 25 step grid at
0.1 s. At each row the common initial state contribution cancels in the
perturbed versus nominal contrast. Zero initial increment means that the
current profile is applied in a single replan without accumulated
perception induced state from previous rows. The grid is a fixed prediction
grid. A future temporal study needs its own replan cadence and consecutive
observations.

The outcomes concern this affine simulator, its weights and this selected
population. Absolute trajectory replay, lane departure, total constraint
violations and absolute safety conclusions require additional geometry,
state and validation. The threshold here applies to the incremental
planned lateral change. RLMB reference independence and online speed
fidelity remain open.

## Frozen comparator arms

The nominal arm has one zero disturbance. Recorded replay supplies one
target per row. The empirical arm samples complete profiles with
replacement from the six training outings only. Full Gaussian draws use
the original frozen unconditional fold state. The diagonal control retains
the same Gaussian means and station variances and zeroes the off diagonal
covariances. This contrast isolates removal of spatial covariance from
that Gaussian. The unconditional flow uses a saved single profile reset
with Heun 128, the training screened native solver. It evaluates the
snapshot distribution at reset. It does not measure temporal advantages
or higher moments in isolation.

Each sampled arm supplies 512 draws at seed 193001. All draws are reused
at every admissible speed. The first 128 draws form the primary CRPS draw
sensitivity check. Models are selected by the frozen held out identity
before outcomes, with no refit and no additional model selection.

## Metrics and speed sensitivity

Score peak absolute planned lateral change in metres and signed first
curvature change in inverse metres. Report mean, 95th percentile of
absolute replay and row conditional draw values, CRPS, central 90 percent
interval coverage and interval width. For the peak lateral change also
report recorded exceedance of 0.3 m, predicted probability and Brier score.
The latter threshold is an engineering reporting point.

Use original cached speed for the primary comparison. Separately compare
speed minus 4 m/s, original speed, and speed plus 4 m/s on their common
eligible row set, with the same replay profiles and draws. This stress
range was chosen prospectively to be of the order of the previously
observed speed disagreement. It does not estimate a correction,
confidence bound or replacement feature. No speed is clipped. The report
records the count excluded from sensitivity for lack of common support.

For the primary metric report paired mean CRPS differences against the
full Gaussian. Allocate each intact original sequence to a 30 second
source time bin using the start of the sequence and the earliest sequence
start as origin. Resample nonempty whole bins with replacement 1,000 times
using seed 193002 and recompute the row weighted contrast. Report the 2.5
and 97.5 percent quantiles if at least five bins are available. This is a
descriptive within recording sensitivity interval. A cross outing
comparison requires the same frozen evaluation on all seven folds and
outing level aggregation.

## Inputs, outputs and owner operation

Use the native sealed original experiment to replay registry and receipt
lineage, regenerate the prepared rows and compare every array. The
accepted flow result contains the Gaussian result through the predecessor
archives. Validate both saved states, model receipts, fold identity and
the flow solver calibration without fitting. Recheck inputs and consumer
source before publishing an aggregate report and a checksum manifest
in a new private result ZIP. On failure preserve any existing attempt
directory and partial ZIP. The owner helper supplies the independently
reviewed input and code pins. Run once after source and helper review,
CI on the reviewed commit, and merge.

The output contains private aggregate outcomes and lineage only.
Keep the report and all upstream scenario and model artifacts private.
After pilot acceptance, freeze the full cross outing assessment before
running it. Conditional and temporal comparisons need their own contracts.
