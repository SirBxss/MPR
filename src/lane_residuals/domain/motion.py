"""Rear-axle odometry interpolation and ego-frame motion compensation."""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .geometry_validation import GeometryValidationError
from .pairing import EgoRelativePath

FloatArray = NDArray[np.float64]


def _wrap_angle(value: float) -> float:
    return float((value + math.pi) % (2.0 * math.pi) - math.pi)


@dataclass(frozen=True)
class Pose2D:
    """One finite rear-axle pose in the continuous odometry frame."""

    x_m: float
    y_m: float
    yaw_rad: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.x_m, self.y_m, self.yaw_rad)):
            raise ValueError("pose values must be finite")


@dataclass(frozen=True)
class OdometrySample:
    """One decoded odometry pose with both state and MCAP chronology times."""

    timestamp_ns: int
    log_time_ns: int
    publish_time_ns: int
    pose: Pose2D

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0 or self.log_time_ns < 0 or self.publish_time_ns < 0:
            raise ValueError("odometry timestamps must be nonnegative")


@dataclass(frozen=True)
class PoseInterpolation:
    """Interpolated pose plus the evidence used to construct it."""

    timestamp_ns: int
    pose: Pose2D
    lower_timestamp_ns: int
    upper_timestamp_ns: int
    fraction: float

    def __post_init__(self) -> None:
        if not self.lower_timestamp_ns <= self.timestamp_ns <= self.upper_timestamp_ns:
            raise ValueError("interpolation timestamp must lie within its bracket")
        if not 0.0 <= self.fraction <= 1.0 or not math.isfinite(self.fraction):
            raise ValueError("interpolation fraction must be finite and within [0, 1]")

    @property
    def bracket_span_ms(self) -> float:
        return (self.upper_timestamp_ns - self.lower_timestamp_ns) / 1e6


def interpolate_odometry_pose(
    samples: Sequence[OdometrySample],
    timestamp_ns: int,
    *,
    maximum_bracket_gap_ns: int,
) -> PoseInterpolation:
    """Interpolate position and shortest-arc yaw at one state timestamp."""

    if maximum_bracket_gap_ns < 0:
        raise ValueError("maximum odometry bracket gap must be nonnegative")
    timestamps = [sample.timestamp_ns for sample in samples]
    if len(timestamps) < 2:
        raise GeometryValidationError(
            "odometry_insufficient_samples",
            "at least two odometry samples are required for interpolation",
        )
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise GeometryValidationError(
            "odometry_timestamps_not_strictly_increasing",
            "odometry state timestamps must be strictly increasing",
        )
    position = bisect_left(timestamps, timestamp_ns)
    if position < len(samples) and timestamps[position] == timestamp_ns:
        sample = samples[position]
        return PoseInterpolation(
            timestamp_ns=timestamp_ns,
            pose=sample.pose,
            lower_timestamp_ns=timestamp_ns,
            upper_timestamp_ns=timestamp_ns,
            fraction=0.0,
        )
    if position == 0 or position == len(samples):
        raise GeometryValidationError(
            "odometry_reference_time_outside_coverage",
            "the RLMB pose-validity timestamp is outside odometry coverage",
        )
    lower = samples[position - 1]
    upper = samples[position]
    span_ns = upper.timestamp_ns - lower.timestamp_ns
    if span_ns > maximum_bracket_gap_ns:
        raise GeometryValidationError(
            "odometry_interpolation_gap_exceeds_limit",
            "the odometry bracket around the RLMB timestamp is too wide",
        )
    fraction = (timestamp_ns - lower.timestamp_ns) / span_ns
    yaw_delta = _wrap_angle(upper.pose.yaw_rad - lower.pose.yaw_rad)
    return PoseInterpolation(
        timestamp_ns=timestamp_ns,
        pose=Pose2D(
            x_m=lower.pose.x_m + fraction * (upper.pose.x_m - lower.pose.x_m),
            y_m=lower.pose.y_m + fraction * (upper.pose.y_m - lower.pose.y_m),
            yaw_rad=_wrap_angle(lower.pose.yaw_rad + fraction * yaw_delta),
        ),
        lower_timestamp_ns=lower.timestamp_ns,
        upper_timestamp_ns=upper.timestamp_ns,
        fraction=float(fraction),
    )


def latest_odometry_at_or_before_log_time(
    samples: Sequence[OdometrySample],
    log_time_ns: int,
    *,
    maximum_log_lag_ns: int,
) -> tuple[OdometrySample, int]:
    """Approximate DPE's latest odometry state at its recorded output time."""

    if maximum_log_lag_ns < 0:
        raise ValueError("maximum odometry log lag must be nonnegative")
    log_times = [sample.log_time_ns for sample in samples]
    if not log_times or any(right < left for left, right in zip(log_times, log_times[1:])):
        raise GeometryValidationError(
            "odometry_log_times_not_monotonic",
            "odometry MCAP log times must be nondecreasing",
        )
    position = bisect_right(log_times, log_time_ns) - 1
    if position < 0:
        raise GeometryValidationError(
            "odometry_no_sample_at_or_before_estimate_log",
            "no odometry sample was recorded before the EDP message",
        )
    sample = samples[position]
    lag_ns = log_time_ns - sample.log_time_ns
    if lag_ns > maximum_log_lag_ns:
        raise GeometryValidationError(
            "odometry_log_lag_exceeds_limit",
            "the latest odometry sample is too old for the EDP message",
        )
    return sample, lag_ns


@dataclass(frozen=True)
class EgoFrameTransform:
    """Rigid transform mapping source-ego coordinates into target-ego coordinates."""

    source_pose: Pose2D
    target_pose: Pose2D
    translation_target_m: FloatArray = field(repr=False)
    yaw_delta_rad: float

    def __post_init__(self) -> None:
        translation = np.asarray(self.translation_target_m, dtype=np.float64)
        if translation.shape != (2,) or not np.all(np.isfinite(translation)):
            raise ValueError("ego-frame translation must be a finite two-vector")
        if not math.isfinite(self.yaw_delta_rad):
            raise ValueError("ego-frame yaw delta must be finite")
        translation.setflags(write=False)
        object.__setattr__(self, "translation_target_m", translation)

    @property
    def source_to_target_travel_m(self) -> float:
        return float(
            math.hypot(
                self.target_pose.x_m - self.source_pose.x_m,
                self.target_pose.y_m - self.source_pose.y_m,
            )
        )

    def apply_points(self, points_m: ArrayLike) -> FloatArray:
        points = np.asarray(points_m, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
            raise ValueError("points must be a finite array with shape (n, 2)")
        cosine = math.cos(self.yaw_delta_rad)
        sine = math.sin(self.yaw_delta_rad)
        rotation = np.asarray(((cosine, -sine), (sine, cosine)))
        return points @ rotation.T + self.translation_target_m


def ego_frame_transform(source_pose: Pose2D, target_pose: Pose2D) -> EgoFrameTransform:
    """Construct ``q_target = R_target.T * (q_world - p_target)``."""

    target_cosine = math.cos(target_pose.yaw_rad)
    target_sine = math.sin(target_pose.yaw_rad)
    world_delta = np.asarray(
        (source_pose.x_m - target_pose.x_m, source_pose.y_m - target_pose.y_m),
        dtype=np.float64,
    )
    translation_target = np.asarray(
        (
            target_cosine * world_delta[0] + target_sine * world_delta[1],
            -target_sine * world_delta[0] + target_cosine * world_delta[1],
        ),
        dtype=np.float64,
    )
    return EgoFrameTransform(
        source_pose=source_pose,
        target_pose=target_pose,
        translation_target_m=translation_target,
        yaw_delta_rad=_wrap_angle(source_pose.yaw_rad - target_pose.yaw_rad),
    )


def transform_path_to_target_ego_frame(
    path: EgoRelativePath,
    transform: EgoFrameTransform,
) -> EgoRelativePath:
    """Rigidly transform RLMB geometry while retaining its source station domain."""

    points = transform.apply_points(path.points)
    origin = transform.apply_points(path.origin_footpoint_m[None, :])[0]
    return EgoRelativePath(
        source=f"{path.source}_motion_compensated",
        stations_m=path.stations_m,
        x_m=points[:, 0],
        y_m=points[:, 1],
        heading_rad=np.asarray(
            [_wrap_angle(float(value) + transform.yaw_delta_rad) for value in path.heading_rad],
            dtype=np.float64,
        ),
        origin_footpoint_m=origin,
        origin_distance_m=float(np.linalg.norm(origin)),
        origin_heading_rad=_wrap_angle(path.origin_heading_rad + transform.yaw_delta_rad),
        reversed_to_positive_x=path.reversed_to_positive_x,
    )


__all__ = [
    "EgoFrameTransform",
    "OdometrySample",
    "Pose2D",
    "PoseInterpolation",
    "ego_frame_transform",
    "interpolate_odometry_pose",
    "latest_odometry_at_or_before_log_time",
    "transform_path_to_target_ego_frame",
]
