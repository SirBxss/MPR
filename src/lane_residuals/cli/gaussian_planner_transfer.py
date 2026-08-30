"""CLI for the predeclared v0.16.1 A3 planner-transfer experiment."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..workflows.gaussian_planner_transfer import run_gaussian_planner_transfer

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute only the v0.16.1 unconditional-Gaussian A3 arm and compare "
            "it with immutable accepted v0.16 A1/A2 metrics."
        )
    )
    parser.add_argument("gaussian_sample_directory", type=Path)
    parser.add_argument("scenario_archive", type=Path)
    parser.add_argument("accepted_v016_sensitivity_directory", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/planner/gaussian_planner_transfer_v0161"),
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
        summary, status = run_gaussian_planner_transfer(
            gaussian_sample_directory=arguments.gaussian_sample_directory,
            scenario_archive=arguments.scenario_archive,
            accepted_v016_sensitivity_directory=(
                arguments.accepted_v016_sensitivity_directory
            ),
            output_directory=arguments.output_directory,
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "evaluated A3 over %d sequences x %d draws: %s",
        summary["sequence_count"],
        summary["sample_count_per_arm"],
        summary["overall_decision"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
