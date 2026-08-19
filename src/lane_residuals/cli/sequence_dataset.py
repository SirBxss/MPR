"""CLI for the common v0.9.0 sequential dataset."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..domain.sequence_dataset import DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS
from ..workflows.sequence_dataset import run_sequence_dataset

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert the frozen v0.8.0 conditional H100 cohort into the common "
            "gap-aware sequential contract for Gaussian, AIOHMM, and RC-GAN models."
        )
    )
    parser.add_argument(
        "conditional_gaussian_directory",
        type=Path,
        help="complete conditional_gaussian_v080 output directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/datasets/sequential_dataset_v090"),
    )
    parser.add_argument(
        "--maximum-contiguous-gap-ms",
        type=float,
        default=DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
        help=(
            "split a recording before a frame whose source-time gap exceeds "
            "this threshold (default: 200 ms)"
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
        summary, status = run_sequence_dataset(arguments)
    except (FileNotFoundError, OSError, ValueError, ResidualDatasetContractError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "sequential dataset: frames=%d, sequences=%d, recordings=%d, drives=%d",
        summary["retained_frame_count"],
        summary["sequence_count"],
        summary["recording_count"],
        summary["drive_count"],
    )
    LOGGER.info(
        "gap splits=%d, median interval=%.3f ms",
        summary["sequence_count"] - summary["recording_count"],
        summary["median_within_sequence_interval_ms"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
