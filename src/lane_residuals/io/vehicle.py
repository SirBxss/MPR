"""Strict decoding of prediction-time vehicle condition signals from MCAP."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from ..domain.conditional_features import LongitudinalSpeedSample
from .mcap import iter_decoded_mcap_messages

DEFAULT_LONGITUDINAL_SPEED_TOPIC = "/adp/velocity_vehicle_longitudinal"
DEFAULT_LONGITUDINAL_SPEED_SCHEMA = "Adp.QualifiedTimedFloat64"
VALID_VEHICLE_MODEL_QUALIFIER = 1
LONGITUDINAL_SPEED_LIMIT_MPS = 400.0 / 3.6


def _strict_integer(message: Any, name: str) -> int:
    value = getattr(message, name, None)
    if isinstance(value, bool):
        raise ValueError(f"speed field {name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"speed field {name} must be an integer") from error
    if result < 0 or result != value:
        raise ValueError(f"speed field {name} must be a nonnegative integer")
    return result


def _finite_float(message: Any, name: str) -> float:
    value = getattr(message, name, None)
    if isinstance(value, bool):
        raise ValueError(f"speed field {name} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"speed field {name} must be numeric") from error
    if not math.isfinite(result):
        raise ValueError(f"speed field {name} must be finite")
    return result


def decode_longitudinal_speed_samples(
    path: Path,
    *,
    topic: str = DEFAULT_LONGITUDINAL_SPEED_TOPIC,
) -> tuple[list[LongitudinalSpeedSample], Counter[str], int]:
    """Decode valid signed m/s samples and retain every rejection count."""

    samples: list[LongitudinalSpeedSample] = []
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
        if schema_name != DEFAULT_LONGITUDINAL_SPEED_SCHEMA or encoding != "protobuf":
            failures["speed__schema_or_encoding_mismatch"] += 1
            continue
        try:
            qualifier = _strict_integer(decoded, "qualifier")
            if qualifier != VALID_VEHICLE_MODEL_QUALIFIER:
                failures[f"speed__qualifier_{qualifier}"] += 1
                continue
            value_mps = _finite_float(decoded, "value")
            if abs(value_mps) > LONGITUDINAL_SPEED_LIMIT_MPS:
                failures["speed__value_out_of_validated_range"] += 1
                continue
            samples.append(
                LongitudinalSpeedSample(
                    timestamp_ns=_strict_integer(decoded, "timestamp"),
                    value_mps=value_mps,
                    log_time_ns=int(getattr(message, "log_time", 0)),
                    publish_time_ns=int(getattr(message, "publish_time", 0)),
                )
            )
        except ValueError:
            failures["speed__invalid_message"] += 1
    samples.sort(key=lambda sample: sample.timestamp_ns)
    return samples, failures, message_count


__all__ = [
    "DEFAULT_LONGITUDINAL_SPEED_SCHEMA",
    "DEFAULT_LONGITUDINAL_SPEED_TOPIC",
    "LONGITUDINAL_SPEED_LIMIT_MPS",
    "VALID_VEHICLE_MODEL_QUALIFIER",
    "decode_longitudinal_speed_samples",
]
