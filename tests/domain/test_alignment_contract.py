import unittest

from lane_residuals.domain.alignment_contract import (
    validate_native_projection_contract,
)


class AlignmentContractTests(unittest.TestCase):
    def test_historical_v050_contract_remains_accepted(self) -> None:
        self.assertEqual(
            validate_native_projection_contract(
                {
                    "version": "0.5.0",
                    "purpose": "ten_mcap_projection_based_reference_alignment_validation",
                },
                name="historical",
            ),
            ("0.5.0", "ten_mcap_projection_based_reference_alignment_validation"),
        )

    def test_explicit_native_v052_contract_is_accepted(self) -> None:
        self.assertEqual(
            validate_native_projection_contract(
                {
                    "version": "0.5.2",
                    "purpose": "exact_manifest_projection_based_reference_alignment_validation",
                    "alignment_semantics": "v0.5.0_native_spatial_projection",
                    "explicit_ego_pose_motion_compensation_applied": False,
                    "source_delta_used_numerically_for_alignment": False,
                    "accepted_for_modeling": True,
                },
                name="current",
            )[0],
            "0.5.2",
        )

    def test_motion_compensated_v051_contract_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an accepted native"):
            validate_native_projection_contract(
                {
                    "version": "0.5.1",
                    "purpose": "ten_mcap_odometry_motion_compensated_alignment_validation",
                    "explicit_ego_pose_motion_compensation_applied": True,
                },
                name="motion",
            )


if __name__ == "__main__":
    unittest.main()
