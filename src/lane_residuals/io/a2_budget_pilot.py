"""Selective reader for the pinned, previously accepted a2 development archives."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import numpy as np
from numpy.lib import format as npformat

from ..domain import artifact_registry as registry_policy, numeric_export as numeric
from ..domain.sequence_dataset import BMW_CONDITION_FEATURE_NAMES
from ..domain.spatial_planner_response import STATIONS_M
from . import artifact_registry as registry, development_experiment as original
from .numeric_export_inputs import read_bytes
from .recording_ingestion import file_state

require = registry_policy.require
IDENTITIES = ("recording_id", "candidate_index", "pair_index", "estimate_message_index",
              "reference_message_index", "estimate_source_time_ns_decimal", "reference_source_time_ns_decimal")
METADATA = ("conditions", "condition_names", "stations_m", "conditioned_profile_indices",
            "conditioned_sequence_offsets")


def value_sha256(value) -> str:
    return hashlib.sha256(original.encoded(value)).hexdigest()


@dataclass(frozen=True)
class Outing:
    outing_id: str
    archive_sha256: str
    archive: Path
    numeric_sha256: str
    profile_count: int
    rows: dict

    @property
    def row_count(self) -> int:
        return len(self.rows["conditioned_profile_indices"])

    @property
    def offsets(self) -> np.ndarray:
        return np.asarray(self.rows["conditioned_sequence_offsets"], dtype=np.int64)


@dataclass(frozen=True)
class PilotInputs:
    experiment_sha256: str
    archive_set_sha256: str
    protected: tuple[Path, ...]
    outer_held: str
    audit: str
    calibration: tuple[Outing, ...]
    audit_outing: Outing


def load_pinned_inputs(project: Path, folder: Path, pin: str, accepted_archive_set: str) -> PilotInputs:
    """Resolve role and blob identity from pinned manifests without opening outcome blobs."""
    folder = original.metadata_path(folder)
    marker, _ = original.pinned_json(folder / "experiment.json", pin)
    require(marker["contract_revision"] == original.REVISION
            and marker["status"] == "complete_matched_development_experiment"
            and marker["protocol"] == original.PROTOCOL
            and marker["final_evaluation_authorized"] is False, "budget_original_experiment_contract")
    request, _ = original.pinned_json(folder / "request.json", marker["request_sha256"])
    original.validate_request(request)
    rows, _ = original.pinned_json(folder / "row_manifest.json", marker["row_manifest_sha256"])
    archives = sorted(marker["archives"], key=lambda entry: entry["outing_id"])
    identities = [{key: entry[key] for key in ("outing_id", "archive_sha256")} for entry in archives]
    ids = [entry["outing_id"] for entry in identities]
    archive_pins = [entry["archive_sha256"] for entry in identities]
    require(len(ids) == len(set(ids)) == len(set(archive_pins)) == 7
            and sorted(archive_pins) == request["archive_sha256"]
            and value_sha256(identities) == registry_policy.digest(accepted_archive_set),
            "budget_accepted_archive_set_mismatch")
    require(marker["folds"] == [
        {"fold_id": "hold_out_" + held, "validation_outing": held,
         "training_outings": [outing for outing in ids if outing != held]} for held in ids
    ], "budget_original_fold_mismatch")
    require(type(rows) is list and [entry["outing_id"] for entry in rows] == ids,
            "budget_original_rows_order_mismatch")

    latest = request["descendants"][-1] if request["descendants"] else {
        "directory": request["original_registry_directory"], "sha256": request["expected_original_registry_sha256"],
    }
    require(latest["sha256"] == marker["latest_registry_sha256"], "budget_registry_pin_mismatch")
    root = original.resolve(project, latest["directory"])
    index, _ = original.pinned_json(root / "registry.json", latest["sha256"])
    require(index["contract_revision"] == registry_policy.REVISION
            and len(index["events"]) <= registry_policy.MAX_EVENTS,
            "budget_original_registry_contract")
    objects = set(index["objects_sha256"])
    archive_events = {}
    for entry in index["events"]:
        if entry["kind"] == "archive":
            files = entry["files"]
            require(set(files) == registry.ARCHIVE_FILES, "budget_archive_file_contract")
            summary_pin = files["numeric/numeric_export.json"]
            if summary_pin in archive_pins:
                require(summary_pin not in archive_events, "budget_archive_event_not_unique")
                archive_events[summary_pin] = files["numeric/residuals.npz"]

    def object_path(digest: str) -> Path:
        require(registry_policy.digest(digest) in objects, "budget_archive_object_unregistered")
        return original.metadata_path(root / "objects" / digest)

    selected = []
    # The outer held object is excluded before resolving or checking any outcome path.
    for entry, row in zip(archives[1:], rows[1:]):
        summary_pin = entry["archive_sha256"]
        require(summary_pin in archive_events, "budget_accepted_archive_event_missing")
        numeric_pin = archive_events[summary_pin]
        summary, _ = original.pinned_json(object_path(summary_pin), summary_pin)
        require(summary["status"] == "complete" and summary["artifacts_sha256"][numeric.ARCHIVE] == numeric_pin,
                "budget_numeric_archive_lineage")
        require(row["archive_sha256"] == summary_pin and 8 <= entry["complete_feature_rows"] <= 20_000
                and entry["complete_feature_rows"] <= entry["geometry_vectors"] <= numeric.MAX_EDP,
                "budget_original_archive_shape")
        require(all(len(row[name]) == entry["complete_feature_rows"] for name in (*IDENTITIES, "conditioned_profile_indices")),
                "budget_original_row_identity_shape")
        ids_in_outing = set(row["recording_id"])
        require(len(ids_in_outing) == 1, "budget_original_single_recording_contract")
        offsets = row["conditioned_sequence_offsets"]
        require(len(offsets) == entry["sequences"] + 1 and offsets[0] == 0
                and offsets[-1] == entry["complete_feature_rows"]
                and all(type(v) is int for v in offsets) and all(b > a for a, b in zip(offsets, offsets[1:])),
                "budget_original_sequence_partition")
        profile_indices = row["conditioned_profile_indices"]
        require(all(type(i) is int and 0 <= i < entry["geometry_vectors"] for i in profile_indices)
                and all(b > a for a, b in zip(profile_indices, profile_indices[1:])),
                "budget_original_conditioned_indices")
        selected.append(Outing(entry["outing_id"], summary_pin, object_path(numeric_pin), numeric_pin,
                               entry["geometry_vectors"], row))
    return PilotInputs(pin, accepted_archive_set, (folder, root), ids[0], ids[-1],
                       tuple(selected[:-1]), selected[-1])


def _read_member(zipped: ZipFile, field: str, expected_shape: tuple[int, ...]) -> np.ndarray:
    info = zipped.getinfo(field + ".npy")
    dtype = np.dtype(numeric.ARRAY_DTYPES[field])
    payload_bytes = math.prod(expected_shape) * dtype.itemsize
    require(info.compress_type in (ZIP_STORED, ZIP_DEFLATED) and not info.flag_bits & 1
            and info.file_size <= payload_bytes + 16_384, "budget_archive_member_bounds")
    with zipped.open(info) as member:
        version = npformat.read_magic(member)
        require(version in ((1, 0), (2, 0)), "budget_archive_npy_version")
        header = npformat.read_array_header_1_0 if version == (1, 0) else npformat.read_array_header_2_0
        shape, fortran, stored_dtype = header(member)
        require(shape == expected_shape and not fortran and stored_dtype == dtype
                and member.tell() + payload_bytes == info.file_size, "budget_archive_npy_schema")
        values = member.read(payload_bytes)
        require(len(values) == payload_bytes and not member.read(1), "budget_archive_npy_payload")
    return np.frombuffer(values, dtype=dtype).reshape(expected_shape)


def open_accepted_outing(spec: Outing, *, labels: bool):
    """Hash only the authorized outing's blob and decode allowlisted NPZ members."""
    raw, state = read_bytes(spec.archive, numeric.MAX_NPZ_BYTES)
    require(hashlib.sha256(raw).hexdigest() == spec.numeric_sha256, "budget_numeric_blob_digest_mismatch")
    expected_shapes = {
        "stations_m": (21,), "condition_names": (6,), "conditions": (spec.row_count, 6),
        "conditioned_profile_indices": (spec.row_count,),
        "conditioned_sequence_offsets": (len(spec.rows["conditioned_sequence_offsets"]),),
        "residuals_m": (spec.profile_count, 21),
        **{name: (spec.profile_count,) for name in IDENTITIES},
    }
    with ZipFile(BytesIO(raw)) as zipped:
        expected = {name + ".npy" for name in numeric.ARRAY_DTYPES}
        require(len(zipped.infolist()) == len(expected) and set(zipped.namelist()) == expected,
                "budget_original_npz_member_set")
        names = (*METADATA, "residuals_m", *IDENTITIES) if labels else METADATA
        arrays = {name: _read_member(zipped, name, expected_shapes[name]) for name in names}
    require(BMW_CONDITION_FEATURE_NAMES[0] == "speed_mps"
            and np.array_equal(arrays["stations_m"], STATIONS_M)
            and arrays["condition_names"].tolist() == list(BMW_CONDITION_FEATURE_NAMES)
            and np.array_equal(arrays["conditioned_profile_indices"], spec.rows["conditioned_profile_indices"])
            and np.array_equal(arrays["conditioned_sequence_offsets"], spec.offsets)
            and np.isfinite(arrays["conditions"]).all(), "budget_numeric_metadata_binding")
    if not labels:
        return arrays["conditions"], state
    indices = arrays["conditioned_profile_indices"]
    require(all(np.array_equal(arrays[name][indices], spec.rows[name]) for name in IDENTITIES)
            and np.isfinite(arrays["residuals_m"]).all(), "budget_labelled_archive_binding")
    archive = SimpleNamespace(arrays=arrays, matched_residuals_m=arrays["residuals_m"][indices],
                              conditions=arrays["conditions"])
    require(file_state(spec.archive) == state, "budget_numeric_archive_changed")
    return original.MatchedBlock(spec.outing_id, archive), state
