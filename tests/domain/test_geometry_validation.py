import math
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals import (
    ComparatorFrameAudit,
    ComparatorGeometry,
    EstimatedFrameAudit,
    GeometryValidationError,
    SplineParameters,
    audit_counts,
    comparator_frame_from_message,
    compare_curve_to_comparator,
    contiguous_state_runs,
    estimated_frame_from_message,
    generate_spline_curve,
    generate_spline_hypotheses,
    state_transition_counts,
    synchronize_estimate_and_comparator,
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


def _estimated_schema():
    role = _enum(
        "Adp.Perception.LaneRole",
        ("LANE_ROLE_UNKNOWN", "LANE_ROLE_KEEP_LANE", "LANE_ROLE_ADJACENT_LEFT"),
    )
    error = _enum(
        "Adp.Perception.DrivePathError",
        (
            "DRIVE_PATH_ERROR_UNINITIALIZED",
            "DRIVE_PATH_ERROR_NO_ERROR",
            "DRIVE_PATH_ERROR_HIGH_CHI_2_FOR_MINIMAL_DISTANCE",
        ),
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
        _field("model_parameters_optional_flag", 8, 8, default_value=False),
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
        file=SimpleNamespace(serialized_pb=b"v038-test-schema"),
    )
    return SimpleNamespace(
        root=root,
        root_fields=root_fields,
        path=path,
        path_fields=path_fields,
        model=model,
        model_fields=model_fields,
    )


def _model(schema, *, starts=(-5.0, 0.0, 10.0), changes=(0.0, 0.0)):
    return _Message(
        schema.model,
        {
            "x_0": 0.0,
            "y_0": 0.0,
            "theta_0": 0.0,
            "curvature_0": 0.0,
            "segment_starts": list(starts),
            "curvature_change": list(changes),
            "index_0": 0,
        },
    )


def _path(schema, *, role=1, error=1, model_flag=True, starts=(-5.0, 0.0, 10.0)):
    return _Message(
        schema.path,
        {
            "error": error,
            "role": role,
            "model_parameters": _model(
                schema,
                starts=starts,
                changes=tuple(0.0 for _ in range(len(starts) - 1)),
            ),
            "model_parameters_optional_flag": model_flag,
            "drive_path_confidences": [0.5],
            "lane_topology_ids": [123456789],
        },
    )


def _root_message(schema, paths, *, timestamp=100, topology=1):
    values = {"topology_source": topology, "drive_paths": list(paths)}
    if timestamp is not None:
        values["time_stamp"] = timestamp
    return _Message(schema.root, values)


def _candidate_v2_schema():
    schema = _estimated_schema()
    schema.path_fields[:] = [
        field
        for field in schema.path_fields
        if field.name != "model_parameters_optional_flag"
    ]
    schema.path.fields = schema.path_fields
    schema.root.file.serialized_pb = b"synthetic-exact-candidate-v2"
    return schema


def _parameters(
    *,
    starts=(-10.0, 0.0, 10.0),
    changes=(0.0, 0.0),
    curvature=0.0,
    x_0=0.0,
    y_0=0.0,
    theta_0=0.0,
    index=0,
    index_explicit=False,
):
    return SplineParameters(
        x_0=x_0,
        y_0=y_0,
        theta_0=theta_0,
        curvature_0=curvature,
        segment_starts=np.asarray(starts),
        curvature_change=np.asarray(changes),
        index_0=index,
        index_0_presence_evidence=("list_fields" if index_explicit else "implicit_default"),
        index_0_explicitly_present=index_explicit,
    )


def _estimated_audit(index, timestamp):
    return EstimatedFrameAudit(
        message_index=index,
        log_time_ns=timestamp,
        publish_time_ns=timestamp,
        source_time_ns=timestamp,
        schema_fingerprint="schema",
        topology_source="ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        total_path_count=1,
        keep_lane_count=1,
        keep_lane_error="DRIVE_PATH_ERROR_NO_ERROR",
        estimator_state="available_no_error",
        conversion_state="candidate_ready",
        interval_count=1,
        candidate=_parameters(starts=(0.0, 1.0), changes=(0.0,)),
    )


def _comparator_audit(index, timestamp):
    return ComparatorFrameAudit(
        message_index=index,
        log_time_ns=timestamp,
        publish_time_ns=timestamp,
        source_time_ns=timestamp,
        state="comparator_ready",
    )


class GeometryIntegrationTests(unittest.TestCase):
    def test_straight_line_integrates_forward_and_backward_from_zero(self):
        curve = generate_spline_curve(
            _parameters(),
            meaning="curvature_rate",
            max_step_m=0.5,
        )
        np.testing.assert_allclose(curve.x, curve.s, atol=1e-12)
        np.testing.assert_allclose(curve.y, 0.0, atol=1e-12)
        np.testing.assert_allclose(curve.heading, 0.0, atol=1e-12)
        np.testing.assert_allclose(curve.curvature, 0.0, atol=1e-12)
        self.assertEqual(curve.invariant_status, "passed")

    def test_constant_curvature_matches_analytic_circle(self):
        curve = generate_spline_curve(
            _parameters(starts=(0.0, 10.0), changes=(0.0,), curvature=0.1),
            meaning="curvature_rate",
            max_step_m=0.25,
        )
        expected_x = np.sin(0.1 * curve.s) / 0.1
        expected_y = (1.0 - np.cos(0.1 * curve.s)) / 0.1
        np.testing.assert_allclose(curve.x, expected_x, atol=1e-11)
        np.testing.assert_allclose(curve.y, expected_y, atol=1e-11)

    def test_rate_and_delta_have_expected_endpoint_curvature(self):
        parameters = _parameters(starts=(0.0, 10.0), changes=(0.02,))
        rate = generate_spline_curve(parameters, meaning="curvature_rate")
        delta = generate_spline_curve(parameters, meaning="curvature_delta")
        self.assertAlmostEqual(rate.curvature[-1], 0.2)
        self.assertAlmostEqual(delta.curvature[-1], 0.02)

    def test_rate_and_delta_parameterizations_are_equivalent_when_scaled(self):
        rate = generate_spline_curve(
            _parameters(starts=(0.0, 4.0), changes=(0.03,)),
            meaning="curvature_rate",
        )
        delta = generate_spline_curve(
            _parameters(starts=(0.0, 4.0), changes=(0.12,)),
            meaning="curvature_delta",
        )
        np.testing.assert_allclose(rate.s, delta.s)
        np.testing.assert_allclose(rate.x, delta.x, atol=1e-12)
        np.testing.assert_allclose(rate.y, delta.y, atol=1e-12)
        np.testing.assert_allclose(rate.curvature, delta.curvature, atol=1e-12)

    def test_variable_nonuniform_interval_counts_are_supported(self):
        starts = np.cumsum([0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        parameters = _parameters(
            starts=tuple(starts),
            changes=tuple(np.linspace(-0.001, 0.001, 7)),
        )
        curves, failures = generate_spline_hypotheses(parameters, max_step_m=0.5)
        self.assertEqual(len(curves), 2)
        self.assertEqual(failures, ())
        self.assertTrue(all(len(curve.s) > 7 for curve in curves))

    def test_index_anchor_requires_explicit_serialized_presence(self):
        curves, failures = generate_spline_hypotheses(
            _parameters(),
            include_explicit_index_anchor=True,
        )
        self.assertEqual(len(curves), 2)
        self.assertEqual(
            {code for _, code in failures},
            {"index_anchor_not_explicit"},
        )

    def test_explicit_interior_index_anchor_integrates_both_directions(self):
        curve = generate_spline_curve(
            _parameters(
                starts=(-5.0, 5.0, 15.0),
                changes=(0.0, 0.0),
                index=1,
                index_explicit=True,
            ),
            meaning="curvature_rate",
            anchor_policy="explicit_index_anchor",
        )
        np.testing.assert_allclose(curve.x, curve.s - 5.0, atol=1e-12)

    def test_curve_generation_is_rigid_transform_equivariant(self):
        base_parameters = _parameters(
            starts=(-2.0, 0.0, 6.0),
            changes=(0.01, -0.02),
            curvature=0.03,
        )
        base = generate_spline_curve(base_parameters, meaning="curvature_rate")
        angle = 0.4
        translation = np.array([2.0, -3.0])
        transformed = generate_spline_curve(
            _parameters(
                starts=(-2.0, 0.0, 6.0),
                changes=(0.01, -0.02),
                curvature=0.03,
                x_0=translation[0],
                y_0=translation[1],
                theta_0=angle,
            ),
            meaning="curvature_rate",
        )
        rotation = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        expected = base.points @ rotation.T + translation
        np.testing.assert_allclose(transformed.points, expected, atol=1e-10)
        np.testing.assert_allclose(
            transformed.heading,
            base.heading + angle,
            atol=1e-12,
        )

    def test_invalid_interval_count_fails_closed(self):
        with self.assertRaisesRegex(
            GeometryValidationError,
            "boundary count minus one",
        ):
            _parameters(starts=(0.0, 1.0, 2.0), changes=(0.0,))

    def test_identical_curve_and_comparator_have_zero_discrepancy(self):
        curve = generate_spline_curve(
            _parameters(starts=(0.0, 25.0), changes=(0.0,)),
            meaning="curvature_rate",
            max_step_m=0.5,
        )
        comparator = ComparatorGeometry(
            s=curve.s,
            x=curve.x,
            y=curve.y,
            heading=curve.heading,
            curvature=curve.curvature,
        )
        metrics = compare_curve_to_comparator(
            curve,
            comparator,
            minimum_common_coverage_m=20.0,
        )
        self.assertEqual(metrics.status, "comparison_completed")
        self.assertAlmostEqual(metrics.lateral_rms_m, 0.0)
        self.assertAlmostEqual(metrics.heading_rms_rad, 0.0)
        self.assertAlmostEqual(metrics.curvature_rms_per_m, 0.0)
        self.assertAlmostEqual(metrics.symmetric_hausdorff_m, 0.0)


class FailClosedExtractionTests(unittest.TestCase):
    def test_valid_adjacent_lane_never_replaces_erroneous_keep_lane(self):
        schema = _estimated_schema()
        message = _root_message(
            schema,
            [
                _path(schema, role=1, error=2),
                _path(schema, role=2, error=1),
            ],
        )
        audit = estimated_frame_from_message(
            message,
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        self.assertEqual(audit.estimator_state, "estimator_reported_error")
        self.assertEqual(audit.conversion_state, "not_attempted_estimator_unavailable")
        self.assertIsNone(audit.candidate)

    def test_exact_keep_lane_candidate_is_ready_but_index_is_implicit(self):
        schema = _estimated_schema()
        audit = estimated_frame_from_message(
            _root_message(schema, [_path(schema)]),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        self.assertEqual(audit.estimator_state, "available_no_error")
        self.assertEqual(audit.conversion_state, "candidate_ready")
        self.assertFalse(audit.candidate.index_0_explicitly_present)
        self.assertEqual(audit.candidate.index_0_presence_evidence, "implicit_default")

    def test_exact_candidate_v2_accepts_absent_flag_from_message_descriptor(self):
        schema = _candidate_v2_schema()
        expected_hash = hashlib.sha256(schema.root.file.serialized_pb).hexdigest()
        for caller_fingerprint in (None, "unrelated-caller-value", "0" * 64):
            with self.subTest(caller_fingerprint=caller_fingerprint):
                path_message = _path(schema)
                delattr(path_message, "model_parameters_optional_flag")
                with patch(
                    "lane_residuals.domain.path_source_probe."
                    "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
                    expected_hash,
                ):
                    audit = estimated_frame_from_message(
                        _root_message(schema, [path_message]),
                        message_index=0,
                        log_time_ns=1,
                        publish_time_ns=1,
                        schema_fingerprint=caller_fingerprint,
                    )
                self.assertTrue(audit.candidate_ready)
                self.assertEqual(audit.descriptor_file_sha256, expected_hash)
                self.assertEqual(audit.descriptor_generation, "candidate_v2")
                self.assertEqual(audit.schema_fingerprint, caller_fingerprint)

    def test_unpinned_flag_absent_descriptor_fails_closed(self):
        schema = _candidate_v2_schema()
        path_message = _path(schema)
        delattr(path_message, "model_parameters_optional_flag")
        audit = estimated_frame_from_message(
            _root_message(schema, [path_message]),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
            schema_fingerprint=(
                "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
            ),
        )
        self.assertEqual(audit.descriptor_generation, "unsupported")
        self.assertEqual(
            audit.conversion_state,
            "unsupported_estimate_descriptor_generation",
        )

    def test_pinned_candidate_identity_rejects_a_descriptor_with_field_8(self):
        schema = _estimated_schema()
        own_hash = hashlib.sha256(schema.root.file.serialized_pb).hexdigest()
        with patch(
            "lane_residuals.domain.path_source_probe."
            "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
            own_hash,
        ):
            audit = estimated_frame_from_message(
                _root_message(schema, [_path(schema)]),
                message_index=0,
                log_time_ns=1,
                publish_time_ns=1,
            )
        self.assertEqual(audit.descriptor_generation, "candidate_v2")
        self.assertEqual(
            audit.conversion_state,
            "candidate_v2_descriptor_contract_mismatch",
        )

    def test_legacy_field_8_requires_explicit_true_boolean(self):
        schema = _estimated_schema()
        for model_flag in (False, None, 1):
            with self.subTest(model_flag=model_flag):
                path_message = _path(schema, model_flag=model_flag)
                if model_flag is None:
                    delattr(path_message, "model_parameters_optional_flag")
                audit = estimated_frame_from_message(
                    _root_message(schema, [path_message]),
                    message_index=0,
                    log_time_ns=1,
                    publish_time_ns=1,
                    schema_fingerprint=(
                        "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
                    ),
                )
                self.assertEqual(audit.descriptor_generation, "legacy_v1")
                self.assertEqual(audit.conversion_state, "model_flag_not_true")

        honest = estimated_frame_from_message(
            _root_message(schema, [_path(schema, model_flag=True)]),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
            schema_fingerprint=(
                "dbfcc4ac6cfb9314dadb860fac9864644a8fe3b9e445270e20621438cf30abf4"
            ),
        )
        self.assertEqual(honest.descriptor_generation, "legacy_v1")
        self.assertTrue(honest.candidate_ready)

    def test_candidate_v2_still_requires_no_error_and_valid_index(self):
        schema = _candidate_v2_schema()
        expected_hash = hashlib.sha256(schema.root.file.serialized_pb).hexdigest()
        cases = (
            ("reported error", _path(schema, error=2), "not_attempted_estimator_unavailable"),
            ("out of range", _path(schema), "index_anchor_out_of_range"),
            ("not integer", _path(schema), "index_anchor_not_integer"),
        )
        cases[0][1].__dict__.pop("model_parameters_optional_flag", None)
        cases[1][1].__dict__.pop("model_parameters_optional_flag", None)
        cases[1][1].model_parameters.index_0 = 99
        cases[2][1].__dict__.pop("model_parameters_optional_flag", None)
        cases[2][1].model_parameters.index_0 = None
        with patch(
            "lane_residuals.domain.path_source_probe."
            "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
            expected_hash,
        ):
            for name, path_message, expected_state in cases:
                with self.subTest(name=name):
                    audit = estimated_frame_from_message(
                        _root_message(schema, [path_message]),
                        message_index=0,
                        log_time_ns=1,
                        publish_time_ns=1,
                    )
                    self.assertEqual(audit.conversion_state, expected_state)

    def test_all_structural_failures_remain_closed_for_both_generations(self):
        mutations = (
            ("parameters absent", lambda path: delattr(path, "model_parameters")),
            (
                "non-finite scalar",
                lambda path: setattr(path.model_parameters, "x_0", float("nan")),
            ),
            (
                "short starts",
                lambda path: setattr(path.model_parameters, "segment_starts", [0.0]),
            ),
            (
                "non-increasing starts",
                lambda path: setattr(
                    path.model_parameters, "segment_starts", [0.0, 0.0, 10.0]
                ),
            ),
            (
                "non-finite changes",
                lambda path: setattr(
                    path.model_parameters,
                    "curvature_change",
                    [0.0, float("inf")],
                ),
            ),
            (
                "count mismatch",
                lambda path: setattr(
                    path.model_parameters, "curvature_change", [0.0]
                ),
            ),
            (
                "index missing",
                lambda path: delattr(path.model_parameters, "index_0"),
            ),
            (
                "index not int-convertible",
                lambda path: setattr(path.model_parameters, "index_0", None),
            ),
            (
                "index boolean",
                lambda path: setattr(path.model_parameters, "index_0", True),
            ),
            (
                "index non-integral numeric",
                lambda path: setattr(path.model_parameters, "index_0", 1.5),
            ),
            (
                "index out of range",
                lambda path: setattr(path.model_parameters, "index_0", 99),
            ),
        )
        for generation in ("legacy_v1", "candidate_v2"):
            for name, mutate in mutations:
                with self.subTest(generation=generation, name=name):
                    schema = (
                        _estimated_schema()
                        if generation == "legacy_v1"
                        else _candidate_v2_schema()
                    )
                    path_message = _path(schema)
                    if generation == "candidate_v2":
                        delattr(path_message, "model_parameters_optional_flag")
                    mutate(path_message)
                    expected_hash = hashlib.sha256(
                        schema.root.file.serialized_pb
                    ).hexdigest()
                    pinned = (
                        expected_hash
                        if generation == "candidate_v2"
                        else "not-the-legacy-decision-source"
                    )
                    with patch(
                        "lane_residuals.domain.path_source_probe."
                        "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
                        pinned,
                    ):
                        audit = estimated_frame_from_message(
                            _root_message(schema, [path_message]),
                            message_index=0,
                            log_time_ns=1,
                            publish_time_ns=1,
                        )
                    self.assertFalse(audit.candidate_ready)

    def test_v1_and_v2_produce_identical_spline_parameters(self):
        legacy_schema = _estimated_schema()
        candidate_schema = _candidate_v2_schema()
        candidate_hash = hashlib.sha256(
            candidate_schema.root.file.serialized_pb
        ).hexdigest()
        legacy_path = _path(legacy_schema)
        candidate_path = _path(candidate_schema)
        delattr(candidate_path, "model_parameters_optional_flag")
        legacy = estimated_frame_from_message(
            _root_message(legacy_schema, [legacy_path]),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        with patch(
            "lane_residuals.domain.path_source_probe."
            "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
            candidate_hash,
        ):
            candidate = estimated_frame_from_message(
                _root_message(candidate_schema, [candidate_path]),
                message_index=0,
                log_time_ns=1,
                publish_time_ns=1,
            )
        self.assertTrue(legacy.candidate_ready and candidate.candidate_ready)
        self.assertEqual(legacy.candidate.index_0, candidate.candidate.index_0)
        for attribute in (
            "x_0",
            "y_0",
            "theta_0",
            "curvature_0",
            "segment_starts",
            "curvature_change",
        ):
            np.testing.assert_array_equal(
                getattr(legacy.candidate, attribute),
                getattr(candidate.candidate, attribute),
            )

    def test_candidate_descriptor_drift_fails_exact_hash_gate(self):
        for drift_name, mutate in (
            ("number", lambda field: setattr(field, "number", 70)),
            ("type", lambda field: setattr(field, "type", 5)),
            ("cardinality", lambda field: setattr(field, "is_repeated", True)),
        ):
            with self.subTest(drift_name=drift_name):
                schema = _candidate_v2_schema()
                pinned_hash = hashlib.sha256(
                    schema.root.file.serialized_pb
                ).hexdigest()
                schema.root.file.serialized_pb = (
                    f"candidate-v2-with-{drift_name}-drift".encode("ascii")
                )
                mutate(schema.model_fields[-1])
                path_message = _path(schema)
                delattr(path_message, "model_parameters_optional_flag")
                with patch(
                    "lane_residuals.domain.path_source_probe."
                    "ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256",
                    pinned_hash,
                ):
                    audit = estimated_frame_from_message(
                        _root_message(schema, [path_message]),
                        message_index=0,
                        log_time_ns=1,
                        publish_time_ns=1,
                    )
                self.assertEqual(audit.descriptor_generation, "unsupported")
                self.assertFalse(audit.candidate_ready)

    def test_missing_timestamp_and_unexpected_topology_are_separate_blocks(self):
        schema = _estimated_schema()
        missing_time = estimated_frame_from_message(
            _root_message(schema, [_path(schema)], timestamp=None),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        wrong_topology = estimated_frame_from_message(
            _root_message(schema, [_path(schema)], topology=0),
            message_index=1,
            log_time_ns=2,
            publish_time_ns=2,
        )
        topology_audit_candidate = estimated_frame_from_message(
            _root_message(schema, [_path(schema)], topology=0),
            message_index=1,
            log_time_ns=2,
            publish_time_ns=2,
            require_sensor_topology=False,
        )
        self.assertEqual(missing_time.estimator_state, "available_no_error")
        self.assertEqual(missing_time.conversion_state, "source_timestamp_missing")
        self.assertEqual(wrong_topology.estimator_state, "available_no_error")
        self.assertEqual(wrong_topology.conversion_state, "unexpected_topology_source")
        self.assertEqual(topology_audit_candidate.conversion_state, "candidate_ready")
        self.assertEqual(
            topology_audit_candidate.topology_source,
            "ROAD_TOPOLOGY_SOURCE_UNKNOWN",
        )

    def test_two_keep_lane_paths_are_ambiguous(self):
        schema = _estimated_schema()
        audit = estimated_frame_from_message(
            _root_message(schema, [_path(schema), _path(schema)]),
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        self.assertEqual(audit.estimator_state, "keep_lane_ambiguous")
        self.assertFalse(audit.candidate_ready)

    def test_strict_ros_comparator_uses_direct_ego_drive_path(self):
        def value(number, invalid=0):
            return SimpleNamespace(mean=number, invalid_flags=invalid)

        vertices = [
            SimpleNamespace(
                x=value(-5.0),
                y=value(0.0),
                heading=value(0.0),
                curvature=value(0.0),
            ),
            SimpleNamespace(
                x=value(0.0),
                y=value(0.0),
                heading=value(0.0),
                curvature=value(0.0),
            ),
            SimpleNamespace(
                x=value(5.0),
                y=value(0.0),
                heading=value(0.0),
                curvature=value(0.0),
            ),
        ]
        message = SimpleNamespace(
            time_stamp_=100,
            ego_lane_segment_indices_=[0],
            polyline_vertex_pool_=vertices,
            polyline_arc_length_pool_=[-5.0, 0.0, 5.0],
            lane_segments_=[
                SimpleNamespace(
                    id_=7,
                    drive_path_range_=SimpleNamespace(start=0, size=3),
                )
            ],
            boundary_vertex_pool_=[],
            lane_boundary_pool_=[],
        )
        audit = comparator_frame_from_message(
            message,
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        self.assertEqual(audit.state, "comparator_ready")
        np.testing.assert_allclose(audit.geometry.s, [-5.0, 0.0, 5.0])

        message.event_data_qualifier_ = SimpleNamespace(qualifier_=2)
        unavailable = comparator_frame_from_message(
            message,
            message_index=1,
            log_time_ns=2,
            publish_time_ns=2,
        )
        self.assertEqual(unavailable.state, "comparator_reported_unavailable")
        self.assertIsNone(unavailable.geometry)

    def test_invalid_comparator_coordinate_mean_is_rejected(self):
        def value(number, invalid=0):
            return SimpleNamespace(mean=number, invalid_flags=invalid)

        message = SimpleNamespace(
            time_stamp_=100,
            ego_lane_segment_indices_=[0],
            polyline_vertex_pool_=[
                SimpleNamespace(
                    x=value(0.0, invalid=1),
                    y=value(0.0),
                    heading=value(0.0),
                    curvature=value(0.0),
                ),
                SimpleNamespace(
                    x=value(1.0),
                    y=value(0.0),
                    heading=value(0.0),
                    curvature=value(0.0),
                ),
            ],
            polyline_arc_length_pool_=[0.0, 1.0],
            lane_segments_=[
                SimpleNamespace(
                    id_=7,
                    drive_path_range_=SimpleNamespace(start=0, size=2),
                )
            ],
            boundary_vertex_pool_=[],
            lane_boundary_pool_=[],
        )
        audit = comparator_frame_from_message(
            message,
            message_index=0,
            log_time_ns=1,
            publish_time_ns=1,
        )
        self.assertNotEqual(audit.state, "comparator_ready")


class SynchronizationAndAvailabilityTests(unittest.TestCase):
    def test_dynamic_programming_avoids_greedy_cardinality_loss(self):
        estimates = [_estimated_audit(0, -3), _estimated_audit(1, 1)]
        comparators = [_comparator_audit(0, 0), _comparator_audit(1, 4)]
        audit = synchronize_estimate_and_comparator(
            estimates,
            comparators,
            max_delta_ms=0.000003,
        )
        self.assertEqual(
            [(pair.estimate_index, pair.comparator_index) for pair in audit.pairs],
            [(0, 0), (1, 1)],
        )

    def test_equal_distance_timestamp_tie_is_ambiguous(self):
        estimates = [_estimated_audit(0, 0)]
        comparators = [_comparator_audit(0, -1), _comparator_audit(1, 1)]
        audit = synchronize_estimate_and_comparator(
            estimates,
            comparators,
            max_delta_ms=0.000001,
        )
        self.assertEqual(audit.pairs, ())
        self.assertEqual(audit.ambiguous_estimate_indices, (0,))

    def test_full_denominator_preserves_structured_error_regime(self):
        ready = _estimated_audit(0, 0)
        error = EstimatedFrameAudit(
            **{
                **ready.__dict__,
                "message_index": 4,
                "estimator_state": "estimator_reported_error",
                "conversion_state": "not_attempted_estimator_unavailable",
                "candidate": None,
            }
        )
        frames = tuple(
            [EstimatedFrameAudit(**{**ready.__dict__, "message_index": index}) for index in range(4)]
            + [EstimatedFrameAudit(**{**error.__dict__, "message_index": index}) for index in range(4, 156)]
            + [EstimatedFrameAudit(**{**ready.__dict__, "message_index": index}) for index in range(156, 251)]
        )
        self.assertEqual(
            contiguous_state_runs(frames),
            (
                ("available_no_error", 4),
                ("estimator_reported_error", 152),
                ("available_no_error", 95),
            ),
        )
        transitions = state_transition_counts(frames)
        cross_transitions = [item for item in transitions if item[0] != item[1]]
        self.assertEqual(len(cross_transitions), 2)
        counts = audit_counts(frames)
        self.assertEqual(counts["decoded_estimate_messages"], 251)
        self.assertEqual(counts["candidate_ready_messages"], 99)
        self.assertTrue(counts["counts_reconcile"])


if __name__ == "__main__":
    unittest.main()
