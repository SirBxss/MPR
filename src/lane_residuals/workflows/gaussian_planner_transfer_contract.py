"""Immutable v0.16.1 Gaussian planner-transfer lineage and run contract."""

from __future__ import annotations

from dataclasses import dataclass

VERSION = "0.16.1"
GAUSSIAN_SAMPLE_FILENAME = "unconditional_gaussian_residual_samples.npz"
GAUSSIAN_SAMPLE_SUMMARY_FILENAME = (
    "unconditional_gaussian_residual_samples_summary.json"
)
TRANSFER_FRAME_FILENAME = "gaussian_transfer_frame_metrics.npz"
TRANSFER_SEQUENCE_FILENAME = "gaussian_transfer_sequence_metrics.csv"
TRANSFER_SUMMARY_FILENAME = "gaussian_planner_transfer_summary.json"


@dataclass(frozen=True)
class GaussianPlannerTransferContract:
    """Exact accepted inputs and predeclared Monte Carlo parameters."""

    development_model_sha256: str
    scenario_sha256: str
    a2_sample_sha256: str
    v016_frame_sha256: str
    v016_sequence_sha256: str
    v016_summary_sha256: str
    sample_count: int = 128
    sequence_count: int = 15
    active_frame_count: int = 4_083
    a2_sampling_seed: int = 20_260_826
    shuffle_seed: int = 20_260_827
    shuffled_frame_positions_changed: int = 520_675
    gaussian_sampling_seed: int = 20_260_828
    bootstrap_seed: int = 20_260_829
    bootstrap_replicates: int = 20_000
    p95_minimum_active_frames: int = 20
    a0_macro_constraint_violation_fraction_rounded_6: float = 0.259355

    def __post_init__(self) -> None:
        digests = (
            self.development_model_sha256,
            self.scenario_sha256,
            self.a2_sample_sha256,
            self.v016_frame_sha256,
            self.v016_sequence_sha256,
            self.v016_summary_sha256,
        )
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in digests
        ):
            raise ValueError("Gaussian transfer SHA-256 values must be lowercase hex")
        for value, label in (
            (self.sample_count, "sample_count"),
            (self.sequence_count, "sequence_count"),
            (self.active_frame_count, "active_frame_count"),
            (self.bootstrap_replicates, "bootstrap_replicates"),
            (self.p95_minimum_active_frames, "p95_minimum_active_frames"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")


ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT = GaussianPlannerTransferContract(
    development_model_sha256=(
        "976259c05eb67e600b017a81bed77846a424b5687d51f4a04168431bfc7b6bd3"
    ),
    scenario_sha256=(
        "615f6c7d5ef6b6b9c0770c65b58bb23c573a838579aa4fdf3f25c141a15c0591"
    ),
    a2_sample_sha256=(
        "5f54e56f73182d6cd61ea0ff1875538ecfc5a751e17c69c6dd5664f3b84b10aa"
    ),
    v016_frame_sha256=(
        "9d2b6a724a648839756597d40497cf6a2fc9b55a4422230fcddb317fe26a2a9f"
    ),
    v016_sequence_sha256=(
        "3f9ea8db4e4e2817c450dd82ebe8a52042a12e6aa76fbb0d4b7b31da4d96a1df"
    ),
    v016_summary_sha256=(
        "38a04f655f9c9f6ec0e89d817534e8e289e0571787c229fa630d37406bcc8154"
    ),
)


__all__ = [
    "ACCEPTED_GAUSSIAN_PLANNER_TRANSFER_CONTRACT",
    "GAUSSIAN_SAMPLE_FILENAME",
    "GAUSSIAN_SAMPLE_SUMMARY_FILENAME",
    "GaussianPlannerTransferContract",
    "TRANSFER_FRAME_FILENAME",
    "TRANSFER_SEQUENCE_FILENAME",
    "TRANSFER_SUMMARY_FILENAME",
    "VERSION",
]
