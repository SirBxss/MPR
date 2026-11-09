from dataclasses import replace
from types import SimpleNamespace
import unittest

import numpy as np

from lane_residuals.domain.cached_planner_scenarios import prepare_scenario_rows
from lane_residuals.domain.reference_planner import ReferencePlannerConfig, plan_reference_horizon
from lane_residuals.domain.spatial_planner_response import STATIONS_M, SpatialPlannerScenario, build_spatial_response


class CachedScenarioPolicyTests(unittest.TestCase):
    def block(self):
        indices = np.array([0, 2, 4, 6], dtype=np.int64)
        arrays = {
            "conditioned_profile_indices": indices,
            "stations_m": np.asarray(STATIONS_M),
            "recording_id": np.array(["recording"] * 7),
            "estimate_source_time_ns_decimal": np.array([str(10**19 + i) for i in range(7)]),
            "reference_source_time_ns_decimal": np.array([str(10**19 + i) for i in range(7)]),
            **{name: np.arange(7) for name in
               ("candidate_index", "pair_index", "estimate_message_index", "reference_message_index")},
        }
        x = np.zeros((4, 6))
        x[:, 0] = (0.0, 15.0, 45.0, -1.0)
        return SimpleNamespace(
            outing_id="outing_a", y=np.arange(84).reshape(4, 21), x=x, offsets=np.array([0, 2, 4]),
            archive=SimpleNamespace(arrays=arrays, summary_sha256="a" * 64,
                                    raw_sha256_by_recording={"recording": "b" * 64}),
        )

    def test_identity_precision_resets_and_all_row_denominators(self):
        block = self.block()
        rows, arrays, summary = prepare_scenario_rows(
            block, {"validation_outing": "outing_a", "training_outings": ["outing_b"]})
        self.assertEqual([r["geometry_profile_row"] for r in rows], [0, 2, 4, 6])
        self.assertEqual(rows[2]["estimate_source_time_ns_decimal"], str(10**19 + 4))
        self.assertEqual(summary["original_complete_rows"], 4)
        self.assertEqual(summary["eligible_rows"], 1)
        self.assertEqual(sum(summary["status_counts"].values()), 4)
        self.assertEqual(rows[0]["status"], "speed_below_planner_minimum")
        self.assertEqual(rows[2]["status"], "lookahead_exceeds_100m")
        np.testing.assert_array_equal(arrays["eligible"], [False, True, False, False])
        np.testing.assert_array_equal(arrays["residuals_m"], block.y)
        np.testing.assert_array_equal(arrays["conditioned_sequence_offsets"], block.offsets)

    def test_incremental_trace_cancels_two_nonzero_initial_states(self):
        config = ReferencePlannerConfig()
        scenario = SpatialPlannerScenario(22.0, 0.1)
        residual = 0.1 + 0.2 * np.sin(np.asarray(STATIONS_M) / 30)
        gains = build_spatial_response(scenario, config)
        for lateral, heading, curvature in ((0.4, -0.06, 0.01), (-0.7, 0.02, -0.015)):
            state = replace(scenario, lateral_error_m=lateral, heading_error_rad=heading,
                            previous_curvature_correction_per_m=curvature)
            inputs = dict(
                stations_m=np.asarray(STATIONS_M), config=config,
                speed_mps=state.speed_mps, dt_s=state.dt_s, lateral_error_m=state.lateral_error_m,
                heading_error_rad=state.heading_error_rad,
                previous_curvature_correction_per_m=state.previous_curvature_correction_per_m,
            )
            nominal = plan_reference_horizon(residual_profile_m=np.zeros(21), **inputs)
            perturbed = plan_reference_horizon(residual_profile_m=residual, **inputs)
            np.testing.assert_allclose(
                perturbed.lateral_error_m - nominal.lateral_error_m,
                residual @ gains.lateral_response, atol=2e-15,
            )
            np.testing.assert_allclose(
                perturbed.curvature_correction_per_m - nominal.curvature_correction_per_m,
                residual @ gains.curvature_response, atol=2e-15,
            )

    def test_duplicate_identity_and_wrong_fold_are_rejected(self):
        block = self.block()
        fold = {"validation_outing": "outing_a", "training_outings": ["outing_a"]}
        with self.assertRaisesRegex(ValueError, "held out"):
            prepare_scenario_rows(block, fold)
        fold["training_outings"] = ["outing_b"]
        block.archive.arrays["conditioned_profile_indices"][1] = 0
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare_scenario_rows(block, fold)
