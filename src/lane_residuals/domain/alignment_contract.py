"""Accepted native projection-alignment metadata contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


HISTORICAL_ALIGNMENT_VERSION = "0.5.0"
HISTORICAL_ALIGNMENT_PURPOSE = (
    "ten_mcap_projection_based_reference_alignment_validation"
)
CURRENT_ALIGNMENT_VERSION = "0.5.2"
CURRENT_ALIGNMENT_PURPOSE = (
    "exact_manifest_projection_based_reference_alignment_validation"
)
CURRENT_ALIGNMENT_SEMANTICS = "v0.5.0_native_spatial_projection"
ACCEPTED_ALIGNMENT_CONTRACTS = {
    (HISTORICAL_ALIGNMENT_VERSION, HISTORICAL_ALIGNMENT_PURPOSE),
    (CURRENT_ALIGNMENT_VERSION, CURRENT_ALIGNMENT_PURPOSE),
}


def validate_native_projection_contract(
    payload: Mapping[str, Any],
    *,
    name: str,
    error_type: type[Exception] = ValueError,
) -> tuple[str, str]:
    """Accept historical v0.5.0 or explicit v0.5.2, never v0.5.1 motion."""

    version = payload.get("version")
    purpose = payload.get("purpose")
    if (version, purpose) not in ACCEPTED_ALIGNMENT_CONTRACTS:
        raise error_type(
            f"{name} is not an accepted native projection-alignment contract"
        )
    if version == CURRENT_ALIGNMENT_VERSION:
        expected = {
            "alignment_semantics": CURRENT_ALIGNMENT_SEMANTICS,
            "explicit_ego_pose_motion_compensation_applied": False,
            "source_delta_used_numerically_for_alignment": False,
            "accepted_for_modeling": True,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise error_type(f"{name} has invalid v0.5.2 field {key}")
    return str(version), str(purpose)


__all__ = [
    "ACCEPTED_ALIGNMENT_CONTRACTS",
    "CURRENT_ALIGNMENT_PURPOSE",
    "CURRENT_ALIGNMENT_SEMANTICS",
    "CURRENT_ALIGNMENT_VERSION",
    "HISTORICAL_ALIGNMENT_PURPOSE",
    "HISTORICAL_ALIGNMENT_VERSION",
    "validate_native_projection_contract",
]
