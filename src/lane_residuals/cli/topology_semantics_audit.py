"""CLI for the complete-corpus EDP topology and alignment-quality audit."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError
from ..workflows.topology_semantics_audit import run_topology_semantics_audit


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only EDP topology semantics and native-alignment quality audit. "
            "Does not change eligibility, stitch MCAPs, export residuals/features, "
            "or train models."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--drive-map", required=True, type=Path)
    parser.add_argument("--corpus-inventory-directory", required=True, type=Path)
    parser.add_argument("--alignment-directory", required=True, type=Path)
    parser.add_argument("--expected-file-count", required=True, type=int)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC)
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
        summary, status = run_topology_semantics_audit(arguments)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "topology audit: messages=%d, transitions=%d, outliers=%d, status=%s",
        summary["edp_message_count"], summary["topology_transition_count"],
        summary["alignment_quality"]["listed_outlier_count"], summary["status"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
