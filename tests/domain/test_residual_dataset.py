import unittest

import numpy as np

from lane_residuals.domain.residual_dataset import (
    CANONICAL_MODEL_STATIONS_M,
    ResidualDatasetContractError,
    build_canonical_residual_dataset,
    residual_column_name,
)


class CanonicalResidualDatasetTests(unittest.TestCase):
    @staticmethod
    def _pair(
        *,
        pair_index: int,
        drive_id: str = "drive_001",
        h60: bool = True,
        h100: bool = True,
    ):
        return {
            "recording_id": "recording_001",
            "drive_id": drive_id,
            "pair_index": pair_index,
            "estimate_message_index": pair_index + 10,
            "map_message_index": pair_index + 20,
            "estimate_source_time_ns_private": 900 + pair_index,
            "map_source_time_ns_private": 100_900 + pair_index,
            "source_delta_ms": -0.1,
            "pair_state": "aligned_h100_ready" if h100 else "aligned_h60_ready",
            "failure_code": "",
            "h60_aligned_eligible": h60,
            "h100_aligned_eligible": h100,
        }

    @staticmethod
    def _stations(*, pair_index: int, h100: bool = True):
        return [
            {
                "recording_id": "recording_001",
                "drive_id": "drive_001",
                "pair_index": pair_index,
                "station_m": station,
                "aligned_lateral_m": 0.01 * station + pair_index,
                "h100_aligned_eligible": h100,
            }
            for station in CANONICAL_MODEL_STATIONS_M
        ]

    def test_complete_h100_rows_become_ordered_wide_vectors(self) -> None:
        pairs = [self._pair(pair_index=2), self._pair(pair_index=1)]
        stations = self._stations(pair_index=2) + self._stations(pair_index=1)

        dataset = build_canonical_residual_dataset(
            pairs,
            stations,
            recording_drive_ids={"recording_001": "drive_001"},
        )

        self.assertEqual(dataset.matrix_m.shape, (2, 21))
        self.assertEqual([row.pair_index for row in dataset.observations], [1, 2])
        np.testing.assert_allclose(
            dataset.matrix_m[0],
            [0.01 * station + 1 for station in CANONICAL_MODEL_STATIONS_M],
        )
        wide = dataset.observations[0].as_csv_row()
        self.assertEqual(wide["residual_000m_m"], 1.0)
        self.assertEqual(wide["residual_100m_m"], 2.0)

    def test_missing_station_fails_instead_of_using_available_cases(self) -> None:
        stations = self._stations(pair_index=1)[:-1]

        with self.assertRaisesRegex(
            ResidualDatasetContractError,
            "exact 21-station grid",
        ):
            build_canonical_residual_dataset(
                [self._pair(pair_index=1), self._pair(pair_index=2)],
                stations + self._stations(pair_index=2),
                recording_drive_ids={"recording_001": "drive_001"},
            )

    def test_h100_without_h60_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResidualDatasetContractError, "subset"):
            build_canonical_residual_dataset(
                [
                    self._pair(pair_index=1, h60=False),
                    self._pair(pair_index=2),
                ],
                self._stations(pair_index=1) + self._stations(pair_index=2),
                recording_drive_ids={"recording_001": "drive_001"},
            )

    def test_drive_assignment_must_match_exact_manifest(self) -> None:
        with self.assertRaisesRegex(ResidualDatasetContractError, "exact manifest"):
            build_canonical_residual_dataset(
                [self._pair(pair_index=1, drive_id="wrong")],
                self._stations(pair_index=1),
                recording_drive_ids={"recording_001": "drive_001"},
            )

    def test_duplicate_station_is_rejected(self) -> None:
        stations = self._stations(pair_index=1)
        with self.assertRaisesRegex(ResidualDatasetContractError, "duplicate station"):
            build_canonical_residual_dataset(
                [self._pair(pair_index=1), self._pair(pair_index=2)],
                stations + [dict(stations[0])] + self._stations(pair_index=2),
                recording_drive_ids={"recording_001": "drive_001"},
            )

    def test_residual_column_names_are_unit_explicit(self) -> None:
        self.assertEqual(residual_column_name(5.0), "residual_005m_m")
        with self.assertRaisesRegex(ValueError, "integer"):
            residual_column_name(2.5)


if __name__ == "__main__":
    unittest.main()
