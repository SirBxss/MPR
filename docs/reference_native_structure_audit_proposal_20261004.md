# Next implementation proposal: bounded native reference structure

Date: 2026-10-04. **Draft for focused contract review, not a frozen executable
predeclaration or private-run authorization.** No CLI exists for this proposal.
Read `reference_evidence_reconciliation_20261004.md` first.

## Question and non-goals

Determine whether the registered pilot's selected streams decode, carry
present/valid native fields, and provide the association information needed
to design an honest reference construction. Do not transform paths across
topics, propagate covariance, select a reference, calculate residuals, export
conditions, remove the old SENSOR filter, train, assign outing roles or delete
raw data. Unknown source revision or covariance mode is a reported unknown,
not an invented default or a reason to suppress native availability counts.

The audit is development evidence for one technical recording. Its counts
are not independent-drive generalization, physical accuracy or H100-pair proof.
Any future all-topology target requires a separate construction/population
amendment, even if geometry code is reused.

## Minimal streams and schema binding

Start with recorded EDP, RLMB, pose, foresight lane data, ENU frame and MPP
best lanes / lanes-on-links / links. Add a morphing/provenance/debug stream
only if its actual recording presence and exact schema are established by
the metadata follow-up and included in the reviewed contract. Do not scan all
foresight payloads because their names look useful.

Resolve schema root and required field number/type/cardinality/presence and
enum values from the recording descriptors. Pin evidence-report lineage and
record every channel/schema version actually audited. Channel IDs are local
to a file, not generic bindings. Extra or changed required types fail closed;
optional additions must follow an explicitly reviewed compatibility policy.
Do not build decoders from the text JSON alone: obtain embedded descriptor
bytes locally through the bounded reader. Respect unknown enum values and
missing optional fields. No ROS covariance order or interface-comment default.

## Counts permitted in the first phase

| Stream | Native observations | Interpretation withheld |
|---|---|---|
| All EDP topologies | Decoded root/qualifier/source counts; KEEP_LANE and error states; clothoid/segment/confidence structure; counts by topology and rejection reason | New residual eligibility, topology independence, geometry epoch |
| RLMB | Empty/multiple ego indices; lane IDs and ranges; finite present means; pool/reference structure; missing stddev versus written zero | Ground truth, reliable uncertainty, equality with raw foresight |
| Pose | Presence and array-length histogram; qualifier/status/sensor/reset combinations; covariance missing/nonfinite; finite mean/frame-id presence | Calibrated 6 x 6 covariance, HPL/GNSS classification, Euler or lateral variance |
| Foresight lanes | Pool sizes, optional/valid flags, IDs, duplicate IDs, present range endpoints, connectivity; bounds only under proved range semantics | Correct ego lane, unambiguous connected H100 reference |
| ENU | Qualifier/status/id presence, origin presence and finite fields; id equality/reuse/content-change/reset census | Monotonic id, physical timestamp age, valid cross-frame transform |
| MPP | Qualifier/status/has-value, correlation IDs, map counters, lane-id references and duplicates | Ego-lane truth, causal validity interval or future-free association |

Do not merge unknown/absent into valid zero. Pose status does not uniquely
prove a writer branch until that mapping is established. Numerical symmetry
or PSD checks on complete finite 36-arrays, if included, need explicit
tolerances and missingness categories in the frozen contract; they cannot
validate covariance basis/calibration. Native polyline length is only a
geometry statistic once point units/range semantics are justified; no use
of arbitrary unconnected pools or reinterpretation of field `length` as H100.

For streams with timestamps, retain differences between header, log and
publish clocks and their reset/nonmonotonic counts; do not relabel them
measurement age or infer Unix time. MPP roots lack a header timestamp:
record that absence. Changes in geometry/content versus restamped identical
content need a precisely declared semantic hash, excluding publication-only
fields. Every partial scan must expose processed coverage, stop reason and
denominator; no extrapolation to full recording counts.

## Engineering and publication contract to freeze before implementation

Reuse domain / I/O / workflow / CLI ownership and the merged indexed storage
reader. Retain the registered bytes, pinned small-file lineage, one fresh
output directory, Linux 6 GiB available-memory / 10 GiB scratch gates, 4 GiB
process cap, and nonzero stored selected-chunk CRC checks. CRC zero means
unavailable; count/report actual checked versus unavailable coverage.

Use one verified open raw stream, file-state checks before/after processing
and publication, physical chunk order, disk-backed summaries where needed
and explicit ceilings on selected message/record/chunk sizes and scratch.
One-chunk retention is not an assertion that an arbitrarily large chunk
fits; reject oversize inputs before allocation using reviewed limits.
Do not retain all decoded messages/geometries, use a seeking FIFO queue,
repeat full raw hashes in each phase or make an O(N*M) temporal join.

The exact full-scan or deterministic bounded-sample policy, timeout,
maximum decoded messages per topic, budget exhaustion semantics, publication
schema and predecessor acceptance are **unfrozen**. The implementation must
not silently reuse the old ZstdError-only successor gate for a different
question. A failure after partial decoding is inconclusive: null full-recording
observations, with separately labelled progress/context if the contract allows
them. CRC/decompression/resource/schema failures do not prove zero usable data.
No automatic retry or threshold lowering. A report/path is preserved.

Private coordinates, absolute epochs, raw IDs/descriptor bytes, source
configuration and paths stay out of public summaries. Allowed reports carry
aggregate counts, schemas/hashes, versioned contract/runtime, provenance
availability and explicit withheld-inference flags. Exact private input
identity is checked locally; public documentation follows the existing
sanitized evidence convention.

## Required synthetic verification and order

Before implementation review: test exact recorded structural bindings and
required type drift; missing/unknown/invalid flags; empty/short/nonfinite
covariance and mode ambiguity; signed RLMB versus foresight range semantics;
uint64 IDs; duplicate/ambiguous lanes; MPP without header time; restamped held
content; ENU id reuse/reset; bounded retention/oversize chunks; selected CRC
failure/unavailable CRC; resource stops; file/registration drift; inconclusive
partial results, no publication on preflight failure and no residual/model
side effects. Add tests appropriate to the actual implemented contract.

Focused contract GO precedes implementation. Synthetic tests and exact-head
implementation GO/CI precede one reviewed private execution in a fresh path.
Reconcile that output before numerical reference construction. Do not add
arbitrary covariance thresholds, lane tie-breaking, timestamp shifts or
reference-fusion weights to make this proposal executable.
