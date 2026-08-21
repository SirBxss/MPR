"""CLI for v0.13.1 accepted-boundary odometry-context sequences."""

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
)
from ..workflows.expanded_sequence_dataset_v0131 import (
    run_expanded_sequence_dataset_v0131,
)


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build v0.13.1 using accepted previous-MCAP context only for the "
            "frozen 50 ms odometry speed feature. No split or model training."
        )
    )
    parser.add_argument("mcap", nargs="+", type=Path)
    parser.add_argument("--alignment-directory", required=True, type=Path)
    parser.add_argument("--topology-audit-directory", required=True, type=Path)
    parser.add_argument("--v0130-directory", required=True, type=Path)
    parser.add_argument("--expected-file-count", required=True, type=int)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument(
        "--maximum-contiguous-gap-ms",
        type=float,
        default=DEFAULT_MAXIMUM_CONTIGUOUS_GAP_MS,
    )
    parser.add_argument(
        "--maximum-odometry-interpolation-gap-ms",
        type=float,
        default=DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS,
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATE_TOPIC)
    parser.add_argument("--odometry-topic", default=DEFAULT_ODOMETRY_TOPIC)
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
        summary, status = run_expanded_sequence_dataset_v0131(arguments)
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
        "v0.13.1: profiles=%d sequences=%d boundary-features=%d stitched=%d",
        summary["profile_count"],
        summary["sequence_count"],
        summary["boundary_odometry_context"]["restored_feature_count"],
        summary["stitched_cross_mcap_boundary_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
