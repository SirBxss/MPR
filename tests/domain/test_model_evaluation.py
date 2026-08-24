import unittest

import numpy as np

from lane_residuals.domain.model_evaluation import build_leave_one_drive_out_folds
from lane_residuals.domain.sequence_dataset import PaddedSequenceDataset


def _dataset() -> PaddedSequenceDataset:
    rng = np.random.default_rng(141)
    conditions = rng.normal(size=(4, 8, 6))
    residuals = rng.normal(size=(4, 8, 21))
    return PaddedSequenceDataset(
        sequence_ids=[f"sequence_{index}" for index in range(4)],
        recording_ids=[f"recording_{index}" for index in range(4)],
        drive_ids=[f"drive_{index}" for index in range(4)],
        conditions=conditions,
        residuals_m=residuals,
        valid_mask=np.ones((4, 8, 21), dtype=np.bool_),
        lengths=[8] * 4,
        pair_indices=np.tile(np.arange(8), (4, 1)),
        estimate_message_indices=np.tile(np.arange(100, 108), (4, 1)),
        estimate_source_times_ns_private=np.vstack(
            [index * 1_000_000_000 + np.arange(8) * 80_000_000 for index in range(4)]
        ),
    )


class DriveGroupedEvaluationTests(unittest.TestCase):
    def test_each_drive_is_tested_once_and_standardization_is_training_only(self) -> None:
        dataset = _dataset()
        drives = tuple(sorted(set(dataset.drive_ids.tolist())))

        folds = build_leave_one_drive_out_folds(dataset, primary_drive_ids=drives)

        self.assertEqual(len(folds), 4)
        self.assertEqual({fold.held_out_drive_id for fold in folds}, set(drives))
        self.assertEqual(
            {sequence for fold in folds for sequence in fold.test_sequence_ids},
            set(dataset.sequence_ids.tolist()),
        )
        for fold in folds:
            self.assertNotIn(fold.held_out_drive_id, fold.standardizer.train_drive_ids)
            expected = dataset.select_drive_ids(fold.training_drive_ids).frame_count
            self.assertEqual(fold.standardizer.training_frame_count, expected)


if __name__ == "__main__":
    unittest.main()
