"""CLI adapter for corpus geometry validation."""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections.abc import Sequence
from pathlib import Path

from ..domain.geometry_validation import GeometryValidationError
from ..workflows.geometry_validation import run_geometry_validation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit estimator availability across a corpus, generate explicitly "
            "labelled spline hypotheses for strict candidates, and compare them "
            "diagnostically with /em/road/ego_lane_path. No residual training "
            "dataset or Gaussian model is produced."
        )
    )
    parser.add_argument(
        "mcap_inputs", nargs="+", type=Path,
        help="MCAP files or directories containing MCAP files.",
    )
    parser.add_argument(
        "--output-directory", type=Path,
        default=Path("outputs") / "mcap_v039_geometry_validation",
    )
    parser.add_argument(
        "--session-map", type=Path,
        help=(
            "Optional JSON object mapping each MCAP basename to a real session "
            "label. Labels are replaced with opaque session IDs in outputs."
        ),
    )
    parser.add_argument(
        "--expected-file-count", type=int, default=10,
        help="Expected corpus size; mismatch makes the corpus incomplete.",
    )
    parser.add_argument(
        "--max-messages-per-topic", type=int,
        help="Diagnostic sampling only; omission performs a complete scan.",
    )
    parser.add_argument(
        "--comparison-max-delta-ms", type=float, default=20.0,
        help="Diagnostic source-time tolerance used for geometry comparison.",
    )
    parser.add_argument(
        "--sync-sensitivity-ms", type=float, nargs="+",
        default=(5.0, 10.0, 20.0, 50.0),
    )
    parser.add_argument("--max-step-m", type=float, default=0.25)
    parser.add_argument("--minimum-common-coverage-m", type=float, default=20.0)
    parser.add_argument(
        "--include-explicit-index-anchor", action="store_true",
        help=(
            "Also evaluate the index anchor, but only when index_0 is explicitly "
            "present. Implicit proto defaults remain blocked."
        ),
    )
    parser.add_argument(
        "--assume-same-frame", action="store_true",
        help=(
            "Explicitly confirm that raw estimate and comparator coordinates may "
            "be compared without fitted alignment."
        ),
    )
    parser.add_argument(
        "--absolute-lateral-rms-tolerance-m", type=float,
        help="Required only to permit a geometrically_preferred label.",
    )
    parser.add_argument(
        "--absolute-heading-p95-tolerance-rad", type=float,
        help="Required only to permit a geometrically_preferred label.",
    )
    parser.add_argument("--max-overlays-per-recording", type=int, default=8)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser


def _validate_arguments(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> None:
    if arguments.expected_file_count < 1:
        parser.error("--expected-file-count must be positive")
    if arguments.max_overlays_per_recording < 0:
        parser.error("--max-overlays-per-recording must be nonnegative")
    if not math.isfinite(arguments.comparison_max_delta_ms) or arguments.comparison_max_delta_ms < 0:
        parser.error("--comparison-max-delta-ms must be finite and nonnegative")
    if not math.isfinite(arguments.max_step_m) or arguments.max_step_m <= 0:
        parser.error("--max-step-m must be finite and positive")
    if not math.isfinite(arguments.minimum_common_coverage_m) or arguments.minimum_common_coverage_m <= 0:
        parser.error("--minimum-common-coverage-m must be finite and positive")
    for value in arguments.sync_sensitivity_ms:
        if not math.isfinite(value) or value < 0:
            parser.error("--sync-sensitivity-ms values must be finite and nonnegative")
    for option, value in (
        ("--absolute-lateral-rms-tolerance-m", arguments.absolute_lateral_rms_tolerance_m),
        ("--absolute-heading-p95-tolerance-rad", arguments.absolute_heading_p95_tolerance_rad),
    ):
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error(f"{option} must be finite and positive")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )
    _validate_arguments(parser, arguments)
    try:
        summary = run_geometry_validation(arguments)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    except (GeometryValidationError,) as error:
        parser.exit(2, f"error while saving validation audit: {error}\n")
    print(f"Semantic validation outputs: {summary['output_directory']}")
    print(
        "Estimate messages audited: "
        f"{summary['decoded_estimate_messages_raw']} raw / "
        f"{summary['decoded_estimate_messages_unique']} unique; "
        f"strict geometry candidates: {summary['candidate_ready_messages']}"
    )
    print(
        f"Semantic decision: {summary['semantic_decision']}. "
        "Training remains prohibited in the geometry-validation command."
    )
    return 0 if summary["corpus_complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
