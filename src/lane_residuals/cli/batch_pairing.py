"""CLI adapter for the ten-recording pairing workflow."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.batch_pairing import BatchAggregationError
from ..domain.geometry_validation import GeometryValidationError
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError, RoadMessageError
from ..workflows.batch_pairing import run_batch
from ..workflows.pairing import DEFAULT_MAP_TOPIC

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the diagnostic EDP--RLMB pairing audit independently for a "
            "predeclared corpus, then aggregate fixed 0--60 m and 0--100 m cohorts."
        )
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="MCAP files and/or directories scanned recursively for *.mcap",
    )
    parser.add_argument(
        "--drive-map", type=Path, required=True,
        help=(
            "private JSON object mapping every resolved MCAP basename to an exact "
            "drive/session label; output labels are replaced with opaque IDs"
        ),
    )
    parser.add_argument("--expected-file-count", type=int, default=10)
    parser.add_argument(
        "--output-directory", type=Path,
        default=Path("outputs/pairing_batch_v045"),
    )
    parser.add_argument(
        "--max-pairs-per-recording", type=int, default=6,
        help="maximum overlay panels per recording; it never truncates CSV rows",
    )
    parser.add_argument(
        "--maximum-pair-delta-ms", type=float, default=None,
        help="optional predeclared source-timestamp gate; omitted by default",
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--map-max-segments", type=int, default=16)
    parser.add_argument("--map-max-junction-gap-m", type=float, default=1.0)
    parser.add_argument("--map-max-junction-heading-deg", type=float, default=30.0)
    parser.add_argument(
        "--recording-tail-window-s", type=float, default=5.0,
        help=(
            "predeclared final time window marked from the complete estimate-stream "
            "source-time envelope; independent of geometry and disagreement values"
        ),
    )
    parser.add_argument(
        "--primary-tail-threshold-m", type=float, default=None,
        help=(
            "optional predeclared 0--60 m per-pair RMS threshold; when omitted, "
            "outcome-tail flags remain empty"
        ),
    )
    parser.add_argument(
        "--full-tail-threshold-m", type=float, default=None,
        help=(
            "optional predeclared 0--100 m per-pair RMS threshold; when omitted, "
            "outcome-tail flags remain empty"
        ),
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
        summary, status = run_batch(arguments)
    except (
        FileNotFoundError, OSError, ValueError, BatchAggregationError,
        GeometryValidationError, McapDependencyError, RoadMessageError,
    ) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "batch %s: %d/%d recordings succeeded",
        summary["status"], summary["successful_recording_count"],
        summary["resolved_file_count"],
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
