"""Outcome-blind generic outing support and permanent-reservation split policy.

Folder/source IDs are private labels. Only an explicit owner declaration asserts
physical membership; raw SHA-256 values still identify exact bytes. This module
does not read files, residuals, features, fit models or grant model admission.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import hashlib
from typing import Any

from .artifact_registry import Components, RegistryError, digest, keys, require
from .independent_outing_intake import (
    EXPECTED_TOPOLOGY_SOURCE, MINIMUM_ELIGIBLE_NEW_OUTING_COUNT,
    OutingEligibilityEvidence, evaluate_outing_eligibility, fixed_final_count,
    outing_fingerprint_sha256, split_score_sha256,
)

REVISION = "v0.19.14-generic-owner-declared-cohort-2026-10-19-a1"
DECLARATION_REVISION = "v0.19.14-owner-session-declaration-2026-10-19-a1"
SPLIT_POLICY = "v0.19.14-v017-content-rank-restricted-to-unexposed-eligible-outings-a1"
EVIDENCE_STATUS = "owner_declared_not_independently_verified"
MAX_OUTINGS = 10_000


def text(value: Any) -> str:
    """Require meaningful bounded text without treating it as a source ID."""
    require(type(value) is str and bool(value.strip()) and len(value) <= 16_384,
            "cohort_nonempty_text_required")
    return value


def parse_declaration(value: dict, known_raws: set[str]) -> dict[str, str]:
    """Validate owner evidence and return raw-to-declared-session membership."""
    keys(value, {"contract_revision", "purpose", "evidence_status", "declaration_text_private",
                 "independence_basis_private", "outings"})
    require(value["contract_revision"] == DECLARATION_REVISION and
            value["purpose"] == "owner_declared_physical_session_membership" and
            value["evidence_status"] == EVIDENCE_STATUS, "cohort_declaration_revision_or_status")
    text(value["declaration_text_private"])
    text(value["independence_basis_private"])
    require(type(value["outings"]) is list and 0 < len(value["outings"]) <= MAX_OUTINGS,
            "cohort_outing_limit")
    result, labels = {}, set()
    for item in value["outings"]:
        keys(item, {"session_id_private", "separate_physical_session", "raw_sha256"})
        label = text(item["session_id_private"])
        require(label not in labels and item["separate_physical_session"] is True,
                "cohort_distinct_session_declaration_required")
        labels.add(label)
        raws = item["raw_sha256"]
        require(type(raws) is list and bool(raws) and raws == sorted(set(raws)),
                "cohort_sorted_unique_raw_membership_required")
        for raw in raws:
            digest(raw)
            require(raw in known_raws and raw not in result, "cohort_unknown_or_duplicate_raw")
            result[raw] = label
    return result


def parse_manifest(value: dict, registry_pin: str, declaration_pin: str) -> list[str]:
    """A fixed prospective raw pool is explicit, complete and independently pinned."""
    keys(value, {"contract_revision", "registry_sha256", "session_declaration_sha256",
                 "scope_raw_sha256", "readiness_by_raw_sha256", "legacy_development_outing_count",
                 "prior_successful_lock_sha256"})
    require(value["contract_revision"] == REVISION and value["registry_sha256"] == digest(registry_pin) and
            value["session_declaration_sha256"] == digest(declaration_pin), "cohort_manifest_lineage")
    scope = value["scope_raw_sha256"]
    require(type(scope) is list and 0 < len(scope) <= MAX_OUTINGS and scope == sorted(set(scope)),
            "cohort_scope_sorted_unique_required")
    require(type(value["readiness_by_raw_sha256"]) is dict and set(value["readiness_by_raw_sha256"]) == set(scope),
            "cohort_exact_readiness_selection_required")
    for raw in scope:
        digest(raw)
        digest(value["readiness_by_raw_sha256"][raw])
    require(type(value["legacy_development_outing_count"]) is int and value["legacy_development_outing_count"] == 1,
            "cohort_legacy_count_fixed")
    # No successful generic lock existed at this version. Supersession needs its
    # own reviewed contract; a caller cannot silently reroll an existing lock.
    require(value["prior_successful_lock_sha256"] is None, "cohort_supersession_not_implemented")
    return scope


def identity_components(metadata: dict, membership: dict[str, str]) -> dict[str, dict]:
    """Keep possible leakage components separate from confirmed identity.

    Exact recording IDs and confirmed links detect cross-raw contradictions.
    Free-text locators stay possible links, never proof of a physical identity.
    Existing exclusion/conflict assertions can only be broadened, never erased.
    """
    rows = {row["raw_sha256"]: row for row in metadata["records"]}
    possible, confirmed = Components(), Components()
    groups = defaultdict(set)
    source_sessions = defaultdict(set)
    for raw, row in rows.items():
        possible.find("raw:" + raw)
        confirmed.find("raw:" + raw)
        for source in row["source_locators"]:
            for field in ("source_recording_id_private", "source_locator_private", "physical_session_id_private"):
                value = source.get(field)
                if value is not None:
                    import json
                    groups[field, json.dumps(value, sort_keys=True, separators=(",", ":"))].add(raw)
            if source.get("physical_session_id_private") is not None:
                source_sessions[raw].add(source["physical_session_id_private"])
    for (field, _), group in groups.items():
        first = min(group)
        for raw in group:
            possible.join("raw:" + first, "raw:" + raw)
            if field == "source_recording_id_private":
                confirmed.join("raw:" + first, "raw:" + raw)
    for event in metadata["events"]:
        if event["kind"] == "relationship":
            claim = event["claim"]
            possible.join(claim["left"], claim["right"])
            if claim["status"] == "confirmed":
                confirmed.join(claim["left"], claim["right"])
    for label in sorted(set(membership.values())):
        group = sorted(raw for raw, name in membership.items() if name == label)
        for raw in group[1:]:
            possible.join("raw:" + group[0], "raw:" + raw)
            confirmed.join("raw:" + group[0], "raw:" + raw)
    owner_by_identity, source_by_identity = defaultdict(set), defaultdict(set)
    possible_members = defaultdict(set)
    for raw in rows:
        component = confirmed.find("raw:" + raw)
        if raw in membership:
            owner_by_identity[component].add(membership[raw])
        source_by_identity[component].update(source_sessions[raw])
        possible_members[possible.find("raw:" + raw)].add(raw)
    conflicts = {possible.find("raw:" + raw) for raw in rows if
                 rows[raw]["session_link_conflict"] or
                 len(owner_by_identity[confirmed.find("raw:" + raw)]) > 1 or
                 len(source_by_identity[confirmed.find("raw:" + raw)]) > 1}
    result = {}
    for group_id, raws in possible_members.items():
        labels = {membership[raw] for raw in raws if raw in membership}
        unknown = any(raw not in membership for raw in raws)
        excluded = any(rows[raw]["linked_development_exclusion"] or
                       rows[raw]["permanent_development_reservation"] or
                       rows[raw]["complete_publication_observed"] for raw in raws)
        component_pin = hashlib.sha256("".join(raw + "\n" for raw in sorted(raws)).encode()).hexdigest()
        for raw in raws:
            result[raw] = {"possible_component_sha256": component_pin, "possible_component_raw_count": len(raws),
                           "identity_conflict": group_id in conflicts,
                           "session_link_unresolved": unknown or len(labels) != 1,
                           "linked_development_exclusion": excluded}
    return result


def build_cohort(metadata: dict, declaration: dict, manifest: dict,
                 support: dict[str, dict], *, registry_pin: str, declaration_pin: str,
                 manifest_pin: str) -> dict:
    """Apply unchanged support thresholds and the versioned exposure-aware draw."""
    scope = parse_manifest(manifest, registry_pin, declaration_pin)
    membership = parse_declaration(declaration, {r["raw_sha256"] for r in metadata["records"]})
    require(set(scope) <= set(membership) and set(support) == set(scope), "cohort_session_or_support_missing")
    # A declared physical outing cannot be cherry-picked by leaving some members
    # outside the frozen scope. Unrelated declared pilot outings remain outside.
    for raw in scope:
        require({r for r, label in membership.items() if label == membership[raw]} <= set(scope),
                "cohort_partial_physical_outing_scope")
    graph = identity_components(metadata, membership)
    outcomes = []
    for label in sorted({membership[raw] for raw in scope}):
        raws = sorted(raw for raw in scope if membership[raw] == label)
        records = [support[raw] for raw in raws]
        intervals = sorted((r["source_start_ns"], r["source_stop_ns"]) for r in records if r["raw_usable"])
        monotonic = all(stop >= start for start, stop in intervals) and all(
            a[1] <= b[0] for a, b in zip(intervals, intervals[1:]))
        frames = sum(r["complete_frame_count"] for r in records if r["raw_usable"])
        sequences = sum(r["complete_sequence_count"] for r in records if r["raw_usable"])
        evidence = OutingEligibilityEvidence(
            raw_usable_recording_count=len(intervals),
            usable_duration_ns=sum(stop - start for start, stop in intervals),
            usable_intervals_monotonic_nonoverlapping=monotonic,
            topology_candidate_count=sum(r["topology_candidate_count"] for r in records),
            non_sensor_topology_candidate_count=sum(r["non_sensor_topology_candidate_count"] for r in records),
            eligible_frame_count=frames, sequence_count=sequences, retained_eligible_frame_count=frames)
        eligible = evaluate_outing_eligibility(evidence)
        failures = list(eligible.failure_codes)
        if any(graph[raw]["identity_conflict"] for raw in raws):
            failures.append("cross_raw_session_identity_conflict")
        if any(graph[raw]["session_link_unresolved"] for raw in raws):
            failures.append("possible_session_or_duplicate_component_unresolved")
        fingerprint = outing_fingerprint_sha256(raws)
        outcomes.append({"session_id_private": label, "raw_sha256": raws,
            "outing_fingerprint_sha256": fingerprint, "split_score_sha256": split_score_sha256(fingerprint),
            "support": asdict(evidence), "failure_codes": failures,
            "technically_eligible": eligible.technically_eligible and not failures,
            "linked_development_exclusion": any(graph[raw]["linked_development_exclusion"] for raw in raws),
            "possible_component_sha256": sorted({graph[raw]["possible_component_sha256"] for raw in raws}),
            "cohort_role": None})
    fingerprints = [o["outing_fingerprint_sha256"] for o in outcomes]
    require(len(fingerprints) == len(set(fingerprints)), "cohort_duplicate_outing_fingerprint")
    for index, item in enumerate(sorted(outcomes, key=lambda o: o["outing_fingerprint_sha256"]), 1):
        item["outing_id"] = f"outing_{index:03d}"
    eligible = [o for o in outcomes if o["technically_eligible"]]
    final_pool = sorted((o for o in eligible if not o["linked_development_exclusion"]),
                        key=lambda o: (o["split_score_sha256"], o["outing_fingerprint_sha256"]))
    count = fixed_final_count(len(eligible))
    status = ("insufficient_independent_outings" if len(eligible) < MINIMUM_ELIGIBLE_NEW_OUTING_COUNT else
              "insufficient_unexposed_final_outings" if len(final_pool) < count else "complete")
    if status == "complete":
        require(2 <= count < len(eligible), "cohort_final_count_invalid")
        final = {o["outing_fingerprint_sha256"] for o in final_pool[:count]}
        for item in outcomes:
            item["cohort_role"] = ("excluded" if not item["technically_eligible"] else
                                   "final_test" if item["outing_fingerprint_sha256"] in final else "development")
    return {"contract_revision": REVISION, "purpose": "generic_owner_declared_outing_cohort_and_split_lock",
        "status": status, "registry_sha256": registry_pin, "manifest_sha256": manifest_pin,
        "session_declaration_sha256": declaration_pin, "session_evidence_status": EVIDENCE_STATUS,
        "physical_independence_independently_verified": False,
        "legacy_development_outing_count": 1, "eligible_new_outing_count": len(eligible),
        "unexposed_eligible_final_pool_count": len(final_pool), "required_final_count": count,
        "split_policy": SPLIT_POLICY, "roles_assigned": status == "complete",
        "cohort_lock_created": status == "complete", "model_admission_authorized": False,
        "raw_cache_deletion_authorized": False, "outings": sorted(outcomes, key=lambda o: o["outing_id"])}
