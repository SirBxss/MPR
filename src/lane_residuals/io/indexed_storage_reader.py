"""Read indexed MCAP chunks incrementally in physical file order.

SeekingReader's FIFO storage-order queue first expands every selected chunk.
This adapter retains its summary/Protobuf decoding but never queues messages
from later chunks. Imports stay behind the optional MCAP dependency boundary.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct

from mcap.opcode import Opcode
from mcap.reader import SeekingReader
from mcap.records import Chunk, Message
from mcap.stream_reader import StreamReader, get_chunk_data_stream

from .recording_pair_feasibility import MAX_CHUNK_BYTES, RecordingReadError, ResourceLimitError


def _memory_snapshot():
    values = {"process_virtual_memory_bytes": None, "process_resident_memory_bytes": None}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            key = {"VmSize:": "process_virtual_memory_bytes", "VmRSS:": "process_resident_memory_bytes"}.get(line.split()[0])
            if key is not None:
                values[key] = int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return values


def _zstd_failure(error):
    # Inspect native text only to select fixed MPR codes. Never export that text.
    text = str(error).lower()
    if any(word in text for word in ("allocation error", "not enough memory", "could not create decompression context")):
        return ResourceLimitError("zstd_decompression_memory_limit")
    if "too much memory" in text:
        return ResourceLimitError("zstd_decoder_window_limit")
    if "dictionary" in text:
        return RecordingReadError("zstd_dictionary_error")
    if any(word in text for word in ("data corruption", "did not decompress full frame", "src size is incorrect")):
        return RecordingReadError("zstd_corrupt_or_incomplete_frame")
    return RecordingReadError("zstd_decompression_failed")


class IndexedStorageReader(SeekingReader):
    """SeekingReader summary and decoder API, with a chunkwise storage iterator."""

    def __init__(self, stream, **kwargs):
        super().__init__(stream, **kwargs)
        self._storage_source = stream
        self._storage_limit = kwargs.get("record_size_limit", MAX_CHUNK_BYTES)
        self._storage_validate_crcs = kwargs.get("validate_crcs", False)

    def iter_messages(self, topics=None, start_time=None, end_time=None,
                      log_time_order=True, reverse=False):
        if log_time_order or reverse or start_time is not None or end_time is not None:
            raise RecordingReadError("indexed_storage_order_without_time_filter_required")
        topics = None if topics is None else {topics} if isinstance(topics, str) else set(topics)
        summary = self.get_summary()
        if summary is None or not summary.chunk_indexes:
            raise ResourceLimitError("indexed_summary_required_no_scan_fallback")
        completed = 0
        previous_end = 8
        # Byte-offset ordering observes physical storage, never log/source time.
        for ordinal, index in enumerate(sorted(summary.chunk_indexes, key=lambda c: c.chunk_start_offset)):
            context = {"indexed_chunk_ordinal": ordinal, "chunk_start_offset_bytes": index.chunk_start_offset,
                       "completed_selected_chunk_count": completed, "phase": "chunk_read",
                       "compression": index.compression if index.compression in ("", "zstd", "lz4") else "unsupported"}
            try:
                if index.chunk_start_offset < previous_end or index.chunk_length < 9:
                    raise RecordingReadError("indexed_chunk_ranges_invalid_or_overlapping")
                previous_end = index.chunk_start_offset + index.chunk_length
                if any(key not in summary.channels for key in index.message_index_offsets):
                    raise RecordingReadError("chunk_index_channel_identity_mismatch")
                if (topics is not None and index.message_index_offsets and
                        not any(summary.channels[key].topic in topics for key in index.message_index_offsets)):
                    continue
                if self._storage_limit is None or max(index.chunk_length, index.uncompressed_size) > self._storage_limit:
                    raise ResourceLimitError("advertised_chunk_exceeds_resource_limit")
                self._storage_source.seek(index.chunk_start_offset)
                raw = self._storage_source.read(index.chunk_length)
                if len(raw) != index.chunk_length:
                    raise RecordingReadError("indexed_chunk_record_truncated")
                opcode, size = struct.unpack_from("<BQ", raw)
                if opcode != Opcode.CHUNK or size != len(raw) - 9:
                    raise RecordingReadError("indexed_chunk_record_identity_or_length_mismatch")
                chunk = next(StreamReader(BytesIO(raw), skip_magic=True, emit_chunks=True,
                                          record_size_limit=self._storage_limit).records)
                del raw
                if (not isinstance(chunk, Chunk) or chunk.uncompressed_size != index.uncompressed_size or
                        len(chunk.data) != index.compressed_size or chunk.compression != index.compression or
                        chunk.message_start_time != index.message_start_time or chunk.message_end_time != index.message_end_time):
                    raise RecordingReadError("indexed_chunk_header_mismatch")
                if chunk.compression not in ("", "zstd", "lz4"):
                    raise RecordingReadError("unsupported_chunk_compression")
                context["phase"] = "chunk_decompression"
                if chunk.compression == "zstd":
                    import zstandard
                    parameters = zstandard.get_frame_parameters(chunk.data)
                    if parameters.content_size not in (zstandard.CONTENTSIZE_UNKNOWN, zstandard.CONTENTSIZE_ERROR):
                        if parameters.content_size != chunk.uncompressed_size:
                            raise RecordingReadError("zstd_frame_content_size_mismatch")
                decoded, length = get_chunk_data_stream(chunk, validate_crc=self._storage_validate_crcs)
                if length != chunk.uncompressed_size:
                    raise RecordingReadError("chunk_uncompressed_size_mismatch")
                data = decoded.read(length) if length else b""
                del decoded, chunk
                context["phase"] = "chunk_records"
                yield from self._messages(data, summary, topics)
                del data
                completed += 1
            except Exception as error:
                original_class = type(error).__name__
                if original_class == "ZstdError":
                    error = _zstd_failure(error)
                # Only scalar container/progress observations, never a payload,
                # path, timestamp, exception text or prefix readiness count.
                error.reader_failure_context = {**context, "exception_class": original_class, **_memory_snapshot()}
                raise error

    def _messages(self, data, summary, topics):
        position = 0
        while position < len(data):
            if len(data) - position < 9:
                raise RecordingReadError("chunk_inner_record_header_truncated")
            opcode, size = struct.unpack_from("<BQ", data, position)
            position += 9
            end = position + size
            if size > self._storage_limit or end > len(data):
                raise RecordingReadError("chunk_inner_record_length_invalid")
            if opcode == Opcode.MESSAGE:
                if size < 22:
                    raise RecordingReadError("chunk_message_header_truncated")
                channel_id, sequence, log_time, publish_time = struct.unpack_from("<HIQQ", data, position)
                channel = summary.channels.get(channel_id)
                if channel is None:
                    raise RecordingReadError("chunk_message_channel_identity_mismatch")
                if topics is None or channel.topic in topics:
                    schema = None if channel.schema_id == 0 else summary.schemas.get(channel.schema_id)
                    if channel.schema_id != 0 and schema is None:
                        raise RecordingReadError("chunk_message_schema_identity_mismatch")
                    yield schema, channel, Message(channel_id=channel_id, sequence=sequence,
                        log_time=log_time, publish_time=publish_time, data=data[position + 22:end])
            position = end
