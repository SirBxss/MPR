"""Matched development flows with supplied fold transforms and bounded work.

This learner is separate from the synthetic prototype. It reuses only its pure
bridge and gradient arithmetic. No split, transform fit, selection on held out
rows, density estimate or real data authorization is provided by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from time import monotonic
from typing import Callable

import numpy as np

from ..domain.flow_matching import _offsets
from .flow_matching import _inputs, _training_inputs, _batch_loss_and_gradients
from .matched_gaussian import MatchedGaussian, matrix

MODES = ("unconditional", "conditional")
MODEL_NAMES = tuple("matched_" + m + "_flow" for m in MODES)
CONFIGURATION = {"hidden_width": 64, "epochs": 100, "batch_size": 256,
                 "learning_rate": .003, "adam_beta1": .9, "adam_beta2": .999,
                 "adam_epsilon": 1e-8, "maximum_fit_seconds": 600,
                 "maximum_rows": 20000, "maximum_sequences": 10000,
                 "maximum_sequence_length": 100, "maximum_sample_values": 16000000,
                 "maximum_sampling_seconds": 180}
ARRAY_FIELDS = ("residual_mean", "residual_scale", "condition_mean", "condition_scale",
                "weights_in", "bias_in", "weights_out", "bias_out")


def joined_blocks(blocks: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Join exact complete blocks, retaining every original sequence boundary."""
    if not blocks or len({b.outing_id for b in blocks}) != len(blocks):
        raise ValueError("flow_distinct_training_blocks_required")
    offsets = [0]
    for b in blocks:
        y, x = matrix(b.y, 21), matrix(b.x, 6)
        if len(y) != len(x):
            raise ValueError("flow_row_alignment")
        o = _offsets(b.offsets, len(y))
        offsets.extend((o[1:] + offsets[-1]).tolist())
    y, x = np.concatenate([b.y for b in blocks]), np.concatenate([b.x for b in blocks])
    o = np.asarray(offsets, dtype=np.int64)
    if (len(y) > CONFIGURATION["maximum_rows"] or len(o)-1 > CONFIGURATION["maximum_sequences"]
            or max(np.diff(o)) > CONFIGURATION["maximum_sequence_length"]):
        raise ValueError("flow_training_resource_bound")
    return y, x, o


@dataclass(frozen=True)
class MatchedFlow:
    """Finite fixed architecture state, with detached immutable parameters."""
    mode: str
    residual_mean: np.ndarray
    residual_scale: np.ndarray
    condition_mean: np.ndarray
    condition_scale: np.ndarray
    weights_in: np.ndarray
    bias_in: np.ndarray
    weights_out: np.ndarray
    bias_out: np.ndarray
    training_losses: tuple[float, ...]
    training_rows: int
    training_sequences: int
    seed: int

    def __post_init__(self) -> None:
        if type(self.mode) is not str or self.mode not in MODES:
            raise ValueError("flow_mode")
        for name in ("training_rows", "training_sequences", "seed"):
            v = getattr(self, name)
            if type(v) is not int or v < (0 if name == "seed" else 1):
                raise ValueError("flow_training_identity")
        if not 1 <= self.training_sequences <= self.training_rows <= CONFIGURATION["maximum_rows"]:
            raise ValueError("flow_training_counts")
        h = CONFIGURATION["hidden_width"]
        shapes = {"residual_mean": (21,), "residual_scale": (21,), "condition_mean": (6,),
                  "condition_scale": (6,), "weights_in": (22 if self.mode == MODES[0] else 50, h),
                  "bias_in": (h,), "weights_out": (h, 21), "bias_out": (21,)}
        for name, shape in shapes.items():
            a = np.asarray(getattr(self, name), dtype=np.float64).copy()
            if a.shape != shape or not np.isfinite(a).all() or (name.endswith("scale") and np.any(a <= 0)):
                raise ValueError("flow_finite_fixed_parameters")
            a.setflags(write=False)
            object.__setattr__(self, name, a)
        losses = np.asarray(self.training_losses, dtype=np.float64)
        if (losses.ndim != 1 or not 1 <= len(losses) <= CONFIGURATION["epochs"]
                or not np.isfinite(losses).all() or np.any(losses < 0)):
            raise ValueError("flow_finite_training_losses")
        object.__setattr__(self, "training_losses", tuple(float(v) for v in losses))

    def to_dict(self) -> dict:
        result = {f.name: getattr(self, f.name) for f in fields(self)}
        result.update({name: getattr(self, name).tolist() for name in ARRAY_FIELDS})
        result["training_losses"] = list(self.training_losses)
        return result

    @classmethod
    def from_dict(cls, value: dict) -> MatchedFlow:
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("flow_closed_state_schema")
        return cls(**value)

    def velocity(self, z: np.ndarray, time: np.ndarray, conditions: np.ndarray,
                 previous: np.ndarray, starts: np.ndarray) -> np.ndarray:
        """Velocity in standardized space; history is a physical generated error."""
        z, x, p = matrix(z, 21), matrix(conditions, 6), matrix(previous, 21)
        t, s = np.asarray(time), np.asarray(starts)
        if (len(x) != len(z) or len(p) != len(z) or t.shape != (len(z),)
                or not np.isfinite(t).all() or np.any((t < 0) | (t > 1))
                or s.shape != t.shape or s.dtype.kind != "b"):
            raise ValueError("flow_velocity_inputs")
        x = (x-self.condition_mean)/self.condition_scale
        p = np.where(s[:, None], 0., (p-self.residual_mean)/self.residual_scale)
        a = _inputs(z, t, x, p, s, self.mode)
        v = np.tanh(a @ self.weights_in + self.bias_in) @ self.weights_out + self.bias_out
        if not np.isfinite(v).all():
            raise ValueError("flow_nonfinite_velocity")
        return v


def fit_matched_flow(base: MatchedGaussian, blocks: list, *, mode: str, seed: int,
                     checkpoint: Callable[[MatchedFlow], None] | None = None) -> tuple[MatchedFlow, dict]:
    """Fit exactly one fixed configuration to supplied training blocks only.

    Checkpoints preserve completed epochs for diagnosis. They are not resumable
    optimizer states and never grant another attempt or automatic continuation.
    """
    if (not isinstance(base, MatchedGaussian) or base.mode != "conditional_gaussian"
            or mode not in MODES or type(seed) is not int or seed < 0):
        raise ValueError("flow_frozen_transform_and_seed_required")
    y, x, offsets = joined_blocks(blocks)
    if base.training_rows != len(y):
        raise ValueError("flow_exact_transform_training_support")
    y = (y-base.residual_mean)/base.residual_scale
    x = (x-base.condition_mean)/base.condition_scale
    rngs = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(4)]
    init, noise, times, order = rngs
    h, width = CONFIGURATION["hidden_width"], (22 if mode == MODES[0] else 50)
    parameters = [init.normal(0, 1/np.sqrt(width), (width, h)), np.zeros(h),
                  init.normal(0, 1/np.sqrt(h), (h, 21)), np.zeros(21)]
    first, second = [np.zeros_like(p) for p in parameters], [np.zeros_like(p) for p in parameters]
    losses: list[float] = []
    started, iteration = monotonic(), 0

    def state() -> MatchedFlow:
        return MatchedFlow(mode, base.residual_mean, base.residual_scale, base.condition_mean,
                           base.condition_scale, *parameters, tuple(losses), len(y), len(offsets)-1, seed)

    for epoch in range(CONFIGURATION["epochs"]):
        a, target = _training_inputs(y, x, offsets, noise.standard_normal(y.shape), times.uniform(0, 1, len(y)), mode)
        indices, total = order.permutation(len(y)), 0.
        for lo in range(0, len(y), CONFIGURATION["batch_size"]):
            if monotonic()-started > CONFIGURATION["maximum_fit_seconds"]:
                raise TimeoutError("flow_fixed_fit_time_budget_preserve_checkpoints")
            ix = indices[lo:lo+CONFIGURATION["batch_size"]]
            loss, gradients = _batch_loss_and_gradients(a[ix], target[ix], parameters)
            total += loss
            iteration += 1
            for i, gradient in enumerate(gradients):
                first[i] = .9*first[i] + .1*gradient
                second[i] = .999*second[i] + .001*gradient*gradient
                parameters[i] -= CONFIGURATION["learning_rate"]*(first[i]/(1-.9**iteration))/(np.sqrt(second[i]/(1-.999**iteration))+1e-8)
            if not np.isfinite(loss) or any(not np.isfinite(p).all() for p in parameters):
                raise ValueError("flow_nonfinite_training_preserve_attempt")
        losses.append(total/(len(y)*21))
        if checkpoint is not None and (epoch == 0 or (epoch+1) % 10 == 0):
            checkpoint(state())
    model = state()
    return model, {"configuration": dict(CONFIGURATION), "epochs_completed": len(losses),
                   "optimizer_updates": iteration, "elapsed_seconds": monotonic()-started,
                   "selection": "fixed_epochs_no_held_out_selection_no_restart",
                   "training_objective": "bridge_velocity_MSE_not_density_or_validation_score",
                   "convergence_claim": False, "transform_refitted": False}


def sample_matched_flow(model: MatchedFlow, x: np.ndarray, offsets: np.ndarray, *,
                        sample_count: int, seed: int, steps: int, batch_size: int = 4096) -> np.ndarray:
    """Euler draws on exact flat rows with independent generated sequence history.

    Noise is indexed by draw and original row before computation batching, so
    solver refinement and batch size preserve the same random inputs. The
    interface accepts conditions and resets, never observed residual targets.
    """
    if not isinstance(model, MatchedFlow):
        raise ValueError("flow_real_saved_state_required")
    x = matrix(x, 6)
    o = _offsets(offsets, len(x))
    if (any(type(v) is not int or v < 1 for v in (sample_count, steps, batch_size))
            or type(seed) is not int or seed < 0 or sample_count < 4 or sample_count % 2
            or steps > 128 or batch_size > 4096 or len(x) > CONFIGURATION["maximum_rows"]
            or len(o)-1 > CONFIGURATION["maximum_sequences"]
            or max(np.diff(o)) > CONFIGURATION["maximum_sequence_length"]
            or sample_count*len(x)*21 > CONFIGURATION["maximum_sample_values"]):
        raise ValueError("flow_sampling_resource_bound")
    started = monotonic()
    result = np.random.default_rng(seed).standard_normal((sample_count, len(x), 21))
    lengths = np.diff(o)
    history = np.zeros((sample_count, len(lengths), 21))
    for frame in range(int(max(lengths))):
        seq = np.flatnonzero(lengths > frame)
        rows = o[:-1][seq] + frame
        z = result[:, rows].reshape(-1, 21).copy()
        xx = np.broadcast_to(x[rows], (sample_count, len(rows), 6)).reshape(-1, 6)
        p = history[:, seq].reshape(-1, 21)
        for step in range(steps):
            for lo in range(0, len(z), batch_size):
                if monotonic()-started > CONFIGURATION["maximum_sampling_seconds"]:
                    raise TimeoutError("flow_sampling_time_budget_preserve_attempt")
                hi = min(lo+batch_size, len(z))
                z[lo:hi] += model.velocity(z[lo:hi], np.full(hi-lo, step/steps), xx[lo:hi],
                                           p[lo:hi], np.full(hi-lo, frame == 0))/steps
        physical = (z*model.residual_scale + model.residual_mean).reshape(sample_count, len(rows), 21)
        if not np.isfinite(physical).all():
            raise ValueError("flow_nonfinite_generated_samples")
        result[:, rows], history[:, seq] = physical, physical
    return result
