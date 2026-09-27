"""Small NumPy flow-matching prototypes for *synthetic-only* engineering tests.

No real-data fit, dataset split, model selection, likelihood, or persistence is
provided. Both modes learn the same straight-path velocity regression. The
unconditional mode is a time-independent sequence null; the conditional mode
uses current six-feature state and observed prior residual during training,
then its own generated prior residual during sampling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ..domain.flow_matching import _finite_shape, _offsets, integrate_euler, linear_flow_batch


Mode = Literal["unconditional", "conditional"]


def _scale(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale < 1e-6] = 1.0
    return mean, scale


def _inputs(z: np.ndarray, time: np.ndarray, conditions: np.ndarray,
            previous: np.ndarray, starts: np.ndarray, mode: Mode) -> np.ndarray:
    parts = [z, (2 * time - 1)[:, None]]
    if mode == "conditional":
        parts.extend((conditions, previous, starts[:, None].astype(np.float64)))
    return np.concatenate(parts, axis=1)


@dataclass(frozen=True)
class SyntheticFlowModel:
    mode: Mode
    residual_mean: np.ndarray
    residual_scale: np.ndarray
    condition_mean: np.ndarray
    condition_scale: np.ndarray
    weights_in: np.ndarray
    bias_in: np.ndarray
    weights_out: np.ndarray
    bias_out: np.ndarray
    training_losses: tuple[float, ...]

    def velocity(self, z: np.ndarray, time: np.ndarray, conditions: np.ndarray,
                 previous: np.ndarray, starts: np.ndarray) -> np.ndarray:
        """Predict velocity in standardized residual coordinates.

        ``previous`` is in physical units; its value is ignored at a start.
        A start flag distinguishes the reset from a genuine zero residual.
        """
        z = np.asarray(z, dtype=np.float64)
        if z.ndim != 2 or z.shape[1] != 21:
            raise ValueError("z must have 21 stations")
        n = len(z)
        z = _finite_shape(z, (n, 21), "z")
        time = _finite_shape(time, (n,), "time")
        if np.any((time < 0) | (time > 1)):
            raise ValueError("time must lie in [0,1]")
        conditions = _finite_shape(conditions, (n, 6), "conditions")
        previous = _finite_shape(previous, (n, 21), "previous")
        starts = np.asarray(starts)
        if starts.shape != (n,) or starts.dtype.kind != "b":
            raise ValueError("starts must be a boolean row vector")
        if self.mode == "conditional":
            x = (conditions - self.condition_mean) / self.condition_scale
            p = (previous - self.residual_mean) / self.residual_scale
            p = np.where(starts[:, None], 0., p)
        else:
            x, p = conditions, previous  # excluded by _inputs
        features = _inputs(z, time, x, p, starts, self.mode)
        hidden = np.tanh(features @ self.weights_in + self.bias_in)
        return _finite_shape(hidden @ self.weights_out + self.bias_out,
                             (n, 21), "learned velocity")

    def sample(self, conditions: np.ndarray, lengths: np.ndarray, *,
               sample_count: int, seed: int, steps: int = 32) -> np.ndarray:
        """Return physical [draw, sequence, padded-frame, station] samples.

        The identical indexed normal draw is available to either model mode.
        Padding is zero. Per-sequence state starts anew for each draw.
        """
        x = np.asarray(conditions, dtype=np.float64)
        if x.ndim != 3 or x.shape[-1] != 6:
            raise ValueError("conditions must have shape [sequence, frame, 6]")
        b, frames, _ = x.shape
        x = _finite_shape(x, (b, frames, 6), "conditions")
        lengths = np.asarray(lengths)
        if (lengths.shape != (b,) or lengths.dtype.kind not in "iu"
                or np.any(lengths < 1) or np.any(lengths > frames)):
            raise ValueError("lengths must identify nonempty sequences")
        if type(sample_count) is not int or sample_count < 1:
            raise ValueError("sample_count must be a positive integer")
        if type(steps) is not int or steps < 1:
            raise ValueError("steps must be a positive integer")
        noise = np.random.default_rng(seed).standard_normal((sample_count, b, frames, 21))
        values = np.zeros_like(noise)
        for draw in range(sample_count):
            for sequence in range(b):
                previous = np.zeros((1, 21))
                for frame in range(int(lengths[sequence])):
                    start = np.array([frame == 0])
                    current_x = x[sequence, frame:frame + 1]

                    def field(z: np.ndarray, time: np.ndarray,
                              _x: np.ndarray, _previous: np.ndarray) -> np.ndarray:
                        return self.velocity(z, time, current_x, previous, start)

                    result = integrate_euler(field, noise[draw, sequence, frame:frame + 1],
                                             current_x, previous, steps)
                    previous = result * self.residual_scale + self.residual_mean
                    values[draw, sequence, frame] = previous[0]
        return values


def fit_synthetic_flow(residuals: np.ndarray, conditions: np.ndarray,
                       sequence_offsets: np.ndarray, *, mode: Mode,
                       seed: int = 0, epochs: int = 40, batch_size: int = 64,
                       hidden_width: int = 64, learning_rate: float = 0.003) -> SyntheticFlowModel:
    """Train a one-hidden-layer tanh velocity MLP on caller-provided synthetic rows.

    All supplied rows are training rows. The caller must not pass real data or
    any held-out rows; there is intentionally no archive adapter or fitting CLI.
    Noise and bridge time are freshly sampled each epoch. This is an engineering
    prototype, with no selection, fitted artifact, or empirical thesis result.
    """
    if mode not in ("unconditional", "conditional"):
        raise ValueError("mode must be unconditional or conditional")
    y = np.asarray(residuals, dtype=np.float64)
    if y.ndim != 2 or y.shape[1] != 21 or not len(y):
        raise ValueError("residuals must contain nonempty 21-station rows")
    n = len(y)
    y = _finite_shape(y, (n, 21), "residuals")
    x = _finite_shape(conditions, (n, 6), "conditions")
    offsets = _offsets(sequence_offsets, n)
    if (any(type(value) is not int or value < 1 for value in
            (epochs, batch_size, hidden_width)) or not np.isfinite(learning_rate)
            or learning_rate <= 0):
        raise ValueError("positive integer training sizes and positive finite learning rate required")
    y_mean, y_scale = _scale(y)
    x_mean, x_scale = _scale(x) if mode == "conditional" else (np.zeros(6), np.ones(6))
    y_standard = (y - y_mean) / y_scale
    x_standard = (x - x_mean) / x_scale
    starts = np.zeros(n, dtype=bool)
    starts[offsets[:-1]] = True
    rng = np.random.default_rng(seed)
    input_width = 50 if mode == "conditional" else 22
    w1 = rng.normal(0, 1 / np.sqrt(input_width), (input_width, hidden_width))
    b1 = np.zeros(hidden_width)
    w2 = rng.normal(0, 1 / np.sqrt(hidden_width), (hidden_width, 21))
    b2 = np.zeros(21)
    parameters = [w1, b1, w2, b2]
    first = [np.zeros_like(p) for p in parameters]
    second = [np.zeros_like(p) for p in parameters]
    iteration = 0
    losses = []
    for _ in range(epochs):
        z0 = rng.standard_normal((n, 21))
        time = rng.uniform(0., 1., n)
        bridge = linear_flow_batch(y_standard, x_standard, offsets, z0, time)
        # At a start there is no observed prior; do not encode -mean/scale.
        previous = bridge.observed_previous.copy()
        previous[starts] = 0.
        features = _inputs(bridge.bridge, time, x_standard, previous, starts, mode)
        target = bridge.target_velocity
        order = rng.permutation(n)
        epoch_loss = 0.
        for lo in range(0, n, batch_size):
            indices = order[lo:lo + batch_size]
            inputs, targets = features[indices], target[indices]
            hidden = np.tanh(inputs @ w1 + b1)
            difference = hidden @ w2 + b2 - targets
            epoch_loss += float(np.sum(difference * difference))
            grad_output = 2 * difference / (len(indices) * 21)
            grad_w2 = hidden.T @ grad_output
            grad_b2 = grad_output.sum(axis=0)
            grad_hidden = (grad_output @ w2.T) * (1 - hidden * hidden)
            gradients = [inputs.T @ grad_hidden, grad_hidden.sum(axis=0),
                         grad_w2, grad_b2]
            iteration += 1
            for index, (param, grad) in enumerate(zip(parameters, gradients)):
                first[index] = 0.9 * first[index] + 0.1 * grad
                second[index] = 0.999 * second[index] + 0.001 * grad * grad
                param -= learning_rate * (first[index] / (1 - 0.9 ** iteration)) / (
                    np.sqrt(second[index] / (1 - 0.999 ** iteration)) + 1e-8)
        loss = epoch_loss / (n * 21)
        if not np.isfinite(loss) or any(not np.all(np.isfinite(p)) for p in parameters):
            raise ValueError("flow training diverged")
        losses.append(loss)
    arrays = (y_mean, y_scale, x_mean, x_scale, *parameters)
    frozen = tuple(a.copy() for a in arrays)
    for array in frozen:
        array.setflags(write=False)
    return SyntheticFlowModel(mode, *frozen, tuple(losses))
