import unittest

import numpy as np

from lane_residuals.domain.expanded_sequence_dataset import (
    EXPECTED_TOPOLOGY_SOURCE,
    ExpandedProfile,
    ExpandedSequence,
    ProfileEligibilityEvidence,
    SequenceBreakEvidence,
    cross_mcap_stitchable,
    evaluate_profile_eligibility,
    sequence_break_reasons,
    standardization_contract,
)
from lane_residuals.domain.residual_dataset import CANONICAL_MODEL_STATIONS_M


def _evidence(**overrides):
    values = {
        "topology_source_name": EXPECTED_TOPOLOGY_SOURCE,
        "h100_aligned_eligible": True,
        "station_grid_m": CANONICAL_MODEL_STATIONS_M,
        "residuals_m": np.linspace(-0.2, 0.2, 21),
        "anchor_distance_m": 1.0,
        "anchor_heading_delta_rad": 3.0,
        "source_delta_ms": -20.0,
        "estimator_state": "available_no_error",
        "estimate_geometry_state": "geometry_ready",
        "estimate_geometry_failure_code": None,
        "map_geometry_state": "geometry_ready",
        "map_geometry_failure_code": None,
        "feature_state": "ready",
        "features": np.arange(6, dtype=float),
    }
    values.update(overrides)
    return ProfileEligibilityEvidence(**values)


def _profile(recording="recording_001", basename="a.mcap", timestamp=100):
    return ExpandedProfile(
        recording_id=recording,
        drive_id="drive_001",
        mcap_basename_private=basename,
        pair_index=0,
        estimate_message_index=0,
        estimate_source_time_ns_private=timestamp,
        topology_source_name=EXPECTED_TOPOLOGY_SOURCE,
        anchor_distance_m=0.2,
        anchor_heading_delta_rad=0.01,
        residuals_m=np.zeros(21),
        conditions=np.ones(6),
    )


class ExpandedProfileEligibilityTests(unittest.TestCase):
    def test_exact_gate_accepts_one_meter_and_complete_profile(self):
        result = evaluate_profile_eligibility(_evidence())
        self.assertTrue(result.eligible)
        self.assertEqual(result.exclusion_reasons, ())

    def test_catastrophic_anchor_and_lane_map_are_excluded_without_heading_gate(self):
        result = evaluate_profile_eligibility(
            _evidence(
                topology_source_name="ROAD_TOPOLOGY_SOURCE_LANE_MAP",
                anchor_distance_m=1.000001,
            )
        )
        self.assertFalse(result.eligible)
        self.assertIn("topology_source_not_sensor_topology", result.exclusion_reasons)
        self.assertIn("anchor_distance_exceeds_1m", result.exclusion_reasons)
        self.assertNotIn("anchor_heading", ";".join(result.exclusion_reasons))

    def test_every_geometry_feature_and_finite_contract_is_fail_closed(self):
        result = evaluate_profile_eligibility(
            _evidence(
                h100_aligned_eligible=False,
                residuals_m=np.full(21, np.nan),
                estimator_state="estimator_reported_error",
                estimate_geometry_state="geometry_not_ready",
                map_geometry_state="geometry_not_ready",
                feature_state="not_ready",
                features=None,
            )
        )
        self.assertEqual(
            set(result.exclusion_reasons),
            {
                "h100_alignment_ineligible",
                "residual_values_invalid",
                "estimator_invalid",
                "estimate_geometry_invalid",
                "map_geometry_invalid",
                "feature_not_ready",
            },
        )

    def test_cross_mcap_stitch_requires_all_endpoint_and_continuity_evidence(self):
        accepted = SequenceBreakEvidence(
            same_physical_drive=True,
            topology_source_changed=False,
            previous_eligible=True,
            current_eligible=True,
            current_anchor_gate_failed=False,
            timestamp_gap_ns=80_000_000,
            crosses_mcap_boundary=True,
            mcap_boundary_accepted=True,
        )
        self.assertTrue(cross_mcap_stitchable(accepted))
        rejected = SequenceBreakEvidence(**{**accepted.__dict__, "current_eligible": False})
        self.assertFalse(cross_mcap_stitchable(rejected))
        self.assertIn("ineligible_observation", sequence_break_reasons(rejected))

    def test_expanded_sequence_preserves_original_recordings_across_mcaps(self):
        sequence = ExpandedSequence(
            sequence_id="drive_001_sequence_001",
            drive_id="drive_001",
            start_reasons=("physical_drive_start",),
            frames=(
                _profile(timestamp=100),
                _profile("recording_002", "b.mcap", 180),
            ),
        )
        self.assertTrue(sequence.crosses_mcap)
        self.assertEqual([frame.recording_id for frame in sequence.frames], ["recording_001", "recording_002"])

    def test_standardization_is_unfitted_until_future_split_assignment(self):
        contract = standardization_contract()
        self.assertFalse(contract["fitted"])
        self.assertFalse(contract["split_assignments_selected"])
        self.assertIsNone(contract["train_drive_ids"])


if __name__ == "__main__":
    unittest.main()
