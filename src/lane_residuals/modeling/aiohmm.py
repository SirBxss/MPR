"""Autoregressive input-output HMM for the MPR v0.11 sequence contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping, Self

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    PaddedSequenceDataset,
)
from .aiohmm_inference import (
    ForwardBackwardResult,
    forward_backward,
    log_softmax,
    transition_log_probabilities,
)
from .base import (
    FitReport,
    ModelCapabilities,
    ProbabilisticSequenceModel,
    SampleResult,
)

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]
BooleanArray = NDArray[np.bool_]
VERSION = "0.11.0"


def _strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


@dataclass(frozen=True)
class AIOHMMConfig:
    """Structural and numerical choices for one deterministic generalized-EM run.

    The v0.11 default has three states. Each state has a conditional linear
    mean, station-wise AR(1) coefficients, and a full spatial covariance.
    Rare-state emission parameters are pooled toward one shared AR regression,
    while covariances are pooled and shrunk because the development corpus
    contains only two physical drives.
    """

    state_count: int = 3
    maximum_em_iterations: int = 30
    minimum_em_iterations: int = 5
    convergence_tolerance: float = 1e-4
    regression_ridge_penalty: float = 1e-3
    emission_parameter_pooling_penalty: float = 10.0
    state_covariance_pooling: float = 0.50
    covariance_diagonal_shrinkage: float = 0.15
    covariance_minimum_eigenvalue: float = 1e-5
    minimum_effective_state_observations: float = 10.0
    maximum_absolute_autoregression: float = 0.98
    transition_l2_penalty: float = 1e-3
    transition_learning_rate: float = 0.03
    transition_adam_steps: int = 30
    initial_probability_smoothing: float = 1e-2
    minimum_state_occupancy_fraction: float = 0.01
    initialization_seed: int = 20260820
    input_dependent_transitions: bool = True

    def __post_init__(self) -> None:
        integer_fields = (
            "state_count",
            "maximum_em_iterations",
            "minimum_em_iterations",
            "transition_adam_steps",
            "initialization_seed",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise TypeError(f"{name} must be an integer")
        if self.state_count < 2:
            raise ValueError("state_count must be at least two")
        if self.maximum_em_iterations < 1:
            raise ValueError("maximum_em_iterations must be positive")
        if not 1 <= self.minimum_em_iterations <= self.maximum_em_iterations:
            raise ValueError(
                "minimum_em_iterations must lie between one and the maximum"
            )
        if self.transition_adam_steps < 1:
            raise ValueError("transition_adam_steps must be positive")
        if self.initialization_seed < 0:
            raise ValueError("initialization_seed must be nonnegative")

        numeric_fields = (
            "convergence_tolerance",
            "regression_ridge_penalty",
            "emission_parameter_pooling_penalty",
            "state_covariance_pooling",
            "covariance_diagonal_shrinkage",
            "covariance_minimum_eigenvalue",
            "minimum_effective_state_observations",
            "maximum_absolute_autoregression",
            "transition_l2_penalty",
            "transition_learning_rate",
            "initial_probability_smoothing",
            "minimum_state_occupancy_fraction",
        )
        for name in numeric_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(
                value, (int, float, np.integer, np.floating)
            ):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.convergence_tolerance <= 0.0:
            raise ValueError("convergence_tolerance must be positive")
        if (
            self.regression_ridge_penalty < 0.0
            or self.emission_parameter_pooling_penalty < 0.0
            or self.transition_l2_penalty < 0.0
        ):
            raise ValueError("regularization penalties must be nonnegative")
        if not 0.0 <= self.state_covariance_pooling <= 1.0:
            raise ValueError("state_covariance_pooling must lie in [0,1]")
        if not 0.0 <= self.covariance_diagonal_shrinkage <= 1.0:
            raise ValueError("covariance_diagonal_shrinkage must lie in [0,1]")
        if self.covariance_minimum_eigenvalue <= 0.0:
            raise ValueError("covariance_minimum_eigenvalue must be positive")
        if self.minimum_effective_state_observations < 2.0:
            raise ValueError(
                "minimum_effective_state_observations must be at least two"
            )
        if not 0.0 < self.maximum_absolute_autoregression < 1.0:
            raise ValueError(
                "maximum_absolute_autoregression must lie strictly inside (0,1)"
            )
        if self.transition_learning_rate <= 0.0:
            raise ValueError("transition_learning_rate must be positive")
        if self.initial_probability_smoothing <= 0.0:
            raise ValueError("initial_probability_smoothing must be positive")
        if not 0.0 < self.minimum_state_occupancy_fraction < 1.0:
            raise ValueError(
                "minimum_state_occupancy_fraction must lie strictly inside (0,1)"
            )
        if not isinstance(self.input_dependent_transitions, bool):
            raise TypeError("input_dependent_transitions must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AIOHMMConfig":
        unknown = set(payload) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(
                f"unknown AIOHMM configuration fields: {sorted(unknown)}"
            )
        return cls(**dict(payload))


@dataclass(frozen=True)
class _AIOHMMState:
    feature_names: tuple[str, ...]
    stations_m: tuple[float, ...]
    initial_probabilities: FloatArray
    initial_emission_coefficients: FloatArray
    initial_emission_covariance: FloatArray
    transition_weights: FloatArray
    emission_coefficients: FloatArray
    autoregressive_coefficients: FloatArray
    covariances: FloatArray
    state_occupancies: FloatArray
    log_likelihood_history: FloatArray
    training_sequence_count: int
    training_frame_count: int
    best_iteration_index: int
    converged: bool


@dataclass(frozen=True)
class _ExpectationResult:
    sequence_log_probabilities: FloatArray
    posteriors: tuple[ForwardBackwardResult, ...]


def _regularize_covariance(
    covariance: FloatArray,
    *,
    diagonal_shrinkage: float,
    minimum_eigenvalue: float,
) -> FloatArray:
    diagonal = np.diag(np.diag(covariance))
    result = (
        (1.0 - diagonal_shrinkage) * covariance
        + diagonal_shrinkage * diagonal
    )
    result = 0.5 * (result + result.T)
    eigenvalues, eigenvectors = np.linalg.eigh(result)
    result = (
        eigenvectors * np.maximum(eigenvalues, minimum_eigenvalue)
    ) @ eigenvectors.T
    return 0.5 * (result + result.T)


class AutoregressiveInputOutputHMM(ProbabilisticSequenceModel):
    r"""Three-state default AIOHMM on standardized MPR sequences.

    For state :math:`z_t`, condition vector :math:`x_t`, and residual profile
    :math:`y_t`:

    .. math::
       p(z_t=j\mid z_{t-1}=i,x_t)=\operatorname{softmax}_j(W_i[1,x_t]),

    .. math::
       y_t\mid z_t=k,x_t,y_{t-1}\sim
       \mathcal N(B_k^T[1,x_t]+d_k\odot y_{t-1},\Sigma_k).

    The AR matrix is diagonal, retaining one persistence coefficient per H100
    station. This state-dependent equation applies after the sequence start.
    At ``t=0``, a state-independent conditional Gaussian marginal fitted on all
    training frames supplies a data-supported reset prior; only 6--7 starts are
    available in a held-out fold, so a separate full start covariance would be
    unidentified. Density evaluation is teacher-forced; sampling is free-running.
    Sequences are never joined or interpolated by the model.
    """

    def __init__(self, config: AIOHMMConfig | None = None) -> None:
        self.config = config or AIOHMMConfig()
        self._state: _AIOHMMState | None = None
        self._cholesky_factors: FloatArray | None = None
        self._initial_cholesky_factor: FloatArray | None = None

    @property
    def model_name(self) -> str:
        return "autoregressive_input_output_hmm"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_log_probability=True,
            supports_missing_targets=False,
            supports_variable_length=True,
        )

    @property
    def is_fitted(self) -> bool:
        return self._state is not None

    @property
    def temporal_dependency_order(self) -> int:
        return 1

    def _require_state(self) -> _AIOHMMState:
        if self._state is None:
            raise ValueError("AIOHMM is not fitted")
        return self._state

    @property
    def initial_probabilities(self) -> FloatArray:
        return self._require_state().initial_probabilities.copy()

    @property
    def transition_weights(self) -> FloatArray:
        return self._require_state().transition_weights.copy()

    @property
    def emission_coefficients(self) -> FloatArray:
        return self._require_state().emission_coefficients.copy()

    @property
    def autoregressive_coefficients(self) -> FloatArray:
        return self._require_state().autoregressive_coefficients.copy()

    @property
    def covariances(self) -> FloatArray:
        return self._require_state().covariances.copy()

    @property
    def state_occupancies(self) -> FloatArray:
        return self._require_state().state_occupancies.copy()

    @property
    def log_likelihood_history(self) -> FloatArray:
        return self._require_state().log_likelihood_history.copy()

    @property
    def state_profile_rms_standardized(self) -> FloatArray:
        intercepts = self._require_state().emission_coefficients[:, 0, :]
        return np.sqrt(np.mean(np.square(intercepts), axis=1))

    def _validated_state(self, state: _AIOHMMState) -> _AIOHMMState:
        state_count = self.config.state_count
        feature_count = len(BMW_CONDITION_FEATURE_NAMES)
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        if state.feature_names != BMW_CONDITION_FEATURE_NAMES:
            raise ValueError("AIOHMM feature contract is not BMW schema v1")
        if state.stations_m != CANONICAL_MODEL_STATIONS_M:
            raise ValueError("AIOHMM station grid is not canonical H100")
        expected_shapes = (
            (state.initial_probabilities, (state_count,), "initial probabilities"),
            (
                state.initial_emission_coefficients,
                (feature_count + 1, station_count),
                "initial emission coefficients",
            ),
            (
                state.initial_emission_covariance,
                (station_count, station_count),
                "initial emission covariance",
            ),
            (
                state.transition_weights,
                (state_count, state_count, feature_count + 1),
                "transition weights",
            ),
            (
                state.emission_coefficients,
                (state_count, feature_count + 1, station_count),
                "emission coefficients",
            ),
            (
                state.autoregressive_coefficients,
                (state_count, station_count),
                "autoregressive coefficients",
            ),
            (
                state.covariances,
                (state_count, station_count, station_count),
                "covariances",
            ),
            (state.state_occupancies, (state_count,), "state occupancies"),
        )
        for values, shape, name in expected_shapes:
            if values.shape != shape:
                raise ValueError(f"{name} have shape {values.shape}, expected {shape}")
        arrays = [values for values, _shape, _name in expected_shapes]
        arrays.append(state.log_likelihood_history)
        if state.log_likelihood_history.ndim != 1:
            raise ValueError("log-likelihood history must be one-dimensional")
        if not all(np.all(np.isfinite(values)) for values in arrays):
            raise ValueError("fitted AIOHMM state must be finite")
        if np.any(state.initial_probabilities <= 0.0) or not np.isclose(
            np.sum(state.initial_probabilities), 1.0, atol=1e-10
        ):
            raise ValueError("initial probabilities must be positive and sum to one")
        if np.any(state.state_occupancies < 0.0) or not np.isclose(
            np.sum(state.state_occupancies), 1.0, atol=1e-10
        ):
            raise ValueError("state occupancies must be nonnegative and sum to one")
        if np.max(np.abs(state.autoregressive_coefficients)) > (
            self.config.maximum_absolute_autoregression + 1e-10
        ):
            raise ValueError("autoregressive stability bound is violated")
        for covariance in state.covariances:
            if not np.allclose(covariance, covariance.T, atol=1e-10, rtol=0.0):
                raise ValueError("state covariance must be symmetric")
            if np.min(np.linalg.eigvalsh(covariance)) < (
                self.config.covariance_minimum_eigenvalue - 1e-10
            ):
                raise ValueError("state covariance violates the eigenvalue floor")
        if not np.allclose(
            state.initial_emission_covariance,
            state.initial_emission_covariance.T,
            atol=1e-10,
            rtol=0.0,
        ):
            raise ValueError("initial emission covariance must be symmetric")
        if np.min(np.linalg.eigvalsh(state.initial_emission_covariance)) < (
            self.config.covariance_minimum_eigenvalue - 1e-10
        ):
            raise ValueError("initial emission covariance violates the eigenvalue floor")
        if state.training_sequence_count < 1 or state.training_frame_count < 2:
            raise ValueError("AIOHMM training counts are invalid")
        if state.best_iteration_index < 0:
            raise ValueError("best iteration index must be nonnegative")
        if not isinstance(state.converged, bool):
            raise TypeError("converged flag must be boolean")
        return state

    def _set_state(self, state: _AIOHMMState) -> None:
        state = self._validated_state(state)
        self._state = state
        self._cholesky_factors = np.stack(
            [np.linalg.cholesky(covariance) for covariance in state.covariances]
        )
        self._initial_cholesky_factor = np.linalg.cholesky(
            state.initial_emission_covariance
        )

    @staticmethod
    def _canonicalized_state(state: _AIOHMMState) -> _AIOHMMState:
        """Apply a deterministic diagnostic label order to exchangeable states."""

        intercept = state.emission_coefficients[:, 0, :]
        rms = np.sqrt(np.mean(np.square(intercept), axis=1))
        mean = np.mean(intercept, axis=1)
        ar = np.median(state.autoregressive_coefficients, axis=1)
        order = np.lexsort((ar, mean, rms))
        return replace(
            state,
            initial_probabilities=state.initial_probabilities[order],
            transition_weights=state.transition_weights[order][:, order],
            emission_coefficients=state.emission_coefficients[order],
            autoregressive_coefficients=state.autoregressive_coefficients[order],
            covariances=state.covariances[order],
            state_occupancies=state.state_occupancies[order],
        )

    @staticmethod
    def _copy_state(state: _AIOHMMState) -> _AIOHMMState:
        return replace(
            state,
            initial_probabilities=state.initial_probabilities.copy(),
            initial_emission_coefficients=(
                state.initial_emission_coefficients.copy()
            ),
            initial_emission_covariance=(
                state.initial_emission_covariance.copy()
            ),
            transition_weights=state.transition_weights.copy(),
            emission_coefficients=state.emission_coefficients.copy(),
            autoregressive_coefficients=state.autoregressive_coefficients.copy(),
            covariances=state.covariances.copy(),
            state_occupancies=state.state_occupancies.copy(),
            log_likelihood_history=state.log_likelihood_history.copy(),
        )

    @staticmethod
    def _previous_values(residuals: FloatArray) -> FloatArray:
        previous = np.zeros_like(residuals, dtype=np.float64)
        if len(residuals) > 1:
            previous[1:] = residuals[:-1]
        return previous

    @staticmethod
    def _require_complete_standardized(dataset: PaddedSequenceDataset) -> None:
        if not dataset.standardized:
            raise ValueError("AIOHMM requires training-standardized data")
        if not np.all(dataset.valid_mask[dataset.time_mask]):
            raise ValueError("AIOHMM v0.11 requires complete active H100 targets")

    def _validate_compatible_dataset(self, dataset: PaddedSequenceDataset) -> None:
        self._require_complete_standardized(dataset)
        state = self._require_state()
        if dataset.feature_names != state.feature_names:
            raise ValueError("dataset features differ from the fitted AIOHMM")
        if dataset.stations_m != state.stations_m:
            raise ValueError("dataset station grid differs from the fitted AIOHMM")

    def _sequence_emission_log_probabilities(
        self,
        conditions: FloatArray,
        residuals: FloatArray,
    ) -> FloatArray:
        state = self._require_state()
        design = np.column_stack(
            (np.ones(len(conditions), dtype=np.float64), conditions)
        )
        previous = self._previous_values(residuals)
        means = np.einsum(
            "tp,spk->tsk", design, state.emission_coefficients, optimize=True
        )
        means += (
            previous[:, None, :]
            * state.autoregressive_coefficients[None, :, :]
        )
        if self._cholesky_factors is None:
            raise RuntimeError("AIOHMM covariance factors are unavailable")
        normalization_constant = len(state.stations_m) * np.log(2.0 * np.pi)
        log_emission = np.empty(
            (len(conditions), self.config.state_count), dtype=np.float64
        )
        for state_index in range(self.config.state_count):
            differences = residuals - means[:, state_index]
            cholesky = self._cholesky_factors[state_index]
            whitened = np.linalg.solve(cholesky, differences.T)
            normalization = normalization_constant + 2.0 * float(
                np.sum(np.log(np.diag(cholesky)))
            )
            log_emission[:, state_index] = -0.5 * (
                normalization + np.sum(np.square(whitened), axis=0)
            )
        if self._initial_cholesky_factor is None:
            raise RuntimeError("AIOHMM initial covariance factor is unavailable")
        initial_mean = design[0] @ state.initial_emission_coefficients
        initial_difference = residuals[0] - initial_mean
        initial_whitened = np.linalg.solve(
            self._initial_cholesky_factor, initial_difference
        )
        initial_normalization = normalization_constant + 2.0 * float(
            np.sum(np.log(np.diag(self._initial_cholesky_factor)))
        )
        initial_log_probability = -0.5 * (
            initial_normalization + float(initial_whitened @ initial_whitened)
        )
        log_emission[0, :] = initial_log_probability
        return log_emission

    def _expectation(self, dataset: PaddedSequenceDataset) -> _ExpectationResult:
        self._validate_compatible_dataset(dataset)
        state = self._require_state()
        log_initial = np.log(state.initial_probabilities)
        results: list[ForwardBackwardResult] = []
        sequence_log_probabilities = np.empty(
            dataset.sequence_count, dtype=np.float64
        )
        for sequence_index, raw_length in enumerate(dataset.lengths):
            length = int(raw_length)
            conditions = np.asarray(
                dataset.conditions[sequence_index, :length], dtype=np.float64
            )
            residuals = np.asarray(
                dataset.residuals_m[sequence_index, :length], dtype=np.float64
            )
            log_emission = self._sequence_emission_log_probabilities(
                conditions, residuals
            )
            log_transition = transition_log_probabilities(
                conditions,
                state.transition_weights,
                input_dependent=self.config.input_dependent_transitions,
            )
            posterior = forward_backward(
                log_initial, log_transition, log_emission
            )
            results.append(posterior)
            sequence_log_probabilities[sequence_index] = posterior.log_probability
        return _ExpectationResult(
            sequence_log_probabilities=sequence_log_probabilities,
            posteriors=tuple(results),
        )

    @staticmethod
    def _flatten_training_arrays(
        dataset: PaddedSequenceDataset,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        conditions: list[FloatArray] = []
        residuals: list[FloatArray] = []
        previous: list[FloatArray] = []
        for sequence_index, raw_length in enumerate(dataset.lengths):
            length = int(raw_length)
            sequence_residuals = np.asarray(
                dataset.residuals_m[sequence_index, :length], dtype=np.float64
            )
            conditions.append(
                np.asarray(
                    dataset.conditions[sequence_index, :length], dtype=np.float64
                )
            )
            residuals.append(sequence_residuals)
            previous.append(
                AutoregressiveInputOutputHMM._previous_values(sequence_residuals)
            )
        return (
            np.concatenate(conditions, axis=0),
            np.concatenate(residuals, axis=0),
            np.concatenate(previous, axis=0),
        )

    def _fit_initial_emission(
        self,
        conditions: FloatArray,
        residuals: FloatArray,
    ) -> tuple[FloatArray, FloatArray]:
        """Fit a training-only marginal prior used at every sequence reset.

        Only 6--7 sequence starts exist in a drive-held-out fold. Estimating a
        separate 21-dimensional start covariance from those rows would be
        singular and unstable, so the reset prior is the state-independent
        conditional Gaussian marginal fitted on all training frames. Later
        frames remain state-dependent and autoregressive.
        """

        design = np.column_stack(
            (np.ones(len(conditions), dtype=np.float64), conditions)
        )
        ridge = np.eye(design.shape[1], dtype=np.float64)
        ridge[0, 0] = 0.0
        ridge *= self.config.regression_ridge_penalty
        gram = design.T @ design + ridge
        right_hand_side = design.T @ residuals
        try:
            coefficients = np.linalg.solve(gram, right_hand_side)
        except np.linalg.LinAlgError:
            coefficients = np.linalg.lstsq(gram, right_hand_side, rcond=None)[0]
        differences = residuals - design @ coefficients
        covariance = differences.T @ differences / len(differences)
        covariance = _regularize_covariance(
            covariance,
            diagonal_shrinkage=self.config.covariance_diagonal_shrinkage,
            minimum_eigenvalue=self.config.covariance_minimum_eigenvalue,
        )
        return coefficients, covariance

    def _optimize_transition_weights(
        self,
        dataset: PaddedSequenceDataset,
        transition_posteriors: tuple[FloatArray, ...],
        initial_weights: FloatArray,
    ) -> FloatArray:
        designs: list[FloatArray] = []
        counts: list[FloatArray] = []
        for sequence_index, raw_length in enumerate(dataset.lengths):
            length = int(raw_length)
            if length <= 1:
                continue
            condition = np.asarray(
                dataset.conditions[sequence_index, 1:length], dtype=np.float64
            )
            design = np.column_stack(
                (np.ones(len(condition), dtype=np.float64), condition)
            )
            if not self.config.input_dependent_transitions:
                design[:, 1:] = 0.0
            designs.append(design)
            counts.append(transition_posteriors[sequence_index])
        if not designs:
            return initial_weights.copy()
        design = np.concatenate(designs, axis=0)
        transition_counts = np.concatenate(counts, axis=0)
        weights = initial_weights.copy()
        beta_one = 0.9
        beta_two = 0.999
        epsilon = 1e-8
        for source_state in range(self.config.state_count):
            source_counts = transition_counts[:, source_state, :]
            source_mass = np.sum(source_counts, axis=1)
            total_mass = float(np.sum(source_mass))
            if total_mass <= np.finfo(np.float64).eps:
                continue
            current = weights[source_state].copy()
            first_moment = np.zeros_like(current)
            second_moment = np.zeros_like(current)
            best = current.copy()
            best_objective = -np.inf
            for step in range(1, self.config.transition_adam_steps + 1):
                logits = design @ current.T
                log_probabilities = log_softmax(logits, axis=1)
                probabilities = np.exp(log_probabilities)
                objective = float(
                    np.sum(source_counts * log_probabilities) / total_mass
                    - 0.5
                    * self.config.transition_l2_penalty
                    * np.sum(np.square(current[:, 1:]))
                )
                if objective > best_objective:
                    best_objective = objective
                    best = current.copy()
                gradient = (
                    (source_counts - source_mass[:, None] * probabilities).T
                    @ design
                ) / total_mass
                gradient[:, 1:] -= (
                    self.config.transition_l2_penalty * current[:, 1:]
                )
                first_moment = (
                    beta_one * first_moment + (1.0 - beta_one) * gradient
                )
                second_moment = (
                    beta_two * second_moment
                    + (1.0 - beta_two) * np.square(gradient)
                )
                corrected_first = first_moment / (1.0 - beta_one**step)
                corrected_second = second_moment / (1.0 - beta_two**step)
                current += self.config.transition_learning_rate * (
                    corrected_first / (np.sqrt(corrected_second) + epsilon)
                )
                current -= np.mean(current, axis=0, keepdims=True)
                if not self.config.input_dependent_transitions:
                    current[:, 1:] = 0.0
            weights[source_state] = best
        return weights

    def _m_step(
        self,
        dataset: PaddedSequenceDataset,
        state_posteriors: tuple[FloatArray, ...],
        transition_posteriors: tuple[FloatArray, ...],
        previous_state: _AIOHMMState | None,
    ) -> _AIOHMMState:
        conditions, residuals, previous_values = self._flatten_training_arrays(
            dataset
        )
        gamma = np.concatenate(state_posteriors, axis=0)
        state_count = self.config.state_count
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        base_design = np.column_stack(
            (np.ones(len(conditions), dtype=np.float64), conditions)
        )
        coefficient_count = base_design.shape[1]
        emission_coefficients = np.empty(
            (state_count, coefficient_count, station_count), dtype=np.float64
        )
        autoregressive_coefficients = np.empty(
            (state_count, station_count), dtype=np.float64
        )
        raw_covariances = np.empty(
            (state_count, station_count, station_count), dtype=np.float64
        )
        effective_counts = np.sum(gamma, axis=0)
        regression_ridge = np.eye(coefficient_count + 1, dtype=np.float64)
        regression_ridge[0, 0] = 0.0
        regression_ridge *= self.config.regression_ridge_penalty
        shared_coefficients = np.empty(
            (coefficient_count + 1, station_count), dtype=np.float64
        )
        for station_index in range(station_count):
            shared_design = np.column_stack(
                (base_design, previous_values[:, station_index])
            )
            shared_gram = shared_design.T @ shared_design + regression_ridge
            shared_right_hand_side = shared_design.T @ residuals[:, station_index]
            try:
                shared = np.linalg.solve(
                    shared_gram, shared_right_hand_side
                )
            except np.linalg.LinAlgError:
                shared = np.linalg.lstsq(
                    shared_gram, shared_right_hand_side, rcond=None
                )[0]
            shared[-1] = np.clip(
                shared[-1],
                -self.config.maximum_absolute_autoregression,
                self.config.maximum_absolute_autoregression,
            )
            shared_coefficients[:, station_index] = shared
        pooling = (
            self.config.emission_parameter_pooling_penalty
            * np.eye(coefficient_count + 1, dtype=np.float64)
        )

        for state_index in range(state_count):
            weights = gamma[:, state_index]
            effective_count = float(effective_counts[state_index])
            if effective_count < self.config.minimum_effective_state_observations:
                raise ValueError(
                    f"state {state_index} has only {effective_count:.3f} "
                    "effective observations"
                )
            square_root_weights = np.sqrt(weights)
            for station_index in range(station_count):
                station_design = np.column_stack(
                    (base_design, previous_values[:, station_index])
                )
                weighted_design = station_design * square_root_weights[:, None]
                weighted_target = residuals[:, station_index] * square_root_weights
                gram = (
                    weighted_design.T @ weighted_design
                    + regression_ridge
                    + pooling
                )
                right_hand_side = (
                    weighted_design.T @ weighted_target
                    + self.config.emission_parameter_pooling_penalty
                    * shared_coefficients[:, station_index]
                )
                try:
                    coefficients = np.linalg.solve(gram, right_hand_side)
                except np.linalg.LinAlgError:
                    coefficients = np.linalg.lstsq(
                        gram, right_hand_side, rcond=None
                    )[0]
                emission_coefficients[
                    state_index, :, station_index
                ] = coefficients[:-1]
                autoregressive_coefficients[
                    state_index, station_index
                ] = np.clip(
                    coefficients[-1],
                    -self.config.maximum_absolute_autoregression,
                    self.config.maximum_absolute_autoregression,
                )
            means = base_design @ emission_coefficients[state_index]
            means += (
                previous_values
                * autoregressive_coefficients[state_index][None, :]
            )
            differences = residuals - means
            weighted = differences * square_root_weights[:, None]
            raw_covariances[state_index] = (
                weighted.T @ weighted / effective_count
            )

        occupancy_weights = effective_counts / np.sum(effective_counts)
        pooled_covariance = np.einsum(
            "s,sij->ij", occupancy_weights, raw_covariances, optimize=True
        )
        covariances = np.empty_like(raw_covariances)
        for state_index in range(state_count):
            pooled = (
                (1.0 - self.config.state_covariance_pooling)
                * raw_covariances[state_index]
                + self.config.state_covariance_pooling * pooled_covariance
            )
            covariances[state_index] = _regularize_covariance(
                pooled,
                diagonal_shrinkage=self.config.covariance_diagonal_shrinkage,
                minimum_eigenvalue=self.config.covariance_minimum_eigenvalue,
            )

        initial_counts = np.sum(
            np.stack([posterior[0] for posterior in state_posteriors]), axis=0
        )
        initial_counts += self.config.initial_probability_smoothing
        initial_probabilities = initial_counts / np.sum(initial_counts)
        if previous_state is None:
            transition_weights = np.zeros(
                (state_count, state_count, coefficient_count), dtype=np.float64
            )
            available_transition_posteriors = [
                values for values in transition_posteriors if len(values)
            ]
            if available_transition_posteriors:
                transition_counts = np.sum(
                    np.concatenate(available_transition_posteriors, axis=0), axis=0
                )
            else:
                transition_counts = np.ones(
                    (state_count, state_count), dtype=np.float64
                )
            transition_counts += self.config.initial_probability_smoothing
            transition_weights[:, :, 0] = np.log(
                transition_counts
                / np.sum(transition_counts, axis=1, keepdims=True)
            )
            transition_weights[:, :, 0] -= np.mean(
                transition_weights[:, :, 0], axis=1, keepdims=True
            )
        else:
            transition_weights = previous_state.transition_weights
        transition_weights = self._optimize_transition_weights(
            dataset, transition_posteriors, transition_weights
        )
        occupancies = np.sum(gamma, axis=0)
        occupancies /= np.sum(occupancies)
        if previous_state is None:
            initial_emission_coefficients, initial_emission_covariance = (
                self._fit_initial_emission(conditions, residuals)
            )
        else:
            initial_emission_coefficients = (
                previous_state.initial_emission_coefficients
            )
            initial_emission_covariance = previous_state.initial_emission_covariance
        return _AIOHMMState(
            feature_names=dataset.feature_names,
            stations_m=dataset.stations_m,
            initial_probabilities=initial_probabilities,
            initial_emission_coefficients=initial_emission_coefficients,
            initial_emission_covariance=initial_emission_covariance,
            transition_weights=transition_weights,
            emission_coefficients=emission_coefficients,
            autoregressive_coefficients=autoregressive_coefficients,
            covariances=covariances,
            state_occupancies=occupancies,
            log_likelihood_history=np.empty(0, dtype=np.float64),
            training_sequence_count=dataset.sequence_count,
            training_frame_count=dataset.frame_count,
            best_iteration_index=0,
            converged=False,
        )

    def _initialize(self, dataset: PaddedSequenceDataset) -> _AIOHMMState:
        _conditions, residuals, _previous = self._flatten_training_arrays(dataset)
        scores = np.sqrt(np.mean(np.square(residuals), axis=1))
        generator = np.random.default_rng(self.config.initialization_seed)
        score_scale = max(float(np.std(scores)), 1e-6)
        perturbed = scores + generator.normal(
            scale=0.02 * score_scale, size=len(scores)
        )
        thresholds = np.quantile(
            perturbed,
            np.arange(1, self.config.state_count) / self.config.state_count,
        )
        assignments = np.digitize(perturbed, thresholds)
        smoothing = 0.02
        gamma = np.full(
            (len(assignments), self.config.state_count),
            smoothing / self.config.state_count,
            dtype=np.float64,
        )
        gamma[np.arange(len(assignments)), assignments] += 1.0 - smoothing
        state_posteriors: list[FloatArray] = []
        transition_posteriors: list[FloatArray] = []
        offset = 0
        for raw_length in dataset.lengths:
            length = int(raw_length)
            sequence_gamma = gamma[offset : offset + length]
            state_posteriors.append(sequence_gamma)
            xi = np.zeros(
                (
                    max(length - 1, 0),
                    self.config.state_count,
                    self.config.state_count,
                ),
                dtype=np.float64,
            )
            for time_index in range(length - 1):
                xi[time_index] = np.outer(
                    sequence_gamma[time_index], sequence_gamma[time_index + 1]
                )
                xi[time_index] /= np.sum(xi[time_index])
            transition_posteriors.append(xi)
            offset += length
        return self._m_step(
            dataset,
            tuple(state_posteriors),
            tuple(transition_posteriors),
            previous_state=None,
        )

    def fit(
        self,
        training_data: PaddedSequenceDataset,
        validation_data: PaddedSequenceDataset | None = None,
    ) -> FitReport:
        """Fit one deterministic generalized-EM restart."""

        self.validate_fit_datasets(training_data, validation_data)
        self._require_complete_standardized(training_data)
        if validation_data is not None:
            self._require_complete_standardized(validation_data)
        self._set_state(self._initialize(training_data))
        history: list[float] = []
        best_state: _AIOHMMState | None = None
        best_log_probability = -np.inf
        best_iteration = 0
        converged = False
        likelihood_decrease_count = 0
        warnings: list[str] = []

        for iteration in range(self.config.maximum_em_iterations):
            expectation = self._expectation(training_data)
            total_log_probability = float(
                np.sum(expectation.sequence_log_probabilities)
            )
            history.append(total_log_probability)
            occupancies = np.sum(
                np.concatenate(
                    [
                        posterior.state_probabilities
                        for posterior in expectation.posteriors
                    ],
                    axis=0,
                ),
                axis=0,
            )
            occupancies /= np.sum(occupancies)
            if np.min(occupancies) < self.config.minimum_state_occupancy_fraction:
                warnings.append(
                    "EM stopped because a hidden state fell below the occupancy floor."
                )
                break
            current = replace(
                self._require_state(),
                state_occupancies=occupancies,
                log_likelihood_history=np.asarray(history, dtype=np.float64),
                best_iteration_index=iteration,
                converged=False,
            )
            self._set_state(current)
            if total_log_probability > best_log_probability:
                best_log_probability = total_log_probability
                best_iteration = iteration
                best_state = self._copy_state(current)
            if len(history) > 1:
                improvement = history[-1] - history[-2]
                relative_improvement = improvement / max(abs(history[-2]), 1.0)
                if improvement < -1e-7:
                    likelihood_decrease_count += 1
                if (
                    iteration + 1 >= self.config.minimum_em_iterations
                    and abs(relative_improvement) < self.config.convergence_tolerance
                ):
                    converged = True
                    break
            if iteration + 1 == self.config.maximum_em_iterations:
                break
            try:
                updated = self._m_step(
                    training_data,
                    tuple(
                        posterior.state_probabilities
                        for posterior in expectation.posteriors
                    ),
                    tuple(
                        posterior.transition_probabilities
                        for posterior in expectation.posteriors
                    ),
                    previous_state=self._require_state(),
                )
            except (ValueError, np.linalg.LinAlgError) as error:
                warnings.append(f"EM stopped during the M-step: {error}")
                break
            self._set_state(updated)

        if best_state is None:
            raise ValueError("AIOHMM fitting ended before a valid state was observed")
        best_state = replace(
            best_state,
            log_likelihood_history=np.asarray(history, dtype=np.float64),
            best_iteration_index=best_iteration,
            converged=converged,
        )
        best_state = self._canonicalized_state(best_state)
        self._set_state(best_state)
        if not converged:
            warnings.append("EM did not reach the configured convergence tolerance.")
        if likelihood_decrease_count:
            warnings.append(
                "Training likelihood decreased on "
                f"{likelihood_decrease_count} generalized-EM iteration(s); "
                "the best observed parameter state was retained."
            )

        training_log_probability = self.log_probability(training_data)
        metrics: dict[str, float] = {
            "training_mean_joint_negative_log_likelihood_standardized": float(
                -np.sum(training_log_probability) / training_data.frame_count
            ),
            "em_best_training_log_probability": best_log_probability,
            "em_iteration_count": float(len(history)),
            "em_best_iteration_index": float(best_iteration),
            "em_converged": float(converged),
            "minimum_state_occupancy_fraction": float(
                np.min(best_state.state_occupancies)
            ),
            "maximum_absolute_autoregressive_coefficient": float(
                np.max(np.abs(best_state.autoregressive_coefficients))
            ),
        }
        validation_count = 0
        if validation_data is not None:
            validation_count = validation_data.sequence_count
            validation_log_probability = self.log_probability(validation_data)
            metrics["validation_mean_joint_negative_log_likelihood_standardized"] = (
                float(
                    -np.sum(validation_log_probability)
                    / validation_data.frame_count
                )
            )
        return FitReport(
            model_name=self.model_name,
            training_sequence_count=training_data.sequence_count,
            validation_sequence_count=validation_count,
            metrics=metrics,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def log_probability(self, dataset: PaddedSequenceDataset) -> FloatArray:
        """Return per-frame filtering increments that sum to each sequence log-density."""

        expectation = self._expectation(dataset)
        values = np.zeros(dataset.time_mask.shape, dtype=np.float64)
        for sequence_index, posterior in enumerate(expectation.posteriors):
            values[sequence_index, : len(posterior.log_normalizers)] = (
                posterior.log_normalizers
            )
        return values

    def sequence_log_probability(self, dataset: PaddedSequenceDataset) -> FloatArray:
        """Return one teacher-forced joint log-density per sequence."""

        return self._expectation(dataset).sequence_log_probabilities.copy()

    def posterior_state_probabilities(
        self, dataset: PaddedSequenceDataset
    ) -> tuple[FloatArray, ...]:
        """Return smoothed posterior state probabilities for diagnostics."""

        return tuple(
            posterior.state_probabilities.copy()
            for posterior in self._expectation(dataset).posteriors
        )

    @staticmethod
    def _validated_condition_tensor(
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> tuple[FloatArray, IntegerArray, BooleanArray]:
        values = np.asarray(conditions, dtype=np.float64)
        sequence_lengths = np.asarray(lengths, dtype=np.int64)
        if values.ndim != 3 or values.shape[0] < 1:
            raise ValueError("conditions must have shape [B,T,6]")
        sequence_count, maximum_length, feature_count = values.shape
        if feature_count != len(BMW_CONDITION_FEATURE_NAMES):
            raise ValueError("conditions must use BMW condition schema v1")
        if sequence_lengths.shape != (sequence_count,):
            raise ValueError("lengths must have shape [B]")
        if np.any(sequence_lengths < 1) or np.any(
            sequence_lengths > maximum_length
        ):
            raise ValueError("sequence lengths are invalid")
        if not np.all(np.isfinite(values)):
            raise ValueError("conditions must be finite")
        time_mask = np.arange(maximum_length)[None, :] < sequence_lengths[:, None]
        if np.any(values[~time_mask] != 0.0):
            raise ValueError("padded condition frames must be zero")
        return values, sequence_lengths, time_mask

    @staticmethod
    def _draw_categorical_rows(
        probabilities: FloatArray,
        generator: np.random.Generator,
    ) -> IntegerArray:
        cumulative = np.cumsum(probabilities, axis=1)
        cumulative[:, -1] = 1.0
        uniforms = generator.random(len(probabilities))
        return np.sum(uniforms[:, None] > cumulative, axis=1).astype(np.int64)

    def sample(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
        *,
        sample_count: int,
        seed: int,
        valid_mask: ArrayLike | None = None,
    ) -> SampleResult:
        """Generate free-running residual sequences with zero-valued padding."""

        if isinstance(sample_count, bool) or not isinstance(
            sample_count, (int, np.integer)
        ):
            raise TypeError("sample_count must be an integer")
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            raise TypeError("seed must be an integer")
        if seed < 0:
            raise ValueError("seed must be nonnegative")
        state = self._require_state()
        condition_array, length_array, time_mask = self._validated_condition_tensor(
            conditions, lengths
        )
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        if valid_mask is None:
            mask = np.broadcast_to(
                time_mask[:, :, None], (*time_mask.shape, station_count)
            ).copy()
        else:
            mask = np.asarray(valid_mask, dtype=np.bool_)
            if mask.shape != (*time_mask.shape, station_count):
                raise ValueError("valid_mask must have shape [B,T,21]")
            if np.any(mask & ~time_mask[:, :, None]):
                raise ValueError("valid_mask marks padding as active")
            if not np.all(mask[time_mask]):
                raise ValueError("AIOHMM v0.11 does not support missing targets")
        if self._cholesky_factors is None or self._initial_cholesky_factor is None:
            raise RuntimeError("AIOHMM covariance factors are unavailable")
        generator = np.random.default_rng(int(seed))
        values = np.zeros(
            (
                sample_count,
                len(length_array),
                condition_array.shape[1],
                station_count,
            ),
            dtype=np.float64,
        )
        initial_rows = np.broadcast_to(
            state.initial_probabilities,
            (sample_count, self.config.state_count),
        )
        for sequence_index, raw_length in enumerate(length_array):
            length = int(raw_length)
            hidden_states = self._draw_categorical_rows(initial_rows, generator)
            previous = np.zeros((sample_count, station_count), dtype=np.float64)
            for time_index in range(length):
                condition = condition_array[sequence_index, time_index]
                design = np.concatenate(([1.0], condition))
                if time_index == 0:
                    initial_mean = design @ state.initial_emission_coefficients
                    generated = (
                        initial_mean[None, :]
                        + generator.standard_normal((sample_count, station_count))
                        @ self._initial_cholesky_factor.T
                    )
                    values[:, sequence_index, time_index] = generated
                    previous = generated
                    continue
                if time_index > 0:
                    transition_design = design.copy()
                    if not self.config.input_dependent_transitions:
                        transition_design[1:] = 0.0
                    selected_weights = state.transition_weights[hidden_states]
                    logits = np.einsum(
                        "snp,p->sn",
                        selected_weights,
                        transition_design,
                        optimize=True,
                    )
                    probabilities = np.exp(log_softmax(logits, axis=1))
                    hidden_states = self._draw_categorical_rows(
                        probabilities, generator
                    )
                means = np.einsum(
                    "spk,p->sk",
                    state.emission_coefficients[hidden_states],
                    design,
                    optimize=True,
                )
                means += state.autoregressive_coefficients[hidden_states] * previous
                generated = np.empty_like(means)
                for state_index in range(self.config.state_count):
                    selected = hidden_states == state_index
                    selected_count = int(np.count_nonzero(selected))
                    if selected_count == 0:
                        continue
                    noise = generator.standard_normal(
                        (selected_count, station_count)
                    )
                    generated[selected] = (
                        means[selected]
                        + noise @ self._cholesky_factors[state_index].T
                    )
                values[:, sequence_index, time_index] = generated
                previous = generated
        return SampleResult(
            values=values,
            lengths=length_array,
            stations_m=CANONICAL_MODEL_STATIONS_M,
            standardized=True,
            valid_mask=mask,
        )

    def transition_probability_summary(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> tuple[FloatArray, FloatArray, int]:
        """Return mean/std transition matrices over all active transitions."""

        condition_array, length_array, _time_mask = self._validated_condition_tensor(
            conditions, lengths
        )
        matrices: list[FloatArray] = []
        state = self._require_state()
        for sequence_index, raw_length in enumerate(length_array):
            length = int(raw_length)
            if length <= 1:
                continue
            log_probabilities = transition_log_probabilities(
                condition_array[sequence_index, :length],
                state.transition_weights,
                input_dependent=self.config.input_dependent_transitions,
            )
            matrices.append(np.exp(log_probabilities))
        if not matrices:
            raise ValueError("transition diagnostics require at least one transition")
        values = np.concatenate(matrices, axis=0)
        return (
            np.mean(values, axis=0),
            np.std(values, axis=0, ddof=0),
            len(values),
        )

    def to_dict(self) -> dict[str, Any]:
        state = self._require_state()
        return {
            "schema_version": VERSION,
            "status": "complete",
            "model_name": self.model_name,
            "input_units": "training_standardized",
            "temporal_dependency_order": self.temporal_dependency_order,
            "teacher_forced_log_probability": True,
            "free_running_sampling": True,
            "state_labels_are_canonicalized_not_physical_classes": True,
            "state_canonicalization": (
                "ascending zero-condition emission-intercept profile RMS, then mean and median AR"
            ),
            "configuration": self.config.to_dict(),
            "feature_names": list(state.feature_names),
            "stations_m": list(state.stations_m),
            "training_sequence_count": state.training_sequence_count,
            "training_frame_count": state.training_frame_count,
            "best_iteration_index": state.best_iteration_index,
            "converged": state.converged,
            "initial_probabilities": state.initial_probabilities.tolist(),
            "initial_emission_role": (
                "state_independent_training_marginal_conditional_gaussian_sequence_reset_prior"
            ),
            "initial_emission_coefficients": (
                state.initial_emission_coefficients.tolist()
            ),
            "initial_emission_covariance_standardized2": (
                state.initial_emission_covariance.tolist()
            ),
            "transition_weights": state.transition_weights.tolist(),
            "emission_coefficients": state.emission_coefficients.tolist(),
            "autoregressive_coefficients": (
                state.autoregressive_coefficients.tolist()
            ),
            "covariances_standardized2": state.covariances.tolist(),
            "state_occupancies": state.state_occupancies.tolist(),
            "state_profile_rms_standardized": (
                self.state_profile_rms_standardized.tolist()
            ),
            "log_likelihood_history": state.log_likelihood_history.tolist(),
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        serialized = json.dumps(
            self.to_dict(), indent=2, sort_keys=True, allow_nan=False
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized + "\n", encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Self:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"AIOHMM model not found: {source}")
        payload = _strict_json(source)
        if not isinstance(payload, Mapping):
            raise ValueError("AIOHMM model payload must be an object")
        if payload.get("schema_version") != VERSION:
            raise ValueError("AIOHMM model schema version must be 0.11.0")
        if payload.get("model_name") != "autoregressive_input_output_hmm":
            raise ValueError("unexpected AIOHMM model name")
        if payload.get("input_units") != "training_standardized":
            raise ValueError("AIOHMM standardized-input declaration is missing")
        try:
            configuration = payload["configuration"]
            if not isinstance(configuration, Mapping):
                raise TypeError("configuration must be an object")
            model = cls(AIOHMMConfig.from_dict(configuration))
            state = _AIOHMMState(
                feature_names=tuple(
                    str(value) for value in payload["feature_names"]
                ),
                stations_m=tuple(float(value) for value in payload["stations_m"]),
                initial_probabilities=np.asarray(
                    payload["initial_probabilities"], dtype=np.float64
                ),
                initial_emission_coefficients=np.asarray(
                    payload["initial_emission_coefficients"], dtype=np.float64
                ),
                initial_emission_covariance=np.asarray(
                    payload["initial_emission_covariance_standardized2"],
                    dtype=np.float64,
                ),
                transition_weights=np.asarray(
                    payload["transition_weights"], dtype=np.float64
                ),
                emission_coefficients=np.asarray(
                    payload["emission_coefficients"], dtype=np.float64
                ),
                autoregressive_coefficients=np.asarray(
                    payload["autoregressive_coefficients"], dtype=np.float64
                ),
                covariances=np.asarray(
                    payload["covariances_standardized2"], dtype=np.float64
                ),
                state_occupancies=np.asarray(
                    payload["state_occupancies"], dtype=np.float64
                ),
                log_likelihood_history=np.asarray(
                    payload["log_likelihood_history"], dtype=np.float64
                ),
                training_sequence_count=int(payload["training_sequence_count"]),
                training_frame_count=int(payload["training_frame_count"]),
                best_iteration_index=int(payload["best_iteration_index"]),
                converged=payload["converged"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid AIOHMM model payload: {error}") from error
        model._set_state(state)
        return model


__all__ = [
    "AIOHMMConfig",
    "AutoregressiveInputOutputHMM",
    "VERSION",
]
