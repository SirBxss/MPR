"""Synthetic-testable straight-path conditional flow matching primitives.

No learned vector field, fitted standardizer, real-data fit, or likelihood is
defined here. A later model can minimize squared velocity error and sample
with the same one-state, free-running temporal contract as the thesis models.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


VectorField = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def _finite_shape(value: np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite with shape {shape}")
    return array


def _offsets(offsets: np.ndarray, count: int) -> np.ndarray:
    values = np.asarray(offsets)
    if (values.ndim != 1 or values.dtype.kind not in "iu" or len(values) == 0
            or values[0] != 0 or values[-1] != count or not np.all(values[1:] > values[:-1])):
        raise ValueError("offsets must partition contiguous nonempty sequences")
    return values


@dataclass(frozen=True)
class LinearFlowBatch:
    """Independent noise-data coupling and observed previous target for training."""

    bridge: np.ndarray
    target_velocity: np.ndarray
    conditions: np.ndarray
    observed_previous: np.ndarray
    time: np.ndarray


def linear_flow_batch(residuals: np.ndarray, conditions: np.ndarray,
                      sequence_offsets: np.ndarray, base_noise: np.ndarray,
                      time: np.ndarray) -> LinearFlowBatch:
    """z_tau=(1-tau)z0+tau*y; squared-error target velocity y-z0.

    The caller supplies fresh independent standard-normal base noise and
    uniform time draws. Previous observed residual is legal only during
    training; inference instead feeds back the sampled previous residual.
    """
    y = np.asarray(residuals, dtype=np.float64)
    if y.ndim != 2 or y.shape[1] != 21:
        raise ValueError("residuals must have 21 stations")
    n = len(y)
    y = _finite_shape(y, (n, 21), "residuals")
    x = _finite_shape(conditions, (n, 6), "conditions")
    z0 = _finite_shape(base_noise, (n, 21), "base_noise")
    tau = _finite_shape(time, (n,), "time")
    if np.any((tau < 0) | (tau > 1)):
        raise ValueError("time must lie in [0,1]")
    offsets = _offsets(sequence_offsets, n)
    previous = np.zeros_like(y)
    for lo, hi in zip(offsets[:-1], offsets[1:]):
        previous[lo + 1:hi] = y[lo:hi - 1]
    return LinearFlowBatch((1 - tau[:, None]) * z0 + tau[:, None] * y,
                           y - z0, x.copy(), previous, tau.copy())


def integrate_euler(vector_field: VectorField, base_noise: np.ndarray,
                    conditions: np.ndarray, previous: np.ndarray, steps: int) -> np.ndarray:
    """Fixed-step ODE integration over tau in [0,1]; no likelihood estimate."""
    z = np.asarray(base_noise, dtype=np.float64)
    if z.ndim != 2 or z.shape[1] != 21:
        raise ValueError("base_noise must have 21 stations")
    count = len(z)
    z = _finite_shape(z, (count, 21), "base_noise").copy()
    x = _finite_shape(conditions, (count, 6), "conditions")
    prev = _finite_shape(previous, (count, 21), "previous")
    if type(steps) is not int or steps < 1:
        raise ValueError("steps must be a positive integer")
    for k in range(steps):
        tau = np.full(count, k / steps)
        velocity = _finite_shape(vector_field(z.copy(), tau, x.copy(), prev.copy()),
                                 (count, 21), "vector field velocity")
        z += velocity / steps
        if not np.all(np.isfinite(z)):
            raise ValueError("ODE integration diverged")
    return z


def sample_free_running(vector_field: VectorField, conditions: np.ndarray,
                        lengths: np.ndarray, base_noise: np.ndarray, steps: int) -> np.ndarray:
    """Sample [sample, sequence, frame, station] with state reset at each run.

    Padded frames stay zero. The vector field only sees current conditions,
    ODE time, current latent vector and its own sampled previous residual.
    """
    x = np.asarray(conditions, dtype=np.float64)
    if x.ndim != 3 or x.shape[-1] != 6:
        raise ValueError("conditions must have shape [sequence, frame, 6]")
    batch, frames, _ = x.shape
    x = _finite_shape(x, (batch, frames, 6), "conditions")
    length = np.asarray(lengths)
    if (length.shape != (batch,) or length.dtype.kind not in "iu"
            or np.any(length < 1) or np.any(length > frames)):
        raise ValueError("lengths must identify nonempty runs within the padded frame grid")
    noise = np.asarray(base_noise, dtype=np.float64)
    if noise.ndim != 4 or noise.shape[1:] != (batch, frames, 21):
        raise ValueError("base_noise must have shape [sample, sequence, frame, 21]")
    noise = _finite_shape(noise, noise.shape, "base_noise")
    if not len(noise):
        raise ValueError("at least one sample required")
    result = np.zeros_like(noise)
    for sample in range(len(noise)):
        for sequence in range(batch):
            previous = np.zeros((1, 21), dtype=np.float64)
            for frame in range(int(length[sequence])):
                current = integrate_euler(vector_field, noise[sample, sequence, frame:frame + 1],
                                          x[sequence, frame:frame + 1], previous, steps)
                result[sample, sequence, frame] = current[0]
                previous = current
    return result
