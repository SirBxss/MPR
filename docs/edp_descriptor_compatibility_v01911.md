# v0.19.11 exact EDP descriptor compatibility amendment

Date: 2026-10-15. Status: **PROPOSED AMENDMENT AND IMPLEMENTATION CANDIDATE**.
Focused independent amendment/implementation GO and exact-head Python 3.10/3.12
CI are required before merge and a separately versioned private successor.
Base: merged PR #35 `4cf0af37ffad05e34b632571ec271485d6de50c3`, accepted tree
`f435f2bf8e26d1e3dc114bb50b10b7ff4cc83501`.
Amendment ID: `v0.19.11-edp-exact-descriptor-compatibility-2026-10-15-a1`.

## Evidence and decision

The new development recording's bounded pilot stopped at unsupported EDP
descriptor generation. Complete selected decoding/CRC/count evidence reconciled;
RLMB/odometry bindings passed. The owner then supplied a summary-only embedded-
descriptor export, linked to that preserved result and original inventory.
Codex reconciled ZIP manifests, Schema-record hashes, message-owned root hashes,
source identity and predecessor lineage. No private recorded payload was read.
Exact private receipts, counts, IDs, paths and full schema bytes stay outside Git.

The EDP root omits legacy `model_parameters_optional_flag` and retains the consumed
v2 path/model/index/confidence and additional clock/topology/qualifier bindings.
Its actual root bytes equal both the embedded FileDescriptorSet member and the
owner/local message-owned `DESCRIPTOR.file.serialized_pb`; the difference is not
a demonstrated Protobuf-runtime hashing artifact. The old approved root bytes
were not supplied, so this is not a claimed whole-file byte diff against them.
The comparison is to the already reviewed v2 consumed-field/presence contract.

An isolated descriptor-only experiment using the existing v2 policy passed all
remaining consumer bindings. The implementation candidate then passes every
actual exported descriptor without a policy override. A synthetic MCAP using
that exact EDP schema, synthetic values and synthetic reference/odometry fixtures
passes the unchanged geometry and conditions. Explicit model absence remains
invalid. These are conformance checks, not measured private data yield, producer
independence or proof of physical geometry. Any semantic inference beyond the
existing v2 interpretation remains outside this amendment.

The proposed engineering decision is to handle this one exact schema under the
existing reviewed v2 availability/validity interpretation. It does not accept
arbitrary flag-absent or structurally similar schemas. The independent reviewer
must assess the evidence and this compatibility decision together with the code.

## Exact generation change

Preserve the original public compatibility constant unchanged:
`ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256`.
Add one second software-schema compatibility identity:
`ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256`, whose exact value is
in `domain/path_source_probe.py`. This compatibility identity is necessary to
specify the proposed software policy; it is not a raw-recording identity.
No private schema files or recording identities are committed.

Compute the fingerprint only from the message's own serialized file descriptor,
as before. Membership in either of these two fixed values selects
`candidate_v2`; both require the legacy flag to be absent and `index_0` to remain
singular int64 field 7. Required consumer bindings remain mandatory. Other
flag-absent roots, even with identical consumed fields or a changed unrelated
file declaration, remain unsupported. Caller hashes, MCAP FileDescriptorSet
hashes and payload qualifiers cannot authorize a generation. There is no CLI,
config-file, environment-variable or metadata override.

The `candidate_v2` label and exact observed root hash remain separate: the label
expresses shared policy; the hash preserves which schema was encountered. Keep
the existing structural legacy branch and all v0.17.1 per-path rules unchanged:
unique KEEP_LANE; exact NO_ERROR symbol, not any nonzero value; explicit model
submessage presence for v2; finite/scalar/interval/index validation; unchanged
primary SENSOR admission. Enum meanings are resolved by recorded symbols, not
hard-coded numeric error values. Confidence fields and all a4 consumer checks
remain required. Invalid values on supported fields remain data rejection.

## Output and historical boundaries

The bounded report keeps the existing keys, count arithmetic, source identities,
resource limits and complete/null/odometry/attrition policies. Only
`contract_revision` and `scientific_adapter_revision` become
`v0.19.11-bounded-recording-readiness-2026-10-15-a1`; source fingerprints naturally
reflect changed code. The CLI name remains `bounded-readiness`, and the disk-
index reader/default decoding revision is unchanged. Registration, inventory,
decode and historical report contracts are unchanged and their artifacts stay
immutable. The original a4 draft and v0.17.1 amendment are retained byte-for-byte;
this document is the explicit successor amendment, not a silent edit to them.

The shared generation classifier is also used by historical converters. Their
behavior on all previously recognized inputs is unchanged; this intentionally
adds the second exact root if encountered by any later authorized caller. It
does not reopen closed cohorts or authorize old diagnostic reruns, role locks,
real fits, model comparison or raw retirement. Fixed 21-station signed target,
pseudo-reference interpretation, six causal inputs, no extrapolation and all
session/split gates remain unchanged.

## Verification and next action

Ten new synthetic tests cover the second entry separately from the original,
unknown/mutated/caller-forged identities, flag/index guards, explicit presence,
error/SENSOR policy, remaining consumer bindings, native MCAP complete/null
behavior and invalid confidence values. Synthetic pins are patched only in tests;
private descriptors are not committed. The delivered validation additionally
uses the privately supplied actual descriptors with synthetic values, without
reading private recorded messages. All real full-suite, focused, private-schema
conformance and intercepted command-simulation evidence is distinguished there.

Use the delivered runbook to apply/test/push a new PR. Ask for focused GO on both
this amendment and its implementation, inspect exact new-head CI, then merge.
A later owner command must use a new v0.19.11 output and retain the old inconclusive
report/digest in its receipt. Reuse the same registration and successful inventory/
decode evidence; do not rerun or overwrite those stages. Actual usable geometry,
causal-feature and sequence yield remain unknown until that successor completes.
Generic numeric export/strict validation is the following consumer.
