"""CLI for the v0.15.3 one-state AR-ceiling sensitivity audit."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..workflows.expanded_ar_boundary import (
    run_expanded_ar_boundary_sensitivity,
)
from .expanded_aiohmm import build_expanded_autoregressive_parser

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = build_expanded_autoregressive_parser(
        description=(
            "Audit the reviewed one-state AR model under the fixed 0.98, 0.99, "
            "0.995, and 0.999 stationarity ceilings. No other setting may change."
        ),
        output_directory=Path("outputs/models/one_state_ar_boundary_v0153"),
        state_count=1,
        state_help="fixed at one for the v0.15.3 boundary sensitivity",
        occupancy_help=(
            "retained for exact v0.15.1 configuration parity; inactive with one state"
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
    parser.add_argument(
        "--two-state-convergence-directory",
        type=Path,
        required=True,
        help="complete reviewed two_state_convergence_v0152 result directory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        summary, status = run_expanded_ar_boundary_sensitivity(arguments)
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
        "v0.15.3 AR ceilings=%s; supported=%s; result=%s",
        summary["predeclared_ar_ceilings"],
        summary["development_supported_ar_ceilings"],
        summary["development_result_classification"],
    )
    LOGGER.info(
        "smallest development-supported ceiling=%s; final selection authorized=%s",
        summary["smallest_development_supported_ar_ceiling"],
        summary["final_model_selection_authorized"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
