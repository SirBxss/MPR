"""v0.13.1 boundary-odometry IO and baseline-parity contracts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.conditional_features import coalesce_identical_odometry_timestamps
from ..domain.expanded_sequence_dataset_v0131 import (
    BASELINE_PURPOSE,
    BASELINE_VERSION,
)
from ..domain.motion import OdometrySample
from .expanded_sequence_dataset import (
    ExpandedSequenceContractError,
    ExpandedSequenceInputs,
    read_json_object,
    sha256_file,
    validate_profile_archive,
)
from .mcap import iter_decoded_mcap_messages
from .odometry import (
    DEFAULT_ODOMETRY_SCHEMA,
    decode_odometry_samples,
)


SEMANTIC_METADATA_REVISION = "rlmb_independence_explicitly_unknown"


@dataclass(frozen=True)
class BoundaryOdometryStream:
    """Decoded and schema-audited odometry for one contributing MCAP."""

    basename_private: str
    topic: str
    message_count: int
    samples: tuple[OdometrySample, ...] = field(repr=False)
    schema_identities: tuple[str, ...]
    failure_counts: Mapping[str, int]
    conflicting_duplicate_timestamp_group_count: int

    @property
    def topic_present(self) -> bool:
        return self.message_count > 0

    @property
    def strict_timestamps(self) -> bool:
        times = [sample.timestamp_ns for sample in self.samples]
        return bool(times) and all(right > left for left, right in zip(times, times[1:]))


def _schema_identity(schema: Any, channel: Any) -> str:
    name = str(getattr(schema, "name", ""))
    encoding = str(getattr(channel, "message_encoding", "")).lower()
    raw = getattr(schema, "data", b"")
    if not isinstance(raw, bytes):
        raw = bytes(raw) if raw is not None else b""
    digest = hashlib.sha256(raw).hexdigest()
    return f"{name}|{encoding}|sha256:{digest}"


def load_boundary_odometry_stream(
    path: Path,
    *,
    basename_private: str,
    topic: str,
) -> BoundaryOdometryStream:
    """Decode one stream and retain exact schema/duplicate evidence."""

    samples, failures, message_count = decode_odometry_samples(path, topic=topic)
    identities = {
        _schema_identity(schema, channel)
        for schema, channel, _, _ in iter_decoded_mcap_messages(
            path, topics=(topic,), include_ros1=False
        )
    }
    duplicate_audit = coalesce_identical_odometry_timestamps(samples)
    counts = dict(sorted((str(key), int(value)) for key, value in failures.items()))
    if duplicate_audit.conflicting_timestamp_group_count:
        counts["odometry__conflicting_duplicate_timestamp_group"] = (
            duplicate_audit.conflicting_timestamp_group_count
        )
    return BoundaryOdometryStream(
        basename_private=basename_private,
        topic=topic,
        message_count=message_count,
        samples=duplicate_audit.samples,
        schema_identities=tuple(sorted(identities)),
        failure_counts=dict(sorted(counts.items())),
        conflicting_duplicate_timestamp_group_count=(
            duplicate_audit.conflicting_timestamp_group_count
        ),
    )


def boundary_schemas_compatible(
    left: BoundaryOdometryStream,
    right: BoundaryOdometryStream,
) -> bool:
    """Require one identical expected protobuf schema and no decode failures."""

    expected_prefix = f"{DEFAULT_ODOMETRY_SCHEMA}|protobuf|sha256:"
    return (
        left.topic == right.topic
        and left.topic_present
        and right.topic_present
        and not left.failure_counts
        and not right.failure_counts
        and len(left.schema_identities) == 1
        and left.schema_identities == right.schema_identities
        and left.schema_identities[0].startswith(expected_prefix)
    )


def validate_corrected_topology_lineage(
    inputs: ExpandedSequenceInputs,
    topology_directory: Path,
) -> None:
    """Require the corrected v0.12.2 semantic summary, manifest, and provenance."""

    summary = inputs.topology_summary
    if summary.get("audit_build_blockers") != [] or "blockers" in summary:
        raise ExpandedSequenceContractError("corrected topology audit blockers differ")
    if summary.get("counting_semantics", {}).get(
        "failure_and_exclusion_reason_counts"
    ) != "non_mutually_exclusive; one message may contribute to multiple reasons":
        raise ExpandedSequenceContractError("topology counting semantics are unavailable")
    interpretations = summary.get("schema_and_code_semantics", {}).get(
        "source_interpretations"
    )
    if not isinstance(interpretations, Sequence) or not interpretations:
        raise ExpandedSequenceContractError("topology source interpretations are unavailable")
    for interpretation in interpretations:
        if not isinstance(interpretation, Mapping):
            raise ExpandedSequenceContractError("invalid topology source interpretation")
        if interpretation.get("independence_from_rlmb") != "unknown":
            raise ExpandedSequenceContractError("RLMB independence must remain unknown")
        if "independent_sensor_topology" in interpretation:
            raise ExpandedSequenceContractError("ambiguous topology independence field remains")
    for name in ("topology_audit_manifest.json", "topology_audit_provenance.json"):
        payload = read_json_object(topology_directory / name)
        if payload.get("semantic_metadata_revision") != SEMANTIC_METADATA_REVISION:
            raise ExpandedSequenceContractError(f"uncorrected topology lineage: {name}")


def load_v0130_baseline(
    directory: Path,
) -> tuple[dict[str, np.ndarray], Mapping[str, Any], dict[str, str]]:
    """Load and hash the complete immutable v0.13.0 parity baseline."""

    required = (
        "expanded_profile_dataset.npz",
        "expanded_sequence_contract.json",
        "expanded_sequence_manifest.json",
        "expanded_sequence_provenance.json",
    )
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"v0.13.0 baseline files missing: {missing}")
    summary = read_json_object(directory / "expanded_sequence_contract.json")
    manifest = read_json_object(directory / "expanded_sequence_manifest.json")
    provenance = read_json_object(directory / "expanded_sequence_provenance.json")
    for name, payload in (("summary", summary), ("manifest", manifest)):
        if (
            payload.get("version") != BASELINE_VERSION
            or payload.get("purpose") != BASELINE_PURPOSE
            or payload.get("status") != "complete"
        ):
            raise ExpandedSequenceContractError(f"invalid v0.13.0 baseline {name}")
    generated = provenance.get("generated_outputs_sha256")
    if not isinstance(generated, Mapping) or not generated:
        raise ExpandedSequenceContractError("v0.13.0 generated hashes unavailable")
    for name, digest in generated.items():
        path = directory / str(name)
        if not path.is_file() or sha256_file(path) != digest:
            raise ExpandedSequenceContractError(f"v0.13.0 provenance mismatch: {name}")
    archive = directory / "expanded_profile_dataset.npz"
    validate_profile_archive(archive)
    with np.load(archive, allow_pickle=False) as payload:
        arrays = {name: np.array(payload[name], copy=True) for name in payload.files}
    hashes = {name: sha256_file(directory / name) for name in required}
    return arrays, summary, dict(sorted(hashes.items()))


def validate_v0131_profile_archive(path: Path) -> dict[str, tuple[int, ...]]:
    """Validate the deterministic v0.13.1 archive and boundary evidence arrays."""

    required_extra = {
        "speed_context_states",
        "speed_context_left_mcap_basenames_private",
        "speed_context_right_mcap_basenames_private",
        "speed_context_odometry_timestamps_ns_json_private",
    }
    with np.load(path, allow_pickle=False) as payload:
        if not required_extra.issubset(payload.files):
            raise ExpandedSequenceContractError("v0.13.1 boundary arrays missing")
        count = payload["residuals_m"].shape[0]
        if any(payload[name].shape != (count,) for name in required_extra):
            raise ExpandedSequenceContractError("v0.13.1 boundary arrays are not [N]")
        if payload["conditions"].shape != (count, 6):
            raise ExpandedSequenceContractError("v0.13.1 conditions must be [N,6]")
        return {name: tuple(payload[name].shape) for name in sorted(payload.files)}


def validate_live_raw_hashes(
    resolved_by_basename: Mapping[str, Path],
    expected_hashes: Mapping[str, str],
) -> dict[str, str]:
    """Reconcile every live private MCAP against immutable v0.12.1 lineage."""

    if set(resolved_by_basename) != set(expected_hashes):
        raise ExpandedSequenceContractError("live MCAP set differs from raw hash lineage")
    actual = {
        basename: sha256_file(resolved_by_basename[basename])
        for basename in sorted(resolved_by_basename)
    }
    mismatches = [name for name in actual if actual[name] != expected_hashes[name]]
    if mismatches:
        raise ExpandedSequenceContractError(f"live raw MCAP hashes differ: {mismatches}")
    return actual


__all__ = [
    "BoundaryOdometryStream",
    "boundary_schemas_compatible",
    "load_boundary_odometry_stream",
    "load_v0130_baseline",
    "validate_corrected_topology_lineage",
    "validate_live_raw_hashes",
    "validate_v0131_profile_archive",
]
