"""Synthetic support/identity fixtures for the prospective generic split policy."""

from copy import deepcopy
import unittest

from lane_residuals.domain import generic_cohort as policy
from lane_residuals.domain.artifact_registry import build_index, RegistryError
from tests.domain.test_artifact_registry import declared, link


def fixture(count=9, reserved=(0,)):
    raws = [f"{i + 1:064x}" for i in range(count)]
    registrations = [declared(raw, f"{100 + i:064x}", source_recording_id_private=f"folder-{i}")
                     for i, raw in enumerate(raws)]
    auth = [("a" * 64, {"authorized_raw_sha256": [raws[i] for i in reserved]})] if reserved else []
    metadata = {"records": build_index(registrations, auth, [], [], {}), "events": []}
    declaration = {"contract_revision": policy.DECLARATION_REVISION,
        "purpose": "owner_declared_physical_session_membership", "evidence_status": policy.EVIDENCE_STATUS,
        "declaration_text_private": "Synthetic owner declares these distinct physical sessions.",
        "independence_basis_private": "Synthetic independent drive fixture.",
        "outings": [{"session_id_private": f"folder-{i}", "separate_physical_session": True, "raw_sha256": [raw]}
                    for i, raw in enumerate(raws)]}
    manifest = {"contract_revision": policy.REVISION, "registry_sha256": "a" * 64,
        "session_declaration_sha256": "b" * 64, "scope_raw_sha256": raws,
        "readiness_by_raw_sha256": {raw: "d" * 64 for raw in raws},
        "legacy_development_outing_count": 1, "prior_successful_lock_sha256": None}
    support = {raw: {"raw_usable": True, "source_start_ns": 1_000_000_000,
        "source_stop_ns": 121_000_000_000, "complete_frame_count": 500, "complete_sequence_count": 500,
        "complete_transition_count": 0, "topology_candidate_count": 600,
        "non_sensor_topology_candidate_count": 0} for raw in raws}
    return raws, metadata, declaration, manifest, support


def build(values):
    _, metadata, declaration, manifest, support = values
    return policy.build_cohort(metadata, declaration, manifest, support,
                              registry_pin="a" * 64, declaration_pin="b" * 64, manifest_pin="c" * 64)


class GenericCohortPolicyTests(unittest.TestCase):
    def test_owner_labels_and_unchanged_thresholds_make_nine_eligible_outings(self):
        values = fixture()
        result = build(values)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["eligible_new_outing_count"], 9)
        self.assertEqual(result["required_final_count"], 2)
        self.assertEqual(result["unexposed_eligible_final_pool_count"], 8)
        self.assertEqual(sum(o["cohort_role"] == "final_test" for o in result["outings"]), 2)
        self.assertTrue(result["roles_assigned"])
        self.assertFalse(result["model_admission_authorized"])
        self.assertFalse(result["physical_independence_independently_verified"])
        self.assertEqual(result["session_evidence_status"], policy.EVIDENCE_STATUS)

    def test_short_sequences_do_not_add_a_new_contiguous_duration_gate(self):
        result = build(fixture())
        self.assertTrue(all(o["technically_eligible"] for o in result["outings"]))
        self.assertTrue(all(o["support"]["sequence_count"] == 500 for o in result["outings"]))

    def test_120_second_and_500_frame_boundaries_are_not_relaxed(self):
        for key, value, code in [("source_stop_ns", 120_999_999_999, "usable_duration_below_120s"),
                                 ("complete_frame_count", 499, "eligible_frame_count_below_500")]:
            values = fixture()
            values[4][values[0][0]][key] = value
            result = build(values)
            row = next(o for o in result["outings"] if o["session_id_private"] == "folder-0")
            self.assertFalse(row["technically_eligible"])
            self.assertIn(code, row["failure_codes"])

    def test_any_non_sensor_h100_candidate_excludes_the_whole_outing(self):
        values = fixture()
        values[4][values[0][1]]["non_sensor_topology_candidate_count"] = 1
        result = build(values)
        self.assertFalse(next(o for o in result["outings"] if o["session_id_private"] == "folder-1")["technically_eligible"])

    def test_no_roles_with_six_eligible_new_outings(self):
        result = build(fixture(count=6))
        self.assertEqual(result["status"], "insufficient_independent_outings")
        self.assertTrue(all(o["cohort_role"] is None for o in result["outings"]))

    def test_reserved_outing_never_enters_final_even_when_its_score_is_lowest(self):
        values = fixture(reserved=())
        first = min(build(values)["outings"], key=lambda o: o["split_score_sha256"])["raw_sha256"][0]
        next(r for r in values[1]["records"] if r["raw_sha256"] == first)["permanent_development_reservation"] = True
        result = build(values)
        self.assertEqual(next(o for o in result["outings"] if first in o["raw_sha256"])["cohort_role"], "development")

    def test_unrun_reservations_and_publications_both_exclude_from_final(self):
        for key in ("permanent_development_reservation", "complete_publication_observed", "linked_development_exclusion"):
            values = fixture(reserved=())
            for row in values[1]["records"]:
                row[key] = True
            result = build(values)
            self.assertEqual(result["status"], "insufficient_unexposed_final_outings")
            self.assertFalse(result["roles_assigned"])

    def test_folder_renames_and_input_order_do_not_reroll_roles(self):
        values = fixture()
        original = {o["outing_fingerprint_sha256"]: (o["cohort_role"], o["outing_id"]) for o in build(values)["outings"]}
        changed = deepcopy(values)
        changed[2]["outings"].reverse()
        for i, outing in enumerate(changed[2]["outings"]):
            outing["session_id_private"] = f"renamed-{i}"
        now = {o["outing_fingerprint_sha256"]: (o["cohort_role"], o["outing_id"]) for o in build(changed)["outings"]}
        self.assertEqual(original, now)

    def test_one_raw_cannot_be_declared_as_two_independent_outings(self):
        values = fixture()
        values[2]["outings"][1]["raw_sha256"] = values[2]["outings"][0]["raw_sha256"]
        with self.assertRaisesRegex(RegistryError, "duplicate_raw"):
            build(values)

    def test_labels_alone_without_literal_owner_declaration_are_rejected(self):
        for wrong in (False, 1, "true"):
            values = fixture()
            values[2]["outings"][0]["separate_physical_session"] = wrong
            with self.assertRaises(RegistryError):
                build(values)

    def test_shared_source_id_contradictions_block_two_distinct_owner_sessions(self):
        values = fixture()
        values[1]["records"][1]["source_locators"] = deepcopy(values[1]["records"][0]["source_locators"])
        result = build(values)
        bad = [o for o in result["outings"] if o["session_id_private"] in {"folder-0", "folder-1"}]
        self.assertTrue(all("cross_raw_session_identity_conflict" in o["failure_codes"] for o in bad))
        self.assertTrue(all(o["linked_development_exclusion"] for o in bad))

    def test_confirmed_cross_raw_link_contradictions_block_admission(self):
        values = fixture()
        values[1]["events"] = [{"kind": "relationship", "claim": link("raw:" + values[0][0], "raw:" + values[0][1])}]
        result = build(values)
        self.assertTrue(all(not o["technically_eligible"] for o in result["outings"] if
                            o["session_id_private"] in {"folder-0", "folder-1"}))

    def test_unresolved_link_is_not_confirmed_identity_but_cannot_cross_folds(self):
        values = fixture()
        values[1]["events"] = [{"kind": "relationship", "claim": link("raw:" + values[0][0], "raw:" + values[0][1], "unresolved")}]
        graph = policy.identity_components(values[1], policy.parse_declaration(values[2], set(values[0])))
        self.assertFalse(graph[values[0][0]]["identity_conflict"])
        self.assertTrue(graph[values[0][0]]["session_link_unresolved"])
        result = build(values)
        self.assertTrue(all(not o["technically_eligible"] for o in result["outings"] if
                            o["session_id_private"] in {"folder-0", "folder-1"}))

    def test_broad_locator_is_possible_only_and_remains_conservative(self):
        values = fixture()
        for row in values[1]["records"][:2]:
            row["source_locators"][0]["source_locator_private"] = "a shared folder"
        membership = policy.parse_declaration(values[2], set(values[0]))
        graph = policy.identity_components(values[1], membership)
        self.assertFalse(graph[values[0][0]]["identity_conflict"])
        self.assertTrue(graph[values[0][0]]["session_link_unresolved"])
        self.assertTrue(graph[values[0][1]]["linked_development_exclusion"])

    def test_same_identity_with_two_source_session_assertions_is_conflicting(self):
        values = fixture()
        for i, row in enumerate(values[1]["records"][:2]):
            row["source_locators"][0].update(source_recording_id_private="same technical source", physical_session_id_private=f"P{i}")
        graph = policy.identity_components(values[1], policy.parse_declaration(values[2], set(values[0])))
        self.assertTrue(graph[values[0][0]]["identity_conflict"])
        self.assertTrue(graph[values[0][1]]["identity_conflict"])

    def test_grouped_files_count_as_one_outing_and_overlaps_fail(self):
        values = fixture()
        first, second = values[2]["outings"][:2]
        first["raw_sha256"] += second["raw_sha256"]
        values[2]["outings"].remove(second)
        result = build(values)
        row = next(o for o in result["outings"] if o["session_id_private"] == "folder-0")
        self.assertIn("usable_source_intervals_overlap_or_are_not_monotonic", row["failure_codes"])
        self.assertEqual(result["eligible_new_outing_count"], 7)

    def test_touching_multifile_intervals_fail_but_one_nanosecond_separation_passes(self):
        values = fixture()
        first, second = values[2]["outings"][:2]
        first["raw_sha256"] += second["raw_sha256"]
        values[2]["outings"].remove(second)
        raw = values[0][1]
        stop = values[4][values[0][0]]["source_stop_ns"]
        values[4][raw].update(source_start_ns=stop, source_stop_ns=stop + 120_000_000_000)
        row = next(o for o in build(values)["outings"] if o["session_id_private"] == "folder-0")
        self.assertIn("usable_source_intervals_overlap_or_are_not_monotonic", row["failure_codes"])
        values[4][raw].update(source_start_ns=stop + 1, source_stop_ns=stop + 120_000_000_001)
        row = next(o for o in build(values)["outings"] if o["session_id_private"] == "folder-0")
        self.assertTrue(row["technically_eligible"])

    def test_partial_outing_scope_and_non_null_prior_lock_are_rejected(self):
        values = fixture()
        first, second = values[2]["outings"][:2]
        first["raw_sha256"] += second["raw_sha256"]
        values[2]["outings"].remove(second)
        raw = values[0][1]
        values[3]["scope_raw_sha256"].remove(raw)
        del values[3]["readiness_by_raw_sha256"][raw]
        del values[4][raw]
        with self.assertRaisesRegex(RegistryError, "partial_physical"):
            build(values)
        values = fixture()
        values[3]["prior_successful_lock_sha256"] = "d" * 64
        with self.assertRaisesRegex(RegistryError, "supersession"):
            build(values)
