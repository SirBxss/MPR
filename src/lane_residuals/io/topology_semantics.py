"""Strict input contracts and immutable lineage copies for topology audits."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..domain.alignment_contract import (
    CURRENT_ALIGNMENT_VERSION,
    validate_native_projection_contract,
)


INVENTORY_LINEAGE_FILES = (
    "mcap_inventory.csv",
    "topic_compatibility.csv",
    "recording_continuity.csv",
    "proposed_session_groups.json",
    "corpus_inventory_summary.json",
    "corpus_inventory_diagnostics.png",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> Mapping[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant in {path}: {value}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=reject_constant)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return tuple(dict(row) for row in reader)


def validate_inventory_lineage(
    directory: Path,
    *,
    expected_file_count: int,
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, str]]:
    """Require the complete regenerated v0.12.1 inventory bundle."""

    missing = [name for name in INVENTORY_LINEAGE_FILES if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"inventory lineage files missing: {missing}")
    summary = read_json_object(directory / "corpus_inventory_summary.json")
    if summary.get("version") != "0.12.1":
        raise ValueError("corpus inventory version must be exactly 0.12.1")
    expected = {
        "status": "complete",
        "exact_drive_map_coverage": True,
        "mcap_file_count": expected_file_count,
        "unusable_file_count": 0,
        "physical_drive_count": 8,
        "provisional_continuous_block_count": 8,
        "rejected_boundary_count": 0,
        "stitchable_boundary_count": expected_file_count - 8,
        "duplicate_count": 0,
        "empty_file_count": 0,
        "unreadable_file_count": 0,
        "required_topic_schema_failure_count": 0,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError(f"invalid v0.12.1 inventory field {key}")
    groups = read_json_object(directory / "proposed_session_groups.json")
    if groups.get("cross_mcap_sequence_stitching_performed") is not False:
        raise ValueError("inventory must not have performed sequence stitching")
    hashes = {name: sha256_file(directory / name) for name in INVENTORY_LINEAGE_FILES}
    return summary, groups, hashes


def validate_alignment_lineage(
    directory: Path,
    *,
    expected_file_count: int,
    inventory_hashes: Mapping[str, str],
    drive_map_hash: str,
) -> tuple[Mapping[str, Any], tuple[dict[str, str], ...], dict[str, str]]:
    """Read only a complete, hashed v0.5.2 native projection batch."""

    required = (
        "alignment_batch_summary.json",
        "batch_manifest.json",
        "batch_output_provenance.json",
        "alignment_pair_audit.csv",
    )
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"alignment lineage files missing: {missing}")
    summary = read_json_object(directory / "alignment_batch_summary.json")
    manifest = read_json_object(directory / "batch_manifest.json")
    provenance = read_json_object(directory / "batch_output_provenance.json")
    for name, payload in (("summary", summary), ("manifest", manifest), ("provenance", provenance)):
        version, _ = validate_native_projection_contract(payload, name=name)
        if version != CURRENT_ALIGNMENT_VERSION:
            raise ValueError("topology audit requires the complete v0.5.2 exact manifest")
    if summary.get("status") != "complete" or manifest.get("status") != "complete":
        raise ValueError("alignment batch must be complete")
    if summary.get("resolved_file_count") != expected_file_count:
        raise ValueError("alignment file count does not match exact corpus")
    if summary.get("failed_recording_count") != 0 or summary.get("blockers") != []:
        raise ValueError("alignment batch contains failures or blockers")
    generated = provenance.get("generated_batch_outputs_sha256")
    if not isinstance(generated, Mapping):
        raise ValueError("alignment provenance generated hashes are unavailable")
    for name, expected_hash in generated.items():
        path = directory / str(name)
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise ValueError(f"alignment provenance mismatch: {name}")
    source_hashes = provenance.get("source_files_sha256")
    if not isinstance(source_hashes, Mapping):
        raise ValueError("alignment source hashes are unavailable")
    if source_hashes.get("drive_map_private_json") != drive_map_hash:
        raise ValueError("drive-map hash differs from v0.5.2 alignment lineage")
    for name in (
        "corpus_inventory_summary.json",
        "recording_continuity.csv",
        "proposed_session_groups.json",
    ):
        if source_hashes.get(name) != inventory_hashes.get(name):
            raise ValueError(f"inventory hash differs from v0.5.2 lineage: {name}")
    rows = read_csv_rows(directory / "alignment_pair_audit.csv")
    if summary.get("mutual_nearest_pair_count") != len(rows):
        raise ValueError("alignment summary pair count does not match pair audit")
    keys = [(row.get("recording_id"), row.get("estimate_message_index")) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("alignment estimate-message keys are not unique")
    hashes = {name: sha256_file(directory / name) for name in required}
    return manifest, rows, hashes


def copy_inventory_lineage(
    source_directory: Path,
    output_directory: Path,
) -> dict[str, str]:
    """Copy the exact accepted inventory outputs and verify copied bytes."""

    output_directory.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    for name in INVENTORY_LINEAGE_FILES:
        source = source_directory / name
        target = output_directory / name
        shutil.copyfile(source, target)
        source_hash = sha256_file(source)
        if sha256_file(target) != source_hash:
            raise OSError(f"lineage copy hash mismatch: {name}")
        hashes[name] = source_hash
    return hashes


__all__ = [
    "INVENTORY_LINEAGE_FILES",
    "copy_inventory_lineage",
    "read_csv_rows",
    "read_json_object",
    "sha256_file",
    "validate_alignment_lineage",
    "validate_inventory_lineage",
]
