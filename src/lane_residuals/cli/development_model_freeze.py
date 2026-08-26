"""CLI for the v0.15.4 development residual-model freeze."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..workflows.development_model_freeze import run_development_model_freeze

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the reviewed v0.15.3 0.99 one-state model for development "
            "planner experiments. The command never refits or performance-selects."
        )
    )
    parser.add_argument(
        "ar_boundary_directory",
        type=Path,
        help="complete reviewed one_state_ar_boundary_v0153 directory",
    )
    parser.add_argument(
        "--one-state-ar-directory",
        type=Path,
        required=True,
        help="complete reviewed one_state_ar_v0151 reference directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/development_residual_model_v0154"),
        help="new empty v0.15.4 output directory",
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
        summary, status = run_development_model_freeze(
            one_state_ar_directory=arguments.one_state_ar_directory,
            ar_boundary_directory=arguments.ar_boundary_directory,
            output_directory=arguments.output_directory,
        )
    except (
        FileNotFoundError,
        OSError,
        TypeError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "v0.15.4 development model frozen at AR ceiling %.3f; final selection=%s",
        summary["selected_ar_ceiling"],
        summary["final_model_selection_authorized"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
