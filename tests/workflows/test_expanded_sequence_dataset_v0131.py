import json
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.domain.motion import OdometrySample, Pose2D
from lane_residuals.io.expanded_sequence_dataset_v0131 import BoundaryOdometryStream
from lane_residuals.workflows.expanded_sequence_dataset_v0131 import (
    _parity_with_v0130,
    _restore_boundary_odometry_features,
)


SENSOR = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"
SCHEMA = ("Adp.OdometryState|protobuf|sha256:abc",)


def _sample(timestamp, x):
    return OdometrySample(timestamp, timestamp, timestamp, Pose2D(x, 0.0, 0.0))


def _stream(name, samples, schema=SCHEMA):
    return BoundaryOdometryStream(
        basename_private=name,
        topic="/adp/odometry",
        message_count=len(samples),
        samples=tuple(samples),
        schema_identities=schema,
        failure_counts={},
        conflicting_duplicate_timestamp_group_count=0,
    )


def _message(recording, basename, timestamp):
    return {
        "recording_id": recording,
        "drive_id": "drive_001",
        "mcap_basename_private": basename,
        "pair_index": "0",
        "source_time_ns_private": str(timestamp),
        "topology_source_name": SENSOR,
        "h100_aligned_eligible": "True",
    }


def _feature():
    return {
        "feature_state": "not_ready",
        "failure_codes": "speed__odometry_reference_time_outside_coverage",
        "estimated_mean_abs_curvature_per_m": 0.1,
        "estimated_curvature_delta_per_m": 0.01,
        "confidence_near_mean": 0.9,
        "confidence_middle_mean": 0.8,
        "confidence_far_mean": 0.7,
    }


class ExpandedSequenceV0131WorkflowTests(unittest.TestCase):
    def _restore(self, right_schema=SCHEMA):
        messages = [
            _message("recording_001", "a.mcap", 100_000_000),
            _message("recording_002", "b.mcap", 150_000_000),
        ]
        features = {("recording_002", 0): _feature()}
        streams = {
            "a.mcap": _stream(
                "a.mcap",
                (_sample(90_000_000, 0.9), _sample(110_000_000, 1.1)),
            ),
            "b.mcap": _stream(
                "b.mcap",
                (_sample(140_000_000, 1.4), _sample(160_000_000, 1.6)),
                schema=right_schema,
            ),
        }

        def loader(path, *, basename_private, topic):
            return streams[basename_private]

        rows, restored = _restore_boundary_odometry_features(
            messages=messages,
            continuity_rows=[{
                "drive_id": "drive_001",
                "left_recording_id": "recording_001",
                "right_recording_id": "recording_002",
                "stitchable": "True",
            }],
            features=features,
            resolved_paths={"a.mcap": Path("a.mcap"), "b.mcap": Path("b.mcap")},
            odometry_topic="/adp/odometry",
            maximum_odometry_gap_ns=30_000_000,
            maximum_contiguous_gap_ms=200.0,
            stream_loader=loader,
        )
        return rows[0], restored, features[("recording_002", 0)]

    def test_accepted_boundary_restores_only_frozen_speed(self):
        row, restored, feature = self._restore()
        self.assertTrue(row["immediate_sensor_h100_candidate"])
        self.assertTrue(row["feature_restored"])
        self.assertEqual(row["recording_local_feature_state"], "not_ready")
        self.assertEqual(feature["feature_state"], "ready")
        self.assertAlmostEqual(feature["speed_mps"], 10.0)
        self.assertEqual(
            feature["speed_evaluation_method"],
            "accepted_previous_mcap_odometry_50ms_displacement",
        )
        self.assertEqual(
            json.loads(row["contributing_mcap_basenames_json_private"]),
            ["a.mcap", "b.mcap"],
        )
        self.assertEqual(set(restored), {("recording_002", 0)})

    def test_schema_mismatch_preserves_failure_and_reason(self):
        row, restored, feature = self._restore(
            ("Other.Odometry|protobuf|sha256:def",)
        )
        self.assertFalse(row["feature_restored"])
        self.assertIn("odometry_schema_incompatible", row["rejection_reasons"])
        self.assertEqual(restored, {})
        self.assertEqual(feature["feature_state"], "not_ready")

    def test_v0130_parity_compares_tensor_bytes_not_metadata_only(self):
        baseline = {
            "recording_ids": np.asarray(["r1"]),
            "pair_indices": np.asarray([1], dtype=np.int64),
            "residuals_m": np.zeros((1, 21), dtype=np.float64),
            "conditions": np.ones((1, 6), dtype=np.float64),
        }
        current = {
            "recording_ids": np.asarray(["r1", "r2"]),
            "pair_indices": np.asarray([1, 0], dtype=np.int64),
            "residuals_m": np.zeros((2, 21), dtype=np.float64),
            "conditions": np.ones((2, 6), dtype=np.float64),
        }
        result = _parity_with_v0130(baseline, current)
        self.assertTrue(result["non_boundary_residual_bytes_identical"])
        self.assertTrue(result["non_boundary_feature_bytes_identical"])
        self.assertEqual(result["added_boundary_profile_count"], 1)
        current["conditions"][0, 0] = 2.0
        with self.assertRaisesRegex(ValueError, "parity failed"):
            _parity_with_v0130(baseline, current)


if __name__ == "__main__":
    unittest.main()
