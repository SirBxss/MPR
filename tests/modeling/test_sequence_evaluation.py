import unittest

import numpy as np

from lane_residuals.domain.sequence_dataset import (
    PaddedSequenceDataset,
    SequenceStandardizer,
)
from lane_residuals.modeling.sequence_evaluation import (
    evaluate_sequence_samples,
    physical_sample_result,
)
from lane_residuals.modeling.sequence_gaussian import SequenceConditionalGaussian


def _raw_dataset() -> PaddedSequenceDataset:
    rng = np.random.default_rng(61)
    conditions = rng.normal(size=(2, 16, 6))
    coefficients = rng.normal(scale=0.04, size=(6, 21))
    residuals = 0.3 + conditions @ coefficients
    residuals += rng.normal(scale=0.08, size=residuals.shape)
    return PaddedSequenceDataset(
        sequence_ids=["sequence_a", "sequence_b"],
        recording_ids=["recording_a", "recording_b"],
        drive_ids=["drive_a", "drive_b"],
        conditions=conditions,
        residuals_m=residuals,
        valid_mask=np.ones((2, 16, 21), dtype=np.bool_),
        lengths=[16, 16],
        pair_indices=np.tile(np.arange(16), (2, 1)),
        estimate_message_indices=np.tile(np.arange(100, 116), (2, 1)),
        estimate_source_times_ns_private=np.vstack(
            (
                np.arange(16) * 80_000_000 + 1_000_000_000,
                np.arange(16) * 80_000_000 + 3_000_000_000,
            )
        ),
        standardized=False,
    )


class SequenceEvaluationTests(unittest.TestCase):
    def test_physical_sample_metrics_use_exact_held_out_frames(self) -> None:
        raw = _raw_dataset()
        standardizer = SequenceStandardizer.fit(
            raw,
            train_drive_ids=("drive_a",),
        )
        standardized = standardizer.standardized_copy(raw)
        training = standardized.select_drive_ids(("drive_a",))
        validation = standardized.select_drive_ids(("drive_b",))
        model = SequenceConditionalGaussian(covariance_regularization=1e-4)
        model.fit(training, validation)
        standardized_samples = model.sample(
            validation.conditions,
            validation.lengths,
            sample_count=20,
            seed=44,
            valid_mask=validation.valid_mask,
        )

        physical_samples = physical_sample_result(
            standardized_samples,
            standardizer,
        )
        evaluation = evaluate_sequence_samples(
            raw.select_drive_ids(("drive_b",)),
            physical_samples,
        )

        self.assertFalse(physical_samples.standardized)
        self.assertEqual(evaluation.mean_prediction_m.shape, (1, 16, 21))
        self.assertEqual(evaluation.frame_energy_score_m.shape, (1, 16))
        self.assertTrue(np.isfinite(evaluation.pooled_mean_prediction_rmse_m))
        self.assertTrue(np.isfinite(evaluation.mean_energy_score_m))
        self.assertGreaterEqual(evaluation.marginal_95_coverage, 0.0)
        self.assertLessEqual(evaluation.marginal_95_coverage, 1.0)
        self.assertEqual(
            evaluation.generated_lag_one_correlation_by_sample.shape,
            (20, 21),
        )
        self.assertTrue(
            np.isfinite(evaluation.median_absolute_lag_one_correlation_error)
        )


if __name__ == "__main__":
    unittest.main()
