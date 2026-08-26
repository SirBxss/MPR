"""Frozen development residual model used by planner experiments."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..domain.sequence_dataset import (
    BMW_CONDITION_FEATURE_NAMES,
    SequenceStandardizer,
)
from .aiohmm import AutoregressiveInputOutputHMM
from .base import SampleResult

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]

DEVELOPMENT_MODEL_VERSION = "0.15.4"
SELECTED_DEVELOPMENT_AR_CEILING = 0.99


def _strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant)


class DevelopmentResidualModel:
    """Physical-unit facade over the frozen standardized one-state AR model."""

    def __init__(
        self,
        *,
        model: AutoregressiveInputOutputHMM,
        standardizer: SequenceStandardizer,
        metadata: Mapping[str, Any],
    ) -> None:
        if model.config.state_count != 1 or model.has_latent_state_switching:
            raise ValueError("development residual model must have one state")
        if model.config.input_dependent_transitions:
            raise ValueError("one-state development model must disable transitions")
        if not np.isclose(
            model.config.maximum_absolute_autoregression,
            SELECTED_DEVELOPMENT_AR_CEILING,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError("development residual model must use the frozen 0.99 cap")
        payload = model.to_dict()
        if tuple(payload["feature_names"]) != standardizer.feature_names:
            raise ValueError("development model and standardizer features differ")
        if tuple(payload["stations_m"]) != standardizer.stations_m:
            raise ValueError("development model and standardizer stations differ")
        self._model = model
        self._standardizer = standardizer
        self._metadata = dict(metadata)

    @classmethod
    def load(cls, path: str | Path) -> "DevelopmentResidualModel":
        """Load and validate the immutable v0.15.4 planner-development bundle."""

        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"development residual model not found: {source}")
        payload = _strict_json(source)
        if not isinstance(payload, Mapping):
            raise ValueError("development residual bundle must be an object")
        if (
            payload.get("schema_version") != DEVELOPMENT_MODEL_VERSION
            or payload.get("status") != "complete"
            or payload.get("purpose")
            != "development_residual_model_for_planner_experiments"
            or payload.get("model_family")
            != "one_state_conditional_autoregressive_gaussian"
            or payload.get("selection_basis")
            != "smallest_tested_nonbinding_ceiling_above_the_identical_interior_optimum"
            or payload.get("development_planner_model_frozen") is not True
            or payload.get("final_model_selection_authorized") is not False
            or payload.get("journey_level_generalization_estimated") is not False
            or payload.get("selected_after_held_out_performance_evaluation")
            is not False
            or payload.get("strict_v0153_performance_gate_passed") is not False
            or payload.get(
                "higher_ceiling_fits_identical_except_configured_ceiling"
            )
            is not True
        ):
            raise ValueError("development residual bundle authorization differs")
        if not np.isclose(
            float(payload.get("selected_ar_ceiling", -1.0)),
            SELECTED_DEVELOPMENT_AR_CEILING,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError("development residual bundle AR ceiling differs")
        standardizer_payload = payload.get("standardizer")
        model_payload = payload.get("model")
        if not isinstance(standardizer_payload, Mapping) or not isinstance(
            model_payload, Mapping
        ):
            raise ValueError("development residual bundle model payload is missing")
        standardizer = SequenceStandardizer.from_dict(standardizer_payload)
        model = AutoregressiveInputOutputHMM.from_dict(model_payload)
        if model.to_dict().get("converged") is not True:
            raise ValueError("development residual model must be converged")
        return cls(model=model, standardizer=standardizer, metadata=payload)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._standardizer.feature_names

    @property
    def stations_m(self) -> tuple[float, ...]:
        return self._standardizer.stations_m

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    @staticmethod
    def _validated_inputs(
        conditions: ArrayLike,
        lengths: ArrayLike,
    ) -> tuple[FloatArray, IntegerArray, NDArray[np.bool_]]:
        values = np.asarray(conditions, dtype=np.float64)
        raw_lengths = np.asarray(lengths)
        if values.ndim != 3 or values.shape[0] < 1:
            raise ValueError("conditions must have shape [B,T,6]")
        if values.shape[2] != len(BMW_CONDITION_FEATURE_NAMES):
            raise ValueError("conditions must use BMW condition schema v1")
        if raw_lengths.shape != (values.shape[0],):
            raise ValueError("lengths must have shape [B]")
        if raw_lengths.dtype == np.bool_ or not np.issubdtype(
            raw_lengths.dtype, np.integer
        ):
            raise TypeError("lengths must use an integer dtype")
        sequence_lengths = np.asarray(raw_lengths, dtype=np.int64)
        if np.any(sequence_lengths < 1) or np.any(
            sequence_lengths > values.shape[1]
        ):
            raise ValueError("sequence lengths are invalid")
        if not np.all(np.isfinite(values)):
            raise ValueError("conditions must be finite")
        time_mask = (
            np.arange(values.shape[1])[None, :] < sequence_lengths[:, None]
        )
        if np.any(values[~time_mask] != 0.0):
            raise ValueError("padded physical condition frames must be zero")
        return values, sequence_lengths, time_mask

    def sample(
        self,
        conditions: ArrayLike,
        lengths: ArrayLike,
        *,
        sample_count: int,
        seed: int,
    ) -> SampleResult:
        """Generate free-running H100 residual sequences in physical metres."""

        physical, sequence_lengths, time_mask = self._validated_inputs(
            conditions, lengths
        )
        standardized = np.zeros_like(physical)
        standardized[time_mask] = (
            physical[time_mask] - self._standardizer.condition_mean
        ) / self._standardizer.condition_scale
        generated = self._model.sample(
            standardized,
            sequence_lengths,
            sample_count=sample_count,
            seed=seed,
        )
        values_m = np.zeros_like(generated.values)
        for sequence_index, raw_length in enumerate(sequence_lengths):
            length = int(raw_length)
            values_m[:, sequence_index, :length] = (
                generated.values[:, sequence_index, :length]
                * self._standardizer.residual_scale_m[None, None, :]
                + self._standardizer.residual_mean_m[None, None, :]
            )
        return SampleResult(
            values=values_m,
            lengths=sequence_lengths,
            stations_m=self._standardizer.stations_m,
            standardized=False,
            valid_mask=generated.valid_mask,
        )


__all__ = [
    "DEVELOPMENT_MODEL_VERSION",
    "DevelopmentResidualModel",
    "SELECTED_DEVELOPMENT_AR_CEILING",
]
