"""Raw-free development access bound to an original lock and explicit ancestry.

Never recompute a split against a later registry. Every intermediate snapshot
must be supplied with its external digest, strictly replay and preserve the
previous snapshot's objects and ordered event prefix.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ..domain import generic_cohort as policy
from ..domain.artifact_registry import digest, require, MAX_EVENTS
from . import artifact_registry as registry, generic_cohort as cohort_io
from .numeric_export_inputs import canonical, read_json

REVISION = "v0.19.15-locked-development-descendants-2026-10-20-a1"


@dataclass(frozen=True)
class RegistryCheckpoint:
    directory: Path
    sha256: str


@dataclass(frozen=True)
class LockedContext:
    cohort_sha256: str
    registry_sha256: str
    cohort: dict
    metadata: dict
    objects: dict
    datasets: dict
    original_metadata: dict
    original_objects: dict
    membership: dict
    graph: dict
    readiness_by_raw: dict


def preserve_ancestry(parent, parent_objects, parent_pin, child, child_objects):
    """A parent hash alone cannot prove retained history or immutable objects."""
    require(child["parent_registry_sha256"] == parent_pin, "locked_registry_parent_chain_mismatch")
    n = len(parent["events"])
    require(canonical(child["events"][:n]) == canonical(parent["events"]),
            "locked_registry_event_prefix_not_preserved")
    require(all(child_objects.get(h) == raw for h, raw in parent_objects.items()),
            "locked_registry_objects_not_preserved")


def _metadata_before_arrays(checkpoint, locked, membership, original_metadata, parent, parent_pin):
    """Reject final exposure/identity drift before opening a descendant's arrays.

    Rebuild an early conservative identity/exposure view from hash-checked JSON
    objects, not cached rows. This is a rejection preflight, never an acceptance
    shortcut: the complete ordinary registry validator still runs afterward.
    """
    directory = Path(checkpoint.directory).expanduser().absolute()
    require(not directory.is_symlink() and not (directory / "objects").is_symlink(),
            "locked_registry_directory_symlink")
    metadata, pin, _ = read_json(directory / "registry.json")
    require(pin == digest(checkpoint.sha256), "locked_registry_digest_mismatch")
    require(metadata["parent_registry_sha256"] == parent_pin and
            canonical(metadata["events"][:len(parent["events"])]) == canonical(parent["events"]),
            "locked_registry_parent_chain_or_prefix_mismatch")
    require(type(metadata["events"]) is list and len(metadata["events"]) <= MAX_EVENTS,
            "locked_registry_event_limit")
    store = registry.ObjectStore()
    def value(pin):
        pin = digest(pin)
        store.add(directory / "objects" / pin, pin)
        return registry.decode(store.objects[pin])
    registrations, auths, archives, relationships = {}, {}, {}, []
    for event in metadata["events"]:
        kind = event["kind"]
        if kind in {"registration", "archive"}:
            files = event["files"]
            prefix = "" if kind == "registration" else "registration/"
            reg_pin = files[prefix + "registration.json"]
            registrations[reg_pin] = (value(files[prefix + "source_specification.json"]),
                                       value(reg_pin), reg_pin)
            if kind == "archive":
                auth_pin, summary_pin = files["lineage/authorization.json"], files["numeric/numeric_export.json"]
                auths[auth_pin] = value(auth_pin)
                archives[summary_pin] = value(summary_pin)
        elif kind == "authorization":
            auths[event["sha256"]] = value(event["sha256"])
        elif kind == "relationship":
            relationships.append(event["claim"])
        else:
            require(kind == "cache_observation", "locked_unknown_registry_event")
    for auth in auths.values():
        require(registry.authorization(auth), "locked_registry_authorization_not_adopted")
    rows = registry.policy.build_index(list(registrations.values()), list(auths.items()),
                                       list(archives.items()), relationships, {})
    check_identity_and_final(locked, membership, original_metadata, {"records": rows, "events": metadata["events"]})
    store.unchanged()


def check_identity_and_final(locked, membership, original_metadata, metadata):
    """Late links cannot erase exposure or change the frozen unit of inference."""
    original = policy.identity_components(original_metadata, membership)
    current = policy.identity_components(metadata, membership)
    # Report a broken final embargo before any development-component error.
    for outing in sorted(locked["outings"], key=lambda o: o["cohort_role"] != "final_test"):
        for raw in outing["raw_sha256"]:
            require(raw in current, "locked_scope_raw_missing")
            state = current[raw]
            changed = state["possible_component_sha256"] != original[raw]["possible_component_sha256"]
            bad = changed or state["identity_conflict"] or state["session_link_unresolved"]
            if outing["cohort_role"] == "final_test":
                require(not bad and not state["linked_development_exclusion"],
                        "locked_final_evidence_invalidated_no_reroll")
            # An already-excluded uncertain component is retained as evidence;
            # it cannot become eligible through this descendant consumer.
            if outing["cohort_role"] == "development":
                require(not bad, "locked_development_identity_or_component_changed")
    return current


def load_context(*, cohort_directory, expected_cohort_sha256, original_registry_directory,
                 descendants=()):
    """Replay original selection and every supplied descendant, without raw I/O.

    The caller must retain the external accepted-lock checkpoint and provide all
    later history. This local API cannot discover omitted external snapshots.
    """
    require(type(descendants) in (tuple, list) and len(descendants) <= MAX_EVENTS,
            "locked_explicit_registry_chain_required")
    locked = cohort_io.load_cohort(cohort_directory, expected_cohort_sha256, original_registry_directory)
    require(locked["status"] == "complete" and locked["cohort_lock_created"] is True,
            "locked_successful_original_cohort_required")
    metadata, objects, datasets = registry.load_registry(original_registry_directory, locked["registry_sha256"])
    original_metadata, original_objects = metadata, objects
    declaration, declaration_pin, _ = read_json(Path(cohort_directory) / "session_declaration.json")
    require(declaration_pin == locked["session_declaration_sha256"], "locked_declaration_changed")
    membership = policy.parse_declaration(declaration, {r["raw_sha256"] for r in metadata["records"]})
    manifest, manifest_pin, _ = read_json(Path(cohort_directory) / "cohort_manifest.json")
    require(manifest_pin == locked["manifest_sha256"], "locked_manifest_changed")
    graph = check_identity_and_final(locked, membership, original_metadata, metadata)
    pin, seen = locked["registry_sha256"], {locked["registry_sha256"]}
    for checkpoint in descendants:
        require(type(checkpoint) is RegistryCheckpoint, "locked_checkpoint_type_required")
        child_pin = digest(checkpoint.sha256)
        require(child_pin not in seen, "locked_duplicate_registry_checkpoint")
        _metadata_before_arrays(checkpoint, locked, membership, original_metadata, metadata, pin)
        child, child_objects, child_datasets = registry.load_registry(checkpoint.directory, child_pin)
        preserve_ancestry(metadata, objects, pin, child, child_objects)
        graph = check_identity_and_final(locked, membership, original_metadata, child)
        metadata, objects, datasets, pin = child, child_objects, child_datasets, child_pin
        seen.add(pin)
    return LockedContext(expected_cohort_sha256, pin, locked, metadata, objects, datasets,
                         original_metadata, original_objects, membership, graph, manifest["readiness_by_raw_sha256"])


def require_project_history(context, project_root):
    """Reject a stale branch before a controller can make a new reservation.

    The registry writer also enforces this under its shared lock. Existing
    project snapshots are read strictly, including siblings of the chosen chain.
    """
    inherited = {canonical(event) for event in context.metadata["events"]}
    private = Path(project_root) / "data/catalog/private"
    for marker in sorted(private.rglob("registry.json")):
        header, pin, _ = read_json(marker)
        # Stop on omitted new history before ordinary replay could consume
        # numeric objects belonging to an unselected/final publication.
        require(all(canonical(event) in inherited for event in header["events"]),
                "locked_registry_omits_project_history")
        registry.load_registry(marker.parent, pin)


def preflight_targets(context, raw_sha256):
    """All targets must be development before attempts or reservations exist."""
    require(type(raw_sha256) is list and bool(raw_sha256) and
            len(raw_sha256) == len(set(raw_sha256)), "locked_unique_export_targets_required")
    rows = {raw: o for o in context.cohort["outings"] for raw in o["raw_sha256"]}
    records = {r["raw_sha256"]: r for r in context.metadata["records"]}
    components = set()
    for raw in raw_sha256:
        digest(raw)
        require(raw in rows and rows[raw]["cohort_role"] == "development",
                "locked_export_target_not_development")
        state = context.graph[raw]
        require(not state["identity_conflict"] and not state["session_link_unresolved"],
                "locked_export_identity_unresolved")
        component = state["possible_component_sha256"]
        require(component not in components, "locked_duplicate_export_component")
        components.add(component)
        linked = [r for r in records.values() if context.graph[r["raw_sha256"]]["possible_component_sha256"] == component]
        require(not any(r["complete_publication_observed"] for r in linked),
                "locked_target_already_published_reuse_archive")
        require(not any(r["inconclusive_numeric_attempt_sha256"] for r in linked),
                "locked_prior_attempt_requires_reviewed_recovery")
    return tuple(rows[raw]["outing_id"] for raw in raw_sha256)


def readiness_files(context, raw):
    """Return exact original selected lineage, never a newer 'best' report.

    Frozen exports operate on whole registrations. This initial controller
    deliberately requires one raw per registration, preventing hidden export of
    an unrelated/final row through a multi-recording predecessor.
    """
    require(raw in context.readiness_by_raw, "locked_readiness_raw_outside_scope")
    # The external manifest was already pinned and replayed by load_cohort.
    candidates = []
    for event in context.original_metadata["events"]:
        if event["kind"] == "registration":
            reports = {r["role"]: r["sha256"] for r in event["reports"]}
            if not {"inventory", "decode", "readiness"} <= set(reports):
                continue
            files = {"registration/registration.json": event["files"]["registration.json"],
                     "registration/source_specification.json": event["files"]["source_specification.json"],
                     **{role + ".json": reports[role] for role in ("inventory", "decode", "readiness")}}
        elif event["kind"] == "archive":
            source = event["files"]
            files = {name: source[name] for name in ("registration/registration.json", "registration/source_specification.json")}
            files.update({role + ".json": source["lineage/" + role + ".json"] for role in ("inventory", "decode", "readiness")})
        else:
            continue
        registration = registry.decode(context.original_objects[files["registration/registration.json"]])
        if raw not in {r["raw_sha256"] for r in registration["recordings"]}:
            continue
        # The selected readiness pin is stored in the original cohort manifest,
        # not in its derived support rows (see selection populated below).
        if files["readiness.json"] != context.readiness_by_raw[raw]:
            continue
        require(len(registration["recordings"]) == 1, "locked_single_recording_export_required")
        if files not in candidates:
            candidates.append(files)
    require(len(candidates) == 1, "locked_exact_original_readiness_lineage_required")
    return candidates[0]


@dataclass(frozen=True)
class DescendantDataset(cohort_io.CohortDataset):
    registry_sha256: str


def load_development_dataset(*, archive_sha256, **context_arguments):
    """Read matched rows/resets from an explicit descendant, never grant a fit."""
    context = load_context(**context_arguments)
    require(type(archive_sha256) is list and bool(archive_sha256) and
            len(archive_sha256) == len(set(archive_sha256)), "locked_unique_archives_required")
    rows = {raw: o for o in context.cohort["outings"] for raw in o["raw_sha256"]}
    archives, sessions, seen, components = [], {}, set(), set()
    for pin in archive_sha256:
        digest(pin)
        require(pin in context.datasets, "locked_archive_missing")
        archive = context.datasets[pin]
        raw_list = list(archive.raw_sha256_by_recording.values())
        require(len(raw_list) == len(set(raw_list)) and not seen.intersection(raw_list),
                "locked_duplicate_raw_alias_in_dataset")
        require(all(raw in rows and rows[raw]["cohort_role"] == "development" for raw in raw_list),
                "locked_archive_not_development")
        labels = {rows[raw]["session_id_private"] for raw in raw_list}
        require(len(labels) == 1, "locked_single_session_archive_required")
        for raw in raw_list:
            component = context.graph[raw]["possible_component_sha256"]
            require(component not in components, "locked_duplicate_possible_component_in_dataset")
            components.add(component)
        seen.update(raw_list)
        archives.append(archive)
        sessions[pin] = next(iter(labels))
    selected_sessions = set(sessions.values())
    require({raw for raw, row in rows.items() if row["session_id_private"] in selected_sessions} == seen,
            "locked_complete_session_archive_coverage_required")
    return DescendantDataset(context.cohort_sha256, tuple(archives), MappingProxyType(sessions), context.registry_sha256)
