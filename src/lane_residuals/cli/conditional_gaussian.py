"""CLI for the frozen-cohort v0.8.0 conditional Gaussian comparison."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..workflows.conditional_gaussian import run_conditional_gaussian

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the complete v0.7.2 conditional-feature cohort and compare "
            "a linear-mean conditional Gaussian with an unconditional Gaussian "
            "on identical leave-one-physical-drive-out folds."
        )
    )
    parser.add_argument(
        "gaussian_baseline_directory",
        type=Path,
        help="complete v0.6.0 Gaussian baseline output directory",
    )
    parser.add_argument(
        "conditional_feature_directory",
        type=Path,
        help="complete v0.7.2 gap-50 conditional-feature audit directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/conditional_gaussian_v080"),
    )
    parser.add_argument(
        "--covariance-regularization-m2",
        type=float,
        default=1e-6,
        help="fixed diagonal covariance variance added in both models",
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
        summary, status = run_conditional_gaussian(arguments)
    except (FileNotFoundError, OSError, ValueError, ResidualDatasetContractError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "conditional Gaussian: selected=%d, excluded=%d, drives=%d",
        summary["selected_vector_count"],
        summary["excluded_boundary_vector_count"],
        summary["evaluation_fold_count"],
    )
    LOGGER.info(
        "conditional minus unconditional held-out NLL: %.6f",
        summary[
            "conditional_minus_unconditional_mean_joint_negative_log_likelihood"
        ],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
