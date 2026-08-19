"""Canonical sequential contract for the three thesis model families.

The v0.8.0 cohort is frame based.  Temporal models must not interpret a
missing pair range or a multi-second recording gap as one ordinary transition.
This module converts immutable H100 frames into contiguous, recording-local
sequences and provides leakage-safe train-drive standardization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .residual_dataset import CANONICAL_MODEL_STATIONS_M

FloatArray = NDArray[np.float64]
IntegerArray = NDArray[np.int64]
BooleanArray = NDArray[np.bool_]

BMW_CONDITION_FEATURE_NAMES = (
    "speed_mps",
    "estimated_mean_abs_curvature_per_m",
    "estimated_curvature_delta_per_m",
    "confidence_near_mean",
    "confidence_middle_mean",
    "confidence_far_mean",
)
DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS = 200.0


def _readonly_array(
    values: ArrayLike,
    *,
    dtype: np.dtype[Any],
    name: str,
) -> np.ndarray:
    array = np.asarray(values, dtype=dtype)
    if not np.all(np.isfinite(array)) and np.issubdtype(array.dtype, np.floating):
        raise ValueError(f"{name} must be finite")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SequenceFrame:
    """One complete conditional H100 frame with temporal provenance."""

    recording_id: str
    drive_id: str
    pair_index: int
    estimate_message_index: int
    estimate_source_time_ns_private: int
    conditions: ArrayLike = field(repr=False)
    residuals_m: ArrayLike = field(repr=False)

    def __post_init__(self) -> None:
        if not self.recording_id or not self.drive_id:
            raise ValueError("frame recording_id and drive_id must be nonempty")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, np.integer))
            for value in (
                self.pair_index,
                self.estimate_message_index,
                self.estimate_source_time_ns_private,
            )
        ):
            raise TypeError("frame indices and timestamps must be integers")
        if min(
            self.pair_index,
            self.estimate_message_index,
            self.estimate_source_time_ns_private,
        ) < 0:
            raise ValueError("frame indices and timestamps must be nonnegative")
        conditions = _readonly_array(
            self.conditions,
            dtype=np.dtype(np.float64),
            name="frame conditions",
        )
        residuals = _readonly_array(
            self.residuals_m,
            dtype=np.dtype(np.float64),
            name="frame residuals",
        )
        if conditions.shape != (len(BMW_CONDITION_FEATURE_NAMES),):
            raise ValueError("frame must contain exactly six BMW conditions")
        if residuals.shape != (len(CANONICAL_MODEL_STATIONS_M),):
            raise ValueError("frame must contain exactly 21 H100 residuals")
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "residuals_m", residuals)

    @property
    def key(self) -> tuple[str, int]:
        return self.recording_id, self.pair_index


@dataclass(frozen=True)
class ResidualSequence:
    """One contiguous run that never crosses a recording or detected gap."""

    sequence_id: str
    recording_id: str
    drive_id: str
    segment_index: int
    start_reason: str
    preceding_pair_index_gap: int | None
    preceding_time_gap_ms: float | None
    frames: tuple[SequenceFrame, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.sequence_id or not self.recording_id or not self.drive_id:
            raise ValueError("sequence identifiers must be nonempty")
        if self.segment_index < 1 or not self.frames:
            raise ValueError("sequence must have a positive index and frames")
        if self.start_reason not in {
            "recording_start",
            "pair_index_gap",
            "time_gap",
            "pair_index_and_time_gap",
        }:
            raise ValueError("unknown sequence start reason")
        if self.start_reason == "recording_start":
            if (
                self.preceding_pair_index_gap is not None
                or self.preceding_time_gap_ms is not None
            ):
                raise ValueError("recording start cannot have preceding gap values")
        else:
            if self.preceding_pair_index_gap is None or self.preceding_time_gap_ms is None:
                raise ValueError("split sequence must retain both preceding gaps")
            if self.preceding_pair_index_gap < 1:
                raise ValueError("preceding pair-index gap must be positive")
            if (
                not math.isfinite(self.preceding_time_gap_ms)
                or self.preceding_time_gap_ms <= 0.0
            ):
                raise ValueError("preceding time gap must be finite and positive")
        keys = [frame.key for frame in self.frames]
        if len(keys) != len(set(keys)):
            raise ValueError("sequence frame keys must be unique")
        for frame in self.frames:
            if frame.recording_id != self.recording_id or frame.drive_id != self.drive_id:
                raise ValueError("sequence frames disagree with sequence provenance")
        for previous, current in zip(self.frames, self.frames[1:]):
            if current.pair_index != previous.pair_index + 1:
                raise ValueError("sequence pair indices must be consecutive")
            if (
                current.estimate_source_time_ns_private
                <= previous.estimate_source_time_ns_private
            ):
                raise ValueError("sequence timestamps must be strictly increasing")

    @property
    def length(self) -> int:
        return len(self.frames)

    @property
    def duration_s(self) -> float:
        if self.length == 1:
            return 0.0
        return (
            self.frames[-1].estimate_source_time_ns_private
            - self.frames[0].estimate_source_time_ns_private
        ) / 1e9

    @property
    def interval_ms(self) -> FloatArray:
        timestamps = np.asarray(
            [frame.estimate_source_time_ns_private for frame in self.frames],
            dtype=np.int64,
        )
        return np.diff(timestamps).astype(np.float64) / 1e6


@dataclass(frozen=True)
class PaddedSequenceDataset:
    """Model-facing padded sequence arrays shared by all three models."""

    sequence_ids: ArrayLike
    recording_ids: ArrayLike
    drive_ids: ArrayLike
    conditions: ArrayLike
    residuals_m: ArrayLike
    valid_mask: ArrayLike
    lengths: ArrayLike
    pair_indices: ArrayLike
    estimate_message_indices: ArrayLike
    estimate_source_times_ns_private: ArrayLike
    feature_names: tuple[str, ...] = BMW_CONDITION_FEATURE_NAMES
    stations_m: tuple[float, ...] = CANONICAL_MODEL_STATIONS_M
    standardized: bool = False

    def __post_init__(self) -> None:
        sequence_ids = np.asarray(self.sequence_ids, dtype=np.str_)
        recording_ids = np.asarray(self.recording_ids, dtype=np.str_)
        drive_ids = np.asarray(self.drive_ids, dtype=np.str_)
        conditions = np.asarray(self.conditions, dtype=np.float64)
        residuals = np.asarray(self.residuals_m, dtype=np.float64)
        valid_mask = np.asarray(self.valid_mask, dtype=np.bool_)
        lengths = np.asarray(self.lengths, dtype=np.int64)
        pair_indices = np.asarray(self.pair_indices, dtype=np.int64)
        message_indices = np.asarray(self.estimate_message_indices, dtype=np.int64)
        source_times = np.asarray(
            self.estimate_source_times_ns_private,
            dtype=np.int64,
        )
        if conditions.ndim != 3 or conditions.shape[0] == 0:
            raise ValueError("conditions must have shape [B,T,F]")
        sequence_count, maximum_length, feature_count = conditions.shape
        station_count = len(self.stations_m)
        if feature_count != len(self.feature_names):
            raise ValueError("feature names do not match condition columns")
        if tuple(self.feature_names) != BMW_CONDITION_FEATURE_NAMES:
            raise ValueError("dataset feature contract is not BMW condition schema v1")
        if tuple(float(value) for value in self.stations_m) != (
            CANONICAL_MODEL_STATIONS_M
        ):
            raise ValueError("dataset station grid is not canonical H100")
        if residuals.shape != (sequence_count, maximum_length, station_count):
            raise ValueError("residuals must have shape [B,T,21]")
        if valid_mask.shape != residuals.shape:
            raise ValueError("valid_mask must match residuals")
        if lengths.shape != (sequence_count,):
            raise ValueError("lengths must have shape [B]")
        for values, name in (
            (sequence_ids, "sequence_ids"),
            (recording_ids, "recording_ids"),
            (drive_ids, "drive_ids"),
        ):
            if values.shape != (sequence_count,) or np.any(values == ""):
                raise ValueError(f"{name} must be nonempty and align with sequences")
        if len(set(sequence_ids.tolist())) != sequence_count:
            raise ValueError("sequence IDs must be unique")
        for values, name in (
            (pair_indices, "pair_indices"),
            (message_indices, "estimate_message_indices"),
            (source_times, "estimate_source_times_ns_private"),
        ):
            if values.shape != (sequence_count, maximum_length):
                raise ValueError(f"{name} must have shape [B,T]")
        if np.any(lengths < 1) or np.any(lengths > maximum_length):
            raise ValueError("sequence lengths are invalid")
        if not np.all(np.isfinite(conditions)) or not np.all(np.isfinite(residuals)):
            raise ValueError("sequence numeric arrays must be finite")
        time_mask = np.arange(maximum_length)[None, :] < lengths[:, None]
        if np.any(conditions[~time_mask] != 0.0):
            raise ValueError("padded conditions must be zero")
        if np.any(residuals[~valid_mask] != 0.0):
            raise ValueError("invalid and padded residuals must be zero")
        if np.any(valid_mask & ~time_mask[:, :, None]):
            raise ValueError("valid_mask must be false on padding")
        if np.any(~np.all(valid_mask[time_mask], axis=1)):
            raise ValueError("active canonical H100 frames must have all stations")
        for values in (pair_indices, message_indices, source_times):
            if np.any(values[time_mask] < 0) or np.any(values[~time_mask] != -1):
                raise ValueError("temporal provenance must use -1 only for padding")
        for array in (
            sequence_ids,
            recording_ids,
            drive_ids,
            conditions,
            residuals,
            valid_mask,
            lengths,
            pair_indices,
            message_indices,
            source_times,
        ):
            array.setflags(write=False)
        object.__setattr__(self, "sequence_ids", sequence_ids)
        object.__setattr__(self, "recording_ids", recording_ids)
        object.__setattr__(self, "drive_ids", drive_ids)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "residuals_m", residuals)
        object.__setattr__(self, "valid_mask", valid_mask)
        object.__setattr__(self, "lengths", lengths)
        object.__setattr__(self, "pair_indices", pair_indices)
        object.__setattr__(self, "estimate_message_indices", message_indices)
        object.__setattr__(self, "estimate_source_times_ns_private", source_times)

    @property
    def time_mask(self) -> BooleanArray:
        return np.arange(self.conditions.shape[1])[None, :] < self.lengths[:, None]

    @property
    def sequence_count(self) -> int:
        return len(self.lengths)

    @property
    def frame_count(self) -> int:
        return int(np.sum(self.lengths))

    def select_drive_ids(
        self,
        drive_ids: Sequence[str],
    ) -> "PaddedSequenceDataset":
        """Return complete sequences from exactly the requested physical drives."""

        requested = tuple(sorted(str(value) for value in drive_ids))
        if (
            not requested
            or any(not value for value in requested)
            or len(set(requested)) != len(requested)
        ):
            raise ValueError("selected drive IDs must be nonempty and unique")
        unknown = sorted(set(requested) - set(self.drive_ids.tolist()))
        if unknown:
            raise ValueError(f"unknown selected drive IDs: {unknown}")
        selected = np.isin(self.drive_ids, requested)
        return PaddedSequenceDataset(
            sequence_ids=self.sequence_ids[selected],
            recording_ids=self.recording_ids[selected],
            drive_ids=self.drive_ids[selected],
            conditions=self.conditions[selected],
            residuals_m=self.residuals_m[selected],
            valid_mask=self.valid_mask[selected],
            lengths=self.lengths[selected],
            pair_indices=self.pair_indices[selected],
            estimate_message_indices=self.estimate_message_indices[selected],
            estimate_source_times_ns_private=(
                self.estimate_source_times_ns_private[selected]
            ),
            feature_names=self.feature_names,
            stations_m=self.stations_m,
            standardized=self.standardized,
        )


@dataclass(frozen=True)
class SequentialResidualDataset:
    """Raw physical-unit sequences and the declared continuity threshold."""

    sequences: tuple[ResidualSequence, ...]
    maximum_contiguous_gap_ms: float

    def __post_init__(self) -> None:
        if not self.sequences:
            raise ValueError("sequential dataset requires at least one sequence")
        if (
            not math.isfinite(self.maximum_contiguous_gap_ms)
            or self.maximum_contiguous_gap_ms <= 0.0
        ):
            raise ValueError("maximum contiguous gap must be finite and positive")
        sequence_ids = [sequence.sequence_id for sequence in self.sequences]
        if len(sequence_ids) != len(set(sequence_ids)):
            raise ValueError("sequential dataset sequence IDs must be unique")
        frame_keys = [
            frame.key for sequence in self.sequences for frame in sequence.frames
        ]
        if len(frame_keys) != len(set(frame_keys)):
            raise ValueError("sequential dataset frame keys must be unique")
        maximum_gap_ns = self.maximum_contiguous_gap_ms * 1e6
        for sequence in self.sequences:
            intervals_ns = np.diff(
                [
                    frame.estimate_source_time_ns_private
                    for frame in sequence.frames
                ]
            )
            if len(intervals_ns) and np.any(intervals_ns > maximum_gap_ns):
                raise ValueError("sequence contains an interval above the gap limit")

    @property
    def frame_count(self) -> int:
        return sum(sequence.length for sequence in self.sequences)

    @property
    def drive_ids(self) -> tuple[str, ...]:
        return tuple(sorted({sequence.drive_id for sequence in self.sequences}))

    def to_padded(self) -> PaddedSequenceDataset:
        sequence_count = len(self.sequences)
        maximum_length = max(sequence.length for sequence in self.sequences)
        feature_count = len(BMW_CONDITION_FEATURE_NAMES)
        station_count = len(CANONICAL_MODEL_STATIONS_M)
        conditions = np.zeros(
            (sequence_count, maximum_length, feature_count),
            dtype=np.float64,
        )
        residuals = np.zeros(
            (sequence_count, maximum_length, station_count),
            dtype=np.float64,
        )
        valid_mask = np.zeros_like(residuals, dtype=np.bool_)
        pair_indices = np.full((sequence_count, maximum_length), -1, dtype=np.int64)
        message_indices = np.full_like(pair_indices, -1)
        source_times = np.full_like(pair_indices, -1)
        lengths = np.asarray(
            [sequence.length for sequence in self.sequences],
            dtype=np.int64,
        )
        for sequence_index, sequence in enumerate(self.sequences):
            length = sequence.length
            conditions[sequence_index, :length] = np.vstack(
                [frame.conditions for frame in sequence.frames]
            )
            residuals[sequence_index, :length] = np.vstack(
                [frame.residuals_m for frame in sequence.frames]
            )
            valid_mask[sequence_index, :length] = True
            pair_indices[sequence_index, :length] = [
                frame.pair_index for frame in sequence.frames
            ]
            message_indices[sequence_index, :length] = [
                frame.estimate_message_index for frame in sequence.frames
            ]
            source_times[sequence_index, :length] = [
                frame.estimate_source_time_ns_private for frame in sequence.frames
            ]
        return PaddedSequenceDataset(
            sequence_ids=[sequence.sequence_id for sequence in self.sequences],
            recording_ids=[sequence.recording_id for sequence in self.sequences],
            drive_ids=[sequence.drive_id for sequence in self.sequences],
            conditions=conditions,
            residuals_m=residuals,
            valid_mask=valid_mask,
            lengths=lengths,
            pair_indices=pair_indices,
            estimate_message_indices=message_indices,
            estimate_source_times_ns_private=source_times,
        )


def build_contiguous_sequences(
    frames: Sequence[SequenceFrame],
    *,
    maximum_contiguous_gap_ms: float = DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
) -> SequentialResidualDataset:
    """Split canonical-order frames at recording, pair-index, or time gaps."""

    if not frames:
        raise ValueError("at least one sequence frame is required")
    if (
        not math.isfinite(maximum_contiguous_gap_ms)
        or maximum_contiguous_gap_ms <= 0.0
    ):
        raise ValueError("maximum contiguous gap must be finite and positive")
    keys = [frame.key for frame in frames]
    if len(keys) != len(set(keys)):
        raise ValueError("input sequence frame keys must be unique")
    recording_blocks: list[tuple[str, list[SequenceFrame]]] = []
    closed_recordings: set[str] = set()
    for frame in frames:
        if not recording_blocks or recording_blocks[-1][0] != frame.recording_id:
            if frame.recording_id in closed_recordings:
                raise ValueError("recording rows must occupy one canonical block")
            if recording_blocks:
                closed_recordings.add(recording_blocks[-1][0])
            recording_blocks.append((frame.recording_id, []))
        recording_blocks[-1][1].append(frame)

    maximum_gap_ns = maximum_contiguous_gap_ms * 1e6
    sequences: list[ResidualSequence] = []
    for recording_id, recording_frames in recording_blocks:
        drive_ids = {frame.drive_id for frame in recording_frames}
        if len(drive_ids) != 1:
            raise ValueError("one recording cannot belong to multiple drives")
        previous: SequenceFrame | None = None
        segment_frames: list[SequenceFrame] = []
        start_reason = "recording_start"
        preceding_pair_gap: int | None = None
        preceding_time_gap_ms: float | None = None
        segment_index = 0

        def close_segment() -> None:
            nonlocal segment_index, segment_frames
            if not segment_frames:
                return
            segment_index += 1
            sequences.append(
                ResidualSequence(
                    sequence_id=f"{recording_id}_segment_{segment_index:03d}",
                    recording_id=recording_id,
                    drive_id=segment_frames[0].drive_id,
                    segment_index=segment_index,
                    start_reason=start_reason,
                    preceding_pair_index_gap=preceding_pair_gap,
                    preceding_time_gap_ms=preceding_time_gap_ms,
                    frames=tuple(segment_frames),
                )
            )
            segment_frames = []

        for frame in recording_frames:
            if previous is not None:
                pair_gap = frame.pair_index - previous.pair_index
                time_gap_ns = (
                    frame.estimate_source_time_ns_private
                    - previous.estimate_source_time_ns_private
                )
                if pair_gap <= 0:
                    raise ValueError("recording pair indices must increase")
                if time_gap_ns <= 0:
                    raise ValueError("recording source timestamps must increase")
                pair_break = pair_gap != 1
                time_break = time_gap_ns > maximum_gap_ns
                if pair_break or time_break:
                    close_segment()
                    if pair_break and time_break:
                        start_reason = "pair_index_and_time_gap"
                    elif pair_break:
                        start_reason = "pair_index_gap"
                    else:
                        start_reason = "time_gap"
                    preceding_pair_gap = pair_gap
                    preceding_time_gap_ms = time_gap_ns / 1e6
            segment_frames.append(frame)
            previous = frame
        close_segment()
    return SequentialResidualDataset(
        sequences=tuple(sequences),
        maximum_contiguous_gap_ms=float(maximum_contiguous_gap_ms),
    )


@dataclass(frozen=True)
class SequenceStandardizer:
    """Training-drive-only transforms for conditions and station residuals."""

    feature_names: tuple[str, ...]
    stations_m: tuple[float, ...]
    train_drive_ids: tuple[str, ...]
    condition_mean: ArrayLike
    condition_scale: ArrayLike
    residual_mean_m: ArrayLike
    residual_scale_m: ArrayLike
    training_frame_count: int
    residual_observation_count_by_station: ArrayLike
    minimum_scale: float
    constant_condition_indices: tuple[int, ...] = ()
    constant_residual_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        condition_mean = np.asarray(self.condition_mean, dtype=np.float64)
        condition_scale = np.asarray(self.condition_scale, dtype=np.float64)
        residual_mean = np.asarray(self.residual_mean_m, dtype=np.float64)
        residual_scale = np.asarray(self.residual_scale_m, dtype=np.float64)
        residual_counts = np.asarray(
            self.residual_observation_count_by_station,
            dtype=np.int64,
        )
        if self.feature_names != BMW_CONDITION_FEATURE_NAMES:
            raise ValueError("standardizer feature contract is not BMW schema v1")
        if self.stations_m != CANONICAL_MODEL_STATIONS_M:
            raise ValueError("standardizer station grid is not canonical H100")
        if not self.train_drive_ids or len(set(self.train_drive_ids)) != len(
            self.train_drive_ids
        ):
            raise ValueError("train drive IDs must be nonempty and unique")
        if self.training_frame_count < 2:
            raise ValueError("standardizer needs at least two training frames")
        if not math.isfinite(self.minimum_scale) or self.minimum_scale <= 0.0:
            raise ValueError("minimum scale must be finite and positive")
        if condition_mean.shape != (len(self.feature_names),) or condition_scale.shape != (
            len(self.feature_names),
        ):
            raise ValueError("condition transform has the wrong shape")
        if residual_mean.shape != (len(self.stations_m),) or residual_scale.shape != (
            len(self.stations_m),
        ):
            raise ValueError("residual transform has the wrong shape")
        if residual_counts.shape != (len(self.stations_m),):
            raise ValueError("residual counts have the wrong shape")
        for values, name in (
            (condition_mean, "condition mean"),
            (condition_scale, "condition scale"),
            (residual_mean, "residual mean"),
            (residual_scale, "residual scale"),
        ):
            if not np.all(np.isfinite(values)):
                raise ValueError(f"{name} must be finite")
        if np.any(condition_scale <= 0.0) or np.any(residual_scale <= 0.0):
            raise ValueError("standardizer scales must be positive")
        if np.any(residual_counts < 2):
            raise ValueError("each residual station needs at least two observations")
        for index in self.constant_condition_indices:
            if index < 0 or index >= len(self.feature_names):
                raise ValueError("constant condition index is invalid")
        for index in self.constant_residual_indices:
            if index < 0 or index >= len(self.stations_m):
                raise ValueError("constant residual index is invalid")
        for array in (
            condition_mean,
            condition_scale,
            residual_mean,
            residual_scale,
            residual_counts,
        ):
            array.setflags(write=False)
        object.__setattr__(self, "condition_mean", condition_mean)
        object.__setattr__(self, "condition_scale", condition_scale)
        object.__setattr__(self, "residual_mean_m", residual_mean)
        object.__setattr__(self, "residual_scale_m", residual_scale)
        object.__setattr__(
            self,
            "residual_observation_count_by_station",
            residual_counts,
        )

    @classmethod
    def fit(
        cls,
        dataset: PaddedSequenceDataset,
        *,
        train_drive_ids: Sequence[str],
        minimum_scale: float = 1e-12,
    ) -> "SequenceStandardizer":
        if dataset.standardized:
            raise ValueError("standardizer must fit physical-unit data")
        drives = tuple(sorted(str(value) for value in train_drive_ids))
        if not drives or any(not value for value in drives) or len(set(drives)) != len(
            drives
        ):
            raise ValueError("train_drive_ids must be nonempty and unique")
        if not math.isfinite(minimum_scale) or minimum_scale <= 0.0:
            raise ValueError("minimum_scale must be finite and positive")
        unknown = sorted(set(drives) - set(dataset.drive_ids.tolist()))
        if unknown:
            raise ValueError(f"unknown training drive IDs: {unknown}")
        selected_sequences = np.isin(dataset.drive_ids, drives)
        selected_frames = selected_sequences[:, None] & dataset.time_mask
        condition_values = dataset.conditions[selected_frames]
        if len(condition_values) < 2:
            raise ValueError("selected training drives provide fewer than two frames")
        condition_mean = np.mean(condition_values, axis=0)
        raw_condition_scale = np.std(condition_values, axis=0, ddof=0)
        constant_conditions = tuple(
            int(index)
            for index in np.flatnonzero(raw_condition_scale < minimum_scale)
        )
        condition_scale = raw_condition_scale.copy()
        condition_scale[list(constant_conditions)] = 1.0

        selected_valid = dataset.valid_mask & selected_sequences[:, None, None]
        residual_mean = np.empty(len(dataset.stations_m), dtype=np.float64)
        residual_scale = np.empty_like(residual_mean)
        residual_counts = np.count_nonzero(selected_valid, axis=(0, 1)).astype(
            np.int64
        )
        for station_index in range(len(dataset.stations_m)):
            values = dataset.residuals_m[:, :, station_index][
                selected_valid[:, :, station_index]
            ]
            if len(values) < 2:
                raise ValueError("training drive has insufficient station observations")
            residual_mean[station_index] = np.mean(values)
            residual_scale[station_index] = np.std(values, ddof=0)
        constant_residuals = tuple(
            int(index) for index in np.flatnonzero(residual_scale < minimum_scale)
        )
        residual_scale[list(constant_residuals)] = 1.0
        return cls(
            feature_names=dataset.feature_names,
            stations_m=dataset.stations_m,
            train_drive_ids=drives,
            condition_mean=condition_mean,
            condition_scale=condition_scale,
            residual_mean_m=residual_mean,
            residual_scale_m=residual_scale,
            training_frame_count=len(condition_values),
            residual_observation_count_by_station=residual_counts,
            minimum_scale=float(minimum_scale),
            constant_condition_indices=constant_conditions,
            constant_residual_indices=constant_residuals,
        )

    def standardized_copy(
        self,
        dataset: PaddedSequenceDataset,
    ) -> PaddedSequenceDataset:
        if dataset.standardized:
            raise ValueError("dataset is already standardized")
        if dataset.feature_names != self.feature_names or dataset.stations_m != self.stations_m:
            raise ValueError("dataset is incompatible with standardizer")
        time_mask = dataset.time_mask
        conditions = np.zeros_like(dataset.conditions)
        conditions[time_mask] = (
            dataset.conditions[time_mask] - self.condition_mean
        ) / self.condition_scale
        residuals = np.zeros_like(dataset.residuals_m)
        for station_index in range(len(self.stations_m)):
            mask = dataset.valid_mask[:, :, station_index]
            residuals[:, :, station_index][mask] = (
                dataset.residuals_m[:, :, station_index][mask]
                - self.residual_mean_m[station_index]
            ) / self.residual_scale_m[station_index]
        return PaddedSequenceDataset(
            sequence_ids=dataset.sequence_ids,
            recording_ids=dataset.recording_ids,
            drive_ids=dataset.drive_ids,
            conditions=conditions,
            residuals_m=residuals,
            valid_mask=dataset.valid_mask,
            lengths=dataset.lengths,
            pair_indices=dataset.pair_indices,
            estimate_message_indices=dataset.estimate_message_indices,
            estimate_source_times_ns_private=(
                dataset.estimate_source_times_ns_private
            ),
            feature_names=dataset.feature_names,
            stations_m=dataset.stations_m,
            standardized=True,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SequenceStandardizer":
        """Reconstruct a validated v0.9.0 fold standardizer."""

        if payload.get("schema_version") != "0.9.0":
            raise ValueError("standardizer schema version must be 0.9.0")
        if payload.get("fitted_split_role") != "training_drives_only":
            raise ValueError("standardizer must be fitted on training drives only")
        try:
            return cls(
                feature_names=tuple(str(value) for value in payload["feature_names"]),
                stations_m=tuple(float(value) for value in payload["stations_m"]),
                train_drive_ids=tuple(
                    str(value) for value in payload["train_drive_ids"]
                ),
                training_frame_count=int(payload["training_frame_count"]),
                condition_mean=payload["condition_mean"],
                condition_scale=payload["condition_scale"],
                residual_mean_m=payload["residual_mean_m"],
                residual_scale_m=payload["residual_scale_m"],
                residual_observation_count_by_station=(
                    payload["residual_observation_count_by_station"]
                ),
                minimum_scale=float(payload["minimum_scale"]),
                constant_condition_indices=tuple(
                    int(value) for value in payload["constant_condition_indices"]
                ),
                constant_residual_indices=tuple(
                    int(value) for value in payload["constant_residual_indices"]
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid standardizer payload: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "0.9.0",
            "fitted_split_role": "training_drives_only",
            "feature_names": list(self.feature_names),
            "stations_m": list(self.stations_m),
            "train_drive_ids": list(self.train_drive_ids),
            "training_frame_count": self.training_frame_count,
            "condition_mean": self.condition_mean.tolist(),
            "condition_scale": self.condition_scale.tolist(),
            "residual_mean_m": self.residual_mean_m.tolist(),
            "residual_scale_m": self.residual_scale_m.tolist(),
            "residual_observation_count_by_station": (
                self.residual_observation_count_by_station.tolist()
            ),
            "minimum_scale": self.minimum_scale,
            "constant_condition_indices": list(self.constant_condition_indices),
            "constant_residual_indices": list(self.constant_residual_indices),
        }


__all__ = [
    "BMW_CONDITION_FEATURE_NAMES",
    "DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS",
    "PaddedSequenceDataset",
    "ResidualSequence",
    "SequenceFrame",
    "SequenceStandardizer",
    "SequentialResidualDataset",
    "build_contiguous_sequences",
]
