import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.cli.gaussian_diagnostics import main
from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    RESIDUAL_VECTOR_FIELDS,
    ResidualObservation,
)
from lane_residuals.io.reports import write_csv_rows
from lane_residuals.modeling.gaussian import fit_gaussian_residual_model
from lane_residuals.modeling.gaussian_diagnostics import (
    leave_one_group_out_gaussian_predictions,
    standard_normal_two_sided_quantile,
)


class GaussianDiagnosticsWorkflowTests(unittest.TestCase):
    @staticmethod
    def _write_baseline(root: Path, *, corrupt_model: bool = False) -> None:
        observations = []
        for drive_number in (1, 2):
            for pair_index in range(4):
                residuals = np.asarray(
                    [
                        0.02 * drive_number
                        + 0.01 * pair_index
                        + 0.0005 * station
                        + 0.003 * np.sin(station / 10.0 + pair_index)
                        for station in CANONICAL_MODEL_STATIONS_M
                    ]
                )
                observations.append(
                    ResidualObservation(
                        recording_id=f"recording_{drive_number:03d}",
                        drive_id=f"drive_{drive_number:03d}",
                        pair_index=pair_index,
                        estimate_message_index=pair_index,
                        map_message_index=pair_index,
                        estimate_source_time_ns_private=900 + pair_index,
                        map_source_time_ns_private=100_900 + pair_index,
                        source_delta_ms=-0.1,
                        residuals_m=residuals,
                    )
                )
        write_csv_rows(
            root / "residual_vectors.csv",
            RESIDUAL_VECTOR_FIELDS,
            [observation.as_csv_row() for observation in observations],
        )
        vector_count = len(observations)
        dataset_summary = {
            "version": "0.6.0",
            "status": "complete",
            "purpose": "canonical_h100_residual_vector_export",
            "canonical_station_grid_m": list(CANONICAL_MODEL_STATIONS_M),
            "constant_pair_count_at_every_station": True,
            "available_case_rows_used": False,
            "drive_grouping_source": "exact_private_basename_map",
            "vector_count": vector_count,
            "drive_count": 2,
            "recording_count": 2,
            "vector_count_by_drive": {"drive_001": 4, "drive_002": 4},
            "vector_count_by_recording": {
                "recording_001": 4,
                "recording_002": 4,
            },
            "station_pair_counts": {
                f"{int(station):03d}m": vector_count
                for station in CANONICAL_MODEL_STATIONS_M
            },
        }
        (root / "residual_dataset_summary.json").write_text(
            json.dumps(dataset_summary),
            encoding="utf-8",
        )

        matrix = np.vstack([observation.residuals_m for observation in observations])
        drives = tuple(observation.drive_id for observation in observations)
        regularization = 1e-6
        model = fit_gaussian_residual_model(matrix, regularization=regularization)
        mean = model.mean.copy()
        if corrupt_model:
            mean[0] += 0.1
        model_payload = {
            "version": "0.6.0",
            "status": "complete",
            "model_type": "unconditional_multivariate_gaussian",
            "stations_m": list(CANONICAL_MODEL_STATIONS_M),
            "dimension": len(CANONICAL_MODEL_STATIONS_M),
            "n_training_vectors": vector_count,
            "regularization_m2": regularization,
            "mean_m": mean.tolist(),
            "covariance_m2": model.covariance.tolist(),
        }
        (root / "gaussian_model.json").write_text(
            json.dumps(model_payload),
            encoding="utf-8",
        )

        predictions = leave_one_group_out_gaussian_predictions(
            matrix,
            drives,
            regularization=regularization,
        )
        summary = {
            "version": "0.6.0",
            "status": "complete",
            "purpose": "drive_held_out_unconditional_gaussian_baseline",
            "evaluation_scheme": "leave_one_physical_drive_out",
            "final_model_training_vector_count": vector_count,
            "dimension": len(CANONICAL_MODEL_STATIONS_M),
            "regularization_m2": regularization,
            "cross_validated_marginal_95_coverage": float(
                np.mean(
                    np.abs(predictions.standardized_marginal_errors)
                    <= standard_normal_two_sided_quantile(0.95)
                )
            ),
            "cross_validated_mean_squared_mahalanobis_per_dimension": float(
                np.mean(predictions.squared_mahalanobis)
                / len(CANONICAL_MODEL_STATIONS_M)
            ),
            "cross_validated_mean_joint_negative_log_likelihood": float(
                np.mean(predictions.joint_negative_log_likelihood)
            ),
        }
        (root / "gaussian_summary.json").write_text(
            json.dumps(summary),
            encoding="utf-8",
        )

    def test_command_exports_reconciled_adequacy_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            baseline.mkdir()
            self._write_baseline(baseline)
            output = root / "diagnostics"

            status = main([str(baseline), "--output-directory", str(output)])

            self.assertEqual(status, 0)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "gaussian_adequacy_summary.json",
                    "gaussian_marginal_diagnostics.csv",
                    "gaussian_marginal_diagnostics.png",
                    "gaussian_multivariate_diagnostics.csv",
                    "gaussian_multivariate_diagnostics.png",
                    "gaussian_vector_diagnostics.csv",
                },
            )
            with (output / "gaussian_marginal_diagnostics.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                marginal_rows = list(csv.DictReader(handle))
            self.assertEqual(len(marginal_rows), 63)
            self.assertEqual(
                sum(row["scope_type"] == "overall" for row in marginal_rows),
                21,
            )
            with (output / "gaussian_multivariate_diagnostics.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                multivariate_rows = list(csv.DictReader(handle))
            self.assertEqual(len(multivariate_rows), 3)
            summary = json.loads(
                (output / "gaussian_adequacy_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(summary["vector_count"], 8)
            self.assertFalse(summary["formal_iid_normality_test_performed"])
            self.assertFalse(summary["adequacy_thresholds_predeclared"])

    def test_stored_model_must_reconcile_before_output_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            baseline.mkdir()
            self._write_baseline(baseline, corrupt_model=True)
            output = root / "diagnostics"

            status = main([str(baseline), "--output-directory", str(output)])

            self.assertEqual(status, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
