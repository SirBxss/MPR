import unittest

from lane_residuals.domain.velocity_timing import TOPICS, summarize, sequence_stats
from tests.io.velocity_timing_fixture import row, LOG, SOURCE


def event(offset=0, quality=1, timestamp=None, value=10.):
    return {"topic": TOPICS[0], "log_ns": str(LOG+offset-10), "publish_ns": str(SOURCE+offset-10),
        "source_ns": str(SOURCE+offset-20 if timestamp is None else timestamp), "qualifier": quality,
        "value": value, "outer_qualifier": None, "nested_present": True}


class TimingScreenTests(unittest.TestCase):
    def screen(self, events, rows=None):
        result, screens = summarize(events, [row(0)] if rows is None else rows, {})
        return result, [r for r in screens if r["topic"] == TOPICS[0]]

    def test_invalid_latest_update_is_not_bypassed(self):
        _, screens = self.screen([event(-100), event(quality=255)])
        self.assertFalse(screens[0]["recorded_clock_screen_met"])
        self.assertIn("inner_qualifier_not_declared_valid", screens[0]["reasons"])

    def test_future_and_zero_latest_source_do_not_fall_back(self):
        for timestamp, reason in ((0, "nonpositive_source_timestamp"), (SOURCE+1, "future_source_timestamp")):
            _, screens = self.screen([event(-100), event(timestamp=timestamp)])
            self.assertIn(reason, screens[0]["reasons"])

    def test_integer_nanoseconds_above_float_precision_are_preserved(self):
        _, screens = self.screen([event(timestamp=SOURCE-1)])
        self.assertEqual(screens[0]["source_age_ns"], "1")
        self.assertTrue(screens[0]["recorded_clock_screen_met"])

    def test_fixed_age_boundary_and_stale_rejection(self):
        for age, expected in ((100_000_000, True), (100_000_001, False)):
            _, screens = self.screen([event(timestamp=SOURCE-age)])
            self.assertEqual(screens[0]["recorded_clock_screen_met"], expected)

    def test_log_future_is_not_selected_and_future_publish_is_rejected(self):
        _, screens = self.screen([event(100)])
        self.assertIn("no_update_in_bounded_log_history", screens[0]["reasons"])
        e = event(); e["publish_ns"] = str(SOURCE+1001)
        _, screens = self.screen([e])
        self.assertIn("publish_clock_screen_failed", screens[0]["reasons"])

    def test_equal_log_timestamp_updates_are_ambiguous(self):
        _, screens = self.screen([event(), event(quality=255)])
        self.assertIn("latest_log_time_ambiguous", screens[0]["reasons"])

    def test_log_tie_to_edp_is_reported_without_physical_availability_claim(self):
        e = event(); e["log_ns"] = str(LOG)
        result, screens = self.screen([e])
        self.assertTrue(screens[0]["log_time_tied_to_edp"])
        self.assertIs(result["physical_causal_availability_proven"], False)
        self.assertEqual(result["topics"][TOPICS[0]]["edp_log_tie_frames"], 1)

    def test_all_producer_speed_path_failures_can_be_replaced_by_the_screen(self):
        for code in ("speed_uses_future_source_sample", "odometry_interpolation_gap_exceeds_limit",
            "odometry_reference_time_outside_coverage", "odometry_speed_history_outside_coverage",
            "odometry_log_lag_exceeds_limit", "odometry_stream_empty",
            "odometry_stream_invalid_or_schema_changed", "ValueError", "TypeError"):
            with self.subTest(code=code):
                r = row(0); r["conditions_available"] = False; r["condition_failure_codes"] = [code]
                _, screens = self.screen([event()], [r])
                self.assertTrue(screens[0]["local_hypothetical_complete"])
                self.assertEqual(screens[0]["condition_failure_codes"], [code])

    def test_geometry_and_estimate_derived_exclusions_remain_barriers(self):
        r = row(0); r["residual_available"] = False
        _, screens = self.screen([event()], [r])
        self.assertTrue(screens[0]["recorded_clock_screen_met"])
        self.assertFalse(screens[0]["local_hypothetical_complete"])
        r["residual_available"] = True
        r["condition_failure_codes"] = ["odometry_interpolation_gap_exceeds_limit", "estimate_features_estimate_inputs_non_finite"]
        _, screens = self.screen([event()], [r])
        self.assertFalse(screens[0]["non_speed_features_available"])
        self.assertFalse(screens[0]["local_hypothetical_complete"])

    def test_zero_speed_with_valid_quality_is_not_treated_as_missing(self):
        _, screens = self.screen([event(value=0.)])
        self.assertTrue(screens[0]["recorded_clock_screen_met"])

    def test_other_feature_failure_is_preserved(self):
        r = row(0); r["condition_failure_codes"] = ["estimate_features_unavailable"]
        _, screens = self.screen([event()], [r])
        self.assertTrue(screens[0]["recorded_clock_screen_met"])
        self.assertFalse(screens[0]["local_hypothetical_complete"])

    def test_sequences_do_not_bridge_exclusions_or_message_gaps(self):
        rows = [row(i) for i in range(5)]
        result = sequence_stats(rows, [True, True, False, True, True])
        self.assertEqual((result["frames"], result["sequences"], result["transitions"]), (4, 2, 2))
        rows[4]["estimate_message_index"] += 1
        self.assertEqual(sequence_stats(rows, [True]*5)["sequences"], 2)
