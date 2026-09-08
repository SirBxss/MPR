from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lane_residuals.domain.conditional_features import ConditionalFeatureError
from lane_residuals.domain.geometry_validation import SplineCurve
from lane_residuals.domain.independent_outing_intake import (
    EXPECTED_TOPOLOGY_SOURCE,
    FrameTechnicalEvidence,
)
from lane_residuals.domain.pairing import ego_relative_path_from_points
from lane_residuals.domain.path_source_probe import (
    ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
    LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
)
from lane_residuals.io.independent_outing_intake import (
    _DecodedEstimate,
    _DecodedReference,
    _decode_geometry_streams,
    _h100_geometry,
    discover_mcaps,
    inspect_recording_technical_evidence,
    read_strict_json_with_bytes,
)


def _straight_path(length: float, lateral_m: float = 0.0):
    return ego_relative_path_from_points(
        np.asarray(((0.0, lateral_m), (length, lateral_m)), dtype=np.float64),
        source="synthetic",
    )


def _curve() -> SplineCurve:
    stations = np.asarray((0.0, 100.0), dtype=np.float64)
    return SplineCurve(
        hypothesis="synthetic",
        curvature_meaning="curvature_rate",
        anchor_policy="anchor_zero",
        s=stations,
        x=stations,
        y=np.zeros(2),
        heading=np.zeros(2),
        curvature=np.zeros(2),
        curvature_rate=np.zeros(2),
        maximum_quadrature_error_m=0.0,
        convergence_position_error_m=0.0,
        convergence_heading_error_rad=0.0,
        sampled_arc_length_deficit_m=0.0,
        invariant_status="passed",
    )


class IndependentOutingIntakeIoTests(unittest.TestCase):
    def test_descriptor_identity_ignores_inconsistent_mcap_schema_bytes(self) -> None:
        message = SimpleNamespace(
            DESCRIPTOR=SimpleNamespace(
                fields=(),
                file=SimpleNamespace(serialized_pb=b"message-owned-descriptor"),
            )
        )
        decoded_stream = [
            (
                SimpleNamespace(
                    name="Adp.Perception.EstimatedDrivePaths",
                    data=b"different-mcap-file-descriptor-set",
                ),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                SimpleNamespace(log_time=1, publish_time=1),
                message,
            )
        ]
        with (
            patch(
                "lane_residuals.io.independent_outing_intake."
                "iter_decoded_mcap_messages",
                return_value=iter(decoded_stream),
            ),
            patch(
                "lane_residuals.io.independent_outing_intake."
                "source_time_ns_from_message",
                return_value=None,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake."
                "estimated_frame_from_message",
                return_value=SimpleNamespace(
                    source_time_ns=None,
                    candidate_ready=False,
                    candidate=None,
                    conversion_state="unsupported_estimate_descriptor_generation",
                ),
            ),
        ):
            estimates, _, failures = _decode_geometry_streams(Path("schema.mcap"))
        self.assertEqual(failures, ())
        self.assertEqual(
            estimates[0].descriptor_file_sha256,
            hashlib.sha256(b"message-owned-descriptor").hexdigest(),
        )

    def test_strict_json_retains_exact_bytes_and_rejects_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.json"
            raw = b'{"value":1}\n'
            valid.write_bytes(raw)
            payload, returned = read_strict_json_with_bytes(valid)
            self.assertEqual(payload, {"value": 1})
            self.assertEqual(returned, raw)

            duplicate = root / "duplicate.json"
            duplicate.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                read_strict_json_with_bytes(duplicate)
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"a":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                read_strict_json_with_bytes(nonfinite)

    def test_recursive_mcap_discovery_is_case_insensitive_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z").mkdir()
            (root / "a.MCAP").write_bytes(b"a")
            (root / "z" / "b.mcap").write_bytes(b"b")
            (root / "ignored.txt").write_bytes(b"x")
            self.assertEqual(
                [path.relative_to(root).as_posix() for path in discover_mcaps(root)],
                ["a.MCAP", "z/b.mcap"],
            )

    def test_stream_decode_failure_discards_a_partial_prefix(self) -> None:
        def interrupted_stream():
            yield (
                SimpleNamespace(name="wrong.EstimateSchema"),
                SimpleNamespace(
                    topic="/adp/estimated_drive_paths",
                    message_encoding="protobuf",
                ),
                SimpleNamespace(log_time=1, publish_time=1),
                object(),
            )
            raise RuntimeError("synthetic stream interruption")

        with (
            patch(
                "lane_residuals.io.independent_outing_intake.iter_decoded_mcap_messages",
                return_value=interrupted_stream(),
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.source_time_ns_from_message",
                return_value=None,
            ),
        ):
            estimates, references, failures = _decode_geometry_streams(
                Path("interrupted.mcap")
            )

        self.assertEqual(estimates, [])
        self.assertEqual(references, [])
        self.assertEqual(failures, ("geometry_stream_decode_failed:RuntimeError",))

    def test_h100_geometry_uses_fixed_coverage_and_anchor_projection(self) -> None:
        ready, anchor, failure = _h100_geometry(
            _straight_path(100.0), _straight_path(101.0, 0.5)
        )
        self.assertTrue(ready)
        self.assertAlmostEqual(anchor or 0.0, 0.5)
        self.assertIsNone(failure)

        ready, _, failure = _h100_geometry(
            _straight_path(100.0), _straight_path(99.0, 0.5)
        )
        self.assertFalse(ready)
        self.assertEqual(failure, "h100_reference_coverage_incomplete")

    def test_topology_is_applied_after_geometry_candidate_classification(self) -> None:
        estimate_path = _straight_path(100.0)
        reference_path = _straight_path(101.0, 0.5)
        condition = SimpleNamespace(
            estimated_mean_abs_curvature_per_m=0.0,
            estimated_curvature_delta_per_m=0.0,
            confidence_near_mean=0.9,
            confidence_middle_mean=0.8,
            confidence_far_mean=0.7,
        )
        odometry = SimpleNamespace(samples=(object(), object()))

        def decoded(topology: str):
            frame = SimpleNamespace(
                estimator_state="available_no_error",
                topology_source=topology,
            )
            return (
                [
                    _DecodedEstimate(
                        message_index=0,
                        source_time_ns=1_000_000_000,
                        frame=frame,
                        curve=_curve(),
                        path=estimate_path,
                        descriptor_file_sha256=(
                            LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256
                        ),
                        decoded=object(),
                    )
                ],
                [
                    _DecodedReference(
                        message_index=0,
                        source_time_ns=1_000_000_000,
                        path=reference_path,
                    )
                ],
                (),
            )

        patches = (
            patch(
                "lane_residuals.io.independent_outing_intake._load_odometry",
                return_value=(odometry, None),
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.selected_keep_lane_confidences",
                return_value=(0.9,) * 20,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.summarize_estimate_conditions",
                return_value=condition,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.derive_unsigned_odometry_speed",
                return_value=SimpleNamespace(),
            ),
        )
        with patches[0], patches[1], patches[2], patches[3]:
            with patch(
                "lane_residuals.io.independent_outing_intake._decode_geometry_streams",
                return_value=decoded(EXPECTED_TOPOLOGY_SOURCE),
            ):
                sensor = inspect_recording_technical_evidence(Path("sensor.mcap"), raw_usable=True)
            with patch(
                "lane_residuals.io.independent_outing_intake._decode_geometry_streams",
                return_value=decoded("ROAD_TOPOLOGY_SOURCE_LANE_MAP"),
            ):
                lane_map = inspect_recording_technical_evidence(Path("map.mcap"), raw_usable=True)

        self.assertEqual(sensor.topology_candidate_count, 1)
        self.assertEqual(sensor.sensor_topology_candidate_count, 1)
        self.assertEqual(sensor.eligible_frame_count, 1)
        self.assertEqual(lane_map.topology_candidate_count, 1)
        self.assertEqual(lane_map.non_sensor_topology_candidate_count, 1)
        self.assertEqual(lane_map.eligible_frame_count, 0)

    def test_semantically_equal_v1_v2_frames_have_equal_downstream_eligibility(self) -> None:
        estimate_path = _straight_path(100.0)
        reference_path = _straight_path(101.0, 0.5)
        frame = SimpleNamespace(
            estimator_state="available_no_error",
            topology_source=EXPECTED_TOPOLOGY_SOURCE,
        )
        condition = SimpleNamespace(
            estimated_mean_abs_curvature_per_m=0.0,
            estimated_curvature_delta_per_m=0.0,
            confidence_near_mean=0.9,
            confidence_middle_mean=0.8,
            confidence_far_mean=0.7,
        )

        def decoded(descriptor_hash: str):
            return (
                [
                    _DecodedEstimate(
                        message_index=0,
                        source_time_ns=1_000_000_000,
                        frame=frame,
                        curve=_curve(),
                        path=estimate_path,
                        descriptor_file_sha256=descriptor_hash,
                        decoded=object(),
                    )
                ],
                [
                    _DecodedReference(
                        message_index=0,
                        source_time_ns=1_000_000_000,
                        path=reference_path,
                    )
                ],
                (),
            )

        evidence = []
        with (
            patch(
                "lane_residuals.io.independent_outing_intake._load_odometry",
                return_value=(SimpleNamespace(samples=(object(), object())), None),
            ),
            patch(
                "lane_residuals.io.independent_outing_intake."
                "selected_keep_lane_confidences",
                return_value=(0.9,) * 20,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake."
                "summarize_estimate_conditions",
                return_value=condition,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake."
                "derive_unsigned_odometry_speed",
                return_value=SimpleNamespace(),
            ),
        ):
            for descriptor_hash in (
                LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256,
                ALLOWED_FLAG_ABSENT_ESTIMATE_FILE_DESCRIPTOR_SHA256,
            ):
                with patch(
                    "lane_residuals.io.independent_outing_intake."
                    "_decode_geometry_streams",
                    return_value=decoded(descriptor_hash),
                ):
                    evidence.append(
                        inspect_recording_technical_evidence(
                            Path("generation.mcap"), raw_usable=True
                        )
                    )
        self.assertEqual(evidence[0].frames, evidence[1].frames)
        self.assertEqual(evidence[0].eligible_frame_count, 1)
        self.assertEqual(evidence[1].eligible_frame_count, 1)

    def test_boundary_odometry_exception_is_limited_to_first_edp_message(self) -> None:
        estimate_path = _straight_path(100.0)
        reference_path = _straight_path(101.0, 0.5)
        frame = SimpleNamespace(
            estimator_state="available_no_error",
            topology_source=EXPECTED_TOPOLOGY_SOURCE,
        )
        timestamps = (1_000_000_000, 1_100_000_000)
        decoded = (
            [
                _DecodedEstimate(
                    message_index=index,
                    source_time_ns=timestamp,
                    frame=frame,
                    curve=_curve(),
                    path=estimate_path,
                    descriptor_file_sha256=(
                        LEGACY_ESTIMATE_FILE_DESCRIPTOR_REFERENCE_SHA256
                    ),
                    decoded=object(),
                )
                for index, timestamp in enumerate(timestamps)
            ],
            [
                _DecodedReference(
                    message_index=index,
                    source_time_ns=timestamp,
                    path=reference_path,
                )
                for index, timestamp in enumerate(timestamps)
            ],
            (),
        )
        condition = SimpleNamespace(
            estimated_mean_abs_curvature_per_m=0.0,
            estimated_curvature_delta_per_m=0.0,
            confidence_near_mean=0.9,
            confidence_middle_mean=0.8,
            confidence_far_mean=0.7,
        )
        previous = FrameTechnicalEvidence(
            estimate_message_index=5,
            source_time_ns=950_000_000,
            topology_source_name=EXPECTED_TOPOLOGY_SOURCE,
            topology_gate_candidate=True,
            h100_geometry_ready=True,
            anchor_distance_within_limit=True,
            causal_inputs_available=True,
            raw_usable=True,
            eligible=True,
        )
        missing_history = ConditionalFeatureError(
            "odometry_reference_time_outside_coverage",
            "synthetic local history is unavailable",
        )
        with (
            patch(
                "lane_residuals.io.independent_outing_intake._decode_geometry_streams",
                return_value=decoded,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake._load_odometry",
                return_value=(SimpleNamespace(samples=(object(), object())), None),
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.selected_keep_lane_confidences",
                return_value=(0.9,) * 20,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.summarize_estimate_conditions",
                return_value=condition,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake.derive_unsigned_odometry_speed",
                side_effect=missing_history,
            ),
            patch(
                "lane_residuals.io.independent_outing_intake._boundary_speed_available",
                return_value=(True, None),
            ) as boundary_speed,
        ):
            evidence = inspect_recording_technical_evidence(
                Path("right.mcap"),
                raw_usable=True,
                previous_path=Path("left.mcap"),
                boundary_accepted=True,
                previous_last_frame=previous,
            )

        self.assertEqual([item.eligible for item in evidence.frames], [True, False])
        boundary_speed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
