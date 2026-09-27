"""Synthetic engineering checks only; never use a recorded driving archive."""

from __future__ import annotations

import unittest

import numpy as np

from lane_residuals.modeling.flow_matching import SyntheticFlowModel, fit_synthetic_flow


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

    def test_conditioned_offsets_reset_observed_predecessor_and_distinguish_start(self):
        # The supplied offsets are for *these* complete rows, never geometric-row indices.
        y = np.arange(1., 6.)[:, None] * np.ones((1, 21))
        x = np.zeros((5, 6))
        model = fit_synthetic_flow(y, x, np.array([0, 2, 5]),
                                   mode="conditional", epochs=1, seed=2)
        self.assertAlmostEqual(model.residual_mean[0], 3.)
        z = np.zeros((3, 21))
        time = np.zeros(3)
        conditions = np.zeros((3, 6))
        physical_previous = np.tile(y[0], (3, 1))
        # Start rows ignore even a spurious prior; non-start rows encode it.
        first = model.velocity(z, time, conditions, physical_previous,
                               np.array([True, True, False]))
        np.testing.assert_array_equal(first[0], first[1])
        with self.assertRaises(ValueError):
            fit_synthetic_flow(y, x, np.array([0, 2, 2, 5]), mode="conditional")

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
                       {"mode": "unconditional", "learning_rate": float("nan")}):
            with self.assertRaises(ValueError):
                fit_synthetic_flow(y, x, np.array([0, 2]), **kwargs)
        model = fit_synthetic_flow(y, x, np.array([0, 2]), mode="unconditional", epochs=1)
        with self.assertRaises(ValueError):
            model.sample(x[None, :, :], np.array([2]), sample_count=1, seed=1, steps=0)


if __name__ == "__main__":
    unittest.main()
