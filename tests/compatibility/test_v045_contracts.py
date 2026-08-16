"""Freeze the public v0.4.5 pairing and batch contracts before relocation."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals import ego_relative_path_from_points
from lane_residuals.batch_pairing_audit import (
    CANONICAL_STATIONS_M,
    HORIZON_60_M,
    HORIZON_100_M,
    RecordingAuditData,
)
from lane_residuals.batch_pairing_audit_cli import (
    _parser as batch_parser,
    run_batch,
)
from lane_residuals.pairing_audit_cli import (
    _TimedPath,
    _parser as pairing_parser,
    run_pairing_audit,
)


PAIRING_FILES = {
    "diagnostic_disagreement.csv",
    "diagnostic_station_profiles.png",
    "message_inventory.csv",
    "pairing_audit.csv",
    "pairing_lateral_zoom.png",
    "pairing_overlays.png",
    "pairing_summary.json",
    "rlmb_chain_audit.csv",
}

PAIRING_HEADERS = {
    "message_inventory.csv": (
        "topic_role", "message_index", "source_time_ns_private",
        "log_time_ns_private", "publish_time_ns_private", "geometry_state",
        "geometry_failure_code", "temporal_state", "counterpart_message_index",
        "counterpart_delta_ms", "map_chain_segment_count",
        "map_chain_segment_indices", "map_chain_segment_ids",
        "map_chain_termination_reason", "map_chain_required_coverage_reached",
        "map_chain_max_junction_gap_m",
        "map_chain_max_junction_heading_delta_rad",
        "map_chain_all_links_reciprocal",
    ),
    "rlmb_chain_audit.csv": (
        "map_message_index", "map_source_time_ns_private", "geometry_state",
        "geometry_failure_code", "segment_count", "segment_indices",
        "segment_ids", "termination_reason", "required_forward_m",
        "required_forward_coverage_reached", "actual_forward_coverage_m",
        "actual_backward_coverage_m", "junction_gaps_m",
        "junction_heading_deltas_rad", "reciprocal_predecessor_links",
    ),
    "pairing_audit.csv": (
        "pair_index", "estimate_message_index", "map_message_index",
        "estimate_source_time_ns_private", "map_source_time_ns_private",
        "source_delta_ms", "absolute_source_delta_ms", "timestamp_gate_ms",
        "timestamp_gate_passed", "pair_state", "failure_code",
        "estimate_geometry_state", "estimate_geometry_failure_code",
        "map_geometry_state", "map_geometry_failure_code",
        "estimate_backward_coverage_m", "estimate_forward_coverage_m",
        "reference_backward_coverage_m", "reference_forward_coverage_m",
        "estimate_reversed_to_positive_x", "reference_reversed_to_positive_x",
        "estimate_origin_distance_m", "reference_origin_distance_m",
        "footpoint_separation_m", "footpoint_dx_m", "footpoint_dy_m",
        "origin_heading_delta_rad", "diagnostic_lateral_rms_m",
        "diagnostic_lateral_max_abs_m", "diagnostic_primary_horizon_max_m",
        "diagnostic_primary_lateral_rms_m", "diagnostic_far_lateral_rms_m",
        "diagnostic_common_max_station_m", "diagnostic_available_lateral_rms_m",
        "reference_chain_segment_count", "reference_chain_segment_indices",
        "reference_chain_segment_ids", "reference_chain_termination_reason",
        "reference_chain_required_coverage_reached",
        "reference_chain_max_junction_gap_m",
        "reference_chain_max_junction_heading_delta_rad",
    ),
    "diagnostic_disagreement.csv": (
        "pair_index", "station_m", "estimate_x_m", "estimate_y_m",
        "reference_x_m", "reference_y_m", "diagnostic_lateral_m",
        "diagnostic_along_track_m", "diagnostic_heading_rad",
        "full_requested_horizon_available", "primary_horizon_available",
    ),
}

BATCH_FILES = {
    "batch_manifest.json", "batch_summary.json",
    "fixed_cohort_station_profiles.png", "recording_horizon_summary.png",
    "recording_summary.csv", "rlmb_chain_summary.json",
    "scope_horizon_metrics.csv", "scope_station_metrics.csv",
    "temporal_diagnostic_events.png", "temporal_tail_events.csv",
}

BATCH_HEADERS = {
    "recording_summary.csv": (
        "recording_id", "drive_id", "mcap_filename_private", "status",
        "error_code", "error_message", "estimate_message_count",
        "map_message_count", "mutual_nearest_pair_count",
        "unmatched_estimate_message_count", "unmatched_map_message_count",
        "median_absolute_source_delta_ms", "rlmb_multi_segment_lane_count",
        "h60_complete_cohort_pair_count", "h60_pooled_lateral_rms_m",
        "h60_median_pair_lateral_rms_m", "h60_p95_pair_lateral_rms_m",
        "h100_complete_cohort_pair_count", "h100_pooled_lateral_rms_m",
        "h100_median_pair_lateral_rms_m", "h100_p95_pair_lateral_rms_m",
        "h60_predeclared_outcome_tail_pair_count",
        "h100_predeclared_outcome_tail_pair_count",
    ),
    "scope_horizon_metrics.csv": (
        "scope_type", "scope_id", "horizon_m", "cohort_pair_count",
        "station_count_per_pair", "pooled_observation_count",
        "contributing_recording_count", "pooled_lateral_mean_m",
        "pooled_lateral_rms_m", "pooled_lateral_median_m",
        "median_pair_lateral_rms_m", "p95_pair_lateral_rms_m",
        "maximum_absolute_lateral_m",
    ),
    "scope_station_metrics.csv": (
        "scope_type", "scope_id", "horizon_m", "station_m",
        "cohort_pair_count", "lateral_mean_m", "lateral_rms_m",
        "lateral_median_m", "lateral_p05_m", "lateral_p95_m",
    ),
    "temporal_tail_events.csv": (
        "recording_id", "drive_id", "pair_index", "estimate_message_index",
        "map_message_index", "recording_relative_source_time_s",
        "drive_relative_source_time_s", "seconds_from_recording_end",
        "in_final_recording_time_window", "recording_tail_window_s",
        "h60_eligible", "h100_eligible", "h60_pair_lateral_rms_m",
        "h100_pair_lateral_rms_m", "h60_tail_threshold_m",
        "h100_tail_threshold_m", "h60_outcome_tail_flag",
        "h100_outcome_tail_flag", "tail_thresholds_predeclared",
    ),
}


def _header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return tuple(next(csv.reader(stream)))


def _timed_path(index: int, time_ns: int, path) -> _TimedPath:
    return _TimedPath(
        message_index=index,
        source_time_ns=time_ns,
        log_time_ns=time_ns,
        publish_time_ns=time_ns,
        geometry_state="geometry_ready",
        failure_code=None,
        path=path,
    )


def _recording(recording_id: str, drive_id: str, filename: str, time_ns: int):
    pair = {
        "pair_index": "0",
        "estimate_message_index": "0",
        "map_message_index": "0",
        "estimate_source_time_ns_private": str(time_ns),
        "diagnostic_primary_lateral_rms_m": "0.2",
        "diagnostic_lateral_rms_m": "0.2",
    }
    stations = tuple(
        {
            "pair_index": "0",
            "station_m": str(station),
            "diagnostic_lateral_m": "0.2",
        }
        for station in CANONICAL_STATIONS_M
    )
    chain = {
        "segment_count": "1",
        "termination_reason": "required_forward_coverage_reached",
        "actual_forward_coverage_m": "110",
        "junction_gaps_m": "",
        "junction_heading_deltas_rad": "",
        "reciprocal_predecessor_links": "",
    }
    return RecordingAuditData(
        recording_id=recording_id,
        drive_id=drive_id,
        mcap_filename=filename,
        status="succeeded",
        output_directory=f"recordings/{recording_id}",
        summary={
            "estimate_messages": 1,
            "map_messages": 1,
            "complete_stream_mutual_nearest_pair_count": 1,
            "unmatched_estimate_message_count": 0,
            "unmatched_map_message_count": 0,
        },
        pair_rows=(pair,),
        station_rows=stations,
        chain_rows=(chain,),
        inventory_rows=(
            {"topic_role": "estimate", "source_time_ns_private": str(time_ns)},
        ),
    )


class V045ObservableContractTests(unittest.TestCase):
    def test_console_entry_points_and_compatibility_modules_are_frozen(self) -> None:
        project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        scripts = project["project"]["scripts"]
        frozen = {
            "mpr-mcap": "lane_residuals.cli:main",
            "mpr-probe-path-source": "lane_residuals.path_probe_cli:main",
            "mpr-validate-path-geometry": "lane_residuals.geometry_validation_cli:main",
            "mpr-audit-reference-candidates": "lane_residuals.reference_audit_cli:main",
            "mpr-audit-path-pairing": "lane_residuals.pairing_audit_cli:main",
            "mpr-audit-edp-transitions": "lane_residuals.edp_transition_audit_cli:main",
            "mpr-audit-path-pairing-batch": "lane_residuals.batch_pairing_audit_cli:main",
        }
        self.assertEqual(
            {name: scripts.get(name) for name in frozen},
            frozen,
        )

    def test_pairing_and_batch_cli_defaults_are_frozen(self) -> None:
        pairing = pairing_parser().parse_args(["recording.mcap"])
        self.assertEqual(pairing.output_directory, Path("outputs/pairing_audit"))
        self.assertEqual(pairing.max_pairs, 20)
        self.assertIsNone(pairing.maximum_pair_delta_ms)
        self.assertEqual(pairing.max_step_m, 0.25)
        self.assertEqual(pairing.map_max_segments, 16)
        self.assertEqual(pairing.map_max_junction_gap_m, 1.0)
        self.assertEqual(pairing.map_max_junction_heading_deg, 30.0)

        batch = batch_parser().parse_args(
            ["recordings", "--drive-map", "groups.json"]
        )
        self.assertEqual(batch.output_directory, Path("outputs/pairing_batch_v045"))
        self.assertEqual(batch.expected_file_count, 10)
        self.assertEqual(batch.max_pairs_per_recording, 6)
        self.assertIsNone(batch.maximum_pair_delta_ms)
        self.assertEqual(batch.recording_tail_window_s, 5.0)
        self.assertIsNone(batch.primary_tail_threshold_m)
        self.assertIsNone(batch.full_tail_threshold_m)

    def test_fixed_horizon_definitions_are_frozen(self) -> None:
        self.assertEqual(HORIZON_60_M, tuple(float(x) for x in range(0, 61, 5)))
        self.assertEqual(HORIZON_100_M, tuple(float(x) for x in range(0, 101, 5)))
        self.assertEqual(CANONICAL_STATIONS_M, HORIZON_100_M)
        self.assertTrue(set(HORIZON_60_M).issubset(HORIZON_100_M))

    def test_single_recording_files_headers_and_numeric_summary_are_frozen(self) -> None:
        x = np.linspace(-5.0, 120.0, 126)
        estimate_path = ego_relative_path_from_points(
            np.column_stack((x, np.full_like(x, 0.2))), source="estimate"
        )
        reference_path = ego_relative_path_from_points(
            np.column_stack((x, np.zeros_like(x))), source="reference"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit"
            arguments = SimpleNamespace(
                mcap=Path("synthetic.mcap"),
                estimate_topic="/estimate",
                map_topic="/map",
                max_step_m=0.25,
                max_pairs=20,
                maximum_pair_delta_ms=None,
                output_directory=output,
            )
            with patch(
                "lane_residuals.workflows.pairing._decode_paths",
                return_value=(
                    [_timed_path(1, 100_000_000, estimate_path)],
                    [_timed_path(2, 90_000_000, reference_path)],
                    {},
                    {"estimate_messages": 1, "map_messages": 1},
                ),
            ):
                summary = run_pairing_audit(arguments, stations_m=HORIZON_100_M)

            self.assertEqual({p.name for p in output.iterdir()}, PAIRING_FILES)
            for filename, expected in PAIRING_HEADERS.items():
                self.assertEqual(_header(output / filename), expected)
            self.assertEqual(summary["complete_stream_mutual_nearest_pair_count"], 1)
            self.assertEqual(summary["diagnostic_ready_pair_count"], 1)
            self.assertAlmostEqual(summary["median_absolute_source_delta_ms"], 10.0)
            self.assertAlmostEqual(summary["median_diagnostic_lateral_rms_m"], 0.2)
            self.assertFalse(summary["diagnostic_disagreement_is_lane_estimation_error"])
            self.assertFalse(summary["generated_final_residual_dataset"])

    def test_batch_files_headers_and_aggregate_values_are_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = (root / "first.mcap", root / "second.mcap")
            for path in files:
                path.touch()
            mapping = root / "groups.json"
            mapping.write_text(
                json.dumps({"first.mcap": "group-a", "second.mcap": "group-b"}),
                encoding="utf-8",
            )
            arguments = argparse.Namespace(
                inputs=files,
                drive_map=mapping,
                expected_file_count=2,
                output_directory=root / "batch",
                max_pairs_per_recording=2,
                maximum_pair_delta_ms=None,
                max_step_m=0.25,
                map_max_segments=16,
                map_max_junction_gap_m=1.0,
                map_max_junction_heading_deg=30.0,
                recording_tail_window_s=5.0,
                primary_tail_threshold_m=None,
                full_tail_threshold_m=None,
                estimate_topic="/estimate",
                map_topic="/map",
            )

            def fake_recording(**kwargs):
                time_ns = 0 if kwargs["recording_id"] == "recording_001" else 1_000_000_000
                return _recording(
                    kwargs["recording_id"], kwargs["drive_id"], kwargs["mcap"].name, time_ns
                )

            with patch(
                "lane_residuals.workflows.batch_pairing._run_one_recording",
                side_effect=fake_recording,
            ):
                summary, status = run_batch(arguments)

            output = arguments.output_directory
            self.assertEqual(status, 0)
            self.assertEqual({p.name for p in output.iterdir() if p.is_file()}, BATCH_FILES)
            for filename, expected in BATCH_HEADERS.items():
                self.assertEqual(_header(output / filename), expected)
            self.assertEqual(summary["successful_recording_count"], 2)
            self.assertEqual(summary["failed_recording_count"], 0)
            self.assertEqual(summary["blockers"], [])
            self.assertEqual(summary["canonical_station_grid_m"], list(HORIZON_100_M))
            self.assertEqual(
                summary["overall_fixed_cohort_metrics"]["60"]["cohort_pair_count"], 2
            )
            self.assertEqual(
                summary["overall_fixed_cohort_metrics"]["100"]["cohort_pair_count"], 2
            )


if __name__ == "__main__":
    unittest.main()
