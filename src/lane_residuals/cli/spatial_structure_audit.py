"""CLI for the lineage-locked v0.16.2 spatial-structure audit."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..workflows.spatial_structure_audit import run_spatial_structure_audit

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit contemporaneous cross-station covariance and correlation in "
            "the exact accepted A2 and A3 generated residual ensembles."
        )
    )
    parser.add_argument("a2_sample_directory", type=Path)
    parser.add_argument("a3_sample_directory", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/planner/spatial_structure_audit_v0162"),
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
        summary, status = run_spatial_structure_audit(
            arguments.a2_sample_directory,
            arguments.a3_sample_directory,
            arguments.output_directory,
        )
    except (FileNotFoundError, KeyError, OSError, TypeError, ValueError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "audited %d generated profiles per arm across %d sequences",
        summary["generated_profile_count_per_arm"],
        summary["sequence_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
