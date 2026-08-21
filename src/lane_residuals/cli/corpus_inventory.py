"""CLI adapter for the expanded-corpus continuity/session audit."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..io.mcap import McapDependencyError
from ..workflows.corpus_inventory import run_corpus_inventory


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory every MCAP recursively and propose fail-closed continuous "
            "blocks without changing the drive map or stitching sequences."
        )
    )
    parser.add_argument("mcap_root", type=Path, help="root directory searched recursively")
    parser.add_argument(
        "--drive-map",
        required=True,
        type=Path,
        help="private exact JSON mapping of every MCAP basename to a drive label",
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="new empty directory for the six private audit outputs",
    )
    parser.add_argument(
        "--maximum-source-gap-ms",
        type=float,
        default=200.0,
        help="fixed v0.12.1 stitch-candidate gate (must remain 200)",
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
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        summary, status = run_corpus_inventory(arguments)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "corpus inventory: files=%d blocks=%d drives=%d stitchable=%d rejected=%d status=%s",
        summary["mcap_file_count"],
        summary["provisional_continuous_block_count"],
        summary["physical_drive_count"],
        summary["stitchable_boundary_count"],
        summary["rejected_boundary_count"],
        summary["status"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
