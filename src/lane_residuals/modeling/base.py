"""Common probabilistic sequence-model lifecycle for the thesis models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Self

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..domain.sequence_dataset import PaddedSequenceDataset


@dataclass(frozen=True)
class ModelCapabilities:
    supports_log_probability: bool
    supports_missing_targets: bool = False
    supports_variable_length: bool = True


@dataclass(frozen=True)
class FitReport:
    model_name: str
    training_sequence_count: int
    validation_sequence_count: int
    metrics: Mapping[str, float]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_name:
            raise ValueError("model_name must be nonempty")
        if self.training_sequence_count < 1 or self.validation_sequence_count < 0:
            raise ValueError("fit sequence counts are invalid")
        if any(not name for name in self.metrics):
            raise ValueError("fit metric names must be nonempty")
        if any(not np.isfinite(value) for value in self.metrics.values()):
            raise ValueError("fit metrics must be finite")


@dataclass(frozen=True)
class SampleResult:
    """Generated values with shape [samples, sequences, time, stations]."""

    values: ArrayLike
    lengths: ArrayLike
    stations_m: ArrayLike
    standardized: bool
    valid_mask: ArrayLike | None = None

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=np.float64)
        lengths = np.asarray(self.lengths, dtype=np.int64)
        stations = np.asarray(self.stations_m, dtype=np.float64)
        if values.ndim != 4:
            raise ValueError("sample values must have shape [S,B,T,K]")
        sample_count, sequence_count, maximum_length, station_count = values.shape
        if sample_count < 1 or sequence_count < 1:
            raise ValueError("sample and sequence counts must be positive")
        if lengths.shape != (sequence_count,):
            raise ValueError("sample lengths must have shape [B]")
        if np.any(lengths < 1) or np.any(lengths > maximum_length):
            raise ValueError("sample lengths are invalid")
        if stations.shape != (station_count,) or not np.all(np.diff(stations) > 0.0):
            raise ValueError("sample station grid is invalid")
        if not np.all(np.isfinite(values)) or not np.all(np.isfinite(stations)):
            raise ValueError("sample arrays must be finite")
        time_mask = np.arange(maximum_length)[None, :] < lengths[:, None]
        if np.any(values * (~time_mask)[None, :, :, None] != 0.0):
            raise ValueError("generated padding frames must be zero")
        mask: NDArray[np.bool_] | None = None
        if self.valid_mask is not None:
            mask = np.asarray(self.valid_mask, dtype=np.bool_)
            if mask.shape != (sequence_count, maximum_length, station_count):
                raise ValueError("sample valid_mask has the wrong shape")
            if np.any(mask & ~time_mask[:, :, None]):
                raise ValueError("sample valid_mask marks padding as valid")
            mask.setflags(write=False)
        for array in (values, lengths, stations):
            array.setflags(write=False)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "lengths", lengths)
        object.__setattr__(self, "stations_m", stations)
        object.__setattr__(self, "valid_mask", mask)

    @property
    def sample_count(self) -> int:
        return int(self.values.shape[0])


class ProbabilisticSequenceModel(ABC):
    """Shared interface for Gaussian, AIOHMM, and RC-GAN implementations."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_fitted(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fit(
        self,
        training_data: PaddedSequenceDataset,
        validation_data: PaddedSequenceDataset | None = None,
    ) -> FitReport:
        raise NotImplementedError

    @abstractmethod
    def sample(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
        *,
        sample_count: int,
        seed: int,
        valid_mask: ArrayLike | None = None,
    ) -> SampleResult:
        raise NotImplementedError

    def log_probability(self, dataset: PaddedSequenceDataset) -> NDArray[np.float64]:
        raise NotImplementedError(
            f"{self.model_name} does not provide a normalized log probability"
        )

    @abstractmethod
    def save(self, path: str | Path) -> Path:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path) -> Self:
        raise NotImplementedError

    @staticmethod
    def validate_fit_datasets(
        training_data: PaddedSequenceDataset,
        validation_data: PaddedSequenceDataset | None,
    ) -> None:
        if not training_data.standardized:
            raise ValueError("training data must use a training-fitted standardizer")
        if validation_data is None:
            return
        if not validation_data.standardized:
            raise ValueError("validation data must use the training standardizer")
        if (
            validation_data.feature_names != training_data.feature_names
            or validation_data.stations_m != training_data.stations_m
        ):
            raise ValueError("training and validation data contracts differ")
        overlap = sorted(
            set(training_data.drive_ids.tolist())
            & set(validation_data.drive_ids.tolist())
        )
        if overlap:
            raise ValueError(
                f"training and validation physical drives overlap: {overlap}"
            )


__all__ = [
    "FitReport",
    "ModelCapabilities",
    "ProbabilisticSequenceModel",
    "SampleResult",
]
