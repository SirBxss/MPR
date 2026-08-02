import json
import unittest
from types import SimpleNamespace

from lane_residuals import probe_decoded_protobuf_messages


def _enum(name: str, symbols: list[str]) -> SimpleNamespace:
    values = [
        SimpleNamespace(name=symbol, number=index)
        for index, symbol in enumerate(symbols)
    ]
    return SimpleNamespace(
        full_name=name,
        values=values,
        values_by_number={value.number: value for value in values},
    )


def _field(
    name: str,
    number: int,
    field_type: int,
    *,
    label: int = 1,
    message_type=None,
    enum_type=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        number=number,
        type=field_type,
        label=label,
        message_type=message_type,
        enum_type=enum_type,
        containing_oneof=None,
    )


class _Message:
    def __init__(self, descriptor, listed_fields):
        self.DESCRIPTOR = descriptor
        self._listed_fields = tuple(listed_fields)
        for field, value in listed_fields:
            setattr(self, field.name, value)

    def ListFields(self):
        return self._listed_fields


class _DescriptorOnlyMessage:
    """Generated-message stand-in without the Google Protobuf ListFields API."""

    def __init__(self, descriptor, values):
        self.DESCRIPTOR = descriptor
        for name, value in values.items():
            setattr(self, name, value)


def _as_descriptor_only(message):
    values = {}
    for field in message.DESCRIPTOR.fields:
        if not hasattr(message, field.name):
            continue
        value = getattr(message, field.name)
        if isinstance(value, _Message):
            value = _as_descriptor_only(value)
        elif isinstance(value, list):
            value = [
                _as_descriptor_only(item) if isinstance(item, _Message) else item
                for item in value
            ]
        values[field.name] = value
    return _DescriptorOnlyMessage(message.DESCRIPTOR, values)


class PathSourceProbeTests(unittest.TestCase):
    def _message(self):
        role_enum = _enum(
            "Adp.Perception.LaneRole",
            ["LANE_ROLE_UNKNOWN", "LANE_ROLE_KEEP_LANE"],
        )
        error_enum = _enum(
            "Adp.Perception.DrivePathError",
            ["DRIVE_PATH_ERROR_NONE", "DRIVE_PATH_ERROR_INVALID"],
        )
        spline_fields = [
            _field("x_0", 1, 1),
            _field("y_0", 2, 1),
            _field("theta_0", 3, 1),
            _field("curvature_0", 4, 1),
            _field("segment_length", 5, 1, label=3),
            _field("curvature_change", 6, 1, label=3),
        ]
        spline = SimpleNamespace(
            full_name="Adp.Perception.ClothoidSpline",
            fields=spline_fields,
        )
        path_fields = [
            _field("role", 1, 14, enum_type=role_enum),
            _field("estimate", 2, 11, message_type=spline),
            _field("drive_path_error", 3, 14, enum_type=error_enum),
        ]
        path = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePath",
            fields=path_fields,
        )
        root_fields = [
            _field("time_stamp", 1, 4),
            _field("drive_paths", 4, 11, label=3, message_type=path),
        ]
        root = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=root_fields,
            file=SimpleNamespace(serialized_pb=b"production-schema"),
        )

        spline_message = _Message(
            spline,
            [
                (spline_fields[0], -2.5),
                (spline_fields[1], 0.1),
                (spline_fields[2], 0.01),
                (spline_fields[3], 0.001),
                (spline_fields[4], [10.0, 20.0, 30.0]),
                (spline_fields[5], [0.0, 0.01, -0.02]),
            ],
        )
        path_message = _Message(
            path,
            [
                (path_fields[0], 1),
                (path_fields[1], spline_message),
                (path_fields[2], 0),
            ],
        )
        return _Message(
            root,
            [
                (root_fields[0], 123_456_789),
                (root_fields[1], [path_message]),
            ],
        )

    def test_probe_finds_semantic_fields_without_numeric_payload_values(self):
        message = self._message()
        decoded = [
            (
                SimpleNamespace(name="Adp.Perception.EstimatedDrivePaths"),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                SimpleNamespace(log_time=1, publish_time=1),
                message,
            )
        ]

        report = probe_decoded_protobuf_messages(decoded)
        payload = report.to_dict()
        serialized = json.dumps(payload)

        self.assertFalse(payload["raw_numeric_values_exported"])
        self.assertNotIn("-2.5", serialized)
        self.assertEqual(payload["source_timestamp_present_messages"], 1)
        candidates = payload["semantic_candidates"]
        self.assertIn(
            "drive_paths.role",
            candidates["lane_role_or_keep_lane"],
        )
        self.assertIn(
            "drive_paths.estimate.segment_length",
            candidates["segment_lengths"],
        )
        self.assertIn(
            "drive_paths.estimate.curvature_change",
            candidates["curvature_changes"],
        )
        fields = {field["path"]: field for field in payload["fields"]}
        self.assertEqual(
            fields["drive_paths.estimate.segment_length"]["repeated_length"],
            {"minimum": 3, "median": 3.0, "maximum": 3},
        )
        self.assertEqual(
            fields["drive_paths.role"]["observed_enum_symbols"],
            ["LANE_ROLE_KEEP_LANE"],
        )

    def test_probe_rejects_wrong_production_schema(self):
        message = self._message()
        decoded = [
            (
                SimpleNamespace(name="Unexpected.Schema"),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                SimpleNamespace(log_time=1, publish_time=1),
                message,
            )
        ]

        with self.assertRaisesRegex(ValueError, "Unexpected.Schema"):
            probe_decoded_protobuf_messages(decoded)

    def test_probe_supports_descriptor_only_generated_wrappers(self):
        message = _as_descriptor_only(self._message())
        decoded = [
            (
                SimpleNamespace(name="Adp.Perception.EstimatedDrivePaths"),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                SimpleNamespace(log_time=1, publish_time=1),
                message,
            )
        ]

        payload = probe_decoded_protobuf_messages(decoded).to_dict()
        fields = {field["path"]: field for field in payload["fields"]}

        self.assertFalse(payload["raw_numeric_values_exported"])
        self.assertEqual(payload["source_timestamp_present_messages"], 1)
        self.assertEqual(
            fields["drive_paths.estimate.segment_length"]["repeated_length"],
            {"minimum": 3, "median": 3.0, "maximum": 3},
        )
        self.assertEqual(
            fields["drive_paths.role"]["observed_enum_symbols"],
            ["LANE_ROLE_KEEP_LANE"],
        )


if __name__ == "__main__":
    unittest.main()
