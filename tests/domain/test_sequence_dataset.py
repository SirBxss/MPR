import unittest

import numpy as np

from lane_residuals.domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from lane_residuals.domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    SequenceFrame,
    SequenceStandardizer,
    build_contiguous_sequences,
)


def _frame(
    recording_id: str,
    drive_id: str,
    pair_index: int,
    source_time_ns: int,
    *,
    offset: float = 0.0,
) -> SequenceFrame:
    conditions = np.asarray(
        [offset + pair_index + index / 10.0 for index in range(6)],
        dtype=np.float64,
    )
    residuals = np.asarray(
        [
            offset + 0.01 * pair_index + 0.0001 * station
            for station in CANONICAL_MODEL_STATIONS_M
        ],
        dtype=np.float64,
    )
    return SequenceFrame(
        recording_id=recording_id,
        drive_id=drive_id,
        pair_index=pair_index,
        estimate_message_index=pair_index + 10,
        estimate_source_time_ns_private=source_time_ns,
        conditions=conditions,
        residuals_m=residuals,
    )


class SequenceDatasetTests(unittest.TestCase):
    def test_split_is_recording_local_and_detects_pair_and_time_gaps(self) -> None:
        frames = (
            _frame("recording_001", "drive_a", 0, 1_000_000_000),
            _frame("recording_001", "drive_a", 1, 1_080_000_000),
            _frame("recording_001", "drive_a", 4, 1_500_000_000),
            _frame("recording_001", "drive_a", 5, 1_580_000_000),
            _frame("recording_002", "drive_b", 0, 3_000_000_000),
            _frame("recording_002", "drive_b", 1, 3_080_000_000),
        )

        dataset = build_contiguous_sequences(
            frames,
            maximum_contiguous_gap_ms=200.0,
        )

        self.assertEqual(dataset.frame_count, 6)
        self.assertEqual(
            [sequence.sequence_id for sequence in dataset.sequences],
            [
                "recording_001_segment_001",
                "recording_001_segment_002",
                "recording_002_segment_001",
            ],
        )
        self.assertEqual(
            [sequence.start_reason for sequence in dataset.sequences],
            ["recording_start", "pair_index_and_time_gap", "recording_start"],
        )
        self.assertEqual(dataset.sequences[1].preceding_pair_index_gap, 3)
        self.assertAlmostEqual(dataset.sequences[1].preceding_time_gap_ms, 420.0)

    def test_pair_gap_and_time_gap_are_independently_classified(self) -> None:
        pair_only = build_contiguous_sequences(
            (
                _frame("recording_001", "drive_a", 0, 1_000_000_000),
                _frame("recording_001", "drive_a", 2, 1_080_000_000),
            ),
            maximum_contiguous_gap_ms=200.0,
        )
        time_only = build_contiguous_sequences(
            (
                _frame("recording_001", "drive_a", 0, 1_000_000_000),
                _frame("recording_001", "drive_a", 1, 1_300_000_000),
            ),
            maximum_contiguous_gap_ms=200.0,
        )

        self.assertEqual(pair_only.sequences[1].start_reason, "pair_index_gap")
        self.assertEqual(time_only.sequences[1].start_reason, "time_gap")

    def test_noncanonical_input_order_and_reappearing_recording_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "pair indices must increase"):
            build_contiguous_sequences(
                (
                    _frame("recording_001", "drive_a", 1, 1_000_000_000),
                    _frame("recording_001", "drive_a", 0, 1_080_000_000),
                )
            )
        with self.assertRaisesRegex(ValueError, "one canonical block"):
            build_contiguous_sequences(
                (
                    _frame("recording_001", "drive_a", 0, 1_000_000_000),
                    _frame("recording_002", "drive_b", 0, 2_000_000_000),
                    _frame("recording_001", "drive_a", 1, 3_000_000_000),
                )
            )

    def test_padded_contract_preserves_provenance_and_zero_padding(self) -> None:
        dataset = build_contiguous_sequences(
            (
                _frame("recording_001", "drive_a", 0, 1_000_000_000),
                _frame("recording_001", "drive_a", 1, 1_080_000_000),
                _frame("recording_002", "drive_b", 0, 2_000_000_000),
            )
        ).to_padded()

        self.assertEqual(dataset.conditions.shape, (2, 2, 6))
        self.assertEqual(dataset.residuals_m.shape, (2, 2, 21))
        self.assertEqual(dataset.feature_names, BMW_CONDITION_FEATURE_NAMES)
        np.testing.assert_array_equal(dataset.lengths, [2, 1])
        np.testing.assert_array_equal(dataset.pair_indices[1], [0, -1])
        self.assertTrue(np.all(dataset.valid_mask[0]))
        self.assertTrue(np.all(dataset.valid_mask[1, 0]))
        self.assertFalse(np.any(dataset.valid_mask[1, 1]))
        self.assertTrue(np.all(dataset.conditions[1, 1] == 0.0))
        self.assertTrue(np.all(dataset.residuals_m[1, 1] == 0.0))
        drive_b = dataset.select_drive_ids(("drive_b",))
        self.assertEqual(drive_b.sequence_ids.tolist(), ["recording_002_segment_001"])
        self.assertEqual(drive_b.frame_count, 1)
        with self.assertRaisesRegex(ValueError, "unknown selected"):
            dataset.select_drive_ids(("drive_missing",))

    def test_standardizer_uses_training_drive_only(self) -> None:
        padded = build_contiguous_sequences(
            (
                _frame("recording_001", "drive_a", 0, 1_000_000_000),
                _frame("recording_001", "drive_a", 1, 1_080_000_000),
                _frame(
                    "recording_002",
                    "drive_b",
                    0,
                    2_000_000_000,
                    offset=100.0,
                ),
                _frame(
                    "recording_002",
                    "drive_b",
                    1,
                    2_080_000_000,
                    offset=100.0,
                ),
            )
        ).to_padded()

        standardizer = SequenceStandardizer.fit(
            padded,
            train_drive_ids=("drive_a",),
        )
        standardized = standardizer.standardized_copy(padded)

        expected_condition_mean = np.mean(padded.conditions[0, :2], axis=0)
        expected_residual_mean = np.mean(padded.residuals_m[0, :2], axis=0)
        np.testing.assert_allclose(standardizer.condition_mean, expected_condition_mean)
        np.testing.assert_allclose(standardizer.residual_mean_m, expected_residual_mean)
        np.testing.assert_allclose(
            np.mean(standardized.conditions[0, :2], axis=0),
            np.zeros(6),
            atol=1e-12,
        )
        self.assertGreater(float(np.mean(standardized.conditions[1, :2])), 100.0)
        self.assertTrue(standardized.standardized)
        restored = SequenceStandardizer.from_dict(standardizer.to_dict())
        np.testing.assert_allclose(restored.condition_mean, standardizer.condition_mean)
        np.testing.assert_allclose(
            restored.residual_scale_m,
            standardizer.residual_scale_m,
        )
        self.assertEqual(restored.train_drive_ids, ("drive_a",))


if __name__ == "__main__":
    unittest.main()
