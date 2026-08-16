"""CLI adapter for exact-manifest batch reference-alignment validation."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError
from ..workflows.alignment import DEFAULT_MAP_TOPIC
from ..workflows.alignment_batch import run_alignment_batch

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate projection-based EDP-to-RLMB alignment over the exact "
            "recording manifest. No final residual dataset or model is created."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="MCAP files and/or directories",
    )
    parser.add_argument(
        "--drive-map",
        required=True,
        type=Path,
        help="exact JSON mapping of every MCAP basename to physical session label",
    )
    parser.add_argument("--expected-file-count", type=int, default=10)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/diagnostics/validation/reference_alignment_batch_v050"),
    )
    parser.add_argument("--maximum-pair-delta-ms", type=float, default=None)
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
        summary, status = run_alignment_batch(arguments)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "alignment batch: recordings=%d/%d, H60=%d, H100=%d",
        summary["successful_recording_count"],
        summary["resolved_file_count"],
        summary["h60_aligned_complete_pair_count"],
        summary["h100_aligned_complete_pair_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
