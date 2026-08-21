import tempfile
import unittest
from pathlib import Path

from lane_residuals.visualization.expanded_sequence_dataset import (
    plot_expanded_sequence_diagnostics,
)


class ExpandedSequenceVisualizationTests(unittest.TestCase):
    def test_plot_accepts_clean_and_mixed_drive_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plot.png"
            plot_expanded_sequence_diagnostics(
                path,
                drive_rows=[
                    {"drive_id": "drive_001", "eligible_profile_count": 4, "excluded_profile_count": 1},
                    {"drive_id": "drive_005", "eligible_profile_count": 2, "excluded_profile_count": 8},
                ],
                sequence_rows=[{"frame_count": 4}, {"frame_count": 2}],
                profile_rows=[{"profile_eligible": True, "anchor_heading_delta_rad": .02}],
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
