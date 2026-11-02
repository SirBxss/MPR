# Agent handoff for metadata recovery

2 November 2026. Read AGENTS, current status, the original
[scientific protocol](direct_speed_study_v01924.md) and
[engineering correction](direct_speed_metadata_recovery_v01925.md).

PR #49 merged at 448c4f9e5c3c21f4b467a68d391eb42348b87c92 with approved
b4b327799bbef12465987a5c73685481dba976a9 tree. Independent source, protocol and
exact private helper GO and all required CI jobs were accepted. The owner's
first run returned a complete failure archive and child exit one. Verification
of its fixed source and control flow establishes a metadata only failure before
any claim, file hash, velocity payload decode or new population statistic.
The proposed claim paths in the report are not created claim files.

The defect was an unnecessary extra decoder schema traversal in the study
wrapper. Reuse the original planner's existing observer hook in its single
decoder construction traversal. Keep the default call unchanged for legacy
consumers. All limits remain unchanged. Source checks, metadata descriptors,
typed fields, qualifiers, CRC, index and file identity checks remain enforced.
Synthetic schema heavy regression tests reproduce the extra traversal failure
under the same budget and show the corrected path stays within the original
planner's byte cost. An insufficient original budget must still fail.

Preserve attempt 001 and its archive. The exact recovery helper verifies that
failure and checks actual owner claims, including matching raw identities under
other diagnostic revisions. A prior or uncertain claim stops continuation.
The unchanged scientific revision/request preserves the original window keys;
the new attempt number identifies engineering recovery and is not permission
to retry a claimed design. New independent source/helper review, current head
CI and owner merge precede the continuation command. Parent signal handling and
partial publication are tested separately. Do not widen limits, select another
window or edit the scientific request.

The longitudinal primary candidate, VehicleVelocity diagnostic control and
strict source sensitivity remain as privately declared before any new payload
result. No such result exists from this failed preflight. Keep gap failures
unknown until actual direct speed evidence; estimate feature failures remain
excluded. Later diagnostic revisions must reconcile semantic claims across
revisions. Optional order checks and plot refinements remain future work.

Four matched baselines remain complete. Both flows await first real matched
fits under existing gates, with preparation able to continue. The owner reported
additional long recordings in ID named storage. They remain future intake
candidates, outside this frozen study and without new admission or roles.
Preserve their files, original final reservations, old fits and all results.

Update README, AGENTS, current status, modeling plan, commands/contracts and
handoff after each implementation, review and result. Keep numerical details and
private digests out of public Git. Deliver a numbered source patch and a private
packet with the original failed evidence and exact recovery helper. Do not push,
open or merge externally without instruction. Main agent decisions, independent
Claude review and internal Copilot source evidence retain their separate roles.
