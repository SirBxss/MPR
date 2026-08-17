"""CLI for canonical residual export and Gaussian baseline training."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..workflows.gaussian_baseline import run_gaussian_baseline

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the accepted v0.5.0 complete H100 residual cohort, evaluate "
            "an unconditional Gaussian by held-out physical drive, and fit the "
            "final all-data baseline."
        )
    )
    parser.add_argument(
        "alignment_batch_directory",
        type=Path,
        help="accepted v0.5.0 reference-alignment batch output directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/gaussian_baseline_v060"),
    )
    parser.add_argument(
        "--regularization-m2",
        type=float,
        default=1e-6,
        help="fixed diagonal covariance regularization in square metres",
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
        summary, status = run_gaussian_baseline(arguments)
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        ResidualDatasetContractError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "Gaussian baseline: vectors=%d, dimension=%d, folds=%d",
        summary["final_model_training_vector_count"],
        summary["dimension"],
        summary["evaluation_fold_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
