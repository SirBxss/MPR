"""Strict loading for the v0.9.0 common sequential tensor contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..domain.sequence_dataset import PaddedSequenceDataset

SEQUENCE_DATASET_NPZ_FIELDS = frozenset(
    {
        "schema_version",
        "standardized",
        "sequence_ids",
        "recording_ids",
        "drive_ids",
        "lengths",
        "conditions",
        "residuals_m",
        "valid_mask",
        "pair_indices",
        "estimate_message_indices",
        "estimate_source_times_ns_private",
        "feature_names",
        "stations_m",
    }
)


def load_sequence_dataset_npz(path: str | Path) -> PaddedSequenceDataset:
    """Load and validate a sequence NPZ without permitting pickled objects."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"sequence dataset not found: {source}")
    try:
        with np.load(source, allow_pickle=False) as payload:
            if set(payload.files) != SEQUENCE_DATASET_NPZ_FIELDS:
                raise ValueError("sequence dataset NPZ fields differ from v0.9.0")
            schema_version = payload["schema_version"]
            standardized = payload["standardized"]
            if schema_version.shape != () or str(schema_version.item()) != "0.9.0":
                raise ValueError("sequence dataset schema version must be 0.9.0")
            if standardized.shape != ():
                raise ValueError("sequence standardized flag must be scalar")
            standardized_value = standardized.item()
            if not isinstance(standardized_value, (bool, np.bool_)):
                raise ValueError("sequence standardized flag must be boolean")
            return PaddedSequenceDataset(
                sequence_ids=payload["sequence_ids"],
                recording_ids=payload["recording_ids"],
                drive_ids=payload["drive_ids"],
                lengths=payload["lengths"],
                conditions=payload["conditions"],
                residuals_m=payload["residuals_m"],
                valid_mask=payload["valid_mask"],
                pair_indices=payload["pair_indices"],
                estimate_message_indices=payload["estimate_message_indices"],
                estimate_source_times_ns_private=(
                    payload["estimate_source_times_ns_private"]
                ),
                feature_names=tuple(
                    str(value) for value in payload["feature_names"].tolist()
                ),
                stations_m=tuple(
                    float(value) for value in payload["stations_m"].tolist()
                ),
                standardized=bool(standardized_value),
            )
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid sequence dataset NPZ: {error}") from error


__all__ = ["SEQUENCE_DATASET_NPZ_FIELDS", "load_sequence_dataset_npz"]
