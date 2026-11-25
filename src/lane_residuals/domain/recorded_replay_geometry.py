"""Verify the geometry for one recorded planner-replay frame."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .alignment import compare_spatially_aligned_paths, project_point_to_path
from .geometry_validation import GeometryValidationError
from .independent_outing_intake import MAXIMUM_ANCHOR_DISTANCE_M
from .motion import Pose2D
from .pairing import EgoRelativePath
from .residual_dataset import CANONICAL_MODEL_STATIONS_M

_METRE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RecordedReplayGeometry:
    """Nominal points at the residual stations, plus ego-relative initial geometry."""

    reference_points_m: NDArray[np.float64]
    residual_stations_from_ego_m: NDArray[np.float64]
    residual_anchor_station_m: float
    ego_reference_station_m: float
    initial_lateral_error_m: float
    initial_heading_error_rad: float


def check_recorded_replay_geometry(
    estimate: EgoRelativePath,
    reference: EgoRelativePath,
    *,
    ego_pose_in_path_frame: Pose2D,
    archived_residual_m: ArrayLike,
    archived_anchor_station_m: float,
    archived_anchor_distance_m: float,
) -> RecordedReplayGeometry:
    """Reconcile one original H100 row and locate the recorded rear axle.

    The caller supplies the archived estimator and reference pair by exact row
    identity. The caller also verifies that both paths and the recorded rear
    axle pose are expressed in the same physical frame at the evaluated epoch.
    The returned stations retain the original samples and express their
    positions relative to the vehicle's separate reference projection.
    """

    stations = np.asarray(CANONICAL_MODEL_STATIONS_M)
    archived = np.asarray(archived_residual_m, dtype=np.float64)
    if archived.shape != stations.shape or not np.isfinite(archived).all():
        raise GeometryValidationError(
            "replay_archived_residual_invalid",
            "a finite archive residual on all canonical H100 stations is required",
        )

    aligned = compare_spatially_aligned_paths(
        estimate, reference, stations_m=CANONICAL_MODEL_STATIONS_M
    )
    if aligned.anchor_distance_m > MAXIMUM_ANCHOR_DISTANCE_M:
        raise GeometryValidationError(
            "anchor_distance_exceeds_1m_or_invalid",
            "the reproduced anchor exceeds the original extraction limit",
        )
    if not (
        np.isclose(
            aligned.reference_anchor_station_m,
            archived_anchor_station_m,
            atol=_METRE_TOLERANCE,
            rtol=0.0,
        )
        and np.isclose(
            aligned.anchor_distance_m,
            archived_anchor_distance_m,
            atol=_METRE_TOLERANCE,
            rtol=0.0,
        )
        and np.allclose(
            aligned.disagreement.lateral_m, archived, atol=_METRE_TOLERANCE, rtol=0.0
        )
    ):
        raise GeometryValidationError(
            "replay_archive_alignment_mismatch",
            "the anchor and signed profile must reproduce the archived row",
        )

    ego_point = np.array([ego_pose_in_path_frame.x_m, ego_pose_in_path_frame.y_m])
    ego_projection = project_point_to_path(ego_point, reference)
    ego_station = ego_projection.station_m
    if not (
        reference.stations_m[0] + _METRE_TOLERANCE
        < ego_station
        < reference.stations_m[-1] - _METRE_TOLERANCE
    ):
        raise GeometryValidationError(
            "replay_ego_projection_at_reference_endpoint",
            "the initial vehicle position requires an interior reference projection",
        )

    reference_heading = float(
        np.interp(ego_station, reference.stations_m, np.unwrap(reference.heading_rad))
    )
    left_normal = np.array([-np.sin(reference_heading), np.cos(reference_heading)])
    heading_delta = ego_pose_in_path_frame.yaw_rad - reference_heading
    relative_stations = stations + (aligned.reference_anchor_station_m - ego_station)
    relative_stations.setflags(write=False)
    return RecordedReplayGeometry(
        reference_points_m=aligned.reference_points_m,
        residual_stations_from_ego_m=relative_stations,
        residual_anchor_station_m=aligned.reference_anchor_station_m,
        ego_reference_station_m=ego_station,
        initial_lateral_error_m=float((ego_point - ego_projection.point_m) @ left_normal),
        initial_heading_error_rad=float((heading_delta + np.pi) % (2.0 * np.pi) - np.pi),
    )
