from __future__ import annotations

import math
import unittest

import numpy as np

from lane_residuals.domain.sensor_topology_feasibility import (
    SensorSegment,
    SensorTopologyAuditError,
    audit_sensor_chain,
    concatenate_boundaries,
    midpoint_from_boundaries,
    mutual_nearest_timestamp_pairs,
)


class SensorTopologyGeometryTests(unittest.TestCase):
    def test_camera_midpoint_and_single_segment_100m_span(self) -> None:
        left = np.asarray(((0.0, 2.0), (120.0, 2.0)))
        right = np.asarray(((0.0, -2.0), (120.0, -2.0)))
        midpoint = midpoint_from_boundaries(left, right)
        result = audit_sensor_chain((0,), (SensorSegment(midpoint, ()),))
        self.assertTrue(result.explicit_ego_candidate)
        self.assertTrue(result.initial_segment_structure)
        self.assertTrue(result.camera_only_successor_chain)
        self.assertTrue(result.camera_chain_100m_span)

    def test_width_boundaries_are_inclusive_and_outside_fails(self) -> None:
        for width in (1.0, 10.0):
            midpoint_from_boundaries(
                ((0.0, width / 2), (10.0, width / 2)),
                ((0.0, -width / 2), (10.0, -width / 2)),
            )
        with self.assertRaisesRegex(SensorTopologyAuditError, "outside"):
            midpoint_from_boundaries(
                ((0.0, 0.4), (10.0, 0.4)),
                ((0.0, -0.4), (10.0, -0.4)),
            )

    def test_boundary_orientation_tie_and_large_gap_fail_closed(self) -> None:
        with self.assertRaisesRegex(SensorTopologyAuditError, "exact endpoint tie"):
            concatenate_boundaries(
                (
                    ((0.0, 0.0), (1.0, 0.0)),
                    ((2.0, 1.0), (2.0, -1.0)),
                )
            )

    def test_boundary_duplicate_tolerance_is_inclusive(self) -> None:
        at_limit = concatenate_boundaries(
            (
                ((0.0, 0.0), (1.0, 0.0)),
                ((1.0 + 1e-6, 0.0), (2.0, 0.0)),
            )
        )
        outside = concatenate_boundaries(
            (
                ((0.0, 0.0), (1.0, 0.0)),
                ((1.0 + 1.01e-6, 0.0), (2.0, 0.0)),
            )
        )
        self.assertEqual(len(at_limit), 3)
        self.assertEqual(len(outside), 4)
        with self.assertRaisesRegex(SensorTopologyAuditError, "gap exceeds"):
            concatenate_boundaries(
                (
                    ((0.0, 0.0), (1.0, 0.0)),
                    ((3.0, 0.0), (4.0, 0.0)),
                )
            )

    def test_ego_index_rejects_missing_multiple_boolean_and_out_of_range(self) -> None:
        segment = SensorSegment(np.asarray(((0.0, 0.0), (101.0, 0.0))), ())
        cases = (
            ((), "sensor_ego_metadata_missing"),
            ((0, 1), "sensor_ego_segment_not_unique"),
            ((True,), "sensor_ego_metadata_invalid"),
            ((1,), "sensor_ego_metadata_invalid"),
        )
        for values, code in cases:
            with self.subTest(values=values):
                self.assertEqual(audit_sensor_chain(values, (segment,)).failure_codes, (code,))

    def test_successor_chain_boundaries_cycle_and_empty_termination(self) -> None:
        first = SensorSegment(np.asarray(((0.0, 0.0), (60.0, 0.0))), (1,))
        second = SensorSegment(np.asarray(((60.0, 0.0), (101.0, 0.0))), ())
        self.assertTrue(audit_sensor_chain((0,), (first, second)).camera_chain_100m_span)

        cycle = SensorSegment(np.asarray(((60.0, 0.0), (80.0, 0.0))), (0,))
        self.assertEqual(
            audit_sensor_chain((0,), (first, cycle)).failure_codes,
            ("sensor_camera_chain_cycle",),
        )
        empty = SensorSegment(None, (), empty_map_influenced_termination=True)
        terminated = audit_sensor_chain((0,), (first, empty))
        self.assertTrue(terminated.camera_only_successor_chain)
        self.assertFalse(terminated.camera_chain_100m_span)

    def test_successor_gap_and_heading_limits_are_inclusive(self) -> None:
        first = SensorSegment(np.asarray(((0.0, 0.0), (50.0, 0.0))), (1,))
        angle = math.radians(30.0)
        at_limit = SensorSegment(
            np.asarray(
                (
                    (51.0, 0.0),
                    (51.0 + 60.0 * math.cos(angle), 60.0 * math.sin(angle)),
                )
            ),
            (),
        )
        self.assertTrue(
            audit_sensor_chain((0,), (first, at_limit)).camera_chain_100m_span
        )

        beyond_gap = SensorSegment(np.asarray(((51.0 + 1e-6, 0.0), (112.0, 0.0))), ())
        self.assertEqual(
            audit_sensor_chain((0,), (first, beyond_gap)).failure_codes,
            ("sensor_camera_chain_junction_invalid",),
        )
        beyond_angle = math.radians(30.0001)
        turned = SensorSegment(
            np.asarray(
                (
                    (51.0, 0.0),
                    (
                        51.0 + 60.0 * math.cos(beyond_angle),
                        60.0 * math.sin(beyond_angle),
                    ),
                )
            ),
            (),
        )
        self.assertEqual(
            audit_sensor_chain((0,), (first, turned)).failure_codes,
            ("sensor_camera_chain_junction_invalid",),
        )

    def test_branch_and_segment_limit_fail_without_guessing(self) -> None:
        branch = SensorSegment(np.asarray(((0.0, 0.0), (10.0, 0.0))), (1, 2))
        leaf = SensorSegment(np.asarray(((10.0, 0.0), (20.0, 0.0))), ())
        self.assertEqual(
            audit_sensor_chain((0,), (branch, leaf, leaf)).failure_codes,
            ("sensor_camera_chain_junction_invalid",),
        )

        segments = tuple(
            SensorSegment(
                np.asarray(((5.0 * index, 0.0), (5.0 * (index + 1), 0.0))),
                (() if index == 16 else (index + 1,)),
            )
            for index in range(17)
        )
        self.assertEqual(
            audit_sensor_chain((0,), segments).failure_codes,
            ("sensor_camera_chain_limit_exceeded",),
        )

    def test_single_segment_span_is_orientation_invariant(self) -> None:
        forward = SensorSegment(np.asarray(((0.0, 0.0), (100.0, 0.0))), ())
        reverse = SensorSegment(np.asarray(((100.0, 0.0), (0.0, 0.0))), ())
        self.assertTrue(audit_sensor_chain((0,), (forward,)).camera_chain_100m_span)
        self.assertTrue(audit_sensor_chain((0,), (reverse,)).camera_chain_100m_span)

    def test_mutual_nearest_gate_is_inclusive_and_ties_are_not_guessed(self) -> None:
        accepted = mutual_nearest_timestamp_pairs((100_000_000,), (150_000_000,))
        self.assertEqual(len(accepted.pairs), 1)
        rejected = mutual_nearest_timestamp_pairs((100_000_000,), (150_000_001,))
        self.assertEqual(len(rejected.pairs), 0)
        self.assertEqual(len(rejected.rejected_by_gate), 1)
        tied = mutual_nearest_timestamp_pairs((100,), (90, 110), maximum_delta_ns=50)
        self.assertEqual(tied.pairs, ())
        self.assertEqual(tied.ambiguous_first_positions, (0,))


if __name__ == "__main__":
    unittest.main()
