import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lane_residuals.io.odometry import decode_odometry_samples


class OdometryDecodingTests(unittest.TestCase):
    @staticmethod
    def _record(*, decoded, schema_name="Adp.OdometryState", encoding="protobuf"):
        return (
            SimpleNamespace(name=schema_name),
            SimpleNamespace(topic="/adp/odometry", message_encoding=encoding),
            SimpleNamespace(log_time=1_010, publish_time=1_011),
            decoded,
        )

    def test_planar_rear_axle_pose_is_decoded_with_both_time_domains(self) -> None:
        record = self._record(
            decoded=SimpleNamespace(
                timestamp=1_000,
                x_position=12.5,
                y_position=-3.25,
                yaw_angle=0.2,
            )
        )
        with patch(
            "lane_residuals.io.odometry.iter_decoded_mcap_messages",
            return_value=iter((record,)),
        ):
            samples, failures, count = decode_odometry_samples(
                Path("synthetic.mcap")
            )

        self.assertEqual(count, 1)
        self.assertEqual(failures, {})
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].timestamp_ns, 1_000)
        self.assertEqual(samples[0].log_time_ns, 1_010)
        self.assertAlmostEqual(samples[0].pose.x_m, 12.5)
        self.assertAlmostEqual(samples[0].pose.yaw_rad, 0.2)

    def test_invalid_and_wrong_schema_messages_remain_visible(self) -> None:
        invalid = self._record(
            decoded=SimpleNamespace(
                timestamp=1_000,
                x_position="",
                y_position=0.0,
                yaw_angle=0.0,
            )
        )
        wrong_schema = self._record(
            decoded=SimpleNamespace(),
            schema_name="Unexpected.Odometry",
        )
        with patch(
            "lane_residuals.io.odometry.iter_decoded_mcap_messages",
            return_value=iter((invalid, wrong_schema)),
        ):
            samples, failures, count = decode_odometry_samples(
                Path("synthetic.mcap")
            )

        self.assertEqual(count, 2)
        self.assertEqual(samples, [])
        self.assertEqual(failures["odometry__invalid_message"], 1)
        self.assertEqual(
            failures["odometry__schema_or_encoding_mismatch"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
