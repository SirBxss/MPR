"""Real synthetic Protobuf/MCAP science fixtures; never private recording bytes."""

from io import BytesIO
from types import SimpleNamespace

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from tests.domain.test_geometry_validation import _estimated_schema
from lane_residuals.domain.path_source_probe import _field_is_repeated

T = 2_000_000_000
TOPICS = ("/adp/estimated_drive_paths", "/adp/road_lane_map_based", "/adp/odometry")


def descriptor_files(mutate=None):
    file=descriptor_pb2.FileDescriptorProto(name="bounded_readiness_fixture.proto",package="Adp.Perception",syntax="proto3")
    fixture=_estimated_schema();enums={}
    for descriptor in (fixture.root,fixture.path):
        for field in descriptor.fields:
            if field.enum_type is not None:
                enums[field.enum_type.full_name]=field.enum_type
    for name,enum in enums.items():
        target=file.enum_type.add(name=name.rsplit(".",1)[1])
        for value in enum.values:
            target.value.add(name=value.name,number=value.number)
    for descriptor in (fixture.model,fixture.path,fixture.root):
        target=file.message_type.add(name=descriptor.full_name.rsplit(".",1)[1])
        for field in descriptor.fields:
            value=target.field.add(name=field.name,number=field.number,type=field.type,label=3 if field.is_repeated else 1)
            reference=field.message_type if field.type==11 else field.enum_type
            if reference is not None:
                value.type_name="."+reference.full_name
    def message(name,fields):
        target=file.message_type.add(name=name)
        for i,(name,kind,repeated,child) in enumerate(fields,1):
            value=target.field.add(name=name,number=i,type=kind,label=3 if repeated else 1)
            if child:
                value.type_name=".Adp.Perception."+child
        return target
    message("Point",[("x",1,False,None),("y",1,False,None)])
    message("Range",[("start",5,False,None),("size",5,False,None)])
    message("Lane",[("id",4,False,None),("drive_path_range",11,False,"Range"),("is_ego_lane",8,False,None)])
    message("Road",[("time_stamp",4,False,None),("polyline_vertex_pool",11,True,"Point"),("lane_segments",11,True,"Lane")])
    odometry=descriptor_pb2.FileDescriptorProto(name="bounded_odometry_fixture.proto",package="Adp",syntax="proto3")
    state=odometry.message_type.add(name="OdometryState")
    for i,(name,kind) in enumerate((("timestamp",4),("x_position",1),("y_position",1),("yaw_angle",1)),1):
        state.field.add(name=name,number=i,type=kind,label=1)
    if mutate is not None:
        mutate(file,odometry)
    return file,odometry


def classes(mutate=None):
    files=descriptor_files(mutate);pool=descriptor_pool.DescriptorPool()
    for file in files:
        pool.Add(file)
    return tuple(message_factory.GetMessageClass(pool.FindMessageTypeByName(name)) for name in
                 ("Adp.Perception.EstimatedDrivePaths","Adp.Perception.Road","Adp.OdometryState"))


def messages(*, times=(T,T+100_000_000), confidence=.5, confidence_count=40, mutate=None, invalid_geometry=False, no_odometry=False, invalid_odometry=False, topology=1, reference_length=120., reference_offset=.5, ambiguous_reference=False):
    E,R,O=classes(mutate);result=[]
    for i,time in enumerate(times):
        estimate=E();road=R()
        for value in (estimate,road):
            field=value.DESCRIPTOR.fields_by_name.get("time_stamp")
            if field is not None and field.type!=11:
                setattr(value,"time_stamp",time)
        if "topology_source" in estimate.DESCRIPTOR.fields_by_name:
            estimate.topology_source=topology
        path=estimate.drive_paths.add(error=1,role=1,model_parameters_optional_flag=True)
        path.model_parameters.segment_starts.extend([-5.,0.,120.]);path.model_parameters.curvature_change.extend([0.,0.])
        ambiguous=ambiguous_reference and i==0
        if ambiguous:
            path.model_parameters.x_0=60.
        field=path.DESCRIPTOR.fields_by_name.get("drive_path_confidences")
        if field is not None:
            values=[] if confidence is None else [confidence]*confidence_count
            if _field_is_repeated(field) and field.type!=11:
                getattr(path,"drive_path_confidences").extend(values)
            elif field.type in (1,2,3,4,5,6,7,13,15,16,17,18):
                path.drive_path_confidences=confidence or 0
        vertices=((-1.,0.),(10.,0.),(20.,-2.),(150.,-2.),(150.,2.),(20.,2.)) if ambiguous else ((-1.,reference_offset),(reference_length,reference_offset))
        if "polyline_vertex_pool" in road.DESCRIPTOR.fields_by_name:
            for x,y in vertices:
                point=road.polyline_vertex_pool.add()
                if point.DESCRIPTOR.fields_by_name.get("x") is not None and point.DESCRIPTOR.fields_by_name["x"].type!=11:
                    point.x=float("nan") if invalid_geometry else x
                if "y" in point.DESCRIPTOR.fields_by_name:
                    point.y=y
        lane=road.lane_segments.add(id=1)
        if "is_ego_lane" in lane.DESCRIPTOR.fields_by_name:
            lane.is_ego_lane=True
        if "drive_path_range" in lane.DESCRIPTOR.fields_by_name:
            if "size" in lane.drive_path_range.DESCRIPTOR.fields_by_name:
                lane.drive_path_range.size=len(vertices)
        result.extend((estimate,road))
        if not no_odometry:
            for timestamp,x in ((max(0,time-50_000_000),float(i)),(time,float(i)+.5)):
                state=O()
                for name,value in (("timestamp",timestamp),("x_position",float("nan") if invalid_odometry else x),("y_position",0.),("yaw_angle",0.)):
                    if name in state.DESCRIPTOR.fields_by_name:
                        setattr(state,name,value)
                result.append(state)
    return result


def stream_items(values):
    for value in values:
        descriptor=value.DESCRIPTOR
        role=(0 if descriptor.full_name.endswith("EstimatedDrivePaths") else 1 if descriptor.full_name.endswith("Road") else 2)
        file=descriptor_pb2.FileDescriptorSet();file.file.add().ParseFromString(descriptor.file.serialized_pb)
        yield (SimpleNamespace(name=descriptor.full_name,data=file.SerializeToString()),
            SimpleNamespace(topic=TOPICS[role],message_encoding="protobuf"),SimpleNamespace(log_time=T+2_000_000_000,publish_time=T+2_000_000_001),value)


def recording(*, compression="ZSTD",crcs=True,extra_streams=(),**options):
    from mcap.writer import CompressionType, Writer
    values=messages(**options);E,R,O=classes(options.get("mutate"))
    buffer=BytesIO();writer=Writer(buffer,compression=getattr(CompressionType,compression),chunk_size=1,enable_crcs=crcs);writer.start()
    channels={}
    for topic,kind in zip(TOPICS,(E,R,O)):
        file=descriptor_pb2.FileDescriptorSet();file.file.add().ParseFromString(kind.DESCRIPTOR.file.serialized_pb)
        schema=writer.register_schema(kind.DESCRIPTOR.full_name,"protobuf",file.SerializeToString())
        channels[kind.DESCRIPTOR.full_name]=writer.register_channel(topic,"protobuf",schema)
    for i,(_,_,message,value) in enumerate(stream_items(values)):
        writer.add_message(channels[value.DESCRIPTOR.full_name],message.log_time,value.SerializeToString(),message.publish_time,sequence=i)
    for topic,kind,extra_values in extra_streams:
        file=descriptor_pb2.FileDescriptorSet();file.file.add().ParseFromString(kind.DESCRIPTOR.file.serialized_pb)
        schema=writer.register_schema(kind.DESCRIPTOR.full_name,"protobuf",file.SerializeToString())
        channel=writer.register_channel(topic,"protobuf",schema)
        for value in extra_values:
            writer.add_message(channel,T+2_000_000_000,value.SerializeToString(),T+2_000_000_001)
    writer.finish();return buffer.getvalue()


def remove_field(message_name,field_name):
    def mutate(file,odometry):
        parent=odometry if message_name=="OdometryState" else file
        message=next(m for m in parent.message_type if m.name==message_name)
        keep=[f for f in message.field if f.name!=field_name]
        del message.field[:];message.field.extend(keep)
    return mutate
