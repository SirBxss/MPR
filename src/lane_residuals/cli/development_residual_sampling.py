"""CLI for deterministic sampling from the v0.15.4 development model."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..workflows.development_residual_sampling import (
    run_development_residual_sampling,
)

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate free-running physical H100 residual sequences from the "
            "frozen v0.15.4 development model. This command does not run a planner."
        )
    )
    parser.add_argument(
        "development_model",
        type=Path,
        help="v0.15.4 development_residual_model.json",
    )
    parser.add_argument(
        "condition_archive",
        type=Path,
        help=(
            "NPZ with conditions [B,T,6], lengths [B], unique sequence_ids [B], "
            "and the exact feature_names array"
        ),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/planner/residual_samples_v0154"),
        help="new empty residual-sample output directory",
    )
    parser.add_argument("--sample-count", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260826)
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
        summary, status = run_development_residual_sampling(
            model_path=arguments.development_model,
            condition_archive=arguments.condition_archive,
            output_directory=arguments.output_directory,
            sample_count=arguments.sample_count,
            seed=arguments.seed,
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
        "sampled %d residual sequences x %d draws; planner executed=%s",
        summary["sequence_count"],
        summary["sample_count"],
        summary["planner_executed"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
