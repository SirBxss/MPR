"""CLI for v0.7.1 prediction-time conditional-feature auditing."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.residual_dataset import ResidualDatasetContractError
from ..io.mcap import McapDependencyError, RoadMessageError
from ..io.odometry import DEFAULT_ODOMETRY_TOPIC
from ..io.vehicle import DEFAULT_LONGITUDINAL_SPEED_TOPIC
from ..workflows.conditional_features import (
    DEFAULT_ESTIMATE_TOPIC,
    DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS,
    DEFAULT_MAXIMUM_SPEED_INTERPOLATION_GAP_MS,
    SPEED_SOURCE_CHOICES,
    run_conditional_feature_audit,
)

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit prediction-time speed, EDP curvature, and native-bucket "
            "KEEP_LANE confidence for every canonical v0.6.0 residual vector."
        )
    )
    parser.add_argument(
        "mcap",
        type=Path,
        nargs="+",
        help="MCAP files or directories; basenames must exactly match the manifest",
    )
    parser.add_argument(
        "--alignment-batch-directory",
        type=Path,
        required=True,
        help="accepted v0.5.0 alignment batch that sourced the residual vectors",
    )
    parser.add_argument(
        "--gaussian-baseline-directory",
        type=Path,
        required=True,
        help="complete v0.6.0 Gaussian baseline output directory",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(
            "outputs/diagnostics/modeling/conditional_feature_audit_v071"
        ),
    )
    parser.add_argument(
        "--speed-source",
        choices=SPEED_SOURCE_CHOICES,
        required=True,
        help=(
            "explicit speed contract: direct signed signal, or unsigned rear-axle "
            "odometry displacement over the fixed preceding 50 ms"
        ),
    )
    parser.add_argument(
        "--maximum-speed-interpolation-gap-ms",
        type=float,
        default=DEFAULT_MAXIMUM_SPEED_INTERPOLATION_GAP_MS,
        help="largest valid speed bracket; interpolation never crosses an MCAP",
    )
    parser.add_argument(
        "--maximum-odometry-interpolation-gap-ms",
        type=float,
        default=DEFAULT_MAXIMUM_ODOMETRY_INTERPOLATION_GAP_MS,
        help="largest valid odometry bracket at either 50 ms endpoint",
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATE_TOPIC)
    parser.add_argument(
        "--speed-topic",
        default=DEFAULT_LONGITUDINAL_SPEED_TOPIC,
    )
    parser.add_argument("--odometry-topic", default=DEFAULT_ODOMETRY_TOPIC)
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
        summary, status = run_conditional_feature_audit(arguments)
    except (
        FileNotFoundError,
        McapDependencyError,
        OSError,
        ResidualDatasetContractError,
        RoadMessageError,
        ValueError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "conditional features: ready=%d/%d (%.2f%%)",
        summary["feature_ready_count"],
        summary["residual_vector_count"],
        100.0 * summary["feature_ready_fraction"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
