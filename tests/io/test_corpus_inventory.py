import hashlib
import tempfile
import unittest
from pathlib import Path

from lane_residuals.io.corpus_inventory import parse_filename_time_hints, sha256_file


class CorpusInventoryIoTests(unittest.TestCase):
    def test_filename_times_and_identifier_are_diagnostic_hints(self) -> None:
        hints = parse_filename_time_hints(
            "2025-05-27_15-13-01_2025-05-27_15-13-21_MCAP_000307.mcap"
        )
        self.assertEqual(hints.start, "2025-05-27T15:13:01")
        self.assertEqual(hints.end, "2025-05-27T15:13:21")
        self.assertEqual(hints.duration_ms, 20_000.0)
        self.assertEqual(hints.mcap_identifier, 307)

    def test_unrecognized_filename_has_no_inferred_identity(self) -> None:
        hints = parse_filename_time_hints("private_chunk.mcap")
        self.assertIsNone(hints.start)
        self.assertIsNone(hints.end)
        self.assertIsNone(hints.mcap_identifier)

    def test_sha256_is_streamed_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mcap"
            payload = b"synthetic-mcap-bytes" * 100
            path.write_bytes(payload)
            self.assertEqual(sha256_file(path), hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
