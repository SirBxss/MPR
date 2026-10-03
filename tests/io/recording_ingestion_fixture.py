"""Small indexed Protobuf MCAP with the same schema/geometry as reviewed tests."""

from tests.domain.test_geometry_validation import _estimated_schema
from tests.domain.test_exploratory_residuals import T


def write_recording(path, *, times=(T, T + 100_000_000), include_odometry=True,
                    missing_confidence_at=None, enable_crcs=True):
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    from mcap.writer import Writer, CompressionType
    from lane_residuals.io.recording_pair_feasibility import TOPICS
    from lane_residuals.io.odometry import DEFAULT_ODOMETRY_TOPIC

    geometry = descriptor_pb2.FileDescriptorProto(name="ingestion_geometry.proto", package="Adp.Perception", syntax="proto3")
    fixture = _estimated_schema()
    enums = {}
    for item in (fixture.root, fixture.path):
        for field in item.fields:
            if field.enum_type is not None:
                enums[field.enum_type.full_name] = field.enum_type
    for name, enum in enums.items():
        target = geometry.enum_type.add(name=name.rsplit(".", 1)[1])
        for value in enum.values:
            target.value.add(name=value.name, number=value.number)
    for item in (fixture.model, fixture.path, fixture.root):
        target = geometry.message_type.add(name=item.full_name.rsplit(".", 1)[1])
        for field in item.fields:
            target_field = target.field.add(name=field.name, number=field.number, type=field.type,
                                            label=3 if field.is_repeated else 1)
            reference = field.message_type if field.type == 11 else field.enum_type
            if reference is not None:
                target_field.type_name = "." + reference.full_name

    def message(name, fields):
        result = geometry.message_type.add(name=name)
        for number, (field_name, kind, repeated, target) in enumerate(fields, 1):
            field = result.field.add(name=field_name, number=number, type=kind, label=3 if repeated else 1)
            if target:
                field.type_name = ".Adp.Perception." + target
    message("Point", [("x", 1, False, None), ("y", 1, False, None)])
    message("Range", [("start", 5, False, None), ("size", 5, False, None)])
    message("Lane", [("id", 4, False, None), ("drive_path_range", 11, False, "Range"), ("is_ego_lane", 8, False, None)])
    message("Road", [("time_stamp", 4, False, None), ("polyline_vertex_pool", 11, True, "Point"), ("lane_segments", 11, True, "Lane")])
    odometry = descriptor_pb2.FileDescriptorProto(name="ingestion_odometry.proto", package="Adp", syntax="proto3")
    odo = odometry.message_type.add(name="OdometryState")
    for number, (name, kind) in enumerate((("timestamp", 4), ("x_position", 1), ("y_position", 1), ("yaw_angle", 1)), 1):
        odo.field.add(name=name, number=number, type=kind, label=1)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(geometry)
    pool.Add(odometry)
    names = ("Adp.Perception.EstimatedDrivePaths", "Adp.Perception.Road", "Adp.OdometryState")
    EDP, Road, Odo = [message_factory.GetMessageClass(pool.FindMessageTypeByName(name)) for name in names]
    descriptors = descriptor_pb2.FileDescriptorSet()
    for item in (geometry, odometry):
        descriptors.file.add().CopyFrom(item)
    with path.open("wb") as stream:
        writer = Writer(stream, compression=CompressionType.ZSTD, chunk_size=1, enable_crcs=enable_crcs)
        writer.start()
        channels = []
        for topic, name in zip((*TOPICS, DEFAULT_ODOMETRY_TOPIC), names):
            schema = writer.register_schema(name, "protobuf", descriptors.SerializeToString())
            channels.append(writer.register_channel(topic, "protobuf", schema))
        ignored = writer.register_channel("/ignored", "protobuf", schema)
        writer.add_message(ignored, T, b"invalid unselected protobuf", T)
        for i, time in enumerate(times):
            estimate = EDP(time_stamp=time, topology_source=1)
            path_message = estimate.drive_paths.add(error=1, role=1, model_parameters_optional_flag=True)
            path_message.model_parameters.segment_starts.extend((-5., 0., 120.))
            path_message.model_parameters.curvature_change.extend((0., 0.))
            if i != missing_confidence_at:
                path_message.drive_path_confidences.extend([.5] * 40)
            road = Road(time_stamp=time)
            road.polyline_vertex_pool.add(x=-1., y=.5)
            road.polyline_vertex_pool.add(x=101., y=.5)
            lane = road.lane_segments.add(id=1, is_ego_lane=True)
            lane.drive_path_range.start, lane.drive_path_range.size = 0, 2
            payloads = [(channels[0], estimate), (channels[1], road)]
            if include_odometry:
                payloads.extend([(channels[2], Odo(timestamp=time-50_000_000, x_position=i)),
                                 (channels[2], Odo(timestamp=time, x_position=i+.5))])
            for channel, payload in payloads:
                log = time + 1_000_000_000
                writer.add_message(channel, log, payload.SerializeToString(), log)
        writer.finish()
