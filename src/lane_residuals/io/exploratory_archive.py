"""Read the immutable v0.19.2 batch02 archive without admitting an outing or fitting.

This validator checks recorded evidence and archive structure; it cannot
reconstruct geometry, verify absent raw MCAP bytes, or establish independence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import zipfile

import numpy as np

from ..domain.exploratory_residuals import sequence_layout
from ..domain.residual_dataset import CANONICAL_MODEL_STATIONS_M
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from .independent_outing_intake import read_strict_json_with_bytes

REVISION = "v0.19.2-batch02-exploratory-residuals-2026-09-24-a1"
PUBLISHED_SUMMARY_SHA256 = "64bee5e5970c173aebff3ac1ee265b4be171d81c1e8292a202b48a696319a678"
SUMMARY = "exploratory_residual_summary.json"
AUDIT = "candidate_audit.json"
ARCHIVE = "exploratory_residuals.npz"
LINEAGE = {
    "registration_sha256": "c7fbce82c027afde3b05b7046e68d338657afc85f14ee5bde8ce5cfde392ad6f",
    "container_context_sha256": "b59f89d646349921b7078f05bdb705be7c477bfc20076c9c68fdb3f933729bad",
    "preserved_feasibility_sha256": "89cbeeb89d3939a297f1602a8750663fd6cfa514d3376642053e05754548f9ec",
    "preserved_diagnostics_sha256": "fad94bc2b20715cb8067883c637f1f208f562fc29d4fcc6bd24bd0e0054a6ffb",
    # Fingerprint of the completed extraction implementation, not this reader.
    "runtime_source_sha256": "96a0df813a1a815fdae963e68ceca1563dd1a89653201453164bf12962c82d6c",
}
ARRAY_DTYPES = {
    "stations_m": "float64", "condition_names": "<U48",
    "residuals_m": "float64", "recording_id": "<U16",
    "candidate_index": "int64", "pair_index": "int64",
    "estimate_message_index": "int64", "reference_message_index": "int64",
    "estimate_source_time_ns_decimal": "<U20",
    "reference_source_time_ns_decimal": "<U20",
    "geometry_sequence_offsets": "int64", "conditioned_profile_indices": "int64",
    "conditions": "float64", "conditioned_sequence_offsets": "int64",
}


@dataclass(frozen=True)
class ExploratoryArchive:
    """Recording-local arrays only; technical IDs are not physical drive IDs."""

    arrays: Mapping[str, np.ndarray]
    summary: Mapping[str, object]

    @property
    def conditioned_residuals_m(self) -> np.ndarray:
        return self.arrays["residuals_m"][self.arrays["conditioned_profile_indices"]]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"v0.19.2 archive: {message}")


def _uint64_decimal(value: object) -> str:
    _require(isinstance(value, str) and value.isascii() and value.isdecimal(), "invalid decimal timestamp")
    _require(str(int(value)) == value and int(value) < 2**64, "noncanonical uint64 timestamp")
    return value


def _offsets(offsets: np.ndarray, count: int) -> None:
    _require(offsets.ndim == 1 and len(offsets) >= 1 and offsets[0] == 0 and offsets[-1] == count,
             "invalid sequence offset endpoints")
    _require(np.all(offsets[1:] > offsets[:-1]), "empty or decreasing sequence interval")


def load_exploratory_archive(directory: Path, *,
                             expected_summary_sha256: str = PUBLISHED_SUMMARY_SHA256) -> ExploratoryArchive:
    """Validate complete published files, identities, subset, and temporal support.

    Does not assign physical sessions, standardize, split, or fit a model.
    """
    directory = Path(directory)
    _require(directory.is_dir() and {p.name for p in directory.iterdir()} == {SUMMARY, AUDIT, ARCHIVE},
             "exactly three complete output files required")
    summary, summary_raw = read_strict_json_with_bytes(directory / SUMMARY)
    _require(hashlib.sha256(summary_raw).hexdigest() == expected_summary_sha256,
             "summary differs from the pinned published result")
    audit, audit_raw = read_strict_json_with_bytes(directory / AUDIT)
    archive_raw = (directory / ARCHIVE).read_bytes()
    _require(isinstance(summary, dict) and isinstance(audit, dict), "invalid report objects")
    expected = {"contract_revision": REVISION, "status": "complete",
                "purpose": "exploratory_recording_local_edp_rlmb_residuals_without_outing_admission",
                "physical_session_provenance": "unavailable_owner_report_2026-09-20",
                "independent_outing_count": None, "roles_assigned": False,
                "cohort_lock_created": False, "model_fitted": False,
                "standardizers_fitted": False, "raw_hashes_verified": True,
                "residuals_exported": True, "recorded_input_causality_checked": True,
                "physical_input_availability_proven": False, **LINEAGE}
    for key, value in expected.items():
        _require(type(summary.get(key)) is type(value) and summary[key] == value, f"summary {key} mismatch")
    _require(set(summary.get("artifacts_sha256", {})) == {ARCHIVE, AUDIT}, "artifact hash keys mismatch")
    for name, raw in ((ARCHIVE, archive_raw), (AUDIT, audit_raw)):
        _require(hashlib.sha256(raw).hexdigest() == summary["artifacts_sha256"][name],
                 f"{name} digest mismatch")
    _require(set(audit) == {"contract_revision", "rows"} and audit["contract_revision"] == REVISION
             and isinstance(audit["rows"], list), "audit revision or row list mismatch")
    rows = audit["rows"]
    _require(type(summary.get("candidate_count")) is int and summary["candidate_count"] == len(rows),
             "candidate count mismatch")
    recordings = summary.get("recordings")
    _require(isinstance(recordings, list) and len(recordings) == 4, "four recordings required")
    expected_ids = [f"recording_{i:02d}" for i in range(1, 5)]
    _require([r.get("recording_id") for r in recordings] == expected_ids and all(
        r.get("status") == "complete" and r.get("legacy_counts_match_preserved") is True
        and r.get("diagnostics_match_preserved") is True and r.get("failure_code") is None
        and isinstance(r.get("counts"), dict) for r in recordings), "recording completion/identity mismatch")
    _require(len(rows) == sum(r["counts"]["sensor_anchored_h100_pair_count"] for r in recordings),
             "recording sensor count mismatch")
    failures = Counter()
    residual_failures = Counter()
    previous_id = ""
    for index, row in enumerate(rows):
        _require(isinstance(row, dict) and type(row.get("candidate_index")) is int
                 and row["candidate_index"] == index, "candidate order mismatch")
        rid = row.get("recording_id")
        _require(rid in expected_ids and rid >= previous_id, "audit recording order mismatch")
        previous_id = rid
        for key in ("pair_index", "estimate_message_index", "reference_message_index"):
            _require(type(row.get(key)) is int and 0 <= row[key] < 2**63, f"invalid {key}")
        for key in ("estimate_source_time_ns_private", "reference_source_time_ns_private"):
            _require(type(row.get(key)) is int and 0 <= row[key] < 2**64, f"invalid {key}")
        codes = row.get("condition_failure_codes")
        _require(isinstance(codes, list) and all(isinstance(c, str) for c in codes), "failure codes invalid")
        _require(type(row.get("conditions_available")) is bool and
                 row["conditions_available"] == (not codes), "condition flag mismatch")
        _require(type(row.get("residual_available")) is bool and
                 row["residual_available"] == (row.get("residual_failure_code") is None),
                 "residual flag mismatch")
        failures.update(codes)
        if row["residual_failure_code"] is not None:
            residual_failures.update([row["residual_failure_code"]])
    _require(dict(failures) == summary.get("condition_failure_counts") and
             dict(residual_failures) == summary.get("residual_failure_counts"), "failure counters mismatch")
    for r in recordings:
        _require(sum(row["recording_id"] == r["recording_id"] for row in rows)
                 == r["counts"]["sensor_anchored_h100_pair_count"], "per-record candidate count mismatch")
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as zf:
        _require(set(zf.namelist()) == {k + ".npy" for k in ARRAY_DTYPES}
                 and len(zf.namelist()) == len(ARRAY_DTYPES), "NPZ member mismatch")
    with np.load(io.BytesIO(archive_raw), allow_pickle=False) as stored:
        _require(set(stored.files) == set(ARRAY_DTYPES), "NPZ array keys mismatch")
        arrays = {key: stored[key] for key in ARRAY_DTYPES}
    for key, dtype in ARRAY_DTYPES.items():
        _require(arrays[key].dtype == np.dtype(dtype), f"{key} dtype mismatch")
    n = len(arrays["residuals_m"])
    m = len(arrays["conditions"])
    shapes = {"stations_m": (21,), "condition_names": (6,), "residuals_m": (n, 21),
              "recording_id": (n,), "candidate_index": (n,), "pair_index": (n,),
              "estimate_message_index": (n,), "reference_message_index": (n,),
              "estimate_source_time_ns_decimal": (n,), "reference_source_time_ns_decimal": (n,),
              "conditioned_profile_indices": (m,), "conditions": (m, 6,)}
    _require(all(arrays[key].shape == shape for key, shape in shapes.items()), "array shape mismatch")
    _require(np.array_equal(arrays["stations_m"], CANONICAL_MODEL_STATIONS_M)
             and tuple(arrays["condition_names"]) == BMW_CONDITION_FEATURE_NAMES,
             "grid or condition names mismatch")
    _require(np.all(np.isfinite(arrays["residuals_m"])) and np.all(np.isfinite(arrays["conditions"])),
             "nonfinite residual or condition")
    profiles = [r for r in rows if r["residual_available"]]
    conditioned = [r for r in profiles if r["conditions_available"]]
    _require(n == len(profiles) and m == len(conditioned), "profile/condition counts mismatch")
    for i, row in enumerate(profiles):
        _require(arrays["recording_id"][i] == row["recording_id"], "profile recording mismatch")
        for key in ("candidate_index", "pair_index", "estimate_message_index", "reference_message_index"):
            _require(arrays[key][i] == row[key], f"profile {key} mismatch")
        for side in ("estimate", "reference"):
            key = f"{side}_source_time_ns_decimal"
            _require(_uint64_decimal(arrays[key][i]) == str(row[f"{side}_source_time_ns_private"]),
                     f"{side} timestamp mismatch")
    indices = arrays["conditioned_profile_indices"]
    _require(np.array_equal(indices, np.asarray([i for i, r in enumerate(profiles)
                if r["conditions_available"]], dtype=np.int64)), "condition-to-profile mapping mismatch")
    support = summary.get("support")
    _require(isinstance(support, dict) and support.get("geometric_profile_count") == n
             and support.get("conditioned_profile_count") == m, "support population mismatch")
    for prefix, population, count in (("geometry", profiles, n), ("conditioned", conditioned, m)):
        offsets = arrays[f"{prefix}_sequence_offsets"]
        _offsets(offsets, count)
        expected_offsets, expected_sequences = sequence_layout(population)
        _require(np.array_equal(offsets, expected_offsets)
                 and support[f"{prefix}_sequences"] == expected_sequences
                 and support[f"{prefix}_transition_count"] == sum(
                    sequence["transition_count"] for sequence in expected_sequences),
                 f"{prefix} temporal support mismatch")
    for a in arrays.values():
        a.setflags(write=False)
    return ExploratoryArchive(MappingProxyType(arrays), MappingProxyType(summary))
