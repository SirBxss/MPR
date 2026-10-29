"""Original sealed experiment, fixed metadata plan, and isolated hash bound."""
import hashlib
import json
import math
from pathlib import Path
import time

from ..domain.artifact_registry import digest, require
from ..domain.direct_speed_study import REVISION, MAX_FILE_BYTES, MAX_TOTAL_BYTES
from ..domain.speed_mechanism import stamp
from . import development_experiment as original
from .numeric_export_inputs import read_json
from .velocity_timing_pilot import fixed_window_start, WINDOW_NS, file_identity, LIMITS, prepare_window
from . import recording_decode_check as decoder

FIELDS = {"revision", "experiment_directory", "experiment_sha256", "previously_examined_outing_id", "cases"}
CASE_FIELDS = {"outing_id", "recording_id", "window_start_log_ns", "window_end_log_ns"}


def object_json(context, pin):
    digest(pin)
    require(pin in context.objects and hashlib.sha256(context.objects[pin]).hexdigest() == pin, "study_object_digest")
    return json.loads(context.objects[pin])


def fixed_cases(inputs, prior):
    """Select by original identity/size and geometry only, never speed outcomes."""
    records = {r["raw_sha256"]:r for r in inputs.context.metadata["records"]}
    require(prior in {b.outing_id for b in inputs.blocks}, "study_prior_case_not_in_development")
    available = []
    for block in sorted(inputs.blocks,key=lambda b:b.outing_id):
        if block.outing_id == prior:
            continue
        identities = block.archive.raw_sha256_by_recording
        if len(identities) != 1:
            continue
        recording, raw = next(iter(identities.items()))
        if 0 < records[raw]["size_bytes"] <= MAX_FILE_BYTES:
            available.append((block,recording,records[raw]))
    require(len(available) >= 2, "study_two_size_eligible_development_outings_required")
    chosen = available[:2]
    require(sum(r["size_bytes"] for _,_,r in chosen) <= MAX_TOTAL_BYTES, "study_total_raw_size_budget")
    cases = []
    for block,recording,raw in chosen:
        summary = object_json(inputs.context,block.archive.summary_sha256)
        audit_pin = summary["artifacts_sha256"]["candidate_audit.json"]
        audit = object_json(inputs.context,audit_pin)
        rows = [r for r in audit["rows"] if r["recording_id"] == recording]
        require(rows and len(rows) == len(audit["rows"]), "study_single_recording_audit_required")
        start = fixed_window_start(rows)
        cases.append({"outing_id":block.outing_id,"recording_id":recording,
            "window_start_log_ns":str(start),"window_end_log_ns":str(start+WINDOW_NS)})
    return cases


def load(project, request_path, expected_sha256):
    digest(expected_sha256)
    request_path = original.metadata_path(request_path)
    request,pin,_ = read_json(request_path,maximum=64*1024)
    require(pin == expected_sha256, "study_request_digest_mismatch")
    require(type(request) is dict and set(request) == FIELDS and request["revision"] == REVISION, "study_closed_request_required")
    require(type(request["previously_examined_outing_id"]) is str and request["previously_examined_outing_id"], "study_prior_case_required")
    require(type(request["cases"]) is list and len(request["cases"]) == 2 and
        all(type(c) is dict and set(c) == CASE_FIELDS for c in request["cases"]), "study_two_closed_cases_required")
    for case in request["cases"]:
        require(all(type(case[k]) is str and case[k] for k in CASE_FIELDS), "study_case_string_fields_required")
        require(stamp(case["window_start_log_ns"]) > 0 and stamp(case["window_end_log_ns"]) > 0, "study_positive_window_required")
    project = original.metadata_path(project)
    folder = original.resolve(project,request["experiment_directory"])
    inputs,manifest = original.load_experiment(project,folder,digest(request["experiment_sha256"]))
    require(request["cases"] == fixed_cases(inputs,request["previously_examined_outing_id"]), "study_fixed_geometry_and_outing_selection_required")
    context = inputs.context
    records = {r["raw_sha256"]:r for r in context.metadata["records"]}
    blocks = {b.outing_id:b for b in inputs.blocks}
    cases, audits = [], {}
    for block in inputs.blocks:
        summary = object_json(context,block.archive.summary_sha256)
        audits[block.outing_id] = object_json(context,summary["artifacts_sha256"]["candidate_audit.json"])["rows"]
    for declared in request["cases"]:
        block = blocks[declared["outing_id"]]
        recording = declared["recording_id"]
        raw_pin = block.archive.raw_sha256_by_recording[recording]
        raw_record = records[raw_pin]
        paths = raw_record["canonical_paths_private"]
        require(len(paths) == 1 and type(paths[0]) is str, "study_unambiguous_registered_raw_path_required")
        summary = object_json(context,block.archive.summary_sha256)
        inventory_pin = summary["preserved_inventory_report_sha256"]
        inventory = object_json(context,inventory_pin)
        inventory_rows = [r for r in inventory["recordings"] if r["recording_id"] == recording]
        require(inventory["purpose"] == "development_only_recording_inventory" and len(inventory_rows) == 1 and
            inventory_rows[0]["status"] == "complete" and inventory_rows[0]["raw_sha256"] == raw_pin and
            inventory_rows[0]["size_bytes"] == raw_record["size_bytes"], "study_inventory_identity_binding")
        rows = audits[block.outing_id]
        start,end = int(declared["window_start_log_ns"]),int(declared["window_end_log_ns"])
        targets = [r for r in rows if start <= int(r["estimate_log_time_ns_decimal_private"]) < end]
        require(bool(targets), "study_nonempty_target_window_required")
        a = block.archive.arrays
        indices = a["conditioned_profile_indices"]
        old = {int(a["candidate_index"][i]):float(v[0]) for i,v in zip(indices,a["conditions"])}
        require(all(math.isfinite(v) for v in old.values()), "study_old_speed_finite_required")
        audit_pin = summary["artifacts_sha256"]["candidate_audit.json"]
        cases.append({**declared, "targets":targets,"old_speed":old,"expected_inventory":inventory_rows[0]["inventory"],
            "raw_path_private":paths[0],"raw_sha256":raw_pin,"size_bytes":raw_record["size_bytes"],
            "audit_bytes":context.objects[audit_pin],"inventory_bytes":context.objects[inventory_pin],
            "binding":{"archive_sha256":block.archive.summary_sha256,"audit_sha256":audit_pin,
                "inventory_sha256":inventory_pin,"original_numeric_sha256":summary["artifacts_sha256"]["residuals.npz"]}})
    inputs.watched[request_path] = expected_sha256
    inputs.unchanged()
    protected = {folder,request_path.parent,*(root for root,_ in inputs.file_sets),
        *(p.parent for p in inputs.watched if p.name == "run_receipt.json")}
    return {"request":request,"request_sha256":expected_sha256,"inputs":inputs,"cases":cases,"audits":audits,
        "protected_output_roots":tuple(protected),"experiment_sha256":request["experiment_sha256"],
        "cohort_sha256":context.cohort_sha256,"registry_sha256":context.registry_sha256}


def design_sha256(case, experiment_sha256):
    value = {"revision":REVISION,"experiment_sha256":experiment_sha256,
        "raw_sha256":case["raw_sha256"],"size_bytes":case["size_bytes"],
        "recording_id":case["recording_id"],"outing_id":case["outing_id"],
        "window_start_log_ns":str(int(case["window_start_log_ns"])),
        "window_end_log_ns":str(int(case["window_end_log_ns"]))}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def verify_raw(stream, case):
    """New study's 4 GiB identity bound; old pilot hashing remains unchanged."""
    require(type(case["size_bytes"]) is int and 0 < case["size_bytes"] <= MAX_FILE_BYTES, "study_raw_file_budget")
    require(file_identity(stream)[2] == case["size_bytes"], "study_raw_size_changed")
    stream.seek(0)
    count,hasher,started = 0,hashlib.sha256(),time.monotonic()
    while count < case["size_bytes"]:
        require(time.monotonic()-started <= LIMITS["hash_seconds"], "study_hash_timeout")
        raw = stream.read(min(1024**2,case["size_bytes"]-count))
        require(bool(raw), "study_hash_truncated")
        hasher.update(raw);count += len(raw)
    require(time.monotonic()-started <= LIMITS["hash_seconds"] and hasher.hexdigest() == case["raw_sha256"], "study_hash_time_or_digest_mismatch")
    return {"bytes":count,"sha256":hasher.hexdigest(),"elapsed_seconds":time.monotonic()-started}


def prepare(stream, size, expected, window, scratch):
    """Original indexed budgets, plus explicit scalar/qualifier type binding."""
    started = time.monotonic()
    prepared = prepare_window(stream,size,expected,window,scratch)
    metered = prepared["metered"]
    declarations = []
    def observe(schema, message):
        descriptor = message.DESCRIPTOR
        if descriptor.full_name == "Adp.VehicleVelocity":
            fields = descriptor.fields_by_name
            require("velocity" in fields and fields["velocity"].type == 11 and
                not fields["velocity"].is_repeated and
                fields["velocity"].message_type.full_name == "Adp.QualifiedTimedFloat64" and
                all(k in fields and not fields[k].is_repeated and fields[k].type in (3,4,5,13,14,17,18) for k in ("qualifier","status_velocity_near_standstill")), "study_vehicle_descriptor_binding")
            descriptor = fields["velocity"].message_type
        require(descriptor.full_name == "Adp.QualifiedTimedFloat64", "study_scalar_descriptor_binding")
        fields = descriptor.fields_by_name
        require(all(k in fields for k in ("value","timestamp","qualifier")) and fields["value"].type == 1 and
            fields["timestamp"].type in (3,4,18) and fields["qualifier"].type == 14 and
            all(not fields[k].is_repeated for k in ("value","timestamp","qualifier")), "study_scalar_field_types")
        valid = fields["qualifier"].enum_type.values_by_number.get(1)
        tokens = set(valid.name.upper().split("_")) if valid else set()
        require(bool({"VALID","OK"}.intersection(tokens)) and not {"NOT","NO","INVALID","UNAVAILABLE"}.intersection(tokens), "study_inner_qualifier_one_not_declared_valid")
        declarations.append({"schema_id":schema.id,"root_name":schema.name,"descriptor_sha256":hashlib.sha256(schema.data).hexdigest(),
            "scalar_fields":[{"name":f.name,"number":f.number,"type":f.type} for f in descriptor.fields],
            "inner_qualifier_one_name":valid.name,"units_and_physical_reference_proven_by_descriptor":False})
    groups = decoder._groups(metered,size,metered.deadline)
    decoder._decoders(metered,groups,prepared["selected"],prepared["schemas"],metered.deadline,observe)
    prepared["summary"]["metadata_elapsed_seconds"] = time.monotonic()-started
    prepared["summary"]["metadata_bytes_read"] = metered.used["metadata"]
    require(prepared["summary"]["metadata_elapsed_seconds"] <= LIMITS["processing_seconds"], "study_planning_timeout")
    prepared["summary"]["descriptor_bindings"] = declarations
    return prepared
