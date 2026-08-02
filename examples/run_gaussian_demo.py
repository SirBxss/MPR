"""Fit and inspect the unconditional Gaussian on controlled residual vectors."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from lane_residuals import (
    fit_gaussian_residual_model,
    plot_gaussian_residual_model,
)


def main() -> None:
    rng = np.random.default_rng(21)
    stations = np.arange(0.0, 50.1, 5.0)

    # Known data-generating distribution used only to verify the implementation.
    true_mean = 0.03 + 0.002 * stations
    true_standard_deviation = 0.06 + 0.0015 * stations
    distance = np.abs(stations[:, None] - stations[None, :])
    true_correlation = np.exp(-distance / 15.0)
    true_covariance = (
        np.outer(true_standard_deviation, true_standard_deviation)
        * true_correlation
    )

    training_residuals = rng.multivariate_normal(
        true_mean,
        true_covariance,
        size=600,
    )
    test_residuals = rng.multivariate_normal(
        true_mean,
        true_covariance,
        size=200,
    )

    model = fit_gaussian_residual_model(
        training_residuals,
        regularization=1e-8,
    )
    generated_residuals = model.sample(5, rng=np.random.default_rng(22))
    figure, _ = plot_gaussian_residual_model(
        model,
        stations,
        observed_residuals=training_residuals,
    )

    output_directory = Path(__file__).resolve().parents[1] / "outputs"
    output_directory.mkdir(exist_ok=True)
    output_path = output_directory / "gaussian_demo.png"
    figure.savefig(output_path, dpi=160)
    plt.close(figure)

    mean_rmse = np.sqrt(np.mean((model.mean - true_mean) ** 2))
    print("Training matrix shape:       ", training_residuals.shape)
    print("Test matrix shape:           ", test_residuals.shape)
    print("Learned mean [m]:            ", np.round(model.mean, 4))
    print("Mean recovery RMSE [m]:      ", round(float(mean_rmse), 6))
    print(
        "Test negative log-likelihood:",
        round(model.negative_log_likelihood(test_residuals), 4),
    )
    print("Generated matrix shape:      ", generated_residuals.shape)
    print("Figure written to:           ", output_path)


if __name__ == "__main__":
    main()
