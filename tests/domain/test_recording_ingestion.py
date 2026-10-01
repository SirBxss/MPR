from copy import deepcopy
import unittest

from lane_residuals.domain.recording_ingestion import (
    ClockOrderSummary, SOURCE_FIELDS, SPECIFICATION_VERSION, parse_specification,
    source_declaration_status, summarize_support,
)
from tests.domain.test_exploratory_residuals import row, T


def specification(path="/private/pilot.mcap"):
    source = dict.fromkeys(SOURCE_FIELDS)
    source["merged_input_mcap_count"] = 180
    return {"schema_version": SPECIFICATION_VERSION, "batch_id": "batch03_pilot001", "purpose": "development_only",
            "recordings": [{"recording_id": "pilot_001", "local_path_private": path, "source": source}]}


class RecordingDeclarationTests(unittest.TestCase):
    def test_unavailable_provenance_is_truthful_and_merged_count_never_proves_sessions(self):
        value = specification()
        self.assertEqual(parse_specification(value), value)
        result = source_declaration_status(value["recordings"][0]["source"])
        self.assertEqual(result["claimed_merged_input_mcap_count"], 180)
        self.assertFalse(result["physical_session_declared_with_evidence"])
        self.assertFalse(result["physical_session_identity_verified"])
        self.assertNotIn("independent_outing_count", result)

    def test_session_declaration_requires_evidence_but_is_never_automatically_verified(self):
        value = specification()
        source = value["recordings"][0]["source"]
        source["physical_session_id_private"] = "provider_session_a"
        with self.assertRaisesRegex(ValueError, "requires_evidence"):
            parse_specification(value)
        source["physical_session_evidence_private"] = "provider explicitly describes a single physical drive"
        parse_specification(value)
        self.assertTrue(source_declaration_status(source)["physical_session_declared_with_evidence"])
        self.assertFalse(source_declaration_status(source)["physical_session_identity_verified"])

    def test_ambiguous_display_dates_and_local_timezone_are_rejected_as_utc_evidence(self):
        for start, end in (("06/10/2026 07:24:20 AM", "06/10/2026 08:24:04 AM"),
                           ("2026-06-10T07:24:20", "2026-06-10T08:24:04"),
                           ("2026-06-10T07:24:20+02:00", "2026-06-10T08:24:04+02:00"),
                           ("2026-06-10T08:24:04Z", "2026-06-10T07:24:20Z")):
            value = specification(); source = value["recordings"][0]["source"]
            source.update(acquisition_start_utc_private=start, acquisition_end_utc_private=end)
            with self.assertRaises(ValueError): parse_specification(value)
        value = specification(); source = value["recordings"][0]["source"]
        source.update(acquisition_start_utc_private="2026-06-10T07:24:20Z", acquisition_end_utc_private="2026-06-10T08:24:04Z")
        parse_specification(value)

    def test_paths_ids_schema_and_undeclared_fields_fail_closed(self):
        for path in ("~/pilot.mcap", "relative.mcap", "/private/../pilot.mcap", "/private//pilot.mcap", "/private/pilot.zip"):
            with self.assertRaises(ValueError): parse_specification(specification(path))
        for mutation in ("purpose", "schema", "extra", "duplicate_id", "duplicate_path", "bool_count"):
            value = specification()
            if mutation == "purpose": value["purpose"] = "final_validation"
            elif mutation == "schema": value["schema_version"] = "unknown"
            elif mutation == "extra": value["recordings"][0]["source"]["role"] = "training"
            elif mutation.startswith("duplicate"):
                value["recordings"].append(deepcopy(value["recordings"][0]))
                if mutation == "duplicate_id": value["recordings"][1]["local_path_private"] = "/private/other.mcap"
                else: value["recordings"][1]["recording_id"] = "other"
            else: value["recordings"][0]["source"]["merged_input_mcap_count"] = True
            with self.assertRaises(ValueError): parse_specification(value)

    def test_support_preserves_original_indices_clock_breaks_and_recording_boundaries(self):
        rows = [row(0, T), row(1, T+100_000_000), row(3, T+200_000_000), row(4, T+200_000_000), row(0, T, recording="other")]
        support = summarize_support(rows)
        self.assertEqual((support["frame_count"], support["sequence_count"], support["transition_count"]), (5, 4, 1))
        self.assertEqual(support["maximum_duration_ns"], 100_000_000)
        self.assertEqual(support["sequence_start_reason_counts"]["timestamp_non_monotonic"], 1)
        self.assertEqual(support["sequence_start_reason_counts"]["recording_boundary"], 1)
        self.assertEqual(summarize_support([])["maximum_frame_count"], 0)

    def test_uint64_clock_summary_is_exact_and_does_not_sort_or_bridge_missing_times(self):
        clock = ClockOrderSummary()
        for time in (2**64-1, 2**63, 2**63, None, 1): clock.add(time)
        summary = clock.summary()
        self.assertEqual(summary["maximum_timestamp_ns_decimal"], str(2**64-1))
        self.assertEqual(summary["minimum_timestamp_ns_decimal"], "1")
        self.assertEqual(summary["backward_step_count"], 1)
        self.assertEqual(summary["repeated_adjacent_timestamp_count"], 1)
        self.assertEqual(summary["missing_timestamp_count"], 1)
