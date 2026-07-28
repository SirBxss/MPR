import json
import tempfile
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lane_residuals import (
    RoadFrame,
    RoadSegment,
    SegmentExtraction,
    build_residual_dataset,
    build_residual_dataset_from_mcap,
    estimate_path_on_reference,
    plot_lane_association_audit,
    plot_mcap_dataset_diagnostics,
    project_points_to_polyline,
    reference_path_from_segment,
    save_residual_dataset,
    select_ego_segment,
    synchronize_road_frames,
)


def _segment(
    segment_id: int,
    *,
    y: float,
    x_start: float = -5.0,
    x_stop: float = 60.0,
    is_ego: bool | None = None,
) -> RoadSegment:
    x = np.linspace(x_start, x_stop, int(x_stop - x_start) + 1)
    return RoadSegment(
        segment_id=segment_id,
        x=x,
        y=np.full_like(x, y),
        arc_length=x - x[0],
        heading=np.zeros_like(x),
        curvature=np.zeros_like(x),
        is_ego=is_ego,
    )


def _frame(
    topic: str,
    time_ns: int,
    segments: tuple[RoadSegment, ...],
) -> RoadFrame:
    return RoadFrame(
        topic=topic,
        schema_name="Adp.Perception.Road",
        log_time_ns=time_ns,
        publish_time_ns=time_ns,
        sequence=0,
        source_time_ns=time_ns + 1_000,
        segments=segments,
    )


class PreprocessingTests(unittest.TestCase):
    def test_projection_returns_reference_station_and_lateral_distance(self) -> None:
        projection = project_points_to_polyline(
            [[0.0, 0.0], [10.0, 0.0]],
            [[2.0, 0.5], [7.0, -0.25]],
        )

        np.testing.assert_allclose(projection.stations, [2.0, 7.0])
        np.testing.assert_allclose(projection.projected_points, [[2.0, 0.0], [7.0, 0.0]])
        np.testing.assert_allclose(projection.distances, [0.5, 0.25])

    def test_reversed_reference_vertices_are_oriented_forward(self) -> None:
        x = np.linspace(60.0, -5.0, 66)
        reversed_segment = RoadSegment(
            segment_id=1,
            x=x,
            y=np.zeros_like(x),
            arc_length=np.linspace(0.0, 65.0, 66),
        )

        path = reference_path_from_segment(reversed_segment)

        self.assertLessEqual(path.s[0], -5.0)
        self.assertGreaterEqual(path.s[-1], 60.0)
        np.testing.assert_allclose(path.sample([0.0, 50.0])[:, 0], [0.0, 50.0])

    def test_estimate_points_beyond_reference_end_are_trimmed(self) -> None:
        reference = reference_path_from_segment(_segment(1, y=0.0))
        long_estimate = _segment(
            2,
            y=0.2,
            x_start=-5.0,
            x_stop=80.0,
        )

        estimate, _, retained_fraction = estimate_path_on_reference(
            long_estimate,
            reference,
        )

        self.assertGreaterEqual(estimate.s[-1], 60.0)
        self.assertEqual(retained_fraction, 1.0)

    def test_ego_metadata_precedes_nearest_origin_fallback(self) -> None:
        metadata_frame = _frame(
            "/road",
            1,
            (
                _segment(1, y=0.05, is_ego=False),
                _segment(2, y=1.0, is_ego=True),
            ),
        )

        selected = select_ego_segment(metadata_frame)

        self.assertEqual(selected.segment.segment_id, 2)
        self.assertEqual(selected.method, "metadata")

        fallback_frame = _frame(
            "/road",
            2,
            (
                _segment(3, y=1.0),
                _segment(4, y=0.1),
            ),
        )
        fallback = select_ego_segment(fallback_frame)
        self.assertEqual(fallback.segment.segment_id, 4)
        self.assertEqual(fallback.method, "nearest_origin_fallback")

    def test_synchronization_is_one_to_one_and_obeys_tolerance(self) -> None:
        segment = _segment(1, y=0.0)
        reference = [
            _frame("/reference", 100_000_000, (segment,)),
            _frame("/reference", 200_000_000, (segment,)),
        ]
        estimate = [
            _frame("/estimate", 90_000_000, (segment,)),
            _frame("/estimate", 101_000_000, (segment,)),
            _frame("/estimate", 260_000_000, (segment,)),
        ]

        result = synchronize_road_frames(
            reference,
            estimate,
            max_delta_ms=20.0,
        )

        self.assertEqual(len(result.pairs), 1)
        self.assertEqual(result.pairs[0].delta_ns, 1_000_000)
        self.assertEqual(result.unmatched_reference, 1)
        self.assertEqual(result.unmatched_estimate, 2)

    def test_source_time_is_default_and_both_time_deltas_are_audited(self) -> None:
        reference_segment = _segment(1, y=0.0, is_ego=True)
        estimate_segment = _segment(2, y=0.2, is_ego=True)
        reference = RoadFrame(
            topic="/reference",
            schema_name="Adp.Perception.Road",
            log_time_ns=100_000_000,
            publish_time_ns=100_000_000,
            sequence=0,
            source_time_ns=80_000_000,
            segments=(reference_segment,),
        )
        estimate = RoadFrame(
            topic="/estimate",
            schema_name="Adp.Perception.Road",
            log_time_ns=100_000_000,
            publish_time_ns=100_000_000,
            sequence=0,
            source_time_ns=104_000_000,
            segments=(estimate_segment,),
        )

        dataset = build_residual_dataset(
            [reference],
            [estimate],
            recording_id="source-time-test",
            max_delta_ms=30.0,
            max_samples=None,
        )

        self.assertEqual(dataset.report.time_basis, "source")
        self.assertEqual(dataset.records[0].synchronization_delta_ms, 24.0)
        self.assertEqual(dataset.records[0].source_time_delta_ms, 24.0)
        self.assertEqual(dataset.records[0].log_time_delta_ms, 0.0)
        self.assertEqual(dataset.pair_audit_records[0].source_time_delta_ms, 24.0)

    def test_candidate_and_horizon_audits_keep_rejected_pairs(self) -> None:
        reference_frames = [
            _frame(
                "/reference",
                index * 100_000_000,
                (
                    _segment(10, y=0.0, is_ego=True),
                    _segment(11, y=3.5, is_ego=False),
                ),
            )
            for index in range(2)
        ]
        estimate_frames = [
            _frame(
                "/estimate",
                0,
                (
                    _segment(20, y=0.2, x_stop=30.0, is_ego=True),
                    _segment(21, y=3.7, is_ego=False),
                ),
            ),
            _frame(
                "/estimate",
                100_000_000,
                (
                    _segment(20, y=0.2, is_ego=True),
                    _segment(21, y=3.7, is_ego=False),
                ),
            ),
        ]

        dataset = build_residual_dataset(
            reference_frames,
            estimate_frames,
            recording_id="audit-test",
            max_samples=None,
            n_association_examples=4,
        )

        self.assertEqual(dataset.residuals.shape, (1, 11))
        self.assertEqual(len(dataset.pair_audit_records), 2)
        self.assertEqual(len(dataset.candidate_records), 8)
        self.assertEqual(
            dataset.pair_audit_records[0].rejection_reason,
            "insufficient_estimate_coverage",
        )
        self.assertEqual(dataset.pair_audit_records[1].accepted, True)
        self.assertEqual(
            dataset.horizon_coverage_counts(),
            {20.0: 2, 30.0: 2, 40.0: 1, 50.0: 1},
        )
        selected_estimates = [
            record
            for record in dataset.candidate_records
            if record.role == "estimate" and record.selected
        ]
        self.assertEqual(
            [record.segment_id for record in selected_estimates],
            [20, 20],
        )

        diagnostics, _ = plot_mcap_dataset_diagnostics(dataset)
        association, _ = plot_lane_association_audit(dataset)
        plt.close(diagnostics)
        plt.close(association)

    def test_failed_explicit_ego_is_not_replaced_by_adjacent_segment(self) -> None:
        adjacent = RoadSegment(
            segment_id=11,
            x=np.linspace(-5.0, 60.0, 66),
            y=np.full(66, 3.5),
            arc_length=np.linspace(0.0, 65.0, 66),
            is_ego=False,
            source_index=1,
        )
        estimate = RoadFrame(
            topic="/estimate",
            schema_name="Adp.Perception.Road",
            log_time_ns=0,
            publish_time_ns=0,
            sequence=0,
            source_time_ns=1_000,
            segments=(adjacent,),
            segment_extractions=(
                SegmentExtraction(
                    segment_index=0,
                    segment_id=10,
                    is_ego=True,
                    quality=None,
                    reconstruction_succeeded=False,
                    geometry_source=None,
                    failure_reason="left lane boundary has no usable geometry",
                ),
                SegmentExtraction(
                    segment_index=1,
                    segment_id=11,
                    is_ego=False,
                    quality=None,
                    reconstruction_succeeded=True,
                    geometry_source="drive_path",
                ),
            ),
        )
        reference = _frame(
            "/reference",
            0,
            (_segment(1, y=0.0, is_ego=True),),
        )

        dataset = build_residual_dataset(
            [reference],
            [estimate],
            recording_id="failed-ego",
            max_samples=None,
        )

        self.assertEqual(dataset.residuals.shape, (0, 11))
        self.assertEqual(
            dataset.pair_audit_records[0].rejection_reason,
            "ego_segment_unavailable",
        )
        self.assertIsNone(dataset.pair_audit_records[0].estimate_segment_id)
        estimate_candidates = [
            item for item in dataset.candidate_records if item.role == "estimate"
        ]
        self.assertEqual(len(estimate_candidates), 2)
        self.assertFalse(estimate_candidates[0].reconstruction_succeeded)
        self.assertTrue(estimate_candidates[0].is_ego)
        self.assertTrue(estimate_candidates[1].reconstruction_succeeded)
        self.assertFalse(estimate_candidates[1].is_ego)
        self.assertFalse(any(item.selected for item in estimate_candidates))

    def test_strict_estimate_metadata_can_only_be_overridden_for_audit(self) -> None:
        reference = _frame(
            "/reference",
            0,
            (_segment(1, y=0.0, is_ego=True),),
        )
        estimate = _frame(
            "/estimate",
            0,
            (_segment(2, y=0.2),),
        )

        strict = build_residual_dataset(
            [reference],
            [estimate],
            recording_id="strict",
            max_samples=None,
        )
        diagnostic_override = build_residual_dataset(
            [reference],
            [estimate],
            recording_id="override",
            max_samples=None,
            require_estimate_ego_metadata=False,
        )

        self.assertEqual(
            strict.pair_audit_records[0].rejection_reason,
            "ego_metadata_missing",
        )
        self.assertEqual(diagnostic_override.residuals.shape, (1, 11))
        self.assertEqual(
            diagnostic_override.records[0].estimate_selection,
            "nearest_origin_fallback",
        )

    def test_horizon_coverage_requires_path_to_start_at_or_before_zero(self) -> None:
        reference = _frame(
            "/reference",
            0,
            (_segment(1, y=0.0, is_ego=True),),
        )
        estimate = _frame(
            "/estimate",
            0,
            (
                _segment(
                    2,
                    y=0.2,
                    x_start=5.0,
                    x_stop=60.0,
                    is_ego=True,
                ),
            ),
        )

        dataset = build_residual_dataset(
            [reference],
            [estimate],
            recording_id="missing-origin",
            max_samples=None,
        )

        audit = dataset.pair_audit_records[0]
        self.assertGreater(audit.common_station_start_m, 0.0)
        self.assertGreaterEqual(audit.common_station_end_m, 50.0)
        self.assertEqual(
            dataset.horizon_coverage_counts(),
            {20.0: 0, 30.0: 0, 40.0: 0, 50.0: 0},
        )
        self.assertEqual(
            audit.rejection_reason,
            "insufficient_estimate_coverage",
        )

    def test_zero_accepted_pairs_still_save_the_association_audit(self) -> None:
        dataset = build_residual_dataset(
            [_frame("/reference", 0, (_segment(1, y=0.0, is_ego=True),))],
            [
                _frame(
                    "/estimate",
                    0,
                    (
                        _segment(
                            2,
                            y=0.2,
                            x_stop=20.0,
                            is_ego=True,
                        ),
                    ),
                )
            ],
            recording_id="all-rejected",
            max_samples=None,
        )

        self.assertEqual(dataset.residuals.shape, (0, 11))
        self.assertEqual(len(dataset.pair_audit_records), 1)
        self.assertEqual(len(dataset.association_examples), 1)

        with tempfile.TemporaryDirectory() as directory:
            written = save_residual_dataset(dataset, directory)
            summary = json.loads(Path(written["summary"]).read_text("utf-8"))
            self.assertIsNone(summary["mean_residual_m"])
            self.assertTrue(Path(written["pair_audit"]).is_file())
            self.assertTrue(Path(written["candidate_segments"]).is_file())

    def test_dataset_recovers_offset_and_reports_short_path_rejection(self) -> None:
        reference_frames = []
        estimate_frames = []
        for index in range(3):
            time_ns = index * 100_000_000
            reference_frames.append(
                _frame(
                    "/reference",
                    time_ns,
                    (_segment(10, y=0.0, is_ego=True),),
                )
            )
            estimate_frames.append(
                _frame(
                    "/estimate",
                    time_ns + 5_000_000,
                    (_segment(20, y=0.2, is_ego=True),),
                )
            )

        reference_frames.append(
            _frame(
                "/reference",
                400_000_000,
                (_segment(10, y=0.0, is_ego=True),),
            )
        )
        estimate_frames.append(
            _frame(
                "/estimate",
                405_000_000,
                (
                    _segment(
                        20,
                        y=0.2,
                        x_start=-2.0,
                        x_stop=20.0,
                        is_ego=True,
                    ),
                ),
            )
        )

        dataset = build_residual_dataset(
            reference_frames,
            estimate_frames,
            recording_id="synthetic-recording",
            stations=np.arange(0.0, 50.1, 5.0),
            reference_topic="/reference",
            estimate_topic="/estimate",
            max_delta_ms=10.0,
            max_samples=None,
        )

        self.assertEqual(dataset.residuals.shape, (3, 11))
        np.testing.assert_allclose(dataset.residuals, 0.2, atol=1e-12)
        self.assertEqual(
            dataset.report.rejection_dict,
            {"insufficient_estimate_coverage": 1},
        )
        self.assertEqual(dataset.report.accepted_pairs, 3)
        self.assertEqual(dataset.records[0].synchronization_delta_ms, 5.0)

        with tempfile.TemporaryDirectory() as directory:
            written = save_residual_dataset(dataset, directory)
            self.assertTrue(all(path.is_file() for path in written.values()))
            summary = json.loads(Path(written["summary"]).read_text(encoding="utf-8"))
            self.assertIn("surrogate reference", summary["interpretation"])
            self.assertEqual(summary["matrix_shape"], [3, 11])

    def test_mcap_wrapper_requires_explicit_same_frame_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "same-frame"):
            build_residual_dataset_from_mcap(
                "does-not-need-to-exist.mcap",
                assume_same_frame=False,
            )


if __name__ == "__main__":
    unittest.main()
