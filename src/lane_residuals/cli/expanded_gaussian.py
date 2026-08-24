"""CLI for the v0.14 drive-grouped Gaussian re-baseline."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..workflows.expanded_gaussian import run_expanded_gaussian

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate unconditional and six-feature conditional Gaussian nulls "
            "with leave-one-clean-physical-drive-out folds on v0.13.1. Mixed-source "
            "fragments are reported separately and never used for fitting."
        )
    )
    parser.add_argument("expanded_sequence_directory", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/models/expanded_gaussian_v0140"),
    )
    parser.add_argument(
        "--covariance-regularization-standardized2",
        type=float,
        default=1e-6,
    )
    parser.add_argument("--sample-count", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1400)
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
        summary, status = run_expanded_gaussian(arguments)
    except (
        ExpandedSequenceContractError,
        FileNotFoundError,
        OSError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "v0.14 Gaussian: primary drives=%d sequences=%d frames=%d",
        len(summary["primary_clean_drive_ids"]),
        summary["primary_sequence_count"],
        summary["primary_frame_count"],
    )
    for model_name, payload in summary["models"].items():
        metrics = payload["primary_macro_drive_metrics"]
        LOGGER.info(
            "%s macro-drive RMSE=%.6f m energy=%.6f m lag-error=%.6f",
            model_name,
            metrics["sample_mean_prediction_rmse_m"],
            metrics["mean_energy_score_m"],
            metrics["median_absolute_lag_one_correlation_error"],
        )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
