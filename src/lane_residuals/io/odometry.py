"""Strict decoding of rear-axle planar odometry from MCAP."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from ..domain.motion import OdometrySample, Pose2D
from .mcap import iter_decoded_mcap_messages

DEFAULT_ODOMETRY_TOPIC = "/adp/odometry"
DEFAULT_ODOMETRY_SCHEMA = "Adp.OdometryState"


def _finite_number(message: Any, name: str) -> float:
    value = getattr(message, name, None)
    if isinstance(value, bool):
        raise ValueError(f"odometry field {name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"odometry field {name} must be numeric") from error
    if not math.isfinite(number):
        raise ValueError(f"odometry field {name} must be finite")
    return number


def _timestamp_ns(message: Any) -> int:
    value = getattr(message, "timestamp", None)
    if isinstance(value, bool):
        raise ValueError("odometry timestamp must be an integer")
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("odometry timestamp must be an integer") from error
    if timestamp < 0 or timestamp != value:
        raise ValueError("odometry timestamp must be a nonnegative integer")
    return timestamp


def decode_odometry_samples(
    path: Path,
    *,
    topic: str = DEFAULT_ODOMETRY_TOPIC,
) -> tuple[list[OdometrySample], Counter[str], int]:
    """Decode every planar odometry message without silently coercing failures."""

    samples: list[OdometrySample] = []
    failures: Counter[str] = Counter()
    message_count = 0
    for schema, channel, message, decoded in iter_decoded_mcap_messages(
        path,
        topics=(topic,),
        include_ros1=False,
    ):
        message_count += 1
        schema_name = str(getattr(schema, "name", ""))
        encoding = str(getattr(channel, "message_encoding", "")).lower()
        if schema_name != DEFAULT_ODOMETRY_SCHEMA or encoding != "protobuf":
            failures["odometry__schema_or_encoding_mismatch"] += 1
            continue
        try:
            samples.append(
                OdometrySample(
                    timestamp_ns=_timestamp_ns(decoded),
                    log_time_ns=int(getattr(message, "log_time", 0)),
                    publish_time_ns=int(getattr(message, "publish_time", 0)),
                    pose=Pose2D(
                        x_m=_finite_number(decoded, "x_position"),
                        y_m=_finite_number(decoded, "y_position"),
                        yaw_rad=_finite_number(decoded, "yaw_angle"),
                    ),
                )
            )
        except ValueError:
            failures["odometry__invalid_message"] += 1
    return samples, failures, message_count


__all__ = [
    "DEFAULT_ODOMETRY_SCHEMA",
    "DEFAULT_ODOMETRY_TOPIC",
    "decode_odometry_samples",
]
