"""CLI adapter for reference-candidate discovery and validation."""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections.abc import Sequence
from pathlib import Path

from ..domain.reference import DEFAULT_REFERENCE_STATIONS_M
from ..workflows.reference import _validate_stations, run_reference_audit

LOGGER = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and cross-validate lane-reference candidates while keeping "
            "the thesis target fixed as lane-estimation error. No training labels "
            "or statistical model are produced."
        )
    )
    parser.add_argument("mcap_inputs", nargs="+", type=Path)
    parser.add_argument("--session-map", type=Path, required=True)
    parser.add_argument("--signal-config", type=Path, required=True)
    parser.add_argument("--expected-file-count", type=int, default=10)
    parser.add_argument(
        "--output-directory", type=Path,
        default=Path("outputs") / "mcap_v039_reference_audit",
    )
    parser.add_argument(
        "--max-messages-per-topic", type=int,
        help="Diagnostic sampling only; a sampled scan can never support a reference.",
    )
    parser.add_argument("--comparison-max-delta-ms", type=float, default=20.0)
    parser.add_argument("--pose-lsa-max-delta-ms", type=float, default=50.0)
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--maximum-position-step-m", type=float, default=10.0)
    parser.add_argument("--maximum-yaw-step-rad", type=float, default=0.5)
    parser.add_argument("--maximum-inter-sample-gap-s", type=float, default=0.25)
    parser.add_argument("--maximum-stationary-duration-s", type=float, default=2.0)
    parser.add_argument("--stationary-step-threshold-m", type=float, default=0.05)
    parser.add_argument(
        "--max-candidate-median-abs-m", type=float,
        help=(
            "Predeclared acceptance tolerance for the median absolute lateral "
            "difference between direct map lane and pose-plus-offset candidates. "
            "Omitting it keeps the reference unresolved."
        ),
    )
    parser.add_argument(
        "--stations-m", nargs="+", type=float, default=DEFAULT_REFERENCE_STATIONS_M
    )
    parser.add_argument("--field-catalog-samples-per-topic", type=int, default=50)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser


def _validate_arguments(arguments: argparse.Namespace) -> None:
    if arguments.expected_file_count < 1:
        raise ValueError("expected file count must be positive")
    if arguments.max_messages_per_topic is not None and arguments.max_messages_per_topic < 1:
        raise ValueError("max messages per topic must be positive")
    for name in (
        "max_step_m", "maximum_position_step_m", "maximum_yaw_step_rad",
        "maximum_inter_sample_gap_s", "maximum_stationary_duration_s",
    ):
        value = float(getattr(arguments, name))
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name.replace('_', ' ')} must be finite and positive")
    for name in ("comparison_max_delta_ms", "pose_lsa_max_delta_ms"):
        value = float(getattr(arguments, name))
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{name.replace('_', ' ')} must be finite and nonnegative")
    if not math.isfinite(arguments.stationary_step_threshold_m) or arguments.stationary_step_threshold_m < 0.0:
        raise ValueError("stationary step threshold must be finite and nonnegative")
    arguments.stations_m = _validate_stations(arguments.stations_m)
    if arguments.max_candidate_median_abs_m is not None and (
        not math.isfinite(arguments.max_candidate_median_abs_m)
        or arguments.max_candidate_median_abs_m < 0.0
    ):
        raise ValueError("candidate agreement tolerance must be finite and nonnegative")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level), format="%(levelname)s %(message)s"
    )
    try:
        _validate_arguments(arguments)
        summary = run_reference_audit(arguments)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
        return 2
    decision = summary["decision"]
    if decision["status"] == "pseudo_reference_supported":
        LOGGER.info(
            "Reference candidate supported; final residual export remains disabled in v0.3.9."
        )
        return 0
    LOGGER.warning("Reference remains unresolved: %s", ", ".join(decision["blockers"]))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
