"""Streaming MCAP/Protobuf ingestion for road-model messages.

The MCAP dependency is deliberately optional.  The geometry and statistical
modules can still be installed and tested without MCAP support; install the
``mcap`` extra when real recordings are processed.

Only schema-backed Protobuf messages are decoded.  No attempt is made to guess
the structure of opaque binary payloads.
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


class McapDependencyError(ImportError):
    """Raised when the optional MCAP decoder dependencies are unavailable."""


class RoadMessageError(ValueError):
    """Raised when a decoded message is not a usable road-model message."""


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

    @property
    def points(self) -> FloatArray:
        """Return centreline coordinates with shape ``(n_points, 2)``."""

        return np.column_stack((self.x, self.y))


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
        if not self.segments:
            raise RoadMessageError("a road frame must contain at least one valid segment")

    @property
    def metadata_dict(self) -> dict[str, MetadataValue]:
        """Return preserved message metadata as a regular dictionary."""

        return dict(self.metadata)


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
    rejection_reasons: Counter[str] = Counter()
    for segment_index, lane_segment in enumerate(lane_segments):
        segment_id = int(_get_attr(lane_segment, ("id", "id_")))
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
                rejection_reasons[str(error)] += 1
                continue
            x = midpoint[:, 0]
            y = midpoint[:, 1]
            arc_length = _geometric_arc_length(x, y)
            heading = None
            curvature = None
            geometry_source = "paired_boundaries"

        is_ego = _optional_bool(
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
            is_ego = segment_id == ego_segment_id
        elif ego_indices:
            is_ego = segment_index in ego_indices

        quality = _optional_metadata(
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
        try:
            extracted.append(
                RoadSegment(
                    segment_id=segment_id,
                    x=x,
                    y=y,
                    arc_length=arc_length,
                    heading=heading,
                    curvature=curvature,
                    is_ego=is_ego,
                    quality=quality,
                    geometry_source=geometry_source,
                )
            )
        except RoadMessageError as error:
            # One malformed range must not discard every usable segment in the frame.
            rejection_reasons[str(error)] += 1
            continue

    if not extracted:
        details = ", ".join(
            f"{count}x {reason}"
            for reason, count in rejection_reasons.most_common(3)
        )
        suffix = f": {details}" if details else ""
        raise RoadMessageError(f"message contains no valid road segments{suffix}")

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
        metadata=tuple(metadata),
    )


def road_frames_from_decoded_messages(
    decoded_messages: Iterable[tuple[Any, Any, Any, Any]],
    *,
    topics: Sequence[str],
    expected_schema_name: str = "Adp.Perception.Road",
) -> dict[str, list[RoadFrame]]:
    """Convert decoded MCAP tuples into road frames grouped by topic."""

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
            rejection_reasons[topic][str(error)] += 1
            continue
        grouped[topic].append(frame)

    for topic, frames in grouped.items():
        frames.sort(key=lambda frame: frame.log_time_ns)
        if decoded_counts[topic] and not frames:
            details = "; ".join(
                f"{count}x {reason}"
                for reason, count in rejection_reasons[topic].most_common(3)
            )
            raise RoadMessageError(
                f'topic "{topic}" had {decoded_counts[topic]} decoded messages, '
                f"but all failed road extraction: {details}"
            )
    return grouped


def _iter_decoded_mcap_messages(
    path: Path,
    *,
    topics: Sequence[str],
) -> Iterator[tuple[Any, Any, Any, Any]]:
    try:
        from mcap.reader import NonSeekingReader, SeekingReader
        from mcap_protobuf.decoder import DecoderFactory as ProtobufDecoderFactory
    except ImportError as error:
        raise McapDependencyError(
            'MCAP support is not installed. Run: pip install -e ".[mcap]"'
        ) from error

    with path.open("rb") as stream:
        reader_type = SeekingReader if stream.seekable() else NonSeekingReader
        reader = reader_type(
            stream,
            validate_crcs=False,
            decoder_factories=[ProtobufDecoderFactory()],
            record_size_limit=None,
        )
        yield from reader.iter_decoded_messages(topics=list(topics))


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
    return road_frames_from_decoded_messages(
        _iter_decoded_mcap_messages(source, topics=topics),
        topics=topics,
        expected_schema_name=expected_schema_name,
    )
