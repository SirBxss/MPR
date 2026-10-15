# Data completion and next-agent handoff: 2026-10-15

PR #34 is merged at `0f2950e2b76b823fabea0b67309b268afe205806`, accepted a4
tree `4100debbc422558b0a049a96aaa7a97f340d7064`. The bounded scientific
readiness implementation is prepared on that base; read
[its implementation record](generic_bounded_readiness_v01910.md) before work.
Implementation GO/new-head CI/merge and a private counts-only pilot remain ahead.
No new private result, numeric dataset or trained model exists at this checkpoint.

## What the new collection establishes so far

One new development recording has complete registration, summary inventory
and selected EDP/RLMB/odometry decoding evidence. The container/serialization
pipeline works on it. The owner's SENSOR-only description is acquisition
context; its actual topology fraction, valid H100 pairs, complete causal rows,
sequence lengths and physical-session independence remain unmeasured.
Do not replace unknown counts with zero or infer yield from file size.

The new readiness command separates each stage so the pilot can answer:

| Pilot result | Acquisition consequence |
|---|---|
| Many SENSOR H100 pairs and complete rows with long sequences | Process a small next set from distinct, evidenced physical sessions; preserve those declarations before expanding |
| Good geometry but large feature rejection | Inspect the reported confidence/odometry/causality causes before bulk acquisition |
| Low H100 coverage or poor alignment | Inspect the geometry attrition; a larger download of equivalent files may repeat the same limitation |
| Unsupported binding or execution failure | Yield remains unknown; correct the evidenced compatibility/resource issue under review |
| Many rows from one session | Useful development density, still insufficient evidence for independent held-out outings |

No fixed fraction of the entire collection is justified yet. Once results exist,
estimate rows per processed byte and sequence support per physical session, then
plan a small incremental batch. Reassess after each batch rather than acquiring
the entire collection first. Source/job/session/interval identifiers must remain
distinct; one downloadable ID or merged file is not automatically one outing.

## Shortest remaining route to a usable training dataset

1. Review/CI/merge the bounded consumer; execute one fresh versioned counts-only
   pilot on the already registered new recording. Preserve old reports and paths.
2. From reviewed pilot evidence, specify/implement the generic numeric exporter
   and strict archive validator, reusing the same geometry/features and exact
   registered identities. Archive separate SENSOR H100 profiles and the complete
   six-feature subset, with provenance and recording-local sequence boundaries.
3. Process additional evidenced sessions incrementally, predeclare the actual
   matched cohort and train/validation/test roles, and satisfy existing model/
   independent-outing/sequence gates. Then execute the reviewed real fits on
   identical eligible rows and splits. Abundant raw bytes alone do not close
   those gates; this implementation does not change them.

The archive/validator is the next generic data consumer after readiness. Full
download orchestration is not required to begin that work. Automated retirement
can follow after exact-byte re-download evidence and archive validation exist.

## Storage direction after a successful pilot

Prefer lowercase `data/` and one persistent private source catalogue record per
downloaded source ID. Its existence can preserve visibility after raw retirement;
empty folders alone cannot preserve lineage. The future catalogue should retain
the source/job/session/interval distinction, declared physical-session evidence,
part order/merge recipe, exact hashes/sizes, pipeline-result identities, numeric
archive validation and tested retrieval evidence. Unavailable evidence stays null.

Continue the existing prospective layout: `data/catalog/<source_id>.json` for
retained private source state/provenance, and
`data/raw/raas/<source-session>/<session-interval>/<job-id>/output.mcap` for
future raw cache. These are provider identities, not inferred physical outings.
Use `data/derived/` for validated numeric archives and existing versioned
`outputs/` paths for registrations/diagnostics. All private catalogue/raw/numeric
evidence stays outside public Git. This is a direction, not a new catalogue
schema or implemented migration.

Keep the current registered external raw path in place. Later metadata belongs
in a private supplement or reviewed successor, not edits to immutable source
specifications. Do not delete old or new raw data until the reviewed archive-
validation and exact-byte retrieval/retirement gates are implemented and pass.
An automated controller must own only explicit cache entries, never broad
directory wipes. No raw deletion is authorized by readiness completion.

## Scientific boundaries

Retain SENSOR admission, full original timestamp pairing before filtering,
the 21-station signed EDP-minus-aligned-RLMB target with no extrapolation,
the anchor limit, fixed six causal inputs and recording-local sequences.
RLMB is a map-relative pseudo-reference; shared producer dependencies remain
material. No all-topology target change, physical ground-truth claim, inferred
outing independence, role lock, real flow fit or model comparison follows
from decoding, the contract GO, or the new implementation alone.
