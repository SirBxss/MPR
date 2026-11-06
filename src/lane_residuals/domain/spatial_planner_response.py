"""Affine response of the reference planner to a single spatial profile."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .reference_planner import ReferencePlannerConfig, plan_reference_horizon


STATIONS_M = tuple(float(station) for station in range(0, 101, 5))


@dataclass(frozen=True)
class SpatialPlannerScenario:
    """A fixed local lateral state and motion for all profiles in one comparison."""

    speed_mps: float
    dt_s: float
    lateral_error_m: float = 0.0
    heading_error_rad: float = 0.0
    previous_curvature_correction_per_m: float = 0.0


@dataclass(frozen=True)
class SpatialPlannerResponse:
    """Response relative to the nominal zero disturbance plan."""

    distances_m: NDArray[np.float64]
    lateral_response: NDArray[np.float64]
    curvature_response: NDArray[np.float64]

    def evaluate(self, profiles_m: NDArray[np.float64]) -> dict[str, NDArray[np.float64]]:
        """Apply the same spatial map to an array ending in 21 station offsets."""
        profiles = np.asarray(profiles_m, dtype=np.float64)
        if profiles.ndim < 1 or profiles.shape[-1] != len(STATIONS_M) or not profiles.size:
            raise ValueError("profiles require a nonempty final dimension of 21 stations")
        if not np.isfinite(profiles).all():
            raise ValueError("profiles must be finite signed metres")
        first = profiles @ self.curvature_response[:, 0]
        lateral = profiles @ self.lateral_response
        if not np.isfinite(first).all() or not np.isfinite(lateral).all():
            raise ValueError("planner response must be finite")
        return {
            "first_curvature_change_per_m": first,
            "peak_planned_lateral_change_m": np.max(np.abs(lateral), axis=-1),
        }


def build_spatial_response(
    scenario: SpatialPlannerScenario, config: ReferencePlannerConfig
) -> SpatialPlannerResponse:
    """Solve nominal and unit disturbances to obtain the planner response map."""
    stations = np.asarray(STATIONS_M)
    if not np.isfinite(scenario.speed_mps) or scenario.speed_mps < config.minimum_speed_mps:
        raise ValueError("spatial scenario speed must be finite and above the planner minimum")
    if scenario.speed_mps * scenario.dt_s * config.horizon_steps > stations[-1]:
        raise ValueError("planner lookahead exceeds the 100 m residual support")
    inputs = {
        "lateral_error_m": scenario.lateral_error_m,
        "heading_error_rad": scenario.heading_error_rad,
        "previous_curvature_correction_per_m": scenario.previous_curvature_correction_per_m,
        "stations_m": stations,
        "speed_mps": scenario.speed_mps,
        "dt_s": scenario.dt_s,
        "config": config,
    }
    nominal = plan_reference_horizon(residual_profile_m=np.zeros_like(stations), **inputs)
    lateral = []
    curvature = []
    for basis in np.eye(len(stations)):
        perturbed = plan_reference_horizon(residual_profile_m=basis, **inputs)
        lateral.append(perturbed.lateral_error_m - nominal.lateral_error_m)
        curvature.append(perturbed.curvature_correction_per_m - nominal.curvature_correction_per_m)
    lateral_response, curvature_response = np.asarray(lateral), np.asarray(curvature)
    for array in (lateral_response, curvature_response):
        if not np.isfinite(array).all():
            raise ValueError("planner response map must be finite")
        array.setflags(write=False)
    return SpatialPlannerResponse(nominal.distances_m, lateral_response, curvature_response)
