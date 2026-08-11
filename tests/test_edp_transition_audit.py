import unittest

import numpy as np

from lane_residuals.edp_transition_audit import (
    CandidateSnapshot,
    SelectedTransition,
    compare_selected_candidates,
    rank_transition_centers,
    sample_candidate_curve,
)
from lane_residuals.geometry_validation import SplineParameters, generate_spline_curve


def _parameters(*, x_0=0.0, y_0=0.0, theta_0=0.0, curvature=0.0):
    return SplineParameters(
        x_0=x_0,
        y_0=y_0,
        theta_0=theta_0,
        curvature_0=curvature,
        segment_starts=np.asarray((0.0, 100.0)),
        curvature_change=np.asarray((0.0,)),
        index_0=0,
        index_0_presence_evidence="implicit_default",
        index_0_explicitly_present=False,
    )


def _snapshot(
    message_index,
    *,
    path_index=0,
    x_0=0.0,
    y_0=0.0,
    theta_0=0.0,
    topology_ids=(10,),
):
    parameters = _parameters(x_0=x_0, y_0=y_0, theta_0=theta_0)
    geometries = []
    for meaning in ("curvature_rate", "curvature_delta"):
        curve = generate_spline_curve(
            parameters,
            meaning=meaning,
            max_step_m=1.0,
            extra_stations=(0.0, 50.0, 100.0),
        )
        geometries.append(
            sample_candidate_curve(
                curve,
                message_index=message_index,
                path_index=path_index,
                stations_m=(0.0, 50.0, 100.0),
            )
        )
    return CandidateSnapshot(
        message_index=message_index,
        source_time_ns=message_index * 80_000_000,
        path_index=path_index,
        topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        role_symbol="LANE_ROLE_KEEP_LANE",
        error_symbol="DRIVE_PATH_ERROR_NO_ERROR",
        selected_unique_keep_lane=True,
        selected_for_pairing_audit=True,
        candidate_status="joint_audit_candidate",
        failure_codes=(),
        model_flag_value=True,
        lane_topology_ids=tuple(topology_ids),
        confidences=(0.5, 0.7),
        parameters=parameters,
        geometries=tuple(geometries),
    )


class EdpTransitionAuditTests(unittest.TestCase):
    def test_pure_pose_shift_is_removed_only_in_explicit_shape_metric(self):
        previous = _snapshot(0)
        current = _snapshot(1, x_0=1.0, y_0=2.0)

        transition = compare_selected_candidates(
            previous,
            current,
            hypothesis="curvature_delta",
        )

        expected = np.hypot(1.0, 2.0)
        self.assertAlmostEqual(transition.station_zero_position_jump_m, expected)
        self.assertAlmostEqual(transition.endpoint_position_jump_m, expected)
        self.assertAlmostEqual(transition.sampled_position_rms_m, expected)
        self.assertAlmostEqual(transition.rigid_normalized_shape_rms_m, 0.0)
        self.assertEqual(transition.source_delta_ms, 80.0)

    def test_candidate_index_and_topology_changes_are_exposed(self):
        previous = _snapshot(4, path_index=0, topology_ids=(10,))
        current = _snapshot(5, path_index=2, topology_ids=(11,))

        transition = compare_selected_candidates(
            previous,
            current,
            hypothesis="curvature_rate",
        )

        self.assertTrue(transition.selected_path_index_changed)
        self.assertTrue(transition.lane_topology_ids_changed)

    def test_ranking_uses_largest_nonoverlapping_changes_without_threshold(self):
        transitions = [
            SelectedTransition(
                previous_message_index=index - 1,
                current_message_index=index,
                previous_path_index=0,
                current_path_index=0,
                hypothesis="curvature_delta",
                source_delta_ms=80.0,
                topology_source_changed=False,
                lane_topology_ids_changed=False,
                selected_path_index_changed=False,
                interval_count_changed=False,
                x_0_delta_m=0.0,
                y_0_delta_m=0.0,
                theta_0_delta_rad=0.0,
                curvature_0_delta_per_m=0.0,
                confidence_mean_delta=0.0,
                common_station_count=3,
                maximum_common_station_m=100.0,
                station_zero_position_jump_m=0.0,
                endpoint_position_jump_m=score,
                sampled_position_rms_m=score,
                rigid_normalized_shape_rms_m=score,
            )
            for index, score in ((10, 5.0), (12, 10.0), (30, 7.0))
        ]

        centers = rank_transition_centers(
            transitions,
            maximum_centers=2,
            minimum_separation_messages=7,
        )

        self.assertEqual(centers, (12, 30))


if __name__ == "__main__":
    unittest.main()
