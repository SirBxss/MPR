from __future__ import annotations

import hashlib
import json
import math
import unittest
from pathlib import Path

from lane_residuals.domain.independent_outing_intake import (
    MANIFEST_PURPOSE,
    SPLIT_SALT,
    FrameTechnicalEvidence,
    OutingEligibilityEvidence,
    assign_cohorts,
    evaluate_outing_eligibility,
    fixed_final_count,
    outing_fingerprint_sha256,
    parse_acquisition_manifest,
    split_score_sha256,
)


def _manifest() -> dict[str, object]:
    return {
        "version": "0.17",
        "purpose": MANIFEST_PURPOSE,
        "acquisition_batch_closed": True,
        "created_before_outcome_inspection": True,
        "legacy_development_outing_count": 1,
        "prior_successful_lock_sha256": None,
        "superseding_contract_amendment_id": None,
        "outings": [
            {
                "private_outing_label": "private-a",
                "acquisition_start_utc": "2026-09-03T10:00:00+00:00",
                "separate_physical_session": True,
                "independence_basis_private": "separately initiated session",
                "mcap_basenames_private": ["a.mcap"],
            }
        ],
    }


class IndependentOutingManifestTests(unittest.TestCase):
    def test_exact_manifest_is_accepted(self) -> None:
        manifest = parse_acquisition_manifest(_manifest())
        self.assertEqual(manifest.basename_to_private_label, {"a.mcap": "private-a"})
        self.assertFalse(manifest.is_superseding)

    def test_tracked_manifest_example_matches_the_strict_schema(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        path = repository / "config/examples/independent_outings_v017.private.example.json"
        manifest = parse_acquisition_manifest(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(len(manifest.outings), 7)
        self.assertEqual(len(manifest.basename_to_private_label), 7)

    def test_unknown_or_missing_field_is_rejected(self) -> None:
        for mutation in ("unknown", "missing"):
            with self.subTest(mutation=mutation):
                payload = _manifest()
                if mutation == "unknown":
                    payload["road_type"] = "forbidden"
                else:
                    payload.pop("created_before_outcome_inspection")
                with self.assertRaisesRegex(ValueError, "fields differ"):
                    parse_acquisition_manifest(payload)

    def test_attestations_must_be_literal_true(self) -> None:
        fields = (
            "acquisition_batch_closed",
            "created_before_outcome_inspection",
        )
        for field in fields:
            for invalid in (False, 1, "true"):
                with self.subTest(field=field, invalid=invalid):
                    payload = _manifest()
                    payload[field] = invalid
                    with self.assertRaises(ValueError):
                        parse_acquisition_manifest(payload)
        payload = _manifest()
        payload["outings"][0]["separate_physical_session"] = False  # type: ignore[index]
        with self.assertRaises(ValueError):
            parse_acquisition_manifest(payload)

    def test_prior_fields_are_both_null_or_both_nonnull(self) -> None:
        for prior, amendment in (("a" * 64, None), (None, "amendment-1")):
            with self.subTest(prior=prior, amendment=amendment):
                payload = _manifest()
                payload["prior_successful_lock_sha256"] = prior
                payload["superseding_contract_amendment_id"] = amendment
                with self.assertRaisesRegex(ValueError, "both be null or both be non-null"):
                    parse_acquisition_manifest(payload)

    def test_duplicate_labels_basenames_and_paths_are_rejected(self) -> None:
        payload = _manifest()
        payload["outings"].append(dict(payload["outings"][0]))  # type: ignore[union-attr,index]
        with self.assertRaisesRegex(ValueError, "private_outing_label"):
            parse_acquisition_manifest(payload)
        payload = _manifest()
        payload["outings"][0]["mcap_basenames_private"] = ["nested/a.mcap"]  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "unqualified"):
            parse_acquisition_manifest(payload)


class IndependentOutingRuleTests(unittest.TestCase):
    def test_frame_state_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            FrameTechnicalEvidence(
                estimate_message_index=0,
                source_time_ns=1,
                topology_source_name="ROAD_TOPOLOGY_SOURCE_LANE_MAP",
                topology_gate_candidate=True,
                h100_geometry_ready=True,
                anchor_distance_within_limit=True,
                causal_inputs_available=True,
                raw_usable=True,
                eligible=True,
            )

    def test_exact_eligibility_boundaries_pass(self) -> None:
        result = evaluate_outing_eligibility(
            OutingEligibilityEvidence(
                raw_usable_recording_count=1,
                usable_duration_ns=120_000_000_000,
                usable_intervals_monotonic_nonoverlapping=True,
                topology_candidate_count=500,
                non_sensor_topology_candidate_count=0,
                eligible_frame_count=500,
                sequence_count=1,
                retained_eligible_frame_count=500,
            )
        )
        self.assertTrue(result.technically_eligible)
        self.assertEqual(result.failure_codes, ())

    def test_each_outing_gate_fails_closed(self) -> None:
        base = {
            "raw_usable_recording_count": 1,
            "usable_duration_ns": 120_000_000_000,
            "usable_intervals_monotonic_nonoverlapping": True,
            "topology_candidate_count": 500,
            "non_sensor_topology_candidate_count": 0,
            "eligible_frame_count": 500,
            "sequence_count": 1,
            "retained_eligible_frame_count": 500,
        }
        cases = (
            ("raw_usable_recording_count", 0, "no_raw_usable_recording"),
            ("usable_duration_ns", 119_999_999_999, "usable_duration_below_120s"),
            (
                "usable_intervals_monotonic_nonoverlapping",
                False,
                "usable_source_intervals_overlap_or_are_not_monotonic",
            ),
            ("non_sensor_topology_candidate_count", 1, "mixed_or_unknown_topology_source"),
            ("eligible_frame_count", 499, "eligible_frame_count_below_500"),
            ("retained_eligible_frame_count", 499, "eligible_sequence_integrity_failed"),
        )
        for field, value, code in cases:
            with self.subTest(field=field):
                evidence = dict(base)
                evidence[field] = value
                result = evaluate_outing_eligibility(OutingEligibilityEvidence(**evidence))
                self.assertFalse(result.technically_eligible)
                self.assertIn(code, result.failure_codes)

    def test_fingerprint_retains_repeated_hashes_and_uses_exact_encoding(self) -> None:
        values = ("b" * 64, "a" * 64, "b" * 64)
        expected = hashlib.sha256(
            ("a" * 64 + "\n" + "b" * 64 + "\n" + "b" * 64 + "\n").encode("ascii")
        ).hexdigest()
        self.assertEqual(outing_fingerprint_sha256(values), expected)
        without_repeat = outing_fingerprint_sha256(values[:2])
        self.assertNotEqual(expected, without_repeat)

    def test_split_score_and_final_count_are_exact(self) -> None:
        fingerprint = "1" * 64
        self.assertEqual(
            split_score_sha256(fingerprint),
            hashlib.sha256(SPLIT_SALT + b"\0" + fingerprint.encode("ascii")).hexdigest(),
        )
        expected = {7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 19: 4}
        self.assertEqual({count: fixed_final_count(count) for count in expected}, expected)

    def test_no_roles_below_seven_and_exact_roles_at_seven(self) -> None:
        fingerprints = {f"label-{i}": f"{i:064x}" for i in range(1, 8)}
        failed, final_count, passed = assign_cohorts(fingerprints, tuple(fingerprints)[:6])
        self.assertFalse(passed)
        self.assertIsNone(final_count)
        self.assertTrue(all(item.cohort_role is None for item in failed.values()))

        assigned, final_count, passed = assign_cohorts(fingerprints, tuple(fingerprints))
        self.assertTrue(passed)
        self.assertEqual(final_count, 2)
        self.assertEqual(sum(item.cohort_role == "final_test" for item in assigned.values()), 2)
        self.assertEqual(sum(item.cohort_role == "development" for item in assigned.values()), 5)
        self.assertTrue(2 <= final_count < len(fingerprints))

    def test_identity_and_split_rank_are_independent_content_orders(self) -> None:
        fingerprints = {f"label-{i}": f"{i:064x}" for i in range(1, 8)}
        assigned, _, passed = assign_cohorts(fingerprints, tuple(fingerprints))
        self.assertTrue(passed)
        opaque_order = sorted(assigned, key=lambda label: assigned[label].outing_id)
        split_order = sorted(assigned, key=lambda label: assigned[label].split_rank or math.inf)
        self.assertNotEqual(opaque_order, split_order)

    def test_labels_and_input_order_cannot_reroll_content_assignment(self) -> None:
        first = {f"private-{i}": f"{i:064x}" for i in range(1, 8)}
        second = {f"renamed-{i}": first[f"private-{i}"] for i in range(7, 0, -1)}
        a, _, _ = assign_cohorts(first, tuple(first))
        b, _, _ = assign_cohorts(second, tuple(second))
        by_fingerprint_a = {
            value.outing_fingerprint_sha256: (value.outing_id, value.split_rank, value.cohort_role)
            for value in a.values()
        }
        by_fingerprint_b = {
            value.outing_fingerprint_sha256: (value.outing_id, value.split_rank, value.cohort_role)
            for value in b.values()
        }
        self.assertEqual(by_fingerprint_a, by_fingerprint_b)

    def test_identical_outing_fingerprints_are_a_lineage_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "fingerprints must be unique"):
            assign_cohorts({"one": "a" * 64, "two": "a" * 64}, ("one", "two"))


if __name__ == "__main__":
    unittest.main()
