from __future__ import annotations

import unittest

from lane_residuals.domain.recording_pair_diagnostics import summarize_timestamp_deltas


class TimestampDiagnosticTests(unittest.TestCase):
    def test_signed_absolute_and_nearest_rank_are_exact(self):
        result = summarize_timestamp_deltas([-20, 0, 7, 9])
        self.assertEqual((result["count"], result["negative_count"], result["zero_count"], result["positive_count"]), (4, 1, 1, 2))
        self.assertEqual(result["signed_reference_minus_estimate_ns"],
                         {"min": -20, "p50": 0, "p95": 9, "p99": 9, "max": 9})
        self.assertEqual(result["absolute_ns"],
                         {"min": 0, "p50": 7, "p95": 20, "p99": 20, "max": 20})

    def test_nanosecond_precision_beyond_float_and_int64_ranges(self):
        huge = 2**65 + 1
        result = summarize_timestamp_deltas([-huge, 2**53 + 1, 2**53 + 2])
        self.assertEqual(result["signed_reference_minus_estimate_ns"]["min"], -huge)
        self.assertEqual(result["signed_reference_minus_estimate_ns"]["p50"], 2**53 + 1)
        self.assertEqual(result["absolute_ns"]["max"], huge)

    def test_empty_groups_have_null_statistics(self):
        result = summarize_timestamp_deltas([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["positive_count"], 0)
        self.assertTrue(all(value is None for value in result["absolute_ns"].values()))
        self.assertTrue(all(value is None for value in result["signed_reference_minus_estimate_ns"].values()))

    def test_float_and_boolean_deltas_are_rejected(self):
        for value in (1.0, True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                summarize_timestamp_deltas([value])


if __name__ == "__main__":
    unittest.main()
