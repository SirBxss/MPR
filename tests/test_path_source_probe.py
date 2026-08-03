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


def _v7_field(
    name: str,
    number: int,
    field_type: int,
    *,
    repeated: bool = False,
    required: bool = False,
    message_type=None,
    enum_type=None,
    default_value=0,
    has_presence: bool = False,
    containing_oneof=None,
) -> SimpleNamespace:
    """Protobuf-7 field stand-in: modern cardinality and no ``label``."""

    return SimpleNamespace(
        name=name,
        number=number,
        type=field_type,
        is_repeated=repeated,
        is_required=required,
        message_type=message_type,
        enum_type=enum_type,
        default_value=default_value,
        has_presence=has_presence,
        containing_oneof=containing_oneof,
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


class _PresenceMessage(_DescriptorOnlyMessage):
    def __init__(
        self,
        descriptor,
        values,
        *,
        present_fields=(),
        selected_oneofs=None,
    ):
        super().__init__(descriptor, values)
        self._present_fields = frozenset(present_fields)
        self._selected_oneofs = dict(selected_oneofs or {})

    def HasField(self, field_name):
        field = next(
            field for field in self.DESCRIPTOR.fields if field.name == field_name
        )
        if not field.has_presence:
            raise ValueError("field has no explicit presence")
        return field_name in self._present_fields

    def WhichOneof(self, oneof_name):
        return self._selected_oneofs.get(oneof_name)


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


def _joint_schema(*, explicit_initial_presence=False):
    role_enum = _enum(
        "Adp.Perception.LaneRole",
        [
            "LANE_ROLE_UNKNOWN",
            "LANE_ROLE_KEEP_LANE",
            "LANE_ROLE_ADJACENT_LEFT",
        ],
    )
    error_enum = _enum(
        "Adp.Perception.DrivePathError",
        [
            "DRIVE_PATH_ERROR_UNINITIALIZED",
            "DRIVE_PATH_ERROR_NO_ERROR",
            "DRIVE_PATH_ERROR_HIGH_CHI_2_FOR_MINIMAL_DISTANCE",
            "DRIVE_PATH_ERROR_NOT_NO_ERROR",
        ],
    )
    topology_enum = _enum(
        "Adp.Perception.TopologySource",
        [
            "ROAD_TOPOLOGY_SOURCE_UNKNOWN",
            "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        ],
    )
    model_fields = [
        _v7_field(
            "x_0",
            1,
            1,
            default_value=0.0,
            has_presence=explicit_initial_presence,
        ),
        _v7_field(
            "y_0",
            2,
            1,
            default_value=0.0,
            has_presence=explicit_initial_presence,
        ),
        _v7_field(
            "theta_0",
            3,
            1,
            default_value=0.0,
            has_presence=explicit_initial_presence,
        ),
        _v7_field(
            "curvature_0",
            4,
            1,
            default_value=0.0,
            has_presence=explicit_initial_presence,
        ),
        _v7_field(
            "segment_starts",
            5,
            1,
            repeated=True,
            default_value=(),
        ),
        _v7_field(
            "curvature_change",
            6,
            1,
            repeated=True,
            default_value=(),
        ),
        _v7_field("index_0", 7, 3, default_value=0),
    ]
    model = SimpleNamespace(
        full_name="Adp.Perception.ClothoidSplineMinimalParameters",
        fields=model_fields,
    )
    path_fields = [
        _v7_field("error", 1, 14, enum_type=error_enum),
        _v7_field("role", 2, 14, enum_type=role_enum),
        _v7_field(
            "model_parameters",
            3,
            11,
            message_type=model,
            has_presence=True,
            default_value=None,
        ),
        _v7_field(
            "model_parameters_optional_flag",
            4,
            8,
            default_value=False,
        ),
        _v7_field(
            "drive_path_confidences",
            5,
            1,
            repeated=True,
            default_value=(),
        ),
        _v7_field(
            "lane_topology_ids",
            6,
            4,
            repeated=True,
            default_value=(),
        ),
    ]
    path = SimpleNamespace(
        full_name="Adp.Perception.DrivePath",
        fields=path_fields,
    )
    root_fields = [
        _v7_field("time_stamp", 1, 18),
        _v7_field("topology_source", 2, 14, enum_type=topology_enum),
        _v7_field(
            "drive_paths",
            3,
            11,
            repeated=True,
            message_type=path,
            default_value=(),
        ),
    ]
    root = SimpleNamespace(
        full_name="Adp.Perception.EstimatedDrivePaths",
        fields=root_fields,
        file=SimpleNamespace(serialized_pb=b"joint-audit-schema"),
    )
    return SimpleNamespace(
        root=root,
        root_fields=root_fields,
        path=path,
        path_fields=path_fields,
        model=model,
        model_fields=model_fields,
    )


def _joint_model(
    schema,
    *,
    initial=(0.0, 0.0, 0.0, 0.0),
    segment_starts=(0.0, 10.0, 20.0, 30.0),
    curvature_change=(0.01, 0.02, 0.03),
    index_0=0,
    explicit_present_fields=None,
):
    values = {
        name: value
        for name, value in zip(
            ("x_0", "y_0", "theta_0", "curvature_0"),
            initial,
        )
    }
    values.update(
        {
            "segment_starts": list(segment_starts),
            "curvature_change": list(curvature_change),
            "index_0": index_0,
        }
    )
    if explicit_present_fields is None:
        return _DescriptorOnlyMessage(schema.model, values)
    return _PresenceMessage(
        schema.model,
        values,
        present_fields=explicit_present_fields,
    )


def _joint_path(
    schema,
    *,
    role=1,
    error=1,
    model=None,
    model_flag=True,
    include_model=True,
    include_flag=True,
    confidences=(0.5, 0.6),
    topology_ids=(812345678901,),
):
    values = {
        "error": error,
        "role": role,
        "drive_path_confidences": list(confidences),
        "lane_topology_ids": list(topology_ids),
    }
    if include_model:
        values["model_parameters"] = _joint_model(schema) if model is None else model
    if include_flag:
        values["model_parameters_optional_flag"] = model_flag
    return _DescriptorOnlyMessage(schema.path, values)


def _joint_message(schema, paths):
    return _DescriptorOnlyMessage(
        schema.root,
        {
            "time_stamp": 123456789,
            "topology_source": 1,
            "drive_paths": list(paths),
        },
    )


class PathSourceProbeTests(unittest.TestCase):
    @staticmethod
    def _decoded(message):
        return [
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

    def test_probe_supports_protobuf7_cardinality_without_label(self):
        role_enum = _enum(
            "Adp.Perception.LaneRole",
            [
                "LANE_ROLE_UNKNOWN",
                "LANE_ROLE_KEEP_LANE",
                "LANE_ROLE_ADJACENT_LEFT",
            ],
        )
        error_enum = _enum(
            "Adp.Perception.DrivePathError",
            [
                "DRIVE_PATH_ERROR_UNINITIALIZED",
                "DRIVE_PATH_ERROR_CROSSES_ITSELF",
                "DRIVE_PATH_ERROR_SEGMENT_BENDS_TOO_STRONG",
                "DRIVE_PATH_ERROR_HIGH_CHI_2",
                "DRIVE_PATH_ERROR_OPTIMIZER_ERROR",
                "DRIVE_PATH_ERROR_INVALID",
                "DRIVE_PATH_ERROR_OTHER",
                "DRIVE_PATH_ERROR_NO_ERROR",
            ],
        )
        parameter_fields = [
            _v7_field("x_0", 1, 1, default_value=0.0),
            _v7_field("y_0", 2, 1, default_value=0.0),
            _v7_field("theta_0", 3, 1, default_value=0.0),
            _v7_field("curvature_0", 4, 1, default_value=0.0),
            _v7_field(
                "segment_starts",
                5,
                1,
                repeated=True,
                default_value=(),
            ),
            _v7_field(
                "curvature_change",
                6,
                1,
                repeated=True,
                default_value=(),
            ),
            _v7_field("index_0", 7, 3, default_value=0),
        ]
        parameters = SimpleNamespace(
            full_name="Adp.Perception.ClothoidSplineMinimalParameters",
            fields=parameter_fields,
        )
        path_fields = [
            _v7_field("error", 1, 14, enum_type=error_enum),
            _v7_field("role", 2, 14, enum_type=role_enum),
            _v7_field(
                "model_parameters",
                3,
                11,
                message_type=parameters,
                has_presence=True,
                default_value=None,
            ),
        ]
        path = SimpleNamespace(
            full_name="Adp.Perception.DrivePath",
            fields=path_fields,
        )
        root_fields = [
            _v7_field("time_stamp", 1, 18),
            _v7_field(
                "drive_paths",
                4,
                11,
                repeated=True,
                message_type=path,
                default_value=(),
            ),
        ]
        root = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=root_fields,
            file=SimpleNamespace(serialized_pb=b"protobuf-7-schema"),
        )

        def path_message(role, segment_starts, curvature_change):
            model = _DescriptorOnlyMessage(
                parameters,
                {
                    "x_0": -123.5,
                    "y_0": 0.25,
                    "theta_0": 0.01,
                    "curvature_0": 0.001,
                    "segment_starts": segment_starts,
                    "curvature_change": curvature_change,
                    "index_0": 987654321,
                },
            )
            return _DescriptorOnlyMessage(
                path,
                {
                    "error": 7,
                    "role": role,
                    "model_parameters": model,
                },
            )

        message = _DescriptorOnlyMessage(
            root,
            {
                "time_stamp": 123456789,
                "drive_paths": [
                    path_message(1, [0.0, 10.0, 20.0, 30.0], [0.1, 0.2, 0.3]),
                    path_message(2, [0.0, 15.0], [0.4]),
                ],
            },
        )

        payload = probe_decoded_protobuf_messages(self._decoded(message)).to_dict()
        fields = {field["path"]: field for field in payload["fields"]}
        serialized = json.dumps(payload)

        self.assertEqual(fields["drive_paths"]["label"], "repeated")
        self.assertEqual(
            fields["drive_paths"]["repeated_length"],
            {"minimum": 2, "median": 2.0, "maximum": 2},
        )
        self.assertEqual(fields["drive_paths"]["observed_occurrences"], 1)
        self.assertEqual(fields["drive_paths.role"]["observed_occurrences"], 2)
        self.assertEqual(
            fields["drive_paths.role"]["observed_enum_symbols"],
            ["LANE_ROLE_ADJACENT_LEFT", "LANE_ROLE_KEEP_LANE"],
        )
        self.assertEqual(
            fields["drive_paths.error"]["observed_enum_symbols"],
            ["DRIVE_PATH_ERROR_NO_ERROR"],
        )
        self.assertEqual(
            fields["drive_paths.model_parameters.segment_starts"]["repeated_length"],
            {"minimum": 2, "median": 3.0, "maximum": 4},
        )
        self.assertEqual(
            fields["drive_paths.model_parameters.curvature_change"]["repeated_length"],
            {"minimum": 1, "median": 2.0, "maximum": 3},
        )
        self.assertEqual(
            fields["drive_paths"]["presence_evidence"],
            ["descriptor_inferred"],
        )
        self.assertIn(
            "drive_paths.model_parameters.index_0",
            payload["semantic_candidates"]["index_or_anchor"],
        )
        self.assertNotIn(
            "drive_paths.model_parameters.index_0",
            payload["semantic_candidates"]["initial_position"],
        )
        self.assertNotIn("-123.5", serialized)
        self.assertNotIn("987654321", serialized)

    def test_presence_fallback_respects_defaults_hasfield_and_oneof(self):
        oneof = SimpleNamespace(name="choice")
        fields = [
            _v7_field(
                "explicit_present",
                1,
                5,
                has_presence=True,
            ),
            _v7_field(
                "explicit_absent",
                2,
                5,
                has_presence=True,
            ),
            _v7_field("implicit_default", 3, 5),
            _v7_field("implicit_nondefault", 4, 5),
            _v7_field(
                "choice_value",
                5,
                5,
                has_presence=True,
                containing_oneof=oneof,
            ),
        ]
        descriptor = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=fields,
            file=SimpleNamespace(serialized_pb=b"presence-schema"),
        )
        message = _PresenceMessage(
            descriptor,
            {
                "explicit_present": 0,
                "explicit_absent": 0,
                "implicit_default": 0,
                "implicit_nondefault": 4,
                "choice_value": 0,
            },
            present_fields={"explicit_present", "choice_value"},
            selected_oneofs={"choice": "choice_value"},
        )

        payload = probe_decoded_protobuf_messages(self._decoded(message)).to_dict()
        observed = {
            field["path"]: field["present_in_sampled_messages"]
            for field in payload["fields"]
        }

        self.assertEqual(observed["explicit_present"], 1)
        self.assertEqual(observed["explicit_absent"], 0)
        self.assertEqual(observed["implicit_default"], 0)
        self.assertEqual(observed["implicit_nondefault"], 1)
        self.assertEqual(observed["choice_value"], 1)

    def test_map_contents_are_not_traversed_or_exported(self):
        map_entry_fields = [
            _v7_field("key", 1, 9, default_value=""),
            _v7_field("value", 2, 5, default_value=0),
        ]
        map_entry = SimpleNamespace(
            full_name="Adp.Perception.SecretMapEntry",
            fields=map_entry_fields,
            GetOptions=lambda: SimpleNamespace(map_entry=True),
        )
        map_field = _v7_field(
            "metadata",
            1,
            11,
            repeated=True,
            message_type=map_entry,
            default_value={},
        )
        descriptor = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=[map_field],
            file=SimpleNamespace(serialized_pb=b"map-schema"),
        )
        message = _DescriptorOnlyMessage(
            descriptor,
            {"metadata": {"CONFIDENTIAL_KEY": 8675309}},
        )

        payload = probe_decoded_protobuf_messages(self._decoded(message)).to_dict()
        fields = {field["path"]: field for field in payload["fields"]}
        serialized = json.dumps(payload)

        self.assertTrue(fields["metadata"]["is_map"])
        self.assertEqual(
            fields["metadata"]["repeated_length"],
            {"minimum": 1, "median": 1.0, "maximum": 1},
        )
        self.assertEqual(fields["metadata.key"]["observed_occurrences"], 0)
        self.assertEqual(fields["metadata.value"]["observed_occurrences"], 0)
        self.assertNotIn("CONFIDENTIAL_KEY", serialized)
        self.assertNotIn("8675309", serialized)

    def test_unknown_enum_number_is_not_exported(self):
        enum_type = _enum("Adp.Perception.Status", ["STATUS_UNKNOWN"])
        field = _v7_field("status", 1, 14, enum_type=enum_type)
        descriptor = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=[field],
            file=SimpleNamespace(serialized_pb=b"enum-schema"),
        )
        message = _DescriptorOnlyMessage(descriptor, {"status": 987654321})

        payload = probe_decoded_protobuf_messages(self._decoded(message)).to_dict()
        serialized = json.dumps(payload)
        observed = payload["fields"][0]["observed_enum_symbols"]

        self.assertEqual(observed, ["UNKNOWN_ENUM_VALUE"])
        self.assertNotIn("987654321", serialized)

    def test_nested_repeated_truncation_is_reported(self):
        child_field = _v7_field("value", 1, 5)
        child = SimpleNamespace(
            full_name="Adp.Perception.Child",
            fields=[child_field],
        )
        children_field = _v7_field(
            "children",
            1,
            11,
            repeated=True,
            message_type=child,
            default_value=(),
        )
        descriptor = SimpleNamespace(
            full_name="Adp.Perception.EstimatedDrivePaths",
            fields=[children_field],
            file=SimpleNamespace(serialized_pb=b"truncation-schema"),
        )
        children = [
            _DescriptorOnlyMessage(child, {"value": index + 1}) for index in range(7)
        ]
        message = _DescriptorOnlyMessage(descriptor, {"children": children})

        payload = probe_decoded_protobuf_messages(
            self._decoded(message),
            max_repeated_items_per_field=3,
        ).to_dict()
        fields = {field["path"]: field for field in payload["fields"]}

        self.assertEqual(payload["max_repeated_items_per_field"], 3)
        self.assertEqual(fields["children"]["nested_message_items_inspected"], 3)
        self.assertEqual(fields["children"]["nested_message_items_truncated"], 4)
        self.assertEqual(fields["children.value"]["observed_occurrences"], 3)

    def test_joint_audit_does_not_correlate_marginal_role_and_error(self):
        schema = _joint_schema()
        message = _joint_message(
            schema,
            [
                _joint_path(schema, role=1, error=2),
                _joint_path(
                    schema,
                    role=2,
                    error=1,
                    model=_joint_model(
                        schema,
                        segment_starts=(0.0, 10.0, 10.0, 30.0),
                    ),
                ),
            ],
        )

        joint = probe_decoded_protobuf_messages(self._decoded(message)).to_dict()[
            "joint_path_semantics"
        ]

        self.assertEqual(joint["summary"]["keep_lane_paths"], 1)
        self.assertEqual(joint["summary"]["no_error_paths"], 1)
        self.assertEqual(joint["summary"]["keep_lane_no_error_paths"], 0)
        self.assertEqual(joint["summary"]["joint_audit_candidate_paths"], 0)
        self.assertNotIn(
            "non_increasing_segment_starts",
            joint["failures_by_code"],
        )
        self.assertEqual(
            joint["role_error_combinations"],
            [
                {
                    "role": "LANE_ROLE_ADJACENT_LEFT",
                    "error": "DRIVE_PATH_ERROR_NO_ERROR",
                    "count": 1,
                },
                {
                    "role": "LANE_ROLE_KEEP_LANE",
                    "error": ("DRIVE_PATH_ERROR_HIGH_CHI_2_FOR_MINIMAL_DISTANCE"),
                    "count": 1,
                },
            ],
        )

    def test_joint_audit_accepts_one_exact_privacy_safe_candidate(self):
        schema = _joint_schema()
        model = _joint_model(
            schema,
            initial=(8123.5, -7123.5, 0.125, -0.0025),
            segment_starts=(0.0, 9.25, 23.75, 51.5),
            curvature_change=(0.011, -0.004, 0.002),
            index_0=998877665544,
        )
        path = _joint_path(
            schema,
            model=model,
            confidences=(0.12345, 0.67891),
            topology_ids=(887766554433,),
        )
        payload = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, [path]))
        ).to_dict()
        joint = payload["joint_path_semantics"]
        audited = joint["paths"][0]
        serialized = json.dumps(payload)

        self.assertEqual(joint["status"], "completed")
        self.assertEqual(joint["summary"]["joint_audit_candidate_paths"], 1)
        self.assertEqual(
            joint["summary"]["messages_safe_for_later_conversion"],
            1,
        )
        self.assertTrue(audited["is_keep_lane_no_error"])
        self.assertTrue(audited["is_joint_audit_candidate"])
        self.assertEqual(audited["candidate_status"], "joint_audit_candidate")
        self.assertEqual(audited["failure_codes"], [])
        self.assertEqual(
            audited["array_counts"],
            {
                "segment_starts": 4,
                "curvature_change": 3,
                "drive_path_confidences": 2,
                "lane_topology_ids": 1,
            },
        )
        self.assertTrue(audited["checks"]["model_structure_valid"])
        self.assertTrue(audited["drive_path_confidences_all_finite"])
        self.assertTrue(audited["index_0_present"])
        for raw_value in (
            "8123.5",
            "-7123.5",
            "51.5",
            "998877665544",
            "887766554433",
            "0.12345",
        ):
            self.assertNotIn(raw_value, serialized)

    def test_joint_audit_accepts_implicit_proto3_zero_initial_values(self):
        schema = _joint_schema()
        path = _joint_path(
            schema,
            model=_joint_model(schema, initial=(0.0, 0.0, 0.0, 0.0)),
        )

        audited = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, [path]))
        ).to_dict()["joint_path_semantics"]["paths"][0]

        self.assertEqual(
            audited["initial_parameter_fields_available"],
            ["x_0", "y_0", "theta_0", "curvature_0"],
        )
        self.assertTrue(audited["checks"]["initial_parameters_all_finite"])
        self.assertTrue(audited["is_joint_audit_candidate"])

    def test_joint_audit_listfields_and_wrapper_forms_agree(self):
        schema = _joint_schema()
        model_values = (1.0, 2.0, 0.1, 0.01)
        model_listed = _Message(
            schema.model,
            [
                (schema.model_fields[0], model_values[0]),
                (schema.model_fields[1], model_values[1]),
                (schema.model_fields[2], model_values[2]),
                (schema.model_fields[3], model_values[3]),
                (schema.model_fields[4], [0.0, 10.0, 20.0, 30.0]),
                (schema.model_fields[5], [0.01, 0.02, 0.03]),
                (schema.model_fields[6], 12),
            ],
        )
        path_listed = _Message(
            schema.path,
            [
                (schema.path_fields[0], 1),
                (schema.path_fields[1], 1),
                (schema.path_fields[2], model_listed),
                (schema.path_fields[3], True),
                (schema.path_fields[4], [0.5, 0.6]),
                (schema.path_fields[5], [123]),
            ],
        )
        message_listed = _Message(
            schema.root,
            [
                (schema.root_fields[0], 123456789),
                (schema.root_fields[1], 1),
                (schema.root_fields[2], [path_listed]),
            ],
        )
        message_wrapper = _joint_message(
            schema,
            [
                _joint_path(
                    schema,
                    model=_joint_model(schema, initial=model_values, index_0=12),
                    topology_ids=(123,),
                )
            ],
        )

        listed_joint = probe_decoded_protobuf_messages(
            self._decoded(message_listed)
        ).to_dict()["joint_path_semantics"]
        wrapper_joint = probe_decoded_protobuf_messages(
            self._decoded(message_wrapper)
        ).to_dict()["joint_path_semantics"]

        self.assertEqual(listed_joint["summary"], wrapper_joint["summary"])
        self.assertEqual(
            listed_joint["paths"][0]["checks"],
            wrapper_joint["paths"][0]["checks"],
        )
        self.assertEqual(
            listed_joint["paths"][0]["is_joint_audit_candidate"],
            wrapper_joint["paths"][0]["is_joint_audit_candidate"],
        )

    def test_joint_audit_rejects_explicitly_absent_initial_values(self):
        schema = _joint_schema(explicit_initial_presence=True)
        model = _joint_model(
            schema,
            explicit_present_fields={
                "x_0",
                "theta_0",
                "curvature_0",
            },
        )
        path = _joint_path(schema, model=model)

        audited = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, [path]))
        ).to_dict()["joint_path_semantics"]["paths"][0]

        self.assertNotIn("y_0", audited["initial_parameter_fields_available"])
        self.assertFalse(audited["checks"]["initial_parameters_all_finite"])
        self.assertFalse(audited["is_joint_audit_candidate"])
        self.assertIn("initial_parameters_unavailable", audited["failure_codes"])

    def test_joint_audit_reports_numeric_failures_without_leaking_values(self):
        schema = _joint_schema()
        paths = [
            _joint_path(
                schema,
                model=_joint_model(schema, initial=(float("nan"), 0, 0, 0)),
            ),
            _joint_path(
                schema,
                model=_joint_model(
                    schema,
                    segment_starts=(0.0, 10.0, float("inf"), 30.0),
                ),
            ),
            _joint_path(
                schema,
                model=_joint_model(
                    schema,
                    segment_starts=(0.0, 10.0, 10.0, 30.0),
                ),
            ),
            _joint_path(
                schema,
                model=_joint_model(
                    schema,
                    curvature_change=(0.1, float("-inf")),
                ),
            ),
        ]
        payload = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, paths))
        ).to_dict()
        joint = payload["joint_path_semantics"]
        serialized = json.dumps(payload)

        self.assertEqual(joint["summary"]["joint_audit_candidate_paths"], 0)
        failures = joint["failures_by_code"]
        self.assertEqual(failures["non_finite_initial_parameters"], 1)
        self.assertEqual(failures["non_finite_segment_starts"], 1)
        self.assertEqual(failures["non_increasing_segment_starts"], 1)
        self.assertEqual(failures["non_finite_curvature_change"], 1)
        self.assertEqual(failures["interval_count_mismatch"], 1)
        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)

    def test_joint_audit_distinguishes_model_flag_and_model_absence(self):
        schema = _joint_schema()
        paths = [
            _joint_path(schema, model_flag=False),
            _joint_path(schema, include_flag=False),
            _joint_path(schema, include_model=False),
        ]

        joint = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, paths))
        ).to_dict()["joint_path_semantics"]

        self.assertEqual(joint["summary"]["keep_lane_no_error_paths"], 3)
        self.assertEqual(joint["summary"]["joint_audit_candidate_paths"], 0)
        self.assertFalse(joint["paths"][0]["model_parameters_optional_flag_present"])
        self.assertFalse(joint["paths"][0]["model_parameters_optional_flag_value"])
        self.assertIsNone(joint["paths"][1]["model_parameters_optional_flag_value"])
        self.assertFalse(joint["paths"][2]["model_parameters_present"])
        self.assertIn(
            "model_parameters_absent",
            joint["paths"][2]["failure_codes"],
        )

    def test_joint_audit_requires_exact_enum_symbols_and_hides_unknown_number(self):
        schema = _joint_schema()
        paths = [
            _joint_path(schema, error=3),
            _joint_path(schema, role=987654321),
        ]
        payload = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, paths))
        ).to_dict()
        joint = payload["joint_path_semantics"]

        self.assertEqual(joint["summary"]["joint_audit_candidate_paths"], 0)
        self.assertEqual(
            joint["paths"][0]["error"],
            "DRIVE_PATH_ERROR_NOT_NO_ERROR",
        )
        self.assertFalse(joint["paths"][0]["is_no_error"])
        self.assertEqual(joint["paths"][1]["role"], "UNKNOWN_ENUM_VALUE")
        self.assertNotIn("987654321", json.dumps(payload))

    def test_joint_audit_marks_multiple_or_truncated_candidates_unsafe(self):
        schema = _joint_schema()
        message = _joint_message(
            schema,
            [_joint_path(schema), _joint_path(schema)],
        )

        complete = probe_decoded_protobuf_messages(
            self._decoded(message),
            max_repeated_items_per_field=64,
        ).to_dict()["joint_path_semantics"]
        truncated = probe_decoded_protobuf_messages(
            self._decoded(message),
            max_repeated_items_per_field=1,
        ).to_dict()["joint_path_semantics"]

        self.assertEqual(
            complete["summary"]["messages_with_multiple_joint_audit_candidates"],
            1,
        )
        self.assertEqual(
            complete["summary"]["messages_safe_for_later_conversion"],
            0,
        )
        self.assertEqual(truncated["status"], "completed_with_truncation")
        self.assertEqual(truncated["summary"]["truncated_paths"], 1)
        self.assertEqual(
            truncated["summary"]["messages_safe_for_later_conversion"],
            0,
        )

    def test_joint_audit_handles_empty_drive_path_container(self):
        schema = _joint_schema()
        joint = probe_decoded_protobuf_messages(
            self._decoded(_joint_message(schema, []))
        ).to_dict()["joint_path_semantics"]

        self.assertEqual(joint["status"], "completed")
        self.assertEqual(joint["summary"]["total_paths"], 0)
        self.assertEqual(joint["summary"]["messages_with_no_keep_lane"], 1)
        self.assertEqual(joint["paths"], [])

    def test_conversion_gate_requires_timestamp_and_expected_topology(self):
        schema = _joint_schema()
        path = _joint_path(schema)
        missing_timestamp = _DescriptorOnlyMessage(
            schema.root,
            {
                "topology_source": 1,
                "drive_paths": [path],
            },
        )
        wrong_topology = _DescriptorOnlyMessage(
            schema.root,
            {
                "time_stamp": 123456789,
                "topology_source": 0,
                "drive_paths": [path],
            },
        )

        missing_summary = probe_decoded_protobuf_messages(
            self._decoded(missing_timestamp)
        ).to_dict()["joint_path_semantics"]["summary"]
        topology_summary = probe_decoded_protobuf_messages(
            self._decoded(wrong_topology)
        ).to_dict()["joint_path_semantics"]["summary"]

        self.assertEqual(missing_summary["joint_audit_candidate_paths"], 1)
        self.assertEqual(missing_summary["messages_safe_for_later_conversion"], 0)
        self.assertEqual(topology_summary["joint_audit_candidate_paths"], 1)
        self.assertEqual(topology_summary["messages_safe_for_later_conversion"], 0)


if __name__ == "__main__":
    unittest.main()
