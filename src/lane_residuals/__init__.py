"""Minimal tools for extracting and modelling lane-estimation residuals."""

from .gaussian import GaussianResidualModel, fit_gaussian_residual_model
from .plotting import plot_gaussian_residual_model, plot_path_pair_and_residual
from .residuals import Path2D, residual_matrix, residual_vector

__all__ = [
    "GaussianResidualModel",
    "Path2D",
    "fit_gaussian_residual_model",
    "plot_gaussian_residual_model",
    "plot_path_pair_and_residual",
    "residual_matrix",
    "residual_vector",
]
