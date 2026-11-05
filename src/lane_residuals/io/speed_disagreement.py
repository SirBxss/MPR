"""Strict bounded cached study reader. Archived raw paths remain inert strings."""
import csv
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from ..domain.artifact_registry import require
from ..domain.direct_speed_study import analyze, REVISION as STUDY_REVISION
from .velocity_history import boolean, close_match, table

MAX_ZIP_BYTES = 16*1024**2
MAX_EXPANDED_BYTES = 20*1024**2
PREFIX = "study_attempt_003/probe/"
UPDATE_COLUMNS = ("topic","log_ns","publish_ns","source_ns","value","qualifier","outer_qualifier","standstill_status","nested_present","non_default_decoded_fields")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_bytes(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
    for row in rows:
        writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    return stream.getvalue().encode()


def load_return(path, pin):
    path = Path(path)
    require(path.suffix.lower() == ".zip" and type(pin) is str and re.fullmatch("[0-9a-f]{64}",pin), "disagreement_zip_and_digest_required")
    with os.fdopen(os.open(path,os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW),"rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_ZIP_BYTES, "disagreement_input_budget")
        payload = stream.read(MAX_ZIP_BYTES+1)
    require(len(payload) <= MAX_ZIP_BYTES and sha(payload) == pin, "disagreement_return_digest")
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        entries = archive.infolist()
        require(len(entries) == 32 and len({i.filename for i in entries}) == 32 and
            sum(i.file_size for i in entries) <= MAX_EXPANDED_BYTES, "disagreement_archive_budget_or_duplicates")
        for entry in entries:
            name = PurePosixPath(entry.filename)
            require(not name.is_absolute() and ".." not in name.parts and not entry.is_dir() and
                (entry.external_attr >> 16) & 0o170000 != 0o120000, "disagreement_archive_path")
        files = {i.filename:archive.read(i) for i in entries}
    require("SHA256SUMS" in files, "disagreement_manifest_required")
    manifest = {}
    for line in files["SHA256SUMS"].decode().splitlines():
        value,name = line.split("  ",1)
        require(name in files and name != "SHA256SUMS" and name not in manifest and
            re.fullmatch("[0-9a-f]{64}",value) and sha(files[name]) == value, "disagreement_member_digest")
        manifest[name] = value
    require(set(manifest) == set(files)-{"SHA256SUMS"}, "disagreement_manifest_coverage")
    value = lambda name:json.loads(files[name])
    report = value(PREFIX+"report.private.json")
    receipt = value("study_attempt_003/launcher_receipt.private.json")
    gate = value("source_gate.private.json");request = value("pinned_inputs/request.private.json")
    require(report["revision"] == request["revision"] == STUDY_REVISION and
        report["status"] == "complete_bounded_direct_speed_development_study" and report["phase"] == "complete", "disagreement_complete_study")
    require(receipt["status"] == "complete" and type(receipt["child_exit_code"]) is int and receipt["child_exit_code"] == 0 and
        receipt["parent_timeout"] is False and receipt["parent_interrupted"] is False and receipt["metadata_only_retries"] == 0 and
        len(receipt["metadata_rounds"]) == 1 and receipt["metadata_rounds"][0]["source_seal_exit_code"] == 0 and
        receipt["metadata_rounds"][0]["study_child_exit_code"] == 0, "disagreement_complete_single_round_parent")
    require(report["source"] == gate and gate["independent_review_go_owner_attested"] is True and
        sha(files["source_gate.private.json"]) == report["gate_sha256"] == receipt["metadata_rounds"][0]["gate_sha256"] and
        files["source_gate.private.json"] == files["study_attempt_003/metadata_round_1/source_gate.private.json"], "disagreement_gate_binding")
    require(sha(files["independent_review_note.private.md"]) == gate["review_note_sha256"] == receipt["helper_review_sha256"] and
        sha(files["pinned_inputs/source_protocol_review.private.md"]) == receipt["source_review_sha256"] == receipt["correct_source_review_sha256"] and
        sha(files["owner_entrypoint.py"]) == receipt["entrypoint_sha256"] and
        gate["tree"] == receipt["expected_reviewed_tree"] and gate["runtime_sha256"] == receipt["runtime_sha256"], "disagreement_review_source_binding")
    require(sha(files["pinned_inputs/request.private.json"]) == gate["request_sha256"] == receipt["request_sha256"] == report["request_sha256"], "disagreement_request_binding")
    require(sha(files["pinned_inputs/previous_attempt_002.zip"]) == receipt["second_result_sha256"] and
        sha(files["pinned_inputs/previous_attempt_001.zip"]) == receipt["first_return"]["previous_result_sha256"], "disagreement_prior_return_binding")
    require(report["claims_created"] == 2 and report["raw_hash_started"] is True and report["payload_decode_started"] is True and
        all(report[k] is False for k in ("model_fitted","new_training_arrays_exported","training_dataset_modified","speed_feature_adopted","final_outings_exposed","physical_causal_availability_proven","cohort_wide_temporal_recovery_established")), "disagreement_original_scope")
    cases = report["cases"]
    require(len(cases) == len(request["cases"]) == 2 and len({c["outing_id"] for c in cases}) == 2 and
        all(re.fullmatch(r"outing_[0-9]{3}",c["outing_id"]) for c in cases), "disagreement_two_fixed_cases")
    names = {"SHA256SUMS","source_gate.private.json","independent_review_note.private.md","owner_launcher.py","owner_entrypoint.py","recovery_evidence.py",
        "pinned_inputs/request.private.json","pinned_inputs/previous_attempt_001.zip","pinned_inputs/previous_attempt_002.zip","pinned_inputs/source_protocol_review.private.md",
        "study_attempt_003/launcher_receipt.private.json","study_attempt_003/metadata_round_1/source_gate.private.json"}
    names |= {"study_attempt_003/metadata_round_1/"+stage+"/"+kind+".private.log" for stage in ("seal","run") for kind in ("stdout","stderr")}
    names |= {PREFIX+n for n in ("report.private.json","population_stations.private.csv","direct_speed_windows.png","direct_speed_windows.pdf","cached_population_difference.png","cached_population_difference.pdf")}
    loaded = []
    for case,declared in zip(cases,request["cases"]):
        require(all(case[k] == v for k,v in declared.items()), "disagreement_case_request")
        folder = PREFIX+case["outing_id"]+"/"
        names |= {folder+n for n in ("frame_decisions.private.csv","old_speed.private.json","original_candidate_audit.private.json","original_inventory.private.json","velocity_updates.private.csv")}
        audit_raw = files[folder+"original_candidate_audit.private.json"]
        require(sha(audit_raw) == case["binding"]["audit_sha256"] and
            sha(files[folder+"original_inventory.private.json"]) == case["binding"]["inventory_sha256"] and
            case["raw_verification"]["sha256"] == case["raw_sha256"] and case["raw_verification"]["bytes"] == case["size_bytes"], "disagreement_case_metadata_binding")
        start,end = int(case["window_start_log_ns"]),int(case["window_end_log_ns"])
        targets = [r for r in json.loads(audit_raw)["rows"] if start <= int(r["estimate_log_time_ns_decimal_private"]) < end]
        old = {int(k):v for k,v in value(folder+"old_speed.private.json").items()}
        records = []
        for row in table(files[folder+"velocity_updates.private.csv"],UPDATE_COLUMNS):
            parsed = {**row,"nested_present":boolean(row["nested_present"]),"value":float(row["value"]) if row["value"] else None,
                "non_default_decoded_fields":json.loads(row["non_default_decoded_fields"])}
            for key in ("qualifier","outer_qualifier","standstill_status"):
                parsed[key] = int(row[key]) if row[key] else None
            for key in ("log_ns","publish_ns","source_ns"):parsed[key] = str(int(row[key]))
            records.append(parsed)
        replay,frames = analyze(records,targets,old)
        require(close_match(replay,case["analysis"]) and csv_bytes(frames) == files[folder+"frame_decisions.private.csv"], "disagreement_original_replay")
        loaded.append({"outing_id":case["outing_id"],"targets":targets,"frames":frames,"original_analysis":replay})
    require(set(files) == names, "disagreement_closed_members")
    return {"cases":loaded,"input_sha256":pin,"input_member_sha256":manifest,"source":gate,
        "input_provenance":"Digest bound accepted cached return; archived evidence only, not live source authorization or a new original lineage validation."}
