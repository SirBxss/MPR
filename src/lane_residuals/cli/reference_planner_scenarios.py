"""CLI for building v0.16 clean planner scenario archives."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..workflows.reference_planner_scenarios import run_reference_planner_scenario_build

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build immutable v0.16 planner scenarios")
    parser.add_argument("expanded_dataset_directory", type=Path)
    parser.add_argument("alignment_directory", type=Path)
    parser.add_argument("--output-directory", type=Path, default=Path("outputs/planner/reference_planner_scenarios_v016"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        summary, status = run_reference_planner_scenario_build(
            expanded_dataset_directory=arguments.expanded_dataset_directory,
            alignment_directory=arguments.alignment_directory,
            output_directory=arguments.output_directory,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info("built %d sequences with %d active frames", summary["sequence_count"], summary["active_frame_count"])
    return status


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
