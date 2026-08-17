"""Fail-closed construction of the canonical H100 residual-vector dataset.

The accepted v0.5.0 alignment batch contains station-long comparison rows and
one pair audit row per recording-local temporal match.  This module freezes the
model input contract: one observation is one complete 21-dimensional vector on
the immutable ``0, 5, ..., 100 m`` grid.  Available-case station rows are never
admitted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

CANONICAL_MODEL_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))


class ResidualDatasetContractError(ValueError):
    """Raised when accepted alignment evidence cannot form canonical vectors."""


def residual_column_name(station_m: float) -> str:
    """Return the stable wide-CSV residual column for a canonical station."""

    numeric_station = float(station_m)
    if (
        not math.isfinite(numeric_station)
        or numeric_station < 0.0
        or not numeric_station.is_integer()
    ):
        raise ValueError("residual station must be a finite nonnegative integer")
    return f"residual_{int(numeric_station):03d}m_m"


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = str(row.get(key, "")).strip()
    if not value:
        raise ResidualDatasetContractError(f"{key} must be present and nonempty")
    return value


def _required_int(row: Mapping[str, Any], key: str) -> int:
    value = _required_text(row, key)
    try:
        parsed = int(value)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be an integer") from error
    if parsed < 0:
        raise ResidualDatasetContractError(f"{key} must be nonnegative")
    return parsed


def _required_finite_float(row: Mapping[str, Any], key: str) -> float:
    value = _required_text(row, key)
    try:
        parsed = float(value)
    except ValueError as error:
        raise ResidualDatasetContractError(f"{key} must be numeric") from error
    if not math.isfinite(parsed):
        raise ResidualDatasetContractError(f"{key} must be finite")
    return parsed


def _strict_bool(row: Mapping[str, Any], key: str) -> bool:
    value = row.get(key)
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ResidualDatasetContractError(f"{key} must be exactly true or false")


@dataclass(frozen=True)
class ResidualObservation:
    """One complete H100 residual vector and its recording-local provenance."""

    recording_id: str
    drive_id: str
    pair_index: int
    estimate_message_index: int
    map_message_index: int
    estimate_source_time_ns_private: int
    map_source_time_ns_private: int
    source_delta_ms: float
    residuals_m: FloatArray = field(repr=False)

    def __post_init__(self) -> None:
        residuals = np.asarray(self.residuals_m, dtype=np.float64)
        if not self.recording_id or not self.drive_id:
            raise ValueError("recording_id and drive_id must be nonempty")
        if any(
            value < 0
            for value in (
                self.pair_index,
                self.estimate_message_index,
                self.map_message_index,
                self.estimate_source_time_ns_private,
                self.map_source_time_ns_private,
            )
        ):
            raise ValueError("observation indices and timestamps must be nonnegative")
        if not math.isfinite(self.source_delta_ms):
            raise ValueError("source_delta_ms must be finite")
        timestamp_delta_ms = (
            self.estimate_source_time_ns_private
            - self.map_source_time_ns_private
        ) / 1e6
        if not math.isclose(
            self.source_delta_ms,
            timestamp_delta_ms,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise ValueError("source_delta_ms does not reconcile with source times")
        if residuals.shape != (len(CANONICAL_MODEL_STATIONS_M),):
            raise ValueError("residual vector must have exactly 21 H100 values")
        if not np.all(np.isfinite(residuals)):
            raise ValueError("residual vector must contain only finite values")
        residuals.setflags(write=False)
        object.__setattr__(self, "residuals_m", residuals)

    @property
    def key(self) -> tuple[str, int]:
        return self.recording_id, self.pair_index

    def as_csv_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "recording_id": self.recording_id,
            "drive_id": self.drive_id,
            "pair_index": self.pair_index,
            "estimate_message_index": self.estimate_message_index,
            "map_message_index": self.map_message_index,
            "estimate_source_time_ns_private": self.estimate_source_time_ns_private,
            "map_source_time_ns_private": self.map_source_time_ns_private,
            "source_delta_ms": self.source_delta_ms,
        }
        row.update(
            {
                residual_column_name(station): float(self.residuals_m[index])
                for index, station in enumerate(CANONICAL_MODEL_STATIONS_M)
            }
        )
        return row


@dataclass(frozen=True)
class CanonicalResidualDataset:
    """Immutable canonical observations with convenience matrix accessors."""

    observations: tuple[ResidualObservation, ...]

    def __post_init__(self) -> None:
        if len(self.observations) < 2:
            raise ValueError("canonical residual dataset requires at least two vectors")
        keys = [observation.key for observation in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("canonical residual observation keys must be unique")

    @property
    def matrix_m(self) -> FloatArray:
        return np.vstack([observation.residuals_m for observation in self.observations])

    @property
    def drive_ids(self) -> tuple[str, ...]:
        return tuple(observation.drive_id for observation in self.observations)

    @property
    def recording_ids(self) -> tuple[str, ...]:
        return tuple(observation.recording_id for observation in self.observations)


def build_canonical_residual_dataset(
    pair_rows: Sequence[Mapping[str, Any]],
    station_rows: Sequence[Mapping[str, Any]],
    *,
    recording_drive_ids: Mapping[str, str],
) -> CanonicalResidualDataset:
    """Build H100 vectors while enforcing cohort and exact-manifest invariants."""

    pair_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    eligible_keys: set[tuple[str, int]] = set()
    for row in pair_rows:
        recording_id = _required_text(row, "recording_id")
        pair_index = _required_int(row, "pair_index")
        drive_id = _required_text(row, "drive_id")
        key = recording_id, pair_index
        if key in pair_by_key:
            raise ResidualDatasetContractError(f"duplicate pair audit row for {key}")
        expected_drive_id = recording_drive_ids.get(recording_id)
        if expected_drive_id is None:
            raise ResidualDatasetContractError(
                f"pair row references recording absent from exact manifest: {recording_id}"
            )
        if drive_id != expected_drive_id:
            raise ResidualDatasetContractError(
                f"drive_id disagrees with exact manifest for {recording_id}"
            )
        h60_eligible = _strict_bool(row, "h60_aligned_eligible")
        h100_eligible = _strict_bool(row, "h100_aligned_eligible")
        if h100_eligible and not h60_eligible:
            raise ResidualDatasetContractError("H100 cohort must be a subset of H60")
        if h100_eligible:
            if _required_text(row, "pair_state") != "aligned_h100_ready":
                raise ResidualDatasetContractError(
                    f"H100 pair {key} is not in aligned_h100_ready state"
                )
            if str(row.get("failure_code", "")).strip():
                raise ResidualDatasetContractError(
                    f"H100 pair {key} has a nonempty failure_code"
                )
            eligible_keys.add(key)
        pair_by_key[key] = row

    if not eligible_keys:
        raise ResidualDatasetContractError("no complete H100 pairs are available")

    residual_by_key: dict[tuple[str, int], dict[float, float]] = {
        key: {} for key in eligible_keys
    }
    canonical_stations = set(CANONICAL_MODEL_STATIONS_M)
    for row in station_rows:
        recording_id = _required_text(row, "recording_id")
        pair_index = _required_int(row, "pair_index")
        drive_id = _required_text(row, "drive_id")
        key = recording_id, pair_index
        if key not in pair_by_key:
            raise ResidualDatasetContractError(
                f"station row has no corresponding pair audit row: {key}"
            )
        expected_drive_id = recording_drive_ids.get(recording_id)
        if expected_drive_id is None:
            raise ResidualDatasetContractError(
                f"station row references recording absent from exact manifest: {recording_id}"
            )
        if drive_id != expected_drive_id:
            raise ResidualDatasetContractError(
                f"station drive_id disagrees with exact manifest for {recording_id}"
            )
        station_h100 = _strict_bool(row, "h100_aligned_eligible")
        pair_is_h100 = key in eligible_keys
        if station_h100 != pair_is_h100:
            raise ResidualDatasetContractError(
                f"station/pair H100 membership disagrees for {key}"
            )
        if not pair_is_h100:
            continue
        station = _required_finite_float(row, "station_m")
        if station not in canonical_stations:
            raise ResidualDatasetContractError(
                f"H100 pair {key} contains noncanonical station {station}"
            )
        values = residual_by_key[key]
        if station in values:
            raise ResidualDatasetContractError(
                f"duplicate station {station} for H100 pair {key}"
            )
        values[station] = _required_finite_float(row, "aligned_lateral_m")

    observations: list[ResidualObservation] = []
    for key in sorted(eligible_keys):
        row = pair_by_key[key]
        values = residual_by_key[key]
        if set(values) != canonical_stations:
            missing = sorted(canonical_stations - set(values))
            extra = sorted(set(values) - canonical_stations)
            raise ResidualDatasetContractError(
                f"H100 pair {key} does not have the exact 21-station grid; "
                f"missing={missing}, extra={extra}"
            )
        observations.append(
            ResidualObservation(
                recording_id=key[0],
                drive_id=_required_text(row, "drive_id"),
                pair_index=key[1],
                estimate_message_index=_required_int(row, "estimate_message_index"),
                map_message_index=_required_int(row, "map_message_index"),
                estimate_source_time_ns_private=_required_int(
                    row, "estimate_source_time_ns_private"
                ),
                map_source_time_ns_private=_required_int(
                    row, "map_source_time_ns_private"
                ),
                source_delta_ms=_required_finite_float(row, "source_delta_ms"),
                residuals_m=np.asarray(
                    [values[station] for station in CANONICAL_MODEL_STATIONS_M],
                    dtype=np.float64,
                ),
            )
        )
    return CanonicalResidualDataset(tuple(observations))


RESIDUAL_VECTOR_FIELDS = (
    "recording_id",
    "drive_id",
    "pair_index",
    "estimate_message_index",
    "map_message_index",
    "estimate_source_time_ns_private",
    "map_source_time_ns_private",
    "source_delta_ms",
    *(residual_column_name(station) for station in CANONICAL_MODEL_STATIONS_M),
)


__all__ = [
    "CANONICAL_MODEL_STATIONS_M",
    "CanonicalResidualDataset",
    "RESIDUAL_VECTOR_FIELDS",
    "ResidualDatasetContractError",
    "ResidualObservation",
    "build_canonical_residual_dataset",
    "residual_column_name",
]
