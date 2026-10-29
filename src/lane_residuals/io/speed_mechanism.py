"""Pinned audit access through the unchanged original-experiment validator."""
from pathlib import Path
import hashlib
import json

from ..domain.artifact_registry import digest, require
from ..domain.speed_mechanism import REVISION
from . import development_experiment as original
from .numeric_export_inputs import read_json

FIELDS = {"revision", "experiment_directory", "experiment_sha256", "previously_examined_outing_id"}


def load(project, request_path, expected_request_sha256):
    expected_request_sha256 = digest(expected_request_sha256)
    request_path = original.metadata_path(request_path)
    require(request_path.suffix == ".json", "mechanism_json_request_required")
    request, pin, _ = read_json(request_path, maximum=64*1024)
    require(pin == expected_request_sha256, "mechanism_request_digest_mismatch")
    require(type(request) is dict and set(request) == FIELDS and request["revision"] == REVISION,
        "mechanism_closed_request_required")
    digest(request["experiment_sha256"])
    require(type(request["previously_examined_outing_id"]) is str and bool(request["previously_examined_outing_id"]),
        "mechanism_prior_case_required")
    project = original.metadata_path(project)
    folder = original.resolve(project, request["experiment_directory"])
    # This strict loader rejects invalid final exposure before descendant arrays,
    # replays all original rows/folds and never dereferences archived raw paths.
    inputs, manifest = original.load_experiment(project, folder, request["experiment_sha256"])
    development = {o["outing_id"] for o in inputs.context.cohort["outings"] if o["cohort_role"] == "development"}
    supports = {a["outing_id"]: a for a in manifest["archives"]}
    ids = [b.outing_id for b in inputs.blocks]
    require(len(set(ids)) == len(ids) and set(ids) == development == set(supports), "mechanism_original_development_coverage_required")
    require(request["previously_examined_outing_id"] in development, "mechanism_prior_case_not_in_development")
    outings = []
    for block in inputs.blocks:
        pin = block.archive.summary_sha256
        objects = inputs.context.objects
        require(pin in objects and hashlib.sha256(objects[pin]).hexdigest() == pin, "mechanism_summary_object_digest")
        summary = json.loads(objects[pin])
        audit_pin = summary["artifacts_sha256"]["candidate_audit.json"]
        events = [e for e in inputs.context.metadata["events"] if e["kind"] == "archive" and e["files"]["numeric/numeric_export.json"] == pin]
        require(bool(events) and all(e["files"]["numeric/candidate_audit.json"] == audit_pin for e in events), "mechanism_audit_registry_binding")
        require(audit_pin in objects and hashlib.sha256(objects[audit_pin]).hexdigest() == audit_pin, "mechanism_audit_object_digest")
        rows = json.loads(objects[audit_pin])["rows"]
        recording_ids = set(block.archive.raw_sha256_by_recording)
        support = supports[block.outing_id]
        require(support["archive_sha256"] == pin and rows and all(r["recording_id"] in recording_ids for r in rows), "mechanism_recording_or_support_binding")
        require(len(rows) == summary["pre_residual_candidate_count"] and
            sum(r["residual_available"] for r in rows) == support["geometry_vectors"] and
            sum(r["residual_available"] and r["conditions_available"] for r in rows) == support["complete_feature_rows"],
            "mechanism_original_candidate_counts_mismatch")
        outings.append({"outing_id": block.outing_id, "rows": rows, "original_support": support,
            "previously_examined": block.outing_id == request["previously_examined_outing_id"], "audit_sha256": audit_pin})
    inputs.watched[request_path] = expected_request_sha256
    inputs.unchanged()
    protected = {folder, *(root for root, _ in inputs.file_sets),
        *(path.parent for path in inputs.watched if path.name == "run_receipt.json")}
    return {"request_sha256": expected_request_sha256, "experiment_sha256": request["experiment_sha256"],
        "cohort_sha256": inputs.context.cohort_sha256, "registry_sha256": inputs.context.registry_sha256,
        "outings": outings, "unchanged": inputs.unchanged, "protected_output_roots": tuple(protected),
        "provenance": "pinned_original_experiment_and_supplied_local_history_replay_not_global_external_history_proof"}
