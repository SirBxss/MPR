"""CLI adapter for projection-based RLMB reference-alignment validation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError
from ..workflows.alignment import DEFAULT_MAP_TOPIC, run_alignment_audit

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate projection/resampling of road_lane_map_based from the EDP "
            "station-zero point. This is spatial alignment, not explicit ego-motion "
            "compensation or independent physical ground truth."
        )
    )
    parser.add_argument("mcap", type=Path, help="one complete MCAP recording chunk")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/diagnostics/validation/reference_alignment"),
    )
    parser.add_argument(
        "--maximum-pair-delta-ms",
        type=float,
        default=None,
        help=(
            "optional predeclared timestamp gate; the source delta is retained but "
            "is not used numerically by the spatial alignment"
        ),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--map-max-segments", type=int, default=16)
    parser.add_argument("--map-max-junction-gap-m", type=float, default=1.0)
    parser.add_argument(
        "--map-max-junction-heading-deg",
        type=float,
        default=30.0,
    )
    parser.add_argument(
        "--estimate-topic",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    )
    parser.add_argument("--map-topic", default=DEFAULT_MAP_TOPIC)
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
        if not arguments.mcap.is_file():
            raise FileNotFoundError(f"MCAP file not found: {arguments.mcap}")
        summary = run_alignment_audit(arguments)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "aligned complete pairs: H60=%d, H100=%d",
        summary["h60_aligned_complete_pair_count"],
        summary["h100_aligned_complete_pair_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return 0 if summary["h100_aligned_complete_pair_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
