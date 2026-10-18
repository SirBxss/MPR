"""Read-only engineering view of a strictly validated generic numeric archive."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np

from ..domain.artifact_registry import ACCEPTED_NUMERIC_PRODUCER, RegistryError, require
from .numeric_archive import read_pinned_summary, validate_archive
from .numeric_export_inputs import load_inputs
from ..workflows.recording_ingestion import _runtime


def _frozen(value):
    if isinstance(value, dict):
        return MappingProxyType({k:_frozen(v) for k,v in value.items()})
    if isinstance(value, list):
        return tuple(_frozen(v) for v in value)
    return value


@dataclass(frozen=True)
class GenericArchiveDataset:
    summary_sha256: str
    producer_source_sha256: str
    arrays: object
    support: object
    raw_sha256_by_recording: object
    model_admission_authorized: bool = False

    @property
    def geometry_residuals_m(self):
        return self.arrays["residuals_m"]

    @property
    def matched_residuals_m(self):
        result = self.arrays["residuals_m"][self.arrays["conditioned_profile_indices"]]
        result.setflags(write=False)
        return result

    @property
    def conditions(self):
        return self.arrays["conditions"]

    def matched_sequences(self):
        """Yield exact feature/residual pairs, preserving every original reset."""
        indices = self.arrays["conditioned_profile_indices"]
        offsets = self.arrays["conditioned_sequence_offsets"]
        for start, stop in zip(offsets[:-1], offsets[1:]):
            selected = indices[start:stop]
            y = self.arrays["residuals_m"][selected]
            y.setflags(write=False)
            yield y, self.conditions[start:stop], selected

    def require_model_admission(self):
        raise RegistryError("generic_dataset_engineering_only_no_model_admission")


def load_generic_archive(arguments, *, checkpoint=lambda: None):
    """Use the actual standalone validator, binding readiness to its producer.

    The accepted historic producer and this installed consumer's own release
    are supported. Metadata cannot add an arbitrary source to this policy.
    No raw path is resolved, statted or opened by this function.
    """
    args = SimpleNamespace(**vars(arguments))
    args.export_directory = Path(args.export_directory)
    summary = read_pinned_summary(args.export_directory, args.expected_summary_sha256, checkpoint=checkpoint)
    own = _runtime(include_compression=True)["runtime_source_sha256"]
    producer = summary["runtime_source_sha256"]
    require(producer in {ACCEPTED_NUMERIC_PRODUCER, own}, "generic_numeric_producer_not_supported")
    context = load_inputs(args, checkpoint, export_source_sha256=producer)
    summary, arrays = validate_archive(args.export_directory, args.expected_summary_sha256, context, checkpoint=checkpoint)
    context.unchanged(checkpoint)
    # Advanced indexing must never choose a different population for a model.
    require(arrays["residuals_m"].shape[1:] == (21,) and arrays["conditions"].shape[1:] == (6,))
    return GenericArchiveDataset(args.expected_summary_sha256, producer, MappingProxyType(arrays),
        _frozen(summary["support"]), MappingProxyType({r["recording_id"]: r["raw_sha256"] for r in summary["recordings"]}))
