"""Real MCAP containers with generic synthetic Protobuf roots, no lane data."""

from io import BytesIO
import struct

from tests.io.test_recording_inventory import assemble, split, record


def recording(*, compression="ZSTD", count=3, crcs=True, index_types=None,
              statistics=True, multi=False, same_chunk=False, required=False, invalid_last=False,
              bad_schema=False, epoch=500):
    from google.protobuf import descriptor_pb2
    from mcap.writer import Writer, CompressionType
    buffer = BytesIO()
    options = {"compression": getattr(CompressionType, compression), "chunk_size": 1024**2 if same_chunk else 1,
               "enable_crcs": crcs, "use_statistics": statistics}
    if index_types is not None:
        options["index_types"] = index_types
    writer = Writer(buffer, **options); writer.start()
    descriptors = descriptor_pb2.FileDescriptorSet(); file = descriptors.file.add()
    file.name = "synthetic_decode.proto"; file.package = "DecodeTest"; file.syntax = "proto2"
    message = file.message_type.add(); message.name = "Sample"
    field = message.field.add(); field.name = "value"; field.number = 1; field.type = field.TYPE_BYTES
    field.label = field.LABEL_REQUIRED if required else field.LABEL_OPTIONAL
    first = writer.register_schema("Absent.Root" if bad_schema else "DecodeTest.Sample", "protobuf", descriptors.SerializeToString())
    channel = writer.register_channel("/selected", "protobuf", first)
    ignored = writer.register_channel("/ignored", "opaque", 0)
    writer.add_message(ignored, epoch+10, b"INVALID PRIVATE UNSELECTED PAYLOAD", epoch+10)
    channels = [channel]
    if multi:
        file.name = "synthetic_decode_v2.proto"; file.package = "DecodeTestV2"
        second = writer.register_schema("DecodeTestV2.Sample", "protobuf", descriptors.SerializeToString())
        channels.append(writer.register_channel("/selected", "protobuf", second))
    for i in range(count):
        # Protobuf field 1, length-delimited bytes; content stays synthetic.
        value = f"sample-{i}".encode(); payload = bytes((10, len(value))) + value
        if required and count == 1:
            payload = b""  # Syntactically valid, proto2 required value missing.
        if invalid_last and i == count-1:
            payload = b"\xffPRIVATE PATH AND COORDINATES"
        writer.add_message(channels[i % len(channels)], epoch-i, payload, epoch-2*i, sequence=i+1)
    writer.finish()
    return buffer.getvalue()


def records(raw):
    position, result = 0, []
    while position < len(raw):
        _, length = struct.unpack_from("<BQ", raw, position)
        result.append(raw[position:position+9+length]); position += 9+length
    return result


def rewrite(raw, opcode, function):
    prefix, groups = split(raw)
    grouped = []
    for op, data in groups:
        if grouped and grouped[-1][0] == op:
            grouped[-1] = (op, grouped[-1][1]+data)
        else:
            grouped.append((op, data))
    groups = [(op, function(data) if op == opcode else data) for op, data in grouped]
    return assemble(prefix, groups)


def inflated_statistics(raw):
    def change(data):
        payload = bytearray(data[9:]); total = struct.unpack_from("<Q", payload)[0]
        struct.pack_into("<Q", payload, 0, total+1)
        map_length = struct.unpack_from("<I", payload, 42)[0]
        for offset in range(46, 46+map_length, 10):
            key, value = struct.unpack_from("<HQ", payload, offset)
            if key == 1:
                struct.pack_into("<Q", payload, offset+2, value+1)
        return record(11, payload)
    return rewrite(raw, 11, change)
