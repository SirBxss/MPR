"""Pinned, raw-free cohort intake above immutable generic registry evidence."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from types import MappingProxyType, SimpleNamespace
from typing import Any

from ..domain import generic_cohort as policy, numeric_export as numeric
from ..domain.artifact_registry import digest, keys, require
from ..domain.recording_ingestion import source_declaration_status
from . import artifact_registry as registry
from .bounded_recording_readiness import TOPIC_ROLES
from .numeric_export_inputs import (READINESS_FIELDS, INHERITED_FIELDS, _registration,
                                   scientific_shape, execution_observations, equal, read_json, canonical)
from ..workflows import bounded_recording_readiness as bounded
from ..workflows.recording_ingestion import _runtime

COHORT_NAME = "cohort.json"
FILES = {COHORT_NAME, "cohort_manifest.json", "session_declaration.json"}
TOPICS = sorted(bounded.TOPIC_LIMITS)


def _validate_readiness(folder: Path, expected_raw: str) -> dict:
    """Replay complete count evidence and frozen predecessors, without consent.

    This intentionally does not call numeric load_inputs or manufacture numeric
    authorization. It reuses its strict shape and bounded-predecessor validators.
    """
    spec, registration, reg_pin = _registration(folder / "registration")
    args = SimpleNamespace(registration_directory=folder / "registration", topic=TOPICS,
        preserved_inventory_report=folder / "inventory.json", preserved_decode_report=folder / "decode.json")
    inventories, decodes, inv_pin, decode_pin = bounded._predecessors(args, registration, reg_pin, spec, TOPICS)
    ready, _, _ = read_json(folder / "readiness.json")
    keys(ready, READINESS_FIELDS)
    expected = {"contract_revision": bounded.REVISION,
        "scientific_adapter_revision": bounded.REVISION,
        "purpose": "development_only_bounded_recording_readiness", "status": "complete",
        "batch_id": registration["batch_id"], "registration_sha256": reg_pin,
        "source_specification_sha256": registration["source_specification_sha256"],
        "preserved_inventory_report_sha256": inv_pin, "preserved_decode_report_sha256": decode_pin,
        "reader_implementation": bounded.decoder.READER_IMPLEMENTATION, "selected_topics": TOPICS,
        "selected_chunk_crc_validation_enabled": True, "technical_recording_count": len(registration["recordings"]),
        "independent_outing_count": None}
    for key in ("roles_assigned", "cohort_lock_created", "model_fitted", "residual_profiles_constructed",
                "numeric_conditions_exported", "physical_input_availability_proven", "reference_independence_proven",
                "raw_cache_deletion_authorized"):
        expected[key] = False
    equal({k: ready[k] for k in expected}, expected, "cohort_readiness_contract_mismatch")
    require(ready["runtime_source_sha256"] in (numeric.ACCEPTED_READINESS_SOURCE, *registry.policy.REVIEWED_NUMERIC_PRODUCERS),
            "cohort_readiness_producer_not_reviewed")
    limits = bounded._limits()
    bounded._evidence_metadata(ready, {k: v for k, v in limits.items() if k != "process_address_space_soft_limit_bytes"})
    require(ready["resources_at_start"]["mem_available_bytes"] >= limits["minimum_mem_available_bytes"] and
            ready["resources_at_start"]["scratch_free_bytes"] >= limits["minimum_initial_scratch_free_bytes"],
            "cohort_readiness_resource_evidence_invalid")
    require(type(ready["recordings"]) is list and len(ready["recordings"]) == len(registration["recordings"]),
            "cohort_readiness_recording_count")
    supports, availability = {}, []
    for row, identity, declaration, inventory, decode in zip(ready["recordings"], registration["recordings"],
                                                           spec["recordings"], inventories, decodes):
        keys(row, INHERITED_FIELDS)
        equal({k: row[k] for k in ("recording_id", "raw_sha256", "size_bytes")},
              {k: identity[k] for k in ("recording_id", "raw_sha256", "size_bytes")})
        equal(row["source_declaration_status"], source_declaration_status(declaration["source"]))
        equal((row["status"], row["failure_code"], row["invalidation_codes"], row["reader_failure_context"]),
              ("complete", None, [], None))
        equal(row["stream_integrity"], decode["decode_check"])
        _, channels, totals = bounded._advertised_selection(inventory["inventory"], TOPICS)
        bindings = row["binding_observations"]
        require(type(bindings) is list and len(bindings) == len(channels), "cohort_binding_count")
        equal([(b["topic"], b["channel_id"]) for b in bindings], sorted((r["topic"], i) for i, r in channels.items()))
        for binding in bindings:
            keys(binding, {"topic", "role", "channel_id", "schema_id", "message_file_descriptor_sha256",
                           "binding_status", "binding_failure_code"})
            equal(binding["schema_id"], channels[binding["channel_id"]]["schema_id"])
            equal(binding["role"], TOPIC_ROLES[binding["topic"]])
            digest(binding["message_file_descriptor_sha256"])
            if binding["role"] != "odometry" or binding["binding_status"] == "supported":
                equal((binding["binding_status"], binding["binding_failure_code"]), ("supported", None))
            else:
                require(binding["binding_status"] == "unsupported" and binding["binding_failure_code"] in
                        {"odometry_schema_or_encoding_mismatch", "odometry_descriptor_fields_unsupported"})
        science = row["readiness"]
        scientific_shape(science, totals)
        execution_observations(row["execution_observations"])
        odometry = science["odometry"]
        available = (odometry["message_count"] > 0 and not odometry["failure_counts"] and
                     len(odometry["schema_counts"]) == 1 and
                     not any(b["role"] == "odometry" and b["binding_status"] != "supported" for b in bindings))
        equal(row["recorded_input_causality_checked"], available)
        equal(row["condition_availability"], "available_for_checks" if available else "unavailable_odometry")
        availability.append(available)
        clock = science["source_clock_order"]["estimate"]
        complete = science["complete_condition_support"]
        if not available:
            equal(complete["frame_count"], 0)
        # The inherited path-conversion policy rejects unavailable estimator
        # states. These two outcomes are the pre-anchor H100 candidate surface.
        topology = {name: values["outcome_counts"].get("anchored_h100_ready", 0) +
                    values["outcome_counts"].get("anchor_distance_exceeds_1m_or_invalid", 0)
                    for name, values in science["diagnostics"]["pair_outcomes_by_estimate_topology"].items()}
        equal(sum(topology.values()), science["counts"]["h100_pair_count"], "cohort_h100_topology_counts_incomplete")
        raw_usable = available and all(totals[t] > 0 for t in TOPICS) and clock["message_count"] > 0 and all(
            clock[k] == 0 for k in ("missing_timestamp_count", "backward_step_count", "repeated_adjacent_timestamp_count"))
        supports[identity["raw_sha256"]] = {
            "raw_usable": raw_usable, "source_start_ns": int(clock["minimum_timestamp_ns_decimal"] or "0"),
            "source_stop_ns": int(clock["maximum_timestamp_ns_decimal"] or "0"),
            "complete_frame_count": complete["frame_count"], "complete_sequence_count": complete["sequence_count"],
            "complete_transition_count": complete["transition_count"],
            "topology_candidate_count": sum(topology.values()),
            "non_sensor_topology_candidate_count": sum(n for name, n in topology.items() if name != policy.EXPECTED_TOPOLOGY_SOURCE)}
    equal(ready["recorded_input_causality_checked_for_all_recordings"], all(availability))
    require(expected_raw in supports, "cohort_readiness_does_not_cover_raw")
    return supports[expected_raw]


def readiness_support(metadata: dict, objects: dict, selections: dict, temporary_parent: Path) -> dict:
    """Select explicit registry-held reports; a failed predecessor is never replaced."""
    candidates = {}
    for event in metadata["events"]:
        if event["kind"] == "registration":
            reports = {r["role"]: r["sha256"] for r in event["reports"]}
            if not {"inventory", "decode", "readiness"} <= set(reports):
                continue
            files = {"registration/registration.json": event["files"]["registration.json"],
                "registration/source_specification.json": event["files"]["source_specification.json"],
                **{role + ".json": reports[role] for role in ("inventory", "decode", "readiness")}}
        elif event["kind"] == "archive":
            f = event["files"]
            files = {"registration/registration.json": f["registration/registration.json"],
                "registration/source_specification.json": f["registration/source_specification.json"],
                **{role + ".json": f["lineage/" + role + ".json"] for role in ("inventory", "decode", "readiness")}}
        else:
            continue
        reg = registry.decode(objects[files["registration/registration.json"]])
        for row in reg["recordings"]:
            raw = row["raw_sha256"]
            if selections.get(raw) == files["readiness.json"]:
                if raw in candidates:
                    equal(candidates[raw], files, "cohort_ambiguous_readiness_lineage")
                candidates[raw] = files
    require(set(candidates) == set(selections), "cohort_selected_readiness_not_in_registry")
    result = {}
    for raw, files in candidates.items():
        with tempfile.TemporaryDirectory(prefix=".cohort-readiness-", dir=temporary_parent) as temporary:
            root = Path(temporary)
            registry.materialize(root, files, objects)
            result[raw] = _validate_readiness(root, raw)
    return result


def _inputs(registry_directory: Path, expected_registry_sha256: str, declaration_path: Path,
            expected_declaration_sha256: str, manifest_path: Path, expected_manifest_sha256: str):
    metadata, objects, _ = registry.load_registry(registry_directory, expected_registry_sha256)
    store = registry.ObjectStore()
    store.raw_paths.update(path for r in metadata["records"] for path in r["canonical_paths_private"])
    # Learn specification aliases as well as canonical paths before any supplied
    # declaration/manifest endpoint is statted or opened.
    for event in metadata["events"]:
        if event["kind"] in {"registration", "archive"}:
            key = "source_specification.json" if event["kind"] == "registration" else "registration/source_specification.json"
            spec = registry.decode(objects[event["files"][key]])
            store.raw_paths.update(r["local_path_private"] for r in spec["recordings"])
    d = store.add(declaration_path, expected_declaration_sha256)
    m = store.add(manifest_path, expected_manifest_sha256)
    declaration, manifest = registry.decode(store.objects[d]), registry.decode(store.objects[m])
    policy.parse_manifest(manifest, expected_registry_sha256, d)
    support = readiness_support(metadata, objects, manifest["readiness_by_raw_sha256"], Path(registry_directory).parent)
    result = policy.build_cohort(metadata, declaration, manifest, support,
        registry_pin=expected_registry_sha256, declaration_pin=d, manifest_pin=m)
    return result, store, metadata


@contextmanager
def _writer(project: Path):
    """Share the registry lock so role publication cannot race reservation import."""
    private = project / "data/catalog/private"
    require(private.resolve() == private, "cohort_private_root_symlink")
    private.mkdir(parents=True, exist_ok=True)
    fd = os.open(private / ".registry-write.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), "cohort_regular_lock_required")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise policy.RegistryError("cohort_another_writer_running") from exc
        yield private
    finally:
        os.close(fd)


def create_cohort(*, project_root: Path, registry_directory: Path, expected_registry_sha256: str,
                  session_declaration: Path, expected_session_declaration_sha256: str,
                  cohort_manifest: Path, expected_cohort_manifest_sha256: str,
                  output_directory: Path) -> tuple[dict, str]:
    """Publish a new immutable lock/audit after checking every input and history."""
    project = Path(project_root).expanduser().resolve(strict=True)
    output = registry._private_output(project, output_directory, (registry_directory,))
    require(output != project / "data/catalog/private" and not os.path.lexists(output), "cohort_new_private_output_required")
    import subprocess
    require(subprocess.run(["git", "-C", str(project), "check-ignore", "--no-index", "--quiet", str(output)],
                           capture_output=True).returncode == 0, "cohort_output_must_be_gitignored")
    runtime = _runtime(include_compression=True)["runtime_source_sha256"]
    with _writer(project) as private:
        registry._private_output(project, output, (registry_directory,))
        result, store, old = _inputs(Path(registry_directory), expected_registry_sha256, session_declaration,
            expected_session_declaration_sha256, cohort_manifest, expected_cohort_manifest_sha256)
        # Anchor the registry to this project's entire retained event history.
        # Rebuilding a smaller index in this checkout cannot clear reservations.
        inherited = {canonical(e) for e in old["events"]}
        for marker in sorted(private.rglob("registry.json")):
            other, _, _ = read_json(marker)
            if other.get("contract_revision") == registry.policy.REVISION:
                require(all(canonical(e) in inherited for e in other["events"]), "cohort_registry_omits_project_history")
        for marker in sorted(private.rglob(COHORT_NAME)):
            other, _, _ = read_json(marker)
            require(other.get("contract_revision") != policy.REVISION or not other.get("cohort_lock_created"),
                    "cohort_prior_successful_lock_is_binding")
        result["creator_runtime_source_sha256"] = runtime
        encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(encoded) <= numeric.MAX_SUMMARY_BYTES, "cohort_output_limit")
        store.unchanged()
        registry.load_registry(registry_directory, expected_registry_sha256)
        require(_runtime(include_compression=True)["runtime_source_sha256"] == runtime, "cohort_source_changed")
        output.parent.mkdir(parents=True, exist_ok=True)
        require(output.parent.resolve() == output.parent and not os.path.lexists(output), "cohort_output_appeared_or_symlinked")
        output.mkdir(mode=0o700)
        def write(path, raw):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        write(output / "session_declaration.json", store.objects[expected_session_declaration_sha256])
        write(output / "cohort_manifest.json", store.objects[expected_cohort_manifest_sha256])
        registry._fsync_directory(output)
        registry._fsync_directory(output.parent)
        store.unchanged()
        registry.load_registry(registry_directory, expected_registry_sha256)
        require(_runtime(include_compression=True)["runtime_source_sha256"] == runtime, "cohort_source_changed")
        write(output / COHORT_NAME, encoded)
        registry._fsync_directory(output)
        registry._fsync_directory(output.parent)
        return result, registry.sha(encoded)


def load_cohort(directory: Path, expected_cohort_sha256: str, registry_directory: Path) -> dict:
    """Recompute roles from original pinned evidence rather than trust edited rows."""
    directory = Path(directory).absolute()
    require(not directory.is_symlink() and directory.is_dir() and {p.name for p in directory.iterdir()} == FILES,
            "cohort_exact_file_set_required")
    stored, pin, _ = read_json(directory / COHORT_NAME)
    require(pin == digest(expected_cohort_sha256), "cohort_digest_mismatch")
    digest(stored["creator_runtime_source_sha256"])
    expected, store, _ = _inputs(Path(registry_directory), stored["registry_sha256"], directory / "session_declaration.json",
        stored["session_declaration_sha256"], directory / "cohort_manifest.json", stored["manifest_sha256"])
    expected["creator_runtime_source_sha256"] = stored["creator_runtime_source_sha256"]
    equal(stored, expected, "cohort_cached_roles_or_support_do_not_replay")
    store.unchanged()
    return stored


@dataclass(frozen=True)
class CohortDataset:
    """Snapshot-bound engineering inputs. A later real-fit gate is still required."""
    cohort_sha256: str
    archives: tuple
    session_id_by_archive: Any
    model_admission_authorized: bool = field(default=False, init=False)

    def require_model_admission(self):
        raise policy.RegistryError("cohort_dataset_real_fit_not_authorized")

    def fold(self, *, training_sessions: list[str], validation_sessions: list[str]) -> tuple[tuple, tuple]:
        """Return disjoint complete-outing blocks; fit transforms only downstream."""
        require(type(training_sessions) is list and type(validation_sessions) is list and
                bool(training_sessions) and bool(validation_sessions) and
                len(set(training_sessions)) == len(training_sessions) and
                len(set(validation_sessions)) == len(validation_sessions), "cohort_explicit_unique_fold_sessions_required")
        training, validation = set(training_sessions), set(validation_sessions)
        require(not training & validation, "cohort_fold_session_overlap")
        known = set(self.session_id_by_archive.values())
        require(training | validation == known, "cohort_fold_exact_archive_coverage_required")
        return (tuple(a for a in self.archives if self.session_id_by_archive[a.summary_sha256] in training),
                tuple(a for a in self.archives if self.session_id_by_archive[a.summary_sha256] in validation))


def load_development_dataset(*, cohort_directory: Path, expected_cohort_sha256: str,
                             registry_directory: Path, archive_sha256: list[str]) -> CohortDataset:
    """Read exact matched blocks only from admitted development outings.

    This first adapter is deliberately bound to the lock's registry snapshot.
    Adding exports later needs a reviewed descendant-registry adapter, not a new
    split or a silent replacement of this immutable snapshot binding.
    """
    cohort = load_cohort(cohort_directory, expected_cohort_sha256, registry_directory)
    require(cohort["status"] == "complete", "cohort_not_locked")
    rows = {raw: outing for outing in cohort["outings"] for raw in outing["raw_sha256"]}
    metadata, _, datasets = registry.load_registry(registry_directory, cohort["registry_sha256"])
    require(type(archive_sha256) is list and bool(archive_sha256) and len(set(archive_sha256)) == len(archive_sha256),
            "cohort_unique_archive_selection_required")
    sessions = {}
    for pin in archive_sha256:
        digest(pin)
        require(pin in datasets, "cohort_archive_missing")
        raws = set(datasets[pin].raw_sha256_by_recording.values())
        require(raws <= set(rows), "cohort_archive_outside_frozen_scope")
        require(all(rows[raw]["cohort_role"] == "development" for raw in raws), "cohort_final_or_excluded_archive_forbidden")
        labels = {rows[raw]["session_id_private"] for raw in raws}
        require(len(labels) == 1, "cohort_multisession_archive_requires_separate_adapter")
        sessions[pin] = next(iter(labels))
    collection = registry.load_registry_dataset(registry_directory, cohort["registry_sha256"], archive_sha256)
    graph = policy.identity_components(metadata, {raw: o["session_id_private"] for o in cohort["outings"] for raw in o["raw_sha256"]})
    components = {}
    for archive in collection.archives:
        for raw in archive.raw_sha256_by_recording.values():
            component = graph[raw]["possible_component_sha256"]
            require(component not in components or components[component] == archive.summary_sha256,
                    "cohort_duplicate_possible_recording_component_in_dataset")
            components[component] = archive.summary_sha256
    return CohortDataset(expected_cohort_sha256, collection.archives, MappingProxyType(sessions))
