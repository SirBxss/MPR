"""Residual extraction for aligned two-dimensional path pairs.

The module intentionally handles only the first modelling assumption: points
on the ground-truth and estimated paths are tagged by the same longitudinal
reference coordinate ``s``. Path matching is outside this minimal version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _one_dimensional_finite(values: ArrayLike, *, name: str) -> FloatArray:
    """Return a finite one-dimensional float array or raise ``ValueError``."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


@dataclass(frozen=True)
class Path2D:
    """A 2-D path parameterised by a shared longitudinal reference coordinate.

    ``s`` should identify corresponding locations for the ground-truth and
    estimated paths. It must be strictly increasing, but the two paths may use
    different sampling densities because both are interpolated at the requested
    evaluation stations.
    """

    s: ArrayLike
    x: ArrayLike
    y: ArrayLike

    def __post_init__(self) -> None:
        s = _one_dimensional_finite(self.s, name="s")
        x = _one_dimensional_finite(self.x, name="x")
        y = _one_dimensional_finite(self.y, name="y")

        if len(s) < 2:
            raise ValueError("a path must contain at least two points")
        if not (len(s) == len(x) == len(y)):
            raise ValueError("s, x, and y must have the same length")
        if np.any(np.diff(s) <= 0.0):
            raise ValueError("s must be strictly increasing")

        object.__setattr__(self, "s", s)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)

    def sample(self, stations: ArrayLike) -> FloatArray:
        """Interpolate the path positions at explicit reference stations."""

        stations_array = _evaluation_stations(stations)
        _check_station_coverage(stations_array, self, path_name="path")
        x = np.interp(stations_array, self.s, self.x)
        y = np.interp(stations_array, self.s, self.y)
        return np.column_stack((x, y))

    def unit_left_normals(self, stations: ArrayLike) -> FloatArray:
        """Estimate ground-truth left normals at the requested stations."""

        stations_array = _evaluation_stations(stations)
        _check_station_coverage(stations_array, self, path_name="path")

        edge_order = 2 if len(self.s) >= 3 else 1
        dx_ds = np.gradient(self.x, self.s, edge_order=edge_order)
        dy_ds = np.gradient(self.y, self.s, edge_order=edge_order)
        tangent_x = np.interp(stations_array, self.s, dx_ds)
        tangent_y = np.interp(stations_array, self.s, dy_ds)
        tangent_norm = np.hypot(tangent_x, tangent_y)

        if np.any(tangent_norm <= np.finfo(np.float64).eps):
            raise ValueError("the path tangent is undefined at an evaluation station")

        return np.column_stack((-tangent_y / tangent_norm, tangent_x / tangent_norm))


def _evaluation_stations(stations: ArrayLike) -> FloatArray:
    stations_array = _one_dimensional_finite(stations, name="stations")
    if len(stations_array) == 0:
        raise ValueError("stations must not be empty")
    if np.any(np.diff(stations_array) <= 0.0):
        raise ValueError("stations must be strictly increasing")
    return stations_array


def _check_station_coverage(
    stations: FloatArray,
    path: Path2D,
    *,
    path_name: str,
) -> None:
    tolerance = 1e-12
    if stations[0] < path.s[0] - tolerance or stations[-1] > path.s[-1] + tolerance:
        raise ValueError(
            f"{path_name} does not cover all evaluation stations: "
            f"path range [{path.s[0]}, {path.s[-1]}], "
            f"requested [{stations[0]}, {stations[-1]}]"
        )


def residual_vector(
    ground_truth: Path2D,
    estimate: Path2D,
    stations: ArrayLike,
) -> FloatArray:
    """Calculate one signed lateral residual vector.

    The residual is the position difference, ``estimate - ground_truth``,
    projected onto the ground-truth left unit normal. Positive values are left
    of the ground-truth path with respect to increasing ``s``.
    """

    stations_array = _evaluation_stations(stations)
    _check_station_coverage(stations_array, ground_truth, path_name="ground truth")
    _check_station_coverage(stations_array, estimate, path_name="estimate")

    ground_truth_points = ground_truth.sample(stations_array)
    estimate_points = estimate.sample(stations_array)
    normals = ground_truth.unit_left_normals(stations_array)
    return np.einsum("ij,ij->i", estimate_points - ground_truth_points, normals)


def residual_matrix(
    path_pairs: Iterable[tuple[Path2D, Path2D]],
    stations: ArrayLike,
) -> FloatArray:
    """Stack independent path-pair residual vectors into an ``N x H`` matrix."""

    stations_array = _evaluation_stations(stations)
    residuals = [
        residual_vector(ground_truth, estimate, stations_array)
        for ground_truth, estimate in path_pairs
    ]
    if not residuals:
        raise ValueError("path_pairs must contain at least one pair")
    return np.vstack(residuals)
