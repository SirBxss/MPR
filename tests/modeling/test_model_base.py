import unittest

import numpy as np

from lane_residuals.domain.sequence_dataset import PaddedSequenceDataset
from lane_residuals.modeling.base import (
    FitReport,
    ProbabilisticSequenceModel,
    SampleResult,
)


def _standardized_dataset(drive_id: str) -> PaddedSequenceDataset:
    return PaddedSequenceDataset(
        sequence_ids=[f"{drive_id}_sequence"],
        recording_ids=[f"{drive_id}_recording"],
        drive_ids=[drive_id],
        conditions=np.zeros((1, 2, 6)),
        residuals_m=np.zeros((1, 2, 21)),
        valid_mask=np.ones((1, 2, 21), dtype=np.bool_),
        lengths=[2],
        pair_indices=[[0, 1]],
        estimate_message_indices=[[10, 11]],
        estimate_source_times_ns_private=[[1_000_000_000, 1_080_000_000]],
        standardized=True,
    )


class ModelBaseContractTests(unittest.TestCase):
    def test_sample_result_accepts_only_zero_padded_variable_lengths(self) -> None:
        values = np.ones((2, 2, 3, 21), dtype=np.float64)
        values[:, 1, 1:] = 0.0

        result = SampleResult(
            values=values,
            lengths=[3, 1],
            stations_m=np.arange(0.0, 105.0, 5.0),
            standardized=True,
        )

        self.assertEqual(result.sample_count, 2)
        with self.assertRaisesRegex(ValueError, "padding frames"):
            SampleResult(
                values=np.ones((1, 1, 2, 21)),
                lengths=[1],
                stations_m=np.arange(0.0, 105.0, 5.0),
                standardized=True,
            )

    def test_fit_report_rejects_nonfinite_metrics(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            FitReport(
                model_name="conditional_gaussian",
                training_sequence_count=2,
                validation_sequence_count=1,
                metrics={"validation_loss": float("nan")},
            )

    def test_fit_validation_rejects_overlapping_physical_drives(self) -> None:
        with self.assertRaisesRegex(ValueError, "physical drives overlap"):
            ProbabilisticSequenceModel.validate_fit_datasets(
                _standardized_dataset("drive_a"),
                _standardized_dataset("drive_a"),
            )
        ProbabilisticSequenceModel.validate_fit_datasets(
            _standardized_dataset("drive_a"),
            _standardized_dataset("drive_b"),
        )


if __name__ == "__main__":
    unittest.main()
