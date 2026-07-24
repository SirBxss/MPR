"""Minimal tools for extracting and modelling lane-estimation residuals."""

from .gaussian import GaussianResidualModel, fit_gaussian_residual_model
from .mcap_io import (
    McapDependencyError,
    RoadFrame,
    RoadMessageError,
    RoadSegment,
    load_road_frames,
    road_frame_from_message,
)
from .plotting import (
    plot_gaussian_residual_model,
    plot_mcap_dataset_diagnostics,
    plot_path_pair_and_residual,
)
from .preprocessing import (
    DEFAULT_ESTIMATE_TOPIC,
    DEFAULT_REFERENCE_TOPIC,
    DEFAULT_STATIONS,
    ExtractionReport,
    FrameRejection,
    ResidualDataset,
    build_residual_dataset,
    build_residual_dataset_from_mcap,
    estimate_path_on_reference,
    project_points_to_polyline,
    reference_path_from_segment,
    save_residual_dataset,
    select_ego_segment,
    synchronize_road_frames,
)
from .residuals import Path2D, residual_matrix, residual_vector

__all__ = [
    "DEFAULT_ESTIMATE_TOPIC",
    "DEFAULT_REFERENCE_TOPIC",
    "DEFAULT_STATIONS",
    "ExtractionReport",
    "FrameRejection",
    "GaussianResidualModel",
    "McapDependencyError",
    "Path2D",
    "ResidualDataset",
    "RoadFrame",
    "RoadMessageError",
    "RoadSegment",
    "build_residual_dataset",
    "build_residual_dataset_from_mcap",
    "estimate_path_on_reference",
    "fit_gaussian_residual_model",
    "load_road_frames",
    "plot_gaussian_residual_model",
    "plot_mcap_dataset_diagnostics",
    "plot_path_pair_and_residual",
    "project_points_to_polyline",
    "reference_path_from_segment",
    "residual_matrix",
    "residual_vector",
    "road_frame_from_message",
    "save_residual_dataset",
    "select_ego_segment",
    "synchronize_road_frames",
]
