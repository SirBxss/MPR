"""CLI adapter for the single-recording pairing workflow."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.pairing import DEFAULT_PAIRING_STATIONS_M
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError
from ..workflows.pairing import DEFAULT_MAP_TOPIC, _validate_arguments, run_pairing_audit

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit temporal and geometric pairing between EstimatedDrivePaths and "
            "road_lane_map_based without exporting thesis residual labels."
        )
    )
    parser.add_argument("mcap", type=Path, help="one MCAP file to inspect")
    parser.add_argument(
        "--output-directory", type=Path, default=Path("outputs/pairing_audit")
    )
    parser.add_argument(
        "--max-pairs", type=int, default=20,
        help="maximum number of evenly distributed diagnostic-ready pairs to plot",
    )
    parser.add_argument(
        "--maximum-pair-delta-ms", type=float, default=None,
        help=(
            "optional predeclared timestamp gate; omitted by default because no "
            "production synchronization tolerance has been proven"
        ),
    )
    parser.add_argument(
        "--stations-m", nargs="+", type=float,
        default=list(DEFAULT_PAIRING_STATIONS_M),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument(
        "--map-max-segments", type=int, default=16,
        help="maximum number of explicit RLMB successor segments to inspect",
    )
    parser.add_argument(
        "--map-max-junction-gap-m", type=float, default=1.0,
        help="largest accepted endpoint gap when joining explicit successors",
    )
    parser.add_argument(
        "--map-max-junction-heading-deg", type=float, default=30.0,
        help="largest accepted tangent discontinuity at an RLMB junction",
    )
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC)
    parser.add_argument("--map-topic", default=DEFAULT_MAP_TOPIC)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        stations_m = _validate_arguments(arguments)
        if not arguments.mcap.is_file():
            raise FileNotFoundError(f"MCAP file not found: {arguments.mcap}")
        summary = run_pairing_audit(arguments, stations_m=stations_m)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "inspected %d pairs; %d have complete diagnostic station coverage",
        summary["inspected_pair_count"], summary["diagnostic_ready_pair_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return 0 if summary["inspected_pair_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
