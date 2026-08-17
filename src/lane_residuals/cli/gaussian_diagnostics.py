"""CLI for v0.6.1 Gaussian adequacy and normality diagnostics."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..workflows.gaussian_diagnostics import run_gaussian_diagnostics

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute leave-one-drive-out Gaussian predictions from an exact "
            "v0.6.0 baseline and export marginal shape, tail, Q–Q, and "
            "multivariate Mahalanobis calibration diagnostics."
        )
    )
    parser.add_argument(
        "gaussian_baseline_directory",
        type=Path,
        help="complete v0.6.0 Gaussian baseline output directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(
            "outputs/diagnostics/modeling/gaussian_adequacy_v061"
        ),
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
        summary, status = run_gaussian_diagnostics(arguments)
    except (FileNotFoundError, OSError, ValueError, ResidualDatasetContractError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "Gaussian adequacy: vectors=%d, dimension=%d, drives=%d",
        summary["vector_count"],
        summary["dimension"],
        summary["drive_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
