# v0.19.21 cached strict-prior-log history investigation

## Scope and status

This implements the next step after the accepted v0.19.20 timing return. It is
a cached-data diagnostic, not a production speed feature or training dataset.
It makes the earlier post-hoc strict-prior-log hypothesis explicit, auditable
and testable without reading a recording again. Source/independent review and
new-head full CI remain pending; local validation and private measured outputs
are delivered separately. No new raw operation or model fit is performed.

The completed v0.19.20 pilot and its accepted rule are preserved. Its GO is not
reused as authorization for a different feature policy, data expansion or fit.
The candidate's success on the same already examined window is not independent
generalization evidence. Actual measured values, input identities and figures
stay in private evidence, never in the source patch.

## Fixed candidate policy

For each cached EDP frame and each of the two direct topics:

1. Exclude all updates with log time equal to or later than EDP log time,
   independently of their values and qualifiers.
2. Select the single latest remaining logged update. Duplicate updates at that
   selected log time are ambiguous and fail. Empty bounded history fails.
3. Validate that selected update once. Do not search further backward after any
   failure. Require a present nested message where applicable, inner generic
   qualifier 1, finite value, positive source timestamp at or before EDP source,
   source age at most the unchanged exploratory 100 ms, and positive publish
   timestamp at or before EDP publish time. Zero speed remains a valid value.
4. Combine that screen with original available geometry and absence of frozen
   `estimate_features_*` failures. Preserve every original failure code, original
   condition flag and the original geometry-qualified complete mask separately.

No timestamp is substituted, offset fitted, threshold tuned, speed interpolated
or value transformed. Log/source/publish times use integer nanoseconds. Input
source/publish regressions in logged order are reported, not repaired or sorted
away. Outer VehicleVelocity and standstill qualifiers are recorded without an
adopted acceptance predicate. VehicleVelocity remains a diagnostic control.

Reject multiple recording identities in one history invocation. Excluded frames,
estimate/pair index discontinuities, nonpositive source steps and steps above
the unchanged sequence bound split runs. Do not bridge gaps, files or outings.
Only the already retained padded update history is available; no widened scan
or source-time search supplies missing history. The hypothetical local complete
mask cannot be exported as training arrays by this consumer.

## Input verification and filesystem boundary

The input is one explicitly supplied, SHA-256-pinned completed a2 return ZIP.
It must be a regular ZIP, opened nonblocking/no-follow, at most 16 MiB, with the
exact expected unique member set and at most 8 MiB total advertised expansion.
Member CRCs are checked; symlink/traversal members are rejected. File names for
the six cached inputs are fixed before the frozen loader joins any paths.

Only those cached bytes are materialized in a disposable temporary directory.
The unchanged loader checks original cohort/development role, raw membership,
inventory/numeric/audit/NPZ pins, geometry-only window and old speed column.
`allow_pickle=False` and the existing NPZ expansion limit remain. The raw-path
string is provenance only: no raw stat, open, hash or decode is called.

The consumer checks parent completion and scope flags, gate/review/request/source
receipt bindings and reported raw identity, then replays the entire original
analysis and frame CSV from the retained updates. Only a consistent return is
compared with the new hypothesis. Archived source/GO statements are archival
evidence, not authenticated review or fresh live-source authorization. No network
gate is contacted and no operational timing claim is created or altered.

This cached analysis is repeatable into new output directories. It never grants
a repeat of the raw pilot. Existing output directories are refused. Failures
after output creation preserve an incomplete diagnostic report; they do not
become coverage evidence.

## Outputs and interpretation

The new CLI is `python -m lane_residuals.cli.velocity_history`, with only
`--result-zip`, `--result-sha256` and `--output`. There are no age, clock, window,
topic, feature-adoption or training switches. `--help` needs no dataset access.

Output contains a private JSON report, auditable selected-update/frame CSV,
support-comparison CSV and Matplotlib PNG/PDF. Each chosen update's log/source/
publish timestamps, log and source ages, co-logged exclusions, qualifiers and
failure reasons are retained. Original and approved-latest masks are separate.
Reports explicitly retain false feature-adoption, producer semantics, physical
availability, independent generalization and cohort-recovery claims. No X/Y
training arrays, residual extraction, transformed features or model states exist.

The private optional verifier also has a narrow access-guard correction. It now
allows only its six exact cached files regardless of which home directory holds
them, and blocks raw/unlisted paths. The previous entire-home ban incorrectly
blocked the owner's legitimate cached return. The failed optional replay did
not alter the accepted raw pilot or invalidate its completed result. Preserve
that partial replay; no raw rerun is needed. This helper is private, not part of
the public runtime or a bypass of a raw-operation gate.

## Scientific decision still required

The candidate can remove this particular recorded-order cause of fragmentation
when earlier updates satisfy the other checks. It cannot establish the deployed
longitudinal quantity's units, sign, reference point, measurement age, clock
comparability or actual EDP consumer availability. Interface creation time is
not automatically measurement time. A nonzero VehicleVelocity timestamp does
not resolve the discrepancy with its comment or turn the two topics into
independent references. Other geometry/features may still limit sequences.

Match the evidence requirement to the eventual claim. A qualified offline
recorded-clock feature and physically demonstrated prediction-time availability
are different claims. The latter may remain an explicit limitation, as for the
existing baseline; do not invent proof or silently strengthen that claim. Value
meaning and comparable timestamp/clock semantics still need evidence before
adopting a scientifically interpretable replacement. Existing review gates,
rather than this software report, decide whether that evidence is sufficient.

Next independently review the candidate and establish producer semantics. Any
new development windows require a separately reviewed bounded expansion; no
cohort-wide scan is implemented here. A later adopted speed definition/population
needs a versioned common-population comparison and appropriate refits. Preserve
the original accepted comparison; do not overwrite models or launch blanket
refits based on this cached window.

Both matched Gaussians and both matched AR controls remain complete. Both flow
configurations still need matched real-data protocol, training and evaluation.
Flow preparation can continue while these semantics are resolved, under existing
real-fit temporal-support/model-substitution gates. Final held-out evaluation
and planner assessment remain later phases; final outings stay unexposed.
