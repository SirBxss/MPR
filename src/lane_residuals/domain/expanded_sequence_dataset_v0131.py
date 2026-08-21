"""v0.13.1 accepted-boundary odometry-context contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expanded_sequence_dataset import standardization_contract


VERSION = "0.13.1"
PURPOSE = "quality_gated_expanded_sensor_topology_sequential_dataset_with_boundary_odometry_context"
BASELINE_VERSION = "0.13.0"
BASELINE_PURPOSE = "quality_gated_expanded_sensor_topology_sequential_dataset"
BOUNDARY_CONTEXT_METHOD = "accepted_previous_mcap_odometry_50ms_displacement"


@dataclass(frozen=True)
class BoundaryContextEvidence:
    """Fail-closed evidence for one immediate cross-MCAP endpoint."""

    same_physical_drive: bool
    inventory_boundary_accepted: bool
    topology_source_continuous: bool
    both_endpoints_sensor_h100: bool
    odometry_topic_present_both: bool
    odometry_schema_compatible: bool
    odometry_timestamps_strict_across_boundary: bool
    recording_local_failure_is_missing_history: bool
    interpolation_succeeded: bool
    interpolation_within_tolerance: bool
    extrapolation_required: bool
    both_mcaps_contributed: bool


def boundary_context_rejection_reasons(
    evidence: BoundaryContextEvidence,
) -> tuple[str, ...]:
    """Return every stable rejection code; empty means context is admissible."""

    checks = (
        (evidence.same_physical_drive, "physical_drive_mismatch"),
        (evidence.inventory_boundary_accepted, "inventory_boundary_not_accepted"),
        (evidence.topology_source_continuous, "topology_source_discontinuity"),
        (evidence.both_endpoints_sensor_h100, "endpoint_not_sensor_h100"),
        (evidence.odometry_topic_present_both, "odometry_topic_missing"),
        (evidence.odometry_schema_compatible, "odometry_schema_incompatible"),
        (
            evidence.odometry_timestamps_strict_across_boundary,
            "odometry_timestamps_not_strict_across_boundary",
        ),
        (
            evidence.recording_local_failure_is_missing_history,
            "recording_local_feature_not_missing_history",
        ),
        (evidence.interpolation_succeeded, "boundary_odometry_interpolation_failed"),
        (
            evidence.interpolation_within_tolerance,
            "boundary_odometry_interpolation_gap_too_wide",
        ),
        (not evidence.extrapolation_required, "boundary_odometry_extrapolation_required"),
        (evidence.both_mcaps_contributed, "boundary_context_did_not_use_both_mcaps"),
    )
    return tuple(code for passed, code in checks if not passed)


def boundary_context_eligible(evidence: BoundaryContextEvidence) -> bool:
    return not boundary_context_rejection_reasons(evidence)


def standardization_contract_v0131() -> dict[str, Any]:
    """Retain the unfitted policy while identifying the v0.13.1 dataset."""

    contract = standardization_contract()
    contract["schema_version"] = VERSION
    contract["feature_definitions_inherited_unchanged_from"] = BASELINE_VERSION
    return contract


__all__ = [
    "BASELINE_PURPOSE",
    "BASELINE_VERSION",
    "BOUNDARY_CONTEXT_METHOD",
    "BoundaryContextEvidence",
    "PURPOSE",
    "VERSION",
    "boundary_context_eligible",
    "boundary_context_rejection_reasons",
    "standardization_contract_v0131",
]
