import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.conditional_gaussian import main
from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    ResidualObservation,
)
from lane_residuals.io.reports import write_csv_rows
from lane_residuals.modeling.gaussian import fit_gaussian_residual_model
from lane_residuals.workflows.conditional_features import FEATURE_FIELDS
from lane_residuals.workflows.conditional_gaussian import CONDITIONAL_FEATURE_NAMES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class ConditionalGaussianWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_sources(root: Path) -> tuple[Path, Path]:
        baseline = root / "baseline"
        features = root / "features"
        baseline.mkdir()
        features.mkdir()
        rng = np.random.default_rng(2026)
        observations: list[ResidualObservation] = []
        feature_rows: list[dict[str, object]] = []
        coefficient = rng.normal(scale=0.025, size=(6, 21))
        intercept = np.linspace(-0.05, 0.08, 21)

        for drive_number in (1, 2):
            for pair_index in range(10):
                source_time = (
                    1_000_000_000
                    + drive_number * 2_000_000_000
                    + pair_index * 100_000_000
                )
                raw = rng.normal(size=6)
                condition = np.asarray(
                    [
                        20.0 + 2.0 * raw[0],
                        0.02 + 0.005 * raw[1],
                        0.01 * raw[2],
                        0.75 + 0.05 * raw[3],
                        0.70 + 0.05 * raw[4],
                        0.65 + 0.05 * raw[5],
                    ]
                )
                standardized_like = np.asarray(
                    [raw[0], raw[1], raw[2], raw[3], raw[4], raw[5]]
                )
                residuals = intercept + standardized_like @ coefficient
                residuals += 0.01 * drive_number
                residuals += rng.normal(scale=0.003, size=21)
                observation = ResidualObservation(
                    recording_id=f"recording_{drive_number:03d}",
                    drive_id=f"drive_{drive_number:03d}",
                    pair_index=pair_index,
                    estimate_message_index=pair_index,
                    map_message_index=pair_index,
                    estimate_source_time_ns_private=source_time,
                    map_source_time_ns_private=source_time + 100_000,
                    source_delta_ms=-0.1,
                    residuals_m=residuals,
                )
                observations.append(observation)

                ready = pair_index != 0
                previous_target = source_time - 50_000_000
                row: dict[str, object] = {
                    "recording_id": observation.recording_id,
                    "drive_id": observation.drive_id,
                    "pair_index": pair_index,
                    "estimate_message_index": pair_index,
                    "estimate_source_time_ns_private": source_time,
                    "feature_state": "ready" if ready else "not_ready",
                    "failure_codes": (
                        ""
                        if ready
                        else "speed__odometry_reference_time_outside_coverage"
                    ),
                    "speed_source": "odometry_50ms_displacement",
                    "speed_is_signed": False,
                    "estimated_mean_abs_curvature_per_m": condition[1],
                    "estimated_curvature_delta_per_m": condition[2],
                    "confidence_near_mean": condition[3],
                    "confidence_middle_mean": condition[4],
                    "confidence_far_mean": condition[5],
                }
                if ready:
                    row.update(
                        {
                            "speed_mps": condition[0],
                            "speed_evaluation_method": (
                                "odometry_50ms_displacement"
                            ),
                            "speed_displacement_m": condition[0] * 0.05,
                            "speed_displacement_interval_ms": 50.0,
                            "speed_previous_target_timestamp_ns_private": previous_target,
                            "speed_current_target_timestamp_ns_private": source_time,
                            "speed_previous_lower_timestamp_ns_private": (
                                previous_target - 10_000_000
                            ),
                            "speed_previous_upper_timestamp_ns_private": (
                                previous_target + 10_000_000
                            ),
                            "speed_current_lower_timestamp_ns_private": (
                                source_time - 10_000_000
                            ),
                            "speed_current_upper_timestamp_ns_private": (
                                source_time + 10_000_000
                            ),
                            "speed_previous_interpolation_span_ms": 20.0,
                            "speed_current_interpolation_span_ms": 20.0,
                        }
                    )
                feature_rows.append(row)

        write_csv_rows(
            baseline / "residual_vectors.csv",
            RESIDUAL_VECTOR_FIELDS,
            [observation.as_csv_row() for observation in observations],
        )
        count = len(observations)
        dataset_summary = {
            "version": "0.6.0",
            "status": "complete",
            "purpose": "canonical_h100_residual_vector_export",
            "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "constant_pair_count_at_every_station": True,
            "available_case_rows_used": False,
            "drive_grouping_source": "exact_private_basename_map",
            "vector_count": count,
            "drive_count": 2,
            "recording_count": 2,
            "vector_count_by_drive": {"drive_001": 10, "drive_002": 10},
            "vector_count_by_recording": {
                "recording_001": 10,
                "recording_002": 10,
            },
            "station_pair_counts": {
                f"{int(station):03d}m": count
                for station in CANONICAL_MODEL_STATIONS_M
            },
        }
        (baseline / "residual_dataset_summary.json").write_text(
            json.dumps(dataset_summary), encoding="utf-8"
        )
        matrix = np.vstack([observation.residuals_m for observation in observations])
        regularization = 1e-6
        model = fit_gaussian_residual_model(matrix, regularization=regularization)
        (baseline / "gaussian_model.json").write_text(
            json.dumps(
                {
                    "version": "0.6.0",
                    "status": "complete",
                    "model_type": "unconditional_multivariate_gaussian",
                    "stations_m": list(CANONICAL_MODEL_STATIONS_M),
                    "dimension": 21,
                    "n_training_vectors": count,
                    "regularization_m2": regularization,
                    "mean_m": model.mean.tolist(),
                    "covariance_m2": model.covariance.tolist(),
                }
            ),
            encoding="utf-8",
        )
        (baseline / "gaussian_summary.json").write_text(
            json.dumps(
                {
                    "version": "0.6.0",
                    "status": "complete",
                    "purpose": "drive_held_out_unconditional_gaussian_baseline",
                    "evaluation_scheme": "leave_one_physical_drive_out",
                    "final_model_training_vector_count": count,
                    "dimension": 21,
                    "regularization_m2": regularization,
                }
            ),
            encoding="utf-8",
        )

        write_csv_rows(features / "conditional_features.csv", FEATURE_FIELDS, feature_rows)
        (features / "conditional_feature_recording_summary.csv").write_text(
            "synthetic_fixture\n", encoding="utf-8"
        )
        baseline_names = (
            "residual_vectors.csv",
            "residual_dataset_summary.json",
            "gaussian_model.json",
            "gaussian_summary.json",
        )
        feature_summary = {
            "version": "0.7.2",
            "status": "incomplete",
            "purpose": "exact_manifest_prediction_time_conditional_feature_audit",
            "source_baseline_version": "0.6.0",
            "source_baseline_files_sha256": {
                name: _sha256(baseline / name) for name in baseline_names
            },
            "drive_grouping_source": "accepted_exact_alignment_manifest",
            "residual_vector_count": count,
            "feature_ready_count": 18,
            "feature_not_ready_count": 2,
            "feature_ready_count_by_drive": {"drive_001": 9, "drive_002": 9},
            "residual_vector_count_by_drive": {
                "drive_001": 10,
                "drive_002": 10,
            },
            "feature_failure_counts": {
                "speed__odometry_reference_time_outside_coverage": 2
            },
            "canonical_condition_station_grid_m": list(
                CANONICAL_MODEL_STATIONS_M
            ),
            "model_feature_fields": list(CONDITIONAL_FEATURE_NAMES),
            "speed_source": "odometry_50ms_displacement",
            "speed_is_signed": False,
            "speed_displacement_interval_ms": 50.0,
            "maximum_odometry_interpolation_gap_ms": 50.0,
            "odometry_conflicting_timestamp_group_count": 0,
            "odometry_discarded_conflicting_message_count": 0,
            "conditional_model_trained": False,
            "cohort_selection_performed": False,
        }
        (features / "conditional_feature_summary.json").write_text(
            json.dumps(feature_summary), encoding="utf-8"
        )
        return baseline, features

    def test_command_freezes_cohort_and_compares_identical_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, features = self._write_sources(root)
            output = root / "conditional"

            status = main(
                [str(baseline), str(features), "--output-directory", str(output)]
            )

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "conditional_cohort.csv",
                    "conditional_cohort_exclusions.csv",
                    "conditional_cohort_summary.json",
                    "conditional_gaussian_comparison.png",
                    "conditional_gaussian_evaluation.csv",
                    "conditional_gaussian_model.json",
                    "conditional_gaussian_station_evaluation.csv",
                    "conditional_gaussian_summary.json",
                    "conditional_gaussian_vector_evaluation.csv",
                },
            )
            summary = json.loads(
                (output / "conditional_gaussian_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["selected_vector_count"], 18)
            self.assertEqual(summary["excluded_boundary_vector_count"], 2)
            self.assertTrue(summary["same_training_and_test_rows_for_both_models"])
            self.assertTrue(summary["fold_local_feature_standardization"])

            with (output / "conditional_gaussian_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                evaluation = list(csv.DictReader(handle))
            self.assertEqual(len(evaluation), 6)
            for scope in ("drive_001", "drive_002"):
                counts = {
                    row["test_vector_count"]
                    for row in evaluation
                    if row["held_out_drive_id"] == scope
                }
                self.assertEqual(counts, {"9"})
            with (output / "conditional_gaussian_station_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 126)
            with (output / "conditional_gaussian_vector_evaluation.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 18)

    def test_feature_hash_mismatch_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline, features = self._write_sources(root)
            with (baseline / "residual_vectors.csv").open("a", encoding="utf-8") as handle:
                handle.write("\n")
            output = root / "conditional"

            status = main(
                [str(baseline), str(features), "--output-directory", str(output)]
            )

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
