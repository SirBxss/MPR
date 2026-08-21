import json
import tempfile
import unittest
from pathlib import Path

from lane_residuals.visualization.topology_semantics import (
    plot_topology_quality_diagnostic,
)
from lane_residuals.workflows.topology_semantics_audit import (
    _summary_row,
    _transition,
)


def _row(recording: str, message: int, source: int, name: str):
    return {
        "recording_id": recording,
        "drive_id": "drive_006",
        "mcap_basename_private": f"{recording}.mcap",
        "message_index": message,
        "source_time_ns_private": 1_000_000_000 + message * 80_000_000,
        "topology_decoded_value": source,
        "topology_source_name": name,
        "mutual_nearest_pair_present": True,
        "estimator_state": "available_no_error",
        "selected_drive_path_count": 1,
        "selected_drive_path_index": 0,
        "estimate_geometry_state": "geometry_ready",
        "estimate_geometry_failure_code": None,
        "map_geometry_state": "geometry_ready",
        "map_geometry_failure_code": None,
        "source_delta_ms": 20.0,
        "anchor_distance_m": 1.2,
        "anchor_heading_delta_rad": 0.02,
        "h60_aligned_eligible": True,
        "h100_aligned_eligible": True,
    }


class TopologySemanticsWorkflowTests(unittest.TestCase):
    def test_within_and_cross_mcap_transitions_are_explicit(self):
        sensor = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"
        lane_map = "ROAD_TOPOLOGY_SOURCE_LANE_MAP"
        left = _row("recording_038", 249, 4, sensor)
        right = _row("recording_039", 0, 3, lane_map)
        transition = _transition(
            left, right, edge_scope="cross_mcap_boundary", boundary_stitchable=True
        )
        self.assertTrue(transition["topology_source_changed"])
        self.assertEqual(transition["edge_scope"], "cross_mcap_boundary")
        self.assertTrue(transition["boundary_stitchable"])
        self.assertTrue(transition["within_physical_session"])

    def test_recording_summary_retains_distributions_and_quantiles(self):
        sensor = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"
        lane_map = "ROAD_TOPOLOGY_SOURCE_LANE_MAP"
        rows = [
            _row("recording_038", 0, 4, sensor),
            _row("recording_038", 1, 3, lane_map),
        ]
        transition = _transition(
            rows[0], rows[1], edge_scope="within_mcap", boundary_stitchable=None
        )
        summary = _summary_row(
            rows, recording_id="recording_038", drive_id="drive_006",
            basename="recording_038.mcap", recording_count=1,
            transitions=[transition],
        )
        self.assertEqual(summary["message_count"], 2)
        self.assertEqual(summary["source_delta_q50"], 20.0)
        self.assertEqual(summary["topology_transition_count"], 1)
        self.assertEqual(
            json.loads(summary["topology_source_counts_json"]),
            {lane_map: 1, sensor: 1},
        )

    def test_diagnostic_plot_is_single_deterministic_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "diagnostic.png"
            plot_topology_quality_diagnostic(
                path,
                message_rows=[
                    _row(
                        "recording_038", 0, 4,
                        "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
                    )
                ],
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
