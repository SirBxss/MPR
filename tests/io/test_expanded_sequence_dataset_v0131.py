import tempfile
import unittest
from pathlib import Path
from lane_residuals.domain.motion import OdometrySample, Pose2D
from lane_residuals.io.expanded_sequence_dataset_v0131 import (
    BoundaryOdometryStream,
    boundary_schemas_compatible,
    validate_live_raw_hashes,
)
from lane_residuals.io.expanded_sequence_dataset import ExpandedSequenceContractError


def _sample(timestamp):
    return OdometrySample(timestamp, timestamp, timestamp, Pose2D(0.0, 0.0, 0.0))


def _stream(name, timestamps=(1, 2), identities=None, failures=None):
    return BoundaryOdometryStream(
        basename_private=name,
        topic="/adp/odometry",
        message_count=len(timestamps),
        samples=tuple(_sample(value) for value in timestamps),
        schema_identities=tuple(identities or ("Adp.OdometryState|protobuf|sha256:abc",)),
        failure_counts=failures or {},
        conflicting_duplicate_timestamp_group_count=0,
    )


class ExpandedSequenceV0131IOTests(unittest.TestCase):
    def test_boundary_schema_requires_exact_matching_expected_streams(self):
        self.assertTrue(boundary_schemas_compatible(_stream("a"), _stream("b")))
        self.assertFalse(
            boundary_schemas_compatible(
                _stream("a"),
                _stream("b", identities=("Other|protobuf|sha256:abc",)),
            )
        )
        self.assertFalse(
            boundary_schemas_compatible(
                _stream("a"), _stream("b", failures={"odometry__invalid_message": 1})
            )
        )

    def test_live_raw_hashes_are_exact_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "a.mcap"
            path.write_bytes(b"raw")
            import hashlib

            digest = hashlib.sha256(b"raw").hexdigest()
            self.assertEqual(
                validate_live_raw_hashes({"a.mcap": path}, {"a.mcap": digest}),
                {"a.mcap": digest},
            )
            with self.assertRaisesRegex(ExpandedSequenceContractError, "hashes differ"):
                validate_live_raw_hashes({"a.mcap": path}, {"a.mcap": "0" * 64})


if __name__ == "__main__":
    unittest.main()
