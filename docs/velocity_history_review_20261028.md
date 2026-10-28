# PR #46 independent review acceptance — 28 October 2026

## Decision and source evidence

The independent reviewer gave GO with no blockers for v0.19.21 source/protocol
and private helpers, and accepted the completed cached diagnostic as a local,
post-hoc exploratory result. The implementation agent accepts those verdicts.
The earlier v0.19.20 return also has reviewer-side confirmation. Keep all private
reviews, measurements, archives and evidence out of public Git.

Read-only repository checks independently confirm the reviewed PR #46 head
`03c00b56d24f285d757bcafcd92297540c14fd5d`, tree
`b69141494fb08bae174f2532619d501222de7753`, and successful tests.yml run
`40667381754`, attempt 1. Python 3.10 current, Python 3.12 current and Python
3.12 frozen-reader jobs all passed compile and unit-test steps. The generated
CI merge ref has the same tree. At this check PR #46 is open and unmerged.

The owner can merge that exact approved head. No source correction or owner
operation is required. Merge it before applying this documentation-only closure,
or carry the closure into the next source checkpoint; do not create another
implementation/review cycle just to refresh pending-status text. This closure
changes no runtime or test. Old CI validates the approved implementation, not
any later documentation commit's CI status.

## Material source-tie qualification

The primary candidate excludes log-time equality but permits source-time equality
and publish-time equality. Those are the existing reviewed conventions, not a
new relaxation. Log observation order and source timestamp meaning are different
concepts, so their tie conventions need producer-based justification rather than
an assumption that they must be symmetric.

The source-equality sensitivity is material on this examined window. Its exact
values and Python plot are in the private acceptance evidence. Preserve the
primary convention unchanged. For every future independent window, predeclare
a secondary analysis that selects the same latest strictly prior-log update and
then requires source age at least one nanosecond. A source-equal selected update
fails that secondary; there is no search further backward for a replacement.
Report both masks, runs, spans, source ties and gained/lost original frames.

This secondary was introduced after examining the same data and is post hoc
here. The current approved public runtime does not implement the new secondary
report; it exists in private review/replay analysis. A future prospective
consumer must declare its reporting before inspecting new windows. Do not switch
tie conventions, fit offsets, enlarge the age bound or choose success criteria
after seeing those results. A sensitivity analysis is not a new adopted dataset
or a fair model benchmark against a retrospectively altered baseline.

## Producer evidence and signal dependence

Next obtain read-only producer-code evidence for the longitudinal value's units,
sign and reference point, both source timestamps' assignments and clock/cycle
relationship, timestamp resolution/conversions, and relevant consumer timing.
Distinguish interface creation from measurement age and actual input availability.
If the deployed build cannot be matched, state that limitation rather than turn
current-source evidence into a claim about the recording.

The direct topics have very strong local numerical/timestamp correspondence.
Treat VehicleVelocity as a consistency comparison, not an independent reference
or physical control. Local near-identity does not prove producer-level identity,
global interchangeability, reverse/standstill behavior or equality of the
documented longitudinal and COG quantities. Outer velocity and standstill
qualifiers remain observed-only. Preserve the actual payload versus interface-
comment distinction.

## Next boundary and training

No new raw read, bounded expansion, feature/schema adoption, population admission,
refit, final exposure or real flow fit is authorized by this review. The completed
analysis is already available; optional replay is unnecessary. Preserve the
closed raw design, its owner claim and the old partial optional replay.

After producer semantics are assessed, prepare a separately reviewed prospective
bounded development expansion. Fix both tie conventions, the secondary report,
the unchanged age screen, geometry-only window selection on other development
outings, success criteria and resource/source gates before inspection. No final
outing or cohort-wide sweep belongs in that scope.

Four accepted matched baseline configurations remain complete and immutable.
Both flows still need their first matched real-data fits. If a changed speed
schema and expanded population are adopted, use a versioned common-population
comparison: refit the affected accepted baselines under that protocol and train
both flows there, preserving the original comparison. Flow protocol/software
preparation can continue; avoid expensive real fits before settling the common
population under the existing scientific gates. Held-out evaluation and planner
assessment remain later phases.
