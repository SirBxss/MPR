"""Sample-based sequence metrics shared by all thesis model families."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..domain.sequence_dataset import (
    PaddedSequenceDataset,
    SequenceStandardizer,
)
from .base import SampleResult

FloatArray = NDArray[np.float64]


def physical_sample_result(
    samples: SampleResult,
    standardizer: SequenceStandardizer,
) -> SampleResult:
    """Invert a fold's target transform while preserving zero padding."""

    if not samples.standardized:
        raise ValueError("sample result is already in physical units")
    if tuple(samples.stations_m.tolist()) != standardizer.stations_m:
        raise ValueError("sample and standardizer station grids differ")
    time_mask = np.arange(samples.values.shape[2])[None, :] < samples.lengths[:, None]
    values = (
        samples.values * standardizer.residual_scale_m[None, None, None, :]
        + standardizer.residual_mean_m[None, None, None, :]
    )
    values *= time_mask[None, :, :, None]
    return SampleResult(
        values=values,
        lengths=samples.lengths,
        stations_m=samples.stations_m,
        standardized=False,
        valid_mask=samples.valid_mask,
    )


def _lag_one_correlations(
    values: FloatArray,
    lengths: NDArray[np.int64],
) -> FloatArray:
    """Return station correlations for [B,T,K] or [S,B,T,K] values."""

    if values.ndim == 3:
        values = values[None, ...]
        squeeze = True
    elif values.ndim == 4:
        squeeze = False
    else:
        raise ValueError("lag-one values must have shape [B,T,K] or [S,B,T,K]")
    previous = np.concatenate(
        [values[:, index, : length - 1] for index, length in enumerate(lengths)],
        axis=1,
    )
    current = np.concatenate(
        [values[:, index, 1:length] for index, length in enumerate(lengths)],
        axis=1,
    )
    if previous.shape[1] < 2:
        raise ValueError("lag-one evaluation requires at least two transitions")
    previous_centered = previous - np.mean(previous, axis=1, keepdims=True)
    current_centered = current - np.mean(current, axis=1, keepdims=True)
    numerator = np.sum(previous_centered * current_centered, axis=1)
    denominator = np.sqrt(
        np.sum(np.square(previous_centered), axis=1)
        * np.sum(np.square(current_centered), axis=1)
    )
    if np.any(denominator <= 0.0):
        raise ValueError("lag-one correlation requires nonconstant transitions")
    correlations = numerator / denominator
    return correlations[0] if squeeze else correlations


@dataclass(frozen=True)
class SequenceSampleEvaluation:
    time_mask: NDArray[np.bool_]
    mean_prediction_m: FloatArray
    lower_95_m: FloatArray
    upper_95_m: FloatArray
    frame_rmse_m: FloatArray
    frame_energy_score_m: FloatArray
    station_rmse_m: FloatArray
    station_bias_m: FloatArray
    station_coverage_95: FloatArray
    observed_lag_one_correlation: FloatArray
    generated_lag_one_correlation_by_sample: FloatArray

    @property
    def pooled_mean_prediction_rmse_m(self) -> float:
        return float(np.sqrt(np.mean(np.square(self.station_rmse_m))))

    @property
    def mean_energy_score_m(self) -> float:
        return float(np.mean(self.frame_energy_score_m[self.time_mask]))

    @property
    def marginal_95_coverage(self) -> float:
        return float(np.mean(self.station_coverage_95))

    @property
    def generated_median_lag_one_correlation(self) -> FloatArray:
        return np.median(self.generated_lag_one_correlation_by_sample, axis=0)

    @property
    def median_absolute_lag_one_correlation_error(self) -> float:
        return float(
            np.median(
                np.abs(
                    self.generated_median_lag_one_correlation
                    - self.observed_lag_one_correlation
                )
            )
        )


def evaluate_sequence_samples(
    observed: PaddedSequenceDataset,
    samples: SampleResult,
) -> SequenceSampleEvaluation:
    """Evaluate physical-unit samples on exact observed sequence frames."""

    if observed.standardized or samples.standardized:
        raise ValueError("common sample evaluation requires physical units")
    if samples.values.shape[1:3] != observed.conditions.shape[:2]:
        raise ValueError("sample sequence/time shape differs from observations")
    if samples.values.shape[3] != observed.residuals_m.shape[2]:
        raise ValueError("sample station dimension differs from observations")
    if not np.array_equal(samples.lengths, observed.lengths):
        raise ValueError("sample and observation lengths differ")
    if not np.array_equal(samples.valid_mask, observed.valid_mask):
        raise ValueError("sample and observation masks differ")
    if samples.sample_count < 4:
        raise ValueError("sample evaluation requires at least four samples")

    time_mask = observed.time_mask
    target = observed.residuals_m
    mean_prediction = np.mean(samples.values, axis=0)
    lower = np.quantile(samples.values, 0.025, axis=0)
    upper = np.quantile(samples.values, 0.975, axis=0)
    for values in (mean_prediction, lower, upper):
        values[~time_mask] = 0.0

    errors = mean_prediction - target
    frame_rmse = np.zeros(time_mask.shape, dtype=np.float64)
    frame_rmse[time_mask] = np.sqrt(
        np.mean(np.square(errors[time_mask]), axis=1)
    )

    distance_to_target = np.linalg.norm(samples.values - target[None, ...], axis=-1)
    half = samples.sample_count // 2
    pair_distance = np.linalg.norm(
        samples.values[:half] - samples.values[half : 2 * half],
        axis=-1,
    )
    energy = np.zeros(time_mask.shape, dtype=np.float64)
    energy[time_mask] = (
        np.mean(distance_to_target[:, time_mask], axis=0)
        - 0.5 * np.mean(pair_distance[:, time_mask], axis=0)
    )

    active_errors = errors[time_mask]
    station_rmse = np.sqrt(np.mean(np.square(active_errors), axis=0))
    station_bias = np.mean(active_errors, axis=0)
    active_target = target[time_mask]
    station_coverage = np.mean(
        (active_target >= lower[time_mask]) & (active_target <= upper[time_mask]),
        axis=0,
    )
    observed_lag = _lag_one_correlations(target, observed.lengths)
    generated_lag = _lag_one_correlations(samples.values, observed.lengths)
    arrays = (
        mean_prediction,
        lower,
        upper,
        frame_rmse,
        energy,
        station_rmse,
        station_bias,
        station_coverage,
        observed_lag,
        generated_lag,
    )
    if not all(np.all(np.isfinite(values)) for values in arrays):
        raise ValueError("sample evaluation produced non-finite values")
    return SequenceSampleEvaluation(
        time_mask=time_mask,
        mean_prediction_m=mean_prediction,
        lower_95_m=lower,
        upper_95_m=upper,
        frame_rmse_m=frame_rmse,
        frame_energy_score_m=energy,
        station_rmse_m=station_rmse,
        station_bias_m=station_bias,
        station_coverage_95=station_coverage,
        observed_lag_one_correlation=observed_lag,
        generated_lag_one_correlation_by_sample=generated_lag,
    )


__all__ = [
    "SequenceSampleEvaluation",
    "evaluate_sequence_samples",
    "physical_sample_result",
]
