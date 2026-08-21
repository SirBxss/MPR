import unittest

from lane_residuals.domain.expanded_sequence_dataset_v0131 import (
    BoundaryContextEvidence,
    boundary_context_eligible,
    boundary_context_rejection_reasons,
    standardization_contract_v0131,
)


def _evidence(**overrides):
    values = {
        "same_physical_drive": True,
        "inventory_boundary_accepted": True,
        "topology_source_continuous": True,
        "both_endpoints_sensor_h100": True,
        "odometry_topic_present_both": True,
        "odometry_schema_compatible": True,
        "odometry_timestamps_strict_across_boundary": True,
        "recording_local_failure_is_missing_history": True,
        "interpolation_succeeded": True,
        "interpolation_within_tolerance": True,
        "extrapolation_required": False,
        "both_mcaps_contributed": True,
    }
    values.update(overrides)
    return BoundaryContextEvidence(**values)


class BoundaryContextContractTests(unittest.TestCase):
    def test_complete_accepted_boundary_evidence_is_eligible(self):
        self.assertTrue(boundary_context_eligible(_evidence()))
        self.assertEqual(boundary_context_rejection_reasons(_evidence()), ())

    def test_schema_monotonicity_and_extrapolation_fail_closed(self):
        result = boundary_context_rejection_reasons(
            _evidence(
                odometry_schema_compatible=False,
                odometry_timestamps_strict_across_boundary=False,
                extrapolation_required=True,
            )
        )
        self.assertEqual(
            result,
            (
                "odometry_schema_incompatible",
                "odometry_timestamps_not_strict_across_boundary",
                "boundary_odometry_extrapolation_required",
            ),
        )

    def test_topology_discontinuity_and_rejected_boundary_are_never_crossed(self):
        reasons = boundary_context_rejection_reasons(
            _evidence(
                inventory_boundary_accepted=False,
                topology_source_continuous=False,
            )
        )
        self.assertIn("inventory_boundary_not_accepted", reasons)
        self.assertIn("topology_source_discontinuity", reasons)

    def test_v0131_standardization_remains_unfitted(self):
        contract = standardization_contract_v0131()
        self.assertEqual(contract["schema_version"], "0.13.1")
        self.assertEqual(
            contract["feature_definitions_inherited_unchanged_from"], "0.13.0"
        )
        self.assertFalse(contract["fitted"])
        self.assertFalse(contract["split_assignments_selected"])


if __name__ == "__main__":
    unittest.main()
