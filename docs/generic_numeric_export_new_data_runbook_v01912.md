# Newer data to validated residuals: v0.19.12 handoff

Date: 2026-10-17. The owner reports newer manually screened downloads in Home,
each source-ID directory containing `output.mcap`. These are technical files;
download IDs, GB and a screenshot do not establish independent physical drives.
The old completed pilot is an optional engineering fixture, not a quality hurdle
or a yield forecast for this newer collection.

## Current stage and remaining work

| Stage | State |
|---|---|
| Register bytes/source declarations | Implemented, merged |
| Inventory selected schemas/topics/counts | Implemented, merged |
| Decode/integrity check | Implemented, merged |
| Bounded counts-only scientific readiness | Implemented, merged |
| Generic numeric export and standalone validation | Implementation candidate; code review/new-head CI/merge next |
| Newer-file usable-yield measurement | Await one selected newer recording and its own preserved reports |
| Generic durable catalog/session/cohort/split and training archive integration | Remaining implementation |
| Incremental acquisition/controller and verified raw retirement | Remaining lifecycle work |

Validated numeric arrays are the residual-pipeline milestone. They do not by
themselves enable real training or a final-data split. Use actual support and
provenance to decide the next acquisition, not the size of the whole collection.

## Start with a small newer selection

1. Obtain a metadata-only listing of the Home download directories, paths and
   sizes. The private delivery includes `DISCOVER_HOME_RECORDINGS.py`; it stats
   files only and neither hashes nor opens MCAP payloads. Its output is private
   and must stay outside Git. Discovery does not reserve/export a collection.
2. Select one newer recording of manageable size with an intended development
   use. Keep prospective final outings separate from numeric authorization.
   A name or chronological-looking directory does not establish a drive/date.
3. Keep that raw path stable. Use the existing merged prepare/register,
   inventory, decode-check and bounded-readiness entry points with new unique
   batch/output paths. Record known download/source IDs; leave unknown session,
   acquisition UTC and re-download evidence null. Each new file needs its own
   real predecessors. Do not reuse the old pilot's reports or rerun its stages.
4. Return the new counts-only evidence for reconciliation. A supported complete
   report establishes assessed yield, even when that yield is zero. An
   inconclusive report is unknown, not a measured zero. Unknown descriptors
   require their own evidence-backed handling; never add a root to an allowlist
   just because the data looks promising.
5. Once the numeric implementation has code GO/CI/merge, use an owner-written
   authorization for the deliberately chosen whole batch and a new versioned
   export. No current helper creates an accepted authorization. Preserve its
   bytes/digest even if unused or failed; linked outings are permanently reserved
   for development under the accepted contract.
6. Run standalone validation with the expected summary digest and unchanged
   lineage/authorization. Retain all three artifacts, receipt and predecessor
   inputs durably. The validator never authorizes raw deletion or model fitting.

The new CLI's full interfaces can be inspected without raw access:

```bash
python -m lane_residuals.cli.recording_ingestion export-residuals --help
python -m lane_residuals.cli.numeric_archive --help
```

These help commands are for implementation review. A separately pinned private
launcher for an exact selected file/source/output set follows acceptance; this
document does not issue a live private export or generate its authorization.

## How the newer data helps

SENSOR EDP plus RLMB is promising because it supplies the required estimate and
pseudo-reference streams. Measure eligible H100 geometry, complete recorded-causal
features, sequence lengths/transitions, schema/root coverage and distinct evidenced
physical outings. Retain outcome-blind, predeclared screening and rejection counts.
Do not screen by residual magnitude or model performance. RLMB stays a map-relative
pseudo-reference, not independent physical ground truth. The two explicit interface
and confidence-width assumptions remain visible before any real-fit decision.

If the first newer selection is productive, process a few more evidenced development
drives incrementally. There is no justified fixed GB target yet. The existing outing
eligibility/support rules are unchanged; file/download counts are not outing counts.
Do not export every available recording and consume the future final pool.

## Proposed private layout and lifecycle

Use lowercase `data/`, already ignored by Git. The intended layout is:

| Path | Meaning |
|---|---|
| `data/raw/raas/<source-id>/output.mcap` | One technical raw download, when placed before initial registration |
| `data/catalog/` | Durable private source, raw identity, session/alias evidence, authorizations, exposure and lifecycle records |
| `data/derived/<versioned-batch>/` | Validated numeric artifacts and their receipts/lineage |
| Existing `outputs/registrations/` and diagnostic directories | Immutable versioned predecessor reports |

Existing registered raw remains where registration pins it. New Home files may
initially stay there too; a catalog can reference an external raw cache without
copying data into the repository. Do not create ambiguous basename-only copies
or move a registered file midway through a lineage chain.

The future catalog, not an empty directory, must preserve visibility after raw
retirement: original source/download ID, exact raw SHA/size and path history,
unknown versus evidenced session links, reservation/exposure/attempt records,
archive/receipt identities, retrieval evidence and lifecycle status. Empty source
folders are optional. Do not treat a download job as a physical outing.

Automated retirement is not implemented here. It requires durable validated
outputs and tested exact-byte retrieval, then a separately reviewed/authorized
lifecycle action. AWS access alone does not prove retrievability. Preserve old
data and current raw paths until those conditions hold.
