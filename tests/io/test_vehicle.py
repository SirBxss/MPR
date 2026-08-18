import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lane_residuals.io.vehicle import decode_longitudinal_speed_samples


class VehicleConditionDecodingTests(unittest.TestCase):
    @staticmethod
    def _record(*, decoded, schema="Adp.QualifiedTimedFloat64"):
        return (
            SimpleNamespace(name=schema),
            SimpleNamespace(
                topic="/adp/velocity_vehicle_longitudinal",
                message_encoding="protobuf",
            ),
            SimpleNamespace(log_time=1_010, publish_time=1_011),
            decoded,
        )

    def test_only_valid_signed_finite_speed_is_retained(self) -> None:
        records = (
            self._record(
                decoded=SimpleNamespace(timestamp=1_000, value=-2.5, qualifier=1)
            ),
            self._record(
                decoded=SimpleNamespace(timestamp=2_000, value=4.0, qualifier=4)
            ),
            self._record(
                decoded=SimpleNamespace(timestamp=3_000, value=float("nan"), qualifier=1)
            ),
            self._record(
                decoded=SimpleNamespace(timestamp=4_000, value=120.0, qualifier=1)
            ),
        )
        with patch(
            "lane_residuals.io.vehicle.iter_decoded_mcap_messages",
            return_value=iter(records),
        ):
            samples, failures, count = decode_longitudinal_speed_samples(
                Path("synthetic.mcap")
            )

        self.assertEqual(count, 4)
        self.assertEqual(len(samples), 1)
        self.assertAlmostEqual(samples[0].value_mps, -2.5)
        self.assertEqual(failures["speed__qualifier_4"], 1)
        self.assertEqual(failures["speed__invalid_message"], 1)
        self.assertEqual(failures["speed__value_out_of_validated_range"], 1)

    def test_wrong_schema_remains_visible(self) -> None:
        record = self._record(decoded=SimpleNamespace(), schema="Unexpected.Speed")
        with patch(
            "lane_residuals.io.vehicle.iter_decoded_mcap_messages",
            return_value=iter((record,)),
        ):
            samples, failures, count = decode_longitudinal_speed_samples(
                Path("synthetic.mcap")
            )

        self.assertEqual(count, 1)
        self.assertEqual(samples, [])
        self.assertEqual(failures["speed__schema_or_encoding_mismatch"], 1)


if __name__ == "__main__":
    unittest.main()
