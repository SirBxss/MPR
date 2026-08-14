import argparse
import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from lane_residuals import (
    ComparatorFrameAudit,
    DecodedRecording,
    EstimatedFrameAudit,
    SplineParameters,
    generate_spline_curve,
    synchronize_estimate_and_comparator,
)
from lane_residuals.cli import main as legacy_mcap_main
from lane_residuals.geometry_validation_cli import (
    _RecordingResult,
    _duplicate_flags,
    _duplicate_gap_rows,
    _write_outputs,
)


class GeometryValidationOutputTests(unittest.TestCase):
    def _result(self):
        parameters = SplineParameters(
            x_0=8123.25,
            y_0=-7123.5,
            theta_0=0.0,
            curvature_0=0.0,
            segment_starts=np.asarray([0.0, 25.0]),
            curvature_change=np.asarray([0.0]),
            index_0=0,
            index_0_presence_evidence="implicit_default",
            index_0_explicitly_present=False,
        )
        estimate = EstimatedFrameAudit(
            message_index=0,
            log_time_ns=987654321987,
            publish_time_ns=987654321900,
            source_time_ns=987654321000,
            schema_fingerprint="estimate-schema-hash",
            topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
            total_path_count=1,
            keep_lane_count=1,
            keep_lane_error="DRIVE_PATH_ERROR_NO_ERROR",
            estimator_state="available_no_error",
            conversion_state="candidate_ready",
            interval_count=1,
            payload_fingerprint="payload-hash",
            candidate=parameters,
        )
        comparator = ComparatorFrameAudit(
            message_index=0,
            log_time_ns=987654321988,
            publish_time_ns=987654321901,
            source_time_ns=987654321001,
            state="comparator_geometry_invalid",
            payload_fingerprint="comparator-payload-hash",
        )
        decoded = DecodedRecording(
            estimated_frames=(estimate,),
            comparator_frames=(comparator,),
            estimate_schema_fingerprints=("estimate-schema-hash",),
            comparator_schema_fingerprints=("comparator-schema-hash",),
            scan_complete=True,
        )
        synchronization = synchronize_estimate_and_comparator(
            decoded.estimated_frames,
            decoded.comparator_frames,
            max_delta_ms=20.0,
        )
        curve = generate_spline_curve(parameters, meaning="curvature_rate")
        return _RecordingResult(
            recording_id="recording_001",
            session_id="session_001",
            source_path=Path("CONFIDENTIAL_8123.mcap"),
            status="completed",
            error_code=None,
            decoded=decoded,
            synchronization=synchronization,
            sensitivity_counts={"5": 1, "10": 1, "20": 1, "50": 1},
            generated_curves={(0, curve.hypothesis): curve},
            generation_failures={},
            metrics=[],
        )

    def test_outputs_are_privacy_safe_and_never_training_artifacts(self):
        arguments = argparse.Namespace(
            expected_file_count=1,
            assume_same_frame=False,
            max_overlays_per_recording=0,
            absolute_lateral_rms_tolerance_m=None,
            absolute_heading_p95_tolerance_rad=None,
            comparison_max_delta_ms=20.0,
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            summary = _write_outputs(
                [self._result()],
                output_directory=destination,
                sessions_confirmed=True,
                arguments=arguments,
            )
            self.assertTrue(summary["corpus_complete"])
            self.assertEqual(summary["decoded_estimate_messages_unique"], 1)
            expected = {
                "corpus_manifest.json",
                "frame_states.csv",
                "availability_summary.json",
                "duplicate_gap_audit.csv",
                "synchronization_audit.csv",
                "hypothesis_metrics.csv",
                "semantic_validation_summary.json",
            }
            self.assertTrue(expected.issubset({path.name for path in destination.iterdir()}))
            serialized = "\n".join(
                path.read_text(encoding="utf-8")
                for path in destination.iterdir()
                if path.suffix in {".json", ".csv"}
            )
            for confidential in (
                "CONFIDENTIAL_8123.mcap",
                "8123.25",
                "-7123.5",
                "987654321987",
                "987654321000",
            ):
                self.assertNotIn(confidential, serialized)
            self.assertFalse((destination / "residual_dataset.npz").exists())
            self.assertFalse((destination / "gaussian_model.npz").exists())
            semantic = json.loads(
                (destination / "semantic_validation_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(semantic["training_eligible"])
            self.assertFalse(semantic["ground_truth_confirmed"])
            self.assertFalse(semantic["prohibited_outputs"]["gaussian_fitted"])

    def test_real_mcap_gaussian_flag_is_unconditionally_blocked(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                legacy_mcap_main(["missing.mcap", "--fit-gaussian"])
        self.assertEqual(caught.exception.code, 2)

    def test_cross_chunk_duplicate_is_retained_but_counted_once(self):
        first = self._result()
        second = replace(
            first,
            recording_id="recording_002",
            source_path=Path("SECOND_CONFIDENTIAL.mcap"),
        )
        duplicates, conflicts = _duplicate_flags(
            [second, first],
            sessions_confirmed=True,
        )
        self.assertEqual(conflicts, set())
        self.assertEqual(duplicates, {("recording_002", 0): "recording_001:0"})

    def test_comparator_payload_conflict_at_same_timestamp_is_reported(self):
        first = self._result()
        conflicting_comparator = replace(
            first.decoded.comparator_frames[0],
            payload_fingerprint="different-comparator-payload-hash",
        )
        second = replace(
            first,
            recording_id="recording_002",
            decoded=replace(
                first.decoded,
                comparator_frames=(conflicting_comparator,),
            ),
        )
        rows = _duplicate_gap_rows(
            [first, second],
            sessions_confirmed=True,
        )
        conflicts = [
            row
            for row in rows
            if row["event"] == "conflicting_same_timestamp"
        ]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["stream"], "comparator")


if __name__ == "__main__":
    unittest.main()
