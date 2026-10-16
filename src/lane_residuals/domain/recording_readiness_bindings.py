"""Descriptor-only gates for the accepted bounded readiness consumer.

These checks deliberately do not change historical converters or generation
classification. No payload qualifier participates in a descriptor decision.
"""

from __future__ import annotations

import hashlib

from .path_source_probe import _field_is_repeated, estimate_descriptor_support

INTEGER = frozenset((3, 4, 5, 6, 7, 13, 15, 16, 17, 18))
NUMERIC = INTEGER | {1, 2}
ROOTS = {"estimate": "Adp.Perception.EstimatedDrivePaths", "reference": "Adp.Perception.Road", "odometry": "Adp.OdometryState"}
ROOT_EGO_IDS = ("ego_lane_segment_id", "ego_lane_segment_id_", "ego_lane_id", "ego_lane_id_", "host_lane_segment_id", "host_lane_segment_id_", "current_lane_segment_id", "current_lane_segment_id_")
EGO_FLAGS = ("is_ego_lane", "is_ego_lane_", "ego_lane", "ego_lane_", "is_host_lane", "is_host_lane_", "is_ego", "is_ego_", "is_current_lane", "is_current_lane_")
LATE_ESTIMATE_BINDINGS = frozenset("estimate_"+name for name in (
    "estimate_descriptor_missing", "unsupported_estimate_descriptor_generation",
    "candidate_v2_descriptor_contract_mismatch", "legacy_index_0_descriptor_contract_mismatch", "schema_bindings_incomplete")) | {"estimate_schema_or_encoding_mismatch"}


class _Unsupported(ValueError):
    pass


def _aliases(name):
    return (name, name+"_")


def _fields(descriptor, names, *, present=False):
    result = [descriptor.fields_by_name[n] for n in names if n in descriptor.fields_by_name]
    return result if present else result[:1]


def _field(descriptor, names, *, required=True, types=None, repeated=False):
    values = _fields(descriptor, names)
    if not values:
        if required:
            raise _Unsupported()
        return None
    field = values[0]
    _shape(field, types, repeated)
    return field


def _shape(field, types, repeated=False):
    if (_field_is_repeated(field) != repeated or (types is not None and field.type not in types) or
            (field.message_type is not None and field.message_type.GetOptions().map_entry)):
        raise _Unsupported()


def _message(descriptor, names, *, required=True, repeated=False):
    field = _field(descriptor, names, required=required, types={11}, repeated=repeated)
    return None if field is None else field.message_type


def _enum(descriptor, name, symbol):
    field = _field(descriptor, (name,), types={14})
    if symbol not in field.enum_type.values_by_name:
        raise _Unsupported()


def _timestamp(field):
    _shape(field, INTEGER | {11})
    if field.type == 11:
        descriptor = field.message_type
        _field(descriptor, ("seconds", "secs", "sec"), types=INTEGER)
        _field(descriptor, ("fractional_seconds", "fractional_seconds_", "nanoseconds", "nanos", "nsecs", "nanosec"), required=False, types=INTEGER)


def _clock(descriptor):
    direct = _fields(descriptor, ("time_stamp", "time_stamp_", "timestamp", "timestamp_"), present=True)
    headers = _fields(descriptor, ("header", "header_"), present=True)
    for field in direct:
        _timestamp(field)
    for header in headers:
        _shape(header, {11})
        _timestamp(_field(header.message_type, ("stamp", "stamp_")))
    if not direct and not headers:
        raise _Unsupported()


def _coordinate(field):
    _shape(field, NUMERIC | {11})
    if field.type == 11:
        _field(field.message_type, _aliases("mean"), types=NUMERIC)
        _field(field.message_type, _aliases("invalid_flags"), required=False, types=INTEGER)


def _vertices(descriptor, name, *, required=False):
    vertex = _message(descriptor, _aliases(name), required=required, repeated=True)
    if vertex is None:
        return
    for axis in ("x", "y"):
        _coordinate(_field(vertex, _aliases(axis)))
    for name in ("heading", "curvature"):
        field = _field(vertex, _aliases(name), required=False)
        if field is not None:
            _coordinate(field)


def _range(descriptor, names, *, required=False):
    child = _message(descriptor, names, required=required)
    if child is not None:
        for name in ("start", "size"):
            _field(child, _aliases(name), types=INTEGER)


def _reference(descriptor):
    _clock(descriptor)
    lane = _message(descriptor, _aliases("lane_segments"), repeated=True)
    _field(lane, _aliases("id"), types=INTEGER)
    _vertices(descriptor, "polyline_vertex_pool", required=True)
    _range(lane, _aliases("drive_path_range"), required=True)
    ego_ids = _fields(descriptor, ROOT_EGO_IDS, present=True)
    for field in ego_ids:
        _shape(field, INTEGER)
    indices = _field(descriptor, _aliases("ego_lane_segment_indices"), required=False, types=INTEGER, repeated=True)
    flags = _fields(lane, EGO_FLAGS, present=True)
    for field in flags:
        _shape(field, INTEGER | {8, 14})
        if field.type == 14 and 1 not in field.enum_type.values_by_number:
            raise _Unsupported()
    if not ego_ids and indices is None and not flags:
        raise _Unsupported()
    for name in ("successor_lane_segment_indices", "predecessor_lane_segment_indices"):
        _field(lane, _aliases(name), required=False, types=INTEGER, repeated=True)
    _vertices(descriptor, "boundary_vertex_pool")
    _field(descriptor, _aliases("polyline_arc_length_pool"), required=False, types=NUMERIC, repeated=True)
    boundary = _message(descriptor, _aliases("lane_boundary_pool"), required=False, repeated=True)
    if boundary is not None:
        _range(boundary, _aliases("geometry"))
    for side in ("left", "right"):
        ranges = _message(lane, _aliases(side+"_lane_boundary_ranges"), required=False)
        if ranges is not None:
            for name in ("camera_based", "map_based", "artificial"):
                _range(ranges, _aliases(name))


def _estimate(descriptor):
    _clock(descriptor)
    _enum(descriptor, "topology_source", "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY")
    path = _message(descriptor, ("drive_paths",), repeated=True)
    _enum(path, "role", "LANE_ROLE_KEEP_LANE")
    _enum(path, "error", "DRIVE_PATH_ERROR_NO_ERROR")
    model = _message(path, ("model_parameters",))
    for name in ("x_0", "y_0", "theta_0", "curvature_0"):
        _field(model, (name,), types=NUMERIC)
    for name in ("segment_starts", "curvature_change"):
        _field(model, (name,), types=NUMERIC, repeated=True)
    _field(path, ("drive_path_confidences",), types=NUMERIC, repeated=True)


def classify(message, role, schema_name, encoding, *, allow_bounded_v01911_edp=False):
    """Return (root-file SHA, static failure or None), without reading values."""
    descriptor = getattr(message, "DESCRIPTOR", None)
    digest = None if descriptor is None else hashlib.sha256(descriptor.file.serialized_pb).hexdigest()
    mismatch = {"estimate": "estimate_schema_or_encoding_mismatch", "reference": "map_schema_or_encoding_mismatch", "odometry": "odometry_schema_or_encoding_mismatch"}[role]
    if schema_name != ROOTS[role] or encoding != "protobuf" or (descriptor is not None and descriptor.full_name != ROOTS[role]):
        return digest, mismatch
    if role == "estimate":
        support = estimate_descriptor_support(
            message, allow_bounded_v01911_edp=allow_bounded_v01911_edp,
        )
        if not support.supported:
            return digest, support.failure_code
        if support.missing_required_fields:
            return digest, "schema_bindings_incomplete"
    code = {"estimate": "estimate_descriptor_fields_unsupported", "reference": "reference_descriptor_fields_unsupported", "odometry": "odometry_descriptor_fields_unsupported"}[role]
    try:
        if descriptor is None:
            raise _Unsupported()
        if role == "estimate":
            _estimate(descriptor)
        elif role == "reference":
            _reference(descriptor)
        else:
            _field(descriptor, ("timestamp",), types=INTEGER)
            for name in ("x_position", "y_position", "yaw_angle"):
                _field(descriptor, (name,), types=NUMERIC)
    except _Unsupported:
        return digest, code
    return digest, None
