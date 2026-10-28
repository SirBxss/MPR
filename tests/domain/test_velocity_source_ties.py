import unittest

from lane_residuals.domain.velocity_history import summarize as primary_summary
from lane_residuals.domain.velocity_source_ties import clock_observations, summarize
from lane_residuals.domain.velocity_timing import TOPICS
from tests.domain.test_velocity_history import event
from tests.io.velocity_timing_fixture import LOG, SOURCE, row


class SourceTieTests(unittest.TestCase):
    def evaluate(self, events, rows=None):
        analysis, screens = summarize(events, [row(0)] if rows is None else rows)
        return analysis["topics"][TOPICS[0]], [r for r in screens if r["topic"] == TOPICS[0]]

    def test_primary_is_exact_unchanged_analysis(self):
        events = [event(-20, 1), event(-10, 0), event(0, -1)]
        expected, expected_rows = primary_summary(events, [row(0)])
        analysis, screens = summarize(events, [row(0)])
        self.assertEqual(analysis["primary_analysis_unchanged"], expected)
        for old, new in zip(expected_rows, screens):
            self.assertEqual({key: new[key] for key in old}, old)

    def test_source_tie_secondary_never_reselects_older_valid_sample(self):
        topic, rows = self.evaluate([event(-20, 1), event(-10, 0)])
        self.assertTrue(rows[0]["local_hypothetical_complete"])
        self.assertFalse(rows[0]["strict_source_local_hypothetical_complete"])
        self.assertEqual(rows[0]["chosen_update_log_ns"], str(LOG-10))
        self.assertEqual(rows[0]["strict_source_reasons"], ["selected_source_time_equal_to_edp"])
        self.assertEqual(topic["primary_only_frames"], 1)
        self.assertEqual(topic["secondary_only_frames"], 0)

    def test_nanosecond_source_and_age_boundaries(self):
        for age, primary, secondary in ((-1, False, False), (0, True, False), (1, True, True),
                (100_000_000, True, True), (100_000_001, False, False)):
            with self.subTest(age=age):
                _, rows = self.evaluate([event(age=age)])
                self.assertEqual(rows[0]["local_hypothetical_complete"], primary)
                self.assertEqual(rows[0]["strict_source_local_hypothetical_complete"], secondary)

    def test_integer_clock_above_float_exact_range(self):
        target = row(0)
        big = 1_800_000_000_000_000_001
        target.update(estimate_source_time_ns_decimal_private=str(big))
        _, rows = self.evaluate([event(age=1, source_ns=str(big-1))], [target])
        self.assertEqual(rows[0]["source_age_ns"], "1")
        self.assertFalse(rows[0]["selected_source_time_equal_to_edp"])
        self.assertTrue(rows[0]["strict_source_local_hypothetical_complete"])

    def test_missing_history_and_invalid_latest_remain_barriers(self):
        for changes in ({"qualifier": 255}, {"value": None}, {"source_ns": "0"},
                {"publish_ns": "0"}, {"nested_present": False}):
            with self.subTest(changes=changes):
                _, rows = self.evaluate([event(-20, 1), event(-10, 0, **changes)])
                self.assertFalse(rows[0]["strict_source_recorded_clock_screen_met"])
                self.assertFalse(rows[0]["local_hypothetical_complete"])
                self.assertEqual(rows[0]["chosen_update_log_ns"], str(LOG-10))
        _, rows = self.evaluate([event(0, 1)])
        self.assertIsNone(rows[0]["source_age_ns"])
        self.assertFalse(rows[0]["selected_source_time_equal_to_edp"])
        self.assertFalse(rows[0]["strict_source_recorded_clock_screen_met"])

    def test_zero_speed_is_retained_under_both_conventions(self):
        _, rows = self.evaluate([event(age=1, value=0.)])
        self.assertTrue(rows[0]["strict_source_local_hypothetical_complete"])

    def test_geometry_other_features_and_original_losses_remain_visible(self):
        targets = [row(i) for i in range(4)]
        targets[1]["residual_available"] = False
        targets[2]["condition_failure_codes"] = ["estimate_features_unavailable"]
        targets[3]["conditions_available"] = False
        targets[3]["condition_failure_codes"] = ["speed_uses_future_source_sample"]
        events = [event(-10+i*100_000_000, source_ns=str(SOURCE+i*100_000_000-(0 if i == 0 else 1))) for i in range(4)]
        topic, rows = self.evaluate(events, targets)
        self.assertEqual([r["strict_source_local_hypothetical_complete"] for r in rows], [False, False, False, True])
        secondary = topic["secondary_source_strictly_before"]
        self.assertEqual(secondary["gained_original_incomplete_frames"], 1)
        self.assertEqual(secondary["lost_original_complete_frames"], 2)
        self.assertEqual(topic["primary_complete_source_equal_frames"], 1)

    def test_removed_tie_and_original_message_gap_split_runs(self):
        targets = [row(i) for i in range(5)]
        targets[4]["estimate_message_index"] += 1
        events = [event(-10+i*100_000_000, source_ns=str(SOURCE+i*100_000_000-(0 if i == 1 else 1))) for i in range(5)]
        topic, _ = self.evaluate(events, targets)
        stat = topic["secondary_source_strictly_before"]["local_hypothetical_complete_under_screen"]
        self.assertEqual((stat["frames"], stat["sequences"], stat["transitions"], stat["maximum_frames"]), (4, 3, 1, 2))

    def test_clock_observations_do_not_identify_epoch_or_producer(self):
        stats = clock_observations(["0", "4000000000", "4000000000", "-1", "4123736000000000"])
        self.assertEqual(stats["positive_timestamp_below_five_seconds_count"], 2)
        self.assertEqual(stats["adjacent_equal_count"], 1)
        self.assertEqual(stats["adjacent_decreasing_count"], 1)
        self.assertEqual(stats["seconds_component_range"], [-1, 4123736])
        self.assertFalse(stats["epoch_or_producer_identified"])
        self.assertIsNone(clock_observations([])["seconds_component_range"])

    def test_claim_flags_stay_false_and_two_topics_remain_separate(self):
        analysis, screens = summarize([event(topic=TOPICS[1], age=0)], [row(0)])
        self.assertEqual(analysis["topics"][TOPICS[0]]["selected_source_equal_frames"], 0)
        self.assertEqual(analysis["topics"][TOPICS[1]]["selected_source_equal_frames"], 1)
        for key in ("speed_feature_adopted", "producer_value_semantics_established", "deployed_producer_identified",
                "physical_causal_availability_proven", "source_publish_clock_comparability_established",
                "independent_generalization_validation", "secondary_update_reselection_used"):
            self.assertIs(analysis[key], False)


if __name__ == "__main__":
    unittest.main()
