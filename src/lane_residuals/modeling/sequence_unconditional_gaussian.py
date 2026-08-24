"""Sequence-shaped adapter for the unconditional Gaussian reference baseline."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Self

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import PaddedSequenceDataset
from .base import FitReport, ModelCapabilities, ProbabilisticSequenceModel, SampleResult
from .gaussian import GaussianResidualModel, fit_gaussian_residual_model

FloatArray = NDArray[np.float64]
VERSION = "0.14.0"


class SequenceUnconditionalGaussian(ProbabilisticSequenceModel):
    """One spatial Gaussian fitted to all active training frames.

    Conditions and sequence boundaries are retained only to guarantee identical
    evaluation rows.  The distribution has neither conditional nor temporal
    dependence and is therefore the reference needed to quantify whether the
    six-condition linear mean actually helps on held-out physical drives.
    """

    def __init__(self, *, covariance_regularization: float = 1e-6) -> None:
        if (
            not math.isfinite(covariance_regularization)
            or covariance_regularization <= 0.0
        ):
            raise ValueError("covariance regularization must be finite and positive")
        self._covariance_regularization = float(covariance_regularization)
        self._model: GaussianResidualModel | None = None

    @property
    def model_name(self) -> str:
        return "sequence_unconditional_gaussian"

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(supports_log_probability=True)

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    @property
    def temporal_dependency_order(self) -> int:
        return 0

    @property
    def fitted_model(self) -> GaussianResidualModel:
        if self._model is None:
            raise ValueError("sequence unconditional Gaussian is not fitted")
        return self._model

    @staticmethod
    def _active_residuals(dataset: PaddedSequenceDataset) -> FloatArray:
        if not dataset.standardized:
            raise ValueError("sequence Gaussian requires standardized data")
        if not np.all(dataset.valid_mask[dataset.time_mask]):
            raise ValueError("sequence Gaussian requires complete active H100 frames")
        return np.asarray(dataset.residuals_m[dataset.time_mask], dtype=np.float64)

    def fit(
        self,
        training_data: PaddedSequenceDataset,
        validation_data: PaddedSequenceDataset | None = None,
    ) -> FitReport:
        self.validate_fit_datasets(training_data, validation_data)
        training = self._active_residuals(training_data)
        self._model = fit_gaussian_residual_model(
            training,
            regularization=self._covariance_regularization,
        )
        metrics = {
            "training_mean_joint_negative_log_likelihood_standardized": (
                self._model.negative_log_likelihood(training)
            ),
            "training_prediction_rmse_standardized": float(
                np.sqrt(np.mean(np.square(training - self._model.mean)))
            ),
        }
        validation_count = 0
        if validation_data is not None:
            validation = self._active_residuals(validation_data)
            validation_count = validation_data.sequence_count
            metrics.update(
                {
                    "validation_mean_joint_negative_log_likelihood_standardized": (
                        self._model.negative_log_likelihood(validation)
                    ),
                    "validation_prediction_rmse_standardized": float(
                        np.sqrt(np.mean(np.square(validation - self._model.mean)))
                    ),
                }
            )
        return FitReport(
            model_name=self.model_name,
            training_sequence_count=training_data.sequence_count,
            validation_sequence_count=validation_count,
            metrics=metrics,
            warnings=(
                "Conditions and temporal state are intentionally absent from this reference baseline.",
            ),
        )

    @staticmethod
    def _validated_shape(
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> tuple[tuple[int, int], NDArray[np.int64], NDArray[np.bool_]]:
        values = np.asarray(conditions, dtype=np.float64)
        sequence_lengths = np.asarray(lengths, dtype=np.int64)
        if values.ndim != 3 or values.shape[0] < 1 or values.shape[2] != 6:
            raise ValueError("conditions must have shape [B,T,6]")
        if not np.all(np.isfinite(values)):
            raise ValueError("conditions must be finite")
        shape = values.shape[:2]
        if sequence_lengths.shape != (shape[0],):
            raise ValueError("lengths must have shape [B]")
        if np.any(sequence_lengths < 1) or np.any(sequence_lengths > shape[1]):
            raise ValueError("sequence lengths are invalid")
        time_mask = np.arange(shape[1])[None, :] < sequence_lengths[:, None]
        if np.any(values[~time_mask] != 0.0):
            raise ValueError("padded condition frames must be zero")
        return shape, sequence_lengths, time_mask

    def sample(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
        *,
        sample_count: int,
        seed: int,
        valid_mask: ArrayLike | None = None,
    ) -> SampleResult:
        if isinstance(sample_count, bool) or not isinstance(sample_count, (int, np.integer)):
            raise TypeError("sample_count must be an integer")
        if sample_count < 1:
            raise ValueError("sample_count must be positive")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            raise TypeError("seed must be an integer")
        if seed < 0:
            raise ValueError("seed must be nonnegative")
        shape, sequence_lengths, time_mask = self._validated_shape(conditions, lengths)
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        if valid_mask is None:
            mask = np.broadcast_to(
                time_mask[:, :, None], (*shape, station_count)
            ).copy()
        else:
            mask = np.asarray(valid_mask, dtype=np.bool_)
            if mask.shape != (*shape, station_count):
                raise ValueError("valid_mask must have shape [B,T,21]")
            if np.any(mask & ~time_mask[:, :, None]) or not np.all(mask[time_mask]):
                raise ValueError("unconditional Gaussian requires complete active targets")
        generator = np.random.default_rng(int(seed))
        noise = generator.standard_normal((sample_count, *shape, station_count))
        cholesky = np.linalg.cholesky(self.fitted_model.covariance)
        values = self.fitted_model.mean + noise @ cholesky.T
        values *= time_mask[None, :, :, None]
        return SampleResult(
            values=values,
            lengths=sequence_lengths,
            stations_m=CANONICAL_MODEL_STATIONS_M,
            standardized=True,
            valid_mask=mask,
        )

    def log_probability(self, dataset: PaddedSequenceDataset) -> FloatArray:
        residuals = self._active_residuals(dataset)
        values = np.zeros(dataset.time_mask.shape, dtype=np.float64)
        values[dataset.time_mask] = self.fitted_model.logpdf(residuals)
        return values

    def squared_mahalanobis(self, dataset: PaddedSequenceDataset) -> FloatArray:
        residuals = self._active_residuals(dataset)
        values = np.zeros(dataset.time_mask.shape, dtype=np.float64)
        values[dataset.time_mask] = self.fitted_model.squared_mahalanobis(residuals)
        return values

    def to_dict(self) -> dict[str, Any]:
        model = self.fitted_model
        return {
            "schema_version": VERSION,
            "model_name": self.model_name,
            "temporal_dependency_order": 0,
            "condition_feature_count": 0,
            "covariance_regularization_standardized2": model.regularization,
            "training_frame_count": model.n_training_samples,
            "mean_standardized": model.mean.tolist(),
            "covariance_standardized2": model.covariance.tolist(),
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Self:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"sequence unconditional Gaussian not found: {source}")

        def reject(value: str) -> None:
            raise ValueError(f"non-finite JSON constant is forbidden: {value}")

        with source.open("r", encoding="utf-8") as handle:
            payload = json.load(handle, parse_constant=reject)
        if not isinstance(payload, dict):
            raise ValueError("sequence unconditional Gaussian payload must be an object")
        if payload.get("schema_version") != VERSION or payload.get("model_name") != "sequence_unconditional_gaussian":
            raise ValueError("unexpected sequence unconditional Gaussian contract")
        model = cls(
            covariance_regularization=float(
                payload["covariance_regularization_standardized2"]
            )
        )
        model._model = GaussianResidualModel(
            mean=payload["mean_standardized"],
            covariance=payload["covariance_standardized2"],
            n_training_samples=int(payload["training_frame_count"]),
            regularization=float(payload["covariance_regularization_standardized2"]),
        )
        return model


__all__ = ["SequenceUnconditionalGaussian", "VERSION"]
