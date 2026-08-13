"""Streaming MCAP/Protobuf ingestion for road-model messages.

The MCAP dependency is deliberately optional.  The geometry and statistical
modules can still be installed and tested without MCAP support; install the
``mcap`` extra when real recordings are processed.

Only schema-backed Protobuf and explicitly requested ROS1 messages are decoded.
No attempt is made to guess the structure of opaque binary payloads.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

from .residuals import FloatArray

MetadataValue = bool | int | float | str
GeometrySource = Literal["drive_path", "paired_boundaries"]
DEFAULT_DIRECT_PATH_TOPICS = (
    "/em/road/ego_lane_path",
    "/adp/estimated_drive_paths",
)


class McapDependencyError(ImportError):
    """Raised when the optional MCAP decoder dependencies are unavailable."""


class RoadMessageError(ValueError):
    """Raised when a decoded message is not a usable road-model message."""


@dataclass(frozen=True)
class TopicProbeRecord:
    """Container-level metadata for a candidate direct path topic."""

    topic: str
    present: bool
    message_count: int
    schema_names: tuple[str, ...]
    schema_encodings: tuple[str, ...]
    message_encodings: tuple[str, ...]
    supported_by_current_road_decoder: bool
    supported_by_structure_probe: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "present": self.present,
            "message_count": self.message_count,
            "schema_names": list(self.schema_names),
            "schema_encodings": list(self.schema_encodings),
            "message_encodings": list(self.message_encodings),
            "supported_by_current_road_decoder": (
                self.supported_by_current_road_decoder
            ),
            "supported_by_structure_probe": self.supported_by_structure_probe,
        }


@dataclass(frozen=True)
class RoadTopicLoadReport:
    """Decoded, retained, and discarded message counts for one road topic."""

    topic: str
    decoded_messages: int
    retained_frames: int
    discard_reasons: tuple[tuple[str, int], ...]

    @property
    def discarded_messages(self) -> int:
        return self.decoded_messages - self.retained_frames

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "decoded_messages": self.decoded_messages,
            "retained_frames": self.retained_frames,
            "discarded_messages": self.discarded_messages,
            "discard_reasons": dict(self.discard_reasons),
        }


@dataclass(frozen=True)
class RoadFrameLoadResult:
    """Road frames plus message-level extraction diagnostics."""

    frames_by_topic: dict[str, list["RoadFrame"]]
    topic_reports: tuple[RoadTopicLoadReport, ...]


def _finite_vector(values: ArrayLike, *, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise RoadMessageError(f"{name} must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise RoadMessageError(f"{name} must contain only finite values")
    return array


@dataclass(frozen=True)
class RoadSegment:
    """One lane/road centreline extracted from a road-model message."""

    segment_id: int
    x: ArrayLike
    y: ArrayLike
    arc_length: ArrayLike
    heading: ArrayLike | None = None
    curvature: ArrayLike | None = None
    is_ego: bool | None = None
    quality: MetadataValue | None = None
    geometry_source: GeometrySource = "drive_path"
    source_index: int | None = None
    successor_indices: tuple[int, ...] = ()
    predecessor_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        x = _finite_vector(self.x, name="x")
        y = _finite_vector(self.y, name="y")
        arc_length = _finite_vector(self.arc_length, name="arc_length")
        if len(x) < 2:
            raise RoadMessageError("a road segment must contain at least two points")
        if not (len(x) == len(y) == len(arc_length)):
            raise RoadMessageError("x, y, and arc_length must have the same length")

        heading = None
        if self.heading is not None:
            heading = _finite_vector(self.heading, name="heading")
            if len(heading) != len(x):
                raise RoadMessageError("heading must have the same length as x")

        curvature = None
        if self.curvature is not None:
            curvature = _finite_vector(self.curvature, name="curvature")
            if len(curvature) != len(x):
                raise RoadMessageError("curvature must have the same length as x")

        if isinstance(self.segment_id, bool) or not isinstance(
            self.segment_id, (int, np.integer)
        ):
            raise RoadMessageError("segment_id must be an integer")
        if self.is_ego is not None and not isinstance(self.is_ego, (bool, np.bool_)):
            raise RoadMessageError("is_ego must be bool or None")
        if self.geometry_source not in ("drive_path", "paired_boundaries"):
            raise RoadMessageError(
                'geometry_source must be "drive_path" or "paired_boundaries"'
            )
        if self.source_index is not None and (
            isinstance(self.source_index, bool)
            or not isinstance(self.source_index, (int, np.integer))
            or int(self.source_index) < 0
        ):
            raise RoadMessageError("source_index must be a nonnegative integer or None")

        def topology_indices(
            values: tuple[int, ...],
            *,
            name: str,
        ) -> tuple[int, ...]:
            result: list[int] = []
            for value in values:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, np.integer))
                    or int(value) < 0
                ):
                    raise RoadMessageError(
                        f"{name} must contain only nonnegative integers"
                    )
                result.append(int(value))
            if len(result) != len(set(result)):
                raise RoadMessageError(f"{name} must not contain duplicates")
            return tuple(result)

        successors = topology_indices(
            self.successor_indices,
            name="successor_indices",
        )
        predecessors = topology_indices(
            self.predecessor_indices,
            name="predecessor_indices",
        )

        object.__setattr__(self, "segment_id", int(self.segment_id))
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "arc_length", arc_length)
        object.__setattr__(self, "heading", heading)
        object.__setattr__(self, "curvature", curvature)
        object.__setattr__(
            self,
            "is_ego",
            None if self.is_ego is None else bool(self.is_ego),
        )
        object.__setattr__(
            self,
            "source_index",
            None if self.source_index is None else int(self.source_index),
        )
        object.__setattr__(self, "successor_indices", successors)
        object.__setattr__(self, "predecessor_indices", predecessors)

    @property
    def points(self) -> FloatArray:
        """Return centreline coordinates with shape ``(n_points, 2)``."""

        return np.column_stack((self.x, self.y))


@dataclass(frozen=True)
class SegmentExtraction:
    """Outcome for one original lane segment, including failed reconstruction."""

    segment_index: int
    segment_id: int | None
    is_ego: bool | None
    quality: MetadataValue | None
    reconstruction_succeeded: bool
    geometry_source: GeometrySource | None
    failure_code: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.segment_index, bool)
            or not isinstance(self.segment_index, (int, np.integer))
            or int(self.segment_index) < 0
        ):
            raise RoadMessageError("segment_index must be a nonnegative integer")
        if self.segment_id is not None and (
            isinstance(self.segment_id, bool)
            or not isinstance(self.segment_id, (int, np.integer))
        ):
            raise RoadMessageError("segment_id must be an integer or None")
        if self.is_ego is not None and not isinstance(self.is_ego, (bool, np.bool_)):
            raise RoadMessageError("is_ego must be bool or None")
        if self.reconstruction_succeeded:
            if self.segment_id is None or self.geometry_source is None:
                raise RoadMessageError(
                    "successful segment extraction requires an id and geometry source"
                )
            if self.failure_code is not None or self.failure_reason is not None:
                raise RoadMessageError(
                    "successful segment extraction cannot have failure metadata"
                )
        elif not self.failure_code or not self.failure_reason:
            raise RoadMessageError(
                "failed segment extraction requires a failure code and reason"
            )

        object.__setattr__(self, "segment_index", int(self.segment_index))
        object.__setattr__(
            self,
            "segment_id",
            None if self.segment_id is None else int(self.segment_id),
        )
        object.__setattr__(
            self,
            "is_ego",
            None if self.is_ego is None else bool(self.is_ego),
        )


@dataclass(frozen=True)
class RoadFrame:
    """A timestamped collection of road segments from one MCAP message."""

    topic: str
    schema_name: str
    log_time_ns: int
    publish_time_ns: int
    sequence: int
    source_time_ns: int | None
    segments: tuple[RoadSegment, ...]
    segment_extractions: tuple[SegmentExtraction, ...] = ()
    metadata: tuple[tuple[str, MetadataValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.topic:
            raise RoadMessageError("topic must not be empty")
        if not self.schema_name:
            raise RoadMessageError("schema_name must not be empty")
        if self.log_time_ns < 0 or self.publish_time_ns < 0:
            raise RoadMessageError("MCAP timestamps must be nonnegative")
        if self.source_time_ns is not None and self.source_time_ns < 0:
            raise RoadMessageError("source_time_ns must be nonnegative")
        if not self.segments and not self.segment_extractions:
            raise RoadMessageError(
                "a road frame must contain segment geometry or extraction evidence"
            )

    @property
    def metadata_dict(self) -> dict[str, MetadataValue]:
        """Return preserved message metadata as a regular dictionary."""

        return dict(self.metadata)

    @property
    def ego_metadata_present(self) -> bool:
        """Whether the message explicitly classified any original segment."""

        if self.segment_extractions:
            return any(
                extraction.is_ego is not None
                for extraction in self.segment_extractions
            )
        return any(segment.is_ego is not None for segment in self.segments)


_MISSING = object()


def _get_attr(
    value: Any,
    names: Sequence[str],
    *,
    default: Any = _MISSING,
) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    if default is _MISSING:
        joined = ", ".join(names)
        raise RoadMessageError(f"message is missing required field ({joined})")
    return default


def _get_present_attr(
    value: Any,
    names: Sequence[str],
) -> Any:
    """Read optional metadata without confusing Proto3 defaults with presence."""

    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None

    present_names: set[str] | None = None
    list_fields = getattr(value, "ListFields", None)
    if callable(list_fields):
        present_names = {descriptor.name for descriptor, _ in list_fields()}

    for name in names:
        if hasattr(value, name) and (
            present_names is None or name in present_names
        ):
            return getattr(value, name)
    return None


def _mean(value: Any) -> float:
    invalid_flags = _get_attr(
        value,
        ("invalid_flags", "invalid_flags_"),
        default=None,
    )
    if invalid_flags is not None:
        try:
            flags = int(invalid_flags)
        except (TypeError, ValueError, OverflowError) as error:
            raise RoadMessageError("distributed value has invalid status flags") from error
        # Bit 0 marks an invalid mean; 255 denotes an unfilled signal in the
        # embedded road_msgs schema.  Standard Python floats do not expose
        # this field and continue to be accepted below.
        if flags == 255 or flags & 1:
            raise RoadMessageError("distributed value mean is marked invalid")
    mean = _get_attr(value, ("mean", "mean_"), default=value)
    return float(mean)


def _primitive(value: Any) -> MetadataValue | None:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, str):
        return value
    return None


def _optional_metadata(value: Any, names: Sequence[str]) -> MetadataValue | None:
    return _primitive(_get_present_attr(value, names))


def _optional_bool(value: Any, names: Sequence[str]) -> bool | None:
    raw = _get_present_attr(value, names)
    if raw is None:
        return None
    if isinstance(raw, (bool, np.bool_)):
        return bool(raw)
    if isinstance(raw, (int, np.integer)) and int(raw) in (0, 1):
        return bool(raw)
    return None


def _timestamp_object_to_ns(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return int(value)

    seconds = _get_attr(value, ("seconds", "secs", "sec"), default=None)
    if seconds is None:
        return None
    fractional = _get_attr(
        value,
        (
            "fractional_seconds",
            "fractional_seconds_",
            "nanoseconds",
            "nanos",
            "nsecs",
            "nanosec",
        ),
        default=0,
    )
    return int(seconds) * 1_000_000_000 + int(fractional)


def _source_time_ns(message: Any) -> int | None:
    direct = _get_present_attr(
        message,
        ("time_stamp", "time_stamp_", "timestamp", "timestamp_"),
    )
    converted = _timestamp_object_to_ns(direct)
    if converted is not None:
        return converted

    header = _get_present_attr(message, ("header", "header_"))
    if header is None:
        return None
    stamp = _get_attr(header, ("stamp", "stamp_"), default=None)
    return _timestamp_object_to_ns(stamp)


def source_time_ns_from_message(message: Any) -> int | None:
    """Return the interface source timestamp without requiring valid geometry."""

    return _source_time_ns(message)


def _geometric_arc_length(x: FloatArray, y: FloatArray) -> FloatArray:
    increments = np.hypot(np.diff(x), np.diff(y))
    return np.concatenate(([0.0], np.cumsum(increments)))


def _valid_pool_range(
    range_value: Any,
    *,
    pool_length: int,
    minimum_size: int,
) -> tuple[int, int] | None:
    if range_value is None:
        return None
    try:
        start = int(_get_attr(range_value, ("start", "start_")))
        size = int(_get_attr(range_value, ("size", "size_")))
    except (RoadMessageError, TypeError, ValueError, OverflowError):
        return None
    end = start + size
    if start < 0 or size < minimum_size or end > pool_length:
        return None
    return start, end


def _optional_numeric_pool(
    values: Sequence[Any],
    names: Sequence[str],
) -> FloatArray | None:
    extracted: list[float] = []
    for value in values:
        item = _get_attr(value, names, default=None)
        if item is None:
            return None
        try:
            extracted.append(_mean(item))
        except (RoadMessageError, TypeError, ValueError, OverflowError):
            return None
    array = np.asarray(extracted, dtype=np.float64)
    return array if np.all(np.isfinite(array)) else None


def _coordinate_pool(vertices: Sequence[Any]) -> tuple[FloatArray, FloatArray]:
    try:
        x = np.asarray(
            [_mean(_get_attr(vertex, ("x", "x_"))) for vertex in vertices],
            dtype=np.float64,
        )
        y = np.asarray(
            [_mean(_get_attr(vertex, ("y", "y_"))) for vertex in vertices],
            dtype=np.float64,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise RoadMessageError("vertex pool contains unreadable coordinates") from error
    return x, y


def _concatenate_polylines(polylines: Sequence[FloatArray]) -> FloatArray:
    if not polylines:
        raise RoadMessageError("boundary range contains no valid geometry")
    result = np.asarray(polylines[0], dtype=np.float64)
    for raw_polyline in polylines[1:]:
        polyline = np.asarray(raw_polyline, dtype=np.float64)
        if np.linalg.norm(result[-1] - polyline[-1]) < np.linalg.norm(
            result[-1] - polyline[0]
        ):
            polyline = polyline[::-1]
        if np.linalg.norm(result[-1] - polyline[0]) <= 1e-6:
            polyline = polyline[1:]
        if len(polyline):
            result = np.vstack((result, polyline))
    if len(result) < 2:
        raise RoadMessageError("boundary geometry has fewer than two points")
    return result


def _boundary_polyline(
    lane_segment: Any,
    *,
    side: Literal["left", "right"],
    boundary_pool: Sequence[Any],
    boundary_points: FloatArray,
) -> FloatArray:
    ranges = _get_attr(
        lane_segment,
        (
            f"{side}_lane_boundary_ranges",
            f"{side}_lane_boundary_ranges_",
        ),
        default=None,
    )
    if ranges is None:
        raise RoadMessageError(f"{side} lane-boundary ranges are missing")

    # Sensor topology normally uses camera_based. The later fallbacks keep the
    # parser useful for road variants that expose only map/artificial geometry.
    for source_name in ("camera_based", "map_based", "artificial"):
        pool_range = _valid_pool_range(
            _get_attr(
                ranges,
                (source_name, f"{source_name}_"),
                default=None,
            ),
            pool_length=len(boundary_pool),
            minimum_size=1,
        )
        if pool_range is None:
            continue

        polylines: list[FloatArray] = []
        for boundary in boundary_pool[slice(*pool_range)]:
            geometry_range = _valid_pool_range(
                _get_attr(boundary, ("geometry", "geometry_"), default=None),
                pool_length=len(boundary_points),
                minimum_size=2,
            )
            if geometry_range is None:
                continue
            points = boundary_points[slice(*geometry_range)]
            if len(points) >= 2 and np.all(np.isfinite(points)):
                polylines.append(points)
        if polylines:
            return _concatenate_polylines(polylines)

    raise RoadMessageError(f"{side} lane boundary has no usable geometry")


def _midpoint_path(left: FloatArray, right: FloatArray) -> FloatArray:
    left_s = _geometric_arc_length(left[:, 0], left[:, 1])
    right_s = _geometric_arc_length(right[:, 0], right[:, 1])
    if left_s[-1] <= 1e-9 or right_s[-1] <= 1e-9:
        raise RoadMessageError("lane boundary geometry is degenerate")

    same_direction_cost = np.linalg.norm(left[0] - right[0]) + np.linalg.norm(
        left[-1] - right[-1]
    )
    reversed_cost = np.linalg.norm(left[0] - right[-1]) + np.linalg.norm(
        left[-1] - right[0]
    )
    if reversed_cost < same_direction_cost:
        right = right[::-1]
        right_s = _geometric_arc_length(right[:, 0], right[:, 1])

    sample_count = max(len(left), len(right))
    normalized_station = np.linspace(0.0, 1.0, sample_count)
    left_normalized = left_s / left_s[-1]
    right_normalized = right_s / right_s[-1]
    left_sampled = np.column_stack(
        (
            np.interp(normalized_station, left_normalized, left[:, 0]),
            np.interp(normalized_station, left_normalized, left[:, 1]),
        )
    )
    right_sampled = np.column_stack(
        (
            np.interp(normalized_station, right_normalized, right[:, 0]),
            np.interp(normalized_station, right_normalized, right[:, 1]),
        )
    )
    widths = np.linalg.norm(left_sampled - right_sampled, axis=1)
    median_width = float(np.median(widths))
    if not np.isfinite(median_width) or not 1.0 <= median_width <= 10.0:
        raise RoadMessageError(
            f"paired boundaries imply implausible median width {median_width:.3f} m"
        )
    return 0.5 * (left_sampled + right_sampled)


def _road_failure_code(reason: str) -> str:
    """Map detailed reconstruction text to a stable aggregation code."""

    normalized = reason.lower()
    if "lane segment list is empty" in normalized:
        return "lane_segments_empty"
    if "segment id is missing or invalid" in normalized:
        return "segment_id_invalid"
    if "lane-boundary ranges are missing" in normalized:
        return "lane_boundary_ranges_missing"
    if "lane boundary has no usable geometry" in normalized:
        return "lane_boundary_geometry_unavailable"
    if "implausible median width" in normalized:
        return "implausible_lane_width"
    if "degenerate" in normalized:
        return "degenerate_geometry"
    if "fewer than two points" in normalized or "at least two points" in normalized:
        return "insufficient_geometry_points"
    if "unreadable coordinates" in normalized or "finite" in normalized:
        return "invalid_geometry_values"
    return "road_message_or_segment_invalid"


def _segment_ego_status(
    lane_segment: Any,
    *,
    segment_index: int,
    segment_id: int | None,
    ego_segment_id: int | None,
    ego_indices: set[int],
) -> bool | None:
    """Resolve explicit ego classification before attempting reconstruction."""

    segment_flag = _optional_bool(
        lane_segment,
        (
            "is_ego_lane",
            "is_ego_lane_",
            "ego_lane",
            "ego_lane_",
            "is_host_lane",
            "is_host_lane_",
            "is_ego",
            "is_ego_",
            "is_current_lane",
            "is_current_lane_",
        ),
    )
    if ego_segment_id is not None:
        return segment_id == ego_segment_id if segment_id is not None else None
    if ego_indices:
        return segment_index in ego_indices
    return segment_flag


def _segment_quality(lane_segment: Any) -> MetadataValue | None:
    return _optional_metadata(
        lane_segment,
        (
            "quality",
            "quality_",
            "qualifier",
            "qualifier_",
            "data_quality",
            "data_quality_",
            "validity",
            "validity_",
        ),
    )


def road_frame_from_message(
    message: Any,
    *,
    topic: str,
    schema_name: str,
    log_time_ns: int,
    publish_time_ns: int,
    sequence: int = 0,
) -> RoadFrame:
    """Convert one decoded ``Adp.Perception.Road``-like message.

    Both the original field names and the underscore-suffixed variants observed
    in reprocessed/shadow schemas are supported.
    """

    vertices = tuple(
        _get_attr(
            message,
            ("polyline_vertex_pool", "polyline_vertex_pool_"),
            default=(),
        )
    )
    lane_segments = tuple(
        _get_attr(message, ("lane_segments", "lane_segments_"))
    )
    if not lane_segments:
        raise RoadMessageError("lane segment list is empty")

    x_pool, y_pool = (
        _coordinate_pool(vertices)
        if vertices
        else (np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64))
    )
    heading_pool = _optional_numeric_pool(vertices, ("heading", "heading_"))
    curvature_pool = _optional_numeric_pool(
        vertices,
        ("curvature", "curvature_"),
    )

    arc_pool_raw = _get_attr(
        message,
        ("polyline_arc_length_pool", "polyline_arc_length_pool_"),
        default=None,
    )
    arc_pool = (
        np.asarray(tuple(arc_pool_raw), dtype=np.float64)
        if arc_pool_raw is not None
        else None
    )
    if arc_pool is not None and len(arc_pool) != len(vertices):
        arc_pool = None

    boundary_vertices = tuple(
        _get_attr(
            message,
            ("boundary_vertex_pool", "boundary_vertex_pool_"),
            default=(),
        )
    )
    boundary_pool = tuple(
        _get_attr(
            message,
            ("lane_boundary_pool", "lane_boundary_pool_"),
            default=(),
        )
    )
    if boundary_vertices:
        boundary_x, boundary_y = _coordinate_pool(boundary_vertices)
        boundary_points = np.column_stack((boundary_x, boundary_y))
    else:
        boundary_points = np.empty((0, 2), dtype=np.float64)

    ego_segment_id = _optional_metadata(
        message,
        (
            "ego_lane_segment_id",
            "ego_lane_segment_id_",
            "ego_lane_id",
            "ego_lane_id_",
            "host_lane_segment_id",
            "host_lane_segment_id_",
            "current_lane_segment_id",
            "current_lane_segment_id_",
        ),
    )
    if not isinstance(ego_segment_id, int):
        ego_segment_id = None

    ego_indices_raw = _get_attr(
        message,
        (
            "ego_lane_segment_indices",
            "ego_lane_segment_indices_",
        ),
        default=(),
    )
    try:
        ego_indices = {int(index) for index in ego_indices_raw}
    except (TypeError, ValueError, OverflowError):
        ego_indices = set()

    extracted: list[RoadSegment] = []
    extraction_records: list[SegmentExtraction] = []
    rejection_reasons: Counter[str] = Counter()
    for segment_index, lane_segment in enumerate(lane_segments):
        try:
            segment_id = int(_get_attr(lane_segment, ("id", "id_")))
        except (RoadMessageError, TypeError, ValueError, OverflowError):
            reason = "segment id is missing or invalid"
            rejection_reasons[reason] += 1
            extraction_records.append(
                SegmentExtraction(
                    segment_index=segment_index,
                    segment_id=None,
                    is_ego=_segment_ego_status(
                        lane_segment,
                        segment_index=segment_index,
                        segment_id=None,
                        ego_segment_id=ego_segment_id,
                        ego_indices=ego_indices,
                    ),
                    quality=_segment_quality(lane_segment),
                    reconstruction_succeeded=False,
                    geometry_source=None,
                    failure_code=_road_failure_code(reason),
                    failure_reason=reason,
                )
            )
            continue

        is_ego = _segment_ego_status(
            lane_segment,
            segment_index=segment_index,
            segment_id=segment_id,
            ego_segment_id=ego_segment_id,
            ego_indices=ego_indices,
        )
        quality = _segment_quality(lane_segment)
        drive_path_range = _valid_pool_range(
            _get_attr(
                lane_segment,
                ("drive_path_range", "drive_path_range_"),
                default=None,
            ),
            pool_length=len(vertices),
            minimum_size=2,
        )
        geometry_source: GeometrySource
        if drive_path_range is not None:
            start, end = drive_path_range
            x = x_pool[start:end]
            y = y_pool[start:end]
            arc_length = (
                arc_pool[start:end]
                if arc_pool is not None
                else _geometric_arc_length(x, y)
            )
            heading = None if heading_pool is None else heading_pool[start:end]
            curvature = (
                None if curvature_pool is None else curvature_pool[start:end]
            )
            geometry_source = "drive_path"
        else:
            try:
                left = _boundary_polyline(
                    lane_segment,
                    side="left",
                    boundary_pool=boundary_pool,
                    boundary_points=boundary_points,
                )
                right = _boundary_polyline(
                    lane_segment,
                    side="right",
                    boundary_pool=boundary_pool,
                    boundary_points=boundary_points,
                )
                midpoint = _midpoint_path(left, right)
            except RoadMessageError as error:
                reason = str(error)
                rejection_reasons[reason] += 1
                extraction_records.append(
                    SegmentExtraction(
                        segment_index=segment_index,
                        segment_id=segment_id,
                        is_ego=is_ego,
                        quality=quality,
                        reconstruction_succeeded=False,
                        geometry_source=None,
                        failure_code=_road_failure_code(reason),
                        failure_reason=reason,
                    )
                )
                continue
            x = midpoint[:, 0]
            y = midpoint[:, 1]
            arc_length = _geometric_arc_length(x, y)
            heading = None
            curvature = None
            geometry_source = "paired_boundaries"

        try:
            successor_indices = tuple(
                int(index)
                for index in _get_attr(
                    lane_segment,
                    (
                        "successor_lane_segment_indices",
                        "successor_lane_segment_indices_",
                    ),
                    default=(),
                )
            )
            predecessor_indices = tuple(
                int(index)
                for index in _get_attr(
                    lane_segment,
                    (
                        "predecessor_lane_segment_indices",
                        "predecessor_lane_segment_indices_",
                    ),
                    default=(),
                )
            )
            segment = RoadSegment(
                segment_id=segment_id,
                x=x,
                y=y,
                arc_length=arc_length,
                heading=heading,
                curvature=curvature,
                is_ego=is_ego,
                quality=quality,
                geometry_source=geometry_source,
                source_index=segment_index,
                successor_indices=successor_indices,
                predecessor_indices=predecessor_indices,
            )
        except (RoadMessageError, TypeError, ValueError, OverflowError) as error:
            # One malformed range must not discard every usable segment in the frame.
            reason = str(error)
            rejection_reasons[reason] += 1
            extraction_records.append(
                SegmentExtraction(
                    segment_index=segment_index,
                    segment_id=segment_id,
                    is_ego=is_ego,
                    quality=quality,
                    reconstruction_succeeded=False,
                    geometry_source=geometry_source,
                    failure_code=_road_failure_code(reason),
                    failure_reason=reason,
                )
            )
            continue
        extracted.append(segment)
        extraction_records.append(
            SegmentExtraction(
                segment_index=segment_index,
                segment_id=segment_id,
                is_ego=is_ego,
                quality=quality,
                reconstruction_succeeded=True,
                geometry_source=geometry_source,
            )
        )

    metadata: list[tuple[str, MetadataValue]] = []
    for output_name, aliases in (
        (
            "quality",
            (
                "quality",
                "quality_",
                "event_data_qualifier",
                "event_data_qualifier_",
                "qualifier",
                "qualifier_",
                "data_quality",
                "data_quality_",
                "validity",
                "validity_",
            ),
        ),
        (
            "topology_source",
            (
                "topology_source",
                "topology_source_",
                "source",
                "source_",
                "road_source",
                "road_source_",
            ),
        ),
    ):
        item = _optional_metadata(message, aliases)
        if item is not None:
            metadata.append((output_name, item))

    return RoadFrame(
        topic=topic,
        schema_name=schema_name,
        log_time_ns=int(log_time_ns),
        publish_time_ns=int(publish_time_ns),
        sequence=int(sequence),
        source_time_ns=_source_time_ns(message),
        segments=tuple(extracted),
        segment_extractions=tuple(extraction_records),
        metadata=tuple(metadata),
    )


def road_frame_load_result_from_decoded_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    topics: Sequence[str],
    expected_schema_name: str = "Adp.Perception.Road",
) -> RoadFrameLoadResult:
    """Convert decoded tuples and retain message-level discard diagnostics."""

    requested = tuple(dict.fromkeys(topics))
    if not requested:
        raise ValueError("topics must not be empty")
    grouped: dict[str, list[RoadFrame]] = {topic: [] for topic in requested}
    decoded_counts: Counter[str] = Counter()
    rejection_reasons: dict[str, Counter[str]] = {
        topic: Counter() for topic in requested
    }

    for schema, channel, message, decoded in decoded_messages:
        topic = str(channel.topic)
        if topic not in grouped:
            continue
        decoded_counts[topic] += 1
        schema_name = str(schema.name)
        if schema_name != expected_schema_name:
            raise RoadMessageError(
                f'topic "{topic}" uses schema "{schema_name}", '
                f'expected "{expected_schema_name}"'
            )
        if str(channel.message_encoding).lower() != "protobuf":
            raise RoadMessageError(
                f'topic "{topic}" is not encoded as Protobuf'
            )
        try:
            frame = road_frame_from_message(
                decoded,
                topic=topic,
                schema_name=schema_name,
                log_time_ns=message.log_time,
                publish_time_ns=message.publish_time,
                sequence=getattr(message, "sequence", 0),
            )
        except RoadMessageError as error:
            rejection_reasons[topic][_road_failure_code(str(error))] += 1
            continue
        grouped[topic].append(frame)

    reports: list[RoadTopicLoadReport] = []
    for topic, frames in grouped.items():
        frames.sort(key=lambda frame: frame.log_time_ns)
        reports.append(
            RoadTopicLoadReport(
                topic=topic,
                decoded_messages=decoded_counts[topic],
                retained_frames=len(frames),
                discard_reasons=tuple(
                    sorted(rejection_reasons[topic].items())
                ),
            )
        )
        if decoded_counts[topic] and not frames:
            details = "; ".join(
                f"{count}x {code}"
                for code, count in rejection_reasons[topic].most_common(3)
            )
            raise RoadMessageError(
                f'topic "{topic}" had {decoded_counts[topic]} decoded messages, '
                f"but all failed road extraction: {details}"
            )
    return RoadFrameLoadResult(
        frames_by_topic=grouped,
        topic_reports=tuple(reports),
    )


def road_frames_from_decoded_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    topics: Sequence[str],
    expected_schema_name: str = "Adp.Perception.Road",
) -> dict[str, list[RoadFrame]]:
    """Convert decoded MCAP tuples into road frames grouped by topic."""

    return road_frame_load_result_from_decoded_messages(
        decoded_messages,
        topics=topics,
        expected_schema_name=expected_schema_name,
    ).frames_by_topic


def _iter_decoded_mcap_messages(
    path: Path,
    *,
    topics: Sequence[str],
) -> Iterator[tuple[Any, Any, Any, Any]]:
    yield from iter_decoded_mcap_messages(
        path,
        topics=topics,
        include_ros1=False,
    )


def iter_decoded_mcap_messages(
    path: str | Path,
    *,
    topics: Sequence[str],
    include_ros1: bool = False,
) -> Iterator[tuple[Any, Any, Any, Any]]:
    """Stream selected schema-backed messages from one MCAP.

    Protobuf support is always enabled.  ROS1 decoding is opt-in so the
    existing Protobuf-only commands do not acquire an unnecessary runtime
    requirement.  The ROS1 factory dynamically consumes the embedded
    ``ros1msg`` schema and does not require a ROS installation.
    """

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"MCAP file not found: {source}")
    requested = tuple(dict.fromkeys(str(topic) for topic in topics))
    if not requested or any(not topic for topic in requested):
        raise ValueError("topics must contain at least one nonempty topic")
    try:
        from mcap.reader import NonSeekingReader, SeekingReader
        from mcap_protobuf.decoder import DecoderFactory as ProtobufDecoderFactory
    except ImportError as error:
        raise McapDependencyError(
            'MCAP support is not installed. Run: pip install -e ".[mcap]"'
        ) from error

    decoder_factories: list[Any] = [ProtobufDecoderFactory()]
    if include_ros1:
        try:
            from mcap_ros1.decoder import DecoderFactory as Ros1DecoderFactory
        except ImportError as error:
            raise McapDependencyError(
                "ROS1 MCAP support is not installed. Run: "
                'pip install -e ".[mcap]"'
            ) from error
        decoder_factories.append(Ros1DecoderFactory())

    with source.open("rb") as stream:
        reader_type = SeekingReader if stream.seekable() else NonSeekingReader
        reader = reader_type(
            stream,
            validate_crcs=False,
            decoder_factories=decoder_factories,
            record_size_limit=None,
        )
        yield from reader.iter_decoded_messages(topics=list(requested))


def load_road_frames(
    path: str | Path,
    *,
    topics: Sequence[str],
    expected_schema_name: str = "Adp.Perception.Road",
) -> dict[str, list[RoadFrame]]:
    """Stream and decode selected road topics from one MCAP file."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"MCAP file not found: {source}")
    return load_road_frame_result(
        source,
        topics=topics,
        expected_schema_name=expected_schema_name,
    ).frames_by_topic


def load_road_frame_result(
    path: str | Path,
    *,
    topics: Sequence[str],
    expected_schema_name: str = "Adp.Perception.Road",
) -> RoadFrameLoadResult:
    """Stream selected road topics and preserve message discard evidence."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"MCAP file not found: {source}")
    return road_frame_load_result_from_decoded_messages(
        _iter_decoded_mcap_messages(source, topics=topics),
        topics=topics,
        expected_schema_name=expected_schema_name,
    )


def topic_probe_from_summary(
    summary: Any,
    *,
    topics: Sequence[str] = DEFAULT_DIRECT_PATH_TOPICS,
) -> tuple[TopicProbeRecord, ...]:
    """Build a candidate-topic inventory from an MCAP summary object."""

    requested = tuple(dict.fromkeys(str(topic) for topic in topics))
    if not requested or any(not topic for topic in requested):
        raise ValueError("topics must contain at least one nonempty topic name")

    channels = getattr(summary, "channels", {}) or {}
    schemas = getattr(summary, "schemas", {}) or {}
    statistics = getattr(summary, "statistics", None)
    channel_counts = (
        getattr(statistics, "channel_message_counts", {}) or {}
        if statistics is not None
        else {}
    )

    records: list[TopicProbeRecord] = []
    for topic in requested:
        matching_channels = [
            (channel_id, channel)
            for channel_id, channel in channels.items()
            if str(getattr(channel, "topic", "")) == topic
        ]
        schema_names: set[str] = set()
        schema_encodings: set[str] = set()
        message_encodings: set[str] = set()
        message_count = 0

        for channel_id, channel in matching_channels:
            message_count += int(channel_counts.get(channel_id, 0))
            message_encoding = str(
                getattr(channel, "message_encoding", "")
            )
            if message_encoding:
                message_encodings.add(message_encoding)
            schema_id = getattr(channel, "schema_id", None)
            schema = schemas.get(schema_id)
            if schema is None:
                continue
            schema_name = str(getattr(schema, "name", ""))
            schema_encoding = str(getattr(schema, "encoding", ""))
            if schema_name:
                schema_names.add(schema_name)
            if schema_encoding:
                schema_encodings.add(schema_encoding)

        records.append(
            TopicProbeRecord(
                topic=topic,
                present=bool(matching_channels),
                message_count=message_count,
                schema_names=tuple(sorted(schema_names)),
                schema_encodings=tuple(sorted(schema_encodings)),
                message_encodings=tuple(sorted(message_encodings)),
                supported_by_current_road_decoder=(
                    schema_names == {"Adp.Perception.Road"}
                    and {value.lower() for value in message_encodings}
                    == {"protobuf"}
                ),
                supported_by_structure_probe=(
                    schema_names == {"Adp.Perception.EstimatedDrivePaths"}
                    and {value.lower() for value in message_encodings}
                    == {"protobuf"}
                ),
            )
        )
    return tuple(records)


def inspect_mcap_topics(
    path: str | Path,
    *,
    topics: Sequence[str] = DEFAULT_DIRECT_PATH_TOPICS,
) -> tuple[TopicProbeRecord, ...]:
    """Inspect candidate path topics without decoding their message payloads."""

    try:
        from mcap.reader import make_reader
    except ImportError as error:
        raise McapDependencyError(
            'MCAP inspection requires the optional "mcap" dependencies; '
            'install with pip install -e ".[mcap]"'
        ) from error

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    with source.open("rb") as stream:
        summary = make_reader(stream).get_summary()
    if summary is None:
        raise RoadMessageError("MCAP file has no readable summary")
    return topic_probe_from_summary(summary, topics=topics)
