"""Content-addressed, self-contained private snapshots of immutable evidence."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time

from ..domain import artifact_registry as policy, numeric_export as numeric
from .numeric_export_inputs import _registration, read_bytes, read_json, canonical, equal
from .generic_dataset import load_generic_archive, _frozen
from ..workflows.recording_ingestion import _runtime

require, keys, digest = policy.require, policy.keys, policy.digest
REGISTRATION_FILES = {"registration.json", "source_specification.json"}
ARCHIVE_FILES = {"registration/registration.json", "registration/source_specification.json",
    "lineage/inventory.json", "lineage/decode.json", "lineage/readiness.json", "lineage/authorization.json",
    "lineage/validation.json", "numeric/numeric_export.json", "numeric/candidate_audit.json", "numeric/residuals.npz"}
TOPICS = ["/adp/estimated_drive_paths", "/adp/road_lane_map_based", "/adp/odometry"]
ARCHIVE_INPUT_FIELDS = {"registration_directory", "preserved_inventory_report", "preserved_decode_report",
    "preserved_readiness_report", "expected_readiness_sha256", "exposure_authorization",
    "expected_exposure_authorization_sha256", "export_directory", "expected_summary_sha256",
    "validation_receipt", "expected_validation_receipt_sha256"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, "registry_duplicate_json_key")
            result[k] = v
        return result
    def constant(_):
        require(False, "registry_nonfinite_json")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    canonical(value)
    return value


def authorization(value):
    keys(value, numeric.AUTHORIZATION_FIELDS)
    require(value["contract_revision"] == numeric.AUTHORIZATION_REVISION and value["purpose"] == numeric.AUTHORIZATION_PURPOSE,
        "registry_authorization_revision")
    keys(value["attestations"], numeric.ATTESTATIONS)
    require(all(type(v) is bool for v in value["attestations"].values()), "registry_authorization_boolean_required")
    for k in ("registration_sha256", "source_specification_sha256", "preserved_readiness_report_sha256"):
        digest(value[k])
    require(type(value["batch_id"]) is str and bool(value["batch_id"]), "registry_authorization_batch")
    raws = value["authorized_raw_sha256"]
    require(type(raws) is list and 0 < len(raws) <= numeric.MAX_EDP, "registry_authorization_raw_set")
    for raw in raws:
        digest(raw)
    require(raws == sorted(set(raws)), "registry_authorization_raw_set")
    flags = list(value["attestations"].values())
    require(all(flags) or not any(flags), "registry_partial_authorization_preserve_and_reconcile")
    return all(flags)


class ObjectStore:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.states = {}
        self.raw_paths = set()
        self.total = sum(map(len, self.objects.values()))
        self.deadline = time.monotonic()+300

    def watch(self, path, raw, state):
        require(time.monotonic() <= self.deadline, "registry_validation_time_limit")
        h = sha(raw)
        if path in self.states:
            require(self.states[path] == (h, state), "registry_input_changed_before_publication")
        self.states[path] = (h, state)
        require(sum(s[1][2] for s in self.states.values()) <= policy.MAX_TOTAL_BYTES, "registry_total_input_limit")
        return h

    def add(self, path, expected=None):
        path = Path(os.path.abspath(Path(path).expanduser()))
        require(str(path) not in self.raw_paths and not path.name.lower().endswith((".mcap", ".mcap.zst")), "registry_raw_payload_input_forbidden")
        require(not path.is_symlink(), "registry_metadata_symlink_forbidden")
        # Resolve only the candidate's parent; never resolve/stat the registered
        # raw endpoint. This also catches aliases through a symlinked directory.
        require(str(path.parent.resolve()/path.name) not in self.raw_paths, "registry_raw_payload_input_forbidden")
        raw, state = read_bytes(path, policy.MAX_OBJECT_BYTES)
        h = self.watch(path, raw, state)
        if expected is not None:
            require(h == digest(expected), "registry_input_digest_mismatch")
        if h not in self.objects:
            require(self.total + len(raw) <= policy.MAX_TOTAL_BYTES, "registry_total_evidence_limit")
            self.objects[h] = raw
            self.total += len(raw)
        return h

    def unchanged(self):
        for path, (h, before) in self.states.items():
            require(time.monotonic() <= self.deadline, "registry_validation_time_limit")
            raw, after = read_bytes(path, policy.MAX_OBJECT_BYTES)
            require(after == before and sha(raw) == h, "registry_input_changed_before_publication")


def materialize(root, files, objects):
    for name, pin in files.items():
        digest(pin)
        require(pin in objects, "registry_evidence_missing")
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(objects[pin])


def original_receipt(receipt, summary, summary_pin):
    keys(receipt, {"contract_revision", "purpose", "status", "summary_sha256", "artifact_sha256",
        "registration_sha256", "source_specification_sha256", "preserved_inventory_report_sha256",
        "preserved_decode_report_sha256", "preserved_readiness_report_sha256", "exposure_authorization_sha256",
        "runtime_source_sha256", "runtime_versions", "geometric_profile_count", "conditioned_profile_count",
        "raw_opened", "model_admission_authorized", "raw_cache_deletion_authorized"})
    expected = {"contract_revision": numeric.VALIDATION_REVISION,
        "purpose": "validate_development_numeric_archive_without_raw_or_model_admission", "status": "complete",
        "summary_sha256": summary_pin, "artifact_sha256": summary["artifacts_sha256"],
        **{k: summary[k] for k in ("registration_sha256", "source_specification_sha256", "preserved_inventory_report_sha256",
            "preserved_decode_report_sha256", "preserved_readiness_report_sha256", "exposure_authorization_sha256")},
        "geometric_profile_count": summary["support"]["geometric_profile_count"],
        "conditioned_profile_count": summary["support"]["conditioned_profile_count"],
        "raw_opened": False, "model_admission_authorized": False, "raw_cache_deletion_authorized": False}
    equal({k: receipt[k] for k in expected}, expected, "registry_original_validation_receipt_mismatch")
    digest(receipt["runtime_source_sha256"])
    require(type(receipt["runtime_versions"]) is dict and type(receipt["runtime_versions"].get("python")) is str,
        "registry_validation_runtime_missing")


def inconclusive_attempt(summary, registration, reg_pin):
    """Retain a failed attempt as reservation evidence, never as a dataset."""
    keys(summary, numeric.SUMMARY_FIELDS)
    require(summary["contract_revision"] == numeric.REVISION and summary["scientific_policy_revision"] == numeric.REVISION and
        summary["purpose"] == numeric.PURPOSE and summary["status"] == "inconclusive", "registry_numeric_attempt_invalid")
    require(type(summary["failure_code"]) is str and bool(summary["failure_code"]), "registry_numeric_attempt_invalid")
    require(summary["registration_sha256"] == reg_pin and summary["source_specification_sha256"] == registration["source_specification_sha256"],
        "registry_numeric_attempt_identity")
    require(all(summary[k] is False for k in ("roles_assigned", "cohort_lock_created", "model_fitted", "standardizers_fitted",
        "residuals_exported", "numeric_conditions_exported", "physical_input_availability_proven", "reference_independence_proven",
        "raw_cache_deletion_authorized")), "registry_numeric_attempt_scope")
    require(summary["independent_outing_count"] is None and summary["artifacts_sha256"] == {} and
        all(summary[k] is None for k in ("pre_residual_candidate_count", "pre_residual_complete_condition_count",
            "condition_failure_counts", "residual_failure_counts", "support")), "registry_numeric_attempt_scope")
    for key in ("runtime_source_sha256", "preserved_readiness_runtime_source_sha256", "preserved_inventory_report_sha256",
            "preserved_decode_report_sha256", "preserved_readiness_report_sha256", "exposure_authorization_sha256"):
        digest(summary[key])
    require(type(summary["technical_recording_count"]) is int and type(summary["recordings"]) is list and
        len(summary["recordings"]) == summary["technical_recording_count"] == len(registration["recordings"]),
        "registry_numeric_attempt_recordings")
    for row, identity in zip(summary["recordings"], registration["recordings"]):
        keys(row, numeric.RECORDING_FIELDS)
        equal({k:row[k] for k in ("recording_id", "raw_sha256", "size_bytes")},
            {k:identity[k] for k in ("recording_id", "raw_sha256", "size_bytes")}, "registry_numeric_attempt_identity")
        require(row["outcome_exposure"] is None, "registry_numeric_attempt_scope")


def replay(events, objects, checkpoint=lambda: None, *, temporary_parent):
    """Semantic rebuild from pinned objects; the cached index is never authority."""
    require(type(events) is list and len(events) <= policy.MAX_EVENTS, "registry_event_limit")
    registrations, auths, archives, links, cache, datasets, attempts = {}, {}, {}, [], {}, {}, {}
    dataset_bytes = 0
    for event in events:
        checkpoint()
        require(type(event) is dict and type(event.get("kind")) is str, "registry_event_invalid")
        kind = event["kind"]
        if kind in {"registration", "archive"}:
            keys(event, {"kind", "files", "reports"} if kind == "registration" else {"kind", "files"})
            require(type(event["files"]) is dict and set(event["files"]) == (REGISTRATION_FILES if kind == "registration" else ARCHIVE_FILES),
                "registry_artifact_file_set")
            with tempfile.TemporaryDirectory(prefix=".registry-validate-", dir=temporary_parent) as temporary:
                folder = Path(temporary)
                materialize(folder, event["files"], objects)
                registration_dir = folder if kind == "registration" else folder/"registration"
                spec, reg, reg_pin = _registration(registration_dir)
                registrations[reg_pin] = (spec, reg, reg_pin)
                if kind == "registration":
                    require(type(event["reports"]) is list and len(event["reports"]) <= 4)
                    require(len({r["role"] for r in event["reports"]}) == len(event["reports"]), "registry_duplicate_report_role")
                    for report in event["reports"]:
                        keys(report, {"role", "sha256"})
                        require(report["role"] in {"inventory", "decode", "readiness", "numeric_attempt"})
                        digest(report["sha256"])
                        require(report["sha256"] in objects, "registry_evidence_missing")
                        data = decode(objects[report["sha256"]])
                        require(data.get("batch_id") == reg["batch_id"] and data.get("registration_sha256") == reg_pin and
                            data.get("source_specification_sha256") == reg["source_specification_sha256"], "registry_report_lineage_mismatch")
                        require(data.get("status") in {"complete", "inconclusive"}, "registry_report_status")
                        if report["role"] == "numeric_attempt":
                            inconclusive_attempt(data, reg, reg_pin)
                            attempts[report["sha256"]] = data
                else:
                    files = event["files"]
                    summary = decode(objects[files["numeric/numeric_export.json"]])
                    auth = decode(objects[files["lineage/authorization.json"]])
                    require(authorization(auth), "registry_archive_requires_adopted_authorization")
                    auths[files["lineage/authorization.json"]] = auth
                    args = SimpleNamespace(registration_directory=registration_dir,
                        preserved_inventory_report=folder/"lineage/inventory.json", preserved_decode_report=folder/"lineage/decode.json",
                        preserved_readiness_report=folder/"lineage/readiness.json", expected_readiness_sha256=files["lineage/readiness.json"],
                        exposure_authorization=folder/"lineage/authorization.json", expected_exposure_authorization_sha256=files["lineage/authorization.json"],
                        export_directory=folder/"numeric", expected_summary_sha256=files["numeric/numeric_export.json"], topic=TOPICS)
                    dataset = load_generic_archive(args, checkpoint=checkpoint)
                    if args.expected_summary_sha256 not in datasets:
                        dataset_bytes += sum(a.nbytes for a in dataset.arrays.values())
                        require(dataset_bytes <= 512*1024**2, "registry_dataset_memory_limit")
                    original_receipt(decode(objects[files["lineage/validation.json"]]), summary, args.expected_summary_sha256)
                    archives[args.expected_summary_sha256] = summary
                    datasets[args.expected_summary_sha256] = dataset
        elif kind == "authorization":
            keys(event, {"kind", "sha256"})
            digest(event["sha256"])
            require(event["sha256"] in objects, "registry_evidence_missing")
            auth = decode(objects[event["sha256"]])
            require(authorization(auth), "registry_draft_is_not_adopted")
            auths[event["sha256"]] = auth
        elif kind == "relationship":
            keys(event, {"kind", "claim"})
            for pin in event["claim"]["evidence_sha256"]:
                digest(pin)
                require(pin in objects and len(objects[pin]) > 0, "registry_link_evidence_required")
            links.append(event["claim"])
        elif kind == "cache_observation":
            keys(event, {"kind", "raw_sha256", "path_private", "observed_at_utc", "state", "stat_identity"})
            digest(event["raw_sha256"])
            require(type(event["path_private"]) is str and Path(event["path_private"]).is_absolute())
            require(event["state"] in {"absent", "present_unverified", "unavailable"})
            require(type(event["observed_at_utc"]) is str and bool(event["observed_at_utc"]))
            state = event["stat_identity"]
            require(state is None if event["state"] != "present_unverified" else
                type(state) is list and len(state) == 5 and all(type(v) is int and v >= 0 for v in state))
            cache.setdefault(event["raw_sha256"], []).append({k:v for k,v in event.items() if k not in {"kind", "raw_sha256"}})
        else:
            require(False, "registry_unknown_event")
    for auth in auths.values():
        if auth["registration_sha256"] in registrations:
            spec, reg, _ = registrations[auth["registration_sha256"]]
            require(auth["batch_id"] == reg["batch_id"] and auth["source_specification_sha256"] == reg["source_specification_sha256"] and
                auth["authorized_raw_sha256"] == sorted(r["raw_sha256"] for r in reg["recordings"]), "registry_authorization_registration_conflict")
    for summary in attempts.values():
        require(summary["exposure_authorization_sha256"] in auths, "registry_attempt_authorization_missing")
        auth = auths[summary["exposure_authorization_sha256"]]
        equal({k:auth[k] for k in ("batch_id", "registration_sha256", "source_specification_sha256")},
            {k:summary[k] for k in ("batch_id", "registration_sha256", "source_specification_sha256")}, "registry_attempt_authorization_conflict")
        equal(auth["preserved_readiness_report_sha256"], summary["preserved_readiness_report_sha256"], "registry_attempt_authorization_conflict")
    rows = policy.build_index(list(registrations.values()), list(auths.items()), list(archives.items()), links, cache, attempts=list(attempts.items()))
    return rows, datasets


def load_registry(directory, expected_registry_sha256):
    """Self-contained replay remains possible when originals or raw are offline."""
    directory = Path(directory).expanduser().absolute()
    require(directory.is_dir() and not directory.is_symlink() and {p.name for p in directory.iterdir()} == {"registry.json", "objects"},
        "registry_snapshot_file_set")
    metadata, pin, _ = read_json(directory/"registry.json")
    require(pin == digest(expected_registry_sha256), "registry_snapshot_digest_mismatch")
    keys(metadata, {"contract_revision", "parent_registry_sha256", "created_at_utc", "events", "objects_sha256", "records",
        "model_admission_authorized", "roles_assigned", "raw_cache_deletion_authorized", "runtime_source_sha256"})
    digest(metadata["runtime_source_sha256"])
    require(metadata["contract_revision"] == policy.REVISION)
    require(all(metadata[k] is False for k in ("model_admission_authorized", "roles_assigned", "raw_cache_deletion_authorized")))
    if metadata["parent_registry_sha256"] is not None:
        digest(metadata["parent_registry_sha256"])
    names = metadata["objects_sha256"]
    require(type(names) is list and names == sorted(set(names)) and len(names) <= 10*policy.MAX_EVENTS, "registry_object_set")
    folder = directory/"objects"
    require(folder.is_dir() and not folder.is_symlink() and {p.name for p in folder.iterdir()} == set(names), "registry_object_set")
    store = ObjectStore()
    for name in names:
        store.add(folder/digest(name), name)
    def checkpoint():
        require(time.monotonic() <= store.deadline, "registry_validation_time_limit")
    rows, datasets = replay(metadata["events"], store.objects, checkpoint, temporary_parent=directory.parent)
    require(canonical(rows) == canonical(metadata["records"]), "registry_cached_index_does_not_match_evidence")
    store.unchanged()
    return metadata, store.objects, datasets


def _private_output(project, output_directory):
    output = Path(output_directory).expanduser().absolute()
    private = project/"data/catalog/private"
    require(".." not in output.parts and output.is_relative_to(private) and output != private and not os.path.lexists(output),
        "registry_new_private_snapshot_required")
    require(private.resolve() == private and output.parent.resolve() == output.parent, "registry_output_parent_symlink_or_existing")
    return output


def _fsync_directory(folder):
    fd = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _import_evidence_locked(manifest_path, *, project_root, output_directory, previous_directory=None,
        expected_previous_sha256=None, observe_cache=False):
    """Append evidence to a new private snapshot; never modify prior snapshots."""
    project = Path(project_root).expanduser().resolve(strict=True)
    runtime = digest(_runtime(include_compression=True)["runtime_source_sha256"])
    output = _private_output(project, output_directory)
    private = project/"data/catalog/private"
    require(output.is_relative_to(private) and output != private and not os.path.lexists(output), "registry_new_private_snapshot_required")
    import subprocess
    checked = subprocess.run(["git", "-C", str(project), "check-ignore", "--no-index", "--quiet", str(output)], capture_output=True)
    require(checked.returncode == 0, "registry_private_output_must_be_gitignored")
    if previous_directory is None:
        require(expected_previous_sha256 is None, "registry_previous_pin_without_snapshot")
        events, objects = [], {}
    else:
        require(expected_previous_sha256 is not None, "registry_previous_snapshot_pin_required")
        old, objects, _ = load_registry(previous_directory, expected_previous_sha256)
        events = list(old["events"])
    inherited_events = {canonical(event) for event in events}
    store = ObjectStore(objects)
    def checkpoint():
        require(time.monotonic() <= store.deadline, "registry_validation_time_limit")
    require(not Path(manifest_path).name.endswith((".mcap", ".mcap.zst")), "registry_raw_payload_input_forbidden")
    manifest, _, _ = read_json(manifest_path)
    store.add(manifest_path)
    keys(manifest, {"contract_revision", "registrations", "archives", "relationships", "additional_authorizations"})
    require(manifest["contract_revision"] == policy.MANIFEST_REVISION)
    require(all(type(manifest[k]) is list and len(manifest[k]) <= policy.MAX_EVENTS for k in ("registrations", "archives", "relationships", "additional_authorizations")))
    def add(event):
        if event not in events:
            require(len(events) < policy.MAX_EVENTS, "registry_event_limit")
            events.append(event)
    # Learn every declared raw path before reading any supplied report/archive
    # path, including paths belonging to a later archive entry.
    for entry in [*manifest["registrations"], *manifest["archives"]]:
        checkpoint()
        spec, reg, _ = _registration(entry["registration_directory"])
        store.raw_paths.update(r["canonical_path_private"] for r in reg["recordings"])
        store.raw_paths.update(r["local_path_private"] for r in spec["recordings"])
    # Registrations are read before other evidence so raw paths can be excluded.
    for entry in manifest["registrations"]:
        keys(entry, {"registration_directory", "expected_registration_sha256", "reports"})
        folder = Path(entry["registration_directory"]).expanduser().absolute()
        spec, reg, pin = _registration(folder)
        require(pin == digest(entry["expected_registration_sha256"]), "registry_registration_digest_mismatch")
        store.raw_paths.update(r["canonical_path_private"] for r in reg["recordings"])
        store.raw_paths.update(r["local_path_private"] for r in spec["recordings"])
        files = {name: store.add(folder/name, pin if name == "registration.json" else reg["source_specification_sha256"]) for name in sorted(REGISTRATION_FILES)}
        reports = []
        require(type(entry["reports"]) is list)
        for report in entry["reports"]:
            keys(report, {"role", "path", "expected_sha256"})
            reports.append({"role": report["role"], "sha256": store.add(report["path"], report["expected_sha256"])})
        add({"kind": "registration", "files": files, "reports": reports})
    for entry in manifest["archives"]:
        keys(entry, ARCHIVE_INPUT_FIELDS)
        folder, numeric_dir = Path(entry["registration_directory"]), Path(entry["export_directory"])
        spec, reg, reg_pin = _registration(folder)
        store.raw_paths.update(r["canonical_path_private"] for r in reg["recordings"])
        store.raw_paths.update(r["local_path_private"] for r in spec["recordings"])
        paths = {"registration/registration.json": (folder/"registration.json", reg_pin),
            "registration/source_specification.json": (folder/"source_specification.json", reg["source_specification_sha256"]),
            "lineage/inventory.json": (entry["preserved_inventory_report"], None),
            "lineage/decode.json": (entry["preserved_decode_report"], None),
            "lineage/readiness.json": (entry["preserved_readiness_report"], entry["expected_readiness_sha256"]),
            "lineage/authorization.json": (entry["exposure_authorization"], entry["expected_exposure_authorization_sha256"]),
            "lineage/validation.json": (entry["validation_receipt"], entry["expected_validation_receipt_sha256"]),
            "numeric/numeric_export.json": (numeric_dir/"numeric_export.json", entry["expected_summary_sha256"]),
            "numeric/candidate_audit.json": (numeric_dir/"candidate_audit.json", None),
            "numeric/residuals.npz": (numeric_dir/"residuals.npz", None)}
        require(not numeric_dir.is_symlink() and {p.name for p in numeric_dir.iterdir()} == {"numeric_export.json", "candidate_audit.json", "residuals.npz"}, "registry_numeric_file_set")
        add({"kind": "archive", "files": {name: store.add(path, expected) for name, (path, expected) in paths.items()}})
    # All currently adopted project authorizations are captured, even unrun/failed.
    authorization_dir = project/"config/private"
    scan_paths = sorted(authorization_dir.rglob("*.json"))
    require(len(scan_paths) <= policy.MAX_EVENTS, "registry_authorization_scan_limit")
    for path in scan_paths:
        # Identify authorization by content too; renaming it must not hide consent.
        raw, state = read_bytes(path, numeric.MAX_SUMMARY_BYTES)
        pin = store.watch(path, raw, state)
        value = decode(raw)
        if (type(value) is dict and (value.get("contract_revision") == numeric.AUTHORIZATION_REVISION or
                value.get("purpose") == numeric.AUTHORIZATION_PURPOSE)) or path.name.startswith("numeric_export_authorization_"):
            store.add(path, pin)
            if authorization(value):
                add({"kind": "authorization", "sha256": pin})
    for entry in manifest["additional_authorizations"]:
        keys(entry, {"path", "expected_sha256"})
        pin = store.add(entry["path"], entry["expected_sha256"])
        if authorization(decode(store.objects[pin])):
            add({"kind": "authorization", "sha256": pin})
    for claim in manifest["relationships"]:
        keys(claim, {"left", "right", "status", "evidence"})
        require(type(claim["evidence"]) is list)
        evidence = []
        for entry in claim["evidence"]:
            keys(entry, {"path", "expected_sha256"})
            evidence.append(store.add(entry["path"], entry["expected_sha256"]))
        add({"kind": "relationship", "claim": {k: claim[k] for k in ("left", "right", "status")} | {"evidence_sha256": evidence}})
    if observe_cache:
        rows, _ = replay(events, store.objects, checkpoint, temporary_parent=private)
        for row in rows:
            for path in row["canonical_paths_private"]:
                try:
                    st = Path(path).lstat()
                    state, identity = "present_unverified", [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]
                except FileNotFoundError:
                    state, identity = "absent", None
                except OSError:
                    state, identity = "unavailable", None
                add({"kind": "cache_observation", "raw_sha256": row["raw_sha256"], "path_private": path,
                    "state": state, "stat_identity": identity, "observed_at_utc": datetime.now(timezone.utc).isoformat()})
    rows, _ = replay(events, store.objects, checkpoint, temporary_parent=private)
    store.unchanged()
    require(scan_paths == sorted(authorization_dir.rglob("*.json")), "registry_authorization_set_changed")
    # A new cold index or update from an older branch must not forget prior consent.
    # The chosen parent is fully replayed above; other snapshots contribute their
    # immutable event history, never their editable cached rows.
    for path in sorted(private.rglob("registry.json")):
        checkpoint()
        existing, _, _ = read_json(path, checkpoint=checkpoint)
        if type(existing) is dict and existing.get("contract_revision") == policy.REVISION:
            require(previous_directory is not None, "registry_previous_required_preserve_existing_history")
            require(type(existing.get("events")) is list and all(canonical(event) in inherited_events for event in existing["events"]),
                "registry_previous_omits_existing_history")
    metadata = {"contract_revision": policy.REVISION, "parent_registry_sha256": expected_previous_sha256,
        "runtime_source_sha256": runtime,
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "events": events, "objects_sha256": sorted(store.objects),
        "records": rows, "model_admission_authorized": False, "roles_assigned": False, "raw_cache_deletion_authorized": False}
    raw = (json.dumps(metadata, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()
    require(len(raw) <= numeric.MAX_SUMMARY_BYTES, "registry_snapshot_size_limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    require(output.parent.resolve() == output.parent and not os.path.lexists(output), "registry_output_parent_symlink_or_existing")
    output.mkdir(mode=0o700)
    (output/"objects").mkdir(mode=0o700)
    def write(path, value):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value); stream.flush(); os.fsync(stream.fileno())
    for pin, value in store.objects.items():
        write(output/"objects"/pin, value)
    for folder in (output/"objects", output, output.parent):
        _fsync_directory(folder)
    store.unchanged()
    require(scan_paths == sorted(authorization_dir.rglob("*.json")), "registry_authorization_set_changed")
    require(_runtime(include_compression=True)["runtime_source_sha256"] == runtime, "registry_runtime_source_changed")
    write(output/"registry.json", raw)  # commit marker is installed last
    for folder in (output, output.parent):
        _fsync_directory(folder)
    return metadata, sha(raw)


def import_evidence(manifest_path, *, project_root, output_directory, previous_directory=None,
        expected_previous_sha256=None, observe_cache=False):
    """Serialize project writers; a cold rebuild cannot erase earlier exclusions."""
    import fcntl
    import subprocess
    project = Path(project_root).expanduser().resolve(strict=True)
    private = project/"data/catalog/private"
    output = _private_output(project, output_directory)
    require(subprocess.run(["git", "-C", str(project), "check-ignore", "--no-index", "--quiet", str(output)],
        capture_output=True).returncode == 0, "registry_private_output_must_be_gitignored")
    require(private.resolve() == private, "registry_private_root_symlink")
    private.mkdir(parents=True, exist_ok=True)
    fd = os.open(private/".registry-write.lock", os.O_RDWR | os.O_CREAT | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_NONBLOCK",0), 0o600)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), "registry_lock_regular_file_required")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise policy.RegistryError("registry_another_import_running")
        return _import_evidence_locked(manifest_path, project_root=project, output_directory=output,
            previous_directory=previous_directory, expected_previous_sha256=expected_previous_sha256, observe_cache=observe_cache)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class GenericDatasetCollection:
    registry_sha256: str
    archives: tuple
    session_state_by_raw: object
    model_admission_authorized: bool = field(default=False, init=False)

    def require_model_admission(self):
        raise policy.RegistryError("generic_dataset_engineering_only_no_model_admission")


def load_registry_dataset(directory, expected_registry_sha256, archive_sha256):
    metadata, _, datasets = load_registry(directory, expected_registry_sha256)
    require(type(archive_sha256) in (list, tuple) and len(archive_sha256) > 0 and len(set(archive_sha256)) == len(archive_sha256),
        "registry_explicit_unique_archive_selection_required")
    rows = {r["raw_sha256"]: r for r in metadata["records"]}
    selected, seen = [], set()
    for pin in archive_sha256:
        digest(pin)
        require(pin in datasets, "registry_archive_not_present")
        dataset = datasets[pin]
        raws = set(dataset.raw_sha256_by_recording.values())
        require(not seen.intersection(raws), "registry_duplicate_raw_in_dataset")
        require(not any(rows[h]["session_link_conflict"] for h in raws), "registry_dataset_session_conflict")
        require(all(rows[h]["permanent_development_reservation"] and rows[h]["complete_publication_observed"] for h in raws),
            "registry_dataset_exposure_conflict")
        seen.update(raws)
        selected.append(dataset)
    state_fields = ("session_link_unresolved", "session_link_conflict", "session_evidence_absent",
        "declared_physical_session_ids", "source_declared_physical_session_ids")
    return GenericDatasetCollection(expected_registry_sha256, tuple(selected),
        _frozen({h:{k:rows[h][k] for k in state_fields} for h in sorted(seen)}))
