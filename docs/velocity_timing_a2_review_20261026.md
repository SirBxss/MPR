# PR #45 a2 correction and continuity record

The independent source/protocol review required two corrections before the
single timing operation. The private operational packet was not available in
that review, so it had no private-helper or operation GO. This revision remains
on PR #45 and supplies the complete private packet for the focused follow-up.
It does not change accepted model/data/reference contracts or fit anything.

## Corrected local estimand and figure

The frozen producer tags estimate-derived feature failures with
`estimate_features_`; remaining condition failures come from the speed path,
including odometry-prefixed codes and static exception class names. The local
hypothetical complete mask now uses available geometry, absence of an
estimate-feature exclusion and the unchanged recorded-clock screen. It no
longer inadvertently retains old speed-path failures as other-feature exclusions.
The frame CSV preserves original failure codes and constituent mask flags.

The raised timeline series is the combined local mask, so its legend and panel
title now name that combined quantity. Clock-screen success alone is distinct.
Geometry/non-speed exclusions still break local runs. The fixed 12-second
geometry-only selection, padding, 100 ms engineering screen, clocks, qualifiers
and no-fallback policy are unchanged. No threshold tuning or data adoption follows.

## Lifecycle and source boundary

- Claims now use canonical semantic identities, excluding JSON formatting and
  input/output paths. The design and submitted request hashes are both recorded.
  File and directory durability is explicit. Claims remain per project; fresh
  clones must not be used to evade them.
- One nonblocking/no-follow descriptor first reads metadata and proves the actual
  indexed window budget. This happens after source/role/resource checks but before
  the hash/payload claim. Global advertised totals alone cannot establish local
  window cost. The prepared metadata/index/decoder plan is reused without another
  summary pass. Full registered SHA verification still precedes all message decoding.
- Atomic, fsynced phase receipts use unknown hash/decode progress initially, and
  persist completed boundaries. SIGTERM becomes a catchable interruption. Hard
  kills retain a truthful unknown snapshot rather than false-negative booleans.
- The private runner pins the full reviewed tree as well as runtime and request.
  Source-only sealing/checking can be tried before the operation. A later merge,
  including documentation alone, invalidates this packet. Independent GO remains
  owner-attested with the note hash; it is not authenticated by software.
- Numeric aggregate keys avoid implied equivalent m/s units. Per-topic EDP log
  ties are aggregated. VehicleVelocity remains a diagnostic comparison signal,
  not an adopted feature. Scalar defaults and interpreter trust limitations remain.
- Older continuity headers are labelled historical. Their original descriptive
  text and the v0.19.19 protocol/result are preserved. The root README, AGENTS,
  status, commands, architecture, handoff and current protocol describe a2.

## Verification and pending actions

The a1 owner head `55575ab37bcd7bf9377800fb845354dfe07c5561`, tree
`807809a51828d6a7d6be35997afbd64d27cf8bdb`, passed all three jobs in run
`40303351499`; the implementation agent verified those GitHub records directly.
That is historical a1 evidence, not validation or permission for a2.

The a2 focused checks cover speed-path code classification, geometry/feature
barriers, actual figure labels, reformatted requests, budget stops before claims,
FIFO rejection, and native SIGINT/SIGTERM/SIGKILL at hash/decode boundaries.
Python 3.12.14 current and frozen-reader environments each pass 101 focused
checks with no skips, including 13 added regressions and 55 unchanged reader
checks. A native synthetic CLI also passes under the actual 4 GiB ceiling;
its source/CI evidence is explicitly mocked. Ten private parent checks pass
with delegated child/network calls stubbed. Plot labels were visually inspected.
Private preparation separately verifies unchanged cached identities and actual
descriptor field/enum bindings, without opening an owner raw endpoint. No BMW
timing operation or model/transform fit has occurred. Full validation and pins
are recorded in the private delivery packet.

Next: owner applies only this delta to the existing PR #45 branch, pushes it,
obtains focused source/protocol/private-packet GO and new-head three-job CI,
then merges. The private runner's metadata-only dry run and single bounded
operation follow those gates. Preserve failed packets; never rerun old probes
or exports to repair history. Flow protocol work can proceed within the existing
scientific gates; this correction is not a new training experiment.
