"""CLI for the MPR v0.11.0 autoregressive input-output HMM."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..workflows.sequence_aiohmm import run_sequence_aiohmm

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fit and evaluate the fixed-development AIOHMM on the unchanged "
            "v0.9.0 sequence/fold contract. State-count selection is not "
            "performed by this command."
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
        default=Path("outputs/models/aiohmm_sequence_v0110"),
    )
    parser.add_argument(
        "--state-count",
        type=int,
        default=3,
        help="fixed exploratory state count; no held-out state-count search is run",
    )
    parser.add_argument("--restart-count", type=int, default=3)
    parser.add_argument("--maximum-em-iterations", type=int, default=30)
    parser.add_argument("--minimum-em-iterations", type=int, default=5)
    parser.add_argument("--convergence-tolerance", type=float, default=1e-4)
    parser.add_argument("--regression-ridge-penalty", type=float, default=1e-3)
    parser.add_argument(
        "--emission-parameter-pooling-penalty",
        type=float,
        default=10.0,
        help="nonnegative shrinkage of rare-state emission/AR parameters toward the shared AR regression",
    )
    parser.add_argument(
        "--state-covariance-pooling",
        type=float,
        default=0.50,
        help="fraction of each state covariance pooled toward the shared covariance",
    )
    parser.add_argument(
        "--covariance-diagonal-shrinkage", type=float, default=0.15
    )
    parser.add_argument(
        "--covariance-minimum-eigenvalue", type=float, default=1e-5
    )
    parser.add_argument(
        "--minimum-effective-state-observations", type=float, default=10.0
    )
    parser.add_argument(
        "--maximum-absolute-autoregression", type=float, default=0.98
    )
    parser.add_argument("--transition-l2-penalty", type=float, default=1e-3)
    parser.add_argument("--transition-learning-rate", type=float, default=0.03)
    parser.add_argument("--transition-adam-steps", type=int, default=30)
    parser.add_argument(
        "--initial-probability-smoothing", type=float, default=1e-2
    )
    parser.add_argument(
        "--minimum-state-occupancy-fraction", type=float, default=0.01
    )
    parser.add_argument(
        "--initialization-seed",
        type=int,
        default=20260820,
        help="base deterministic EM seed; restarts use a recorded fixed stride",
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
        default=20260820,
        help="base nonnegative sampling seed; fold index is added deterministically",
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
        summary, status = run_sequence_aiohmm(arguments)
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        ResidualDatasetContractError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    metrics = summary["cross_validated_metrics"]
    LOGGER.info(
        "AIOHMM: sequences=%d, frames=%d, drives=%d, states=%d",
        summary["sequence_count"],
        summary["frame_count"],
        summary["drive_count"],
        summary["state_count"],
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
    LOGGER.info(
        "minimum held-out posterior state occupancy=%.6f",
        metrics["minimum_posterior_state_occupancy"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
