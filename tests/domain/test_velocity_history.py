import unittest

from lane_residuals.domain.velocity_history import summarize
from lane_residuals.domain.velocity_timing import TOPICS
from tests.io.velocity_timing_fixture import row, LOG, SOURCE


def event(log=-10, age=20, **changes):
    value = {"topic": TOPICS[0], "log_ns": str(LOG+log), "source_ns": str(SOURCE-age),
        "publish_ns": str(SOURCE-1), "value": 10., "qualifier": 1, "nested_present": True,
        "outer_qualifier": None, "standstill_status": None}
    value.update(changes)
    return value


class HistoryTests(unittest.TestCase):
    def evaluate(self, records, rows=None):
        result, screens = summarize(records, [row(0)] if rows is None else rows)
        return result, [s for s in screens if s["topic"] == TOPICS[0]]

    def test_co_logged_future_update_excluded_before_one_selection(self):
        result, screens = self.evaluate([event(), event(0, -1)])
        self.assertTrue(screens[0]["local_hypothetical_complete"])
        self.assertEqual(screens[0]["chosen_update_log_ns"], str(LOG-10))
        self.assertEqual(screens[0]["co_logged_updates_excluded"], 1)
        self.assertFalse(result["speed_feature_adopted"])
        self.assertFalse(result["physical_causal_availability_proven"])

    def test_no_history_when_only_co_logged_or_future_records_exist(self):
        _, screens = self.evaluate([event(0), event(10)])
        self.assertIsNone(screens[0]["chosen_update_log_ns"])
        self.assertEqual(screens[0]["reasons"], ["no_strictly_prior_update_in_bounded_history"])

    def test_duplicate_latest_prior_log_fails_without_searching_older(self):
        _, screens = self.evaluate([event(-20), event(), event(value=11.)])
        self.assertIn("latest_prior_log_time_ambiguous", screens[0]["reasons"])
        self.assertFalse(screens[0]["local_hypothetical_complete"])

    def test_duplicate_co_logged_records_are_all_excluded(self):
        _, screens = self.evaluate([event(), event(0), event(0, qualifier=255)])
        self.assertTrue(screens[0]["recorded_clock_screen_met"])
        self.assertEqual(screens[0]["co_logged_updates_excluded"], 2)

    def test_invalid_latest_prior_is_not_bypassed(self):
        variants = [({"qualifier": 255}, "inner_qualifier_not_declared_valid"),
            ({"source_ns": "0"}, "nonpositive_source_timestamp"),
            ({"source_ns": "-1"}, "nonpositive_source_timestamp"),
            ({"source_ns": str(SOURCE+1)}, "future_source_timestamp"),
            ({"source_ns": str(SOURCE-100_000_001)}, "source_age_above_exploratory_100ms"),
            ({"publish_ns": str(SOURCE+1001)}, "publish_clock_screen_failed"),
            ({"publish_ns": "0"}, "publish_clock_screen_failed"),
            ({"value": None}, "nonfinite_value"), ({"value": float("nan")}, "nonfinite_value"),
            ({"value": float("inf")}, "nonfinite_value"), ({"nested_present": False}, "nested_message_absent")]
        for changes, reason in variants:
            with self.subTest(changes=changes):
                _, screens = self.evaluate([event(-20), event(**changes)])
                self.assertIn(reason, screens[0]["reasons"])
                self.assertEqual(screens[0]["chosen_update_log_ns"], str(LOG-10))
                self.assertFalse(screens[0]["local_hypothetical_complete"])

    def test_integer_nanoseconds_and_strict_one_ns_log_boundary(self):
        _, screens = self.evaluate([event(-1, 1), event(0)])
        self.assertEqual(screens[0]["source_age_ns"], "1")
        self.assertEqual(screens[0]["logged_history_age_ns"], "1")
        self.assertTrue(screens[0]["recorded_clock_screen_met"])

    def test_age_boundary_unchanged(self):
        for age, included in ((0, True), (100_000_000, True), (100_000_001, False)):
            with self.subTest(age=age):
                _, screens = self.evaluate([event(age=age)])
                self.assertEqual(screens[0]["recorded_clock_screen_met"], included)

    def test_zero_speed_is_a_value_not_a_missing_measurement(self):
        _, screens = self.evaluate([event(value=0.)])
        self.assertTrue(screens[0]["local_hypothetical_complete"])

    def test_non_speed_and_geometry_exclusions_still_break_runs(self):
        rows = [row(i) for i in range(4)]
        rows[1]["condition_failure_codes"] = ["estimate_features_unavailable"]
        rows[2]["residual_available"] = False
        records = [event(-10+i*100_000_000, source_ns=str(SOURCE+i*100_000_000-20)) for i in range(4)]
        result, screens = self.evaluate(records, rows)
        self.assertEqual([s["local_hypothetical_complete"] for s in screens], [True, False, False, True])
        self.assertFalse(screens[2]["original_local_complete"])
        self.assertEqual(result["topics"][TOPICS[0]]["local_hypothetical_complete_under_screen"]["sequences"], 2)

    def test_replaced_speed_failure_preserves_original_provenance(self):
        r = row(0); r["conditions_available"] = False
        r["condition_failure_codes"] = ["odometry_interpolation_gap_exceeds_limit"]
        result, screens = self.evaluate([event()], [r])
        self.assertTrue(screens[0]["local_hypothetical_complete"])
        self.assertEqual(screens[0]["condition_failure_codes"], r["condition_failure_codes"])
        self.assertEqual(result["topics"][TOPICS[0]]["gained_original_incomplete_frames"], 1)

    def test_message_pair_and_source_gaps_split_sequences(self):
        for field in ("estimate_message_index", "pair_index", "estimate_source_time_ns_decimal_private"):
            with self.subTest(field=field):
                rows = [row(i) for i in range(3)]
                rows[2][field] = str(SOURCE+400_000_000) if field.endswith("private") else rows[2][field]+1
                events = [event(-10+i*100_000_000, source_ns=str(int(rows[i]["estimate_source_time_ns_decimal_private"])-20)) for i in range(3)]
                result, _ = self.evaluate(events, rows)
                self.assertEqual(result["topics"][TOPICS[0]]["local_hypothetical_complete_under_screen"]["sequences"], 2)

    def test_multiple_recordings_must_not_share_one_history_stream(self):
        rows = [row(0), row(1)]; rows[1]["recording_id"] = "another"
        with self.assertRaisesRegex(ValueError, "one_recording"):
            self.evaluate([event()], rows)

    def test_outer_and_standstill_enums_are_observed_not_adopted(self):
        records = [event(topic=TOPICS[1], outer_qualifier=2, standstill_status=15)]
        result, screens = summarize(records, [row(0)])
        control = [s for s in screens if s["topic"] == TOPICS[1]][0]
        self.assertTrue(control["local_hypothetical_complete"])
        self.assertEqual(control["chosen_outer_qualifier_observed_only"], 2)
        self.assertEqual(control["chosen_standstill_status_observed_only"], 15)
        self.assertFalse(result["topics"][TOPICS[1]]["outer_qualifier_policy_adopted"])

    def test_source_inversions_are_observed_without_resorting_or_repair(self):
        result, screens = self.evaluate([event(-20, 10), event(-10, 30)])
        self.assertEqual(screens[0]["source_age_ns"], "30")
        self.assertEqual(result["topics"][TOPICS[0]]["source_time_inversions_in_log_order"], 1)


if __name__ == "__main__":
    unittest.main()
