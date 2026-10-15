"""Fresh registered bytes to bounded counts-only scientific readiness."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time

from ..domain.recording_ingestion import RecordingIngestionError, source_declaration_status
from ..io import recording_decode_check as decoder
from ..io.bounded_recording_readiness import REVISION, TOPIC_LIMITS, ScientificSink
from ..io.corpus_inventory import sha256_file
from ..io.recording_ingestion import file_state, sha256_stream
from ..io.recording_inventory import MAX_RECORD_BYTES, MAX_SUMMARY_BYTES, MAX_SUMMARY_RECORDS, MAX_SUMMARY_SECONDS, MAX_TEXT_BYTES, read_inventory
from ..io.recording_readiness_resources import (
    INITIAL_SCRATCH_BYTES, MAX_COMBINED_BYTES, MAX_SCIENCE_BYTES, PAGE_CACHE_BYTES,
    PROCESSING_SECONDS, RUNTIME_SCRATCH_BYTES, Observations, Workspace, check_configuration, scientific_failure,
)
from .recording_ingestion import REGISTRATION_NAME, SPECIFICATION_NAME, _new_output, _registration, _runtime, _sha256
from .recording_pair_feasibility import MINIMUM_AVAILABLE_MEMORY_BYTES, _available_memory_bytes

LOGGER = logging.getLogger(__name__)
REPORT_NAME = "bounded_recording_readiness.json"
MAX_REPORT_BYTES = 64 * 1024**2


def _fail(code="readiness_predecessor_mismatch"):
    raise RecordingIngestionError(code)


def canonical(value):
    """Strict JSON equality keeps bool/int and float/int distinctions."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _read_report(path):
    with path.open("rb") as stream:
        raw=stream.read(MAX_REPORT_BYTES+1)
    if len(raw)>MAX_REPORT_BYTES:
        _fail("readiness_predecessor_report_budget_exceeded")
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                _fail()
            result[key]=value
        return result
    def constant(_):
        _fail()
    try:
        value=json.loads(raw.decode("utf-8"),object_pairs_hook=pairs,parse_constant=constant)
        canonical(value)
    except (ValueError,TypeError,UnicodeError):
        _fail()
    return value,hashlib.sha256(raw).hexdigest()


def _integer(value):
    return type(value) is int and value>=0


def _evidence_metadata(report, expected_limits, *, compression_versions=True):
    versions=report["runtime_versions"]
    resources=report["resources_at_start"]
    limits=report["execution_limits"]
    soft=limits.get("process_address_space_soft_limit_bytes") if isinstance(limits,dict) else None
    version_keys={"python","mcap","mcap-protobuf-support","protobuf","numpy"}|({"zstandard","lz4"} if compression_versions else set())
    if (not isinstance(versions,dict) or set(versions)!=version_keys or
            not isinstance(versions["python"],str) or not versions["python"] or
            any(v is not None and (not isinstance(v,str) or not v) for v in versions.values()) or
            not _sha256(report["runtime_source_sha256"]) or not isinstance(report["interpretation"],str) or
            not isinstance(resources,dict) or set(resources)!={"mem_available_bytes","scratch_free_bytes"} or any(not _integer(v) for v in resources.values()) or
            not isinstance(limits,dict) or set(limits)!=set(expected_limits)|{"process_address_space_soft_limit_bytes"} or
            canonical({k:v for k,v in limits.items() if k!="process_address_space_soft_limit_bytes"})!=canonical(expected_limits) or
            (soft is not None and (type(soft) is not int or not 0<soft<=4*1024**3))):
        _fail()


def _advertised_selection(inventory, topics):
    channels=inventory["channels"];schemas=inventory["schemas"]
    if not isinstance(channels,list) or not isinstance(schemas,list):
        _fail()
    if (any(not _integer(r["channel_id"]) or not _integer(r["schema_id"]) for r in channels) or
            any(not _integer(r["schema_id"]) for r in schemas) or
            len({r["channel_id"] for r in channels})!=len(channels) or len({r["schema_id"] for r in schemas})!=len(schemas)):
        _fail()
    statistics=inventory["advertised_statistics"]
    if (not isinstance(statistics,dict) or any(not _integer(r["advertised_message_count"]) for r in channels) or
            not _integer(statistics["message_count"]) or statistics["message_count"]!=sum(r["advertised_message_count"] for r in channels) or
            type(statistics["schema_count"]) is not int or statistics["schema_count"]!=len(schemas) or
            type(statistics["channel_count"]) is not int or statistics["channel_count"]!=len(channels) or
            type(statistics["chunk_count"]) is not int or statistics["chunk_count"]!=inventory["chunk_index_summary"]["indexed_chunk_count"]):
        _fail()
    selected={r["channel_id"]:r for r in channels if r["topic"] in topics}
    schema_map={r["schema_id"]:r for r in schemas}
    totals={topic:0 for topic in topics}
    for row in selected.values():
        if not _integer(row["advertised_message_count"]):
            _fail()
        schema=schema_map[row["schema_id"]]
        if row["message_encoding"]!="protobuf" or schema["encoding"]!="protobuf" or not _integer(schema["data_size_bytes"]) or not _sha256(schema["data_sha256"]):
            _fail()
        totals[row["topic"]]+=row["advertised_message_count"]
    for topic in topics:
        rows=[r for r in inventory["topics"] if r["topic"]==topic]
        count=sum(c["topic"]==topic for c in selected.values())
        if len(rows)!=1 or count==0 or type(rows[0]["channel_count"]) is not int or rows[0]["channel_count"]!=count or type(rows[0]["advertised_message_count"]) is not int or rows[0]["advertised_message_count"]!=totals[topic]:
            _fail()
    needed={c["schema_id"] for c in selected.values()}
    if len(selected)>decoder.MAX_CHANNELS or len(needed)>decoder.MAX_SCHEMAS or sum(schema_map[k]["data_size_bytes"] for k in needed)>decoder.MAX_SCHEMA_BYTES:
        _fail("readiness_advertised_container_budget")
    return schema_map,selected,totals


def _predecessors(arguments, registration, digest, specification, topics):
    inventory_path=arguments.preserved_inventory_report.expanduser()
    decode_path=arguments.preserved_decode_report.expanduser()
    try:
        old_inventory,inventory_digest=decoder.read_predecessor(inventory_path,registration,digest)
        canonical(old_inventory)
        inventory_evidence,checked_inventory_digest=_read_report(inventory_path)
        if checked_inventory_digest!=inventory_digest:
            _fail()
        _evidence_metadata(inventory_evidence,{"maximum_record_bytes":MAX_RECORD_BYTES,"maximum_summary_bytes":MAX_SUMMARY_BYTES,
            "maximum_summary_records_per_section":MAX_SUMMARY_RECORDS,"maximum_text_bytes":MAX_TEXT_BYTES,
            "maximum_summary_seconds_per_recording":MAX_SUMMARY_SECONDS,"minimum_mem_available_bytes":MINIMUM_AVAILABLE_MEMORY_BYTES,
            "minimum_scratch_free_bytes":RUNTIME_SCRATCH_BYTES},compression_versions=False)
        del inventory_evidence
        old,decode_digest=_read_report(decode_path)
        keys={"contract_revision","purpose","batch_id","status","registration_sha256","source_specification_sha256","preserved_inventory_report_sha256","selected_topics","reader_implementation","selected_payload_decoding_enabled","selected_chunk_crc_validation_enabled","technical_recording_count","independent_outing_count","geometry_readiness_assessed","residual_profiles_constructed","numeric_conditions_exported","reference_independence_proven","model_fitted","roles_assigned","raw_cache_deletion_authorized","runtime_versions","runtime_source_sha256","resources_at_start","execution_limits","recordings","interpretation"}
        if (not isinstance(old,dict) or set(old)!=keys or old["contract_revision"]!=decoder.DECODE_REVISION or
                old["purpose"]!="development_only_recording_decode_check" or old["status"]!="complete" or
                old["batch_id"]!=registration["batch_id"] or old["registration_sha256"]!=digest or
                old["source_specification_sha256"]!=registration["source_specification_sha256"] or
                old["preserved_inventory_report_sha256"]!=inventory_digest or old["selected_topics"]!=topics or
                old["reader_implementation"]!=decoder.READER_IMPLEMENTATION or
                type(old["technical_recording_count"]) is not int or old["technical_recording_count"]!=len(old_inventory) or
                old["independent_outing_count"] is not None or not _sha256(old["runtime_source_sha256"])):
            _fail()
        for key in ("selected_payload_decoding_enabled","selected_chunk_crc_validation_enabled"):
            if old[key] is not True:
                _fail()
        for key in ("geometry_readiness_assessed","residual_profiles_constructed","numeric_conditions_exported","reference_independence_proven","model_fitted","roles_assigned","raw_cache_deletion_authorized"):
            if old[key] is not False:
                _fail()
        legacy_limit_keys=("maximum_selected_topics","maximum_messages_per_topic","maximum_selected_messages_per_recording",
            "maximum_selected_chunk_bytes","maximum_index_database_bytes","maximum_selected_schema_bytes","maximum_selected_schema_count",
            "maximum_selected_channel_count","maximum_selected_payload_bytes","maximum_decode_seconds_per_recording",
            "maximum_preserved_inventory_bytes","minimum_mem_available_bytes","minimum_scratch_free_bytes")
        limits=_limits()
        _evidence_metadata(old,{key:limits[key] for key in legacy_limit_keys})
        if not isinstance(old["recordings"],list) or len(old["recordings"])!=len(old_inventory):
            _fail()
        for row,inv,identity,declaration in zip(old["recordings"],old_inventory,registration["recordings"],specification["recordings"]):
            if (not isinstance(row,dict) or set(row)!={"recording_id","raw_sha256","size_bytes","source_declaration_status","status","failure_code","invalidation_codes","reader_failure_context","decode_check"} or
                    any(type(row[k]) is not type(identity[k]) or row[k]!=identity[k] for k in ("recording_id","raw_sha256","size_bytes")) or
                    row["status"]!="complete" or row["failure_code"] is not None or row["invalidation_codes"]!=[] or row["reader_failure_context"] is not None or
                    canonical(row["source_declaration_status"])!=canonical(source_declaration_status(declaration["source"])) or
                    canonical(inv["source_declaration_status"])!=canonical(row["source_declaration_status"])):
                _fail()
            schemas,selected,totals=_advertised_selection(inv["inventory"],topics)
            check=row["decode_check"]
            if not isinstance(check,dict) or set(check)!={"summary_crc_status","indexed_chunk_count","index_ranges_and_unique_offsets_validated","summary_index_listing_in_physical_order","selected_indexed_chunk_count","skipped_indexed_chunk_count","selected_chunks_without_channel_indexes","completed_selected_chunk_count","selected_chunk_crc","decoded_selected_message_count","selected_payload_bytes_processed","channel_versions","topics"}:
                _fail()
            versions=[{**{k:c[k] for k in ("channel_id","schema_id","topic","message_encoding","advertised_message_count")},"schema_name":schemas[c["schema_id"]]["name"],"schema_encoding":schemas[c["schema_id"]]["encoding"],"schema_data_sha256":schemas[c["schema_id"]]["data_sha256"],"decoded_message_count":c["advertised_message_count"]} for _,c in sorted(selected.items())]
            expected_topics=[{"topic":topic,"advertised_message_count":totals[topic],"decoded_message_count":totals[topic],"channel_version_count":sum(c["topic"]==topic for c in selected.values())} for topic in topics]
            numeric=("indexed_chunk_count","selected_indexed_chunk_count","skipped_indexed_chunk_count","selected_chunks_without_channel_indexes","completed_selected_chunk_count","decoded_selected_message_count","selected_payload_bytes_processed")
            crc=check["selected_chunk_crc"]
            if (any(not _integer(check[k]) for k in numeric) or not isinstance(crc,dict) or set(crc)!={"checked_nonzero_count","unavailable_zero_count"} or any(not _integer(v) for v in crc.values()) or
                    canonical(check["channel_versions"])!=canonical(versions) or canonical(check["topics"])!=canonical(expected_topics) or
                    check["decoded_selected_message_count"]!=sum(totals.values()) or check["selected_payload_bytes_processed"]>decoder.MAX_PAYLOAD_BYTES or
                    check["indexed_chunk_count"]!=inv["inventory"]["chunk_index_summary"]["indexed_chunk_count"] or
                    check["selected_indexed_chunk_count"]+check["skipped_indexed_chunk_count"]!=check["indexed_chunk_count"] or
                    check["completed_selected_chunk_count"]!=check["selected_indexed_chunk_count"] or
                    check["selected_chunks_without_channel_indexes"]>check["selected_indexed_chunk_count"] or sum(crc.values())!=check["selected_indexed_chunk_count"] or
                    check["index_ranges_and_unique_offsets_validated"] is not True or type(check["summary_index_listing_in_physical_order"]) is not bool or
                    canonical(check["summary_crc_status"])!=canonical(inv["inventory"]["summary_crc_status"])):
                _fail()
            if any(totals[topic]>limit for topic,limit in TOPIC_LIMITS.items()):
                _fail("scientific_advertised_topic_limit")
            decoder._selection(inv["inventory"],topics)
    except (ValueError,TypeError,KeyError,IndexError) as error:
        if isinstance(error,RecordingIngestionError) and error.code in ("scientific_advertised_topic_limit","readiness_predecessor_report_budget_exceeded","readiness_advertised_container_budget"):
            raise
        _fail()
    return old_inventory,old["recordings"],inventory_digest,decode_digest


def _resources(scratch, *, initial=False):
    memory,free=_available_memory_bytes(),shutil.disk_usage(scratch).free
    if memory<MINIMUM_AVAILABLE_MEMORY_BYTES:
        _fail("available_memory_below_6gib")
    if free<(INITIAL_SCRATCH_BYTES if initial else RUNTIME_SCRATCH_BYTES):
        _fail("insufficient_initial_scratch_space" if initial else "scratch_free_below_runtime_floor")
    return {"mem_available_bytes":memory,"scratch_free_bytes":free}


def _inconclusive(row, code, context=None, *, invalidate=False):
    if row["failure_code"] is None:
        row.update(failure_code=code,reader_failure_context=context)
    elif code!=row["failure_code"] and code not in row["invalidation_codes"]:
        row["invalidation_codes"].append(code)
    row.update(status="inconclusive",readiness=None,condition_availability="not_assessed",recorded_input_causality_checked=False)
    if invalidate:
        row.update(stream_integrity=None,binding_observations=None)


def _limits():
    soft,_=resource.getrlimit(resource.RLIMIT_AS)
    return {"maximum_selected_topics":decoder.MAX_TOPICS,"maximum_messages_per_topic":decoder.MAX_TOPIC_MESSAGES,
        "maximum_selected_messages_per_recording":decoder.MAX_TOTAL_MESSAGES,"maximum_selected_chunk_bytes":decoder.MAX_CHUNK_BYTES,
        "maximum_index_database_bytes":decoder.MAX_INDEX_BYTES,"maximum_selected_schema_bytes":decoder.MAX_SCHEMA_BYTES,
        "maximum_selected_schema_count":decoder.MAX_SCHEMAS,"maximum_selected_channel_count":decoder.MAX_CHANNELS,
        "maximum_selected_payload_bytes":decoder.MAX_PAYLOAD_BYTES,"maximum_decode_seconds_per_recording":decoder.MAX_DECODE_SECONDS,
        "maximum_preserved_inventory_bytes":decoder.MAX_PREDECESSOR_BYTES,"process_address_space_soft_limit_bytes":None if soft==resource.RLIM_INFINITY else soft,
        "minimum_mem_available_bytes":MINIMUM_AVAILABLE_MEMORY_BYTES,"minimum_scratch_free_bytes":RUNTIME_SCRATCH_BYTES,
        "maximum_summary_bytes":MAX_SUMMARY_BYTES,"maximum_summary_record_bytes":MAX_RECORD_BYTES,"maximum_parsed_summary_text_bytes":MAX_TEXT_BYTES,
        "maximum_summary_records_per_section":MAX_SUMMARY_RECORDS,"maximum_summary_seconds":MAX_SUMMARY_SECONDS,
        "maximum_scientific_messages_by_topic":TOPIC_LIMITS.copy(),"maximum_scientific_database_bytes":MAX_SCIENCE_BYTES,
        "maximum_combined_database_bytes":MAX_COMBINED_BYTES,"sqlite_page_cache_bytes":PAGE_CACHE_BYTES,
        "minimum_initial_scratch_free_bytes":INITIAL_SCRATCH_BYTES,"maximum_processing_seconds_per_recording":PROCESSING_SECONDS}


def _same_file(path,state):
    try:
        return file_state(path)==state
    except OSError:
        return False


def _atomic_report(output, report):
    raw=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    if len(raw)>MAX_REPORT_BYTES:
        _fail("bounded_readiness_report_budget_exceeded")
    output.mkdir(parents=True,exist_ok=False)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=output,prefix=".readiness-",delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,output/REPORT_NAME)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if not list(output.iterdir()):
            output.rmdir()
        raise


def run_bounded_readiness(arguments):
    output=_new_output(arguments.output_directory)
    if arguments.output_directory.expanduser().is_symlink():
        _fail("new_absent_output_directory_required")
    topics=decoder.selected_topics(arguments.topic)
    if topics!=sorted(TOPIC_LIMITS):
        _fail("readiness_explicit_three_topics_required")
    specification,registration,digest=_registration(arguments.registration_directory)
    if output.resolve().is_relative_to(arguments.registration_directory.expanduser().resolve()):
        _fail("readiness_output_must_not_change_registration")
    inventories,decodes,inventory_hash,decode_hash=_predecessors(arguments,registration,digest,specification,topics)
    scratch=arguments.scratch_directory.expanduser().resolve(strict=True)
    if not scratch.is_dir():
        _fail("existing_scratch_directory_required")
    start_resources=_resources(scratch,initial=True)
    decoder.check_dependencies()
    try:
        import numpy, zstandard, lz4.frame  # noqa: F401; resolve native dependencies before hashing.
    except ImportError:
        _fail("readiness_mcap_extra_required")
    check_configuration(scratch)
    runtime=_runtime(include_compression=True)
    results,states=[],[]
    for index,(identity,declaration,old_inventory,old_decode) in enumerate(zip(registration["recordings"],specification["recordings"],inventories,decodes),1):
        _resources(scratch,initial=True)
        observations=Observations();observations.phase("raw_hash")
        path=Path(identity["canonical_path_private"])
        LOGGER.info("Verifying raw bytes %d/%d for bounded readiness",index,len(inventories))
        with path.open("rb") as stream:
            before=file_state(stream=stream)
            if before[2]!=identity["size_bytes"] or sha256_stream(stream)!=identity["raw_sha256"]:
                _fail("registered_raw_hash_or_size_changed")
            if file_state(stream=stream)!=before or not _same_file(path,before):
                _fail("file_changed_during_raw_verification")
            row={"recording_id":identity["recording_id"],"raw_sha256":identity["raw_sha256"],"size_bytes":identity["size_bytes"],
                "source_declaration_status":source_declaration_status(declaration["source"]),"status":"complete","failure_code":None,"invalidation_codes":[],
                "reader_failure_context":None,"binding_observations":None,"stream_integrity":None,"readiness":None,
                "condition_availability":"not_assessed","recorded_input_causality_checked":False,"execution_observations":None}
            sink=None
            try:
                _resources(scratch);observations.phase("fresh_summary")
                fresh=read_inventory(stream,before[2])
                if canonical(fresh)!=canonical(old_inventory["inventory"]):
                    _fail("readiness_preserved_inventory_mismatch")
                deadline=time.monotonic()+PROCESSING_SECONDS
                _resources(scratch);observations.phase("descriptor_binding")
                with Workspace(scratch,lambda:_resources(scratch),observations,deadline) as workspace:
                    sink=ScientificSink(workspace)
                    LOGGER.info("Checking selected streams, bindings and bounded science %d/%d; counts only",index,len(inventories))
                    row["stream_integrity"]=decoder.check_decoding(stream,before[2],fresh,topics,scratch,workspace.checkpoint,
                        scientific_sink=sink,processing_deadline=deadline,index_connection=workspace.index)
                    if canonical(row["stream_integrity"])!=canonical(old_decode["decode_check"]):
                        _fail("readiness_preserved_decode_mismatch")
                    observations.phase("scientific_finalize");workspace.checkpoint()
                    row["readiness"],row["condition_availability"],row["recorded_input_causality_checked"]=sink.finalize()
                    if sink.failure_code is not None:
                        _inconclusive(row,sink.failure_code)
            except Exception as error:
                if isinstance(error,RecordingIngestionError) and error.code in ("readiness_preserved_inventory_mismatch","readiness_preserved_decode_mismatch"):
                    raise
                _inconclusive(row,scientific_failure(error),getattr(error,"reader_failure_context",None))
            if sink is not None:
                row["binding_observations"]=sink.binding_observations
            try:
                unchanged=file_state(stream=stream)==before and _same_file(path,before)
            except OSError:
                unchanged=False
            if not unchanged:
                _inconclusive(row,"file_changed_during_readiness",invalidate=True)
        row["execution_observations"]=observations.summary()
        results.append(row);states.append((path,before))
    try:
        _resources(scratch)
    except RecordingIngestionError as error:
        for row in results:
            _inconclusive(row,error.code)
    for row,(path,state) in zip(results,states):
        if not _same_file(path,state):
            _inconclusive(row,"file_changed_before_report_publish",invalidate=True)
    directory=arguments.registration_directory.expanduser().resolve()
    try:
        unchanged={p.name for p in directory.iterdir()}=={REGISTRATION_NAME,SPECIFICATION_NAME} and sha256_file(directory/REGISTRATION_NAME)==digest and sha256_file(directory/SPECIFICATION_NAME)==registration["source_specification_sha256"]
    except OSError:
        unchanged=False
    if not unchanged:
        for row in results:
            _inconclusive(row,"registration_changed_before_report_publish",invalidate=True)
    for path,expected,code in ((arguments.preserved_inventory_report.expanduser(),inventory_hash,"preserved_inventory_changed_before_report_publish"),(arguments.preserved_decode_report.expanduser(),decode_hash,"preserved_decode_changed_before_report_publish")):
        try:
            unchanged=sha256_file(path)==expected
        except OSError:
            unchanged=False
        if not unchanged:
            for row in results:
                _inconclusive(row,code,invalidate=True)
    complete=all(row["status"]=="complete" for row in results)
    report={"contract_revision":REVISION,"purpose":"development_only_bounded_recording_readiness","batch_id":registration["batch_id"],"status":"complete" if complete else "inconclusive",
        "registration_sha256":digest,"source_specification_sha256":registration["source_specification_sha256"],"preserved_inventory_report_sha256":inventory_hash,"preserved_decode_report_sha256":decode_hash,
        "reader_implementation":decoder.READER_IMPLEMENTATION,"scientific_adapter_revision":REVISION,"selected_topics":topics,"selected_chunk_crc_validation_enabled":True,
        "technical_recording_count":len(results),"independent_outing_count":None,"roles_assigned":False,"cohort_lock_created":False,"model_fitted":False,"residual_profiles_constructed":False,"numeric_conditions_exported":False,
        "recorded_input_causality_checked_for_all_recordings":all(row["status"]=="complete" and row["recorded_input_causality_checked"] for row in results),
        "physical_input_availability_proven":False,"reference_independence_proven":False,"raw_cache_deletion_authorized":False,**runtime,
        "execution_limits":_limits(),"resources_at_start":start_resources,"recordings":results,
        "interpretation":"Counts-only development readiness on freshly verified registered bytes. Geometry/H100, SENSOR admission, feature rejection and contiguous support are distinct. RLMB is a map-relative pseudo-reference. Recorded-input checks do not prove physical availability. Unsupported/incomplete science is unknown, not zero. No numeric archive, independent-outing admission, model fit or raw deletion is authorized."}
    _atomic_report(output,report)
    LOGGER.info("Bounded readiness %s; no residual profiles, numeric conditions or model produced",report["status"])
    return report,0 if complete else 3
