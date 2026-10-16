# v0.19.11 exact EDP descriptor compatibility amendment

Date: 2026-10-16. Status: **A2 PROPOSED AMENDMENT AND IMPLEMENTATION CANDIDATE**.
Focused independent amendment/implementation GO and exact-head Python 3.10/3.12
CI are required before merge and a separately versioned private successor.
Base: merged PR #35 `4cf0af37ffad05e34b632571ec271485d6de50c3`, accepted tree
`f435f2bf8e26d1e3dc114bb50b10b7ff4cc83501`.
Amendment ID: `v0.19.11-edp-exact-descriptor-compatibility-2026-10-16-a2`.

PR #36 a1 (`132e2e5`, tree `8f13bae`) received NO-GO: B-1 required reviewable
descriptor/semantic evidence; B-2 identified accidental admission by historical
consumers whose immutable lineage declares only the original pin. A2 supplies
extension-aware evidence below and scopes the additional root to bounded
readiness. It is a delta on that same PR, not a new PR or permission to merge.

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
independence or proof of physical geometry. The semantic compatibility argument
and its explicit assumption are recorded below; descriptor shape alone is not
treated as proof of producer behavior.

The proposed engineering decision is to handle this one exact schema under the
existing reviewed v2 availability/validity interpretation. It does not accept
arbitrary flag-absent or structurally similar schemas. The independent reviewer
must assess the evidence and this compatibility decision together with the code.

## Privacy-safe declaration and semantic evidence (B-1)

### Method and interface identity

The actual exported FileDescriptorSet includes the definitions of BMW's custom
options. Parsing its root using the generated `descriptor_pb2` class preserves
unknown option bytes but prints empty option blocks. Empty printed blocks do
**not** show that custom options are absent. A2 constructs the dynamic
`google.protobuf.FileDescriptorProto` class from that same descriptor pool and
parses the root again. The dynamic message serializes to the original bytes;
discarding unknown fields also leaves those bytes identical. Thus all custom
options, including nested options, are accounted for by that pool.

The message-owned root remains the exact second pin in the implementation:
file `interfaces/perception/road/estimated_drive_paths.proto`, package
`Adp.Perception`, syntax `proto3`. `system_file_options3` (extension 50030)
declares **major_version 2, minor_version 3**. No patch version is explicitly
declared. `orion_file_options1` (60030) sets memory optimization disabled;
that is not a model-validity rule. The previously reviewed BMW-source trace
records version **2.2.0**, so the observed root retains the same declared major
version. This is evidence of its declaration, not an independently verified
deployed producer/build identity.

### Consumed bindings

All singular scalar and enum fields below have implicit proto3 presence:
`proto3_optional` is false and runtime `has_presence` is false. Singular message
fields have explicit presence. Repeated fields have cardinality/emptiness,
without a singular presence bit. BMW's description of a required model is an
interface requirement, **not** Protobuf's proto2 required wire label.

| Message.field | Number | Protobuf type/cardinality | Presence |
|---|---:|---|---|
| EstimatedDrivePaths.time_stamp | 1 | sint64, singular | implicit |
| EstimatedDrivePaths.drive_paths | 4 | DrivePath, repeated | repeated |
| EstimatedDrivePaths.topology_source | 5 | RoadTopologySource enum, singular | implicit |
| DrivePath.error | 1 | DrivePathError enum, singular | implicit |
| DrivePath.role | 2 | LaneRole enum, singular | implicit |
| DrivePath.model_parameters | 3 | ClothoidSplineMinimalParameters, singular | explicit |
| DrivePath.drive_path_confidences | 7 | double, repeated | repeated |
| ClothoidSplineMinimalParameters.x_0 | 1 | double, singular | implicit |
| ClothoidSplineMinimalParameters.y_0 | 2 | double, singular | implicit |
| ClothoidSplineMinimalParameters.theta_0 | 3 | double, singular | implicit |
| ClothoidSplineMinimalParameters.curvature_0 | 4 | double, singular | implicit |
| ClothoidSplineMinimalParameters.segment_starts | 5 | double, repeated | repeated |
| ClothoidSplineMinimalParameters.curvature_change | 6 | double, repeated | repeated |
| ClothoidSplineMinimalParameters.index_0 | 7 | int64, singular | implicit |

`DrivePath` has neither field 8 nor the name `model_parameters_optional_flag`.
Neither the number nor name is reserved, and neither is reused. This does not
authorize future roots. The dynamic custom options on `model_parameters`
describe it as required. No optional wrapper or validity-field binding is set
anywhere in this EDP root: `orion_field_options1.use_amp_optional` defaults to
false, and the system/run `validity_field_name` defaults to an empty string.
Other observed field options specify descriptions, units, suggested defaults,
static vectors, alias names and maximum counts. They introduce no substitute
model-validity signal. Units remain meters for initial x/y and segment starts,
radians for heading, inverse meters for curvature, inverse square meters for
curvature change, and nanoseconds for the source clock.

### Enum/default facts

| Enum | Relevant declaration | Unset implicit value |
|---|---|---|
| DrivePathError | `DRIVE_PATH_ERROR_NO_ERROR = 7`; `DRIVE_PATH_ERROR_CROSSES_ITSELF = 1` | `DRIVE_PATH_ERROR_UNINITIALIZED = 0`, rejected |
| LaneRole | `LANE_ROLE_KEEP_LANE = 1` | `LANE_ROLE_UNKNOWN = 0`, not selected |
| RoadTopologySource | `ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY = 4`; LANE_MAP = 3 | UNKNOWN = 0, rejected |

DrivePathError declares values 0 through 18; every value except exact NO_ERROR
is rejected. LaneRole declares 0 through 9; only a unique KEEP_LANE is selected.
RoadTopologySource declares UNKNOWN/CROC/ODOMETRY/LANE_MAP/SENSOR_TOPOLOGY as
0/1/2/3/4. No success/KEEP_LANE/SENSOR symbol has numeric value zero, so implicit
defaults cannot authorize an unset path. Production resolves symbols rather
than assuming the simplified fixtures' numeric success value. A2 adds an
explicit NO_ERROR=7/failure=1/unset-error/unset-role regression.

### Comparison boundary and semantic basis

Every consumed binding listed in the committed v0.17.1 table has the same
name, number, type and cardinality here; the old flag is still absent. The old
table's non-consumed fields `considered_objects_range` (10, singular Range) and
`raw_lane_topology_ids` (11, repeated uint64) are present as described.
Additional declarations visible here but not enumerated in that old table are
DrivePath lane_topology_ids (4, repeated uint64), estimation_age (5, uint64),
distance_driven_since_last_external_constraint (6, double),
sensor_boundary_cut_off_distance (9, double), and root qualifiers (2/3) and
considered_objects (6). Their presence is **not** proof that they were added
since the old root. The old record does not enumerate the full enum or custom
option sets either; those full old/new differences cannot be reconstructed
without the old bytes. No consumed rename/removal/type change is observed
against the published table. No claim of an exhaustive whole-file diff is made.

The engineering argument uses review option B-1(3)(b):

1. The actual root declares major 2/minor 3, retaining the major version of the
   reviewed 2.2.0 producer/source trace in `bmw_edp_schema_evidence.md`.
2. Its decoded options still require model parameters and provide no removed
   optional-wrapper/validity-field mechanism. Its explicit message presence,
   exact nonzero success enum, geometry units and all consumed fields match
   the established v2 consumer interpretation.
3. The accepted BMW-source record reports that `interfaces/README.md`
   classifies semantic-meaning changes as major breaks. **Assumption:** the
   producer/interface authors followed that policy for this minor revision.
   The old source trace supports how v2 availability and errors are used;
   this export does not independently re-trace the deployed producer.
4. Consequently the proposed bounded consumer retains explicit model presence
   AND exact NO_ERROR AND all fixed numeric/geometry/feature checks. Parameter
   presence alone never proves validity. No residual or model outcome was
   inspected to choose this policy.

Residual risk is an undocumented producer semantic change or version-policy
violation. This argument is offered explicitly for independent review, not
asserted as a new producer-source fact. A stronger deployed-source trace may
be required if the reviewer finds a concrete inconsistency. B-1 is not marked
independently closed until the reviewer receives the actual evidence bundle
and assesses this argument. The portable private reproducer verifies the
version, custom options, defaults, identities, historical rejection and
bounded conformance without opening any recorded message payload.

## Exact generation change

Preserve the original public compatibility constant unchanged:
`ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256`.
Add one second software-schema compatibility identity:
`ADDITIONAL_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256`, whose exact value is
in `domain/path_source_probe.py`. This compatibility identity is necessary to
specify the proposed software policy; it is not a raw-recording identity.
No private schema files or recording identities are committed.

Compute the fingerprint only from the message's own serialized file descriptor,
as before. The original pin selects `candidate_v2` by default. The additional
pin selects it only under the keyword-only Boolean
`allow_bounded_v01911_edp=True`; both require the legacy flag absent and `index_0`
to remain
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
`v0.19.11-bounded-recording-readiness-2026-10-16-a2`; source fingerprints naturally
reflect changed code. The CLI name remains `bounded-readiness`, and the disk-
index reader/default decoding revision is unchanged. Registration, inventory,
decode and historical report contracts are unchanged and their artifacts stay
immutable. The original a4 draft and v0.17.1 amendment are retained byte-for-byte;
this document is the explicit successor amendment, not a silent edit to them.

### Consumer-scoped correction and reviewed scope expansion (B-2)

The shared classifier, geometry conversion, descriptor precheck and geometry
iterator all default to the historical v0.17.1 policy. The Boolean opt-in is
threaded through these existing layers; only `ScientificSink` supplies true,
at schema registration, late descriptor rechecks and geometry consumption.
It is not a root list or a CLI/config/environment/metadata switch. The v0.17
lock's real technical inspector rejects the additional root and cannot turn
it into eligible geometry. Its old lineage, verifier and output schemas remain
byte-identical. The closed v0.18 consumer and other historical callers keep
their default behavior too.

A2 explicitly expands the original two-source-file scope to **five** paths:
`domain/path_source_probe.py`, `domain/geometry_validation.py`,
`domain/recording_readiness_bindings.py`, `io/independent_outing_intake.py`,
and `io/bounded_recording_readiness.py`. The extra three paths only thread
the default-false policy; no historical workflow, import graph, geometry
arithmetic, reader, resource limit or output contract changes. The runbook
enforces these exact paths and exact test paths. This scope note and the
regression tests are part of focused a2 review.

This does not reopen closed cohorts or authorize old diagnostic reruns, role
locks, real fits, model comparison or raw retirement. Fixed 21-station signed target,
pseudo-reference interpretation, six causal inputs, no extrapolation and all
session/split gates remain unchanged.

## Verification and next action

Fifteen synthetic tests cover the second entry separately from the original,
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
