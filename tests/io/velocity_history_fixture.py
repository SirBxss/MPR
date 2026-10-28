"""A synthetic cached return, never an owner operation or real GO evidence."""
import csv
from io import StringIO
import json
from pathlib import Path
import zipfile

from lane_residuals.domain.velocity_timing import TOPICS, summarize
from lane_residuals.io.velocity_history import PREFIX, sha
from lane_residuals.io.velocity_timing_pilot import design_sha256, load_request
from tests.io.velocity_timing_fixture import LOG, SOURCE, prepare


def csv_bytes(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    return stream.getvalue().encode()


def fixture(base, role="development", change_request=None):
    base = Path(base); cache = base/"cache"; cache.mkdir()
    request_path, _, raw_path = prepare(cache, role)
    request = json.loads(request_path.read_bytes())
    mapping = {"cohort.json": "cohort.accepted.private.json", "inventory.json": "inventory.accepted.private.json",
        "numeric.json": "numeric_export.json", "audit.json": "candidate_audit.json", "numeric.npz": "residuals.npz"}
    for old, new in mapping.items(): (cache/new).write_bytes((cache/old).read_bytes())
    request["summary_scope"].update(cohort_file=mapping["cohort.json"], inventory_file=mapping["inventory.json"],
        raw_path_private="/synthetic/private_raw/DO_NOT_READ_SYNTHETIC_PATH/output.mcap")
    request.update(numeric_summary_file=mapping["numeric.json"], audit_file=mapping["audit.json"], numeric_file=mapping["numeric.npz"])
    if change_request: change_request(request)
    data = (json.dumps(request, sort_keys=True)+"\n").encode()
    (cache/"request.private.json").write_bytes(data)
    # Build original analysis from an unmodified development copy even for
    # deliberately invalid role/name fixtures; the loader must reject those.
    valid_request = dict(request, audit_file="candidate_audit.json")
    valid_request["summary_scope"] = dict(request["summary_scope"])
    valid_request["summary_scope"]["cohort_file"] = "cohort.accepted.private.json"
    cohort = json.loads((cache/"cohort.accepted.private.json").read_bytes())
    if role != "development":
        cohort["outings"][0]["cohort_role"] = "development"
        validation_cohort = json.dumps(cohort).encode(); (cache/"validation_cohort.json").write_bytes(validation_cohort)
        valid_request["summary_scope"].update(cohort_file="validation_cohort.json", cohort_sha256=sha(validation_cohort))
    valid_data = json.dumps(valid_request).encode(); (cache/"validation_request.json").write_bytes(valid_data)
    _, _, targets, old = load_request(cache/"validation_request.json", sha(valid_data))
    records = []
    for topic in TOPICS:
        for i in range(120):
            for offset, age in ((-33_000_000, 10_000_000), (0, -10_000_000)):
                records.append({"topic": topic, "log_ns": str(LOG+i*100_000_000+offset),
                    "publish_ns": str(SOURCE+i*100_000_000-1), "source_ns": str(SOURCE+i*100_000_000-age),
                    "value": 10., "qualifier": 1, "outer_qualifier": 2 if topic == TOPICS[1] else None,
                    "standstill_status": 15 if topic == TOPICS[1] else None, "nested_present": True,
                    "non_default_decoded_fields": ["value", "qualifier", "timestamp"]})
    analysis, frames = summarize(records, targets, old)
    note = b"Synthetic fixture only. Not an owner GO or operation authorization."
    gate = {"independent_review_go_owner_attested": True, "review_note_sha256": sha(note),
        "request_sha256": sha(data), "tree": "synthetic-tree", "runtime_sha256": "synthetic-runtime"}
    gate_data = json.dumps(gate).encode()
    report = {"revision": request["revision"], "status": "complete_local_exploratory_timing_pilot", "phase": "complete",
        "source": gate, "gate_sha256": sha(gate_data), "request_sha256": sha(data), "design_sha256": design_sha256(request),
        "raw_verification": {"sha256": request["summary_scope"]["raw_sha256"], "bytes": request["summary_scope"]["size_bytes"]},
        "decode": {"messages_retained_in_padded_log_window": len(records)}, "analysis": analysis,
        "current_full_raw_hash_verified": True, "message_payloads_decoded": True,
        **{k: False for k in ("model_fitted", "residual_geometry_recomputed", "training_dataset_modified", "speed_policy_adopted", "physical_causal_availability_proven", "cohort_wide_temporal_recovery_established")}}
    receipt = {"status": "complete", "child_exit_code": 0, "parent_timeout": False,
        "gate_sha256": sha(gate_data), "request_sha256": sha(data), "expected_reviewed_tree": gate["tree"], "runtime_sha256": gate["runtime_sha256"]}
    files = {"pinned_inputs/"+name: (cache/name).read_bytes() for name in
        ("request.private.json", *mapping.values())}
    files.update({"source_gate.private.json": gate_data, "independent_review_note.private.md": note,
        "timing_a2_attempt_001/launcher_receipt.private.json": json.dumps(receipt).encode(),
        "timing_a2_attempt_001/child.stdout.private.log": b"synthetic", "timing_a2_attempt_001/child.stderr.private.log": b"",
        PREFIX+"report.private.json": json.dumps(report).encode(), PREFIX+"frame_screens.private.csv": csv_bytes(frames),
        PREFIX+"velocity_updates.private.csv": csv_bytes(records), PREFIX+"01_velocity_observations.png": b"synthetic placeholder",
        PREFIX+"02_local_support_screen.png": b"synthetic placeholder"})
    raw_path.unlink()  # No raw file exists while the new consumer is exercised.
    return files


def write_archive(base, files):
    path = Path(base)/"cached_results.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items(): archive.writestr(name, data)
    return path, sha(path.read_bytes())
