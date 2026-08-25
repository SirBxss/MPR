"""CLI for the v0.15.2 two-state AIOHMM convergence audit."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..modeling.aiohmm import (
    ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE,
)
from ..workflows.expanded_aiohmm_convergence import (
    CONVERGENCE_TOLERANCE_PER_FRAME,
    run_expanded_aiohmm_convergence_audit,
)
from .expanded_aiohmm import build_expanded_autoregressive_parser

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = build_expanded_autoregressive_parser(
        description=(
            "Re-fit the reviewed v0.15 two-state AIOHMM with the fixed v0.15.2 "
            "absolute per-frame EM convergence rule."
        ),
        output_directory=Path("outputs/models/two_state_convergence_v0152"),
        state_count=2,
        state_help="fixed at two for the v0.15.2 convergence audit",
        occupancy_help="unchanged fixed 5%% v0.15 occupancy floor",
    )
    parser.set_defaults(
        convergence_tolerance=CONVERGENCE_TOLERANCE_PER_FRAME,
        convergence_criterion=(
            ABSOLUTE_LOG_PROBABILITY_IMPROVEMENT_PER_FRAME_CONVERGENCE
        ),
    )
    parser.add_argument(
        "--aiohmm-directory",
        type=Path,
        required=True,
        help="complete reviewed expanded_aiohmm_v0150 result directory",
    )
    parser.add_argument(
        "--one-state-ar-directory",
        type=Path,
        required=True,
        help="complete reviewed one_state_ar_v0151 result directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        summary, status = run_expanded_aiohmm_convergence_audit(arguments)
    except (
        ExpandedSequenceContractError,
        FileNotFoundError,
        OSError,
        ValueError,
        np.linalg.LinAlgError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    convergence = summary["selected_fit_convergence_comparison"]
    deltas = summary[
        "corrected_two_state_minus_one_state_ar_primary_macro_deltas"
    ]
    LOGGER.info(
        "v0.15.2 convergence audit: selected fits converged=%d/%d",
        convergence["corrected_converged_fit_count"],
        convergence["selected_fit_count"],
    )
    LOGGER.info(
        "added EM iterations: min=%d mean=%.2f max=%d",
        convergence["minimum_added_iteration_count"],
        convergence["mean_added_iteration_count"],
        convergence["maximum_added_iteration_count"],
    )
    LOGGER.info(
        "corrected two-state minus one-state: sequence-energy=%+.6f m "
        "lag-error=%+.6f; result=%s",
        deltas["mean_normalized_sequence_energy_score_m"],
        deltas["median_absolute_lag_one_correlation_error"],
        summary["convergence_audit_result_classification"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
