"""Public compatibility facade with lazy imports.

Historically this module eagerly imported every project layer.  That made a
structural-audit CLI import modeling, plotting, and residual construction
before its own module was reached.  Lazy resolution preserves the public names
while allowing narrow workflows to maintain auditable dependency boundaries.
"""

from __future__ import annotations

import importlib
from typing import Any


_PUBLIC_MODULES = (
    ".domain.residual_dataset",
    ".domain.alignment",
    ".domain.motion",
    ".batch_pairing_audit",
    ".edp_transition_audit",
    ".gaussian",
    ".geometry_validation",
    ".mcap_io",
    ".path_source_probe",
    ".pairing_audit",
    ".plotting",
    ".preprocessing",
    ".residuals",
    ".reference_audit",
    ".residual_extraction",
)

_PUBLIC_OVERRIDES = {
    # ``edp_transition_audit`` also defines an internal CandidateGeometry;
    # the historical root export is the reference-audit class.
    "CandidateGeometry": ".reference_audit",
    "EdpCandidateGeometry": ".edp_transition_audit",
}

__all__ = [
    "BatchAggregationError",
    "CANONICAL_MODEL_STATIONS_M",
    "CANONICAL_STATIONS_M",
    "DEFAULT_AUDIT_HORIZONS",
    "DEFAULT_COMPARATOR_SCHEMA",
    "DEFAULT_COMPARATOR_TOPIC",
    "DEFAULT_DIRECT_PATH_TOPICS",
    "DEFAULT_DEBUG_SCHEMA",
    "DEFAULT_DEBUG_TOPIC",
    "DEFAULT_EDP_TRANSITION_STATIONS_M",
    "DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA",
    "DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC",
    "DEFAULT_ESTIMATE_TOPIC",
    "DEFAULT_PAIRING_STATIONS_M",
    "DEFAULT_REFERENCE_TOPIC",
    "DEFAULT_REFERENCE_STATIONS_M",
    "DEFAULT_RESIDUAL_STATIONS_M",
    "DEFAULT_STATIONS",
    "EDP_SPLINE_HYPOTHESES",
    "EXPECTED_TOPOLOGY_SOURCE",
    "CandidateSegmentRecord",
    "CandidateDiscrepancy",
    "CandidateGeometry",
    "CandidateSnapshot",
    "CenterlineWorldSample",
    "ComparatorFrameAudit",
    "ComparatorGeometry",
    "CanonicalResidualDataset",
    "DecodedRecording",
    "DecodedResidualRecording",
    "DebugFrameAudit",
    "DebugSemanticAudit",
    "DebugSplineParameters",
    "DiagnosticPathDisagreement",
    "EdpCandidateGeometry",
    "EgoRelativePath",
    "EgoFrameTransform",
    "EstimatedFrameAudit",
    "ExtractionReport",
    "FrameRejection",
    "GaussianResidualModel",
    "HORIZON_60_M",
    "HORIZON_100_M",
    "GeometryValidationError",
    "HypothesisMetrics",
    "LaneAssociationExample",
    "LateralLaneSample",
    "McapDependencyError",
    "MutualNearestTimestampAudit",
    "OrderedEgoLane",
    "OdometrySample",
    "PairAuditRecord",
    "PathPointProjection",
    "Path2D",
    "PoseSample",
    "Pose2D",
    "PoseInterpolation",
    "ProtobufFieldProbe",
    "ProtobufJointPathSemanticAudit",
    "ProtobufMessageSemanticAudit",
    "ProtobufPathSemanticTuple",
    "ProtobufPathSourceProbe",
    "ResidualDataset",
    "ResidualDatasetContractError",
    "RESIDUAL_VECTOR_FIELDS",
    "RecordingAuditData",
    "ResidualObservation",
    "ResidualFrame",
    "RoadFrame",
    "RoadFrameLoadResult",
    "RoadMessageError",
    "RoadSegment",
    "RoadTopicLoadReport",
    "SegmentExtraction",
    "SelectedTransition",
    "SplineCurve",
    "SplineParameters",
    "SpatialAlignmentResult",
    "SynchronizationAudit",
    "SynchronizationPair",
    "TopicProbeRecord",
    "TimedMessage",
    "TimestampPair",
    "THESIS_TARGET_QUESTION",
    "THESIS_TARGET_VARIABLE",
    "build_residual_dataset",
    "build_residual_dataset_from_mcap",
    "build_canonical_residual_dataset",
    "audit_counts",
    "audit_pose_continuity",
    "build_hindsight_candidate",
    "candidate_from_polyline",
    "candidate_segment_records",
    "aggregate_fixed_cohorts",
    "aggregate_rlmb_chains",
    "detect_drive_overlaps",
    "comparator_frame_from_message",
    "compare_curve_to_comparator",
    "compare_selected_candidates",
    "compare_estimate_to_candidate",
    "compare_ego_relative_paths",
    "compare_reference_candidates",
    "compare_production_to_debug",
    "compare_spatially_aligned_paths",
    "compute_provisional_gt_residual",
    "contiguous_state_runs",
    "decode_recording_messages",
    "decode_residual_recording_messages",
    "debug_frame_from_message",
    "production_error_matches_debug",
    "estimated_frame_from_message",
    "ego_relative_path_from_points",
    "ego_relative_path_from_road_frame",
    "ego_relative_path_from_spline",
    "ego_frame_transform",
    "evenly_spaced_indices",
    "estimate_path_on_reference",
    "fit_gaussian_residual_model",
    "fixed_horizon_vectors",
    "flatten_scalar_fields",
    "inspect_mcap_topics",
    "inspect_protobuf_path_source",
    "interpolate_odometry_pose",
    "iter_decoded_mcap_messages",
    "load_road_frame_result",
    "load_road_frames",
    "latest_odometry_at_or_before_log_time",
    "mutual_nearest_timestamp_pairs",
    "nearest_monotone_pairs_unbounded",
    "ordered_ego_lane_from_road_frame",
    "origin_alignment_metrics",
    "plot_gaussian_residual_model",
    "plot_lane_association_audit",
    "plot_mcap_dataset_diagnostics",
    "plot_path_pair_and_residual",
    "probe_decoded_protobuf_messages",
    "project_points_to_polyline",
    "project_point_to_path",
    "generate_spline_curve",
    "generate_spline_hypotheses",
    "reference_path_from_segment",
    "rank_transition_centers",
    "reconstruct_centerline_samples",
    "reference_decision",
    "residual_matrix",
    "residual_column_name",
    "residual_vector",
    "road_frame_from_message",
    "road_frame_load_result_from_decoded_messages",
    "source_time_ns_from_message",
    "save_protobuf_path_source_probe",
    "save_residual_dataset",
    "sample_candidate",
    "sample_candidate_curve",
    "sample_ego_relative_path",
    "select_unique_ego_drive_path",
    "select_ego_segment",
    "state_transition_counts",
    "selected_candidate_transitions",
    "synchronize_road_frames",
    "temporal_diagnostic_rows",
    "synchronize_estimate_and_comparator",
    "summarize_field_catalog",
    "topic_probe_from_summary",
    "transform_path_to_target_ego_frame",
]


def __getattr__(name: str) -> Any:
    """Resolve a historical public export only when a caller requests it."""

    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name in _PUBLIC_OVERRIDES:
        module = importlib.import_module(_PUBLIC_OVERRIDES[name], __name__)
        attribute = "CandidateGeometry" if name == "EdpCandidateGeometry" else name
        value = getattr(module, attribute)
        globals()[name] = value
        return value
    for relative_module in _PUBLIC_MODULES:
        module = importlib.import_module(relative_module, __name__)
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(f"public export {name!r} has no implementation")


def __dir__() -> list[str]:
    return sorted(set(globals()).union(__all__))
