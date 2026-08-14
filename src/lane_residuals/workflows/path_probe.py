"""CLI for evidence-first inspection of direct-path Protobuf messages."""

from __future__ import annotations

from ..domain.path_source_probe import (
    inspect_protobuf_path_source,
    save_protobuf_path_source_probe,
)


def run_path_probe(arguments):
    """Inspect and save one direct-path structural report."""
    report = inspect_protobuf_path_source(
        arguments.mcap_file,
        topic=arguments.topic,
        expected_schema_name=arguments.expected_schema,
        max_messages=arguments.max_messages,
        max_schema_depth=arguments.max_schema_depth,
        max_repeated_items_per_field=arguments.max_repeated_items_per_field,
    )
    output = save_protobuf_path_source_probe(report, arguments.output)
    return report, output
