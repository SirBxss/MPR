"""Expanded-corpus MCAP inventory and fail-closed continuity workflow."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from ..domain.corpus_inventory import (
    MAXIMUM_STITCH_SOURCE_GAP_NS,
    McapInventoryRecord,
    assign_duplicate_evidence,
    chronological_records,
    continuity_edges,
    exact_drive_map_coverage,
    proposed_session_groups,
)
from ..io.corpus_inventory import DEFAULT_REQUIRED_TOPICS, inspect_mcap_for_inventory
from ..io.reports import write_csv_rows, write_strict_json
from ..visualization.corpus_inventory import plot_corpus_inventory


INVENTORY_FIELDS = (
    "recording_id",
    "drive_id",
    "relative_path_private",
    "mcap_basename_private",
    "file_size_bytes",
    "sha256",
    "drive_map_covered",
    "readable",
    "empty",
    "duplicate_of_recording_id",
    "usable",
    "chronological_index_within_drive",
    "filename_start_hint_private",
    "filename_end_hint_private",
    "filename_duration_ms",
    "mcap_identifier_hint",
    "internal_start_log_time_ns_private",
    "internal_end_log_time_ns_private",
    "internal_duration_ms",
    "first_estimate_source_time_ns_private",
    "last_estimate_source_time_ns_private",
    "estimate_source_duration_ms",
    "estimate_source_timestamp_count",
    "estimate_missing_source_timestamp_count",
    "estimate_source_timestamps_strictly_increasing",
    "required_topics_schemas_compatible",
    "filename_internal_time_disagreement",
    "filename_order_disagrees_with_internal_order",
    "failure_codes",
    "exclusion_codes",
)

TOPIC_FIELDS = (
    "recording_id",
    "drive_id",
    "mcap_basename_private",
    "topic_role",
    "topic",
    "present",
    "message_count",
    "expected_schema_name",
    "schema_names",
    "schema_encodings",
    "message_encodings",
    "schema_compatible",
    "failure_codes",
)

CONTINUITY_FIELDS = (
    "drive_id",
    "left_recording_id",
    "right_recording_id",
    "left_mcap_basename_private",
    "right_mcap_basename_private",
    "internal_log_gap_ms",
    "relevant_source_gap_ms",
    "filename_gap_ms",
    "filename_internal_gap_disagreement",
    "identifier_delta",
    "identifier_discontinuity",
    "same_drive_label",
    "internal_log_times_compatible",
    "relevant_source_timestamps_strictly_increasing",
    "source_gap_within_200_ms",
    "required_topics_schemas_compatible",
    "overlap_detected",
    "timestamp_reset_detected",
    "pair_index_boundary_state",
    "stitchable",
    "rejection_codes",
)


def discover_mcaps(root: Path) -> tuple[Path, ...]:
    """Recursively discover every case-insensitive ``.mcap`` file."""

    source = root.expanduser()
    if not source.exists():
        raise FileNotFoundError(f"MCAP root not found: {source}")
    if not source.is_dir():
        raise ValueError(f"MCAP root must be a directory: {source}")
    resolved_root = source.resolve()
    files = sorted(
        (
            item.resolve()
            for item in resolved_root.rglob("*")
            if item.is_file() and item.suffix.lower() == ".mcap"
        ),
        key=lambda item: str(item.relative_to(resolved_root)),
    )
    if not files:
        raise ValueError(f"no MCAP files found recursively under {source}")
    return tuple(files)


def load_drive_map_pairs(path: Path) -> tuple[tuple[str, str], ...]:
    """Load a flat JSON object while preserving duplicate keys for validation."""

    if not path.is_file():
        raise FileNotFoundError(f"drive map not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, object_pairs_hook=lambda pairs: pairs)
    if not isinstance(payload, list) or any(
        not isinstance(item, tuple) or len(item) != 2 for item in payload
    ):
        raise ValueError("drive map must be a flat JSON object of basename: label")
    return tuple((key, value) for key, value in payload)


def _ensure_empty_output(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"output path exists and is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"output directory is not empty: {path}; use a new directory")
    path.mkdir(parents=True, exist_ok=True)


def _join(values: Sequence[object]) -> str:
    return ";".join(str(value) for value in values)


def _exclusion_codes(record: McapInventoryRecord) -> tuple[str, ...]:
    if record.usable:
        return ()
    codes = [
        code
        for code in record.failure_codes
        if code != "filename_internal_duration_disagreement"
    ]
    if record.drive_id is None:
        codes.append("drive_map_missing_or_ambiguous")
    if record.duplicate_of_recording_id is not None:
        codes.append("duplicate_content")
    if not record.usable and not codes:
        codes.append("file_not_usable")
    return tuple(sorted(set(codes)))


def _inventory_row(record: McapInventoryRecord) -> dict[str, Any]:
    return {
        "recording_id": record.recording_id,
        "drive_id": record.drive_id,
        "relative_path_private": record.relative_path,
        "mcap_basename_private": record.basename,
        "file_size_bytes": record.file_size_bytes,
        "sha256": record.sha256,
        "drive_map_covered": record.drive_id is not None,
        "readable": record.readable,
        "empty": record.empty,
        "duplicate_of_recording_id": record.duplicate_of_recording_id,
        "usable": record.usable,
        "chronological_index_within_drive": record.chronological_index_within_drive,
        "filename_start_hint_private": record.filename_start,
        "filename_end_hint_private": record.filename_end,
        "filename_duration_ms": record.filename_duration_ms,
        "mcap_identifier_hint": record.mcap_identifier,
        "internal_start_log_time_ns_private": record.internal_start_log_time_ns,
        "internal_end_log_time_ns_private": record.internal_end_log_time_ns,
        "internal_duration_ms": (
            None if record.internal_duration_ns is None else record.internal_duration_ns / 1e6
        ),
        "first_estimate_source_time_ns_private": record.first_estimate_source_time_ns,
        "last_estimate_source_time_ns_private": record.last_estimate_source_time_ns,
        "estimate_source_duration_ms": (
            None if record.relevant_duration_ns is None else record.relevant_duration_ns / 1e6
        ),
        "estimate_source_timestamp_count": record.estimate_source_timestamp_count,
        "estimate_missing_source_timestamp_count": record.estimate_missing_source_timestamp_count,
        "estimate_source_timestamps_strictly_increasing": (
            record.estimate_source_timestamps_strictly_increasing
        ),
        "required_topics_schemas_compatible": (
            record.required_topics_and_schemas_compatible
        ),
        "filename_internal_time_disagreement": record.filename_internal_time_disagreement,
        "filename_order_disagrees_with_internal_order": (
            record.filename_order_disagrees_with_internal_order
        ),
        "failure_codes": _join(record.failure_codes),
        "exclusion_codes": _join(_exclusion_codes(record)),
    }


def _topic_rows(records: Sequence[McapInventoryRecord]) -> list[dict[str, Any]]:
    return [
        {
            "recording_id": record.recording_id,
            "drive_id": record.drive_id,
            "mcap_basename_private": record.basename,
            "topic_role": topic.role,
            "topic": topic.topic,
            "present": topic.present,
            "message_count": topic.message_count,
            "expected_schema_name": topic.expected_schema_name,
            "schema_names": _join(topic.schema_names),
            "schema_encodings": _join(topic.schema_encodings),
            "message_encodings": _join(topic.message_encodings),
            "schema_compatible": topic.compatible,
            "failure_codes": _join(topic.failure_codes),
        }
        for record in records
        for topic in sorted(record.topics, key=lambda item: item.role)
    ]


def _edge_row(edge: Any) -> dict[str, Any]:
    return {
        "drive_id": edge.drive_id,
        "left_recording_id": edge.left_recording_id,
        "right_recording_id": edge.right_recording_id,
        "left_mcap_basename_private": edge.left_basename,
        "right_mcap_basename_private": edge.right_basename,
        "internal_log_gap_ms": (
            None if edge.internal_log_gap_ns is None else edge.internal_log_gap_ns / 1e6
        ),
        "relevant_source_gap_ms": (
            None if edge.relevant_source_gap_ns is None else edge.relevant_source_gap_ns / 1e6
        ),
        "filename_gap_ms": edge.filename_gap_ms,
        "filename_internal_gap_disagreement": edge.filename_internal_gap_disagreement,
        "identifier_delta": edge.identifier_delta,
        "identifier_discontinuity": edge.identifier_discontinuity,
        "same_drive_label": edge.same_drive_label,
        "internal_log_times_compatible": edge.internal_log_times_compatible,
        "relevant_source_timestamps_strictly_increasing": (
            edge.relevant_source_timestamps_strictly_increasing
        ),
        "source_gap_within_200_ms": edge.source_gap_within_limit,
        "required_topics_schemas_compatible": edge.required_topics_schemas_compatible,
        "overlap_detected": edge.overlap_detected,
        "timestamp_reset_detected": edge.timestamp_reset_detected,
        "pair_index_boundary_state": edge.pair_index_boundary_state,
        "stitchable": edge.stitchable,
        "rejection_codes": _join(edge.rejection_codes),
    }


def run_corpus_inventory(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Inventory the full corpus and emit deterministic continuity evidence."""

    if arguments.maximum_source_gap_ms < 0:
        raise ValueError("maximum-source-gap-ms must be nonnegative")
    maximum_gap_ns = int(round(arguments.maximum_source_gap_ms * 1_000_000.0))
    if maximum_gap_ns != MAXIMUM_STITCH_SOURCE_GAP_NS:
        raise ValueError("the v0.12.0 audit contract fixes maximum-source-gap-ms at 200")

    root = arguments.mcap_root.resolve()
    files = discover_mcaps(root)
    manifest_pairs = load_drive_map_pairs(arguments.drive_map)
    assignments, coverage_issues = exact_drive_map_coverage(
        [path.name for path in files], manifest_pairs
    )
    coverage_exact = not any(coverage_issues.values())
    labels = sorted(set(assignments.values()))
    opaque_ids = {label: f"drive_{index:03d}" for index, label in enumerate(labels, 1)}
    recording_ids = {
        path: f"recording_{index:03d}" for index, path in enumerate(files, 1)
    }

    _ensure_empty_output(arguments.output_directory)
    inspected = [
        inspect_mcap_for_inventory(
            path,
            root=root,
            recording_id=recording_ids[path],
            drive_id=(opaque_ids[assignments[path.name]] if path.name in assignments else None),
        )
        for path in files
    ]
    records = chronological_records(assign_duplicate_evidence(inspected))
    edges = continuity_edges(records, maximum_source_gap_ns=maximum_gap_ns)
    groups = proposed_session_groups(records, edges)

    write_csv_rows(
        arguments.output_directory / "mcap_inventory.csv",
        INVENTORY_FIELDS,
        (_inventory_row(record) for record in records),
    )
    write_csv_rows(
        arguments.output_directory / "topic_compatibility.csv",
        TOPIC_FIELDS,
        _topic_rows(records),
    )
    write_csv_rows(
        arguments.output_directory / "recording_continuity.csv",
        CONTINUITY_FIELDS,
        (_edge_row(edge) for edge in edges),
    )

    exclusions = [
        {
            "recording_id": record.recording_id,
            "drive_id": record.drive_id,
            "mcap_basename_private": record.basename,
            "exclusion_codes": list(_exclusion_codes(record)),
        }
        for record in records
        if not record.usable
    ]
    group_payload = {
        "version": "0.12.1",
        "purpose": "proposed_verified_cross_mcap_continuous_blocks",
        "drive_map_modified": False,
        "cross_mcap_sequence_stitching_performed": False,
        "original_recording_id_preserved": True,
        "maximum_relevant_source_time_gap_ms": arguments.maximum_source_gap_ms,
        "groups": [
            {
                "block_id": group.block_id,
                "drive_id": group.drive_id,
                "recording_ids": list(group.recording_ids),
                "mcap_basenames_private": list(group.mcap_basenames),
                "first_estimate_source_time_ns_private": group.first_estimate_source_time_ns,
                "last_estimate_source_time_ns_private": group.last_estimate_source_time_ns,
                "usable_duration_s": group.usable_duration_ns / 1e9,
            }
            for group in groups
        ],
        "file_exclusions": exclusions,
        "drive_map_coverage_failures": {
            key: list(value) for key, value in coverage_issues.items()
        },
    }
    write_strict_json(
        arguments.output_directory / "proposed_session_groups.json", group_payload
    )

    duplicate_count = sum(record.duplicate_of_recording_id is not None for record in records)
    unreadable_count = sum(not record.readable for record in records)
    required_failure_files = sum(
        not record.required_topics_and_schemas_compatible for record in records
    )
    required_failure_topics = sum(
        not topic.compatible for record in records for topic in record.topics
    )
    unusable_count = sum(not record.usable for record in records)
    status = "complete" if coverage_exact and unusable_count == 0 else "incomplete"
    summary: dict[str, Any] = {
        "version": "0.12.1",
        "status": status,
        "purpose": "expanded_corpus_continuity_and_session_audit",
        "mcap_file_count": len(records),
        "provisional_continuous_block_count": len(groups),
        "physical_drive_count": len(opaque_ids),
        "total_duration_s": sum(
            max(record.internal_duration_ns or 0, 0) for record in records if record.readable
        )
        / 1e9,
        "usable_duration_s": sum(
            max(record.internal_duration_ns or 0, 0) for record in records if record.usable
        )
        / 1e9,
        "stitchable_boundary_count": sum(edge.stitchable for edge in edges),
        "rejected_boundary_count": sum(not edge.stitchable for edge in edges),
        "duplicate_count": duplicate_count,
        "unreadable_file_count": unreadable_count,
        "empty_file_count": sum(record.empty for record in records),
        "required_topic_schema_failure_file_count": required_failure_files,
        "required_topic_schema_failure_count": required_failure_topics,
        "unusable_file_count": unusable_count,
        "exact_drive_map_coverage": coverage_exact,
        "drive_map_coverage_failures": {
            key: list(value) for key, value in coverage_issues.items()
        },
        "chronological_sort_basis": (
            "explicit drive label, then first relevant estimate source time, then "
            "internal MCAP start time; filename is tie-breaker only"
        ),
        "continuity_gate": {
            "same_explicit_drive_label_required": True,
            "next_internal_start_greater_than_or_equal_previous_internal_end_required": True,
            "strictly_increasing_relevant_source_timestamps_required": True,
            "maximum_relevant_source_time_gap_ms": arguments.maximum_source_gap_ms,
            "required_topic_schema_compatibility_required": True,
            "mcap_identifier_continuity_required": False,
            "recording_local_pair_index_continuity_required": False,
        },
        "filename_times_are_diagnostic_hints_only": True,
        "drive_identity_inferred_from_filename_or_identifier": False,
        "private_drive_map_modified": False,
        "cross_mcap_sequence_stitching_performed": False,
        "accepted_v0_5_native_alignment_target_changed": False,
        "delta_t_added_as_model_input": False,
        "outputs_contain_private_metadata": True,
        "next_step": (
            "Run the accepted v0.5.2 exact-manifest native spatial projection-"
            "alignment validation; do not stitch sequences or apply odometry "
            "motion compensation."
            if status == "complete"
            else "Review all exclusions and complete the exact private drive map "
            "before any alignment or sequence-contract work."
        ),
    }
    write_strict_json(
        arguments.output_directory / "corpus_inventory_summary.json", summary
    )
    plot_corpus_inventory(
        records,
        edges,
        arguments.output_directory / "corpus_inventory_diagnostics.png",
    )
    return summary, 0 if status == "complete" else 3


__all__ = [
    "CONTINUITY_FIELDS",
    "INVENTORY_FIELDS",
    "TOPIC_FIELDS",
    "discover_mcaps",
    "load_drive_map_pairs",
    "run_corpus_inventory",
]
