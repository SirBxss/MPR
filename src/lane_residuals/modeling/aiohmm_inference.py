"""Numerically stable inference for time-inhomogeneous hidden Markov models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def logsumexp(
    values: FloatArray,
    *,
    axis: int | tuple[int, ...] | None = None,
    keepdims: bool = False,
) -> FloatArray | np.float64:
    """Return a NumPy-only, overflow-safe log-sum-exp."""

    array = np.asarray(values, dtype=np.float64)
    maximum = np.max(array, axis=axis, keepdims=True)
    finite_maximum = np.where(np.isfinite(maximum), maximum, 0.0)
    total = np.sum(np.exp(array - finite_maximum), axis=axis, keepdims=True)
    result = finite_maximum + np.log(total)
    if not keepdims and axis is not None:
        result = np.squeeze(result, axis=axis)
    if axis is None and not keepdims:
        return np.float64(np.asarray(result).item())
    return np.asarray(result, dtype=np.float64)


def log_softmax(values: FloatArray, *, axis: int) -> FloatArray:
    """Return normalized log probabilities along ``axis``."""

    array = np.asarray(values, dtype=np.float64)
    return array - np.asarray(logsumexp(array, axis=axis, keepdims=True))


def transition_log_probabilities(
    conditions: FloatArray,
    transition_weights: FloatArray,
    *,
    input_dependent: bool,
) -> FloatArray:
    """Return ``[T-1, source_state, destination_state]`` log probabilities.

    The condition at the destination frame controls the transition into that
    frame. This convention is shared by training, density evaluation, and
    free-running generation.
    """

    condition_array = np.asarray(conditions, dtype=np.float64)
    weights = np.asarray(transition_weights, dtype=np.float64)
    if condition_array.ndim != 2 or len(condition_array) < 1:
        raise ValueError("conditions must have nonempty shape [T,F]")
    if weights.ndim != 3 or weights.shape[0] != weights.shape[1]:
        raise ValueError("transition_weights must have shape [N,N,F+1]")
    if weights.shape[2] != condition_array.shape[1] + 1:
        raise ValueError("transition weights and conditions are incompatible")
    if not np.all(np.isfinite(condition_array)) or not np.all(np.isfinite(weights)):
        raise ValueError("transition inputs must be finite")
    if len(condition_array) == 1:
        return np.empty((0, weights.shape[0], weights.shape[1]), dtype=np.float64)
    design = np.column_stack(
        (np.ones(len(condition_array) - 1, dtype=np.float64), condition_array[1:])
    )
    if not input_dependent:
        design[:, 1:] = 0.0
    logits = np.einsum("tp,ijp->tij", design, weights, optimize=True)
    return log_softmax(logits, axis=2)


@dataclass(frozen=True)
class ForwardBackwardResult:
    """Smoothed state/transition probabilities for one complete sequence."""

    log_probability: float
    log_normalizers: FloatArray
    state_probabilities: FloatArray
    transition_probabilities: FloatArray

    def __post_init__(self) -> None:
        gamma = np.asarray(self.state_probabilities, dtype=np.float64)
        xi = np.asarray(self.transition_probabilities, dtype=np.float64)
        normalizers = np.asarray(self.log_normalizers, dtype=np.float64)
        if gamma.ndim != 2 or len(gamma) < 1:
            raise ValueError("state probabilities must have nonempty shape [T,N]")
        if xi.shape != (len(gamma) - 1, gamma.shape[1], gamma.shape[1]):
            raise ValueError("transition probabilities have an invalid shape")
        if normalizers.shape != (len(gamma),):
            raise ValueError("log normalizers must have shape [T]")
        if not all(
            np.all(np.isfinite(values)) for values in (gamma, xi, normalizers)
        ) or not np.isfinite(self.log_probability):
            raise ValueError("forward-backward result must be finite")
        if not np.allclose(np.sum(gamma, axis=1), 1.0, atol=1e-8):
            raise ValueError("state posterior rows must sum to one")
        if len(xi) and not np.allclose(np.sum(xi, axis=(1, 2)), 1.0, atol=1e-8):
            raise ValueError("transition posterior slices must sum to one")
        if not np.isclose(np.sum(normalizers), self.log_probability, atol=1e-8):
            raise ValueError("filter normalizers do not reconcile to sequence density")
        for array in (gamma, xi, normalizers):
            array.setflags(write=False)
        object.__setattr__(self, "state_probabilities", gamma)
        object.__setattr__(self, "transition_probabilities", xi)
        object.__setattr__(self, "log_normalizers", normalizers)


def forward_backward(
    log_initial_probabilities: FloatArray,
    log_transition_probabilities: FloatArray,
    log_emission_probabilities: FloatArray,
) -> ForwardBackwardResult:
    """Run log-domain forward-backward inference for one sequence."""

    log_initial = np.asarray(log_initial_probabilities, dtype=np.float64)
    log_transition = np.asarray(log_transition_probabilities, dtype=np.float64)
    log_emission = np.asarray(log_emission_probabilities, dtype=np.float64)
    if log_initial.ndim != 1:
        raise ValueError("initial probabilities must have shape [N]")
    if log_emission.ndim != 2 or log_emission.shape[1] != len(log_initial):
        raise ValueError("emission probabilities must have shape [T,N]")
    time_count, state_count = log_emission.shape
    if time_count < 1:
        raise ValueError("at least one emission frame is required")
    if log_transition.shape != (time_count - 1, state_count, state_count):
        raise ValueError("transition probabilities must have shape [T-1,N,N]")
    if not all(
        np.all(np.isfinite(values))
        for values in (log_initial, log_transition, log_emission)
    ):
        raise ValueError("forward-backward inputs must be finite")

    log_alpha = np.empty((time_count, state_count), dtype=np.float64)
    normalizers = np.empty(time_count, dtype=np.float64)
    first = log_initial + log_emission[0]
    normalizers[0] = float(logsumexp(first))
    log_alpha[0] = first - normalizers[0]
    for time_index in range(1, time_count):
        predicted = logsumexp(
            log_alpha[time_index - 1, :, None]
            + log_transition[time_index - 1],
            axis=0,
        )
        current = np.asarray(predicted) + log_emission[time_index]
        normalizers[time_index] = float(logsumexp(current))
        log_alpha[time_index] = current - normalizers[time_index]

    log_beta = np.zeros_like(log_alpha)
    for time_index in range(time_count - 2, -1, -1):
        log_beta[time_index] = np.asarray(
            logsumexp(
                log_transition[time_index]
                + log_emission[time_index + 1][None, :]
                + log_beta[time_index + 1][None, :],
                axis=1,
            )
        ) - normalizers[time_index + 1]

    log_gamma = log_alpha + log_beta
    log_gamma -= np.asarray(logsumexp(log_gamma, axis=1, keepdims=True))
    gamma = np.exp(log_gamma)
    xi = np.empty((time_count - 1, state_count, state_count), dtype=np.float64)
    for time_index in range(time_count - 1):
        log_xi = (
            log_alpha[time_index, :, None]
            + log_transition[time_index]
            + log_emission[time_index + 1][None, :]
            + log_beta[time_index + 1][None, :]
        )
        log_xi -= float(logsumexp(log_xi))
        xi[time_index] = np.exp(log_xi)
    return ForwardBackwardResult(
        log_probability=float(np.sum(normalizers)),
        log_normalizers=normalizers,
        state_probabilities=gamma,
        transition_probabilities=xi,
    )


__all__ = [
    "ForwardBackwardResult",
    "forward_backward",
    "log_softmax",
    "logsumexp",
    "transition_log_probabilities",
]
