"""Immutable accepted-input contract for the v0.16.2 spatial audit."""

from __future__ import annotations

from dataclasses import dataclass

VERSION = "0.16.2"

A2_SAMPLE_FILENAME = "sampled_residual_sequences.npz"
A2_SUMMARY_FILENAME = "sampled_residual_sequences_summary.json"
A3_SAMPLE_FILENAME = "unconditional_gaussian_residual_samples.npz"
A3_SUMMARY_FILENAME = "unconditional_gaussian_residual_samples_summary.json"

MATRICES_FILENAME = "spatial_structure_matrices.npz"
PAIR_FILENAME = "spatial_structure_by_station_pair.csv"
SEPARATION_FILENAME = "spatial_structure_by_separation.csv"
SEQUENCE_FILENAME = "spatial_structure_by_sequence.csv"
SUMMARY_FILENAME = "spatial_structure_audit_summary.json"

OUTPUT_FILENAMES = (
    MATRICES_FILENAME,
    PAIR_FILENAME,
    SEPARATION_FILENAME,
    SEQUENCE_FILENAME,
    SUMMARY_FILENAME,
)


@dataclass(frozen=True)
class SpatialStructureAuditContract:
    """Exact source hashes and fixed dimensions for one audit execution."""

    a2_sample_sha256: str
    a2_summary_sha256: str
    a3_sample_sha256: str
    a3_summary_sha256: str
    sample_count: int = 128
    sequence_count: int = 15
    maximum_sequence_length: int = 924
    active_frame_count: int = 4_083
    a2_sampling_seed: int = 20_260_826
    a3_sampling_seed: int = 20_260_828
    correlation_tolerance: float = 1e-12

    def __post_init__(self) -> None:
        for value in (
            self.a2_sample_sha256,
            self.a2_summary_sha256,
            self.a3_sample_sha256,
            self.a3_summary_sha256,
        ):
            if len(value) != 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise ValueError("spatial-audit SHA-256 values must be lowercase hex")
        for value, label in (
            (self.sample_count, "sample_count"),
            (self.sequence_count, "sequence_count"),
            (self.maximum_sequence_length, "maximum_sequence_length"),
            (self.active_frame_count, "active_frame_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if self.active_frame_count > (
            self.sequence_count * self.maximum_sequence_length
        ):
            raise ValueError("active_frame_count exceeds the padded sequence capacity")
        if (
            not isinstance(self.correlation_tolerance, float)
            or self.correlation_tolerance < 0.0
        ):
            raise ValueError("correlation_tolerance must be a nonnegative float")


ACCEPTED_SPATIAL_STRUCTURE_AUDIT_CONTRACT = SpatialStructureAuditContract(
    a2_sample_sha256=(
        "5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa"
    ),
    a2_summary_sha256=(
        "6038dde59c9db9b715ce4966c1b7f5d239133664856efd4cc4acf6e8e18acb4b"
    ),
    a3_sample_sha256=(
        "458a255f76334b281889df48bf8f549bd7b1f2fd124579b958b41d5353a8c81f"
    ),
    a3_summary_sha256=(
        "8b17a16be7d6f76b5a3d69f3b03f82e28f8105a4a60f4fe9df6aac60e806f0f2"
    ),
)


__all__ = [
    "A2_SAMPLE_FILENAME",
    "A2_SUMMARY_FILENAME",
    "A3_SAMPLE_FILENAME",
    "A3_SUMMARY_FILENAME",
    "ACCEPTED_SPATIAL_STRUCTURE_AUDIT_CONTRACT",
    "MATRICES_FILENAME",
    "OUTPUT_FILENAMES",
    "PAIR_FILENAME",
    "SEPARATION_FILENAME",
    "SEQUENCE_FILENAME",
    "SUMMARY_FILENAME",
    "SpatialStructureAuditContract",
    "VERSION",
]
