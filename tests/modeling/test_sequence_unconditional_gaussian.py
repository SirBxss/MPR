import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.domain.sequence_dataset import PaddedSequenceDataset
from lane_residuals.modeling.sequence_unconditional_gaussian import (
    SequenceUnconditionalGaussian,
)


def _dataset() -> PaddedSequenceDataset:
    rng = np.random.default_rng(142)
    residuals = rng.normal(size=(2, 12, 21))
    return PaddedSequenceDataset(
        sequence_ids=["sequence_a", "sequence_b"],
        recording_ids=["recording_a", "recording_b"],
        drive_ids=["drive_a", "drive_b"],
        conditions=rng.normal(size=(2, 12, 6)),
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


class SequenceUnconditionalGaussianTests(unittest.TestCase):
    def test_fit_sample_density_and_round_trip(self) -> None:
        dataset = _dataset()
        training = dataset.select_drive_ids(("drive_a",))
        test = dataset.select_drive_ids(("drive_b",))
        model = SequenceUnconditionalGaussian(covariance_regularization=1e-3)

        report = model.fit(training, test)
        log_probability = model.log_probability(test)
        samples = model.sample(
            test.conditions,
            test.lengths,
            sample_count=8,
            seed=14,
            valid_mask=test.valid_mask,
        )

        self.assertEqual(report.training_sequence_count, 1)
        self.assertEqual(log_probability.shape, (1, 12))
        self.assertTrue(np.all(np.isfinite(log_probability)))
        self.assertEqual(samples.values.shape, (8, 1, 12, 21))
        self.assertFalse(np.allclose(samples.values[:, :, 0], samples.values[:, :, 1]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model.save(path)
            restored = SequenceUnconditionalGaussian.load(path)
            np.testing.assert_allclose(
                restored.log_probability(test), log_probability
            )
            np.testing.assert_allclose(
                restored.sample(
                    test.conditions,
                    test.lengths,
                    sample_count=8,
                    seed=14,
                    valid_mask=test.valid_mask,
                ).values,
                samples.values,
            )


if __name__ == "__main__":
    unittest.main()
