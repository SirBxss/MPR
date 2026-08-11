import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals import ego_relative_path_from_points
from lane_residuals.pairing_audit_cli import _TimedPath, main, run_pairing_audit


class PairingAuditCliTests(unittest.TestCase):
    def test_missing_mcap_returns_argument_error(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.mcap"
            with contextlib.redirect_stderr(stderr):
                status = main([str(missing)])
        self.assertEqual(status, 2)

    def test_invalid_timestamp_gate_is_rejected(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(["missing.mcap", "--maximum-pair-delta-ms", "-1"])
        self.assertEqual(status, 2)

    def test_synthetic_audit_writes_only_diagnostic_outputs(self) -> None:
        x = np.linspace(-5.0, 120.0, 126)
        estimate_path = ego_relative_path_from_points(
            np.column_stack((x, np.full_like(x, 0.2))),
            source="estimate",
        )
        reference_path = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))),
            source="reference",
        )
        estimate = _TimedPath(1, 100_000_000, 1, 1, estimate_path)
        reference = _TimedPath(2, 90_000_000, 1, 1, reference_path)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit"
            arguments = SimpleNamespace(
                mcap=Path("synthetic.mcap"),
                estimate_topic="/adp/estimated_drive_paths",
                map_topic="/adp/road_lane_map_based",
                max_step_m=0.25,
                max_pairs=20,
                maximum_pair_delta_ms=None,
                output_directory=output,
            )
            with patch(
                "lane_residuals.pairing_audit_cli._decode_paths",
                return_value=(
                    [estimate],
                    [reference],
                    {},
                    {"estimate_messages": 1, "map_messages": 1},
                ),
            ):
                summary = run_pairing_audit(
                    arguments,
                    stations_m=tuple(float(value) for value in range(0, 101, 5)),
                )

            self.assertEqual(summary["diagnostic_ready_pair_count"], 1)
            self.assertFalse(summary["generated_final_residual_dataset"])
            self.assertFalse(
                summary["diagnostic_disagreement_is_lane_estimation_error"]
            )
            self.assertTrue((output / "pairing_audit.csv").is_file())
            self.assertTrue((output / "diagnostic_disagreement.csv").is_file())
            self.assertTrue((output / "pairing_overlays.png").is_file())
            self.assertTrue((output / "pairing_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
