"""Gated one-attempt diagnostic with private CSVs, Python plots and receipts."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time

from ..domain.velocity_timing import summarize
from ..io import velocity_review_gate as gate
from ..io.velocity_timing_pilot import REVISION, LIMITS, PADDING_NS, prepare_window, decode_prepared, design_sha256, file_identity, load_request, verify_raw
from ..io.velocity_summary_probe import require


def write_json(path, value):
    temporary = path.with_name(path.name+".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def resources(directory):
    require(shutil.disk_usage(directory).free >= 256*1024**2, "pilot_scratch_free_below_256MiB")
    info = Path("/proc/meminfo").read_text().splitlines()
    available = next(int(line.split()[1])*1024 for line in info if line.startswith("MemAvailable:"))
    require(available >= 1024**3, "pilot_mem_available_below_1GiB")
    return {"mem_available_bytes": available, "scratch_free_bytes": shutil.disk_usage(directory).free}


def run(*, project, request_path, request_sha256, gate_path, gate_sha256, expected_runtime, output):
    project, output = Path(project).resolve(strict=True), Path(output).absolute()
    request, expected, targets, old_speed = load_request(request_path, request_sha256)
    # These checks, including live merge/CI verification, precede raw path access.
    source = gate.validate(project, gate_path, gate_sha256, expected_runtime, request_sha256)
    require(not output.exists() and not output.is_symlink() and output.parent.is_dir() and
        output.parent.resolve() == output.parent, "pilot_new_output_required")
    available = resources(output.parent)
    path = Path(request["summary_scope"]["raw_path_private"])
    require(path.is_absolute() and not path.is_symlink() and path.resolve() == path and path != output,
        "pilot_canonical_raw_path_required")
    claims = project/"outputs/private/velocity_timing_attempts"
    require(all(not p.is_symlink() for p in (project/"outputs", project/"outputs/private", claims)), "pilot_claim_symlink_forbidden")
    design = design_sha256(request)
    claim_path = claims/(design+".started.json")
    if claim_path.exists() or claim_path.is_symlink():
        raise FileExistsError(str(claim_path))
    raw_stat = path.stat()
    require(stat.S_ISREG(raw_stat.st_mode) and raw_stat.st_size == request["summary_scope"]["size_bytes"],
        "pilot_regular_registered_raw_required")
    started = time.monotonic()
    # One nonblocking descriptor spans metadata preflight, hash and decode.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "pilot_regular_raw_file_required")
        before = file_identity(stream)
        require(before[2] == request["summary_scope"]["size_bytes"] and
            0 < before[2] <= LIMITS["maximum_raw_file_bytes"], "pilot_raw_size_or_budget_changed")
        window = (int(request["window_start_log_ns"])-PADDING_NS, int(request["window_end_log_ns"])+PADDING_NS)
        prepared = prepare_window(stream, before[2], expected, window, output.parent)
        require(file_identity(stream) == before, "pilot_raw_changed_during_preflight")
        # Budget failure above opens metadata only and consumes no hash/payload claim.
        claims.mkdir(parents=True, exist_ok=True)
        claim = {"revision": REVISION, "design_sha256": design, "request_sha256": request_sha256,
            "gate_sha256": gate_sha256, "source_commit": source["commit"], "source_tree": source["tree"],
            "window_plan": prepared["summary"], "output_private": str(output)}
        with claim_path.open("x") as claim_stream:
            claim_stream.write(json.dumps(claim, indent=2, sort_keys=True)+"\n")
            claim_stream.flush()
            os.fsync(claim_stream.fileno())
        for directory in (claims, claims.parent, claims.parent.parent, project):
            sync_directory(directory)
        output.mkdir()
        report = {"revision": REVISION, "design_sha256": design, "request_sha256": request_sha256,
            "gate_sha256": gate_sha256, "source": source, "attempt_claim_private": str(claim_path), "limits": LIMITS,
            "window_plan": prepared["summary"], "resources_at_start": available, "status": "started",
            "phase": "metadata_plan_complete", "model_fitted": False,
            "residual_geometry_recomputed": False, "training_dataset_modified": False,
            "speed_policy_adopted": False, "physical_causal_availability_proven": False,
            "cohort_wide_temporal_recovery_established": False,
            "current_full_raw_hash_verified": None, "message_payloads_decoded": None,
            "window_start_log_ns": request["window_start_log_ns"], "window_end_log_ns": request["window_end_log_ns"]}
        write_json(output/"report.private.json", report)
        try:
            report["raw_verification"] = verify_raw(stream, request["summary_scope"])
            report["current_full_raw_hash_verified"] = True
            require(file_identity(stream) == before, "pilot_raw_changed_during_hash")
            report["phase"] = "raw_hash_verified"
            write_json(output/"report.private.json", report)
            records, report["decode"] = decode_prepared(prepared)
            report["message_payloads_decoded"] = report["decode"]["decoded_selected_messages_in_touched_chunks"] > 0
            require(file_identity(stream) == before, "pilot_raw_changed_during_decode")
            report["phase"] = "payload_decode_complete"
            write_json(output/"report.private.json", report)
            report["analysis"], screens = summarize(records, targets, old_speed)
            write_csv(output/"velocity_updates.private.csv", records)
            write_csv(output/"frame_screens.private.csv", screens)
            from ..reporting.velocity_timing import plot
            plot(output, records, screens, report)
            load_request(request_path, request_sha256)
            require(gate.runtime_sha256(project) == expected_runtime and gate.git(project, "rev-parse", "HEAD") == source["commit"],
                "pilot_source_changed_during_operation")
            report.update(status="complete_local_exploratory_timing_pilot", phase="complete", elapsed_seconds=time.monotonic()-started)
        except BaseException as error:
            report.update(status="incomplete", failure_class=type(error).__name__, elapsed_seconds=time.monotonic()-started)
            code = str(error)
            if isinstance(error, (ValueError, InterruptedError)) and code.startswith(("pilot_", "decode_", "inventory_")):
                report["failure_code"] = code
            raise
        finally:
            write_json(output/"report.private.json", report)
    return report
