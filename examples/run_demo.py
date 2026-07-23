"""Run a deterministic synthetic check of the residual definition."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lane_residuals import Path2D, plot_path_pair_and_residual, residual_vector


def main() -> None:
    "source_stations = np.linspace(0.0, 50.0, 101)"
    source_stations = np.linspace(0.0, 50.0, 101)
    ground_truth = Path2D(
        s=source_stations,
        x=source_stations,
        y=0.002 * source_stations**2,
    )

    offset = 0.20 + 0.10 * np.sin(source_stations / 12.0)
    normals = ground_truth.unit_left_normals(source_stations)
    ground_truth_points = ground_truth.sample(source_stations)
    estimate_points = ground_truth_points + offset[:, None] * normals
    estimate = Path2D(
        s=source_stations,
        x=estimate_points[:, 0],
        y=estimate_points[:, 1],
    )

    evaluation_stations = np.arange(0.0, 50.1, 5.0)
    residual = residual_vector(ground_truth, estimate, evaluation_stations)
    figure, _ = plot_path_pair_and_residual(
        ground_truth,
        estimate,
        evaluation_stations,
    )

    output_directory = Path(__file__).resolve().parents[1] / "outputs"
    output_directory.mkdir(exist_ok=True)
    output_path = output_directory / "residual_demo.png"
    figure.savefig(output_path, dpi=160)
    plt.close(figure)

    print("Evaluation stations [m]:", evaluation_stations)
    print("Residual vector [m]:", np.round(residual, 4))
    print("Figure written to:", output_path)


if __name__ == "__main__":
    main()
