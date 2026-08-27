"""CLI for the paired v0.16 temporal-order planner experiment."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..workflows.reference_planner_sensitivity import run_reference_planner_sensitivity

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the A0/A1/A2 v0.16 reference-planner sensitivity experiment")
    parser.add_argument("residual_sample_directory", type=Path)
    parser.add_argument("scenario_archive", type=Path)
    parser.add_argument("--output-directory", type=Path, default=Path("outputs/planner/reference_planner_sensitivity_v016"))
    parser.add_argument("--shuffle-seed", type=int, default=20260827)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        summary, status = run_reference_planner_sensitivity(
            residual_sample_directory=arguments.residual_sample_directory,
            scenario_archive=arguments.scenario_archive,
            output_directory=arguments.output_directory,
            shuffle_seed=arguments.shuffle_seed,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError, np.linalg.LinAlgError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info("evaluated %d sequences x %d paired draws", summary["sequence_count"], summary["sample_count"])
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
