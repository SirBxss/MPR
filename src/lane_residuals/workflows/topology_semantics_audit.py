"""Complete-corpus read-only EDP topology and alignment-quality audit."""

from __future__ import annotations

import argparse
import json
import logging
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.geometry_validation import _schema_fingerprint
from ..domain.path_source_probe import (
    DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
    DEFAULT_ESTIMATED_DRIVE_PATHS_TOPIC,
)
from ..domain.topology_semantics import (
    decode_topology_message,
    numeric_summary,
    stable_counts,
    topology_interpretation,
)
from ..io.mcap import iter_decoded_mcap_messages
from ..io.reports import write_csv_rows, write_strict_json
from ..io.topology_semantics import (
    INVENTORY_LINEAGE_FILES,
    copy_inventory_lineage,
    read_csv_rows,
    sha256_file,
    validate_alignment_lineage,
    validate_inventory_lineage,
)
from ..visualization.topology_semantics import plot_topology_quality_diagnostic
from .batch_pairing import _resolve_mcaps
from .projection_alignment_batch import _exact_drive_assignments


LOGGER = logging.getLogger(__name__)
VERSION = "0.12.2"
PURPOSE = "complete_corpus_edp_topology_semantics_alignment_quality_audit"
OUTLIER_DISTANCE_M = 1.0
SEMANTIC_METADATA_REVISION = "rlmb_independence_explicitly_unknown"
DOWNSTREAM_MODELING_CONSTRAINTS = (
    "sensor_topology_source_required_by_existing_alignment_contract",
    "independence_from_rlmb_unknown",
    "alignment_quality_eligibility_not_changed_by_read_only_audit",
)

MESSAGE_FIELDS = (
    "recording_id", "drive_id", "mcap_basename_private", "message_index",
    "log_time_ns_private", "publish_time_ns_private", "source_time_ns_private",
    "schema_fingerprint", "topology_field_number", "topology_enum_type",
    "topology_wire_present", "topology_wire_value", "topology_wire_occurrence_count",
    "topology_decoded_value", "topology_source_name", "topology_presence_evidence",
    "topology_wire_decode_consistent", "estimator_state", "conversion_state",
    "total_drive_path_count", "selected_drive_path_count",
    "selected_drive_path_indices_json", "selected_drive_path_index",
    "mutual_nearest_pair_present", "pair_index", "map_message_index",
    "source_delta_ms", "absolute_source_delta_ms", "pair_state", "failure_code",
    "estimate_geometry_state", "estimate_geometry_failure_code",
    "map_geometry_state", "map_geometry_failure_code", "anchor_distance_m",
    "anchor_heading_delta_rad", "aligned_h100_residual_rms_m",
    "h60_aligned_eligible", "h100_aligned_eligible",
)

SUMMARY_FIELDS = (
    "recording_id", "drive_id", "mcap_basename_private", "recording_count",
    "message_count", "paired_message_count", "topology_source_counts_json",
    "estimator_state_counts_json", "selected_drive_path_count_counts_json",
    "selected_drive_path_index_counts_json", "estimate_geometry_state_counts_json",
    "estimate_failure_code_counts_json", "map_geometry_state_counts_json",
    "map_failure_code_counts_json", "h60_eligibility_counts_json",
    "h100_eligibility_counts_json", "source_delta_count", "source_delta_min",
    "source_delta_q05", "source_delta_q25", "source_delta_q50", "source_delta_q75",
    "source_delta_q95", "source_delta_max", "topology_transition_count",
    "cross_mcap_topology_transition_count",
)

TRANSITION_FIELDS = (
    "drive_id", "edge_scope", "left_recording_id", "right_recording_id",
    "left_mcap_basename_private", "right_mcap_basename_private",
    "left_message_index", "right_message_index", "left_source_time_ns_private",
    "right_source_time_ns_private", "source_time_gap_ms", "left_topology_value",
    "right_topology_value", "left_topology_name", "right_topology_name",
    "topology_source_changed", "within_physical_session", "boundary_stitchable",
)

OUTLIER_FIELDS = (
    "recording_id", "drive_id", "mcap_basename_private", "message_index",
    "pair_index", "topology_decoded_value", "topology_source_name",
    "source_delta_ms", "anchor_distance_m", "anchor_heading_delta_rad",
    "aligned_h100_residual_rms_m", "h60_aligned_eligible", "h100_aligned_eligible",
    "audit_listing_threshold_m", "eligibility_changed_by_audit",
)


def _ensure_empty(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"output directory must be new and empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1"}


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _summary_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    recording_id: str,
    drive_id: str,
    basename: str,
    recording_count: int,
    transitions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_stats = numeric_summary([row.get("source_delta_ms") for row in rows])
    return {
        "recording_id": recording_id,
        "drive_id": drive_id,
        "mcap_basename_private": basename,
        "recording_count": recording_count,
        "message_count": len(rows),
        "paired_message_count": sum(_bool(row.get("mutual_nearest_pair_present")) for row in rows),
        "topology_source_counts_json": stable_counts([row.get("topology_source_name") for row in rows]),
        "estimator_state_counts_json": stable_counts([row.get("estimator_state") for row in rows]),
        "selected_drive_path_count_counts_json": stable_counts([row.get("selected_drive_path_count") for row in rows]),
        "selected_drive_path_index_counts_json": stable_counts([row.get("selected_drive_path_index") for row in rows]),
        "estimate_geometry_state_counts_json": stable_counts([row.get("estimate_geometry_state") for row in rows]),
        "estimate_failure_code_counts_json": stable_counts([row.get("estimate_geometry_failure_code") for row in rows]),
        "map_geometry_state_counts_json": stable_counts([row.get("map_geometry_state") for row in rows]),
        "map_failure_code_counts_json": stable_counts([row.get("map_geometry_failure_code") for row in rows]),
        "h60_eligibility_counts_json": stable_counts([row.get("h60_aligned_eligible") for row in rows]),
        "h100_eligibility_counts_json": stable_counts([row.get("h100_aligned_eligible") for row in rows]),
        **{f"source_delta_{key}": value for key, value in source_stats.items()},
        "topology_transition_count": sum(_bool(row["topology_source_changed"]) for row in transitions),
        "cross_mcap_topology_transition_count": sum(
            row["edge_scope"] == "cross_mcap_boundary" and _bool(row["topology_source_changed"])
            for row in transitions
        ),
    }


def _transition(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    edge_scope: str,
    boundary_stitchable: bool | None,
) -> dict[str, Any]:
    left_time, right_time = left.get("source_time_ns_private"), right.get("source_time_ns_private")
    gap = None if left_time in {None, ""} or right_time in {None, ""} else (int(right_time) - int(left_time)) / 1e6
    return {
        "drive_id": left["drive_id"], "edge_scope": edge_scope,
        "left_recording_id": left["recording_id"], "right_recording_id": right["recording_id"],
        "left_mcap_basename_private": left["mcap_basename_private"],
        "right_mcap_basename_private": right["mcap_basename_private"],
        "left_message_index": left["message_index"], "right_message_index": right["message_index"],
        "left_source_time_ns_private": left_time, "right_source_time_ns_private": right_time,
        "source_time_gap_ms": gap, "left_topology_value": left["topology_decoded_value"],
        "right_topology_value": right["topology_decoded_value"],
        "left_topology_name": left["topology_source_name"],
        "right_topology_name": right["topology_source_name"],
        "topology_source_changed": left["topology_decoded_value"] != right["topology_decoded_value"],
        "within_physical_session": True, "boundary_stitchable": boundary_stitchable,
    }


def _cross_tab(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for source in sorted({str(row["topology_source_name"]) for row in rows}):
        selected = [row for row in rows if str(row["topology_source_name"]) == source]
        result.append({
            "topology_source_name": source,
            "topology_decoded_value": selected[0]["topology_decoded_value"],
            "message_count": len(selected),
            "h100_eligibility_counts": json.loads(stable_counts([row["h100_aligned_eligible"] for row in selected])),
            "estimate_failure_code_counts": json.loads(stable_counts([row["estimate_geometry_failure_code"] for row in selected])),
            "source_delta_ms": numeric_summary([row["source_delta_ms"] for row in selected]),
            "anchor_distance_m": numeric_summary([row["anchor_distance_m"] for row in selected]),
            "anchor_heading_delta_rad": numeric_summary([row["anchor_heading_delta_rad"] for row in selected]),
            "aligned_h100_residual_rms_m": numeric_summary([row["aligned_h100_residual_rms_m"] for row in selected]),
        })
    return result


def run_topology_semantics_audit(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Run the complete read-only audit and return its strict summary."""

    if arguments.expected_file_count < 1:
        raise ValueError("expected-file-count must be positive")
    files = _resolve_mcaps(arguments.inputs)
    if len(files) != arguments.expected_file_count:
        raise ValueError("resolved MCAP count does not match expected-file-count")
    recording_ids, drive_ids = _exact_drive_assignments(arguments.drive_map, files)
    drive_map_hash = sha256_file(arguments.drive_map)
    inventory_summary, groups_payload, inventory_hashes = validate_inventory_lineage(
        arguments.corpus_inventory_directory, expected_file_count=len(files)
    )
    alignment_manifest, pair_rows, alignment_hashes = validate_alignment_lineage(
        arguments.alignment_directory, expected_file_count=len(files),
        inventory_hashes=inventory_hashes, drive_map_hash=drive_map_hash,
    )
    manifest_recordings = {
        item["mcap_filename_private"]: (item["recording_id"], item["drive_id"])
        for item in alignment_manifest["recordings"]
    }
    for path in files:
        expected = (recording_ids[path], drive_ids[path])
        if manifest_recordings.get(path.name) != expected:
            raise ValueError(f"alignment manifest identity mismatch: {path.name}")
    inventory_rows = read_csv_rows(arguments.corpus_inventory_directory / "mcap_inventory.csv")
    inventory_by_name = {row["mcap_basename_private"]: row for row in inventory_rows}
    if set(inventory_by_name) != {path.name for path in files}:
        raise ValueError("mcap_inventory.csv does not exactly cover resolved files")
    for path in files:
        if int(inventory_by_name[path.name]["file_size_bytes"]) != path.stat().st_size:
            raise ValueError(f"MCAP size differs from accepted inventory: {path.name}")
        digest = inventory_by_name[path.name].get("sha256", "")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid accepted MCAP SHA-256: {path.name}")

    groups = groups_payload.get("groups")
    if not isinstance(groups, list) or len(groups) != 8:
        raise ValueError("expected exactly eight accepted physical-session groups")
    group_by_recording: dict[str, Mapping[str, Any]] = {}
    for group in groups:
        for recording_id in group["recording_ids"]:
            if recording_id in group_by_recording:
                raise ValueError(f"recording appears in multiple groups: {recording_id}")
            group_by_recording[recording_id] = group

    pair_by_key = {
        (row["recording_id"], int(row["estimate_message_index"])): row for row in pair_rows
    }
    message_rows: list[dict[str, Any]] = []
    by_recording: dict[str, list[dict[str, Any]]] = defaultdict(list)
    enum_declarations: set[tuple[int, str, str]] = set()
    enum_schema_values: set[tuple[int, str]] = set()
    for ordinal, path in enumerate(sorted(files, key=lambda item: recording_ids[item]), 1):
        recording_id, drive_id = recording_ids[path], drive_ids[path]
        LOGGER.info("decoding topology semantics %d/%d: %s", ordinal, len(files), recording_id)
        message_index = 0
        for schema, channel, mcap_message, decoded in iter_decoded_mcap_messages(
            path, topics=[arguments.estimate_topic], include_ros1=False
        ):
            if str(getattr(schema, "name", "")) != DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA:
                raise ValueError(f"unexpected EDP schema in {path.name}")
            if str(getattr(channel, "message_encoding", "")).lower() != "protobuf":
                raise ValueError(f"unexpected EDP encoding in {path.name}")
            raw = bytes(getattr(mcap_message, "data"))
            decoded_topology = decode_topology_message(
                decoded, raw_payload=raw, message_index=message_index,
                log_time_ns=int(getattr(mcap_message, "log_time", 0)),
                publish_time_ns=int(getattr(mcap_message, "publish_time", 0)),
                schema_fingerprint=_schema_fingerprint(schema, decoded),
            )
            pair = pair_by_key.get((recording_id, message_index))
            decoded_values = decoded_topology.row()
            decoded_values.pop("log_time_ns")
            decoded_values.pop("publish_time_ns")
            decoded_values.pop("source_time_ns")
            row = {
                "recording_id": recording_id, "drive_id": drive_id,
                "mcap_basename_private": path.name, **decoded_values,
                "log_time_ns_private": decoded_topology.log_time_ns,
                "publish_time_ns_private": decoded_topology.publish_time_ns,
                "source_time_ns_private": decoded_topology.source_time_ns,
                "mutual_nearest_pair_present": pair is not None,
            }
            for key in (
                "pair_index", "map_message_index", "source_delta_ms", "absolute_source_delta_ms",
                "pair_state", "failure_code", "estimate_geometry_state",
                "estimate_geometry_failure_code", "map_geometry_state", "map_geometry_failure_code",
                "anchor_distance_m", "anchor_heading_delta_rad",
            ):
                row[key] = None if pair is None or pair.get(key) == "" else pair.get(key)
            row["aligned_h100_residual_rms_m"] = (
                None if pair is None or pair.get("aligned_h100_lateral_rms_m") == ""
                else pair.get("aligned_h100_lateral_rms_m")
            )
            row["h60_aligned_eligible"] = False if pair is None else _bool(pair["h60_aligned_eligible"])
            row["h100_aligned_eligible"] = False if pair is None else _bool(pair["h100_aligned_eligible"])
            enum_declarations.add((decoded_topology.topology_field_number, decoded_topology.topology_enum_type, decoded_topology.topology_source_name))
            topology_field = decoded.DESCRIPTOR.fields_by_name["topology_source"]
            enum_schema_values.update(
                (int(value.number), str(value.name))
                for value in topology_field.enum_type.values
            )
            message_rows.append(row)
            by_recording[recording_id].append(row)
            message_index += 1
        if message_index == 0:
            raise ValueError(f"no EDP messages decoded: {path.name}")
    matched_pair_count = sum(row["mutual_nearest_pair_present"] for row in message_rows)
    if matched_pair_count != len(pair_rows):
        raise ValueError(f"alignment join incomplete: matched {matched_pair_count}/{len(pair_rows)}")
    if not all(row["topology_wire_decode_consistent"] for row in message_rows):
        raise ValueError("raw-wire and descriptor topology decoding disagree")

    continuity_rows = read_csv_rows(arguments.corpus_inventory_directory / "recording_continuity.csv")
    stitchable = {(row["left_recording_id"], row["right_recording_id"]): _bool(row["stitchable"]) for row in continuity_rows}
    if len(stitchable) != len(files) - len(groups) or not all(stitchable.values()):
        raise ValueError("accepted within-session boundary lineage is incomplete")
    transitions: list[dict[str, Any]] = []
    for rows in by_recording.values():
        transitions.extend(_transition(left, right, edge_scope="within_mcap", boundary_stitchable=None) for left, right in zip(rows, rows[1:]))
    for group in groups:
        recording_order = list(group["recording_ids"])
        for left_id, right_id in zip(recording_order, recording_order[1:]):
            transitions.append(_transition(
                by_recording[left_id][-1], by_recording[right_id][0],
                edge_scope="cross_mcap_boundary",
                boundary_stitchable=stitchable.get((left_id, right_id)),
            ))
    transitions.sort(key=lambda row: (row["drive_id"], row["left_recording_id"], int(row["left_message_index"]), row["edge_scope"]))

    recording_summaries = []
    for path in sorted(files, key=lambda item: recording_ids[item]):
        recording_id = recording_ids[path]
        relevant = [row for row in transitions if row["left_recording_id"] == recording_id and row["right_recording_id"] == recording_id]
        recording_summaries.append(_summary_row(
            by_recording[recording_id], recording_id=recording_id, drive_id=drive_ids[path],
            basename=path.name, recording_count=1, transitions=relevant,
        ))
    session_summaries = []
    for group in groups:
        ids = list(group["recording_ids"])
        rows = [row for recording_id in ids for row in by_recording[recording_id]]
        relevant = [row for row in transitions if row["drive_id"] == group["drive_id"]]
        session_summaries.append(_summary_row(
            rows, recording_id="", drive_id=group["drive_id"], basename="",
            recording_count=len(ids), transitions=relevant,
        ))

    outliers = []
    for row in message_rows:
        distance = _optional_float(row["anchor_distance_m"])
        if row["h60_aligned_eligible"] and distance is not None and distance > OUTLIER_DISTANCE_M:
            outliers.append({
                **{key: row.get(key) for key in OUTLIER_FIELDS if key not in {"audit_listing_threshold_m", "eligibility_changed_by_audit"}},
                "audit_listing_threshold_m": OUTLIER_DISTANCE_M,
                "eligibility_changed_by_audit": False,
            })
    outliers.sort(key=lambda row: (-float(row["anchor_distance_m"]), row["recording_id"], int(row["message_index"])))

    _ensure_empty(arguments.output_directory)
    copied_hashes = copy_inventory_lineage(
        arguments.corpus_inventory_directory,
        arguments.output_directory / "lineage" / "expanded_corpus_inventory_v0121",
    )
    if copied_hashes != inventory_hashes:
        raise OSError("packaged inventory lineage hashes changed")
    write_csv_rows(arguments.output_directory / "topology_message_audit.csv", MESSAGE_FIELDS, message_rows)
    write_csv_rows(arguments.output_directory / "topology_recording_summary.csv", SUMMARY_FIELDS, recording_summaries)
    write_csv_rows(arguments.output_directory / "topology_session_summary.csv", SUMMARY_FIELDS, session_summaries)
    write_csv_rows(arguments.output_directory / "topology_transition_audit.csv", TRANSITION_FIELDS, transitions)
    write_csv_rows(arguments.output_directory / "alignment_quality_outliers.csv", OUTLIER_FIELDS, outliers)
    plot_topology_quality_diagnostic(
        arguments.output_directory / "topology_alignment_quality_diagnostics.png",
        message_rows=message_rows,
    )

    observed = sorted({(int(row["topology_decoded_value"]), str(row["topology_source_name"])) for row in message_rows})
    wire_consistent = all(row["topology_wire_decode_consistent"] for row in message_rows)
    h60_rows = [row for row in message_rows if row["h60_aligned_eligible"]]
    h100_rows = [row for row in message_rows if row["h100_aligned_eligible"]]
    recording_038_outliers = [
        row for row in outliers
        if row["drive_id"] == "drive_006" and row["recording_id"] == "recording_038"
    ]
    summary = {
        "version": VERSION, "purpose": PURPOSE, "status": "complete",
        "audit_build_blockers": [],
        "downstream_modeling_constraints": list(DOWNSTREAM_MODELING_CONSTRAINTS),
        "counting_semantics": {
            "distribution_counts": "mutually_exclusive_within_each_reported_field",
            "failure_and_exclusion_reason_counts": (
                "non_mutually_exclusive; one message may contribute to multiple reasons"
            ),
        },
        "read_only_audit": True, "eligibility_changed": False,
        "topology_source_validation_relaxed": False,
        "expected_topology_source_remains": "ROAD_TOPOLOGY_SOURCE_SENSOR_TOPOLOGY",
        "model_training_performed": False, "residual_export_performed": False,
        "feature_extraction_performed": False, "cross_mcap_stitching_performed": False,
        "mcap_file_count": len(files), "physical_session_count": len(groups),
        "edp_message_count": len(message_rows), "alignment_pair_count": len(pair_rows),
        "h60_eligible_pair_count": len(h60_rows), "h100_eligible_pair_count": len(h100_rows),
        "topology_source_counts": json.loads(stable_counts([row["topology_source_name"] for row in message_rows])),
        "raw_wire_descriptor_decode_consistent_count": sum(row["topology_wire_decode_consistent"] for row in message_rows),
        "raw_wire_descriptor_decode_mismatch_count": sum(not row["topology_wire_decode_consistent"] for row in message_rows),
        "topology_transition_edge_count": len(transitions),
        "topology_transition_count": sum(row["topology_source_changed"] for row in transitions),
        "within_mcap_transition_count": sum(row["edge_scope"] == "within_mcap" and row["topology_source_changed"] for row in transitions),
        "cross_mcap_boundary_transition_count": sum(row["edge_scope"] == "cross_mcap_boundary" and row["topology_source_changed"] for row in transitions),
        "topology_cross_tab": _cross_tab(message_rows),
        "alignment_quality": {
            "audit_listing_threshold_m": OUTLIER_DISTANCE_M,
            "threshold_selected_from_model_performance": False,
            "eligible_pair_definition_for_outlier_listing": "current_h60_aligned_eligible",
            "listed_outlier_count": len(outliers),
            "drive_006_recording_038_style_outlier_count": sum(row["drive_id"] == "drive_006" and row["recording_id"] == "recording_038" for row in outliers),
            "drive_006_recording_038_style_outliers": {
                "recording_id": "recording_038",
                "drive_id": "drive_006",
                "message_indices": [int(row["message_index"]) for row in recording_038_outliers],
                "maximum_anchor_distance_m": (
                    max(float(row["anchor_distance_m"]) for row in recording_038_outliers)
                    if recording_038_outliers else None
                ),
            },
            "outlier_counts_by_recording": dict(sorted(
                Counter(row["recording_id"] for row in outliers).items()
            )),
            "h60_anchor_distance_m": numeric_summary([row["anchor_distance_m"] for row in h60_rows]),
            "h60_absolute_anchor_heading_delta_rad": numeric_summary([abs(float(row["anchor_heading_delta_rad"])) for row in h60_rows if row["anchor_heading_delta_rad"] not in {None, ""}]),
            "h100_anchor_distance_m": numeric_summary([row["anchor_distance_m"] for row in h100_rows]),
            "h100_absolute_anchor_heading_delta_rad": numeric_summary([abs(float(row["anchor_heading_delta_rad"])) for row in h100_rows if row["anchor_heading_delta_rad"] not in {None, ""}]),
        },
        "schema_and_code_semantics": {
            "semantic_metadata_revision": SEMANTIC_METADATA_REVISION,
            "edp_schema": DEFAULT_ESTIMATED_DRIVE_PATHS_SCHEMA,
            "topology_enum_declarations_observed": [
                {"field_number": field, "enum_type": enum_type, "observed_enum_name": name}
                for field, enum_type, name in sorted(enum_declarations)
            ],
            "topology_enum_values_declared": [
                {"numeric_value": value, "enum_name": name}
                for value, name in sorted(enum_schema_values)
            ],
            "source_interpretations": [topology_interpretation(value, name, all_wire_decodes_consistent=wire_consistent) for value, name in observed],
            "rlmb_reference_role": "best_available_pseudo_reference",
            "rlmb_upstream_sharing_provable_from_available_schema_or_code": False,
            "semantic_conclusions_use_timing": False,
        },
        "lineage": {
            "inventory_version": inventory_summary["version"],
            "packaged_inventory_directory": "lineage/expanded_corpus_inventory_v0121",
            "packaged_inventory_files_sha256": copied_hashes,
            "private_drive_map_sha256": drive_map_hash,
            "alignment_input_files_sha256": alignment_hashes,
            "raw_mcap_sha256_lineage_file": "lineage/expanded_corpus_inventory_v0121/mcap_inventory.csv",
        },
    }
    write_strict_json(arguments.output_directory / "topology_semantics_summary.json", summary)
    output_names = (
        "topology_message_audit.csv", "topology_recording_summary.csv",
        "topology_session_summary.csv", "topology_transition_audit.csv",
        "alignment_quality_outliers.csv", "topology_semantics_summary.json",
        "topology_alignment_quality_diagnostics.png",
    )
    manifest = {
        "version": VERSION, "purpose": PURPOSE, "status": "complete",
        "semantic_metadata_revision": SEMANTIC_METADATA_REVISION,
        "audit_build_blockers": [],
        "downstream_modeling_constraints": list(DOWNSTREAM_MODELING_CONSTRAINTS),
        "read_only_audit": True, "expected_file_count": arguments.expected_file_count,
        "resolved_file_count": len(files), "alignment_contract_version": "0.5.2",
        "inventory_contract_version": "0.12.1", "output_files": list(output_names),
        "packaged_inventory_files": list(INVENTORY_LINEAGE_FILES),
        "private_drive_map_sha256": drive_map_hash,
    }
    write_strict_json(arguments.output_directory / "topology_audit_manifest.json", manifest)
    generated = {
        name: sha256_file(arguments.output_directory / name)
        for name in (*output_names, "topology_audit_manifest.json")
    }
    provenance = {
        "version": VERSION, "purpose": PURPOSE,
        "semantic_metadata_revision": SEMANTIC_METADATA_REVISION,
        "private_drive_map_sha256": drive_map_hash,
        "inventory_inputs_sha256": inventory_hashes,
        "alignment_inputs_sha256": alignment_hashes,
        "generated_outputs_sha256": generated,
    }
    write_strict_json(arguments.output_directory / "topology_audit_provenance.json", provenance)
    return summary, 0


__all__ = [
    "MESSAGE_FIELDS", "OUTLIER_FIELDS", "SUMMARY_FIELDS", "TRANSITION_FIELDS",
    "run_topology_semantics_audit",
]
