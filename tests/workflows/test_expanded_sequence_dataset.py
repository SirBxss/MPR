import unittest

import numpy as np

from lane_residuals.domain.expanded_sequence_dataset import (
    EXPECTED_TOPOLOGY_SOURCE,
    ExpandedProfile,
)
from lane_residuals.workflows.expanded_sequence_dataset import (
    _build_sequences_and_stitch_audit,
    _make_audit_rows,
)


def _message(recording, drive, basename, pair, timestamp, anchor=0.2):
    return {
        "recording_id": recording,
        "drive_id": drive,
        "mcap_basename_private": basename,
        "pair_index": str(pair),
        "message_index": str(pair),
        "source_time_ns_private": str(timestamp),
        "topology_source_name": EXPECTED_TOPOLOGY_SOURCE,
        "h100_aligned_eligible": "True",
        "anchor_distance_m": str(anchor),
        "anchor_heading_delta_rad": "0.02",
        "source_delta_ms": "-20.0",
        "estimator_state": "available_no_error",
        "estimate_geometry_state": "geometry_ready",
        "estimate_geometry_failure_code": "",
        "map_geometry_state": "geometry_ready",
        "map_geometry_failure_code": "",
    }


def _feature(recording, pair):
    return {
        "recording_id": recording,
        "pair_index": pair,
        "feature_state": "ready",
        "speed_mps": 10.0,
        "estimated_mean_abs_curvature_per_m": 0.01,
        "estimated_curvature_delta_per_m": 0.001,
        "confidence_near_mean": 0.9,
        "confidence_middle_mean": 0.8,
        "confidence_far_mean": 0.7,
    }


class ExpandedSequenceWorkflowTests(unittest.TestCase):
    def test_anchor_gate_excludes_h100_without_heading_threshold(self):
        messages = [_message("recording_038", "drive_006", "a.mcap", 84, 100, anchor=5.8)]
        residuals = {("recording_038", 84): np.zeros(21)}
        features = {("recording_038", 84): _feature("recording_038", 84)}
        rows, profiles = _make_audit_rows(messages, residuals, features)
        self.assertEqual(profiles, {})
        self.assertIn("anchor_distance_exceeds_1m", rows[0]["exclusion_reasons"])
        self.assertNotIn("heading", rows[0]["exclusion_reasons"])

    def test_accepted_boundary_stitches_and_preserves_recording_ids(self):
        messages = [
            _message("recording_001", "drive_001", "a.mcap", 0, 100),
            _message("recording_002", "drive_001", "b.mcap", 0, 180_000_100),
        ]
        residuals = {(row["recording_id"], int(row["pair_index"])): np.zeros(21) for row in messages}
        features = {(row["recording_id"], int(row["pair_index"])): _feature(row["recording_id"], int(row["pair_index"])) for row in messages}
        rows, eligible = _make_audit_rows(messages, residuals, features)
        continuity = [{
            "left_recording_id": "recording_001",
            "right_recording_id": "recording_002",
            "stitchable": "True",
        }]
        sequences, stitches = _build_sequences_and_stitch_audit(
            rows, eligible, continuity, maximum_gap_ms=200.0
        )
        self.assertEqual(len(sequences), 1)
        self.assertEqual(
            [frame.recording_id for frame in sequences[0].frames],
            ["recording_001", "recording_002"],
        )
        self.assertTrue(stitches[0]["immediately_eligible_boundary_candidate"])
        self.assertTrue(stitches[0]["stitched"])

    def test_lane_map_interval_prevents_stitching(self):
        messages = [
            _message("recording_001", "drive_001", "a.mcap", 0, 100),
            {
                **_message("recording_002", "drive_001", "b.mcap", 0, 80_000_100),
                "topology_source_name": "ROAD_TOPOLOGY_SOURCE_LANE_MAP",
            },
        ]
        residuals = {(row["recording_id"], int(row["pair_index"])): np.zeros(21) for row in messages}
        features = {(row["recording_id"], int(row["pair_index"])): _feature(row["recording_id"], int(row["pair_index"])) for row in messages}
        rows, eligible = _make_audit_rows(messages, residuals, features)
        sequences, stitches = _build_sequences_and_stitch_audit(
            rows, eligible,
            [{"left_recording_id": "recording_001", "right_recording_id": "recording_002", "stitchable": "True"}],
            maximum_gap_ms=200.0,
        )
        self.assertEqual(len(sequences), 1)
        self.assertFalse(stitches[0]["immediately_eligible_boundary_candidate"])
        self.assertFalse(stitches[0]["stitched"])
        self.assertIn("topology_source_change", stitches[0]["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
