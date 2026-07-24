"""Streaming MCAP/Protobuf ingestion for road-model messages.

The MCAP dependency is deliberately optional.  The geometry and statistical
modules can still be installed and tested without MCAP support; install the
``mcap`` extra when real recordings are processed.

Only schema-backed Protobuf messages are decoded.  No attempt is made to guess
the structure of opaque binary payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike

from .residuals import FloatArray

MetadataValue = bool | int | float | str


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
        )
    )
    lane_segments = tuple(
        _get_attr(message, ("lane_segments", "lane_segments_"))
    )
    if not vertices:
        raise RoadMessageError("polyline vertex pool is empty")
    if not lane_segments:
        raise RoadMessageError("lane segment list is empty")

    x_pool = np.asarray(
        [_mean(_get_attr(vertex, ("x", "x_"))) for vertex in vertices],
        dtype=np.float64,
    )
    y_pool = np.asarray(
        [_mean(_get_attr(vertex, ("y", "y_"))) for vertex in vertices],
        dtype=np.float64,
    )

    heading_values = [
        _get_attr(vertex, ("heading", "heading_"), default=None)
        for vertex in vertices
    ]
    heading_pool = (
        np.asarray([_mean(value) for value in heading_values], dtype=np.float64)
        if all(value is not None for value in heading_values)
        else None
    )

    curvature_values = [
        _get_attr(vertex, ("curvature", "curvature_"), default=None)
        for vertex in vertices
    ]
    curvature_pool = (
        np.asarray([_mean(value) for value in curvature_values], dtype=np.float64)
        if all(value is not None for value in curvature_values)
        else None
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
        raise RoadMessageError(
            "polyline arc-length pool does not match the vertex-pool length"
        )

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

    extracted: list[RoadSegment] = []
    for lane_segment in lane_segments:
        segment_id = int(_get_attr(lane_segment, ("id", "id_")))
        drive_path_range = _get_attr(
            lane_segment,
            ("drive_path_range", "drive_path_range_"),
        )
        start = int(_get_attr(drive_path_range, ("start", "start_")))
        size = int(_get_attr(drive_path_range, ("size", "size_")))
        end = start + size
        if start < 0 or size < 2 or end > len(vertices):
            continue

        x = x_pool[start:end]
        y = y_pool[start:end]
        arc_length = (
            arc_pool[start:end]
            if arc_pool is not None
            else _geometric_arc_length(x, y)
        )
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
                    heading=None if heading_pool is None else heading_pool[start:end],
                    curvature=(
                        None
                        if curvature_pool is None
                        else curvature_pool[start:end]
                    ),
                    is_ego=is_ego,
                    quality=quality,
                )
            )
        except RoadMessageError:
            # One malformed range must not discard every usable segment in the frame.
            continue

    if not extracted:
        raise RoadMessageError("message contains no valid road segments")

    metadata: list[tuple[str, MetadataValue]] = []
    for output_name, aliases in (
        (
            "quality",
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

    for schema, channel, message, decoded in decoded_messages:
        topic = str(channel.topic)
        if topic not in grouped:
            continue
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
        except RoadMessageError:
            continue
        grouped[topic].append(frame)

    for frames in grouped.values():
        frames.sort(key=lambda frame: frame.log_time_ns)
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
