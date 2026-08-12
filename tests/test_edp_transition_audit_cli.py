import csv
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lane_residuals.edp_transition_audit_cli import (
    _decode_one_estimate_message,
    main,
    run_edp_transition_audit,
)


def _enum(name, symbols):
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
    name,
    number,
    field_type,
    *,
    repeated=False,
    message_type=None,
    enum_type=None,
    default_value=0,
    has_presence=False,
):
    return SimpleNamespace(
        name=name,
        number=number,
        type=field_type,
        is_repeated=repeated,
        is_required=False,
        message_type=message_type,
        enum_type=enum_type,
        default_value=default_value,
        has_presence=has_presence,
        containing_oneof=None,
    )


class _Message:
    def __init__(self, descriptor, values):
        self.DESCRIPTOR = descriptor
        for name, value in values.items():
            setattr(self, name, value)


def _schema():
    role = _enum(
        "Adp.Perception.LaneRole",
        ("LANE_ROLE_UNKNOWN", "LANE_ROLE_KEEP_LANE", "LANE_ROLE_ADJACENT_LEFT"),
    )
    error = _enum(
        "Adp.Perception.DrivePathError",
        ("DRIVE_PATH_ERROR_UNINITIALIZED", "DRIVE_PATH_ERROR_NO_ERROR"),
    )
    topology = _enum(
        "Adp.Perception.TopologySource",
        (
            "ROAD_TOPOLOGY_SOURCE_UNKNOWN",
            "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        ),
    )
    model_fields = [
        _field("x_0", 1, 1, default_value=0.0),
        _field("y_0", 2, 1, default_value=0.0),
        _field("theta_0", 3, 1, default_value=0.0),
        _field("curvature_0", 4, 1, default_value=0.0),
        _field("segment_starts", 5, 1, repeated=True, default_value=()),
        _field("curvature_change", 6, 1, repeated=True, default_value=()),
        _field("index_0", 7, 3, default_value=0),
    ]
    model = SimpleNamespace(
        full_name="Adp.Perception.ClothoidSplineMinimalParameters",
        fields=model_fields,
    )
    path_fields = [
        _field("error", 1, 14, enum_type=error),
        _field("role", 2, 14, enum_type=role),
        _field(
            "model_parameters",
            3,
            11,
            message_type=model,
            default_value=None,
            has_presence=True,
        ),
        _field("model_parameters_optional_flag", 4, 8, default_value=False),
        _field("drive_path_confidences", 5, 1, repeated=True, default_value=()),
        _field("lane_topology_ids", 6, 4, repeated=True, default_value=()),
    ]
    path = SimpleNamespace(full_name="Adp.Perception.DrivePath", fields=path_fields)
    root_fields = [
        _field("time_stamp", 1, 18, default_value=0),
        _field("topology_source", 2, 14, enum_type=topology),
        _field(
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
        file=SimpleNamespace(serialized_pb=b"v042-test-schema"),
    )
    return SimpleNamespace(root=root, path=path, model=model)


def _path(schema, *, role, y_0, topology_id):
    model = _Message(
        schema.model,
        {
            "x_0": 0.0,
            "y_0": y_0,
            "theta_0": 0.0,
            "curvature_0": 0.0,
            "segment_starts": [0.0, 120.0],
            "curvature_change": [0.0],
            "index_0": 0,
        },
    )
    return _Message(
        schema.path,
        {
            "error": 1,
            "role": role,
            "model_parameters": model,
            "model_parameters_optional_flag": True,
            "drive_path_confidences": [0.4, 0.8],
            "lane_topology_ids": [topology_id],
        },
    )


def _root(schema, *, timestamp, keep_y):
    return _Message(
        schema.root,
        {
            "time_stamp": timestamp,
            "topology_source": 1,
            "drive_paths": [
                _path(schema, role=2, y_0=-3.0, topology_id=20),
                _path(schema, role=1, y_0=keep_y, topology_id=10),
            ],
        },
    )


def _decode(decoded, index):
    return _decode_one_estimate_message(
        decoded,
        message_index=index,
        log_time_ns=index,
        publish_time_ns=index,
        schema_name="Adp.Perception.EstimatedDrivePaths",
        message_encoding="protobuf",
        max_step_m=1.0,
        stations_m=(0.0, 50.0, 100.0),
    )


class EdpTransitionAuditCliTests(unittest.TestCase):
    def test_all_candidates_are_retained_and_keep_lane_index_is_explicit(self):
        schema = _schema()
        message = _decode(_root(schema, timestamp=100_000_000, keep_y=0.0), 0)

        self.assertEqual(message.total_path_count, 2)
        self.assertEqual(message.selected_keep_lane_path_index, 1)
        self.assertEqual(message.selected_pairing_audit_path_index, 1)
        self.assertEqual(len(message.candidate_records), 2)
        self.assertFalse(
            message.candidate_records[0].snapshot.selected_unique_keep_lane
        )
        self.assertTrue(
            message.candidate_records[1].snapshot.selected_for_pairing_audit
        )
        self.assertEqual(len(message.candidate_records[0].snapshot.geometries), 2)
        self.assertEqual(len(message.candidate_records[1].snapshot.geometries), 2)

    def test_synthetic_run_writes_candidate_and_transition_evidence(self):
        schema = _schema()
        messages = [
            _decode(_root(schema, timestamp=100_000_000, keep_y=0.0), 0),
            _decode(_root(schema, timestamp=180_000_000, keep_y=2.0), 1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit"
            arguments = SimpleNamespace(
                mcap=Path("synthetic.mcap"),
                estimate_topic="/adp/estimated_drive_paths",
                max_step_m=1.0,
                transition_centers=[1],
                ranking_hypothesis="curvature_delta",
                max_transition_windows=4,
                transition_window_radius=1,
                output_directory=output,
            )
            with patch(
                "lane_residuals.edp_transition_audit_cli._decode_estimate_stream",
                return_value=(messages, Counter({"candidate_ready": 2})),
            ):
                summary = run_edp_transition_audit(
                    arguments,
                    stations_m=(0.0, 50.0, 100.0),
                )

            self.assertEqual(summary["all_candidate_count"], 4)
            self.assertEqual(summary["selected_transition_comparison_count"], 2)
            self.assertEqual(summary["version"], "0.4.3")
            self.assertEqual(
                summary["provisional_pairing_reconstruction"],
                "curvature_rate",
            )
            self.assertFalse(summary["generated_final_residual_dataset"])
            self.assertFalse(summary["curvature_change_semantics_confirmed"])
            for name in (
                "edp_message_inventory.csv",
                "edp_candidate_inventory.csv",
                "edp_candidate_geometry.csv",
                "edp_selected_transitions.csv",
                "edp_transition_windows.png",
                "edp_transition_metrics.png",
                "edp_transition_summary.json",
            ):
                self.assertTrue((output / name).is_file(), name)
            with (output / "edp_candidate_inventory.csv").open(
                "r", encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(
                [row["path_index"] for row in rows if row["selected_for_pairing_audit"] == "True"],
                ["1", "1"],
            )

    def test_missing_mcap_returns_argument_error(self):
        self.assertEqual(main(["missing.mcap"]), 2)


if __name__ == "__main__":
    unittest.main()
