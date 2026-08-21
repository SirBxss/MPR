import hashlib
import tempfile
import unittest
from pathlib import Path

import numpy as np

from lane_residuals.io.expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    residual_profiles_by_pair,
    validate_profile_archive,
    write_deterministic_npz,
)


class ExpandedSequenceIOTests(unittest.TestCase):
    def test_profile_reconstruction_requires_exact_21_station_h100_rows(self):
        rows = [
            {
                "recording_id": "recording_001",
                "pair_index": "4",
                "station_m": str(station),
                "aligned_lateral_m": str(station / 100.0),
                "h100_aligned_eligible": "True",
            }
            for station in range(0, 101, 5)
        ]
        rows.append({**rows[-1], "recording_id": "recording_002"})
        profiles = residual_profiles_by_pair(rows)
        self.assertEqual(set(profiles), {("recording_001", 4)})
        self.assertEqual(profiles[("recording_001", 4)].shape, (21,))

    def test_deterministic_archive_is_byte_identical_and_validated(self):
        count = 3
        arrays = {
            "residuals_m": np.zeros((count, 21)),
            "conditions": np.ones((count, 6)),
            "timestamps_ns_private": np.arange(count, dtype=np.int64),
            "recording_ids": np.asarray(["r1", "r1", "r2"]),
            "drive_ids": np.asarray(["d1", "d1", "d2"]),
            "mcap_basenames_private": np.asarray(["a", "a", "b"]),
            "sequence_ids": np.asarray(["s1", "s1", "s2"]),
            "pair_indices": np.arange(count, dtype=np.int64),
            "estimate_message_indices": np.arange(count, dtype=np.int64),
            "stations_m": np.arange(0, 101, 5, dtype=np.float64),
            "eligibility": np.ones(count, dtype=np.bool_),
            "exclusion_reasons": np.asarray(["", "", ""]),
        }
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.npz"
            second = Path(temporary) / "second.npz"
            write_deterministic_npz(first, arrays)
            write_deterministic_npz(second, dict(reversed(list(arrays.items()))))
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            shapes = validate_profile_archive(first)
            self.assertEqual(shapes["residuals_m"], (3, 21))
            self.assertEqual(shapes["conditions"], (3, 6))

            bad = dict(arrays)
            bad["conditions"] = np.ones((count, 5))
            write_deterministic_npz(first, bad)
            with self.assertRaisesRegex(ExpandedSequenceContractError, "invalid shape"):
                validate_profile_archive(first)


if __name__ == "__main__":
    unittest.main()
