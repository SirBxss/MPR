"""CLI adapter for EstimatedDrivePaths transition diagnostics."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from ..domain.edp_transitions import DEFAULT_EDP_TRANSITION_STATIONS_M, EDP_SPLINE_HYPOTHESES
from ..domain.path_source_probe import DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC
from ..io.mcap import McapDependencyError
from ..workflows.edp_transitions import _validate_arguments, run_edp_transition_audit

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export every EstimatedDrivePaths candidate, detect spline-window "
            "rollovers, and compare retained geometry under both unresolved "
            "curvature hypotheses."
        )
    )
    parser.add_argument("mcap", type=Path, help="one MCAP file to inspect")
    parser.add_argument(
        "--output-directory", type=Path,
        default=Path("outputs/edp_transition_audit"),
    )
    parser.add_argument(
        "--stations-m", nargs="+", type=float,
        default=list(DEFAULT_EDP_TRANSITION_STATIONS_M),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument(
        "--transition-centers", nargs="*", type=int, default=None,
        help=(
            "optional EDP message indices to inspect; when omitted, the largest "
            "non-overlapping curve changes are ranked without a threshold"
        ),
    )
    parser.add_argument("--transition-window-radius", type=int, default=3)
    parser.add_argument("--max-transition-windows", type=int, default=4)
    parser.add_argument(
        "--ranking-hypothesis", choices=EDP_SPLINE_HYPOTHESES,
        default="curvature_rate",
    )
    parser.add_argument("--estimate-topic", default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC)
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
        summary = run_edp_transition_audit(arguments, stations_m=stations_m)
    except (FileNotFoundError, OSError, ValueError, McapDependencyError) as error:
        LOGGER.error("%s", error)
        return 2
    LOGGER.info(
        "exported %d candidates and ranked %d transition windows",
        summary["all_candidate_count"], len(summary["ranked_transition_centers"]),
    )
    LOGGER.info("outputs: %s", arguments.output_directory)
    return 0 if summary["estimate_message_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
