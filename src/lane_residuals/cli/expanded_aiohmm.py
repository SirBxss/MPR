"""CLI for the v0.15 clean-drive AIOHMM evaluation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..workflows.expanded_aiohmm import run_expanded_aiohmm

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the fixed two-state AIOHMM on the exact v0.14 clean-drive "
            "folds and metrics. Mixed-source fragments remain supplementary."
        )
    )
    parser.add_argument("expanded_sequence_directory", type=Path)
    parser.add_argument(
        "--gaussian-directory",
        type=Path,
        required=True,
        help="complete expanded_gaussian_v0140 result directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/expanded_aiohmm_v0150"),
    )
    parser.add_argument(
        "--state-count",
        type=int,
        default=2,
        help="fixed at two for v0.15; other values are rejected",
    )
    parser.add_argument("--restart-count", type=int, default=3)
    parser.add_argument("--maximum-em-iterations", type=int, default=30)
    parser.add_argument("--minimum-em-iterations", type=int, default=5)
    parser.add_argument("--convergence-tolerance", type=float, default=1e-4)
    parser.add_argument("--regression-ridge-penalty", type=float, default=1e-3)
    parser.add_argument(
        "--emission-parameter-pooling-penalty", type=float, default=10.0
    )
    parser.add_argument("--state-covariance-pooling", type=float, default=0.50)
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
        "--minimum-state-occupancy-fraction",
        type=float,
        default=0.05,
        help="fail a restart whose fitted training occupancy falls below 5%%",
    )
    parser.add_argument(
        "--initialization-seed",
        type=int,
        default=20260823,
        help="deterministic base EM seed; restarts use the recorded fixed stride",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=128,
        help="must match the frozen v0.14 Monte Carlo sample count",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1400,
        help="must match the frozen v0.14 Monte Carlo base seed",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        summary, status = run_expanded_aiohmm(arguments)
    except (
        ExpandedSequenceContractError,
        FileNotFoundError,
        OSError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    metrics = summary["primary_macro_drive_metrics"]
    deltas = summary["aiohmm_minus_conditional_gaussian_primary_macro_deltas"]
    LOGGER.info(
        "v0.15 AIOHMM: clean drives=%d sequences=%d frames=%d states=%d",
        len(summary["primary_clean_drive_ids"]),
        summary["primary_sequence_count"],
        summary["primary_frame_count"],
        summary["state_count"],
    )
    LOGGER.info(
        "macro-drive RMSE=%.6f m energy=%.6f m lag-error=%.6f",
        metrics["sample_mean_prediction_rmse_m"],
        metrics["mean_energy_score_m"],
        metrics["median_absolute_lag_one_correlation_error"],
    )
    LOGGER.info(
        "AIOHMM minus conditional Gaussian: energy=%+.6f m lag-error=%+.6f",
        deltas["mean_energy_score_m"],
        deltas["median_absolute_lag_one_correlation_error"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
