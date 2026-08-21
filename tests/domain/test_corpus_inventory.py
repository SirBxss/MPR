import unittest
from dataclasses import replace

from lane_residuals.domain.corpus_inventory import (
    McapInventoryRecord,
    TopicCompatibility,
    assess_continuity_edge,
    chronological_records,
    exact_drive_map_coverage,
)


def _topics(schema: str = "EstimateSchema") -> tuple[TopicCompatibility, ...]:
    specifications = (
        ("estimate", "/estimate", schema),
        ("map", "/map", "MapSchema"),
        ("odometry", "/odometry", "OdomSchema"),
    )
    return tuple(
        TopicCompatibility(
            role=role,
            topic=topic,
            expected_schema_name=expected,
            present=True,
            message_count=10,
            schema_names=(expected,),
            schema_encodings=("protobuf",),
            message_encodings=("protobuf",),
        )
        for role, topic, expected in specifications
    )


def _record(
    recording_id: str,
    identifier: int,
    internal_start: int,
    internal_end: int,
    source_start: int,
    source_end: int,
    *,
    drive_id: str = "drive_001",
    topics: tuple[TopicCompatibility, ...] | None = None,
    monotonic: bool = True,
) -> McapInventoryRecord:
    basename = (
        f"2025-05-27_12-00-{identifier % 60:02d}_"
        f"2025-05-27_12-00-{(identifier + 1) % 60:02d}_MCAP_{identifier:06d}.mcap"
    )
    return McapInventoryRecord(
        path=f"/private/{basename}",
        basename=basename,
        relative_path=basename,
        recording_id=recording_id,
        drive_id=drive_id,
        file_size_bytes=100,
        sha256=recording_id * 8,
        readable=True,
        empty=False,
        internal_start_log_time_ns=internal_start,
        internal_end_log_time_ns=internal_end,
        first_estimate_source_time_ns=source_start,
        last_estimate_source_time_ns=source_end,
        estimate_source_timestamp_count=10,
        estimate_missing_source_timestamp_count=0,
        estimate_source_timestamps_strictly_increasing=monotonic,
        filename_start="2025-05-27T12:00:00",
        filename_end="2025-05-27T12:00:01",
        filename_duration_ms=1000.0,
        mcap_identifier=identifier,
        filename_internal_time_disagreement=False,
        topics=_topics() if topics is None else topics,
    )


class CorpusInventoryDomainTests(unittest.TestCase):
    def test_exact_drive_map_coverage(self) -> None:
        assignments, issues = exact_drive_map_coverage(
            ["a.mcap", "b.mcap"],
            [("a.mcap", "session-a"), ("b.mcap", "session-a")],
        )
        self.assertEqual(assignments, {"a.mcap": "session-a", "b.mcap": "session-a"})
        self.assertFalse(any(issues.values()))

    def test_duplicate_and_missing_basenames_are_explicit(self) -> None:
        assignments, issues = exact_drive_map_coverage(
            ["a.mcap", "a.mcap", "b.mcap"],
            [("a.mcap", "one"), ("a.mcap", "two"), ("extra.mcap", "three")],
        )
        self.assertEqual(assignments, {})
        self.assertEqual(issues["missing_basenames"], ("b.mcap",))
        self.assertEqual(issues["extra_basenames"], ("extra.mcap",))
        self.assertEqual(issues["duplicate_discovered_basenames"], ("a.mcap",))
        self.assertEqual(issues["duplicate_drive_map_basenames"], ("a.mcap",))

    def test_chronological_sort_uses_source_time_not_filename(self) -> None:
        later = replace(
            _record("recording_001", 1, 300, 400, 300, 400),
            filename_start="2025-05-27T12:00:00",
        )
        earlier = replace(
            _record("recording_002", 2, 100, 200, 100, 200),
            filename_start="2025-05-27T12:00:10",
        )
        ordered = chronological_records((later, earlier))
        self.assertEqual([item.recording_id for item in ordered], ["recording_002", "recording_001"])
        self.assertTrue(all(item.filename_order_disagrees_with_internal_order for item in ordered))

    def test_continuous_adjacent_mcaps_are_stitchable(self) -> None:
        left = _record("recording_001", 307, 0, 1_000_000_000, 0, 1_000_000_000)
        right = _record(
            "recording_002", 308, 1_010_000_000, 2_000_000_000, 1_080_000_000, 2_000_000_000
        )
        edge = assess_continuity_edge(left, right)
        self.assertTrue(edge.stitchable)
        self.assertEqual(edge.relevant_source_gap_ns, 80_000_000)

    def test_zero_internal_log_gap_is_a_valid_touching_boundary(self) -> None:
        left = _record("recording_001", 1, 0, 1_000, 0, 1_000)
        right = _record("recording_002", 2, 1_000, 2_000, 1_001, 2_000)
        edge = assess_continuity_edge(left, right)
        self.assertEqual(edge.internal_log_gap_ns, 0)
        self.assertTrue(edge.internal_log_times_compatible)
        self.assertFalse(edge.overlap_detected)
        self.assertTrue(edge.stitchable)

    def test_timestamp_gap_rejects_edge(self) -> None:
        left = _record("recording_001", 1, 0, 100, 0, 100)
        right = _record("recording_002", 2, 101, 400_000_000, 300_000_001, 400_000_000)
        edge = assess_continuity_edge(left, right)
        self.assertFalse(edge.stitchable)
        self.assertIn("relevant_source_time_gap_exceeds_200_ms", edge.rejection_codes)

    def test_true_negative_internal_log_gap_is_an_overlap(self) -> None:
        left = _record("recording_001", 1, 0, 200, 0, 200)
        right = _record("recording_002", 2, 150, 300, 150, 300)
        edge = assess_continuity_edge(left, right)
        self.assertEqual(edge.internal_log_gap_ns, -50)
        self.assertTrue(edge.overlap_detected)
        self.assertFalse(edge.stitchable)
        self.assertIn("internal_log_time_overlap", edge.rejection_codes)

    def test_timestamp_reset_inside_file_rejects_edge(self) -> None:
        left = _record("recording_001", 1, 0, 100, 0, 100)
        right = _record("recording_002", 2, 101, 300, 101, 300, monotonic=False)
        edge = assess_continuity_edge(left, right)
        self.assertTrue(edge.timestamp_reset_detected)
        self.assertFalse(edge.stitchable)
        self.assertIn("right_file_unusable", edge.rejection_codes)

    def test_recording_local_pair_index_reset_does_not_reject_edge(self) -> None:
        left = _record("recording_001", 1, 0, 100, 0, 100)
        right = _record("recording_002", 2, 101, 300, 101, 300)
        edge = assess_continuity_edge(left, right)
        self.assertTrue(edge.stitchable)
        self.assertEqual(
            edge.pair_index_boundary_state,
            "recording_local_reset_allowed_not_a_stitch_gate",
        )

    def test_schema_mismatch_rejects_edge(self) -> None:
        left = _record("recording_001", 1, 0, 100, 0, 100)
        mismatched = list(_topics())
        mismatched[0] = replace(mismatched[0], schema_names=("UnexpectedSchema",))
        right = _record("recording_002", 2, 101, 300, 101, 300, topics=tuple(mismatched))
        edge = assess_continuity_edge(left, right)
        self.assertFalse(edge.stitchable)
        self.assertIn("required_topic_or_schema_incompatible", edge.rejection_codes)

    def test_000307_to_000398_identifier_jump_is_flag_only(self) -> None:
        left = _record("recording_001", 307, 0, 100, 0, 100)
        right = _record("recording_002", 398, 101, 300, 101, 300)
        edge = assess_continuity_edge(left, right)
        self.assertTrue(edge.identifier_discontinuity)
        self.assertEqual(edge.identifier_delta, 91)
        self.assertTrue(edge.stitchable)


if __name__ == "__main__":
    unittest.main()
