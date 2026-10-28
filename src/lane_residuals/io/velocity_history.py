"""Bounded cached-return verification. No archived raw path is opened or statted."""
from __future__ import annotations

import csv
import hashlib
from io import BytesIO, StringIO
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from tempfile import TemporaryDirectory
import zipfile

from ..domain.velocity_timing import TOPICS, summarize as original_summary
from .velocity_timing_pilot import REVISION as PILOT_REVISION, design_sha256, load_request

MAX_ARCHIVE_BYTES = 16*1024**2
MAX_EXPANDED_BYTES = 8*1024**2
PREFIX = "timing_a2_attempt_001/probe/"
INPUTS = ("request.private.json", "cohort.accepted.private.json", "inventory.accepted.private.json",
    "numeric_export.json", "candidate_audit.json", "residuals.npz")
MEMBERS = {"pinned_inputs/"+name for name in INPUTS} | {"source_gate.private.json", "independent_review_note.private.md",
    "timing_a2_attempt_001/launcher_receipt.private.json", "timing_a2_attempt_001/child.stdout.private.log",
    "timing_a2_attempt_001/child.stderr.private.log"} | {PREFIX+name for name in
    ("report.private.json", "frame_screens.private.csv", "velocity_updates.private.csv", "01_velocity_observations.png", "02_local_support_screen.png")}


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def close_match(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a) == set(b) and all(close_match(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(close_match(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return type(a) is type(b) and a == b


def boolean(value):
    require(value in ("True", "False"), "history_csv_boolean")
    return value == "True"


def table(data, expected):
    reader = csv.DictReader(StringIO(data.decode("utf-8")))
    require(reader.fieldnames is not None and len(reader.fieldnames) == len(expected) and set(reader.fieldnames) == set(expected), "history_csv_columns")
    rows = list(reader)
    require(len(rows) <= 50_000 and all(None not in r and None not in r.values() for r in rows), "history_csv_rows")
    return rows


def read_archive(path, pin):
    """Read one explicitly supplied regular ZIP; never follow its raw-path strings."""
    path = Path(path)
    require(path.suffix.lower() == ".zip", "history_zip_input_required")
    require(isinstance(pin, str) and len(pin) == 64 and all(c in "0123456789abcdef" for c in pin), "history_sha256_required")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_ARCHIVE_BYTES, "history_regular_bounded_zip_required")
        payload = stream.read(MAX_ARCHIVE_BYTES+1)
    require(len(payload) <= MAX_ARCHIVE_BYTES and sha(payload) == pin, "history_archive_sha256")
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        entries = archive.infolist()
        require(len(entries) == len(MEMBERS) and {i.filename for i in entries} == MEMBERS, "history_archive_members")
        require(sum(i.file_size for i in entries) <= MAX_EXPANDED_BYTES and all(i.file_size >= 0 for i in entries), "history_archive_expansion")
        for entry in entries:
            p = PurePosixPath(entry.filename)
            require(not p.is_absolute() and ".." not in p.parts and (entry.external_attr >> 16) & 0o170000 != 0o120000, "history_archive_path")
        # zipfile verifies each member's CRC while reading it.
        return {i.filename: archive.read(i) for i in entries}


def load_return(path, pin):
    files = read_archive(path, pin)
    value = lambda name: json.loads(files[name])
    report, gate = value(PREFIX+"report.private.json"), value("source_gate.private.json")
    receipt = value("timing_a2_attempt_001/launcher_receipt.private.json")
    request = value("pinned_inputs/request.private.json")
    require(report["revision"] == request["revision"] == PILOT_REVISION and report["status"] == "complete_local_exploratory_timing_pilot" and report["phase"] == "complete", "history_complete_pilot_required")
    require(receipt["status"] == "complete" and receipt["child_exit_code"] == 0 and not receipt["parent_timeout"], "history_complete_parent_required")
    require(report["current_full_raw_hash_verified"] is True and report["message_payloads_decoded"] is True, "history_pilot_execution_flags")
    require(all(report[k] is False for k in ("model_fitted", "residual_geometry_recomputed", "training_dataset_modified", "speed_policy_adopted", "physical_causal_availability_proven", "cohort_wide_temporal_recovery_established")), "history_pilot_scope_flags")
    require(report["source"] == gate and gate["independent_review_go_owner_attested"] is True, "history_archived_source_evidence")
    require(sha(files["source_gate.private.json"]) == report["gate_sha256"] == receipt["gate_sha256"] and
        sha(files["independent_review_note.private.md"]) == gate["review_note_sha256"], "history_gate_review_digest")
    request_pin = sha(files["pinned_inputs/request.private.json"])
    require(request_pin == report["request_sha256"] == receipt["request_sha256"] == gate["request_sha256"] and
        gate["tree"] == receipt["expected_reviewed_tree"] and gate["runtime_sha256"] == receipt["runtime_sha256"], "history_receipt_bindings")
    # Enforce all names before the frozen loader joins paths. Only six known
    # cached files are materialized; absolute/traversal/raw aliases are rejected.
    require(request["summary_scope"]["cohort_file"] == INPUTS[1] and request["summary_scope"]["inventory_file"] == INPUTS[2] and
        request["numeric_summary_file"] == INPUTS[3] and request["audit_file"] == INPUTS[4] and request["numeric_file"] == INPUTS[5], "history_cached_input_names")
    require(report["raw_verification"]["sha256"] == request["summary_scope"]["raw_sha256"] and
        report["raw_verification"]["bytes"] == request["summary_scope"]["size_bytes"], "history_reported_raw_identity")
    with TemporaryDirectory(prefix="mpr-cached-velocity-") as temporary:
        base = Path(temporary)
        for name in INPUTS:
            (base/name).write_bytes(files["pinned_inputs/"+name])
        _, _, targets, old = load_request(base/INPUTS[0], request_pin)
    require(design_sha256(request) == report["design_sha256"], "history_design_identity")
    updates = table(files[PREFIX+"velocity_updates.private.csv"],
        ("topic", "log_ns", "publish_ns", "source_ns", "value", "qualifier", "outer_qualifier", "standstill_status", "nested_present", "non_default_decoded_fields"))
    records = []
    for row in updates:
        require(row["topic"] in TOPICS, "history_selected_topics_only")
        records.append({"topic": row["topic"], "log_ns": str(int(row["log_ns"])), "publish_ns": str(int(row["publish_ns"])),
            "source_ns": str(int(row["source_ns"])), "value": float(row["value"]) if row["value"] else None,
            "qualifier": int(row["qualifier"]), "outer_qualifier": int(row["outer_qualifier"]) if row["outer_qualifier"] else None,
            "standstill_status": int(row["standstill_status"]) if row["standstill_status"] else None,
            "nested_present": boolean(row["nested_present"]), "non_default_decoded_fields": json.loads(row["non_default_decoded_fields"])})
    padded = (int(request["window_start_log_ns"])-1_000_000_000, int(request["window_end_log_ns"])+1_000_000_000)
    require(all(padded[0] <= int(r["log_ns"]) <= padded[1] for r in records), "history_update_window")
    require(report["decode"]["messages_retained_in_padded_log_window"] == len(records), "history_update_count")
    frames = table(files[PREFIX+"frame_screens.private.csv"], ("topic", "candidate_index", "edp_source_ns", "edp_log_ns", "source_age_ns",
        "recorded_clock_screen_met", "log_time_tied_to_edp", "local_hypothetical_complete", "old_complete", "residual_available",
        "non_speed_features_available", "condition_failure_codes", "old_speed_mps", "candidate_value_native_units", "reasons"))
    for row in frames:
        row["candidate_index"] = int(row["candidate_index"])
        for key in ("recorded_clock_screen_met", "log_time_tied_to_edp", "local_hypothetical_complete", "old_complete", "residual_available", "non_speed_features_available"):
            row[key] = boolean(row[key])
        for key in ("old_speed_mps", "candidate_value_native_units"):
            row[key] = float(row[key]) if row[key] else None
        for key in ("condition_failure_codes", "reasons"):
            row[key] = json.loads(row[key])
        row["source_age_ns"] = row["source_age_ns"] or None
    baseline, baseline_frames = original_summary(records, targets, old)
    require(close_match(baseline, report["analysis"]) and close_match(baseline_frames, frames), "history_original_analysis_replay")
    return {"request": request, "targets": targets, "records": records, "original_analysis": baseline,
        "original_frames": frames, "input_archive_sha256": pin,
        "input_member_sha256": {name: sha(data) for name, data in files.items()},
        "provenance": "archived_receipt_and_cache_replay_not_live_source_authorization"}
