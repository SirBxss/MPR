"""Regression checks for the predeclared recorded spatial pilot scores."""

import unittest

import numpy as np

from lane_residuals.domain.spatial_planner_pilot import (
    ARMS, FIRST, FULL, PEAK, PROTOCOL, _bootstrap, _row_statistics, score_spatial_pilot,
)
from lane_residuals.domain.spatial_planner_response import STATIONS_M


class SpatialPlannerPilotTests(unittest.TestCase):
    def test_crps_matches_discrete_pairwise_definition(self):
        draws = np.array([2.0, 0.0, 4.0, 1.0])
        observed = 1.5
        direct = np.mean(abs(draws - observed)) - np.mean(abs(draws[:, None] - draws)) / 2
        self.assertAlmostEqual(_row_statistics(draws, observed)["crps"], direct)
        self.assertEqual(_row_statistics(np.zeros(1), observed)["crps"], observed)

    def test_bootstrap_keeps_row_weights_and_whole_blocks(self):
        contrasts = np.array([0.0] * 8 + [1.0] * 4)
        blocks = np.array([0] * 8 + [1, 2, 3, 4])
        result = _bootstrap(contrasts, blocks)
        self.assertAlmostEqual(result["mean_crps_difference_vs_full"], 1 / 3)
        self.assertEqual(result["blocks"], 5)
        self.assertEqual(result, _bootstrap(contrasts, blocks))
        self.assertIsNone(_bootstrap(contrasts, np.zeros(len(blocks)))["central_95_block_bootstrap_interval"])

    def test_speed_sensitivity_common_support_and_identical_profile_control(self):
        profile = np.linspace(0.0, 1.0, len(STATIONS_M))
        arrays = {
            "speed_mps": np.array([20.0, 38.0, 41.0]),
            "eligible": np.array([True, True, False]),
            "residuals_m": np.tile(profile, (3, 1)),
            "stations_m": np.array(STATIONS_M),
            "conditioned_sequence_offsets": np.array([0, 2, 3]),
        }
        rows = [{"estimate_source_time_ns_decimal": str(i * 10**10)} for i in range(3)]
        arms = {name: np.tile(profile, (PROTOCOL["draws"], 1)) for name in ARMS}
        arms["nominal"] = np.zeros((1, len(STATIONS_M)))
        result = score_spatial_pilot(arrays, rows, arms)
        self.assertEqual(result["primary"]["rows"], 2)
        self.assertEqual(result["excluded_from_speed_sensitivity"], 1)
        self.assertTrue(all(v["rows"] == 1 for v in result["speed_sensitivity"].values()))
        for metric in (PEAK, FIRST):
            self.assertAlmostEqual(result["primary"]["arms"][FULL][metric]["crps"], 0)
        self.assertAlmostEqual(result["primary"]["prefix_primary_crps"][FULL], 0)
        self.assertGreater(result["primary"]["arms"]["nominal"][PEAK]["crps"], 0)
        self.assertNotEqual(result["speed_sensitivity"]["minus_4_mps"]["replay"][PEAK]["mean"],
                            result["speed_sensitivity"]["plus_4_mps"]["replay"][PEAK]["mean"])

    def test_mismatched_primary_mask_fails(self):
        arms = {name: np.zeros((1 if name == "nominal" else PROTOCOL["draws"], 21))
                for name in ARMS}
        arrays = {"speed_mps": np.array([20.0]), "eligible": np.array([False]),
                  "stations_m": np.array(STATIONS_M)}
        with self.assertRaisesRegex(ValueError, "eligibility"):
            score_spatial_pilot(arrays, [], arms)


if __name__ == "__main__":
    unittest.main()
