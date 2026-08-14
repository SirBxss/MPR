import json
import math
import tempfile
import unittest
from pathlib import Path

from lane_residuals.batch_pairing_audit import (
    CANONICAL_STATIONS_M,
    RecordingAuditData,
    aggregate_fixed_cohorts,
    aggregate_rlmb_chains,
    detect_drive_overlaps,
    fixed_horizon_vectors,
    temporal_diagnostic_rows,
    write_strict_json,
)


def _recording(
    recording_id: str,
    drive_id: str,
    coverages_and_values,
    *,
    source_start_ns: int = 0,
) -> RecordingAuditData:
    pair_rows = []
    station_rows = []
    for pair_index, (coverage_m, value) in enumerate(coverages_and_values):
        pair_rows.append(
            {
                "pair_index": str(pair_index),
                "estimate_message_index": str(pair_index),
                "map_message_index": str(pair_index),
                "estimate_source_time_ns_private": str(
                    source_start_ns + pair_index * 100_000_000
                ),
                "diagnostic_primary_lateral_rms_m": (
                    str(abs(value)) if coverage_m >= 60.0 else ""
                ),
                "diagnostic_lateral_rms_m": (
                    str(abs(value)) if coverage_m >= 100.0 else ""
                ),
            }
        )
        for station in CANONICAL_STATIONS_M:
            if station <= coverage_m + 1e-9:
                station_rows.append(
                    {
                        "pair_index": str(pair_index),
                        "station_m": str(station),
                        "diagnostic_lateral_m": str(value),
                    }
                )
    message_count = len(pair_rows)
    inventory_rows = [
        {
            "topic_role": "estimate",
            "source_time_ns_private": str(
                source_start_ns + index * 100_000_000
            ),
        }
        for index in range(message_count)
    ]
    chain_rows = [
        {
            "segment_count": "1",
            "termination_reason": "required_forward_coverage_reached",
            "actual_forward_coverage_m": "110",
            "junction_gaps_m": "",
            "junction_heading_deltas_rad": "",
            "reciprocal_predecessor_links": "",
        }
        for _ in range(message_count)
    ]
    return RecordingAuditData(
        recording_id=recording_id,
        drive_id=drive_id,
        mcap_filename=f"{recording_id}.mcap",
        status="succeeded",
        output_directory=f"recordings/{recording_id}",
        summary={
            "estimate_messages": message_count,
            "map_messages": message_count,
            "complete_stream_mutual_nearest_pair_count": message_count,
            "unmatched_estimate_message_count": 0,
            "unmatched_map_message_count": 0,
        },
        pair_rows=tuple(pair_rows),
        station_rows=tuple(station_rows),
        chain_rows=tuple(chain_rows),
        inventory_rows=tuple(inventory_rows),
    )


class BatchPairingAggregationTests(unittest.TestCase):
    def test_fixed_cohorts_never_shrink_with_station(self) -> None:
        recording = _recording(
            "recording_001",
            "drive_001",
            [(55.0, 1.0), (65.0, 2.0), (105.0, 3.0)],
        )

        vectors = fixed_horizon_vectors(recording)
        self.assertEqual(set(vectors[60]), {1, 2})
        self.assertEqual(set(vectors[100]), {2})

        station_rows, _, _ = aggregate_fixed_cohorts([recording])
        overall_60 = [
            row
            for row in station_rows
            if row["scope_type"] == "overall" and row["horizon_m"] == 60
        ]
        overall_100 = [
            row
            for row in station_rows
            if row["scope_type"] == "overall" and row["horizon_m"] == 100
        ]
        self.assertEqual({row["cohort_pair_count"] for row in overall_60}, {2})
        self.assertEqual({row["cohort_pair_count"] for row in overall_100}, {1})
        self.assertEqual(len(overall_60), 13)
        self.assertEqual(len(overall_100), 21)

    def test_h100_station_zero_is_recomputed_from_h100_cohort(self) -> None:
        recording = _recording(
            "recording_001",
            "drive_001",
            [(65.0, 10.0), (105.0, 0.0)],
        )
        station_rows, _, _ = aggregate_fixed_cohorts([recording])
        zero_60 = next(
            row
            for row in station_rows
            if row["scope_type"] == "overall"
            and row["horizon_m"] == 60
            and row["station_m"] == 0.0
        )
        zero_100 = next(
            row
            for row in station_rows
            if row["scope_type"] == "overall"
            and row["horizon_m"] == 100
            and row["station_m"] == 0.0
        )
        self.assertEqual(zero_60["lateral_mean_m"], 5.0)
        self.assertEqual(zero_100["lateral_mean_m"], 0.0)

    def test_overall_rms_is_pair_weighted_not_average_of_recording_rms(self) -> None:
        first = _recording("recording_001", "drive_001", [(105.0, 0.0)])
        second = _recording(
            "recording_002",
            "drive_002",
            [(105.0, 3.0), (105.0, 3.0)],
            source_start_ns=1_000_000_000,
        )
        _, horizon_rows, _ = aggregate_fixed_cohorts([first, second])
        overall = next(
            row
            for row in horizon_rows
            if row["scope_type"] == "overall" and row["horizon_m"] == 100
        )
        self.assertAlmostEqual(overall["pooled_lateral_rms_m"], math.sqrt(6.0))
        self.assertNotAlmostEqual(overall["pooled_lateral_rms_m"], 1.5)

    def test_no_link_chain_is_not_counted_as_nonreciprocal(self) -> None:
        recording = _recording(
            "recording_001", "drive_001", [(105.0, 0.1)]
        )
        summary = aggregate_rlmb_chains([recording])["overall"]["overall"]
        self.assertEqual(summary["junction_link_count"], 0)
        self.assertEqual(summary["nonreciprocal_link_count"], 0)
        self.assertEqual(summary["no_link_chain_count_not_applicable"], 1)

    def test_recording_time_tail_membership_is_independent_of_lateral_values(self) -> None:
        first = _recording(
            "recording_001", "drive_001", [(105.0, 0.1), (105.0, 0.2)]
        )
        second = _recording(
            "recording_001", "drive_001", [(105.0, 100.0), (105.0, -100.0)]
        )
        rows_a = temporal_diagnostic_rows(
            [first],
            recording_tail_window_s=0.05,
            primary_tail_threshold_m=None,
            full_tail_threshold_m=None,
        )
        rows_b = temporal_diagnostic_rows(
            [second],
            recording_tail_window_s=0.05,
            primary_tail_threshold_m=None,
            full_tail_threshold_m=None,
        )
        self.assertEqual(
            [row["in_final_recording_time_window"] for row in rows_a],
            [row["in_final_recording_time_window"] for row in rows_b],
        )
        self.assertTrue(all(row["h60_outcome_tail_flag"] is None for row in rows_a))

    def test_same_drive_boundary_overlap_is_reported(self) -> None:
        first = _recording(
            "recording_001", "drive_001", [(105.0, 0.0), (105.0, 0.0)]
        )
        second = _recording(
            "recording_002",
            "drive_001",
            [(105.0, 0.0), (105.0, 0.0)],
            source_start_ns=100_000_000,
        )
        overlaps = detect_drive_overlaps([first, second])
        self.assertEqual(len(overlaps), 1)
        self.assertTrue(overlaps[0]["boundary_timestamp_shared"])

    def test_strict_json_rejects_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            with self.assertRaises(ValueError):
                write_strict_json(path, {"invalid": float("nan")})


if __name__ == "__main__":
    unittest.main()
