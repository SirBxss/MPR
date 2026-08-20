"""CLI for the v0.10.0 sequence-contract conditional Gaussian baseline."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..workflows.sequence_gaussian import run_sequence_gaussian

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fit and evaluate the conditionally independent Gaussian temporal "
            "null under the common v0.9.0 sequence/fold contract."
        )
    )
    parser.add_argument(
        "sequential_dataset_directory",
        type=Path,
        help="complete sequential_dataset_v090 output directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/gaussian_sequence_v0100"),
    )
    parser.add_argument(
        "--covariance-regularization-standardized2",
        type=float,
        default=1e-6,
        help="positive diagonal covariance variance in standardized target units",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=128,
        help="even Monte Carlo sample count used by common generative metrics",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260819,
        help="base nonnegative random seed; fold index is added deterministically",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        summary, status = run_sequence_gaussian(arguments)
    except (FileNotFoundError, OSError, ValueError, ResidualDatasetContractError) as error:
        LOGGER.error("%s", error)
        return 2
    metrics = summary["cross_validated_metrics"]
    LOGGER.info(
        "sequence Gaussian: sequences=%d, frames=%d, drives=%d",
        summary["sequence_count"],
        summary["frame_count"],
        summary["drive_count"],
    )
    LOGGER.info(
        "held-out sample-mean RMSE=%.6f m, energy score=%.6f m",
        metrics["sample_mean_prediction_rmse_m"],
        metrics["mean_energy_score_m"],
    )
    LOGGER.info(
        "observed/generated median lag-one correlation=%.6f/%.6f",
        metrics["median_observed_lag_one_correlation"],
        metrics["median_generated_lag_one_correlation"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
