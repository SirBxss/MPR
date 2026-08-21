"""v0.13.0 quality-gated expanded sensor-topology sequence contract."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .residual_dataset import CANONICAL_MODEL_STATIONS_M
from .sequence_dataset import BMW_CONDITION_FEATURE_NAMES


VERSION = "0.13.0"
PURPOSE = "quality_gated_expanded_sensor_topology_sequential_dataset"
EXPECTED_TOPOLOGY_SOURCE = "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY"
MAXIMUM_ANCHOR_DISTANCE_M = 1.0
DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS = 200.0

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ProfileEligibilityEvidence:
    """All non-model evidence used to admit or exclude one aligned profile."""

    topology_source_name: str
    h100_aligned_eligible: bool
    station_grid_m: Sequence[float]
    residuals_m: ArrayLike
    anchor_distance_m: float | None
    estimator_state: str
    estimate_geometry_state: str
    estimate_geometry_failure_code: str | None
    map_geometry_state: str
    map_geometry_failure_code: str | None
    feature_state: str
    features: ArrayLike | None


@dataclass(frozen=True)
class ProfileEligibility:
    eligible: bool
    exclusion_reasons: tuple[str, ...]


def evaluate_profile_eligibility(
    evidence: ProfileEligibilityEvidence,
) -> ProfileEligibility:
    """Apply the frozen pre-model v0.13.0 geometric/profile rules."""

    reasons: list[str] = []
    if evidence.topology_source_name != EXPECTED_TOPOLOGY_SOURCE:
        reasons.append("topology_source_not_sensor_topology")
    if evidence.h100_aligned_eligible is not True:
        reasons.append("h100_alignment_ineligible")
    try:
        stations = np.asarray(evidence.station_grid_m, dtype=np.float64)
        residuals = np.asarray(evidence.residuals_m, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        stations = np.asarray([], dtype=np.float64)
        residuals = np.asarray([], dtype=np.float64)
    if stations.shape != (21,) or not np.array_equal(
        stations, np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64)
    ):
        reasons.append("residual_station_contract_invalid")
    if residuals.shape != (21,) or not np.all(np.isfinite(residuals)):
        reasons.append("residual_values_invalid")
    anchor = evidence.anchor_distance_m
    if anchor is None or not math.isfinite(float(anchor)):
        reasons.append("anchor_distance_invalid")
    elif float(anchor) > MAXIMUM_ANCHOR_DISTANCE_M:
        reasons.append("anchor_distance_exceeds_1m")
    if evidence.estimator_state != "available_no_error":
        reasons.append("estimator_invalid")
    if (
        evidence.estimate_geometry_state != "geometry_ready"
        or evidence.estimate_geometry_failure_code not in {None, ""}
    ):
        reasons.append("estimate_geometry_invalid")
    if (
        evidence.map_geometry_state != "geometry_ready"
        or evidence.map_geometry_failure_code not in {None, ""}
    ):
        reasons.append("map_geometry_invalid")
    if evidence.feature_state != "ready" or evidence.features is None:
        reasons.append("feature_not_ready")
    else:
        try:
            features = np.asarray(evidence.features, dtype=np.float64)
        except (TypeError, ValueError, OverflowError):
            features = np.asarray([], dtype=np.float64)
        if features.shape != (6,) or not np.all(np.isfinite(features)):
            reasons.append("feature_values_invalid")
    unique = tuple(dict.fromkeys(reasons))
    return ProfileEligibility(eligible=not unique, exclusion_reasons=unique)


@dataclass(frozen=True)
class ExpandedProfile:
    """One eligible physical-unit H100 profile with original provenance."""

    recording_id: str
    drive_id: str
    mcap_basename_private: str
    pair_index: int
    estimate_message_index: int
    estimate_source_time_ns_private: int
    topology_source_name: str
    anchor_distance_m: float
    anchor_heading_delta_rad: float
    residuals_m: ArrayLike = field(repr=False)
    conditions: ArrayLike = field(repr=False)

    def __post_init__(self) -> None:
        if not self.recording_id or not self.drive_id or not self.mcap_basename_private:
            raise ValueError("profile provenance identifiers must be nonempty")
        if self.topology_source_name != EXPECTED_TOPOLOGY_SOURCE:
            raise ValueError("expanded profile must use SENSOR_TOPOLOGY")
        for value, name in (
            (self.pair_index, "pair_index"),
            (self.estimate_message_index, "estimate_message_index"),
            (self.estimate_source_time_ns_private, "estimate timestamp"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if (
            not math.isfinite(self.anchor_distance_m)
            or self.anchor_distance_m > MAXIMUM_ANCHOR_DISTANCE_M
            or self.anchor_distance_m < 0.0
        ):
            raise ValueError("profile anchor distance violates v0.13.0")
        if not math.isfinite(self.anchor_heading_delta_rad):
            raise ValueError("profile anchor heading must be finite")
        residuals = np.asarray(self.residuals_m, dtype=np.float64)
        conditions = np.asarray(self.conditions, dtype=np.float64)
        if residuals.shape != (21,) or not np.all(np.isfinite(residuals)):
            raise ValueError("profile residual tensor must be finite [21]")
        if conditions.shape != (6,) or not np.all(np.isfinite(conditions)):
            raise ValueError("profile condition tensor must be finite [6]")
        residuals.setflags(write=False)
        conditions.setflags(write=False)
        object.__setattr__(self, "residuals_m", residuals)
        object.__setattr__(self, "conditions", conditions)

    @property
    def key(self) -> tuple[str, int]:
        return self.recording_id, self.pair_index


@dataclass(frozen=True)
class SequenceBreakEvidence:
    """Evidence evaluated between two observations in canonical session order."""

    same_physical_drive: bool
    topology_source_changed: bool
    previous_eligible: bool
    current_eligible: bool
    current_anchor_gate_failed: bool
    timestamp_gap_ns: int | None
    crosses_mcap_boundary: bool
    mcap_boundary_accepted: bool | None


def sequence_break_reasons(
    evidence: SequenceBreakEvidence,
    *,
    maximum_contiguous_gap_ms: float = DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
) -> tuple[str, ...]:
    """Return every applicable boundary reason without model-dependent logic."""

    if not math.isfinite(maximum_contiguous_gap_ms) or maximum_contiguous_gap_ms <= 0:
        raise ValueError("maximum contiguous gap must be finite and positive")
    reasons: list[str] = []
    if not evidence.same_physical_drive:
        reasons.append("physical_drive_change")
    if evidence.topology_source_changed:
        reasons.append("topology_source_change")
    if not evidence.previous_eligible or not evidence.current_eligible:
        reasons.append("ineligible_observation")
    if evidence.current_anchor_gate_failed:
        reasons.append("anchor_distance_gate_failure")
    gap = evidence.timestamp_gap_ns
    if gap is None or gap <= 0:
        reasons.append("timestamp_non_monotonic")
    elif gap > maximum_contiguous_gap_ms * 1e6:
        reasons.append("temporal_gap_exceeds_tolerance")
    if evidence.crosses_mcap_boundary and evidence.mcap_boundary_accepted is not True:
        reasons.append("mcap_boundary_not_accepted")
    return tuple(reasons)


def cross_mcap_stitchable(
    evidence: SequenceBreakEvidence,
    *,
    maximum_contiguous_gap_ms: float = DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
) -> bool:
    """Admit only explicitly accepted, eligible, time-contiguous MCAP edges."""

    return (
        evidence.crosses_mcap_boundary
        and evidence.mcap_boundary_accepted is True
        and not sequence_break_reasons(
            evidence,
            maximum_contiguous_gap_ms=maximum_contiguous_gap_ms,
        )
    )


@dataclass(frozen=True)
class ExpandedSequence:
    """One sensor-topology run; frames retain original recording identity."""

    sequence_id: str
    drive_id: str
    start_reasons: tuple[str, ...]
    frames: tuple[ExpandedProfile, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.sequence_id or not self.drive_id or not self.frames:
            raise ValueError("sequence identifiers and frames must be nonempty")
        if any(frame.drive_id != self.drive_id for frame in self.frames):
            raise ValueError("sequence cannot cross physical drives")
        if len({frame.key for frame in self.frames}) != len(self.frames):
            raise ValueError("sequence profile keys must be unique")
        timestamps = [frame.estimate_source_time_ns_private for frame in self.frames]
        if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            raise ValueError("sequence timestamps must be strictly increasing")

    @property
    def length(self) -> int:
        return len(self.frames)

    @property
    def crosses_mcap(self) -> bool:
        return len({frame.mcap_basename_private for frame in self.frames}) > 1


def standardization_contract() -> dict[str, Any]:
    """Unfitted metadata; split assignments remain deliberately undefined."""

    return {
        "schema_version": VERSION,
        "policy": "fit_on_training_drives_only_after_split_assignment",
        "feature_names": list(BMW_CONDITION_FEATURE_NAMES),
        "stations_m": list(CANONICAL_MODEL_STATIONS_M),
        "train_drive_ids": None,
        "condition_mean": None,
        "condition_scale": None,
        "residual_mean_m": None,
        "residual_scale_m": None,
        "fitted": False,
        "split_assignments_selected": False,
    }


__all__ = [
    "DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS",
    "EXPECTED_TOPOLOGY_SOURCE",
    "ExpandedProfile",
    "ExpandedSequence",
    "MAXIMUM_ANCHOR_DISTANCE_M",
    "PURPOSE",
    "ProfileEligibility",
    "ProfileEligibilityEvidence",
    "SequenceBreakEvidence",
    "VERSION",
    "cross_mcap_stitchable",
    "evaluate_profile_eligibility",
    "sequence_break_reasons",
    "standardization_contract",
]
