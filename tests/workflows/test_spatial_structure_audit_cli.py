from __future__ import annotations

import unittest
from unittest.mock import patch

from lane_residuals.cli.spatial_structure_audit import main


class SpatialStructureAuditCliTest(unittest.TestCase):
    @patch(
        "lane_residuals.cli.spatial_structure_audit.run_spatial_structure_audit"
    )
    def test_success(self, run_audit) -> None:
        run_audit.return_value = (
            {"generated_profile_count_per_arm": 12, "sequence_count": 2},
            0,
        )

        status = main(["a2", "a3", "--output-directory", "result"])

        self.assertEqual(status, 0)
        run_audit.assert_called_once()

    @patch(
        "lane_residuals.cli.spatial_structure_audit.run_spatial_structure_audit",
        side_effect=ValueError("contract drift"),
    )
    def test_contract_error_returns_two(self, run_audit) -> None:
        self.assertEqual(main(["a2", "a3"]), 2)
        run_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
