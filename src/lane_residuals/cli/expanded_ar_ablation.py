"""CLI for the v0.15.1 one-state conditional-AR ablation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..workflows.expanded_ar_ablation import run_expanded_ar_ablation
from .expanded_aiohmm import build_expanded_autoregressive_parser

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = build_expanded_autoregressive_parser(
        description=(
            "Evaluate the one-state conditional-AR ablation on the exact v0.14/v0.15 "
            "folds, transforms, hyperparameters, sampling, and metrics."
        ),
        output_directory=Path("outputs/models/one_state_ar_v0151"),
        state_count=1,
        state_help="fixed at one for v0.15.1; other values are rejected",
    )
    parser.add_argument(
        "--aiohmm-directory",
        type=Path,
        required=True,
        help="complete reviewed expanded_aiohmm_v0150 result directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        summary, status = run_expanded_ar_ablation(arguments)
    except (
        ExpandedSequenceContractError,
        FileNotFoundError,
        OSError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    metrics = summary["primary_macro_drive_metrics"]
    gaussian_deltas = summary[
        "one_state_ar_minus_conditional_gaussian_primary_macro_deltas"
    ]
    two_state_deltas = summary[
        "one_state_ar_minus_two_state_aiohmm_primary_macro_deltas"
    ]
    LOGGER.info(
        "v0.15.1 one-state AR: clean groups=%d sequences=%d frames=%d",
        len(summary["primary_clean_drive_ids"]),
        summary["primary_sequence_count"],
        summary["primary_frame_count"],
    )
    LOGGER.info(
        "macro-group RMSE=%.6f m energy=%.6f m sequence-energy=%.6f m lag-error=%.6f",
        metrics["sample_mean_prediction_rmse_m"],
        metrics["mean_energy_score_m"],
        metrics["mean_normalized_sequence_energy_score_m"],
        metrics["median_absolute_lag_one_correlation_error"],
    )
    LOGGER.info(
        "one-state minus Gaussian: sequence-energy=%+.6f m lag-error=%+.6f",
        gaussian_deltas["mean_normalized_sequence_energy_score_m"],
        gaussian_deltas["median_absolute_lag_one_correlation_error"],
    )
    LOGGER.info(
        "one-state minus two-state: sequence-energy=%+.6f m lag-error=%+.6f; %s",
        two_state_deltas["mean_normalized_sequence_energy_score_m"],
        two_state_deltas["median_absolute_lag_one_correlation_error"],
        summary["latent_switching_result_classification"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
