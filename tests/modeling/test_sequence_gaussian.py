import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.domain.sequence_dataset import PaddedSequenceDataset
from lane_residuals.modeling.sequence_gaussian import SequenceConditionalGaussian


def _dataset() -> PaddedSequenceDataset:
    rng = np.random.default_rng(27)
    conditions = rng.normal(size=(2, 12, 6))
    coefficients = rng.normal(scale=0.15, size=(6, 21))
    residuals = 0.1 + conditions @ coefficients
    residuals += rng.normal(scale=0.05, size=residuals.shape)
    return PaddedSequenceDataset(
        sequence_ids=["sequence_a", "sequence_b"],
        recording_ids=["recording_a", "recording_b"],
        drive_ids=["drive_a", "drive_b"],
        conditions=conditions,
        residuals_m=residuals,
        valid_mask=np.ones((2, 12, 21), dtype=np.bool_),
        lengths=[12, 12],
        pair_indices=np.tile(np.arange(12), (2, 1)),
        estimate_message_indices=np.tile(np.arange(100, 112), (2, 1)),
        estimate_source_times_ns_private=np.vstack(
            (
                np.arange(12) * 80_000_000 + 1_000_000_000,
                np.arange(12) * 80_000_000 + 3_000_000_000,
            )
        ),
        standardized=True,
    )


class SequenceConditionalGaussianTests(unittest.TestCase):
    def test_fit_log_probability_sampling_and_round_trip(self) -> None:
        dataset = _dataset()
        training = dataset.select_drive_ids(("drive_a",))
        validation = dataset.select_drive_ids(("drive_b",))
        model = SequenceConditionalGaussian(covariance_regularization=1e-4)

        report = model.fit(training, validation)
        log_probability = model.log_probability(validation)
        samples = model.sample(
            validation.conditions,
            validation.lengths,
            sample_count=5,
            seed=123,
            valid_mask=validation.valid_mask,
        )

        self.assertTrue(model.is_fitted)
        self.assertEqual(report.training_sequence_count, 1)
        self.assertEqual(report.validation_sequence_count, 1)
        self.assertEqual(log_probability.shape, (1, 12))
        self.assertTrue(np.all(np.isfinite(log_probability)))
        self.assertEqual(samples.values.shape, (5, 1, 12, 21))
        self.assertTrue(samples.standardized)
        self.assertFalse(np.allclose(samples.values[:, :, 0], samples.values[:, :, 1]))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model.save(path)
            restored = SequenceConditionalGaussian.load(path)
            np.testing.assert_allclose(
                restored.log_probability(validation),
                log_probability,
            )
            np.testing.assert_allclose(
                restored.sample(
                    validation.conditions,
                    validation.lengths,
                    sample_count=5,
                    seed=123,
                    valid_mask=validation.valid_mask,
                ).values,
                samples.values,
            )

    def test_requires_standardized_complete_targets(self) -> None:
        dataset = _dataset()
        raw = PaddedSequenceDataset(
            sequence_ids=dataset.sequence_ids,
            recording_ids=dataset.recording_ids,
            drive_ids=dataset.drive_ids,
            conditions=dataset.conditions,
            residuals_m=dataset.residuals_m,
            valid_mask=dataset.valid_mask,
            lengths=dataset.lengths,
            pair_indices=dataset.pair_indices,
            estimate_message_indices=dataset.estimate_message_indices,
            estimate_source_times_ns_private=(
                dataset.estimate_source_times_ns_private
            ),
            standardized=False,
        )
        with self.assertRaisesRegex(ValueError, "standard"):
            SequenceConditionalGaussian().fit(raw.select_drive_ids(("drive_a",)))


if __name__ == "__main__":
    unittest.main()
