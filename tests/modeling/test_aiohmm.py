import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from lane_residuals.domain.sequence_dataset import PaddedSequenceDataset
from lane_residuals.modeling.aiohmm import (
    AIOHMMConfig,
    AutoregressiveInputOutputHMM,
)


def _dataset(seed: int = 51) -> PaddedSequenceDataset:
    generator = np.random.default_rng(seed)
    sequence_count = 8
    length = 28
    feature_count = 6
    station_count = 21
    conditions = generator.normal(
        size=(sequence_count, length, feature_count)
    )
    residuals = np.zeros(
        (sequence_count, length, station_count), dtype=np.float64
    )
    slopes = generator.normal(scale=0.025, size=(2, feature_count, station_count))
    intercepts = np.vstack(
        (
            np.linspace(-0.15, 0.05, station_count),
            np.linspace(0.10, 0.30, station_count),
        )
    )
    autoregression = np.vstack(
        (
            np.linspace(0.55, 0.70, station_count),
            np.linspace(0.78, 0.90, station_count),
        )
    )
    covariance = 0.018 * np.eye(station_count)
    covariance += 0.006 * np.ones((station_count, station_count))
    cholesky = np.linalg.cholesky(covariance)
    for sequence_index in range(sequence_count):
        state = sequence_index % 2
        previous = np.zeros(station_count, dtype=np.float64)
        for time_index in range(length):
            condition = conditions[sequence_index, time_index]
            if time_index and generator.random() < 0.08:
                state = 1 - state
            mean = (
                intercepts[state]
                + condition @ slopes[state]
                + autoregression[state] * previous
            )
            value = mean + generator.standard_normal(station_count) @ cholesky.T
            residuals[sequence_index, time_index] = value
            previous = value
    pair_indices = np.tile(np.arange(length), (sequence_count, 1))
    return PaddedSequenceDataset(
        sequence_ids=[f"sequence_{index:03d}" for index in range(sequence_count)],
        recording_ids=[f"recording_{index:03d}" for index in range(sequence_count)],
        drive_ids=["drive_a"] * 4 + ["drive_b"] * 4,
        conditions=conditions,
        residuals_m=residuals,
        valid_mask=np.ones_like(residuals, dtype=np.bool_),
        lengths=np.full(sequence_count, length, dtype=np.int64),
        pair_indices=pair_indices,
        estimate_message_indices=pair_indices + 100,
        estimate_source_times_ns_private=(
            pair_indices * 80_000_000
            + np.arange(sequence_count)[:, None] * 10_000_000_000
            + 1_000_000_000
        ),
        standardized=True,
    )


def _config() -> AIOHMMConfig:
    return AIOHMMConfig(
        state_count=2,
        maximum_em_iterations=6,
        minimum_em_iterations=2,
        convergence_tolerance=1e-5,
        regression_ridge_penalty=1e-3,
        state_covariance_pooling=0.5,
        covariance_diagonal_shrinkage=0.1,
        covariance_minimum_eigenvalue=1e-5,
        minimum_effective_state_observations=2.0,
        maximum_absolute_autoregression=0.95,
        transition_l2_penalty=1e-3,
        transition_learning_rate=0.03,
        transition_adam_steps=6,
        initial_probability_smoothing=0.01,
        minimum_state_occupancy_fraction=0.001,
        initialization_seed=177,
    )


class AIOHMMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset = _dataset()
        cls.training = dataset.select_drive_ids(("drive_a",))
        cls.validation = dataset.select_drive_ids(("drive_b",))
        cls.model = AutoregressiveInputOutputHMM(_config())
        cls.report = cls.model.fit(cls.training, cls.validation)

    def test_fit_density_and_posterior_contract(self) -> None:
        log_probability = self.model.log_probability(self.validation)
        sequence_log_probability = self.model.sequence_log_probability(
            self.validation
        )
        posteriors = self.model.posterior_state_probabilities(self.validation)

        self.assertTrue(self.model.is_fitted)
        self.assertEqual(self.report.training_sequence_count, 4)
        self.assertEqual(self.report.validation_sequence_count, 4)
        self.assertEqual(log_probability.shape, (4, 28))
        np.testing.assert_allclose(
            np.sum(log_probability, axis=1), sequence_log_probability
        )
        self.assertTrue(np.all(np.isfinite(log_probability)))
        self.assertEqual(len(posteriors), 4)
        for posterior in posteriors:
            self.assertEqual(posterior.shape, (28, 2))
            np.testing.assert_allclose(np.sum(posterior, axis=1), 1.0)
        self.assertIn(
            "validation_mean_joint_negative_log_likelihood_standardized",
            self.report.metrics,
        )
        self.assertTrue(
            np.all(np.diff(self.model.state_profile_rms_standardized) >= 0.0)
        )
        history = self.model.log_likelihood_history
        self.assertTrue(
            np.all(np.diff(history) >= -1e-9 * np.maximum(np.abs(history[:-1]), 1.0))
        )
        self.assertIn("em_backtracked_m_step_count", self.report.metrics)
        self.assertIn("em_rejected_m_step_count", self.report.metrics)

    def test_state_specific_emissions_exclude_sequence_reset_frames(self) -> None:
        conditions, residuals, previous, dynamic_mask = (
            AutoregressiveInputOutputHMM._flatten_training_arrays(self.training)
        )

        self.assertEqual(len(dynamic_mask), self.training.frame_count)
        self.assertEqual(int(np.sum(~dynamic_mask)), self.training.sequence_count)
        reset_indices = np.cumsum(
            np.concatenate(([0], self.training.lengths[:-1]))
        )
        np.testing.assert_array_equal(
            dynamic_mask[reset_indices],
            np.zeros(self.training.sequence_count, dtype=np.bool_),
        )
        np.testing.assert_array_equal(
            previous[reset_indices],
            np.zeros((self.training.sequence_count, 21), dtype=np.float64),
        )
        self.assertEqual(conditions.shape[0], residuals.shape[0])

    def test_sampling_is_free_running_deterministic_and_persistent(self) -> None:
        first = self.model.sample(
            self.validation.conditions,
            self.validation.lengths,
            sample_count=5,
            seed=91,
            valid_mask=self.validation.valid_mask,
        )
        second = self.model.sample(
            self.validation.conditions,
            self.validation.lengths,
            sample_count=5,
            seed=91,
            valid_mask=self.validation.valid_mask,
        )
        np.testing.assert_array_equal(first.values, second.values)
        self.assertEqual(first.values.shape, (5, 4, 28, 21))
        self.assertFalse(np.allclose(first.values[:, :, 0], first.values[:, :, 1]))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aiohmm.json"
            self.model.save(path)
            restored = AutoregressiveInputOutputHMM.load(path)
        np.testing.assert_allclose(
            restored.log_probability(self.validation),
            self.model.log_probability(self.validation),
            rtol=0.0,
            atol=0.0,
        )
        np.testing.assert_array_equal(
            restored.sample(
                self.validation.conditions,
                self.validation.lengths,
                sample_count=5,
                seed=91,
                valid_mask=self.validation.valid_mask,
            ).values,
            first.values,
        )

    def test_one_state_is_exact_conditional_ar_ablation(self) -> None:
        config = _config()
        config = AIOHMMConfig.from_dict(
            {
                **config.to_dict(),
                "state_count": 1,
                "input_dependent_transitions": False,
            }
        )
        first = AutoregressiveInputOutputHMM(config)
        report = first.fit(self.training, self.validation)
        second = AutoregressiveInputOutputHMM(
            AIOHMMConfig.from_dict(
                {**config.to_dict(), "initialization_seed": 9127}
            )
        )
        second.fit(self.training, self.validation)

        self.assertFalse(first.has_latent_state_switching)
        self.assertTrue(report.metrics["em_converged"])
        np.testing.assert_allclose(first.initial_probabilities, [1.0])
        np.testing.assert_allclose(first.state_occupancies, [1.0])
        np.testing.assert_allclose(
            first.posterior_state_probabilities(self.validation)[0],
            np.ones((28, 1)),
        )
        np.testing.assert_allclose(
            first.log_probability(self.validation),
            second.log_probability(self.validation),
            rtol=0.0,
            atol=0.0,
        )
        self.assertFalse(first.to_dict()["latent_state_switching"])

    def test_multistate_decreasing_tail_is_not_reported_converged(self) -> None:
        model = AutoregressiveInputOutputHMM(_config())
        original_expectation = model._expectation
        controlled_totals = (100.0, 100.0 - 1e-6)
        expectation_count = 0

        def controlled_expectation(
            dataset: PaddedSequenceDataset,
        ):
            nonlocal expectation_count
            result = original_expectation(dataset)
            if expectation_count >= len(controlled_totals):
                return result
            total = controlled_totals[expectation_count]
            expectation_count += 1
            return replace(
                result,
                sequence_log_probabilities=np.full(
                    dataset.sequence_count,
                    total / dataset.sequence_count,
                    dtype=np.float64,
                ),
            )

        def retain_current_state(
            _dataset: PaddedSequenceDataset,
            *,
            current_state,
            proposed_state,
            current_log_probability: float,
        ):
            del proposed_state, current_log_probability
            return current_state, 0

        with patch.object(
            model, "_expectation", side_effect=controlled_expectation
        ), patch.object(
            model, "_backtracked_m_step", side_effect=retain_current_state
        ):
            report = model.fit(self.training, self.validation)

        self.assertEqual(model.to_dict()["best_iteration_index"], 0)
        self.assertEqual(len(model.log_likelihood_history), 2)
        self.assertFalse(model.to_dict()["converged"])
        self.assertEqual(report.metrics["em_converged"], 0.0)
        self.assertIn(
            "EM did not reach the configured convergence tolerance.",
            report.warnings,
        )

    def test_configuration_rejects_unstable_or_empty_state_models(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            AIOHMMConfig(state_count=0)
        with self.assertRaisesRegex(ValueError, "strictly inside"):
            AIOHMMConfig(maximum_absolute_autoregression=1.0)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            AIOHMMConfig(emission_parameter_pooling_penalty=-1.0)


if __name__ == "__main__":
    unittest.main()
