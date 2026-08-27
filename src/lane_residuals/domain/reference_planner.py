"""Deterministic lateral error-state reference planner for v0.16.

The planner is deliberately not a vehicle or production-planner replica.  It
propagates lateral and heading error around the recorded motion and replans at
each recorded frame.  This is the smallest model in which temporal ordering of
an exogenous perception-error sequence can affect later outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ReferencePlannerConfig:
    """Fixed numerical contract for the v0.16 sensitivity experiment."""

    horizon_steps: int = 25
    weight_lateral: float = 8.0
    weight_heading: float = 3.0
    weight_curvature: float = 1.0
    weight_curvature_rate: float = 4.0
    terminal_multiplier: float = 4.0
    maximum_abs_curvature_per_m: float = 0.20
    maximum_abs_curvature_rate_per_m_s: float = 0.25
    maximum_abs_lateral_acceleration_mps2: float = 3.0
    maximum_abs_lateral_jerk_mps3: float = 5.0
    maximum_abs_lateral_deviation_m: float = 1.0
    lateral_excursion_threshold_m: float = 0.3
    minimum_speed_mps: float = 0.1
    minimum_dt_s: float = 0.01
    maximum_dt_s: float = 0.25

    def __post_init__(self) -> None:
        if (
            isinstance(self.horizon_steps, bool)
            or not isinstance(self.horizon_steps, (int, np.integer))
            or self.horizon_steps < 1
        ):
            raise ValueError("horizon_steps must be a positive integer")
        positive_fields = (
            "weight_lateral",
            "weight_heading",
            "weight_curvature",
            "weight_curvature_rate",
            "terminal_multiplier",
            "maximum_abs_curvature_per_m",
            "maximum_abs_curvature_rate_per_m_s",
            "maximum_abs_lateral_acceleration_mps2",
            "maximum_abs_lateral_jerk_mps3",
            "maximum_abs_lateral_deviation_m",
            "lateral_excursion_threshold_m",
            "minimum_speed_mps",
            "minimum_dt_s",
            "maximum_dt_s",
        )
        if not all(
            not isinstance(getattr(self, name), bool)
            and np.isfinite(float(getattr(self, name)))
            and float(getattr(self, name)) > 0.0
            for name in positive_fields
        ):
            raise ValueError("all reference-planner parameters must be positive")
        if self.minimum_dt_s >= self.maximum_dt_s:
            raise ValueError("minimum_dt_s must be smaller than maximum_dt_s")


@dataclass(frozen=True)
class PlannerStep:
    """One receding-horizon decision and propagated error state."""

    lateral_error_m: float
    heading_error_rad: float
    curvature_correction_per_m: float
    objective: float


def signed_curvature_at_origin(path_xy_m: NDArray[np.float64]) -> float:
    """Estimate signed curvature from the first three H100 path points."""

    path = np.asarray(path_xy_m, dtype=np.float64)
    if path.shape != (21, 2) or not np.all(np.isfinite(path)):
        raise ValueError("nominal path must be finite with shape [21,2]")
    first = path[1] - path[0]
    second = path[2] - path[1]
    chord = path[2] - path[0]
    lengths = (np.linalg.norm(first), np.linalg.norm(second), np.linalg.norm(chord))
    if min(lengths) <= 1e-9:
        raise ValueError("nominal path begins with coincident points")
    cross = first[0] * second[1] - first[1] * second[0]
    return float(2.0 * cross / np.prod(lengths))


def perturb_path_left_normal(
    path_xy_m: NDArray[np.float64], residual_m: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Apply signed H100 offsets along robust finite-difference left normals."""

    path = np.asarray(path_xy_m, dtype=np.float64)
    residual = np.asarray(residual_m, dtype=np.float64)
    if path.shape != (21, 2) or residual.shape != (21,):
        raise ValueError("path and residual must have shapes [21,2] and [21]")
    if not np.all(np.isfinite(path)) or not np.all(np.isfinite(residual)):
        raise ValueError("path perturbation inputs must be finite")
    tangents = np.empty_like(path)
    tangents[0] = path[1] - path[0]
    tangents[-1] = path[-1] - path[-2]
    tangents[1:-1] = path[2:] - path[:-2]
    norms = np.linalg.norm(tangents, axis=1)
    if np.any(norms <= 1e-9):
        raise ValueError("nominal path contains an undefined tangent")
    tangents /= norms[:, None]
    left_normals = np.column_stack((-tangents[:, 1], tangents[:, 0]))
    return path + residual[:, None] * left_normals


def plan_reference_step(
    *,
    lateral_error_m: float,
    heading_error_rad: float,
    previous_curvature_correction_per_m: float,
    residual_profile_m: NDArray[np.float64],
    stations_m: NDArray[np.float64],
    speed_mps: float,
    dt_s: float,
    config: ReferencePlannerConfig,
) -> PlannerStep:
    """Solve one unconstrained finite-horizon affine LQ tracking problem."""

    residual = np.asarray(residual_profile_m, dtype=np.float64)
    stations = np.asarray(stations_m, dtype=np.float64)
    if residual.shape != (21,) or stations.shape != (21,):
        raise ValueError("residual_profile_m and stations_m must have shape [21]")
    if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(stations)):
        raise ValueError("planner profile inputs must be finite")
    if np.any(np.diff(stations) <= 0) or stations[0] != 0.0:
        raise ValueError("planner stations must strictly increase from zero")
    scalars = (
        lateral_error_m,
        heading_error_rad,
        previous_curvature_correction_per_m,
        speed_mps,
        dt_s,
    )
    if not all(np.isfinite(value) for value in scalars):
        raise ValueError("planner scalar inputs must be finite")
    if speed_mps < 0.0:
        raise ValueError("reference-planner speed must be nonnegative")
    speed = max(float(speed_mps), config.minimum_speed_mps)
    if not config.minimum_dt_s <= dt_s <= config.maximum_dt_s:
        raise ValueError("frame interval lies outside the predeclared range")

    step_distance = speed * dt_s
    references = np.interp(
        step_distance * (np.arange(config.horizon_steps) + 1),
        stations,
        residual,
        right=float(residual[-1]),
    )
    a = np.array(
        [[1.0, step_distance, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    b = np.array([[0.0], [step_distance], [1.0]], dtype=np.float64)
    next_state_cost = np.diag(
        [2.0 * config.weight_lateral, 2.0 * config.weight_heading, 0.0]
    )
    previous_input_cost = np.diag(
        [0.0, 0.0, 2.0 * config.weight_curvature_rate]
    )
    input_cost = 2.0 * (
        config.weight_curvature + config.weight_curvature_rate
    )
    cross_cost = np.array(
        [[0.0], [0.0], [-2.0 * config.weight_curvature_rate]]
    )
    p_matrix = np.zeros((3, 3), dtype=np.float64)
    p_vector = np.zeros(3, dtype=np.float64)
    policies: list[tuple[NDArray[np.float64], float]] = []
    for reverse_index, reference in enumerate(references[::-1]):
        multiplier = (
            config.terminal_multiplier if reverse_index == 0 else 1.0
        )
        predicted_cost = multiplier * next_state_cost
        predicted_linear = np.array(
            [-2.0 * multiplier * config.weight_lateral * reference, 0.0, 0.0]
        )
        combined_matrix = p_matrix + predicted_cost
        combined_vector = p_vector + predicted_linear
        hessian = float(input_cost + (b.T @ combined_matrix @ b)[0, 0])
        gain_term = b.T @ combined_matrix @ a + cross_cost.T
        offset_term = float((b.T @ combined_vector.reshape(-1, 1))[0, 0])
        gain = gain_term / hessian
        offset = offset_term / hessian
        p_matrix = (
            previous_input_cost
            + a.T @ combined_matrix @ a
            - gain_term.T @ gain
        )
        p_matrix = 0.5 * (p_matrix + p_matrix.T)
        p_vector = (
            a.T @ combined_vector - gain_term.ravel() * offset
        )
        policies.append((gain, offset))
    policies.reverse()
    state = np.array(
        [lateral_error_m, heading_error_rad, previous_curvature_correction_per_m],
        dtype=np.float64,
    )
    objective = 0.0
    first_correction: float | None = None
    first_next_state: NDArray[np.float64] | None = None
    for index, ((gain, offset), reference) in enumerate(
        zip(policies, references)
    ):
        correction = -float((gain @ state)[0]) - offset
        next_state = a @ state + b[:, 0] * correction
        multiplier = (
            config.terminal_multiplier
            if index == config.horizon_steps - 1
            else 1.0
        )
        objective += multiplier * (
            config.weight_lateral * (next_state[0] - reference) ** 2
            + config.weight_heading * next_state[1] ** 2
        )
        objective += config.weight_curvature * correction**2
        objective += config.weight_curvature_rate * (correction - state[2]) ** 2
        if index == 0:
            first_correction = correction
            first_next_state = next_state.copy()
        state = next_state
    if first_correction is None or first_next_state is None:
        raise RuntimeError("reference-planner horizon produced no control policy")
    return PlannerStep(
        lateral_error_m=float(first_next_state[0]),
        heading_error_rad=float(first_next_state[1]),
        curvature_correction_per_m=first_correction,
        objective=float(objective),
    )


__all__ = [
    "PlannerStep",
    "ReferencePlannerConfig",
    "perturb_path_left_normal",
    "plan_reference_step",
    "signed_curvature_at_origin",
]
