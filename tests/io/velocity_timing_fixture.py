"""Synthetic interfaces and original-cache shapes; no private descriptor bytes."""
from io import BytesIO
import hashlib
import json
from pathlib import Path


LOG = 2**60
SOURCE = 2**55


def row(i):
    return {"candidate_index": i, "recording_id": "synthetic", "estimate_message_index": i, "pair_index": i,
        "estimate_source_time_ns_decimal_private": str(SOURCE+i*100_000_000),
        "estimate_log_time_ns_decimal_private": str(LOG+i*100_000_000),
        "estimate_publish_time_ns_decimal_private": str(SOURCE+i*100_000_000+1000),
        "residual_available": True, "conditions_available": True, "condition_failure_codes": []}


def recording(compression="ZSTD"):
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    from mcap.writer import Writer, CompressionType
    from lane_residuals.domain.velocity_timing import TOPICS
    value = descriptor_pb2.FileDescriptorSet()
    file = value.file.add(name="synthetic_velocity.proto", package="Adp", syntax="proto3")
    enum = file.enum_type.add(name="SyntheticQuality")
    for name, number in (("INITIAL", 0), ("VALID", 1), ("INVALID", 255)):
        enum.value.add(name=name, number=number)
    m = file.message_type.add(name="QualifiedTimedFloat64")
    m.field.add(name="value", number=1, type=1, label=1)
    m.field.add(name="qualifier", number=2, type=14, label=1, type_name=".Adp.SyntheticQuality")
    m.field.add(name="timestamp", number=3, type=18, label=1)
    m = file.message_type.add(name="VehicleVelocity")
    m.field.add(name="velocity", number=1, type=11, label=1, type_name=".Adp.QualifiedTimedFloat64")
    m.field.add(name="status_velocity_near_standstill", number=2, type=5, label=1)
    m.field.add(name="qualifier", number=3, type=5, label=1)
    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(file.SerializeToString())
    scalar = message_factory.GetMessageClass(pool.FindMessageTypeByName("Adp.QualifiedTimedFloat64"))
    vehicle = message_factory.GetMessageClass(pool.FindMessageTypeByName("Adp.VehicleVelocity"))
    stream = BytesIO()
    writer = Writer(stream, compression=getattr(CompressionType, compression), chunk_size=1, enable_crcs=True)
    writer.start()
    a = writer.register_schema("Adp.QualifiedTimedFloat64", "protobuf", value.SerializeToString())
    b = writer.register_schema("Adp.VehicleVelocity", "protobuf", value.SerializeToString())
    channels = [writer.register_channel(TOPICS[0], "protobuf", a), writer.register_channel(TOPICS[1], "protobuf", b)]
    ignored = writer.register_channel("/ignored", "opaque", 0)
    writer.add_message(ignored, LOG, b"\xffunselected invalid wire", SOURCE)
    for i, quality in enumerate((1, 255, 1)):
        message = scalar(value=10+i, qualifier=quality, timestamp=SOURCE+i*100_000_000-20_000_000)
        writer.add_message(channels[0], LOG+i*100_000_000-10_000_000, message.SerializeToString(), SOURCE+i*100_000_000-1000)
        control = vehicle(velocity=scalar(value=10+i, qualifier=1, timestamp=0), qualifier=2)
        writer.add_message(channels[1], LOG+i*100_000_000-10_000_000, control.SerializeToString(), SOURCE+i*100_000_000-1000)
    # A far-away chunk is outside the fixed indexed window and must not be read.
    writer.add_message(channels[0], LOG+100_000_000_000, scalar(value=99, qualifier=1, timestamp=SOURCE).SerializeToString(), SOURCE)
    writer.finish()
    return stream.getvalue()


def prepare(base, role="development"):
    import numpy as np
    from lane_residuals.io.recording_inventory import read_inventory
    from lane_residuals.io.velocity_summary_probe import REVISION as SUMMARY_REVISION
    from lane_residuals.io.velocity_timing_pilot import REVISION, WINDOW_NS
    base = Path(base)
    raw = recording()
    path = base/"input.mcap"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    def save(name, value):
        data = (json.dumps(value)+"\n").encode()
        (base/name).write_bytes(data)
        return hashlib.sha256(data).hexdigest()
    cohort = save("cohort.json", {"cohort_lock_created": True, "outings": [{"outing_id": "synthetic", "cohort_role": role,
        "raw_sha256": [digest]}]})
    inv = read_inventory(BytesIO(raw), len(raw))
    inventory = save("inventory.json", {"purpose": "development_only_recording_inventory", "recordings": [{
        "recording_id": "synthetic", "raw_sha256": digest, "size_bytes": len(raw), "status": "complete", "inventory": inv}]})
    rows = [row(i) for i in range(125)]
    audit = save("audit.json", {"rows": rows})
    buffer = BytesIO()
    np.savez_compressed(buffer, conditioned_profile_indices=np.arange(125), candidate_index=np.arange(125), conditions=np.full((125, 6), 10.))
    payload = buffer.getvalue()
    (base/"numeric.npz").write_bytes(payload)
    summary = save("numeric.json", {"status": "complete", "preserved_inventory_report_sha256": inventory,
        "artifacts_sha256": {"candidate_audit.json": audit, "residuals.npz": hashlib.sha256(payload).hexdigest()}})
    request = {"revision": REVISION, "summary_scope": {"revision": SUMMARY_REVISION, "outing_id": "synthetic",
        "recording_id": "synthetic", "raw_sha256": digest, "size_bytes": len(raw), "raw_path_private": str(path),
        "cohort_file": "cohort.json", "cohort_sha256": cohort, "inventory_file": "inventory.json", "inventory_sha256": inventory},
        "numeric_summary_file": "numeric.json", "numeric_summary_sha256": summary, "audit_file": "audit.json",
        "numeric_file": "numeric.npz", "window_start_log_ns": str(LOG), "window_end_log_ns": str(LOG+WINDOW_NS)}
    pin = save("request.json", request)
    return base/"request.json", pin, path
