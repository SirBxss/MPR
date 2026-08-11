import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals import ego_relative_path_from_points
from lane_residuals.pairing_audit_cli import (
    _TimedPath,
    _decode_paths,
    main,
    run_pairing_audit,
)


class PairingAuditCliTests(unittest.TestCase):
    @staticmethod
    def _timed_path(
        *,
        message_index: int,
        source_time_ns: int,
        path,
        failure_code: str | None = None,
    ) -> _TimedPath:
        return _TimedPath(
            message_index=message_index,
            source_time_ns=source_time_ns,
            log_time_ns=source_time_ns,
            publish_time_ns=source_time_ns,
            geometry_state=(
                "geometry_ready" if path is not None else "geometry_not_ready"
            ),
            failure_code=failure_code,
            path=path,
        )

    def test_missing_mcap_returns_argument_error(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.mcap"
            with contextlib.redirect_stderr(stderr):
                status = main([str(missing)])
        self.assertEqual(status, 2)

    def test_decode_retains_schema_invalid_messages_and_their_times(self) -> None:
        mcap_message = SimpleNamespace(log_time=10, publish_time=9)
        records = [
            (
                SimpleNamespace(name="wrong.Estimate"),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                mcap_message,
                SimpleNamespace(time_stamp_=26_000_000),
            ),
            (
                SimpleNamespace(name="wrong.Map"),
                SimpleNamespace(
                    topic="/adp/road_lane_map_based",
                    message_encoding="protobuf",
                ),
                mcap_message,
                SimpleNamespace(time_stamp_=0),
            ),
        ]
        with patch(
            "lane_residuals.pairing_audit_cli.iter_decoded_mcap_messages",
            return_value=iter(records),
        ):
            estimates, references, failures, counts = _decode_paths(
                Path("synthetic.mcap"),
                estimate_topic="/adp/estimated_drive_paths",
                map_topic="/adp/road_lane_map_based",
                max_step_m=0.25,
                stations_m=(0.0, 5.0),
            )

        self.assertEqual(counts, {"estimate_messages": 1, "map_messages": 1})
        self.assertEqual(len(estimates), 1)
        self.assertEqual(len(references), 1)
        self.assertEqual(estimates[0].source_time_ns, 26_000_000)
        self.assertEqual(references[0].source_time_ns, 0)
        self.assertEqual(
            failures,
            {
                "estimate__schema_or_encoding_mismatch": 1,
                "map__schema_or_encoding_mismatch": 1,
            },
        )

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
        estimate = self._timed_path(
            message_index=1,
            source_time_ns=100_000_000,
            path=estimate_path,
        )
        reference = self._timed_path(
            message_index=2,
            source_time_ns=90_000_000,
            path=reference_path,
        )
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
            self.assertTrue(summary["pairing_before_geometry_filtering"])
            self.assertTrue((output / "message_inventory.csv").is_file())
            self.assertTrue((output / "pairing_audit.csv").is_file())
            self.assertTrue((output / "diagnostic_disagreement.csv").is_file())
            self.assertTrue((output / "pairing_overlays.png").is_file())
            self.assertTrue((output / "pairing_summary.json").is_file())

    def test_invalid_map_prefix_does_not_shift_timestamp_pairing(self) -> None:
        x = np.linspace(-5.0, 120.0, 126)
        estimate_path = ego_relative_path_from_points(
            np.column_stack((x, np.full_like(x, 0.2))),
            source="estimate",
        )
        reference_path = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))),
            source="reference",
        )
        estimates = [
            self._timed_path(
                message_index=index,
                source_time_ns=26_000_000 + 80_000_000 * index,
                path=estimate_path,
            )
            for index in range(60)
        ]
        references = [
            self._timed_path(
                message_index=index,
                source_time_ns=80_000_000 * index,
                path=(None if index < 57 else reference_path),
                failure_code=(
                    "map__map_ego_drive_path_not_unique" if index < 57 else None
                ),
            )
            for index in range(60)
        ]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit"
            arguments = SimpleNamespace(
                mcap=Path("synthetic_invalid_prefix.mcap"),
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
                    estimates,
                    references,
                    {"map__map_ego_drive_path_not_unique": 57},
                    {"estimate_messages": 60, "map_messages": 60},
                ),
            ):
                summary = run_pairing_audit(
                    arguments,
                    stations_m=tuple(float(value) for value in range(0, 101, 5)),
                )

            with (output / "pairing_audit.csv").open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))

            self.assertEqual(len(rows), 60)
            self.assertEqual(
                (rows[0]["estimate_message_index"], rows[0]["map_message_index"]),
                ("0", "0"),
            )
            self.assertEqual(
                (
                    rows[57]["estimate_message_index"],
                    rows[57]["map_message_index"],
                ),
                ("57", "57"),
            )
            self.assertTrue(
                all(
                    abs(float(row["source_delta_ms"]) - 26.0) < 1e-12
                    for row in rows
                )
            )
            self.assertEqual(rows[0]["pair_state"], "map_geometry_not_ready")
            self.assertEqual(
                rows[57]["pair_state"],
                "diagnostic_ready_uncompensated",
            )
            self.assertEqual(
                summary["complete_stream_mutual_nearest_pair_count"],
                60,
            )
            self.assertEqual(summary["diagnostic_ready_pair_count"], 3)


if __name__ == "__main__":
    unittest.main()
