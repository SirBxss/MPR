"""Synthetic engineering checks only; never use a recorded driving archive."""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from lane_residuals.modeling import flow_matching as flow_module
from lane_residuals.modeling.flow_matching import (
    SyntheticFlowModel, _training_inputs, fit_synthetic_flow,
)


class SyntheticFlowTests(unittest.TestCase):
    def test_two_modes_learn_same_rows_but_only_conditional_responds_to_features(self):
        rng = np.random.default_rng(84)
        x = rng.normal(size=(192, 6))
        y = x[:, :1] * 0.8 + rng.normal(size=(192, 21)) * 0.2
        offsets = np.arange(0, 193, 8)
        common = dict(seed=13, epochs=55, batch_size=48, hidden_width=24)
        unconditional = fit_synthetic_flow(y, x, offsets, mode="unconditional", **common)
        conditional = fit_synthetic_flow(y, x, offsets, mode="conditional", **common)
        for model in (unconditional, conditional):
            self.assertLess(np.mean(model.training_losses[-5:]),
                            np.mean(model.training_losses[:5]))
            self.assertTrue(np.isfinite(model.sample(np.zeros((2, 2, 6)),
                                                          np.array([1, 2]),
                                                          sample_count=2, seed=22, steps=8)).all())
            self.assertEqual(model.training_losses, fit_synthetic_flow(
                y, x, offsets, mode=model.mode, **common).training_losses)
            self.assertFalse(model.weights_in.flags.writeable)
        z = np.zeros((2, 21))
        t = np.ones(2) * .5
        conditions = np.zeros((2, 6))
        conditions[1, 0] = 2
        previous = np.zeros((2, 21))
        starts = np.ones(2, dtype=bool)
        null_velocity = unconditional.velocity(z, t, conditions, previous, starts)
        np.testing.assert_array_equal(null_velocity[0], null_velocity[1])
        feature_velocity = conditional.velocity(z, t, conditions, previous, starts)
        self.assertGreater(float(np.mean(np.abs(feature_velocity[0] - feature_velocity[1]))), .1)

    def test_training_uses_conditioned_offsets_and_explicit_start_indicator(self):
        # The supplied offsets are for *these* complete rows, never geometric-row indices.
        y = np.arange(1., 6.)[:, None] * np.ones((1, 21))
        x = np.zeros((5, 6))
        model = fit_synthetic_flow(y, x, np.array([0, 2, 5]),
                                   mode="conditional", epochs=1, seed=2)
        self.assertAlmostEqual(model.residual_mean[0], 3.)
        standardized = (y - model.residual_mean) / model.residual_scale
        tau = np.array([0., .25, .5, .75, 1.])
        noise = np.zeros_like(y)
        features, target = _training_inputs(standardized, x,
                                             np.array([0, 2, 5]), noise, tau,
                                             "conditional")
        np.testing.assert_allclose(features[:, 28],
                                   [0., standardized[0, 0], 0.,
                                    standardized[2, 0], standardized[3, 0]])
        np.testing.assert_array_equal(features[:, 49], [1., 0., 1., 0., 0.])
        np.testing.assert_allclose(features[:, :21], tau[:, None] * standardized)
        np.testing.assert_allclose(target, standardized)
        z = np.zeros((3, 21))
        time = np.zeros(3)
        conditions = np.zeros((3, 6))
        physical_previous = np.tile(y[0], (3, 1))
        # Start rows ignore even a spurious prior.
        first = model.velocity(z, time, conditions, physical_previous,
                               np.array([True, True, False]))
        np.testing.assert_array_equal(first[0], first[1])
        with self.assertRaises(ValueError):
            fit_synthetic_flow(y, x, np.array([0, 2, 2, 5]), mode="conditional")

    def test_small_unit_feature_keeps_its_standardized_signal(self):
        rng = np.random.default_rng(84)
        x = rng.normal(size=(192, 6))
        y = .8 * x[:, :1] + .2 * rng.normal(size=(192, 21))
        tiny = x.copy()
        tiny[:, 0] *= 5e-7
        offsets = np.arange(0, 193, 8)
        opts = dict(mode="conditional", seed=13, epochs=55, batch_size=48,
                    hidden_width=24)
        original = fit_synthetic_flow(y, x, offsets, **opts)
        scaled = fit_synthetic_flow(y, tiny, offsets, **opts)
        self.assertLess(scaled.condition_scale[0], 1e-6)
        np.testing.assert_allclose(scaled.condition_scale[0],
                                   original.condition_scale[0] * 5e-7)
        z, t, prev, starts = (np.zeros((2, 21)), np.full(2, .5),
                              np.zeros((2, 21)), np.ones(2, dtype=bool))
        probe = np.zeros((2, 6))
        probe[:, 0] = [-2 * original.condition_scale[0],
                        2 * original.condition_scale[0]]
        tiny_probe = probe.copy()
        tiny_probe[:, 0] *= 5e-7
        first = original.velocity(z, t, probe, prev, starts)
        second = scaled.velocity(z, t, tiny_probe, prev, starts)
        self.assertGreater(float(np.mean(np.abs(second[1] - second[0]))), .1)
        np.testing.assert_allclose(second, first, rtol=1e-10, atol=1e-10)
        self.assertEqual(scaled.condition_scale[1], original.condition_scale[1])
        constant = fit_synthetic_flow(np.zeros((2, 21)), np.zeros((2, 6)),
                                      np.array([0, 2]), mode="conditional", epochs=1)
        np.testing.assert_array_equal(constant.residual_scale, np.ones(21))
        np.testing.assert_array_equal(constant.condition_scale, np.ones(6))

    def test_conditional_field_can_learn_previous_residual_dependence(self):
        rng = np.random.default_rng(10)
        y = np.zeros((320, 21))
        x = np.zeros((320, 6))
        for start in range(0, 320, 8):
            for index in range(start, start + 8):
                y[index] = (.8 * y[index - 1] if index > start else 0) + rng.normal(0, .3)
        model = fit_synthetic_flow(y, x, np.arange(0, 321, 8), mode="conditional",
                                   seed=2, epochs=60, hidden_width=24)
        previous = np.vstack((-np.ones(21), np.ones(21)))
        velocity = model.velocity(np.zeros((2, 21)), np.ones(2) * .5,
                                  x[:2], previous, np.zeros(2, dtype=bool))
        self.assertGreater(velocity[1, 0] - velocity[0, 0], .5)
        at_start = model.velocity(np.zeros((2, 21)), np.ones(2) * .5,
                                  x[:2], previous, np.ones(2, dtype=bool))
        np.testing.assert_array_equal(at_start[0], at_start[1])

    def test_free_running_feedback_reset_and_padding_in_physical_units(self):
        # A hand-built tanh field makes the generated-history contract exact.
        w1 = np.zeros((50, 2))
        w1[28, 0] = 1  # standardized previous station zero
        w1[49, 1] = 1  # explicit start flag
        w2 = np.zeros((2, 21))
        w2[0, 0] = 1
        w2[1, 1] = 1
        model = SyntheticFlowModel("conditional", np.ones(21) * 2,
                                   np.ones(21) * 4, np.zeros(6), np.ones(6),
                                   w1, np.zeros(2), w2, np.zeros(21), ())
        x = np.zeros((2, 3, 6))
        out = model.sample(x, np.array([2, 1]), sample_count=1, seed=19, steps=4)
        base = np.random.default_rng(19).standard_normal((1, 2, 3, 21))
        np.testing.assert_allclose(out[0, 0, 0, 0], 2 + 4 * base[0, 0, 0, 0])
        np.testing.assert_allclose(out[0, 0, 1, 0],
                                   2 + 4 * (base[0, 0, 1, 0] + np.tanh(base[0, 0, 0, 0])))
        np.testing.assert_allclose(out[0, 1, 0, 0], 2 + 4 * base[0, 1, 0, 0])
        np.testing.assert_allclose(out[0, :, 0, 1],
                                   2 + 4 * (base[0, :, 0, 1] + np.tanh(1)))
        self.assertEqual(out[0, 0, 2, 0], 0.)
        self.assertEqual(out[0, 1, 1, 0], 0.)

    def test_solver_step_halving_converges_on_known_time_dependent_field(self):
        # The existing Euler solver can be checked without a fitted field.
        from lane_residuals.domain.flow_matching import integrate_euler

        def velocity(z, time, conditions, previous):
            return np.ones_like(z) * time[:, None]

        z = np.zeros((1, 21))
        x = np.zeros((1, 6))
        errors = [abs(integrate_euler(velocity, z, x, z, steps)[0, 0] - .5)
                  for steps in (4, 8, 16)]
        np.testing.assert_allclose(errors, [.125, .0625, .03125])

    def test_invalid_mode_values_and_training_controls_fail_closed(self):
        y, x = np.zeros((2, 21)), np.zeros((2, 6))
        for kwargs in ({"mode": "missing"}, {"mode": "conditional", "epochs": 0},
                       {"mode": "unconditional", "learning_rate": float("nan")},
                       {"mode": "conditional", "learning_rate": True},
                       {"mode": "conditional", "learning_rate": "0.01"},
                       {"mode": "conditional", "seed": None},
                       {"mode": "conditional", "seed": 1.5}):
            with self.assertRaises(ValueError):
                fit_synthetic_flow(y, x, np.array([0, 2]), **kwargs)
        model = fit_synthetic_flow(y, x, np.array([0, 2]), mode="unconditional", epochs=1)
        with self.assertRaises(ValueError):
            model.sample(x[None, :, :], np.array([2]), sample_count=1, seed=1, steps=0)
        for invalid_seed in (None, 1.5, -1):
            with self.assertRaises(ValueError):
                model.sample(x[None, :, :], np.array([2]), sample_count=1,
                             seed=invalid_seed)

    def test_direct_model_construction_validates_shapes_scales_and_copies(self):
        w1 = np.zeros((50, 2))
        model = SyntheticFlowModel("conditional", np.zeros(21), np.ones(21),
                                   np.zeros(6), np.ones(6), w1, np.zeros(2),
                                   np.zeros((2, 21)), np.zeros(21), ())
        w1[0, 0] = 7.
        self.assertEqual(model.weights_in[0, 0], 0.)
        self.assertFalse(model.weights_in.flags.writeable)
        invalid = (
            {"mode": "unknown"}, {"mode": ["conditional"]},
            {"residual_scale": np.zeros(21)},
            {"condition_scale": np.ones(6) * -1},
            {"condition_mean": np.zeros(5)},
            {"weights_in": np.zeros((22, 2))},
            {"weights_out": np.zeros((3, 21))},
            {"bias_out": np.full(21, np.nan)},
            {"training_losses": (float("nan"),)},
        )
        for change in invalid:
            with self.subTest(change=next(iter(change))):
                with self.assertRaises(ValueError):
                    replace(model, **change)

    def test_training_bridge_noise_time_are_paired_across_modes_and_widths(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=(32, 6))
        y = rng.normal(size=(32, 21))
        original = flow_module._training_inputs
        captured = []

        def capture(y_standard, x_standard, offsets, noise, time, mode):
            captured.append((noise.copy(), time.copy()))
            return original(y_standard, x_standard, offsets, noise, time, mode)

        with patch.object(flow_module, "_training_inputs", side_effect=capture):
            for mode, width in (("unconditional", 9), ("conditional", 17)):
                fit_synthetic_flow(y, x, np.arange(0, 33, 8), mode=mode,
                                   hidden_width=width, epochs=2, seed=46)
        for a, b in zip(captured[:2], captured[2:]):
            np.testing.assert_array_equal(a[0], b[0])
            np.testing.assert_array_equal(a[1], b[1])
        self.assertFalse(np.array_equal(captured[0][0], captured[1][0]))
        self.assertFalse(np.array_equal(captured[0][1], captured[1][1]))

    def test_velocity_gradients_match_finite_differences_in_both_modes(self):
        rng = np.random.default_rng(87)
        for input_width in (22, 50):
            with self.subTest(input_width=input_width):
                inputs = rng.normal(size=(4, input_width))
                targets = rng.normal(size=(4, 21))
                params = [rng.normal(size=(input_width, 3)) * .1,
                          rng.normal(size=3) * .1,
                          rng.normal(size=(3, 21)) * .1,
                          rng.normal(size=21) * .1]
                _, gradients = flow_module._batch_loss_and_gradients(
                    inputs, targets, params)

                def independent_loss() -> float:
                    w1, b1, w2, b2 = params
                    prediction = np.tanh(inputs @ w1 + b1) @ w2 + b2
                    return float(np.mean((prediction - targets) ** 2))

                for param, gradient in zip(params, gradients):
                    for index in list(np.ndindex(param.shape))[:3]:
                        original = param[index]
                        param[index] = original + 1e-6
                        upper = independent_loss()
                        param[index] = original - 1e-6
                        lower = independent_loss()
                        param[index] = original
                        np.testing.assert_allclose(gradient[index],
                                                   (upper - lower) / (2e-6),
                                                   rtol=2e-6, atol=1e-8)

    def test_learned_synthetic_field_euler_step_halving(self):
        rng = np.random.default_rng(55)
        x = rng.normal(size=(128, 6))
        y = .7 * x[:, :1] + .2 * rng.normal(size=(128, 21))
        conditions = rng.normal(size=(2, 4, 6))
        lengths = np.array([4, 2])
        for mode in ("unconditional", "conditional"):
            with self.subTest(mode=mode):
                model = fit_synthetic_flow(y, x, np.arange(0, 129, 8),
                                           mode=mode, seed=22, epochs=30,
                                           hidden_width=16)
                draws = [model.sample(conditions, lengths, sample_count=2,
                                      seed=42, steps=steps)
                         for steps in (4, 8, 16, 32)]
                distances = [float(np.sqrt(np.mean((left - right) ** 2)))
                             for left, right in zip(draws[:-1], draws[1:])]
                self.assertTrue(distances[0] > distances[1] > distances[2] > 0)


if __name__ == "__main__":
    unittest.main()
