"""Command adapter for the v0.18.0 structural feasibility audit."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from ..workflows.sensor_topology_feasibility import run_sensor_topology_feasibility


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit standalone sensor-topology 100 m structural feasibility; "
            "this command does not construct residuals"
        )
    )
    parser.add_argument("new_mcap_root", type=Path)
    parser.add_argument("--acquisition-manifest", type=Path, required=True)
    parser.add_argument("--preserved-intake-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(arguments.log_level).upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )
    try:
        status = run_sensor_topology_feasibility(
            arguments.new_mcap_root,
            acquisition_manifest=arguments.acquisition_manifest,
            preserved_intake_directory=arguments.preserved_intake_directory,
            output_directory=arguments.output_directory,
        )
    except (OSError, ValueError) as error:
        logging.error("sensor-topology feasibility audit failed: %s", error)
        return 2
    if status == 0:
        logging.info("synchronized 100 m structural candidates were observed")
    else:
        logging.warning("no synchronized 100 m structural candidates were observed")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
