from copy import deepcopy
import unittest

from lane_residuals.domain.speed_mechanism import BRACKETS, TICK_NS, clock_summary, summarize


def row(i=0, complete=True, equal=True):
    t = 10_000_000_000+i*100_000_000
    return {"recording_id": "synthetic", "candidate_index": i, "estimate_message_index": i, "pair_index": i,
        "estimate_source_time_ns_decimal_private": str(t), "reference_source_time_ns_decimal_private": str(t),
        "residual_available": True, "conditions_available": complete,
        "condition_failure_codes": [] if complete else ["speed_uses_future_source_sample"],
        "speed_bracket_evidence": dict(zip(BRACKETS, map(str, (t if equal else t-1, t if equal else t+1, t-60_000_000, t-40_000_000))))}


def support():
    return {"maximum_complete_sequence_duration_ns": 100_000_000, "maximum_complete_sequence_frames": 2}


class MechanismTests(unittest.TestCase):
    def test_all_four_cells_are_observations_and_reconcile(self):
        rows = [row(i, complete, equal) for i, (complete, equal) in enumerate(((True, True),(True, False),(False, True),(False, False)))]
        result, frames = summarize("synthetic", rows, support(), False)
        self.assertEqual(set(result["all_assessable_complete_endpoint_table"].values()), {1})
        self.assertEqual(result["retained_candidate_rows"], 4)
        self.assertEqual(result["other_rows"], 0)
        self.assertEqual(len(frames), 4)

    def test_missing_null_zero_inverted_and_outside_brackets_stay_unknown(self):
        variants = [{}, {BRACKETS[0]: None, BRACKETS[1]: "10000000000"},
            {BRACKETS[0]: "0", BRACKETS[1]: "10000000000"},
            {BRACKETS[0]: "10000000001", BRACKETS[1]: "9999999999"},
            {BRACKETS[0]: "9999999998", BRACKETS[1]: "9999999999"}]
        for evidence in variants+[None]:
            with self.subTest(evidence=evidence):
                r = row(); r["speed_bracket_evidence"] = evidence
                result, frames = summarize("synthetic", [r], support(), True)
                self.assertIsNone(frames[0]["current_endpoint_equal"])
                self.assertEqual(sum(result["all_assessable_complete_endpoint_table"].values()), 0)
                self.assertEqual(sum(result["endpoint_not_assessable_counts"].values()), 1)

    def test_float_boolean_and_noncanonical_stamps_are_rejected(self):
        for value in (1., True, "01", "1e9", " 1", "1.0", "-0"):
            with self.subTest(value=value):
                r=row();r["speed_bracket_evidence"][BRACKETS[0]]=value
                with self.assertRaisesRegex(ValueError, "integer_decimal"):
                    summarize("synthetic", [r], support(), False)

    def test_integer_equality_above_float_exact_range(self):
        r=row();t=2**60+1;r["estimate_source_time_ns_decimal_private"]=str(t)
        r["speed_bracket_evidence"][BRACKETS[0]]=str(t-1);r["speed_bracket_evidence"][BRACKETS[1]]=str(t+1)
        result,frames=summarize("synthetic",[r],support(),False)
        self.assertIs(frames[0]["current_endpoint_equal"],False)
        self.assertEqual(result["all_assessable_complete_endpoint_table"]["complete_unequal"],1)

    def test_other_features_and_geometry_do_not_disappear_from_denominators(self):
        rows=[row(0,False,True),row(1,False,True),row(2,False,False)]
        rows[0]["condition_failure_codes"]=["estimate_features_unavailable"]
        rows[1]["residual_available"]=False
        result,frames=summarize("synthetic",rows,support(),False)
        self.assertEqual(result["retained_candidate_rows"],3)
        self.assertEqual(result["geometry_without_declared_estimate_failure_rows"],1)
        self.assertEqual(sum(result["stratum_assessable_complete_endpoint_table"].values()),1)
        self.assertEqual(result["other_rows"],2)
        self.assertEqual(frames[0]["condition_failure_codes"],["estimate_features_unavailable"])

    def test_equality_elsewhere_never_replaces_row_local_current_bracket(self):
        r=row(equal=False);r["speed_bracket_evidence"][BRACKETS[2]]=r["estimate_source_time_ns_decimal_private"]
        _,frames=summarize("synthetic",[r],support(),False)
        self.assertIs(frames[0]["current_endpoint_equal"],False)

    def test_clock_grid_is_within_second_and_uniqueness_is_recording_local(self):
        t=str(1_000_000_000+TICK_NS)
        result=clock_summary([("a",t),("a",t),("b",t),("a",None),("a","0"),("a","-1")])
        self.assertEqual(result["positive_entries_on_grid"],3)
        self.assertEqual(result["unique_positive_recording_stamp_pairs"],2)
        self.assertEqual(result["missing_entries"],1)
        self.assertEqual(result["nonpositive_entries"],2)
        self.assertFalse(result["clock_identity_or_physical_resolution_proven"])

    def test_duplicate_candidate_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate_candidate"):
            summarize("synthetic",[row(),row()],support(),False)

    def test_prior_label_and_original_rows_are_preserved_without_mutation(self):
        rows=[row()];before=deepcopy(rows);original=support()
        result,frames=summarize("synthetic",rows,original,True)
        self.assertEqual(rows,before);self.assertEqual(result["original_matched_support"],original)
        self.assertTrue(frames[0]["previously_examined_case"])

    def test_missing_previous_brackets_does_not_invalidate_current_comparison(self):
        r=row();del r["speed_bracket_evidence"][BRACKETS[2]];del r["speed_bracket_evidence"][BRACKETS[3]]
        result,frames=summarize("synthetic",[r],support(),False)
        self.assertTrue(frames[0]["current_endpoint_equal"])
        self.assertEqual(result["clock_observations"]["odometry_brackets"]["missing_entries"],2)


if __name__ == "__main__":unittest.main()
