import tempfile
import unittest
from pathlib import Path

from lane_residuals.visualization.expanded_sequence_dataset_v0131 import (
    plot_expanded_sequence_diagnostics_v0131,
)


class ExpandedSequenceV0131VisualizationTests(unittest.TestCase):
    def test_boundary_context_plot_is_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plot.png"
            plot_expanded_sequence_diagnostics_v0131(
                path,
                drive_rows=[{
                    "drive_id": "drive_001",
                    "eligible_profile_count": 4,
                    "excluded_profile_count": 1,
                }],
                sequence_rows=[{"frame_count": 4}],
                profile_rows=[{
                    "profile_eligible": True,
                    "anchor_heading_delta_rad": 0.02,
                }],
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
