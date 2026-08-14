"""CLI adapter for the direct-path structural probe workflow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ..domain.path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)
from ..io.mcap import McapDependencyError, RoadMessageError
from ..workflows.path_probe import run_path_probe


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect direct-path Protobuf schema/presence and joint per-path "
            "role/error/model structure without exporting numeric payloads."
        )
    )
    parser.add_argument("mcap_file", type=Path)
    parser.add_argument("--topic", default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC)
    parser.add_argument("--expected-schema", default=DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA)
    parser.add_argument("--max-messages", type=int, default=20)
    parser.add_argument("--max-schema-depth", type=int, default=6)
    parser.add_argument(
        "--max-repeated-items-per-field", type=int, default=64,
        help=(
            "Maximum nested message items inspected per repeated field; "
            "container lengths are still reported in full."
        ),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("outputs") / "mcap_v039" / "estimated_drive_paths_joint_audit.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the direct-path structural probe."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        report, output = run_path_probe(arguments)
    except (FileNotFoundError, ValueError, RoadMessageError, McapDependencyError) as error:
        parser.exit(2, f"error: {error}\n")
    joint = report.joint_path_semantics
    summary = dict(joint.summary_counts)
    print(f"Joint semantic audit written to: {output}")
    print(f"Joint audit status: {joint.status}")
    print(
        "Keep-lane/no-error paths: "
        f"{summary['keep_lane_no_error_paths']}; joint audit candidates: "
        f"{summary['joint_audit_candidate_paths']}; converter-safe sampled messages: "
        f"{summary['messages_safe_for_later_conversion']}"
    )
    print(
        "No raw numeric payload values were exported. A joint audit candidate "
        "is not yet permission to implement geometry conversion."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
