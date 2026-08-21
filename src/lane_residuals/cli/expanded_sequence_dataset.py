"""CLI for the v0.13 quality-gated expanded sequential dataset."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.expanded_sequence_dataset import DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS
from ..io.expanded_sequence_dataset import ExpandedSequenceContractError
from ..io.mcap import McapDependencyError
from ..io.odometry import DEFAULT_ODOMETRY_TOPIC
from ..workflows.conditional_features import DEFAULT_ESTIMATE_TOPIC
from ..workflows.expanded_sequence_dataset import (
    DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS,
    run_expanded_sequence_dataset,
)


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build v0.13 physical-unit sensor-topology H100 profiles and "
            "quality-gated cross-MCAP sequences. No split selection or model training."
        )
    )
    parser.add_argument("mcap", nargs="+", type=Path)
    parser.add_argument("--alignment-directory", required=True, type=Path)
    parser.add_argument("--topology-audit-directory", required=True, type=Path)
    parser.add_argument("--expected-file-count", required=True, type=int)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument(
        "--maximum-contiguous-gap-ms", type=float,
        default=DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
    )
    parser.add_argument(
        "--maximum-odometry-interpolation-gap-ms", type=float,
        default=DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS,
    )
    parser.add_argument("--max-step-m", type=float, default=.25)
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATE_TOPIC)
    parser.add_argument("--odometry-topic", default=DEFAULT_ODOMETRY_TOPIC)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        summary, status = run_expanded_sequence_dataset(arguments)
    except (
        ExpandedSequenceContractError,
        FileNotFoundError,
        McapDependencyError,
        OSError,
        ValueError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "expanded sequences: profiles=%d sequences=%d immediate-boundaries=%d stitched=%d",
        summary["profile_count"], summary["sequence_count"],
        summary["immediately_eligible_cross_mcap_boundary_candidate_count"],
        summary["stitched_cross_mcap_boundary_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
