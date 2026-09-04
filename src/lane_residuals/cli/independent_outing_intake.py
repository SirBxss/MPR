"""CLI for the reviewed v0.17 independent-outing intake and cohort lock."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..io.mcap import McapDependencyError
from ..workflows.independent_outing_intake import run_independent_outing_intake


LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit prospectively declared independent outings and lock an "
            "outcome-blind development/final cohort split."
        )
    )
    parser.add_argument(
        "new_mcap_root",
        type=Path,
        help="root searched recursively for the newly acquired MCAPs",
    )
    parser.add_argument(
        "--acquisition-manifest",
        required=True,
        type=Path,
        help="prospective private v0.17 acquisition manifest",
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="new directory for exactly four private intake outputs",
    )
    parser.add_argument(
        "--prior-successful-lock",
        type=Path,
        help="exact prior successful lock required only for declared supersession",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="console verbosity only",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(message)s",
    )
    try:
        summary, status = run_independent_outing_intake(arguments)
    except (FileNotFoundError, OSError, TypeError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "v0.17 intake: files=%d declared=%d eligible=%d status=%s",
        summary["mcap_file_count"],
        summary["declared_new_outing_count"],
        summary["eligible_new_outing_count"],
        summary["status"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
