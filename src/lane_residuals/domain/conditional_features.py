"""Prediction-time condition features for the canonical H100 residual vectors.

The feature contract is intentionally small and leakage-safe.  Every feature
comes from the EstimatedDrivePaths message or a vehicle-speed signal available
at the estimate epoch.  RLMB geometry, residual values, and drive identity are
never model inputs.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .geometry_validation import SplineCurve
from .motion import OdometrySample, PoseInterpolation, interpolate_odometry_pose
from .pairing import EgoRelativePath

CANONICAL_CONDITION_STATIONS_M = tuple(float(value) for value in range(0, 101, 5))
CONFIDENCE_BUCKET_SIZE_M = 5.0
CONFIDENCE_MINIMUM = 0.001
CONFIDENCE_MAXIMUM = 1.0
CONFIDENCE_LATERAL_JUMP_VALUE = 0.0123
CONFIDENCE_SAMPLE_CENTERS_M = tuple(
    2.5 + CONFIDENCE_BUCKET_SIZE_M * index for index in range(20)
)
ODOMETRY_SPEED_INTERVAL_NS = 50_000_000
ODOMETRY_SPEED_INTERVAL_MS = ODOMETRY_SPEED_INTERVAL_NS / 1e6


class ConditionalFeatureError(ValueError):
    """Fail-closed feature extraction error with a stable audit code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class LongitudinalSpeedSample:
    """One valid signed rear-axle longitudinal-speed sample."""

    timestamp_ns: int
    value_mps: float
    log_time_ns: int
    publish_time_ns: int

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, (int, np.integer))
            for value in (self.timestamp_ns, self.log_time_ns, self.publish_time_ns)
        ):
            raise ValueError("speed timestamps must be integers")
        if min(self.timestamp_ns, self.log_time_ns, self.publish_time_ns) < 0:
            raise ValueError("speed timestamps must be nonnegative")
        if not math.isfinite(self.value_mps):
            raise ValueError("speed must be finite")


@dataclass(frozen=True)
class InterpolatedSpeed:
    """Signed speed evaluated at one estimate source timestamp."""

    timestamp_ns: int
    value_mps: float
    method: str
    lower_timestamp_ns: int
    upper_timestamp_ns: int

    @property
    def bracket_span_ms(self) -> float:
        return (self.upper_timestamp_ns - self.lower_timestamp_ns) / 1e6


@dataclass(frozen=True)
class DerivedOdometrySpeed:
    """Unsigned rear-axle displacement speed over a fixed time interval."""

    timestamp_ns: int
    value_mps: float
    displacement_m: float
    interval_ns: int
    previous_pose: PoseInterpolation
    current_pose: PoseInterpolation

    def __post_init__(self) -> None:
        if self.interval_ns <= 0:
            raise ValueError("odometry speed interval must be positive")
        if self.timestamp_ns != self.current_pose.timestamp_ns:
            raise ValueError("current pose must be evaluated at the speed timestamp")
        if self.previous_pose.timestamp_ns != self.timestamp_ns - self.interval_ns:
            raise ValueError("previous pose must be evaluated one speed interval earlier")
        if not math.isfinite(self.value_mps) or self.value_mps < 0.0:
            raise ValueError("derived odometry speed must be finite and nonnegative")
        if not math.isfinite(self.displacement_m) or self.displacement_m < 0.0:
            raise ValueError("odometry displacement must be finite and nonnegative")

    @property
    def interval_ms(self) -> float:
        return self.interval_ns / 1e6


@dataclass(frozen=True)
class EstimateConditionFeatures:
    """EDP-only geometry and confidence summaries at one prediction epoch."""

    estimated_mean_abs_curvature_per_m: float
    estimated_curvature_delta_per_m: float
    confidence_near_mean: float
    confidence_middle_mean: float
    confidence_far_mean: float
    confidence_minimum: float
    confidence_floor_fraction: float
    confidence_lateral_jump_detected: bool
    confidence_bucket_count: int
    confidence_native_start_station_m: float
    confidence_native_end_station_m: float


def interpolate_longitudinal_speed(
    samples: Sequence[LongitudinalSpeedSample],
    timestamp_ns: int,
    *,
    maximum_bracket_gap_ns: int,
) -> InterpolatedSpeed:
    """Linearly interpolate speed without extrapolation or cross-file pairing."""

    if isinstance(timestamp_ns, bool) or not isinstance(timestamp_ns, (int, np.integer)):
        raise TypeError("speed target timestamp must be an integer")
    if timestamp_ns < 0:
        raise ValueError("speed target timestamp must be nonnegative")
    if maximum_bracket_gap_ns < 0:
        raise ValueError("maximum speed bracket gap must be nonnegative")
    if not samples:
        raise ConditionalFeatureError(
            "speed_stream_empty",
            "no valid longitudinal-speed samples are available",
        )
    times = [int(sample.timestamp_ns) for sample in samples]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ConditionalFeatureError(
            "speed_timestamps_not_strictly_increasing",
            "valid speed timestamps must be strictly increasing",
        )
    position = bisect_left(times, int(timestamp_ns))
    if position < len(samples) and times[position] == timestamp_ns:
        sample = samples[position]
        return InterpolatedSpeed(
            timestamp_ns=int(timestamp_ns),
            value_mps=float(sample.value_mps),
            method="exact",
            lower_timestamp_ns=int(timestamp_ns),
            upper_timestamp_ns=int(timestamp_ns),
        )
    if position == 0 or position == len(samples):
        raise ConditionalFeatureError(
            "speed_timestamp_outside_coverage",
            "estimate source time lies outside valid speed coverage",
        )
    lower = samples[position - 1]
    upper = samples[position]
    span_ns = upper.timestamp_ns - lower.timestamp_ns
    if span_ns > maximum_bracket_gap_ns:
        raise ConditionalFeatureError(
            "speed_interpolation_gap_too_wide",
            "valid speed samples around the estimate exceed the declared gap",
        )
    fraction = (timestamp_ns - lower.timestamp_ns) / span_ns
    value = lower.value_mps + fraction * (upper.value_mps - lower.value_mps)
    return InterpolatedSpeed(
        timestamp_ns=int(timestamp_ns),
        value_mps=float(value),
        method="linear",
        lower_timestamp_ns=lower.timestamp_ns,
        upper_timestamp_ns=upper.timestamp_ns,
    )


def derive_unsigned_odometry_speed(
    samples: Sequence[OdometrySample],
    timestamp_ns: int,
    *,
    maximum_bracket_gap_ns: int,
    interval_ns: int = ODOMETRY_SPEED_INTERVAL_NS,
) -> DerivedOdometrySpeed:
    """Evaluate rear-axle displacement speed at an estimate source epoch.

    Position is interpolated independently at ``timestamp_ns`` and exactly one
    fixed interval earlier.  The Euclidean displacement is divided by that
    interval, so the result is deliberately unsigned and never extrapolated.
    """

    if isinstance(timestamp_ns, bool) or not isinstance(timestamp_ns, (int, np.integer)):
        raise TypeError("odometry speed target timestamp must be an integer")
    if isinstance(interval_ns, bool) or not isinstance(interval_ns, (int, np.integer)):
        raise TypeError("odometry speed interval must be an integer")
    if timestamp_ns < 0:
        raise ValueError("odometry speed target timestamp must be nonnegative")
    if interval_ns <= 0:
        raise ValueError("odometry speed interval must be positive")
    if timestamp_ns < interval_ns:
        raise ConditionalFeatureError(
            "odometry_speed_history_outside_coverage",
            "the fixed odometry speed interval begins before timestamp zero",
        )
    previous = interpolate_odometry_pose(
        samples,
        int(timestamp_ns - interval_ns),
        maximum_bracket_gap_ns=maximum_bracket_gap_ns,
    )
    current = interpolate_odometry_pose(
        samples,
        int(timestamp_ns),
        maximum_bracket_gap_ns=maximum_bracket_gap_ns,
    )
    displacement_m = math.hypot(
        current.pose.x_m - previous.pose.x_m,
        current.pose.y_m - previous.pose.y_m,
    )
    return DerivedOdometrySpeed(
        timestamp_ns=int(timestamp_ns),
        value_mps=float(displacement_m / (interval_ns / 1e9)),
        displacement_m=float(displacement_m),
        interval_ns=int(interval_ns),
        previous_pose=previous,
        current_pose=current,
    )


def _native_stations_for_ego_offsets(
    curve: SplineCurve,
    path: EgoRelativePath,
    offsets_m: Sequence[float],
) -> np.ndarray:
    offsets = np.asarray(offsets_m, dtype=np.float64)
    if (
        offsets.ndim != 1
        or len(offsets) == 0
        or not np.all(np.isfinite(offsets))
        or not np.all(np.diff(offsets) > 0.0)
    ):
        raise ValueError("ego offsets must be finite and strictly increasing")
    if len(path.stations_m) != len(curve.s):
        raise ConditionalFeatureError(
            "estimate_native_station_mapping_unavailable",
            "spline and ego-relative samples do not align one-to-one",
        )
    tolerance = 1e-9
    if (
        offsets[0] < path.stations_m[0] - tolerance
        or offsets[-1] > path.stations_m[-1] + tolerance
    ):
        raise ConditionalFeatureError(
            "estimate_condition_horizon_incomplete",
            "EDP geometry does not cover the complete requested condition horizon",
        )
    native_stations = curve.s[::-1] if path.reversed_to_positive_x else curve.s
    return np.interp(offsets, path.stations_m, native_stations)


def _enum_symbol(message: Any, field_name: str) -> str:
    descriptor = getattr(message, "DESCRIPTOR", None)
    fields_by_name = getattr(descriptor, "fields_by_name", {})
    field = fields_by_name.get(field_name)
    if field is None or getattr(field, "enum_type", None) is None:
        raise ConditionalFeatureError(
            "estimate_role_schema_unavailable",
            "DrivePath role enum descriptor is unavailable",
        )
    try:
        number = int(getattr(message, field_name))
        value = field.enum_type.values_by_number[number]
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ConditionalFeatureError(
            "estimate_role_unavailable",
            "DrivePath role value is unavailable or unknown",
        ) from error
    return str(value.name)


def selected_keep_lane_confidences(message: Any) -> tuple[float, ...]:
    """Return confidence buckets from exactly one KEEP_LANE DrivePath."""

    paths = getattr(message, "drive_paths", None)
    if paths is None:
        raise ConditionalFeatureError(
            "estimate_drive_paths_unavailable",
            "EstimatedDrivePaths.drive_paths is unavailable",
        )
    selected = [
        path
        for path in paths
        if _enum_symbol(path, "role") == "LANE_ROLE_KEEP_LANE"
    ]
    if len(selected) != 1:
        raise ConditionalFeatureError(
            "estimate_keep_lane_not_unique",
            "exactly one KEEP_LANE DrivePath is required",
        )
    raw_values = getattr(selected[0], "drive_path_confidences", None)
    if raw_values is None:
        raise ConditionalFeatureError(
            "estimate_confidence_field_unavailable",
            "KEEP_LANE drive_path_confidences is unavailable",
        )
    try:
        values = tuple(float(value) for value in raw_values)
    except (TypeError, ValueError) as error:
        raise ConditionalFeatureError(
            "estimate_confidence_non_numeric",
            "confidence buckets must be numeric",
        ) from error
    if not values:
        raise ConditionalFeatureError(
            "estimate_confidence_empty",
            "KEEP_LANE confidence vector is empty",
        )
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ConditionalFeatureError(
            "estimate_confidence_non_finite",
            "confidence buckets must be finite",
        )
    tolerance = 1e-12
    if np.any(array < CONFIDENCE_MINIMUM - tolerance) or np.any(
        array > CONFIDENCE_MAXIMUM + tolerance
    ):
        raise ConditionalFeatureError(
            "estimate_confidence_out_of_range",
            "confidence buckets must lie within [0.001, 1.0]",
        )
    return values


def summarize_estimate_conditions(
    curve: SplineCurve,
    path: EgoRelativePath,
    confidences: Sequence[float],
) -> EstimateConditionFeatures:
    """Summarize EDP curvature and native-bucket confidence over H100."""

    condition_offsets = np.asarray(CANONICAL_CONDITION_STATIONS_M)
    native_condition_stations = _native_stations_for_ego_offsets(
        curve,
        path,
        condition_offsets,
    )
    curvature = np.interp(native_condition_stations, curve.s, curve.curvature)
    if path.reversed_to_positive_x:
        curvature = -curvature
    absolute_curvature = np.abs(curvature)
    integral = np.sum(
        0.5
        * (absolute_curvature[:-1] + absolute_curvature[1:])
        * np.diff(condition_offsets)
    )
    mean_abs_curvature = float(
        integral / (condition_offsets[-1] - condition_offsets[0])
    )
    curvature_delta = float(curvature[-1] - curvature[0])

    confidence_array = np.asarray(confidences, dtype=np.float64)
    if confidence_array.ndim != 1 or len(confidence_array) == 0:
        raise ConditionalFeatureError(
            "estimate_confidence_empty",
            "confidence vector must be nonempty",
        )
    centers = np.asarray(CONFIDENCE_SAMPLE_CENTERS_M)
    native_centers = _native_stations_for_ego_offsets(curve, path, centers)
    bucket_indices = np.floor(native_centers / CONFIDENCE_BUCKET_SIZE_M).astype(int)
    if np.any(bucket_indices < 0) or np.any(bucket_indices >= len(confidence_array)):
        raise ConditionalFeatureError(
            "estimate_confidence_h100_coverage_incomplete",
            "native confidence buckets do not cover every ego-relative H100 bin",
        )
    selected = confidence_array[bucket_indices]
    near = selected[centers < 30.0]
    middle = selected[(centers >= 30.0) & (centers < 65.0)]
    far = selected[centers >= 65.0]
    return EstimateConditionFeatures(
        estimated_mean_abs_curvature_per_m=mean_abs_curvature,
        estimated_curvature_delta_per_m=curvature_delta,
        confidence_near_mean=float(np.mean(near)),
        confidence_middle_mean=float(np.mean(middle)),
        confidence_far_mean=float(np.mean(far)),
        confidence_minimum=float(np.min(selected)),
        confidence_floor_fraction=float(
            np.mean(np.isclose(selected, CONFIDENCE_MINIMUM, atol=1e-12, rtol=0.0))
        ),
        confidence_lateral_jump_detected=bool(
            np.all(
                np.isclose(
                    confidence_array,
                    CONFIDENCE_LATERAL_JUMP_VALUE,
                    atol=1e-12,
                    rtol=0.0,
                )
            )
        ),
        confidence_bucket_count=len(confidence_array),
        confidence_native_start_station_m=float(native_centers[0]),
        confidence_native_end_station_m=float(native_centers[-1]),
    )


__all__ = [
    "CANONICAL_CONDITION_STATIONS_M",
    "CONFIDENCE_BUCKET_SIZE_M",
    "CONFIDENCE_LATERAL_JUMP_VALUE",
    "CONFIDENCE_MAXIMUM",
    "CONFIDENCE_MINIMUM",
    "CONFIDENCE_SAMPLE_CENTERS_M",
    "ConditionalFeatureError",
    "DerivedOdometrySpeed",
    "EstimateConditionFeatures",
    "InterpolatedSpeed",
    "LongitudinalSpeedSample",
    "ODOMETRY_SPEED_INTERVAL_MS",
    "ODOMETRY_SPEED_INTERVAL_NS",
    "derive_unsigned_odometry_speed",
    "interpolate_longitudinal_speed",
    "selected_keep_lane_confidences",
    "summarize_estimate_conditions",
]
