"""Two fixed windows, durable claims, descriptive caches and raw guards."""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import stat
import time

from ..domain.artifact_registry import require
from ..domain.direct_speed_study import REVISION, MAX_FILE_BYTES, MAX_TOTAL_BYTES, analyze, population
from ..io import velocity_review_gate as gate
from ..io.artifact_registry import separate_output
from ..io.direct_speed_study import load, design_sha256, prepare, verify_raw
from ..io.private_reports import write_json, write_csv, sync_directory
from ..io.velocity_timing_pilot import LIMITS, PADDING_NS, decode_prepared, file_identity
from .velocity_timing_pilot import resources


def run(*, project, request_path, request_sha256, gate_path, gate_sha256, expected_runtime, output):
    project,output = Path(project).resolve(strict=True),Path(output).absolute()
    require(not output.exists() and not output.is_symlink() and output.parent.is_dir() and
        output.parent.resolve() == output.parent, "study_fresh_canonical_output_required")
    separate_output(output)
    loaded = load(project,request_path,request_sha256)
    separate_output(output,loaded["protected_output_roots"])
    # No raw path stat/resolve/open and no population statistics before this.
    source = gate.validate(project,gate_path,gate_sha256,expected_runtime,request_sha256)
    available = resources(output.parent)
    claims = project/"outputs/private/direct_speed_study_attempts"
    require(all(not p.is_symlink() for p in (project/"outputs",project/"outputs/private",claims)), "study_claim_symlink_forbidden")
    cases = loaded["cases"]
    keys = [design_sha256(c,loaded["experiment_sha256"]) for c in cases]
    require(len(set(keys)) == 2 and len(cases) == 2 and sum(c["size_bytes"] for c in cases) <= MAX_TOTAL_BYTES, "study_fixed_two_case_budget")
    claim_paths = [claims/(key+".started.json") for key in keys]
    require(all(not p.exists() and not p.is_symlink() for p in claim_paths), "study_window_already_claimed")
    output.mkdir()
    report = {"revision":REVISION,"status":"started_bounded_direct_speed_study","phase":"before_raw_metadata",
        "request_sha256":request_sha256,"source":source,"gate_sha256":gate_sha256,
        **{k:loaded[k] for k in ("experiment_sha256","cohort_sha256","registry_sha256")},
        "limits":{"maximum_raw_file_bytes":MAX_FILE_BYTES,"maximum_total_raw_bytes":MAX_TOTAL_BYTES,
            "window_count":2,"per_window_decoder_limits":dict(LIMITS)},"resources_at_start":available,
        "window_claims_private":[str(p) for p in claim_paths],"cases":[],
        "model_fitted":False,"training_dataset_modified":False,"new_training_arrays_exported":False,
        "speed_feature_adopted":False,"cohort_wide_temporal_recovery_established":False,
        "physical_causal_availability_proven":False,"final_outings_exposed":False,
        "raw_hash_started":False,"payload_decode_started":False,"claims_created":0}
    started = time.monotonic()
    write_json(output/"report.private.json",report)
    try:
        with ExitStack() as descriptors:
            plans = []
            for case in cases:
                path = Path(case["raw_path_private"])
                require(path.is_absolute() and not path.is_symlink() and path.resolve() == path, "study_canonical_raw_path_required")
                require(stat.S_ISREG(path.stat().st_mode), "study_regular_raw_file_required")
                stream = descriptors.enter_context(os.fdopen(os.open(path,os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW),"rb"))
                before = file_identity(stream)
                require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode) and before[2] == case["size_bytes"] and
                    0 < before[2] <= MAX_FILE_BYTES, "study_registered_raw_size_or_type_changed")
                window = (int(case["window_start_log_ns"])-PADDING_NS,int(case["window_end_log_ns"])+PADDING_NS)
                plan = prepare(stream,before[2],case["expected_inventory"],window,output.parent)
                require(file_identity(stream) == before, "study_raw_changed_during_planning")
                plans.append((stream,before,plan))
                report["cases"].append({**{k:case[k] for k in ("outing_id","recording_id","raw_sha256","size_bytes","window_start_log_ns","window_end_log_ns","binding")},
                    "window_plan":plan["summary"],"phase":"metadata_plan_complete","raw_verification":None,"decode":None})
                write_json(output/"report.private.json",report)
            report["phase"] = "all_metadata_plans_complete"
            claims.mkdir(parents=True,exist_ok=True)
            for case,key,path in zip(cases,keys,claim_paths):
                claim = {"revision":REVISION,"design_sha256":key,"request_sha256":request_sha256,
                    "source_commit":source["commit"],"source_tree":source["tree"],"gate_sha256":gate_sha256,
                    "raw_sha256":case["raw_sha256"],"outing_id":case["outing_id"],"output_private":str(output)}
                with path.open("x") as stream:
                    import json
                    stream.write(json.dumps(claim,sort_keys=True,indent=2)+"\n");stream.flush();os.fsync(stream.fileno())
                report["claims_created"] += 1
                for directory in (claims,claims.parent,claims.parent.parent,project):
                    sync_directory(directory)
                write_json(output/"report.private.json",report)
            # Both windows are claimed before the first identity hash/payload.
            for case,item,(stream,before,plan) in zip(cases,report["cases"],plans):
                folder = output/case["outing_id"];folder.mkdir()
                (folder/"original_candidate_audit.private.json").write_bytes(case["audit_bytes"])
                (folder/"original_inventory.private.json").write_bytes(case["inventory_bytes"])
                write_json(folder/"old_speed.private.json",{str(k):v for k,v in case["old_speed"].items()})
                report["phase"],item["phase"] = "raw_hash_started","raw_hash_started"
                report["raw_hash_started"] = True
                write_json(output/"report.private.json",report)
                require(file_identity(stream) == before, "study_raw_changed_before_hash")
                item["raw_verification"] = verify_raw(stream,case)
                require(file_identity(stream) == before, "study_raw_changed_during_hash")
                report["phase"],item["phase"] = "payload_decode_started","payload_decode_started"
                report["payload_decode_started"] = True
                write_json(output/"report.private.json",report)
                records,item["decode"] = decode_prepared(plan)
                require(file_identity(stream) == before, "study_raw_changed_during_decode")
                item["phase"] = "payload_decode_complete"
                write_csv(folder/"velocity_updates.private.csv",records)
                write_json(output/"report.private.json",report)
                item["analysis"],frames = analyze(records,case["targets"],case["old_speed"])
                write_csv(folder/"frame_decisions.private.csv",frames)
                item["phase"] = "window_analysis_complete"
                write_json(output/"report.private.json",report)
            for stream,before,_ in plans:
                require(file_identity(stream) == before, "study_raw_changed_before_completion")
        report["phase"] = "cached_population_comparison"
        write_json(output/"report.private.json",report)
        report["population"],stations = population(loaded["inputs"].blocks,loaded["audits"])
        write_csv(output/"population_stations.private.csv",stations)
        from ..reporting.direct_speed_study import plot
        plot(output,report,stations)
        loaded["inputs"].unchanged()
        require(gate.runtime_sha256(project) == expected_runtime and gate.git(project,"rev-parse","HEAD") == source["commit"] and
            not gate.git(project,"status","--porcelain"), "study_source_changed_during_operation")
        report.update(status="complete_bounded_direct_speed_development_study",phase="complete")
    except BaseException as error:
        report.update(status="incomplete_bounded_direct_speed_development_study",failure_class=type(error).__name__)
        if isinstance(error,(ValueError,InterruptedError)) and str(error).startswith(("study_","pilot_","decode_","inventory_","experiment_")):
            report["failure_code"] = str(error)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic()-started
        write_json(output/"report.private.json",report)
    return report
