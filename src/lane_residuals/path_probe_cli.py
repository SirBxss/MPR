"""CLI for evidence-first inspection of direct-path Protobuf messages."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .mcap_io import McapDependencyError, RoadMessageError
from .path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    inspect_protobuf_path_source,
    save_protobuf_path_source_probe,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a direct-path Protobuf schema and observed field presence "
            "without exporting raw numeric payload values."
        )
    )
    parser.add_argument("mcap_file", type=Path)
    parser.add_argument(
        "--topic",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
    )
    parser.add_argument(
        "--expected-schema",
        default=DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    )
    parser.add_argument("--max-messages", type=int, default=20)
    parser.add_argument("--max-schema-depth", type=int, default=6)
    parser.add_argument(
        "--max-repeated-items-per-field",
        type=int,
        default=64,
        help=(
            "Maximum nested message items inspected per repeated field; "
            "container lengths are still reported in full."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs")
        / "mcap_v036"
        / "estimated_drive_paths_structure.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the direct-path structural probe."""

    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        report = inspect_protobuf_path_source(
            arguments.mcap_file,
            topic=arguments.topic,
            expected_schema_name=arguments.expected_schema,
            max_messages=arguments.max_messages,
            max_schema_depth=arguments.max_schema_depth,
            max_repeated_items_per_field=(
                arguments.max_repeated_items_per_field
            ),
        )
        output = save_protobuf_path_source_probe(report, arguments.output)
    except (
        FileNotFoundError,
        ValueError,
        RoadMessageError,
        McapDependencyError,
    ) as error:
        parser.exit(2, f"error: {error}\n")

    print(f"Structural report written to: {output}")
    print(
        "No raw numeric payload values were exported. Review semantic_candidates "
        "before implementing geometry conversion."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
