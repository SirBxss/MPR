"""Strict v0.13.0 input lineage and deterministic tensor serialization."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.alignment_contract import validate_native_projection_contract
from ..domain.expanded_sequence_dataset import PURPOSE, VERSION
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M


class ExpandedSequenceContractError(ValueError):
    """An accepted prerequisite or expanded tensor contract is inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path) -> Mapping[str, Any]:
    def reject(value: str) -> None:
        raise ExpandedSequenceContractError(f"non-finite JSON constant: {value}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=reject)
    if not isinstance(payload, Mapping):
        raise ExpandedSequenceContractError(f"JSON object required: {path}")
    return payload


def read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ExpandedSequenceContractError(f"CSV header missing: {path}")
        return tuple(dict(row) for row in reader)


@dataclass(frozen=True)
class ExpandedSequenceInputs:
    alignment_manifest: Mapping[str, Any] = field(repr=False)
    topology_summary: Mapping[str, Any] = field(repr=False)
    topology_message_rows: tuple[dict[str, str], ...] = field(repr=False)
    alignment_pair_rows: tuple[dict[str, str], ...] = field(repr=False)
    station_rows: tuple[dict[str, str], ...] = field(repr=False)
    continuity_rows: tuple[dict[str, str], ...] = field(repr=False)
    source_files_sha256: Mapping[str, str] = field(repr=False)


def _validate_generated_hashes(directory: Path, payload: Mapping[str, Any], key: str) -> None:
    hashes = payload.get(key)
    if not isinstance(hashes, Mapping) or not hashes:
        raise ExpandedSequenceContractError(f"provenance lacks {key}")
    for name, expected in hashes.items():
        path = directory / str(name)
        if not path.is_file() or sha256_file(path) != expected:
            raise ExpandedSequenceContractError(f"provenance mismatch: {path}")


def load_expanded_sequence_inputs(
    *,
    alignment_directory: Path,
    topology_audit_directory: Path,
    expected_file_count: int = 67,
) -> ExpandedSequenceInputs:
    """Load only complete, mutually reconciled v0.5.2/v0.12.2 inputs."""

    alignment_files = (
        "batch_manifest.json",
        "alignment_batch_summary.json",
        "alignment_station_comparison.csv",
        "alignment_pair_audit.csv",
        "batch_output_provenance.json",
    )
    topology_files = (
        "topology_semantics_summary.json",
        "topology_message_audit.csv",
        "topology_audit_manifest.json",
        "topology_audit_provenance.json",
    )
    for directory, names in (
        (alignment_directory, alignment_files),
        (topology_audit_directory, topology_files),
    ):
        missing = [name for name in names if not (directory / name).is_file()]
        if missing:
            raise FileNotFoundError(f"required input files missing: {missing}")

    alignment_manifest = read_json_object(alignment_directory / "batch_manifest.json")
    alignment_summary = read_json_object(alignment_directory / "alignment_batch_summary.json")
    for name, payload in (("alignment manifest", alignment_manifest), ("alignment summary", alignment_summary)):
        version, _ = validate_native_projection_contract(
            payload, name=name, error_type=ExpandedSequenceContractError
        )
        if version != "0.5.2":
            raise ExpandedSequenceContractError("expanded dataset requires v0.5.2")
    if alignment_manifest.get("status") != "complete" or alignment_summary.get("status") != "complete":
        raise ExpandedSequenceContractError("alignment inputs must be complete")
    if alignment_summary.get("resolved_file_count") != expected_file_count:
        raise ExpandedSequenceContractError("alignment corpus size mismatch")
    alignment_provenance = read_json_object(
        alignment_directory / "batch_output_provenance.json"
    )
    _validate_generated_hashes(
        alignment_directory, alignment_provenance, "generated_batch_outputs_sha256"
    )

    topology_summary = read_json_object(
        topology_audit_directory / "topology_semantics_summary.json"
    )
    topology_manifest = read_json_object(
        topology_audit_directory / "topology_audit_manifest.json"
    )
    topology_provenance = read_json_object(
        topology_audit_directory / "topology_audit_provenance.json"
    )
    expected_topology = {
        "version": "0.12.2",
        "purpose": "complete_corpus_edp_topology_semantics_alignment_quality_audit",
        "status": "complete",
        "read_only_audit": True,
        "eligibility_changed": False,
        "topology_source_validation_relaxed": False,
        "mcap_file_count": expected_file_count,
    }
    for key, value in expected_topology.items():
        if topology_summary.get(key) != value:
            raise ExpandedSequenceContractError(f"invalid topology summary field {key}")
    if topology_manifest.get("version") != "0.12.2" or topology_manifest.get("status") != "complete":
        raise ExpandedSequenceContractError("topology manifest is not accepted")
    _validate_generated_hashes(
        topology_audit_directory, topology_provenance, "generated_outputs_sha256"
    )
    alignment_hashes = topology_provenance.get("alignment_inputs_sha256")
    if not isinstance(alignment_hashes, Mapping):
        raise ExpandedSequenceContractError("topology alignment lineage is unavailable")
    for name in ("batch_manifest.json", "alignment_batch_summary.json"):
        if alignment_hashes.get(name) != sha256_file(alignment_directory / name):
            raise ExpandedSequenceContractError(f"topology/alignment lineage mismatch: {name}")

    messages = read_csv_rows(topology_audit_directory / "topology_message_audit.csv")
    if len(messages) != topology_summary.get("edp_message_count"):
        raise ExpandedSequenceContractError("topology message count does not reconcile")
    message_keys = [(row["recording_id"], row["pair_index"]) for row in messages if row["mutual_nearest_pair_present"] == "True"]
    if len(message_keys) != len(set(message_keys)):
        raise ExpandedSequenceContractError("paired topology message keys are not unique")

    stations = read_csv_rows(alignment_directory / "alignment_station_comparison.csv")
    alignment_pairs = read_csv_rows(alignment_directory / "alignment_pair_audit.csv")
    if len(alignment_pairs) != alignment_summary.get("mutual_nearest_pair_count"):
        raise ExpandedSequenceContractError("alignment pair count does not reconcile")
    continuity_path = (
        topology_audit_directory
        / "lineage"
        / "expanded_corpus_inventory_v0121"
        / "recording_continuity.csv"
    )
    continuity = read_csv_rows(continuity_path)
    if len(continuity) != expected_file_count - 8 or any(row["stitchable"] != "True" for row in continuity):
        raise ExpandedSequenceContractError("accepted continuity lineage is incomplete")

    sources = {
        f"alignment/{name}": sha256_file(alignment_directory / name)
        for name in alignment_files
    }
    sources.update(
        {
            f"topology/{name}": sha256_file(topology_audit_directory / name)
            for name in topology_files
        }
    )
    sources["topology/lineage/recording_continuity.csv"] = sha256_file(continuity_path)
    return ExpandedSequenceInputs(
        alignment_manifest=alignment_manifest,
        topology_summary=topology_summary,
        topology_message_rows=messages,
        alignment_pair_rows=alignment_pairs,
        station_rows=stations,
        continuity_rows=continuity,
        source_files_sha256=dict(sorted(sources.items())),
    )


def residual_profiles_by_pair(
    station_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], np.ndarray]:
    """Reconstruct exact finite canonical [21] profiles, omitting incomplete rows."""

    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for row in station_rows:
        if row.get("h100_aligned_eligible") != "True":
            continue
        try:
            key = (str(row["recording_id"]), int(str(row["pair_index"])))
        except (KeyError, ValueError) as error:
            raise ExpandedSequenceContractError("invalid station profile key") from error
        grouped.setdefault(key, []).append(row)
    result: dict[tuple[str, int], np.ndarray] = {}
    expected = np.asarray(CANONICAL_MODEL_STATIONS_M, dtype=np.float64)
    for key, rows in grouped.items():
        try:
            stations = np.asarray([float(row["station_m"]) for row in rows], dtype=np.float64)
            residuals = np.asarray([float(row["aligned_lateral_m"]) for row in rows], dtype=np.float64)
        except (KeyError, ValueError) as error:
            raise ExpandedSequenceContractError(f"invalid station values for {key}") from error
        if stations.shape == (21,) and np.array_equal(stations, expected) and np.all(np.isfinite(residuals)):
            residuals.setflags(write=False)
            result[key] = residuals
    return result


def write_deterministic_npz(path: Path, arrays: Mapping[str, Any]) -> None:
    """Write NumPy arrays in a ZIP with fixed ordering, metadata, and compression."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with zipfile.ZipFile(raw, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(arrays):
                if not name or "/" in name or "\\" in name:
                    raise ValueError("NPZ array names must be simple nonempty names")
                buffer = io.BytesIO()
                np.lib.format.write_array(buffer, np.asarray(arrays[name]), allow_pickle=False)
                info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                info.create_system = 3
                archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def validate_profile_archive(path: Path) -> dict[str, tuple[int, ...]]:
    """Validate the stable model-independent [N,21]/[N,6] archive contract."""

    required = {
        "residuals_m", "conditions", "timestamps_ns_private", "recording_ids",
        "drive_ids", "mcap_basenames_private", "sequence_ids", "pair_indices",
        "estimate_message_indices", "stations_m", "eligibility", "exclusion_reasons",
    }
    with np.load(path, allow_pickle=False) as payload:
        if set(payload.files) != required:
            raise ExpandedSequenceContractError("expanded profile archive fields differ")
        residuals = payload["residuals_m"]
        conditions = payload["conditions"]
        count = residuals.shape[0] if residuals.ndim == 2 else -1
        if residuals.shape != (count, 21) or conditions.shape != (count, 6):
            raise ExpandedSequenceContractError("expanded tensors have invalid shape")
        if not np.all(np.isfinite(residuals)) or not np.all(np.isfinite(conditions)):
            raise ExpandedSequenceContractError("expanded tensors must be finite")
        if not np.array_equal(payload["stations_m"], CANONICAL_MODEL_STATIONS_M):
            raise ExpandedSequenceContractError("expanded station grid differs")
        for name in required - {"residuals_m", "conditions", "stations_m"}:
            if payload[name].shape != (count,):
                raise ExpandedSequenceContractError(f"archive field {name} is not [N]")
        return {name: tuple(payload[name].shape) for name in sorted(required)}


__all__ = [
    "ExpandedSequenceContractError",
    "ExpandedSequenceInputs",
    "load_expanded_sequence_inputs",
    "read_csv_rows",
    "read_json_object",
    "residual_profiles_by_pair",
    "sha256_file",
    "validate_profile_archive",
    "write_deterministic_npz",
]
