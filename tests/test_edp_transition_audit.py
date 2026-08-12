import unittest

import numpy as np

from lane_residuals.edp_transition_audit import (
    CandidateSnapshot,
    SelectedTransition,
    compare_selected_candidates,
    detect_station_correspondence,
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
        segment_starts=np.asarray((0.0, 50.0, 100.0)),
        curvature_change=np.asarray((0.0, 0.0)),
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


def _snapshot_from_parameters(message_index, parameters, *, stations):
    geometries = []
    for meaning in ("curvature_rate", "curvature_delta"):
        curve = generate_spline_curve(
            parameters,
            meaning=meaning,
            max_step_m=0.25,
            extra_stations=stations,
        )
        geometries.append(
            sample_candidate_curve(
                curve,
                message_index=message_index,
                path_index=0,
                stations_m=stations,
            )
        )
    return CandidateSnapshot(
        message_index=message_index,
        source_time_ns=(message_index + 1) * 80_000_000,
        path_index=0,
        topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        role_symbol="LANE_ROLE_KEEP_LANE",
        error_symbol="DRIVE_PATH_ERROR_NO_ERROR",
        selected_unique_keep_lane=True,
        selected_for_pairing_audit=True,
        candidate_status="joint_audit_candidate",
        failure_codes=(),
        model_flag_value=True,
        lane_topology_ids=(10,),
        confidences=(0.5, 0.7),
        parameters=parameters,
        geometries=tuple(geometries),
    )


def _rollover_parameters(*, perturb_retained_rate=0.0):
    shift = 31.34266104145169
    previous = SplineParameters(
        x_0=-4.0,
        y_0=1.0,
        theta_0=0.2,
        curvature_0=0.001,
        segment_starts=np.asarray((0.0, shift, shift + 30.0, shift + 60.0, shift + 90.0)),
        curvature_change=np.asarray((1e-4, -2e-4, 3e-4, 0.0)),
        index_0=0,
        index_0_presence_evidence="implicit_default",
        index_0_explicitly_present=False,
    )
    current = SplineParameters(
        x_0=8.0,
        y_0=-3.0,
        theta_0=-0.7,
        curvature_0=previous.curvature_0 + previous.curvature_change[0] * shift,
        segment_starts=np.asarray((0.0, 30.0, 60.0, 90.0, 130.0)),
        curvature_change=np.asarray(
            (-2e-4, 3e-4 + perturb_retained_rate, 0.0, 4e-4)
        ),
        index_0=0,
        index_0_presence_evidence="implicit_default",
        index_0_explicitly_present=False,
    )
    return shift, previous, current


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
        self.assertFalse(transition.same_station_metrics_valid)
        self.assertEqual(
            transition.station_correspondence_failure_code,
            "edp_transition_candidate_identity_changed",
        )

    def test_non_grid_rollover_uses_shifted_stations_and_invalidates_same_station_metrics(self):
        shift, previous_parameters, current_parameters = _rollover_parameters()
        stations = tuple(float(value) for value in range(0, 91, 10))
        previous = _snapshot_from_parameters(0, previous_parameters, stations=stations)
        current = _snapshot_from_parameters(1, current_parameters, stations=stations)

        rate = compare_selected_candidates(
            previous,
            current,
            hypothesis="curvature_rate",
        )
        delta = compare_selected_candidates(
            previous,
            current,
            hypothesis="curvature_delta",
        )

        self.assertTrue(rate.rollover_detected)
        self.assertEqual(rate.dropped_interval_count, 1)
        self.assertAlmostEqual(rate.station_shift_m, shift)
        self.assertFalse(rate.interval_count_changed)
        self.assertFalse(rate.same_station_metrics_valid)
        self.assertIsNone(rate.station_zero_position_jump_m)
        self.assertIsNone(rate.sampled_position_rms_m)
        self.assertEqual(rate.shift_aware_metric_status, "ready")
        self.assertEqual(rate.shift_aware_station_count, len(stations))
        self.assertAlmostEqual(rate.shift_aware_maximum_current_station_m, 90.0)
        self.assertLess(rate.shift_aware_shape_rms_m, 1e-3)
        self.assertLess(abs(rate.rate_curvature_at_shift_delta_per_m), 1e-12)
        self.assertGreater(delta.shift_aware_shape_rms_m, 0.1)

    def test_repeated_uniform_boundaries_do_not_create_false_rollover(self):
        previous = SplineParameters(
            x_0=0.0,
            y_0=0.0,
            theta_0=0.0,
            curvature_0=0.0,
            segment_starts=np.asarray((0.0, 30.0, 60.0, 90.0, 120.0)),
            curvature_change=np.zeros(4),
            index_0=0,
            index_0_presence_evidence="implicit_default",
            index_0_explicitly_present=False,
        )
        current = SplineParameters(
            x_0=0.0,
            y_0=0.0,
            theta_0=0.0,
            curvature_0=0.0,
            segment_starts=np.asarray((0.0, 30.0, 60.0, 90.0, 125.0)),
            curvature_change=np.zeros(4),
            index_0=0,
            index_0_presence_evidence="implicit_default",
            index_0_explicitly_present=False,
        )

        result = detect_station_correspondence(previous, current)

        self.assertEqual(result.status, "unassessed")
        self.assertFalse(result.rollover_detected)
        self.assertEqual(
            result.failure_code,
            "rollover_boundary_alignment_ambiguous",
        )

    def test_boundary_count_change_without_suffix_invariant_is_unassessed(self):
        previous = _parameters()
        current = SplineParameters(
            x_0=0.0,
            y_0=0.0,
            theta_0=0.0,
            curvature_0=0.0,
            segment_starts=np.asarray((0.0, 25.0, 55.0, 85.0)),
            curvature_change=np.zeros(3),
            index_0=0,
            index_0_presence_evidence="implicit_default",
            index_0_explicitly_present=False,
        )

        result = detect_station_correspondence(previous, current)

        self.assertEqual(result.status, "unassessed")
        self.assertIn(
            result.failure_code,
            {
                "rollover_boundary_alignment_ambiguous",
                "rollover_boundary_overlap_insufficient",
            },
        )
        self.assertFalse(result.rollover_detected)

    def test_tied_uniform_alignment_fails_closed(self):
        def parameters(boundaries):
            return SplineParameters(
                x_0=0.0,
                y_0=0.0,
                theta_0=0.0,
                curvature_0=0.0,
                segment_starts=np.asarray(boundaries),
                curvature_change=np.zeros(len(boundaries) - 1),
                index_0=0,
                index_0_presence_evidence="implicit_default",
                index_0_explicitly_present=False,
            )

        result = detect_station_correspondence(
            parameters((0.0, 30.0, 60.0, 90.0)),
            parameters((0.0, 30.0, 60.0)),
        )

        self.assertEqual(result.status, "unassessed")
        self.assertEqual(
            result.failure_code,
            "rollover_boundary_alignment_ambiguous",
        )

    def test_perturbed_retained_rate_produces_nonzero_shift_aware_shape_error(self):
        _, previous_parameters, current_parameters = _rollover_parameters(
            perturb_retained_rate=1e-4
        )
        stations = tuple(float(value) for value in range(0, 91, 10))
        transition = compare_selected_candidates(
            _snapshot_from_parameters(0, previous_parameters, stations=stations),
            _snapshot_from_parameters(1, current_parameters, stations=stations),
            hypothesis="curvature_rate",
        )

        self.assertTrue(transition.rollover_detected)
        self.assertGreater(transition.shift_aware_shape_rms_m, 0.01)

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
            hypothesis="curvature_delta",
            maximum_centers=2,
            minimum_separation_messages=7,
        )

        self.assertEqual(centers, (12, 30))


if __name__ == "__main__":
    unittest.main()
