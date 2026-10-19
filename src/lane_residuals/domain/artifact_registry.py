"""Private evidence-index policy. No cohort roles, training or raw retirement."""

from collections import defaultdict
import hashlib
import json
import re

REVISION = "v0.19.13-private-artifact-registry-2026-10-18"
MANIFEST_REVISION = "v0.19.13-private-registry-import-2026-10-18"
ACCEPTED_NUMERIC_PRODUCER = "45f1f96fb3709fb9a41a482374aecc5c8453cd1a315cd5bb2b4c693fbd3d3bdf"
# Durable compatibility policy: never accept an unreviewed installed release
# merely because its fingerprint happens to equal an archive's producer today.
REVIEWED_NUMERIC_PRODUCERS = (ACCEPTED_NUMERIC_PRODUCER,)
MAX_EVENTS = 10_000
MAX_OBJECT_BYTES = 256 * 1024**2
MAX_TOTAL_BYTES = 1024**3


class RegistryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code="registry_invalid"):
    if not condition:
        raise RegistryError(code)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names), "registry_fields_invalid")


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "registry_digest_invalid")
    return value


def node(value):
    require(type(value) is str, "registry_node_invalid")
    if value.startswith("raw:"):
        digest(value[4:])
    else:
        require(value.startswith("session:") and re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", value[8:]) is not None,
            "registry_node_invalid")
    return value


class Components:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            next_item = self.parent[item]
            self.parent[item] = root
            item = next_item
        return root

    def join(self, left, right):
        left, right = self.find(left), self.find(right)
        self.parent[max(left, right)] = min(left, right)


def build_index(registrations, authorizations, archives, relationships, cache, *, attempts=()):
    """Rebuild disposable rows from pinned evidence, retaining every reservation.

    Potential links conservatively carry exclusion. Only confirmed links carry
    declared session identity. Neither creates an admitted independent outing.
    """
    records = {}
    declaration_links = []
    locator_groups = defaultdict(lambda: defaultdict(set))
    def record(raw):
        digest(raw)
        return records.setdefault(raw, {"raw_sha256": raw, "size_bytes": None,
            "registration_aliases": [], "source_locators": [], "canonical_paths_private": [],
            "authorization_sha256": [], "complete_archive_sha256": [],
            "inconclusive_numeric_attempt_sha256": [],
            "permanent_development_reservation": False, "complete_publication_observed": False})
    for entry in registrations:
        spec, registration, pin = entry
        for identity, declaration in zip(registration["recordings"], spec["recordings"]):
            value = record(identity["raw_sha256"])
            require(value["size_bytes"] in (None, identity["size_bytes"]), "registry_raw_identity_conflict")
            value["size_bytes"] = identity["size_bytes"]
            alias = {"registration_sha256": pin, "batch_id": registration["batch_id"],
                "recording_id": identity["recording_id"]}
            if alias not in value["registration_aliases"]:
                value["registration_aliases"].append(alias)
            path = identity["canonical_path_private"]
            if path not in value["canonical_paths_private"]:
                value["canonical_paths_private"].append(path)
            locator = declaration["source"]
            if locator not in value["source_locators"]:
                value["source_locators"].append(locator)
            for key in ("source_recording_id_private", "source_locator_private"):
                if locator.get(key) is not None:
                    exact = json.dumps(locator[key], sort_keys=True, allow_nan=False, separators=(",", ":"))
                    locator_groups[key, exact][identity["raw_sha256"]].add(registration["source_specification_sha256"])
            # A pre-existing session declaration is evidence of a possible link,
            # never an independent-outing admission. Do not ignore it at import.
            if locator.get("physical_session_id_private") is not None:
                declaration_links.append({"left": "raw:"+identity["raw_sha256"],
                    "right": "session:source-declared-"+hashlib.sha256(locator["physical_session_id_private"].encode("utf-8")).hexdigest(),
                    "status": "unresolved",
                    "evidence_sha256": [registration["source_specification_sha256"]]})
    for group in locator_groups.values():
        # A spanning star is sufficient and avoids quadratic alias expansion.
        # These possible raw links carry exclusion, never a session identity.
        raws = sorted(group)
        for raw in raws[1:]:
            declaration_links.append({"left":"raw:"+raws[0], "right":"raw:"+raw,
                "status":"unresolved", "evidence_sha256":sorted(group[raws[0]] | group[raw])})
    for pin, auth in authorizations:
        for raw in auth["authorized_raw_sha256"]:
            value = record(raw)
            value["permanent_development_reservation"] = True
            if pin not in value["authorization_sha256"]:
                value["authorization_sha256"].append(pin)
    for pin, summary in archives:
        for identity in summary["recordings"]:
            value = record(identity["raw_sha256"])
            require(value["permanent_development_reservation"], "registry_archive_without_reservation")
            require(summary["exposure_authorization_sha256"] in value["authorization_sha256"], "registry_archive_authorization_conflict")
            value["complete_publication_observed"] = True
            if pin not in value["complete_archive_sha256"]:
                value["complete_archive_sha256"].append(pin)
    for pin, summary in attempts:
        for identity in summary["recordings"]:
            value = record(identity["raw_sha256"])
            require(summary["exposure_authorization_sha256"] in value["authorization_sha256"], "registry_attempt_without_reservation")
            if pin not in value["inconclusive_numeric_attempt_sha256"]:
                value["inconclusive_numeric_attempt_sha256"].append(pin)
    confirmed, potential, session_aliases = Components(), Components(), Components()
    unresolved, explicit_conflicts = set(), set()
    for link in [*declaration_links, *relationships]:
        keys(link, {"left", "right", "status", "evidence_sha256"})
        left, right = node(link["left"]), node(link["right"])
        require(left != right and link["status"] in {"confirmed", "unresolved", "conflicting"}, "registry_link_invalid")
        require(type(link["evidence_sha256"]) is list and bool(link["evidence_sha256"]), "registry_link_evidence_required")
        for h in link["evidence_sha256"]:
            digest(h)
        for endpoint in (left, right):
            if endpoint.startswith("raw:"):
                record(endpoint[4:])
        potential.join(left, right)
        if link["status"] == "confirmed":
            confirmed.join(left, right)
            if left.startswith("session:") and right.startswith("session:"):
                session_aliases.join(left, right)
        elif link["status"] == "unresolved":
            unresolved.update((left, right))
        else:
            explicit_conflicts.update((left, right))
    sessions = defaultdict(set)
    for n in tuple(confirmed.parent):
        if n.startswith("session:"):
            sessions[confirmed.find(n)].add(n)
    reserved_components = {potential.find("raw:"+h) for h, r in records.items()
        if r["permanent_development_reservation"] or r["complete_publication_observed"]}
    uncertain_components = {potential.find(n) for n in unresolved}
    conflict_components = {potential.find(n) for n in explicit_conflicts}
    source_sessions = {raw: sorted({s["physical_session_id_private"] for s in value["source_locators"]
        if s.get("physical_session_id_private") is not None}) for raw, value in records.items()}
    conflict_components.update(potential.find("raw:"+raw) for raw, names in source_sessions.items() if len(names) > 1)
    session_evidence_components = {potential.find(n) for n in tuple(potential.parent) if n.startswith("session:")}
    for raw, value in sorted(records.items()):
        n = "raw:"+raw
        names = sorted(sessions[confirmed.find(n)])
        conflicting_identity = len({session_aliases.find(s) for s in names}) > 1
        possible = potential.find(n)
        value.update(declared_physical_session_ids=[s[8:] for s in names],
            source_declared_physical_session_ids=source_sessions[raw],
            session_link_unresolved=possible in uncertain_components,
            session_link_conflict=conflicting_identity or possible in conflict_components,
            session_evidence_absent=possible not in session_evidence_components,
            linked_development_exclusion=possible in reserved_components,
            independent_outing_admitted=False, cohort_role=None, model_admission_authorized=False,
            final_candidate_authorized=False, raw_cache_deletion_authorized=False,
            exact_byte_retrieval_verified=False,
            raw_cache_observations=cache.get(raw, []))
        value["final_candidate_status"] = ("excluded_development" if value["linked_development_exclusion"] else
            "blocked_session_conflict" if value["session_link_conflict"] else
            "blocked_unresolved_session" if value["session_link_unresolved"] or not names else "not_admitted")
    return [records[h] for h in sorted(records)]
