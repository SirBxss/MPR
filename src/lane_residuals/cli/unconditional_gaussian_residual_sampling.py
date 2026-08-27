"""CLI for the fixed v0.16.1 unconditional-Gaussian A3 sampler."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..workflows.unconditional_gaussian_residual_sampling import (
    run_unconditional_gaussian_residual_sampling,
)

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the predeclared 128-draw v0.16.1 A3 ensemble from the "
            "stored v0.14 all-clean unconditional Gaussian. No planner is run."
        )
    )
    parser.add_argument("dataset_directory", type=Path)
    parser.add_argument("gaussian_directory", type=Path)
    parser.add_argument("development_model", type=Path)
    parser.add_argument("accepted_a2_sample_directory", type=Path)
    parser.add_argument("scenario_archive", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/planner/unconditional_gaussian_samples_v0161"),
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
        summary, status = run_unconditional_gaussian_residual_sampling(
            dataset_directory=arguments.dataset_directory,
            gaussian_directory=arguments.gaussian_directory,
            development_model_path=arguments.development_model,
            accepted_a2_sample_directory=arguments.accepted_a2_sample_directory,
            scenario_archive=arguments.scenario_archive,
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
        "sampled A3: %d sequences x %d draws; planner executed=%s",
        summary["sequence_count"],
        summary["sample_count"],
        summary["planner_executed"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
