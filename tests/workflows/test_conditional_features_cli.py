import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals.domain.residual_dataset import (
    CanonicalResidualDataset,
    ResidualObservation,
)
from lane_residuals.workflows.conditional_features import (
    ManifestRecording,
    RecordingFeatureResult,
    _validated_manifest_recordings,
    run_conditional_feature_audit,
)


class ConditionalFeatureWorkflowTests(unittest.TestCase):
    @staticmethod
    def _observation(pair_index: int) -> ResidualObservation:
        return ResidualObservation(
            recording_id="recording_001",
            drive_id="drive_001",
            pair_index=pair_index,
            estimate_message_index=pair_index,
            map_message_index=pair_index,
            estimate_source_time_ns_private=1_000 + pair_index,
            map_source_time_ns_private=101_000 + pair_index,
            source_delta_ms=-0.1,
            residuals_m=np.zeros(21),
        )

    @staticmethod
    def _feature_row(observation: ResidualObservation, *, ready: bool) -> dict:
        return {
            "recording_id": observation.recording_id,
            "drive_id": observation.drive_id,
            "pair_index": observation.pair_index,
            "estimate_message_index": observation.estimate_message_index,
            "estimate_source_time_ns_private": (
                observation.estimate_source_time_ns_private
            ),
            "feature_state": "ready" if ready else "not_ready",
            "failure_codes": "" if ready else "speed__speed_stream_empty",
            "speed_mps": 12.0 if ready else None,
            "speed_interpolation_method": "exact" if ready else None,
            "speed_lower_timestamp_ns_private": 1_000 if ready else None,
            "speed_upper_timestamp_ns_private": 1_000 if ready else None,
            "speed_interpolation_span_ms": 0.0 if ready else None,
            "estimated_mean_abs_curvature_per_m": 0.002,
            "estimated_curvature_delta_per_m": 0.001,
            "confidence_near_mean": 0.8,
            "confidence_middle_mean": 0.7,
            "confidence_far_mean": 0.6,
            "confidence_minimum": 0.5,
            "confidence_floor_fraction": 0.0,
            "confidence_lateral_jump_detected": False,
            "confidence_bucket_count": 24,
            "confidence_native_start_station_m": 2.5,
            "confidence_native_end_station_m": 107.5,
        }

    @staticmethod
    def _write_required_sources(root: Path) -> tuple[Path, Path, Path]:
        baseline = root / "baseline"
        alignment = root / "alignment"
        raw = root / "raw"
        baseline.mkdir()
        alignment.mkdir()
        raw.mkdir()
        for name in (
            "residual_vectors.csv",
            "residual_dataset_summary.json",
            "gaussian_model.json",
            "gaussian_summary.json",
        ):
            (baseline / name).write_text("{}", encoding="utf-8")
        (alignment / "batch_manifest.json").write_text("{}", encoding="utf-8")
        (raw / "recording.mcap").write_bytes(b"")
        return baseline, alignment, raw

    def test_audit_exports_complete_four_file_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, alignment, raw = self._write_required_sources(root)
            observations = (self._observation(0), self._observation(1))
            artifacts = SimpleNamespace(
                dataset=CanonicalResidualDataset(observations),
                dataset_summary={},
            )
            recording = ManifestRecording(
                recording_id="recording_001",
                drive_id="drive_001",
                basename="recording.mcap",
                path=raw / "recording.mcap",
            )
            feature_rows = tuple(
                self._feature_row(observation, ready=True)
                for observation in observations
            )
            result = RecordingFeatureResult(
                rows=feature_rows,
                summary_row={
                    "recording_id": "recording_001",
                    "drive_id": "drive_001",
                    "mcap_filename_private": "recording.mcap",
                    "status": "complete",
                    "residual_vector_count": 2,
                    "feature_ready_count": 2,
                    "feature_ready_fraction": 1.0,
                    "estimate_message_count": 2,
                    "speed_message_count": 4,
                    "valid_speed_sample_count": 4,
                    "median_speed_interpolation_span_ms": 0.0,
                    "failure_counts": "{}",
                },
                failure_counts={},
            )
            output = root / "output"
            arguments = SimpleNamespace(
                mcap=[raw],
                alignment_batch_directory=alignment,
                gaussian_baseline_directory=baseline,
                output_directory=output,
                maximum_speed_interpolation_gap_ms=20.0,
                max_step_m=0.25,
                estimate_topic="/adp/estimated_drive_paths",
                speed_topic="/adp/velocity_vehicle_longitudinal",
            )
            with patch(
                "lane_residuals.workflows.conditional_features."
                "load_gaussian_baseline_artifacts",
                return_value=artifacts,
            ), patch(
                "lane_residuals.workflows.conditional_features."
                "_validated_manifest_recordings",
                return_value=({"version": "0.5.0"}, (recording,)),
            ), patch(
                "lane_residuals.workflows.conditional_features."
                "_extract_recording_features",
                return_value=result,
            ):
                summary, status = run_conditional_feature_audit(arguments)

            self.assertEqual(status, 0)
            self.assertEqual(summary["feature_ready_count"], 2)
            self.assertFalse(summary["conditional_model_trained"])
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "conditional_features.csv",
                    "conditional_feature_recording_summary.csv",
                    "conditional_feature_audit.png",
                    "conditional_feature_summary.json",
                },
            )
            with (output / "conditional_features.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)

    def test_incomplete_feature_coverage_returns_status_three(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, alignment, raw = self._write_required_sources(root)
            observations = (self._observation(0), self._observation(1))
            artifacts = SimpleNamespace(
                dataset=CanonicalResidualDataset(observations),
                dataset_summary={},
            )
            recording = ManifestRecording(
                "recording_001",
                "drive_001",
                "recording.mcap",
                raw / "recording.mcap",
            )
            rows = (
                self._feature_row(observations[0], ready=True),
                self._feature_row(observations[1], ready=False),
            )
            result = RecordingFeatureResult(
                rows=rows,
                summary_row={
                    "recording_id": "recording_001",
                    "drive_id": "drive_001",
                    "mcap_filename_private": "recording.mcap",
                    "status": "incomplete",
                    "residual_vector_count": 2,
                    "feature_ready_count": 1,
                    "feature_ready_fraction": 0.5,
                    "estimate_message_count": 2,
                    "speed_message_count": 0,
                    "valid_speed_sample_count": 0,
                    "median_speed_interpolation_span_ms": None,
                    "failure_counts": '{"speed__speed_stream_empty": 1}',
                },
                failure_counts={"speed__speed_stream_empty": 1},
            )
            arguments = SimpleNamespace(
                mcap=[raw],
                alignment_batch_directory=alignment,
                gaussian_baseline_directory=baseline,
                output_directory=root / "output",
                maximum_speed_interpolation_gap_ms=20.0,
                max_step_m=0.25,
                estimate_topic="/adp/estimated_drive_paths",
                speed_topic="/adp/velocity_vehicle_longitudinal",
            )
            with patch(
                "lane_residuals.workflows.conditional_features."
                "load_gaussian_baseline_artifacts",
                return_value=artifacts,
            ), patch(
                "lane_residuals.workflows.conditional_features."
                "_validated_manifest_recordings",
                return_value=({"version": "0.5.0"}, (recording,)),
            ), patch(
                "lane_residuals.workflows.conditional_features."
                "_extract_recording_features",
                return_value=result,
            ):
                summary, status = run_conditional_feature_audit(arguments)

            self.assertEqual(status, 3)
            self.assertEqual(summary["status"], "incomplete")
            self.assertEqual(summary["feature_not_ready_count"], 1)

    def test_manifest_must_match_baseline_hash_and_exact_mcap_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alignment = root / "alignment"
            raw = root / "raw"
            alignment.mkdir()
            raw.mkdir()
            mcap = raw / "recording.mcap"
            mcap.write_bytes(b"")
            manifest = {
                "version": "0.5.0",
                "purpose": "ten_mcap_projection_based_reference_alignment_validation",
                "status": "complete",
                "blockers": [],
                "drive_grouping_source": "exact_private_basename_map",
                "canonical_station_grid_m": [float(value) for value in range(0, 101, 5)],
                "recordings": [
                    {
                        "recording_id": "recording_001",
                        "drive_id": "drive_001",
                        "mcap_filename_private": "recording.mcap",
                        "status": "succeeded",
                    }
                ],
            }
            manifest_path = alignment / "batch_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

            _, recordings = _validated_manifest_recordings(
                alignment_batch_directory=alignment,
                baseline_dataset_summary={
                    "source_files_sha256": {"batch_manifest.json": digest}
                },
                mcap_inputs=[raw],
            )

            self.assertEqual(len(recordings), 1)
            self.assertEqual(recordings[0].basename, "recording.mcap")


if __name__ == "__main__":
    unittest.main()
