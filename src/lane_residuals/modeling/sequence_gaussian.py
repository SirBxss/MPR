"""Sequence-contract adapter for the conditionally independent Gaussian null."""

from __future__ import annotations

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
from .base import (
    FitReport,
    ModelCapabilities,
    ProbabilisticSequenceModel,
    SampleResult,
)
from .conditional_gaussian import (
    ConditionalGaussianResidualModel,
    fit_linear_conditional_gaussian,
)

FloatArray = NDArray[np.float64]
VERSION = "0.10.0"


def _strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


class SequenceConditionalGaussian(ProbabilisticSequenceModel):
    """Linear conditional Gaussian with no transition or recurrent state.

    The adapter consumes the common standardized sequence tensors but flattens
    active frames for fitting. Samples are spatially correlated across the 21
    stations and conditionally independent across time. It is therefore the
    temporal-null baseline for AIOHMM and RC-GAN comparisons.
    """

    def __init__(self, *, covariance_regularization: float = 1e-6) -> None:
        if (
            not math.isfinite(covariance_regularization)
            or covariance_regularization <= 0.0
        ):
            raise ValueError("covariance regularization must be finite and positive")
        self._covariance_regularization = float(covariance_regularization)
        self._model: ConditionalGaussianResidualModel | None = None

    @property
    def model_name(self) -> str:
        return "sequence_conditional_gaussian"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_log_probability=True,
            supports_missing_targets=False,
            supports_variable_length=True,
        )

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    @property
    def temporal_dependency_order(self) -> int:
        return 0

    @property
    def covariance_regularization(self) -> float:
        return self._covariance_regularization

    @property
    def fitted_model(self) -> ConditionalGaussianResidualModel:
        if self._model is None:
            raise ValueError("sequence conditional Gaussian is not fitted")
        return self._model

    @staticmethod
    def _active_arrays(
        dataset: PaddedSequenceDataset,
    ) -> tuple[FloatArray, FloatArray]:
        if not dataset.standardized:
            raise ValueError("sequence Gaussian requires standardized data")
        if not np.all(dataset.valid_mask[dataset.time_mask]):
            raise ValueError("sequence Gaussian requires complete active H100 frames")
        return (
            np.asarray(dataset.conditions[dataset.time_mask], dtype=np.float64),
            np.asarray(dataset.residuals_m[dataset.time_mask], dtype=np.float64),
        )

    def fit(
        self,
        training_data: PaddedSequenceDataset,
        validation_data: PaddedSequenceDataset | None = None,
    ) -> FitReport:
        self.validate_fit_datasets(training_data, validation_data)
        conditions, residuals = self._active_arrays(training_data)
        self._model = fit_linear_conditional_gaussian(
            conditions,
            residuals,
            feature_names=BMW_CONDITION_FEATURE_NAMES,
            covariance_regularization_m2=self._covariance_regularization,
        )
        training_log_probability = self._model.logpdf(conditions, residuals)
        training_prediction = self._model.predict_mean(conditions)
        metrics = {
            "training_mean_joint_negative_log_likelihood_standardized": float(
                -np.mean(training_log_probability)
            ),
            "training_prediction_rmse_standardized": float(
                np.sqrt(np.mean(np.square(residuals - training_prediction)))
            ),
        }
        validation_count = 0
        if validation_data is not None:
            validation_conditions, validation_residuals = self._active_arrays(
                validation_data
            )
            validation_count = validation_data.sequence_count
            validation_prediction = self._model.predict_mean(validation_conditions)
            metrics.update(
                {
                    "validation_mean_joint_negative_log_likelihood_standardized": (
                        float(
                            -np.mean(
                                self._model.logpdf(
                                    validation_conditions,
                                    validation_residuals,
                                )
                            )
                        )
                    ),
                    "validation_prediction_rmse_standardized": float(
                        np.sqrt(
                            np.mean(
                                np.square(
                                    validation_residuals - validation_prediction
                                )
                            )
                        )
                    ),
                }
            )
        return FitReport(
            model_name=self.model_name,
            training_sequence_count=training_data.sequence_count,
            validation_sequence_count=validation_count,
            metrics=metrics,
            warnings=(
                "Frames are conditionally independent across time; no transition state is fitted.",
            ),
        )

    @staticmethod
    def _validated_condition_tensor(
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> tuple[FloatArray, NDArray[np.int64], NDArray[np.bool_]]:
        values = np.asarray(conditions, dtype=np.float64)
        sequence_lengths = np.asarray(lengths, dtype=np.int64)
        if values.ndim != 3 or values.shape[0] < 1:
            raise ValueError("conditions must have shape [B,T,6]")
        sequence_count, maximum_length, feature_count = values.shape
        if feature_count != len(BMW_CONDITION_FEATURE_NAMES):
            raise ValueError("conditions must use BMW condition schema v1")
        if sequence_lengths.shape != (sequence_count,):
            raise ValueError("lengths must have shape [B]")
        if np.any(sequence_lengths < 1) or np.any(sequence_lengths > maximum_length):
            raise ValueError("sequence lengths are invalid")
        if not np.all(np.isfinite(values)):
            raise ValueError("conditions must be finite")
        time_mask = np.arange(maximum_length)[None, :] < sequence_lengths[:, None]
        if np.any(values[~time_mask] != 0.0):
            raise ValueError("padded condition frames must be zero")
        return values, sequence_lengths, time_mask

    def predict_mean(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> FloatArray:
        values, _sequence_lengths, time_mask = self._validated_condition_tensor(
            conditions,
            lengths,
        )
        prediction = np.zeros(
            (*values.shape[:2], len(CANONICAL_MODEL_STATIONS_M)),
            dtype=np.float64,
        )
        prediction[time_mask] = self.fitted_model.predict_mean(values[time_mask])
        return prediction

    def sample(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
        *,
        sample_count: int,
        seed: int,
        valid_mask: ArrayLike | None = None,
    ) -> SampleResult:
        if isinstance(sample_count, bool) or not isinstance(
            sample_count,
            (int, np.integer),
        ):
            raise TypeError("sample_count must be an integer")
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            raise TypeError("seed must be an integer")
        if seed < 0:
            raise ValueError("seed must be nonnegative")
        values, sequence_lengths, time_mask = self._validated_condition_tensor(
            conditions,
            lengths,
        )
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        if valid_mask is None:
            mask = np.broadcast_to(
                time_mask[:, :, None],
                (*time_mask.shape, station_count),
            ).copy()
        else:
            mask = np.asarray(valid_mask, dtype=np.bool_)
            if mask.shape != (*time_mask.shape, station_count):
                raise ValueError("valid_mask must have shape [B,T,21]")
            if np.any(mask & ~time_mask[:, :, None]):
                raise ValueError("valid_mask marks padding as active")
            if not np.all(mask[time_mask]):
                raise ValueError("sequence Gaussian does not support missing targets")
        prediction = self.predict_mean(values, sequence_lengths)
        generator = np.random.default_rng(int(seed))
        noise = generator.standard_normal(
            (sample_count, *values.shape[:2], station_count)
        )
        cholesky = np.linalg.cholesky(self.fitted_model.covariance_m2)
        samples = prediction[None, ...] + noise @ cholesky.T
        samples *= time_mask[None, :, :, None]
        return SampleResult(
            values=samples,
            lengths=sequence_lengths,
            stations_m=CANONICAL_MODEL_STATIONS_M,
            standardized=True,
            valid_mask=mask,
        )

    def log_probability(self, dataset: PaddedSequenceDataset) -> FloatArray:
        conditions, residuals = self._active_arrays(dataset)
        values = np.zeros(dataset.time_mask.shape, dtype=np.float64)
        values[dataset.time_mask] = self.fitted_model.logpdf(conditions, residuals)
        return values

    def squared_mahalanobis(self, dataset: PaddedSequenceDataset) -> FloatArray:
        conditions, residuals = self._active_arrays(dataset)
        values = np.zeros(dataset.time_mask.shape, dtype=np.float64)
        values[dataset.time_mask] = self.fitted_model.squared_mahalanobis(
            conditions,
            residuals,
        )
        return values

    def to_dict(self) -> dict[str, Any]:
        model = self.fitted_model
        return {
            "schema_version": VERSION,
            "status": "complete",
            "model_name": self.model_name,
            "input_units": "training_standardized",
            "temporal_dependency_order": self.temporal_dependency_order,
            "temporally_conditionally_independent": True,
            "feature_names": list(model.feature_names),
            "stations_m": list(CANONICAL_MODEL_STATIONS_M),
            "n_training_frames": model.n_training_samples,
            "covariance_regularization_standardized2": (
                self._covariance_regularization
            ),
            "feature_mean_after_external_standardization": model.feature_mean.tolist(),
            "feature_scale_after_external_standardization": model.feature_scale.tolist(),
            "intercept_standardized": model.intercept_m.tolist(),
            "standardized_feature_coefficients": (
                model.standardized_coefficients_m.tolist()
            ),
            "covariance_standardized2": model.covariance_m2.tolist(),
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        serialized = json.dumps(
            self.to_dict(),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized + "\n", encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Self:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"sequence Gaussian model not found: {source}")
        payload = _strict_json(source)
        if not isinstance(payload, Mapping):
            raise ValueError("sequence Gaussian model payload must be an object")
        if payload.get("schema_version") != VERSION:
            raise ValueError("sequence Gaussian model schema version must be 0.10.0")
        if payload.get("model_name") != "sequence_conditional_gaussian":
            raise ValueError("unexpected sequence Gaussian model name")
        if payload.get("input_units") != "training_standardized":
            raise ValueError("sequence Gaussian input-unit contract is missing")
        if payload.get("temporally_conditionally_independent") is not True:
            raise ValueError("sequence Gaussian temporal-null declaration is missing")
        try:
            model = cls(
                covariance_regularization=float(
                    payload["covariance_regularization_standardized2"]
                )
            )
            model._model = ConditionalGaussianResidualModel(
                feature_names=tuple(str(value) for value in payload["feature_names"]),
                feature_mean=payload["feature_mean_after_external_standardization"],
                feature_scale=payload[
                    "feature_scale_after_external_standardization"
                ],
                intercept_m=payload["intercept_standardized"],
                standardized_coefficients_m=payload[
                    "standardized_feature_coefficients"
                ],
                covariance_m2=payload["covariance_standardized2"],
                n_training_samples=int(payload["n_training_frames"]),
                covariance_regularization_m2=float(
                    payload["covariance_regularization_standardized2"]
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid sequence Gaussian model payload: {error}") from error
        if tuple(float(value) for value in payload.get("stations_m", ())) != (
            CANONICAL_MODEL_STATIONS_M
        ):
            raise ValueError("sequence Gaussian station grid is not canonical H100")
        return model


__all__ = ["SequenceConditionalGaussian", "VERSION"]
