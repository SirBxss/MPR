"""Reservation/session graph tests use synthetic identity strings only."""

import unittest

from lane_residuals.domain.artifact_registry import build_index, RegistryError

A, B, C = "a"*64, "b"*64, "c"*64


def link(left, right, status="confirmed"):
    return dict(left=left, right=right, status=status, evidence_sha256=["e"*64])


def declared(raw, pin, **source):
    return ({"recordings":[{"source":source}]},
        {"batch_id":"synthetic", "source_specification_sha256":pin,
         "recordings":[dict(raw_sha256=raw,size_bytes=123,recording_id="recording",canonical_path_private="/synthetic/"+raw)]},pin)


class RegistryGraphTests(unittest.TestCase):
    def test_download_aliases_carry_exclusion_in_both_directions_without_session_identity(self):
        for key in ("source_recording_id_private", "source_locator_private"):
            for reserved in (A, B):
                with self.subTest(key=key,reserved=reserved):
                    regs=[declared(A,"1"*64,**{key:"same locator"}),declared(B,"2"*64,**{key:"same locator"})]
                    rows=build_index(regs,[("3"*64,{"authorized_raw_sha256":[reserved]})],[],[],{})
                    self.assertTrue(all(r["linked_development_exclusion"] and r["session_link_unresolved"] for r in rows))
                    self.assertTrue(all(r["declared_physical_session_ids"]==[] for r in rows))
                    self.assertFalse(any(r["independent_outing_admitted"] for r in rows))

    def test_confirmed_session_on_download_alias_cannot_restore_final_eligibility(self):
        regs=[declared(A,"1"*64,source_recording_id_private="download"),
            declared(B,"2"*64,source_recording_id_private="download")]
        rows=build_index(regs,[("3"*64,{"authorized_raw_sha256":[A]})],[],[link("raw:"+B,"session:fresh")],{})
        other=next(r for r in rows if r["raw_sha256"]==B)
        self.assertEqual(other["final_candidate_status"],"excluded_development")
        self.assertTrue(other["session_link_unresolved"])
        self.assertEqual(other["declared_physical_session_ids"],["fresh"])

    def test_single_download_locator_is_not_session_evidence(self):
        rows=build_index([declared(A,"1"*64,source_recording_id_private="download")],[],[],[],{})
        self.assertFalse(rows[0]["session_link_unresolved"])
        self.assertTrue(rows[0]["session_evidence_absent"])
        self.assertFalse(rows[0]["linked_development_exclusion"])
        self.assertEqual(rows[0]["declared_physical_session_ids"],[])

    def test_locator_groups_are_exact_and_exclusion_propagates_transitively(self):
        regs=[declared(A,"1"*64,source_recording_id_private="download"),
            declared(B,"2"*64,source_recording_id_private="download",source_locator_private="uri"),
            declared(C,"3"*64,source_locator_private="uri")]
        rows=build_index(regs,[("4"*64,{"authorized_raw_sha256":[A]})],[],[],{})
        self.assertTrue(all(r["linked_development_exclusion"] for r in rows))
        rows=build_index([declared(A,"1"*64,source_locator_private="uri"),
            declared(B,"2"*64,source_locator_private="uri ")],[("3"*64,{"authorized_raw_sha256":[A]})],[],[],{})
        self.assertFalse(next(r for r in rows if r["raw_sha256"]==B)["linked_development_exclusion"])

    def test_contradictory_source_sessions_block_the_entire_possible_component(self):
        regs=[declared(A,"1"*64,physical_session_id_private="one"),
            declared(A,"2"*64,physical_session_id_private="two"),
            declared(B,"3"*64,physical_session_id_private="one")]
        rows=build_index(regs,[],[],[],{})
        self.assertTrue(all(r["session_link_conflict"] for r in rows))
        self.assertTrue(all(r["final_candidate_status"]=="blocked_session_conflict" for r in rows))
        self.assertEqual(rows[0]["source_declared_physical_session_ids"],["one","two"])

    def test_possible_session_evidence_is_distinct_from_absent_evidence(self):
        rows=build_index([],[],[],[link("raw:"+A,"session:possible","unresolved")],{})
        self.assertTrue(rows[0]["session_link_unresolved"])
        self.assertFalse(rows[0]["session_evidence_absent"])

    def test_unrun_authorization_reserves_unknown_raw_and_no_role(self):
        rows = build_index([], [("d"*64, {"authorized_raw_sha256":[A]})], [], [], {})
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["permanent_development_reservation"])
        self.assertFalse(rows[0]["complete_publication_observed"])
        self.assertIsNone(rows[0]["size_bytes"])
        self.assertEqual(rows[0]["declared_physical_session_ids"], [])
        self.assertIsNone(rows[0]["cohort_role"])
        self.assertEqual(rows[0]["final_candidate_status"], "excluded_development")

    def test_confirmed_session_aliases_propagate_reservation_transitively(self):
        links = [link("raw:"+A,"session:one"), link("session:one","session:two"), link("session:two","raw:"+B), link("raw:"+B,"raw:"+C)]
        rows = build_index([], [("d"*64,{"authorized_raw_sha256":[A]})], [], links, {})
        self.assertTrue(all(r["linked_development_exclusion"] for r in rows))
        self.assertFalse(any(r["session_link_conflict"] for r in rows))
        self.assertTrue(all(r["declared_physical_session_ids"] == ["one","two"] for r in rows))
        self.assertFalse(any(r["independent_outing_admitted"] for r in rows))

    def test_unresolved_link_blocks_final_without_asserting_session_identity(self):
        rows = build_index([], [("d"*64,{"authorized_raw_sha256":[A]})], [], [link("raw:"+A,"raw:"+B,"unresolved")], {})
        second = next(r for r in rows if r["raw_sha256"]==B)
        self.assertTrue(second["linked_development_exclusion"])
        self.assertTrue(second["session_link_unresolved"])
        self.assertFalse(second["permanent_development_reservation"])
        self.assertEqual(second["declared_physical_session_ids"], [])

    def test_two_unaliased_session_claims_are_conflict(self):
        rows = build_index([],[],[],[link("raw:"+A,"session:one"),link("raw:"+A,"session:two")],{})
        self.assertTrue(rows[0]["session_link_conflict"])
        self.assertEqual(rows[0]["final_candidate_status"], "blocked_session_conflict")

    def test_explicit_conflict_carries_conservative_exclusion(self):
        rows = build_index([],[("d"*64,{"authorized_raw_sha256":[A]})],[],[link("raw:"+A,"raw:"+B,"conflicting")],{})
        self.assertTrue(all(r["session_link_conflict"] and r["linked_development_exclusion"] for r in rows))

    def test_publication_cannot_exist_without_matching_authorization(self):
        summary = {"recordings":[{"raw_sha256":A}],"exposure_authorization_sha256":"f"*64}
        with self.assertRaises(RegistryError):
            build_index([],[],[("e"*64,summary)],[],{})

    def test_missing_link_evidence_and_locator_node_are_rejected(self):
        for value in [dict(left="raw:"+A,right="session:one",status="confirmed",evidence_sha256=[]),
                link("raw:"+A,"raas:download")]:
            with self.subTest(value=value), self.assertRaises(RegistryError):
                build_index([],[],[],[value],{})

    def test_existing_source_session_declarations_carry_conservative_exclusion(self):
        def registration(raw,pin):
            source=dict(physical_session_id_private="same session: Δ",physical_session_evidence_private="owner declaration")
            return ({"recordings":[{"source":source}]},{"batch_id":"synthetic","source_specification_sha256":"e"*64,
                "recordings":[dict(raw_sha256=raw,size_bytes=123,recording_id="recording",canonical_path_private="/synthetic/"+raw)]},pin)
        rows=build_index([registration(A,"1"*64),registration(B,"2"*64)],[("3"*64,{"authorized_raw_sha256":[A]})],[],[],{})
        other=next(r for r in rows if r["raw_sha256"]==B)
        self.assertTrue(other["linked_development_exclusion"])
        self.assertTrue(other["session_link_unresolved"])
        self.assertEqual(other["declared_physical_session_ids"],[])
        self.assertEqual(other["source_declared_physical_session_ids"],["same session: Δ"])
        self.assertFalse(other["independent_outing_admitted"])
